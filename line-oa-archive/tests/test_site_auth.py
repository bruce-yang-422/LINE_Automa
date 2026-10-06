"""Real HTTP authentication with isolated SQLite; no LINE network calls."""
import http.client
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import app
import admin_server
import reports
import site_auth

PASSWORD = 'A memorable testing sentence 2026!'
CHANGED = 'A different testing sentence 2026!'


class SiteAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='line-auth-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'instance').mkdir()
        shutil.copyfile(app.BASE_DIR/'schema.sql',self.root/'schema.sql')
        shutil.copytree(app.BASE_DIR/'web',self.root/'web')
        for name,value in [('BASE_DIR',self.root),('DATABASE_PATH',self.root/'test.db')]:
            p=patch.object(app,name,value);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'ADMIN_PUBLIC_HOST':'admin.example.test'},clear=True)
        p.start();self.addCleanup(p.stop)
        app.initialize_database()
        self.server=admin_server.AdminServer(0);self.server.start();self.addCleanup(self.server.close)
        reports.bootstrap_users({'admin@example.test'})
        site_auth.change_password('admin@example.test',None,PASSWORD)
        reports.save_user({'email':'sender@example.test','role':'operator','organization_id':'A','active':True},'admin@example.test')

    def request(self,path,body=None,cookie='',csrf='',extra=None,local=False):
        origin=f'http://127.0.0.1:{self.server.server_port}' if local else 'https://admin.example.test'
        headers={} if local else {'Host':'admin.example.test','X-Forwarded-Proto':'https'}
        if body is not None:headers.update({'Origin':origin,'Content-Type':'application/json'})
        if cookie:headers['Cookie']=cookie
        if csrf:headers['X-CSRF-Token']=csrf
        if extra:
            for key,value in extra.items():
                if value is None:headers.pop(key,None)
                else:headers[key]=value
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            conn.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
            response=conn.getresponse();raw=response.read();info=dict(response.getheaders())
            return response.status,json.loads(raw) if 'application/json' in info.get('Content-Type','') else raw,info
        finally:conn.close()

    def login(self,email='admin@example.test',password=PASSWORD,remember=False):
        code,_,headers=self.request('/api/auth/login',{'email':email,'password':password,'remember':remember})
        self.assertEqual(code,200)
        cookie=headers['Set-Cookie'].split(';')[0]
        code,data,_=self.request('/api/session',cookie=cookie)
        self.assertEqual(code,200)
        return cookie,data['auth']['csrf']

    def test_login_public_assets_and_protected_routes(self):
        self.assertEqual(self.request('/login')[0],200)
        self.assertEqual(self.request('/app.css')[0],200)
        for route in ['/api/session','/api/contacts','/api/settings','/admin.js']:
            self.assertEqual(self.request(route)[0],401)
        code,_,headers=self.request('/')
        self.assertEqual(code,303);self.assertEqual(headers['Location'],'/login')
        self.assertEqual(self.request('/login',extra={'Host':'evil.test'})[0],403)
        self.assertEqual(self.request('/login',extra={'X-Forwarded-Proto':'http'})[0],403)

    def test_cookie_properties_and_opaque_storage(self):
        code,_,headers=self.request('/api/auth/login',{'email':'ADMIN@example.test','password':PASSWORD,'remember':True})
        self.assertEqual(code,200)
        for attribute in ['__Host-line_session=','Secure','HttpOnly','SameSite=Lax','Path=/','Max-Age=2592000']:
            self.assertIn(attribute,headers['Set-Cookie'])
        self.assertNotIn('Domain=',headers['Set-Cookie'])
        raw=headers['Set-Cookie'].split(';')[0].split('=')[1]
        with app.database_connection() as conn:
            saved=conn.execute('SELECT token_hash FROM site_sessions').fetchone()[0]
            password_hash=conn.execute('SELECT password_hash FROM site_credentials').fetchone()[0]
        self.assertEqual(saved,site_auth.digest(raw));self.assertNotIn(PASSWORD,password_hash)
        self.assertTrue(password_hash.startswith('scrypt17$'))

    def test_login_origin_and_post_csrf(self):
        body={'email':'admin@example.test','password':PASSWORD}
        for origin in [None,'https://evil.test','null']:
            self.assertEqual(self.request('/api/auth/login',body,extra={'Origin':origin})[0],403)
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/auth/logout',{},cookie)[0],403)
        self.assertEqual(self.request('/api/auth/logout',{},cookie,'bad')[0],403)
        self.assertEqual(self.request('/api/auth/logout',{},cookie,csrf,{'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/not-found',{},cookie)[0],403)
        self.assertEqual(self.request('/api/auth/logout',{},cookie,csrf)[0],200)
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)

    def test_wrong_password_unknown_and_recipient_cannot_login(self):
        for email in ['admin@example.test','unknown@example.test','recipient@example.test']:
            self.assertEqual(self.request('/api/auth/login',{'email':email,'password':'not the password'})[0],401)
        with self.assertRaises(site_auth.AuthError):site_auth.issue_activation('recipient@example.test','admin@example.test')

    def test_rate_limit_persists_in_database(self):
        with app.database_connection() as conn:
            conn.execute('INSERT INTO site_login_limits VALUES (?,?,10)',('email:'+site_auth.digest('admin@example.test'),int(time.time())))
        with patch.object(site_auth,'derive',side_effect=AssertionError('must rate limit before hashing')):
            self.assertEqual(self.request('/api/auth/login',{'email':'admin@example.test','password':PASSWORD})[0],429)

    def test_expiry_and_idle_timeout(self):
        cookie,_=self.login()
        with app.database_connection() as conn:conn.execute('UPDATE site_sessions SET expires_at=1')
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)
        cookie,_=self.login()
        with app.database_connection() as conn:conn.execute('UPDATE site_sessions SET last_seen=1')
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)

    def test_password_change_revokes_all_sessions(self):
        first,csrf=self.login();second,_=self.login()
        self.assertEqual(self.request('/api/auth/password',{'password':CHANGED,'current_password':'wrong'},first,csrf)[0],400)
        self.assertEqual(self.request('/api/auth/password',{'password':CHANGED,'current_password':PASSWORD},first,csrf)[0],200)
        for cookie in [first,second]:self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)
        self.login(password=CHANGED)

    def test_activation_single_use_expiry_and_rotation(self):
        original=site_auth.issue_activation('sender@example.test','admin@example.test')
        current=site_auth.issue_activation('sender@example.test','admin@example.test')
        self.assertEqual(self.request('/api/auth/activate',{'token':original,'password':PASSWORD})[0],400)
        self.assertEqual(self.request('/api/auth/activate',{'token':current,'password':PASSWORD})[0],200)
        self.assertEqual(self.request('/api/auth/activate',{'token':current,'password':PASSWORD})[0],400)
        self.login(email='sender@example.test')
        expired=site_auth.issue_activation('sender@example.test','admin@example.test')
        with app.database_connection() as conn:conn.execute('UPDATE site_activation SET expires_at=1')
        self.assertEqual(self.request('/api/auth/activate',{'token':expired,'password':PASSWORD})[0],400)

    def test_disable_and_reenable_does_not_restore_session(self):
        site_auth.change_password('sender@example.test',None,PASSWORD)
        cookie,_=self.login(email='sender@example.test')
        data={'email':'sender@example.test','role':'operator','organization_id':'A','active':False}
        reports.save_user(data,'admin@example.test')
        reports.save_user({**data,'active':True},'admin@example.test')
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)

    def test_permissions_preview_and_local_recovery(self):
        site_auth.change_password('sender@example.test',None,PASSWORD)
        cookie,csrf=self.login(email='sender@example.test')
        for route in ['/api/auth/invite','/api/auth/revoke']:
            self.assertEqual(self.request(route,{'email':'admin@example.test'},cookie,csrf)[0],403)
        self.assertEqual(self.request('/api/settings',cookie=cookie)[0],403)
        self.assertEqual(self.request('/api/auth/revoke',{'email':'sender@example.test'},cookie,csrf)[0],200)
        admin,csrf=self.login()
        self.assertEqual(self.request('/api/auth/password',{'password':CHANGED},admin,csrf,{'X-Workspace-View-As':'sender@example.test'})[0],403)
        code,data,_=self.request('/api/auth/invite',{'email':'admin@example.test'},local=True,extra={'Authorization':'Bearer '+self.server.token})
        self.assertEqual(code,200);self.assertTrue(data['url'].startswith('https://admin.example.test/login#setup='))

    def test_org_admin_login_links_are_scoped_to_own_members(self):
        for email,role,org in [('manager@example.test','org_admin','A'),
                               ('helper@example.test','collaborator','A'),
                               ('other@example.test','operator','B'),
                               ('peer@example.test','org_admin','A')]:
            reports.save_user({'email':email,'role':role,'organization_id':org,'active':True},'admin@example.test')
        site_auth.change_password('manager@example.test',None,PASSWORD)
        cookie,csrf=self.login(email='manager@example.test')
        for email in ['sender@example.test','helper@example.test']:
            code,data,_=self.request('/api/auth/invite',{'email':email},cookie,csrf)
            self.assertEqual(code,200)
            self.assertEqual(data['expires_in'],1800)
            self.assertTrue(data['url'].startswith('https://admin.example.test/login#setup='))
            self.assertEqual(self.request('/api/auth/revoke',{'email':email},cookie,csrf)[0],200)
        for email in ['admin@example.test','peer@example.test','manager@example.test','other@example.test']:
            for route in ['/api/auth/invite','/api/auth/revoke']:
                if route.endswith('/revoke') and email=='manager@example.test':continue
                self.assertEqual(self.request(route,{'email':email},cookie,csrf)[0],403)
        with app.database_connection() as conn:
            conn.execute("INSERT INTO organization_members(email,org_id,role,active) VALUES ('sender@example.test','B','operator',1)")
        self.assertEqual(self.request('/api/auth/invite',{'email':'sender@example.test'},cookie,csrf)[0],403)
        self.assertEqual(self.request('/api/auth/invite',{'email':'helper@example.test'},cookie,csrf,
                                      {'X-Workspace-View-As':'helper@example.test'})[0],403)

    def test_database_session_survives_server_restart(self):
        cookie,_=self.login()
        raw=cookie.split('=')[1]
        self.assertEqual(site_auth.session(raw)['email'],'admin@example.test')
        previous=self.server
        other=admin_server.AdminServer(0)
        other.start()
        try:
            self.server=other
            self.assertEqual(self.request('/api/session',cookie=cookie)[0],200)
        finally:
            self.server=previous
            other.close()

    def test_concurrent_activation_only_one_succeeds(self):
        raw=site_auth.issue_activation('sender@example.test','admin@example.test')
        def use():
            try:site_auth.activate(raw,PASSWORD);return True
            except site_auth.AuthError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:use(),range(2)))
        self.assertEqual(results.count(True),1)

    def test_password_validation_and_duplicate_cookie(self):
        for password in ['short','a'*20,'x'*129]:
            with self.assertRaises(site_auth.AuthError):site_auth.hash_password(password)
        cookie,_=self.login()
        self.assertEqual(self.request('/api/session',cookie=cookie+'; '+cookie)[0],401)


if __name__=='__main__':unittest.main()

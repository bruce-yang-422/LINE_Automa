import base64
from datetime import datetime, timezone, timedelta
import http.client
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
from urllib.parse import quote

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import app
import admin_server
import reports

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
USER = 'U' + '1' * 32
OTHER = 'U' + '2' * 32


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='line-workspace-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'instance').mkdir()
        (self.root / 'schema.sql').write_bytes((app.BASE_DIR / 'schema.sql').read_bytes())
        self.image = self.root / 'weather.png'
        self.image.write_bytes(PNG)
        for target, value in [('BASE_DIR', self.root), ('DATABASE_PATH', self.root / 'test.db')]:
            p = patch.object(app, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'LINE_CHANNEL_ACCESS_TOKEN': 'fake-token', 'WEATHER_IMAGE_PATH': str(self.image),
                       'ADMIN_PUBLIC_HOST': 'admin.example.com', 'CF_ACCESS_TEAM_DOMAIN': 'test.cloudflareaccess.com',
                       'CF_ACCESS_AUD': 'aud-test', 'ADMIN_ALLOWED_EMAILS': 'admin@example.com'}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        app.initialize_database()
        reports.bootstrap_users({'admin@example.com'})
        with app.database_connection() as conn:
            conn.executemany("INSERT INTO recipients(recipient_id,kind,company,department) VALUES (?,'user',?,?)",
                             [(USER, 'A', 'Sales'), (OTHER, 'B', 'Sales')])
        for email, company, department in [('alice@example.com', 'A', 'Sales'), ('bob@example.com', 'A', 'Finance'), ('eve@example.com', 'B', 'Sales')]:
            reports.save_user({'email': email, 'role': 'sender', 'company': company, 'department': department, 'active': True,
                               'recipient_id': USER if email.startswith('alice') else ''}, 'admin@example.com')

    def add_report(self, scope='company', company='A', department='Sales', owner_email='alice@example.com'):
        return reports.save({'title': 'Business report', 'category': 'company', 'source_path': str(self.image),
                             'company': company, 'scope': scope, 'department': department, 'owner_email': owner_email}, 'admin@example.com')

    def server(self):
        server = admin_server.AdminServer(0)
        server.start()
        self.addCleanup(server.close)
        p = patch.object(server.remote_access.keys, 'get_signing_key_from_jwt', return_value=SimpleNamespace(key=self.signer.public_key()))
        p.start()
        self.addCleanup(p.stop)
        return server

    def request(self, server, path, email='alice@example.com', payload=None, view_as=None, organization=None, preview_org=None):
        token = jwt.encode({'exp': int(time.time()) + 300, 'iat': int(time.time()) - 1, 'iss': server.remote_access.issuer,
                            'aud': server.remote_access.audience, 'sub': 'test', 'email': email}, self.signer, algorithm='RS256', headers={'kid': 'test'})
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {'Host': server.remote_access.host, 'X-Forwarded-Proto': 'https', 'Origin': 'https://' + server.remote_access.host,
                   'Cf-Access-Jwt-Assertion': token, 'Content-Type': 'application/json'}
        if view_as is not None:
            headers['X-Workspace-View-As'] = view_as
        if organization is not None:
            headers['X-Workspace-Organization'] = quote(organization)
        if preview_org is not None:
            headers['X-Workspace-Preview-Organization'] = quote(preview_org)
        try:
            conn.request('GET' if payload is None else 'POST', path, None if payload is None else json.dumps(payload), headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_report_visibility_by_company_and_direct_api(self):
        company, department, personal, other = self.add_report(), self.add_report('department'), self.add_report('personal'), self.add_report(company='B')
        self.company_admins()
        server = self.server()
        for email, expected in [('a-admin@example.com', {company['report_id'], department['report_id'], personal['report_id']}),
                                ('b-admin@example.com', {other['report_id']}), ('alice@example.com', set())]:
            status, data = self.request(server, '/api/reports', 'admin@example.com', view_as=email)
            self.assertEqual(status, 200)
            self.assertEqual({r['report_id'] for r in data['reports']}, expected)
            for report in (company, department, personal, other):
                status, data = self.request(server, '/api/reports/' + report['report_id'], 'admin@example.com', view_as=email)
                self.assertEqual(status, 200 if report['report_id'] in expected else 404)
                self.assertNotIn('source_path', data)
                if status == 200:
                    self.assertTrue(data['preview'].startswith('data:image/png;base64,'))

    def test_weather_removal_persists_and_restore_does_not_resume_jobs(self):
        server = self.server()
        weather = reports.describe(reports.find('weather'))
        payload = self.scheduled_text()
        payload.pop('message_text')
        payload.update(report_id='weather', report_version=weather['version'], allow_stale=True)
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image', return_value=('https://example.test/frozen.png', PNG)), patch.object(admin_server, 'verify_public_image'):
            server.dispatcher.submit(payload, 'admin@example.com')
        regular = self.add_report()
        self.assertEqual(self.request(server, '/api/reports/remove', 'admin@example.com', {'report_id':'weather'})[0], 200)
        self.assertIsNone(reports.find('weather'))
        self.assertIsNotNone(reports.find(regular['report_id']))
        self.assertEqual(self.image.read_bytes(), PNG)
        job = admin_server.job_status(payload['job_id'])[0]
        self.assertEqual(job['status'], 'cancelled')
        self.assertEqual(job['deliveries'][0]['status'], 'cancelled')
        app.initialize_database()
        self.assertIsNone(reports.find('weather'))
        self.assertEqual(self.request(server, '/api/reports/weather', 'admin@example.com')[0], 404)
        self.assertTrue(self.request(server, '/api/settings', 'admin@example.com')[1]['weather_report_removed'])
        self.assertEqual(self.request(server, '/api/reports/restore-weather', 'admin@example.com', {})[0], 200)
        self.assertIsNotNone(reports.find('weather'))
        self.assertEqual(admin_server.job_status(payload['job_id'])[0]['status'], 'cancelled')
        with patch.object(admin_server, 'send_push') as push:
            server.dispatcher.run(payload['job_id'])
            push.assert_not_called()
        actions = [r['action'] for r in reports.activity()]
        self.assertIn('report.remove', actions)
        self.assertIn('report.restore', actions)

    def test_report_removal_and_restore_require_platform_admin(self):
        reports.save_user({'email':'lead@example.com', 'company':'A', 'role':'company_admin', 'active':True}, 'admin@example.com')
        server = self.server()
        for route in ('/api/reports/remove', '/api/reports/restore-weather'):
            for email in ('alice@example.com', 'lead@example.com'):
                self.assertEqual(self.request(server, route, email, {'report_id':'weather'})[0], 403)
            self.assertEqual(self.request(server, route, 'admin@example.com', {'report_id':'weather'}, view_as='lead@example.com')[0], 403)
        self.assertIsNotNone(reports.find('weather'))
        regular = self.add_report()
        self.assertEqual(self.request(server, '/api/reports/remove', 'admin@example.com', {'report_id':regular['report_id']})[0], 200)
        self.assertIsNone(reports.find(regular['report_id']))
        self.assertTrue(self.image.exists())
        reports.remove('weather', 'admin@example.com')
        with patch.dict(os.environ, {'WEATHER_MODULE_ENABLED':'false'}):
            self.assertEqual(self.request(server, '/api/reports/restore-weather', 'admin@example.com', {})[0], 400)
            self.assertTrue(reports.weather_removed())

    def test_contact_without_account_cannot_read_or_modify_administration(self):
        server = self.server()
        for route in ('/api/contacts', '/api/jobs', '/api/settings', '/api/activity'):
            self.assertEqual(self.request(server, route, 'nobody@example.com')[0], 403)
        for route in ('/api/send', '/api/contact', '/api/profiles', '/api/accounts/save', '/api/reports/save', '/api/reports/remove'):
            self.assertEqual(self.request(server, route, 'nobody@example.com', payload={})[0], 403)
        self.assertEqual(self.request(server, '/api/settings', 'admin@example.com')[0], 200)
        self.assertEqual(self.request(server, '/api/reports', 'unlisted@example.com')[0], 403)
        reports.save_user({'email': 'alice@example.com', 'company': 'A', 'role': 'sender', 'active': False}, 'admin@example.com')
        self.assertEqual(self.request(server, '/api/reports')[0], 403)

    def test_admin_sender_preview_is_scoped_readonly_and_revalidated(self):
        mine, other = self.add_report('personal'), self.add_report(company='B')
        server = self.server()
        def preview(path, payload=None):
            return self.request(server, path, 'admin@example.com', payload, 'alice@example.com')
        status, session = preview('/api/session')
        self.assertEqual(status, 200)
        self.assertTrue(session['preview'])
        self.assertEqual(session['principal'], 'admin@example.com')
        self.assertEqual(session['identity'], 'alice@example.com')
        self.assertEqual(session['role'], 'sender')
        # A sender sees only granted reports; none are granted here.
        self.assertEqual({r['report_id'] for r in preview('/api/reports')[1]['reports']}, set())
        self.assertEqual(preview('/api/reports/' + mine['report_id'])[0], 404)
        self.assertEqual(preview('/api/reports/' + other['report_id'])[0], 404)
        # Senders may read their scoped contacts and jobs; admin pages stay closed and the preview never writes.
        for path in ('/api/settings', '/api/view-options'):
            self.assertEqual(preview(path)[0], 403)
        for path in ('/api/send', '/api/contact', '/api/accounts/save'):
            self.assertEqual(preview(path, {})[0], 403)
        self.assertEqual(self.request(server, '/api/session', view_as='admin@example.com')[0], 403)
        self.assertEqual(self.request(server, '/api/view-options')[0], 403)
        self.assertEqual(self.request(server, '/api/settings', 'admin@example.com')[0], 200)
        choices = self.request(server, '/api/view-options', 'admin@example.com')[1]['users']
        self.assertEqual({u['email'] for u in choices}, {'alice@example.com','bob@example.com','eve@example.com'})
        reports.save_user({'email':'alice@example.com','role':'sender','company':'A','active':False},'admin@example.com')
        self.assertEqual(preview('/api/reports')[0], 403)
        reports.save_user({'email':'admin2@example.com','role':'administrator','active':True},'本機管理員')
        reports.save_user({'email':'admin@example.com','role':'sender','company':'A','active':True},'本機管理員')
        self.assertEqual(self.request(server, '/api/session', 'admin@example.com', view_as='bob@example.com')[0], 403)

    def test_last_admin_and_bootstrap_do_not_restore_revoked_permissions(self):
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'admin@example.com', 'role': 'sender', 'company': 'A', 'active': True}, '本機管理員')
        reports.save_user({'email': 'admin2@example.com', 'role': 'administrator', 'active': True}, '本機管理員')
        reports.save_user({'email': 'admin@example.com', 'role': 'sender', 'company': 'A', 'active': False}, '本機管理員')
        reports.bootstrap_users({'admin@example.com'})
        self.assertIsNone(reports.account('admin@example.com'))
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'invalid', 'role': 'sender', 'active': True}, 'admin2@example.com')

    def test_employee_role_is_rejected_and_legacy_rows_are_removed(self):
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'legacy@example.com', 'role': 'employee', 'company': 'A', 'active': True}, 'admin@example.com')
        with self.assertRaises(ValueError):
            reports.save_membership({'email': 'alice@example.com', 'org_id': 'A', 'role': 'employee', 'active': True}, 'admin@example.com')
        # Simulate a database created before the role was removed, whose CHECK constraints still allowed it.
        with app.database_connection() as conn:
            conn.execute('PRAGMA ignore_check_constraints=ON')
            conn.execute("INSERT INTO workspace_users(email,role,company,active) VALUES ('legacy@example.com','employee','A',1)")
            conn.execute("INSERT INTO site_credentials(email,password_hash,changed_at) VALUES ('legacy@example.com','x',0)")
            conn.execute("INSERT INTO workspace_users(email,role,company,active) VALUES ('both@example.com','employee','A',1)")
            conn.execute("INSERT INTO organization_members(email,org_id,role,active) VALUES ('both@example.com','A','employee',1),('both@example.com','B','sender',1)")
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM workspace_users WHERE email='legacy@example.com'").fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM site_credentials WHERE email='legacy@example.com'").fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM organization_members WHERE role='employee'").fetchone()[0], 0)
            # An account that still operates in another organization keeps that membership.
            self.assertEqual(conn.execute("SELECT org_id,role FROM organization_members WHERE email='both@example.com'").fetchall(), [('B', 'sender')])

    def scheduled_text(self, stamp=None):
        return {'job_id':str(uuid4()), 'audience':'selected', 'ids':[USER], 'message_text':'Meeting reminder',
                'scheduled_at':(stamp or datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}

    def company_admins(self):
        for company in ('A', 'B'):
            reports.save_user({'email':company.lower()+'-admin@example.com','role':'company_admin','company':company,'active':True}, 'admin@example.com')

    def test_multiple_organization_roles_switch_and_revoke(self):
        self.company_admins()
        own,other=self.add_report(),self.add_report(company='B')
        server=self.server()
        def get(path,org):
            return self.request(server,path,'a-admin@example.com',organization=org)
        self.assertEqual(get('/api/session','A')[1]['role'],'company_admin')
        self.assertEqual(get('/api/session','B')[0],403)
        self.assertEqual(get('/api/reports','B')[0],403)
        self.assertEqual(get('/api/reports/'+own['report_id'],'B')[0],403)
        self.assertEqual(get('/api/contacts','B')[0],403)
        self.assertEqual(get('/api/session','not-a-member')[0],403)
        self.assertEqual(self.request(server,'/api/memberships/save','a-admin@example.com',{},organization='A')[0],403)
        reports.save_membership({'email':'a-admin@example.com','org_id':'B','role':'company_admin','active':True},'admin@example.com')
        payload=self.scheduled_text();payload['ids']=[OTHER]
        with patch.object(admin_server,'load_settings'):
            self.assertEqual(self.request(server,'/api/send','a-admin@example.com',payload,organization='B')[0],202)
        reports.save_membership({'email':'a-admin@example.com','org_id':'B','role':'company_admin','active':False},'admin@example.com')
        self.assertEqual(get('/api/session','B')[0],403)
        with patch.object(server.dispatcher.pool,'submit'):
            server.dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server,'send_push') as send:
            server.dispatcher.run(payload['job_id']);send.assert_not_called()

    def test_organization_rename_modules_and_deactivation(self):
        self.company_admins()
        source=self.add_report()
        config={'org_id':'A','name':'登山俱樂部','kind':'club','active':True,'reports_enabled':False,'messaging_enabled':False,'weather_enabled':False}
        reports.save_organization(config,'admin@example.com')
        user=reports.account('a-admin@example.com')
        self.assertEqual(user['company'],'A')
        self.assertEqual(user['organization_name'],'登山俱樂部')
        self.assertFalse(reports.can_view(reports.find(source['report_id']),user))
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with self.assertRaises(ValueError):
            dispatcher.submit(self.scheduled_text(),'a-admin@example.com',organization='A')
        config['weather_enabled']=True
        reports.save_organization(config,'admin@example.com')
        self.assertTrue(reports.can_view(reports.find('weather'),reports.account('a-admin@example.com')))
        config['active']=False
        reports.save_organization(config,'admin@example.com')
        self.assertIsNone(reports.account('alice@example.com','A'))
        app.initialize_database()
        self.assertIsNone(reports.account('alice@example.com','A'))

    def test_restart_does_not_recreate_deleted_organizations_or_memberships(self):
        with app.database_connection() as conn:
            conn.execute('DELETE FROM organization_members')
            conn.execute('DELETE FROM organizations')
        app.initialize_database()
        self.assertEqual(reports.organizations(), [])
        self.assertEqual(reports.memberships(), [])
        self.assertIsNone(reports.account('alice@example.com', 'A'))

    def test_company_admin_api_isolation_and_privilege_escalation(self):
        self.company_admins()
        own, other = self.add_report('personal'), self.add_report(company='B')
        server = self.server()
        def request(path, payload=None, view=None):
            return self.request(server, path, 'a-admin@example.com', payload, view)
        self.assertEqual({r['report_id'] for r in request('/api/reports')[1]['reports']}, {own['report_id']})
        for report_id in ('weather', other['report_id']):
            self.assertEqual(request('/api/reports/'+report_id)[0],404)
        contacts = request('/api/contacts')[1]['contacts']
        self.assertEqual([r['recipient_id'] for r in contacts], [USER])
        self.assertNotIn('weather_subscribed', contacts[0])
        settings = request('/api/settings')[1]
        self.assertTrue(all(u['company']=='A' and u['role']!='administrator' for u in settings['users']))
        for path in ('/api/reports/save','/api/reports/remove'):
            self.assertEqual(request(path, {})[0],403)
        self.assertEqual(request('/api/accounts/save', {'email': 'invalid'})[0],400)
        for change in ({'id':OTHER,'alias':'stolen'}, {'id':USER,'company':'B','alias':'moved'}, {'id':USER,'subscribed':True,'alias':'weather'}):
            self.assertEqual(request('/api/contact',change)[0],400)
        self.assertEqual(request('/api/contact',{'id':USER,'alias':'A contact','department':'Sales'})[0],200)
        self.assertEqual({u['email'] for u in request('/api/view-options')[1]['users']},{'alice@example.com','bob@example.com'})
        self.assertEqual(request('/api/session',view='eve@example.com')[0],403)
        self.assertEqual(request('/api/session',view='admin@example.com')[0],403)
        self.assertEqual(request('/api/session',view='alice@example.com')[1]['role'],'sender')
        preview = self.request(server,'/api/session','admin@example.com',view_as='a-admin@example.com')
        self.assertEqual(preview[1]['role'],'company_admin')
        self.assertEqual(self.request(server,'/api/contact','admin@example.com',{'id':USER,'alias':'preview'},'a-admin@example.com')[0],403)

    def test_company_jobs_are_scoped_and_rechecked_on_execution(self):
        self.company_admins()
        server = self.server()
        with patch.object(admin_server,'load_settings'), patch.object(admin_server,'publish_image') as publish:
            a = self.scheduled_text()
            self.assertEqual(self.request(server,'/api/send','a-admin@example.com',a)[0],202)
            b = self.scheduled_text();b['ids']=[OTHER]
            self.assertEqual(self.request(server,'/api/send','b-admin@example.com',b)[0],202)
            for payload in (b, dict(self.scheduled_text(), ids=[OTHER]), dict(self.scheduled_text(), image_path=str(self.image))):
                self.assertEqual(self.request(server,'/api/send','a-admin@example.com',payload)[0],400)
            publish.assert_not_called()
        jobs = self.request(server,'/api/jobs','a-admin@example.com')[1]['jobs']
        self.assertEqual([j['job_id'] for j in jobs],[a['job_id']])
        self.assertNotIn('image_path', jobs[0])
        self.assertEqual(self.request(server,'/api/jobs/'+b['job_id'],'a-admin@example.com')[0],404)
        self.assertEqual(self.request(server,'/api/jobs/cancel','a-admin@example.com',{'job_id':b['job_id']})[0],400)
        events = self.request(server,'/api/activity','a-admin@example.com')[1]['events']
        self.assertTrue(events)
        self.assertTrue(all(e['company']=='A' for e in events))
        # Moving the creator to another company invalidates the queued delivery.
        reports.save_user({'email':'a-admin@example.com','role':'company_admin','company':'B','active':True},'admin@example.com')
        with patch.object(server.dispatcher.pool,'submit'):
            server.dispatcher.tick(datetime.fromisoformat(a['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server,'send_push') as send:
            server.dispatcher.run(a['job_id'])
            send.assert_not_called()
        self.assertEqual(admin_server.job_status(a['job_id'])[0]['deliveries'][0]['status'],'cancelled')

    def test_restart_preserves_accounts_and_supports_company_admin(self):
        before = reports.users()
        app.initialize_database()
        app.initialize_database()
        self.assertEqual(reports.users(), before)
        self.company_admins()
        self.assertEqual(reports.account('a-admin@example.com')['role'], 'company_admin')

    def test_company_module_send_rejects_other_modules_and_private_paths(self):
        self.company_admins()
        own, other = self.add_report(), self.add_report(company='B')
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        with patch.object(admin_server,'load_settings'), patch.object(admin_server,'publish_image',return_value=('https://example.test/snapshot.png',PNG)) as publish, patch.object(admin_server,'verify_public_image'):
            for report in (other, reports.describe(reports.find('weather'))):
                payload=self.scheduled_text();del payload['message_text']
                payload.update(report_id=report['report_id'],report_version=report['version'])
                with self.assertRaises(ValueError):
                    dispatcher.submit(payload,'a-admin@example.com')
            publish.assert_not_called()
            payload=self.scheduled_text();del payload['message_text']
            payload.update(report_id=own['report_id'],report_version=own['version'])
            self.assertEqual(dispatcher.submit(payload,'a-admin@example.com')['company'],'A')
            manual=self.scheduled_text();del manual['message_text'];manual['image_path']=str(self.image)
            self.assertEqual(dispatcher.submit(manual,'admin@example.com')['company'],'')
            self.assertEqual(admin_server.job_status(manual['job_id'],reports.account('a-admin@example.com')),[])

    def test_schedules_survive_restart_cancel_and_claim_once(self):
        with patch.object(admin_server, 'load_settings'):
            first = admin_server.Dispatcher()
            payload = self.scheduled_text()
            self.assertEqual(first.submit(payload, 'admin@example.com')['status'], 'scheduled')
            self.assertEqual(first.submit(payload, 'admin@example.com')['job_id'], payload['job_id'])
            first.close()
            second = admin_server.Dispatcher()
            self.addCleanup(second.close)
            self.assertEqual(admin_server.job_status(payload['job_id'])[0]['deliveries'][0]['status'], 'pending')
            with patch.object(second.pool, 'submit') as dispatch:
                second.tick(datetime.fromisoformat(payload['scheduled_at'])-timedelta(seconds=1))
                dispatch.assert_not_called()
                second.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
                second.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=2))
                dispatch.assert_called_once()
            with patch.object(admin_server, 'send_push', return_value='mock-id') as push:
                second.run(payload['job_id'])
                second.run(payload['job_id'])
                push.assert_called_once()
                self.assertEqual(push.call_args.kwargs['text'], 'Meeting reminder')
            cancelled = self.scheduled_text()
            second.submit(cancelled)
            second.cancel(cancelled['job_id'], 'admin@example.com')
            with patch.object(second.pool, 'submit') as dispatch:
                second.tick(datetime.fromisoformat(cancelled['scheduled_at'])+timedelta(seconds=1))
                dispatch.assert_not_called()
            self.assertEqual(admin_server.job_status(cancelled['job_id'])[0]['status'], 'cancelled')

    def test_schedule_expiry_validation_and_revoked_actor(self):
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        with patch.object(admin_server, 'load_settings'), patch.object(dispatcher.pool, 'submit') as dispatch:
            for stamp in ('not-a-date','2030-01-01T10:00:00',datetime.now(timezone.utc).isoformat()):
                payload = self.scheduled_text();payload['scheduled_at']=stamp
                with self.assertRaises(ValueError):
                    dispatcher.submit(payload)
            missed = self.scheduled_text()
            dispatcher.submit(missed)
            dispatcher.tick(datetime.fromisoformat(missed['scheduled_at'])+timedelta(minutes=11))
            self.assertEqual(admin_server.job_status(missed['job_id'])[0]['status'], 'missed')
            dispatch.assert_not_called()
            revoked = self.scheduled_text()
            dispatcher.submit(revoked, 'admin@example.com')
            reports.save_user({'email':'admin2@example.com','role':'administrator','active':True},'本機管理員')
            reports.save_user({'email':'admin@example.com','role':'sender','company':'A','active':True},'本機管理員')
            dispatcher.tick(datetime.fromisoformat(revoked['scheduled_at'])+timedelta(seconds=1))
            with patch.object(admin_server, 'send_push') as push:
                dispatcher.run(revoked['job_id'])
                push.assert_not_called()
            self.assertEqual(admin_server.job_status(revoked['job_id'])[0]['deliveries'][0]['status'], 'cancelled')

    def test_personal_weather_module_not_shared_with_other_admins(self):
        self.company_admins()
        self.assertFalse(reports.can_view(reports.find('weather'), reports.account('a-admin@example.com')))
        with patch.dict(os.environ, {'WEATHER_OWNER_EMAIL':'a-admin@example.com'}):
            self.assertTrue(reports.can_view(reports.find('weather'), reports.account('a-admin@example.com')))
            self.assertFalse(reports.can_view(reports.find('weather'), reports.account('b-admin@example.com')))
        with patch.dict(os.environ, {'WEATHER_MODULE_ENABLED':'false'}):
            self.assertIsNone(reports.find('weather'))

    def test_scheduled_image_uses_confirmed_snapshot(self):
        report = self.add_report()
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        payload = self.scheduled_text()
        del payload['message_text']
        payload.update(report_id=report['report_id'], report_version=report['version'])
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image', return_value=('https://example.test/frozen.png', PNG)), patch.object(admin_server, 'verify_public_image'):
            dispatcher.submit(payload, 'admin@example.com')
        self.image.write_bytes(PNG + b'newer report')
        with patch.object(dispatcher.pool, 'submit'):
            dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server, 'send_push', return_value='mock') as push:
            dispatcher.run(payload['job_id'])
            self.assertEqual(push.call_args.args[2], 'https://example.test/frozen.png')

    def test_report_changed_missing_oversized_and_stale(self):
        report = reports.describe(reports.find('weather'), preview=True)
        self.assertEqual(report['status'], 'ready')
        self.image.write_bytes(PNG + b'changed')
        with self.assertRaisesRegex(ValueError, '已更新'):
            reports.prepare('weather', report['version'])
        self.image.write_bytes(PNG)
        os.utime(self.image, (0, 0))
        with self.assertRaisesRegex(ValueError, '不是今天'):
            reports.prepare('weather', report['version'])
        reports.prepare('weather', report['version'], allow_stale=True)
        self.image.write_bytes(PNG + b'x' * reports.MAX_BYTES)
        self.assertEqual(reports.describe(reports.find('weather'))['status'], 'invalid')
        self.image.unlink()
        self.assertEqual(reports.describe(reports.find('weather'))['status'], 'missing')

    def test_scope_checked_before_publication_and_actor_audited(self):
        report = self.add_report('department')
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        payload = {'job_id': str(uuid4()), 'report_id': report['report_id'], 'report_version': report['version'], 'ids': [OTHER], 'audience': 'selected'}
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image', return_value=('https://example.test/test.png', PNG)) as publish, \
                patch.object(admin_server, 'verify_public_image'), patch.object(dispatcher.pool, 'submit'):
            with self.assertRaisesRegex(ValueError, '範圍'):
                dispatcher.submit(payload, actor='admin@example.com')
            publish.assert_not_called()
            payload['ids'] = [USER]
            job = dispatcher.submit(payload, actor='admin@example.com')
            self.assertEqual(job['actor'], 'admin@example.com')
            self.assertEqual(job['report_title'], 'Business report')
            self.assertEqual(len(job['deliveries']), 1)
            self.assertTrue(any(e['action'] == 'send.create' for e in reports.activity()))
            # Changing recipient scope after submission must cancel, not send.
            with app.database_connection() as conn:
                conn.execute("UPDATE recipients SET company='B' WHERE recipient_id=?", (USER,))
            with patch.object(admin_server, 'send_push') as send:
                dispatcher.run(job['job_id'])
                send.assert_not_called()
            self.assertEqual(admin_server.job_status(job['job_id'])[0]['deliveries'][0]['status'], 'cancelled')

    def test_migration_preserves_original_data_and_is_repeatable(self):
        with app.database_connection() as conn:
            conn.execute("UPDATE recipients SET alias='Saved',weather_subscribed=1 WHERE recipient_id=?", (USER,))
        app.initialize_database()
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT alias,weather_subscribed,company FROM recipients WHERE recipient_id=?', (USER,)).fetchone(), ('Saved', 1, 'A'))

    def test_report_scope_edit_takes_effect_without_restart(self):
        report = self.add_report()
        target = [{'recipient_id': USER, 'company': 'A', 'department': 'Sales'}]
        reports.validate_targets(reports.find(report['report_id']), target)
        reports.save({'report_id': report['report_id'], 'title': 'Private', 'category': 'company', 'source_path': str(self.image),
                      'company': 'A', 'scope': 'department', 'department': 'Finance'}, 'admin@example.com')
        with self.assertRaises(ValueError):
            reports.validate_targets(reports.find(report['report_id']), target)
        self.assertEqual(len(reports.sources()), 2)
        self.assertTrue(any(e['action'] == 'report.update' for e in reports.activity()))

    def test_subscriber_changes_and_image_race_block_publication_or_send(self):
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        report = reports.describe(reports.find('weather'))
        payload = {'job_id': str(uuid4()), 'report_id': 'weather', 'report_version': report['version'], 'ids': [USER], 'audience': 'subscribers'}
        with app.database_connection() as conn:
            conn.execute('UPDATE recipients SET weather_subscribed=1')
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image') as publish:
            with self.assertRaisesRegex(ValueError, '訂閱名單已變更'):
                dispatcher.submit(payload)
            publish.assert_not_called()
        payload['audience'] = 'selected'
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image', return_value=('https://example.test/image.png', PNG+b'changed')), patch.object(admin_server, 'verify_public_image') as verify:
            with self.assertRaisesRegex(ValueError, '準備時已變更'):
                dispatcher.submit(payload)
            verify.assert_not_called()
            self.assertEqual(admin_server.job_status(payload['job_id']), [])


if __name__ == '__main__':
    unittest.main()

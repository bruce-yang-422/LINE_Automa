import base64
from datetime import datetime, timezone, timedelta
import http.client
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from urllib.parse import quote

from login_helper import session_headers
from oa_fixture import register_oa, use_oa
import app
import admin_server
import channels
import reports

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
USER = 'U' + '1' * 32
OTHER = 'U' + '2' * 32
# 每個組織各有一個 OA；USER 屬於組織 A 的 OA，OTHER 屬於組織 B 的 OA。
CHANNEL_A = 'a' * 32
CHANNEL_B = 'b' * 32


class WorkspaceTests(unittest.TestCase):
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
        p = patch.dict(os.environ, {'PUBLIC_BASE_URL': 'https://reports.example.test', 'ADMIN_PUBLIC_HOST': 'admin.example.com'}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        app.initialize_database()
        reports.bootstrap_users({'admin@example.com'})
        register_oa('A', channel_id=CHANNEL_A, bot='U' + 'a' * 32, name='OA A')
        register_oa('B', channel_id=CHANNEL_B, bot='U' + 'c' * 32, name='OA B')
        use_oa(self, CHANNEL_A)
        with app.database_connection() as conn:
            conn.executemany("INSERT INTO recipients(channel_id,recipient_id,kind,organization_id,department) VALUES (?,?,'user',?,?)",
                             [(CHANNEL_A, USER, 'A', 'Sales'), (CHANNEL_B, OTHER, 'B', 'Sales')])
        for email, organization_id, department in [('alice@example.com', 'A', 'Sales'), ('bob@example.com', 'A', 'Finance'), ('eve@example.com', 'B', 'Sales')]:
            reports.save_user({'email': email, 'role': 'operator', 'organization_id': organization_id, 'department': department, 'active': True}, 'admin@example.com')

    def server(self):
        server = admin_server.AdminServer(0)
        server.start()
        self.addCleanup(server.close)
        return server

    def request(self, server, path, email='alice@example.com', payload=None, view_as=None, organization=None, preview_org=None, channel=CHANNEL_A):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {**session_headers(email, server.public_host), 'Content-Type': 'application/json'}
        if channel:
            headers['X-Line-Channel'] = channel
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

    def test_contact_without_account_cannot_read_or_modify_administration(self):
        server = self.server()
        for route in ('/api/contacts', '/api/jobs', '/api/settings', '/api/activity'):
            self.assertEqual(self.request(server, route, 'nobody@example.com')[0], 401)
        for route in ('/api/send', '/api/contact', '/api/profiles', '/api/accounts/save'):
            self.assertEqual(self.request(server, route, 'nobody@example.com', payload={})[0], 401)
        self.assertEqual(self.request(server, '/api/settings', 'admin@example.com')[0], 200)
        self.assertEqual(self.request(server, '/api/contacts', 'unlisted@example.com')[0], 401)
        reports.save_user({'email': 'alice@example.com', 'organization_id': 'A', 'role': 'operator', 'active': False}, 'admin@example.com')
        self.assertEqual(self.request(server, '/api/contacts')[0], 401)

    def test_admin_sender_preview_is_scoped_readonly_and_revalidated(self):
        server = self.server()
        def preview(path, payload=None):
            return self.request(server, path, 'admin@example.com', payload, 'alice@example.com')
        status, session = preview('/api/session')
        self.assertEqual(status, 200)
        self.assertTrue(session['preview'])
        self.assertEqual(session['principal'], 'admin@example.com')
        self.assertEqual(session['identity'], 'alice@example.com')
        self.assertEqual(session['role'], 'operator')
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
        reports.save_user({'email':'alice@example.com','role':'operator','organization_id':'A','active':False},'admin@example.com')
        self.assertEqual(preview('/api/contacts')[0], 403)
        reports.save_user({'email':'admin2@example.com','role':'platform_admin','active':True},'本機管理員')
        reports.save_user({'email':'admin@example.com','role':'operator','organization_id':'A','active':True},'本機管理員')
        self.assertEqual(self.request(server, '/api/session', 'admin@example.com', view_as='bob@example.com')[0], 403)

    def test_last_admin_and_bootstrap_do_not_restore_revoked_permissions(self):
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'admin@example.com', 'role': 'operator', 'organization_id': 'A', 'active': True}, '本機管理員')
        reports.save_user({'email': 'admin2@example.com', 'role': 'platform_admin', 'active': True}, '本機管理員')
        reports.save_user({'email': 'admin@example.com', 'role': 'operator', 'organization_id': 'A', 'active': False}, '本機管理員')
        reports.bootstrap_users({'admin@example.com'})
        self.assertIsNone(reports.account('admin@example.com'))
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'invalid', 'role': 'operator', 'active': True}, 'admin2@example.com')

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            reports.save_user({'email': 'guest@example.com', 'role': 'guest', 'organization_id': 'A', 'active': True}, 'admin@example.com')
        with self.assertRaises(ValueError):
            reports.save_membership({'email': 'alice@example.com', 'org_id': 'A', 'role': 'guest', 'active': True}, 'admin@example.com')

    def scheduled_text(self, stamp=None):
        return {'job_id':str(uuid4()), 'audience':'selected', 'ids':[USER], 'message_text':'Meeting reminder',
                'scheduled_at':(stamp or datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}

    def org_admins(self):
        for organization_id in ('A', 'B'):
            reports.save_user({'email':organization_id.lower()+'-admin@example.com','role':'org_admin','organization_id':organization_id,'active':True}, 'admin@example.com')

    def test_multiple_organization_roles_switch_and_revoke(self):
        self.org_admins()
        server=self.server()
        def get(path,org):
            return self.request(server,path,'a-admin@example.com',organization=org)
        self.assertEqual(get('/api/session','A')[1]['role'],'org_admin')
        self.assertEqual(get('/api/session','B')[0],403)
        self.assertEqual(get('/api/contacts','B')[0],403)
        self.assertEqual(get('/api/session','not-a-member')[0],403)
        self.assertEqual(self.request(server,'/api/organizations/save','a-admin@example.com',{},organization='A')[0],403)
        reports.save_membership({'email':'a-admin@example.com','org_id':'B','role':'org_admin','active':True},'admin@example.com')
        payload=self.scheduled_text();payload['ids']=[OTHER]
        with patch.object(admin_server,'load_settings'):
            self.assertEqual(self.request(server,'/api/send','a-admin@example.com',payload,organization='B',channel=CHANNEL_B)[0],202)
        reports.save_membership({'email':'a-admin@example.com','org_id':'B','role':'org_admin','active':False},'admin@example.com')
        self.assertEqual(get('/api/session','B')[0],403)
        with patch.object(server.dispatcher.pool,'submit'):
            server.dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server,'send_push') as send, channels.use(CHANNEL_B):
            server.dispatcher.run(payload['job_id']);send.assert_not_called()

    def test_organization_rename_modules_and_deactivation(self):
        self.org_admins()
        config={'org_id':'A','name':'登山俱樂部','kind':'club','active':True,'messaging_enabled':False}
        reports.save_organization(config,'admin@example.com')
        user=reports.account('a-admin@example.com')
        self.assertEqual(user['organization_id'],'A')
        self.assertEqual(user['organization_name'],'登山俱樂部')
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with self.assertRaises(ValueError):
            dispatcher.submit(self.scheduled_text(),'a-admin@example.com',organization='A')
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

    def test_org_admin_api_isolation_and_privilege_escalation(self):
        self.org_admins()
        server = self.server()
        def request(path, payload=None, view=None):
            return self.request(server, path, 'a-admin@example.com', payload, view)
        contacts = request('/api/contacts')[1]['contacts']
        self.assertEqual([r['recipient_id'] for r in contacts], [USER])
        settings = request('/api/settings')[1]
        self.assertTrue(all(u['organization_id']=='A' and u['role']!='platform_admin' for u in settings['users']))
        self.assertEqual(request('/api/accounts/save', {'email': 'invalid'})[0],400)
        for change in ({'id':OTHER,'custom_name':'stolen'}, {'id':USER,'organization_id':'B','custom_name':'moved'}):
            self.assertEqual(request('/api/contact',change)[0],400)
        self.assertEqual(request('/api/contact',{'id':USER,'custom_name':'A contact','department':'Sales'})[0],200)
        self.assertEqual({u['email'] for u in request('/api/view-options')[1]['users']},{'alice@example.com','bob@example.com'})
        self.assertEqual(request('/api/session',view='eve@example.com')[0],403)
        self.assertEqual(request('/api/session',view='admin@example.com')[0],403)
        self.assertEqual(request('/api/session',view='alice@example.com')[1]['role'],'operator')
        preview = self.request(server,'/api/session','admin@example.com',view_as='a-admin@example.com')
        self.assertEqual(preview[1]['role'],'org_admin')
        self.assertEqual(self.request(server,'/api/contact','admin@example.com',{'id':USER,'custom_name':'preview'},'a-admin@example.com')[0],403)

    def test_company_jobs_are_scoped_and_rechecked_on_execution(self):
        self.org_admins()
        server = self.server()
        with patch.object(admin_server,'load_settings'), patch.object(admin_server,'publish_image') as publish:
            a = self.scheduled_text()
            self.assertEqual(self.request(server,'/api/send','a-admin@example.com',a)[0],202)
            b = self.scheduled_text();b['ids']=[OTHER]
            self.assertEqual(self.request(server,'/api/send','b-admin@example.com',b,channel=CHANNEL_B)[0],202)
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
        self.assertTrue(all(e['organization_id']=='A' for e in events))
        # Moving the creator to another organization_id invalidates the queued delivery.
        reports.save_user({'email':'a-admin@example.com','role':'org_admin','organization_id':'B','active':True},'admin@example.com')
        with patch.object(server.dispatcher.pool,'submit'):
            server.dispatcher.tick(datetime.fromisoformat(a['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server,'send_push') as send:
            server.dispatcher.run(a['job_id'])
            send.assert_not_called()
        self.assertEqual(admin_server.job_status(a['job_id'])[0]['deliveries'][0]['status'],'cancelled')

    def test_restart_preserves_accounts_and_supports_org_admin(self):
        before = reports.users()
        app.initialize_database()
        app.initialize_database()
        self.assertEqual(reports.users(), before)
        self.org_admins()
        self.assertEqual(reports.account('a-admin@example.com')['role'], 'org_admin')

    def test_manual_image_send_is_platform_only(self):
        self.org_admins()
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        with patch.object(admin_server,'load_settings'), patch.object(admin_server,'publish_image',return_value=('https://example.test/snapshot.png',PNG)), patch.object(admin_server,'verify_public_image'):
            manual=self.scheduled_text();del manual['message_text'];manual['image_path']=str(self.image)
            with self.assertRaises(ValueError):
                dispatcher.submit(dict(manual, job_id=str(uuid4())),'a-admin@example.com')
            self.assertEqual(dispatcher.submit(manual,'admin@example.com')['organization_id'],'')
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
            reports.save_user({'email':'admin2@example.com','role':'platform_admin','active':True},'本機管理員')
            reports.save_user({'email':'admin@example.com','role':'collaborator','organization_id':'A','active':True},'本機管理員')
            dispatcher.tick(datetime.fromisoformat(revoked['scheduled_at'])+timedelta(seconds=1))
            with patch.object(admin_server, 'send_push') as push:
                dispatcher.run(revoked['job_id'])
                push.assert_not_called()
            self.assertEqual(admin_server.job_status(revoked['job_id'])[0]['deliveries'][0]['status'], 'cancelled')

    def test_scheduled_image_uses_confirmed_snapshot(self):
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        payload = self.scheduled_text()
        del payload['message_text']
        payload['image_path'] = str(self.image)
        with patch.object(admin_server, 'load_settings'), patch.object(admin_server, 'publish_image', return_value=('https://example.test/frozen.png', PNG)), patch.object(admin_server, 'verify_public_image'):
            dispatcher.submit(payload, 'admin@example.com')
        self.image.write_bytes(PNG + b'newer report')
        with patch.object(dispatcher.pool, 'submit'):
            dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
        with patch.object(admin_server, 'send_push', return_value='mock') as push:
            dispatcher.run(payload['job_id'])
            self.assertEqual(push.call_args.args[2], 'https://example.test/frozen.png')

    def test_actor_audited_and_recipient_move_cancels(self):
        self.org_admins()
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        payload = self.scheduled_text()
        with patch.object(admin_server, 'load_settings'), patch.object(dispatcher.pool, 'submit'):
            job = dispatcher.submit(payload, actor='a-admin@example.com', organization='A')
            self.assertEqual(job['actor'], 'a-admin@example.com')
            self.assertEqual(job['report_title'], '文字訊息：Meeting reminder')
            self.assertEqual(len(job['deliveries']), 1)
            self.assertTrue(any(e['action'] == 'send.create' for e in reports.activity()))
            dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
            # Moving the recipient to another organization after submission must cancel, not send.
            with app.database_connection() as conn:
                conn.execute("UPDATE recipients SET organization_id='B' WHERE recipient_id=?", (USER,))
            with patch.object(admin_server, 'send_push') as send:
                dispatcher.run(job['job_id'])
                send.assert_not_called()
            self.assertEqual(admin_server.job_status(job['job_id'])[0]['deliveries'][0]['status'], 'cancelled')

    def test_migration_preserves_original_data_and_is_repeatable(self):
        with app.database_connection() as conn:
            conn.execute("UPDATE recipients SET custom_name='Saved' WHERE recipient_id=?", (USER,))
        app.initialize_database()
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT custom_name,organization_id FROM recipients WHERE recipient_id=?', (USER,)).fetchone(), ('Saved', 'A'))



if __name__ == '__main__':
    unittest.main()

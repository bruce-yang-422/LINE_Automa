import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import base64
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
import app
import reports
import composer
import admin_server
import test_workspace as workspace
from test_workspace import USER, OTHER, PNG


SENDER = 'sender@example.com'
THIRD = 'U' + '3' * 32
GROUP = 'C' + '4' * 32


class SenderTests(unittest.TestCase):
    setUpClass = classmethod(workspace.WorkspaceTests.setUpClass.__func__)
    setUp = workspace.WorkspaceTests.setUp
    request = workspace.WorkspaceTests.request
    server = workspace.WorkspaceTests.server
    add_report = workspace.WorkspaceTests.add_report
    scheduled_text = workspace.WorkspaceTests.scheduled_text

    def setup_sender(self):
        reports.save_user({'email':SENDER,'role':'sender','company':'A','active':True},'admin@example.com')
        with app.database_connection() as conn:
            conn.executemany("INSERT INTO recipients(recipient_id,kind,company,department) VALUES (?,?,'A','Finance')",[(THIRD,'user'),(GROUP,'group')])
        self.source = self.add_report()
        self.scope = reports.save_dispatch_scope({'company':'A','name':'Sales','kind':'department','department':'Sales','active':True},'admin@example.com')['scope_id']
        self.grant = {'email':SENDER,'company':'A','scope_ids':[self.scope],'report_ids':[self.source['report_id']], 'messaging':True,'reports':True,'weather':False}
        reports.save_grant(self.grant,'admin@example.com')
        return reports.account(SENDER)

    def test_contact_without_account_cannot_login_but_other_org_operator_can(self):
        server = self.server()
        for route in ('/api/session','/api/reports','/api/organizations'):
            self.assertEqual(self.request(server,route,'nobody@example.com')[0],403)
        reports.save_user({'email':'carol@example.com','role':'sender','company':'B','active':True},'admin@example.com')
        status,session = self.request(server,'/api/session','carol@example.com')
        self.assertEqual(status,200)
        self.assertEqual(session['user']['company'],'B')
        self.assertEqual([m['org_id'] for m in session['memberships']],['B'])
        self.assertEqual(self.request(server,'/api/session','carol@example.com',organization='A')[0],403)

    def test_sender_default_deny_and_union_of_scopes(self):
        user = self.setup_sender()
        server = self.server()
        # 丙級可直接看見所屬組織/OA 的聯絡對象
        rows = self.request(server, '/api/contacts', SENDER)[1]['contacts']
        self.assertEqual({r['recipient_id'] for r in rows}, {USER, THIRD, GROUP})
        # 丙級可直接發送所屬組織的文字訊息
        with patch.object(admin_server, 'load_settings'):
            self.assertEqual(self.request(server, '/api/send', SENDER, self.scheduled_text())[0], 202)
        # 發送範圍建立驗證
        for invalid in (OTHER,):
            with self.assertRaises(ValueError):
                reports.save_dispatch_scope({'company':'A','name':'Bad','kind':'group','recipient_ids':[invalid],'active':True},'admin@example.com')

    def test_sender_api_boundary_and_direct_report_access(self):
        self.setup_sender()
        other = self.add_report(company='B')
        ungranted = self.add_report()
        server = self.server()
        # 丙級可查看本組織的報告
        self.assertEqual({r['report_id'] for r in self.request(server,'/api/reports',SENDER)[1]['reports']},{self.source['report_id'], ungranted['report_id']})
        # 丙級無法查看其他組織報告或未授權的客製模組（weather）
        for rid in (other['report_id'], 'weather'):
            self.assertEqual(self.request(server,'/api/reports/'+rid,SENDER)[0],404)
        for route in ('/api/settings','/api/view-options'):
            self.assertEqual(self.request(server,route,SENDER)[0],403)
        for route in ('/api/accounts/save','/api/memberships/save','/api/sender-grants/save','/api/dispatch-scopes/save','/api/reports/save'):
            self.assertEqual(self.request(server,route,SENDER,{})[0],403)
        with patch.object(admin_server,'load_settings'):
            for ids in ([OTHER],):
                self.assertEqual(self.request(server,'/api/send',SENDER,{**self.scheduled_text(),'ids':ids})[0],400)
            self.assertEqual(self.request(server,'/api/send',SENDER,{**self.scheduled_text(),'image_path':str(self.image)})[0],400)
            self.assertEqual(self.request(server,'/api/send',SENDER,self.scheduled_text())[0],202)

    def test_preview_is_readonly_and_grants_are_rechecked(self):
        self.setup_sender()
        server = self.server()
        self.assertEqual(self.request(server,'/api/session','admin@example.com',view_as=SENDER)[1]['role'],'sender')
        self.assertEqual(self.request(server,'/api/send','admin@example.com',self.scheduled_text(),view_as=SENDER)[0],403)
        with app.database_connection() as conn:
            conn.execute("UPDATE organizations SET reports_enabled=0 WHERE org_id='A'")
        self.assertEqual(self.request(server,'/api/reports','admin@example.com',view_as=SENDER)[1]['reports'],[])

    def test_schedule_revocation_and_recipient_move_cancel_before_send(self):
        self.setup_sender()
        dispatcher = admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        for change in ('module','membership','recipient_company'):
            with self.subTest(change=change):
                with app.database_connection() as conn:
                    conn.execute("UPDATE recipients SET company='A' WHERE recipient_id=?",(USER,))
                    conn.execute('UPDATE organizations SET messaging_enabled=1')
                    conn.execute("UPDATE organization_members SET active=1 WHERE email=?",(SENDER,))
                payload = self.scheduled_text()
                with patch.object(admin_server,'load_settings'),patch.object(dispatcher.pool,'submit'):
                    dispatcher.submit(payload,SENDER,'A')
                    dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
                with app.database_connection() as conn:
                    if change=='recipient_company':conn.execute("UPDATE recipients SET company='B' WHERE recipient_id=?",(USER,))
                    if change=='module':conn.execute('UPDATE organizations SET messaging_enabled=0')
                    if change=='membership':conn.execute('UPDATE organization_members SET active=0 WHERE email=?',(SENDER,))
                with patch.object(admin_server,'send_push') as push:
                    dispatcher.run(payload['job_id']);push.assert_not_called()
                self.assertEqual(admin_server.job_status(payload['job_id'])[0]['deliveries'][0]['status'],'cancelled')

    def test_own_job_only_including_duplicate_and_cancel(self):
        user = self.setup_sender();dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with patch.object(admin_server,'load_settings'):
            own=self.scheduled_text();foreign=self.scheduled_text()
            dispatcher.submit(own,SENDER,'A');dispatcher.submit(foreign,'admin@example.com')
            self.assertEqual(len(admin_server.job_status(user=user)),1)
            with self.assertRaises(ValueError):dispatcher.submit(foreign,SENDER,'A')
            with self.assertRaises(ValueError):dispatcher.cancel(foreign['job_id'],SENDER,'A')
            dispatcher.cancel(own['job_id'],SENDER,'A')

    def test_personal_report_without_login_account(self):
        self.setup_sender()
        report=reports.save({'title':'Private','category':'company','company':'A','scope':'personal','owner_recipient_id':THIRD,'source_path':str(self.image)},'admin@example.com')
        self.assertEqual(report['owner_recipient_id'],THIRD)
        source=reports.find(report['report_id'])
        reports.validate_targets(source,[{'recipient_id':THIRD,'company':'A'}])
        with self.assertRaises(ValueError):reports.validate_targets(source,[{'recipient_id':USER,'company':'A'}])
        with app.database_connection() as conn:conn.execute("UPDATE recipients SET company='B' WHERE recipient_id=?",(THIRD,))
        with self.assertRaises(ValueError):reports.validate_targets(source,[{'recipient_id':THIRD,'company':'B'}])

    def test_sender_assets_owner_and_cross_org_grants(self):
        user=self.setup_sender()
        other=composer.upload({'name':'private.png','data':base64.b64encode(PNG).decode(),'company':'A'},reports.account('admin@example.com'))
        with self.assertRaises(ValueError):composer.asset(other['asset_id'],user)
        own=composer.upload({'name':'mine.png','data':base64.b64encode(PNG).decode()},user)
        self.assertEqual(composer.asset(own['asset_id'],user)['owner'],SENDER)
        report=self.add_report(company='B')
        with self.assertRaises(ValueError):reports.save_grant({**self.grant,'report_ids':[report['report_id']]},'admin@example.com')
        scope=reports.save_dispatch_scope({'company':'B','kind':'department','name':'B','department':'Sales','active':True},'admin@example.com')
        with self.assertRaises(ValueError):reports.save_grant({**self.grant,'scope_ids':[scope['scope_id']]},'admin@example.com')

    def test_authorized_report_send_and_revoked_report_schedule(self):
        self.setup_sender()
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        for revoke in (False,True):
            payload=self.scheduled_text();payload.pop('message_text')
            payload.update(report_id=self.source['report_id'],report_version=self.source['version'])
            with patch.object(admin_server,'load_settings'),patch.object(admin_server,'publish_image',return_value=('https://test.invalid/snapshot.png',PNG)),patch.object(admin_server,'verify_public_image'),patch.object(dispatcher.pool,'submit'):
                dispatcher.submit(payload,SENDER,'A')
                dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
            if revoke:
                with app.database_connection() as conn:
                    conn.execute("UPDATE organizations SET reports_enabled=0 WHERE org_id='A'")
            with patch.object(admin_server,'send_push',return_value='mock-request') as push:
                dispatcher.run(payload['job_id'])
                self.assertEqual(push.call_count,0 if revoke else 1)
                if not revoke:self.assertEqual(push.call_args.args[1],USER)

    def test_restart_preserves_accounts_and_memberships(self):
        before_users=reports.users();before_members=reports.memberships()
        app.initialize_database();app.initialize_database()
        self.assertEqual(reports.users(),before_users)
        self.assertEqual(reports.memberships(),before_members)
        reports.save_user({'email':SENDER,'role':'sender','company':'A','active':True},'admin@example.com')
        self.assertEqual(reports.login_account(SENDER)['role'],'sender')

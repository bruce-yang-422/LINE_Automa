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
from test_workspace import USER, OTHER, PNG, CHANNEL_A, CHANNEL_B


SENDER = 'sender@example.com'
THIRD = 'U' + '3' * 32
GROUP = 'C' + '4' * 32


class SenderTests(unittest.TestCase):
    setUpClass = classmethod(workspace.WorkspaceTests.setUpClass.__func__)
    setUp = workspace.WorkspaceTests.setUp
    request = workspace.WorkspaceTests.request
    server = workspace.WorkspaceTests.server
    scheduled_text = workspace.WorkspaceTests.scheduled_text

    def setup_sender(self):
        reports.save_user({'email':SENDER,'role':'operator','organization_id':'A','active':True},'admin@example.com')
        with app.database_connection() as conn:
            conn.executemany("INSERT INTO recipients(channel_id,recipient_id,kind,organization_id,department) VALUES (?,?,?,'A','Finance')",[(CHANNEL_A,THIRD,'user'),(CHANNEL_A,GROUP,'group')])
        return reports.account(SENDER)

    def test_contact_without_account_cannot_login_but_other_org_operator_can(self):
        server = self.server()
        for route in ('/api/session','/api/organizations'):
            self.assertEqual(self.request(server,route,'nobody@example.com')[0],401)
        reports.save_user({'email':'carol@example.com','role':'operator','organization_id':'B','active':True},'admin@example.com')
        status,session = self.request(server,'/api/session','carol@example.com',channel=CHANNEL_B)
        self.assertEqual(status,200)
        self.assertEqual(session['user']['organization_id'],'B')
        self.assertEqual([m['org_id'] for m in session['memberships']],['B'])
        self.assertEqual(self.request(server,'/api/session','carol@example.com',organization='A')[0],403)

    def test_operator_sees_org_contacts_and_can_send(self):
        self.setup_sender()
        server = self.server()
        # 丙級可直接看見所屬組織/OA 的聯絡對象
        rows = self.request(server, '/api/contacts', SENDER)[1]['contacts']
        self.assertEqual({r['recipient_id'] for r in rows}, {USER, THIRD, GROUP})
        # 丙級可直接發送所屬組織的文字訊息
        with patch.object(admin_server, 'load_settings'):
            self.assertEqual(self.request(server, '/api/send', SENDER, self.scheduled_text())[0], 202)

    def test_sender_api_boundary(self):
        self.setup_sender()
        server = self.server()
        for route in ('/api/settings','/api/view-options'):
            self.assertEqual(self.request(server,route,SENDER)[0],403)
        for route in ('/api/accounts/save','/api/memberships/save'):
            self.assertEqual(self.request(server,route,SENDER,{})[0],403)
        with patch.object(admin_server,'load_settings'):
            for ids in ([OTHER],):
                self.assertEqual(self.request(server,'/api/send',SENDER,{**self.scheduled_text(),'ids':ids})[0],400)
            self.assertEqual(self.request(server,'/api/send',SENDER,{**self.scheduled_text(),'image_path':str(self.image)})[0],400)
            self.assertEqual(self.request(server,'/api/send',SENDER,self.scheduled_text())[0],202)

    def test_preview_is_readonly(self):
        self.setup_sender()
        server = self.server()
        self.assertEqual(self.request(server,'/api/session','admin@example.com',view_as=SENDER)[1]['role'],'operator')
        self.assertEqual(self.request(server,'/api/send','admin@example.com',self.scheduled_text(),view_as=SENDER)[0],403)

    def test_schedule_revocation_and_recipient_move_cancel_before_send(self):
        self.setup_sender()
        dispatcher = admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        for change in ('module','membership','recipient_company'):
            with self.subTest(change=change):
                with app.database_connection() as conn:
                    conn.execute("UPDATE recipients SET organization_id='A' WHERE recipient_id=?",(USER,))
                    conn.execute('UPDATE organizations SET messaging_enabled=1')
                    conn.execute("UPDATE organization_members SET active=1 WHERE email=?",(SENDER,))
                payload = self.scheduled_text()
                with patch.object(admin_server,'load_settings'),patch.object(dispatcher.pool,'submit'):
                    dispatcher.submit(payload,SENDER,'A')
                    dispatcher.tick(datetime.fromisoformat(payload['scheduled_at'])+timedelta(seconds=1))
                with app.database_connection() as conn:
                    if change=='recipient_company':conn.execute("UPDATE recipients SET organization_id='B' WHERE recipient_id=?",(USER,))
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

    def test_sender_assets_owner(self):
        user=self.setup_sender()
        other=composer.upload({'name':'private.png','data':base64.b64encode(PNG).decode(),'organization_id':'A'},reports.account('admin@example.com'))
        with self.assertRaises(ValueError):composer.asset(other['asset_id'],user)
        own=composer.upload({'name':'mine.png','data':base64.b64encode(PNG).decode()},user)
        self.assertEqual(composer.asset(own['asset_id'],user)['owner'],SENDER)

    def test_restart_preserves_accounts_and_memberships(self):
        before_users=reports.users();before_members=reports.memberships()
        app.initialize_database();app.initialize_database()
        self.assertEqual(reports.users(),before_users)
        self.assertEqual(reports.memberships(),before_members)
        reports.save_user({'email':SENDER,'role':'operator','organization_id':'A','active':True},'admin@example.com')
        self.assertEqual(reports.login_account(SENDER)['role'],'operator')

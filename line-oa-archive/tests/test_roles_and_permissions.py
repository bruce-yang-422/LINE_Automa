import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import http.client
import json
import sqlite3
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote
from login_helper import session_headers
import app
import reports
import channels
import admin_server
import test_workspace as workspace
from test_workspace import USER, OTHER, PNG

ADMIN = 'admin@example.com'
ORG_ADMIN = 'boss@org-a.com'
SENDER = 'operator@org-a.com'
COLLABORATOR = 'assistant@org-a.com'
ORG_A = 'org-a'
ORG_B = 'org-b'
CONTACT_USER = 'U' + '1' * 32

SCHEMA_PATH = Path(__file__).resolve().parent.parent / 'schema.sql'


class RolesAndPermissionsTests(unittest.TestCase):
    def server(self):
        return workspace.WorkspaceTests.server(self)

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix='line-roles-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'instance').mkdir()
        (self.root / 'schema.sql').write_bytes(SCHEMA_PATH.read_bytes())
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

    def request(self, server, path, email='alice@example.com', payload=None, view_as=None, organization=None, preview_org=None, channel=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {**session_headers(email, server.public_host), 'Content-Type': 'application/json'}
        if view_as is not None:
            headers['X-Workspace-View-As'] = view_as
        if organization is not None:
            headers['X-Workspace-Organization'] = quote(organization)
        if preview_org is not None:
            headers['X-Workspace-Preview-Organization'] = quote(preview_org)
        if channel is not None:
            headers['X-Line-Channel'] = channel
        try:
            conn.request('GET' if payload is None else 'POST', path, None if payload is None else json.dumps(payload), headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def setup_roles_environment(self):
        # 1. Create Organization A & B
        with app.database_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO organizations(org_id, name, kind, active, reports_enabled, messaging_enabled, weather_enabled) VALUES (?, 'Org A', 'company', 1, 1, 1, 0)", (ORG_A,))
            conn.execute("INSERT OR REPLACE INTO organizations(org_id, name, kind, active, reports_enabled, messaging_enabled, weather_enabled) VALUES (?, 'Org B', 'company', 1, 1, 1, 0)", (ORG_B,))
            conn.execute("INSERT OR REPLACE INTO line_channels (channel_id, name, token_cipher, secret_cipher, active, org_id, bot_user_id) VALUES ('primary', 'Main OA', 'sec', 'tok', 1, ?, 'U00000000000000000000000000000001')", (ORG_A,))
            conn.execute("INSERT OR REPLACE INTO recipients(recipient_id, channel_id, kind, organization_id, display_name) VALUES (?, 'primary', 'user', ?, 'Test Customer')", (CONTACT_USER, ORG_A))
            conn.execute("INSERT OR REPLACE INTO line_messages(channel_id, message_id, conversation_id, conversation_type, direction, message_type, text_content, sent_at) VALUES ('primary', 'msg-1', ?, 'user', 'inbound', 'text', 'Hello OA', datetime('now'))", (CONTACT_USER,))

        # 2. Create users
        reports.save_user({'email': ORG_ADMIN, 'display_name': 'Org Boss', 'role': 'org_admin', 'organization_id': ORG_A, 'active': True}, ADMIN)
        reports.save_user({'email': SENDER, 'display_name': 'Sender User', 'role': 'operator', 'organization_id': ORG_A, 'active': True}, ADMIN)
        reports.save_user({'email': COLLABORATOR, 'display_name': 'Assistant User', 'role': 'collaborator', 'organization_id': ORG_A, 'active': True}, ADMIN)

    def test_administrator_read_triggers_vendor_view_audit(self):
        self.setup_roles_environment()
        server = self.server()
        
        # Administrator reading customer chat messages
        status, res = self.request(server, f'/api/chat/messages?recipient_id={CONTACT_USER}', ADMIN, organization=ORG_A, channel='primary')
        self.assertEqual(status, 200)
        self.assertEqual(len(res['messages']), 1)
        
        # Check audit events for vendor.view
        with app.database_connection() as conn:
            conn.row_factory = sqlite3.Row
            vendor_events = [dict(r) for r in conn.execute("SELECT * FROM audit_events WHERE action='vendor.view'").fetchall()]
        self.assertTrue(len(vendor_events) >= 1)
        self.assertIn('平台管理員檢視客戶營運內容', vendor_events[0]['detail'])
        # 組織管理員在本組織的操作紀錄看得到供應商查看紀錄。
        status, res = self.request(server, '/api/activity', ORG_ADMIN, organization=ORG_A, channel='primary')
        self.assertEqual(status, 200)
        self.assertTrue(any(e['action'] == 'vendor.view' for e in res['events']))

    def test_administrator_write_blocked_with_403(self):
        self.setup_roles_environment()
        server = self.server()
        
        # Try sending chat message
        status, res = self.request(server, '/api/chat/send', ADMIN, {'recipient_id': CONTACT_USER, 'text': 'Hello'}, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)
        self.assertIn('平台管理員對客戶營運內容只有閱讀權', res.get('error', ''))
        
        # Try creating a case
        status, res = self.request(server, '/api/cases', ADMIN, {'case_subject_id': CONTACT_USER, 'title': 'Test Case'}, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)
        
        # Try creating a chat note
        status, res = self.request(server, '/api/chat-notes', ADMIN, {'action': 'add', 'recipient_id': CONTACT_USER, 'title': 'Note 1'}, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)

    def test_platform_admin_manages_only_org_admins_and_not_personnel(self):
        # 甲級只管理 OA 與乙級：可建立管理員，不能建立丙、丁級，也不能使用乙級的人員與組織設定 API。
        self.setup_roles_environment()
        server = self.server()
        status, _ = self.request(server, '/api/accounts/save', ADMIN, {
            'email': 'boss2@org-a.com', 'role': 'org_admin', 'organization_id': ORG_A, 'active': True})
        self.assertEqual(status, 200)
        for role in ('operator', 'collaborator'):
            status, res = self.request(server, '/api/accounts/save', ADMIN, {
                'email': f'{role}2@org-a.com', 'role': role, 'organization_id': ORG_A, 'active': True})
            self.assertEqual(status, 400)
            self.assertIn('組織的管理員', res.get('error', ''))
        self.assertEqual(self.request(server, '/api/personnel', ADMIN)[0], 403)
        self.assertEqual(self.request(server, '/api/personnel/save', ADMIN, {
            'email': 'x@org-a.com', 'role': 'operator', 'active': True})[0], 403)
        self.assertEqual(self.request(server, '/api/org-settings/save', ADMIN, {'name': 'Renamed'})[0], 403)
        # 乙級仍可使用自己的人員與權限。
        self.assertEqual(self.request(server, '/api/personnel', ORG_ADMIN)[0], 200)

    def test_org_admin_can_manage_operator_and_collaborator_in_own_org(self):
        self.setup_roles_environment()
        server = self.server()
        
        # Company Admin creates a new assistant in Org A
        new_staff = 'staff2@org-a.com'
        status, res = self.request(server, '/api/personnel/save', ORG_ADMIN, {
            'email': new_staff,
            'org_id': ORG_A,
            'display_name': 'New Staff',
            'role': 'collaborator',
            'department': 'Support',
            'active': True,
            'channel_ids': ['primary']
        }, organization=ORG_A)
        self.assertEqual(status, 200)
        
        # Verify created
        user = reports.account(new_staff)
        self.assertEqual(user['role'], 'collaborator')
        
        # Company Admin attempting to create administrator -> blocked
        status, res = self.request(server, '/api/personnel/save', ORG_ADMIN, {
            'email': 'hacker@example.com',
            'org_id': ORG_A,
            'role': 'platform_admin'
        }, organization=ORG_A)
        self.assertIn(status, (400, 403))
        
        # Company Admin attempting to create org_admin -> blocked
        status, res = self.request(server, '/api/personnel/save', ORG_ADMIN, {
            'email': 'another_boss@org-a.com',
            'org_id': ORG_A,
            'role': 'org_admin'
        }, organization=ORG_A)
        self.assertIn(status, (400, 403))
        
        # Company Admin attempting to manage another org -> blocked
        status, res = self.request(server, '/api/personnel/save', ORG_ADMIN, {
            'email': 'intruder@org-b.com',
            'org_id': ORG_B,
            'role': 'operator'
        }, organization=ORG_A)
        self.assertIn(status, (400, 403))

    def test_assistant_can_manage_cases_and_notes_but_cannot_send_messages(self):
        self.setup_roles_environment()
        server = self.server()
        
        # Assistant can read chat
        status, res = self.request(server, f'/api/chat/messages?recipient_id={CONTACT_USER}', COLLABORATOR, organization=ORG_A, channel='primary')
        self.assertEqual(status, 200)
        
        # Assistant can create chat note
        status, res = self.request(server, '/api/chat-notes', COLLABORATOR, {
            'action': 'add',
            'recipient_id': CONTACT_USER,
            'title': 'Assistant Note',
            'content': 'Taking notes'
        }, organization=ORG_A, channel='primary')
        self.assertEqual(status, 200)
        
        # Assistant can create case
        status, res = self.request(server, '/api/cases', COLLABORATOR, {
            'case_subject_id': CONTACT_USER,
            'title': 'Assistant Created Case',
            'priority': 'normal'
        }, organization=ORG_A, channel='primary')
        self.assertEqual(status, 200)
        
        # Assistant CANNOT send chat message
        status, res = self.request(server, '/api/chat/send', COLLABORATOR, {
            'recipient_id': CONTACT_USER,
            'text': 'I should not be able to send this'
        }, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)
        self.assertIn('協作人員無法傳送訊息', res.get('error', ''))
        
        # Assistant CANNOT send broadcast / report
        status, res = self.request(server, '/api/send', COLLABORATOR, {
            'job_id': 'job-assist-1',
            'message_text': 'Broadcast attempt',
            'ids': [CONTACT_USER]
        }, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)

    def test_oa_member_access_filtering(self):
        self.setup_roles_environment()
        # Add another OA channel
        with app.database_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO line_channels (channel_id, name, token_cipher, secret_cipher, active, org_id, bot_user_id) VALUES ('branch_oa', 'Branch OA', 'sec2', 'tok2', 1, ?, 'U00000000000000000000000000000002')", (ORG_A,))
        
        # Grant SENDER access ONLY to 'branch_oa'
        reports.save_membership({
            'email': SENDER,
            'org_id': ORG_A,
            'role': 'operator',
            'active': True,
            'channel_ids': ['branch_oa']
        }, ADMIN)
        
        server = self.server()
        # SENDER accessing primary channel -> 403
        status, res = self.request(server, '/api/contacts', SENDER, organization=ORG_A, channel='primary')
        self.assertEqual(status, 403)
        
        # SENDER accessing branch_oa channel -> 200
        status, res = self.request(server, '/api/contacts', SENDER, organization=ORG_A, channel='branch_oa')
        self.assertEqual(status, 200)

if __name__ == '__main__':
    unittest.main()

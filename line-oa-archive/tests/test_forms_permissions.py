"""Phase-one A1 checks: isolated database, real HTTP authorization, no LINE API."""
import sqlite3
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app
import channels
import forms
import limits
import reports
import test_roles_and_permissions as roles
from test_roles_and_permissions import ADMIN, ORG_ADMIN, SENDER, COLLABORATOR, ORG_A, ORG_B


class FormsPermissionsTests(unittest.TestCase):
    setUp = roles.RolesAndPermissionsTests.setUp
    server = roles.RolesAndPermissionsTests.server
    request = roles.RolesAndPermissionsTests.request
    setup_roles_environment = roles.RolesAndPermissionsTests.setup_roles_environment

    def prepare(self):
        self.setup_roles_environment()
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET forms_enabled=1 WHERE org_id=?', (ORG_A,))
        self.user = reports.account(ORG_ADMIN)

    def call(self, server, path, email=ORG_ADMIN, payload=None, **kwargs):
        return self.request(server, path, email, payload, channel='primary', **kwargs)

    def create(self, name='表單', template='group_buy'):
        with channels.use('primary'):
            return forms.save(self.user, {'name': name, 'template_id': template})['form']

    def test_module_defaults_disabled_and_only_platform_changes_switch(self):
        self.setup_roles_environment()
        server = self.server()
        self.assertEqual(self.call(server, '/api/forms')[0], 403)
        payload = {'org_id': ORG_A, 'name': 'Org A', 'kind': 'company',
                   'active': True, 'messaging_enabled': True, 'forms_enabled': True}
        for email in (ORG_ADMIN, SENDER, COLLABORATOR):
            self.assertEqual(self.request(server, '/api/organizations/save', email, payload)[0], 403)
        self.assertEqual(self.request(server, '/api/organizations/save', ADMIN, payload)[0], 200)
        self.assertEqual(self.call(server, '/api/forms')[0], 200)
        self.assertTrue(self.call(server, '/api/session')[1]['modules']['forms'])
        self.assertEqual(self.call(server, '/api/session')[1]['limits']['FORMS_PER_OA'], limits.FORMS_PER_OA)
        payload['forms_enabled'] = 1
        self.assertEqual(self.request(server, '/api/organizations/save', ADMIN, payload)[0], 400)

    def test_four_roles_visibility_and_capabilities(self):
        self.prepare()
        server = self.server()
        for email in (ORG_ADMIN, SENDER, COLLABORATOR):
            status, data = self.call(server, '/api/forms', email)
            self.assertEqual(status, 200)
            self.assertTrue(data['capabilities']['view'])
            for action in ('maintain', 'publish', 'send', 'export'):
                self.assertEqual(data['capabilities'][action], email != COLLABORATOR)
        self.assertEqual(self.call(server, '/api/forms', ADMIN)[0], 403)
        for email in (COLLABORATOR, ADMIN):
            for route in ('save', 'copy', 'delete', 'status'):
                self.assertEqual(self.call(server, '/api/forms/'+route, email, {'name': '越權'})[0], 403)

    def test_platform_preview_read_is_audited_and_writes_rejected(self):
        self.prepare()
        row = self.create()
        server = self.server()
        status, data = self.call(server, '/api/forms', ADMIN, view_as=ORG_ADMIN, preview_org=ORG_A)
        self.assertEqual(status, 200)
        self.assertFalse(data['capabilities']['maintain'])
        self.assertEqual(self.call(server, '/api/forms/detail?form_id='+row['form_id'], ADMIN,
                                   view_as=ORG_ADMIN, preview_org=ORG_A)[0], 200)
        self.assertEqual(self.call(server, '/api/forms/save', ADMIN, {'name': '越權'},
                                   view_as=ORG_ADMIN, preview_org=ORG_A)[0], 403)
        with app.database_connection() as conn:
            rows = conn.execute("SELECT actor,organization_id FROM audit_events WHERE action='vendor.view'").fetchall()
            self.assertEqual(rows, [(ADMIN, ORG_A), (ADMIN, ORG_A)])

    def test_operator_can_modify_another_authors_form(self):
        self.prepare()
        row = self.create()
        server = self.server()
        status, updated = self.call(server, '/api/forms/save', SENDER,
                                    {'form_id': row['form_id'], 'name': '操作人員修改', 'description': '說明'})
        self.assertEqual(status, 200)
        self.assertEqual(updated['form']['created_by'], ORG_ADMIN)
        self.assertEqual(updated['form']['updated_by'], SENDER)
        self.assertEqual(updated['form']['questions'], row['questions'])

    def test_cross_organization_and_unassigned_oa_denied(self):
        self.prepare()
        row = self.create()
        with app.database_connection() as conn:
            conn.execute("INSERT INTO line_channels(channel_id,name,token_cipher,secret_cipher,bot_user_id,org_id) VALUES ('other','Other','tok','sec','other-bot',?)", (ORG_B,))
            conn.execute("INSERT INTO line_channels(channel_id,name,token_cipher,secret_cipher,bot_user_id,org_id) VALUES ('second','Second','tok','sec','second-bot',?)", (ORG_A,))
            conn.execute("INSERT INTO oa_member_access(channel_id,email,org_id) VALUES ('primary',?,?)", (SENDER, ORG_A))
            conn.execute("UPDATE organizations SET forms_enabled=1 WHERE org_id=?", (ORG_B,))
        server = self.server()
        self.assertEqual(self.request(server, '/api/forms', ORG_ADMIN, channel='other')[0], 403)
        self.assertEqual(self.request(server, '/api/forms', SENDER, channel='second')[0], 403)
        self.assertEqual(self.request(server, '/api/forms/detail?form_id='+row['form_id'], ORG_ADMIN, channel='second')[0], 403)
        for route, payload in [('save', {'name': '跨 OA'}), ('copy', {}), ('delete', {'confirm_counts': {'invitations': 0, 'responses': 0}}), ('status', {'status': 'collecting'})]:
            self.assertEqual(self.request(server, '/api/forms/'+route, ORG_ADMIN,
                                          {**payload, 'form_id': row['form_id']}, channel='second')[0], 403)

    def test_disabled_module_org_oa_and_revoked_membership(self):
        self.prepare()
        stale = reports.account(SENDER)
        with channels.use('primary'):
            for table, flag, key in [('organizations','forms_enabled','org_id'), ('organizations','active','org_id'), ('line_channels','active','channel_id')]:
                identifier = ORG_A if key=='org_id' else 'primary'
                with app.database_connection() as conn:
                    conn.execute(f'UPDATE {table} SET {flag}=0 WHERE {key}=?', (identifier,))
                self.assertFalse(any(forms.capabilities(stale).values()))
                with app.database_connection() as conn:
                    conn.execute(f'UPDATE {table} SET {flag}=1 WHERE {key}=?', (identifier,))
            with app.database_connection() as conn:
                conn.execute('UPDATE organization_members SET active=0 WHERE email=?', (SENDER,))
            self.assertFalse(any(forms.capabilities(stale).values()))

    def test_messaging_switch_only_removes_send_capability(self):
        self.prepare()
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET messaging_enabled=0 WHERE org_id=?', (ORG_A,))
        with channels.use('primary'):
            caps = forms.capabilities(self.user)
            self.assertFalse(caps.pop('send'))
            self.assertTrue(all(caps.values()))

    def test_invitation_gate_rejects_draft_stopped_and_expired(self):
        self.prepare()
        row = self.create()
        with channels.use('primary'):
            with self.assertRaises(ValueError):
                forms.invitation_form(self.user, row['form_id'])
            forms.transition(self.user, {'form_id': row['form_id'], 'status': 'collecting'})
            self.assertEqual(forms.invitation_form(self.user, row['form_id'])['form_id'], row['form_id'])
            with self.assertRaises(PermissionError):
                forms.invitation_form(reports.account(COLLABORATOR), row['form_id'])
            forms.save(self.user, {'form_id': row['form_id'], 'name': row['name'], 'deadline_at': '2000-01-01T00:00:00+00:00'})
            with self.assertRaises(ValueError):
                forms.invitation_form(self.user, row['form_id'])
            forms.transition(self.user, {'form_id': row['form_id'], 'status': 'stopped'})
            with self.assertRaises(ValueError):
                forms.invitation_form(self.user, row['form_id'])

    def test_templates_copy_draft_and_delete_confirmation_audit(self):
        self.prepare()
        with channels.use('primary'):
            for template in forms.TEMPLATES:
                row = self.create(template=template)
                self.assertEqual(row['questions'], forms.TEMPLATES[template]['questions'])
            row = self.create()
            forms.transition(self.user, {'form_id': row['form_id'], 'status': 'collecting'})
            copied = forms.duplicate(self.user, {'form_id': row['form_id']})['form']
            self.assertEqual(copied['status'], 'draft')
            self.assertNotEqual(row['form_id'], copied['form_id'])
            self.assertEqual(copied['questions'], row['questions'])
            with self.assertRaises(ValueError):
                forms.delete(self.user, {'form_id': copied['form_id']})
            forms.delete(self.user, {'form_id': copied['form_id'], 'confirm_counts': {'invitations': 0, 'responses': 0}})
            with self.assertRaises(PermissionError):
                forms.detail(self.user, copied['form_id'])
        with app.database_connection() as conn:
            actions = {r[0] for r in conn.execute("SELECT action FROM audit_events WHERE action LIKE 'forms.%'")}
            self.assertTrue({'forms.create','forms.copy','forms.status','forms.delete'} <= actions)
            detail = conn.execute("SELECT detail FROM audit_events WHERE action='forms.delete'").fetchone()[0]
            self.assertIn('邀請 0、回覆 0', detail)

    def test_stop_deadline_reopen_and_utc_storage(self):
        self.prepare()
        row = self.create()
        with channels.use('primary'):
            with self.assertRaises(ValueError):
                forms.transition(self.user, {'form_id': row['form_id'], 'status': 'stopped'})
            forms.transition(self.user, {'form_id': row['form_id'], 'status': 'collecting'})
            forms.transition(self.user, {'form_id': row['form_id'], 'status': 'stopped'})
            forms.save(self.user, {'form_id': row['form_id'], 'name': row['name'], 'deadline_at': '2000-01-01T08:00:00+08:00'})
            with self.assertRaises(ValueError):
                forms.transition(self.user, {'form_id': row['form_id'], 'status': 'collecting'})
            updated = forms.save(self.user, {'form_id': row['form_id'], 'name': row['name'], 'deadline_at': '2099-01-01T08:00:00+08:00'})['form']
            self.assertEqual(updated['deadline_at'], '2099-01-01T00:00:00+00:00')
            self.assertEqual(forms.transition(self.user, {'form_id': row['form_id'], 'status': 'collecting'})['form']['status'], 'collecting')

    def test_validation_capacity_and_no_status_or_questions_bypass(self):
        self.prepare()
        with channels.use('primary'):
            for payload in [{'name': ' '}, {'name': 'x'*(limits.FORM_NAME_MAX+1)}, {'name':'x','template_id':'unknown'}, {'name':'x','deadline_at':'2027-01-01T00:00'}, {'name':'x','status':'collecting'}, {'name':'x','questions':[]}]:
                with self.assertRaises(ValueError):
                    forms.save(self.user, payload)
            self.create()
            with patch.object(limits, 'FORMS_PER_OA', 1):
                with self.assertRaises(ValueError):
                    self.create()

    def test_additive_startup_preserves_prior_v2_and_is_idempotent(self):
        schema = (self.root/'schema.sql').read_text(encoding='utf-8').split('-- ============ 表單第一階段')[0]
        schema = '\n'.join(line for line in schema.splitlines() if 'forms_enabled INTEGER' not in line)
        previous = self.root/'prior.db'
        from contextlib import closing
        with closing(sqlite3.connect(previous)) as conn:
            conn.executescript(schema)
            conn.execute('PRAGMA user_version=2')
            conn.execute("INSERT INTO organizations(org_id,name) VALUES ('original','Original')")
            conn.commit()
        with patch.object(app, 'DATABASE_PATH', previous):
            app.initialize_database()
            app.initialize_database()
            with app.database_connection() as conn:
                self.assertEqual(conn.execute('SELECT name,forms_enabled FROM organizations').fetchone(), ('Original',0))
                self.assertEqual(conn.execute('SELECT count(*) FROM forms').fetchone()[0],0)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],2)


if __name__ == '__main__':
    unittest.main()

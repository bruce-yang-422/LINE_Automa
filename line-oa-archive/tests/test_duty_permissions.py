"""Duty phase-one authorization uses isolated databases and no LINE sends."""
import sqlite3
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app
import duty
import reports
import test_roles_and_permissions as roles_tests
from test_roles_and_permissions import (
    ADMIN, ORG_ADMIN, SENDER, COLLABORATOR, ORG_A, ORG_B,
)


class DutyPermissionsTests(unittest.TestCase):
    setUp = roles_tests.RolesAndPermissionsTests.setUp
    server = roles_tests.RolesAndPermissionsTests.server
    request = roles_tests.RolesAndPermissionsTests.request
    setup_roles_environment = roles_tests.RolesAndPermissionsTests.setup_roles_environment

    def prepare(self):
        self.setup_roles_environment()
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET duty_enabled=1 WHERE org_id=?', (ORG_A,))

    def test_default_disabled_and_organization_isolation_without_oa(self):
        self.setup_roles_environment()
        server = self.server()
        self.assertEqual(self.request(server, '/api/duty', ORG_ADMIN)[0], 403)
        self.prepare_flags()
        status, data = self.request(server, '/api/duty', ORG_ADMIN)
        self.assertEqual(status, 200)
        self.assertEqual(data['organization']['org_id'], ORG_A)
        self.assertIsNone(data['notification_oa'])
        self.assertEqual(self.request(server, '/api/duty?org_id='+ORG_B, ORG_ADMIN)[0], 403)
        self.assertEqual(self.request(server, '/api/duty', ADMIN)[0], 403)
        self.assertEqual(self.request(server, '/api/duty', COLLABORATOR)[0], 403)

    def prepare_flags(self):
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET duty_enabled=1 WHERE org_id=?', (ORG_A,))

    def test_grant_revoke_and_preview(self):
        self.prepare()
        server = self.server()
        payload = {'org_id': ORG_A, 'email': SENDER, 'duty_manager': True}
        status, result = self.request(server, '/api/duty', SENDER)
        self.assertEqual(status, 200)
        self.assertTrue(result['capabilities']['view'])
        self.assertFalse(result['capabilities']['edit'])
        for email in (SENDER, COLLABORATOR, ADMIN):
            self.assertEqual(self.request(server, '/api/duty/grants', email, payload)[0], 403)
        self.assertEqual(self.request(server, '/api/duty/grants', ORG_ADMIN, payload)[0], 200)
        stale_user = reports.account(SENDER)
        for action in duty.ACTIONS:
            self.assertTrue(duty.capabilities(stale_user)[action])
        for principal in (ADMIN, ORG_ADMIN):
            status, result = self.request(server, '/api/duty', principal, view_as=SENDER, preview_org=ORG_A)
            self.assertEqual(status, 200)
            self.assertTrue(result['capabilities']['view'])
            self.assertFalse(result['capabilities']['send'])
        self.assertEqual(self.request(server, '/api/duty/grants', ORG_ADMIN, payload, view_as=SENDER)[0], 403)
        payload['duty_manager'] = False
        self.assertEqual(self.request(server, '/api/duty/grants', ORG_ADMIN, payload)[0], 200)
        self.assertFalse(duty.capabilities(stale_user)['edit'])
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_events WHERE action='duty.manager'").fetchone()[0], 2)

    def test_grant_validation_and_downgrade(self):
        self.prepare()
        admin = reports.account(ORG_ADMIN)
        with self.assertRaises(ValueError):
            duty.grant(admin, {'email': COLLABORATOR, 'duty_manager': True})
        with self.assertRaises(ValueError):
            duty.grant(admin, {'email': SENDER, 'duty_manager': 1})
        with self.assertRaises(PermissionError):
            duty.grant(admin, {'org_id': ORG_B, 'email': SENDER, 'duty_manager': True})
        duty.grant(admin, {'email': SENDER, 'duty_manager': True})
        stale = reports.account(SENDER)
        reports.save_membership({'email': SENDER, 'org_id': ORG_A, 'role': 'collaborator', 'active': True}, ORG_ADMIN)
        self.assertFalse(duty.capabilities(stale)['view'])
        self.assertEqual(reports.account(SENDER)['duty_manager'], 0)
        reports.save_membership({'email': SENDER, 'org_id': ORG_A, 'role': 'operator', 'active': True}, ORG_ADMIN)
        self.assertFalse(duty.capabilities(reports.account(SENDER))['edit'])

    def test_disabled_org_revokes_every_capability(self):
        self.prepare()
        user = reports.account(ORG_ADMIN)
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET duty_enabled=0 WHERE org_id=?', (ORG_A,))
        self.assertFalse(any(duty.capabilities(user).values()))

    def test_additive_extension_preserves_old_v2_data_and_is_idempotent(self):
        # Reconstruct the prior v2 schema in a separate file; never production.
        old = (self.root / 'schema.sql').read_text(encoding='utf-8')
        old = old.split('-- ============ 值日生第二階段')[0]
        old = '\n'.join(line for line in old.splitlines() if not any(k in line for k in ('duty_enabled INTEGER', 'duty_manager INTEGER')))
        previous = self.root / 'previous.db'
        from contextlib import closing
        with closing(sqlite3.connect(previous)) as conn:
            conn.executescript(old)
            conn.execute('PRAGMA user_version=2')
            conn.execute("INSERT INTO organizations(org_id,name) VALUES ('existing','Existing')")
            conn.commit()
        from unittest.mock import patch
        with patch.object(app, 'DATABASE_PATH', previous):
            app.initialize_database()
            app.initialize_database()
            with app.database_connection() as conn:
                self.assertEqual(conn.execute('SELECT name,duty_enabled FROM organizations').fetchone(), ('Existing', 0))
                self.assertIn('duty_manager', {r[1] for r in conn.execute('PRAGMA table_info(organization_members)')})
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({'duty_people','duty_tasks','duty_rosters','duty_assignments','duty_substitutions'} <= tables)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],2)

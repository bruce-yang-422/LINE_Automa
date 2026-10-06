import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import unittest
from unittest.mock import patch
import app
import duty
import reports
import duty_fixture
import test_roles_and_permissions as roles


class DutyPeopleTests(unittest.TestCase):
    setUp = roles.RolesAndPermissionsTests.setUp
    server = roles.RolesAndPermissionsTests.server
    request = roles.RolesAndPermissionsTests.request
    setup_roles_environment = roles.RolesAndPermissionsTests.setup_roles_environment

    def prepare(self):
        self.setup_roles_environment()
        with app.database_connection() as conn:
            conn.execute('UPDATE organizations SET duty_enabled=1 WHERE org_id=?', (roles.ORG_A,))
        return reports.account(roles.ORG_ADMIN)

    def person(self, user, name='範例員工01', **extra):
        return duty.save_person(user, {'full_name': name, 'effective_from': '2026-01-01', **extra})['person_id']

    def test_original_fixture_and_reserved_position(self):
        user = self.prepare()
        duty_fixture.seed(user)
        data = duty.list_people(user)
        self.assertEqual(len(data['people']), 16)
        self.assertEqual(len(data['positions']), 17)
        self.assertTrue(next(p for p in data['positions'] if p['code'] == '12')['vacant'])
        self.assertEqual(len(duty.list_tasks(user)['tasks']), 17)

    def test_replacement_keeps_former_employee_and_dates(self):
        user = self.prepare()
        old = self.person(user)
        person = duty.list_people(user)['people'][0]
        position = person['memberships'][0]['position_id']
        duty.remove_resource(user, {'kind': 'person', 'id': old})
        new = self.person(user, '範例員工02', effective_from='2026-11-01', position_id=position)
        self.assertNotEqual(old, new)
        with app.database_connection() as conn:
            rows = conn.execute('SELECT person_id,effective_from,effective_to FROM duty_position_members ORDER BY effective_from').fetchall()
        self.assertEqual(rows, [(old, '2026-01-01', '2026-10-31'), (new, '2026-11-01', None)])
        with self.assertRaises(ValueError):
            duty.save_person(user, {'full_name': '範例員工11', 'effective_from': '2026-11-01', 'position_id': position})

    def test_bulk_preview_atomic_limit_and_x(self):
        user = self.prepare()
        payload = {'text': '全名,顯示名稱,部門,樓層\n範例員工01,範例暱稱01,管理部,2F\nX,,,\n範例員工02,範例暱稱02,管理部,2F', 'effective_from': '2026-01-01'}
        self.assertEqual(len(duty.bulk_people(user, payload)['rows']), 3)
        self.assertEqual(len(duty.list_people(user)['people']), 0)
        self.assertEqual(duty.bulk_people(user, {**payload, 'confirm': True})['count'], 2)
        with patch.object(duty.limits, 'DUTY_PEOPLE_PER_ORG', 3):
            with self.assertRaises(ValueError):
                duty.bulk_people(user, {'text': '範例員工03,,,\n範例員工04,,,', 'effective_from': '2026-01-01', 'confirm': True})
        self.assertEqual(len(duty.list_people(user)['people']), 2)

    def test_oa_binding_scope_unique_and_unset(self):
        user = self.prepare()
        one, two = self.person(user), self.person(user, '範例員工02')
        self.assertIsNone(duty.binding_candidates(user)['channel_id'])
        payload = {'person_id': one, 'channel_id': 'primary', 'recipient_id': roles.CONTACT_USER}
        with self.assertRaises(ValueError):
            duty.save_binding(user, payload)
        with patch.object(duty, 'notification_oa', return_value='primary'):
            duty.save_binding(user, payload)
            candidates = duty.binding_candidates(user)['recipients']
            self.assertEqual(candidates[0]['bound_name'], '範例員工01')
            with self.assertRaises(ValueError):
                duty.save_binding(user, {**payload, 'person_id': two})
            with app.database_connection() as conn:
                conn.execute("INSERT INTO recipients(channel_id,recipient_id,kind) VALUES ('primary','group','group')")
            with self.assertRaises(ValueError):
                duty.save_binding(user, {**payload, 'recipient_id': 'group'})
            duty.save_binding(user, {**payload, 'recipient_id': ''})
            self.assertIsNone(duty.binding_candidates(user)['recipients'][0]['person_id'])

    def test_http_permission_org_and_stale_updates(self):
        user = self.prepare()
        server = self.server()
        payload = {'full_name': '範例員工01', 'effective_from': '2026-01-01'}
        self.assertEqual(self.request(server, '/api/duty/people/save', roles.SENDER, payload)[0], 403)
        self.assertEqual(self.request(server, '/api/duty/people', roles.SENDER)[0], 403)
        self.assertEqual(self.request(server, '/api/duty/people/save', roles.ORG_ADMIN, {**payload, 'org_id': roles.ORG_B})[0], 403)
        person_id = self.person(user)
        with self.assertRaises(ValueError):
            duty.save_person(user, {**payload, 'person_id': person_id, 'expected_updated_at': 'old'})
        with self.assertRaises(PermissionError):
            duty.save_person(user, payload, preview=True)

    def test_removal_confirmation_restore_and_reference_guard(self):
        user = self.prepare()
        person_id = self.person(user)
        impacts = [{'period': '2026-11', 'status': 'published'}]
        with patch.object(duty, 'reference_impacts', return_value=impacts):
            with self.assertRaises(ValueError):
                duty.remove_resource(user, {'kind': 'person', 'id': person_id})
            duty.remove_resource(user, {'kind': 'person', 'id': person_id, 'effective_from': '2026-11-01', 'reason': '離職', 'confirm_impacts': True, 'impacts': impacts})
        self.assertEqual(duty.list_people(user)['people'][0]['active'], 0)
        duty.remove_resource(user, {'kind': 'person', 'id': person_id, 'restore': True})
        self.assertEqual(duty.list_people(user)['people'][0]['active'], 1)

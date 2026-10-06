import unittest
from unittest.mock import patch
import app
import duty
import reports
import test_duty_people as people_tests
import test_roles_and_permissions as roles


class DutyRosterTests(unittest.TestCase):
    setUp = people_tests.DutyPeopleTests.setUp
    prepare = people_tests.DutyPeopleTests.prepare
    setup_roles_environment = people_tests.DutyPeopleTests.setup_roles_environment
    server = people_tests.DutyPeopleTests.server
    request = people_tests.DutyPeopleTests.request

    def environment(self, rotation='month'):
        user = self.prepare()
        person = duty.save_person(user, {'full_name': '範例員工01', 'effective_from': '2026-01-01'})['person_id']
        other = duty.save_person(user, {'full_name': '範例員工02', 'effective_from': '2026-01-01'})['person_id']
        task = duty.save_task(user, {'name': '打包垃圾', 'rotation': rotation, 'effective_from': '2026-01-01'})['task_id']
        return user, person, other, task

    def draft(self, user, **extra):
        return duty.create_draft(user, {'name': '2026/10', 'date_from': '2026-10-01', 'date_to': '2026-10-31', 'period_type': 'month', **extra})['roster_id']

    def assign(self, user, roster_id, person, substitutions=None):
        record = duty.get_roster(user, roster_id)
        assignments = record['assignments']
        assignments[0]['person_ids'] = [person]
        assignments[0]['substitutions'] = substitutions or []
        duty.save_draft(user, {'roster_id': roster_id, 'expected_updated_at': record['updated_at'], 'assignments': assignments})

    def publish(self, user, roster_id, **extra):
        record = duty.get_roster(user, roster_id)
        return duty.publish_roster(user, {'roster_id': roster_id, 'expected_updated_at': record['updated_at'], 'acknowledged': [r['key'] for r in record['checks']['warnings']], **extra})

    def test_draft_idempotence_copy_publish_and_versions(self):
        user, person, _, _ = self.environment()
        roster = self.draft(user)
        self.assertEqual(self.draft(user), roster)
        self.assign(user, roster, person)
        self.assertEqual(self.publish(user, roster)['version'], 1)
        clone = self.draft(user, copy_from=roster)
        self.assertNotEqual(clone, roster)
        self.assertEqual(duty.get_roster(user, clone)['assignments'][0]['person_ids'], [person])
        with self.assertRaises(ValueError):
            self.publish(user, clone)
        self.assertEqual(self.publish(user, clone, reason='调整班表')['version'], 2)
        self.assertEqual(duty.get_roster(user, roster)['status'], 'replaced')
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM duty_rosters WHERE status='published'").fetchone()[0], 1)
        self.assertTrue(duty.roster_activity(user, clone)['events'])

    def test_archive_task_removes_draft_but_preserves_published_snapshot(self):
        user, person, _, task = self.environment()
        roster = self.draft(user)
        self.assign(user, roster, person)
        self.publish(user, roster)
        clone = self.draft(user, copy_from=roster)
        before = duty.get_roster(user, clone)
        payload = {'kind': 'task', 'id': task, 'mode': 'archive', 'effective_from': '2026-10-06'}
        with self.assertRaises(ValueError):
            duty.remove_resource(user, payload)
        self.assertEqual(len(duty.get_roster(user, clone)['assignments']), 1)
        impacts = duty.list_tasks(user)['tasks'][0]['impacts']
        duty.remove_resource(user, {**payload, 'confirm_impacts': True, 'impacts': impacts, 'reason': '移除不再使用的工作'})
        self.assertEqual(duty.list_tasks(user)['tasks'], [])
        self.assertEqual(duty.get_roster(user, clone)['assignments'], [])
        self.assertNotEqual(duty.get_roster(user, clone)['updated_at'], before['updated_at'])
        published = duty.get_roster(user, roster)
        self.assertEqual(published['assignments'][0]['snapshot']['name'], '打包垃圾')
        self.assertEqual(published['assignments'][0]['person_ids'], [person])

    def test_warnings_acknowledgement_and_blocking_disabled_person(self):
        user, person, _, _ = self.environment()
        roster = self.draft(user)
        r = duty.get_roster(user, roster)
        self.assertTrue(r['checks']['warnings'])
        with self.assertRaises(ValueError):
            duty.publish_roster(user, {'roster_id': roster, 'expected_updated_at': r['updated_at']})
        self.assign(user, roster, person)
        with app.database_connection() as conn:
            conn.execute('UPDATE duty_people SET active=0 WHERE person_id=?', (person,))
        self.assertTrue(duty.get_roster(user, roster)['checks']['blocking'])
        with self.assertRaises(ValueError):
            self.publish(user, roster)

    def test_overlapping_roster_conflict_and_old_snapshot_preserved(self):
        user, person, _, _ = self.environment()
        roster = self.draft(user)
        self.assign(user, roster, person)
        self.publish(user, roster)
        with app.database_connection() as conn:
            conn.execute("UPDATE duty_people SET full_name='範例員工01新版' WHERE person_id=?", (person,))
        self.assertEqual(duty.get_roster(user, roster)['assignments'][0]['snapshot']['people'][person]['full_name'], '範例員工01')
        preview = duty.notification_preview(user, roster)
        self.assertEqual(preview['messages'][0]['name'], '範例員工01')
        self.assertIn('負責人：範例員工01', preview['group_message'])
        overlap = self.draft(user, date_from='2026-10-15', date_to='2026-11-14')
        self.assertTrue(duty.get_roster(user, overlap)['checks']['blocking'])
        with self.assertRaises(ValueError):
            self.publish(user, overlap)

    def test_substitution_conflicts_and_dates(self):
        user, person, substitute, _ = self.environment()
        roster = self.draft(user)
        sub = {'original_person_id': person, 'substitute_person_id': substitute, 'date_from': '2026-10-06', 'date_to': '2026-10-06'}
        self.assign(user, roster, person, [sub])
        self.assertFalse(duty.get_roster(user, roster)['checks']['blocking'])
        with app.database_connection() as conn:
            self.assertEqual(len(duty.reference_impacts(conn,user['organization_id'],'person',substitute)),1)
        preview = duty.notification_preview(user,roster)
        self.assertEqual(len(preview['messages']),2)
        self.assertIn('代班 2026-10-06',preview['group_message'])
        self.assign(user, roster, person, [sub, sub])
        self.assertTrue(duty.get_roster(user, roster)['checks']['blocking'])
        with self.assertRaises(ValueError):
            self.assign(user, roster, person, [{**sub, 'date_to': '2026-11-01'}])

    def test_annual_work_inherited_readonly_and_no_send(self):
        user, person, _, _ = self.environment(rotation='year')
        year = self.draft(user, period_type='year', date_from='2026-01-01', date_to='2026-12-31', name='2026')
        self.assign(user, year, person)
        self.publish(user, year)
        month = self.draft(user)
        assignment = duty.get_roster(user, month)['assignments'][0]
        self.assertTrue(assignment['snapshot']['inherited'])
        self.assertEqual(assignment['person_ids'], [person])
        with self.assertRaises(ValueError):
            self.assign(user, month, '')
        self.assertEqual(duty.notification_preview(user, month)['push_count'], 0)
        with self.assertRaises(ValueError):
            self.publish(user, month, send_now=True)

    def test_readonly_operator_drafts_hidden_and_cross_org_denied(self):
        user, person, _, _ = self.environment()
        roster = self.draft(user)
        operator = reports.account(roles.SENDER)
        self.assertFalse(duty.roster_rows(operator)['rosters'])
        with self.assertRaises(PermissionError):
            duty.get_roster(operator, roster)
        self.assign(user, roster, person)
        self.publish(user, roster)
        self.assertEqual(duty.get_roster(operator, roster)['version'], 1)
        with self.assertRaises(PermissionError):
            self.publish(operator, roster)
        other_user = {**user, 'organization_id': roles.ORG_B}
        with self.assertRaises((PermissionError, ValueError)):
            duty.get_roster(other_user, roster)

    def test_stale_draft_save_and_published_delete_rejected(self):
        user, person, _, _ = self.environment()
        roster = self.draft(user)
        original = duty.get_roster(user, roster)
        self.assign(user, roster, person)
        with self.assertRaises(ValueError):
            duty.save_draft(user, {'roster_id': roster, 'expected_updated_at': original['updated_at'], 'assignments': original['assignments']})
        self.publish(user, roster)
        with self.assertRaises(ValueError):
            duty.delete_draft(user, {'roster_id': roster, 'expected_updated_at': duty.get_roster(user, roster)['updated_at']})

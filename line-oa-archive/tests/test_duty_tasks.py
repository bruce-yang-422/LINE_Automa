import unittest
from unittest.mock import patch
import app
import duty
import test_duty_people as people_tests


class DutyTasksTests(unittest.TestCase):
    setUp = people_tests.DutyPeopleTests.setUp
    setup_roles_environment = people_tests.DutyPeopleTests.setup_roles_environment
    prepare = people_tests.DutyPeopleTests.prepare

    def task(self):
        return {'name': '掃地與擦拭（主機區域）', 'effective_from': '2026-10-01', 'rotation': 'month',
                'items': [{'content': '每日清潔', 'frequency': 'daily', 'reminder_enabled': True, 'reminder_time': '08:30'},
                          {'content': '週二拖地', 'frequency': 'weekly', 'weekdays': [1], 'reminder_enabled': True, 'reminder_time': '08:30'}]}

    def test_daily_weekly_merge_and_exclusions(self):
        task = self.task()
        days = duty.execution_preview(task, '2026-10-06')
        self.assertEqual(len(days), 14)
        self.assertEqual(days[0]['due'], ['每日清潔', '週二拖地'])
        self.assertEqual(days[0]['reminders'], [{'time': '08:30', 'contents': ['每日清潔', '週二拖地']}])
        self.assertEqual(days[1]['due'], ['每日清潔'])
        task['items'][0]['excluded_dates'] = ['2026-10-06']
        self.assertEqual(duty.execution_preview(task, '2026-10-06')[0]['due'], ['週二拖地'])

    def test_month_half_ranges_annual_unset_and_rest(self):
        task = self.task()
        task['items'] = [{'content': '前半月', 'frequency': 'monthly', 'day_start': 1, 'day_end': 15},
                         {'content': '後半月', 'frequency': 'monthly', 'day_start': 16, 'day_end': 31},
                         {'content': '年度', 'frequency': 'annual', 'annual_date': ''}]
        days = duty.execution_preview(task, '2026-10-15')
        self.assertEqual(days[0]['due'], ['前半月'])
        self.assertEqual(days[1]['due'], ['後半月'])
        task['items'][-1]['annual_date'] = '10-16'
        self.assertEqual(duty.execution_preview(task, '2026-10-16')[0]['due'], ['後半月', '年度'])
        task['kind'] = 'rest'
        self.assertFalse(any(d['due'] for d in duty.execution_preview(task)))

    def test_version_effective_date_and_reference_confirmation(self):
        user = self.prepare()
        result = duty.save_task(user, self.task())
        record = duty.list_tasks(user)['tasks'][0]
        payload = {**self.task(), 'name': '清潔新版', 'task_id': result['task_id'], 'effective_from': '2026-11-01', 'expected_updated_at': record['updated_at']}
        with patch.object(duty, 'reference_impacts', return_value=['2026/11 草稿']):
            with self.assertRaises(ValueError):
                duty.save_task(user, payload)
            duty.save_task(user, {**payload, 'confirm_impacts': True, 'impacts': ['2026/11 草稿'], 'reason': '調整內容'})
        with patch.object(duty, 'today', return_value=duty.checked_date('2026-10-06')):
            record = duty.list_tasks(user)['tasks'][0]
            self.assertEqual(record['current']['name'], '掃地與擦拭（主機區域）')
            self.assertEqual(record['versions'][0]['name'], '清潔新版')
            self.assertEqual(len(record['versions']), 2)

    def test_invalid_dates_weekdays_time_and_missing_time(self):
        for item in [{'content': 'x', 'frequency': 'weekly', 'weekdays': []},
                     {'content': 'x', 'frequency': 'annual', 'annual_date': '02-30'},
                     {'content': 'x', 'day_start': 16, 'day_end': 15},
                     {'content': 'x', 'reminder_time': '25:00'},
                     {'content': 'x', 'excluded_dates': ['2026-02-30']}]:
            with self.assertRaises(ValueError):
                duty.execution_preview({**self.task(), 'items': [item]})
        days = duty.execution_preview({**self.task(), 'items': [{'content': 'x', 'reminder_enabled': True}]})
        self.assertTrue(days[0]['due'])
        self.assertFalse(days[0]['reminders'])

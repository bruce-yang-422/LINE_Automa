import csv
import io
import unittest
from unittest.mock import patch
import app
import duty
import reports
import test_duty_people as people_tests
import test_roles_and_permissions as roles


def csv_text(headers,rows):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return '\ufeff'+stream.getvalue()


class DutyCsvTests(unittest.TestCase):
    setUp=people_tests.DutyPeopleTests.setUp
    prepare=people_tests.DutyPeopleTests.prepare
    setup_roles_environment=people_tests.DutyPeopleTests.setup_roles_environment
    server=people_tests.DutyPeopleTests.server
    request=people_tests.DutyPeopleTests.request

    def commit(self,user,payload):
        preview=duty.csv_import(user,payload)
        self.assertTrue(preview['can_import'],preview['errors'])
        return duty.csv_import(user,{**payload,'confirm':True,'preview_signature':preview['preview_signature']})

    def test_employee_list_preview_bom_skip_x_export_roundtrip(self):
        user=self.prepare()
        raw=csv_text(['樓層','部門','姓名','英文名/暱稱','職稱','分機','備註'],[['2F','管理部','範例員工01','範例暱稱01','電商助理','#27',''],['','','X','','','','']])
        payload={'kind':'people','text':raw,'effective_from':'2026-01-01'}
        preview=duty.csv_import(user,payload)
        self.assertEqual((preview['added'],preview['skipped']),(1,1))
        self.assertFalse(duty.list_people(user)['people'])
        self.commit(user,payload)
        exported=duty.csv_export(user,{'kind':'people'})
        self.assertTrue(exported['content'].startswith('\ufeff'))
        self.assertIn('範例員工01',exported['content'])
        self.assertEqual(self.commit(user,{'kind':'people','text':exported['content']})['added'],0)
        self.assertEqual(len(duty.list_people(user)['people']),1)

    def test_work_multi_item_roundtrip_and_multiline_quoted_text(self):
        user=self.prepare()
        base=['掃地與擦拭','含櫃子、桌椅\n"清潔"','主機區域','一般','每月','0','1','2026-01-01']
        raw=csv_text(duty.TASK_CSV_HEADERS,[base+['掃地','每日','','1','31','','2026-10-10','08:30','1'],base+['拖地','每週','2','1','31','','','08:30','1']])
        self.commit(user,{'kind':'tasks','text':raw})
        task=duty.list_tasks(user)['tasks'][0]
        self.assertEqual(len(task['versions'][0]['items']),2)
        self.assertEqual(task['versions'][0]['items'][1]['weekdays'],[1])
        self.assertEqual(task['versions'][0]['description'],base[1])
        exported=duty.csv_export(user,{'kind':'tasks'})
        result=self.commit(user,{'kind':'tasks','text':exported['content']})
        self.assertEqual((result['added'],result['skipped']),(0,1))

    def test_validation_no_partial_writes_duplicate_conflict_and_capacity(self):
        user=self.prepare()
        raw=csv_text(duty.PEOPLE_CSV_HEADERS,[['範例員工01','','管理部','2F','','2026-01-01','1'],['範例員工02','','管理部','2F','','bad','1']])
        payload={'kind':'people','text':raw}
        result=duty.csv_import(user,payload)
        self.assertFalse(result['can_import'])
        with self.assertRaises(ValueError):
            duty.csv_import(user,{**payload,'confirm':True,'preview_signature':result['preview_signature']})
        self.assertFalse(duty.list_people(user)['people'])
        raw=csv_text(['姓名','部門'],[['範例員工01','管理部']])
        self.commit(user,{'kind':'people','text':raw})
        self.assertFalse(duty.csv_import(user,{'kind':'people','text':csv_text(['姓名','部門'],[['範例員工01','網路部']])})['can_import'])
        with patch.object(duty.limits,'DUTY_PEOPLE_PER_ORG',1):
            self.assertFalse(duty.csv_import(user,{'kind':'people','text':csv_text(['姓名'],[['範例員工02']])})['can_import'])

    def test_stale_preview_and_transaction_rollback(self):
        user=self.prepare()
        payload={'kind':'tasks','text':csv_text(['工作名稱'],[['掃地'],['倒垃圾']])}
        preview=duty.csv_import(user,payload)
        duty.save_task(user,{'name':'擦桌子','effective_from':'2026-01-01'})
        with self.assertRaises(ValueError):
            duty.csv_import(user,{**payload,'confirm':True,'preview_signature':preview['preview_signature']})
        preview=duty.csv_import(user,payload)
        original=duty.save_task
        calls=[]
        def failing(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise ValueError('test failure')
            return original(*args,**kwargs)
        with patch.object(duty,'save_task',side_effect=failing):
            with self.assertRaises(ValueError):
                duty.csv_import(user,{**payload,'confirm':True,'preview_signature':preview['preview_signature']})
        self.assertEqual(len(duty.list_tasks(user)['tasks']),1)

    def test_permissions_scope_preview_and_csv_formula_protection(self):
        user=self.prepare()
        operator=reports.account(roles.SENDER)
        for method in (duty.csv_export,duty.csv_import):
            with self.assertRaises(PermissionError):method(operator,{'kind':'people','text':'姓名\n測試'})
            with self.assertRaises(PermissionError):method(user,{'kind':'people','org_id':roles.ORG_B,'text':'姓名\n測試'})
        with self.assertRaises(PermissionError):duty.csv_import(user,{'kind':'people','text':'姓名\n測試'},preview=True)
        self.commit(user,{'kind':'people','text':csv_text(['姓名','英文名/暱稱'],[['測試','=HYPERLINK("bad")']])})
        exported=duty.csv_export(user,{'kind':'people'},preview=True)
        self.assertIn("'=HYPERLINK",exported['content'])
        self.assertEqual(self.commit(user,{'kind':'people','text':exported['content']})['added'],0)
        for value in ('+cmd','-cmd','@cmd',' =cmd','\tcmd'):
            self.assertTrue(duty.csv_cell(value).startswith("'"))

    def test_bad_headers_weekday_and_size(self):
        user=self.prepare()
        for raw in ('wrong\n姓名','姓名,姓名\n甲,乙','姓名\n甲,乙'):
            try:result=duty.csv_import(user,{'kind':'people','text':raw})
            except ValueError:continue
            self.assertFalse(result['can_import'])
        raw=csv_text(['工作名稱','執行內容','執行頻率','星期'],[['倒垃圾','打包','每週','8']])
        self.assertFalse(duty.csv_import(user,{'kind':'tasks','text':raw})['can_import'])
        with patch.object(duty.limits,'DUTY_CSV_MAX_BYTES',1):
            with self.assertRaises(ValueError):duty.csv_import(user,{'kind':'people','text':'姓名\n甲'})

    def test_roster_import_draft_substitution_export_and_readonly(self):
        user=self.prepare()
        for name in ('範例員工01','範例員工02'):
            duty.save_person(user,{'full_name':name,'effective_from':'2026-01-01'})
        duty.save_task(user,{'name':'倒垃圾','effective_from':'2026-01-01'})
        raw=csv_text(duty.ROSTER_CSV_HEADERS,[['十月','月','2026-10-01','2026-10-31','倒垃圾','範例員工01','記得打包','範例員工01','範例員工02','2026-10-08','2026-10-09']])
        result=self.commit(user,{'kind':'rosters','text':raw})
        roster=duty.get_roster(user,result['roster_ids'][0])
        self.assertEqual(roster['status'],'draft')
        self.assertEqual(len(roster['assignments'][0]['substitutions']),1)
        self.assertEqual(roster['assignments'][0]['note'],'記得打包')
        exported=duty.csv_export(user,{'kind':'rosters','roster_id':roster['roster_id']})
        self.assertIn('範例員工02',exported['content'])
        self.assertFalse(duty.csv_import(user,{'kind':'rosters','text':exported['content']})['can_import'])
        operator=reports.account(roles.SENDER)
        with self.assertRaises(PermissionError):duty.csv_export(operator,{'kind':'rosters','roster_id':roster['roster_id']})
        duty.publish_roster(user,{'roster_id':roster['roster_id'],'expected_updated_at':roster['updated_at'],'acknowledged':[w['key'] for w in roster['checks']['warnings']]})
        self.assertIn('倒垃圾',duty.csv_export(operator,{'kind':'rosters','roster_id':roster['roster_id']})['content'])
        clone=self.commit(user,{'kind':'rosters','text':exported['content']})
        self.assertEqual(duty.get_roster(user,clone['roster_ids'][0])['status'],'draft')
        with self.assertRaises(PermissionError):duty.csv_import(operator,{'kind':'rosters','text':raw})

    def test_roster_invalid_reference_conflict_dates_and_atomicity(self):
        user=self.prepare()
        duty.save_person(user,{'full_name':'範例員工01','effective_from':'2026-01-01'})
        duty.save_task(user,{'name':'倒垃圾','effective_from':'2026-01-01'})
        base=['十月','月','2026-10-01','2026-10-31','倒垃圾','黄範例暱稱01','','','','','']
        result=duty.csv_import(user,{'kind':'rosters','text':csv_text(duty.ROSTER_CSV_HEADERS,[base])})
        self.assertFalse(result['can_import'])
        self.assertIn('找不到',result['errors'][0]['message'])
        base[5]='範例員工01'
        payload={'kind':'rosters','text':csv_text(duty.ROSTER_CSV_HEADERS,[base])}
        preview=duty.csv_import(user,payload)
        with patch.object(duty,'save_draft',side_effect=ValueError('test failure')):
            with self.assertRaises(ValueError):
                duty.csv_import(user,{**payload,'confirm':True,'preview_signature':preview['preview_signature']})
        self.assertFalse(duty.roster_rows(user)['rosters'])

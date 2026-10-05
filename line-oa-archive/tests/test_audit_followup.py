"""Unit tests for Phase 6 Audit Follow-up requirements."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['DATABASE_PATH'] = ':memory:'

import app
from oa_fixture import CHANNEL, register_oa, use_oa
import cases
import chat_notes
import channels
import template_packs
import admin_server


class AuditFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "instance").mkdir()
        (self.root / "schema.sql").write_bytes((app.BASE_DIR / "schema.sql").read_bytes())

        for target, value in (("BASE_DIR", self.root), ("DATABASE_PATH", self.root / "test.db")):
            p = patch.object(app, target, value)
            p.start()
            self.addCleanup(p.stop)

        p = patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://reports.example.test"}, clear=True)
        p.start()
        self.addCleanup(p.stop)

        app.initialize_database()

        register_oa()

        use_oa(self)

        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, custom_name, active) VALUES (current_channel(), 'U_test_1', 'user', 'Bob', '鮑伯', 1)"
            )

    def tearDown(self):
        channels._current.set("")

    def test_custom_template_packs_crud_and_limits(self):
        with app.database_connection() as conn:
            # 1. Create custom pack
            pack = template_packs.save_custom_pack(conn, 'org_A', {
                'name': '客製化服務流程',
                'description': '適用於特定專案服務',
                'note_types': ['一般備忘', '專案備忘', '會議'],
                'case_categories': ['一般備忘', '諮詢', '報價']
            }, 'admin@test.com')
            pack_id = pack['pack_id']
            self.assertTrue(bool(pack_id))

            # 2. Duplicate name check
            with self.assertRaises(ValueError):
                template_packs.save_custom_pack(conn, 'org_A', {'name': '客製化服務流程'}, 'admin@test.com')

            # 3. Lock & edit protection
            template_packs.toggle_pack_lock(conn, 'org_A', pack_id, True, 'admin@test.com')
            with self.assertRaises(ValueError):
                template_packs.save_custom_pack(conn, 'org_A', {'pack_id': pack_id, 'name': '修改名稱'}, 'admin@test.com')
            with self.assertRaises(ValueError):
                template_packs.delete_custom_pack(conn, 'org_A', pack_id, 'admin@test.com')

            # Unlock
            template_packs.toggle_pack_lock(conn, 'org_A', pack_id, False, 'admin@test.com')

            # 4. Copy pack
            copied = template_packs.copy_pack(conn, 'org_A', pack_id, '客製化服務流程 (複製)', 'admin@test.com')
            self.assertEqual(copied['name'], '客製化服務流程 (複製)')

            # 5. Delete pack
            ok = template_packs.delete_custom_pack(conn, 'org_A', copied['pack_id'], 'admin@test.com')
            self.assertTrue(ok)

    def test_custom_templates_crud_and_source_conversion(self):
        with app.database_connection() as conn:
            pack = template_packs.save_custom_pack(conn, 'org_A', {'name': '專案範本包'}, 'admin@test.com')
            pack_id = pack['pack_id']

            # 1. Create case template
            ct = template_packs.save_template(conn, 'org_A', 'case', {
                'pack_id': pack_id,
                'name': '標準報修範本',
                'category_name': '報修',
                'title': '{聯絡對象} - 設備報修',
                'body': '設備名稱：\n故障現象：\n報修日期：{今天}'
            }, 'admin@test.com')
            tmpl_id = ct['template_id']

            # 2. Create note template
            nt = template_packs.save_template(conn, 'org_A', 'note', {
                'pack_id': pack_id,
                'name': '會議備忘範本',
                'category_name': '一般備忘',
                'title': '專案會議 - {今天}',
                'body': '會議重點：\n決議事項：'
            }, 'admin@test.com')

            # 3. Create case and convert to template
            test_case = cases.create_case(conn, {
                'title': '伺服器異常檢修',
                'case_subject_id': 'U_test_1',
                'category': 'IT 報修',
                'description': '機房主機連線逾時，需安排工程師現場確認。'
            }, 'admin@test.com')

            case_tmpl = template_packs.create_template_from_source(
                conn, 'org_A', 'case', test_case['case_id'], pack_id, '主機檢修標準範本', 'admin@test.com'
            )
            self.assertEqual(case_tmpl['name'], '主機檢修標準範本')

            # 4. Create chat note and convert to template
            test_note = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_test_1',
                'title': '客戶拜訪紀錄',
                'content': '談定次月採購數量 50 台。',
                'note_type': '商務'
            }, 'admin@test.com')

            note_tmpl = template_packs.create_template_from_source(
                conn, 'org_A', 'note', test_note['note_id'], pack_id, '採購談定範本', 'admin@test.com'
            )
            self.assertEqual(note_tmpl['name'], '採購談定範本')

    def test_single_category_management(self):
        with app.database_connection() as conn:
            # 1. Add single category
            cats = template_packs.save_single_category(conn, CHANNEL, 'case', 'VIP 諮詢', actor='admin@test.com')
            names = [c['name'] for c in cats['case_categories']]
            self.assertIn('VIP 諮詢', names)

            # 2. Rename category and verify cascade to cases
            c = cases.create_case(conn, {
                'title': 'VIP 專屬諮詢',
                'case_subject_id': 'U_test_1',
                'category': 'VIP 諮詢',
                'description': '測試'
            }, 'admin@test.com')
            self.assertEqual(c['category'], 'VIP 諮詢')

            cats = template_packs.save_single_category(conn, CHANNEL, 'case', '頂級 VIP 諮詢', old_name='VIP 諮詢', actor='admin@test.com')
            c_updated = cases.get_case(conn, c['case_id'])
            self.assertEqual(c_updated['category'], '頂級 VIP 諮詢')

            # 3. Delete category -> defaults to '一般備忘'
            cats = template_packs.delete_single_category(conn, CHANNEL, 'case', '頂級 VIP 諮詢', actor='admin@test.com')
            c_after_delete = cases.get_case(conn, c['case_id'])
            self.assertEqual(c_after_delete['category'], '一般備忘')

            # 4. '一般備忘' cannot be deleted or renamed
            with self.assertRaises(ValueError):
                template_packs.delete_single_category(conn, CHANNEL, 'case', '一般備忘', actor='admin@test.com')
            with self.assertRaises(ValueError):
                template_packs.save_single_category(conn, CHANNEL, 'case', '修改一般', old_name='一般備忘', actor='admin@test.com')

    def test_note_tags_and_completion_and_conflict(self):
        with app.database_connection() as conn:
            # 1. Save note with tags
            for name in ['交接', '早班']:
                chat_notes.save_note_tag(conn, name, actor_role='org_admin')
            n = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_test_1',
                'title': '交接筆記',
                'content': '明天早班請先開門',
                'tags': ['交接', '早班']
            }, 'admin@test.com')
            note_id = n['note_id']

            # 2. Toggle completion
            res = chat_notes.toggle_note_completed(conn, note_id)
            self.assertEqual(res['is_completed'], 1)
            res2 = chat_notes.toggle_note_completed(conn, note_id)
            self.assertEqual(res2['is_completed'], 0)

            # 3. Tag management: rename tag across notes
            tags_info = chat_notes.save_note_tag(conn, '交接事項', old_name='交接')
            tag_names = [t['name'] for t in tags_info['tags']]
            self.assertIn('交接事項', tag_names)

            # 4. Conflict check
            with self.assertRaises(ValueError):
                chat_notes.save_chat_note(conn, {
                    'note_id': note_id,
                    'recipient_id': 'U_test_1',
                    'content': '衝突編輯測試',
                    'expected_updated_at': '2020-01-01T00:00:00Z'
                }, 'bob@test.com')

    def test_case_notify_and_overdue_filter(self):
        with app.database_connection() as conn:
            # 1. Create overdue case (due yesterday)
            c = cases.create_case(conn, {
                'title': '逾期處理案件',
                'case_subject_id': 'U_test_1',
                'due_date': '2020-01-01',
                'description': '逾期測試'
            }, 'admin@test.com')
            case_id = c['case_id']

            # 2. Query overdue cases
            overdue_list = cases.list_cases(conn, status='overdue')
            self.assertTrue(any(x['case_id'] == case_id for x in overdue_list))

            # 3. Notify case subject
            with patch.object(admin_server, 'send_push') as push:
                notified = cases.notify_case_subject(conn, case_id, '您的案件進度已更新，請查收。', 'admin@test.com')
                push.assert_called_once()
                self.assertEqual(len(notified['activities']), 2)
                self.assertEqual(notified['activities'][1]['activity_type'], 'notify')


if __name__ == '__main__':
    unittest.main()

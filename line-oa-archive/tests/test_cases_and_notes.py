"""Unit tests for Case Management, Chat Notes, Saved Filters, and Quantity Limits."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ['DATABASE_PATH'] = ':memory:'

import app
import cases
import chat_notes
import recipients
import channels


class CasesAndNotesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        app.DATABASE_PATH = self.db_path
        app.initialize_database()
        
        # Setup test channel and recipient
        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO line_channels (channel_id, owner_email, name, bot_user_id, token_cipher, secret_cipher) VALUES (?, ?, ?, ?, ?, ?)",
                ("chan_1", "admin@test.com", "Test OA", "U_bot_1", "t", "s")
            )
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, alias) VALUES (?, ?, ?, ?, ?)",
                ("chan_1", "U_user_1", "user", "Alice", "愛麗絲")
            )
        channels._current.set("chan_1")

    def tearDown(self):
        channels._current.set("")
        self.temp_dir.cleanup()

    def test_case_lifecycle(self):
        with app.database_connection() as conn:
            # 1. Create case
            c = cases.create_case(conn, {
                'title': '諮詢保固問題',
                'case_subject_id': 'U_user_1',
                'priority': 'high',
                'description': '客戶詢問吸塵器保固範圍與維修地點'
            }, 'admin@test.com')
            self.assertEqual(c['status'], 'pending')
            self.assertEqual(c['priority'], 'high')
            self.assertTrue(c['case_no'].startswith('CASE-'))
            self.assertEqual(len(c['activities']), 1)
            self.assertEqual(c['activities'][0]['activity_type'], 'create_case')

            case_id = c['case_id']

            # 2. Transition pending -> processing
            c = cases.transition_case(conn, case_id, 'processing', {}, 'admin@test.com')
            self.assertEqual(c['status'], 'processing')

            # 3. Transition processing -> waiting (requires waiting_party and waiting_reason)
            with self.assertRaises(ValueError):
                cases.transition_case(conn, case_id, 'waiting', {}, 'admin@test.com')
            
            c = cases.transition_case(conn, case_id, 'waiting', {
                'waiting_party': 'case_subject',
                'waiting_reason': '等待客戶提供購買發票照片'
            }, 'admin@test.com')
            self.assertEqual(c['status'], 'waiting')
            self.assertEqual(c['waiting_party'], 'case_subject')
            self.assertEqual(c['waiting_reason'], '等待客戶提供購買發票照片')
            self.assertTrue(bool(c['waiting_since']))

            # 4. Transition waiting -> processing
            c = cases.transition_case(conn, case_id, 'processing', {}, 'admin@test.com')
            self.assertEqual(c['status'], 'processing')

            # 5. Add custom activity
            act = cases.add_activity(conn, case_id, 'note', 'admin@test.com', '已轉交維修中心處理')
            self.assertEqual(act['activity_type'], 'note')

            # 6. Transition processing -> ready_to_close
            c = cases.transition_case(conn, case_id, 'ready_to_close', {}, 'admin@test.com')
            self.assertEqual(c['status'], 'ready_to_close')

            # 7. Transition ready_to_close -> closed (requires resolution)
            with self.assertRaises(ValueError):
                cases.transition_case(conn, case_id, 'closed', {}, 'admin@test.com')

            c = cases.transition_case(conn, case_id, 'closed', {
                'resolution': '已於今日派工維修完成並完成電話滿意度調查'
            }, 'admin@test.com')
            self.assertEqual(c['status'], 'closed')
            self.assertEqual(c['resolution'], '已於今日派工維修完成並完成電話滿意度調查')
            self.assertTrue(bool(c['closed_at']))

            # 8. Invalid transition: closed -> processing is prohibited
            with self.assertRaises(ValueError):
                cases.transition_case(conn, case_id, 'processing', {}, 'admin@test.com')

    def test_chat_notes_and_limits(self):
        with app.database_connection() as conn:
            # Create notes
            n1 = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_user_1',
                'content': '10/01 答應週五前回覆報價'
            }, 'admin@test.com')
            self.assertEqual(n1['content'], '10/01 答應週五前回覆報價')

            n2 = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_user_1',
                'content': '客戶偏好使用 Email 接收報表'
            }, 'admin@test.com')
            
            res = chat_notes.list_chat_notes(conn, 'U_user_1')
            self.assertEqual(res['count'], 2)
            self.assertEqual(res['limit'], 100)

            # Edit note
            chat_notes.save_chat_note(conn, {
                'note_id': n1['note_id'],
                'recipient_id': 'U_user_1',
                'content': '10/01 答應週五前回覆報價（已提前週四送達）'
            }, 'admin@test.com')
            
            res = chat_notes.list_chat_notes(conn, 'U_user_1')
            self.assertEqual(res['notes'][1]['content'], '10/01 答應週五前回覆報價（已提前週四送達）')

            # Delete note
            chat_notes.delete_chat_note(conn, n2['note_id'])
            res = chat_notes.list_chat_notes(conn, 'U_user_1')
            self.assertEqual(res['count'], 1)

    def test_saved_filters(self):
        with app.database_connection() as conn:
            f1 = chat_notes.save_saved_filter(conn, {
                'name': 'VIP 公務客戶',
                'criteria': {'kind': 'user', 'contact_type': 'person_business'}
            })
            self.assertEqual(f1['name'], 'VIP 公務客戶')

            # Duplicate name rejected
            with self.assertRaises(ValueError):
                chat_notes.save_saved_filter(conn, {
                    'name': 'VIP 公務客戶',
                    'criteria': {}
                })

            res = chat_notes.list_saved_filters(conn)
            self.assertEqual(res['count'], 1)
            self.assertEqual(res['limit'], 10)

            chat_notes.delete_saved_filter(conn, f1['filter_id'])
            res = chat_notes.list_saved_filters(conn)
            self.assertEqual(res['count'], 0)

    def test_tag_limits(self):
        with app.database_connection() as conn:
            # 1. Per contact limit (10)
            tag_ids = []
            for i in range(12):
                tid = recipients.save_tag(conn, f"Tag_{i}")
                tag_ids.append(tid)

            recipients.set_contact_tags(conn, 'U_user_1', tag_ids)
            contacts = recipients.list_contacts(conn)
            self.assertEqual(len(contacts[0]['tags']), 10)

            # 2. Bulk tag update skips contacts with 10 tags
            res = recipients.bulk_update_tags(conn, ['U_user_1'], [tag_ids[11]], 'add')
            self.assertEqual(res['skipped'], 1)


if __name__ == '__main__':
    unittest.main()

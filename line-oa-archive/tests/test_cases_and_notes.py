"""Unit tests for Case Management, Chat Notes, Saved Filters, and Quantity Limits."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ['DATABASE_PATH'] = ':memory:'

import app
from oa_fixture import CHANNEL, add_account, register_oa, use_oa
import cases
import chat_notes
import recipients
import channels


from unittest.mock import patch

class CasesAndNotesTests(unittest.TestCase):
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

        add_account('boss@test.com', 'org_admin', 'A', 'Boss')

        # Setup test recipient
        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, custom_name, active) VALUES (current_channel(), ?, 'user', 'Alice', '愛麗絲', 1)",
                ("U_user_1",)
            )

    def tearDown(self):
        channels._current.set("")

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
            self.assertTrue(c['case_no'].startswith('TESTOA-'))
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

    def test_http_case_and_notes_endpoints(self):
        import json
        from urllib.request import Request, urlopen
        import admin_server
        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok:
                    handler.user = {"email": "boss@test.com", "role": "org_admin", "organization_id": "A", "display_name": "Boss"}
                    handler.identity = handler.user["email"]
                return ok

        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}

        # 1. POST /api/cases (Create case)
        payload = {"title": "測試案件建立", "case_subject_id": "U_user_1", "priority": "normal", "description": "測試內容"}
        req = Request(f"{base}/api/cases", data=json.dumps(payload).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            case_id = data["case"]["case_id"]
            self.assertEqual(data["case"]["title"], "測試案件建立")

        # 2. GET /api/cases
        req = Request(f"{base}/api/cases", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("cases", data)
            self.assertEqual(len(data["cases"]), 1)

        # 3. GET /api/cases/{case_id}
        req = Request(f"{base}/api/cases/{case_id}", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["case"]["case_id"], case_id)

        # 4. POST /api/cases/{case_id} (Status transition)
        req = Request(f"{base}/api/cases/{case_id}", data=json.dumps({"status": "processing"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data["case"]["status"], "processing")

        # 5. POST /api/chat-notes (Create note)
        req = Request(f"{base}/api/chat-notes", data=json.dumps({"recipient_id": "U_user_1", "content": "重要客戶紀錄"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            note_id = data["note"]["note_id"]

        # 6. GET /api/chat-notes?recipient_id=U_user_1
        req = Request(f"{base}/api/chat-notes?recipient_id=U_user_1", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["notes"][0]["note_id"], note_id)


if __name__ == '__main__':
    unittest.main()

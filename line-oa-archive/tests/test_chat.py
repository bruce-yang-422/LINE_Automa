import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.request import Request, urlopen

import app
import admin_server
import chat


class ChatSystemTests(unittest.TestCase):
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

        p = patch.dict(os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "fake-test-token"}, clear=True)
        p.start()
        self.addCleanup(p.stop)

        app.initialize_database()

        self.user1 = "U11111111111111111111111111111111"
        self.group1 = "C11111111111111111111111111111111"

        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO recipients (recipient_id, kind, display_name, alias, active) VALUES (?, 'user', 'Alice', '小愛', 1)",
                (self.user1,)
            )
            conn.execute(
                "INSERT INTO recipients (recipient_id, kind, display_name, alias, active) VALUES (?, 'group', 'Sales Group', '', 1)",
                (self.group1,)
            )

    def test_chat_rooms_and_messages_flow(self):
        with app.database_connection() as conn:
            past_ts = "2025-01-01T10:00:00.000Z"
            # 1. Inbound message from Alice
            conn.execute(
                """INSERT INTO line_messages
                   (channel_id, message_id, conversation_type, conversation_id, sender_user_id, message_type, text_content, sent_at, direction, reply_token)
                   VALUES (current_channel(), 'msg_1', 'user', ?, ?, 'text', '您好，想詢問發票開立', ?, 'inbound', 'token_123')""",
                (self.user1, self.user1, past_ts)
            )
            conn.execute(
                """INSERT INTO chat_state (channel_id, chat_id, status, last_inbound_at)
                   VALUES (current_channel(), ?, 'open', ?)""",
                (self.user1, past_ts)
            )

            # Check chat rooms
            rooms = chat.list_chat_rooms(conn)
            self.assertEqual(rooms["total"], 2)
            self.assertEqual(rooms["unread_count"], 1)

            alice_room = next(r for r in rooms["rooms"] if r["recipient_id"] == self.user1)
            self.assertEqual(alice_room["name"], "小愛")
            self.assertEqual(alice_room["unread_count"], 1)
            self.assertEqual(alice_room["last_message"]["text_content"], "您好，想詢問發票開立")

            # Mark read
            chat.mark_chat_read(conn, self.user1)
            rooms_after_read = chat.list_chat_rooms(conn)
            self.assertEqual(rooms_after_read["unread_count"], 0)

            # Set status to pending and done
            chat.set_chat_status(conn, self.user1, "pending", "admin@stack-base.com")
            room_pending = chat.list_chat_rooms(conn, status="pending")
            self.assertEqual(len(room_pending["rooms"]), 1)

            # List messages
            msg_res = chat.list_messages(conn, self.user1)
            self.assertEqual(len(msg_res["messages"]), 1)
            self.assertEqual(msg_res["messages"][0]["text_content"], "您好，想詢問發票開立")
            self.assertEqual(msg_res["messages"][0]["sender_name"], "小愛")

    def test_canned_replies_crud(self):
        with app.database_connection() as conn:
            # 1. Create canned reply
            r1 = chat.save_canned_reply(conn, {"title": "問候語", "category": "常用", "content": "您好！很高興為您服務。"}, "admin")
            self.assertTrue(r1["id"].startswith("canned_"))

            # 2. List canned replies
            res = chat.list_canned_replies(conn)
            self.assertEqual(res["count"], 1)
            self.assertEqual(res["replies"][0]["title"], "問候語")

            # 3. Update canned reply
            chat.save_canned_reply(conn, {"id": r1["id"], "title": "熱情問候", "category": "常用", "content": "哈囉！有什麼能協助您的嗎？"}, "admin")
            res2 = chat.list_canned_replies(conn)
            self.assertEqual(res2["replies"][0]["title"], "熱情問候")

            # 4. Delete canned reply
            chat.delete_canned_reply(conn, r1["id"])
            res3 = chat.list_canned_replies(conn)
            self.assertEqual(res3["count"], 0)

    def test_send_chat_message_and_mock_line_api(self):
        with app.database_connection() as conn:
            with patch("line_api.request") as mock_req:
                mock_req.return_value = {}

                # Send push message
                res = chat.send_chat_message(conn, self.user1, "我們已收到您的詢問，稍候為您確認。", "admin@test.com", use_reply_token=False)
                self.assertTrue(res["ok"])
                self.assertEqual(res["send_method"], "push")
                mock_req.assert_called_with("message/push", {"to": self.user1, "messages": [{"type": "text", "text": "我們已收到您的詢問，稍候為您確認。"}]})

                # Verify message is in db as outbound
                msg_list = chat.list_messages(conn, self.user1)
                self.assertEqual(len(msg_list["messages"]), 1)
                out_msg = msg_list["messages"][0]
                self.assertEqual(out_msg["direction"], "outbound")
                self.assertEqual(out_msg["sent_by"], "admin@test.com")
                self.assertEqual(out_msg["send_method"], "push")

    def test_http_api_chat_endpoints(self):
        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok:
                    handler.user = {"email": "boss@test.com", "role": "company_admin", "company": "A", "display_name": "Boss"}
                    handler.identity = handler.user["email"]
                return ok
        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token}

        # 1. GET /api/chat/rooms
        req = Request(f"{base}/api/chat/rooms", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("rooms", data)
            self.assertEqual(data["total"], 2)

        # 2. POST /api/chat/canned-replies/save
        canned_payload = {"title": "發票開立說明", "category": "財務", "content": "發票將於每月中旬統一寄送至登記之 Email。"}
        req = Request(f"{base}/api/chat/canned-replies/save", data=json.dumps(canned_payload).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            canned_id = data["reply"]["id"]

        # 3. GET /api/chat/canned-replies
        req = Request(f"{base}/api/chat/canned-replies", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["replies"][0]["id"], canned_id)

        # 4. POST /api/chat/status
        req = Request(f"{base}/api/chat/status", data=json.dumps({"recipient_id": self.user1, "status": "pending"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data["status"], "pending")

        # 5. GET /api/chat/messages
        req = Request(f"{base}/api/chat/messages?recipient_id={self.user1}", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("messages", data)
            self.assertEqual(data["chat_status"], "pending")


if __name__ == "__main__":
    unittest.main()

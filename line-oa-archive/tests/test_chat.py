import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.request import Request, urlopen

import app
from oa_fixture import CHANNEL, add_account, register_oa, use_oa
import admin_server
import chat


class ChatSystemTests(unittest.TestCase):
    def test_sticker_auto_reply_setting_and_event_scope(self):
        event={'type':'message','source':{'type':'user','userId':'U_sticker'},'replyToken':'reply-sticker',
               'message':{'id':'sticker-1','type':'sticker'}}
        with patch('subscriptions.handle_event',return_value=None),patch('recipients.handle_event'):
            self.assertEqual(app.save_events([event]),[])
            with app.database_connection() as conn:
                chat.save_response_hours(conn,{'enabled':True,'weekly':{'1':{'start':'08:30','end':'17:30'}}})
                chat.save_response_hours(conn,{'sticker_reply_enabled':True})
                config=chat.get_response_hours(conn)
                self.assertTrue(config['enabled'])
                self.assertEqual(config['weekly']['1']['start'],'08:30')
                chat.save_response_hours(conn,{'enabled':False})
                self.assertTrue(chat.get_response_hours(conn)['sticker_reply_enabled'])
                with self.assertRaises(ValueError):chat.save_response_hours(conn,{'sticker_reply_enabled':'true'})
            # Enabling must not reply to an already archived message.
            self.assertEqual(app.save_events([event]),[])
            new={**event,'message':{'id':'sticker-2','type':'sticker'}}
            self.assertEqual(app.save_events([new]),[('reply-sticker','系統無法辨識貼圖意圖，請改以文字輸入。')])
            self.assertEqual(app.save_events([new]),[])
            for kind in ['group','room']:
                other={**event,'source':{'type':kind,kind+'Id':'C_test','userId':'U_sticker'},
                       'message':{'id':'sticker-'+kind,'type':'sticker'}}
                self.assertEqual(app.save_events([other]),[])
            self.assertEqual(app.save_events([{**event,'message':{'id':'text-1','type':'text','text':'hi'}}]),[])
            self.assertEqual(app.save_events([{**event,'replyToken':'','message':{'id':'sticker-no-token','type':'sticker'}}]),[])
            with app.database_connection() as conn:
                self.assertEqual(conn.execute("SELECT reply_token FROM line_messages WHERE message_id='sticker-2'").fetchone()[0],'')
                self.assertEqual(conn.execute("SELECT count(*) FROM line_messages WHERE sent_by='系統（貼圖提示）'").fetchone()[0],1)
                chat.save_response_hours(conn,{'sticker_reply_enabled':False})
            self.assertEqual(app.save_events([{**event,'message':{'id':'sticker-off','type':'sticker'}}]),[])

    def test_sticker_auto_reply_settings_isolated_and_migrate(self):
        import channels
        with app.database_connection() as conn:
            chat.save_response_hours(conn,{'sticker_reply_enabled':True})
            with channels.use('another-oa'):
                self.assertFalse(chat.get_response_hours(conn)['sticker_reply_enabled'])
            conn.execute('ALTER TABLE response_hours DROP COLUMN sticker_reply_enabled')
        app.initialize_database()
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertFalse(chat.get_response_hours(conn)['sticker_reply_enabled'])

    def test_sticker_webhook_records_reply_result_without_retries(self):
        import base64
        import hashlib
        import hmac
        import io
        from types import SimpleNamespace
        import channels
        channel=channels.get()
        with app.database_connection() as conn:chat.save_response_hours(conn,{'sticker_reply_enabled':True})
        for message_id,failure in [('auto-success',False),('auto-failure',True)]:
            event={'type':'message','source':{'type':'user','userId':self.user1},'replyToken':'token-'+message_id,
                   'message':{'id':message_id,'type':'sticker'}}
            body=json.dumps({'destination':channel['bot_user_id'],'events':[event]}).encode()
            signature=base64.b64encode(hmac.new(channels.credentials()[1].encode(),body,hashlib.sha256).digest()).decode()
            handler=SimpleNamespace(headers={'Content-Length':str(len(body)),'x-line-signature':signature},
                                    rfile=io.BytesIO(body),respond=MagicMock())
            with patch('line_api.reply',side_effect=ValueError('failed') if failure else None) as send,patch('subscriptions.export'),patch('recipients.handle_event'),patch('subscriptions.handle_event',return_value=None):
                app.Handler.receive_webhook(handler,channel)
                send.assert_called_once_with(event['replyToken'],'系統無法辨識貼圖意圖，請改以文字輸入。')
                handler.respond.assert_called_with(200,'ok')
                handler.rfile=io.BytesIO(body)
                app.Handler.receive_webhook(handler,channel)
                self.assertEqual(send.call_count,1)
            with app.database_connection() as conn:
                row=conn.execute('SELECT delivery_status,reply_token FROM line_messages WHERE message_id=?',('auto-sticker:'+message_id,)).fetchone()
                self.assertEqual(row,('unknown' if failure else 'sent',''))

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

        self.user1 = "U11111111111111111111111111111111"
        self.group1 = "C11111111111111111111111111111111"

        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, custom_name, active) VALUES (current_channel(), ?, 'user', 'Alice', '小愛', 1)",
                (self.user1,)
            )
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, custom_name, active) VALUES (current_channel(), ?, 'group', 'Sales Group', '', 1)",
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
                    handler.user = {"email": "boss@test.com", "role": "org_admin", "organization_id": "A", "display_name": "Boss"}
                    handler.identity = handler.user["email"]
                return ok
        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}

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

        # 6. GET /api/chat/messages with in-chat search query
        from urllib.parse import quote
        req = Request(f"{base}/api/chat/messages?recipient_id={self.user1}&q={quote('發票')}", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("messages", data)

        # 7. GET /api/chat/media/stats
        req = Request(f"{base}/api/chat/media/stats", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("total_bytes", data)
            self.assertIn("limit_gb", data)
            self.assertEqual(data["limit_gb"], 10)

        # 8. GET /api/chat/export (TXT and CSV)
        req_txt = Request(f"{base}/api/chat/export?chat_id={self.user1}&format=txt", headers=headers)
        with urlopen(req_txt) as resp:
            txt_content = resp.read().decode("utf-8")
            self.assertIn("LINE OA 聊天紀錄匯出", txt_content)
            self.assertIn("小愛", txt_content)

        req_csv = Request(f"{base}/api/chat/export?chat_id={self.user1}&format=csv", headers=headers)
        with urlopen(req_csv) as resp:
            csv_content = resp.read().decode("utf-8-sig")
            self.assertIn("時間,發送方向,發話者,訊息類型,訊息內容", csv_content)

        # 9. POST /api/chat/media/cleanup
        req_clean = Request(f"{base}/api/chat/media/cleanup", data=json.dumps({"days": 365}).encode(), headers=headers)
        with urlopen(req_clean) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

    def test_search_and_export_and_media_limits(self):
        with app.database_connection() as conn:
            past_ts = "2025-01-01T10:00:00.000Z"
            conn.execute(
                """INSERT INTO line_messages
                   (channel_id, message_id, conversation_type, conversation_id, sender_user_id, message_type, text_content, sent_at, direction)
                   VALUES (current_channel(), 'msg_search_1', 'user', ?, ?, 'text', '我想確認退貨退款流程', ?, 'inbound')""",
                (self.user1, self.user1, past_ts)
            )

            # 1. Search messages within chat room
            res = chat.search_messages(conn, self.user1, "退款")
            self.assertEqual(res["count"], 1)
            self.assertIn("退貨退款", res["messages"][0]["text_content"])

            # 2. Export chat in TXT and CSV
            txt_bytes, txt_mime, txt_name = chat.export_chat_history(conn, self.user1, format="txt", actor="Admin")
            self.assertIn("text/plain", txt_mime)
            self.assertTrue(txt_name.endswith(".txt"))
            self.assertIn("退貨退款", txt_bytes.decode("utf-8"))

            csv_bytes, csv_mime, csv_name = chat.export_chat_history(conn, self.user1, format="csv", actor="Admin")
            self.assertIn("text/csv", csv_mime)
            self.assertTrue(csv_name.endswith(".csv"))
            self.assertIn("退貨退款", csv_bytes.decode("utf-8-sig"))

            # 3. Media storage limits & stats
            stats = chat.get_media_storage_stats(conn)
            self.assertEqual(stats["limit_gb"], 10)
            self.assertEqual(stats["retention_days"], 365)

            # Mock LINE API returning data > 20 MB (single limit)
            with patch("line_api.get_message_content") as mock_get_content:
                mock_get_content.return_value = (b"0" * (21 * 1024 * 1024), "image/jpeg")
                with self.assertRaises(ValueError) as cm:
                    chat.get_chat_media(conn, "msg_oversized")
                self.assertIn("超過 20 MB 上限", str(cm.exception))

            # Cleanup expired media
            clean_res = chat.cleanup_expired_media(max_age_days=0)
            self.assertTrue(clean_res["ok"])


if __name__ == "__main__":
    unittest.main()


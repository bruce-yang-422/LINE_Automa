import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

import app
import admin_server
import recipients
from oa_fixture import CHANNEL, register_oa, use_oa

USER = "U" + "1" * 32
USER2 = "U" + "2" * 32
GROUP = "C" + "3" * 32


class RecipientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="line-recipients-test-")
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

    def event(self, rid=USER, message="訂閱天氣", stamp=1000, event_type="message", message_id=None):
        kind = "user" if rid.startswith("U") else "group"
        return {"type": event_type, "timestamp": stamp, "replyToken": "fake-reply",
                "source": {"type": kind, "userId" if kind == "user" else "groupId": rid},
                "message": {"id": message_id or str(uuid4()), "type": "text", "text": message}}

    def contact(self, rid=USER):
        with app.database_connection() as conn:
            return next(r for r in recipients.list_contacts(conn) if r["recipient_id"] == rid)

    def test_subscribe_cancel_redelivery_and_out_of_order_commands(self):
        first = self.event(message_id="first")
        self.assertEqual(len(app.save_events([first])), 1)
        self.assertTrue(self.contact()["weather_subscribed"])
        self.assertEqual(app.save_events([first]), [])
        app.save_events([self.event(message="取消訂閱", stamp=3000)])
        app.save_events([self.event(stamp=2000)])
        self.assertFalse(self.contact()["weather_subscribed"])
        reply = app.save_events([self.event(message="我的訂閱", stamp=4000)])[0][1]
        self.assertIn("未訂閱", reply)

    def test_groups_require_admin_and_unfollow_deactivates(self):
        response = app.save_events([self.event(GROUP)])[0][1]
        self.assertIn("管理員", response)
        self.assertFalse(self.contact(GROUP)["weather_subscribed"])
        app.save_events([self.event()])
        app.save_events([self.event(event_type="unfollow", stamp=3000)])
        app.save_events([self.event(stamp=2000)])
        self.assertFalse(self.contact()["active"])
        self.assertFalse(self.contact()["weather_subscribed"])
        app.save_events([self.event(event_type="follow", stamp=4000)])
        self.assertTrue(self.contact()["active"])
        self.assertFalse(self.contact()["weather_subscribed"])

    def test_restart_preserves_subscription_and_does_not_restore_deleted_contact(self):
        app.save_events([self.event()])
        with app.database_connection() as conn:
            recipients.update_contact(conn, USER, "測試同事", True)
        app.initialize_database()
        self.assertEqual(self.contact()["custom_name"], "測試同事")
        self.assertTrue(self.contact()["weather_subscribed"])
        with app.database_connection() as conn:
            conn.execute("DELETE FROM recipients")
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(recipients.list_contacts(conn), [])

    def test_batch_is_idempotent_and_scoped_to_selected_contacts(self):
        app.save_events([self.event(), self.event(USER2), self.event(GROUP)])
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        payload = {"job_id": str(uuid4()), "audience": "selected", "ids": [USER, GROUP], "image_path": "fake.png"}
        with patch.object(admin_server, "load_settings"), patch.object(admin_server, "publish_image", return_value=("https://example.test/image.png", b"PNG")), \
                patch.object(admin_server, "verify_public_image"), patch.object(admin_server, "send_push", return_value="request-id") as send:
            dispatcher.submit(payload)
            dispatcher.submit(payload)
            deadline = time.monotonic() + 3
            while admin_server.job_status(payload["job_id"])[0]["status"] != "finished" and time.monotonic() < deadline:
                time.sleep(0.02)
            called = [call.args[1] for call in send.call_args_list]
            self.assertEqual(sorted(called), sorted([USER, GROUP]))
            job = admin_server.job_status(payload["job_id"])[0]
            self.assertEqual(len(job["deliveries"]), 2)
            self.assertTrue(all(row["status"] == "accepted" for row in job["deliveries"]))
        with app.database_connection() as conn:
            with self.assertRaises(ValueError):
                admin_server.select_contacts(conn, "selected", ["U" + "9" * 32])

    def test_subscriber_cancel_is_checked_before_each_delivery(self):
        app.save_events([self.event(), self.event(USER2)])
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        job_id = str(uuid4())
        with app.database_connection() as conn:
            conn.execute("INSERT INTO send_jobs (channel_id,job_id,audience,image_path,image_url) VALUES (?,?,'subscribers','test.png','https://example.test/image.png')", (CHANNEL, job_id))
            conn.executemany("INSERT INTO send_deliveries (job_id,recipient_id,label,retry_key) VALUES (?,?,?,?)",
                             [(job_id, rid, rid, str(uuid4())) for rid in (USER, USER2)])
        def fake_send(token, rid, url, retry_key):
            with app.database_connection() as conn:
                recipients.update_contact(conn, USER2, "", False)
            return "request-id"
        with patch.object(admin_server, "send_push", side_effect=fake_send) as send:
            dispatcher.run(job_id)
        self.assertEqual(send.call_count, 1)
        statuses = {r["recipient_id"]: r["status"] for r in admin_server.job_status(job_id)[0]["deliveries"]}
        self.assertEqual(statuses, {USER: "accepted", USER2: "cancelled"})

    def test_admin_requires_token_and_rejects_cross_origin_or_proxy(self):
        server = admin_server.AdminServer(0)
        server.start()
        self.addCleanup(server.close)
        url = f"http://127.0.0.1:{server.server_port}/api/contacts"
        for headers in ({}, {"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + server.token, "Origin": "https://untrusted.example"},
                        {"Authorization": "Bearer " + server.token, "CF-Connecting-IP": "192.0.2.1"}):
            with self.assertRaises(HTTPError) as raised:
                urlopen(Request(url, headers=headers), timeout=2)
            self.assertIn(raised.exception.code, (401, 403))
            raised.exception.close()
        with urlopen(Request(url, headers={"Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}), timeout=2) as response:
            self.assertEqual(json.load(response)["contacts"], [])


    def test_uncertain_delivery_is_recorded_without_retry(self):
        app.save_events([self.event(), self.event(USER2)])
        dispatcher = admin_server.Dispatcher()
        self.addCleanup(dispatcher.close)
        job_id = str(uuid4())
        with app.database_connection() as conn:
            conn.execute("INSERT INTO send_jobs (channel_id,job_id,audience,image_path,image_url) VALUES (?,?,'selected','test.png','https://example.test/image.png')", (CHANNEL, job_id))
            conn.executemany("INSERT INTO send_deliveries (job_id,recipient_id,label,retry_key) VALUES (?,?,?,?)",
                             [(job_id, rid, rid, str(uuid4())) for rid in (USER, USER2)])
        with patch.object(admin_server, "send_push", side_effect=[ValueError("送達狀態不明"), "request-id"]) as send:
            dispatcher.run(job_id)
        self.assertEqual(send.call_count, 2)
        statuses = {r["recipient_id"]: r["status"] for r in admin_server.job_status(job_id)[0]["deliveries"]}
        self.assertEqual(statuses, {USER: "unknown", USER2: "accepted"})


if __name__ == "__main__":
    unittest.main()

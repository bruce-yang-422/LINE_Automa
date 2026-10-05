"""Keyword subscriptions from topics.json, access rules and exported rosters; no real LINE requests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import app
import recipients
import subscriptions
from oa_fixture import register_oa, use_oa

USER = "U" + "1" * 32
BOSS = "U" + "2" * 32
GROUP = "C" + "3" * 32
CONFIG = {
    "status_keywords": ["我的訂閱"],
    "topics": [
        {"key": "weather", "name": "天氣報告", "subscribe": ["訂閱天氣"], "unsubscribe": ["取消天氣"], "allow": "all", "groups": True},
        {"key": "sales_daily", "name": "營業日報", "subscribe": ["訂閱營業日報"], "unsubscribe": ["取消營業日報"],
         "allow": {"tags": ["主管"]}, "deny": {"ids": [USER]}},
    ],
}


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="line-subscriptions-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "instance").mkdir()
        (self.root / "schema.sql").write_bytes((app.BASE_DIR / "schema.sql").read_bytes())
        self.folder = self.root / "subscribers"
        self.folder.mkdir()
        for target, obj, value in (("BASE_DIR", app, self.root), ("DATABASE_PATH", app, self.root / "test.db")):
            p = patch.object(obj, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://reports.example.test"}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        subscriptions._cache.update(mtime=None, config=None, error="")
        app.initialize_database()
        register_oa()
        use_oa(self)
        self.write_config(CONFIG)

    def write_config(self, data):
        path = self.folder / "topics.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        stamp = (path.stat().st_mtime_ns // 10**9 + len(str(data))) * 10**9
        os.utime(path, ns=(stamp, stamp))  # Guarantee the cache sees each rewrite.

    def send(self, text, rid=USER, stamp=1000, message_id=None, event_type="message"):
        kind = "user" if rid.startswith("U") else "group"
        event = {"type": event_type, "timestamp": stamp, "replyToken": "token",
                 "source": {"type": kind, "userId" if kind == "user" else "groupId": rid},
                 "message": {"id": message_id or str(uuid4()), "type": "text", "text": text}}
        replies = app.save_events([event])
        return replies[0][1] if replies else None

    def tag(self, rid, name):
        with app.database_connection() as conn:
            tag_id = recipients.save_tag(conn, name, "#007AFF", None)
            recipients.set_contact_tags(conn, rid, [tag_id])

    def roster(self, key):
        subscriptions.export()
        return [r["recipient_id"] for r in json.loads((self.folder / f"{key}.json").read_text(encoding="utf-8"))["subscribers"]]

    def test_subscribe_unsubscribe_redelivery_and_out_of_order(self):
        self.assertIn("已訂閱「天氣報告」", self.send(" 訂閱 天氣 ", message_id="m1"))
        self.assertIsNone(self.send("訂閱天氣", message_id="m1"))  # redelivery is silent and idempotent
        self.assertEqual(self.roster("weather"), [USER])
        self.send("取消天氣", stamp=3000)
        self.send("訂閱天氣", stamp=2000)  # older event arrives late and must not resubscribe
        self.assertEqual(self.roster("weather"), [])
        self.assertIsNone(self.send("普通訊息"))

    def test_allow_tags_deny_ids_and_status(self):
        self.send("hi", BOSS)
        self.assertIn("沒有訂閱「營業日報」的權限", self.send("訂閱營業日報", BOSS))
        self.tag(BOSS, "主管")
        self.assertIn("已訂閱「營業日報」", self.send("訂閱營業日報", BOSS, stamp=2000))
        self.tag(USER, "主管")
        self.assertIn("沒有訂閱", self.send("訂閱營業日報", USER))  # deny wins over allow
        status = self.send("我的訂閱", BOSS, stamp=3000)
        self.assertIn("目前訂閱：營業日報", status)
        self.assertIn("訂閱天氣", status)
        self.assertEqual(self.roster("sales_daily"), [BOSS])
        # Removing the tag later drops BOSS from the roster without code changes.
        with app.database_connection() as conn:
            recipients.set_contact_tags(conn, BOSS, [])
        self.assertEqual(self.roster("sales_daily"), [])

    def test_groups_need_groups_true_and_unfollow_leaves_roster(self):
        self.assertIn("只開放個人訂閱", self.send("訂閱營業日報", GROUP))
        self.assertIn("已訂閱「天氣報告」", self.send("訂閱天氣", GROUP))
        self.send("訂閱天氣", USER)
        self.assertEqual(sorted(self.roster("weather")), sorted([USER, GROUP]))
        self.send("", GROUP, stamp=5000, event_type="leave")
        self.assertEqual(self.roster("weather"), [USER])
        contacts = json.loads((self.folder / "_contacts.json").read_text(encoding="utf-8"))["contacts"]
        self.assertEqual({c["recipient_id"] for c in contacts}, {USER, GROUP})

    def test_removed_topic_roster_is_deleted_but_other_files_kept(self):
        self.send("訂閱天氣")
        self.roster("weather")
        (self.folder / "notes.json").write_text('{"topic": "other"}', encoding="utf-8")
        trimmed = json.loads(json.dumps(CONFIG))
        trimmed["topics"] = trimmed["topics"][1:]
        self.write_config(trimmed)
        subscriptions.export()
        self.assertFalse((self.folder / "weather.json").exists())
        self.assertTrue((self.folder / "notes.json").exists())
        self.assertTrue((self.folder / "sales_daily.json").exists())

    def test_invalid_config_keeps_previous_rules(self):
        broken = json.loads(json.dumps(CONFIG))
        broken["topics"][1]["subscribe"] = ["訂閱天氣"]  # duplicate keyword
        self.assertIsNotNone(subscriptions.load_config())
        self.write_config(broken)
        self.assertIn("已訂閱「天氣報告」", self.send("訂閱天氣"))
        self.assertIn("重複", subscriptions._cache["error"])
        for bad in ({"topics": [{"key": "Bad Key", "name": "x", "subscribe": ["a"]}]},
                    {"topics": [{"key": "a", "name": "x", "subscribe": ["a"], "allow": {"ids": ["not-an-id"]}}]},
                    {"topics": [{"key": "a", "name": "x", "subscribe": []}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                subscriptions.parse_config(bad)

    def test_example_config_is_valid(self):
        example = app.BASE_DIR.parent / "subscribers" / "topics.example.json"
        if not example.exists():  # BASE_DIR is patched; resolve from the module location instead.
            example = Path(subscriptions.__file__).resolve().parent / "subscribers" / "topics.example.json"
        subscriptions.parse_config(json.loads(example.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()

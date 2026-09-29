"""使用暫存 SQLite 驗證訊息儲存行為。"""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import app


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = app.DATABASE_PATH
        app.DATABASE_PATH = Path(self.temp.name) / "data" / "messages.db"
        app.initialize_database()

    def tearDown(self):
        app.DATABASE_PATH = self.original_path
        self.temp.cleanup()

    def message(self, message_id="1", source_type="user"):
        key = {"user": "userId", "group": "groupId", "room": "roomId"}[source_type]
        return {
            "type": "message",
            "source": {"type": source_type, "userId": "U1", key: "C1"},
            "timestamp": 1700000000000,
            "message": {"id": message_id, "type": "text", "text": "繁體中文訊息"},
        }

    def rows(self):
        with app.database_connection() as conn:
            return conn.execute(
                "SELECT message_id, text_content, unsent_at FROM line_messages ORDER BY message_id"
            ).fetchall()

    def test_sources_duplicates_and_restart(self):
        events = [self.message(str(i), kind) for i, kind in enumerate(("user", "group", "room"))]
        app.save_events(events)
        app.save_events(events)
        app.initialize_database()
        self.assertEqual(len(self.rows()), 3)
        self.assertEqual(self.rows()[0][1], "繁體中文訊息")
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT sent_at FROM line_messages LIMIT 1").fetchone()[0],
                             "2023-11-14T22:13:20.000+00:00")

    def test_unsend_before_and_after_message(self):
        for message_id, before in (("1", False), ("2", True)):
            message = self.message(message_id)
            unsend = {"type": "unsend", "source": message["source"], "unsend": {"messageId": message_id}}
            app.save_events([unsend, message] if before else [message, unsend])
            app.save_events([message])
        for _, text, unsent_at in self.rows():
            self.assertIsNone(text)
            self.assertIsNotNone(unsent_at)

    def test_parallel_writes(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: app.save_events([self.message(str(i))]), range(30)))
        self.assertEqual(len(self.rows()), 30)

    def test_failed_batch_rolls_back(self):
        invalid = self.message("2")
        invalid["message"]["text"] = {"invalid": "value"}
        with self.assertRaises(app.sqlite3.Error):
            app.save_events([self.message(), invalid])
        self.assertEqual(self.rows(), [])

    def test_empty_events(self):
        app.save_events([])
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()

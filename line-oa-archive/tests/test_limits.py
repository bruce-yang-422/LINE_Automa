"""數量上限集中於 limits.py，以及回應時間設定的驗證。"""

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['DATABASE_PATH'] = ':memory:'

import app
import channels
import chat
import chat_notes
import limits


class LimitsTests(unittest.TestCase):
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
        app.initialize_database()
        with app.database_connection() as conn:
            conn.execute("INSERT INTO recipients (channel_id, recipient_id, kind, display_name, active) VALUES ('', 'U_limit', 'user', 'Amy', 1)")

    def tearDown(self):
        channels._current.set("")

    def test_limits_are_defined_only_in_limits_module(self):
        for path in Path(__file__).resolve().parents[1].glob("*.py"):
            if path.name == "limits.py":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^LIMITS\s*=", text, re.M), path.name)
        exposed = limits.as_dict()
        for key in ("TAGS_PER_OA", "NOTE_TAGS_PER_OA", "SCHEDULED_MESSAGES_PER_OA", "CATEGORIES_PER_OA"):
            self.assertIn(key, exposed)

    def test_note_tags_per_oa_cap(self):
        with app.database_connection() as conn:
            per_note = limits.TAGS_PER_NOTE
            for i in range(limits.NOTE_TAGS_PER_OA // per_note):
                chat_notes.save_chat_note(conn, {
                    'recipient_id': 'U_limit', 'content': f'記事 {i}',
                    'tags': [f't{i}-{j}' for j in range(per_note)],
                }, 'admin@test.com')
            self.assertEqual(chat_notes.list_note_tags(conn)['count'], limits.NOTE_TAGS_PER_OA)
            with self.assertRaisesRegex(ValueError, '記事標籤已達上限'):
                chat_notes.save_chat_note(conn, {'recipient_id': 'U_limit', 'content': '新標籤', 'tags': ['全新']}, 'admin@test.com')
            # 沿用既有標籤不受影響
            chat_notes.save_chat_note(conn, {'recipient_id': 'U_limit', 'content': '沿用', 'tags': ['t0-0']}, 'admin@test.com')

    def test_response_hours_validation_and_round_trip(self):
        with app.database_connection() as conn:
            with self.assertRaises(ValueError):
                chat.save_response_hours(conn, {'enabled': True, 'weekly': {'1': {'start': '9am', 'end': '18:00'}}})
            with self.assertRaises(ValueError):
                chat.save_response_hours(conn, {'enabled': True, 'weekly': {'8': {'start': '09:00', 'end': '18:00'}}})
            with self.assertRaises(ValueError):
                chat.save_response_hours(conn, {'enabled': True, 'holidays': ['10/10']})
            chat.save_response_hours(conn, {
                'enabled': True, 'timezone': 'Asia/Taipei',
                'weekly': {'1': {'start': '09:00', 'end': '18:00'}},
                'holidays': ['2026-10-10', '2026-10-10'],
            })
            saved = chat.get_response_hours(conn)
        self.assertTrue(saved['enabled'])
        self.assertEqual(saved['weekly'], {'1': {'start': '09:00', 'end': '18:00'}})
        self.assertEqual(saved['holidays'], ['2026-10-10'])


if __name__ == '__main__':
    unittest.main()

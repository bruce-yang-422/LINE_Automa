import unittest
import app
import chat
import test_recipients as fixtures


class RoomPreferenceTests(unittest.TestCase):
    setUp = fixtures.RecipientTests.setUp

    def test_persist_personal_preferences_and_validate(self):
        with app.database_connection() as conn:
            conn.execute("INSERT INTO recipients(channel_id,recipient_id,kind) VALUES(current_channel(),?,'user')", (fixtures.USER,))
            chat.save_room_preference(conn, {'recipient_id': fixtures.USER, 'is_pinned': True, 'marker': 'flag'}, 'member-a')
            room = next(r for r in chat.list_chat_rooms(conn, actor='member-a')['rooms'] if r['recipient_id'] == fixtures.USER)
            self.assertTrue(room['is_pinned'])
            self.assertEqual(room['marker'], 'flag')
            other = next(r for r in chat.list_chat_rooms(conn, actor='member-b')['rooms'] if r['recipient_id'] == fixtures.USER)
            self.assertFalse(other['is_pinned'])
            self.assertEqual(other['marker'], '')
            with self.assertRaises(ValueError):
                chat.save_room_preference(conn, {'recipient_id': fixtures.USER, 'is_pinned': True, 'marker': 'invalid'}, 'member-a')
            with self.assertRaises(ValueError):
                chat.save_room_preference(conn, {'recipient_id': 'missing', 'is_pinned': False}, 'member-a')

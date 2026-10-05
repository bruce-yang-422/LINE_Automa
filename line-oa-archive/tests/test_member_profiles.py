import threading
import unittest
from unittest.mock import patch

import app
import chat
import channels
import line_api
import member_profiles
import test_recipients as fixtures
USER, GROUP = fixtures.USER, fixtures.GROUP


class MemberProfileTests(unittest.TestCase):
    setUp = fixtures.RecipientTests.setUp
    event = fixtures.RecipientTests.event

    def group_message(self, conversation_id=GROUP):
        event = self.event(GROUP, message='舊訊息')
        event['source'] = {'type': 'room' if conversation_id.startswith('R') else 'group',
                           'roomId' if conversation_id.startswith('R') else 'groupId': conversation_id, 'userId': USER}
        app.save_events([event])

    def test_background_backfills_old_messages_and_uses_member_endpoint(self):
        self.group_message()
        with app.database_connection() as conn:
            self.assertFalse(chat.list_messages(conn, GROUP)['messages'][0]['sender_name_resolved'])
        def lookup(path):
            with app.database_connection() as conn:
                conn.execute('UPDATE recipients SET custom_name=custom_name')
            return {'displayName': '王小明', 'pictureUrl': 'https://profile.line-scdn.net/member'}
        with patch.object(line_api, 'request', side_effect=lookup) as api:
            member_profiles.tick(threading.Event())
            member_profiles.tick(threading.Event())
            api.assert_called_once_with(f'group/{GROUP}/member/{USER}')
        with app.database_connection() as conn:
            message = chat.list_messages(conn, GROUP)['messages'][0]
            self.assertEqual(message['sender_name'], '王小明')
            self.assertTrue(message['sender_name_resolved'])

    def test_room_route_failure_backoff_and_cached_name_retained(self):
        room = 'R' + '4' * 32
        self.group_message(room)
        with patch.object(line_api, 'request', return_value={'displayName': '同事'}):
            self.assertEqual(member_profiles.refresh(room, USER, now=100), 'updated')
        with patch.object(line_api, 'request', side_effect=ValueError('not available')) as api:
            self.assertEqual(member_profiles.refresh(room, USER, now=101, force=True), 'failed')
            self.assertEqual(member_profiles.refresh(room, USER, now=102), 'skipped')
            api.assert_called_once_with(f'room/{room}/member/{USER}')
        with app.database_connection() as conn:
            self.assertEqual(chat.list_messages(conn, room)['messages'][0]['sender_name'], '同事')
            self.assertEqual(conn.execute('SELECT next_at FROM member_profile_jobs').fetchone()[0], 1001)

    def test_oa_isolation_invalid_ids_and_departure_during_lookup(self):
        self.group_message()
        with channels.use('other-oa'), patch.object(line_api, 'request') as api:
            self.assertEqual(member_profiles.refresh(GROUP, USER), 'skipped')
            api.assert_not_called()
        with patch.object(line_api, 'request') as api:
            self.assertEqual(member_profiles.refresh(GROUP, 'invalid'), 'skipped')
            api.assert_not_called()
        def leave(path):
            with app.database_connection() as conn:
                conn.execute('UPDATE recipients SET active=0')
            return {'displayName': 'late name'}
        with patch.object(line_api, 'request', side_effect=leave):
            self.assertEqual(member_profiles.refresh(GROUP, USER), 'skipped')
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM group_member_cache').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()

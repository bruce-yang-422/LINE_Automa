import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import unittest
from unittest.mock import patch
import app
import recipients
import line_api
import test_recipients as fixtures


class ProfileCacheTests(unittest.TestCase):
    setUp = fixtures.RecipientTests.setUp
    event = fixtures.RecipientTests.event
    contact = fixtures.RecipientTests.contact

    def test_discovery_cache_routes_and_alias_preserved(self):
        app.save_events([self.event(message='hello'),self.event(fixtures.GROUP,event_type='join')])
        with app.database_connection() as conn:
            conn.execute('UPDATE recipients SET alias=? WHERE recipient_id=?',('My family',fixtures.GROUP))
        def lookup(path):
            # Another write succeeds while LINE is queried: no database lock held over network.
            with app.database_connection() as conn:
                conn.execute('UPDATE recipients SET alias=alias')
            return {'displayName':'Alice'} if path.startswith('profile/') else {'groupName':'Family'}
        with patch.object(line_api,'request',side_effect=lookup) as api:
            self.assertEqual(recipients.refresh_profile(fixtures.USER,now=100),'updated')
            self.assertEqual(recipients.refresh_profile(fixtures.GROUP,now=100),'updated')
            self.assertEqual(recipients.refresh_profile(fixtures.GROUP,now=101),'skipped')
            self.assertEqual(api.call_args_list[0].args,('profile/'+fixtures.USER,))
            self.assertEqual(api.call_args_list[1].args,('group/'+fixtures.GROUP+'/summary',))
        self.assertEqual(self.contact()['display_name'],'Alice')
        self.assertEqual(self.contact(fixtures.GROUP)['display_name'],'Family')
        self.assertEqual(self.contact(fixtures.GROUP)['alias'],'My family')

    def test_failure_backoff_retains_messages_and_last_name(self):
        app.save_events([self.event(message='test')])
        with app.database_connection() as conn:
            conn.execute("UPDATE recipients SET display_name='Known name'")
        with patch.object(line_api,'request',side_effect=ValueError('unavailable')) as api:
            self.assertEqual(recipients.refresh_profile(fixtures.USER,now=100),'failed')
            self.assertEqual(recipients.refresh_profile(fixtures.USER,now=101),'skipped')
            api.assert_called_once()
        self.assertEqual(self.contact()['display_name'],'Known name')
        self.assertEqual(self.contact()['profile_next_at'],1000)
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM line_messages').fetchone()[0],1)
        with patch.object(line_api,'request',return_value={'displayName':'New name'}):
            self.assertEqual(recipients.refresh_profile(fixtures.USER,now=1000),'updated')
        self.assertEqual(self.contact()['profile_failures'],0)

    def test_worker_backfills_existing_contacts_and_refreshes_stale_names(self):
        app.save_events([self.event()])
        worker=recipients.ProfileRefresher()
        with patch.object(line_api,'request',return_value={'displayName':'Cached'}) as api:
            worker.tick();worker.tick();api.assert_called_once()
            with app.database_connection() as conn:
                conn.execute('UPDATE recipients SET profile_next_at=0')
            worker.tick();self.assertEqual(api.call_count,2)
            worker.close();worker.tick();self.assertEqual(api.call_count,2)

    def test_no_token_inactive_room_and_concurrent_lease_skip(self):
        app.save_events([self.event()])
        with patch.object(line_api,'request') as api:
            with patch.dict(os.environ,{'LINE_CHANNEL_ACCESS_TOKEN':''}):
                self.assertEqual(recipients.refresh_profile(fixtures.USER),'skipped')
            with app.database_connection() as conn:
                conn.execute('UPDATE recipients SET profile_lease_until=500')
            self.assertEqual(recipients.refresh_profile(fixtures.USER,force=True,now=100),'skipped')
            app.save_events([self.event(event_type='unfollow',stamp=2000)])
            self.assertEqual(recipients.refresh_profile(fixtures.USER,force=True,now=600),'skipped')
            api.assert_not_called()

    def test_leave_while_querying_does_not_reactivate_or_update_name(self):
        app.save_events([self.event()])
        def lookup(path):
            app.save_events([self.event(event_type='unfollow',stamp=3000)])
            return {'displayName':'Late result'}
        with patch.object(line_api,'request',side_effect=lookup):
            self.assertEqual(recipients.refresh_profile(fixtures.USER,now=100),'skipped')
        self.assertFalse(self.contact()['active'])
        self.assertEqual(self.contact()['display_name'],'')

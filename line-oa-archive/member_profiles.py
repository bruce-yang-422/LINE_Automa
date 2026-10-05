"""Fetch group/room member names without delaying webhook persistence."""
import re
import sqlite3
import time

import channels
import line_api


def refresh(conversation_id, user_id, *, now=None, force=False):
    import app
    import chat
    if not re.fullmatch(r'U[0-9a-fA-F]{32}', user_id):
        return 'skipped'
    try:
        if not channels.access_token():
            return 'skipped'
    except ValueError:
        return 'skipped'
    now = int(time.time()) if now is None else now
    lease = now + 60
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN IMMEDIATE')
        recipient = conn.execute('''SELECT kind,active FROM recipients
            WHERE channel_id=current_channel() AND recipient_id=?''', (conversation_id,)).fetchone()
        if not recipient or not recipient['active'] or recipient['kind'] not in {'group', 'room'}:
            return 'skipped'
        prefix = 'C' if recipient['kind'] == 'group' else 'R'
        if not re.fullmatch(prefix + r'[0-9a-fA-F]{32}', conversation_id):
            return 'skipped'
        conn.execute('''INSERT OR IGNORE INTO member_profile_jobs
            (channel_id,conversation_id,user_id) VALUES (current_channel(),?,?)''', (conversation_id, user_id))
        job = conn.execute('''SELECT * FROM member_profile_jobs
            WHERE channel_id=current_channel() AND conversation_id=? AND user_id=?''', (conversation_id, user_id)).fetchone()
        if job['lease_until'] > now or (not force and job['next_at'] > now):
            return 'skipped'
        conn.execute('''UPDATE member_profile_jobs SET lease_until=?
            WHERE channel_id=current_channel() AND conversation_id=? AND user_id=?''', (lease, conversation_id, user_id))
    try:
        profile = line_api.request(f"{recipient['kind']}/{conversation_id}/member/{user_id}")
        name = profile.get('displayName')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('LINE 未提供成員名稱。')
        picture = profile.get('pictureUrl') or ''
        if not isinstance(picture, str):
            picture = ''
    except (ValueError, OSError):
        failures = min(job['failures'] + 1, 8)
        delay = min(900 * 2 ** (failures - 1), 86400)
        with app.database_connection() as conn:
            conn.execute('''UPDATE member_profile_jobs SET failures=?,next_at=?,lease_until=0
                WHERE channel_id=current_channel() AND conversation_id=? AND user_id=? AND lease_until=?''',
                (failures, now + delay, conversation_id, user_id, lease))
        return 'failed'
    with app.database_connection() as conn:
        changed = conn.execute('''UPDATE member_profile_jobs SET failures=0,next_at=?,lease_until=0
            WHERE channel_id=current_channel() AND conversation_id=? AND user_id=? AND lease_until=?
            AND EXISTS (SELECT 1 FROM recipients WHERE channel_id=current_channel() AND recipient_id=? AND active=1)''',
            (now + 86400, conversation_id, user_id, lease, conversation_id)).rowcount
        if changed:
            chat.cache_group_member(conn, conversation_id, user_id, name.strip()[:200], picture.strip()[:500])
            # Authorized share copies use their owner's lookup and never another OA's cache.
            conn.execute(f'''INSERT INTO group_member_cache (channel_id,group_id,user_id,display_name,picture_url,fetched_at)
                SELECT r.channel_id,c.group_id,c.user_id,c.display_name,c.picture_url,c.fetched_at
                FROM group_member_cache c JOIN recipients r ON r.recipient_id=c.group_id
                WHERE c.channel_id=current_channel() AND c.group_id=? AND c.user_id=?
                AND r.channel_id IN ({channels.SHARE_SCOPES}) AND r.channel_id!=current_channel()
                ON CONFLICT(channel_id,group_id,user_id) DO UPDATE SET
                display_name=excluded.display_name,picture_url=excluded.picture_url,fetched_at=excluded.fetched_at''',
                (conversation_id, user_id))
    return 'updated' if changed else 'skipped'


def tick(stopping):
    import app
    now = int(time.time())
    with app.database_connection() as conn:
        pairs = conn.execute('''SELECT m.conversation_id,m.sender_user_id
            FROM line_messages m JOIN recipients r
            ON r.channel_id=m.channel_id AND r.recipient_id=m.conversation_id
            LEFT JOIN member_profile_jobs j ON j.channel_id=m.channel_id
            AND j.conversation_id=m.conversation_id AND j.user_id=m.sender_user_id
            LEFT JOIN group_member_cache c ON c.channel_id=m.channel_id
            AND c.group_id=m.conversation_id AND c.user_id=m.sender_user_id
            WHERE m.channel_id=current_channel() AND m.direction='inbound'
            AND r.active=1 AND r.kind IN ('group','room')
            AND length(m.sender_user_id)=33 AND substr(m.sender_user_id,1,1)='U'
            AND substr(m.sender_user_id,2) NOT GLOB '*[^0-9a-fA-F]*'
            AND length(m.conversation_id)=33 AND substr(m.conversation_id,2) NOT GLOB '*[^0-9a-fA-F]*'
            AND ((r.kind='group' AND substr(m.conversation_id,1,1)='C') OR (r.kind='room' AND substr(m.conversation_id,1,1)='R'))
            AND COALESCE(j.next_at,0)<=? AND COALESCE(j.lease_until,0)<=?
            AND (j.user_id IS NOT NULL OR c.user_id IS NULL OR c.display_name='' OR julianday(c.fetched_at)<julianday(?,'unixepoch','-1 day'))
            GROUP BY m.conversation_id,m.sender_user_id
            ORDER BY CASE WHEN c.display_name IS NULL OR c.display_name='' THEN 0 ELSE 1 END, MAX(m.sent_at) DESC
            LIMIT 20''', (now, now, now)).fetchall()
    for conversation_id, user_id in pairs:
        if stopping.is_set():
            break
        refresh(conversation_id, user_id, now=now)

"""Recipient discovery and idempotent self-service weather subscriptions."""

import time
import sqlite3
import os
import re
import threading
import channels
import limits

COMMANDS = {"訂閱天氣", "取消訂閱", "取消訂閱天氣", "我的訂閱", "幫助"}


def refresh_profile(recipient_id, *, force=False, now=None):
    """Fetch outside the write transaction. SQLite lease prevents concurrent lookups."""
    import app
    import line_api
    if not channels.access_token():
        return 'skipped'
    now = int(time.time()) if now is None else now
    lease = now + 60
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
        if (not row or not row['active'] or row['profile_lease_until'] > now
                or (not force and row['profile_next_at'] > now)
                or row['kind'] not in {'user', 'group'}
                or not re.fullmatch(('U' if row['kind']=='user' else 'C') + '[0-9a-fA-F]{32}', recipient_id)):
            return 'skipped'
        conn.execute('UPDATE recipients SET profile_lease_until=? WHERE recipients.channel_id=current_channel() AND recipient_id=?', (lease, recipient_id))
    try:
        path = 'profile/' + recipient_id if row['kind']=='user' else 'group/' + recipient_id + '/summary'
        profile = line_api.request(path)
        name = profile.get('displayName' if row['kind']=='user' else 'groupName')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('LINE 未提供名稱。')
    except (ValueError, OSError):
        failures = min(row['profile_failures'] + 1, 8)
        delay = min(900 * 2 ** (failures - 1), 86400)
        with app.database_connection() as conn:
            conn.execute("""UPDATE recipients SET profile_next_at=?,profile_failures=?,profile_lease_until=0
                            WHERE recipients.channel_id=current_channel() AND recipient_id=? AND profile_lease_until=?""", (now+delay, failures, recipient_id, lease))
        return 'failed'
    with app.database_connection() as conn:
        changed = conn.execute("""UPDATE recipients SET display_name=?,profile_checked_at=?,profile_next_at=?,
                                 profile_failures=0,profile_lease_until=0
                                 WHERE recipients.channel_id=current_channel() AND recipient_id=? AND active=1 AND profile_lease_until=?""",
                               (name.strip()[:200],now,now+86400,recipient_id,lease)).rowcount
        if changed:
            conn.execute(f'UPDATE recipients SET display_name=?,profile_checked_at=? WHERE recipient_id=? AND channel_id IN ({channels.SHARE_SCOPES})',
                         (name.strip()[:200], now, recipient_id))
    return 'updated' if changed else 'skipped'


class ProfileRefresher:
    """Recipient rows are the durable backlog, including contacts discovered before startup."""
    def __init__(self):
        self.stopping = threading.Event()

    def tick(self):
        # Names are fetched once per real OA; share copies are updated from the owner's result.
        rows = [r for r in channels._rows() if not r['shared']]
        for channel_id in ([r['channel_id'] for r in rows if channels.operational(r)] if rows else ['']):
            with channels.use(channel_id):
                self.tick_channel()

    def tick_channel(self):
        import app
        if not channels.access_token():
            return
        now = int(time.time())
        with app.database_connection() as conn:
            ids = [r[0] for r in conn.execute("""SELECT recipient_id FROM recipients
                WHERE recipients.channel_id=current_channel() AND active=1 AND kind IN ('user','group') AND profile_next_at<=? AND profile_lease_until<=?
                AND length(recipient_id)=33 AND substr(recipient_id,2) NOT GLOB '*[^0-9a-fA-F]*'
                AND ((kind='user' AND substr(recipient_id,1,1)='U') OR (kind='group' AND substr(recipient_id,1,1)='C'))
                ORDER BY profile_next_at,recipient_id LIMIT 20""", (now,now))]
        for rid in ids:
            if self.stopping.is_set():
                break
            refresh_profile(rid)

    def start(self):
        def run():
            while not self.stopping.is_set():
                try:
                    self.tick()
                except Exception:
                    # A profile lookup must not stop webhook persistence or expose raw API errors.
                    pass
                self.stopping.wait(2)
        self.thread = threading.Thread(target=run, name='line-profile-cache', daemon=True)
        self.thread.start()

    def close(self):
        self.stopping.set()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=12)


def handle_event(conn, event, source_type, recipient_id):
    event_type = event.get("type")
    if event_type not in {"message", "follow", "unfollow", "join", "leave"}:
        return None
    stamp = event.get("timestamp")
    stamp = int(stamp) if isinstance(stamp, (int, float)) else int(time.time() * 1000)
    active = int(event_type not in {"unfollow", "leave"})
    conn.execute("""INSERT INTO recipients (channel_id,recipient_id, kind, active, event_at)
                    VALUES (current_channel(),?, ?, ?, ?)
                    ON CONFLICT (channel_id,recipient_id) DO UPDATE SET
                    active=CASE WHEN excluded.event_at >= event_at THEN excluded.active ELSE active END,
                    weather_subscribed=CASE WHEN excluded.event_at >= event_at AND excluded.active=0
                                            THEN 0 ELSE weather_subscribed END,
                    subscription_at=CASE WHEN excluded.event_at >= event_at AND excluded.active=0
                                         THEN MAX(subscription_at, excluded.event_at) ELSE subscription_at END,
                    event_at=MAX(event_at, excluded.event_at),
                    last_seen=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')""",
                 (recipient_id, source_type, active, stamp))
    company = channels.organization_id()
    if company is not None:
        conn.execute('UPDATE recipients SET company=? WHERE channel_id=current_channel() AND recipient_id=?', (company, recipient_id))
    # Shared workspaces hold copies of assigned recipients; follow/block state comes only from the owner's webhook.
    conn.execute(f"""UPDATE recipients SET active=o.active,event_at=o.event_at,last_seen=o.last_seen,
                     weather_subscribed=CASE WHEN o.active=0 THEN 0 ELSE recipients.weather_subscribed END
                     FROM (SELECT active,event_at,last_seen FROM recipients WHERE channel_id=current_channel() AND recipient_id=?) AS o
                     WHERE recipients.recipient_id=? AND recipients.channel_id IN ({channels.SHARE_SCOPES})""",
                 (recipient_id, recipient_id))
    message = event.get("message") or {}
    if event_type != "message" or message.get("type") != "text" or not message.get("id"):
        return None
    command = "".join(str(message.get("text", "")).split())
    if command not in COMMANDS:
        return None
    message_id = str(message["id"])
    if conn.execute('SELECT 1 FROM subscription_commands WHERE subscription_commands.channel_id=current_channel() AND message_id=?', (message_id,)).fetchone():
        return None
    if source_type != "user":
        response = "群組天氣訂閱由管理員設定。若要個人接收，請私訊我「訂閱天氣」。"
    else:
        if command in {"訂閱天氣", "取消訂閱", "取消訂閱天氣"}:
            conn.execute("""UPDATE recipients SET weather_subscribed=?, subscription_at=?
                            WHERE recipients.channel_id=current_channel() AND recipient_id=? AND active=1 AND subscription_at <= ?""",
                         (int(command == "訂閱天氣"), stamp, recipient_id, stamp))
        subscribed = conn.execute('SELECT weather_subscribed FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()[0]
        if command == "幫助":
            response = "可用指令：\n訂閱天氣：加入天氣通知名單\n取消訂閱：停止天氣通知\n我的訂閱：查看目前狀態\n目前由管理員發送報告，尚未設定每日自動排程。"
        else:
            response = ("目前已訂閱天氣通知。管理員發送報告時會通知你。\n可傳「取消訂閱」停止通知。"
                        if subscribed else "目前未訂閱天氣通知。可傳「訂閱天氣」加入。")
    conn.execute('INSERT INTO subscription_commands(channel_id,message_id,recipient_id,response) VALUES (current_channel(),?, ?, ?)', (message_id, recipient_id, response))
    token = event.get("replyToken")
    return (token, response) if token else None


def list_tags(conn):
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM contact_tags WHERE channel_id=current_channel() ORDER BY name").fetchall()]
    except sqlite3.OperationalError:
        return []


def save_tag(conn, name, color=None, tag_id=None):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 40:
        raise ValueError("標籤名稱請輸入 1 至 40 字以內。")
    color = (color or '#7C916C').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = '#7C916C'
    name = name.strip()
    if tag_id:
        row = conn.execute("SELECT tag_id FROM contact_tags WHERE channel_id=current_channel() AND tag_id=?", (tag_id,)).fetchone()
        if not row:
            raise ValueError("找不到標籤。")
        conn.execute("UPDATE contact_tags SET name=?, color=? WHERE channel_id=current_channel() AND tag_id=?", (name, color, tag_id))
        return tag_id
    else:
        existing = conn.execute("SELECT tag_id FROM contact_tags WHERE channel_id=current_channel() AND name=?", (name,)).fetchone()
        if existing:
            return existing[0]
        count = conn.execute("SELECT COUNT(*) FROM contact_tags WHERE channel_id=current_channel()").fetchone()[0]
        if count >= limits.TAGS_PER_OA:
            raise ValueError(f"每個 LINE OA 最多建立 {limits.TAGS_PER_OA} 個標籤，請刪除不用的標籤後再新增。")
        from uuid import uuid4
        new_id = "tag_" + str(uuid4().hex[:12])
        conn.execute("INSERT INTO contact_tags (tag_id, name, color, channel_id) VALUES (?, ?, ?, current_channel())", (new_id, name, color))
        return new_id


def delete_tag(conn, tag_id):
    conn.execute("DELETE FROM contact_tag_assignments WHERE channel_id=current_channel() AND tag_id=?", (tag_id,))
    conn.execute("DELETE FROM contact_tags WHERE channel_id=current_channel() AND tag_id=?", (tag_id,))


def set_contact_tags(conn, recipient_id, tag_ids):
    conn.execute("DELETE FROM contact_tag_assignments WHERE channel_id=current_channel() AND recipient_id=?", (recipient_id,))
    if tag_ids:
        tag_ids = tag_ids[:limits.TAGS_PER_CONTACT]
        for tid in tag_ids:
            if conn.execute("SELECT 1 FROM contact_tags WHERE channel_id=current_channel() AND tag_id=?", (tid,)).fetchone():
                conn.execute("INSERT OR IGNORE INTO contact_tag_assignments (channel_id, recipient_id, tag_id) VALUES (current_channel(), ?, ?)", (recipient_id, tid))


def bulk_update_tags(conn, recipient_ids, tag_ids, action="add"):
    if not isinstance(recipient_ids, list) or not isinstance(tag_ids, list):
        raise ValueError("參數格式不正確。")
    if len(recipient_ids) > limits.BULK_CONTACTS:
        raise ValueError(f"單次批次操作上限為 {limits.BULK_CONTACTS} 個聯絡對象，請分批操作。")

    # Verify contacts belong to current channel
    valid_ids = {r[0] for r in conn.execute(
        f"SELECT recipient_id FROM recipients WHERE channel_id=current_channel() AND recipient_id IN ({','.join(['?']*len(recipient_ids))})",
        tuple(recipient_ids)
    ).fetchall()} if recipient_ids else set()

    updated = 0
    skipped = 0

    for rid in recipient_ids:
        if rid not in valid_ids:
            continue
        if action == "add":
            current_tags = conn.execute(
                "SELECT COUNT(*) FROM contact_tag_assignments WHERE channel_id=current_channel() AND recipient_id=?",
                (rid,)
            ).fetchone()[0]
            if current_tags >= limits.TAGS_PER_CONTACT:
                skipped += 1
                continue
            available_slots = limits.TAGS_PER_CONTACT - current_tags
            assigned_this = 0
            for tid in tag_ids[:available_slots]:
                if conn.execute("SELECT 1 FROM contact_tags WHERE channel_id=current_channel() AND tag_id=?", (tid,)).fetchone():
                    res = conn.execute("INSERT OR IGNORE INTO contact_tag_assignments (channel_id, recipient_id, tag_id) VALUES (current_channel(), ?, ?)", (rid, tid))
                    if res.rowcount > 0:
                        assigned_this += 1
            if assigned_this > 0:
                updated += 1
        elif action == "remove":
            removed_this = 0
            for tid in tag_ids:
                res = conn.execute("DELETE FROM contact_tag_assignments WHERE channel_id=current_channel() AND recipient_id=? AND tag_id=?", (rid, tid))
                if res.rowcount > 0:
                    removed_this += 1
            if removed_this > 0:
                updated += 1

    return {'updated': updated, 'skipped': skipped}



def bulk_update_subscription(conn, recipient_ids, subscribed):
    if not isinstance(recipient_ids, list) or type(subscribed) is not bool:
        raise ValueError("參數格式不正確。")
    stamp = int(time.time() * 1000)
    for rid in recipient_ids:
        row = conn.execute("SELECT active FROM recipients WHERE channel_id=current_channel() AND recipient_id=?", (rid,)).fetchone()
        if row and (not subscribed or row[0]):
            conn.execute("UPDATE recipients SET weather_subscribed=?, subscription_at=? WHERE channel_id=current_channel() AND recipient_id=?",
                         (int(subscribed), stamp, rid))


def list_contacts(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recipients WHERE recipients.channel_id=current_channel() ORDER BY kind, COALESCE(NULLIF(alias,''), NULLIF(display_name,''), recipient_id)").fetchall()
    tags_by_recipient = {}
    try:
        tag_rows = conn.execute(
            """SELECT a.recipient_id, t.tag_id, t.name, t.color 
               FROM contact_tag_assignments a 
               JOIN contact_tags t ON a.tag_id=t.tag_id AND a.channel_id=t.channel_id 
               WHERE a.channel_id=current_channel()"""
        ).fetchall()
        for r in tag_rows:
            tags_by_recipient.setdefault(r["recipient_id"], []).append(
                {"id": r["tag_id"], "name": r["name"], "color": r["color"]}
            )
    except sqlite3.OperationalError:
        pass

    result = []
    for row in rows:
        d = dict(row)
        d["custom_name"] = d.get("alias", "")
        d["notes"] = d.get("notes", "")
        d["contact_type"] = d.get("contact_type", "")
        d["phone"] = d.get("phone", "")
        d["email"] = d.get("email", "")
        d["postal_code"] = d.get("postal_code", "")
        d["address"] = d.get("address", "")
        d["organization_name"] = d.get("organization_name", "")
        d["job_title"] = d.get("job_title", "")
        d["work_phone"] = d.get("work_phone", "")
        d["work_phone_ext"] = d.get("work_phone_ext", "")
        d["work_email"] = d.get("work_email", "")
        d["tags"] = tags_by_recipient.get(d["recipient_id"], [])
        result.append(d)
    return result


def update_contact(conn, recipient_id, alias, subscribed, notes=None, tag_ids=None,
                   contact_type=None, phone=None, email=None, postal_code=None, address=None,
                   organization_name=None, job_title=None, work_phone=None, work_phone_ext=None, work_email=None,
                   **kwargs):
    if not isinstance(alias, str) or len(alias) > 80 or type(subscribed) is not bool:
        raise ValueError("自訂名稱最多 80 字，訂閱設定必須為勾選值。")
    row = conn.execute('SELECT active FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
    if not row:
        raise ValueError("找不到聯絡對象，請先向 Bot 傳送訊息。")
    if subscribed and not row[0]:
        raise ValueError("已封鎖或已離開的聊天室不能加入訂閱。")

    if contact_type is not None:
        contact_type = str(contact_type).strip()
        if contact_type not in {'organization', 'person_business', 'person_private', ''}:
            raise ValueError("聯絡對象類型無效。")

    if notes is not None and (not isinstance(notes, str) or len(notes) > 2000):
        raise ValueError("備忘筆記請限制在 2000 字以內。")

    phone = str(phone).strip() if phone is not None else ""
    email = str(email).strip() if email is not None else ""
    postal_code = str(postal_code).strip() if postal_code is not None else ""
    address = str(address).strip() if address is not None else ""
    organization_name = str(organization_name).strip() if organization_name is not None else ""
    job_title = str(job_title).strip() if job_title is not None else ""
    work_phone = str(work_phone).strip() if work_phone is not None else ""
    work_phone_ext = str(work_phone_ext).strip() if work_phone_ext is not None else ""
    work_email = str(work_email).strip() if work_email is not None else ""
    notes_val = str(notes).strip() if notes is not None else ""

    # If contact_type is set, ensure fields follow non-applicable rules
    if contact_type == 'organization':
        job_title = ""
        work_phone = ""
        work_phone_ext = ""
        work_email = ""
    elif contact_type == 'person_private':
        organization_name = ""
        job_title = ""
        work_phone = ""
        work_phone_ext = ""
        work_email = ""

    stamp = int(time.time() * 1000)
    try:
        conn.execute("""UPDATE recipients SET
                        alias=?, notes=?, contact_type=?, phone=?, email=?, postal_code=?, address=?,
                        organization_name=?, job_title=?, work_phone=?, work_phone_ext=?, work_email=?,
                        weather_subscribed=?, subscription_at=?
                        WHERE recipients.channel_id=current_channel() AND recipient_id=?""",
                     (alias.strip(), notes_val, contact_type or "", phone, email, postal_code, address,
                      organization_name, job_title, work_phone, work_phone_ext, work_email,
                      int(subscribed), stamp, recipient_id))
    except sqlite3.OperationalError:
        conn.execute('UPDATE recipients SET alias=?, weather_subscribed=?, subscription_at=? WHERE recipients.channel_id=current_channel() AND recipient_id=?',
                     (alias.strip(), int(subscribed), stamp, recipient_id))

    if tag_ids is not None and isinstance(tag_ids, list):
        try:
            set_contact_tags(conn, recipient_id, tag_ids)
        except sqlite3.OperationalError:
            pass

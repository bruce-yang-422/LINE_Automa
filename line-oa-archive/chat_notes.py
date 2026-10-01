"""Chat Notes & Saved Filters management according to 聯絡人管理規格.md, 聊天功能規格.md & 案件管理流程規格.md"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
import channels

# Central Quantity Limits definition (集中定義數量上限)
LIMITS = {
    'MAX_TAGS_PER_OA': 100,
    'MAX_TAGS_PER_CONTACT': 10,
    'MAX_BULK_CONTACTS': 200,
    'MAX_CHAT_NOTES_PER_ROOM': 100,
    'MAX_PINNED_NOTES_PER_ROOM': 5,
    'MAX_TAGS_PER_NOTE': 5,
    'MAX_SAVED_FILTERS_PER_OA': 10
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_taipei_now() -> datetime:
    tz_taipei = timezone(timedelta(hours=8))
    return datetime.now(tz_taipei)


# ----------------- Chat Notes (對話記事本) -----------------

def list_chat_notes(conn: sqlite3.Connection, recipient_id: str, include_completed: bool = True) -> dict:
    conn.row_factory = sqlite3.Row
    # Purge old trash notes (> 30 days)
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    conn.execute(
        "DELETE FROM chat_notes WHERE channel_id=current_channel() AND deleted_at<>'' AND deleted_at < ?",
        (thirty_days_ago,)
    )

    sql = """SELECT * FROM chat_notes 
             WHERE channel_id=current_channel() AND recipient_id=? AND (deleted_at='' OR deleted_at IS NULL)"""
    params = [recipient_id]
    if not include_completed:
        sql += " AND is_completed=0"
    sql += " ORDER BY is_pinned DESC, created_at DESC"

    rows = conn.execute(sql, tuple(params)).fetchall()
    notes = []
    today_str = get_taipei_now().strftime('%Y-%m-%d')
    for r in rows:
        d = dict(r)
        d['tags'] = json.loads(d.get('tags_json') or '[]')
        d['is_overdue'] = bool(d.get('due_date') and d['due_date'] < today_str and not d.get('is_completed'))
        notes.append(d)

    trash_count = conn.execute(
        "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND deleted_at<>''",
        (recipient_id,)
    ).fetchone()[0]

    return {
        'notes': notes,
        'count': len(notes),
        'trash_count': trash_count,
        'limit': LIMITS['MAX_CHAT_NOTES_PER_ROOM'],
        'pinned_limit': LIMITS['MAX_PINNED_NOTES_PER_ROOM']
    }


def list_trash_notes(conn: sqlite3.Connection, recipient_id: str) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM chat_notes 
        WHERE channel_id=current_channel() AND recipient_id=? AND deleted_at<>''
        ORDER BY deleted_at DESC""",
        (recipient_id,)
    ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d['tags'] = json.loads(d.get('tags_json') or '[]')
        res.append(d)
    return res


def save_chat_note(conn: sqlite3.Connection, payload: dict, actor: str) -> dict:
    note_id = payload.get('note_id') or payload.get('id')
    recipient_id = (payload.get('recipient_id') or '').strip()
    title = (payload.get('title') or '').strip()[:100]
    note_type = (payload.get('note_type') or '一般').strip()[:40]
    content = (payload.get('content') or '').strip()
    about_member_id = (payload.get('about_member_id') or '').strip()
    due_date = (payload.get('due_date') or '').strip()
    is_completed = 1 if payload.get('is_completed') else 0
    
    tags = payload.get('tags', [])
    if isinstance(tags, list):
        tags = [str(t).strip() for t in tags if str(t).strip()][:LIMITS['MAX_TAGS_PER_NOTE']]
    else:
        tags = []
    tags_json = json.dumps(tags, ensure_ascii=False)

    if not content or len(content) > 1000:
        raise ValueError('記事內容必須在 1 至 1000 字之間。')

    if not recipient_id:
        raise ValueError('缺少聯絡對象聊天室識別碼。')

    ts = now_iso()
    if note_id:
        # Edit existing note
        note = conn.execute(
            "SELECT * FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
            (note_id,)
        ).fetchone()
        if not note:
            raise ValueError('找不到此記事。')
        
        # Check lock
        if note['is_locked']:
            raise ValueError('此記事已鎖定，請先解除 🔒 鎖定後再修改。')

        # Conflict check
        expected_ts = payload.get('expected_updated_at') or payload.get('last_updated_at')
        if expected_ts and note['updated_at'] != expected_ts:
            raise ValueError('此記事內容已被其他人修改，請重新整理取得最新版本。')

        conn.execute(
            """UPDATE chat_notes SET 
                title=?, note_type=?, tags_json=?, content=?, about_member_id=?,
                due_date=?, is_completed=?, author=?, updated_at=?
            WHERE channel_id=current_channel() AND note_id=?""",
            (title, note_type, tags_json, content, about_member_id, due_date, is_completed, actor, ts, note_id)
        )
        return {
            'note_id': note_id,
            'recipient_id': recipient_id,
            'title': title,
            'note_type': note_type,
            'tags': tags,
            'content': content,
            'about_member_id': about_member_id,
            'due_date': due_date,
            'is_completed': is_completed,
            'author': actor,
            'updated_at': ts
        }
    else:
        # Check limit
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND (deleted_at='' OR deleted_at IS NULL)",
            (recipient_id,)
        ).fetchone()[0]
        if count >= LIMITS['MAX_CHAT_NOTES_PER_ROOM']:
            raise ValueError(f'此聊天室的記事本已達上限（{LIMITS["MAX_CHAT_NOTES_PER_ROOM"]} 筆），請刪除舊記事後再新增。')

        new_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO chat_notes (
                note_id, channel_id, recipient_id, title, note_type, tags_json,
                content, is_pinned, is_locked, about_member_id, due_date, is_completed,
                deleted_at, author, created_at, updated_at
            ) VALUES (?, current_channel(), ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, '', ?, ?, ?)""",
            (new_id, recipient_id, title, note_type, tags_json, content, about_member_id, due_date, is_completed, actor, ts, ts)
        )
        return {
            'note_id': new_id,
            'recipient_id': recipient_id,
            'title': title,
            'note_type': note_type,
            'tags': tags,
            'content': content,
            'is_pinned': 0,
            'is_locked': 0,
            'about_member_id': about_member_id,
            'due_date': due_date,
            'is_completed': is_completed,
            'author': actor,
            'created_at': ts,
            'updated_at': ts
        }


def toggle_note_pin(conn: sqlite3.Connection, note_id: str) -> dict:
    note = conn.execute(
        "SELECT recipient_id, is_pinned FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        raise ValueError('找不到此記事。')
    recipient_id, is_pinned = note[0], note[1]

    if not is_pinned:
        # Check pinned limit
        pinned_count = conn.execute(
            "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND is_pinned=1 AND (deleted_at='' OR deleted_at IS NULL)",
            (recipient_id,)
        ).fetchone()[0]
        if pinned_count >= LIMITS['MAX_PINNED_NOTES_PER_ROOM']:
            raise ValueError(f'此聊天室置頂記事已達上限（{LIMITS["MAX_PINNED_NOTES_PER_ROOM"]} 筆）。')

    new_pin = 0 if is_pinned else 1
    ts = now_iso()
    conn.execute(
        "UPDATE chat_notes SET is_pinned=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (new_pin, ts, note_id)
    )
    return {'note_id': note_id, 'is_pinned': new_pin}


def toggle_note_lock(conn: sqlite3.Connection, note_id: str) -> dict:
    note = conn.execute(
        "SELECT is_locked FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        raise ValueError('找不到此記事。')
    new_locked = 0 if note[0] else 1
    ts = now_iso()
    conn.execute(
        "UPDATE chat_notes SET is_locked=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (new_locked, ts, note_id)
    )
    return {'note_id': note_id, 'is_locked': new_locked}


def delete_chat_note(conn: sqlite3.Connection, note_id: str) -> bool:
    note = conn.execute(
        "SELECT is_locked FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        return False
    if note[0]:
        raise ValueError('此記事已鎖定，請先解除 🔒 鎖定後再刪除。')

    # Soft delete
    ts = now_iso()
    res = conn.execute(
        "UPDATE chat_notes SET deleted_at=?, is_pinned=0, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (ts, ts, note_id)
    )
    return res.rowcount > 0


def restore_chat_note(conn: sqlite3.Connection, note_id: str) -> bool:
    ts = now_iso()
    res = conn.execute(
        "UPDATE chat_notes SET deleted_at='', updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (ts, note_id)
    )
    return res.rowcount > 0


def convert_note_to_case(conn: sqlite3.Connection, note_id: str, actor: str) -> dict:
    """Convert a chat note to a new case."""
    conn.row_factory = sqlite3.Row
    note = conn.execute(
        "SELECT * FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        raise ValueError('找不到此記事。')

    import cases
    title = note['title'] or f"來自記事：{note['content'][:30]}"
    payload = {
        'title': title,
        'case_subject_id': note['recipient_id'],
        'category': note['note_type'] or '一般',
        'description': note['content'],
        'due_date': note['due_date'],
        'source_note_id': note_id,
        'priority': 'medium'
    }
    new_case = cases.create_case(conn, payload, actor)
    return new_case


# ----------------- Saved Filters (自訂篩選條件) -----------------

def list_saved_filters(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM saved_filters WHERE channel_id=current_channel() ORDER BY created_at ASC"
    ).fetchall()
    filters = []
    for r in rows:
        d = dict(r)
        try:
            d['criteria'] = json.loads(d.get('criteria_json') or '{}')
        except Exception:
            d['criteria'] = {}
        filters.append(d)
    return {
        'filters': filters,
        'count': len(filters),
        'limit': LIMITS['MAX_SAVED_FILTERS_PER_OA']
    }


def save_saved_filter(conn: sqlite3.Connection, payload: dict) -> dict:
    filter_id = payload.get('filter_id') or payload.get('id')
    name = (payload.get('name') or '').strip()
    if not name or len(name) > 40:
        raise ValueError('篩選名稱請填寫 1 至 40 字以內。')

    criteria = payload.get('criteria') or {}
    criteria_json = json.dumps(criteria, ensure_ascii=False)
    ts = now_iso()

    if filter_id:
        conn.execute(
            "UPDATE saved_filters SET name=?, criteria_json=?, updated_at=? WHERE channel_id=current_channel() AND filter_id=?",
            (name, criteria_json, ts, filter_id)
        )
        return {'filter_id': filter_id, 'name': name, 'criteria': criteria, 'updated_at': ts}
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM saved_filters WHERE channel_id=current_channel()"
        ).fetchone()[0]
        if count >= LIMITS['MAX_SAVED_FILTERS_PER_OA']:
            raise ValueError(f'此 OA 的自訂篩選條件已達上限（{LIMITS["MAX_SAVED_FILTERS_PER_OA"]} 組），請刪除不用的篩選後再新增。')

        # check duplicate name in same OA
        dup = conn.execute(
            "SELECT filter_id FROM saved_filters WHERE channel_id=current_channel() AND name=?",
            (name,)
        ).fetchone()
        if dup:
            raise ValueError(f'已存在同名的篩選條件「{name}」。')

        new_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO saved_filters (filter_id, channel_id, name, criteria_json, created_at, updated_at)
            VALUES (?, current_channel(), ?, ?, ?, ?)""",
            (new_id, name, criteria_json, ts, ts)
        )
        return {'filter_id': new_id, 'name': name, 'criteria': criteria, 'created_at': ts, 'updated_at': ts}


def delete_saved_filter(conn: sqlite3.Connection, filter_id: str) -> bool:
    res = conn.execute(
        "DELETE FROM saved_filters WHERE channel_id=current_channel() AND filter_id=?",
        (filter_id,)
    )
    return res.rowcount > 0

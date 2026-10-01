"""Chat Notes & Saved Filters management according to 聯絡人管理規格.md"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
import channels

# Central Quantity Limits definition (集中定義數量上限)
LIMITS = {
    'MAX_TAGS_PER_OA': 100,
    'MAX_TAGS_PER_CONTACT': 10,
    'MAX_BULK_CONTACTS': 200,
    'MAX_CHAT_NOTES_PER_ROOM': 100,
    'MAX_SAVED_FILTERS_PER_OA': 10
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------- Chat Notes (對話記事本) -----------------

def list_chat_notes(conn: sqlite3.Connection, recipient_id: str) -> dict:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM chat_notes 
        WHERE channel_id=current_channel() AND recipient_id=? 
        ORDER BY created_at DESC""",
        (recipient_id,)
    ).fetchall()
    notes = [dict(r) for r in rows]
    return {
        'notes': notes,
        'count': len(notes),
        'limit': LIMITS['MAX_CHAT_NOTES_PER_ROOM']
    }


def save_chat_note(conn: sqlite3.Connection, payload: dict, actor: str) -> dict:
    note_id = payload.get('note_id') or payload.get('id')
    recipient_id = (payload.get('recipient_id') or '').strip()
    content = (payload.get('content') or '').strip()

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
        conn.execute(
            "UPDATE chat_notes SET content=?, author=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
            (content, actor, ts, note_id)
        )
        return {'note_id': note_id, 'recipient_id': recipient_id, 'content': content, 'author': actor, 'updated_at': ts}
    else:
        # Check limit
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=?",
            (recipient_id,)
        ).fetchone()[0]
        if count >= LIMITS['MAX_CHAT_NOTES_PER_ROOM']:
            raise ValueError(f'此聊天室的記事本已達上限（{LIMITS["MAX_CHAT_NOTES_PER_ROOM"]} 筆），請刪除舊記事後再新增。')

        new_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO chat_notes (note_id, channel_id, recipient_id, author, content, created_at, updated_at)
            VALUES (?, current_channel(), ?, ?, ?, ?, ?)""",
            (new_id, recipient_id, actor, content, ts, ts)
        )
        return {'note_id': new_id, 'recipient_id': recipient_id, 'content': content, 'author': actor, 'created_at': ts, 'updated_at': ts}


def delete_chat_note(conn: sqlite3.Connection, note_id: str) -> bool:
    res = conn.execute(
        "DELETE FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    )
    return res.rowcount > 0


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

"""Chat Notes & Taxonomy Governance management according to 對話記事本管理規格.md.

支援通用跨產業場景（商務、工務、政策、協商、教務、客服、筆記等），
具備 Apple iOS / macOS HIG 色彩系統、雙層管理（側欄與全域中心）、
組織彈性鎖定政策、分類與標籤防氾濫治理（合併、清理、調色）、轉為案件與匯出功能。
"""

import csv
import io
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

import channels
import limits
import reports


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_taipei_now() -> datetime:
    tz_taipei = timezone(timedelta(hours=8))
    return datetime.now(tz_taipei)


# ----------------- 預設 Apple HIG 分類與標籤 -----------------

DEFAULT_CATEGORIES = [
    {"name": "商務商談", "color": "#007AFF", "sort_order": 1},
    {"name": "工程工務", "color": "#FF9500", "sort_order": 2},
    {"name": "政策民意", "color": "#AF52DE", "sort_order": 3},
    {"name": "商務協商", "color": "#30B0C7", "sort_order": 4},
    {"name": "學校教務", "color": "#34C759", "sort_order": 5},
    {"name": "售後客服", "color": "#FF3B30", "sort_order": 6},
    {"name": "學生筆記", "color": "#FFCC00", "sort_order": 7},
    {"name": "一般備忘", "color": "#8E8E93", "sort_order": 8},
]

DEFAULT_TAGS = [
    {"name": "急件優先", "color": "#FF3B30", "category": "優先等級"},
    {"name": "待主管確認", "color": "#FFCC00", "category": "審核流程"},
    {"name": "已報價", "color": "#007AFF", "category": "商務進度"},
    {"name": "重要協議", "color": "#5856D6", "category": "法律合約"},
    {"name": "需二次回訪", "color": "#30B0C7", "category": "追蹤進度"},
    {"name": "現場勘查", "color": "#FF9500", "category": "工務執行"},
    {"name": "交接待辦", "color": "#34C759", "category": "內部協作"},
    {"name": "處理中", "color": "#8E8E93", "category": "任務狀態"},
]


def ensure_default_categories(conn: sqlite3.Connection, channel_id: Optional[str] = None) -> None:
    cid = channel_id or channels.current_id()
    if not cid:
        return
    count = conn.execute(
        "SELECT COUNT(*) FROM chat_note_categories WHERE channel_id=?", (cid,)
    ).fetchone()[0]
    if count == 0:
        ts = now_iso()
        for cat in DEFAULT_CATEGORIES:
            cat_id = uuid.uuid4().hex
            conn.execute(
                """INSERT OR IGNORE INTO chat_note_categories (category_id, channel_id, name, color, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (cat_id, cid, cat["name"], cat["color"], cat["sort_order"], ts)
            )


def ensure_default_tags(conn: sqlite3.Connection, channel_id: Optional[str] = None) -> None:
    cid = channel_id or channels.current_id()
    if not cid:
        return
    count = conn.execute(
        "SELECT COUNT(*) FROM chat_note_tags WHERE channel_id=?", (cid,)
    ).fetchone()[0]
    if count == 0:
        ts = now_iso()
        for t in DEFAULT_TAGS:
            tag_id = uuid.uuid4().hex
            conn.execute(
                """INSERT OR IGNORE INTO chat_note_tags (tag_id, channel_id, name, color, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (tag_id, cid, t["name"], t["color"], t["category"], ts)
            )


def get_org_note_policies(conn: sqlite3.Connection) -> dict:
    """查詢當前 OA 所屬組織的記事政策設定（note_lock_policy 與 note_tag_policy）。"""
    cid = channels.current_id()
    if not cid:
        return {"note_lock_policy": "disabled", "note_tag_policy": "controlled"}
    
    row = conn.execute(
        """SELECT o.note_lock_policy, o.note_tag_policy
        FROM line_channels c
        JOIN organizations o ON c.org_id = o.org_id
        WHERE c.channel_id = ?""",
        (cid,)
    ).fetchone()
    if row:
        return {
            "note_lock_policy": row[0] or "disabled",
            "note_tag_policy": row[1] or "controlled"
        }
    return {"note_lock_policy": "disabled", "note_tag_policy": "controlled"}


# ----------------- 對話記事本 (Chat Notes) CRUD & Lifecycle -----------------

def _format_note_dict(d: dict, today_str: str, cat_map: dict) -> dict:
    d = dict(d)
    tags_raw = d.get('tags_json') or '[]'
    try:
        d['tags'] = json.loads(tags_raw) if isinstance(tags_raw, str) else list(tags_raw)
    except Exception:
        d['tags'] = []
    
    cat_info = cat_map.get(d.get('category_id')) or cat_map.get(d.get('note_type')) or {}
    d['category_name'] = cat_info.get('name') or d.get('note_type') or '一般'
    d['category_color'] = cat_info.get('color') or '#007AFF'
    
    d['is_overdue'] = bool(d.get('due_date') and d['due_date'] < today_str and not d.get('is_completed'))
    return d


def list_chat_notes(conn: sqlite3.Connection, recipient_id: str, include_completed: bool = True) -> dict:
    """取得單一聊天室的記事列表（側欄檢視）。"""
    conn.row_factory = sqlite3.Row
    ensure_default_categories(conn)
    ensure_default_tags(conn)
    
    # 清理超過 30 天的垃圾桶記事
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=limits.NOTE_TRASH_DAYS)).isoformat()
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

    # 取得分類映射
    cat_rows = conn.execute(
        "SELECT category_id, name, color FROM chat_note_categories WHERE channel_id=current_channel()"
    ).fetchall()
    cat_map = {}
    for cr in cat_rows:
        cat_map[cr['category_id']] = {'name': cr['name'], 'color': cr['color']}
        cat_map[cr['name']] = {'name': cr['name'], 'color': cr['color']}

    notes = []
    today_str = get_taipei_now().strftime('%Y-%m-%d')
    pinned_count = 0
    active_count = 0
    completed_count = 0

    for r in rows:
        item = _format_note_dict(r, today_str, cat_map)
        if item.get('is_pinned'):
            pinned_count += 1
        if item.get('is_completed'):
            completed_count += 1
        else:
            active_count += 1
        notes.append(item)

    trash_count = conn.execute(
        "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND deleted_at<>''",
        (recipient_id,)
    ).fetchone()[0]

    policies = get_org_note_policies(conn)

    return {
        'notes': notes,
        'count': len(notes),
        'pinned_count': pinned_count,
        'active_count': active_count,
        'completed_count': completed_count,
        'trash_count': trash_count,
        'limit': limits.NOTES_PER_ROOM,
        'pinned_limit': limits.PINNED_NOTES_PER_ROOM,
        'policies': policies
    }


def list_trash_notes(conn: sqlite3.Connection, recipient_id: str = '') -> list:
    """取得垃圾桶記事。"""
    conn.row_factory = sqlite3.Row
    sql = """SELECT * FROM chat_notes 
             WHERE channel_id=current_channel() AND deleted_at<>''"""
    params = []
    if recipient_id:
        sql += " AND recipient_id=?"
        params.append(recipient_id)
    sql += " ORDER BY deleted_at DESC"
    
    rows = conn.execute(sql, tuple(params)).fetchall()
    
    cat_rows = conn.execute(
        "SELECT category_id, name, color FROM chat_note_categories WHERE channel_id=current_channel()"
    ).fetchall()
    cat_map = {}
    for cr in cat_rows:
        cat_map[cr['category_id']] = {'name': cr['name'], 'color': cr['color']}
        cat_map[cr['name']] = {'name': cr['name'], 'color': cr['color']}
        
    today_str = get_taipei_now().strftime('%Y-%m-%d')
    res = []
    for r in rows:
        res.append(_format_note_dict(r, today_str, cat_map))
    return res


def list_global_chat_notes(conn: sqlite3.Connection, query_params: dict, user_role: str = '') -> dict:
    """全域對話記事本管理中心查詢（支援多維度篩選與分頁）。"""
    conn.row_factory = sqlite3.Row
    ensure_default_categories(conn)
    ensure_default_tags(conn)
    
    q = (query_params.get('q') or '').strip()
    recipient_id = (query_params.get('recipient_id') or '').strip()
    category_id = (query_params.get('category_id') or '').strip()
    category_name = (query_params.get('category') or query_params.get('category_name') or '').strip()
    tag = (query_params.get('tag') or '').strip()
    status = (query_params.get('status') or 'all').strip()  # all, active, pinned, completed, locked, case, trash
    created_by = (query_params.get('created_by') or query_params.get('author') or '').strip()
    due_from = (query_params.get('due_from') or '').strip()
    due_to = (query_params.get('due_to') or '').strip()
    date_from = (query_params.get('date_from') or '').strip()
    date_to = (query_params.get('date_to') or '').strip()
    
    try:
        limit = max(1, min(int(query_params.get('limit', 50)), 200))
    except (ValueError, TypeError):
        limit = 50
    try:
        page = max(1, int(query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * limit

    where_clauses = ["channel_id=current_channel()"]
    params = []

    if status == 'trash':
        where_clauses.append("deleted_at<>''")
    else:
        where_clauses.append("(deleted_at='' OR deleted_at IS NULL)")
        if status == 'active':
            where_clauses.append("is_completed=0")
        elif status == 'pinned':
            where_clauses.append("is_pinned=1 AND is_completed=0")
        elif status == 'completed':
            where_clauses.append("is_completed=1")
        elif status == 'locked':
            where_clauses.append("is_locked=1")
        elif status == 'case':
            where_clauses.append("linked_case_id<>''")

    if recipient_id:
        where_clauses.append("recipient_id=?")
        params.append(recipient_id)

    if category_id:
        where_clauses.append("category_id=?")
        params.append(category_id)
    elif category_name:
        where_clauses.append("(note_type=? OR category_id IN (SELECT category_id FROM chat_note_categories WHERE channel_id=current_channel() AND name=?))")
        params.extend([category_name, category_name])

    if tag:
        where_clauses.append("tags_json LIKE ?")
        params.append(f'%"{tag}"%')

    if q:
        where_clauses.append("(title LIKE ? OR content LIKE ? OR author LIKE ?)")
        wildcard = f"%{q}%"
        params.extend([wildcard, wildcard, wildcard])

    if created_by:
        where_clauses.append("author=?")
        params.append(created_by)

    if due_from:
        where_clauses.append("due_date >= ? AND due_date <> ''")
        params.append(due_from)
    if due_to:
        where_clauses.append("due_date <= ? AND due_date <> ''")
        params.append(due_to)

    if date_from:
        where_clauses.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("created_at <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_clauses)
    count_sql = f"SELECT COUNT(*) FROM chat_notes WHERE {where_sql}"
    total = conn.execute(count_sql, tuple(params)).fetchone()[0]

    select_sql = f"""SELECT * FROM chat_notes 
                     WHERE {where_sql} 
                     ORDER BY is_pinned DESC, updated_at DESC, created_at DESC 
                     LIMIT ? OFFSET ?"""
    query_params_list = list(params) + [limit, offset]
    rows = conn.execute(select_sql, tuple(query_params_list)).fetchall()

    # 取得分類映射
    cat_rows = conn.execute(
        "SELECT category_id, name, color FROM chat_note_categories WHERE channel_id=current_channel() ORDER BY sort_order ASC, name ASC"
    ).fetchall()
    cat_map = {}
    categories_list = []
    for cr in cat_rows:
        cat_info = {'id': cr['category_id'], 'category_id': cr['category_id'], 'name': cr['name'], 'color': cr['color']}
        cat_map[cr['category_id']] = cat_info
        cat_map[cr['name']] = cat_info
        categories_list.append(cat_info)

    today_str = get_taipei_now().strftime('%Y-%m-%d')
    notes = [_format_note_dict(r, today_str, cat_map) for r in rows]

    tags_data = list_note_tags(conn)
    policies = get_org_note_policies(conn)

    return {
        'notes': notes,
        'total': total,
        'page': page,
        'limit': limit,
        'categories': categories_list,
        'tags': tags_data.get('tags', []),
        'policies': policies
    }


def save_chat_note(conn: sqlite3.Connection, payload: dict, actor: str, actor_role: str = '') -> dict:
    """新增或修改記事（明確手動儲存）。"""
    note_id = (payload.get('note_id') or payload.get('id') or '').strip()
    recipient_id = (payload.get('recipient_id') or '').strip()
    title = (payload.get('title') or '').strip()[:100]
    content = (payload.get('content') or '').strip()
    category_id = (payload.get('category_id') or '').strip()
    note_type = (payload.get('note_type') or '一般').strip()[:40]
    target_user_id = (payload.get('target_user_id') or payload.get('about_member_id') or '').strip()
    due_date = (payload.get('due_date') or '').strip()
    source_message_id = (payload.get('source_message_id') or '').strip()
    linked_case_id = (payload.get('linked_case_id') or '').strip()
    is_completed = 1 if payload.get('is_completed') else 0

    if not content or len(content) > limits.NOTE_CONTENT_MAX:
        raise ValueError(f'記事內容必須在 1 至 {limits.NOTE_CONTENT_MAX} 字之間。')

    if not recipient_id:
        raise ValueError('缺少聯絡對象聊天室識別碼。')

    # 若傳入 category_id 但未指定 note_type，嘗試從 category_id 反查名稱
    if category_id:
        cat_row = conn.execute(
            "SELECT name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
            (category_id,)
        ).fetchone()
        if cat_row:
            note_type = cat_row[0]
    elif note_type:
        cat_row = conn.execute(
            "SELECT category_id FROM chat_note_categories WHERE channel_id=current_channel() AND name=?",
            (note_type,)
        ).fetchone()
        if cat_row:
            category_id = cat_row[0]

    # 標籤處理
    tags_in = payload.get('tags', [])
    if isinstance(tags_in, str):
        try:
            tags_in = json.loads(tags_in)
        except Exception:
            tags_in = [t.strip() for t in tags_in.split(',') if t.strip()]
    if isinstance(tags_in, list):
        tags = [str(t).strip().lstrip('#') for t in tags_in if str(t).strip()][:limits.TAGS_PER_NOTE]
    else:
        tags = []

    # 檢查標籤政策與數量上限
    if tags:
        policies = get_org_note_policies(conn)
        existing_tags = set(t['name'] for t in list_note_tags(conn)['tags'])
        new_tags_attempt = set(tags) - existing_tags

        if len(existing_tags | set(tags)) > limits.NOTE_TAGS_PER_OA and new_tags_attempt:
            raise ValueError(f'此 OA 的記事標籤已達上限（{limits.NOTE_TAGS_PER_OA} 個），請沿用既有標籤或先刪除不用的標籤。')

        if new_tags_attempt:
            if actor_role == 'collaborator':
                raise ValueError('協作人員僅能選用既有標準標籤，無法自創新標籤。')
            for nt in new_tags_attempt:
                tag_id = uuid.uuid4().hex
                conn.execute(
                    """INSERT OR IGNORE INTO chat_note_tags (tag_id, channel_id, name, color, category, created_at)
                    VALUES (?, current_channel(), ?, '#007AFF', 'general', ?)""",
                    (tag_id, nt, now_iso())
                )

    tags_json = json.dumps(tags, ensure_ascii=False)
    ts = now_iso()

    if note_id:
        # 修改既有記事
        conn.row_factory = sqlite3.Row
        note = conn.execute(
            "SELECT * FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
            (note_id,)
        ).fetchone()
        if not note:
            raise ValueError('找不到此記事。')

        # 鎖定狀態檢查
        if note['is_locked']:
            raise ValueError('此記事已鎖定為唯讀狀態，請先解除鎖定後再進行修改。')

        # 衝突防護檢查 (Dirty Check / Optimistic Concurrency)
        expected_ts = payload.get('expected_updated_at') or payload.get('last_updated_at')
        if expected_ts and note['updated_at'] != expected_ts:
            raise ValueError('此記事內容已被其他人修改，請重新整理取得最新版本後再儲存。')

        conn.execute(
            """UPDATE chat_notes SET 
                title=?, note_type=?, category_id=?, tags_json=?, content=?, 
                target_user_id=?, about_member_id=?, due_date=?, source_message_id=?, 
                linked_case_id=?, is_completed=?, author=?, updated_at=?
            WHERE channel_id=current_channel() AND note_id=?""",
            (title, note_type, category_id, tags_json, content,
             target_user_id, target_user_id, due_date, source_message_id,
             linked_case_id, is_completed, actor, ts, note_id)
        )

        # 更新多對多標籤關聯表
        _sync_note_tags_assignments(conn, note_id, tags)

        return {
            'note_id': note_id,
            'id': note_id,
            'recipient_id': recipient_id,
            'title': title,
            'note_type': note_type,
            'category_id': category_id,
            'tags': tags,
            'content': content,
            'target_user_id': target_user_id,
            'about_member_id': target_user_id,
            'due_date': due_date,
            'source_message_id': source_message_id,
            'linked_case_id': linked_case_id,
            'is_completed': is_completed,
            'author': actor,
            'updated_at': ts
        }
    else:
        # 檢查單一聊天室上限 (100 筆)
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND (deleted_at='' OR deleted_at IS NULL)",
            (recipient_id,)
        ).fetchone()[0]
        if count >= limits.NOTES_PER_ROOM:
            raise ValueError(f'此聊天室的記事本已達上限（{limits.NOTES_PER_ROOM} 筆），請先歸檔或刪除舊記事後再新增。')

        new_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO chat_notes (
                note_id, channel_id, recipient_id, target_user_id, title, note_type, category_id,
                tags_json, content, is_pinned, is_locked, about_member_id, due_date,
                source_message_id, linked_case_id, is_completed, deleted_at, author, created_at, updated_at
            ) VALUES (?, current_channel(), ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, '', ?, ?, ?)""",
            (new_id, recipient_id, target_user_id, title, note_type, category_id,
             tags_json, content, target_user_id, due_date, source_message_id,
             linked_case_id, is_completed, actor, ts, ts)
        )

        # 寫入標籤關聯
        _sync_note_tags_assignments(conn, new_id, tags)

        return {
            'note_id': new_id,
            'id': new_id,
            'recipient_id': recipient_id,
            'title': title,
            'note_type': note_type,
            'category_id': category_id,
            'tags': tags,
            'content': content,
            'is_pinned': 0,
            'is_locked': 0,
            'target_user_id': target_user_id,
            'about_member_id': target_user_id,
            'due_date': due_date,
            'source_message_id': source_message_id,
            'linked_case_id': linked_case_id,
            'is_completed': is_completed,
            'author': actor,
            'created_at': ts,
            'updated_at': ts
        }


def _sync_note_tags_assignments(conn: sqlite3.Connection, note_id: str, tags: list) -> None:
    cid = channels.current_id()
    conn.execute(
        "DELETE FROM chat_note_tag_assignments WHERE channel_id=? AND note_id=?",
        (cid, note_id)
    )
    if not tags:
        return
    ts = now_iso()
    for tag_name in tags:
        tag_row = conn.execute(
            "SELECT tag_id FROM chat_note_tags WHERE channel_id=? AND name=?",
            (cid, tag_name)
        ).fetchone()
        if tag_row:
            conn.execute(
                """INSERT OR IGNORE INTO chat_note_tag_assignments (channel_id, note_id, tag_id, created_at)
                VALUES (?, ?, ?, ?)""",
                (cid, note_id, tag_row[0], ts)
            )


def toggle_note_pin(conn: sqlite3.Connection, note_id: str) -> dict:
    """切換置頂狀態（單一聊天室上限 5 筆）。"""
    note = conn.execute(
        "SELECT recipient_id, is_pinned FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        raise ValueError('找不到此記事。')
    recipient_id, is_pinned = note[0], note[1]

    if not is_pinned:
        pinned_count = conn.execute(
            "SELECT COUNT(*) FROM chat_notes WHERE channel_id=current_channel() AND recipient_id=? AND is_pinned=1 AND (deleted_at='' OR deleted_at IS NULL)",
            (recipient_id,)
        ).fetchone()[0]
        if pinned_count >= limits.PINNED_NOTES_PER_ROOM:
            raise ValueError(f'此聊天室置頂記事已達上限（{limits.PINNED_NOTES_PER_ROOM} 筆），請先取消現有置頂。')

    new_pin = 0 if is_pinned else 1
    ts = now_iso()
    conn.execute(
        "UPDATE chat_notes SET is_pinned=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (new_pin, ts, note_id)
    )
    return {'note_id': note_id, 'is_pinned': new_pin}


def toggle_note_lock(conn: sqlite3.Connection, note_id: str, actor_role: str = '') -> dict:
    """切換記事鎖定狀態（依據組織 note_lock_policy 嚴格校驗）。"""
    policies = get_org_note_policies(conn)
    lock_policy = policies.get('note_lock_policy', 'disabled')

    if lock_policy == 'disabled':
        raise ValueError('組織目前設定為自由編輯模式，無需使用鎖定功能。')
    elif lock_policy == 'strict_admin' and actor_role not in {'org_admin', 'platform_admin'}:
        raise ValueError('組織設定為嚴格合規模式，僅組織管理員可以鎖定或解鎖記事。')

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


def toggle_note_completed(conn: sqlite3.Connection, note_id: str) -> dict:
    """標記已完成或重啟記事。"""
    note = conn.execute(
        "SELECT is_completed, is_locked FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        raise ValueError('找不到此記事。')
    if note[1]:
        raise ValueError('此記事已鎖定，請先解除鎖定後再修改完成狀態。')

    new_completed = 0 if note[0] else 1
    ts = now_iso()
    conn.execute(
        "UPDATE chat_notes SET is_completed=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (new_completed, ts, note_id)
    )
    return {'note_id': note_id, 'is_completed': new_completed}


def delete_chat_note(conn: sqlite3.Connection, note_id: str, actor_role: str = '') -> bool:
    """軟刪除記事（移入垃圾桶）。"""
    note = conn.execute(
        "SELECT is_locked FROM chat_notes WHERE channel_id=current_channel() AND note_id=?",
        (note_id,)
    ).fetchone()
    if not note:
        return False
    if note[0]:
        raise ValueError('此記事已鎖定，請先解除鎖定後再刪除。')

    ts = now_iso()
    res = conn.execute(
        "UPDATE chat_notes SET deleted_at=?, is_pinned=0, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (ts, ts, note_id)
    )
    return res.rowcount > 0


def restore_chat_note(conn: sqlite3.Connection, note_id: str) -> bool:
    """從垃圾桶還原記事。"""
    ts = now_iso()
    res = conn.execute(
        "UPDATE chat_notes SET deleted_at='', updated_at=? WHERE channel_id=current_channel() AND note_id=?",
        (ts, note_id)
    )
    return res.rowcount > 0


def purge_chat_note(conn: sqlite3.Connection, note_id: str, actor_role: str = '') -> bool:
    """永久刪除垃圾桶中的指定記事（僅限管理員）。"""
    if actor_role not in {'org_admin', 'platform_admin'}:
        raise ValueError('只有管理員可以永久刪除記事。')
    
    cid = channels.current_id()
    conn.execute(
        "DELETE FROM chat_note_tag_assignments WHERE channel_id=? AND note_id=?",
        (cid, note_id)
    )
    res = conn.execute(
        "DELETE FROM chat_notes WHERE channel_id=? AND note_id=? AND deleted_at<>''",
        (cid, note_id)
    )
    return res.rowcount > 0


def convert_note_to_case(conn: sqlite3.Connection, note_id: str, actor: str) -> dict:
    """將記事升級轉換為正式案件，並建立雙向關聯。"""
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
    case_id = new_case.get('case_id') or new_case.get('id')
    
    # 寫回雙向關聯
    if case_id:
        conn.execute(
            "UPDATE chat_notes SET linked_case_id=?, updated_at=? WHERE channel_id=current_channel() AND note_id=?",
            (case_id, now_iso(), note_id)
        )
    return new_case


# ----------------- 分類治理 (Category Governance) -----------------

def list_note_categories(conn: sqlite3.Connection) -> dict:
    """取得組織標準分類清單（含各分類引用計數）。"""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT c.category_id, c.name, c.color, c.sort_order, c.created_at,
                  (SELECT COUNT(*) FROM chat_notes n 
                   WHERE n.channel_id=c.channel_id 
                     AND (n.category_id=c.category_id OR n.note_type=c.name) 
                     AND (n.deleted_at='' OR n.deleted_at IS NULL)) as usage_count
           FROM chat_note_categories c
           WHERE c.channel_id=current_channel()
           ORDER BY c.sort_order ASC, c.name ASC"""
    ).fetchall()
    
    categories = []
    for r in rows:
        d = dict(r)
        d['note_count'] = d.get('usage_count', 0)
        categories.append(d)
    return {
        'categories': categories,
        'count': len(categories),
        'limit': limits.NOTE_CATEGORIES_PER_OA
    }


def save_note_category(conn: sqlite3.Connection, payload: dict, actor_role: str = '') -> dict:
    """新增或修改記事分類（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無記事分類管理權限。')

    ensure_default_categories(conn)
    category_id = (payload.get('category_id') or payload.get('id') or '').strip()
    name = (payload.get('name') or '').strip()[:30]
    color = (payload.get('color') or '#007AFF').strip()[:20]
    try:
        sort_order = int(payload.get('sort_order', 0))
    except (ValueError, TypeError):
        sort_order = 0

    if not name:
        raise ValueError('分類名稱不能為空。')

    ts = now_iso()
    if category_id:
        # 修改既有分類
        old_cat = conn.execute(
            "SELECT name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
            (category_id,)
        ).fetchone()
        if not old_cat:
            raise ValueError('找不到此分類。')
        
        old_name = old_cat[0]
        conn.execute(
            """UPDATE chat_note_categories 
            SET name=?, color=?, sort_order=? 
            WHERE channel_id=current_channel() AND category_id=?""",
            (name, color, sort_order, category_id)
        )
        if old_name != name:
            conn.execute(
                """UPDATE chat_notes 
                SET note_type=? 
                WHERE channel_id=current_channel() AND (category_id=? OR note_type=?)""",
                (name, category_id, old_name)
            )
        return {'category_id': category_id, 'name': name, 'color': color, 'sort_order': sort_order}
    else:
        existing = conn.execute(
            "SELECT category_id FROM chat_note_categories WHERE channel_id=current_channel() AND name=?",
            (name,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE chat_note_categories SET color=?, sort_order=? WHERE channel_id=current_channel() AND category_id=?",
                (color, sort_order, existing[0])
            )
            return {'category_id': existing[0], 'name': name, 'color': color, 'sort_order': sort_order}

        # 檢查數量上限
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_note_categories WHERE channel_id=current_channel()"
        ).fetchone()[0]
        if count >= limits.NOTE_CATEGORIES_PER_OA:
            raise ValueError(f'此 OA 的記事分類已達上限（{limits.NOTE_CATEGORIES_PER_OA} 個）。')

        new_id = uuid.uuid4().hex
        try:
            conn.execute(
                """INSERT INTO chat_note_categories (category_id, channel_id, name, color, sort_order, created_at)
                VALUES (?, current_channel(), ?, ?, ?, ?)""",
                (new_id, name, color, sort_order, ts)
            )
        except sqlite3.IntegrityError:
            raise ValueError(f'已存在名稱為「{name}」的分類。')
        return {'category_id': new_id, 'name': name, 'color': color, 'sort_order': sort_order}


def merge_note_categories(conn: sqlite3.Connection, source_category_ids: list, target_category_id: str, actor_role: str = '') -> dict:
    """合併多個同義分類至目標分類，並自動轉移歷史記事關聯（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無分類治理權限。')

    if not target_category_id or not source_category_ids:
        raise ValueError('請指定要合併的來源分類與目標分類。')

    target_cat = conn.execute(
        "SELECT category_id, name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
        (target_category_id,)
    ).fetchone()
    if not target_cat:
        raise ValueError('找不到目標分類。')
    
    target_id, target_name = target_cat[0], target_cat[1]

    placeholders = ",".join("?" for _ in source_category_ids)
    source_rows = conn.execute(
        f"SELECT category_id, name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id IN ({placeholders})",
        tuple(source_category_ids)
    ).fetchall()

    source_names = [r[1] for r in source_rows if r[0] != target_id]
    valid_source_ids = [r[0] for r in source_rows if r[0] != target_id]

    if not valid_source_ids:
        return {'ok': True, 'merged_count': 0}

    # 批次更新記事
    for sid in valid_source_ids:
        conn.execute(
            """UPDATE chat_notes 
            SET category_id=?, note_type=?
            WHERE channel_id=current_channel() AND category_id=?""",
            (target_id, target_name, sid)
        )
    for sname in source_names:
        conn.execute(
            """UPDATE chat_notes 
            SET category_id=?, note_type=?
            WHERE channel_id=current_channel() AND note_type=?""",
            (target_id, target_name, sname)
        )

    # 刪除被合併的來源分類
    conn.execute(
        f"DELETE FROM chat_note_categories WHERE channel_id=current_channel() AND category_id IN ({','.join('?' for _ in valid_source_ids)})",
        tuple(valid_source_ids)
    )

    return {'ok': True, 'merged_count': len(valid_source_ids), 'target_category_id': target_id}


def delete_note_category(conn: sqlite3.Connection, category_id: str, reassign_to_id: str = '', actor_role: str = '') -> dict:
    """刪除分類（支援關聯記事自動轉移目標分類）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無分類管理權限。')

    cat = conn.execute(
        "SELECT name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
        (category_id,)
    ).fetchone()
    if not cat:
        return {'ok': True}

    cat_name = cat[0]

    # 若有指定轉移目標
    if reassign_to_id:
        target = conn.execute(
            "SELECT name FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
            (reassign_to_id,)
        ).fetchone()
        if target:
            conn.execute(
                "UPDATE chat_notes SET category_id=?, note_type=? WHERE channel_id=current_channel() AND (category_id=? OR note_type=?)",
                (reassign_to_id, target[0], category_id, cat_name)
            )
    else:
        # 重設為未分類 / 一般備忘
        conn.execute(
            "UPDATE chat_notes SET category_id='', note_type='一般' WHERE channel_id=current_channel() AND (category_id=? OR note_type=?)",
            (category_id, cat_name)
        )

    conn.execute(
        "DELETE FROM chat_note_categories WHERE channel_id=current_channel() AND category_id=?",
        (category_id,)
    )
    return {'ok': True}


# ----------------- 標籤治理 (Tag Governance) -----------------

def list_note_tags(conn: sqlite3.Connection) -> dict:
    """取得組織標準標籤庫清單（含各標籤引用篇數）。"""
    conn.row_factory = sqlite3.Row
    tag_rows = conn.execute(
        """SELECT t.tag_id, t.name, t.color, t.category, t.created_at,
                  (SELECT COUNT(*) FROM chat_notes n 
                   WHERE n.channel_id=t.channel_id 
                     AND n.tags_json LIKE ('%"' || t.name || '"%')
                     AND (n.deleted_at='' OR n.deleted_at IS NULL)) as usage_count
           FROM chat_note_tags t
           WHERE t.channel_id=current_channel()
           ORDER BY usage_count DESC, t.name ASC"""
    ).fetchall()
    
    known_names = {r['name'] for r in tag_rows}
    cat_usage_by_tag = {}  # { tag_name: { category_id: count, category_name: count } }
    notes_rows = conn.execute(
        "SELECT category_id, note_type, tags_json FROM chat_notes WHERE channel_id=current_channel() AND (deleted_at='' OR deleted_at IS NULL)"
    ).fetchall()
    extra_counts = {}
    for nr in notes_rows:
        cid_val = nr[0] or ''
        ntype_val = nr[1] or ''
        try:
            for t in json.loads(nr[2] or '[]'):
                if not t:
                    continue
                if t not in cat_usage_by_tag:
                    cat_usage_by_tag[t] = {}
                if cid_val:
                    cat_usage_by_tag[t][cid_val] = cat_usage_by_tag[t].get(cid_val, 0) + 1
                if ntype_val:
                    cat_usage_by_tag[t][ntype_val] = cat_usage_by_tag[t].get(ntype_val, 0) + 1
                if t not in known_names:
                    extra_counts[t] = extra_counts.get(t, 0) + 1
        except Exception:
            pass

    default_tag_colors = {t['name']: t['color'] for t in DEFAULT_TAGS}
    apple_palette = ["#007AFF", "#34C759", "#FF9500", "#AF52DE", "#FF2D55", "#5856D6", "#30B0C7", "#FF3B30", "#FFCC00", "#8E8E93"]

    tags = []
    for r in tag_rows:
        d = dict(r)
        d['count'] = d['usage_count']
        d['note_count'] = d['usage_count']
        d['category_usage'] = cat_usage_by_tag.get(d['name'], {})
        if not d.get('color'):
            d['color'] = default_tag_colors.get(d['name']) or apple_palette[abs(hash(d['name'])) % len(apple_palette)]
        tags.append(d)
    for name, cnt in sorted(extra_counts.items(), key=lambda x: (-x[1], x[0])):
        c = default_tag_colors.get(name) or apple_palette[abs(hash(name)) % len(apple_palette)]
        tags.append({
            'tag_id': '',
            'name': name,
            'color': c,
            'category': 'general',
            'created_at': '',
            'usage_count': cnt,
            'count': cnt,
            'note_count': cnt,
            'category_usage': cat_usage_by_tag.get(name, {})
        })

    return {
        'tags': tags,
        'count': len(tags),
        'limit': limits.NOTE_TAGS_PER_OA
    }


def save_note_tag(conn: sqlite3.Connection, name: str, old_name: str = '', color: str = '', category: str = '', actor_role: str = '') -> dict:
    """新增或修改標籤（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無標籤管理權限。')

    name = str(name).strip().lstrip('#')
    old_name = str(old_name).strip().lstrip('#') if old_name else ''
    color = (color or '#007AFF').strip()
    category = (category or 'general').strip()

    if not name or len(name) > 30:
        raise ValueError('記事標籤名稱需在 1 至 30 字以內。')

    cid = channels.current_id()
    ts = now_iso()

    if old_name and old_name != name:
        # 更名
        conn.execute(
            "UPDATE chat_note_tags SET name=?, color=?, category=? WHERE channel_id=? AND name=?",
            (name, color, category, cid, old_name)
        )
        # 同步更新記事 tags_json
        rows = conn.execute(
            "SELECT note_id, tags_json FROM chat_notes WHERE channel_id=? AND tags_json LIKE ?",
            (cid, f'%"{old_name}"%')
        ).fetchall()
        for nid, tj in rows:
            tags = json.loads(tj or '[]')
            if old_name in tags:
                new_tags = [name if t == old_name else t for t in tags]
                seen = set()
                deduped = [x for x in new_tags if not (x in seen or seen.add(x))]
                conn.execute(
                    "UPDATE chat_notes SET tags_json=? WHERE channel_id=? AND note_id=?",
                    (json.dumps(deduped, ensure_ascii=False), cid, nid)
                )
    else:
        # 新增或更新顏色分組
        existing = conn.execute(
            "SELECT tag_id FROM chat_note_tags WHERE channel_id=? AND name=?",
            (cid, name)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE chat_note_tags SET color=?, category=? WHERE channel_id=? AND name=?",
                (color, category, cid, name)
            )
        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM chat_note_tags WHERE channel_id=?", (cid,)
            ).fetchone()[0]
            if count >= limits.NOTE_TAGS_PER_OA:
                raise ValueError(f'此 OA 的記事標籤已達上限（{limits.NOTE_TAGS_PER_OA} 個）。')
            tag_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO chat_note_tags (tag_id, channel_id, name, color, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (tag_id, cid, name, color, category, ts)
            )

    return list_note_tags(conn)


def merge_note_tags(conn: sqlite3.Connection, source_names: list, target_name: str, actor_role: str = '') -> dict:
    """合併多個同義標籤至指定目標標籤，自動移轉所有歷史記事關聯（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無標籤治理權限。')

    target_name = str(target_name).strip().lstrip('#')
    if not target_name:
        raise ValueError('請指定合併的目標標籤。')

    clean_sources = [str(s).strip().lstrip('#') for s in source_names if str(s).strip().lstrip('#') and str(s).strip().lstrip('#') != target_name]
    if not clean_sources:
        return {'ok': True, 'merged_count': 0}

    cid = channels.current_id()
    # 確保目標標籤存在
    target_tag = conn.execute(
        "SELECT tag_id FROM chat_note_tags WHERE channel_id=? AND name=?",
        (cid, target_name)
    ).fetchone()
    if not target_tag:
        save_note_tag(conn, target_name, color='#007AFF', actor_role=actor_role)

    # 批次更新記事 tags_json
    notes = conn.execute(
        "SELECT note_id, tags_json FROM chat_notes WHERE channel_id=?", (cid,)
    ).fetchall()

    source_set = set(clean_sources)
    for nid, tj in notes:
        tags = json.loads(tj or '[]')
        if any(t in source_set for t in tags):
            new_tags = []
            has_target = False
            for t in tags:
                if t in source_set or t == target_name:
                    if not has_target:
                        new_tags.append(target_name)
                        has_target = True
                else:
                    new_tags.append(t)
            conn.execute(
                "UPDATE chat_notes SET tags_json=? WHERE channel_id=? AND note_id=?",
                (json.dumps(new_tags, ensure_ascii=False), cid, nid)
            )
            _sync_note_tags_assignments(conn, nid, new_tags)

    # 刪除被合併的來源標籤
    placeholders = ",".join("?" for _ in clean_sources)
    conn.execute(
        f"DELETE FROM chat_note_tags WHERE channel_id=? AND name IN ({placeholders})",
        tuple([cid] + clean_sources)
    )

    return {'ok': True, 'merged_count': len(clean_sources), 'target_tag': target_name}


def cleanup_orphan_tags(conn: sqlite3.Connection, actor_role: str = '') -> dict:
    """一鍵清理 0 篇引用之孤立廢棄標籤（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無標籤清理權限。')

    cid = channels.current_id()
    tags_data = list_note_tags(conn)
    orphan_names = [t['name'] for t in tags_data.get('tags', []) if t.get('usage_count', 0) == 0]

    if not orphan_names:
        return {'ok': True, 'cleaned_count': 0}

    placeholders = ",".join("?" for _ in orphan_names)
    conn.execute(
        f"DELETE FROM chat_note_tags WHERE channel_id=? AND name IN ({placeholders})",
        tuple([cid] + orphan_names)
    )
    return {'ok': True, 'cleaned_count': len(orphan_names), 'cleaned_tags': orphan_names}


def delete_note_tag(conn: sqlite3.Connection, name: str, actor_role: str = '') -> dict:
    """刪除標籤（僅限乙級與丙級）。"""
    if actor_role in {'collaborator'}:
        raise ValueError('協作人員無標籤管理權限。')

    name = str(name).strip().lstrip('#')
    cid = channels.current_id()

    # 從所有記事中移除此標籤
    rows = conn.execute(
        "SELECT note_id, tags_json FROM chat_notes WHERE channel_id=? AND tags_json LIKE ?",
        (cid, f'%"{name}"%')
    ).fetchall()
    for nid, tj in rows:
        tags = json.loads(tj or '[]')
        if name in tags:
            new_tags = [t for t in tags if t != name]
            conn.execute(
                "UPDATE chat_notes SET tags_json=? WHERE channel_id=? AND note_id=?",
                (json.dumps(new_tags, ensure_ascii=False), cid, nid)
            )
            _sync_note_tags_assignments(conn, nid, new_tags)

    conn.execute(
        "DELETE FROM chat_note_tags WHERE channel_id=? AND name=?",
        (cid, name)
    )
    return list_note_tags(conn)


# ----------------- 匯出功能 (Export) -----------------

def export_chat_notes(conn: sqlite3.Connection, query_params: dict, fmt: str = 'csv', actor: str = '') -> Tuple[bytes, str, str]:
    """匯出符合篩選條件之記事（CSV / JSON / Markdown）。"""
    res = list_global_chat_notes(conn, {**query_params, 'limit': 5000, 'page': 1})
    notes = res.get('notes', [])
    today_str = get_taipei_now().strftime('%Y%m%d_%H%M%S')
    
    fmt = fmt.lower().strip()
    if fmt == 'json':
        content = json.dumps({'notes': notes, 'exported_at': now_iso(), 'exported_by': actor}, ensure_ascii=False, indent=2)
        return content.encode('utf-8'), 'application/json; charset=utf-8', f'chat_notes_{today_str}.json'
    
    elif fmt == 'md' or fmt == 'markdown':
        lines = [f"# 對話記事本匯出報告 ({today_str})\n", f"匯出人員：{actor}\n總計篇數：{len(notes)}\n\n---\n"]
        for i, n in enumerate(notes, 1):
            tags_str = " ".join(f"`#{t}`" for t in n.get('tags', []))
            lines.append(f"## {i}. {n.get('title') or '未命名記事'}")
            lines.append(f"- **分類**：{n.get('category_name')} | **狀態**：{'已完成' if n.get('is_completed') else '進行中'} | **置頂**：{'是' if n.get('is_pinned') else '否'} | **鎖定**：{'是' if n.get('is_locked') else '否'}")
            if tags_str:
                lines.append(f"- **標籤**：{tags_str}")
            if n.get('due_date'):
                lines.append(f"- **到期日**：{n.get('due_date')}")
            lines.append(f"- **建立者**：{n.get('author')} ({n.get('created_at')})")
            lines.append(f"\n```\n{n.get('content')}\n```\n\n---\n")
        content = "\n".join(lines)
        return content.encode('utf-8'), 'text/markdown; charset=utf-8', f'chat_notes_{today_str}.md'
    
    else:  # CSV (Default, UTF-8 with BOM for Excel)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['記事編號', '聯絡對象ID', '標題', '業務分類', '標籤', '內文', '置頂', '鎖定', '完成狀態', '到期日', '建立人員', '建立時間', '最後修改時間'])
        for n in notes:
            writer.writerow([
                n.get('note_id', ''),
                n.get('recipient_id', ''),
                n.get('title', ''),
                n.get('category_name', ''),
                "; ".join(n.get('tags', [])),
                n.get('content', ''),
                '是' if n.get('is_pinned') else '否',
                '是' if n.get('is_locked') else '否',
                '已完成' if n.get('is_completed') else '進行中',
                n.get('due_date', ''),
                n.get('author', ''),
                n.get('created_at', ''),
                n.get('updated_at', '')
            ])
        csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
        return csv_bytes, 'text/csv; charset=utf-8', f'chat_notes_{today_str}.csv'


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
        'limit': limits.SAVED_FILTERS_PER_OA
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
        if count >= limits.SAVED_FILTERS_PER_OA:
            raise ValueError(f'此 OA 的自訂篩選條件已達上限（{limits.SAVED_FILTERS_PER_OA} 組），請刪除不用的篩選後再新增。')

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

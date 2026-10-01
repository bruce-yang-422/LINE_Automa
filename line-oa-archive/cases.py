"""Case Management core logic according to 案件管理流程規格.md"""

import sqlite3
import uuid
from datetime import datetime, timezone
import channels

ALLOWED_STATUSES = {'pending', 'processing', 'waiting', 'ready_to_close', 'closed'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'urgent'}
ALLOWED_WAITING_PARTIES = {'internal', 'case_subject', 'third_party'}

ALLOWED_TRANSITIONS = {
    'pending': {'processing'},
    'processing': {'waiting', 'ready_to_close'},
    'waiting': {'processing'},
    'ready_to_close': {'processing', 'closed'},
    'closed': set()
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_case_no(conn: sqlite3.Connection) -> str:
    date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    prefix = f"CASE-{date_str}-"
    row = conn.execute(
        "SELECT COUNT(*) FROM cases WHERE channel_id=current_channel() AND case_no LIKE ?",
        (prefix + "%",)
    ).fetchone()
    count = (row[0] if row else 0) + 1
    return f"{prefix}{count:04d}"


def create_case(conn: sqlite3.Connection, payload: dict, actor: str) -> dict:
    title = (payload.get('title') or '').strip()
    if not title or len(title) > 100:
        raise ValueError('請輸入 100 字以內的案件標題。')
    
    subject_id = (payload.get('case_subject_id') or payload.get('subject_id') or '').strip()
    if not subject_id:
        raise ValueError('請選擇案件對象。')
    
    contact = conn.execute(
        "SELECT recipient_id FROM recipients WHERE channel_id=current_channel() AND recipient_id=?",
        (subject_id,)
    ).fetchone()
    if not contact:
        raise ValueError('找不到所選的案件對象。')

    priority = payload.get('priority', 'medium').strip().lower()
    if priority not in ALLOWED_PRIORITIES:
        priority = 'medium'
        
    category = (payload.get('category') or 'general').strip()
    description = (payload.get('description') or '').strip()
    if len(description) > 2000:
        raise ValueError('案件說明請限制在 2000 字以內。')

    case_id = uuid.uuid4().hex
    case_no = generate_case_no(conn)
    ts = now_iso()
    
    conn.execute(
        """INSERT INTO cases (
            case_id, case_no, channel_id, title, category, status, priority,
            case_subject_id, description, resolution, waiting_party, waiting_reason,
            waiting_since, created_at, updated_at, closed_at
        ) VALUES (?, ?, current_channel(), ?, ?, 'pending', ?, ?, ?, '', '', '', '', ?, ?, '')""",
        (case_id, case_no, title, category, priority, subject_id, description, ts, ts)
    )
    
    add_activity(conn, case_id, 'create_case', actor, f"建立案件「{title}」（對象：{subject_id}）")
    return get_case(conn, case_id)


def update_case(conn: sqlite3.Connection, case_id: str, payload: dict, actor: str) -> dict:
    c = get_case(conn, case_id)
    if not c:
        raise ValueError('找不到該案件。')
    if c['status'] == 'closed':
        raise ValueError('已結案的案件無法修改內容。')

    title = payload.get('title')
    category = payload.get('category')
    priority = payload.get('priority')
    description = payload.get('description')

    updates = []
    params = []

    if title is not None:
        title = title.strip()
        if not title or len(title) > 100:
            raise ValueError('案件標題必須在 100 字以內。')
        updates.append("title=?")
        params.append(title)
        
    if category is not None:
        updates.append("category=?")
        params.append(category.strip())
        
    if priority is not None:
        p = priority.strip().lower()
        if p not in ALLOWED_PRIORITIES:
            raise ValueError('無效的優先級。')
        updates.append("priority=?")
        params.append(p)
        
    if description is not None:
        d = description.strip()
        if len(d) > 2000:
            raise ValueError('案件說明請限制在 2000 字以內。')
        updates.append("description=?")
        params.append(d)

    if updates:
        ts = now_iso()
        updates.append("updated_at=?")
        params.append(ts)
        params.append(case_id)
        conn.execute(
            f"UPDATE cases SET {', '.join(updates)} WHERE channel_id=current_channel() AND case_id=?",
            tuple(params)
        )
        add_activity(conn, case_id, 'note', actor, "更新案件基本資訊")

    return get_case(conn, case_id)


def transition_case(conn: sqlite3.Connection, case_id: str, to_status: str, payload: dict, actor: str) -> dict:
    c = get_case(conn, case_id)
    if not c:
        raise ValueError('找不到該案件。')
    
    current_status = c['status']
    to_status = to_status.strip().lower()
    
    if to_status not in ALLOWED_STATUSES:
        raise ValueError(f'無效的案件狀態：{to_status}')
    
    if to_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError(f'不允許從「{current_status}」轉換至「{to_status}」。')

    ts = now_iso()
    waiting_party = ''
    waiting_reason = ''
    waiting_since = ''
    resolution = c['resolution']
    closed_at = ''

    if to_status == 'waiting':
        waiting_party = (payload.get('waiting_party') or '').strip().lower()
        if waiting_party not in ALLOWED_WAITING_PARTIES:
            raise ValueError('進入等待狀態時必須指定等待對象（internal / case_subject / third_party）。')
        waiting_reason = (payload.get('waiting_reason') or '').strip()
        if not waiting_reason or len(waiting_reason) > 500:
            raise ValueError('請填寫 500 字以內的具體等待原因。')
        waiting_since = ts
        party_label = {'internal': '內部', 'case_subject': '案件對象', 'third_party': '第三方'}.get(waiting_party, waiting_party)
        note = f"狀態變更為「等待中」（等待{party_label}：{waiting_reason}）"

    elif to_status == 'processing':
        if current_status == 'waiting':
            note = f"取得回覆或完成等待事項，恢復為「處理中」"
        elif current_status == 'pending':
            note = "開始處理案件"
        else:
            note = "退回為「處理中」"

    elif to_status == 'ready_to_close':
        note = "主要處理完成，標記為「待結案」"

    elif to_status == 'closed':
        resolution = (payload.get('resolution') or '').strip()
        if not resolution or len(resolution) > 2000:
            raise ValueError('結案時必須填寫 2000 字以內的結案摘要（Resolution）。')
        closed_at = ts
        note = f"正式結案。結案摘要：{resolution}"
    else:
        note = f"狀態變更為 {to_status}"

    conn.execute(
        """UPDATE cases SET
            status=?, waiting_party=?, waiting_reason=?, waiting_since=?,
            resolution=?, updated_at=?, closed_at=?
        WHERE channel_id=current_channel() AND case_id=?""",
        (to_status, waiting_party, waiting_reason, waiting_since, resolution, ts, closed_at, case_id)
    )

    add_activity(conn, case_id, 'status_change', actor, note)
    return get_case(conn, case_id)


def add_activity(conn: sqlite3.Connection, case_id: str, activity_type: str, actor: str, content: str) -> dict:
    content = (content or '').strip()
    if not content or len(content) > 2000:
        raise ValueError('處理紀錄內容必須在 1 至 2000 字之間。')
    activity_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        """INSERT INTO case_activities (activity_id, case_id, channel_id, activity_type, actor, content, created_at)
        VALUES (?, ?, current_channel(), ?, ?, ?, ?)""",
        (activity_id, case_id, activity_type, actor, content, ts)
    )
    conn.execute(
        "UPDATE cases SET updated_at=? WHERE channel_id=current_channel() AND case_id=?",
        (ts, case_id)
    )
    return {'id': activity_id, 'case_id': case_id, 'activity_type': activity_type, 'actor': actor, 'content': content, 'created_at': ts}


def get_case(conn: sqlite3.Connection, case_id: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT c.*, r.display_name as subject_display_name, r.alias as subject_alias, r.kind as subject_kind,
                  r.contact_type as subject_contact_type, r.organization_name as subject_org_name
        FROM cases c
        LEFT JOIN recipients r ON c.case_subject_id=r.recipient_id AND r.channel_id=c.channel_id
        WHERE c.channel_id=current_channel() AND c.case_id=?""",
        (case_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    act_rows = conn.execute(
        "SELECT * FROM case_activities WHERE channel_id=current_channel() AND case_id=? ORDER BY created_at ASC",
        (case_id,)
    ).fetchall()
    d['activities'] = [dict(a) for a in act_rows]
    return d


def list_cases(conn: sqlite3.Connection, status: str = None, subject_id: str = None, query: str = None) -> list:
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT c.*, r.display_name as subject_display_name, r.alias as subject_alias, r.kind as subject_kind,
               r.contact_type as subject_contact_type, r.organization_name as subject_org_name
        FROM cases c
        LEFT JOIN recipients r ON c.case_subject_id=r.recipient_id AND r.channel_id=c.channel_id
        WHERE c.channel_id=current_channel()
    """
    params = []
    if status and status != 'all':
        sql += " AND c.status=?"
        params.append(status)
    if subject_id:
        sql += " AND c.case_subject_id=?"
        params.append(subject_id)
    if query:
        q = f"%{query.strip()}%"
        sql += " AND (c.case_no LIKE ? OR c.title LIKE ? OR c.description LIKE ? OR r.alias LIKE ? OR r.display_name LIKE ?)"
        params.extend([q, q, q, q, q])
    sql += " ORDER BY CASE c.status WHEN 'pending' THEN 1 WHEN 'processing' THEN 2 WHEN 'waiting' THEN 3 WHEN 'ready_to_close' THEN 4 ELSE 5 END, c.updated_at DESC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]

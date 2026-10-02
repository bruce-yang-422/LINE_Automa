"""Case Management core logic according to 案件管理流程規格.md"""

import csv
import io
import json
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
import channels
import limits

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

STATUS_LABELS = {
    'pending': '待處理',
    'processing': '處理中',
    'waiting': '等待中',
    'ready_to_close': '待結案',
    'closed': '已結案'
}

WAITING_PARTY_LABELS = {
    'internal': '內部',
    'case_subject': '案件對象',
    'third_party': '第三方'
}

PRIORITY_LABELS = {
    'low': '低',
    'medium': '中',
    'high': '高',
    'urgent': '緊急'
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_taipei_now() -> datetime:
    tz_taipei = timezone(timedelta(hours=8))
    return datetime.now(tz_taipei)


def get_or_init_prefix(conn: sqlite3.Connection, channel_id: str = None) -> str:
    if not channel_id:
        channel_id = channels.current_id()
    row = conn.execute(
        "SELECT case_prefix, basic_id, name FROM line_channels WHERE channel_id=?",
        (channel_id,)
    ).fetchone()
    if not row:
        return "CASE"
    
    current_prefix, basic_id, name = row[0], row[1], row[2]
    if current_prefix:
        return current_prefix.upper()
    
    # Derive default prefix: strip leading '@', take first 6 uppercase chars
    cand = re.sub(r'[^A-Za-z0-9]', '', (basic_id or '').lstrip('@')).upper()
    if len(cand) < 2:
        cand = re.sub(r'[^A-Za-z0-9]', '', name or '').upper()[:6]
    if len(cand) < 2:
        cand = channel_id[:6].upper()
    cand = cand[:6]

    # Check if candidate prefix is already taken by another OA
    taken = conn.execute(
        "SELECT channel_id FROM line_channels WHERE UPPER(case_prefix)=? AND channel_id<>?",
        (cand, channel_id)
    ).fetchone()
    if taken:
        # Append suffix or generate fallback
        for idx in range(1, 100):
            cand_alt = f"{cand[:4]}{idx:02d}"
            if not conn.execute("SELECT channel_id FROM line_channels WHERE UPPER(case_prefix)=? AND channel_id<>?", (cand_alt, channel_id)).fetchone():
                cand = cand_alt
                break

    conn.execute(
        "UPDATE line_channels SET case_prefix=? WHERE channel_id=?",
        (cand, channel_id)
    )
    return cand


def generate_case_no(conn: sqlite3.Connection, channel_id: str = None) -> str:
    if not channel_id:
        channel_id = channels.current_id()
    prefix = get_or_init_prefix(conn, channel_id)
    period = get_taipei_now().strftime('%Y%m')

    # Atomic sequence generation
    conn.execute(
        """INSERT INTO case_number_sequences (prefix, period, last_number)
        VALUES (?, ?, 1)
        ON CONFLICT(prefix, period) DO UPDATE SET last_number = case_number_sequences.last_number + 1""",
        (prefix, period)
    )
    row = conn.execute(
        "SELECT last_number FROM case_number_sequences WHERE prefix=? AND period=?",
        (prefix, period)
    ).fetchone()
    seq_num = row[0] if row else 1
    return f"{prefix}-{period}-{seq_num:04d}"


def update_case_prefix(conn: sqlite3.Connection, new_prefix: str, mode: str, actor: str) -> dict:
    channel_id = channels.current_id()
    new_prefix = (new_prefix or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{2,6}', new_prefix):
        raise ValueError('案件前綴必須為 2 至 6 個大寫英文字母或數字。')

    # Check uniqueness
    taken = conn.execute(
        "SELECT name FROM line_channels WHERE UPPER(case_prefix)=? AND channel_id<>?",
        (new_prefix, channel_id)
    ).fetchone()
    if taken:
        raise ValueError(f'此前綴已由「{taken[0]}」使用，請改用其他前綴。')

    old_prefix = get_or_init_prefix(conn, channel_id)
    affected_count = 0

    if mode == 'overwrite_existing' and old_prefix != new_prefix:
        cases_rows = conn.execute(
            "SELECT case_id, case_no FROM cases WHERE channel_id=?",
            (channel_id,)
        ).fetchall()
        now_str = now_iso()
        for cid, old_no in cases_rows:
            # Parse old_no (e.g. 216RUX-202610-0042)
            parts = old_no.split('-')
            if len(parts) >= 3:
                period_part = parts[1]
                seq_part = parts[2]
            else:
                period_part = get_taipei_now().strftime('%Y%m')
                seq_part = "0001"
            new_no = f"{new_prefix}-{period_part}-{seq_part}"
            conn.execute(
                "INSERT OR REPLACE INTO case_number_aliases (case_id, old_case_no, replaced_at) VALUES (?, ?, ?)",
                (cid, old_no, now_str)
            )
            conn.execute(
                "UPDATE cases SET case_no=? WHERE case_id=?",
                (new_no, cid)
            )
            affected_count += 1

            # Sync sequence table
            try:
                seq_int = int(seq_part)
                conn.execute(
                    """INSERT INTO case_number_sequences (prefix, period, last_number)
                    VALUES (?, ?, ?)
                    ON CONFLICT(prefix, period) DO UPDATE SET last_number = MAX(case_number_sequences.last_number, excluded.last_number)""",
                    (new_prefix, period_part, seq_int)
                )
            except ValueError:
                pass

    conn.execute(
        "UPDATE line_channels SET case_prefix=? WHERE channel_id=?",
        (new_prefix, channel_id)
    )

    import reports
    reports.audit(conn, actor, "cases.update_prefix", channel_id,
                  f"變更案件編號前綴：{old_prefix} -> {new_prefix}（模式：{mode}，影響 {affected_count} 筆）")

    return {
        'old_prefix': old_prefix,
        'new_prefix': new_prefix,
        'mode': mode,
        'affected_count': affected_count
    }


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
        
    category = (payload.get('category') or '一般').strip()
    description = (payload.get('description') or '').strip()
    if len(description) > 2000:
        raise ValueError('案件說明請限制在 2000 字以內。')

    ref_no = (payload.get('ref_no') or payload.get('reference_no') or '').strip()[:60]
    continued_from_id = (payload.get('continued_from_id') or '').strip()
    source_note_id = (payload.get('source_note_id') or '').strip()
    source_message_id = (payload.get('source_message_id') or '').strip()
    source_snapshot = (payload.get('source_snapshot') or '').strip()
    due_date = (payload.get('due_date') or '').strip()

    if continued_from_id:
        parent = conn.execute(
            "SELECT case_no, title FROM cases WHERE channel_id=current_channel() AND case_id=?",
            (continued_from_id,)
        ).fetchone()
        if not parent:
            raise ValueError('找不到欲延續的前案。')

    case_id = uuid.uuid4().hex
    case_no = generate_case_no(conn)
    ts = now_iso()
    
    conn.execute(
        """INSERT INTO cases (
            case_id, case_no, channel_id, title, category, status, priority,
            case_subject_id, description, resolution, waiting_party, waiting_reason,
            waiting_since, ref_no, continued_from_id, is_locked, due_date, source_note_id,
            created_at, updated_at, closed_at
        ) VALUES (?, ?, current_channel(), ?, ?, 'pending', ?, ?, ?, '', '', '', '', ?, ?, 0, ?, ?, ?, ?, '')""",
        (case_id, case_no, title, category, priority, subject_id, description, ref_no, continued_from_id, due_date, source_note_id, ts, ts)
    )
    
    activity_note = f"建立案件「{title}」（編號：{case_no}）"
    if continued_from_id:
        parent_no = parent[0]
        activity_note += f"，延續自前案 {parent_no}"
    
    add_activity(conn, case_id, 'create_case', actor, activity_note,
                 source_message_id=source_message_id, source_snapshot=source_snapshot)
    return get_case(conn, case_id)


def update_case(conn: sqlite3.Connection, case_id: str, payload: dict, actor: str) -> dict:
    c = get_case(conn, case_id)
    if not c:
        raise ValueError('找不到該案件。')
    if c['is_locked']:
        raise ValueError('此案件已鎖定，請先按 🔒 解鎖後再進行編輯。')
    if c['status'] == 'closed':
        raise ValueError('已結案的案件無法修改內容。')

    title = payload.get('title')
    category = payload.get('category')
    priority = payload.get('priority')
    description = payload.get('description')
    ref_no = payload.get('ref_no')
    due_date = payload.get('due_date')

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

    if ref_no is not None:
        updates.append("ref_no=?")
        params.append(ref_no.strip()[:60])

    if due_date is not None:
        updates.append("due_date=?")
        params.append(due_date.strip())

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


def toggle_case_lock(conn: sqlite3.Connection, case_id: str, actor: str) -> dict:
    c = get_case(conn, case_id)
    if not c:
        raise ValueError('找不到該案件。')
    new_locked = 0 if c['is_locked'] else 1
    ts = now_iso()
    conn.execute(
        "UPDATE cases SET is_locked=?, updated_at=? WHERE channel_id=current_channel() AND case_id=?",
        (new_locked, ts, case_id)
    )
    action_str = "鎖定案件" if new_locked else "解除案件鎖定"
    add_activity(conn, case_id, 'internal_action', actor, action_str)
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

    if c['is_locked'] and to_status == 'closed':
        raise ValueError('此案件已鎖定，請先解除鎖定後再結案。')

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
        party_label = WAITING_PARTY_LABELS.get(waiting_party, waiting_party)
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


def add_activity(conn: sqlite3.Connection, case_id: str, activity_type: str, actor: str, content: str,
                 source_message_id: str = '', source_snapshot: str = '') -> dict:
    content = (content or '').strip()
    if not content or len(content) > 2000:
        raise ValueError('處理紀錄內容必須在 1 至 2000 字之間。')
    activity_id = uuid.uuid4().hex
    ts = now_iso()
    conn.execute(
        """INSERT INTO case_activities (
            activity_id, case_id, channel_id, activity_type, actor, content,
            source_message_id, source_snapshot, created_at
        ) VALUES (?, ?, current_channel(), ?, ?, ?, ?, ?, ?)""",
        (activity_id, case_id, activity_type, actor, content, source_message_id, source_snapshot, ts)
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
    
    # Overdue check
    today_str = get_taipei_now().strftime('%Y-%m-%d')
    d['is_overdue'] = bool(d.get('due_date') and d['due_date'] < today_str and d['status'] != 'closed')
    
    # Fetch aliases
    alias_rows = conn.execute(
        "SELECT old_case_no, replaced_at FROM case_number_aliases WHERE case_id=? ORDER BY replaced_at DESC",
        (case_id,)
    ).fetchall()
    d['aliases'] = [dict(a) for a in alias_rows]

    # Fetch parent case info if continued
    if d.get('continued_from_id'):
        parent = conn.execute(
            "SELECT case_id, case_no, title, status FROM cases WHERE case_id=?",
            (d['continued_from_id'],)
        ).fetchone()
        d['continued_from'] = dict(parent) if parent else None
    else:
        d['continued_from'] = None

    # Fetch subsequent cases
    sub_rows = conn.execute(
        "SELECT case_id, case_no, title, status, created_at FROM cases WHERE continued_from_id=? ORDER BY created_at ASC",
        (case_id,)
    ).fetchall()
    d['subsequent_cases'] = [dict(s) for s in sub_rows]

    # Fetch activities
    act_rows = conn.execute(
        "SELECT * FROM case_activities WHERE channel_id=current_channel() AND case_id=? ORDER BY created_at ASC",
        (case_id,)
    ).fetchall()
    d['activities'] = [dict(a) for a in act_rows]
    return d


def list_cases(conn: sqlite3.Connection, status: str = None, subject_id: str = None, query: str = None,
               category: str = None, start_date: str = None, end_date: str = None, limit: int = limits.CASE_EXPORT_MAX) -> list:
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT c.*, r.display_name as subject_display_name, r.alias as subject_alias, r.kind as subject_kind,
               r.contact_type as subject_contact_type, r.organization_name as subject_org_name,
               (SELECT COUNT(*) FROM case_activities ca WHERE ca.case_id=c.case_id) as activity_count,
               (SELECT MAX(ca.created_at) FROM case_activities ca WHERE ca.case_id=c.case_id) as last_activity_at
        FROM cases c
        LEFT JOIN recipients r ON c.case_subject_id=r.recipient_id AND r.channel_id=c.channel_id
        WHERE c.channel_id=current_channel()
    """
    params = []
    if status == 'overdue':
        today_str = get_taipei_now().strftime('%Y-%m-%d')
        sql += " AND c.due_date <> '' AND c.due_date < ? AND c.status <> 'closed'"
        params.append(today_str)
    elif status and status != 'all':
        sql += " AND c.status=?"
        params.append(status)
    if category and category != 'all':
        sql += " AND c.category=?"
        params.append(category)
    if subject_id:
        sql += " AND c.case_subject_id=?"
        params.append(subject_id)
    if start_date:
        sql += " AND c.created_at >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND c.created_at <= ?"
        params.append(end_date + "T23:59:59.999Z")
    if query:
        q = f"%{query.strip()}%"
        sql += """ AND (
            c.case_no LIKE ? OR c.title LIKE ? OR c.description LIKE ? OR c.ref_no LIKE ?
            OR r.alias LIKE ? OR r.display_name LIKE ?
            OR c.case_id IN (SELECT case_id FROM case_number_aliases WHERE old_case_no LIKE ?)
            OR c.case_id IN (SELECT case_id FROM case_activities WHERE content LIKE ?)
        )"""
        params.extend([q, q, q, q, q, q, q, q])
    
    sql += """ ORDER BY 
        CASE c.status WHEN 'pending' THEN 1 WHEN 'processing' THEN 2 WHEN 'waiting' THEN 3 WHEN 'ready_to_close' THEN 4 ELSE 5 END,
        c.updated_at DESC
        LIMIT ?"""
    params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    
    today_str = get_taipei_now().strftime('%Y-%m-%d')
    res = []
    for r in rows:
        d = dict(r)
        d['is_overdue'] = bool(d.get('due_date') and d['due_date'] < today_str and d['status'] != 'closed')
        res.append(d)
    return res


def notify_case_subject(conn: sqlite3.Connection, case_id: str, message_text: str, actor: str) -> dict:
    """Send progress notification message to case subject and record activity (Section 17.6)."""
    c = get_case(conn, case_id)
    if not c:
        raise ValueError('找不到指定案件。')
    
    message_text = (message_text or '').strip()
    if not message_text or len(message_text) > 1000:
        raise ValueError('通知訊息內容請填寫 1 至 1,000 字以內。')

    subject_id = c['case_subject_id']
    if not subject_id:
        raise ValueError('此案件沒有關聯的對象。')

    # Send push notification via Line OA
    import admin_server
    token = channels.access_token()
    if not token:
        raise ValueError('OA 連線尚未設定，無法傳送訊息。')

    retry_key = str(uuid.uuid4())
    admin_server.send_push(token, subject_id, '', retry_key=retry_key, text=message_text)

    # Record message to line_messages
    mid = uuid.uuid4().hex
    now = now_iso()
    channel_id = channels.current_id()
    conn.execute(
        """INSERT INTO line_messages (
            channel_id, message_id, conversation_type, conversation_id, sender_user_id,
            message_type, text_content, sent_at, received_at, direction, sent_by, send_method, delivery_status
        ) VALUES (?, ?, 'user', ?, ?, 'text', ?, ?, ?, 'outbound', ?, 'push', 'delivered')""",
        (channel_id, mid, subject_id, subject_id, message_text, now, now, actor)
    )

    # Record activity in case
    add_activity(conn, case_id, 'notify', actor, f"已傳送進度通知給對象：\n{message_text}")

    import reports
    reports.audit(conn, actor, 'case.notify_subject', case_id, f"傳送案件「{c['title']}」進度通知給對象")

    return get_case(conn, case_id)



# ----------------- Export CSV / XLSX -----------------

def escape_csv_formula(val: str) -> str:
    """Prepend single quote if value begins with =, +, -, @ to prevent spreadsheet formula injection."""
    if isinstance(val, str) and len(val) > 0 and val[0] in ('=', '+', '-', '@'):
        return "'" + val
    return val


def format_iso_taipei(iso_str: str) -> str:
    if not iso_str:
        return ''
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        tz_taipei = timezone(timedelta(hours=8))
        return dt.astimezone(tz_taipei).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso_str[:16].replace('T', ' ')


def generate_cases_csv(cases_data: list, include_contacts: bool = False) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    
    headers = [
        "案件編號", "原編號", "標題", "類別", "優先級", "狀態",
        "等待對象", "等待原因", "等待開始時間",
        "案件對象", "聯絡對象類型", "對方組織",
        "參考編號", "延續自", "到期日", "建立時間", "最後更新時間", "結案時間",
        "結案摘要", "處理紀錄筆數", "最後處理時間"
    ]
    if include_contacts:
        headers.extend(["電話", "Email", "地址"])
    writer.writerow(headers)

    for c in cases_data:
        old_no = ", ".join([a['old_case_no'] for a in c.get('aliases', [])])
        subject_name = c.get('subject_alias') or c.get('subject_display_name') or c.get('case_subject_id', '')
        row = [
            escape_csv_formula(c.get('case_no', '')),
            escape_csv_formula(old_no),
            escape_csv_formula(c.get('title', '')),
            escape_csv_formula(c.get('category', '')),
            PRIORITY_LABELS.get(c.get('priority', ''), c.get('priority', '')),
            STATUS_LABELS.get(c.get('status', ''), c.get('status', '')),
            WAITING_PARTY_LABELS.get(c.get('waiting_party', ''), ''),
            escape_csv_formula(c.get('waiting_reason', '')),
            format_iso_taipei(c.get('waiting_since', '')),
            escape_csv_formula(subject_name),
            c.get('subject_contact_type', ''),
            escape_csv_formula(c.get('subject_org_name', '')),
            escape_csv_formula(c.get('ref_no', '')),
            escape_csv_formula(c.get('continued_from', {}).get('case_no', '') if c.get('continued_from') else ''),
            c.get('due_date', ''),
            format_iso_taipei(c.get('created_at', '')),
            format_iso_taipei(c.get('updated_at', '')),
            format_iso_taipei(c.get('closed_at', '')),
            escape_csv_formula(c.get('resolution', '')),
            c.get('activity_count', len(c.get('activities', []))),
            format_iso_taipei(c.get('last_activity_at', ''))
        ]
        if include_contacts:
            row.extend([
                escape_csv_formula(c.get('phone', '')),
                escape_csv_formula(c.get('email', '')),
                escape_csv_formula(c.get('address', ''))
            ])
        writer.writerow(row)

    return '\ufeff' + output.getvalue()


def generate_activities_csv(cases_data: list) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(["案件編號", "紀錄時間", "紀錄類型", "操作者", "紀錄內容", "訊息快照"])

    for c in cases_data:
        case_no = c.get('case_no', '')
        for a in c.get('activities', []):
            writer.writerow([
                escape_csv_formula(case_no),
                format_iso_taipei(a.get('created_at', '')),
                a.get('activity_type', ''),
                escape_csv_formula(a.get('actor', '')),
                escape_csv_formula(a.get('content', '')),
                escape_csv_formula(a.get('source_snapshot', ''))
            ])
    return '\ufeff' + output.getvalue()


def build_pure_xlsx(sheets: dict[str, list[list[str]]]) -> bytes:
    """Build a compliant Office Open XML (.xlsx) workbook using only Python standard library."""
    import xml.sax.saxutils as saxutils

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                         '<Default Extension="xml" ContentType="application/xml"/>',
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
                         '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        for idx in range(1, len(sheets) + 1):
            content_types.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        content_types.append('</Types>')
        zf.writestr('[Content_Types].xml', ''.join(content_types))

        # _rels/.rels
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>')
        zf.writestr('_rels/.rels', rels)

        # xl/_rels/workbook.xml.rels
        wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
                   '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
        for idx in range(1, len(sheets) + 1):
            wb_rels.append(f'<Relationship Id="rIdSheet{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')
        wb_rels.append('</Relationships>')
        zf.writestr('xl/_rels/workbook.xml.rels', ''.join(wb_rels))

        # xl/styles.xml
        styles_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                      '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                      '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                      '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                      '</styleSheet>')
        zf.writestr('xl/styles.xml', styles_xml)

        # xl/workbook.xml
        wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
              '<sheets>']
        for idx, sheet_name in enumerate(sheets.keys(), start=1):
            safe_name = saxutils.escape(sheet_name)
            wb.append(f'<sheet name="{safe_name}" sheetId="{idx}" r:id="rIdSheet{idx}"/>')
        wb.append('</sheets></workbook>')
        zf.writestr('xl/workbook.xml', ''.join(wb))

        # Worksheets
        def col_letter(c_idx: int) -> str:
            res = ""
            while c_idx > 0:
                c_idx, rem = divmod(c_idx - 1, 26)
                res = chr(65 + rem) + res
            return res

        for idx, (sheet_name, rows) in enumerate(sheets.items(), start=1):
            sheet_xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                         '<sheetData>']
            for r_idx, row in enumerate(rows, start=1):
                sheet_xml.append(f'<row r="{r_idx}">')
                for c_idx, cell_val in enumerate(row, start=1):
                    ref = f"{col_letter(c_idx)}{r_idx}"
                    val_str = str(cell_val if cell_val is not None else '')
                    safe_val = saxutils.escape(escape_csv_formula(val_str))
                    sheet_xml.append(f'<c r="{ref}" t="inlineStr"><is><t>{safe_val}</t></is></c>')
                sheet_xml.append('</row>')
            sheet_xml.append('</sheetData></worksheet>')
            zf.writestr(f'xl/worksheets/sheet{idx}.xml', ''.join(sheet_xml))

    return buf.getvalue()


def export_cases(conn: sqlite3.Connection, filters: dict, fmt: str, include_activities: bool,
                 include_contacts: bool, actor: str) -> tuple[bytes, str, str]:
    """Returns (content_bytes, content_type, filename). Max 5,000 cases."""
    cases_data = list_cases(
        conn,
        status=filters.get('status'),
        category=filters.get('category'),
        subject_id=filters.get('subject_id'),
        query=filters.get('query') or filters.get('search'),
        start_date=filters.get('start_date'),
        end_date=filters.get('end_date'),
        limit=limits.CASE_EXPORT_MAX
    )
    
    # Populate activities for all returned cases if needed
    if include_activities:
        for c in cases_data:
            act_rows = conn.execute(
                "SELECT * FROM case_activities WHERE channel_id=current_channel() AND case_id=? ORDER BY created_at ASC",
                (c['case_id'],)
            ).fetchall()
            c['activities'] = [dict(a) for a in act_rows]

    channel_prefix = get_or_init_prefix(conn)
    date_str = get_taipei_now().strftime('%Y%m%d')

    import reports
    reports.audit(
        conn, actor, "cases.export", f"{channel_prefix}_{date_str}",
        f"匯出案件：格式 {fmt.upper()}，筆數 {len(cases_data)} 筆，含處理紀錄：{include_activities}，含聯絡資訊：{include_contacts}"
    )

    if fmt == 'xlsx':
        sheets = {}
        # Sheet 1: 案件清單
        s1_headers = [
            "案件編號", "原編號", "標題", "類別", "優先級", "狀態",
            "等待對象", "等待原因", "等待開始時間",
            "案件對象", "聯絡對象類型", "對方組織",
            "參考編號", "延續自", "到期日", "建立時間", "最後更新時間", "結案時間",
            "結案摘要", "處理紀錄筆數", "最後處理時間"
        ]
        if include_contacts:
            s1_headers.extend(["電話", "Email", "地址"])
        
        s1_rows = [s1_headers]
        for c in cases_data:
            old_no = ", ".join([a['old_case_no'] for a in c.get('aliases', [])])
            subject_name = c.get('subject_alias') or c.get('subject_display_name') or c.get('case_subject_id', '')
            r = [
                c.get('case_no', ''),
                old_no,
                c.get('title', ''),
                c.get('category', ''),
                PRIORITY_LABELS.get(c.get('priority', ''), c.get('priority', '')),
                STATUS_LABELS.get(c.get('status', ''), c.get('status', '')),
                WAITING_PARTY_LABELS.get(c.get('waiting_party', ''), ''),
                c.get('waiting_reason', ''),
                format_iso_taipei(c.get('waiting_since', '')),
                subject_name,
                c.get('subject_contact_type', ''),
                c.get('subject_org_name', ''),
                c.get('ref_no', ''),
                c.get('continued_from', {}).get('case_no', '') if c.get('continued_from') else '',
                c.get('due_date', ''),
                format_iso_taipei(c.get('created_at', '')),
                format_iso_taipei(c.get('updated_at', '')),
                format_iso_taipei(c.get('closed_at', '')),
                c.get('resolution', ''),
                c.get('activity_count', len(c.get('activities', []))),
                format_iso_taipei(c.get('last_activity_at', ''))
            ]
            if include_contacts:
                r.extend([c.get('phone', ''), c.get('email', ''), c.get('address', '')])
            s1_rows.append(r)
        sheets["案件清單"] = s1_rows

        if include_activities:
            s2_headers = ["案件編號", "紀錄時間", "紀錄類型", "操作者", "紀錄內容", "訊息快照"]
            s2_rows = [s2_headers]
            for c in cases_data:
                case_no = c.get('case_no', '')
                for a in c.get('activities', []):
                    s2_rows.append([
                        case_no,
                        format_iso_taipei(a.get('created_at', '')),
                        a.get('activity_type', ''),
                        a.get('actor', ''),
                        a.get('content', ''),
                        a.get('source_snapshot', '')
                    ])
            sheets["處理紀錄"] = s2_rows

        data = build_pure_xlsx(sheets)
        filename = f"cases_{channel_prefix}_{date_str}.xlsx"
        return data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename

    else:
        # CSV format
        cases_csv = generate_cases_csv(cases_data, include_contacts=include_contacts)
        if include_activities:
            # Package as ZIP
            act_csv = generate_activities_csv(cases_data)
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"cases_{channel_prefix}_{date_str}.csv", cases_csv.encode('utf-8'))
                zf.writestr(f"activities_{channel_prefix}_{date_str}.csv", act_csv.encode('utf-8'))
            filename = f"cases_{channel_prefix}_{date_str}.zip"
            return zip_buf.getvalue(), 'application/zip', filename
        else:
            filename = f"cases_{channel_prefix}_{date_str}.csv"
            return cases_csv.encode('utf-8'), 'text/csv; charset=utf-8', filename

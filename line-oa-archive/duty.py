"""Organization-scoped duty permissions, setup, and versioned manual rosters."""
import app
import reports
import csv
import io
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import limits

TAIPEI = timezone(timedelta(hours=8))


def today():
    return datetime.now(TAIPEI).date()


def now():
    return datetime.now(timezone.utc).isoformat()


def checked_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('請填寫 YYYY-MM-DD 格式的生效日。')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('日期不正確。') from None


def text(payload, key, *, required=False, maximum=None):
    value = payload.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > (maximum or limits.DUTY_NAME_MAX):
        raise ValueError(f'{key} 格式或長度不正確。')
    if required and not value.strip():
        raise ValueError(f'請填寫 {key}。')
    return value.strip()


def flag(payload, key, default=False):
    value = payload.get(key, default)
    if type(value) is not bool:
        raise ValueError(f'{key} 必須為布林值。')
    return int(value)


def managed_org(user, payload=None, *, preview=False, read=False):
    return authorize(user, 'edit', organization_id=(payload or {}).get('org_id'), preview=False if read else preview)


def notification_oa(org_id):
    with app.database_connection() as conn:
        row=conn.execute('SELECT channel_id FROM duty_notice_settings WHERE org_id=?',(org_id,)).fetchone()
    return row[0] if row and row[0] else None


def scoped(conn, table, key, value, org_id):
    conn.row_factory = sqlite3.Row
    row = conn.execute(f'SELECT * FROM {table} WHERE {key}=? AND org_id=?', (value, org_id)).fetchone()
    if not row:
        raise ValueError('找不到本組織的資料。')
    return dict(row)


def reference_impacts(conn, org_id, kind, resource_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='duty_rosters'").fetchone():
        return []
    rows = conn.execute('''SELECT r.roster_id,r.name,r.status,r.date_from,r.date_to,a.task_id,a.person_ids,a.assignment_id
                           FROM duty_rosters r JOIN duty_assignments a ON a.roster_id=r.roster_id
                           WHERE r.org_id=? AND r.status IN ('draft','published','replaced')''', (org_id,)).fetchall()
    results = []
    for row in rows:
        row = dict(row) if isinstance(row, sqlite3.Row) else dict(zip(('roster_id','name','status','date_from','date_to','task_id','person_ids','assignment_id'), row))
        matches = row['task_id'] == resource_id if kind == 'task' else resource_id in json.loads(row['person_ids'])
        if kind == 'person' and not matches:
            matches = bool(conn.execute('SELECT 1 FROM duty_substitutions WHERE assignment_id=? AND (original_person_id=? OR substitute_person_id=?)', (row['assignment_id'], resource_id, resource_id)).fetchone())
        if matches:
            result = {k: row[k] for k in ('roster_id','name','status','date_from','date_to')}
            if result not in results:
                results.append(result)
    return results


def confirm_impacts(conn, org_id, kind, resource_id, payload):
    impacts = reference_impacts(conn, org_id, kind, resource_id)
    if impacts:
        checked_date(payload.get('effective_from'))
        if payload.get('confirm_impacts') is not True or payload.get('impacts') != impacts:
            raise ValueError('受影響項目已變更，請重新預覽並確認。')
        text(payload, 'reason', required=True, maximum=limits.DUTY_CONTENT_MAX)
    return impacts


def list_people(user, *, preview=False):
    org_id = managed_org(user, read=True)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        people = [dict(r) for r in conn.execute('SELECT * FROM duty_people WHERE org_id=? AND deleted=0 ORDER BY full_name,person_id', (org_id,))]
        positions = [dict(r) for r in conn.execute('SELECT * FROM duty_positions WHERE org_id=? ORDER BY sort_order,position_id', (org_id,))]
        for person in people:
            person['memberships'] = [dict(r) for r in conn.execute('''SELECT m.*,p.code,p.sort_order FROM duty_position_members m
                JOIN duty_positions p ON p.position_id=m.position_id WHERE m.person_id=? ORDER BY m.effective_from''', (person['person_id'],))]
            person['bindings'] = [dict(r) for r in conn.execute('SELECT * FROM duty_person_bindings WHERE person_id=? AND org_id=?', (person['person_id'], org_id))]
            person['impacts'] = reference_impacts(conn, org_id, 'person', person['person_id'])
            person['removal'] = 'deactivate' if person['impacts'] or len(person['memberships']) > 1 else 'delete'
    return {'people': people, 'positions': positions, 'notification_oa': notification_oa(org_id)}


def save_person(user, payload, *, preview=False, conn=None):
    org_id = managed_org(user, payload, preview=preview)
    name = text(payload, 'full_name', required=True)
    if name.upper() == 'X':
        raise ValueError('X 是待補位標記，不可新增為員工。')
    values = [name, text(payload, 'display_name'), text(payload, 'department'), text(payload, 'floor'), flag(payload, 'active', True)]
    effective = checked_date(payload.get('effective_from')).isoformat()
    if conn is None:
        with app.database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            return save_person(user, payload, preview=preview, conn=connection)
    person_id = payload.get('person_id') or uuid4().hex
    existing = scoped(conn, 'duty_people', 'person_id', person_id, org_id) if payload.get('person_id') else None
    if existing:
        if existing['deleted']:
            raise ValueError('請先復原已刪除的人員。')
        confirm_impacts(conn, org_id, 'person', person_id, payload)
        if payload.get('expected_updated_at') != existing['updated_at']:
            raise ValueError('人員資料已被修改，請重新載入。')
        conn.execute('UPDATE duty_people SET full_name=?,display_name=?,department=?,floor=?,active=?,updated_at=? WHERE person_id=?', (*values, now(), person_id))
    else:
        if conn.execute('SELECT COUNT(*) FROM duty_people WHERE org_id=? AND deleted=0', (org_id,)).fetchone()[0] >= limits.DUTY_PEOPLE_PER_ORG:
            raise ValueError('值日人員已達上限。')
        conn.execute('INSERT INTO duty_people VALUES (?,?,?,?,?,?,?,0,?,?)', (person_id, org_id, *values, now(), now()))
    # Existing position is explicitly selected for replacement; code is not an identity.
    position_id = payload.get('position_id')
    if position_id:
        scoped(conn, 'duty_positions', 'position_id', position_id, org_id)
    elif not existing:
        code = text(payload, 'code') or str(conn.execute('SELECT COUNT(*)+1 FROM duty_positions WHERE org_id=?', (org_id,)).fetchone()[0])
        if conn.execute('SELECT 1 FROM duty_positions WHERE org_id=? AND code=?', (org_id, code)).fetchone():
            raise ValueError('代號已存在，請選擇既有空缺位置補位。')
        order = conn.execute('SELECT COALESCE(MAX(sort_order),0)+1 FROM duty_positions WHERE org_id=?', (org_id,)).fetchone()[0]
        if payload.get('after_position_id'):
            after = scoped(conn, 'duty_positions', 'position_id', payload['after_position_id'], org_id)
            order = after['sort_order'] + 1
            conn.execute('UPDATE duty_positions SET sort_order=sort_order+1 WHERE org_id=? AND sort_order>=?', (org_id, order))
        position_id = uuid4().hex
        conn.execute('INSERT INTO duty_positions VALUES (?,?,?,?,1)', (position_id, org_id, code, order))
    if position_id:
        prior = conn.execute('SELECT person_id,effective_from FROM duty_position_members WHERE position_id=? AND (effective_to IS NULL OR effective_to>=?) ORDER BY effective_from DESC LIMIT 1', (position_id, effective)).fetchone()
        if prior and prior[0] != person_id:
            if prior[1] >= effective:
                raise ValueError('補位生效日不得覆寫既有或未來的接任紀錄。')
            prior_person = scoped(conn, 'duty_people', 'person_id', prior[0], org_id)
            if prior_person['active'] and not prior_person['deleted']:
                raise ValueError('此位置仍有人在職，請先處理離職或代班。')
            conn.execute('UPDATE duty_position_members SET effective_to=? WHERE position_id=? AND effective_to IS NULL', ((date.fromisoformat(effective)-timedelta(days=1)).isoformat(), position_id))
        if not prior or prior[0] != person_id:
            if conn.execute('SELECT 1 FROM duty_position_members WHERE person_id=? AND (effective_to IS NULL OR effective_to>=?)', (person_id, effective)).fetchone():
                raise ValueError('此人員已有輪替位置，請先結束原接任關係。')
            conn.execute('INSERT INTO duty_position_members VALUES (?,?,?,?,NULL)', (uuid4().hex, position_id, person_id, effective))
        conn.execute('UPDATE duty_positions SET vacant=0 WHERE position_id=?', (position_id,))
    reports.audit(conn, user['email'], 'duty.person.save', person_id, name, org_id)
    return {'person_id': person_id}


def bulk_people(user, payload, *, preview=False):
    managed_org(user, payload, preview=preview)
    raw = text(payload, 'text', required=True, maximum=limits.DUTY_CONTENT_MAX * limits.DUTY_BULK_PEOPLE)
    rows = list(csv.reader(io.StringIO(raw), delimiter='\t' if '\t' in raw else ','))
    if len(rows) > limits.DUTY_BULK_PEOPLE:
        raise ValueError('批次新增超過上限。')
    preview_rows = []
    for index, row in enumerate(rows, 1):
        if not row or not any(v.strip() for v in row):
            continue
        if row[0].strip() in ('全名', '姓名'):
            continue
        if len(row) > 4:
            raise ValueError(f'第 {index} 列應為全名、顯示名稱、部門、樓層。')
        data = dict(zip(('full_name', 'display_name', 'department', 'floor'), row + ['']*(4-len(row))))
        for key in data:
            data[key] = text(data, key, required=key == 'full_name')
        preview_rows.append({**data, 'skip': data['full_name'].upper() == 'X'})
    if not preview_rows:
        raise ValueError('沒有可預覽的人員。')
    if payload.get('confirm') is not True:
        return {'rows': preview_rows}
    checked_date(payload.get('effective_from'))
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for row in preview_rows:
            if not row['skip']:
                save_person(user, {**row, 'effective_from': payload['effective_from']}, conn=conn)
    return {'count': sum(not r['skip'] for r in preview_rows)}


def remove_resource(user, payload, *, preview=False):
    org_id = managed_org(user, payload, preview=preview)
    kind = payload.get('kind')
    if kind not in ('person', 'task'):
        raise ValueError('資料類型不正確。')
    mode = payload.get('mode', 'default')
    if mode not in ('default', 'archive') or (mode == 'archive' and kind != 'task'):
        raise ValueError('移除方式不正確。')
    table, key = ('duty_people', 'person_id') if kind == 'person' else ('duty_tasks', 'task_id')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        resource = scoped(conn, table, key, payload.get('id'), org_id)
        impacts = confirm_impacts(conn, org_id, kind, payload['id'], payload)
        if payload.get('restore') is True:
            if kind == 'person':
                memberships = conn.execute('SELECT position_id FROM duty_position_members WHERE person_id=? AND effective_to IS NULL', (payload['id'],)).fetchall()
                for membership in memberships:
                    occupied = conn.execute('''SELECT 1 FROM duty_position_members m JOIN duty_people p ON p.person_id=m.person_id
                        WHERE m.position_id=? AND m.person_id<>? AND m.effective_to IS NULL AND p.active=1 AND p.deleted=0''', (membership[0], payload['id'])).fetchone()
                    if occupied:
                        raise ValueError('原輪替位置已有接任人員，請先調整位置再復原。')
                    conn.execute('UPDATE duty_positions SET vacant=0 WHERE position_id=?', (membership[0],))
            conn.execute(f'UPDATE {table} SET deleted=0,active=1,updated_at=? WHERE {key}=?', (now(), payload['id']))
        else:
            historical = kind == 'person' and conn.execute('SELECT COUNT(*) FROM duty_position_members WHERE person_id=?', (payload['id'],)).fetchone()[0] > 1
            deleted = 1 if mode == 'archive' else (0 if impacts or historical else 1)
            conn.execute(f'UPDATE {table} SET active=0,deleted=?,updated_at=? WHERE {key}=?', (deleted, now(), payload['id']))
            if kind == 'task' and mode == 'archive':
                drafts = conn.execute('''SELECT a.assignment_id,a.roster_id FROM duty_assignments a
                    JOIN duty_rosters r ON r.roster_id=a.roster_id
                    WHERE a.task_id=? AND r.org_id=? AND r.status='draft' ''', (payload['id'], org_id)).fetchall()
                for assignment in drafts:
                    conn.execute('DELETE FROM duty_substitutions WHERE assignment_id=?', (assignment['assignment_id'],))
                    conn.execute('DELETE FROM duty_assignments WHERE assignment_id=?', (assignment['assignment_id'],))
                    conn.execute('UPDATE duty_rosters SET updated_at=? WHERE roster_id=?', (now(), assignment['roster_id']))
            if kind == 'person':
                conn.execute('UPDATE duty_positions SET vacant=1 WHERE position_id IN (SELECT position_id FROM duty_position_members WHERE person_id=? AND effective_to IS NULL)', (payload['id'],))
                conn.execute('DELETE FROM duty_person_bindings WHERE person_id=? AND org_id=?', (payload['id'], org_id))
        detail = '復原' if payload.get('restore') else ('移除工作（草稿同步移除，歷史保留）' if mode == 'archive' else '停用' if not deleted else '刪除（可復原）')
        reports.audit(conn, user['email'], 'duty.'+kind+'.remove', payload['id'], detail, org_id)
    return {'ok': True}


def validated_task(payload):
    data = {'name': text(payload, 'name', required=True),
            'description': text(payload, 'description', maximum=limits.DUTY_CONTENT_MAX),
            'area': text(payload, 'area'), 'kind': payload.get('kind', 'normal'),
            'rotation': payload.get('rotation', 'month'), 'allow_multiple': flag(payload, 'allow_multiple')}
    if data['kind'] not in ('normal', 'rest', 'blank') or data['rotation'] not in ('year', 'month', 'week', 'fixed'):
        raise ValueError('工作類型或換人週期不正確。')
    items = payload.get('items', [])
    if not isinstance(items, list) or len(items) > limits.DUTY_ITEMS_PER_TASK:
        raise ValueError('執行子項目格式不正確或已達上限。')
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('執行子項目格式不正確。')
        frequency = item.get('frequency', 'daily')
        weekdays = item.get('weekdays', [])
        if frequency not in ('daily', 'weekly', 'monthly', 'annual') or not isinstance(weekdays, list) or any(type(d) is not int or d not in range(7) for d in weekdays):
            raise ValueError('頻率或星期不正確。')
        if frequency == 'weekly' and not weekdays:
            raise ValueError('每週工作至少選擇一個星期。')
        start, end = item.get('day_start', 1), item.get('day_end', 31)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= 31:
            raise ValueError('月內日期範圍需介於 1–31 日。')
        annual = item.get('annual_date', '')
        if annual:
            if not isinstance(annual, str) or not re.fullmatch(r'\d{2}-\d{2}', annual):
                raise ValueError('年度日期需為 MM-DD。')
            checked_date('2000-'+annual)
        excluded = item.get('excluded_dates', [])
        if not isinstance(excluded, list) or len(excluded) > limits.DUTY_EXCLUDED_DATES_MAX:
            raise ValueError('排除日期格式不正確或已達上限。')
        for day in excluded:
            checked_date(day)
        reminder = item.get('reminder_time', '')
        if not isinstance(reminder, str) or (reminder and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', reminder)):
            raise ValueError('提醒時間需為 HH:MM。')
        result.append({'content': text(item, 'content', required=True, maximum=limits.DUTY_CONTENT_MAX),
                       'frequency': frequency, 'weekdays': sorted(set(weekdays)), 'day_start': start, 'day_end': end,
                       'annual_date': annual, 'excluded_dates': sorted(set(excluded)), 'reminder_time': reminder,
                       'reminder_enabled': flag(item, 'reminder_enabled')})
    return {**data, 'items': result}


def execution_preview(data, start=None):
    data = validated_task(data)
    start = checked_date(start) if start else today()
    result = []
    for offset in range(limits.DUTY_PREVIEW_DAYS):
        day = start + timedelta(days=offset)
        due, groups = [], {}
        if data['kind'] == 'normal':
            for item in data['items']:
                if day.isoformat() in item['excluded_dates']:
                    continue
                frequency = item['frequency']
                matches = (frequency == 'daily' or frequency == 'weekly' and day.weekday() in item['weekdays'] or
                           frequency == 'monthly' and item['day_start'] <= day.day <= item['day_end'] or
                           frequency == 'annual' and item['annual_date'] == day.strftime('%m-%d'))
                if not matches:
                    continue
                due.append(item['content'])
                if item['reminder_enabled'] and item['reminder_time']:
                    groups.setdefault(item['reminder_time'], []).append(item['content'])
        result.append({'date': day.isoformat(), 'weekday': day.weekday(), 'due': due,
                       'reminders': [{'time': time, 'contents': contents} for time, contents in sorted(groups.items())]})
    return result


def list_tasks(user, *, preview=False):
    org_id = managed_org(user, read=True)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        result = []
        for task in conn.execute('SELECT * FROM duty_tasks WHERE org_id=? AND deleted=0 ORDER BY sort_order,task_id', (org_id,)).fetchall():
            versions = []
            for row in conn.execute('SELECT * FROM duty_task_versions WHERE task_id=? ORDER BY effective_from DESC,version DESC', (task['task_id'],)):
                version = dict(row)
                version['items'] = []
                for item in conn.execute('SELECT * FROM duty_task_items WHERE version_id=? ORDER BY sort_order', (row['version_id'],)):
                    item = dict(item)
                    for key in ('weekdays', 'excluded_dates'):
                        item[key] = json.loads(item[key])
                    item['reminder_enabled'] = bool(item['reminder_enabled'])
                    version['items'].append(item)
                version['allow_multiple'] = bool(version['allow_multiple'])
                versions.append(version)
            effective = next((v for v in versions if v['effective_from'] <= today().isoformat()), None)
            result.append({**dict(task), 'versions': versions, 'current': effective,
                           'impacts': reference_impacts(conn, org_id, 'task', task['task_id'])})
    return {'tasks': result}


def save_task(user, payload, *, preview=False, conn=None):
    org_id = managed_org(user, payload, preview=preview)
    data = validated_task(payload)
    effective = checked_date(payload.get('effective_from')).isoformat()
    active = flag(payload, 'active', True)
    if conn is None:
        with app.database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            return save_task(user, payload, preview=preview, conn=connection)
    task_id = payload.get('task_id') or uuid4().hex
    if payload.get('task_id'):
        old = scoped(conn, 'duty_tasks', 'task_id', task_id, org_id)
        if old['deleted']:
            raise ValueError('請先復原已刪除的工作。')
        if old['updated_at'] != payload.get('expected_updated_at'):
            raise ValueError('工作已被修改，請重新載入。')
        confirm_impacts(conn, org_id, 'task', task_id, payload)
        last = conn.execute('SELECT MAX(effective_from) FROM duty_task_versions WHERE task_id=?', (task_id,)).fetchone()[0]
        if effective < last:
            raise ValueError('新版本生效日不得早於既有版本。')
        conn.execute('UPDATE duty_tasks SET active=?,updated_at=? WHERE task_id=?', (active, now(), task_id))
    else:
        if conn.execute('SELECT COUNT(*) FROM duty_tasks WHERE org_id=? AND deleted=0', (org_id,)).fetchone()[0] >= limits.DUTY_TASKS_PER_ORG:
            raise ValueError('工作項目已達上限。')
        order = conn.execute('SELECT COALESCE(MAX(sort_order),0)+1 FROM duty_tasks WHERE org_id=?', (org_id,)).fetchone()[0]
        conn.execute('INSERT INTO duty_tasks VALUES (?,?,?,0,?,?)', (task_id, org_id, active, order, now()))
    version = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM duty_task_versions WHERE task_id=?', (task_id,)).fetchone()[0]
    version_id = uuid4().hex
    conn.execute('INSERT INTO duty_task_versions VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 (version_id, task_id, version, effective, data['name'], data['description'], data['area'], data['kind'], data['rotation'], data['allow_multiple'], now()))
    for index, item in enumerate(data['items']):
        conn.execute('INSERT INTO duty_task_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                     (uuid4().hex, version_id, item['content'], item['frequency'], json.dumps(item['weekdays']),
                      item['day_start'], item['day_end'], item['annual_date'], json.dumps(item['excluded_dates']),
                      item['reminder_time'], item['reminder_enabled'], index))
    reports.audit(conn, user['email'], 'duty.task.save', task_id, f"{data['name']} v{version}｜生效 {effective}", org_id)
    return {'task_id': task_id, 'version': version}


def roster_rows(user):
    org_id = authorize(user)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute('SELECT * FROM duty_rosters WHERE org_id=? ORDER BY date_from DESC,version DESC', (org_id,))]
    if not capabilities(user)['edit']:
        rows = [r for r in rows if r['status'] in ('published', 'replaced')]
    return {'rosters': rows}


def get_roster(user, roster_id, *, conn=None):
    org_id = authorize(user)
    if conn is None:
        with app.database_connection() as connection:
            return get_roster(user, roster_id, conn=connection)
    row = scoped(conn, 'duty_rosters', 'roster_id', roster_id, org_id)
    if row['status'] == 'draft' and not capabilities(user)['edit']:
        raise PermissionError('只能查看已發布班表。')
    assignments = []
    for assignment in conn.execute('SELECT * FROM duty_assignments WHERE roster_id=? ORDER BY rowid', (roster_id,)).fetchall():
        assignment = dict(assignment)
        assignment['person_ids'] = json.loads(assignment['person_ids'])
        assignment['snapshot'] = json.loads(assignment['snapshot'])
        assignment['substitutions'] = [dict(r) for r in conn.execute('SELECT * FROM duty_substitutions WHERE assignment_id=? ORDER BY date_from', (assignment['assignment_id'],))]
        assignments.append(assignment)
    row['assignments'] = assignments
    row['checks'] = roster_checks(user, row, conn=conn) if row['status'] == 'draft' else {'blocking': [], 'warnings': [], 'info': []}
    return row


def task_snapshot(conn, task_id, on_date):
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM duty_task_versions WHERE task_id=? AND effective_from<=? ORDER BY effective_from DESC,version DESC LIMIT 1', (task_id, on_date)).fetchone()
    if not row:
        return None
    version = dict(row)
    version['allow_multiple'] = bool(version['allow_multiple'])
    version['items'] = []
    for item in conn.execute('SELECT * FROM duty_task_items WHERE version_id=? ORDER BY sort_order', (row['version_id'],)):
        item = dict(item)
        item['weekdays'] = json.loads(item['weekdays'])
        item['excluded_dates'] = json.loads(item['excluded_dates'])
        item['reminder_enabled'] = bool(item['reminder_enabled'])
        version['items'].append(item)
    return version


def create_draft(user, payload, *, preview=False, conn=None):
    org_id = authorize(user, 'edit', organization_id=payload.get('org_id'), preview=preview)
    first, last = checked_date(payload.get('date_from')), checked_date(payload.get('date_to'))
    period = payload.get('period_type', 'month')
    if period not in ('week', 'month', 'year') or last < first or (last-first).days > 366:
        raise ValueError('排班期間不正確或超過一年。')
    name = text(payload, 'name', required=True)
    if conn is None:
        with app.database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            return create_draft(user, payload, preview=preview, conn=connection)
    existing = conn.execute("SELECT roster_id FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status='draft'", (org_id, first.isoformat(), last.isoformat())).fetchone()
    if existing:
        return {'roster_id': existing[0], 'existing': True}
    if conn.execute('SELECT COUNT(*) FROM duty_rosters WHERE org_id=?', (org_id,)).fetchone()[0] >= limits.DUTY_ROSTERS_PER_ORG:
        raise ValueError('班表數量已達上限。')
    source = get_roster(user, payload['copy_from'], conn=conn) if payload.get('copy_from') else None
    roster_id = uuid4().hex
    conn.execute("INSERT INTO duty_rosters VALUES (?,?,?,?,?,?,'draft',0,'','','',?)", (roster_id, org_id, name, period, first.isoformat(), last.isoformat(), now()))
    tasks = conn.execute('SELECT task_id FROM duty_tasks WHERE org_id=? AND active=1 AND deleted=0 ORDER BY sort_order', (org_id,)).fetchall()
    for task in tasks:
        snapshot = task_snapshot(conn, task[0], first.isoformat())
        if not snapshot:
            continue
        old = next((a for a in source['assignments'] if a['task_id'] == task[0]), None) if source else None
        ids = old['person_ids'] if old else []
        inherited = snapshot['rotation'] not in (period, 'fixed')
        if inherited:
            inherited_row = conn.execute('''SELECT a.person_ids FROM duty_assignments a JOIN duty_rosters r ON r.roster_id=a.roster_id
                WHERE r.org_id=? AND r.status='published' AND r.period_type=? AND a.task_id=? AND r.date_from<=? AND r.date_to>=?
                ORDER BY r.published_at DESC LIMIT 1''', (org_id, snapshot['rotation'], task[0], first.isoformat(), last.isoformat())).fetchone()
            ids = json.loads(inherited_row[0]) if inherited_row else []
        snapshot['inherited'] = inherited
        conn.execute('INSERT INTO duty_assignments VALUES (?,?,?,?,?,?)', (uuid4().hex, roster_id, task[0], json.dumps(ids), old['note'] if old else '', json.dumps(snapshot, ensure_ascii=False)))
    reports.audit(conn, user['email'], 'duty.roster.create', roster_id, name, org_id)
    return {'roster_id': roster_id, 'existing': False}


def roster_checks(user, roster, *, conn):
    blocking, warnings, info, counts = [], [], [], {}
    org_id = user['organization_id']
    for assignment in roster['assignments']:
        snapshot = assignment['snapshot']
        label = snapshot.get('name', '工作')
        task = scoped(conn, 'duty_tasks', 'task_id', assignment['task_id'], org_id)
        if not task['active'] or task['deleted']:
            blocking.append({'key': 'task:'+task['task_id'], 'task_id': task['task_id'], 'message': label+' 已停用，仍列入班表'})
        if snapshot.get('kind') in ('rest', 'blank'):
            info.append({'message': label+' 不產生提醒', 'task_id': task['task_id']})
        elif not assignment['person_ids']:
            warnings.append({'key':'unassigned:'+task['task_id'], 'message':label+' 未分配', 'task_id':task['task_id']})
        if not snapshot.get('allow_multiple') and len(assignment['person_ids']) > 1:
            blocking.append({'key':'multiple:'+task['task_id'], 'message':label+' 不允許多人共同負責', 'task_id':task['task_id']})
        for person_id in assignment['person_ids']:
            person = scoped(conn, 'duty_people', 'person_id', person_id, org_id)
            counts[person_id] = counts.get(person_id, 0) + 1
            if not person['active'] or person['deleted']:
                blocking.append({'key':'inactive:'+task['task_id']+person_id, 'message':person['full_name']+' 已在值日人員中停用，仍被分配', 'task_id':task['task_id']})
            membership = conn.execute('SELECT 1 FROM duty_position_members WHERE person_id=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>=?)', (person_id, roster['date_from'], roster['date_to'])).fetchone()
            if not membership:
                warnings.append({'key':'membership:'+task['task_id']+person_id, 'message':person['full_name']+' 的輪替生效期間未涵蓋班表', 'task_id':task['task_id']})
            if not conn.execute('SELECT 1 FROM duty_person_bindings WHERE person_id=? AND org_id=?', (person_id, org_id)).fetchone():
                warnings.append({'key':'binding:'+person_id, 'message':person['full_name']+' 未綁定 LINE', 'task_id':task['task_id']})
        for item in snapshot.get('items', []):
            if item.get('reminder_enabled') and (not item.get('reminder_time') or item.get('frequency') == 'annual' and not item.get('annual_date')):
                warnings.append({'key':'time:'+item['item_id'], 'message':label+' 提醒時間或年度日期待設定', 'task_id':task['task_id']})
        if not snapshot.get('inherited'):
            conflicts = conn.execute('''SELECT r.roster_id,a.snapshot FROM duty_assignments a JOIN duty_rosters r ON r.roster_id=a.roster_id
                WHERE r.org_id=? AND r.status='published' AND r.roster_id<>? AND a.task_id=?
                AND r.date_from<=? AND r.date_to>=? AND NOT (r.date_from=? AND r.date_to=?)''',
                (org_id, roster['roster_id'], task['task_id'], roster['date_to'], roster['date_from'], roster['date_from'], roster['date_to'])).fetchall()
            if any(not json.loads(row['snapshot']).get('inherited') for row in conflicts):
                blocking.append({'key':'conflict:'+task['task_id'], 'message':label+' 與已發布班表期間衝突', 'task_id':task['task_id']})
        subs = assignment.get('substitutions', [])
        for index, sub in enumerate(subs):
            substitute = scoped(conn, 'duty_people', 'person_id', sub['substitute_person_id'], org_id)
            if not substitute['active'] or substitute['deleted']:
                blocking.append({'key':'sub:'+sub['substitution_id'], 'message':substitute['full_name']+' 代班人員已停用', 'task_id':task['task_id']})
            if any(s['original_person_id']==sub['original_person_id'] and s['date_from']<=sub['date_to'] and s['date_to']>=sub['date_from'] for s in subs[:index]):
                blocking.append({'key':'sub-conflict:'+sub['substitution_id'], 'message':label+' 的代班期間衝突', 'task_id':task['task_id']})
    for person_id, count in counts.items():
        if count > 1:
            person = scoped(conn, 'duty_people', 'person_id', person_id, org_id)
            warnings.append({'key':'workload:'+person_id, 'message':person['full_name']+f' 兼任 {count} 項工作'})
    return {'blocking':blocking, 'warnings':list({r['key']:r for r in warnings}.values()), 'info':info}


def save_draft(user, payload, *, preview=False, conn=None):
    org_id = authorize(user, 'edit', preview=preview, organization_id=payload.get('org_id'))
    if conn is None:
        with app.database_connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            return save_draft(user, payload, preview=preview, conn=connection)
    roster = get_roster(user, payload.get('roster_id'), conn=conn)
    if roster['status'] != 'draft' or roster['updated_at'] != payload.get('expected_updated_at'):
        raise ValueError('班表已更新或已發布，請重新載入。')
    changes = payload.get('assignments')
    if not isinstance(changes, list) or any(not isinstance(a,dict) for a in changes) or len(changes) != len(roster['assignments']):
        raise ValueError('請提交完整工作分配。')
    known = {a['assignment_id']:a for a in roster['assignments']}
    if len({a.get('assignment_id') for a in changes}) != len(changes):
        raise ValueError('工作分配不可重複。')
    for change in changes:
        original = known.get(change.get('assignment_id'))
        if not original:
            raise ValueError('工作分配不屬於此班表。')
        ids = change.get('person_ids', [])
        if not isinstance(ids, list) or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids) or len(ids)>limits.DUTY_PEOPLE_PER_ORG:
            raise ValueError('負責人格式不正確。')
        for person_id in ids:
            scoped(conn, 'duty_people', 'person_id', person_id, org_id)
        if original['snapshot'].get('inherited') and ids != original['person_ids']:
            raise ValueError('不同輪換週期的工作請至對應期間班表修改。')
        note = text(change, 'note', maximum=limits.DUTY_CONTENT_MAX)
        substitutions = change.get('substitutions', [])
        if not isinstance(substitutions,list) or any(not isinstance(s,dict) for s in substitutions) or len(substitutions)>limits.DUTY_SUBSTITUTIONS_PER_ASSIGNMENT:
            raise ValueError('代班格式或數量不正確。')
        conn.execute('DELETE FROM duty_substitutions WHERE assignment_id=?', (original['assignment_id'],))
        for sub in substitutions:
            start, end = checked_date(sub.get('date_from')), checked_date(sub.get('date_to'))
            if start>end or start.isoformat()<roster['date_from'] or end.isoformat()>roster['date_to'] or sub.get('original_person_id') not in ids or sub.get('original_person_id')==sub.get('substitute_person_id'):
                raise ValueError('代班人員或期間不正確。')
            scoped(conn,'duty_people','person_id',sub.get('substitute_person_id'),org_id)
            if original['snapshot'].get('inherited'):
                raise ValueError('不同週期工作不可在本期設定代班。')
            conn.execute('INSERT INTO duty_substitutions VALUES (?,?,?,?,?,?)', (uuid4().hex, original['assignment_id'], sub['original_person_id'], sub['substitute_person_id'], start.isoformat(), end.isoformat()))
        conn.execute('UPDATE duty_assignments SET person_ids=?,note=? WHERE assignment_id=?', (json.dumps(ids), note, original['assignment_id']))
    conn.execute('UPDATE duty_rosters SET updated_at=? WHERE roster_id=?', (now(), roster['roster_id']))
    reports.audit(conn,user['email'],'duty.roster.save',roster['roster_id'],'儲存草稿',org_id)
    return {'ok':True}


def notification_preview(user, roster_id):
    roster = get_roster(user, roster_id)
    messages, missing, people, names, group = [], [], {}, {}, []
    with app.database_connection() as conn:
        def person_name(person_id, assignment):
            historical = assignment['snapshot'].get('people', {}).get(person_id)
            return historical['full_name'] if historical else scoped(conn,'duty_people','person_id',person_id,user['organization_id'])['full_name']
        for assignment in roster['assignments']:
            snapshot = assignment['snapshot']
            content = snapshot.get('name','工作')
            for item in snapshot.get('items', []):
                frequency = {'daily':'每天','weekly':'每週','monthly':'每月','annual':'每年'}[item['frequency']]
                if item['frequency']=='weekly':
                    frequency += '、'.join('一二三四五六日'[d] for d in item['weekdays'])
                elif item['frequency']=='monthly':
                    frequency += f" {item['day_start']}–{item['day_end']} 日"
                elif item['frequency']=='annual':
                    frequency += ' '+(item['annual_date'] or '日期待設定')
                content += '\n  '+frequency+'：'+item['content']
            for person_id in assignment['person_ids']:
                names[person_id] = person_name(person_id, assignment)
                people.setdefault(person_id,[]).append(content)
            group.append(content+'\n負責人：'+('、'.join(names[p] for p in assignment['person_ids']) or '未分配'))
            for sub in assignment['substitutions']:
                person_id = sub['substitute_person_id']
                names[person_id] = person_name(person_id, assignment)
                description = f"代班 {sub['date_from']}–{sub['date_to']}：{snapshot.get('name','工作')}（原負責人：{person_name(sub['original_person_id'], assignment)}）"
                people.setdefault(person_id,[]).append(description)
                group.append(names[person_id]+'｜'+description)
        for person_id, tasks in people.items():
            messages.append({'person_id':person_id,'name':names[person_id],'text':f"【值日生班表】{roster['name']}\n負責人：{names[person_id]}\n"+'\n'.join(tasks)})
            missing.append({'name':names[person_id],'reason':'通知 OA／訂閱尚未設定，不會發送'})
    import duty_automation
    with app.database_connection() as conn:
        setting=duty_automation.settings(conn,user['organization_id']);missing=[];count=0
        previous=conn.execute("SELECT 1 FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status='published' AND roster_id<>?",(user['organization_id'],roster['date_from'],roster['date_to'],roster['roster_id'])).fetchone()
        kind='change' if previous else 'publish'
        mode=setting['config']['type_channels'].get(kind,{'personal':True,'groups':True})
        for message in messages:
            target,reason=duty_automation.person_target(conn,user['organization_id'],setting['channel_id'],message['person_id'])
            if target and setting['config']['personal'] and mode['personal']:count+=1
            else:missing.append({'name':message['name'],'reason':reason or '個人通知未啟用'})
        groups=setting['config']['groups'] if mode['groups'] else []
        previous=conn.execute("SELECT 1 FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status='published' AND roster_id<>?",(user['organization_id'],roster['date_from'],roster['date_to'],roster['roster_id'])).fetchone()
        enabled=bool(setting['channel_id'] and setting['config']['change_enabled' if previous else 'publish_enabled'])
    return {'messages':messages,'missing':missing,'group_message':roster['name']+'\n'+'\n'.join(group), 'push_count':count,'group_count':len(groups),'estimate_complete':not groups,'enabled':enabled}


def publish_roster(user, payload, *, preview=False):
    org_id = authorize(user,'publish',preview=preview,organization_id=payload.get('org_id'))
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        roster = get_roster(user,payload.get('roster_id'),conn=conn)
        if roster['status']!='draft' or roster['updated_at']!=payload.get('expected_updated_at'):
            raise ValueError('班表已更新或已發布，請重新檢查。')
        checks = roster_checks(user,roster,conn=conn)
        if checks['blocking']:
            raise ValueError('尚有必須處理的項目，不能發布。')
        accepted = payload.get('acknowledged',[])
        if not isinstance(accepted,list) or set(accepted)!={r['key'] for r in checks['warnings']}:
            raise ValueError('請確認所有需確認項目；資料有異動時需重新檢查。')
        previous = conn.execute("SELECT * FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status='published'", (org_id,roster['date_from'],roster['date_to'])).fetchone()
        reason = text(payload,'reason',required=bool(previous),maximum=limits.DUTY_CONTENT_MAX)
        version = conn.execute('SELECT COALESCE(MAX(version),0)+1 FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=?', (org_id,roster['date_from'],roster['date_to'])).fetchone()[0]
        for assignment in roster['assignments']:
            snapshot = assignment['snapshot']
            snapshot['people'] = {person_id:{k:scoped(conn,'duty_people','person_id',person_id,org_id)[k] for k in ('full_name','display_name')} for person_id in assignment['person_ids']}
            for sub in assignment['substitutions']:
                snapshot['people'][sub['substitute_person_id']] = {k:scoped(conn,'duty_people','person_id',sub['substitute_person_id'],org_id)[k] for k in ('full_name','display_name')}
            conn.execute('UPDATE duty_assignments SET snapshot=? WHERE assignment_id=?',(json.dumps(snapshot,ensure_ascii=False),assignment['assignment_id']))
        if previous:
            conn.execute("UPDATE duty_rosters SET status='replaced' WHERE roster_id=?",(previous['roster_id'],))
        timestamp = now()
        conn.execute("UPDATE duty_rosters SET status='published',version=?,published_by=?,published_at=?,reason=?,updated_at=? WHERE roster_id=?",(version,user['email'],timestamp,reason,timestamp,roster['roster_id']))
        previous_assignments = get_roster(user,previous['roster_id'],conn=conn)['assignments'] if previous else []
        differences = []
        for assignment in roster['assignments']:
            old = next((a for a in previous_assignments if a['task_id']==assignment['task_id']), None)
            old_names = '、'.join(old['snapshot'].get('people',{}).get(p,{}).get('full_name',p) for p in old['person_ids']) if old else '未分配'
            new_names = '、'.join(assignment['snapshot']['people'][p]['full_name'] for p in assignment['person_ids']) or '未分配'
            if old_names != new_names or (old and (old['substitutions'] != assignment['substitutions'] or old['note'] != assignment['note'])):
                differences.append({'work':assignment['snapshot']['name'],'before':old_names or '未分配','after':new_names,
                                    'substitutions':[{**{k:s[k] for k in ('date_from','date_to')},'original':assignment['snapshot']['people'][s['original_person_id']]['full_name'],'substitute':assignment['snapshot']['people'][s['substitute_person_id']]['full_name']} for s in assignment['substitutions']], 'note':assignment['note']})
        detail = {'version':version,'reason':reason,'previous':previous['roster_id'] if previous else None,'differences':differences,
                  'assignments':[{k:a[k] for k in ('task_id','person_ids','substitutions')} for a in roster['assignments']]}
        reports.audit(conn,user['email'],'duty.roster.publish',roster['roster_id'],json.dumps(detail,ensure_ascii=False),org_id)
        import duty_automation
        duty_automation.on_publish(conn,user,roster['roster_id'],previous['roster_id'] if previous else None,payload.get('send_now',False))
    duty_automation.safe_rebuild(org_id)
    return {'roster_id':roster['roster_id'],'version':version}


def delete_draft(user,payload,*,preview=False):
    org_id = authorize(user,'edit',preview=preview,organization_id=payload.get('org_id'))
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        roster = get_roster(user,payload.get('roster_id'),conn=conn)
        if roster['status']!='draft' or roster['updated_at']!=payload.get('expected_updated_at'):
            raise ValueError('只能刪除未變更的草稿。')
        conn.execute('DELETE FROM duty_substitutions WHERE assignment_id IN (SELECT assignment_id FROM duty_assignments WHERE roster_id=?)',(roster['roster_id'],))
        conn.execute('DELETE FROM duty_assignments WHERE roster_id=?',(roster['roster_id'],))
        conn.execute('DELETE FROM duty_rosters WHERE roster_id=?',(roster['roster_id'],))
        reports.audit(conn,user['email'],'duty.roster.delete',roster['roster_id'],roster['name'],org_id)
    return {'ok':True}


def roster_activity(user, roster_id):
    get_roster(user,roster_id)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        events = [dict(row) for row in conn.execute("SELECT * FROM audit_events WHERE organization_id=? AND target=? AND action LIKE 'duty.roster.%' ORDER BY event_id DESC", (user['organization_id'],roster_id))]
    return {'events':events}


def binding_candidates(user, *, preview=False):
    org_id = managed_org(user, read=True)
    channel = notification_oa(org_id)
    if not channel:
        return {'channel_id': None, 'recipients': [], 'message': '尚未指定通知 OA，LINE 綁定待設定。'}
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute('''SELECT r.recipient_id,r.display_name,r.custom_name,r.picture_url,b.person_id,p.full_name AS bound_name
            FROM recipients r LEFT JOIN duty_person_bindings b ON b.channel_id=r.channel_id AND b.recipient_id=r.recipient_id AND b.org_id=?
            LEFT JOIN duty_people p ON p.person_id=b.person_id
            WHERE r.channel_id=? AND r.kind='user' AND r.active=1 ORDER BY r.display_name''', (org_id, channel))]
    return {'channel_id': channel, 'recipients': rows}


def save_binding(user, payload, *, preview=False):
    org_id = managed_org(user, payload, preview=preview)
    channel = notification_oa(org_id)
    if not channel or payload.get('channel_id') != channel:
        raise ValueError('通知 OA 尚未設定或已變更，請重新開啟綁定。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        person = scoped(conn, 'duty_people', 'person_id', payload.get('person_id'), org_id)
        if not person['active'] or person['deleted']:
            raise ValueError('停用或刪除的人員不可綁定。')
        if not conn.execute('SELECT 1 FROM line_channels WHERE channel_id=? AND org_id=? AND active=1', (channel, org_id)).fetchone():
            raise ValueError('通知 OA 不屬於本組織或已停用。')
        recipient = payload.get('recipient_id')
        if recipient:
            if not conn.execute("SELECT 1 FROM recipients WHERE channel_id=? AND recipient_id=? AND kind='user' AND active=1", (channel, recipient)).fetchone():
                raise ValueError('只能選擇通知 OA 的有效個人聯絡對象。')
            if conn.execute('SELECT 1 FROM duty_person_bindings WHERE org_id=? AND channel_id=? AND recipient_id=? AND person_id<>?', (org_id, channel, recipient, person['person_id'])).fetchone():
                raise ValueError('此聯絡對象已綁定其他人員。')
        conn.execute('DELETE FROM duty_person_bindings WHERE org_id=? AND person_id=?', (org_id, person['person_id']))
        if recipient:
            conn.execute('INSERT INTO duty_person_bindings VALUES (?,?,?,?,?)', (org_id, person['person_id'], channel, recipient, now()))
        reports.audit(conn, user['email'], 'duty.binding', person['person_id'], '更新 LINE 綁定', org_id)
    return {'ok': True}

ACTIONS = ('view', 'edit', 'publish', 'notify_settings', 'send')

PEOPLE_CSV_HEADERS = ('姓名','英文名/暱稱','部門','樓層','代號','生效日','啟用')
TASK_CSV_HEADERS = ('工作名稱','說明','區域','類型','輪換週期','允許多人','啟用','生效日',
                    '執行內容','執行頻率','星期','每月起始日','每月結束日','年度日期','排除日期','提醒時間','啟用提醒')
ROSTER_CSV_HEADERS = ('班表名稱','期間類型','起始日','結束日','工作名稱','負責人','當期備註','代班原負責人','代班人員','代班起始日','代班結束日')
CSV_KINDS = {'一般':'normal','休息':'rest','空白欄':'blank'}
CSV_ROTATIONS = {'每年':'year','每月':'month','每週':'week','固定':'fixed'}
CSV_FREQUENCIES = {'每日':'daily','每週':'weekly','每月':'monthly','每年':'annual'}


def csv_cell(value):
    value = str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value


def csv_original(value):
    # Undo the spreadsheet formula protection emitted by our exporter.
    return value[1:] if value.startswith("'") and csv_cell(value[1:]) == value else value


def csv_export(user, payload, *, preview=False):
    kind = payload.get('kind')
    if kind=='rosters':
        org_id = authorize(user,organization_id=payload.get('org_id'))
    else:
        org_id = managed_org(user,payload,read=True)
    if kind not in ('people','tasks','rosters'):
        raise ValueError('CSV 類型不正確。')
    rows = []
    if not payload.get('template'):
        if kind == 'people':
            for p in list_people(user)['people']:
                member = p['memberships'][-1] if p['memberships'] else {}
                rows.append([p['full_name'],p['display_name'],p['department'],p['floor'],member.get('code',''),member.get('effective_from',today().isoformat()),p['active']])
        elif kind=='tasks':
            for task in list_tasks(user)['tasks']:
                v = task['versions'][0]
                base = [v['name'],v['description'],v['area'],next(k for k,val in CSV_KINDS.items() if val==v['kind']),next(k for k,val in CSV_ROTATIONS.items() if val==v['rotation']),int(v['allow_multiple']),task['active'],v['effective_from']]
                for item in v['items'] or [None]:
                    rows.append(base+([item['content'],next(k for k,val in CSV_FREQUENCIES.items() if val==item['frequency']),';'.join(str(d+1) for d in item['weekdays']),item['day_start'],item['day_end'],item['annual_date'],';'.join(item['excluded_dates']),item['reminder_time'],int(item['reminder_enabled'])] if item else ['']*9))
        else:
            roster = get_roster(user,payload.get('roster_id'))
            with app.database_connection() as conn:
                def name(person_id,assignment):
                    return assignment['snapshot'].get('people',{}).get(person_id,{}).get('full_name') or scoped(conn,'duty_people','person_id',person_id,org_id)['full_name']
                for assignment in roster['assignments']:
                    base = [roster['name'],{'week':'週','month':'月','year':'年'}[roster['period_type']],roster['date_from'],roster['date_to'],assignment['snapshot']['name'],';'.join(name(p,assignment) for p in assignment['person_ids']),assignment['note']]
                    for sub in assignment['substitutions'] or [None]:
                        rows.append(base+([name(sub['original_person_id'],assignment),name(sub['substitute_person_id'],assignment),sub['date_from'],sub['date_to']] if sub else ['']*4))
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow({'people':PEOPLE_CSV_HEADERS,'tasks':TASK_CSV_HEADERS,'rosters':ROSTER_CSV_HEADERS}[kind])
    writer.writerows([csv_cell(v) for v in row] for row in rows)
    with app.database_connection() as conn:
        reports.audit(conn,user['email'],'duty.csv.export',kind,'下載範本' if payload.get('template') else f'匯出 {len(rows)} 列',org_id)
    return {'filename':{'people':'值日人員','tasks':'工作項目','rosters':'值日生班表'}[kind]+('_範本' if payload.get('template') else '')+'.csv','content':'\ufeff'+stream.getvalue()}


def csv_import_roster(user,payload,*,preview=False):
    org_id = managed_org(user,payload,preview=preview)
    raw = payload.get('text')
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>limits.DUTY_CSV_MAX_BYTES:
        raise ValueError('CSV 檔案大小超過上限。')
    try:
        reader = csv.DictReader(io.StringIO(raw.lstrip('\ufeff'),newline=''),strict=True)
        if tuple(reader.fieldnames or ())!=ROSTER_CSV_HEADERS:
            raise ValueError('班表 CSV 標題不正確，請下載範本。')
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError('CSV 引號或換行格式不正確。') from exc
    if not rows or len(rows)>limits.DUTY_CSV_ROWS_MAX:
        raise ValueError('CSV 沒有資料或列數超過上限。')
    groups, errors, display, task_cache = {}, [], [], {}
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.row_factory = sqlite3.Row
        people = [dict(p) for p in conn.execute('SELECT * FROM duty_people WHERE org_id=? AND active=1 AND deleted=0',(org_id,))]
        def resolve_person(name):
            matches = [p['person_id'] for p in people if p['full_name']==name]
            if len(matches)!=1:
                raise ValueError('找不到唯一的啟用人員：'+name)
            return matches[0]
        for line,raw_row in enumerate(rows,2):
            try:
                if None in raw_row or any(v is None for v in raw_row.values()):
                    raise ValueError('欄位數與標題不一致。')
                row = {k:csv_original(v).strip() for k,v in raw_row.items()}
                if not any(row.values()):continue
                first,last=checked_date(row['起始日']),checked_date(row['結束日'])
                period={'週':'week','月':'month','年':'year'}.get(row['期間類型'],row['期間類型'])
                if period not in ('week','month','year') or last<first or (last-first).days>366:
                    raise ValueError('班表期間不正確。')
                text({'name':row['班表名稱']},'name',required=True)
                key=(row['起始日'],row['結束日'])
                if key not in groups:
                    groups[key]={'name':row['班表名稱'],'period_type':period,'date_from':row['起始日'],'date_to':row['結束日'],'assignments':{},'line':line}
                group=groups[key]
                if group['name']!=row['班表名稱'] or group['period_type']!=period:
                    raise ValueError('同期間的班表名稱與類型必須一致。')
                if row['起始日'] not in task_cache:
                    task_cache[row['起始日']] = {}
                    for task in conn.execute('SELECT task_id FROM duty_tasks WHERE org_id=? AND active=1 AND deleted=0 ORDER BY sort_order',(org_id,)):
                        snapshot=task_snapshot(conn,task['task_id'],row['起始日'])
                        if snapshot:
                            task_cache[row['起始日']].setdefault(snapshot['name'],[]).append((task['task_id'],snapshot))
                tasks=task_cache[row['起始日']].get(row['工作名稱'],[])
                if len(tasks)!=1:
                    raise ValueError('找不到本期間唯一的啟用工作：'+row['工作名稱'])
                task_id,snapshot=tasks[0]
                names=[name.strip() for name in row['負責人'].split(';') if name.strip()]
                ids=[resolve_person(name) for name in names]
                if len(set(ids))!=len(ids) or len(ids)>1 and not snapshot['allow_multiple']:
                    raise ValueError('負責人重複或工作不允許多人。')
                note=text({'note':row['當期備註']},'note',maximum=limits.DUTY_CONTENT_MAX)
                assignment=group['assignments'].setdefault(task_id,{'person_ids':ids,'note':note,'substitutions':[],'snapshot':snapshot})
                if assignment['person_ids']!=ids or assignment['note']!=note:
                    raise ValueError('同一工作的負責人及備註必須一致。')
                sub_values=[row[k] for k in ROSTER_CSV_HEADERS[7:]]
                if any(sub_values):
                    if not all(sub_values):raise ValueError('代班四個欄位必須一起填寫。')
                    original,substitute=resolve_person(sub_values[0]),resolve_person(sub_values[1])
                    start,end=checked_date(sub_values[2]),checked_date(sub_values[3])
                    if original not in ids or original==substitute or start>end or start<first or end>last:
                        raise ValueError('代班人員或期間不正確。')
                    subs=assignment['substitutions']
                    if len(subs)>=limits.DUTY_SUBSTITUTIONS_PER_ASSIGNMENT or any(s['original_person_id']==original and s['date_from']<=sub_values[3] and s['date_to']>=sub_values[2] for s in subs):
                        raise ValueError('代班期間衝突或數量超過上限。')
                    subs.append({'original_person_id':original,'substitute_person_id':substitute,'date_from':sub_values[2],'date_to':sub_values[3]})
                display.append({'line':line,'name':row['工作名稱'],'action':'匯入草稿','summary':row['班表名稱']+'｜'+(row['負責人'] or '未分配')+(('｜代班：'+row['代班人員']) if row['代班人員'] else '')})
            except ValueError as exc:
                errors.append({'line':line,'message':str(exc)})
        for group in groups.values():
            if conn.execute("SELECT 1 FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status='draft'",(org_id,group['date_from'],group['date_to'])).fetchone():
                errors.append({'line':group['line'],'message':'此期間已有草稿，請先編輯或刪除既有草稿。'})
            for task_id,assignment in group['assignments'].items():
                snapshot=assignment['snapshot']
                if snapshot['rotation'] not in (group['period_type'],'fixed'):
                    inherited=conn.execute('''SELECT a.person_ids FROM duty_assignments a JOIN duty_rosters r ON r.roster_id=a.roster_id
                        WHERE r.org_id=? AND r.status='published' AND r.period_type=? AND a.task_id=? AND r.date_from<=? AND r.date_to>=? ORDER BY r.published_at DESC LIMIT 1''',
                        (org_id,snapshot['rotation'],task_id,group['date_from'],group['date_to'])).fetchone()
                    if assignment['person_ids']!=(json.loads(inherited[0]) if inherited else []) or assignment['substitutions']:
                        errors.append({'line':group['line'],'message':snapshot['name']+' 為不同輪換週期，請於對應班表分配。'})
        count=conn.execute('SELECT COUNT(*) FROM duty_rosters WHERE org_id=?',(org_id,)).fetchone()[0]
        if count+len(groups)>limits.DUTY_ROSTERS_PER_ORG:
            errors.append({'line':0,'message':'匯入後班表數量超過上限。'})
        if not display and not errors:raise ValueError('CSV 沒有可匯入的班表。')
        import hashlib
        state=[dict(r) for r in conn.execute('SELECT * FROM duty_rosters WHERE org_id=?',(org_id,))]
        task_state=[dict(r) for r in conn.execute('SELECT * FROM duty_tasks WHERE org_id=?',(org_id,))]
        signature=hashlib.sha256(json.dumps([raw,people,state,task_state],sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
        imported=[]
        if payload.get('confirm') is True:
            if errors:raise ValueError('CSV 有錯誤，請修正後重新預覽。')
            if payload.get('preview_signature')!=signature:raise ValueError('檔案或既有資料已變更，請重新預覽。')
            for group in groups.values():
                result=create_draft(user,group,conn=conn)
                roster=get_roster(user,result['roster_id'],conn=conn)
                for assignment in roster['assignments']:
                    values=group['assignments'].get(assignment['task_id'])
                    if values:assignment.update({k:values[k] for k in ('person_ids','note','substitutions')})
                save_draft(user,{'roster_id':roster['roster_id'],'expected_updated_at':roster['updated_at'],'assignments':roster['assignments']},conn=conn)
                imported.append(roster['roster_id'])
            reports.audit(conn,user['email'],'duty.csv.import','rosters',f'匯入 {len(imported)} 份草稿',org_id)
        return {'rows':display,'errors':errors,'added':len(groups),'skipped':0,'preview_signature':signature,'can_import':not errors,'roster_ids':imported}


def csv_bool(value, default=True):
    if value=='':
        return default
    if value not in ('0','1','true','false','啟用','停用','是','否'):
        raise ValueError('啟用及允許多人欄位須填 1／0。')
    return value in ('1','true','啟用','是')


def csv_enum(value, mapping, default):
    result = mapping.get(value,value) if value else default
    if result not in mapping.values():
        raise ValueError('類型、輪換週期或執行頻率不正確。')
    return result


def csv_import(user, payload, *, preview=False):
    org_id = managed_org(user,payload,preview=preview)
    kind = payload.get('kind')
    if kind=='rosters':
        return csv_import_roster(user,payload,preview=preview)
    if kind not in ('people','tasks'):
        raise ValueError('CSV 類型不正確。')
    raw = payload.get('text')
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>limits.DUTY_CSV_MAX_BYTES:
        raise ValueError('CSV 檔案大小超過上限。')
    if payload.get('confirm') not in (None,False,True):
        raise ValueError('匯入確認格式不正確。')
    reader = csv.DictReader(io.StringIO(raw.lstrip('\ufeff'),newline=''),strict=True)
    aliases = {'全名':'姓名','顯示名稱':'英文名/暱稱','顯示名稱／暱稱':'英文名/暱稱','英文名／暱稱':'英文名/暱稱','名稱':'工作名稱'}
    try:
        headers = [aliases.get(h.strip(),h.strip()) for h in (reader.fieldnames or [])]
    except csv.Error as exc:
        raise ValueError('CSV 引號或換行格式不正確。') from exc
    required = '姓名' if kind=='people' else '工作名稱'
    allowed = set(PEOPLE_CSV_HEADERS if kind=='people' else TASK_CSV_HEADERS)
    if kind=='people':
        allowed.update(('職稱','分機','備註'))  # Existing employee-list CSV is accepted.
    if required not in headers or len(set(headers))!=len(headers) or set(headers)-allowed:
        raise ValueError('CSV 標題不正確，請下載範本；員工清單也可直接匯入。')
    reader.fieldnames = headers
    records, errors, groups, skipped = [], [], {}, []
    try:
        for index,row in enumerate(reader,2):
            if index-1>limits.DUTY_CSV_ROWS_MAX:
                raise ValueError('CSV 列數超過上限。')
            if None in row or any(v is None for v in row.values()):
                errors.append({'line':reader.line_num,'message':'欄位數與標題不一致。'});continue
            row = {k:csv_original(v).strip() for k,v in row.items()}
            if not any(row.values()):
                continue
            line = reader.line_num
            try:
                effective = checked_date(row.get('生效日') or payload.get('effective_from') or today().isoformat()).isoformat()
                if kind=='people':
                    if row['姓名'].upper()=='X':
                        skipped.append({'line':line,'name':'X','action':'略過','message':'待補位標記'});continue
                    data = {'full_name':row['姓名'],'display_name':row.get('英文名/暱稱',''),'department':row.get('部門',''),'floor':row.get('樓層',''),'code':row.get('代號',''),'effective_from':effective,'active':csv_bool(row.get('啟用',''))}
                    for key in ('full_name','display_name','department','floor','code'):
                        text(data,key,required=key=='full_name')
                    if any(r['data']['full_name']==data['full_name'] for r in records):
                        raise ValueError('檔案內姓名重複，請確認。')
                    records.append({'line':line,'name':data['full_name'],'data':data})
                else:
                    base = {'name':row['工作名稱'],'description':row.get('說明',''),'area':row.get('區域',''),'kind':csv_enum(row.get('類型',''),CSV_KINDS,'normal'),'rotation':csv_enum(row.get('輪換週期',''),CSV_ROTATIONS,'month'),'allow_multiple':csv_bool(row.get('允許多人',''),False),'active':csv_bool(row.get('啟用','')),'effective_from':effective}
                    text(base,'name',required=True)
                    name = base['name']
                    if name not in groups:
                        groups[name]={'line':line,'name':name,'data':{**base,'items':[]}}
                    elif {k:v for k,v in groups[name]['data'].items() if k!='items'}!=base:
                        raise ValueError('同一工作的說明、類型、週期或生效日必須一致。')
                    if row.get('執行內容'):
                        weekdays = [int(d)-1 for d in re.split(r'[;；,，\s]+',row.get('星期','')) if d]
                        item = {'content':row['執行內容'],'frequency':csv_enum(row.get('執行頻率',''),CSV_FREQUENCIES,'daily'),'weekdays':weekdays,'day_start':int(row.get('每月起始日') or 1),'day_end':int(row.get('每月結束日') or 31),'annual_date':row.get('年度日期',''),'excluded_dates':[d for d in re.split(r'[;；,，\s]+',row.get('排除日期','')) if d],'reminder_time':row.get('提醒時間',''),'reminder_enabled':csv_bool(row.get('啟用提醒',''),False)}
                        groups[name]['data']['items'].append(item)
                    elif any(row.get(k) for k in TASK_CSV_HEADERS[9:]):
                        raise ValueError('填寫執行頻率或提醒設定時，執行內容不可留空。')
            except ValueError as exc:
                errors.append({'line':line,'message':str(exc)})
    except csv.Error as exc:
        raise ValueError('CSV 引號或換行格式不正確。') from exc
    if kind=='tasks':
        records = list(groups.values())
        for record in records:
            try:
                validated_task(record['data'])
            except ValueError as exc:
                errors.append({'line':record['line'],'message':str(exc)})
    if not records and not skipped and not errors:
        raise ValueError('CSV 沒有可匯入的資料。')
    maximum = limits.DUTY_PEOPLE_PER_ORG if kind=='people' else limits.DUTY_TASKS_PER_ORG
    if len(records)>maximum:
        raise ValueError('CSV 項目數超過上限。')
    # Preview and commit share this validation, including duplicate/capacity checks.
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.row_factory = sqlite3.Row
        if kind=='people':
            existing = [dict(r) for r in conn.execute('SELECT * FROM duty_people WHERE org_id=? AND deleted=0',(org_id,))]
        else:
            existing = []
            for task in conn.execute('SELECT * FROM duty_tasks WHERE org_id=? AND deleted=0',(org_id,)):
                version = conn.execute('SELECT * FROM duty_task_versions WHERE task_id=? ORDER BY version DESC LIMIT 1',(task['task_id'],)).fetchone()
                existing.append({**dict(task),**dict(version)})
        for record in records:
            data = record['data']
            matching = [r for r in existing if r['full_name' if kind=='people' else 'name']==record['name']]
            record['action']='新增'
            if matching:
                identical = len(matching)==1
                keys = ('full_name','display_name','department','floor','active') if kind=='people' else ('name','description','area','kind','rotation','allow_multiple','active','effective_from')
                identical = identical and all(matching[0][k]==data[k] for k in keys)
                if identical and kind=='tasks':
                    saved = task_snapshot(conn,matching[0]['task_id'],matching[0]['effective_from'])
                    saved_items = [{k:item[k] for k in data_item} for item,data_item in zip(saved['items'],data['items'])]
                    identical = len(saved['items'])==len(data['items']) and saved_items==data['items']
                if identical:
                    record['action']='略過';record['message']='同名且內容相同，保留既有資料'
                else:
                    errors.append({'line':record['line'],'message':record['name']+' 已存在且內容不同，請從編輯頁更新。'})
            elif kind=='people' and data['code']:
                position = conn.execute('SELECT * FROM duty_positions WHERE org_id=? AND code=?',(org_id,data['code'])).fetchone()
                if position:
                    if not position['vacant']:
                        errors.append({'line':record['line'],'message':'代號 '+data['code']+' 已有人員。'})
                    else:
                        data['position_id']=position['position_id']
                if sum(r['data'].get('code')==data['code'] for r in records)>1:
                    errors.append({'line':record['line'],'message':'檔案內代號重複。'})
        additions = [r for r in records if r['action']=='新增']
        if len(existing)+len(additions)>maximum:
            errors.append({'line':0,'message':'匯入後數量超過組織上限。'})
        display = [{**{k:v for k,v in r.items() if k!='data'},'summary':(' · '.join(r['data'][k] for k in ('display_name','department','floor') if r['data'][k]) if kind=='people' else f"{r['data']['rotation']}｜"+'；'.join(i['content']+'（'+i['frequency']+'）' for i in r['data']['items']))} for r in records]+skipped
        import hashlib
        signature = hashlib.sha256(json.dumps({'kind':kind,'text':raw,'effective_from':payload.get('effective_from'),'existing':existing},ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
        if payload.get('confirm') is True:
            if errors:
                raise ValueError('CSV 有錯誤，請修正後重新預覽。')
            if payload.get('preview_signature')!=signature:
                raise ValueError('檔案或既有資料已變更，請重新預覽。')
            for record in additions:
                (save_person if kind=='people' else save_task)(user,record['data'],conn=conn)
            reports.audit(conn,user['email'],'duty.csv.import',kind,f'新增 {len(additions)} 項；略過 {len(display)-len(additions)} 項',org_id)
        return {'rows':display,'errors':errors,'added':len(additions),'skipped':len(display)-len(additions),'preview_signature':signature,'can_import':not errors}


def capabilities(user, *, preview=False):
    result = {action: False for action in ACTIONS}
    if not user or user.get('role') not in {'org_admin', 'operator'}:
        return result
    current = reports.account(user['email'], user.get('organization_id'))
    if not current or current['role'] not in {'org_admin', 'operator'} or not reports.module_enabled(current, 'duty'):
        return result
    result['view'] = True
    manages = current['role'] == 'org_admin' or bool(current.get('duty_manager'))
    for action in ACTIONS[1:]:
        result[action] = manages and not preview
    return result


def authorize(user, action='view', *, organization_id=None, preview=False):
    if organization_id is not None and organization_id != user.get('organization_id'):
        raise PermissionError('不能存取其他組織的值日生資料。')
    if action not in ACTIONS or not capabilities(user, preview=preview).get(action):
        raise PermissionError('值日生模組未啟用或你沒有此操作權限。')
    return user['organization_id']


def context(user, *, preview=False, organization_id=None):
    org_id = authorize(user, organization_id=organization_id, preview=preview)
    org = next(o for o in reports.organizations() if o['org_id'] == org_id)
    return {'today': today().isoformat(), 'organization': {'org_id': org_id, 'name': org['name']},
            'notification_oa': notification_oa(org_id),
            'effective_version': next((r for r in roster_rows(user)['rosters'] if r['status']=='published' and r['date_from']<=today().isoformat()<=r['date_to']), None),
            'capabilities': capabilities(user, preview=preview),
            'can_inspect_setup': capabilities(user)['edit']}


def grant(user, payload, *, preview=False):
    """Only the active organization's admin may delegate; never a preview."""
    org_id = authorize(user, 'edit', organization_id=payload.get('org_id'), preview=preview)
    current = reports.account(user['email'], org_id)
    if current['role'] != 'org_admin' or preview:
        raise PermissionError('只有本組織管理員可以授予或收回值日生管理權。')
    enabled = payload.get('duty_manager')
    if type(enabled) is not bool:
        raise ValueError('值日生管理權必須為布林值。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT m.role,m.active,u.active,m.duty_manager
                              FROM organization_members m JOIN workspace_users u ON u.email=m.email
                              WHERE m.org_id=? AND m.email=?''', (org_id, payload.get('email'))).fetchone()
        if not row or row[0] != 'operator' or not row[1] or not row[2]:
            raise ValueError('只能授權本組織啟用中的操作人員。')
        conn.execute('UPDATE organization_members SET duty_manager=? WHERE org_id=? AND email=?',
                     (int(enabled), org_id, payload['email']))
        if bool(row[3]) != enabled:
            reports.audit(conn, user['email'], 'duty.manager', payload['email'],
                          '授予值日生管理權' if enabled else '收回值日生管理權', org_id)
    return {'ok': True}

"""OA-scoped forms. Phase one: explicit basic maintenance and role capabilities."""
import copy
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import app
import channels
import limits
import reports
import forms_validation

ACTIONS = ('view', 'maintain', 'publish', 'send', 'export')


def question(identifier, title, kind='short_text', options=None, required=False):
    return {'id': identifier, 'title': title, 'description': '', 'type': kind,
            'required': required, 'options': [{'id': f'{identifier}-{i}', 'label': label}
                                             for i, label in enumerate(options or [])],
            'allow_other': False, 'validation': {'enabled': False}}


TEMPLATES = {
    'group_buy': {'name': '團購', 'description': '請填寫訂購品項與數量。', 'questions': [
        question('name', '姓名', required=True),
        question('product', '訂購品項', 'single_choice', ['品項一', '品項二'], True),
        question('quantity', '訂購數量', 'number', required=True),
        question('notes', '備註', 'paragraph')]},
    'travel': {'name': '旅遊意見', 'description': '請分享你偏好的旅遊安排。', 'questions': [
        question('destination', '偏好目的地', 'single_choice', ['山區', '海邊', '城市'], True),
        question('date', '方便參加的日期', 'date'),
        question('notes', '其他建議', 'paragraph')]},
    'parent_feedback': {'name': '家長回饋', 'description': '請分享孩子的學習情況與建議。', 'questions': [
        question('name', '學生姓名', required=True),
        question('feedback', '回饋與建議', 'paragraph', required=True)]},
}


def authorize(user, action='view', *, preview=False):
    if action not in ACTIONS or not user or user.get('role') == 'platform_admin':
        raise PermissionError('表單只能在授權的組織與 OA 工作區使用；平台管理員請使用視角預覽。')
    # Refresh membership and module state, including calls outside HTTP handlers.
    fresh = reports.account(user['email'], user.get('organization_id'))
    if not fresh or fresh['role'] not in {'org_admin', 'operator', 'collaborator'}:
        raise PermissionError('組織成員資格已失效。')
    try:
        oa = channels.authorize(channels.current_id(), fresh)
    except ValueError as exc:
        raise PermissionError(str(exc)) from exc
    if oa['org_id'] != fresh['organization_id'] or not channels.operational(oa):
        raise PermissionError('無法使用其他組織或已停用的 OA。')
    if not reports.module_enabled(fresh, 'forms'):
        raise PermissionError('此組織尚未啟用表單模組。')
    if action != 'view' and (preview or fresh['role'] not in {'org_admin', 'operator'}):
        raise PermissionError('目前角色只能閱讀表單與回覆。')
    if action == 'send' and not reports.module_enabled(fresh, 'messaging'):
        raise PermissionError('此組織尚未啟用訊息發送模組。')
    return fresh


def capabilities(user, *, preview=False):
    result = {}
    for action in ACTIONS:
        try:
            authorize(user, action, preview=preview)
            result[action] = True
        except PermissionError:
            result[action] = False
    return result


def _scope(user):
    return channels.current_id(), user['organization_id']


def _find(conn, user, form_id):
    if not isinstance(form_id, str):
        raise PermissionError('找不到授權範圍內的表單。')
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM forms WHERE form_id=? AND channel_id=? AND organization_id=?',
                       (form_id, *_scope(user))).fetchone()
    if not row:
        raise PermissionError('找不到授權範圍內的表單。')
    return dict(row)


def _counts(conn, form_id):
    notifications=conn.execute('SELECT count(*) FROM form_notifications WHERE form_id=?',(form_id,)).fetchone()[0]
    responses=conn.execute('SELECT count(*) FROM form_submissions WHERE form_id=?',(form_id,)).fetchone()[0]
    return {'notifications':notifications,'responses':responses}


def _ensure_public_link(conn,form_id):
    import secrets
    conn.execute('INSERT OR IGNORE INTO form_public_links VALUES (?,?)',(form_id,secrets.token_urlsafe(32)))


def _public(conn, row):
    result = {**row, 'questions': json.loads(row['questions_json']),
              'counts': _counts(conn, row['form_id'])}
    result.pop('questions_json')
    folder = conn.execute('SELECT folder_id FROM form_folder_items WHERE form_id=?', (row['form_id'],)).fetchone()
    result['folder_id'] = folder[0] if folder else ''
    link=conn.execute('SELECT token FROM form_public_links WHERE form_id=?',(row['form_id'],)).fetchone()
    import os
    base=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
    result['public_url']=base+'/forms/'+row['form_id']+'?token='+link[0] if base and link else ''
    result['expired'] = bool(row['deadline_at'] and datetime.fromisoformat(row['deadline_at']) <= datetime.now(timezone.utc))
    return result


def listing(user, *, preview=False):
    user = authorize(user, preview=preview)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM forms WHERE channel_id=? AND organization_id=? ORDER BY updated_at DESC,form_id', _scope(user)).fetchall()
        return {'forms': [_public(conn, dict(row)) for row in rows],
                'templates': [{'id': key, 'name': value['name']} for key, value in TEMPLATES.items()],
                'folders': [dict(folder) for folder in conn.execute('SELECT folder_id,name FROM form_folders WHERE channel_id=? AND organization_id=? ORDER BY name,folder_id', _scope(user))],
                'rules': forms_validation.configuration(),
                'capabilities': capabilities(user, preview=preview)}


def detail(user, form_id, *, preview=False):
    user = authorize(user, preview=preview)
    with app.database_connection() as conn:
        return {'form': _public(conn, _find(conn, user, form_id))}


def invitation_form(user, form_id, *, preview=False):
    """Shared gate for invitation sending; draft/stopped/expired forms cannot send."""
    user = authorize(user, 'send', preview=preview)
    with app.database_connection() as conn:
        row = _public(conn, _find(conn, user, form_id))
        if row['status'] != 'collecting' or row['expired']:
            raise ValueError('表單尚未發布、已停止收件或已截止，不能發送邀請。')
        return row


def design_impact(old_questions, new_questions):
    old = {q['id']: q for q in old_questions}
    new = {q['id']: q for q in new_questions}
    return any(key not in new or old[key]['type'] != new[key]['type'] or old[key].get('options', []) != new[key].get('options', []) for key in old)


def save_design(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'maintain', preview=preview)
    questions = forms_validation.validate_questions(payload.get('questions'))
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = _find(conn, user, payload.get('form_id'))
        import form_content
        form_content.validate_images(conn, row, questions)
        if payload.get('expected_updated_at') != row['updated_at']:
            raise ValueError('表單已由其他人更新，請重新開啟後再編輯；目前修改仍保留在畫面。')
        responses = _counts(conn, row['form_id'])['responses']
        if responses and design_impact(json.loads(row['questions_json']), questions) and payload.get('confirm_response_impact') is not True:
            raise ValueError('已有回覆，刪題、改題型或修改選項會影響新填寫者；舊答案仍依提交快照解讀。請確認後再儲存。')
        actor = actor or user['email']
        conn.execute('UPDATE forms SET questions_json=?,updated_by=?,updated_at=? WHERE form_id=?',
                     (json.dumps(questions, ensure_ascii=False), actor, datetime.now(timezone.utc).isoformat(), row['form_id']))
        _audit(conn, actor, 'design', row, f'{len(questions)} 個題目／分區')
        return {'form': _public(conn, _find(conn, user, row['form_id']))}


def preview_answers(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'view', preview=preview)
    with app.database_connection() as conn:
        row = _find(conn, user, payload.get('form_id'))
    # Unsaved designer content can be previewed without writing any business records.
    questions = forms_validation.validate_questions(payload.get('questions', json.loads(row['questions_json'])))
    import form_content
    with app.database_connection() as conn:form_content.validate_images(conn, row, questions)
    answers = payload.get('answers')
    errors = forms_validation.validate_answers(questions, answers)
    for q in questions:
        if q['type']=='attachment' and isinstance(answers,dict) and answers.get(q['id']):
            errors[q['id']]='預覽不接受正式附件，請使用公開填寫頁上傳。'
    return {'valid': not errors, 'errors': errors, 'answers': answers if not errors else None}


def _text(payload, key, maximum, *, required=False, default=''):
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        label = {'name': '表單名稱', 'description': '說明', 'submission_message': '送出後提示'}[key]
        raise ValueError(f'{label}請填寫有效文字（最多 {maximum} 字）。')
    return value.strip()


def _deadline(value):
    if value == '':
        return ''
    if not isinstance(value, str):
        raise ValueError('截止時間格式不正確。')
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        raise ValueError('截止時間需包含時區。') from None


def _audit(conn, actor, action, row, detail=''):
    reports.audit(conn, actor, 'forms.' + action, row['form_id'], row['name'] + (' · ' + detail if detail else ''), row['organization_id'])


def save(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'maintain', preview=preview)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        existing = _find(conn, user, payload.get('form_id')) if payload.get('form_id') else None
        if 'questions' in payload or 'questions_json' in payload or 'status' in payload:
            raise ValueError('題目請使用設計器；狀態請使用發布或停止收件操作。')
        template_id = payload.get('template_id', '')
        if not isinstance(template_id, str) or (template_id and (existing or template_id not in TEMPLATES)):
            raise ValueError('範本不正確。')
        template = TEMPLATES.get(template_id, {})
        defaults = existing or template
        name = _text(payload, 'name', limits.FORM_NAME_MAX, required=True, default=template.get('name', ''))
        description = _text(payload, 'description', limits.FORM_TEXT_MAX, default=defaults.get('description', ''))
        message = _text(payload, 'submission_message', limits.FORM_TEXT_MAX, default=defaults.get('submission_message', '已收到你的回覆，謝謝。'))
        deadline = _deadline(payload.get('deadline_at', defaults.get('deadline_at', '')))
        now = datetime.now(timezone.utc).isoformat()
        actor = actor or user['email']
        if existing:
            conn.execute('UPDATE forms SET name=?,description=?,deadline_at=?,submission_message=?,updated_by=?,updated_at=? WHERE form_id=?',
                         (name, description, deadline, message, actor, now, existing['form_id']))
            form_id = existing['form_id']
        else:
            _capacity(conn, user)
            form_id = uuid4().hex
            questions = copy.deepcopy(template.get('questions', []))
            conn.execute('INSERT INTO forms(form_id,channel_id,organization_id,name,description,questions_json,deadline_at,submission_message,created_by,updated_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                         (form_id, *_scope(user), name, description, json.dumps(questions, ensure_ascii=False), deadline, message, actor, actor, now, now))
        if not existing and payload.get('folder_id'):
            folder_id = payload['folder_id']
            if not isinstance(folder_id, str) or not conn.execute('SELECT 1 FROM form_folders WHERE folder_id=? AND channel_id=? AND organization_id=?', (folder_id, *_scope(user))).fetchone():
                raise PermissionError('找不到授權範圍內的資料夾。')
            conn.execute('INSERT INTO form_folder_items VALUES (?,?)', (form_id,folder_id))
        _ensure_public_link(conn,form_id)
        row = _find(conn, user, form_id)
        _audit(conn, actor, 'update' if existing else 'create', row)
        return {'form': _public(conn, row)}


def _capacity(conn, user):
    count = conn.execute('SELECT count(*) FROM forms WHERE channel_id=? AND organization_id=?', _scope(user)).fetchone()[0]
    if count >= limits.FORMS_PER_OA:
        raise ValueError(f'此 OA 最多可建立 {limits.FORMS_PER_OA} 份表單。')


def duplicate(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'maintain', preview=preview)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        original = _find(conn, user, payload.get('form_id'))
        _capacity(conn, user)
        new_id, now = uuid4().hex, datetime.now(timezone.utc).isoformat()
        name = original['name'][:limits.FORM_NAME_MAX - len('（副本）')] + '（副本）'
        actor = actor or user['email']
        conn.execute("INSERT INTO forms(form_id,channel_id,organization_id,name,description,questions_json,status,deadline_at,submission_message,created_by,updated_by,created_at,updated_at) VALUES (?,?,?,?,?,?,'draft','',?,?,?,?,?)",
                     (new_id, *_scope(user), name, original['description'], original['questions_json'], original['submission_message'], actor, actor, now, now))
        folder = conn.execute('SELECT folder_id FROM form_folder_items WHERE form_id=?', (original['form_id'],)).fetchone()
        if folder:
            conn.execute('INSERT INTO form_folder_items VALUES (?,?)', (new_id,folder[0]))
        _ensure_public_link(conn,new_id)
        row = _find(conn, user, new_id)
        _audit(conn, actor, 'copy', row)
        return {'form': _public(conn, row)}


def transition(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'publish', preview=preview)
    status = payload.get('status')
    if not isinstance(status, str) or status not in {'collecting', 'stopped'}:
        raise ValueError('請選擇發布或停止收件。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = _find(conn, user, payload.get('form_id'))
        if status == 'stopped' and row['status'] == 'draft':
            raise ValueError('草稿尚未發布。')
        if status == 'collecting':
            questions = forms_validation.validate_questions(json.loads(row['questions_json']))
            if not any(q['type'] not in forms_validation.RULES['display_types'] for q in questions):
                raise ValueError('請先新增至少一個題目。')
            if row['deadline_at'] and datetime.fromisoformat(row['deadline_at']) <= datetime.now(timezone.utc):
                raise ValueError('截止時間已過，請先調整截止時間再重新開放。')
        _ensure_public_link(conn,row['form_id'])
        actor = actor or user['email']
        conn.execute('UPDATE forms SET status=?,updated_by=?,updated_at=? WHERE form_id=?',
                     (status, actor, datetime.now(timezone.utc).isoformat(), row['form_id']))
        _audit(conn, actor, 'status', row, status)
        return {'form': _public(conn, _find(conn, user, row['form_id']))}


def delete(user, payload, *, actor=None, preview=False):
    user = authorize(user, 'maintain', preview=preview)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = _find(conn, user, payload.get('form_id'))
        counts = _counts(conn, row['form_id'])
        if payload.get('confirm_counts') != counts:
            raise ValueError('通知或回覆數量已變更，請重新確認刪除。')
        conn.execute("UPDATE form_attachments SET status='deleted' WHERE form_id=?",(row['form_id'],))
        conn.execute('DELETE FROM form_upload_drafts WHERE form_id=?',(row['form_id'],))
        conn.execute('DELETE FROM form_submissions WHERE form_id=?', (row['form_id'],))
        conn.execute('DELETE FROM form_public_links WHERE form_id=?', (row['form_id'],))
        conn.execute('DELETE FROM form_notifications WHERE form_id=?', (row['form_id'],))
        conn.execute('DELETE FROM form_folder_items WHERE form_id=?', (row['form_id'],))
        conn.execute('DELETE FROM forms WHERE form_id=?', (row['form_id'],))
        _audit(conn, actor or user['email'], 'delete', row, f"通知 {counts['notifications']}、回覆 {counts['responses']}")
    import form_attachments
    form_attachments.cleanup()
    return {'ok': True}


def folder_action(user, payload, *, actor=None, preview=False):
    """Maintain OA-scoped folders; deleting a folder never deletes its forms."""
    user = authorize(user, 'maintain', preview=preview)
    action = payload.get('action')
    if action not in ('create', 'rename', 'delete', 'move'):
        raise ValueError('資料夾操作不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        folder_id = '' if action == 'create' else payload.get('folder_id', '')
        folder = None
        if action != 'create' and (action != 'move' or folder_id != ''):
            if not isinstance(folder_id, str):
                raise PermissionError('找不到授權範圍內的資料夾。')
            folder = conn.execute('SELECT name FROM form_folders WHERE folder_id=? AND channel_id=? AND organization_id=?', (folder_id, *_scope(user))).fetchone()
            if not folder:
                raise PermissionError('找不到授權範圍內的資料夾。')
        if action in ('create', 'rename'):
            name = _text(payload, 'name', limits.FORM_NAME_MAX, required=True)
            if conn.execute('SELECT 1 FROM form_folders WHERE channel_id=? AND organization_id=? AND name=? AND folder_id<>?', (*_scope(user), name, folder_id)).fetchone():
                raise ValueError('已有同名資料夾，請使用其他名稱。')
            if action == 'create':
                folder_id = uuid4().hex
                conn.execute('INSERT INTO form_folders VALUES (?,?,?,?,?)', (folder_id,user['organization_id'],channels.current_id(),name,datetime.now(timezone.utc).isoformat()))
            else:
                conn.execute('UPDATE form_folders SET name=? WHERE folder_id=?', (name,folder_id))
        elif action == 'delete':
            conn.execute('DELETE FROM form_folder_items WHERE folder_id=?', (folder_id,))
            conn.execute('DELETE FROM form_folders WHERE folder_id=?', (folder_id,))
        else:
            row = _find(conn, user, payload.get('form_id'))
            conn.execute('DELETE FROM form_folder_items WHERE form_id=?', (row['form_id'],))
            if folder_id:
                conn.execute('INSERT INTO form_folder_items VALUES (?,?)', (row['form_id'],folder_id))
        reports.audit(conn, actor or user['email'], 'forms.folder.'+action, folder_id or payload.get('form_id',''), '問卷資料夾管理', user['organization_id'])
        return {'ok': True, 'folder_id': folder_id}

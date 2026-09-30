"""LINE account registry and request/job scope. Credentials never leave this module.

Workspace membership is evaluated on every access. ContextVar isolates HTTP threads,
webhook requests and workers; no request changes process-wide environment variables.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import os
import re
import sqlite3
import threading
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

_current = ContextVar('line_channel', default='')
_key_lock = threading.Lock()
SCOPED_TABLES = ('line_messages', 'recipients', 'subscription_commands', 'send_jobs',
                 'report_sources', 'audit_events', 'upload_assets', 'dispatch_scopes',
                 'sender_grants', 'builtin_report_state')


def current_id():
    return _current.get()


@contextmanager
def use(channel_id):
    token = _current.set(channel_id)
    try:
        yield
    finally:
        _current.reset(token)


def _rows():
    import app
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute('SELECT * FROM line_channels ORDER BY created_at,channel_id')]


def get(channel_id=None):
    channel_id = current_id() if channel_id is None else channel_id
    return next((c for c in _rows() if c['channel_id'] == channel_id), None)


def configured():
    return bool(_rows())


def cipher():
    import app
    path = app.BASE_DIR / 'instance' / 'line-credentials.key'
    with _key_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Never silently generate a replacement key for existing ciphertext.
            if any(c['token_cipher'] for c in _rows()):
                raise ValueError('OA 金鑰檔遺失，請還原 instance/line-credentials.key。')
            try:
                with path.open('xb') as stream:
                    stream.write(Fernet.generate_key())
                os.chmod(path, 0o600)
            except FileExistsError:
                pass
        return Fernet(path.read_bytes())


def _decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, OSError, ValueError):
        raise ValueError('無法解密 OA 憑證，請檢查伺服器金鑰檔。') from None


def workspace_key(channel):
    return ('o:' + channel['org_id']) if channel['org_id'] else ('p:' + channel['owner_email'])


def workspace_options(user):
    import reports
    platform = user['role'] == 'administrator'
    people = reports.users() if platform else [user]
    result = [{'id': 'p:' + p['email'], 'name': (p.get('display_name') or p['email']) + ' · 個人',
               'kind': 'personal', 'org_id': '', 'owner_email': p['email'], 'can_manage': True}
              for p in people if p.get('active', True) and reports.operator(p)]
    members = reports.memberships(user['email'])
    for org in reports.organizations():
        member = next((m for m in members if m['org_id'] == org['org_id'] and m['active']), None)
        if org['active'] and (platform or (member and member['role'] in {'company_admin', 'sender', 'employee'})):
            result.append({'id': 'o:' + org['org_id'], 'name': org['name'], 'kind': 'organization',
                           'org_id': org['org_id'], 'owner_email': '',
                           'can_manage': platform or member['role'] == 'company_admin'})
    return result


def workspace(channel, user, manage=False):
    result = next((w for w in workspace_options(user) if w['id'] == workspace_key(channel)), None)
    if not result or (manage and not result['can_manage']):
        raise ValueError('沒有此工作區的 OA 存取權限。')
    return result


def authorize(channel_id, user, *, manage=False, enabled=True):
    row = get(channel_id)
    if not row:
        raise ValueError('找不到可使用的 LINE OA。')
    workspace(row, user, manage)
    if enabled and not row['active']:
        raise ValueError('此 LINE OA 已停用。')
    return row


def operational(channel):
    import reports
    if not channel or not channel['active']:
        return False
    if channel['org_id']:
        return any(o['org_id'] == channel['org_id'] and o['active'] for o in reports.organizations())
    return any(u['email'] == channel['owner_email'] and u['active'] and reports.operator(u) for u in reports.users())


def credentials():
    row = get()
    if row:
        if not operational(row):
            raise ValueError('此 OA 或所屬工作區已停用。')
        return _decrypt(row['token_cipher']), _decrypt(row['secret_cipher'])
    if current_id() or configured():
        raise ValueError('請先選擇要使用的 LINE OA。')
    # Single-account installations remain available only until the explicit import.
    return os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '').strip(), os.environ.get('LINE_CHANNEL_SECRET', '')


def access_token():
    return credentials()[0]


def organization_id():
    row = get()
    return row['org_id'] if row else None


def personal_owner(user):
    row = get()
    return bool(row and not row['org_id'] and row['owner_email'] == user.get('email'))


def enforce_company(company):
    expected = organization_id()
    if expected is not None and company != expected:
        raise ValueError('資料必須屬於目前 OA 的工作區；請先切換工作區與 OA。')


def public(row, user):
    base = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
    w = workspace(row, user)
    fields = ('channel_id', 'name', 'bot_user_id', 'basic_id', 'active', 'verified_at', 'webhook_seen_at', 'legacy_webhook')
    return {**{k: row[k] for k in fields}, 'workspace_id': w['id'], 'workspace_name': w['name'],
            'can_manage': w['can_manage'], 'webhook_url': base + '/webhook/' + row['channel_id'],
            'credentials_set': bool(row['token_cipher'] and row['secret_cipher'])}


def catalogue(user):
    spaces = workspace_options(user)
    ids = {w['id'] for w in spaces}
    rows = _rows()
    return {'workspaces': spaces, 'channels': [public(c, user) for c in rows if workspace_key(c) in ids],
            'registry_enabled': bool(rows),
            'can_import': not rows and user['role'] == 'administrator' and bool(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))}


def _verify(token):
    import line_api
    info = line_api.request('info', token=token)
    if not re.fullmatch(r'U[0-9a-fA-F]{32}', str(info.get('userId', ''))):
        raise ValueError('LINE 未傳回有效的 OA 識別資料。')
    return info


def save(payload, user):
    """Create/rotate credentials after a read-only bot identity check. Ownership is fixed."""
    import app
    import reports
    existing = authorize(payload['channel_id'], user, manage=True, enabled=False) if payload.get('channel_id') else None
    importing = payload.get('import_existing') is True
    if importing and (configured() or user['role'] != 'administrator'):
        raise ValueError('既有 OA 只能由平台管理員首次匯入。')
    if not existing and not importing and not configured() and os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'):
        raise ValueError('請先匯入既有 OA，再新增其他 OA，以保留原本的 Webhook 入口。')
    requested = payload.get('workspace_id')
    w = next((w for w in workspace_options(user) if w['id'] == requested and w['can_manage']), None)
    if not w or (existing and workspace_key(existing) != requested):
        raise ValueError('請選擇有管理權限的工作區；建立後不能移轉 OA 歸屬。')
    secret = payload.get('secret', '')
    token = payload.get('access_token', '')
    name = payload.get('name', '')
    active = payload.get('active', True)
    if any(not isinstance(v, str) for v in (secret, token, name)) or type(active) is not bool:
        raise ValueError('OA 設定格式不正確。')
    if len(token) > 4096 or len(name.strip()) > 80:
        raise ValueError('OA 名稱或憑證長度不正確。')
    if importing:
        token, secret = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', ''), os.environ.get('LINE_CHANNEL_SECRET', '')
    elif existing:
        token = token.strip() or _decrypt(existing['token_cipher'])
        secret = secret.strip() or _decrypt(existing['secret_cipher'])
    if not token.strip() or not re.fullmatch(r'[0-9a-fA-F]{32}', secret.strip()):
        raise ValueError('請填入 Channel access token 與 32 位 Channel secret。')
    info = _verify(token.strip())
    if existing and info['userId'] != existing['bot_user_id']:
        raise ValueError('這組 Token 屬於不同 OA，請新增另一個 OA。')
    channel_id = existing['channel_id'] if existing else uuid4().hex
    crypto = cipher()
    now = datetime.now(timezone.utc).isoformat()
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if importing and conn.execute('SELECT 1 FROM line_channels').fetchone():
            raise ValueError('既有 OA 已由另一個操作匯入，請重新整理。')
        try:
            conn.execute('''INSERT INTO line_channels(channel_id,org_id,owner_email,name,bot_user_id,basic_id,
                            token_cipher,secret_cipher,active,verified_at,legacy_webhook)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET
                            name=excluded.name,token_cipher=excluded.token_cipher,secret_cipher=excluded.secret_cipher,
                            active=excluded.active,verified_at=excluded.verified_at,basic_id=excluded.basic_id''',
                         (channel_id, w['org_id'], w['owner_email'], name.strip() or info.get('displayName', 'LINE OA'),
                          info['userId'], info.get('basicId', ''), crypto.encrypt(token.strip().encode()).decode(),
                          crypto.encrypt(secret.strip().encode()).decode(), int(active), now, int(importing)))
        except sqlite3.IntegrityError:
            raise ValueError('這個 OA 已登記在平台上，不能重複加入其他工作區。') from None
        if importing:
            for table in SCOPED_TABLES:
                conn.execute(f"UPDATE {table} SET channel_id=? WHERE channel_id=''", (channel_id,))
            conn.execute('UPDATE recipients SET company=? WHERE channel_id=?', (w['org_id'], channel_id))
            conn.execute('UPDATE report_sources SET company=? WHERE channel_id=?', (w['org_id'], channel_id))
            conn.execute('UPDATE upload_assets SET company=? WHERE channel_id=?', (w['org_id'], channel_id))
            conn.execute('UPDATE send_jobs SET company=? WHERE channel_id=?', (w['org_id'], channel_id))
        # Registry audit is platform-scoped; no credentials or API responses are stored in it.
        reports.audit(conn, user['email'], 'oa.save', channel_id, '更新 LINE OA 設定', w['org_id'])
    return public(get(channel_id), user)


def set_active(payload, user):
    import app
    import reports
    row = authorize(payload.get('channel_id'), user, manage=True, enabled=False)
    if type(payload.get('active')) is not bool:
        raise ValueError('請指定 OA 啟用狀態。')
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET active=? WHERE channel_id=?', (int(payload['active']), row['channel_id']))
        reports.audit(conn, user['email'], 'oa.active', row['channel_id'], '啟用' if payload['active'] else '停用', row['org_id'])
    return {'ok': True}


def verify(channel_id, user):
    import app
    row = authorize(channel_id, user, manage=True, enabled=False)
    info = _verify(_decrypt(row['token_cipher']))
    if info['userId'] != row['bot_user_id']:
        raise ValueError('OA 身分與登記資料不一致。')
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET verified_at=? WHERE channel_id=?', (datetime.now(timezone.utc).isoformat(), channel_id))
    return {'ok': True, 'name': info.get('displayName', ''), 'note': 'Token 可連線；Channel secret 須以 LINE Webhook 驗證確認。'}


def webhook_channel(path):
    if path == '/webhook':
        row = next((c for c in _rows() if c['legacy_webhook']), None)
        if row:
            return row
        if not configured():
            return None
    else:
        match = re.fullmatch(r'/webhook/([0-9a-f]{32})', path)
        row = get(match[1]) if match else None
        if row:
            return row
    raise ValueError('找不到此 Webhook。')


def seen(channel_id):
    import app
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET webhook_seen_at=? WHERE channel_id=?', (datetime.now(timezone.utc).isoformat(), channel_id))

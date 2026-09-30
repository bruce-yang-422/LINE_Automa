"""LINE account registry and request/job scope. Credentials never leave this module.

Workspace membership is evaluated on every access. ContextVar isolates HTTP threads,
webhook requests and workers; no request changes process-wide environment variables.

A "usage row" is what request/job code sees as an OA: the owner's own row (scope id =
channel_id) or a share (scope id = share_id) whose org/owner is the receiving workspace.
Shares reuse the owner's credentials but keep their own recipients, reports and jobs.
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


def _owners():
    import app
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute('SELECT * FROM line_channels ORDER BY created_at,channel_id')]


def _shares(channel_id=None):
    import app
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = 'SELECT * FROM line_channel_shares' + (' WHERE channel_id=?' if channel_id else '') + ' ORDER BY created_at,share_id'
        return [dict(r) for r in conn.execute(sql, (channel_id,) if channel_id else ())]


def _rows():
    """Owner rows plus active shares, each addressed by its own scope id."""
    owners = _owners()
    by_id = {c['channel_id']: c for c in owners}
    rows = [{**c, 'base_id': c['channel_id'], 'shared': False} for c in owners]
    for s in _shares():
        base = by_id.get(s['channel_id'])
        if base and s['active']:
            rows.append({**base, 'channel_id': s['share_id'], 'base_id': base['channel_id'], 'shared': True,
                         'org_id': s['org_id'], 'owner_email': s['owner_email'], 'legacy_webhook': 0,
                         'created_at': s['created_at']})
    return rows


def get(channel_id=None):
    channel_id = current_id() if channel_id is None else channel_id
    return next((c for c in _rows() if c['channel_id'] == channel_id), None)


def owner(channel_id):
    return next((c for c in _owners() if c['channel_id'] == channel_id), None)


def configured():
    return bool(_owners())


def cipher():
    import app
    path = app.BASE_DIR / 'instance' / 'line-credentials.key'
    with _key_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Never silently generate a replacement key for existing ciphertext.
            if any(c['token_cipher'] for c in _owners()):
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
    # A share stops when the owning workspace can no longer use its own OA.
    if channel.get('shared') and not operational({**owner(channel['base_id']), 'shared': False}):
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


def workspace_name(org_id, owner_email):
    import reports
    if org_id:
        return next((o['name'] for o in reports.organizations() if o['org_id'] == org_id), org_id)
    person = next((u for u in reports.users() if u['email'] == owner_email), None)
    return ((person or {}).get('display_name') or owner_email) + ' · 個人'


def _assigned_counts(channel_id):
    import app
    with app.database_connection() as conn:
        return dict(conn.execute('''SELECT s.share_id,count(r.recipient_id) FROM line_channel_shares s
                                    LEFT JOIN recipients r ON r.channel_id=s.share_id
                                    WHERE s.channel_id=? GROUP BY s.share_id''', (channel_id,)).fetchall())


def public(row, user):
    base = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
    w = workspace(row, user)
    fields = ('channel_id', 'name', 'bot_user_id', 'basic_id', 'active', 'verified_at', 'webhook_seen_at', 'legacy_webhook')
    result = {**{k: row[k] for k in fields}, 'workspace_id': w['id'], 'workspace_name': w['name'],
              'shared': row['shared'], 'can_manage': w['can_manage'] and not row['shared'],
              'webhook_url': '' if row['shared'] else base + '/webhook/' + row['channel_id'],
              'credentials_set': bool(row['token_cipher'] and row['secret_cipher'])}
    if row['shared']:
        base_row = owner(row['base_id'])
        result['owner_workspace_name'] = workspace_name(base_row['org_id'], base_row['owner_email'])
    elif result['can_manage']:
        counts = _assigned_counts(row['channel_id'])
        result['shares'] = [{'share_id': s['share_id'], 'workspace_id': workspace_key(s), 'active': bool(s['active']),
                             'workspace_name': workspace_name(s['org_id'], s['owner_email']),
                             'recipients': counts.get(s['share_id'], 0)} for s in _shares(row['channel_id'])]
    return result


def catalogue(user):
    spaces = workspace_options(user)
    ids = {w['id'] for w in spaces}
    rows = _rows()
    return {'workspaces': spaces, 'channels': [public(c, user) for c in rows if workspace_key(c) in ids],
            'registry_enabled': bool(rows),
            'can_import': not rows and user['role'] == 'administrator' and bool(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))}


def _owned(channel_id, user, *, manage=True):
    """Credential, share and transfer operations only apply to the owner's own row."""
    row = authorize(channel_id, user, manage=manage, enabled=False)
    if row['shared']:
        raise ValueError('這是其他工作區共用給你的 OA；憑證、Webhook 與共用設定由擁有者管理。')
    return row


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
    existing = _owned(payload['channel_id'], user) if payload.get('channel_id') else None
    importing = payload.get('import_existing') is True
    if importing and (configured() or user['role'] != 'administrator'):
        raise ValueError('既有 OA 只能由平台管理員首次匯入。')
    if not existing and not importing and not configured() and os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'):
        raise ValueError('請先匯入既有 OA，再新增其他 OA，以保留原本的 Webhook 入口。')
    requested = payload.get('workspace_id')
    w = next((w for w in workspace_options(user) if w['id'] == requested and w['can_manage']), None)
    if not w or (existing and workspace_key(existing) != requested):
        raise ValueError('請選擇有管理權限的工作區；要變更歸屬請使用「移轉歸屬」。')
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
            raise ValueError('這個 OA 已登記在平台上；要讓其他工作區使用，請由擁有者設定共用。') from None
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
    row = _owned(payload.get('channel_id'), user)
    if type(payload.get('active')) is not bool:
        raise ValueError('請指定 OA 啟用狀態。')
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET active=? WHERE channel_id=?', (int(payload['active']), row['channel_id']))
        reports.audit(conn, user['email'], 'oa.active', row['channel_id'], '啟用' if payload['active'] else '停用', row['org_id'])
    return {'ok': True}


def verify(channel_id, user):
    import app
    row = _owned(channel_id, user)
    info = _verify(_decrypt(row['token_cipher']))
    if info['userId'] != row['bot_user_id']:
        raise ValueError('OA 身分與登記資料不一致。')
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET verified_at=? WHERE channel_id=?', (datetime.now(timezone.utc).isoformat(), channel_id))
    return {'ok': True, 'name': info.get('displayName', ''), 'note': 'Token 可連線；Channel secret 須以 LINE Webhook 驗證確認。'}


def webhook_channel(path):
    """Only real OA rows receive webhooks; share ids are never webhook paths."""
    if path == '/webhook':
        row = next((c for c in _owners() if c['legacy_webhook']), None)
    else:
        match = re.fullmatch(r'/webhook/([0-9a-f]{32})', path)
        row = owner(match[1]) if match else None
    if row:
        return {**row, 'base_id': row['channel_id'], 'shared': False}
    if path == '/webhook' and not configured():
        return None
    raise ValueError('找不到此 Webhook。')


def seen(channel_id):
    import app
    with app.database_connection() as conn:
        conn.execute('UPDATE line_channels SET webhook_seen_at=? WHERE channel_id=?', (datetime.now(timezone.utc).isoformat(), channel_id))


# Scope ids of the shares of the OA in the current (owner) context, for SQL IN clauses.
SHARE_SCOPES = 'SELECT share_id FROM line_channel_shares WHERE line_channel_shares.channel_id=current_channel()'


def _platform(user):
    if not user or user['role'] != 'administrator':
        raise ValueError('OA 共用與移轉歸屬由平台管理員操作。')


def _target(workspace_id, user):
    w = next((w for w in workspace_options(user) if w['id'] == workspace_id), None)
    if not w:
        raise ValueError('請選擇有效的目標工作區。')
    return w


def share(payload, user):
    """Start, pause or resume another workspace's use of an OA; pausing keeps its data."""
    import app
    import reports
    _platform(user)
    row = _owned(payload.get('channel_id'), user)
    active = payload.get('active', True)
    if type(active) is not bool:
        raise ValueError('請指定共用狀態。')
    w = _target(payload.get('workspace_id'), user)
    if w['id'] == workspace_key(row):
        raise ValueError('擁有者工作區本身就能使用此 OA，不需要共用。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        found = conn.execute('SELECT share_id FROM line_channel_shares WHERE channel_id=? AND org_id=? AND owner_email=?',
                             (row['channel_id'], w['org_id'], w['owner_email'])).fetchone()
        if found:
            share_id = found[0]
            conn.execute('UPDATE line_channel_shares SET active=? WHERE share_id=?', (int(active), share_id))
        elif active:
            share_id = uuid4().hex
            conn.execute('INSERT INTO line_channel_shares(share_id,channel_id,org_id,owner_email,created_by) VALUES (?,?,?,?,?)',
                         (share_id, row['channel_id'], w['org_id'], w['owner_email'], user['email']))
        else:
            raise ValueError('尚未共用給此工作區。')
        reports.audit(conn, user['email'], 'oa.share', row['channel_id'],
                      ('共用給 ' if active else '停止共用給 ') + w['name'], row['org_id'])
    return {'share_id': share_id, 'workspace_id': w['id'], 'active': active}


def _share_row(share_id, user):
    s = next((s for s in _shares() if s['share_id'] == share_id), None)
    if not s:
        raise ValueError('找不到此共用設定。')
    # Recipients are distributed by whoever manages the owning workspace.
    return s, _owned(s['channel_id'], user)


def share_recipients(share_id, user):
    import app
    s, base = _share_row(share_id, user)
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        assigned = {r[0] for r in conn.execute('SELECT recipient_id FROM recipients WHERE channel_id=?', (share_id,))}
        rows = conn.execute('''SELECT recipient_id,kind,display_name,alias,active FROM recipients WHERE channel_id=?
                               ORDER BY kind,COALESCE(NULLIF(alias,''),NULLIF(display_name,''),recipient_id)''', (base['channel_id'],))
        contacts = [{**dict(r), 'assigned': r['recipient_id'] in assigned} for r in rows]
    return {'share_id': share_id, 'workspace_name': workspace_name(s['org_id'], s['owner_email']),
            'oa_name': base['name'], 'recipients': contacts}


def assign(payload, user):
    """Set exactly which owner recipients the shared workspace may see and send to."""
    import app
    import reports
    s, base = _share_row(payload.get('share_id'), user)
    ids = payload.get('recipient_ids')
    if not isinstance(ids, list) or len(ids) > 10000 or any(not isinstance(i, str) for i in ids):
        raise ValueError('收件者清單格式不正確。')
    wanted = set(ids)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        owned = {r[0] for r in conn.execute('SELECT recipient_id FROM recipients WHERE channel_id=?', (base['channel_id'],))}
        if wanted - owned:
            raise ValueError('只能指派此 OA 名單中的收件者。')
        current = {r[0] for r in conn.execute('SELECT recipient_id FROM recipients WHERE channel_id=?', (s['share_id'],))}
        # Copies carry LINE-side state only; alias, department and subscriptions belong to the receiving workspace.
        for rid in sorted(wanted - current):
            conn.execute('''INSERT INTO recipients(channel_id,recipient_id,kind,display_name,active,event_at,
                                                   profile_checked_at,profile_next_at,company)
                            SELECT ?,recipient_id,kind,display_name,active,event_at,profile_checked_at,profile_next_at,?
                            FROM recipients WHERE channel_id=? AND recipient_id=?''',
                         (s['share_id'], s['org_id'], base['channel_id'], rid))
        conn.executemany('DELETE FROM recipients WHERE channel_id=? AND recipient_id=?',
                         [(s['share_id'], rid) for rid in sorted(current - wanted)])
        reports.audit(conn, user['email'], 'oa.share.recipients', s['share_id'],
                      f'指派 {len(wanted)} 位收件者給 {workspace_name(s["org_id"], s["owner_email"])}', base['org_id'])
    return {'assigned': len(wanted), 'added': len(wanted - current), 'removed': len(current - wanted)}


def transfer(payload, user):
    """Move an OA to another workspace. Without confirm=True only the impact is returned."""
    import app
    import reports
    _platform(user)
    row = _owned(payload.get('channel_id'), user)
    w = _target(payload.get('workspace_id'), user)
    if w['id'] == workspace_key(row):
        raise ValueError('OA 已屬於此工作區。')
    if any(workspace_key(s) == w['id'] for s in _shares(row['channel_id'])):
        raise ValueError('目標工作區目前以共用方式使用此 OA，不能同時成為擁有者。')
    cid, company = row['channel_id'], w['org_id']
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        def count(sql):
            return conn.execute(sql, (cid,)).fetchone()[0]
        impact = {'from': workspace_name(row['org_id'], row['owner_email']), 'to': w['name'],
                  'pending_jobs': count("SELECT count(*) FROM send_jobs WHERE channel_id=? AND status IN ('scheduled','queued','running')"),
                  'recipients': count('SELECT count(*) FROM recipients WHERE channel_id=?'),
                  'reports': count('SELECT count(*) FROM report_sources WHERE channel_id=?'),
                  'assets': count('SELECT count(*) FROM upload_assets WHERE channel_id=?'),
                  'jobs': count('SELECT count(*) FROM send_jobs WHERE channel_id=?'),
                  'dispatch_scopes': count('SELECT count(*) FROM dispatch_scopes WHERE channel_id=?'),
                  'sender_grants': count('SELECT count(*) FROM sender_grants WHERE channel_id=?'),
                  'shares': count('SELECT count(*) FROM line_channel_shares WHERE channel_id=? AND active=1')}
        if payload.get('confirm') is not True:
            return {**impact, 'transferred': False}
        if impact['pending_jobs']:
            raise ValueError(f'還有 {impact["pending_jobs"]} 筆預約或進行中的發送，請先取消或等它完成再移轉。')
        conn.execute('UPDATE line_channels SET org_id=?,owner_email=? WHERE channel_id=?', (w['org_id'], w['owner_email'], cid))
        # Departments, scopes and sender grants describe the previous workspace's people; they do not carry over.
        conn.execute("UPDATE recipients SET company=?,department='' WHERE channel_id=?", (company, cid))
        conn.execute("""UPDATE report_sources SET company=?,scope='company',department='',owner_email='',owner_recipient_id=''
                        WHERE channel_id=?""", (company, cid))
        conn.execute('UPDATE upload_assets SET company=? WHERE channel_id=?', (company, cid))
        conn.execute('UPDATE send_jobs SET company=? WHERE channel_id=?', (company, cid))
        conn.execute('DELETE FROM dispatch_scopes WHERE channel_id=?', (cid,))
        conn.execute('DELETE FROM sender_grants WHERE channel_id=?', (cid,))
        reports.audit(conn, user['email'], 'oa.transfer', cid, f'{impact["from"]} → {impact["to"]}', company)
    return {**impact, 'transferred': True, 'workspace_id': w['id'], 'channel_id': cid}

"""Website credentials and revocable opaque sessions."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
from http.cookies import SimpleCookie, CookieError

import app
import reports

HASH_SLOTS = threading.BoundedSemaphore(2)
SESSION_SECONDS = 12 * 3600
REMEMBER_SECONDS = 30 * 86400
IDLE_SECONDS = 2 * 3600
REMEMBER_IDLE = 7 * 86400
COOKIE_REMOTE = '__Host-line_session'
COOKIE_LOCAL = 'line_local_session'


class AuthError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def email_value(value):
    if not isinstance(value, str) or len(value) > 254:
        raise AuthError('請輸入完整 Email。')
    value = value.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise AuthError('請輸入完整 Email。')
    return value


def password_value(value):
    if not isinstance(value, str) or not 15 <= len(value) <= 128:
        raise AuthError('密碼請使用 15～128 個字元，可使用一段容易記住的句子。')
    if len(set(value)) < 5 or value.lower() in {'123456789012345', 'passwordpassword', 'qwertyuiopasdfgh'}:
        raise AuthError('請使用較不容易猜中的密碼或句子。')
    return value


def derive(password, salt):
    if not HASH_SLOTS.acquire(blocking=False):
        raise AuthError('登入服務忙碌，請稍後重試。', 429)
    try:
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**17, r=8, p=1,
                              maxmem=256*1024*1024, dklen=32).hex()
    finally:
        HASH_SLOTS.release()


def hash_password(password):
    password_value(password)
    salt = secrets.token_hex(16)
    return 'scrypt17$' + salt + '$' + derive(password, salt)


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 128:
        return False
    # Unknown accounts perform the same expensive derivation without a real credential.
    parts = (encoded or ('scrypt17$' + '00'*16 + '$' + '00'*32)).split('$')
    if len(parts) != 3 or parts[0] != 'scrypt17':
        return False
    return hmac.compare_digest(derive(password, parts[1]), parts[2]) and bool(encoded)


def credential(email):
    with app.database_connection() as conn:
        row = conn.execute('SELECT password_hash FROM site_credentials WHERE email=?', (email,)).fetchone()
    return row[0] if row else None


def limit_login(email, client):
    now = int(time.time())
    buckets = [('global', 300), ('ip:'+digest(client), 40), ('email:'+digest(email), 10)]
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM site_login_limits WHERE started_at<?', (now-900,))
        for bucket, limit in buckets:
            row = conn.execute('SELECT attempts FROM site_login_limits WHERE bucket=?', (bucket,)).fetchone()
            if row and row[0] >= limit:
                raise AuthError('登入嘗試過於頻繁，請於 15 分鐘後再試。', 429)
        for bucket, _ in buckets:
            conn.execute('INSERT INTO site_login_limits VALUES (?,?,1) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1', (bucket,now))


def login(email, password, remember, client):
    email = email_value(email)
    if type(remember) is not bool:
        raise AuthError('登入設定格式不正確。')
    limit_login(email, client)
    encoded = credential(email)
    valid = verify_password(password, encoded)
    if not valid or not reports.login_account(email):
        raise AuthError('Email 或密碼不正確，或此帳號尚未取得後台登入資格。', 401)
    now = int(time.time())
    raw = secrets.token_urlsafe(32)
    lifetime = REMEMBER_SECONDS if remember else SESSION_SECONDS
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT password_hash FROM site_credentials WHERE email=?', (email,)).fetchone()
        if not current or not hmac.compare_digest(encoded, current[0]):
            raise AuthError('登入資料已變更，請重新登入。', 401)
        if not reports.login_account(email):
            raise AuthError('此帳號已無後台登入資格。',401)
        conn.execute('DELETE FROM site_sessions WHERE expires_at<=? OR last_seen+idle_seconds<=?', (now,now))
        conn.execute('INSERT INTO site_sessions VALUES (?,?,?,?,?,?)',
                     (digest(raw),email,now,now,now+lifetime,REMEMBER_IDLE if remember else IDLE_SECONDS))
        conn.execute('DELETE FROM site_login_limits WHERE bucket=?', ('email:'+digest(email),))
        reports.audit(conn,email,'auth.login',email,'網站帳密登入')
    return raw, lifetime


def session(raw):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', raw or ''):
        return None
    now = int(time.time())
    with app.database_connection() as conn:
        row = conn.execute('SELECT email,last_seen,expires_at,idle_seconds FROM site_sessions WHERE token_hash=?', (digest(raw),)).fetchone()
        if not row or row[2] <= now or row[1]+row[3] <= now:
            return None
        user = reports.login_account(row[0])
        if not user:
            conn.execute('DELETE FROM site_sessions WHERE token_hash=?', (digest(raw),))
            return None
        if row[1] < now-60:
            conn.execute('UPDATE site_sessions SET last_seen=? WHERE token_hash=?', (now,digest(raw)))
    return user


def revoke(email, actor):
    with app.database_connection() as conn:
        conn.execute('DELETE FROM site_sessions WHERE email=?', (email,))
        conn.execute('DELETE FROM site_activation WHERE email=?', (email,))
        reports.audit(conn,actor,'auth.revoke',email,'撤銷所有網站登入及啟用連結')


def issue_activation(email, actor):
    email = email_value(email)
    if not reports.login_account(email):
        raise AuthError('請先建立並啟用具後台資格的帳號。')
    raw = secrets.token_urlsafe(32)
    with app.database_connection() as conn:
        conn.execute('DELETE FROM site_activation WHERE email=? OR expires_at<=?', (email,int(time.time())))
        conn.execute('INSERT INTO site_activation VALUES (?,?,?)', (digest(raw),email,int(time.time())+1800))
        reports.audit(conn,actor,'auth.activation',email,'產生 30 分鐘一次性密碼設定連結')
    return raw


def activate(raw, password):
    if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', raw):
        raise AuthError('設定連結已失效，請向管理員重新取得。')
    with app.database_connection() as conn:
        row = conn.execute('SELECT email,expires_at FROM site_activation WHERE token_hash=?', (digest(raw),)).fetchone()
    if not row or row[1] <= time.time() or not reports.login_account(row[0]):
        raise AuthError('設定連結已失效，請向管理員重新取得。')
    encoded = hash_password(password)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not reports.login_account(row[0]):
            raise AuthError('此帳號已無後台登入資格。',401)
        if not conn.execute('DELETE FROM site_activation WHERE token_hash=? AND expires_at>?', (digest(raw),int(time.time()))).rowcount:
            raise AuthError('設定連結已失效，請向管理員重新取得。')
        set_credential(conn,row[0],encoded)
        reports.audit(conn,row[0],'auth.password',row[0],'透過一次性連結設定密碼；撤銷既有登入')


def set_credential(conn, email, encoded):
    conn.execute('INSERT INTO site_credentials VALUES (?,?,?) ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,changed_at=excluded.changed_at', (email,encoded,int(time.time())))
    conn.execute('DELETE FROM site_sessions WHERE email=?', (email,))
    conn.execute('DELETE FROM site_activation WHERE email=?', (email,))


def change_password(email, current_password, new_password):
    email = email_value(email)
    previous = credential(email)
    if previous and not verify_password(current_password,previous):
        raise AuthError('目前密碼不正確。')
    encoded = hash_password(new_password)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT password_hash FROM site_credentials WHERE email=?', (email,)).fetchone()
        if (row[0] if row else None) != previous:
            raise AuthError('密碼已變更，請重新操作。')
        set_credential(conn,email,encoded)
        reports.audit(conn,email,'auth.password',email,'更新網站密碼；撤銷既有登入')


def context(handler):
    """Public login endpoints still reject unknown hosts, HTTP proxying and duplicate headers."""
    for name in ('Host','Origin','Authorization','Cookie','Content-Length','X-CSRF-Token','X-Forwarded-Proto','CF-Connecting-IP'):
        if len(handler.headers.get_all(name, [])) > 1:
            raise AuthError('不接受重複的驗證標頭。',403)
    host = handler.headers.get('Host','')
    public = handler.server.public_host
    if public and re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',public) and host.lower() == public:
        if handler.headers.get('X-Forwarded-Proto') != 'https':
            raise AuthError('請透過 HTTPS 管理網址操作。',403)
        origin = 'https://' + public
        remote = True
    elif host == f'127.0.0.1:{handler.server.server_port}' and not any(h in handler.headers for h in ('CF-Connecting-IP','X-Forwarded-For','X-Forwarded-Proto')):
        origin, remote = 'http://' + host, False
    else:
        raise AuthError('請使用已設定的管理網址。',403)
    supplied = handler.headers.get('Origin')
    if (supplied and supplied != origin) or (handler.command == 'POST' and supplied != origin):
        raise AuthError('請從同一個管理網站送出操作。',403)
    return remote, origin


def cookie_token(handler, remote):
    value = handler.headers.get('Cookie','')
    if len(value)>8192:
        return ''
    name = COOKIE_REMOTE if remote else COOKIE_LOCAL
    if len(re.findall(r'(?:^|;)\s*'+re.escape(name)+r'=',value)) != 1:
        return ''
    jar = SimpleCookie()
    try:
        jar.load(value)
        return jar[name].value if name in jar else ''
    except CookieError:
        return ''


def csrf(raw):
    return hmac.new(raw.encode(), b'line-workspace-csrf', hashlib.sha256).hexdigest()


def set_cookie(handler, raw, remote, max_age=None):
    name = COOKIE_REMOTE if remote else COOKIE_LOCAL
    value = f'{name}={raw}; Path=/; HttpOnly; SameSite=Lax'
    if remote:
        value += '; Secure'
    if max_age is not None:
        value += f'; Max-Age={max_age}'
    handler.response_cookie = value


def authorize(handler):
    try:
        remote, _ = context(handler)
        raw = cookie_token(handler,remote)
        user = session(raw)
        if not user:
            if handler.command == 'GET' and handler.path in {'/','/index.html'}:
                handler.send_response(303)
                handler.send_header('Location','/login')
                handler.send_header('Cache-Control','no-store')
                handler.send_header('Content-Length','0')
                handler.end_headers()
                return False
            raise AuthError('登入已逾時，請重新登入。',401)
        if handler.command == 'POST' and not hmac.compare_digest(handler.headers.get('X-CSRF-Token','').encode(),csrf(raw).encode()):
            raise AuthError('操作驗證已失效，請重新整理。',403)
        handler.identity, handler.user = user['email'], user
        handler.auth_method, handler.auth_token = 'password', raw
        return handler.apply_view()
    except AuthError as exc:
        handler.respond(exc.status,{'error':str(exc),'login_url':'/login'})
        return False


def status(handler):
    method = getattr(handler,'auth_method','local')
    principal = getattr(handler,'principal',handler.identity)
    return {'method':method,
            'password_set':bool(credential(principal)) if handler.server.workspace_ready else False,
            'csrf':csrf(handler.auth_token) if method=='password' else ''}


def handle_get(handler):
    paths = {'/login':('login.html','text/html; charset=utf-8'),'/login.js':('login.js','text/javascript; charset=utf-8')}
    assets = {'/app.css','/favicon.ico'}
    public_asset = handler.path in assets or re.fullmatch(r'/assets/brand/line-automation-logo-light\.(png|ico)',handler.path)
    if handler.path not in paths and handler.path!='/api/auth/setup-state' and not public_asset:
        return False
    try:
        context(handler)
        if handler.path=='/api/auth/setup-state':
            # 尚無平台管理員時，登入頁只顯示「系統尚未完成初始設定」。
            handler.respond(200,{'initialized':reports.has_platform_admin()})
            return True
        name,mime = paths.get(handler.path,('',''))
        if not name:
            name = handler.path.lstrip('/')
            if handler.path=='/favicon.ico':name='assets/brand/line-automation-logo-light.ico'
            mime = 'text/css; charset=utf-8' if name.endswith('.css') else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'image/png' if name.endswith('.png') else 'image/x-icon'
        handler.respond(200,(app.BASE_DIR/'web'/name).read_bytes(),mime)
    except AuthError as exc:
        handler.respond(exc.status,{'error':str(exc)})
    return True


def handle_post(handler):
    if not handler.path.startswith('/api/auth/'):
        return False
    try:
        remote, origin = context(handler)
        size = int(handler.headers.get('Content-Length','0'))
        if not 0<size<=8192 or handler.headers.get_content_type()!='application/json' or handler.headers.get('Transfer-Encoding'):
            raise AuthError('請求格式不正確。')
        payload = json.loads(handler.rfile.read(size))
        if not isinstance(payload,dict):raise AuthError('請求格式不正確。')
        client = handler.headers.get('CF-Connecting-IP','remote') if remote else 'local'
        if handler.path=='/api/auth/login':
            raw,lifetime = login(payload.get('email'),payload.get('password'),payload.get('remember',False),client)
            set_cookie(handler,raw,remote,lifetime if payload.get('remember') else None)
            handler.respond(200,{'ok':True})
        elif handler.path=='/api/auth/activate':
            limit_login('activation',client)
            activate(payload.get('token'),payload.get('password'))
            set_cookie(handler,'',remote,0)
            handler.respond(200,{'ok':True})
        else:
            if not handler.authorized():return True
            if handler.preview:raise AuthError('請返回原帳號操作登入設定。',403)
            if handler.path=='/api/auth/logout':
                raw = getattr(handler,'auth_token','')
                with app.database_connection() as conn:
                    conn.execute('DELETE FROM site_sessions WHERE token_hash=?',(digest(raw),))
                set_cookie(handler,'',remote,0)
                handler.respond(200,{'ok':True})
            elif handler.path=='/api/auth/password':
                limit_login(handler.identity,client)
                change_password(handler.identity,payload.get('current_password'),payload.get('password'))
                set_cookie(handler,'',remote,0)
                handler.respond(200,{'ok':True})
            elif handler.path in {'/api/auth/invite','/api/auth/revoke'}:
                target = email_value(payload.get('email'))
                own_revoke = handler.path.endswith('/revoke') and target==handler.principal
                can_manage = handler.user['role']=='platform_admin'
                if handler.user['role']=='org_admin':
                    org_id = handler.user.get('organization_id')
                    account = next((u for u in reports.users() if u['email']==target),None)
                    member = reports.account(target,org_id)
                    # Password setup affects the entire account, including other memberships.
                    can_manage = bool(account and account['organization_id']==org_id
                                      and account['role'] in {'operator','collaborator'}
                                      and member and member['role'] in {'operator','collaborator'}
                                      and not any(m['active'] and m['org_id']!=org_id
                                                  for m in reports.memberships(target)))
                if not can_manage and not own_revoke:
                    raise AuthError('只能管理本組織的操作或協作人員登入；跨組織帳號請由平台管理員處理。',403)
                if handler.path.endswith('/invite'):
                    raw = issue_activation(target,handler.identity)
                    public = handler.server.public_host
                    link_origin = 'https://'+public if re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',public) else origin
                    handler.respond(200,{'url':link_origin+'/login#setup='+raw,'local_url':origin+'/login#setup='+raw if not remote else '', 'expires_in':1800})
                else:
                    revoke(target,handler.identity)
                    handler.respond(200,{'ok':True})
            else:handler.respond(404,{'error':'找不到操作。'})
    except AuthError as exc:
        handler.respond(exc.status,{'error':str(exc)})
    except (ValueError,TypeError):
        handler.respond(400,{'error':'請求格式不正確。'})
    except (OSError,sqlite3.Error):
        handler.respond(500,{'error':'登入服務暫時無法使用，請稍後再試。'})
    return True

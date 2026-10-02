"""Private report catalogue, versioned previews, and workspace access."""

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
from uuid import uuid4

import app
import channels

MAX_BYTES = 1_000_000
CATEGORIES = {"weather": "天氣報告", "company": "組織報表", "other": "其他報告"}


def bootstrap_users(emails):
    with app.database_connection() as conn:
        conn.executemany("INSERT OR IGNORE INTO workspace_users(email,role) VALUES (?,'platform_admin')", [(email,) for email in emails])


def has_platform_admin():
    with app.database_connection() as conn:
        return bool(conn.execute("SELECT 1 FROM workspace_users WHERE role='platform_admin' AND active=1").fetchone())


def create_platform_admin(email, display_name, actor):
    """首次設定與 create_admin.py：新增或重新啟用平台管理員；密碼由本人透過一次性連結設定。"""
    email = str(email or '').strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError('請填入完整 Email。')
    if not isinstance(display_name, str) or len(display_name.strip()) > 80:
        raise ValueError('顯示名稱請限制在 80 字以內。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT role,active FROM workspace_users WHERE email=?', (email,)).fetchone()
        if row and row[0] != 'platform_admin':
            raise ValueError('此 Email 已是組織帳號，平台管理員請使用另一個 Email。')
        conn.execute("""INSERT INTO workspace_users(email,role,display_name,active) VALUES (?,'platform_admin',?,1)
                        ON CONFLICT(email) DO UPDATE SET active=1,
                        display_name=CASE WHEN excluded.display_name<>'' THEN excluded.display_name ELSE workspace_users.display_name END""",
                     (email, display_name.strip()))
        detail = '建立平台管理員' if not row else ('重新啟用平台管理員' if not row[1] else '平台管理員重設密碼')
        audit(conn, actor, 'platform_admin.setup', email, detail)
    return email


def users():
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM workspace_users ORDER BY role,email")]


def organizations():
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        return [dict(r) for r in conn.execute('SELECT * FROM organizations ORDER BY name,org_id')]


def memberships(email=None):
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        sql='SELECT m.*,o.name,o.kind,o.active AS org_active FROM organization_members m JOIN organizations o ON o.org_id=m.org_id'
        return [dict(r) for r in conn.execute(sql+(' WHERE m.email=?' if email else '')+' ORDER BY o.name,m.email', (email,) if email else ())]


def account(email, organization_id=None):
    user=next((u for u in users() if u['email']==email and u['active']),None)
    if not user or user['role']=='platform_admin':
        return user
    choices=[m for m in memberships(email) if m['active'] and m['org_active']]
    selected=next((m for m in choices if m['org_id']==(organization_id if organization_id is not None else user['organization_id'])),None)
    if selected is None and organization_id is None:
        selected=next(iter(choices),None)
    if not selected:
        return None
    return {**user,'role':selected['role'],'organization_id':selected['org_id'],'department':selected['department'],
            'organization_name':selected['name']}


def module_enabled(user, module):
    if user['role']=='platform_admin':
        return True
    org=next((o for o in organizations() if o['org_id']==user.get('organization_id') and o['active']),None)
    if not org or not org.get(module+'_enabled'):
        return False
    if user['role'] == 'operator':
        if module in ('messaging', 'reports'):
            return True
        return bool(grant(user).get(module))
    return True


def scoped_users(user):
    if user['role']=='platform_admin':
        return users()
    return [u for raw in users() if raw['role']!='platform_admin'
            for u in [account(raw['email'],user['organization_id'])] if u]


ORG_KINDS = {'company','unit','association','club','family','personal','other'}


def org_profile(payload):
    name=payload.get('name','');kind=payload.get('kind')
    if not isinstance(name,str) or not name.strip() or len(name.strip())>80 or kind not in ORG_KINDS:
        raise ValueError('請填寫組織名稱並選擇類型。')
    return name.strip(), kind


def save_organization(payload, actor):
    """平台管理員：組織資料、啟用狀態與模組（含客製模組設定）。"""
    name, kind = org_profile(payload)
    flags=[payload.get(k) for k in ('active','reports_enabled','messaging_enabled','weather_enabled')]
    if any(type(v) is not bool for v in flags):
        raise ValueError('組織狀態與模組授權格式不正確。')
    weather_path=payload.get('weather_image_path','')
    if not isinstance(weather_path,str) or len(weather_path)>1024:
        raise ValueError('天氣圖片路徑格式不正確。')
    weather_path=weather_path.strip()
    if weather_path and (not Path(weather_path).is_absolute() or Path(weather_path).suffix.lower()!='.png'):
        raise ValueError('天氣圖片請填入伺服器上 PNG 檔的完整路徑。')
    if flags[3] and not weather_path:
        raise ValueError('啟用天氣模組時，請填入天氣圖片的 PNG 路徑。')
    org_id=payload.get('org_id') or uuid4().hex
    with app.database_connection() as conn:
        if payload.get('org_id') and not conn.execute('SELECT 1 FROM organizations WHERE org_id=?',(org_id,)).fetchone():
            raise ValueError('找不到組織。')
        conn.execute('''INSERT INTO organizations(org_id,name,kind,active,reports_enabled,messaging_enabled,weather_enabled,weather_image_path)
                        VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(org_id) DO UPDATE SET name=excluded.name,kind=excluded.kind,
                        active=excluded.active,reports_enabled=excluded.reports_enabled,messaging_enabled=excluded.messaging_enabled,
                        weather_enabled=excluded.weather_enabled,weather_image_path=excluded.weather_image_path''',
                     (org_id,name,kind,*[int(v) for v in flags],weather_path))
        audit(conn,actor,'organization.update',org_id,name,org_id)
    return {'org_id':org_id}


def save_organization_profile(org_id, payload, actor):
    """管理員：只能修改本組織名稱與類型；啟用狀態與模組由平台管理員設定。"""
    name, kind = org_profile(payload)
    with app.database_connection() as conn:
        if not conn.execute('UPDATE organizations SET name=?,kind=? WHERE org_id=?',(name,kind,org_id)).rowcount:
            raise ValueError('找不到組織。')
        audit(conn,actor,'organization.profile',org_id,name,org_id)
    return {'org_id':org_id}


def save_membership(payload, actor):
    email=payload.get('email');org_id=payload.get('org_id');role=payload.get('role');active=payload.get('active')
    department=payload.get('department','')
    actor_acc = account(actor)
    if actor_acc and actor_acc['role'] == 'org_admin':
        if org_id != actor_acc.get('organization_id'):
            raise ValueError("只能管理本組織的成員。")
        if role not in {'operator', 'collaborator'}:
            raise ValueError("管理員只能建立操作人員或協作人員。")
    if role not in {'org_admin','operator','collaborator'} or type(active) is not bool or not isinstance(department,str) or len(department)>80:
        raise ValueError('成員角色或欄位格式不正確。')
    with app.database_connection() as conn:
        if not conn.execute('SELECT 1 FROM workspace_users WHERE email=?',(email,)).fetchone() or not conn.execute('SELECT 1 FROM organizations WHERE org_id=?',(org_id,)).fetchone():
            raise ValueError('請先建立登入帳號與組織。')
        conn.execute('''INSERT INTO organization_members(email,org_id,role,department,active) VALUES (?,?,?,?,?)
                        ON CONFLICT(email,org_id) DO UPDATE SET role=excluded.role,department=excluded.department,active=excluded.active''',
                     (email,org_id,role,department.strip(),int(active)))
        conn.execute("UPDATE workspace_users SET role=?,department=? WHERE email=? AND organization_id=? AND role<>'platform_admin'",
                     (role,department.strip(),email,org_id))
        if 'channel_ids' in payload and isinstance(payload['channel_ids'], list):
            conn.execute("DELETE FROM oa_member_access WHERE email=? AND org_id=?", (email, org_id))
            for ch_id in payload['channel_ids']:
                conn.execute("INSERT OR IGNORE INTO oa_member_access (channel_id, email, org_id) VALUES (?, ?, ?)",
                             (ch_id, email, org_id))
        audit(conn,actor,'membership.update',org_id,email+' · '+role)


def manager(user):
    return bool(user) and user['role'] in {'platform_admin', 'org_admin'}


def operator(user):
    return bool(user) and user['role'] in {'platform_admin', 'org_admin', 'operator', 'collaborator'}


def can_send(user):
    return bool(user) and user['role'] in {'platform_admin', 'org_admin', 'operator'}


def login_account(email, organization_id=None):
    user = account(email, organization_id)
    if operator(user):
        return user
    if organization_id is None:
        for member in memberships(email):
            user = account(email, member['org_id'])
            if operator(user):
                return user
    return None


def dispatch_scopes():
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [{**dict(r), 'recipient_ids': json.loads(r['recipients_json'])}
                for r in conn.execute('SELECT * FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() ORDER BY organization_id,name')]


def grant(user):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM sender_grants WHERE sender_grants.channel_id=current_channel() AND email=? AND organization_id=?', (user['email'], user['organization_id'])).fetchone()
    return {**(dict(row) if row else {'messaging': 0, 'reports': 0, 'weather': 0}),
            'scope_ids': json.loads(row['scopes_json']) if row else [],
            'report_ids': json.loads(row['reports_json']) if row else []}


def allowed_contact(user, row):
    if not same_organization(user, row.get('organization_id')):
        return False
    return operator(user)


def string_list(payload, key):
    value = payload.get(key, [])
    if not isinstance(value, list) or len(value) > 500 or any(not isinstance(v, str) or len(v) > 254 for v in value):
        raise ValueError('授權選項格式不正確。')
    return sorted(set(value))


def save_dispatch_scope(payload, actor):
    organization_id, name, kind = payload.get('organization_id'), payload.get('name'), payload.get('kind')
    active, department = payload.get('active'), payload.get('department', '')
    ids = string_list(payload, 'recipient_ids')
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or kind not in {'department','project','group'} or type(active) is not bool:
        raise ValueError('請填寫範圍名稱、類型與啟用狀態。')
    if not isinstance(department, str) or len(department) > 60 or (kind == 'department' and not department.strip()):
        raise ValueError('部門範圍必須指定部門。')
    if kind == 'group' and len(ids) != 1:
        raise ValueError('群組範圍須選擇一個 LINE 群組。')
    if kind == 'project' and not ids:
        raise ValueError('專案範圍須選擇聯絡對象。')
    channels.enforce_organization(organization_id)
    scope_id = payload.get('scope_id') or uuid4().hex
    if not isinstance(scope_id, str) or not re.fullmatch('[0-9a-f]{32}', scope_id):
        raise ValueError('範圍識別資料不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM organizations WHERE org_id=?', (organization_id,)).fetchone():
            raise ValueError('請選擇有效組織。')
        old = conn.execute('SELECT organization_id FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() AND scope_id=?', (scope_id,)).fetchone()
        if payload.get('scope_id') and (not old or old[0] != organization_id):
            raise ValueError('範圍不存在或組織不可變更，請另建範圍。')
        for rid in ids:
            row = conn.execute('SELECT kind,organization_id FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (rid,)).fetchone()
            if not row or row[1] != organization_id or (kind == 'group' and row[0] not in {'group','room'}):
                raise ValueError('請選擇同組織的有效聯絡對象／群組。')
        conn.execute("""INSERT INTO dispatch_scopes(channel_id,scope_id,organization_id,name,kind,department,recipients_json,active) VALUES (current_channel(),?,?,?,?,?,?,?) ON CONFLICT(scope_id) DO UPDATE SET
                        name=excluded.name,kind=excluded.kind,department=excluded.department,recipients_json=excluded.recipients_json,active=excluded.active WHERE dispatch_scopes.channel_id=excluded.channel_id""",
                     (scope_id,organization_id,name.strip(),kind,department.strip() if kind=='department' else '',json.dumps(ids if kind!='department' else []),int(active)))
        audit(conn,actor,'scope.update',scope_id,name.strip(),organization_id)
    return {'scope_id':scope_id}


def save_grant(payload, actor):
    email, organization_id = payload.get('email'), payload.get('organization_id')
    channels.enforce_organization(organization_id)
    scopes, report_ids = string_list(payload,'scope_ids'), string_list(payload,'report_ids')
    flags = [payload.get(k) for k in ('messaging','reports','weather')]
    if any(type(v) is not bool for v in flags):
        raise ValueError('請設定模組授權。')
    user = account(email, organization_id)
    if not user or user['role'] != 'operator':
        raise ValueError('請先建立此組織的操作人員資格。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for sid in scopes:
            if not conn.execute('SELECT 1 FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() AND scope_id=? AND organization_id=?', (sid,organization_id)).fetchone():
                raise ValueError('範圍不屬於此組織。')
        for rid in report_ids:
            if rid != 'weather' and not conn.execute('SELECT 1 FROM report_sources WHERE report_sources.channel_id=current_channel() AND report_id=? AND organization_id=?', (rid,organization_id)).fetchone():
                raise ValueError('報告不屬於此組織。')
        conn.execute("""INSERT INTO sender_grants(channel_id,email,organization_id,scopes_json,reports_json,messaging,reports,weather) VALUES (current_channel(),?,?,?,?,?,?,?) ON CONFLICT(channel_id,email,organization_id) DO UPDATE SET
                        scopes_json=excluded.scopes_json,reports_json=excluded.reports_json,messaging=excluded.messaging,reports=excluded.reports,weather=excluded.weather""",
                     (email,organization_id,json.dumps(scopes),json.dumps(report_ids),*[int(v) for v in flags]))
        audit(conn,actor,'grant.update',email,'更新發送範圍、報告與模組授權',organization_id)


def same_organization(user, organization_id):
    return user['role'] == 'platform_admin' or (bool(user.get('organization_id')) and user['organization_id'] == organization_id)


def actor_user(actor, organization_id=None):
    if actor == '本機管理員':
        return {'email': actor, 'role': 'platform_admin', 'organization_id': ''}
    user = account(actor, organization_id)
    if not operator(user):
        raise ValueError('發送權限已失效。')
    if channels.current_id():
        channels.authorize(channels.current_id(), user)
    return user


def view_options(user):
    result=[]
    for member in memberships():
        row=account(member['email'],member['org_id'])
        if row and row['role']!='platform_admin':
            if user['role']=='platform_admin':
                result.append(row)
            elif user['role']=='org_admin' and same_organization(user,row['organization_id']) and row['role'] in {'operator','collaborator'}:
                result.append(row)
    return result


def save_user(payload, actor):
    email = str(payload.get("email", "")).strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("請填入完整 Email。")
    role = payload.get("role")
    active = payload.get("active")
    if role not in {"platform_admin", "org_admin", "operator", "collaborator"} or type(active) is not bool:
        raise ValueError("角色或啟用狀態不正確。")
    
    actor_acc = account(actor) if actor != '本機管理員' else {'role': 'platform_admin', 'organization_id': ''}
    if not actor_acc:
        actor_acc = next((u for u in users() if u['email'] == actor), None)
    
    if actor_acc and actor_acc['role'] == 'org_admin':
        # 乙級只能在本組織新增／修改丙級（operator）或丁級（collaborator）
        if role not in {'operator', 'collaborator'}:
            raise ValueError("管理員只能建立操作人員或協作人員。")
        if payload.get("organization_id") and payload.get("organization_id") != actor_acc.get("organization_id"):
            raise ValueError("只能管理本組織的帳號。")
        payload["organization_id"] = actor_acc.get("organization_id")
    elif actor_acc and actor_acc['role'] not in {'platform_admin'}:
        raise ValueError("權限不足。")

    fields = {}
    for key in ("display_name", "organization_id", "department"):
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value.strip()) > 80:
            raise ValueError("帳號欄位請限制在 80 字以內。")
        fields[key] = value.strip()
    if role != "platform_admin" and not fields["organization_id"]:
        raise ValueError("管理員與成員必須指定所屬組織。")
    with app.database_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("SELECT role,active,organization_id FROM workspace_users WHERE email=?", (email,)).fetchone()
        if actor_acc and actor_acc['role'] == 'org_admin' and previous:
            if previous[0] in {'platform_admin', 'org_admin'} and email != actor:
                raise ValueError("無法修改管理員帳號。")
            if previous[2] and previous[2] != actor_acc.get('organization_id'):
                raise ValueError("無法修改其他組織帳號。")
        if previous and previous[0] == "platform_admin" and previous[1] == 1 and (role != "platform_admin" or not active):
            remaining = conn.execute("SELECT COUNT(*) FROM workspace_users WHERE role='platform_admin' AND active=1 AND email<>?", (email,)).fetchone()[0]
            if not remaining:
                raise ValueError("至少必須保留一位啟用中的管理員。")
        if email == actor and not active:
            raise ValueError("不能停用目前登入的帳號。")
        old_organization_id=conn.execute('SELECT organization_id FROM workspace_users WHERE email=?',(email,)).fetchone()
        if fields['organization_id']:
            conn.execute('INSERT OR IGNORE INTO organizations(org_id,name) VALUES (?,?)',(fields['organization_id'],fields['organization_id']))
        if old_organization_id and old_organization_id[0]!=fields['organization_id']:
            conn.execute('DELETE FROM organization_members WHERE email=? AND org_id=?',(email,old_organization_id[0]))
        if role!='platform_admin':
            conn.execute('''INSERT INTO organization_members(email,org_id,role,department,active) VALUES (?,?,?,?,?)
                            ON CONFLICT(email,org_id) DO UPDATE SET role=excluded.role,department=excluded.department,active=excluded.active''',
                         (email,fields['organization_id'],role,fields['department'],int(active)))
        conn.execute("""INSERT INTO workspace_users(email,role,active,display_name,organization_id,department)
                        VALUES (?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET role=excluded.role,active=excluded.active,
                        display_name=excluded.display_name,organization_id=excluded.organization_id,department=excluded.department""",
                     (email, role, int(active), fields["display_name"], fields["organization_id"], fields["department"]))
        if previous and (not active or previous[0] != role):
            conn.execute('DELETE FROM site_sessions WHERE email=?', (email,))
            conn.execute('DELETE FROM site_activation WHERE email=?', (email,))
        audit(conn, actor, "account.update", email, role + (" · 啟用" if active else " · 停用"))



def can_view(source, user):
    if user["role"] == "platform_admin":
        return True
    if not user.get("organization_id"):
        return False
    if source["report_id"] == "weather":
        if user["role"] == "operator":
            return bool(grant(user).get("weather")) and module_enabled(user, "weather")
        return module_enabled(user, "weather")
    if not module_enabled(user, "reports"):
        return False
    if source.get("organization_id") != user["organization_id"]:
        return False
    return user["role"] in {"org_admin", "operator"}


def validate_targets(source, selected):
    if source["report_id"] == "weather":
        return
    owner_id = source.get("owner_recipient_id", "")
    for row in selected:
        if ((not source["organization_id"] and channels.current_organization_id() is None) or row.get("organization_id") != source["organization_id"]
                or (source["scope"] == "department" and row.get("department") != source["department"])
                or (source["scope"] == "personal" and (not owner_id or row["recipient_id"] != owner_id))):
            raise ValueError("發送對象不在這份報告的組織／部門／個人範圍內，請重新選擇。")


def audit(conn, actor, action, target, detail, organization_id=None):
    user = conn.execute('SELECT role,organization_id FROM workspace_users WHERE email=? AND active=1', (actor,)).fetchone()
    if organization_id is None:
        organization_id = user[1] if user and user[0] == 'org_admin' else ''
    conn.execute('INSERT INTO audit_events(channel_id,actor,action,target,detail,organization_id) VALUES (current_channel(),?,?,?,?,?)',
                 (actor, action, target, detail, organization_id))


def weather_removed():
    with app.database_connection() as conn:
        row = conn.execute("SELECT removed FROM builtin_report_state WHERE builtin_report_state.channel_id=current_channel() AND report_id='weather'").fetchone()
        return bool(row and row[0])


def sources():
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute('SELECT * FROM report_sources WHERE report_sources.channel_id=current_channel() ORDER BY created_at,report_id')]
    return weather_source() + rows


def weather_org():
    """目前 OA 所屬組織；平台管理員已啟用天氣客製模組並設定圖片來源時才回傳。"""
    org_id = channels.current_organization_id()
    org = next((o for o in organizations() if o['org_id'] == org_id and o['active']), None)
    return org if org and org['weather_enabled'] and org['weather_image_path'] else None


def weather_source():
    org = weather_org()
    if not org or weather_removed():
        return []
    return [{"report_id": "weather", "title": "天氣報告", "category": "weather", "department": "", "organization_id": org['org_id'],
             "scope": "module", "source_path": org['weather_image_path']}]


def read_source(source):
    path = Path(source["source_path"])
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
        modified = os.fstat(stream.fileno()).st_mtime
    if len(data) > MAX_BYTES:
        raise ValueError("圖片超過 1 MB，請先縮小後再發送。")
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("報告必須是有效的 PNG 圖片。")
    return data, modified


def describe(source, preview=False):
    item = {key: source[key] for key in ("report_id", "title", "category", "department", "organization_id", "scope")}
    item["owner_recipient_id"] = source.get("owner_recipient_id", "")
    item.update(status="missing", reason="尚未找到報告，請先執行產生報告的程式。", modified_at=None,
                size=0, version="", stale=False)
    try:
        data, modified = read_source(source)
        stamp = datetime.fromtimestamp(modified, timezone.utc)
        local_zone = timezone(timedelta(hours=8))
        stale = stamp.astimezone(local_zone).date() < datetime.now(local_zone).date()
        item.update(status="ready", reason="", modified_at=stamp.isoformat(), size=len(data),
                    version=hashlib.sha256(data).hexdigest(), stale=stale)
        if preview:
            item["preview"] = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        item.update(status="invalid", reason=str(exc) if isinstance(exc, ValueError) else "無法讀取報告，請檢查檔案權限。")
    return item


def find(report_id):
    return next((row for row in sources() if row["report_id"] == report_id), None)


def prepare(report_id, version, allow_stale=False):
    source = find(report_id)
    if not source:
        raise ValueError("找不到這份報告，請重新整理報告中心。")
    item = describe(source)
    if item["status"] != "ready":
        raise ValueError(item["reason"])
    if not version or version != item["version"]:
        raise ValueError("報告已更新，請重新預覽後再發送。")
    if item["stale"] and allow_stale is not True:
        raise ValueError("這份報告不是今天更新，請確認後再發送。")
    return source, item


def save(payload, actor):
    title, category = payload.get("title"), payload.get("category")
    source_path, department = payload.get("source_path"), payload.get("department", "")
    if payload.get('asset_id'):
        import composer
        asset=composer.asset(payload['asset_id'],actor_user(actor))
        source_path=str(asset['path'])
    organization_id, scope = payload.get("organization_id", ""), payload.get("scope", "company")
    if payload.get('asset_id') and asset['organization_id'] and asset['organization_id'] != organization_id:
        raise ValueError('圖片與報告必須屬於同一組織，請重新選擇圖片。')
    channels.enforce_organization(organization_id)
    if not isinstance(organization_id, str) or (not organization_id.strip() and channels.current_organization_id() is None) or len(organization_id.strip()) > 60 or scope not in {"company", "department", "personal"}:
        raise ValueError("請設定報告所屬組織與可見範圍。")
    owner_id = payload.get('owner_recipient_id','')
    if not isinstance(owner_id,str):
        raise ValueError('個人聯絡對象格式不正確。')
    if scope == 'personal':
        with app.database_connection() as conn:
            if not conn.execute("SELECT 1 FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=? AND organization_id=? AND kind='user' AND active=1", (owner_id,organization_id.strip())).fetchone():
                raise ValueError('個人報告必須指定同組織、啟用中的 LINE 個人聯絡對象。')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 80:
        raise ValueError("請填寫 1 至 80 字的報告名稱。")
    if category == "weather":
        raise ValueError("天氣報告由組織的天氣模組提供，請在「組織」設定，不另外新增報告來源。")
    if category not in CATEGORIES or not isinstance(department, str) or len(department.strip()) > 60:
        raise ValueError("報告類型或部門格式不正確。")
    if scope == "department" and not department.strip():
        raise ValueError("部門報告必須指定部門。")
    if not isinstance(source_path, str) or not Path(source_path).is_absolute() or Path(source_path).suffix.lower() != ".png":
        raise ValueError("請選擇報告圖片，或在進階設定填入伺服器 PNG 完整路徑。")
    if len(source_path) > 1024:
        raise ValueError("檔案路徑過長。")
    report_id = payload.get("report_id") or uuid4().hex
    if not isinstance(report_id, str) or not re.fullmatch(r"[0-9a-f]{32}", report_id):
        raise ValueError("報告識別資料不正確。")
    with app.database_connection() as conn:
        if payload.get("report_id") and not conn.execute('SELECT 1 FROM report_sources WHERE report_sources.channel_id=current_channel() AND report_id=?', (report_id,)).fetchone():
            raise ValueError("這份報告來源已移除。")
        conn.execute("""INSERT INTO report_sources(channel_id,report_id,title,category,source_path,department,organization_id,scope,owner_recipient_id) VALUES (current_channel(),?,?,?,?,?,?,?,?)
                        ON CONFLICT(report_id) DO UPDATE SET title=excluded.title,category=excluded.category,source_path=excluded.source_path,
                        department=excluded.department,organization_id=excluded.organization_id,scope=excluded.scope,owner_recipient_id=excluded.owner_recipient_id WHERE report_sources.channel_id=excluded.channel_id""",
                     (report_id, title.strip(), category, source_path.strip(), department.strip(), organization_id.strip(), scope, owner_id if scope == "personal" else ""))
        audit(conn, actor, "report.update" if payload.get("report_id") else "report.create", report_id, title.strip())
    return describe(find(report_id))


def remove(report_id, actor):
    if not isinstance(report_id, str):
        raise ValueError("報告識別資料不正確。")
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if report_id == 'weather':
            title = '天氣報告'
            conn.execute("INSERT INTO builtin_report_state(channel_id,report_id,removed) VALUES (current_channel(),'weather',1) ON CONFLICT(channel_id,report_id) DO UPDATE SET removed=1")
        else:
            row = conn.execute('SELECT title FROM report_sources WHERE report_sources.channel_id=current_channel() AND report_id=?', (report_id,)).fetchone()
            if not row:
                raise ValueError("找不到報告來源。")
            title = row[0]
            conn.execute('DELETE FROM report_sources WHERE report_sources.channel_id=current_channel() AND report_id=?', (report_id,))
        conn.execute("""UPDATE send_deliveries SET status='cancelled' WHERE status='pending'
                        AND job_id IN (SELECT job_id FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND report_id=? AND status IN ('scheduled','queued'))""", (report_id,))
        conn.execute("UPDATE send_jobs SET status='cancelled',error='報告來源已移除。' WHERE send_jobs.channel_id=current_channel() AND report_id=? AND status IN ('scheduled','queued')", (report_id,))
        audit(conn, actor, "report.remove", report_id, title)


def restore_weather(actor):
    if not weather_org():
        raise ValueError('此 OA 所屬組織尚未啟用天氣模組，請先在「組織」設定。')
    with app.database_connection() as conn:
        conn.execute("UPDATE builtin_report_state SET removed=0 WHERE builtin_report_state.channel_id=current_channel() AND report_id='weather'")
        audit(conn, actor, 'report.restore', 'weather', '天氣報告')


def activity(user=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        if user and user['role'] == 'operator':
            return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND actor=? AND organization_id=? ORDER BY event_id DESC LIMIT 50', (user['email'],user['organization_id']))]
        if user and user['role'] != 'platform_admin':
            return [dict(row) for row in conn.execute("SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND organization_id=? AND organization_id<>'' ORDER BY event_id DESC LIMIT 50", (user['organization_id'],))]
        return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() ORDER BY event_id DESC LIMIT 50')]

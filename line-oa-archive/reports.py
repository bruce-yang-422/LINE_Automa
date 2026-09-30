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
        conn.executemany("INSERT OR IGNORE INTO workspace_users(email,role) VALUES (?,'administrator')", [(email,) for email in emails])


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


def account(email, company=None):
    user=next((u for u in users() if u['email']==email and u['active']),None)
    if not user or user['role']=='administrator':
        return user
    choices=[m for m in memberships(email) if m['active'] and m['org_active']]
    selected=next((m for m in choices if m['org_id']==(company if company is not None else user['company'])),None)
    if selected is None and company is None:
        selected=next(iter(choices),None)
    if not selected:
        return None
    return {**user,'role':selected['role'],'company':selected['org_id'],'department':selected['department'],
            'recipient_id':selected['recipient_id'],'organization_name':selected['name']}


def module_enabled(user, module):
    if user['role']=='administrator' or channels.personal_owner(user):
        return True
    org=next((o for o in organizations() if o['org_id']==user.get('company') and o['active']),None)
    return bool(org and org.get(module+'_enabled') and (user['role']!='sender' or grant(user).get(module)))


def scoped_users(user):
    if user['role']=='administrator':
        return users()
    return [u for raw in users() if raw['role']!='administrator'
            for u in [account(raw['email'],user['company'])] if u]


def save_organization(payload, actor):
    name=payload.get('name','');kind=payload.get('kind')
    if not isinstance(name,str) or not name.strip() or len(name.strip())>80 or kind not in {'company','unit','association','club','family','personal','other'}:
        raise ValueError('請填寫組織名稱並選擇類型。')
    flags=[payload.get(k) for k in ('active','reports_enabled','messaging_enabled','weather_enabled')]
    if any(type(v) is not bool for v in flags):
        raise ValueError('組織狀態與模組授權格式不正確。')
    org_id=payload.get('org_id') or uuid4().hex
    with app.database_connection() as conn:
        if payload.get('org_id') and not conn.execute('SELECT 1 FROM organizations WHERE org_id=?',(org_id,)).fetchone():
            raise ValueError('找不到組織。')
        conn.execute('''INSERT INTO organizations(org_id,name,kind,active,reports_enabled,messaging_enabled,weather_enabled)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(org_id) DO UPDATE SET name=excluded.name,kind=excluded.kind,
                        active=excluded.active,reports_enabled=excluded.reports_enabled,messaging_enabled=excluded.messaging_enabled,weather_enabled=excluded.weather_enabled''',
                     (org_id,name.strip(),kind,*[int(v) for v in flags]))
        audit(conn,actor,'organization.update',org_id,name.strip())
    return {'org_id':org_id}


def save_membership(payload, actor):
    email=payload.get('email');org_id=payload.get('org_id');role=payload.get('role');active=payload.get('active')
    department=payload.get('department','');recipient=payload.get('recipient_id','')
    if role not in {'company_admin','sender','employee'} or type(active) is not bool or any(not isinstance(v,str) or len(v)>80 for v in (department,recipient)):
        raise ValueError('成員角色或欄位格式不正確。')
    with app.database_connection() as conn:
        if not conn.execute('SELECT 1 FROM workspace_users WHERE email=?',(email,)).fetchone() or not conn.execute('SELECT 1 FROM organizations WHERE org_id=?',(org_id,)).fetchone():
            raise ValueError('請先建立登入帳號與組織。')
        if recipient and not conn.execute("SELECT 1 FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=? AND company=? AND kind='user'",(recipient,org_id)).fetchone():
            raise ValueError('LINE 個人聊天室必須屬於此組織。')
        conn.execute('''INSERT INTO organization_members(email,org_id,role,department,recipient_id,active) VALUES (?,?,?,?,?,?)
                        ON CONFLICT(email,org_id) DO UPDATE SET role=excluded.role,department=excluded.department,recipient_id=excluded.recipient_id,active=excluded.active''',
                     (email,org_id,role,department.strip(),recipient,int(active)))
        conn.execute("UPDATE workspace_users SET role=?,department=?,recipient_id=? WHERE email=? AND company=? AND role<>'administrator'",
                     (role,department.strip(),recipient,email,org_id))
        audit(conn,actor,'membership.update',org_id,email+' · '+role)


def manager(user):
    return bool(user) and user['role'] in {'administrator', 'company_admin'}


def operator(user):
    return bool(user) and user['role'] in {'administrator', 'company_admin', 'sender'}


def login_account(email, company=None):
    user = account(email, company)
    if operator(user):
        return user
    if company is None:
        for member in memberships(email):
            user = account(email, member['org_id'])
            if operator(user):
                return user
    return None


def dispatch_scopes():
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [{**dict(r), 'recipient_ids': json.loads(r['recipients_json'])}
                for r in conn.execute('SELECT * FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() ORDER BY company,name')]


def grant(user):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM sender_grants WHERE sender_grants.channel_id=current_channel() AND email=? AND company=?', (user['email'], user['company'])).fetchone()
    return {**(dict(row) if row else {'messaging': 0, 'reports': 0, 'weather': 0}),
            'scope_ids': json.loads(row['scopes_json']) if row else [],
            'report_ids': json.loads(row['reports_json']) if row else []}


def allowed_contact(user, row):
    if not same_company(user, row.get('company')):
        return False
    if user['role'] != 'sender' or channels.personal_owner(user):
        return operator(user)
    ids = set(grant(user)['scope_ids'])
    return any(s['scope_id'] in ids and s['active'] and s['company'] == user['company'] and
               ((s['kind'] == 'department' and bool(s['department']) and row.get('department') == s['department']) or
                (s['kind'] in {'project', 'group'} and row['recipient_id'] in s['recipient_ids'])) for s in dispatch_scopes())


def string_list(payload, key):
    value = payload.get(key, [])
    if not isinstance(value, list) or len(value) > 500 or any(not isinstance(v, str) or len(v) > 254 for v in value):
        raise ValueError('授權選項格式不正確。')
    return sorted(set(value))


def save_dispatch_scope(payload, actor):
    company, name, kind = payload.get('company'), payload.get('name'), payload.get('kind')
    active, department = payload.get('active'), payload.get('department', '')
    ids = string_list(payload, 'recipient_ids')
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or kind not in {'department','project','group'} or type(active) is not bool:
        raise ValueError('請填寫範圍名稱、類型與啟用狀態。')
    if not isinstance(department, str) or len(department) > 60 or (kind == 'department' and not department.strip()):
        raise ValueError('部門範圍必須指定部門。')
    if kind == 'group' and len(ids) != 1:
        raise ValueError('群組範圍須選擇一個 LINE 群組。')
    if kind == 'project' and not ids:
        raise ValueError('專案範圍須選擇收件者。')
    channels.enforce_company(company)
    scope_id = payload.get('scope_id') or uuid4().hex
    if not isinstance(scope_id, str) or not re.fullmatch('[0-9a-f]{32}', scope_id):
        raise ValueError('範圍識別資料不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM organizations WHERE org_id=?', (company,)).fetchone():
            raise ValueError('請選擇有效組織。')
        old = conn.execute('SELECT company FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() AND scope_id=?', (scope_id,)).fetchone()
        if payload.get('scope_id') and (not old or old[0] != company):
            raise ValueError('範圍不存在或組織不可變更，請另建範圍。')
        for rid in ids:
            row = conn.execute('SELECT kind,company FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (rid,)).fetchone()
            if not row or row[1] != company or (kind == 'group' and row[0] not in {'group','room'}):
                raise ValueError('請選擇同組織的有效收件者／群組。')
        conn.execute("""INSERT INTO dispatch_scopes(channel_id,scope_id,company,name,kind,department,recipients_json,active) VALUES (current_channel(),?,?,?,?,?,?,?) ON CONFLICT(scope_id) DO UPDATE SET
                        name=excluded.name,kind=excluded.kind,department=excluded.department,recipients_json=excluded.recipients_json,active=excluded.active WHERE dispatch_scopes.channel_id=excluded.channel_id""",
                     (scope_id,company,name.strip(),kind,department.strip() if kind=='department' else '',json.dumps(ids if kind!='department' else []),int(active)))
        audit(conn,actor,'scope.update',scope_id,name.strip(),company)
    return {'scope_id':scope_id}


def save_grant(payload, actor):
    email, company = payload.get('email'), payload.get('company')
    channels.enforce_company(company)
    scopes, report_ids = string_list(payload,'scope_ids'), string_list(payload,'report_ids')
    flags = [payload.get(k) for k in ('messaging','reports','weather')]
    if any(type(v) is not bool for v in flags):
        raise ValueError('請設定模組授權。')
    user = account(email, company)
    if not user or user['role'] != 'sender':
        raise ValueError('請先建立此組織的發送人員資格。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for sid in scopes:
            if not conn.execute('SELECT 1 FROM dispatch_scopes WHERE dispatch_scopes.channel_id=current_channel() AND scope_id=? AND company=?', (sid,company)).fetchone():
                raise ValueError('範圍不屬於此組織。')
        for rid in report_ids:
            if rid != 'weather' and not conn.execute('SELECT 1 FROM report_sources WHERE report_sources.channel_id=current_channel() AND report_id=? AND company=?', (rid,company)).fetchone():
                raise ValueError('報告不屬於此組織。')
        conn.execute("""INSERT INTO sender_grants(channel_id,email,company,scopes_json,reports_json,messaging,reports,weather) VALUES (current_channel(),?,?,?,?,?,?,?) ON CONFLICT(channel_id,email,company) DO UPDATE SET
                        scopes_json=excluded.scopes_json,reports_json=excluded.reports_json,messaging=excluded.messaging,reports=excluded.reports,weather=excluded.weather""",
                     (email,company,json.dumps(scopes),json.dumps(report_ids),*[int(v) for v in flags]))
        audit(conn,actor,'grant.update',email,'更新發送範圍、報告與模組授權',company)


def same_company(user, company):
    return user['role'] == 'administrator' or (channels.personal_owner(user) and company == '') or (bool(user.get('company')) and user['company'] == company)


def actor_user(actor, company=None):
    if actor == '本機管理員':
        return {'email': actor, 'role': 'administrator', 'company': ''}
    user = account(actor, company)
    if not user and channels.current_id():
        candidate = login_account(actor)
        if candidate and channels.personal_owner(candidate):
            user = {**candidate, 'company': ''}
    if not operator(user):
        raise ValueError('發送權限已失效。')
    if channels.current_id():
        channels.authorize(channels.current_id(), user)
    return user


def view_options(user):
    result=[]
    for member in memberships():
        row=account(member['email'],member['org_id'])
        if row and row['role']!='administrator' and (user['role']=='administrator' or (row['role'] in {'sender','employee'} and same_company(user,row['company']))):
            result.append(row)
    return result


def save_user(payload, actor):
    email = str(payload.get("email", "")).strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("請填入完整 Email。")
    role = payload.get("role")
    active = payload.get("active")
    if role not in {"administrator", "company_admin", "sender", "employee"} or type(active) is not bool:
        raise ValueError("角色或啟用狀態不正確。")
    fields = {}
    for key in ("display_name", "company", "department", "recipient_id"):
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value.strip()) > 80:
            raise ValueError("帳號欄位請限制在 80 字以內。")
        fields[key] = value.strip()
    if role != "administrator" and not fields["company"]:
        raise ValueError("組織管理員與成員必須指定所屬組織。")
    with app.database_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if fields["recipient_id"]:
            contact = conn.execute('SELECT kind,company FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (fields["recipient_id"],)).fetchone()
            if not contact or contact[0] != "user" or contact[1] != fields["company"]:
                raise ValueError("請先在收件者管理設定該個人的組織，再連結到帳號。")
        previous = conn.execute("SELECT role,active FROM workspace_users WHERE email=?", (email,)).fetchone()
        if previous and previous == ("administrator", 1) and (role != "administrator" or not active):
            remaining = conn.execute("SELECT COUNT(*) FROM workspace_users WHERE role='administrator' AND active=1 AND email<>?", (email,)).fetchone()[0]
            if not remaining:
                raise ValueError("至少必須保留一位啟用中的管理員。")
        if email == actor and not active:
            raise ValueError("不能停用目前登入的帳號。")
        old_company=conn.execute('SELECT company FROM workspace_users WHERE email=?',(email,)).fetchone()
        if fields['company']:
            conn.execute('INSERT OR IGNORE INTO organizations(org_id,name) VALUES (?,?)',(fields['company'],fields['company']))
        if old_company and old_company[0]!=fields['company']:
            conn.execute('DELETE FROM organization_members WHERE email=? AND org_id=?',(email,old_company[0]))
        if role!='administrator':
            conn.execute('''INSERT INTO organization_members(email,org_id,role,department,recipient_id,active) VALUES (?,?,?,?,?,?)
                            ON CONFLICT(email,org_id) DO UPDATE SET role=excluded.role,department=excluded.department,recipient_id=excluded.recipient_id,active=excluded.active''',
                         (email,fields['company'],role,fields['department'],fields['recipient_id'],int(active)))
        conn.execute("""INSERT INTO workspace_users(email,role,active,display_name,company,department,recipient_id)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET role=excluded.role,active=excluded.active,
                        display_name=excluded.display_name,company=excluded.company,department=excluded.department,recipient_id=excluded.recipient_id""",
                     (email, role, int(active), fields["display_name"], fields["company"], fields["department"], fields["recipient_id"]))
        if previous and (not active or previous[0] != role):
            conn.execute('DELETE FROM site_sessions WHERE email=?', (email,))
            conn.execute('DELETE FROM site_activation WHERE email=?', (email,))
        audit(conn, actor, "account.update", email, role + (" · 啟用" if active else " · 停用"))


def can_view(source, user):
    if user["role"] == "administrator" or channels.personal_owner(user):
        return True
    if user['role']=='sender':
        return (source['report_id'] in grant(user)['report_ids'] and module_enabled(user, 'weather' if source['report_id']=='weather' else 'reports')
                and (source['report_id']=='weather' or same_company(user,source.get('company'))))
    if source["report_id"] == "weather":
        return module_enabled(user,'weather') or (bool(source.get("owner_email")) and source["owner_email"] == user["email"])
    if not module_enabled(user,'reports'):
        return False
    if not user.get("company") or source.get("company") != user["company"]:
        return False
    if user['role'] == 'company_admin':
        return True
    scope = source.get("scope")
    return (scope == "company" or (scope == "department" and bool(user.get("department")) and source["department"] == user["department"])
            or (scope == "personal" and source.get("owner_email") == user["email"]))


def validate_targets(source, selected):
    if source["report_id"] == "weather":
        return
    owner = account(source.get("owner_email", ""),source['company']) if source["scope"] == "personal" else None
    owner_id = source.get("owner_recipient_id") or (owner["recipient_id"] if owner else "")
    for row in selected:
        if ((not source["company"] and channels.organization_id() is None) or row.get("company") != source["company"]
                or (source["scope"] == "department" and row.get("department") != source["department"])
                or (source["scope"] == "personal" and (not owner_id or row["recipient_id"] != owner_id))):
            raise ValueError("收件者不在這份報告的組織／部門／個人範圍內，請重新選擇。")


def audit(conn, actor, action, target, detail, company=None):
    user = conn.execute('SELECT role,company FROM workspace_users WHERE email=? AND active=1', (actor,)).fetchone()
    if company is None:
        company = user[1] if user and user[0] == 'company_admin' else ''
    conn.execute('INSERT INTO audit_events(channel_id,actor,action,target,detail,company) VALUES (current_channel(),?,?,?,?,?)',
                 (actor, action, target, detail, company))


def weather_removed():
    with app.database_connection() as conn:
        row = conn.execute("SELECT removed FROM builtin_report_state WHERE builtin_report_state.channel_id=current_channel() AND report_id='weather'").fetchone()
        return bool(row and row[0])


def sources():
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute('SELECT * FROM report_sources WHERE report_sources.channel_id=current_channel() ORDER BY created_at,report_id')]
    # Weather follows the existing environment setting and doesn't rewrite user configuration.
    weather = []
    if (not channels.current_id() or (channels.get() and channels.get()["legacy_webhook"])) and not weather_removed() and os.environ.get("WEATHER_MODULE_ENABLED", "true").lower() not in {"false", "0", "no"}:
        weather = [{"report_id": "weather", "title": "個人模組 · 天氣報告", "category": "weather", "department": "", "company": "", "scope": "module",
                    "owner_email": os.environ.get("WEATHER_OWNER_EMAIL", "").strip().lower(),
                    "source_path": os.environ.get("WEATHER_IMAGE_PATH", r"D:\Tools\ai_weather_report\output\weather_report.png")}]
    return weather + rows


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
    item = {key: source[key] for key in ("report_id", "title", "category", "department", "company", "scope", "owner_email")}
    item["owner_recipient_id"] = source.get("owner_recipient_id", "")
    if source.get('scope')=='personal' and not item['owner_recipient_id']:
        legacy=account(source.get('owner_email',''),source['company'])
        item['owner_recipient_id']=legacy['recipient_id'] if legacy else ''
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
    company, scope, owner = payload.get("company", ""), payload.get("scope", "company"), payload.get("owner_email", "")
    if payload.get('asset_id') and asset['company'] and asset['company'] != company:
        raise ValueError('圖片與報告必須屬於同一組織，請重新選擇圖片。')
    channels.enforce_company(company)
    if not isinstance(company, str) or (not company.strip() and channels.organization_id() is None) or len(company.strip()) > 60 or scope not in {"company", "department", "personal"}:
        raise ValueError("請設定報告所屬組織與可見範圍。")
    if not isinstance(owner, str):
        raise ValueError("個人帳號格式不正確。")
    owner = owner.strip().lower()
    owner_id = payload.get('owner_recipient_id','')
    if not isinstance(owner_id,str):
        raise ValueError('個人收件者格式不正確。')
    if scope == 'personal':
        # Read legacy account bindings only as a migration fallback; new UI selects a recipient.
        if not owner_id:
            legacy = account(owner,company.strip())
            owner_id = legacy['recipient_id'] if legacy else ''
        with app.database_connection() as conn:
            if not conn.execute("SELECT 1 FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=? AND company=? AND kind='user' AND active=1", (owner_id,company.strip())).fetchone():
                raise ValueError('個人報告必須指定同組織、啟用中的 LINE 個人收件者。')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 80:
        raise ValueError("請填寫 1 至 80 字的報告名稱。")
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
        conn.execute("""INSERT INTO report_sources(channel_id,report_id,title,category,source_path,department,company,scope,owner_email,owner_recipient_id) VALUES (current_channel(),?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(report_id) DO UPDATE SET title=excluded.title,category=excluded.category,source_path=excluded.source_path,
                        department=excluded.department,company=excluded.company,scope=excluded.scope,owner_email=excluded.owner_email,owner_recipient_id=excluded.owner_recipient_id WHERE report_sources.channel_id=excluded.channel_id""",
                     (report_id, title.strip(), category, source_path.strip(), department.strip(), company.strip(), scope, owner if scope == "personal" else "", owner_id if scope == "personal" else ""))
        audit(conn, actor, "report.update" if payload.get("report_id") else "report.create", report_id, title.strip())
    return describe(find(report_id))


def remove(report_id, actor):
    if not isinstance(report_id, str):
        raise ValueError("報告識別資料不正確。")
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if report_id == 'weather':
            title = '個人模組 · 天氣報告'
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
    if os.environ.get('WEATHER_MODULE_ENABLED', 'true').lower() in {'false', '0', 'no'}:
        raise ValueError('天氣模組已在本機設定停用，請先啟用模組。')
    with app.database_connection() as conn:
        conn.execute("UPDATE builtin_report_state SET removed=0 WHERE builtin_report_state.channel_id=current_channel() AND report_id='weather'")
        audit(conn, actor, 'report.restore', 'weather', '個人模組 · 天氣報告')


def activity(user=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        if user and user['role'] == 'sender':
            return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND actor=? AND company=? ORDER BY event_id DESC LIMIT 50', (user['email'],user['company']))]
        if user and user['role'] != 'administrator':
            return [dict(row) for row in conn.execute("SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND company=? AND company<>'' ORDER BY event_id DESC LIMIT 50", (user['company'],))]
        return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() ORDER BY event_id DESC LIMIT 50')]

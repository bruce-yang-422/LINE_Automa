"""Accounts, organizations, memberships, permissions and audit log."""

import re
import sqlite3
from uuid import uuid4

import app
import channels

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
            'organization_name':selected['name'], 'duty_manager':selected.get('duty_manager', 0)}


def module_enabled(user, module):
    if user['role']=='platform_admin':
        return True
    org=next((o for o in organizations() if o['org_id']==user.get('organization_id') and o['active']),None)
    if not org or not org.get(module+'_enabled'):
        return False
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
    """平台管理員：組織資料、啟用狀態與訊息模組。"""
    name, kind = org_profile(payload)
    flags=[payload.get(k) for k in ('active','messaging_enabled')]
    duty_flag = payload.get('duty_enabled')
    if duty_flag is not None and type(duty_flag) is not bool:
        raise ValueError('值日生模組開關格式不正確。')
    if any(type(v) is not bool for v in flags):
        raise ValueError('組織狀態與模組授權格式不正確。')
    org_id=payload.get('org_id') or uuid4().hex
    with app.database_connection() as conn:
        if payload.get('org_id') and not conn.execute('SELECT 1 FROM organizations WHERE org_id=?',(org_id,)).fetchone():
            raise ValueError('找不到組織。')
        conn.execute('''INSERT INTO organizations(org_id,name,kind,active,messaging_enabled)
                        VALUES (?,?,?,?,?) ON CONFLICT(org_id) DO UPDATE SET name=excluded.name,kind=excluded.kind,
                        active=excluded.active,messaging_enabled=excluded.messaging_enabled''',
                     (org_id,name,kind,*[int(v) for v in flags]))
        if duty_flag is not None:
            conn.execute('UPDATE organizations SET duty_enabled=? WHERE org_id=?', (int(duty_flag), org_id))
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
        if role != 'operator':
            conn.execute('UPDATE organization_members SET duty_manager=0 WHERE email=? AND org_id=?', (email, org_id))
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


def allowed_contact(user, row):
    if not same_organization(user, row.get('organization_id')):
        return False
    return operator(user)


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
        if role != 'operator' and fields['organization_id']:
            conn.execute('UPDATE organization_members SET duty_manager=0 WHERE email=? AND org_id=?', (email, fields['organization_id']))
        conn.execute("""INSERT INTO workspace_users(email,role,active,display_name,organization_id,department)
                        VALUES (?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET role=excluded.role,active=excluded.active,
                        display_name=excluded.display_name,organization_id=excluded.organization_id,department=excluded.department""",
                     (email, role, int(active), fields["display_name"], fields["organization_id"], fields["department"]))
        if previous and (not active or previous[0] != role):
            conn.execute('DELETE FROM site_sessions WHERE email=?', (email,))
            conn.execute('DELETE FROM site_activation WHERE email=?', (email,))
        audit(conn, actor, "account.update", email, role + (" · 啟用" if active else " · 停用"))



def audit(conn, actor, action, target, detail, organization_id=None):
    user = conn.execute('SELECT role,organization_id FROM workspace_users WHERE email=? AND active=1', (actor,)).fetchone()
    if organization_id is None:
        organization_id = user[1] if user and user[0] == 'org_admin' else ''
    conn.execute('INSERT INTO audit_events(channel_id,actor,action,target,detail,organization_id) VALUES (current_channel(),?,?,?,?,?)',
                 (actor, action, target, detail, organization_id))


def activity(user=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        if user and user['role'] == 'operator':
            return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND actor=? AND organization_id=? ORDER BY event_id DESC LIMIT 50', (user['email'],user['organization_id']))]
        if user and user['role'] != 'platform_admin':
            return [dict(row) for row in conn.execute("SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() AND organization_id=? AND organization_id<>'' ORDER BY event_id DESC LIMIT 50", (user['organization_id'],))]
        return [dict(row) for row in conn.execute('SELECT * FROM audit_events WHERE audit_events.channel_id=current_channel() ORDER BY event_id DESC LIMIT 50')]

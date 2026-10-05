"""管理後台：本機控制台以 bearer token 進入；對外網址一律使用站內帳號密碼登入。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4
from urllib.parse import urlsplit, parse_qs

import app
import channels
import limits
from control_runtime import load_settings
import line_api
import recipients
import reports
import site_auth
from send_image import publish_image, verify_public_image, send_push
import composer
import cases
import chat_notes
import chat
import template_packs


def contact_label(row):
    return row["custom_name"] or row["display_name"] or (("個人" if row["kind"] == "user" else "群組") + " · " + row["recipient_id"][-8:])


def select_contacts(conn, audience, ids):
    contacts = recipients.list_contacts(conn)
    if audience == "selected" and isinstance(ids, list) and all(isinstance(i, str) for i in ids):
        wanted = set(ids)
        selected = [r for r in contacts if r["active"] and r["recipient_id"] in wanted]
        if len(selected) != len(wanted):
            raise ValueError("部分發送對象已停用或不存在，請重新整理名單。")
    else:
        raise ValueError("請選擇發送對象。")
    if not selected or len(selected) > 500:
        raise ValueError("請選擇 1 至 500 個有效發送對象。")
    if any(not re.fullmatch(r"[UCR][0-9a-fA-F]{32}", r["recipient_id"]) for r in selected):
        raise ValueError("名單含有無效 ID，請重新接收 LINE Webhook。")
    return selected


def job_status(job_id=None, user=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        scope_sql = " AND organization_id=? AND organization_id<>''" if user and user['role'] != 'platform_admin' else ''
        scope_args = (user['organization_id'],) if scope_sql else ()
        if job_id:
            jobs = conn.execute('SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND job_id=?' + scope_sql, (job_id,) + scope_args).fetchall()
        else:
            jobs = conn.execute("SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND status='scheduled'" + scope_sql + " ORDER BY scheduled_at", scope_args).fetchall()
            jobs += conn.execute("SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND status<>'scheduled'" + scope_sql + " ORDER BY created_at DESC LIMIT 20", scope_args).fetchall()
        result = []
        for row in jobs:
            item = dict(row)
            if user and user['role']=='operator' and item['actor']!=user['email']:
                continue
            if user and not reports.same_organization(user, item['organization_id']):
                continue
            item["deliveries"] = [dict(r) for r in conn.execute(
                "SELECT recipient_id,label,status,request_id,error FROM send_deliveries WHERE job_id=?", (row["job_id"],))]
            if user and user['role']=='operator':
                permitted = {r['recipient_id'] for r in recipients.list_contacts(conn) if reports.allowed_contact(user,r)}
                if any(r['recipient_id'] not in permitted for r in item['deliveries']):
                    continue
            if user and user['role'] != 'platform_admin':
                item.pop('image_path', None)
            result.append(item)
        return result


class Dispatcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.closing = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1)
        # A previous process may have died after LINE accepted a request. Never auto-resend it.
        with app.database_connection() as conn:
            conn.execute("UPDATE send_deliveries SET status='unknown', error='上次服務中斷，請先確認聊天室。' WHERE status='sending'")
            conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE status='pending' AND job_id IN (SELECT job_id FROM send_jobs WHERE status<>'scheduled')")
            conn.execute("UPDATE send_jobs SET status='interrupted' WHERE status IN ('queued','running')")

    def start_scheduler(self):
        def loop():
            while not self.closing.wait(2):
                try:
                    self.tick()
                except Exception:
                    # Keep the scheduler alive; the next tick can retry unclaimed rows.
                    continue
        self.scheduler = threading.Thread(target=loop, daemon=True)
        self.scheduler.start()

    def tick(self, now=None):
        now = now or datetime.now(timezone.utc)
        with self.lock:
            if self.closing.is_set():
                return
            with app.database_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                due = conn.execute("SELECT job_id,scheduled_at FROM send_jobs WHERE status='scheduled' AND scheduled_at<=?", (now.isoformat(),)).fetchall()
                claimed = []
                for job_id, stamp in due:
                    missed = (now - datetime.fromisoformat(stamp)).total_seconds() > 600
                    conn.execute("UPDATE send_jobs SET status=?,error=? WHERE job_id=? AND status='scheduled'",
                                 ('missed' if missed else 'queued', '已錯過預約時間超過 10 分鐘，未補發；請重新確認內容。' if missed else '', job_id))
                    if missed:
                        conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=?", (job_id,))
                    else:
                        claimed.append(job_id)
            for job_id in claimed:
                self.pool.submit(self.run, job_id)

    def cancel(self, job_id, actor, organization=None):
        job_id = str(UUID(str(job_id)))
        user = reports.actor_user(actor, organization)
        with self.lock, app.database_connection() as conn:
            job = conn.execute('SELECT organization_id,actor FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND job_id=?', (job_id,)).fetchone()
            if not job or not reports.same_organization(user, job[0]) or (user['role']=='operator' and job[1]!=actor):
                raise ValueError('找不到可操作的預約。')
            changed = conn.execute("UPDATE send_jobs SET status='cancelled' WHERE send_jobs.channel_id=current_channel() AND job_id=? AND status='scheduled'", (job_id,)).rowcount
            if not changed:
                raise ValueError("此預約已開始處理或已取消，請重新整理紀錄。")
            conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=? AND status='pending'", (job_id,))
            reports.audit(conn, actor, "send.cancel", job_id, "取消預約", user['organization_id'])

    def submit(self, payload, actor="本機管理員", organization=None):
        job_id = str(UUID(str(payload.get("job_id", ""))))
        with self.lock:
            user = reports.actor_user(actor, organization)
            if not reports.module_enabled(user,'messaging'):
                raise ValueError('此組織尚未授權訊息發送模組。')
            if self.closing.is_set():
                raise ValueError("服務正在停止，請稍後再發送。")
            existing = job_status(job_id)
            if existing:
                if not job_status(job_id, user):
                    raise ValueError('無法存取此工作。')
                return existing[0]
            scheduled_at = payload.get("scheduled_at", "")
            if scheduled_at:
                try:
                    stamp = datetime.fromisoformat(scheduled_at)
                    if stamp.utcoffset() is None:
                        raise ValueError()
                    stamp = stamp.astimezone(timezone.utc)
                    delay = (stamp - datetime.now(timezone.utc)).total_seconds()
                    if not 30 <= delay <= 366 * 86400:
                        raise ValueError()
                    scheduled_at = stamp.isoformat()
                except (ValueError, TypeError):
                    raise ValueError("預約時間須包含時區，且介於 30 秒後至一年內。") from None
            elif scheduled_at not in ("", None):
                raise ValueError("預約時間格式不正確。")
            scheduled_at = scheduled_at or ""
            if scheduled_at:
                with app.database_connection() as conn:
                    pending = conn.execute("SELECT COUNT(*) FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND status='scheduled'").fetchone()[0]
                if pending >= limits.SCHEDULED_MESSAGES_PER_OA:
                    raise ValueError(f"此 LINE OA 同時預約中的訊息已達上限（{limits.SCHEDULED_MESSAGES_PER_OA} 則），請等待送出或取消部分預約。")
            message_text = payload.get("message_text", "")
            composition = payload.get('composition')
            if 'composition' in payload and (not isinstance(composition, dict) or message_text or payload.get('image_path') or payload.get('audience') != 'selected'):
                raise ValueError('自訂訊息請選擇發送對象，且不能混合文字。')
            if not isinstance(message_text, str) or ("message_text" in payload and not message_text.strip()) or len(message_text.encode('utf-16-le')) // 2 > limits.TEXT_MESSAGE_MAX:
                raise ValueError(f"文字訊息請填入 1 至 {limits.TEXT_MESSAGE_MAX} 字（表情符號可能佔兩字）。")
            if message_text and (payload.get("image_path") or payload.get("audience") != "selected"):
                raise ValueError("文字訊息請使用手動選擇對象。")
            if not channels.access_token():
                raise ValueError("請先設定 LINE OA 憑證。")
            audience = payload.get("audience")
            if user['role'] != 'platform_admin' and (audience != 'selected' or payload.get('image_path')):
                raise ValueError('請選擇文字或圖片訊息，以及本組織的對象。')
            with app.database_connection() as conn:
                selected = select_contacts(conn, audience, payload.get("ids"))
            if any(not reports.allowed_contact(user, row) for row in selected):
                raise ValueError('發送對象不在所屬組織範圍。')
            report_title = "手動圖片"
            messages = []
            prepared = composer.prepare(composition, user, selected) if composition is not None else None
            if not message_text and prepared is None:
                source = Path(str(payload.get("image_path", "")))
            if prepared is not None:
                messages = composer.build(prepared, publish_image, verify_public_image)
                source, url, report_title = '', '', {'images':'多圖訊息', 'card':'圖文卡片', 'carousel':'輪播卡片', 'imagemap':'圖文訊息'}[prepared['format']] + '：' + prepared['alt_text'][:32]
            elif message_text:
                source, url, report_title = "", "", "文字訊息：" + message_text.strip()[:32]
            else:
                url, content = publish_image(source, app.public_base_url())
                verify_public_image(url, content)
            organization_ids = {row['organization_id'] for row in selected}
            organization_id = user['organization_id'] if user['role'] != 'platform_admin' else (next(iter(organization_ids)) if message_text and len(organization_ids) == 1 else '')
            if prepared and user['role'] == 'platform_admin':
                organization_id = next((item['asset']['organization_id'] for item in prepared['items'] if item['asset']['organization_id']), '')
            with app.database_connection() as conn:
                conn.execute('INSERT INTO send_jobs (channel_id,job_id,audience,image_path,image_url,actor,report_title,scheduled_at,message_text,status,organization_id,messages_json) VALUES (current_channel(),?,?,?,?,?,?,?,?,?,?,?)',
                             (job_id, audience, str(source), url, actor, report_title, scheduled_at, message_text, 'scheduled' if scheduled_at else 'queued', organization_id, json.dumps(messages, ensure_ascii=False)))
                conn.executemany("INSERT INTO send_deliveries (job_id,recipient_id,label,retry_key) VALUES (?,?,?,?)",
                                 [(job_id, r["recipient_id"], contact_label(r), str(uuid4())) for r in selected])
                reports.audit(conn, actor, "send.create", job_id, f"{report_title} · {len(selected)} 個聊天室", organization_id)
            if not scheduled_at:
                self.pool.submit(self.run, job_id)
            return job_status(job_id)[0]

    def run(self, job_id):
        # Workers never inherit an HTTP thread's OA; derive it from the persisted job.
        with app.database_connection() as conn:
            row = conn.execute('SELECT channel_id FROM send_jobs WHERE job_id=?', (job_id,)).fetchone()
        if row:
            with channels.use(row[0]):
                self.run_channel(job_id)

    def run_channel(self, job_id):
        try:
            if not channels.access_token():
                raise ValueError('OA 尚未設定。')
            with app.database_connection() as conn:
                conn.row_factory = sqlite3.Row
                job = conn.execute('SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND job_id=?', (job_id,)).fetchone()
                rows = conn.execute("SELECT * FROM send_deliveries WHERE job_id=?", (job_id,)).fetchall()
                claimed = conn.execute("UPDATE send_jobs SET status='running' WHERE send_jobs.channel_id=current_channel() AND job_id=? AND status='queued'", (job_id,)).rowcount
                if not claimed:
                    return
            if job['scheduled_at'] and (datetime.now(timezone.utc) - datetime.fromisoformat(job['scheduled_at'])).total_seconds() > 600:
                with app.database_connection() as conn:
                    conn.execute("UPDATE send_jobs SET status='missed',error='等待發送逾期，未補發。' WHERE send_jobs.channel_id=current_channel() AND job_id=?", (job_id,))
                    conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=?", (job_id,))
                return
            for row in rows:
                recipient_id = row["recipient_id"]
                with app.database_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    current = conn.execute('SELECT active FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                    skip = self.closing.is_set() or not current or not current[0]
                    if job['organization_id']:
                        org=next((o for o in reports.organizations() if o['org_id']==job['organization_id']),None)
                        if not org or not org['active'] or not org['messaging_enabled']:
                            skip=True
                        if job['messages_json'] != '[]':
                            contact = conn.execute('SELECT organization_id FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                            if not contact or contact[0] != job['organization_id']:
                                skip = True
                    if job["actor"] and job["actor"] != "本機管理員":
                        actor = reports.actor_user(job["actor"],job['organization_id'])
                        if not reports.can_send(actor) or not reports.module_enabled(actor,'messaging'):
                            skip = True
                        elif actor['role'] != 'platform_admin':
                            contact = conn.execute('SELECT * FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                            if (not reports.same_organization(actor, job['organization_id']) or not contact
                                    or not reports.allowed_contact(actor, dict(contact))):
                                skip = True
                    conn.execute("UPDATE send_deliveries SET status=? WHERE job_id=? AND recipient_id=?",
                                 ("cancelled" if skip else "sending", job_id, recipient_id))
                if skip:
                    continue
                status, request_id, error = "accepted", "", ""
                try:
                    extra = {"text": job["message_text"]} if job["message_text"] else {}
                    if job['messages_json'] != '[]':
                        extra = {'messages': json.loads(job['messages_json'])}
                    request_id = send_push(channels.access_token(), recipient_id,
                                           job["image_url"], retry_key=row["retry_key"], **extra)
                except ValueError as exc:
                    error = str(exc)
                    status = "unknown" if "不明" in error else "failed"
                with app.database_connection() as conn:
                    conn.execute("UPDATE send_deliveries SET status=?,request_id=?,error=? WHERE job_id=? AND recipient_id=?",
                                 (status, request_id, error, job_id, recipient_id))
            with app.database_connection() as conn:
                conn.execute("UPDATE send_jobs SET status='finished' WHERE send_jobs.channel_id=current_channel() AND job_id=?", (job_id,))
        except Exception:
            with app.database_connection() as conn:
                conn.execute("UPDATE send_deliveries SET status='unknown' WHERE job_id=? AND status='sending'", (job_id,))
                conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=? AND status='pending'", (job_id,))
                conn.execute("UPDATE send_jobs SET status='interrupted',error='發送中斷，請確認結果後再操作。' WHERE send_jobs.channel_id=current_channel() AND job_id=?", (job_id,))

    def close(self):
        self.closing.set()
        if hasattr(self, 'scheduler'):
            self.scheduler.join(timeout=5)
        self.pool.shutdown(wait=True)


class AdminHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        pass

    def respond(self, code, data, content_type="application/json; charset=utf-8", headers=None):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        if getattr(self, 'response_cookie', None):
            self.send_header('Set-Cookie', self.response_cookie)
            self.response_cookie = None
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, require_token=True):
        self.auth_method = 'local'
        self.identity = "本機管理員"
        self.user = {"email": self.identity, "display_name": "本機管理員", "role": "platform_admin", "organization_id": "", "department": ""}
        for name in ("Host", "Origin", "Authorization", "Cookie", "X-CSRF-Token", "X-Forwarded-Proto", "X-Workspace-View-As", "X-Workspace-Organization", "X-Workspace-Preview-Organization"):
            if len(self.headers.get_all(name, [])) > 1:
                self.respond(403, {"error": "不接受重複的驗證標頭。"})
                return False
        public_host = self.server.public_host
        if public_host and self.headers.get('Host', '').lower() == public_host:
            return site_auth.authorize(self)
        expected_host = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        if (self.headers.get("Host") != expected_host or (origin and origin != "http://" + expected_host)
                or any(name in self.headers for name in ("CF-Connecting-IP", "X-Forwarded-For", "X-Forwarded-Proto"))):
            self.respond(403, {"error": "請從本機控制台或已設定的管理網址登入。"})
            return False
        if require_token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.token):
            query = getattr(self, 'query', {})
            query_token = query.get('token', '') if isinstance(query, dict) else ''
            if query_token and hmac.compare_digest(query_token, self.server.token):
                return self.apply_view()
            return site_auth.authorize(self)
        return self.apply_view() if require_token else True

    def apply_view(self):
        self.principal = self.identity
        # 視角預覽會把 self.user 換成被預覽者；查看紀錄依實際登入者判斷。
        self.principal_role = self.user['role']
        self.preview = False
        self.preview_edit = False
        org=self.headers.get('X-Workspace-Organization')
        if org and self.user['role']!='platform_admin':
            # Header values are ASCII; legacy organization keys may contain Chinese.
            from urllib.parse import unquote
            self.user=reports.login_account(self.identity,unquote(org))
            if not self.user:
                self.respond(403,{'error':'此組織成員資格已失效，請切換組織。'})
                return False
        target = self.headers.get("X-Workspace-View-As", "").strip().lower()
        if not target:
            return True
        if not reports.manager(self.user) or not self.server.workspace_ready:
            self.respond(403, {"error": "只有管理員可以切換成員視角。"})
            return False
        from urllib.parse import unquote
        preview_org=unquote(self.headers.get('X-Workspace-Preview-Organization','')) or (self.user['organization_id'] if self.user['role']!='platform_admin' else None)
        user = reports.account(target,preview_org)
        if not user or (target,user['organization_id']) not in {(row['email'],row['organization_id']) for row in reports.view_options(self.user)}:
            self.respond(403, {"error": "此成員帳號已停用或角色已變更，請返回管理員視角。"})
            return False
        
        # 乙級管理員視角切換編輯狀態判斷（甲級只能檢視）
        if self.user['role'] == 'org_admin' and self.headers.get('X-Workspace-Preview-Edit') in ('1', 'true'):
            self.preview_edit = True

        self.identity, self.user, self.preview = user["email"], user, True
        return True

    def select_line_channel(self):
        if not self.server.workspace_ready:
            return True
        ids = self.headers.get_all('X-Line-Channel', [])
        if len(ids) > 1:
            self.respond(400, {'error': 'OA 標頭不能重複。'})
            return False
        channel_id = ids[0] if ids else ''
        globals_ = {'/api/session', '/api/organizations', '/api/view-options', '/api/settings',
                    '/api/accounts/save', '/api/organizations/save', '/api/memberships/save',
                    '/api/oa-list', '/api/personnel', '/api/personnel/save', '/api/org-settings/save'}
        registry = self.path.startswith('/api/channels')
        if registry or re.fullmatch(r"/api/chat/media/[0-9a-zA-Z_]+", self.path):
            return True
        try:
            if channel_id:
                row = channels.authorize(channel_id, self.user)
                if self.user['role'] != 'platform_admin':
                    self.user = reports.account(self.identity, row['org_id'])
                    if not self.user:
                        raise ValueError('組織成員資格已失效。')
                channels._current.set(channel_id)
            elif self.path not in globals_:
                raise ValueError('請先選擇工作區與 LINE OA。')
        except ValueError as exc:
            self.respond(403, {'error': str(exc)})
            return False
        return True

    def first_admin_setup(self):
        """權限規格第 9 節：尚無啟用中的平台管理員時，只能從本機控制台建立第一位平台管理員。"""
        if getattr(self, 'auth_method', '') != 'local' or self.preview:
            self.respond(403, {'error': '首次設定只能從本機控制台開啟的管理後台進行。'})
            return
        if reports.has_platform_admin():
            self.respond(403, {'error': '系統已完成首次設定；新增平台管理員請使用 create_admin.py。'})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192 or self.headers.get_content_type() != "application/json":
                raise ValueError("請求格式不正確。")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("請求格式不正確。")
            email = reports.create_platform_admin(payload.get('email'), payload.get('display_name', ''), '本機管理員（首次設定）')
            raw = site_auth.issue_activation(email, '本機管理員（首次設定）')
        except (ValueError, TypeError) as error:
            self.respond(400, {"error": str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "請求格式不正確。"})
            return
        public = f"https://{self.server.public_host}/login#setup={raw}" if self.server.public_host else ''
        self.respond(200, {'email': email, 'url': public, 'local_url': f"http://127.0.0.1:{self.server.server_port}/login#setup={raw}", 'expires_in': 1800})

    def admin_only(self):
        if not reports.manager(self.user):
            self.respond(403, {"error": "此功能僅供管理員使用。"})
            return False
        return True

    def scoped_contacts(self):
        with app.database_connection() as conn:
            rows = recipients.list_contacts(conn)
        return [row for row in rows if reports.allowed_contact(self.user, row)]

    def scoped_tags(self):
        with app.database_connection() as conn:
            rows = recipients.list_tags(conn)
        return [{"id": r["tag_id"], "tag_id": r["tag_id"], "name": r["name"], "color": r["color"]} for r in rows]

    def do_GET(self):
        with channels.use(''):
            self.get_request()

    def get_request(self):
        parsed = urlsplit(self.path)
        self.path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.query = query
        if site_auth.handle_get(self):
            return
        files = {"/": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/index.html": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/admin.js": (app.BASE_DIR / "web" / "admin.js", "text/javascript; charset=utf-8"),
                 "/app.css": (app.BASE_DIR / "web" / "app.css", "text/css; charset=utf-8"),
                 "/channels.js": (app.BASE_DIR / "web" / "channels.js", "text/javascript; charset=utf-8"),
                 "/chat.js": (app.BASE_DIR / "web" / "chat.js", "text/javascript; charset=utf-8"),
                 "/workspace.js": (app.BASE_DIR / "web" / "workspace.js", "text/javascript; charset=utf-8"),
                 "/account-security.js": (app.BASE_DIR / "web" / "account-security.js", "text/javascript; charset=utf-8"),
                 "/composer.js": (app.BASE_DIR / "web" / "composer.js", "text/javascript; charset=utf-8"),
                 "/workspace-theme.css": (app.BASE_DIR / "web" / "workspace-theme.css", "text/css; charset=utf-8"),
                 "/density.css": (app.BASE_DIR / "web" / "density.css", "text/css; charset=utf-8"),
                 "/management.js": (app.BASE_DIR / "web" / "management.js", "text/javascript; charset=utf-8"),
                 "/management.css": (app.BASE_DIR / "web" / "management.css", "text/css; charset=utf-8"),
                 "/admin.css": (app.BASE_DIR / "web" / "admin.css", "text/css; charset=utf-8")}
        brand = app.BASE_DIR / 'web' / 'assets' / 'brand'
        for variant in ('light',):
            for extension, mime in (('png', 'image/png'), ('ico', 'image/x-icon')):
                name = f'line-automation-logo-{variant}.{extension}'
                files['/assets/brand/' + name] = (brand / name, mime)
        files['/favicon.ico'] = (brand / 'line-automation-logo-light.ico', 'image/x-icon')
        if re.fullmatch(r"/api/chat/avatar/[0-9a-zA-Z_]+", self.path) or self.path == "/api/chat/avatar":
            rid = self.path.rsplit('/', 1)[1] if '/' in self.path and self.path != "/api/chat/avatar" else (query.get('recipient_id') or '')
            try:
                with app.database_connection() as conn:
                    result = chat.get_recipient_avatar(conn, rid)
                    if not result:
                        self.respond(404, {"error": "找不到頭像。"})
                        return
                    data, content_type = result
                    self.respond(200, data, content_type=content_type, headers={'Cache-Control': 'public, max-age=86400'})
                    return
            except Exception as exc:
                self.respond(404, {"error": str(exc)})
                return
        if not self.authorized(require_token=self.path not in files):
            return
        if self.path not in files and not self.select_line_channel():
            return
        read_routes = {
            "/api/channels", "/api/session", "/api/organizations",
            "/api/chat-notes", "/api/chat-notes/global", "/api/chat-notes/trash",
            "/api/chat-notes/categories", "/api/chat-notes/tags", "/api/chat-notes/export",
            "/api/saved-filters",
            "/api/cases", "/api/cases/prefix", "/api/cases/export",
            "/api/template-packs", "/api/template-packs/templates", "/api/categories",
            "/api/chat/rooms", "/api/chat/messages", "/api/chat/canned-replies",
            "/api/chat/response-hours", "/api/chat/media/stats", "/api/chat/export"
        }
        if (self.path not in files and self.path not in read_routes 
            and not re.fullmatch(r"/api/cases/[0-9a-f]{32}", self.path)
            and not re.fullmatch(r"/api/chat/media/[0-9a-zA-Z_]+", self.path)):
            if self.user['role'] in {'operator', 'collaborator'} and self.path in {'/api/view-options','/api/settings'}:
                self.respond(403, {'error':'此功能僅供管理員使用。'})
                return
            if not reports.operator(self.user):
                self.respond(403, {'error':'沒有此功能的存取權限。'})
                return

        # 甲級平台管理員查閱客戶營運內容時寫入操作紀錄
        if getattr(self, 'principal_role', self.user['role']) == 'platform_admin' and (self.path.startswith('/api/chat-notes') or self.path in {'/api/cases', '/api/chat/messages', '/api/contacts'}):
            with app.database_connection() as conn:
                # 記在該 OA 所屬組織，讓組織管理員在操作紀錄看得到（權限規格 6.2）。
                reports.audit(conn, getattr(self, 'principal', self.identity), "vendor.view", channels.current_id() or "all", f"平台管理員檢視客戶營運內容（{self.path}）",
                              channels.current_organization_id() or '')

        if self.path in files:
            path, mime = files[self.path]
            self.respond(200, path.read_bytes(), mime)
        elif self.path == '/api/channels':
            self.respond(200, channels.catalogue(self.user))
        elif re.fullmatch(r'/api/channels/shares/[0-9a-f]{32}', self.path):
            try:
                self.respond(200, channels.share_recipients(self.path.rsplit('/', 1)[1], self.user))
            except ValueError as exc:
                self.respond(403, {'error': str(exc)})
        elif self.path == "/api/session":
            self.respond(200, {"identity": self.identity, "user": self.user, "role": self.user["role"],
                               "principal": self.principal, "preview": self.preview, "auth": site_auth.status(self),
                               "memberships": [m for m in reports.memberships(self.identity) if m['active'] and m['org_active'] and m['role'] in {'org_admin','operator','collaborator'}] if not self.preview and self.server.workspace_ready else [],
                               "modules": {'messaging': reports.module_enabled(self.user, 'messaging')},
                               "needs_setup": getattr(self, 'auth_method', '') == 'local' and not reports.has_platform_admin(),
                               "limits": limits.as_dict()})
        elif self.path == '/api/organizations':
            self.respond(200,{'organizations':[o for o in reports.organizations() if self.user['role']=='platform_admin' or reports.same_organization(self.user,o['org_id'])],
                              'memberships':[m for m in reports.memberships() if self.user['role']=='platform_admin' or (self.user['role']=='org_admin' and reports.same_organization(self.user,m['org_id']))]})
        elif self.path == "/api/view-options":
            self.respond(200, {"users": [{key: row[key] for key in ("email", "display_name", "organization_id", "department", "role", "organization_name")}
                                           for row in reports.view_options(self.user)]})
        elif self.path == "/api/activity":
            self.respond(200, {"events": reports.activity(self.user)})
        elif self.path == "/api/settings":
            self.respond(200, {"remote_enabled": bool(self.server.public_host),
                               "admin_host": self.server.public_host,
                               "users": reports.scoped_users(self.user),
                               "line_configured": bool(channels.get()),
                               "public_base": os.environ.get("PUBLIC_BASE_URL", ""),
                               "role": self.user['role']})
        elif self.path == "/api/contacts":
            self.respond(200, {"contacts": self.scoped_contacts(), "tags": self.scoped_tags()})
        elif self.path == "/api/tags":
            self.respond(200, {"tags": self.scoped_tags(), "limit": 100, "count": len(self.scoped_tags())})
        elif self.path == "/api/chat-notes":
            with app.database_connection() as conn:
                self.respond(200, chat_notes.list_chat_notes(conn, query.get('recipient_id', '')))
        elif self.path == "/api/chat-notes/global":
            with app.database_connection() as conn:
                self.respond(200, chat_notes.list_global_chat_notes(conn, query, self.user['role']))
        elif self.path == "/api/chat-notes/trash":
            with app.database_connection() as conn:
                self.respond(200, {"trash": chat_notes.list_trash_notes(conn, query.get('recipient_id', ''))})
        elif self.path == "/api/chat-notes/categories":
            with app.database_connection() as conn:
                self.respond(200, chat_notes.list_note_categories(conn))
        elif self.path == "/api/chat-notes/tags":
            with app.database_connection() as conn:
                self.respond(200, chat_notes.list_note_tags(conn))
        elif self.path == "/api/chat-notes/export":
            if self.user['role'] not in {'org_admin', 'operator', 'platform_admin'}:
                self.respond(403, {'error': '沒有匯出記事的權限。'})
                return
            with app.database_connection() as conn:
                content, mime, filename = chat_notes.export_chat_notes(conn, query, query.get('format', 'csv'), actor=self.identity)
                from urllib.parse import quote
                ext = "json" if query.get('format', 'csv').lower() == "json" else ("md" if query.get('format', 'csv').lower() in ("md", "markdown") else "csv")
                ascii_name = f"chat_notes_export.{ext}"
                self.respond(200, content, content_type=mime, headers={'Content-Disposition': f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'})
        elif self.path == "/api/saved-filters":
            with app.database_connection() as conn:
                self.respond(200, chat_notes.list_saved_filters(conn))
        elif self.path == "/api/cases":
            with app.database_connection() as conn:
                self.respond(200, {"cases": cases.list_cases(conn, status=query.get('status'), category=query.get('category'), subject_id=query.get('subject_id'), query=query.get('q'))})
        elif self.path == "/api/cases/prefix":
            with app.database_connection() as conn:
                self.respond(200, {"prefix": cases.get_or_init_prefix(conn)})
        elif self.path == "/api/cases/export":
            if self.user['role'] != 'org_admin':
                self.respond(403, {'error': '只有管理員可以匯出案件。'})
                return
            with app.database_connection() as conn:
                content, mime, filename = cases.export_cases(
                    conn, query, query.get('format', 'csv'),
                    include_activities=query.get('include_activities') in ('1', 'true'),
                    include_contacts=query.get('include_contacts') in ('1', 'true'),
                    actor=self.identity
                )
                from urllib.parse import quote
                ext = "xlsx" if query.get('format', 'csv').lower() == "xlsx" else "csv"
                ascii_name = f"cases_export.{ext}"
                self.respond(200, content, content_type=mime, headers={'Content-Disposition': f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'})
        elif re.fullmatch(r"/api/cases/[0-9a-f]{32}", self.path):
            case_id = self.path.rsplit("/", 1)[1]
            with app.database_connection() as conn:
                c = cases.get_case(conn, case_id)
                self.respond(200 if c else 404, {"case": c} if c else {"error": "找不到此案件。"})
        elif self.path == "/api/template-packs":
            with app.database_connection() as conn:
                self.respond(200, {"packs": template_packs.list_all_packs(conn, self.user.get('organization_id'), channels.current_id())})
        elif self.path == "/api/template-packs/templates":
            with app.database_connection() as conn:
                self.respond(200, template_packs.get_oa_enabled_templates(conn, channels.current_id(), query.get('contact_name', '')))
        elif self.path == "/api/categories":
            with app.database_connection() as conn:
                self.respond(200, template_packs.list_oa_categories(conn, channels.current_id()))
        elif self.path == "/api/chat/rooms":
            with app.database_connection() as conn:
                res = chat.list_chat_rooms(conn, status=query.get('status'), query=query.get('q'), limit=query.get('limit'), offset=query.get('offset'), actor=self.identity)
            self.respond(200, res)
        elif self.path == "/api/oa-list":
            self.respond(200, {"channels": channels.oa_list(self.user)})
        elif self.path == "/api/personnel":
            # 人員與權限只給乙級（管理員）；甲級在「組織」頁管理管理員帳號。
            org_id = self.user.get('organization_id')
            if self.user['role'] != 'org_admin' or not org_id:
                self.respond(403, {'error': '人員與權限僅供管理員使用。'})
                return
            with app.database_connection() as conn:
                conn.row_factory = sqlite3.Row
                members = conn.execute("""
                    SELECT m.email, m.role, m.department, m.active, u.display_name
                    FROM organization_members m
                    JOIN workspace_users u ON u.email = m.email
                    WHERE m.org_id=?
                    ORDER BY m.role, m.email
                """, (org_id,)).fetchall()
                member_list = []
                for m in members:
                    md = dict(m)
                    access_rows = conn.execute("SELECT channel_id FROM oa_member_access WHERE email=? AND org_id=?", (m['email'], org_id)).fetchall()
                    md['channel_ids'] = [r[0] for r in access_rows]
                    member_list.append(md)
                org_channels = conn.execute("SELECT channel_id, name, basic_id FROM line_channels WHERE org_id=? AND active=1", (org_id,)).fetchall()
                self.respond(200, {
                    "members": member_list,
                    "channels": [dict(c) for c in org_channels]
                })
        elif self.path == "/api/chat/messages":
            cid = query.get('recipient_id') or query.get('chat_id') or ''
            if getattr(self, 'principal_role', self.user['role']) == 'platform_admin' and channels.current_id():
                with app.database_connection() as conn:
                    tz_taipei = timezone(timedelta(hours=8))
                    t_str = datetime.now(tz_taipei).strftime('%Y-%m-%d %H:%M')
                    org_id = channels.current_organization_id() or ''
                    last = conn.execute("SELECT created_at FROM audit_events WHERE actor=? AND action='vendor.view' AND channel_id=? ORDER BY event_id DESC LIMIT 1", (getattr(self, 'principal', self.identity), channels.current_id())).fetchone()
                    should_log = True
                    if last:
                        try:
                            from datetime import datetime as dt
                            last_time = dt.fromisoformat(last[0].replace('Z', '+00:00'))
                            if (datetime.now(timezone.utc) - last_time).total_seconds() < 60:
                                should_log = False
                        except Exception:
                            pass
                    if should_log:
                        reports.audit(conn, getattr(self, 'principal', self.identity), "vendor.view", channels.current_id(), f"供應商曾於 {t_str} 查看", org_id)
            with app.database_connection() as conn:
                if query.get('q'):
                    res = chat.search_messages(conn, chat_id=cid, query=query.get('q'), limit=query.get('limit'))
                else:
                    res = chat.list_messages(conn, chat_id=cid, limit=query.get('limit'), before_id=query.get('before_id'))
            self.respond(200, res)
        elif self.path == "/api/chat/canned-replies":
            with app.database_connection() as conn:
                res = chat.list_canned_replies(conn, category=query.get('category'), search=query.get('q'))
            self.respond(200, res)
        elif self.path == "/api/chat/response-hours":
            with app.database_connection() as conn:
                res = chat.get_response_hours(conn)
            self.respond(200, res)
        elif self.path == "/api/chat/media/stats":
            with app.database_connection() as conn:
                res = chat.get_media_storage_stats(conn)
            self.respond(200, res)
        elif self.path == "/api/chat/export":
            if self.user['role'] == 'platform_admin':
                self.respond(403, {'error': '平台管理員無法匯出客戶營運資料。'})
                return
            cid = query.get('recipient_id') or query.get('chat_id') or ''
            with app.database_connection() as conn:
                content, mime, filename = chat.export_chat_history(
                    conn, cid, format=query.get('format', 'txt'), actor=self.identity
                )
                from urllib.parse import quote
                ext = "csv" if query.get('format', 'txt').lower() == "csv" else "txt"
                ascii_name = f"chat_export.{ext}"
                self.respond(200, content, content_type=mime, headers={'Content-Disposition': f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'})
        elif re.fullmatch(r"/api/chat/media/[0-9a-zA-Z_]+", self.path):
            msg_id = self.path.rsplit('/', 1)[1]
            try:
                with app.database_connection() as conn:
                    msg_row = conn.execute(
                        "SELECT channel_id, message_type, text_content FROM line_messages WHERE message_id=?",
                        (msg_id,)
                    ).fetchone()
                    if not msg_row:
                        raise ValueError("找不到指定的訊息。")
                    msg_channel_id, msg_type, msg_text = msg_row[0], msg_row[1], msg_row[2]
                    channels.authorize(msg_channel_id, self.user)
                    with channels.use(msg_channel_id):
                        data, content_type = chat.get_chat_media(conn, msg_id)
                        from urllib.parse import quote
                        filename = (msg_text or f"media_{msg_id}").strip()
                        if msg_type == "file" and "." not in filename:
                            if "pdf" in content_type: filename += ".pdf"
                            elif "zip" in content_type: filename += ".zip"
                        elif msg_type == "image" and not filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                            ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
                            if ext == "jpeg": ext = "jpg"
                            filename = f"image_{msg_id}.{ext}"
                        elif msg_type == "video" and not filename.lower().endswith(".mp4"):
                            filename = f"video_{msg_id}.mp4"
                        elif msg_type == "audio" and not filename.lower().endswith((".m4a", ".mp3", ".wav")):
                            filename = f"audio_{msg_id}.m4a"

                        headers = {}
                        if msg_type == "file":
                            headers['Content-Disposition'] = f'attachment; filename="{quote(filename)}"; filename*=UTF-8\'\'{quote(filename)}'
                        else:
                            headers['Content-Disposition'] = f'inline; filename="{quote(filename)}"; filename*=UTF-8\'\'{quote(filename)}'
                        self.respond(200, data, content_type=content_type, headers=headers)
            except ValueError as exc:
                self.respond(404, {"error": str(exc)})
        elif re.fullmatch(r"/api/chat/avatar/[0-9a-zA-Z_]+", self.path) or self.path == "/api/chat/avatar":
            rid = self.path.rsplit('/', 1)[1] if '/' in self.path and self.path != "/api/chat/avatar" else (query.get('recipient_id') or '')
            try:
                with app.database_connection() as conn:
                    result = chat.get_recipient_avatar(conn, rid)
                    if not result:
                        self.respond(404, {"error": "找不到頭像。"})
                        return
                    data, content_type = result
                    self.respond(200, data, content_type=content_type, headers={'Cache-Control': 'public, max-age=86400'})
            except Exception as exc:
                self.respond(404, {"error": str(exc)})
        elif self.path == "/api/jobs":
            self.respond(200, {"jobs": job_status(user=self.user)})
        elif re.fullmatch(r"/api/jobs/[0-9a-f-]{36}", self.path):
            jobs = job_status(self.path.rsplit("/", 1)[1], user=self.user)
            self.respond(200 if jobs else 404, {"jobs": jobs})
        else:
            self.respond(404, {"error": "找不到頁面。"})

    def do_POST(self):
        with channels.use(''):
            self.post_request()

    def post_request(self):
        if site_auth.handle_post(self):
            return
        if not self.authorized():
            return
        if self.path == '/api/setup/first-admin':
            self.first_admin_setup()
            return
        if not self.select_line_channel():
            return
        if not reports.operator(self.user):
            self.respond(403, {'error':'沒有操作權限。'})
            return

        if self.preview and not getattr(self, 'preview_edit', False):
            self.respond(403, {'error': '視角預覽僅供檢視，請先切換為編輯狀態或返回原帳號操作。'})
            return

        allowed_collaborator_posts = {
            '/api/contacts/bulk', '/api/contact', '/api/tags/save', '/api/tags/delete',
            '/api/chat-notes', '/api/chat-notes/save', '/api/chat-notes/delete',
            '/api/chat-notes/pin', '/api/chat-notes/lock', '/api/chat-notes/restore', '/api/chat-notes/convert-to-case',
            '/api/chat-notes/complete', '/api/chat-notes/task', '/api/cases/task',
            '/api/saved-filters', '/api/saved-filters/save', '/api/saved-filters/delete',
            '/api/cases', '/api/cases/save', '/api/cases/transition', '/api/cases/activity',
            '/api/template-packs/save', '/api/template-packs/delete', '/api/template-packs/copy', '/api/template-packs/lock',
            '/api/templates/save', '/api/templates/delete', '/api/templates/batch-delete', '/api/templates/copy', '/api/templates/move',
            '/api/templates/lock', '/api/templates/create-from-source',
            '/api/template-packs/toggle', '/api/categories/preview', '/api/categories/apply',
            '/api/categories/save', '/api/categories/delete', '/api/categories/reorder',
            '/api/chat/room-preference', '/api/chat/mark-read', '/api/chat/status', '/api/chat/media/cleanup'
        }
        allowed_operator_posts = allowed_collaborator_posts | {
            '/api/send', '/api/jobs/cancel', '/api/assets/upload', '/api/channels/save',
            '/api/channels/verify', '/api/channels/active', '/api/chat/send',
            '/api/chat/canned-replies/save', '/api/chat/canned-replies/delete', '/api/chat/response-hours/save',
            '/api/chat-notes/categories/save', '/api/chat-notes/categories/merge', '/api/chat-notes/categories/delete',
            '/api/chat-notes/tags/save', '/api/chat-notes/tags/merge', '/api/chat-notes/tags/cleanup', '/api/chat-notes/tags/delete'
        }

        if self.user['role'] == 'collaborator' and (self.path not in allowed_collaborator_posts and not re.fullmatch(r'/api/cases/[0-9a-f]{32}(/lock)?', self.path)):
            self.respond(403, {'error': '協作人員無法傳送訊息或變更系統發送設定。'})
            return

        if self.user['role'] == 'operator' and (self.path not in allowed_operator_posts and not re.fullmatch(r'/api/cases/[0-9a-f]{32}(/(lock|notify))?', self.path)):
            self.respond(403, {'error': '操作人員不能修改聯絡對象分類、來源或帳號授權。'})
            return

        admin_only_posts = {'/api/organizations/save'}
        if self.path in admin_only_posts and self.user['role'] != 'platform_admin':
            self.respond(403, {'error': '模組歸屬及來源設定由平台管理員管理。'})
            return

        org_admin_only_posts = {
            '/api/memberships/save', '/api/accounts/save',
            '/api/chat-notes/purge', '/api/org-settings/notes-policy'
        }
        if self.path in org_admin_only_posts and self.user['role'] not in {'platform_admin', 'org_admin'}:
            self.respond(403, {'error': '管理員才能變更成員與授權設定。'})
            return

        # 平台管理員對客戶營運內容只有閱讀權，禁止傳送訊息與建立/修改客戶案件/記事/聯絡人
        customer_write_paths = {
            '/api/chat/room-preference', '/api/chat/send', '/api/send', '/api/jobs/cancel', '/api/contact', '/api/contacts/bulk',
            '/api/tags/save', '/api/tags/delete', '/api/chat-notes', '/api/chat-notes/save',
            '/api/chat-notes/delete', '/api/chat-notes/pin', '/api/chat-notes/lock', '/api/chat-notes/restore',
            '/api/chat-notes/purge', '/api/chat-notes/convert-to-case', '/api/chat-notes/complete', '/api/chat-notes/task', '/api/cases/task',
            '/api/chat-notes/categories/save', '/api/chat-notes/categories/merge', '/api/chat-notes/categories/delete',
            '/api/chat-notes/tags/save', '/api/chat-notes/tags/merge', '/api/chat-notes/tags/cleanup', '/api/chat-notes/tags/delete',
            '/api/org-settings/notes-policy',
            '/api/saved-filters', '/api/saved-filters/save', '/api/saved-filters/delete',
            '/api/cases', '/api/cases/save', '/api/cases/transition', '/api/cases/activity',
            '/api/template-packs/save', '/api/template-packs/delete', '/api/template-packs/copy', '/api/template-packs/lock',
            '/api/templates/save', '/api/templates/delete', '/api/templates/batch-delete', '/api/templates/copy', '/api/templates/move',
            '/api/templates/lock', '/api/templates/create-from-source',
            '/api/categories/apply', '/api/categories/save', '/api/categories/delete', '/api/categories/reorder',
            '/api/chat/canned-replies/save', '/api/chat/canned-replies/delete', '/api/chat/response-hours/save', '/api/chat/status'
        }
        if self.user['role'] == 'platform_admin' and (self.path in customer_write_paths or re.fullmatch(r'/api/cases/[0-9a-f]{32}(/(lock|notify))?', self.path)):
            self.respond(403, {'error': '平台管理員對客戶營運內容只有閱讀權，無法修改或傳送。'})
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
            maximum = 12 * 1024 * 1024 if self.path == '/api/assets/upload' else 65536
            if size <= 0 or size > maximum or self.headers.get_content_type() != "application/json":
                raise ValueError("請求格式不正確。")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("請求格式不正確。")

            actor_label = self.identity
            if self.preview:
                actor_label = f"{self.principal}（於 {self.identity} 視角下）"

            if self.path == '/api/channels/save':
                self.respond(200, channels.save(payload, self.user))
            elif self.path == '/api/channels/verify':
                self.respond(200, channels.verify(payload.get('channel_id'), self.user))
            elif self.path == '/api/channels/active':
                self.respond(200, channels.set_active(payload, self.user))
            elif self.path == '/api/channels/share':
                self.respond(200, channels.share(payload, self.user))
            elif self.path == '/api/channels/assign':
                self.respond(200, channels.assign(payload, self.user))
            elif self.path == '/api/channels/transfer':
                self.respond(200, channels.transfer(payload, self.user))
            elif self.path == '/api/tags/save':
                with app.database_connection() as conn:
                    tid = recipients.save_tag(conn, payload.get('name'), payload.get('color'), payload.get('id'))
                    reports.audit(conn, actor_label, "tag.save", tid, f"儲存標籤「{payload.get('name')}」", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'tag_id': tid, 'tag': {'id': tid, 'name': payload.get('name'), 'color': payload.get('color')}})
            elif self.path == '/api/tags/delete':
                with app.database_connection() as conn:
                    recipients.delete_tag(conn, payload.get('id'))
                    reports.audit(conn, actor_label, "tag.delete", str(payload.get('id')), "刪除標籤", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True})
            elif self.path == '/api/contacts/bulk':
                action = payload.get('action')
                ids = payload.get('ids') or payload.get('contact_ids') or []
                res_data = {'ok': True}
                with app.database_connection() as conn:
                    if action in {'add_tags', 'remove_tags'}:
                        tag_ids = payload.get('tag_ids', [])
                        res = recipients.bulk_update_tags(conn, ids, tag_ids, 'add' if action == 'add_tags' else 'remove')
                        reports.audit(conn, actor_label, "contacts.bulk_tag", f"{len(ids)} contacts", "批次更新標籤", self.user.get('organization_id', ''))
                        res_data.update(res)
                    else:
                        raise ValueError('不支援的操作。')
                self.respond(200, res_data)
            elif self.path in ('/api/chat-notes', '/api/chat-notes/save'):
                action = payload.get('action', 'save')
                with app.database_connection() as conn:
                    if action == 'delete':
                        chat_notes.delete_chat_note(conn, payload.get('note_id') or payload.get('id'), self.user['role'], actor_label)
                        reports.audit(conn, actor_label, "chat_note.delete", payload.get('note_id') or payload.get('id', ''), "刪除對話記事", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True})
                    else:
                        res = chat_notes.save_chat_note(conn, payload, actor_label, self.user['role'])
                        reports.audit(conn, actor_label, "chat_note.save", res.get('recipient_id', ''), "儲存對話記事", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True, 'note': res})
            elif self.path == '/api/chat-notes/delete':
                with app.database_connection() as conn:
                    chat_notes.delete_chat_note(conn, payload.get('note_id') or payload.get('id'), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note.delete", payload.get('id', ''), "刪除對話記事", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True})
            elif self.path == '/api/chat-notes/pin':
                with app.database_connection() as conn:
                    res = chat_notes.toggle_note_pin(conn, payload.get('note_id') or payload.get('id'))
                    self.respond(200, {'ok': True, **res})
            elif self.path == '/api/chat-notes/lock':
                with app.database_connection() as conn:
                    res = chat_notes.toggle_note_lock(conn, payload.get('note_id') or payload.get('id'), self.user['role'])
                    self.respond(200, {'ok': True, **res})
            elif self.path == '/api/chat-notes/restore':
                with app.database_connection() as conn:
                    ok = chat_notes.restore_chat_note(conn, payload.get('note_id') or payload.get('id'))
                    self.respond(200, {'ok': ok})
            elif self.path == '/api/chat-notes/purge':
                with app.database_connection() as conn:
                    ok = chat_notes.purge_chat_note(conn, payload.get('note_id') or payload.get('id'), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note.purge", payload.get('note_id') or payload.get('id', ''), "永久刪除對話記事", self.user.get('organization_id', ''))
                    self.respond(200, {'ok': ok})
            elif self.path == '/api/chat-notes/convert-to-case':
                with app.database_connection() as conn:
                    new_case = chat_notes.convert_note_to_case(conn, payload.get('note_id') or payload.get('id'), actor_label)
                    reports.audit(conn, actor_label, "chat_note.convert_to_case", new_case.get('case_id', ''), f"記事轉為案件 {new_case.get('case_no')}", self.user.get('organization_id', ''))
                    self.respond(200, {'ok': True, 'case': new_case})
            elif self.path == '/api/chat-notes/complete':
                with app.database_connection() as conn:
                    res = chat_notes.toggle_note_completed(conn, payload.get('note_id') or payload.get('id'))
                    self.respond(200, {'ok': True, **res})
            elif self.path == '/api/chat-notes/task':
                with app.database_connection() as conn:
                    res = chat_notes.update_note_task(conn, payload, actor_label)
                self.respond(200, {'ok': True, 'note': res})
            elif self.path == '/api/chat-notes/categories/save':
                with app.database_connection() as conn:
                    res = chat_notes.save_note_category(conn, payload, self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_category.save", res.get('name', ''), "儲存記事分類", self.user.get('organization_id', ''))
                    self.respond(200, {'ok': True, 'category': res})
            elif self.path == '/api/chat-notes/categories/merge':
                with app.database_connection() as conn:
                    res = chat_notes.merge_note_categories(conn, payload.get('source_category_ids') or payload.get('source_ids', []), payload.get('target_category_id') or payload.get('target_id', ''), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_category.merge", payload.get('target_category_id', ''), "合併記事分類", self.user.get('organization_id', ''))
                    self.respond(200, res)
            elif self.path == '/api/chat-notes/categories/delete':
                with app.database_connection() as conn:
                    res = chat_notes.delete_note_category(conn, payload.get('category_id') or payload.get('id', ''), payload.get('reassign_to_id', ''), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_category.delete", payload.get('category_id') or payload.get('id', ''), "刪除記事分類", self.user.get('organization_id', ''))
                    self.respond(200, res)
            elif self.path == '/api/chat-notes/tags/save':
                with app.database_connection() as conn:
                    res = chat_notes.save_note_tag(conn, payload.get('name'), payload.get('old_name', ''), payload.get('color', ''), payload.get('category', ''), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_tag.save", payload.get('name', ''), "儲存記事標籤", self.user.get('organization_id', ''))
                    self.respond(200, {'ok': True, **res})
            elif self.path == '/api/chat-notes/tags/merge':
                with app.database_connection() as conn:
                    res = chat_notes.merge_note_tags(conn, payload.get('source_names') or payload.get('sources', []), payload.get('target_name') or payload.get('target', ''), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_tag.merge", payload.get('target_name', ''), "合併記事標籤", self.user.get('organization_id', ''))
                    self.respond(200, res)
            elif self.path == '/api/chat-notes/tags/cleanup':
                with app.database_connection() as conn:
                    res = chat_notes.cleanup_orphan_tags(conn, self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_tag.cleanup", f"{res.get('cleaned_count', 0)} tags", "清理孤立記事標籤", self.user.get('organization_id', ''))
                    self.respond(200, res)
            elif self.path == '/api/chat-notes/tags/delete':
                with app.database_connection() as conn:
                    res = chat_notes.delete_note_tag(conn, payload.get('name'), self.user['role'])
                    reports.audit(conn, actor_label, "chat_note_tag.delete", payload.get('name', ''), "刪除記事標籤", self.user.get('organization_id', ''))
                    self.respond(200, {'ok': True, **res})
            elif self.path == '/api/org-settings/notes-policy':
                if self.user['role'] not in {'org_admin', 'platform_admin'}:
                    raise ValueError('只有管理員可以修改組織記事政策。')
                lock_policy = payload.get('note_lock_policy', 'disabled')
                tag_policy = payload.get('note_tag_policy', 'controlled')
                if lock_policy not in {'disabled', 'collaborative', 'strict_admin'}:
                    raise ValueError('不支援的鎖定政策值。')
                if tag_policy not in {'controlled', 'open'}:
                    raise ValueError('不支援的標籤政策值。')
                with app.database_connection() as conn:
                    org_id = self.user.get('organization_id')
                    if not org_id and self.user['role'] == 'platform_admin':
                        org_id = payload.get('org_id')
                    if not org_id:
                        raise ValueError('請先選擇組織。')
                    updated = conn.execute(
                        'UPDATE organizations SET note_lock_policy=?, note_tag_policy=? WHERE org_id=?',
                        (lock_policy, tag_policy, org_id),
                    )
                    if updated.rowcount != 1:
                        raise ValueError('找不到該組織。')
                    lock_names = {'disabled': '自由編輯模式', 'collaborative': '全員協作防護', 'strict_admin': '管理員嚴格管控'}
                    tag_names = {'controlled': '集中規範管理', 'open': '全員自由自訂'}
                    detail_str = f"更新記事本政策：[防護模式：{lock_names.get(lock_policy, lock_policy)}] · [標籤管理：{tag_names.get(tag_policy, tag_policy)}]"
                    reports.audit(conn, actor_label, "org.notes_policy", org_id or '', detail_str, org_id or '')
                self.respond(200, {'ok': True, 'note_lock_policy': lock_policy, 'note_tag_policy': tag_policy})
            elif self.path in ('/api/saved-filters', '/api/saved-filters/save'):
                action = payload.get('action', 'save')
                with app.database_connection() as conn:
                    if action == 'delete':
                        chat_notes.delete_saved_filter(conn, payload.get('filter_id') or payload.get('id'))
                        reports.audit(conn, actor_label, "saved_filter.delete", payload.get('filter_id') or payload.get('id', ''), "刪除自訂篩選條件", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True})
                    else:
                        res = chat_notes.save_saved_filter(conn, payload)
                        reports.audit(conn, actor_label, "saved_filter.save", res.get('name', ''), "儲存自訂篩選條件", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True, 'filter': res})
            elif self.path == '/api/saved-filters/delete':
                with app.database_connection() as conn:
                    chat_notes.delete_saved_filter(conn, payload.get('filter_id') or payload.get('id'))
                    reports.audit(conn, actor_label, "saved_filter.delete", payload.get('id', ''), "刪除自訂篩選條件", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True})
            elif self.path == '/api/cases/task':
                with app.database_connection() as conn:
                    res = cases.update_case_task(conn, payload, actor_label)
                    reports.audit(conn, actor_label, 'case.task', res['case_id'], '更新案件待辦項目', self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'case': res})
            elif self.path in ('/api/cases', '/api/cases/save'):
                case_id = payload.get('case_id') or payload.get('id')
                with app.database_connection() as conn:
                    if case_id:
                        res = cases.update_case(conn, case_id, payload, actor_label)
                        reports.audit(conn, actor_label, "case.update", case_id, f"更新案件 {res.get('case_no')}", self.user.get('organization_id', ''))
                    else:
                        res = cases.create_case(conn, payload, actor_label)
                        reports.audit(conn, actor_label, "case.create", res.get('case_id', ''), f"建立案件 {res.get('case_no')}", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'case': res})
            elif self.path == '/api/cases/prefix':
                if self.user['role'] not in {'org_admin', 'platform_admin'}:
                    raise ValueError('只有管理員可以修改案件編號前綴。')
                with app.database_connection() as conn:
                    res = cases.update_case_prefix(conn, payload.get('prefix'), payload.get('mode', 'apply_new_only'), actor_label)
                self.respond(200, {'ok': True, **res})
            elif re.fullmatch(r'/api/cases/[0-9a-f]{32}/lock', self.path):
                case_id = self.path.split('/')[3]
                with app.database_connection() as conn:
                    res = cases.toggle_case_lock(conn, case_id, actor_label, self.user['role'])
                self.respond(200, {'ok': True, 'case': res})
            elif re.fullmatch(r'/api/cases/[0-9a-f]{32}/notify', self.path):
                case_id = self.path.split('/')[3]
                if self.user['role'] not in {'org_admin', 'operator'}:
                    raise ValueError('只有管理員與操作人員可以傳送進度通知。')
                with app.database_connection() as conn:
                    res = cases.notify_case_subject(conn, case_id, payload.get('message_text') or payload.get('text', ''), actor_label)
                self.respond(200, {'ok': True, 'case': res})
            elif re.fullmatch(r'/api/cases/[0-9a-f]{32}', self.path):
                case_id = self.path.rsplit('/', 1)[1]
                action = payload.get('action')
                with app.database_connection() as conn:
                    if action == 'add_note' or (payload.get('note') and 'status' not in payload):
                        res = cases.add_activity(conn, case_id, 'note', actor_label, payload.get('note', ''))
                        reports.audit(conn, actor_label, "case.activity", case_id, "新增案件處理紀錄", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True, 'activity': res})
                    elif 'status' in payload:
                        to_status = payload.get('status')
                        res = cases.transition_case(conn, case_id, to_status, payload, actor_label)
                        reports.audit(conn, actor_label, "case.transition", case_id, f"案件 {res.get('case_no')} 狀態變更為 {to_status}", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True, 'case': res})
                    else:
                        res = cases.update_case(conn, case_id, payload, actor_label)
                        reports.audit(conn, actor_label, "case.update", case_id, f"更新案件 {res.get('case_no')}", self.user.get('organization_id', ''))
                        self.respond(200, {'ok': True, 'case': res})
            elif self.path == '/api/cases/transition':
                case_id = payload.get('case_id') or payload.get('id')
                to_status = payload.get('status')
                with app.database_connection() as conn:
                    res = cases.transition_case(conn, case_id, to_status, payload, actor_label)
                    reports.audit(conn, actor_label, "case.transition", case_id, f"案件 {res.get('case_no')} 狀態變更為 {to_status}", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'case': res})
            elif self.path == '/api/cases/activity':
                case_id = payload.get('case_id') or payload.get('id')
                activity_type = payload.get('activity_type') or 'note'
                content = payload.get('content') or payload.get('note') or ''
                with app.database_connection() as conn:
                    res = cases.add_activity(conn, case_id, activity_type, actor_label, content)
                    reports.audit(conn, actor_label, "case.activity", case_id, "新增案件處理紀錄", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'activity': res})
            elif self.path == '/api/template-packs/save':
                with app.database_connection() as conn:
                    res = template_packs.save_custom_pack(conn, self.user.get('organization_id', ''), payload, actor_label)
                self.respond(200, {'ok': True, **res})
            elif self.path == '/api/template-packs/delete':
                with app.database_connection() as conn:
                    template_packs.delete_custom_pack(conn, self.user.get('organization_id', ''), payload.get('pack_id'), actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/template-packs/copy':
                with app.database_connection() as conn:
                    res = template_packs.copy_pack(conn, self.user.get('organization_id', ''), payload.get('source_pack_key'), payload.get('name', ''), actor_label)
                self.respond(200, {'ok': True, **res})
            elif self.path == '/api/template-packs/lock':
                with app.database_connection() as conn:
                    template_packs.toggle_pack_lock(conn, self.user.get('organization_id', ''), payload.get('pack_id'), bool(payload.get('is_locked')), actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/templates/save':
                with app.database_connection() as conn:
                    res = template_packs.save_template(conn, self.user.get('organization_id', ''), payload.get('template_type', 'case'), payload, actor_label)
                self.respond(200, {'ok': True, **res})
            elif self.path == '/api/templates/delete':
                with app.database_connection() as conn:
                    template_packs.delete_template(conn, self.user.get('organization_id', ''), payload.get('template_type', 'case'), payload.get('template_id'), actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/templates/batch-delete':
                items = payload.get('items', [])
                with app.database_connection() as conn:
                    cnt = template_packs.batch_delete_templates(conn, self.user.get('organization_id', ''), items, actor_label)
                self.respond(200, {'ok': True, 'deleted_count': cnt})
            elif self.path == '/api/templates/copy':
                with app.database_connection() as conn:
                    res = template_packs.copy_template(conn, self.user.get('organization_id', ''), payload.get('template_type', 'case'), payload.get('source_id'), payload.get('target_pack_id'), payload.get('name', ''), actor_label)
                self.respond(200, {'ok': True, **res})
            elif self.path == '/api/templates/move':
                with app.database_connection() as conn:
                    template_packs.move_template(conn, self.user.get('organization_id', ''), payload.get('template_type', 'case'), payload.get('template_id'), payload.get('target_pack_id'), actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/templates/lock':
                with app.database_connection() as conn:
                    template_packs.toggle_template_lock(conn, self.user.get('organization_id', ''), payload.get('template_type', 'case'), payload.get('template_id'), bool(payload.get('is_locked')), actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/templates/create-from-source':
                with app.database_connection() as conn:
                    res = template_packs.create_template_from_source(conn, self.user.get('organization_id', ''), payload.get('source_type', 'case'), payload.get('source_id'), payload.get('target_pack_id'), payload.get('name', ''), actor_label)
                self.respond(200, {'ok': True, **res})
            elif self.path == '/api/categories/save':
                with app.database_connection() as conn:
                    res = template_packs.save_single_category(conn, channels.current_id(), payload.get('category_type', 'case'), payload.get('name', ''), payload.get('old_name', ''), actor_label)
                self.respond(200, {'ok': True, 'categories': res})
            elif self.path == '/api/categories/delete':
                with app.database_connection() as conn:
                    res = template_packs.delete_single_category(conn, channels.current_id(), payload.get('category_type', 'case'), payload.get('name', ''), actor_label)
                self.respond(200, {'ok': True, 'categories': res})
            elif self.path == '/api/categories/reorder':
                with app.database_connection() as conn:
                    res = template_packs.reorder_categories(conn, channels.current_id(), payload.get('category_type', 'case'), payload.get('names', []), actor_label)
                self.respond(200, {'ok': True, 'categories': res})
            elif self.path == '/api/template-packs/toggle':
                with app.database_connection() as conn:
                    ok = template_packs.toggle_oa_pack(conn, channels.current_id(), payload.get('pack_key'), bool(payload.get('enabled')))
                self.respond(200, {'ok': ok})
            elif self.path == '/api/categories/preview':
                with app.database_connection() as conn:
                    res = template_packs.preview_apply_category_set(conn, channels.current_id(), payload.get('pack_key'), payload.get('mode', 'replace'))
                self.respond(200, res)
            elif self.path == '/api/categories/apply':
                with app.database_connection() as conn:
                    res = template_packs.apply_category_set(conn, channels.current_id(), payload.get('pack_key'), payload.get('mode', 'replace'), actor_label)
                self.respond(200, {'ok': True, 'categories': res})
            elif self.path == '/api/chat/send':
                cid = payload.get('recipient_id') or payload.get('chat_id') or ''
                text = payload.get('text') or payload.get('message') or ''
                use_reply = bool(payload.get('use_reply_token', True))
                with app.database_connection() as conn:
                    res = chat.send_chat_message(conn, cid, text, actor_label, use_reply_token=use_reply)
                    reports.audit(conn, actor_label, "chat.send", cid, f"傳送訊息（{res.get('send_method')}）", self.user.get('organization_id', ''))
                self.respond(200, res)
            elif self.path == '/api/chat/room-preference':
                with app.database_connection() as conn:
                    result=chat.save_room_preference(conn,payload,self.identity)
                self.respond(200,{'ok':True,**result})
            elif self.path == '/api/chat/mark-read':
                cid = payload.get('recipient_id') or payload.get('chat_id') or ''
                with app.database_connection() as conn:
                    res = chat.mark_chat_read(conn, cid)
                self.respond(200, res)
            elif self.path == '/api/chat/status':
                cid = payload.get('recipient_id') or payload.get('chat_id') or ''
                status = payload.get('status', 'open')
                status_names = {'done': '已完成', 'pending': '待處理', 'in_progress': '處理中', 'open': '一般（無狀態）'}
                status_label = status_names.get(status, status)
                with app.database_connection() as conn:
                    res = chat.set_chat_status(conn, cid, status, actor_label)
                    reports.audit(conn, actor_label, "chat.status", cid, f"變更聊天狀態為 [{status_label}]", self.user.get('organization_id', ''))
                self.respond(200, res)
            elif self.path == '/api/chat/canned-replies/save':
                with app.database_connection() as conn:
                    res = chat.save_canned_reply(conn, payload, actor_label)
                    reports.audit(conn, actor_label, "canned_reply.save", res.get('id', ''), "儲存預設訊息", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True, 'reply': res})
            elif self.path == '/api/chat/canned-replies/delete':
                rid = payload.get('id') or payload.get('reply_id') or ''
                with app.database_connection() as conn:
                    chat.delete_canned_reply(conn, rid)
                    reports.audit(conn, actor_label, "canned_reply.delete", rid, "刪除預設訊息", self.user.get('organization_id', ''))
                self.respond(200, {'ok': True})
            elif self.path == '/api/chat/response-hours/save':
                with app.database_connection() as conn:
                    res = chat.save_response_hours(conn, payload)
                    reports.audit(conn, actor_label, "response_hours.save", "", "儲存回應時間設定", self.user.get('organization_id', ''))
                self.respond(200, res)
            elif self.path == '/api/chat/media/cleanup':
                res = chat.cleanup_expired_media(max_age_days=int(payload.get('days') or limits.MEDIA_RETENTION_DAYS))
                with app.database_connection() as conn:
                    reports.audit(conn, actor_label, "media.cleanup", "", f"清理過期媒體（刪除 {res.get('deleted_count')} 筆，釋放 {res.get('freed_mb')} MB）", self.user.get('organization_id', ''))
                self.respond(200, res)

            elif self.path == '/api/personnel/save':
                if self.user['role'] != 'org_admin':
                    self.respond(403, {'error': '只有管理員可以管理組織人員。'})
                    return
                org_id = self.user.get('organization_id')
                payload['org_id'] = org_id
                payload['organization_id'] = org_id
                reports.save_user(payload, actor_label)
                reports.save_membership(payload, actor_label)
                self.respond(200, {'ok': True})
            elif self.path == '/api/org-settings/save':
                if self.user['role'] != 'org_admin':
                    self.respond(403, {'error': '只有管理員可以修改組織設定。'})
                    return
                reports.save_organization_profile(self.user.get('organization_id'), payload, actor_label)
                self.respond(200, {'ok': True})

            elif self.path == '/api/assets/upload':
                if not reports.module_enabled(self.user, 'messaging'):
                    raise ValueError('此組織尚未授權訊息發送模組。')
                self.respond(201, composer.upload(payload, self.user))
                self.respond(200,{'ok':True})
            elif self.path == '/api/organizations/save':
                self.respond(200,reports.save_organization(payload,self.identity))
            elif self.path == '/api/memberships/save':
                reports.save_membership(payload,self.identity)
                self.respond(200,{'ok':True})
            elif self.path == "/api/contact":
                with app.database_connection() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    current = conn.execute('SELECT organization_id FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (payload.get('id'),)).fetchone()
                    if not current or not reports.same_organization(self.user, current[0]):
                        raise ValueError('找不到可管理的聯絡對象。')
                    if self.user['role'] != 'platform_admin':
                        if payload.get('organization_id', current[0]) != current[0]:
                            raise ValueError('組織歸屬由平台管理員設定。')
                    recipients.update_contact(
                        conn,
                        payload.get("id"),
                        payload.get("custom_name", ""),
                        notes=payload.get("notes"),
                        tag_ids=payload.get("tag_ids"),
                        contact_type=payload.get("contact_type"),
                        phone=payload.get("phone"),
                        email=payload.get("email"),
                        postal_code=payload.get("postal_code"),
                        address=payload.get("address"),
                        organization_name=payload.get("organization_name"),
                        job_title=payload.get("job_title"),
                        work_phone=payload.get("work_phone"),
                        work_phone_ext=payload.get("work_phone_ext"),
                        work_email=payload.get("work_email")
                    )
                    department = payload.get("department")
                    if department is not None:
                        if not isinstance(department, str) or len(department.strip()) > 60:
                            raise ValueError("部門名稱請限制在 60 字以內。")
                        conn.execute('UPDATE recipients SET department=? WHERE recipients.channel_id=current_channel() AND recipient_id=?', (department.strip(), payload["id"]))
                    organization_id = payload.get("organization_id")
                    if organization_id is not None:
                        channels.enforce_organization(organization_id)
                    if organization_id is not None:
                        if not isinstance(organization_id, str) or len(organization_id.strip()) > 60:
                            raise ValueError("組織名稱請限制在 60 字以內。")
                        conn.execute('UPDATE recipients SET organization_id=? WHERE recipients.channel_id=current_channel() AND recipient_id=?', (organization_id.strip(), payload["id"]))
                    reports.audit(conn, actor_label, "contact.update", payload["id"], "更新備註與分類", self.user.get('organization_id', ''))
                self.respond(200, {"ok": True})
            elif self.path == "/api/profiles":
                load_settings()
                rows = self.scoped_contacts()
                updated, failed = 0, 0
                for row in rows:
                    if not row["active"] or row["kind"] == "room":
                        continue
                    rid = row["recipient_id"]
                    if not re.fullmatch(r"[UC][0-9a-fA-F]{32}", rid):
                        continue
                    result = recipients.refresh_profile(rid, force=True)
                    if result == 'updated':
                        updated += 1
                    elif result == 'failed':
                        failed += 1
                with app.database_connection() as conn:
                    reports.audit(conn, actor_label, "profiles.update", "recipients", f"更新 {updated} 個 LINE 名稱，{failed} 個未完成", self.user.get('organization_id', ''))
                self.respond(200, {"updated": updated, "failed": failed})
            elif self.path == "/api/send":
                self.respond(202, self.server.dispatcher.submit(payload, actor=self.identity, organization=self.user['organization_id']))
            elif self.path == "/api/jobs/cancel":
                self.server.dispatcher.cancel(payload.get("job_id"), self.identity, self.user['organization_id'])
                self.respond(200, {"ok": True})
            elif self.path == "/api/accounts/save":
                # 甲級在「組織」只建立組織的管理員；操作人員、協作人員由該組織的管理員在「人員與權限」建立。
                if self.user['role'] == 'platform_admin' and payload.get('role') in {'operator', 'collaborator'}:
                    raise ValueError('操作人員與協作人員請由該組織的管理員在「人員與權限」建立。')
                # 權限規格第 9 節：平台管理員只能經首次設定或 create_admin.py 建立；這裡不能新增、升級或降級平台管理員。
                email = str(payload.get('email', '')).strip().lower()
                existing = next((u for u in reports.users() if u['email'] == email), None)
                was_platform = bool(existing and existing['role'] == 'platform_admin')
                if payload.get('role') == 'platform_admin' and not was_platform:
                    raise ValueError('平台管理員只能從本機控制台首次設定或 create_admin.py 建立。')
                if was_platform and payload.get('role') != 'platform_admin':
                    raise ValueError('平台管理員帳號不能改為組織帳號；組織的管理員請使用另一個 Email。')
                reports.save_user(payload, self.identity)
                self.respond(200, {"ok": True})
            else:
                self.respond(404, {"error": "找不到操作。"})
        except (ValueError, TypeError) as error:
            message = str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "請求格式不正確。"
            self.respond(400, {"error": message})
        except (OSError, sqlite3.Error):
            self.respond(500, {"error": "讀取檔案或資料庫失敗，請確認設定及路徑。"})


class AdminServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, port):
        super().__init__(("127.0.0.1", port), AdminHandler)
        self.token = secrets.token_urlsafe(32)
        # 對外管理網域；未設定時只接受本機控制台連線。
        self.public_host = os.environ.get("ADMIN_PUBLIC_HOST", "").strip().lower()
        self.dispatcher = None
        self.workspace_ready = False

    def start(self):
        self.workspace_ready = True
        self.dispatcher = Dispatcher()
        self.dispatcher.start_scheduler()
        # Browser uses a fragment; the credential is never in an HTTP query or access log.
        (app.BASE_DIR / "instance" / "admin-access.json").write_text(
            json.dumps({"port": self.server_port, "token": self.token}), encoding="utf-8")
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.dispatcher:
            self.dispatcher.closing.set()
            self.shutdown()
            self.server_close()
            self.dispatcher.close()
        else:
            self.server_close()

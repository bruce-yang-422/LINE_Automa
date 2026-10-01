"""Recipient management: local bearer token or verified Cloudflare Access identity."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4
from urllib.parse import urlsplit

import app
import channels
from control_runtime import load_settings
import line_api
import recipients
import reports
import site_auth
from remote_auth import RemoteAccess
from send_image import publish_image, verify_public_image, send_push
import composer


def contact_label(row):
    return row["alias"] or row["display_name"] or (("個人" if row["kind"] == "user" else "群組") + " · " + row["recipient_id"][-8:])


def select_contacts(conn, audience, ids):
    contacts = recipients.list_contacts(conn)
    if audience == "subscribers":
        selected = [r for r in contacts if r["active"] and r["weather_subscribed"]]
    elif audience == "selected" and isinstance(ids, list) and all(isinstance(i, str) for i in ids):
        wanted = set(ids)
        selected = [r for r in contacts if r["active"] and r["recipient_id"] in wanted]
        if len(selected) != len(wanted):
            raise ValueError("部分發送對象已停用或不存在，請重新整理名單。")
    else:
        raise ValueError("請選擇發送對象或天氣訂閱名單。")
    if not selected or len(selected) > 500:
        raise ValueError("請選擇 1 至 500 個有效發送對象。")
    if any(not re.fullmatch(r"[UCR][0-9a-fA-F]{32}", r["recipient_id"]) for r in selected):
        raise ValueError("名單含有無效 ID，請重新接收 LINE Webhook。")
    return selected


def job_status(job_id=None, user=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        scope_sql = " AND company=? AND company<>''" if user and user['role'] != 'administrator' and not channels.personal_owner(user) else ''
        scope_args = (user['company'],) if scope_sql else ()
        if job_id:
            jobs = conn.execute('SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND job_id=?' + scope_sql, (job_id,) + scope_args).fetchall()
        else:
            jobs = conn.execute("SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND status='scheduled'" + scope_sql + " ORDER BY scheduled_at", scope_args).fetchall()
            jobs += conn.execute("SELECT * FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND status<>'scheduled'" + scope_sql + " ORDER BY created_at DESC LIMIT 20", scope_args).fetchall()
        result = []
        for row in jobs:
            item = dict(row)
            if user and user['role']=='sender' and item['actor']!=user['email']:
                continue
            if user and not reports.same_company(user, item['company']):
                continue
            item["deliveries"] = [dict(r) for r in conn.execute(
                "SELECT recipient_id,label,status,request_id,error FROM send_deliveries WHERE job_id=?", (row["job_id"],))]
            if user and user['role']=='sender':
                permitted = {r['recipient_id'] for r in recipients.list_contacts(conn) if reports.allowed_contact(user,r)}
                if any(r['recipient_id'] not in permitted for r in item['deliveries']):
                    continue
            if user and user['role'] != 'administrator':
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
            job = conn.execute('SELECT company,actor FROM send_jobs WHERE send_jobs.channel_id=current_channel() AND job_id=?', (job_id,)).fetchone()
            if not job or not reports.same_company(user, job[0]) or (user['role']=='sender' and job[1]!=actor):
                raise ValueError('找不到可操作的預約。')
            changed = conn.execute("UPDATE send_jobs SET status='cancelled' WHERE send_jobs.channel_id=current_channel() AND job_id=? AND status='scheduled'", (job_id,)).rowcount
            if not changed:
                raise ValueError("此預約已開始處理或已取消，請重新整理紀錄。")
            conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=? AND status='pending'", (job_id,))
            reports.audit(conn, actor, "send.cancel", job_id, "取消預約", user['company'])

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
            message_text = payload.get("message_text", "")
            composition = payload.get('composition')
            if 'composition' in payload and (not isinstance(composition, dict) or message_text or payload.get('report_id') or payload.get('image_path') or payload.get('audience') != 'selected'):
                raise ValueError('自訂訊息請選擇發送對象，且不能混合文字或報告來源。')
            if not isinstance(message_text, str) or ("message_text" in payload and not message_text.strip()) or len(message_text.encode('utf-16-le')) // 2 > 5000:
                raise ValueError("文字訊息請填入 1 至 5000 字（表情符號可能佔兩字）。")
            if message_text and (payload.get("report_id") or payload.get("image_path") or payload.get("audience") != "selected"):
                raise ValueError("文字訊息請使用手動選擇對象，且不能混合報告來源。")
            if not channels.access_token():
                raise ValueError("請先設定 LINE OA 憑證。")
            audience = payload.get("audience")
            if user['role'] != 'administrator' and (audience != 'selected' or payload.get('image_path')):
                raise ValueError('組織管理員請選擇已授權報告或文字訊息，以及本組織的對象。')
            with app.database_connection() as conn:
                selected = select_contacts(conn, audience, payload.get("ids"))
            if any(not reports.allowed_contact(user, row) for row in selected):
                raise ValueError('發送對象不在所屬組織範圍。')
            report_id, report_title = "", "手動圖片"
            messages = []
            prepared = composer.prepare(composition, user, selected) if composition is not None else None
            if payload.get("report_id"):
                candidate = reports.find(payload['report_id'])
                if not candidate or not reports.can_view(candidate, user):
                    raise ValueError('找不到可使用的報告。')
                if audience == "subscribers" and (not isinstance(payload.get("ids"), list)
                        or set(payload["ids"]) != {row["recipient_id"] for row in selected}):
                    raise ValueError("天氣訂閱名單已變更，請重新整理並確認發送對象。")
                report, item = reports.prepare(payload["report_id"], payload.get("report_version"), payload.get("allow_stale"))
                if audience == "subscribers" and report["category"] != "weather":
                    raise ValueError("天氣訂閱名單只能用於天氣報告，其他報表請自行選擇對象。")
                source = Path(report["source_path"])
                report_id, report_title = report["report_id"], report["title"]
                reports.validate_targets(report, selected)
            elif not message_text and prepared is None:
                source = Path(str(payload.get("image_path", "")))
            if prepared is not None:
                messages = composer.build(prepared, publish_image, verify_public_image)
                source, url, report_title = '', '', {'images':'多圖訊息', 'card':'圖文卡片', 'carousel':'輪播卡片', 'imagemap':'圖文訊息'}[prepared['format']] + '：' + prepared['alt_text'][:32]
            elif message_text:
                source, url, report_title = "", "", "文字訊息：" + message_text.strip()[:32]
            else:
                url, content = publish_image(source, os.environ.get("PUBLIC_BASE_URL", "https://reports.stack-base.com"))
                if report_id and hashlib.sha256(content).hexdigest() != payload["report_version"]:
                    raise ValueError("報告在準備時已變更，請重新預覽；尚未發送。")
                verify_public_image(url, content)
            companies = {row['company'] for row in selected}
            company = user['company'] if user['role'] != 'administrator' else (report['company'] if report_id else (next(iter(companies)) if message_text and len(companies) == 1 else ''))
            if prepared and user['role'] == 'administrator':
                company = next((item['asset']['company'] for item in prepared['items'] if item['asset']['company']), '')
            with app.database_connection() as conn:
                conn.execute('INSERT INTO send_jobs (channel_id,job_id,audience,image_path,image_url,actor,report_title,report_id,scheduled_at,message_text,status,company,messages_json) VALUES (current_channel(),?,?,?,?,?,?,?,?,?,?,?,?)',
                             (job_id, audience, str(source), url, actor, report_title, report_id, scheduled_at, message_text, 'scheduled' if scheduled_at else 'queued', company, json.dumps(messages, ensure_ascii=False)))
                conn.executemany("INSERT INTO send_deliveries (job_id,recipient_id,label,retry_key) VALUES (?,?,?,?)",
                                 [(job_id, r["recipient_id"], contact_label(r), str(uuid4())) for r in selected])
                reports.audit(conn, actor, "send.create", job_id, f"{report_title} · {len(selected)} 個聊天室", company)
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
                    current = conn.execute('SELECT active,weather_subscribed FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                    skip = (self.closing.is_set() or not current or not current[0] or
                            (job["audience"] == "subscribers" and not current[1]))
                    if job['company']:
                        org=next((o for o in reports.organizations() if o['org_id']==job['company']),None)
                        if not org or not org['active'] or not org['messaging_enabled'] or (job['report_id'] and job['report_id']!='weather' and not org['reports_enabled']):
                            skip=True
                        if job['messages_json'] != '[]':
                            contact = conn.execute('SELECT company FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                            if not contact or contact[0] != job['company']:
                                skip = True
                    if job["report_id"]:
                        source = reports.find(job["report_id"])
                        try:
                            if not source:
                                raise ValueError("Report removed")
                            reports.validate_targets(source, select_contacts(conn, "selected", [recipient_id]))
                        except ValueError:
                            skip = True
                    if job["actor"] and job["actor"] != "本機管理員":
                        actor = reports.actor_user(job["actor"],job['company'])
                        if not reports.operator(actor) or not reports.module_enabled(actor,'messaging'):
                            skip = True
                        elif actor['role'] != 'administrator':
                            contact = conn.execute('SELECT * FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (recipient_id,)).fetchone()
                            if (not reports.same_company(actor, job['company']) or not contact or not reports.allowed_contact(actor, dict(contact))
                                    or (job['report_id'] and (not source or not reports.can_view(source, actor)))):
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

    def respond(self, code, data, content_type="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if getattr(self, 'response_cookie', None):
            self.send_header('Set-Cookie', self.response_cookie)
            self.response_cookie = None
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, require_token=True):
        self.auth_method = 'local'
        self.identity = "本機管理員"
        self.user = {"email": self.identity, "display_name": "本機管理員", "role": "administrator", "company": "", "department": ""}
        for name in ("Host", "Origin", "Authorization", "Cookie", "X-CSRF-Token", "Cf-Access-Jwt-Assertion", "X-Forwarded-Proto", "X-Workspace-View-As", "X-Workspace-Organization", "X-Workspace-Preview-Organization"):
            if len(self.headers.get_all(name, [])) > 1:
                self.respond(403, {"error": "不接受重複的驗證標頭。"})
                return False
        expected_host = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        remote = self.server.remote_access
        if self.server.auth_mode == 'password' and remote.host and self.headers.get('Host','').lower() == remote.host:
            return site_auth.authorize(self)
        if remote.enabled and self.headers.get("Host", "").lower() == remote.host:
            if (self.headers.get("X-Forwarded-Proto") != "https"
                    or (origin is not None and origin != "https://" + remote.host)
                    or (self.command == "POST" and origin != "https://" + remote.host)):
                self.respond(403, {"error": "請透過 HTTPS 管理網址操作。"})
                return False
            try:
                self.auth_method = 'cloudflare'
                if self.server.workspace_ready:
                    allowed = {u["email"] for u in reports.users() if u["active"]}
                    self.identity = remote.verify(self.headers.get("Cf-Access-Jwt-Assertion", ""), allowed_emails=allowed)
                    self.user = reports.login_account(self.identity)
                    if not self.user:
                        raise ValueError("此帳號沒有後台登入資格；聯絡對象請直接使用 LINE，不需後台帳號。")
                else:
                    self.identity = remote.verify(self.headers.get("Cf-Access-Jwt-Assertion", ""))
            except ValueError as exc:
                self.respond(403, {"error": str(exc)})
                return False
            return self.apply_view()
        if (self.headers.get("Host") != expected_host or (origin and origin != "http://" + expected_host)
                or any(name in self.headers for name in ("CF-Connecting-IP", "X-Forwarded-For", "X-Forwarded-Proto", "Cf-Access-Jwt-Assertion"))):
            self.respond(403, {"error": "請從本機控制台或已設定的 Cloudflare Access 管理入口登入。"})
            return False
        if require_token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.token):
            if self.server.auth_mode == 'password' or site_auth.cookie_token(self, False):
                return site_auth.authorize(self)
            self.respond(401, {"error": "管理連線已失效，請從控制台重新開啟。"})
            return False
        return self.apply_view() if require_token else True

    def apply_view(self):
        self.principal = self.identity
        self.preview = False
        org=self.headers.get('X-Workspace-Organization')
        if org and self.user['role']!='administrator':
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
        preview_org=unquote(self.headers.get('X-Workspace-Preview-Organization','')) or (self.user['company'] if self.user['role']!='administrator' else None)
        user = reports.account(target,preview_org)
        if not user or (target,user['company']) not in {(row['email'],row['company']) for row in reports.view_options(self.user)}:
            self.respond(403, {"error": "此成員帳號已停用或角色已變更，請返回管理員視角。"})
            return False
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
                    '/api/accounts/save', '/api/organizations/save', '/api/memberships/save'}
        registry = self.path.startswith('/api/channels')
        if registry:
            return True
        try:
            if channel_id:
                row = channels.authorize(channel_id, self.user)
                if row['org_id'] and self.user['role'] != 'administrator':
                    self.user = reports.account(self.identity, row['org_id'])
                    if not self.user:
                        raise ValueError('組織成員資格已失效。')
                elif not row['org_id'] and self.user['role'] != 'administrator':
                    self.user = {**self.user, 'company': ''}
                channels._current.set(channel_id)
            elif channels.configured() and self.path not in globals_:
                raise ValueError('請先選擇工作區與 LINE OA。')
        except ValueError as exc:
            self.respond(403, {'error': str(exc)})
            return False
        return True

    def admin_only(self):
        if not reports.manager(self.user):
            self.respond(403, {"error": "此功能僅供管理員使用。"})
            return False
        return True

    def scoped_contacts(self):
        with app.database_connection() as conn:
            rows = recipients.list_contacts(conn)
        result = [row for row in rows if reports.allowed_contact(self.user, row)]
        if self.user['role'] != 'administrator':
            result = [{key: value for key, value in row.items() if key not in {'weather_subscribed', 'subscription_at'}} for row in result]
        return result

    def scoped_tags(self):
        with app.database_connection() as conn:
            rows = recipients.list_tags(conn)
        return [{"id": r["tag_id"], "tag_id": r["tag_id"], "name": r["name"], "color": r["color"]} for r in rows]

    def do_GET(self):
        with channels.use(''):
            self.get_request()

    def get_request(self):
        self.path = urlsplit(self.path).path
        if site_auth.handle_get(self):
            return
        files = {"/": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/index.html": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/admin.js": (app.BASE_DIR / "web" / "admin.js", "text/javascript; charset=utf-8"),
                 "/app.css": (app.BASE_DIR / "web" / "app.css", "text/css; charset=utf-8"),
                 "/channels.js": (app.BASE_DIR / "web" / "channels.js", "text/javascript; charset=utf-8"),
                 "/workspace.js": (app.BASE_DIR / "web" / "workspace.js", "text/javascript; charset=utf-8"),
                 "/account-security.js": (app.BASE_DIR / "web" / "account-security.js", "text/javascript; charset=utf-8"),
                 "/composer.js": (app.BASE_DIR / "web" / "composer.js", "text/javascript; charset=utf-8"),
                 "/workspace-theme.css": (app.BASE_DIR / "web" / "workspace-theme.css", "text/css; charset=utf-8"),
                 "/management.js": (app.BASE_DIR / "web" / "management.js", "text/javascript; charset=utf-8"),
                 "/management.css": (app.BASE_DIR / "web" / "management.css", "text/css; charset=utf-8"),
                 "/admin.css": (app.BASE_DIR / "web" / "admin.css", "text/css; charset=utf-8")}
        brand = app.BASE_DIR / 'web' / 'assets' / 'brand'
        for variant in ('light',):
            for extension, mime in (('png', 'image/png'), ('ico', 'image/x-icon')):
                name = f'line-automation-logo-{variant}.{extension}'
                files['/assets/brand/' + name] = (brand / name, mime)
        files['/favicon.ico'] = (brand / 'line-automation-logo-light.ico', 'image/x-icon')
        if not self.authorized(require_token=self.path not in files):
            return
        if self.path not in files and not self.select_line_channel():
            return
        read_routes = {"/api/channels", "/api/session", "/api/reports", "/api/organizations"}
        if self.path not in files and self.path not in read_routes and not re.fullmatch(r"/api/reports/(weather|[0-9a-f]{32})", self.path):
            if self.user['role']=='sender' and self.path in {'/api/view-options','/api/settings'}:
                self.respond(403, {'error':'此功能僅供管理員使用。'})
                return
            if not reports.operator(self.user):
                self.respond(403, {'error':'沒有此功能的存取權限。'})
                return
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
                               "memberships": [m for m in reports.memberships(self.identity) if m['active'] and m['org_active'] and m['role'] in {'company_admin','sender'}] if not self.preview and self.server.workspace_ready else [],
                               "modules": {m:reports.module_enabled(self.user,m) for m in ('reports','messaging','weather')}})
        elif self.path == '/api/organizations':
            self.respond(200,{'organizations':[o for o in reports.organizations() if self.user['role']=='administrator' or reports.same_company(self.user,o['org_id'])],
                              'memberships':reports.memberships() if self.user['role']=='administrator' else []})
        elif self.path == "/api/view-options":
            self.respond(200, {"users": [{key: row[key] for key in ("email", "display_name", "company", "department", "role", "organization_name")}
                                           for row in reports.view_options(self.user)]})
        elif self.path == "/api/reports":
            self.respond(200, {"reports": [reports.describe(row) for row in reports.sources() if reports.can_view(row, self.user)]})
        elif re.fullmatch(r"/api/reports/(weather|[0-9a-f]{32})", self.path):
            source = reports.find(self.path.rsplit("/", 1)[1])
            if source and not reports.can_view(source, self.user):
                source = None
            self.respond(200 if source else 404, reports.describe(source, preview=True) if source else {"error": "找不到報告。"})
        elif self.path == "/api/activity":
            self.respond(200, {"events": reports.activity(self.user)})
        elif self.path == "/api/settings":
            self.respond(200, {"remote_enabled": self.server.remote_access.enabled,
                               "weather_report_removed": reports.weather_removed() if self.user['role']=='administrator' else False,
                               "admin_host": self.server.remote_access.host,
                               "users": reports.scoped_users(self.user),
                               "report_sources": reports.sources() if self.user['role'] == 'administrator' else [],
                               "line_configured": bool(channels.get()) if channels.configured() else bool(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")),
                               "public_base": os.environ.get("PUBLIC_BASE_URL", ""),
                               "dispatch_scopes": reports.dispatch_scopes() if self.user['role']=='administrator' else [],
                               "sender_grants": [{"email":m['email'],"company":m['org_id'],**reports.grant({'email':m['email'],'company':m['org_id']})} for m in reports.memberships() if m['role']=='sender'] if self.user['role']=='administrator' else [],
                               "role": self.user['role']})
        elif self.path == "/api/contacts":
            self.respond(200, {"contacts": self.scoped_contacts(), "tags": self.scoped_tags()})
        elif self.path == "/api/tags":
            self.respond(200, {"tags": self.scoped_tags()})
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
        if not self.select_line_channel():
            return
        if not reports.operator(self.user):
            self.respond(403, {'error':'沒有發送操作權限。'})
            return
        if self.user['role']=='sender' and self.path not in {'/api/send','/api/jobs/cancel','/api/assets/upload','/api/channels/save','/api/channels/verify','/api/channels/active', '/api/contacts/bulk'}:
            self.respond(403, {'error':'發送人員不能修改聯絡對象分類、來源或帳號授權。'})
            return
        if self.preview:
            self.respond(403, {'error': '視角預覽僅供檢視，請返回原帳號操作。'})
            return
        if self.path in {'/api/accounts/save', '/api/reports/save', '/api/reports/remove', '/api/reports/restore-weather', '/api/organizations/save', '/api/memberships/save', '/api/dispatch-scopes/save', '/api/sender-grants/save'} and self.user['role'] != 'administrator':
            self.respond(403, {'error': '帳號授權、模組歸屬及來源設定由平台管理員管理。'})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            maximum = 12 * 1024 * 1024 if self.path == '/api/assets/upload' else 65536
            if size <= 0 or size > maximum or self.headers.get_content_type() != "application/json":
                raise ValueError("請求格式不正確。")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("請求格式不正確。")
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
                if not reports.manager(self.user):
                    raise ValueError('只有管理員可以管理標籤。')
                with app.database_connection() as conn:
                    tid = recipients.save_tag(conn, payload.get('name'), payload.get('color'), payload.get('id'))
                    reports.audit(conn, self.identity, "tag.save", tid, f"儲存標籤「{payload.get('name')}」", self.user['company'])
                self.respond(200, {'ok': True, 'tag_id': tid, 'tag': {'id': tid, 'name': payload.get('name'), 'color': payload.get('color')}})
            elif self.path == '/api/tags/delete':
                if not reports.manager(self.user):
                    raise ValueError('只有管理員可以刪除標籤。')
                with app.database_connection() as conn:
                    recipients.delete_tag(conn, payload.get('id'))
                    reports.audit(conn, self.identity, "tag.delete", str(payload.get('id')), "刪除標籤", self.user['company'])
                self.respond(200, {'ok': True})
            elif self.path == '/api/contacts/bulk':
                action = payload.get('action')
                ids = payload.get('ids') or payload.get('contact_ids') or []
                with app.database_connection() as conn:
                    if action in {'add_tags', 'remove_tags'}:
                        tag_ids = payload.get('tag_ids', [])
                        recipients.bulk_update_tags(conn, ids, tag_ids, 'add' if action == 'add_tags' else 'remove')
                        reports.audit(conn, self.identity, "contacts.bulk_tag", f"{len(ids)} contacts", "批次更新標籤", self.user['company'])
                    elif action == 'set_subscription':
                        if self.user['role'] != 'administrator':
                            raise ValueError('天氣訂閱由平台管理員設定。')
                        sub = bool(payload.get('subscribed'))
                        recipients.bulk_update_subscription(conn, ids, sub)
                        reports.audit(conn, self.identity, "contacts.bulk_sub", f"{len(ids)} contacts", "批次更新訂閱", self.user['company'])
                    else:
                        raise ValueError('不支援的操作。')
                self.respond(200, {'ok': True})
            elif self.path == '/api/assets/upload':
                if not reports.module_enabled(self.user, 'messaging'):
                    raise ValueError('此組織尚未授權訊息發送模組。')
                self.respond(201, composer.upload(payload, self.user))
            elif self.path == '/api/dispatch-scopes/save':
                self.respond(200,reports.save_dispatch_scope(payload,self.identity))
            elif self.path == '/api/sender-grants/save':
                reports.save_grant(payload,self.identity)
                self.respond(200,{'ok':True})
            elif self.path == '/api/organizations/save':
                self.respond(200,reports.save_organization(payload,self.identity))
            elif self.path == '/api/memberships/save':
                reports.save_membership(payload,self.identity)
                self.respond(200,{'ok':True})
            elif self.path == "/api/contact":
                with app.database_connection() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    current = conn.execute('SELECT company,weather_subscribed FROM recipients WHERE recipients.channel_id=current_channel() AND recipient_id=?', (payload.get('id'),)).fetchone()
                    if not current or not reports.same_company(self.user, current[0]):
                        raise ValueError('找不到可管理的聯絡對象。')
                    if self.user['role'] != 'administrator':
                        if payload.get('company', current[0]) != current[0] or 'subscribed' in payload:
                            raise ValueError('組織歸屬與個人天氣模組由平台管理員設定。')
                        payload['subscribed'] = bool(current[1])
                    recipients.update_contact(conn, payload.get("id"), payload.get("alias", ""), payload.get("subscribed", False), notes=payload.get("notes"), tag_ids=payload.get("tag_ids"))
                    department = payload.get("department")
                    if department is not None:
                        if not isinstance(department, str) or len(department.strip()) > 60:
                            raise ValueError("部門名稱請限制在 60 字以內。")
                        conn.execute('UPDATE recipients SET department=? WHERE recipients.channel_id=current_channel() AND recipient_id=?', (department.strip(), payload["id"]))
                    company = payload.get("company")
                    if company is not None:
                        channels.enforce_company(company)
                    if company is not None:
                        if not isinstance(company, str) or len(company.strip()) > 60:
                            raise ValueError("組織名稱請限制在 60 字以內。")
                        conn.execute('UPDATE recipients SET company=? WHERE recipients.channel_id=current_channel() AND recipient_id=?', (company.strip(), payload["id"]))
                    reports.audit(conn, self.identity, "contact.update", payload["id"], "更新備註與分類",self.user['company'])
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
                    reports.audit(conn, self.identity, "profiles.update", "recipients", f"更新 {updated} 個 LINE 名稱，{failed} 個未完成",self.user['company'])
                self.respond(200, {"updated": updated, "failed": failed})
            elif self.path == "/api/send":
                self.respond(202, self.server.dispatcher.submit(payload, actor=self.identity, organization=self.user['company']))
            elif self.path == "/api/jobs/cancel":
                self.server.dispatcher.cancel(payload.get("job_id"), self.identity, self.user['company'])
                self.respond(200, {"ok": True})
            elif self.path == "/api/reports/save":
                self.respond(201, reports.save(payload, self.identity))
            elif self.path == "/api/reports/remove":
                reports.remove(payload.get("report_id"), self.identity)
                self.respond(200, {"ok": True})
            elif self.path == '/api/reports/restore-weather':
                reports.restore_weather(self.identity)
                self.respond(200, {'ok': True})
            elif self.path == "/api/accounts/save":
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
        self.remote_access = RemoteAccess()
        self.auth_mode = os.environ.get('ADMIN_AUTH_MODE', 'cloudflare').strip().lower()
        if self.auth_mode not in {'cloudflare', 'password'}:
            self.server_close()
            raise ValueError('ADMIN_AUTH_MODE 必須為 cloudflare 或 password。')
        self.dispatcher = None
        self.workspace_ready = False

    def start(self):
        reports.bootstrap_users(self.remote_access.emails)
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

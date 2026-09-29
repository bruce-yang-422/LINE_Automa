"""Recipient management: local bearer token or verified Cloudflare Access identity."""

from concurrent.futures import ThreadPoolExecutor
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

import app
from control_runtime import load_settings
import line_api
import recipients
from remote_auth import RemoteAccess
from send_image import publish_image, verify_public_image, send_push


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
            raise ValueError("部分收件者已停用或不存在，請重新整理名單。")
    else:
        raise ValueError("請選擇收件者或天氣訂閱名單。")
    if not selected or len(selected) > 500:
        raise ValueError("請選擇 1 至 500 個有效收件者。")
    if any(not re.fullmatch(r"[UCR][0-9a-fA-F]{32}", r["recipient_id"]) for r in selected):
        raise ValueError("名單含有無效 ID，請重新接收 LINE Webhook。")
    return selected


def job_status(job_id=None):
    with app.database_connection() as conn:
        conn.row_factory = sqlite3.Row
        if job_id:
            jobs = conn.execute("SELECT * FROM send_jobs WHERE job_id=?", (job_id,)).fetchall()
        else:
            jobs = conn.execute("SELECT * FROM send_jobs ORDER BY created_at DESC LIMIT 20").fetchall()
        result = []
        for row in jobs:
            item = dict(row)
            item["deliveries"] = [dict(r) for r in conn.execute(
                "SELECT recipient_id,label,status,request_id,error FROM send_deliveries WHERE job_id=?", (row["job_id"],))]
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
            conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE status='pending'")
            conn.execute("UPDATE send_jobs SET status='interrupted' WHERE status IN ('queued','running')")

    def submit(self, payload):
        job_id = str(UUID(str(payload.get("job_id", ""))))
        with self.lock:
            if self.closing.is_set():
                raise ValueError("服務正在停止，請稍後再發送。")
            existing = job_status(job_id)
            if existing:
                return existing[0]
            load_settings()
            if not os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip():
                raise ValueError("請先在 .env 填入 Channel access token。")
            audience = payload.get("audience")
            with app.database_connection() as conn:
                selected = select_contacts(conn, audience, payload.get("ids"))
            source = Path(str(payload.get("image_path", "")))
            url, content = publish_image(source, os.environ.get("PUBLIC_BASE_URL", "https://reports.stack-base.com"))
            verify_public_image(url, content)
            with app.database_connection() as conn:
                conn.execute("INSERT INTO send_jobs (job_id,audience,image_path,image_url) VALUES (?,?,?,?)",
                             (job_id, audience, str(source), url))
                conn.executemany("INSERT INTO send_deliveries (job_id,recipient_id,label,retry_key) VALUES (?,?,?,?)",
                                 [(job_id, r["recipient_id"], contact_label(r), str(uuid4())) for r in selected])
            self.pool.submit(self.run, job_id)
            return job_status(job_id)[0]

    def run(self, job_id):
        try:
            with app.database_connection() as conn:
                conn.row_factory = sqlite3.Row
                job = conn.execute("SELECT * FROM send_jobs WHERE job_id=?", (job_id,)).fetchone()
                rows = conn.execute("SELECT * FROM send_deliveries WHERE job_id=?", (job_id,)).fetchall()
                conn.execute("UPDATE send_jobs SET status='running' WHERE job_id=?", (job_id,))
            for row in rows:
                recipient_id = row["recipient_id"]
                with app.database_connection() as conn:
                    current = conn.execute("SELECT active,weather_subscribed FROM recipients WHERE recipient_id=?", (recipient_id,)).fetchone()
                    skip = (self.closing.is_set() or not current or not current[0] or
                            (job["audience"] == "subscribers" and not current[1]))
                    conn.execute("UPDATE send_deliveries SET status=? WHERE job_id=? AND recipient_id=?",
                                 ("cancelled" if skip else "sending", job_id, recipient_id))
                if skip:
                    continue
                status, request_id, error = "accepted", "", ""
                try:
                    request_id = send_push(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""), recipient_id,
                                           job["image_url"], retry_key=row["retry_key"])
                except ValueError as exc:
                    error = str(exc)
                    status = "unknown" if "不明" in error else "failed"
                with app.database_connection() as conn:
                    conn.execute("UPDATE send_deliveries SET status=?,request_id=?,error=? WHERE job_id=? AND recipient_id=?",
                                 (status, request_id, error, job_id, recipient_id))
            with app.database_connection() as conn:
                conn.execute("UPDATE send_jobs SET status='finished' WHERE job_id=?", (job_id,))
        except Exception:
            with app.database_connection() as conn:
                conn.execute("UPDATE send_deliveries SET status='unknown' WHERE job_id=? AND status='sending'", (job_id,))
                conn.execute("UPDATE send_deliveries SET status='cancelled' WHERE job_id=? AND status='pending'", (job_id,))
                conn.execute("UPDATE send_jobs SET status='interrupted',error='發送中斷，請確認結果後再操作。' WHERE job_id=?", (job_id,))

    def close(self):
        self.closing.set()
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
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, require_token=True):
        self.identity = "本機管理員"
        for name in ("Host", "Origin", "Authorization", "Cf-Access-Jwt-Assertion", "X-Forwarded-Proto"):
            if len(self.headers.get_all(name, [])) > 1:
                self.respond(403, {"error": "不接受重複的驗證標頭。"})
                return False
        expected_host = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        remote = self.server.remote_access
        if remote.enabled and self.headers.get("Host", "").lower() == remote.host:
            if (self.headers.get("X-Forwarded-Proto") != "https"
                    or (origin is not None and origin != "https://" + remote.host)
                    or (self.command == "POST" and origin != "https://" + remote.host)):
                self.respond(403, {"error": "請透過 HTTPS 管理網址操作。"})
                return False
            try:
                self.identity = remote.verify(self.headers.get("Cf-Access-Jwt-Assertion", ""))
            except ValueError as exc:
                self.respond(403, {"error": str(exc)})
                return False
            return True
        if (self.headers.get("Host") != expected_host or (origin and origin != "http://" + expected_host)
                or any(name in self.headers for name in ("CF-Connecting-IP", "X-Forwarded-For", "X-Forwarded-Proto", "Cf-Access-Jwt-Assertion"))):
            self.respond(403, {"error": "請從本機控制台或已設定的 Cloudflare Access 管理入口登入。"})
            return False
        if require_token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.token):
            self.respond(401, {"error": "管理連線已失效，請從控制台重新開啟。"})
            return False
        return True

    def do_GET(self):
        files = {"/": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/index.html": (app.BASE_DIR.parent / "index.html", "text/html; charset=utf-8"),
                 "/admin.js": (app.BASE_DIR / "web" / "admin.js", "text/javascript; charset=utf-8"),
                 "/admin.css": (app.BASE_DIR / "web" / "admin.css", "text/css; charset=utf-8")}
        if not self.authorized(require_token=self.path not in files):
            return
        if self.path in files:
            path, mime = files[self.path]
            self.respond(200, path.read_bytes(), mime)
        elif self.path == "/api/session":
            self.respond(200, {"identity": self.identity})
        elif self.path == "/api/contacts":
            with app.database_connection() as conn:
                rows = recipients.list_contacts(conn)
            self.respond(200, {"contacts": rows, "default_image": os.environ.get("WEATHER_IMAGE_PATH", r"D:\Tools\ai_weather_report\output\weather_report.png")})
        elif self.path == "/api/jobs":
            self.respond(200, {"jobs": job_status()})
        elif re.fullmatch(r"/api/jobs/[0-9a-f-]{36}", self.path):
            jobs = job_status(self.path.rsplit("/", 1)[1])
            self.respond(200 if jobs else 404, {"jobs": jobs})
        else:
            self.respond(404, {"error": "找不到頁面。"})

    def do_POST(self):
        if not self.authorized():
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 65536 or self.headers.get_content_type() != "application/json":
                raise ValueError("請求格式不正確。")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("請求格式不正確。")
            if self.path == "/api/contact":
                with app.database_connection() as conn:
                    recipients.update_contact(conn, payload.get("id"), payload.get("alias"), payload.get("subscribed"))
                self.respond(200, {"ok": True})
            elif self.path == "/api/profiles":
                load_settings()
                with app.database_connection() as conn:
                    rows = recipients.list_contacts(conn)
                updated, failed = 0, 0
                for row in rows:
                    if not row["active"] or row["kind"] == "room":
                        continue
                    rid = row["recipient_id"]
                    if not re.fullmatch(r"[UC][0-9a-fA-F]{32}", rid):
                        continue
                    try:
                        path = "profile/" + rid if row["kind"] == "user" else "group/" + rid + "/summary"
                        profile = line_api.request(path)
                        name = profile.get("displayName" if row["kind"] == "user" else "groupName", "")
                        with app.database_connection() as conn:
                            conn.execute("UPDATE recipients SET display_name=? WHERE recipient_id=?", (str(name)[:200], rid))
                        updated += 1
                    except ValueError:
                        failed += 1
                self.respond(200, {"updated": updated, "failed": failed})
            elif self.path == "/api/send":
                self.respond(202, self.server.dispatcher.submit(payload))
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
        self.dispatcher = None

    def start(self):
        self.dispatcher = Dispatcher()
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

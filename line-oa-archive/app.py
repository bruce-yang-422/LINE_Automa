"""接收帶有簽章的 LINE Messaging API Webhook，並將訊息儲存於本機。"""

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import recipients
import channels

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", "data/line_archive.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH
MAX_BODY_BYTES = 1_048_576
IMAGE_DIR = BASE_DIR / "published-images"
# 外部腳本放置的公開圖片素材（營業數據、天氣報告等），以 /media/<子資料夾>/<檔名> 對外提供。
MEDIA_DIR = BASE_DIR / "media"
MEDIA_MAX_BYTES = 10 * 1024 * 1024  # LINE 圖片訊息原圖上限
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def public_base_url() -> str:
    """對外 HTTPS 網址（.env 的 PUBLIC_BASE_URL），供 LINE 讀取公開圖片。"""
    value = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if not value:
        raise ValueError("請在 .env 設定 PUBLIC_BASE_URL（對外 HTTPS 網址）後重新啟動 LINE 服務。")
    return value


@contextmanager
def database_connection():
    """每個請求使用獨立連線；交易失敗時回復，結束後關閉連線。"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.create_function("current_channel", 0, channels.current_id)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


SCHEMA_VERSION = 2


def initialize_database() -> None:
    """Open schema v2; apply authorized additive extensions without replacing data."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        populated = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone()
        if populated and version != SCHEMA_VERSION:
            raise RuntimeError("資料庫版本不符；本版不相容舊結構，請先備份並重置資料庫。")
        if not populated and version not in (0, SCHEMA_VERSION):
            raise RuntimeError("資料庫版本不符，請先備份並重置資料庫。")
        conn.execute("PRAGMA journal_mode=WAL")
        if not populated:
            conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        # Approved additive v2 extension; idempotent and serialized across services.
        conn.execute("BEGIN IMMEDIATE")
        for table, column in (("organizations", "duty_enabled"),
                              ("organizations", "forms_enabled"),
                              ("organization_members", "duty_manager")):
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0 CHECK ({column} IN (0, 1))")

        columns = {row[1] for row in conn.execute("PRAGMA table_info(recipients)")}
        if "work_department" not in columns:
            conn.execute("ALTER TABLE recipients ADD COLUMN work_department TEXT NOT NULL DEFAULT ''")

        columns = {row[1] for row in conn.execute("PRAGMA table_info(response_hours)")}
        if "sticker_reply_enabled" not in columns:
            conn.execute("ALTER TABLE response_hours ADD COLUMN sticker_reply_enabled INTEGER NOT NULL DEFAULT 0 CHECK (sticker_reply_enabled IN (0, 1))")

        # New module tables only: no changes to existing business tables.
        duty_schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8").split("-- ============ 值日生第二階段", 1)
        if len(duty_schema) == 2:
            conn.commit()
            conn.executescript("-- ============ 值日生第二階段" + duty_schema[1].split("-- ============ 表單第一階段", 1)[0])
        forms_schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8").split("-- ============ 表單第一階段", 1)
        if len(forms_schema) == 2:
            conn.commit()
            conn.executescript("-- ============ 表單第一階段" + forms_schema[1])
            # Approved switch to shareable forms: retain answers, remove recipient attribution.
            import secrets
            from uuid import uuid4
            conn.execute('BEGIN IMMEDIATE')
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'form_invitations' in tables:
                conn.execute("INSERT OR IGNORE INTO form_notifications SELECT invitation_id,form_id,channel_id,recipient_id,sent_at,last_reminded_at FROM form_invitations")
                if 'form_responses' in tables:
                    for old in conn.execute('SELECT r.invitation_id,i.form_id,r.answers_json,r.questions_snapshot_json,r.first_submitted_at,r.updated_at FROM form_responses r JOIN form_invitations i ON i.invitation_id=r.invitation_id').fetchall():
                        conn.execute('INSERT INTO form_submissions VALUES (?,?,?,?,?,?,?,?)',(uuid4().hex,old[1],secrets.token_urlsafe(32),secrets.token_urlsafe(32),*old[2:]))
                    conn.execute('DROP TABLE form_responses')
                conn.execute('DROP TABLE form_invitations')
            for form_id, in conn.execute('SELECT form_id FROM forms').fetchall():
                conn.execute('INSERT OR IGNORE INTO form_public_links VALUES (?,?)',(form_id,secrets.token_urlsafe(32)))



def valid_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    expected = base64.b64encode(hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()).decode("ascii")
    return hmac.compare_digest(expected, signature)


def source_fields(event: dict) -> tuple[str, str, str | None] | None:
    source = event.get("source") or {}
    source_type = source.get("type")
    key = {"user": "userId", "group": "groupId", "room": "roomId"}.get(source_type)
    if not key or not source.get(key):
        return None
    return source_type, source[key], source.get("userId")


def save_events(events: list[dict]) -> list:
    """保存事件並套用關鍵字訂閱，回傳待送出的 (replyToken, 文字)。交易失敗時回傳 HTTP 503，讓 LINE 重送。"""
    import subscriptions
    replies = []
    with database_connection() as conn:
        with closing(conn.cursor()) as cur:
            for event in events:
                fields = source_fields(event)
                if fields is None:
                    continue
                source_type, conversation_id, sender_user_id = fields
                recipients.handle_event(conn, event, source_type, conversation_id)
                reply = subscriptions.handle_event(conn, event, source_type, conversation_id)
                if reply:
                    replies.append(reply)
                event_type = event.get("type")
                if event_type == "message":
                    message = event.get("message") or {}
                    message_id = message.get("id")
                    if not message_id:
                        continue
                    message_type = message.get("type") or "unknown"
                    text = message.get("text") if message_type == "text" else (message.get("fileName") if message_type == "file" else None)
                    timestamp = event.get("timestamp")
                    reply_token = event.get("replyToken") or ""
                    sent_at = (
                        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat(timespec="milliseconds")
                        if isinstance(timestamp, (int, float))
                        else None
                    )
                    cur.execute(
                        """
                        INSERT INTO line_messages
                            (channel_id, message_id, conversation_type, conversation_id,
                             sender_user_id, message_type, text_content, sent_at,
                             direction, reply_token)
                        VALUES (current_channel(), ?, ?, ?, ?, ?, ?, ?, 'inbound', ?)
                        ON CONFLICT (channel_id, message_id) DO NOTHING
                        """,
                        (message_id, source_type, conversation_id,
                         sender_user_id, message_type, text, sent_at, reply_token),
                    )
                    inserted = cur.rowcount == 1
                    if inserted and not reply and source_type == "user" and message_type == "sticker" and reply_token:
                        import chat
                        auto_reply = chat.queue_sticker_reply(conn, message_id, conversation_id, reply_token)
                        if auto_reply:
                            replies.append(auto_reply)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    cur.execute(
                        """
                        INSERT INTO chat_state (channel_id, chat_id, status, last_inbound_at, updated_at)
                        VALUES (current_channel(), ?, 'open', ?, ?)
                        ON CONFLICT (channel_id, chat_id) DO UPDATE
                        SET last_inbound_at = excluded.last_inbound_at,
                            status = CASE WHEN chat_state.status = 'done' THEN 'open' ELSE chat_state.status END,
                            updated_at = excluded.updated_at
                        """,
                        (conversation_id, sent_at or now_iso, now_iso),
                    )
                elif event_type == "unsend":
                    message_id = (event.get("unsend") or {}).get("messageId")
                    if not message_id:
                        continue
                    # 即使收回事件比原始訊息先到達，也要寫入收回標記。
                    cur.execute(
                        """
                        INSERT INTO line_messages
                            (channel_id,message_id, conversation_type, conversation_id,
                             sender_user_id, message_type, unsent_at)
                        VALUES (current_channel(),?, ?, ?, ?, 'unknown', strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'))
                        ON CONFLICT (channel_id,message_id) DO UPDATE
                        SET text_content = NULL, unsent_at = strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
                        """,
                        (message_id, source_type, conversation_id, sender_user_id),
                    )
    return replies


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        if urlsplit(self.path).path.startswith('/forms/'):
            self.log_message('%s %s %s', self.command, '/forms/[invitation]', code)
        else:
            super().log_request(code, size)

    def serve_forms(self):
        import public_forms
        return public_forms.handle(self)

    def serve_image(self, head_only: bool = False) -> bool:
        # Only explicitly published PNG snapshots are public, never arbitrary local paths.
        match = re.fullmatch(r"/images/([0-9a-f]{32}\.png)", self.path)
        imagemap = re.fullmatch(r"/imagemaps/([0-9a-f]{32})/(240|300|460|700|1040)", self.path)
        if not match and not imagemap:
            return False
        path = IMAGE_DIR / (match[1] if match else f'{imagemap[1]}-{imagemap[2]}.png')
        try:
            with path.open("rb") as image:
                data = image.read(1_000_001)
        except OSError:
            self.respond(404, "找不到圖片")
            return True
        if len(data) > 1_000_000 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            self.respond(404, "找不到圖片")
            return True
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            self.wfile.write(data)
        return True

    def do_HEAD(self) -> None:
        if self.serve_forms():
            return
        if not self.serve_image(head_only=True) and not self.serve_media(head_only=True):
            self.send_response(404)
            self.end_headers()

    def respond(self, code: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_media(self, head_only: bool = False) -> bool:
        # 只開放 media/ 底下一層子資料夾內的 PNG／JPG；查詢字串（例如 ?v=日期）僅供 LINE 快取區分。
        path = urlsplit(self.path).path
        match = re.fullmatch(r"/media/(?:([A-Za-z0-9_-]{1,40})/)?([A-Za-z0-9_-][A-Za-z0-9_.-]{0,99})", path)
        if not path.startswith("/media/"):
            return False
        suffix = Path(match[2]).suffix.lower() if match else ""
        if not match or suffix not in MEDIA_TYPES:
            self.respond(404, "找不到圖片")
            return True
        root = MEDIA_DIR.resolve()
        file = (MEDIA_DIR / (match[1] or "") / match[2]).resolve()
        try:
            if file.parent not in (root, root / (match[1] or "")) or not file.is_file():
                raise OSError
            with file.open("rb") as stream:
                data = stream.read(MEDIA_MAX_BYTES + 1)
        except OSError:
            self.respond(404, "找不到圖片")
            return True
        signature = data.startswith(b"\x89PNG\r\n\x1a\n") if suffix == ".png" else data.startswith(b"\xff\xd8\xff")
        if len(data) > MEDIA_MAX_BYTES or not signature:
            self.respond(404, "找不到圖片")
            return True
        self.send_response(200)
        self.send_header("Content-Type", MEDIA_TYPES[suffix])
        self.send_header("Content-Length", str(len(data)))
        # 檔案可能被同名覆寫，快取時間短；要立刻換圖請在網址加 ?v=日期 或改檔名。
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            self.wfile.write(data)
        return True

    def do_GET(self) -> None:
        if self.serve_forms():
            return
        if self.serve_image() or self.serve_media():
            return
        if self.path == "/healthz":
            try:
                with database_connection() as conn:
                    conn.execute('SELECT message_id FROM line_messages WHERE line_messages.channel_id=current_channel() LIMIT 1')
                self.respond(200, "ok")
            except sqlite3.Error:
                self.respond(503, "資料庫無法使用")
        else:
            self.respond(404, "找不到資源")

    def do_POST(self) -> None:
        if self.serve_forms():
            return
        try:
            row = channels.webhook_channel(self.path)
            with channels.use(row['channel_id']):
                if not channels.operational(row):
                    self.respond(403, "OA 已停用")
                    return
                self.receive_webhook(row)
        except ValueError:
            self.respond(404, "找不到可使用的 Webhook")

    def receive_webhook(self, channel) -> None:
        try:
            size = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.respond(411, "必須提供有效的 Content-Length 標頭")
            return
        if size < 0 or size > MAX_BODY_BYTES:
            self.respond(413, "請求本文大小超出允許範圍")
            return
        body = self.rfile.read(size)
        if not valid_signature(body, self.headers.get("x-line-signature", ""), channels.credentials()[1]):
            self.respond(401, "簽章無效")
            return
        try:
            payload = json.loads(body)
            events = payload["events"]
            if payload.get('destination') != channel['bot_user_id']:
                self.respond(401, "Webhook OA 身分不符")
                return
            if not isinstance(events, list):
                raise ValueError("events 必須為陣列")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.respond(400, "Webhook 格式無效")
            return
        try:
            replies = save_events(events)
            channels.seen(channel["channel_id"])
        except sqlite3.Error:
            self.respond(503, "資料庫無法使用")
            return
        self.respond(200, "ok")
        # 訂閱已寫入資料庫後才更新名冊與回覆；LINE 重送時不會重複切換或回覆。
        if replies or any(e.get("type") in {"follow", "unfollow", "join", "leave"} for e in events):
            import subscriptions
            try:
                subscriptions.export()
            except (OSError, sqlite3.Error):
                pass  # 背景排程會在下一輪重新輸出名冊。
        if replies:
            import line_api
            for token, text in replies:
                status = "sent"
                try:
                    line_api.reply(token, text)
                except ValueError:
                    status = "unknown"
                try:
                    with database_connection() as conn:
                        conn.execute("UPDATE line_messages SET delivery_status=?,reply_token='' WHERE channel_id=current_channel() AND direction='outbound' AND sent_by='系統（貼圖提示）' AND reply_token=?", (status, token))
                except sqlite3.Error:
                    pass


if __name__ == "__main__":
    initialize_database()
    profiles = recipients.ProfileRefresher()
    profiles.start()
    try:
        with ThreadingHTTPServer(("127.0.0.1", 18474), Handler) as server:
            server.serve_forever()
    finally:
        profiles.close()

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
import recipients

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", "data/line_archive.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
MAX_BODY_BYTES = 1_048_576
IMAGE_DIR = BASE_DIR / "published-images"


@contextmanager
def database_connection():
    """每個請求使用獨立連線；交易失敗時回復，結束後關閉連線。"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_database() -> None:
    """啟動時自動建立資料夾與資料表，保留既有紀錄。"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
        import reports
        reports.migrate(conn)
        recipients.migrate_contacts(conn)


def valid_signature(body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("ascii")
    return bool(signature) and hmac.compare_digest(expected, signature)


def source_fields(event: dict) -> tuple[str, str, str | None] | None:
    source = event.get("source") or {}
    source_type = source.get("type")
    key = {"user": "userId", "group": "groupId", "room": "roomId"}.get(source_type)
    if not key or not source.get(key):
        return None
    return source_type, source[key], source.get("userId")


def save_events(events: list[dict]) -> list:
    # 交易失敗時回傳 HTTP 503，讓 LINE 可以重新傳送 Webhook。
    replies = []
    with database_connection() as conn:
        with closing(conn.cursor()) as cur:
            for event in events:
                fields = source_fields(event)
                if fields is None:
                    continue
                source_type, conversation_id, sender_user_id = fields
                reply = recipients.handle_event(conn, event, source_type, conversation_id)
                if reply:
                    replies.append(reply)
                event_type = event.get("type")
                if event_type == "message":
                    message = event.get("message") or {}
                    message_id = message.get("id")
                    if not message_id:
                        continue
                    message_type = message.get("type") or "unknown"
                    text = message.get("text") if message_type == "text" else None
                    timestamp = event.get("timestamp")
                    sent_at = (
                        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat(timespec="milliseconds")
                        if isinstance(timestamp, (int, float))
                        else None
                    )
                    cur.execute(
                        """
                        INSERT INTO line_messages
                            (message_id, conversation_type, conversation_id,
                             sender_user_id, message_type, text_content, sent_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (message_id) DO NOTHING
                        """,
                        (message_id, source_type, conversation_id,
                         sender_user_id, message_type, text, sent_at),
                    )
                elif event_type == "unsend":
                    message_id = (event.get("unsend") or {}).get("messageId")
                    if not message_id:
                        continue
                    # 即使收回事件比原始訊息先到達，也要寫入收回標記。
                    cur.execute(
                        """
                        INSERT INTO line_messages
                            (message_id, conversation_type, conversation_id,
                             sender_user_id, message_type, unsent_at)
                        VALUES (?, ?, ?, ?, 'unknown', strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'))
                        ON CONFLICT (message_id) DO UPDATE
                        SET text_content = NULL, unsent_at = strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
                        """,
                        (message_id, source_type, conversation_id, sender_user_id),
                    )
    return replies


class Handler(BaseHTTPRequestHandler):
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
        if not self.serve_image(head_only=True):
            self.send_response(404)
            self.end_headers()

    def respond(self, code: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.serve_image():
            return
        if self.path == "/healthz":
            try:
                with database_connection() as conn:
                    conn.execute("SELECT message_id FROM line_messages LIMIT 1")
                self.respond(200, "ok")
            except sqlite3.Error:
                self.respond(503, "資料庫無法使用")
        else:
            self.respond(404, "找不到資源")

    def do_POST(self) -> None:
        if self.path != "/webhook":
            self.respond(404, "找不到資源")
            return
        try:
            size = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.respond(411, "必須提供有效的 Content-Length 標頭")
            return
        if size < 0 or size > MAX_BODY_BYTES:
            self.respond(413, "請求本文大小超出允許範圍")
            return
        body = self.rfile.read(size)
        if not valid_signature(body, self.headers.get("x-line-signature", "")):
            self.respond(401, "簽章無效")
            return
        try:
            payload = json.loads(body)
            events = payload["events"]
            if not isinstance(events, list):
                raise ValueError("events 必須為陣列")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.respond(400, "Webhook 格式無效")
            return
        try:
            replies = save_events(events)
        except sqlite3.Error:
            self.respond(503, "資料庫無法使用")
            return
        self.respond(200, "ok")
        # Acknowledge persisted subscriptions before calling LINE; redelivery won't toggle or reply twice.
        if replies and os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"):
            import line_api
            for token, text in replies:
                try:
                    line_api.reply(token, text)
                except ValueError:
                    # Subscription state remains committed. Users can request status again.
                    pass


if __name__ == "__main__":
    if not CHANNEL_SECRET:
        raise SystemExit("請先設定 LINE_CHANNEL_SECRET")
    initialize_database()
    profiles = recipients.ProfileRefresher()
    profiles.start()
    try:
        with ThreadingHTTPServer(("127.0.0.1", 18474), Handler) as server:
            server.serve_forever()
    finally:
        profiles.close()

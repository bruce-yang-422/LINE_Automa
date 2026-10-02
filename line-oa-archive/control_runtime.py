"""Local desktop controller entry point; no network stop endpoint or extra packages."""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parent


def load_settings():
    """Read literal KEY=value settings, never execute shell or expand variables."""
    settings = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            # 只讀部署基礎設定；LINE OA 憑證與模組設定一律存在資料庫，由網頁後台設定。
            if separator and key.strip() in {"DATABASE_PATH", "PUBLIC_BASE_URL", "ADMIN_PUBLIC_HOST"}:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                settings[key.strip()] = value
    os.environ.update(settings)
    # 站內登入不需 .env 設定即可使用；OA 由網頁後台新增。
    return True


def oa_configured():
    """資料庫中是否已有啟用中的 LINE OA（唯讀檢查，資料庫不存在時回傳 False）。"""
    path = Path(os.environ.get("DATABASE_PATH", "data/line_archive.db"))
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            return bool(conn.execute("SELECT 1 FROM line_channels WHERE active=1 LIMIT 1").fetchone())
    except sqlite3.Error:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--instance", type=UUID)
    parser.add_argument("--port", type=int, default=18474)
    parser.add_argument("--admin-port", type=int, default=18475)
    args = parser.parse_args()
    configured = load_settings()
    if args.check:
        print(json.dumps({"configured": configured, "python_ok": sys.version_info >= (3, 11),
                          "public_base_url": bool(os.environ.get("PUBLIC_BASE_URL", "").strip()),
                          "oa_configured": oa_configured()}))
        return 0
    if not configured or not args.instance:
        print("Setup required: start with an instance id.", file=sys.stderr)
        return 2

    # app reads environment settings at import time.
    import app

    instance = str(args.instance)
    state = ROOT / "instance"
    state.mkdir(exist_ok=True)
    stop_file = state / ("stop-" + instance)

    class ManagedHandler(app.Handler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def do_GET(self):
            if self.path.split("?", 1)[0] != "/_control/healthz":
                return super().do_GET()
            try:
                with app.database_connection() as conn:
                    conn.execute("SELECT message_id FROM line_messages LIMIT 1")
            except app.sqlite3.Error:
                self.respond(503, "Database unavailable")
                return
            payload = json.dumps({"application": "LINE_Automation", "protocol": 1,
                                  "instance": instance, "stopping": stop_file.exists()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            # Do not put user-controlled paths or message contents in controller logs.
            pass

    class ManagedServer(app.ThreadingHTTPServer):
        # ThreadingHTTPServer defaults to daemon threads, which would drop active writes.
        daemon_threads = False
        block_on_close = True

    # Bind before opening the database; an occupied port must not launch a second service.
    from admin_server import AdminServer
    with ManagedServer(("127.0.0.1", args.port), ManagedHandler) as server:
        admin = AdminServer(args.admin_port)
        profiles = app.recipients.ProfileRefresher()
        try:
            app.initialize_database()
            admin.start()
            profiles.start()
            server.timeout = 0.25
            while not stop_file.exists():
                server.handle_request()
        finally:
            profiles.close()
            admin.close()
        # server_close waits for request threads and their database transactions.
    stop_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Service failed. Check configuration, database permissions, and port availability.", file=sys.stderr)
        raise SystemExit(1)

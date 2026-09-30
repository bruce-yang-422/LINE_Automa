"""Local desktop controller entry point; no network stop endpoint or extra packages."""

import argparse
import json
import os
from pathlib import Path
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
            if separator and key.strip() in {"LINE_CHANNEL_SECRET", "DATABASE_PATH", "LINE_CHANNEL_ACCESS_TOKEN",
                                             "LINE_PUSH_USER_ID", "LINE_PUSH_GROUP_ID", "PUBLIC_BASE_URL", "WEATHER_IMAGE_PATH",
                                             "WEATHER_MODULE_ENABLED", "WEATHER_OWNER_EMAIL",
                                             "ADMIN_PUBLIC_HOST", "ADMIN_AUTH_MODE", "CF_ACCESS_TEAM_DOMAIN", "CF_ACCESS_AUD", "ADMIN_ALLOWED_EMAILS"}:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                settings[key.strip()] = value
    os.environ.update(settings)
    secret = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
    # Native login can be set up before adding the first OA through the website.
    return bool((secret and secret != "replace_with_messaging_api_channel_secret")
                or os.environ.get('ADMIN_AUTH_MODE') == 'password')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--instance", type=UUID)
    parser.add_argument("--port", type=int, default=18474)
    parser.add_argument("--admin-port", type=int, default=18475)
    args = parser.parse_args()
    configured = load_settings()
    if args.check:
        print(json.dumps({"configured": configured, "python_ok": sys.version_info >= (3, 11)}))
        return 0
    if not configured or not args.instance:
        print("Setup required: configure native login or LINE_CHANNEL_SECRET before starting.", file=sys.stderr)
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

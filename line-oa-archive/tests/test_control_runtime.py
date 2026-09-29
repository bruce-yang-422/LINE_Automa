"""Exercise the managed HTTP process with temporary settings and database."""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class ManagedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="line-runtime-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("control_runtime.py", "app.py", "schema.sql", "recipients.py", "admin_server.py", "line_api.py", "send_image.py", "remote_auth.py"):
            shutil.copy2(ROOT / name, self.root / name)
        self.environment = os.environ.copy()
        self.environment.pop("LINE_CHANNEL_SECRET", None)
        self.environment.pop("DATABASE_PATH", None)
        self.secret = "test-secret-not-a-real-credential"
        (self.root / ".env").write_text(
            f'LINE_CHANNEL_SECRET="{self.secret}"\nDATABASE_PATH=data/test.db\n', encoding="utf-8-sig")

    def start_service(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.instance = str(uuid4())
        self.process = subprocess.Popen(
            [sys.executable, str(self.root / "control_runtime.py"), "--instance", self.instance,
             "--port", str(self.port), "--admin-port", "0"], env=self.environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.cleanup_process)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                with urlopen(self.url("/healthz"), timeout=1) as response:
                    self.assertEqual(response.read(), b"ok")
                return
            except (URLError, TimeoutError):
                if self.process.poll() is not None:
                    self.fail("Managed process exited during startup")
                time.sleep(0.05)
        self.fail("Managed process did not start")

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def cleanup_process(self):
        if self.process.poll() is None:
            (self.root / "instance" / ("stop-" + self.instance)).touch()
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def test_health_signed_webhook_and_graceful_stop(self):
        self.start_service()
        with urlopen(self.url("/_control/healthz?probe=test"), timeout=2) as response:
            state = json.load(response)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(state["application"], "LINE_Automation")
        self.assertEqual(state["instance"], self.instance)
        self.assertNotIn(self.secret, json.dumps(state))
        body = json.dumps({"events": [{"type": "message", "source": {"type": "user", "userId": "test-user"},
                                     "message": {"id": "1", "type": "text", "text": "test"}}]}).encode()
        signature = base64.b64encode(hmac.new(self.secret.encode(), body, hashlib.sha256).digest()).decode()
        with urlopen(Request(self.url("/webhook"), data=body, headers={"x-line-signature": signature}), timeout=2) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.url("/webhook"), data=body), timeout=2)
        self.assertEqual(raised.exception.code, 401)
        raised.exception.close()
        (self.root / "instance" / ("stop-" + self.instance)).touch()
        self.assertEqual(self.process.wait(timeout=5), 0)
        with closing(sqlite3.connect(self.root / "data/test.db")) as conn:
            self.assertEqual(conn.execute("SELECT text_content FROM line_messages").fetchall(), [("test",)])

    def test_stop_waits_for_in_flight_database_transaction(self):
        self.start_service()
        body = json.dumps({"events": [{"type": "message", "source": {"type": "user", "userId": "test-user"},
                                     "message": {"id": "pending", "type": "text", "text": "saved before stop"}}]}).encode()
        signature = base64.b64encode(hmac.new(self.secret.encode(), body, hashlib.sha256).digest()).decode()

        def send_message():
            with urlopen(Request(self.url("/webhook"), data=body, headers={"x-line-signature": signature}), timeout=8) as response:
                return response.status

        with closing(sqlite3.connect(self.root / "data/test.db")) as lock, ThreadPoolExecutor(max_workers=1) as pool:
            lock.execute("BEGIN IMMEDIATE")
            request = pool.submit(send_message)
            try:
                time.sleep(0.4)
                self.assertFalse(request.done())
                (self.root / "instance" / ("stop-" + self.instance)).touch()
                time.sleep(0.5)
                self.assertIsNone(self.process.poll())
            finally:
                lock.rollback()
            self.assertEqual(request.result(timeout=5), 200)
        self.assertEqual(self.process.wait(timeout=5), 0)
        with closing(sqlite3.connect(self.root / "data/test.db")) as conn:
            self.assertEqual(conn.execute("SELECT text_content FROM line_messages WHERE message_id='pending'").fetchone(),
                             ("saved before stop",))

    def test_missing_secret_does_not_start_or_create_database(self):
        (self.root / ".env").write_text("LINE_CHANNEL_SECRET=replace_with_messaging_api_channel_secret\n")
        result = subprocess.run([sys.executable, str(self.root / "control_runtime.py"), "--check"],
                                env=self.environment, capture_output=True, text=True, timeout=5)
        self.assertFalse(json.loads(result.stdout)["configured"])
        result = subprocess.run([sys.executable, str(self.root / "control_runtime.py"), "--instance", str(uuid4())],
                                env=self.environment, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "data").exists())

    def test_wrong_stop_marker_does_not_stop_service(self):
        self.start_service()
        (self.root / "instance" / ("stop-" + str(uuid4()))).touch()
        time.sleep(0.4)
        self.assertIsNone(self.process.poll())

    def test_public_png_route_does_not_expose_other_files(self):
        self.start_service()
        directory = self.root / "published-images"
        directory.mkdir()
        filename = "a" * 32 + ".png"
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH1cAAAAASUVORK5CYII=")
        (directory / filename).write_bytes(png)
        with urlopen(self.url("/images/" + filename), timeout=2) as response:
            self.assertEqual(response.headers["Content-Type"], "image/png")
            self.assertEqual(response.read(), png)
        with urlopen(Request(self.url("/images/" + filename), method="HEAD"), timeout=2) as response:
            self.assertEqual(int(response.headers["Content-Length"]), len(png))
            self.assertEqual(response.read(), b"")
        for path in ("/.env", "/images/", "/images/../.env", "/images/%2e%2e/.env"):
            with self.assertRaises(HTTPError) as raised:
                urlopen(self.url(path), timeout=2)
            self.assertEqual(raised.exception.code, 404)
            raised.exception.close()


if __name__ == "__main__":
    unittest.main()

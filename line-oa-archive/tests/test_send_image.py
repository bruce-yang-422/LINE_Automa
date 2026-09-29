import base64
from email.message import Message
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import send_image

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH1cAAAAASUVORK5CYII=")


class SendImageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="line-image-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "weather.png"
        self.source.write_bytes(PNG)
        self.patch_root = patch.object(send_image, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.patch_env = patch.dict(os.environ, {}, clear=True)
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)

    def test_publish_copies_snapshot_and_limits_preview_size(self):
        url, data = send_image.publish_image(self.source, "https://reports.stack-base.com")
        self.source.write_bytes(b"changed later")
        saved = self.root / "published-images" / url.rsplit("/", 1)[1]
        self.assertEqual(saved.read_bytes(), PNG)
        self.assertEqual(data, PNG)
        self.source.write_bytes(PNG + b"x" * 1_000_000)
        with self.assertRaises(ValueError):
            send_image.publish_image(self.source, "https://reports.stack-base.com")
        with self.assertRaises(ValueError):
            send_image.publish_image(saved, "http://reports.stack-base.com")

    def test_targets_are_separate_and_ambiguous_targets_are_rejected(self):
        os.environ["DATABASE_PATH"] = "test.db"
        con = sqlite3.connect(self.root / "test.db")
        self.addCleanup(con.close)
        con.execute("CREATE TABLE line_messages (conversation_type TEXT, conversation_id TEXT)")
        user = "U" + "1" * 32
        group = "C" + "2" * 32
        con.executemany("INSERT INTO line_messages VALUES (?, ?)", [("user", user), ("group", group)])
        con.commit()
        self.assertEqual(send_image.select_recipient("user"), user)
        self.assertEqual(send_image.select_recipient("group"), group)
        con.execute("INSERT INTO line_messages VALUES ('user', ?)", ("U" + "3" * 32,))
        con.commit()
        with self.assertRaises(ValueError):
            send_image.select_recipient("user")
        os.environ["LINE_PUSH_USER_ID"] = user
        self.assertEqual(send_image.select_recipient("user"), user)
        os.environ["LINE_PUSH_USER_ID"] = group
        with self.assertRaises(ValueError):
            send_image.select_recipient("user")

    def test_push_payload_and_no_automatic_retry_on_timeout(self):
        class Response(io.BytesIO):
            status = 200
            headers = {"x-line-request-id": "test-request"}

        url = "https://reports.stack-base.com/images/" + "a" * 32 + ".png"
        with patch.object(send_image, "urlopen", return_value=Response(b"{}")) as call:
            self.assertEqual(send_image.send_push("test-token", "U" + "1" * 32, url), "test-request")
            request = call.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(request.full_url, "https://api.line.me/v2/bot/message/push")
            self.assertEqual(payload["messages"][0]["originalContentUrl"], url)
            self.assertEqual(payload["messages"][0]["previewImageUrl"], url)
            self.assertEqual(payload["to"], "U" + "1" * 32)
        with patch.object(send_image, "urlopen", side_effect=TimeoutError) as call:
            with self.assertRaisesRegex(ValueError, "送達狀態不明"):
                send_image.send_push("test-token", "U" + "1" * 32, url)
            self.assertEqual(call.call_count, 1)

    def test_public_verification_rejects_wrong_content(self):
        class Response(io.BytesIO):
            headers = Message()
        response = Response(b"not the PNG")
        response.headers["Content-Type"] = "image/png"
        with patch.object(send_image, "urlopen", return_value=response):
            with self.assertRaises(ValueError):
                send_image.verify_public_image("https://reports.stack-base.com/images/test.png", PNG)

    def test_both_preflight_resolves_all_targets_before_sending(self):
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test-token"
        with patch.object(send_image, "load_settings"), patch.object(send_image, "select_recipient", side_effect=["U" + "1" * 32, ValueError("missing group")]), \
                patch.object(send_image, "send_push") as push, patch.object(send_image, "publish_image") as publish, \
                patch("sys.argv", ["send_image.py", str(self.source), "--target", "both"]):
            with self.assertRaises(ValueError):
                send_image.main()
            push.assert_not_called()
            publish.assert_not_called()


    def test_subscribers_use_authenticated_local_manager(self):
        folder = self.root / "instance"
        folder.mkdir()
        (folder / "admin-access.json").write_text(json.dumps({"port": 12345, "token": "local-test-token"}))
        response = io.BytesIO(json.dumps({"status": "finished", "deliveries": [{"label": "test", "status": "accepted"}]}).encode())
        with patch.object(send_image, "urlopen", return_value=response) as call, patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(send_image.send_to_subscribers(self.source), 0)
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:12345/api/send")
        self.assertEqual(request.get_header("Authorization"), "Bearer local-test-token")
        self.assertEqual(json.loads(request.data)["audience"], "subscribers")


if __name__ == "__main__":
    unittest.main()

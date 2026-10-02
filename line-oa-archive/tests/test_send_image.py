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


if __name__ == "__main__":
    unittest.main()

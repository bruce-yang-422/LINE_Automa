"""Public /media/ route: only PNG/JPG files directly inside media/ or one subfolder."""
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import app

PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 32
JPG = b'\xff\xd8\xff' + b'0' * 32


class PublicMediaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='line-media-test-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        media = root / 'media'
        (media / 'weather').mkdir(parents=True)
        (media / 'weather' / 'today.png').write_bytes(PNG)
        (media / 'sales').mkdir()
        (media / 'sales' / 'report-2026.jpg').write_bytes(JPG)
        (media / 'sales' / 'fake.png').write_bytes(b'not an image')
        (media / 'notes.txt').write_bytes(b'secret')
        (root / 'outside.png').write_bytes(PNG)
        p = patch.object(app, 'MEDIA_DIR', media)
        p.start()
        self.addCleanup(p.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path, method='GET'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path)
            response = conn.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            conn.close()

    def test_serves_png_and_jpg_with_cache_busting_query(self):
        self.assertEqual(self.get('/media/weather/today.png'), (200, 'image/png', PNG))
        self.assertEqual(self.get('/media/weather/today.png?v=2026-10-05')[2], PNG)
        self.assertEqual(self.get('/media/sales/report-2026.jpg')[:2], (200, 'image/jpeg'))
        self.assertEqual(self.get('/media/weather/today.png', 'HEAD')[0], 200)

    def test_rejects_traversal_wrong_types_and_fake_images(self):
        for path in ('/media/../outside.png', '/media/%2e%2e/outside.png', '/media/weather/../../outside.png',
                     '/media/notes.txt', '/media/sales/fake.png', '/media/a/b/today.png',
                     '/media/weather/missing.png', '/media/', '/media/weather/'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)


if __name__ == '__main__':
    unittest.main()

"""第七階段驗收：只有三項部署設定的全新安裝，可完成首次設定 → 建立組織 → 網頁設定 OA → Webhook 收訊 → 發送。"""
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import app
import admin_server
import channels
import recipients
import reports
import site_auth

USER = 'U' + '7' * 32
SECRET = 'f' * 32


class FreshInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='line-fresh-install-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'instance').mkdir()
        shutil.copyfile(app.BASE_DIR / 'schema.sql', self.root / 'schema.sql')
        shutil.copytree(app.BASE_DIR / 'web', self.root / 'web')
        for name, value in [('BASE_DIR', self.root), ('DATABASE_PATH', self.root / 'data' / 'line.db')]:
            p = patch.object(app, name, value); p.start(); self.addCleanup(p.stop)
        # 只有部署基礎設定；沒有任何 LINE 憑證或帳號設定。
        p = patch.dict(os.environ, {'DATABASE_PATH': 'data/line.db', 'PUBLIC_BASE_URL': 'https://reports.example.test',
                                    'ADMIN_PUBLIC_HOST': 'admin.example.test'}, clear=True)
        p.start(); self.addCleanup(p.stop)

    def admin_request(self, server, path, payload=None, channel=None):
        headers = {'Authorization': 'Bearer ' + server.token, 'Content-Type': 'application/json'}
        if payload is not None:
            headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
        if channel:
            headers['X-Line-Channel'] = channel
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        try:
            conn.request('POST' if payload is not None else 'GET', path, json.dumps(payload) if payload is not None else None, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_first_setup_organization_oa_webhook_and_send(self):
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], app.SCHEMA_VERSION)
            tables = conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall(), tables)

        server = admin_server.AdminServer(0); server.start(); self.addCleanup(server.close)
        # 1. 首次設定：本機控制台建立第一位平台管理員。
        code, setup = self.admin_request(server, '/api/setup/first-admin', {'email': 'vendor@example.test'})
        self.assertEqual(code, 200)
        site_auth.activate(setup['local_url'].split('#setup=')[1], 'A memorable testing sentence 2026!')
        # 2. 平台管理員建立組織與該組織的管理員。
        code, org = self.admin_request(server, '/api/organizations/save', {'name': '星河科技', 'kind': 'company', 'active': True,
                                       'reports_enabled': True, 'messaging_enabled': True, 'weather_enabled': False})
        self.assertEqual(code, 200)
        org_id = org['org_id']
        self.assertEqual(self.admin_request(server, '/api/accounts/save', {'email': 'boss@example.test', 'role': 'org_admin',
                                            'organization_id': org_id, 'active': True})[0], 200)
        # 3. 在網頁設定 OA：只查驗 Bot 身分，不呼叫其他 LINE API。
        bot = 'U' + hashlib.md5(b'token').hexdigest()
        with patch('line_api.request', return_value={'userId': bot, 'displayName': '星河客服', 'basicId': '@starriver'}):
            code, oa = self.admin_request(server, '/api/channels/save', {'workspace_id': 'o:' + org_id, 'secret': SECRET,
                                          'access_token': 'token', 'name': '星河客服'})
        self.assertEqual(code, 200)
        self.assertEqual(oa['webhook_url'], 'https://reports.example.test/webhook/' + oa['channel_id'])
        # 4. Webhook 收訊：簽章與 destination 都須符合此 OA。
        webhook = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=webhook.serve_forever, daemon=True).start()
        self.addCleanup(webhook.server_close); self.addCleanup(webhook.shutdown)
        body = json.dumps({'destination': bot, 'events': [{'type': 'message', 'timestamp': 1790750000000,
                           'source': {'type': 'user', 'userId': USER}, 'message': {'id': 'm1', 'type': 'text', 'text': '你好'}}]}).encode()
        signature = base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()
        conn = http.client.HTTPConnection('127.0.0.1', webhook.server_port, timeout=10)
        conn.request('POST', '/webhook/' + oa['channel_id'], body, {'x-line-signature': signature})
        self.assertEqual(conn.getresponse().status, 200)
        conn.close()
        with channels.use(oa['channel_id']), app.database_connection() as conn:
            contacts = recipients.list_contacts(conn)
        self.assertEqual([(c['recipient_id'], c['organization_id']) for c in contacts], [(USER, org_id)])
        # 5. 組織管理員發送文字訊息（LINE 推播以假函式取代）。
        with channels.use(oa['channel_id']):
            job = server.dispatcher.submit({'job_id': str(uuid4()), 'audience': 'selected', 'ids': [USER], 'message_text': '收到，謝謝。',
                                            'scheduled_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()},
                                           actor='boss@example.test', organization=org_id)
        with app.database_connection() as conn:
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at=''")
        with patch.object(admin_server, 'send_push', return_value='request-id') as push:
            server.dispatcher.run(job['job_id'])
        push.assert_called_once()
        self.assertEqual(push.call_args.args[:2], ('token', USER))

    def test_old_database_is_refused(self):
        # 第七階段以前的資料庫沒有結構版本；不沿用，必須備份後重建。
        app.DATABASE_PATH.parent.mkdir(parents=True)
        with closing(sqlite3.connect(app.DATABASE_PATH)) as conn:
            conn.execute('CREATE TABLE recipients (recipient_id TEXT PRIMARY KEY, organization TEXT)')
            conn.commit()
        with self.assertRaises(RuntimeError):
            app.initialize_database()


if __name__ == '__main__':
    unittest.main()

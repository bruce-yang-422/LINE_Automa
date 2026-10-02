"""首次設定（第一位平台管理員）與 create_admin.py；權限規格第 9 節。"""
import builtins
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import app
import admin_server
import create_admin
import reports
import site_auth

PASSWORD = 'A memorable testing sentence 2026!'


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='line-first-run-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'instance').mkdir()
        shutil.copyfile(app.BASE_DIR / 'schema.sql', self.root / 'schema.sql')
        shutil.copytree(app.BASE_DIR / 'web', self.root / 'web')
        for name, value in [('BASE_DIR', self.root), ('DATABASE_PATH', self.root / 'test.db')]:
            p = patch.object(app, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'ADMIN_PUBLIC_HOST': 'admin.example.test'}, clear=True)
        p.start(); self.addCleanup(p.stop)
        app.initialize_database()
        self.server = admin_server.AdminServer(0); self.server.start(); self.addCleanup(self.server.close)

    def request(self, path, body=None, local=True, token=True):
        if local:
            headers = {'Authorization': 'Bearer ' + self.server.token} if token else {}
            if body is not None:
                headers.update({'Origin': f'http://127.0.0.1:{self.server.server_port}', 'Content-Type': 'application/json'})
        else:
            headers = {'Host': 'admin.example.test', 'X-Forwarded-Proto': 'https'}
            if body is not None:
                headers.update({'Origin': 'https://admin.example.test', 'Content-Type': 'application/json'})
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            conn.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_local_console_creates_first_platform_admin_once(self):
        self.assertTrue(self.request('/api/session')[1]['needs_setup'])
        self.assertFalse(self.request('/api/auth/setup-state', local=False)[1]['initialized'])
        # 對外網址與沒有控制台 token 的本機連線都不能建立帳號。
        self.assertEqual(self.request('/api/setup/first-admin', {'email': 'root@example.test'}, local=False)[0], 401)
        self.assertEqual(self.request('/api/setup/first-admin', {'email': 'root@example.test'}, token=False)[0], 401)
        self.assertEqual(self.request('/api/setup/first-admin', {'email': 'not-an-email'})[0], 400)
        code, result = self.request('/api/setup/first-admin', {'email': 'Root@Example.test', 'display_name': '供應商'})
        self.assertEqual(code, 200)
        self.assertEqual(result['email'], 'root@example.test')
        self.assertTrue(result['url'].startswith('https://admin.example.test/login#setup='))
        self.assertTrue(result['local_url'].startswith(f'http://127.0.0.1:{self.server.server_port}/login#setup='))
        # 建立後首次設定頁不再出現，也不能再呼叫。
        self.assertFalse(self.request('/api/session')[1]['needs_setup'])
        self.assertTrue(self.request('/api/auth/setup-state', local=False)[1]['initialized'])
        self.assertEqual(self.request('/api/setup/first-admin', {'email': 'second@example.test'})[0], 403)
        # 本人以一次性連結設定密碼後可登入；資料庫只有雜湊。
        site_auth.activate(result['local_url'].split('#setup=')[1], PASSWORD)
        self.assertEqual(reports.login_account('root@example.test')['role'], 'platform_admin')
        self.assertTrue(site_auth.verify_password(PASSWORD, site_auth.credential('root@example.test')))
        actions = [e['action'] for e in reports.activity()]
        self.assertIn('platform_admin.setup', actions)

    def run_cli(self, answers, argv=('create_admin.py',)):
        output = io.StringIO()
        with patch.object(sys, 'argv', list(argv)), patch.object(builtins, 'input', side_effect=list(answers)), \
                patch.object(create_admin, 'load_settings'), redirect_stdout(output):
            code = create_admin.main()
        return code, output.getvalue()

    def test_create_admin_cli_creates_resets_and_rejects_arguments(self):
        code, out = self.run_cli(['ops@example.test', '維運'])
        self.assertEqual(code, 0)
        self.assertIn('https://admin.example.test/login#setup=', out)
        self.assertEqual(reports.login_account('ops@example.test')['role'], 'platform_admin')
        # 已存在：確認後產生重設連結；不確認則不變更。
        self.assertEqual(self.run_cli(['ops@example.test', 'n'])[0], 0)
        code, out = self.run_cli(['ops@example.test', 'y'])
        self.assertEqual(code, 0)
        self.assertIn('#setup=', out)
        # 不接受任何參數（包含密碼）；組織帳號不能變成平台管理員。
        self.assertEqual(self.run_cli([], argv=('create_admin.py', '--password', 'x'))[0], 2)
        reports.save_user({'email': 'boss@example.test', 'role': 'org_admin', 'organization_id': 'A', 'active': True}, '本機管理員')
        self.assertEqual(self.run_cli(['boss@example.test'])[0], 1)
        self.assertEqual(reports.account('boss@example.test')['role'], 'org_admin')
        # 停用的平台管理員可被重新啟用（緊急復原）。
        with app.database_connection() as conn:
            conn.execute("UPDATE workspace_users SET active=0 WHERE email='ops@example.test'")
        self.assertEqual(self.run_cli(['ops@example.test', ''])[0], 0)
        self.assertEqual(reports.login_account('ops@example.test')['role'], 'platform_admin')


if __name__ == '__main__':
    unittest.main()

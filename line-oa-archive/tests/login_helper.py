"""測試用：直接在資料庫建立站內登入 session，取得對外網址請求所需的 Cookie 與 CSRF 標頭。"""
import secrets
import time

import app
import site_auth


def session_headers(email, host):
    raw = secrets.token_urlsafe(32)
    now = int(time.time())
    with app.database_connection() as conn:
        conn.execute('INSERT INTO site_sessions VALUES (?,?,?,?,?,?)',
                     (site_auth.digest(raw), email, now, now, now + 3600, 3600))
    return {'Host': host, 'X-Forwarded-Proto': 'https', 'Origin': 'https://' + host,
            'Cookie': f'{site_auth.COOKIE_REMOTE}={raw}', 'X-CSRF-Token': site_auth.csrf(raw)}

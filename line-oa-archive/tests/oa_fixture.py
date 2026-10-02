"""測試用：建立組織與一個以假憑證加密登記的 LINE OA；所有營運資料都屬於某個 OA。"""
import app
import channels

CHANNEL = 'f' * 32
BOT = 'U' + 'b' * 32
TOKEN = 'fake-token'
SECRET = '0' * 32


def register_oa(org_id='A', org_name=None, channel_id=CHANNEL, bot=BOT, token=TOKEN, secret=SECRET, name='Test OA', **org_flags):
    """建立（或沿用）組織並登記 OA，回傳 channel_id。"""
    crypto = channels.cipher()
    flags = {'reports_enabled': 1, 'messaging_enabled': 1, 'weather_enabled': 0, 'weather_image_path': '', **org_flags}
    with app.database_connection() as conn:
        conn.execute('INSERT OR IGNORE INTO organizations(org_id,name,reports_enabled,messaging_enabled,weather_enabled,weather_image_path) VALUES (?,?,?,?,?,?)',
                     (org_id, org_name or org_id, flags['reports_enabled'], flags['messaging_enabled'], flags['weather_enabled'], flags['weather_image_path']))
        conn.execute('''INSERT INTO line_channels(channel_id,org_id,name,bot_user_id,token_cipher,secret_cipher,active)
                        VALUES (?,?,?,?,?,?,1)''',
                     (channel_id, org_id, name, bot, crypto.encrypt(token.encode()).decode(), crypto.encrypt(secret.encode()).decode()))
    return channel_id


def use_oa(testcase, channel_id=CHANNEL):
    """在測試主執行緒切換到指定 OA，測試結束後恢復。"""
    token = channels._current.set(channel_id)
    testcase.addCleanup(channels._current.reset, token)


def add_account(email, role='org_admin', org_id='A', display_name=''):
    """建立具組織成員資格的後台帳號（測試直接寫入，不經權限檢查）。"""
    import reports
    reports.save_user({'email': email, 'role': role, 'organization_id': org_id, 'display_name': display_name, 'active': True}, '本機管理員')

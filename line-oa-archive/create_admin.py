"""一次性指令：建立平台管理員，或為平台管理員產生重設密碼連結（緊急復原）。

用於沒有桌面控制台的主機（權限規格第 9 節）。不接受任何命令列參數（也就不接受密碼），
不寫入設定檔；只在執行當下印出 30 分鐘有效的一次性設定連結，密碼由本人透過連結設定。
"""
import os
import sys

from control_runtime import load_settings

ACTOR = 'create_admin.py'


def main():
    if len(sys.argv) > 1:
        print('用法：python create_admin.py（不接受參數；Email 與顯示名稱會互動詢問）', file=sys.stderr)
        return 2
    load_settings()
    # app 在匯入時讀取 DATABASE_PATH，需在載入設定之後匯入。
    import app
    import reports
    import site_auth
    app.initialize_database()
    email = input('平台管理員 Email：').strip().lower()
    existing = next((u for u in reports.users() if u['email'] == email), None)
    if existing and existing['role'] != 'platform_admin':
        print('此 Email 已是組織帳號，平台管理員請使用另一個 Email。', file=sys.stderr)
        return 1
    if existing and existing['active']:
        if input('此平台管理員已存在，要產生重設密碼連結嗎？(y/N)：').strip().lower() != 'y':
            print('未變更。')
            return 0
        name = ''
    else:
        name = input('顯示名稱（選填）：').strip()
    try:
        email = reports.create_platform_admin(email, name, ACTOR)
        raw = site_auth.issue_activation(email, ACTOR)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    host = os.environ.get('ADMIN_PUBLIC_HOST', '').strip().lower()
    print('請把下方一次性連結交給本人設定密碼（30 分鐘內有效，只顯示這一次）：')
    if host:
        print(f'  https://{host}/login#setup={raw}')
    print(f'  本機：http://127.0.0.1:18475/login#setup={raw}（LINE 服務需在執行中）')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print('\n已取消。', file=sys.stderr)
        raise SystemExit(1)

"""Local-only login mode cutover. Never accepts or prints passwords or session tokens."""
import argparse
import os
from pathlib import Path
import re

from control_runtime import load_settings


def configure(mode=None):
    load_settings()
    import app
    with app.database_connection() as conn:
        ready = conn.execute("SELECT COUNT(*) FROM site_credentials c JOIN workspace_users u ON u.email=c.email WHERE u.active=1 AND u.role='administrator'").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM send_jobs WHERE status IN ('queued','running')").fetchone()[0]
    current = os.environ.get('ADMIN_AUTH_MODE','cloudflare')
    if mode is None:
        return {'mode':current,'administrators_with_password':ready,'active_send_jobs':active}
    if active:
        raise ValueError('仍有發送中的工作，請等待完成後再切換。')
    if mode == 'password':
        if not ready:
            raise ValueError('請先讓至少一位啟用中的平台管理員完成網站密碼設定。')
        if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',os.environ.get('ADMIN_PUBLIC_HOST','')):
            raise ValueError('請先設定有效的 ADMIN_PUBLIC_HOST。')
    elif mode == 'cloudflare':
        from remote_auth import RemoteAccess
        if not RemoteAccess().enabled:
            raise ValueError('Cloudflare Access 設定不完整，無法切回。')
    else:
        raise ValueError('登入模式不正確。')
    file=Path(__file__).parent/'.env'
    text=file.read_text(encoding='utf-8-sig')
    # Replace only the mode key, preserving every other setting and comment.
    lines=[line for line in text.splitlines() if not re.match(r'^\s*ADMIN_AUTH_MODE\s*=',line)]
    file.write_text('\n'.join([*lines,'ADMIN_AUTH_MODE='+mode,'']),encoding='utf-8')
    return {'mode':mode,'restart_required':True,'cloudflare_policy_unchanged':True}


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['cloudflare','password'])
    args=parser.parse_args()
    try:print(json.dumps(configure(args.mode),ensure_ascii=False))
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')

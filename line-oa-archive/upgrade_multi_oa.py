"""One-time, offline schema upgrade. Startup never runs historical migrations.

Run after stopping the LINE service: python upgrade_multi_oa.py --apply
All existing rows and login credentials are retained in a single atomic transaction.
OA ownership is chosen separately in the authenticated import screen.
"""
from contextlib import closing
import argparse
from pathlib import Path
import socket
import sqlite3

from channels import SCOPED_TABLES


def statements(schema):
    pending = ''
    for line in schema.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ''
    if pending.strip() and not pending.lstrip().startswith('--'):
        raise ValueError('Incomplete schema statement')


def upgrade(database, schema, apply=False):
    if not database.exists():
        raise ValueError('資料庫不存在；全新安裝請直接啟動服務。')
    with closing(sqlite3.connect(database)) as conn, conn:
        columns = {t: [r[1] for r in conn.execute(f'PRAGMA table_info({t})')] for t in SCOPED_TABLES}
        if all('channel_id' in cols for cols in columns.values()):
            return {'status': 'already_current'}
        if any(not cols or 'channel_id' in cols for cols in columns.values()):
            raise ValueError('不是支援的上一版 schema；未變更任何資料。')
        counts = {t: conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in SCOPED_TABLES}
        if not apply:
            return {'status': 'ready', 'rows_preserved': counts}
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute('PRAGMA legacy_alter_table=ON')
        conn.execute('BEGIN EXCLUSIVE')
        try:
            for t in SCOPED_TABLES:
                conn.execute(f'ALTER TABLE {t} RENAME TO upgrade_previous_{t}')
            for sql in statements(schema):
                conn.execute(sql)
            for t in SCOPED_TABLES:
                names = ','.join('"' + c + '"' for c in columns[t])
                conn.execute(f'INSERT INTO {t} ({names}) SELECT {names} FROM upgrade_previous_{t}')
                if conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] != counts[t]:
                    raise ValueError('資料筆數不一致；已取消升級。')
            for t in reversed(SCOPED_TABLES):
                conn.execute(f'DROP TABLE upgrade_previous_{t}')
            # Existing index names were attached to the old tables until they were dropped.
            for sql in statements(schema):
                conn.execute(sql)
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('完整性檢查未通過；已取消升級。')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'status': 'upgraded', 'rows_preserved': counts}


if __name__ == '__main__':
    import json
    from control_runtime import load_settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    load_settings()
    import app
    if args.apply:
        for port in (18474, 18475):
            with socket.socket() as sock:
                sock.settimeout(1)
                if sock.connect_ex(('127.0.0.1', port)) == 0:
                    raise SystemExit('請先從控制台停止 LINE 服務；不需停止 Cloudflare Tunnel。')
    print(json.dumps(upgrade(app.DATABASE_PATH, (app.BASE_DIR/'schema.sql').read_text(encoding='utf-8'), args.apply), ensure_ascii=False))

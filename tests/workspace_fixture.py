"""Isolated browser fixture. Never uses production credentials, database, or LINE APIs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import struct
import zlib

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'line-oa-archive'))
parser = argparse.ArgumentParser()
parser.add_argument('state_file', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='line-ui-fixture-') as temp:
    root = Path(temp)
    assert root.resolve().parent == Path(tempfile.gettempdir()).resolve()
    base = root / 'line-oa-archive'
    base.mkdir()
    (base / 'instance').mkdir()
    shutil.copyfile(REPO / 'index.html', root / 'index.html')
    shutil.copyfile(REPO / 'line-oa-archive/schema.sql', base / 'schema.sql')
    shutil.copytree(REPO / 'line-oa-archive/web', base / 'web')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    # A deterministic synthetic chart-like PNG; no production report or personal data.
    pixels = bytearray()
    for y in range(240):
        pixels.append(0)
        for x in range(480):
            color = (237, 245, 245)
            if 25 < x < 455 and 25 < y < 65: color = (42, 77, 88)
            if 35 < x < 445 and 200-(x//40)*9 < y < 210 and x % 40 < 28: color = (86, 157, 160)
            pixels.extend(color)
    image = base / 'sample.png'
    image.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',480,240,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(pixels)) + chunk(b'IEND',b''))
    for key in list(os.environ):
        if key.startswith(('LINE_', 'CF_ACCESS_', 'ADMIN_')):
            os.environ.pop(key)
    os.environ.update(WEATHER_IMAGE_PATH=str(image), LINE_CHANNEL_ACCESS_TOKEN='fixture-only', ADMIN_ALLOWED_EMAILS='admin@example.test')
    import app
    import admin_server
    import reports
    import send_image
    import control_runtime
    control_runtime.ROOT = base
    app.BASE_DIR = base
    app.IMAGE_DIR = base / 'published-images'
    app.DATABASE_PATH = base / 'test.db'
    send_image.ROOT = base
    app.initialize_database()
    with app.database_connection() as conn:
        for i in range(24):
            conn.execute("INSERT INTO recipients(recipient_id,kind,display_name,company,department,weather_subscribed) VALUES (?,?,?,?,?,?)",
                         (('U' if i % 3 else 'C') + format(i+1,'032x'), 'user' if i % 3 else 'group',
                          ('同事 ' if i % 3 else '營運群組 ') + str(i+1), '示範公司' if i < 20 else '第二公司', '營運部' if i % 2 else '業務部', int(i % 4 == 0)))
    reports.bootstrap_users({'admin@example.test'})
    reports.save_user({'email':'employee@example.test','display_name':'測試員工','role':'employee','company':'示範公司','department':'營運部','active':True},'admin@example.test')
    reports.save_user({'email':'company-admin@example.test','display_name':'公司管理員','role':'company_admin','company':'示範公司','active':True},'admin@example.test')
    # Legacy company key used by the report fixture, independent of its display name.
    with app.database_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations(org_id,name) VALUES ('第二公司','第二公司')")
    reports.save_membership({'email':'company-admin@example.test','org_id':'第二公司','role':'sender','active':True},'admin@example.test')
    for title, company, scope in [('每日營運數據','示範公司','department'),('公司公告','示範公司','company'),('其他公司報告','第二公司','company')]:
        reports.save({'title':title,'source_path':str(image),'category':'company','company':company,'department':'營運部','scope':scope},'admin@example.test')
    reports.save_user({'email':'sender@example.test','display_name':'專案發送人員','role':'sender','company':'示範公司','active':True},'admin@example.test')
    scope_id=reports.save_dispatch_scope({'company':'第二公司','name':'營運部','kind':'department','department':'營運部','active':True},'admin@example.test')['scope_id']
    reports.save_grant({'email':'company-admin@example.test','company':'第二公司','scope_ids':[scope_id],'report_ids':[r['report_id'] for r in reports.sources() if r['company']=='第二公司'],'messaging':True,'reports':True,'weather':False},'admin@example.test')
    class FixtureHandler(admin_server.AdminHandler):
        def authorized(self, require_token=True):
            ok = super().authorized(require_token)
            if ok and self.headers.get('X-Fixture-Role') in {'employee','company_admin','sender'}:
                from urllib.parse import unquote
                self.user = reports.login_account({'employee':'employee@example.test','company_admin':'company-admin@example.test','sender':'sender@example.test'}[self.headers.get('X-Fixture-Role')],unquote(self.headers.get('X-Workspace-Organization','')) or None)
                if not self.user:
                    self.respond(403,{'error':'一般收件者不需後台登入。'})
                    return False
                self.identity = self.user['email']
            return ok
    def forbidden_send(*args, **kwargs):
        raise AssertionError('Real LINE API is forbidden in the browser fixture')
    admin_server.send_push = forbidden_send
    admin_server.verify_public_image = forbidden_send
    admin_server.line_api.request = forbidden_send
    server = admin_server.AdminServer(0)
    server.RequestHandlerClass = FixtureHandler
    server.start()
    args.state_file.write_text(json.dumps({'port':server.server_port,'token':server.token,'sample_image':str(image)}),encoding='utf-8')
    try:
        while not args.state_file.with_suffix('.stop').exists():
            time.sleep(.2)
    finally:
        server.close()

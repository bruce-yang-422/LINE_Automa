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
parser.add_argument('--multi-oa', action='store_true')
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
        if key.startswith(('LINE_', 'ADMIN_', 'WEATHER_')):
            os.environ.pop(key)
    os.environ['PUBLIC_BASE_URL'] = 'https://reports.example.test'
    import hashlib
    import app
    import admin_server
    import channels
    import reports
    import send_image
    import control_runtime
    control_runtime.ROOT = base
    app.BASE_DIR = base
    app.IMAGE_DIR = base / 'published-images'
    app.DATABASE_PATH = base / 'test.db'
    send_image.ROOT = base
    app.initialize_database()
    # LINE API is never called; only the bot identity lookup used when registering an OA is answered.
    def fixture_line(path, payload=None, *, token=None):
        if path == 'info' and token:
            return {'userId':'U'+hashlib.md5(token.encode()).hexdigest(),'displayName':'OA '+token,'basicId':'@fixture'}
        raise AssertionError('Only bot identity lookup is allowed in this fixture')
    admin_server.line_api.request = fixture_line
    reports.bootstrap_users({'admin@example.test'})
    owner = reports.account('admin@example.test')
    with app.database_connection() as conn:
        # Organization keys used by the fixture, independent of their display names.
        conn.execute("INSERT OR IGNORE INTO organizations(org_id,name) VALUES ('示範公司','示範公司')")
        conn.execute("INSERT OR IGNORE INTO organizations(org_id,name) VALUES ('第二公司','第二公司')")
    # Every organization works in its own OA; contacts belong to that OA.
    first = channels.save({'workspace_id':'o:示範公司','secret':'a'*32,'access_token':'first','name':'總公司通知 OA'}, owner)
    other = channels.save({'workspace_id':'o:第二公司','secret':'d'*32,'access_token':'other','name':'第二公司 OA'}, owner)
    oa = {'示範公司': first['channel_id'], '第二公司': other['channel_id']}
    with app.database_connection() as conn:
        for i in range(24):
            organization_id = '示範公司' if i < 20 else '第二公司'
            conn.execute("INSERT INTO recipients(channel_id,recipient_id,kind,display_name,organization_id,department) VALUES (?,?,?,?,?,?)",
                         (oa[organization_id], ('U' if i % 3 else 'C') + format(i+1,'032x'), 'user' if i % 3 else 'group',
                          ('同事 ' if i % 3 else '營運群組 ') + str(i+1), organization_id, '營運部' if i % 2 else '業務部'))
    reports.save_user({'email':'company-admin@example.test','display_name':'公司管理員','role':'org_admin','organization_id':'示範公司','active':True},'admin@example.test')
    reports.save_membership({'email':'company-admin@example.test','org_id':'第二公司','role':'operator','active':True},'admin@example.test')
    reports.save_user({'email':'sender@example.test','display_name':'專案發送人員','role':'operator','organization_id':'示範公司','active':True},'admin@example.test')
    reports.save_user({'email':'collaborator@example.test','display_name':'協作人員','role':'collaborator','organization_id':'示範公司','active':True},'admin@example.test')
    with app.database_connection() as conn:
        conn.execute("UPDATE organizations SET duty_enabled=1 WHERE org_id='示範公司'")
        conn.execute("UPDATE organizations SET forms_enabled=1 WHERE org_id='示範公司'")
        conn.execute("INSERT INTO organizations(org_id,name,duty_enabled) VALUES ('無OA組織','無OA組織',1)")
    reports.save_membership({'email':'company-admin@example.test','org_id':'無OA組織','role':'org_admin','active':True},'admin@example.test')
    sys.path.insert(0, str(REPO / 'line-oa-archive/tests'))
    import duty_fixture
    duty_fixture.seed(reports.account('company-admin@example.test'))
    import duty_automation
    duty_automation.send_push = lambda *args, **kwargs: 'fixture-duty-request'
    class FixtureHandler(admin_server.AdminHandler):
        def authorized(self, require_token=True):
            ok = super().authorized(require_token)
            if ok and self.headers.get('X-Fixture-Role') in {'contact','org_admin','operator','collaborator'}:
                from urllib.parse import unquote
                self.user = reports.login_account({'contact':'contact@example.test','org_admin':'company-admin@example.test','operator':'sender@example.test','collaborator':'collaborator@example.test'}[self.headers.get('X-Fixture-Role')],unquote(self.headers.get('X-Workspace-Organization','')) or None)
                if not self.user:
                    self.respond(403,{'error':'聯絡對象沒有後台帳號。'})
                    return False
                self.identity = self.user['email']
            return ok
    def forbidden_send(*args, **kwargs):
        raise AssertionError('Real LINE API is forbidden in the browser fixture')
    admin_server.send_push = forbidden_send
    admin_server.verify_public_image = forbidden_send
    if args.multi_oa:
        second=channels.save({'workspace_id':'o:示範公司','secret':'b'*32,'access_token':'second','name':'門市服務 OA'},owner)
        with channels.use(second['channel_id']):
            app.save_events([{'type':'message','source':{'type':'user','userId':'U'+'2'*32},'message':{'id':'store-only','type':'text','text':'hello'}}])
            with app.database_connection() as conn:
                conn.execute("UPDATE recipients SET display_name='門市客戶' WHERE channel_id=current_channel()")
    server = admin_server.AdminServer(0)
    server.RequestHandlerClass = FixtureHandler
    server.start()
    args.state_file.write_text(json.dumps({'port':server.server_port,'token':server.token,'sample_image':str(image)}),encoding='utf-8')
    try:
        while not args.state_file.with_suffix('.stop').exists():
            time.sleep(.2)
    finally:
        server.close()

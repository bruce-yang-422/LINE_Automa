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
parser.add_argument('--public-forms', action='store_true')
parser.add_argument('--form-pages', action='store_true')
parser.add_argument('--form-sends', action='store_true')
parser.add_argument('--form-responses', action='store_true')
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
        if args.form_responses and path.startswith(('profile/','group/')):
            # Existing chat initialization refreshes profiles in the background.
            raise ValueError('假 LINE API：本測試不更新聯絡對象個人資料。')
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
                self.principal = self.user['email']
                self.principal_role = self.user['role']
            return ok
    def forbidden_send(*args, **kwargs):
        raise AssertionError('Real LINE API is forbidden in the browser fixture')
    admin_server.send_push = forbidden_send
    if args.form_sends:
        attempts={}
        def fake_form_send(token,recipient,*args,**kwargs):
            attempts[recipient]=attempts.get(recipient,0)+1
            if recipient=='U'+format(2,'032x') and attempts[recipient]==1:raise ValueError('測試 API 明確拒絕')
            if recipient=='U'+format(3,'032x'):raise ValueError('測試 API 結果不明')
            return 'fake-form-request'
        admin_server.send_push=fake_form_send
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
    public_server = None
    public_info = {}
    if args.public_forms or args.form_responses:
        import forms
        import public_forms
        import threading
        from http.server import ThreadingHTTPServer
        questions = [forms.question('section','聯絡資訊','section'),forms.question('phone','手機',required=True),forms.question('free','不驗證電話'),forms.question('email','Email'),forms.question('notes','意見','paragraph'),forms.question('single','單選','single_choice',['選項 A','選項 B']),forms.question('multi','多選','multiple_choice',['選項 A','選項 B']),forms.question('dropdown','下拉','dropdown',['選項 A','選項 B']),forms.question('number','數量','number'),forms.question('date','日期','date'),forms.question('time','時間','time'),forms.question('rating','評分','rating'),forms.question('attachment','附件','attachment')]
        questions[1]['validation']={'enabled':True,'format':'phone','phone_mode':'tw_mobile'}
        questions[3]['validation']={'enabled':True,'format':'email'}
        for index in (5,6):questions[index]['allow_other']=True
        questions[6]['validation']={'enabled':True,'count_exact':2}
        questions[8]['validation']={'enabled':True,'integer':True,'min':1,'max':3}
        questions[9]['validation']={'enabled':True,'date_min':'2026-01-01','date_max':'2026-12-31'}
        questions[11]['rating']={'min':1,'max':7,'lower_label':'不滿意','upper_label':'滿意'}
        questions[12]['attachment']={'extensions':['png','pdf'],'max_files':1,'max_file_bytes':1048576,'max_total_bytes':1048576}
        if args.form_pages:
            section=forms.question('page-two','活動意見','section');section['page_break']=True
            questions.insert(4,section)
        with channels.use(oa['示範公司']):
            user=reports.account('company-admin@example.test')
            form=forms.save(user,{'name':'公開問卷驗收','description':'測試問卷說明，請提供你的意見。','submission_message':'感謝你的回覆！'})['form']
            form=forms.save_design(user,{'form_id':form['form_id'],'questions':questions,'expected_updated_at':form['updated_at']})['form']
            form=forms.transition(user,{'form_id':form['form_id'],'status':'collecting'})['form']
            invitation=public_forms.ensure_link(user,form['form_id'])
        if args.form_responses:
            import form_attachments
            response_ids=[]
            for n in range(3):
                page=public_forms.view(form['form_id'],invitation['token'])
                meta=form_attachments.upload(form['form_id'],page['draft_key'],'attachment','中文照片.PNG' if n==0 else '文件.pdf',image.read_bytes() if n==0 else b'%PDF-1.7\nfixture')
                answers={'phone':'0912 345-678','free':'自述 '+str(n+1),'notes':'中文,逗號\n第二行 "引號"' if n==0 else '=SUM(1,2)','single':{'option_id':'single-0','other':''},'multi':{'option_ids':['multi-0','__other__'],'other':'多選補充'},'attachment':[meta['attachment_id']]}
                code,result=public_forms.submit(form['form_id'],invitation['token'],{'answers':answers,'submission_key':page['submission_key'],'draft_key':page['draft_key'],'expected_updated_at':form['updated_at'],'expected_response_updated_at':''})
                assert code==200,result
                with app.database_connection() as conn:
                    identifier=conn.execute('SELECT response_id FROM form_submissions WHERE edit_token=?',(result['edit_url'].split('&edit=')[1],)).fetchone()[0]
                    conn.execute('UPDATE form_submissions SET first_submitted_at=?,updated_at=? WHERE response_id=?',('2026-10-08T0'+str(n+1)+':00:00+00:00','2026-10-09T00:00:00+00:00' if n==0 else '2026-10-08T06:00:00+00:00',identifier))
                    response_ids.append(identifier)
            # The detail and export must still show the saved labels and deleted question.
            changed=[q for q in questions if q['id']!='notes']
            next(q for q in changed if q['id']=='single')['title']='改名後的單選題'
            next(q for q in changed if q['id']=='single')['options'][0]['label']='改名後的選項'
            with app.database_connection() as conn:conn.execute('UPDATE forms SET questions_json=? WHERE form_id=?',(json.dumps(changed,ensure_ascii=False),form['form_id']))
            public_info['response_ids']=response_ids
        public_server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        threading.Thread(target=public_server.serve_forever,daemon=True).start()
        public_info.update({'public_port':public_server.server_port,'form_id':form['form_id'],'invitation_token':invitation['token']})
    args.state_file.write_text(json.dumps({'port':server.server_port,'token':server.token,'sample_image':str(image),**public_info}),encoding='utf-8')
    try:
        while not args.state_file.with_suffix('.stop').exists():
            time.sleep(.2)
    finally:
        if public_server:
            public_server.shutdown()
            public_server.server_close()
        server.close()

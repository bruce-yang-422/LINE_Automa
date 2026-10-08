"""Phase three A2/A3/A4/A6/A7/A11/A12: isolated public HTTP and persistence."""
import copy
import json
import http.client
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import app
import channels
import forms
import public_forms as public
import test_forms_permissions as permissions
from test_roles_and_permissions import CONTACT_USER, ORG_A, COLLABORATOR
from test_forms_validation import VECTORS
import limits
import reports

class PublicFormTests(unittest.TestCase):
    setUp=permissions.FormsPermissionsTests.setUp
    setup_roles_environment=permissions.FormsPermissionsTests.setup_roles_environment
    prepare=permissions.FormsPermissionsTests.prepare
    create=permissions.FormsPermissionsTests.create

    def ready(self,questions=None):
        self.prepare();row=self.create()
        with channels.use('primary'):
            if questions is not None:row=forms.save_design(self.user,{'form_id':row['form_id'],'questions':questions,'expected_updated_at':row['updated_at']})['form']
            row=forms.transition(self.user,{'form_id':row['form_id'],'status':'collecting'})['form']
            invitation=public.ensure_link(self.user,row['form_id'])
        self.row=row;self.link=invitation
        return row,invitation

    def payload(self,answers):
        return {'answers':answers,'expected_updated_at':self.row['updated_at'],'expected_response_updated_at':'','submission_key':public.secrets.token_urlsafe(32)}

    def public_server(self):
        class Quiet(app.Handler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return server

    def request(self,server,method,path,payload=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        body=json.dumps(payload).encode() if payload is not None else None
        conn.request(method,path,body,headers or ({'Content-Type':'application/json'} if body is not None else {}))
        response=conn.getresponse();result=(response.status,dict(response.getheaders()),response.read());conn.close();return result

    def url(self):return '/forms/'+self.row['form_id']+'?token='+self.link['token']
    def submit_url(self):return '/forms/'+self.row['form_id']+'/submit?token='+self.link['token']

    def test_shared_link_open_creates_no_response_and_exposes_no_identity(self):
        row,invite=self.ready()
        with channels.use('primary'):
            again=public.ensure_link(self.user,row['form_id'])
            self.assertEqual(again,invite)
            with app.database_connection() as conn:
                second='U'+'2'*32
                conn.execute("INSERT INTO recipients(channel_id,recipient_id,kind,organization_id) VALUES ('primary',?,'user',?)",(second,ORG_A))
            other=public.ensure_link(self.user,row['form_id'])
            self.assertEqual(other['token'],invite['token'])
        server=self.public_server();status,headers,body=self.request(server,'GET',self.url())
        self.assertEqual(status,200);self.assertNotIn(CONTACT_USER.encode(),body);self.assertNotIn(invite['token'].encode(),body)
        self.assertNotIn(b'org-a',body);self.assertIn("default-src 'none'",headers['Content-Security-Policy']);self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
        self.assertEqual(headers['Referrer-Policy'],'no-referrer');self.assertEqual(headers['Cache-Control'],'no-store')
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM form_submissions').fetchone()[0],0)
        self.assertFalse(public.view(row['form_id'],invite['token'])['submitted'])

    def test_submit_update_duplicate_and_snapshot_preserve_phone(self):
        q=forms.question('phone','電話',required=True);q['validation']={'enabled':True,'format':'phone','phone_mode':'tw_mobile'}
        self.ready([q]);payload=self.payload({'phone':'0912 345-678'})
        code,result=public.submit(self.row['form_id'],self.link['token'],payload);self.assertEqual(code,200)
        self.assertEqual(public.submit(self.row['form_id'],self.link['token'],payload),(code,result))
        payload['expected_response_updated_at']=result['updated_at'];payload['answers']['phone']='0987654321'
        edit=result['edit_url'].split('&edit=')[1]
        _,updated=public.submit(self.row['form_id'],self.link['token'],payload,edit)
        self.assertEqual(updated['first_submitted_at'],result['first_submitted_at']);self.assertNotEqual(updated['updated_at'],result['updated_at'])
        data=public.view(self.row['form_id'],self.link['token'],edit);self.assertEqual(data['answers']['phone'],'0987654321')
        self.assertEqual(public.view(self.row['form_id'],self.link['token'])['answers'],{})
        with app.database_connection() as conn:
            rows=conn.execute('SELECT * FROM form_submissions').fetchall();self.assertEqual(len(rows),1)
            self.assertEqual(json.loads(rows[0][5]),[q])
            self.assertEqual(conn.execute('SELECT phone FROM recipients WHERE recipient_id=?',(CONTACT_USER,)).fetchone()[0],'')

    def test_shared_vectors_server_rejects_and_preserves_original_answers(self):
        self.ready()
        for vector in VECTORS:
            with self.subTest(name=vector['name']):
                # Definition replacement isolates each test vector, including empty/attachment-only cases.
                with app.database_connection() as conn:
                    conn.execute('DELETE FROM form_submissions')
                    conn.execute('UPDATE forms SET questions_json=? WHERE form_id=?',(json.dumps(vector['questions']),self.row['form_id']))
                original=copy.deepcopy(vector['answers'])
                code,result=public.submit(self.row['form_id'],self.link['token'],self.payload(vector['answers']))
                attachment_input=any(q['type']=='attachment' and vector['answers'].get(q['id']) for q in vector['questions']) if isinstance(vector['answers'],dict) else False
                rejected=bool(vector['expected'] or attachment_input)
                self.assertEqual(code,422 if rejected else 200);self.assertEqual(vector['answers'],original)
                with app.database_connection() as conn:
                    saved=conn.execute('SELECT answers_json FROM form_submissions').fetchone()
                    if rejected:self.assertIsNone(saved)
                    else:self.assertEqual(json.loads(saved[0]),original)

    def test_stopped_draft_expired_deleted_disabled_reject_read_and_submit(self):
        self.ready();server=self.public_server()
        for status,deadline,text in [('draft','','尚未發布'),('stopped','','停止收件'),('collecting','2000-01-01T00:00:00+00:00','已截止')]:
            with app.database_connection() as conn:conn.execute('UPDATE forms SET status=?,deadline_at=?',(status,deadline))
            code,_,body=self.request(server,'GET',self.url());self.assertEqual(code,403);self.assertIn(text,body.decode())
            self.assertEqual(self.request(server,'POST',self.submit_url(),self.payload({}))[0],403)
        with app.database_connection() as conn:
            conn.execute("UPDATE forms SET status='collecting',deadline_at=''")
            conn.execute('UPDATE organizations SET forms_enabled=0 WHERE org_id=?',(ORG_A,))
        self.assertEqual(self.request(server,'GET',self.url())[0],403)
        with app.database_connection() as conn:conn.execute('UPDATE organizations SET forms_enabled=1 WHERE org_id=?',(ORG_A,))
        with channels.use('primary'):forms.delete(self.user,{'form_id':self.row['form_id'],'confirm_counts':{'notifications':0,'responses':0}})
        code,_,body=self.request(server,'GET',self.url());self.assertEqual(code,404);self.assertIn('已刪除',body.decode())
        self.assertEqual(self.request(server,'POST',self.submit_url(),self.payload({}))[0],404)

    def test_invalid_token_cross_form_and_spoofed_identity_rejected(self):
        self.ready([forms.question('q','文字')]);server=self.public_server()
        for path in [self.url().replace(self.link['token'],'bad'),self.url().replace(self.row['form_id'],'0'*32),self.url()+'&token='+self.link['token']]:
            self.assertEqual(self.request(server,'GET',path)[0],404)
        payload={**self.payload({'q':'答案'}),'recipient_id':'another','channel_id':'another'}
        self.assertEqual(self.request(server,'POST',self.submit_url(),payload)[0],400)
        self.assertEqual(self.request(server,'POST',self.submit_url(),self.payload({'q':'答案'}),{'Content-Type':'application/json','Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request(server,'POST',self.submit_url(),self.payload({}),{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request(server,'GET','/forms-assets/../app.py')[0],404)

    def test_schema_changes_keep_snapshot_new_required_does_not_remove_response(self):
        q=forms.question('q','舊名稱','single_choice',['舊選項']);self.ready([q])
        _,saved=public.submit(self.row['form_id'],self.link['token'],self.payload({'q':'q-0'}))
        with channels.use('primary'):
            changed=copy.deepcopy(q);changed['options']=[{'id':'new','label':'新選項'}]
            forms.save_design(self.user,{'form_id':self.row['form_id'],'questions':[changed,forms.question('new','新增必填',required=True)],'expected_updated_at':self.row['updated_at'],'confirm_response_impact':True})
        data=public.view(self.row['form_id'],self.link['token'],saved['edit_url'].split('&edit=')[1]);self.assertTrue(data['submitted']);self.assertTrue(data['definition_changed']);self.assertNotIn('q',data['answers'])
        with app.database_connection() as conn:self.assertEqual(json.loads(conn.execute('SELECT questions_snapshot_json FROM form_submissions').fetchone()[0]),[q])
        with self.assertRaises(public.PublicError) as cm:public.submit(self.row['form_id'],self.link['token'],self.payload({'q':'q-0'}))
        self.assertEqual(cm.exception.code,409)

    def test_concurrent_duplicate_keeps_one_response_and_stale_edits_reject(self):
        self.ready([forms.question('q','文字')]);payload=self.payload({'q':'第一次'})
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:public.submit(self.row['form_id'],self.link['token'],payload),range(4)))
        self.assertTrue(all(r==results[0] for r in results))
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM form_submissions').fetchone()[0],1)
        payload['answers']['q']='覆蓋'
        with self.assertRaises(public.PublicError) as cm:public.submit(self.row['form_id'],self.link['token'],payload)
        self.assertEqual(cm.exception.code,409)

    def test_delete_response_cleanup_and_repeated_initialization(self):
        self.ready([forms.question('q','文字')]);public.submit(self.row['form_id'],self.link['token'],self.payload({'q':'已填'}))
        app.initialize_database()
        with channels.use('primary'):
            self.assertEqual(forms.detail(self.user,self.row['form_id'])['form']['counts'],{'notifications':0,'responses':1})
            forms.delete(self.user,{'form_id':self.row['form_id'],'confirm_counts':{'notifications':0,'responses':1}})
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM form_notifications').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM form_submissions').fetchone()[0],0)

    def test_http_limits_assets_and_unavailable_database(self):
        self.ready([forms.question('q','文字')]);server=self.public_server()
        for asset in ('public-forms.js','forms-validation.js','public-forms.css'):
            code,headers,body=self.request(server,'GET','/forms-assets/'+asset)
            self.assertEqual(code,200);self.assertTrue(body);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        code,headers,body=self.request(server,'HEAD',self.url())
        self.assertEqual(code,200);self.assertFalse(body);self.assertGreater(int(headers['Content-Length']),0)
        with patch.object(limits,'FORM_ANSWERS_MAX_BYTES',1):
            self.assertEqual(self.request(server,'POST',self.submit_url(),self.payload({'q':'測試'}))[0],413)
        with patch.object(public,'lookup',side_effect=public.sqlite3.OperationalError('private database detail')):
            code,_,body=self.request(server,'POST',self.submit_url(),self.payload({'q':'測試'}))
            self.assertEqual(code,503);self.assertNotIn(b'private database detail',body)
        with channels.use('primary'):
            with self.assertRaises(PermissionError):public.ensure_link(reports.account(COLLABORATOR),self.row['form_id'])

    def test_contact_revocation_does_not_affect_share_link_or_history(self):
        self.ready([forms.question('q','文字')])
        public.submit(self.row['form_id'],self.link['token'],self.payload({'q':'歷史回覆'}))
        with app.database_connection() as conn:
            conn.execute('DELETE FROM recipients WHERE channel_id=? AND recipient_id=?',('primary',CONTACT_USER))
        self.assertEqual(public.view(self.row['form_id'],self.link['token'])['answers'],{})
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM form_submissions').fetchone()[0],1)

    def test_shared_link_independent_submissions_and_edit_isolation(self):
        self.ready([forms.question('q','文字')])
        first_page=public.view(self.row['form_id'],self.link['token'])
        second_page=public.view(self.row['form_id'],self.link['token'])
        self.assertNotEqual(first_page['submission_key'],second_page['submission_key'])
        one=self.payload({'q':'同樣答案'});one['submission_key']=first_page['submission_key']
        two=self.payload({'q':'同樣答案'});two['submission_key']=second_page['submission_key']
        _,a=public.submit(self.row['form_id'],self.link['token'],one)
        _,b=public.submit(self.row['form_id'],self.link['token'],two)
        self.assertNotEqual(a['edit_url'],b['edit_url'])
        self.assertEqual(public.view(self.row['form_id'],self.link['token'])['answers'],{})
        with self.assertRaises(public.PublicError):public.view(self.row['form_id'],self.link['token'],'bad')
        edit=a['edit_url'].split('&edit=')[1]
        one['answers']['q']='修改第一份';one['expected_response_updated_at']=a['updated_at']
        public.submit(self.row['form_id'],self.link['token'],one,edit)
        self.assertEqual(public.view(self.row['form_id'],self.link['token'],b['edit_url'].split('&edit=')[1])['answers'],{'q':'同樣答案'})
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM form_submissions').fetchone()[0],2)
            self.assertNotIn('recipient_id',{r[1] for r in conn.execute('PRAGMA table_info(form_submissions)')})

    def test_legacy_migration_preserves_answers_without_recipient_binding(self):
        self.ready([forms.question('q','文字')])
        old_token=public.secrets.token_urlsafe(32)
        with app.database_connection() as conn:
            conn.execute('CREATE TABLE form_invitations(invitation_id TEXT,form_id TEXT,channel_id TEXT,recipient_id TEXT,token TEXT,sent_at TEXT,last_reminded_at TEXT)')
            conn.execute('CREATE TABLE form_responses(invitation_id TEXT,answers_json TEXT,questions_snapshot_json TEXT,first_submitted_at TEXT,updated_at TEXT)')
            conn.execute('INSERT INTO form_invitations VALUES (?,?,?,?,?,?,?)',('old',self.row['form_id'],'primary',CONTACT_USER,old_token,'sent','reminded'))
            conn.execute('INSERT INTO form_responses VALUES (?,?,?,?,?)',('old','{"q":"0912345678"}',json.dumps(self.row['questions']),'first','last'))
        app.initialize_database();app.initialize_database()
        with app.database_connection() as conn:
            row=conn.execute('SELECT answers_json,first_submitted_at,updated_at FROM form_submissions').fetchone()
            self.assertEqual(row,('{"q":"0912345678"}','first','last'))
            self.assertEqual(conn.execute('SELECT count(*) FROM form_notifications').fetchone()[0],1)
            self.assertNotEqual(conn.execute('SELECT response_id FROM form_submissions').fetchone()[0],'old')
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='form_invitations'").fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='form_responses'").fetchone())
        with self.assertRaises(public.PublicError):public.view(self.row['form_id'],old_token)
        self.assertFalse(public.view(self.row['form_id'],self.link['token'])['submitted'])

if __name__=='__main__':unittest.main()

"""A7/A8/A12: snapshot reading, private files, safe CSV and authorization."""
import copy,csv,io,json,http.client,unittest
from unittest.mock import patch
from urllib.parse import urlencode,quote
from PIL import Image
import app,channels,forms,form_responses as responses,public_forms as public,form_attachments as files,reports
import test_public_forms as public_tests
import test_forms_permissions as permissions
from test_roles_and_permissions import ADMIN,ORG_ADMIN,SENDER,COLLABORATOR,ORG_A,CONTACT_USER
from login_helper import session_headers

class ResponseTests(unittest.TestCase):
    setUp=public_tests.PublicFormTests.setUp
    setup_roles_environment=public_tests.PublicFormTests.setup_roles_environment
    prepare=public_tests.PublicFormTests.prepare
    create=public_tests.PublicFormTests.create
    ready=public_tests.PublicFormTests.ready
    payload=public_tests.PublicFormTests.payload
    server=permissions.FormsPermissionsTests.server
    request=permissions.FormsPermissionsTests.request
    call=permissions.FormsPermissionsTests.call

    def submit(self,answers):
        code,result=public.submit(self.row['form_id'],self.link['token'],self.payload(answers));self.assertEqual(code,200)
        with app.database_connection() as conn:
            identifier=conn.execute('SELECT response_id FROM form_submissions WHERE edit_token=?',(result['edit_url'].split('&edit=')[1],)).fetchone()[0]
        return identifier

    def query(self,**kwargs):return {'form_id':self.row['form_id'],**kwargs}

    def binary(self,server,path,email=ORG_ADMIN,channel='primary',view_as=None):
        headers=session_headers(email,server.public_host);headers['X-Line-Channel']=channel
        if view_as:headers.update({'X-Workspace-View-As':view_as,'X-Workspace-Preview-Organization':quote(ORG_A)})
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);conn.request('GET',path,headers=headers);r=conn.getresponse();result=r.status,dict(r.getheaders()),r.read();conn.close();return result

    def test_snapshot_old_titles_options_deleted_questions_and_no_secrets(self):
        q=forms.question('choice','原題目','single_choice',['原選項']);q['allow_other']=True
        self.ready([q,forms.question('deleted','已刪除題目','paragraph')]);identifier=self.submit({'choice':'choice-0','deleted':'舊答案'})
        with app.database_connection() as conn:conn.execute('UPDATE forms SET questions_json=? WHERE form_id=?',(json.dumps([forms.question('choice','新題目','single_choice',['新選項'])]),self.row['form_id']))
        with channels.use('primary'):
            detail=responses.detail(self.user,self.row['form_id'],identifier)['response'];listing=responses.listing(self.user,self.query())
        self.assertEqual([(i['title'],i['text']) for i in detail['items']],[('原題目','原選項'),('已刪除題目','舊答案')])
        self.assertIn('原選項',listing['responses'][0]['summary'])
        serialized=json.dumps([detail,listing]);self.assertNotIn(self.link['token'],serialized)
        for key in ('edit_token','submission_key','recipient_id','draft_key'):self.assertNotIn(key,serialized)

    def test_csv_bom_chinese_quotes_lines_choices_phone_and_formula(self):
        phone=forms.question('phone','電話');phone['validation']={'enabled':False,'format':'phone'}
        choice=forms.question('choice','複選','multiple_choice',['中文,選項','引號"選項']);choice['allow_other']=True
        self.ready([forms.question('name','=危險欄名'),phone,choice,forms.question('notes','備註','paragraph')])
        identifier=self.submit({'name':' =HYPERLINK("bad")','phone':'0912 345-678','choice':{'option_ids':['choice-0','choice-1','__other__'],'other':'自己的選項'},'notes':'中文,逗號\n第二行 "引號"'})
        self.submit({'name':'@SUM(1)','phone':'+886 912 345678','choice':[],'notes':'\t=1'})
        with channels.use('primary'):data,name=responses.export(self.user,self.query())
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'));self.assertTrue(name.endswith('.csv'));rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(rows[0][3],"'=危險欄名 [name]")
        first=next(row for row in rows[1:] if row[0]==identifier)
        self.assertEqual(first[3],"' =HYPERLINK(\"bad\")");self.assertEqual(first[4],"'0912 345-678")
        self.assertEqual(first[5],'中文,選項、引號"選項、其他：自己的選項');self.assertEqual(first[6],'中文,逗號\n第二行 "引號"')
        second=next(row for row in rows[1:] if row[0]!=identifier);self.assertEqual(second[4],"'+886 912 345678");self.assertEqual(second[6],"'\t=1")
        self.assertNotIn(self.link['token'].encode(),data)
        with app.database_connection() as conn:
            for edit,key in conn.execute('SELECT edit_token,submission_key FROM form_submissions'):
                self.assertNotIn(edit.encode(),data);self.assertNotIn(key.encode(),data)
            self.assertEqual(conn.execute('SELECT phone FROM recipients WHERE recipient_id=?',(CONTACT_USER,)).fetchone()[0],'')
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action='forms.export'").fetchone()[0],1)

    def test_mixed_versions_csv_keeps_deleted_and_renamed_questions(self):
        self.ready([forms.question('same','原名稱'),forms.question('old','已刪題')]);self.submit({'same':'舊內容','old':'舊題答案'})
        with app.database_connection() as conn:conn.execute('UPDATE forms SET questions_json=? WHERE form_id=?',(json.dumps([forms.question('same','新名稱'),forms.question('new','新題')]),self.row['form_id']))
        self.submit({'same':'新內容','new':'新題答案'})
        with channels.use('primary'):data,_=responses.export(self.user,self.query())
        rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'))));self.assertEqual(rows[0][3:],["原名稱／新名稱 [same]","已刪題 [old]","新題 [new]"])
        self.assertEqual(rows[1][3:],['新內容','','新題答案']);self.assertEqual(rows[2][3:],['舊內容','舊題答案',''])
        with app.database_connection() as conn:conn.execute('UPDATE forms SET questions_json=? WHERE form_id=?',(json.dumps([forms.question('same','新名稱','paragraph')]),self.row['form_id']))
        self.submit({'same':'題型變更後'})
        with channels.use('primary'):data,_=responses.export(self.user,self.query())
        header=next(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(len(header),len(set(header)))
        self.assertEqual(sum('[same]' in label for label in header),2)

    def test_search_pagination_uses_self_reported_snapshot_answers(self):
        self.ready([forms.question('name','自述姓名'),forms.question('choice','選項','single_choice',['舊選項'])])
        for n in range(28):self.submit({'name':'搜尋測試 '+str(n),'choice':'choice-0'})
        with channels.use('primary'):
            first=responses.listing(self.user,self.query(query='舊選項'));second=responses.listing(self.user,self.query(page='2'))
            found=responses.listing(self.user,self.query(query='搜尋測試 27'))
        self.assertEqual(first['total'],28);self.assertEqual(len(first['responses']),25);self.assertEqual(len(second['responses']),3);self.assertEqual(found['total'],1)
        with channels.use('primary'),self.assertRaises(ValueError):responses.listing(self.user,self.query(page='bad'))

    def test_taipei_date_boundaries_first_vs_last_and_invalid_filters(self):
        self.ready([forms.question('q','內容')]);a=self.submit({'q':'甲'});b=self.submit({'q':'乙'})
        with app.database_connection() as conn:
            conn.execute("UPDATE form_submissions SET first_submitted_at='2026-10-07T16:00:00+00:00',updated_at='2026-10-09T00:00:00+00:00' WHERE response_id=?",(a,))
            conn.execute("UPDATE form_submissions SET first_submitted_at='2026-10-08T16:00:00+00:00',updated_at='2026-10-08T12:00:00+00:00' WHERE response_id=?",(b,))
        with channels.use('primary'):
            first=responses.listing(self.user,self.query(date_from='2026-10-08',date_to='2026-10-08'))
            last=responses.listing(self.user,self.query(time_field='updated',date_from='2026-10-08',date_to='2026-10-08'))
            data,_=responses.export(self.user,self.query(date_from='2026-10-08',date_to='2026-10-08'))
        self.assertEqual([r['response_id'] for r in first['responses']],[a]);self.assertEqual([r['response_id'] for r in last['responses']],[b]);self.assertEqual(len(list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))),2)
        for extra in ({'date_from':'2026-99-99'},{'date_from':'2026-10-09','date_to':'2026-10-08'},{'time_field':'email'}):
            with channels.use('primary'),self.assertRaises(ValueError):responses.listing(self.user,self.query(**extra))

    def test_http_roles_cross_oa_export_denial_and_platform_read_audit(self):
        self.ready([forms.question('q','內容')]);identifier=self.submit({'q':'答案'});server=self.server();query=urlencode(self.query())
        for email in (ORG_ADMIN,SENDER,COLLABORATOR):
            self.assertEqual(self.call(server,'/api/forms/responses?'+query,email)[0],200)
            self.assertEqual(self.call(server,'/api/forms/responses/detail?'+query+'&response_id='+identifier,email)[0],200)
        self.assertEqual(self.binary(server,'/api/forms/responses/export?'+query,COLLABORATOR)[0],403)
        self.assertEqual(self.binary(server,'/api/forms/responses/export?'+query,SENDER)[0],200)
        self.assertEqual(self.binary(server,'/api/forms/responses/export?'+query,ADMIN,view_as=ORG_ADMIN)[0],403)
        self.assertEqual(self.call(server,'/api/forms/responses?'+query,ADMIN,view_as=ORG_ADMIN,preview_org=ORG_A)[0],200)
        self.assertEqual(self.binary(server,'/api/forms/responses?'+query,channel='wrong')[0],403)
        self.assertEqual(self.call(server,'/api/forms/responses/detail?'+query+'&response_id='+('f'*32))[0],403)
        with app.database_connection() as conn:self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action='vendor.view'").fetchone()[0],1)
        with app.database_connection() as conn:conn.execute('UPDATE organizations SET forms_enabled=0 WHERE org_id=?',(ORG_A,))
        self.assertEqual(self.call(server,'/api/forms/responses?'+query)[0],403)

    def test_attachment_detail_thumbnail_view_download_and_foreign_form_denial(self):
        q=forms.question('file','附件','attachment');q['attachment']={'extensions':['png'],'max_files':1,'max_file_bytes':4096,'max_total_bytes':4096};self.ready([q])
        page=public.view(self.row['form_id'],self.link['token']);stream=io.BytesIO();Image.new('RGB',(40,20),'green').save(stream,format='PNG');raw=stream.getvalue()
        meta=files.upload(self.row['form_id'],page['draft_key'],'file','中文照片.PNG',raw)
        payload=self.payload({'file':[meta['attachment_id']]});payload.update(draft_key=page['draft_key'],submission_key=page['submission_key']);self.assertEqual(public.submit(self.row['form_id'],self.link['token'],payload)[0],200)
        with app.database_connection() as conn:identifier=conn.execute('SELECT response_id FROM form_submissions').fetchone()[0]
        with channels.use('primary'):
            detail=responses.detail(self.user,self.row['form_id'],identifier)['response'];data,_=responses.export(self.user,self.query());other=self.create('其他表單')
        self.assertEqual(detail['items'][0]['attachments'][0]['original_name'],'中文照片.PNG');self.assertIn('中文照片.PNG ['+meta['attachment_id']+']',data.decode('utf-8-sig'))
        server=self.server();url='/api/forms/attachment?'+urlencode({'form_id':self.row['form_id'],'attachment_id':meta['attachment_id']})
        for kind in ('thumb','view','download'):
            code,headers,body=self.binary(server,url+'&kind='+kind,COLLABORATOR);self.assertEqual(code,200)
            if kind=='thumb':self.assertEqual(headers['Content-Type'],'image/jpeg')
            else:self.assertEqual(body,raw)
        foreign=url.replace(self.row['form_id'],other['form_id']);self.assertEqual(self.binary(server,foreign)[0],403)

    def test_deleted_form_revoked_member_and_empty_export(self):
        self.ready([forms.question('q','內容')])
        with channels.use('primary'):
            content,_=responses.export(self.user,self.query());self.assertEqual(len(list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))),1)
            forms.delete(self.user,{'form_id':self.row['form_id'],'confirm_counts':{'notifications':0,'responses':0}})
            with self.assertRaises(PermissionError):responses.listing(self.user,self.query())
        self.row=self.create()
        with app.database_connection() as conn:conn.execute('UPDATE organization_members SET active=0 WHERE email=?',(ORG_ADMIN,))
        with channels.use('primary'),self.assertRaises(PermissionError):responses.export(self.user,self.query())

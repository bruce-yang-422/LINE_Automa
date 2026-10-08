"""A13–A16: private fixtures, ownership, content checks and physical cleanup."""
import io
import json
import zipfile
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import unittest
from PIL import Image
import app,channels,forms,public_forms as public,form_attachments as files
import test_public_forms as public_tests
from test_roles_and_permissions import COLLABORATOR,ORG_A
import reports

class AttachmentTests(unittest.TestCase):
    setUp=public_tests.PublicFormTests.setUp
    setup_roles_environment=public_tests.PublicFormTests.setup_roles_environment
    prepare=public_tests.PublicFormTests.prepare
    create=public_tests.PublicFormTests.create
    ready=public_tests.PublicFormTests.ready
    public_server=public_tests.PublicFormTests.public_server
    request=public_tests.PublicFormTests.request
    url=public_tests.PublicFormTests.url

    def setup_attachment(self,**config):
        q=forms.question('file','附件','attachment',required=True)
        q['attachment']={'extensions':['png','pdf','txt'],'max_files':2,'max_file_bytes':4096,'max_total_bytes':6000,**config}
        self.ready([q]);self.q=q
        self.page=public.view(self.row['form_id'],self.link['token'])
        return self.page['draft_key']

    def png(self):
        stream=io.BytesIO();Image.new('RGB',(800,400),'green').save(stream,format='PNG');return stream.getvalue()

    def upload(self,name='測試.PNG',data=None,key=None,keep=None):
        return files.upload(self.row['form_id'],key or self.page['draft_key'],'file',name,data or self.png(),keep)

    def payload(self,ids,page=None):
        page=page or self.page
        return {'answers':{'file':ids},'expected_updated_at':self.row['updated_at'],'expected_response_updated_at':page['response_updated_at'],'submission_key':page['submission_key'],'draft_key':page['draft_key']}

    def submit(self,ids,page=None,edit=None):
        return public.submit(self.row['form_id'],self.link['token'],self.payload(ids,page),edit)

    def test_thumbnail_ratio_metadata_and_private_read(self):
        key=self.setup_attachment();data=self.png();meta=self.upload(data=data)
        self.assertEqual(meta['extension'],'png');self.assertNotIn('file_name',meta)
        raw,mime,name=files.read(self.row['form_id'],key,meta['attachment_id']);self.assertEqual(raw,data);self.assertEqual(mime,'image/png')
        thumb,_,_=files.read(self.row['form_id'],key,meta['attachment_id'],'thumb')
        with Image.open(io.BytesIO(thumb)) as image:self.assertEqual(image.size,(640,320));self.assertFalse(image.getexif())
        other=public.view(self.row['form_id'],self.link['token'])
        with self.assertRaises(files.AttachmentError):files.read(self.row['form_id'],other['draft_key'],meta['attachment_id'])
        with self.assertRaises(files.AttachmentError):files.path('../secret.txt')
        with channels.use('primary'):
            with self.assertRaises(files.AttachmentError):files.admin_read(self.user,self.row['form_id'],meta['attachment_id'])
        code,result=self.submit([meta['attachment_id']]);self.assertEqual(code,200)
        self.assertEqual(self.submit([meta['attachment_id']]),(code,result))
        with channels.use('primary'):
            self.assertEqual(files.admin_read(reports.account(COLLABORATOR),self.row['form_id'],meta['attachment_id'])[0],data)
        with channels.use('another'):
            with self.assertRaises(PermissionError):files.admin_read(self.user,self.row['form_id'],meta['attachment_id'])

    def test_orientation_thumbnail_removes_exif(self):
        stream=io.BytesIO();image=Image.new('RGB',(40,20));exif=Image.Exif();exif[274]=6;exif[270]='private metadata';image.save(stream,format='JPEG',exif=exif)
        thumb=files.inspect('jpg',stream.getvalue())
        with Image.open(io.BytesIO(thumb)) as image:self.assertEqual(image.size,(20,40));self.assertFalse(image.getexif())
        with patch.object(Image,'MAX_IMAGE_PIXELS',500),self.assertRaises(files.AttachmentError):files.inspect('jpg',stream.getvalue())

    def test_forged_extension_ids_and_limits(self):
        self.setup_attachment(max_files=1)
        for name,data in [('bad.png',b'%PDF-1.7'),('bad.pdf',self.png()),('bad.txt',b'\xff'),('bad.exe',b'MZ'),('bad.gif',b'GIF89a'),('../bad.pdf',b'%PDF-1.7')]:
            with self.subTest(name=name),self.assertRaises(files.AttachmentError):self.upload(name,data)
        with self.assertRaises(files.AttachmentError):self.upload('too.pdf',b'%PDF-'+b'x'*4096)
        self.assertEqual(self.submit(['a'*32])[0],422)
        meta=self.upload('okay.PDF',b'%PDF-1.7\nexample')
        with self.assertRaises(files.AttachmentError):self.upload('second.pdf',b'%PDF-1.7')
        other=public.view(self.row['form_id'],self.link['token'])
        self.assertEqual(self.submit([meta['attachment_id']],other)[0],422)
        with self.assertRaises(files.AttachmentError):files.upload(self.row['form_id'],self.page['draft_key'],'wrong','okay.pdf',b'%PDF-1.7')

    def test_office_odf_and_archives_content(self):
        def zipped(values):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                for name,data in values.items():archive.writestr(name,data)
            return stream.getvalue()
        self.assertIsNone(files.inspect('docx',zipped({'[Content_Types].xml':'x','word/document.xml':'x'})))
        self.assertIsNone(files.inspect('ods',zipped({'mimetype':'application/vnd.oasis.opendocument.spreadsheet','content.xml':'x'})))
        with self.assertRaises(files.AttachmentError):files.inspect('docx',zipped({'random.txt':'x'}))
        with self.assertRaises(files.AttachmentError):files.inspect('odt',zipped({'mimetype':'wrong','content.xml':'x'}))
        with self.assertRaises(files.AttachmentError):files.inspect('zip',b'PK\x03\x04fake')
        self.assertIsNone(files.inspect('zip',zipped({'../never-extracted.txt':'x'})))

    def test_upload_retry_after_lost_response_does_not_duplicate(self):
        key=self.setup_attachment(max_files=1);identifier='b'*32
        first=files.upload(self.row['form_id'],key,'file','one.pdf',b'%PDF-1.7',upload_id=identifier)
        self.assertEqual(files.upload(self.row['form_id'],key,'file','one.pdf',b'%PDF-1.7',upload_id=identifier),first)
        with self.assertRaises(files.AttachmentError):files.upload(self.row['form_id'],key,'file','changed.pdf',b'%PDF-1.7',upload_id=identifier)
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM form_attachments').fetchone()[0],1)

    def test_replacement_only_removes_old_files_after_success(self):
        self.setup_attachment(max_files=1);old=self.upload();_,result=self.submit([old['attachment_id']]);edit=result['edit_url'].split('&edit=')[1]
        page=public.view(self.row['form_id'],self.link['token'],edit);self.assertEqual(page['attachments'][0]['attachment_id'],old['attachment_id'])
        files.remove(self.row['form_id'],page['draft_key'],old['attachment_id'])
        self.assertTrue(files.path(old['thumbnail_name']).exists())
        with self.assertRaises(files.AttachmentError):self.upload('new.pdf',b'%PDF-1.7',page['draft_key'])
        new=self.upload('new.pdf',b'%PDF-1.7',page['draft_key'],keep=[])
        payload=self.payload([new['attachment_id']],page);payload['expected_response_updated_at']='wrong'
        with self.assertRaises(public.PublicError):public.submit(self.row['form_id'],self.link['token'],payload,edit)
        files.cleanup();self.assertTrue(files.path(old['thumbnail_name']).exists())
        self.assertEqual(self.submit([new['attachment_id']],page,edit)[0],200)
        files.cleanup();self.assertFalse(files.path(old['thumbnail_name']).exists());self.assertFalse(files.path(old['attachment_id']+'.png').exists())
        self.assertEqual(files.read(self.row['form_id'],page['draft_key'],new['attachment_id'])[0],b'%PDF-1.7')

    def test_expiry_remove_delete_and_total_cleanup(self):
        key=self.setup_attachment(max_total_bytes=5000);one=self.upload('one.pdf',b'%PDF-'+b'x'*2995)
        with self.assertRaises(files.AttachmentError):self.upload('two.pdf',b'%PDF-'+b'x'*2995)
        files.remove(self.row['form_id'],key,one['attachment_id']);self.assertFalse(files.path(one['attachment_id']+'.pdf').exists())
        saved=self.upload();self.submit([saved['attachment_id']]);temporary=self.upload('temporary.pdf',b'%PDF-1.7')
        files.cleanup(datetime.now(timezone.utc)+timedelta(hours=25))
        self.assertFalse(files.path(temporary['attachment_id']+'.pdf').exists());self.assertTrue(files.path(saved['thumbnail_name']).exists())
        with channels.use('primary'):forms.delete(self.user,{'form_id':self.row['form_id'],'confirm_counts':{'notifications':0,'responses':1}})
        self.assertFalse(files.path(saved['thumbnail_name']).exists());self.assertFalse(list(files.root().iterdir()))

    def test_http_upload_origin_capability_and_status(self):
        key=self.setup_attachment();server=self.public_server()
        import http.client
        from urllib.parse import quote
        def post(draft=key,origin=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);headers={'Content-Type':'application/octet-stream','X-Filename':quote('測試.PDF')}
            if origin:headers['Origin']=origin
            conn.request('POST','/forms/'+self.row['form_id']+'/upload?token='+self.link['token']+'&draft='+draft+'&question=file',b'%PDF-1.7',headers)
            response=conn.getresponse();status=response.status;data=response.read();conn.close();return status,data
        self.assertEqual(post(origin='https://evil.example')[0],403);self.assertEqual(post('invalid')[0],400)
        status,data=post();self.assertEqual(status,200);meta=json.loads(data)
        url='/forms/'+self.row['form_id']+'/attachments/'+meta['attachment_id']+'/download?token='+self.link['token']+'&draft='+key
        status,headers,body=self.request(server,'GET',url);self.assertEqual(status,200);self.assertEqual(body,b'%PDF-1.7');self.assertIn('attachment',headers['Content-Disposition'])
        with channels.use('primary'):forms.transition(self.user,{'form_id':self.row['form_id'],'status':'stopped'})
        self.assertEqual(post()[0],403)

import base64
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
from http.server import ThreadingHTTPServer
import http.client

from PIL import Image
import app
import admin_server
import composer
import reports
import send_image
import channels
import test_workspace
from test_workspace import CHANNEL_B


class ComposerTests(unittest.TestCase):
    setUpClass = classmethod(test_workspace.WorkspaceTests.setUpClass.__func__)
    setUp = test_workspace.WorkspaceTests.setUp
    server = test_workspace.WorkspaceTests.server
    request = test_workspace.WorkspaceTests.request

    def upload(self, organization_id='A', fmt='PNG'):
        image = Image.new('RGB', (400, 300), (40, 100, 130))
        stream = BytesIO()
        image.save(stream, format=fmt)
        return composer.upload({'name':r'C:\private\report.jpg', 'organization_id':organization_id,
                                'data':base64.b64encode(stream.getvalue()).decode()}, reports.account('admin@example.com'))

    def draft(self, kind='carousel', count=2, organization_id='A'):
        uploaded = self.upload(organization_id)
        return {'format':kind, 'alt_text':'季度報告', 'items':[{'asset_id':uploaded['asset_id'], 'title':f'報告 {i}',
                'text':'營運摘要', 'label':'查看報告', 'url':'https://example.com/report'} for i in range(count)]}

    def selected(self, rid=test_workspace.USER):
        with app.database_connection() as conn:
            return admin_server.select_contacts(conn, 'selected', [rid])

    def test_upload_normalizes_jpeg_and_does_not_publish_source(self):
        result = self.upload(fmt='JPEG')
        self.assertEqual(result['name'], 'report.jpg')
        path = composer.asset(result['asset_id'], reports.account('admin@example.com'))['path']
        self.assertTrue(path.is_relative_to(self.root/'data/uploads'))
        with Image.open(path) as image:
            self.assertEqual(image.format, 'PNG')
        self.assertLessEqual(path.stat().st_size, composer.MAX_BYTES)
        self.assertFalse((self.root/'published-images').exists())
        for invalid in ('<svg/>', base64.b64encode(b'not a PNG').decode(), 'A'*(12*1024*1024)):
            with self.assertRaises(ValueError):
                composer.upload({'data':invalid}, reports.account('admin@example.com'))
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 100):
            with self.assertRaises(ValueError): self.upload()

    def test_upload_api_permission_and_preview_and_org_isolation(self):
        server = self.server()
        self.assertEqual(self.request(server, '/api/assets/upload', 'nobody@example.com', {})[0], 401)
        self.assertEqual(self.request(server, '/api/assets/upload', 'admin@example.com', {}, view_as='alice@example.com')[0], 403)
        reports.save_user({'email':'manager@example.com','role':'org_admin','organization_id':'A','active':True}, 'admin@example.com')
        with channels.use(CHANNEL_B):
            image = self.upload('B')
        with self.assertRaises(ValueError): composer.asset(image['asset_id'], reports.account('manager@example.com'))
        with self.assertRaises(ValueError): composer.asset('../test.db', reports.account('admin@example.com'))
        raw = base64.b64encode((self.root/'data/uploads'/(image['asset_id']+'.png')).read_bytes()).decode()
        status, uploaded = self.request(server, '/api/assets/upload', 'manager@example.com', {'data':raw,'organization_id':'B','name':'test.png'})
        self.assertEqual(status, 201)
        self.assertEqual(uploaded['organization_id'], 'A')
        reports.save_organization({'org_id':'A','name':'A','kind':'company','active':True,'messaging_enabled':False},'admin@example.com')
        self.assertEqual(self.request(server, '/api/assets/upload', 'manager@example.com', {'data':raw})[0], 400)

    def test_formats_validate_scope_count_and_actions_before_publication(self):
        user=reports.account('admin@example.com'); selected=self.selected()
        for kind,count in [('images',6),('card',2),('carousel',13),('imagemap',2)]:
            with self.assertRaises(ValueError): composer.prepare(self.draft(kind,count),user,selected)
        draft=self.draft()
        with self.assertRaises(ValueError): composer.prepare(draft,user,self.selected(test_workspace.OTHER))
        for url in ('javascript:alert(1)','http://example.com','https://user:password@example.com'):
            draft['items'][0]['url']=url
            with self.assertRaises(ValueError): composer.prepare(draft,user,selected)
        draft=self.draft('imagemap',1);draft.update(layout='four',areas=[])
        with self.assertRaises(ValueError): composer.prepare(draft,user,selected)

    def test_images_cards_carousel_and_imagemap_payloads(self):
        user=reports.account('admin@example.com'); publish=Mock(return_value=('https://example.com/image.png',b'data')); verify=Mock()
        for kind,count,typ in [('images',5,'image'),('card',1,'flex'),('carousel',12,'flex')]:
            messages=composer.build(composer.prepare(self.draft(kind,count),user,self.selected()),publish,verify)
            self.assertEqual(messages[0]['type'],typ)
            if kind=='images': self.assertEqual(len(messages),5)
            elif kind=='card': self.assertEqual(messages[0]['contents']['type'],'bubble')
            else: self.assertEqual(len(messages[0]['contents']['contents']),12)
        draft=self.draft('imagemap',1);draft.update(layout='six',areas=[{'label':str(i),'url':'https://example.com/'+str(i)} for i in range(6)])
        publish.reset_mock();verify.reset_mock()
        message=composer.build(composer.prepare(draft,user,self.selected()),publish,verify)[0]
        publish.assert_not_called();self.assertEqual(verify.call_count,5)
        self.assertEqual(message['baseSize'],{'width':1040,'height':780})
        self.assertEqual(len(message['actions']),6)
        self.assertEqual(sum(a['area']['width']*a['area']['height'] for a in message['actions']),1040*780)
        self.assertEqual(len(list((self.root/'published-images').glob('*.png'))),5)

    def test_scheduled_composition_is_frozen_and_uses_existing_retry_key(self):
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        draft=self.draft()
        payload={'job_id':str(uuid4()),'audience':'selected','ids':[test_workspace.USER],'composition':draft,
                 'scheduled_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        with patch.object(send_image,'ROOT',self.root), patch.object(admin_server,'verify_public_image'), patch.object(admin_server,'load_settings'):
            job=dispatcher.submit(payload, 'admin@example.com')
        messages=json.loads(job['messages_json'])
        self.assertEqual(job['status'],'scheduled');self.assertEqual(job['organization_id'],'A')
        draft['items'][0]['title']='Edited afterwards'
        composer.asset(draft['items'][0]['asset_id'], reports.account('admin@example.com'))['path'].unlink()
        with app.database_connection() as conn:
            retry_key=conn.execute('SELECT retry_key FROM send_deliveries WHERE job_id=?',(job['job_id'],)).fetchone()[0]
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at='' WHERE job_id=?",(job['job_id'],))
        with patch.object(admin_server,'send_push',return_value='request') as send:
            dispatcher.run(job['job_id'])
        self.assertEqual(send.call_args.kwargs['messages'],messages)
        self.assertNotEqual(messages[0]['contents']['contents'][0]['body']['contents'][0]['text'],'Edited afterwards')
        self.assertEqual(send.call_args.kwargs['retry_key'],retry_key)
        self.assertEqual(admin_server.job_status(job['job_id'])[0]['deliveries'][0]['status'],'accepted')

    def test_scheduled_organization_media_cancelled_if_contact_moves(self):
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        payload={'job_id':str(uuid4()),'audience':'selected','ids':[test_workspace.USER],'composition':self.draft('images',1),
                 'scheduled_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        with patch.object(send_image,'ROOT',self.root), patch.object(admin_server,'verify_public_image'), patch.object(admin_server,'load_settings'):
            job=dispatcher.submit(payload,'admin@example.com')
        with app.database_connection() as conn:
            conn.execute("UPDATE recipients SET organization_id='B' WHERE recipient_id=?",(test_workspace.USER,))
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at='' WHERE job_id=?",(job['job_id'],))
        with patch.object(admin_server,'send_push') as send: dispatcher.run(job['job_id'])
        send.assert_not_called()
        self.assertEqual(admin_server.job_status(job['job_id'])[0]['deliveries'][0]['status'],'cancelled')

    def test_public_imagemap_sizes_are_strictly_allowlisted(self):
        draft=self.draft('imagemap',1);draft.update(layout='one',areas=[{'label':'開啟','url':'https://example.com'}])
        message=composer.build(composer.prepare(draft,reports.account('admin@example.com'),self.selected()),Mock(),Mock())[0]
        map_id=message['baseUrl'].rsplit('/',1)[1]
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        with patch.object(app,'IMAGE_DIR',self.root/'published-images'):
            for path,expected in [(f'/imagemaps/{map_id}/1040',200),(f'/imagemaps/{map_id}/123',404),('/data/uploads/test.png',404),('/imagemaps/../../test.db/1040',404)]:
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                connection.request('GET',path);response=connection.getresponse()
                self.assertEqual(response.status,expected)
                if expected==200:self.assertTrue(response.read().startswith(b'\x89PNG'))
                else:response.read()
                connection.close()

    def test_native_messages_reach_push_request_unchanged(self):
        response=Mock(status=200,headers={'x-line-request-id':'mock-request'})
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        messages=[{'type':'image','originalContentUrl':'https://example.com/a.png','previewImageUrl':'https://example.com/a.png'}]
        with patch.object(send_image,'urlopen',return_value=response) as request:
            self.assertEqual(send_image.send_push('fake-token',test_workspace.USER,'',retry_key='retry-key',messages=messages),'mock-request')
        data=json.loads(request.call_args.args[0].data)
        self.assertEqual(data,{'to':test_workspace.USER,'messages':messages})

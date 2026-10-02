"""Multi-OA isolation, authorization and dispatch tests; no real LINE requests."""
from contextlib import closing
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import app
import channels
import composer
import admin_server
import reports
import recipients

USER = 'U' + '1' * 32
ADMIN = 'admin@example.test'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class ChannelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='line-oa-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.schema = (app.BASE_DIR/'schema.sql').read_text(encoding='utf-8')
        (self.root/'schema.sql').write_text(self.schema, encoding='utf-8')
        (self.root/'instance').mkdir()
        for target, value in [('BASE_DIR', self.root), ('DATABASE_PATH', self.root/'test.db')]:
            p = patch.object(app, target, value);p.start();self.addCleanup(p.stop)
        env = patch.dict(os.environ, {'PUBLIC_BASE_URL': 'https://reports.example.test'}, clear=True)
        env.start();self.addCleanup(env.stop)
        app.initialize_database()
        reports.bootstrap_users({ADMIN})
        self.admin = reports.account(ADMIN)
        for email, org, role in [('boss@example.test', 'A', 'org_admin'), ('other@example.test', 'B', 'org_admin'), ('sender@example.test', 'A', 'operator')]:
            reports.save_user({'email': email, 'role': role, 'organization_id': org, 'active': True}, ADMIN)
        api = patch('line_api.request', side_effect=lambda path, payload=None, token=None: {
            'userId': 'U' + hashlib.md5(token.encode()).hexdigest(), 'displayName': 'OA ' + token, 'basicId': '@test'})
        api.start();self.addCleanup(api.stop)
        self.a = self.add('a', 'o:A')
        self.b = self.add('b', 'o:A')
        self.c = self.add('c', 'o:B')
        # 第三個組織，作為移轉目標。
        with app.database_connection() as conn:
            conn.execute("INSERT INTO organizations(org_id,name,kind) VALUES ('C','C','personal')")

    def add(self, token, workspace):
        return channels.save({'workspace_id': workspace, 'secret': 'a'*32, 'access_token': token}, self.admin)['channel_id']

    def event(self, channel, text='hello', message='same-message'):
        with channels.use(channel):
            app.save_events([{'type': 'message', 'timestamp': 1790750000000,
                             'source': {'type': 'user', 'userId': USER},
                             'message': {'id': message, 'type': 'text', 'text': text}}])

    def server(self):
        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok and handler.headers.get('Test-User'):
                    handler.user = reports.login_account(handler.headers['Test-User'])
                    handler.identity = handler.user['email']
                return ok
        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start();self.addCleanup(server.close)
        return server

    def request(self, server, path, channel=None, payload=None, email=None):
        headers = {'Authorization': 'Bearer '+server.token, 'Content-Type': 'application/json'}
        if channel:headers['X-Line-Channel'] = channel
        if email:headers['Test-User'] = email
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        try:
            conn.request('GET' if payload is None else 'POST', path, json.dumps(payload) if payload is not None else None, headers)
            result = conn.getresponse()
            return result.status, json.loads(result.read())
        finally:conn.close()

    def test_identical_user_and_message_ids_are_separate_and_subscriptions_independent(self):
        self.event(self.a, '訂閱天氣');self.event(self.b, 'hello')
        for channel, subscribed, text in [(self.a, 1, '訂閱天氣'), (self.b, 0, 'hello')]:
            with channels.use(channel), app.database_connection() as conn:
                rows = recipients.list_contacts(conn)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['organization_id'], 'A')
                self.assertEqual(rows[0]['weather_subscribed'], subscribed)
                self.assertEqual(conn.execute('SELECT text_content FROM line_messages WHERE channel_id=current_channel()').fetchone()[0], text)
        with channels.use(self.a):
            app.save_events([{'type': 'unsend', 'source': {'type':'user','userId':USER}, 'unsend': {'messageId':'same-message'}}])
        with channels.use(self.b), app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT text_content FROM line_messages WHERE channel_id=current_channel()').fetchone()[0], 'hello')

    def test_workspace_authorization_missing_selection_and_no_secret_disclosure(self):
        self.event(self.a);self.event(self.c)
        server = self.server()
        self.assertEqual(self.request(server, '/api/contacts')[0], 403)
        self.assertEqual(self.request(server, '/api/contacts', self.c, email='boss@example.test')[0], 403)
        code, result = self.request(server, '/api/contacts', self.a, email='boss@example.test')
        self.assertEqual(code, 200);self.assertEqual(len(result['contacts']), 1)
        _, result = self.request(server, '/api/channels', email='boss@example.test')
        self.assertEqual({c['channel_id'] for c in result['channels']}, {self.a, self.b})
        encoded = json.dumps(result)
        self.assertNotIn('token_cipher', encoded);self.assertNotIn('secret_cipher', encoded)
        with self.assertRaises(ValueError):
            channels.set_active({'channel_id': self.c, 'active': False}, reports.account('boss@example.test'))
        with self.assertRaises(ValueError):
            channels.set_active({'channel_id': self.a, 'active': False}, reports.account('sender@example.test'))

    def test_duplicate_bot_wrong_rotation_and_ownership_transfer_rejected(self):
        with self.assertRaises(ValueError):self.add('a', 'o:B')
        row = channels.get(self.a)
        with self.assertRaises(ValueError):
            channels.save({'channel_id': self.a, 'workspace_id': 'o:A', 'access_token': 'b'}, self.admin)
        with self.assertRaises(ValueError):
            channels.save({'channel_id': self.a, 'workspace_id': 'o:B'}, self.admin)
        self.assertEqual(channels.get(self.a)['token_cipher'], row['token_cipher'])
        self.assertNotEqual(channels.get(self.a)['secret_cipher'], 'a'*32)

    def test_private_assets_reports_grants_and_cancellation_do_not_cross_oa(self):
        self.event(self.a);self.event(self.b)
        with channels.use(self.a):
            asset = composer.upload({'data':base64.b64encode(PNG).decode(), 'name':'report.png','organization_id':'A'},self.admin)
            report = reports.save({'asset_id':asset['asset_id'],'title':'A report','organization_id':'A','scope':'company','category':'company'},ADMIN)
            scope = reports.save_dispatch_scope({'organization_id':'A','name':'Team','kind':'department','department':'Sales','active':True,'recipient_ids':[]},ADMIN)
            reports.save_grant({'email':'sender@example.test','organization_id':'A','scope_ids':[scope['scope_id']], 'report_ids':[report['report_id']], 'messaging':True,'reports':True,'weather':False},ADMIN)
        with channels.use(self.b):
            self.assertEqual(reports.sources(), [])
            with self.assertRaises(ValueError):composer.asset(asset['asset_id'],self.admin)
            with self.assertRaises(ValueError):reports.remove(report['report_id'],ADMIN)
            self.assertFalse(reports.grant(reports.account('sender@example.test'))['messaging'])
            with self.assertRaises(ValueError):
                composer.upload({'data':base64.b64encode(PNG).decode(),'organization_id':'B'},self.admin)

    def test_jobs_keep_oa_token_and_cross_oa_lookup_and_cancel_are_rejected(self):
        for channel in (self.a,self.b):self.event(channel)
        dispatcher = admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        jobs=[]
        for channel in (self.a,self.b):
            with channels.use(channel):
                job = dispatcher.submit({'job_id':str(uuid4()),'message_text':'test','audience':'selected','ids':[USER],
                                         'scheduled_at':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()},actor=ADMIN)
                jobs.append(job['job_id'])
        with channels.use(self.b):
            self.assertEqual(admin_server.job_status(jobs[0]), [])
            with self.assertRaises(ValueError):dispatcher.cancel(jobs[0],ADMIN)
        with app.database_connection() as conn:
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at=''")
        with patch('admin_server.send_push', return_value='fake-id') as push:
            # Intentionally run both jobs from the wrong HTTP scope.
            with channels.use(self.c):
                for job in jobs:dispatcher.run(job)
            self.assertEqual([call.args[0] for call in push.call_args_list], ['a','b'])
        self.assertEqual(channels.current_id(), '')

    def test_organization_admin_job_is_delivered(self):
        # Regression: non-platform actors were re-checked against a tuple row and every delivery was interrupted.
        self.event(self.a)
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with channels.use(self.a):
            job=dispatcher.submit({'job_id':str(uuid4()),'message_text':'test','audience':'selected','ids':[USER],
                                   'scheduled_at':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()},actor='boss@example.test',organization='A')
        with app.database_connection() as conn:
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at=''")
        with patch('admin_server.send_push',return_value='fake-id') as push:
            dispatcher.run(job['job_id'])
        push.assert_called_once()
        with channels.use(self.a):
            self.assertEqual(admin_server.job_status(job['job_id'])[0]['status'],'finished')

    def test_disabled_oa_and_revoked_membership_prevent_scheduled_delivery(self):
        self.event(self.a)
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with channels.use(self.a):
            job=dispatcher.submit({'job_id':str(uuid4()),'message_text':'test','audience':'selected','ids':[USER],
                                   'scheduled_at':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()},actor='boss@example.test',organization='A')
        with app.database_connection() as conn:
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at=''")
            conn.execute("UPDATE organization_members SET active=0 WHERE email='boss@example.test'")
        with patch('admin_server.send_push') as push:
            dispatcher.run(job['job_id']);push.assert_not_called()
        channels.set_active({'channel_id':self.a,'active':False},self.admin)
        with channels.use(self.a),self.assertRaises(ValueError):channels.access_token()

    def test_webhook_requires_matching_secret_and_destination(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def post(path,destination,secret):
            body=json.dumps({'destination':destination,'events':[]}).encode()
            signature=base64.b64encode(hmac.new(secret.encode(),body,hashlib.sha256).digest()).decode()
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            try:
                conn.request('POST',path,body,{'x-line-signature':signature});r=conn.getresponse();r.read();return r.status
            finally:conn.close()
        path='/webhook/'+self.a;bot=channels.get(self.a)['bot_user_id']
        self.assertEqual(post(path,bot,'a'*32),200)
        self.assertTrue(channels.get(self.a)['webhook_seen_at'])
        self.assertEqual(post(path,bot,'b'*32),401)
        self.assertEqual(post(path,channels.get(self.b)['bot_user_id'],'a'*32),401)
        self.assertEqual(post('/webhook',bot,'a'*32),404)

    def test_profiles_use_their_own_oa_token_and_empty_secret_is_rejected(self):
        self.event(self.a);self.event(self.b)
        seen=[]
        def profile(path, payload=None, **kwargs):
            seen.append(channels.access_token())
            return {'displayName':'Profile '+seen[-1]}
        with patch('line_api.request',side_effect=profile):
            recipients.ProfileRefresher().tick()
        self.assertEqual(seen,['a','b'])
        body=b'{}'
        signature=base64.b64encode(hmac.new(b'',body,hashlib.sha256).digest()).decode()
        self.assertFalse(app.valid_signature(body,signature,secret=''))

    def shared_to_b(self):
        self.event(self.a)
        with channels.use(self.a):
            app.save_events([{'type':'follow','timestamp':1790750000001,'source':{'type':'user','userId':'U'+'2'*32}}])
        return channels.share({'channel_id':self.a,'workspace_id':'o:B'},self.admin)['share_id']

    def test_shared_oa_sees_only_assigned_recipients_and_uses_owner_token(self):
        share=self.shared_to_b()
        other=reports.account('other@example.test')
        rows={c['channel_id']:c for c in channels.catalogue(other)['channels']}
        self.assertEqual(set(rows),{self.c,share})
        self.assertTrue(rows[share]['shared']);self.assertEqual(rows[share]['webhook_url'],'')
        self.assertFalse(rows[share]['can_manage']);self.assertNotIn('shares',rows[share])
        for call in (lambda:channels.verify(share,other),lambda:channels.set_active({'channel_id':share,'active':False},other),
                     lambda:channels.save({'channel_id':share,'workspace_id':'o:B'},other),
                     lambda:channels.assign({'share_id':share,'recipient_ids':[USER]},other)):
            with self.assertRaises(ValueError):call()
        with channels.use(share),app.database_connection() as conn:
            self.assertEqual(recipients.list_contacts(conn),[])
        # The owning workspace's manager distributes recipients.
        self.assertEqual(channels.assign({'share_id':share,'recipient_ids':[USER]},reports.account('boss@example.test'))['added'],1)
        with self.assertRaises(ValueError):channels.assign({'share_id':share,'recipient_ids':['U'+'9'*32]},self.admin)
        server=self.server()
        code,result=self.request(server,'/api/contacts',share,email='other@example.test')
        self.assertEqual(code,200)
        self.assertEqual([(c['recipient_id'],c['organization_id']) for c in result['contacts']],[(USER,'B')])
        self.assertEqual(self.request(server,'/api/contacts',share,email='boss@example.test')[0],403)
        self.assertEqual(self.request(server,'/api/channels/shares/'+share,email='other@example.test')[0],403)
        _,detail=self.request(server,'/api/channels/shares/'+share,email='boss@example.test')
        self.assertEqual({r['recipient_id']:r['assigned'] for r in detail['recipients']},{USER:True,'U'+'2'*32:False})
        dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
        with channels.use(share):
            job=dispatcher.submit({'job_id':str(uuid4()),'message_text':'shared','audience':'selected','ids':[USER],
                                   'scheduled_at':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()},actor='other@example.test',organization='B')
        with channels.use(self.a):self.assertEqual(admin_server.job_status(job['job_id']),[])
        with app.database_connection() as conn:
            conn.execute("UPDATE send_jobs SET status='queued',scheduled_at=''")
        with patch('admin_server.send_push',return_value='fake-id') as push:
            dispatcher.run(job['job_id'])
        self.assertEqual(push.call_args.args[0],'a')

    def test_owner_webhook_state_and_names_follow_into_shares_and_pause_keeps_data(self):
        share=self.shared_to_b()
        channels.assign({'share_id':share,'recipient_ids':[USER]},self.admin)
        with channels.use(share),app.database_connection() as conn:
            conn.execute("UPDATE recipients SET custom_name='B note' WHERE channel_id=current_channel()")
        with channels.use(self.a):
            app.save_events([{'type':'unfollow','timestamp':1790750009999,'source':{'type':'user','userId':USER}}])
            with patch('line_api.request',return_value={'displayName':'Owner lookup'}):
                with app.database_connection() as conn:
                    conn.execute('UPDATE recipients SET active=1 WHERE channel_id=current_channel()')
                recipients.refresh_profile(USER,force=True)
        with channels.use(share),app.database_connection() as conn:
            row=recipients.list_contacts(conn)[0]
        self.assertEqual((row['active'],row['display_name'],row['custom_name']),(0,'Owner lookup','B note'))
        channels.share({'channel_id':self.a,'workspace_id':'o:B','active':False},self.admin)
        with self.assertRaises(ValueError):channels.authorize(share,reports.account('other@example.test'))
        self.assertNotIn(share,{c['channel_id'] for c in channels.catalogue(self.admin)['channels']})
        self.assertEqual(channels.share({'channel_id':self.a,'workspace_id':'o:B'},self.admin)['share_id'],share)
        with channels.use(share),app.database_connection() as conn:
            self.assertEqual(len(recipients.list_contacts(conn)),1)
        with self.assertRaises(ValueError):channels.webhook_channel('/webhook/'+share)
        with app.database_connection() as conn:conn.execute("UPDATE organizations SET active=0 WHERE org_id='A'")
        self.assertFalse(channels.operational(channels.get(share)))

    def test_only_platform_admin_shares_or_transfers(self):
        boss=reports.account('boss@example.test')
        with self.assertRaises(ValueError):channels.share({'channel_id':self.a,'workspace_id':'o:B'},boss)
        with self.assertRaises(ValueError):channels.transfer({'channel_id':self.a,'workspace_id':'o:B','confirm':True},boss)
        with self.assertRaises(ValueError):channels.share({'channel_id':self.a,'workspace_id':'o:A'},self.admin)
        share=channels.share({'channel_id':self.a,'workspace_id':'o:B'},self.admin)['share_id']
        with self.assertRaises(ValueError):channels.share({'channel_id':share,'workspace_id':'o:C'},self.admin)
        with self.assertRaises(ValueError):channels.transfer({'channel_id':self.a,'workspace_id':'o:B','confirm':True},self.admin)

    def test_transfer_previews_blocks_pending_jobs_and_moves_owner_data(self):
        self.event(self.a)
        with channels.use(self.a):
            scope=reports.save_dispatch_scope({'organization_id':'A','name':'Team','kind':'department','department':'Sales','active':True,'recipient_ids':[]},ADMIN)
            reports.save_grant({'email':'sender@example.test','organization_id':'A','scope_ids':[scope['scope_id']],'report_ids':[],'messaging':True,'reports':False,'weather':False},ADMIN)
            with app.database_connection() as conn:conn.execute("UPDATE recipients SET department='Sales' WHERE channel_id=current_channel()")
            dispatcher=admin_server.Dispatcher();self.addCleanup(dispatcher.close)
            job=dispatcher.submit({'job_id':str(uuid4()),'message_text':'later','audience':'selected','ids':[USER],
                                   'scheduled_at':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()},actor=ADMIN)
        target={'channel_id':self.a,'workspace_id':'o:C'}
        preview=channels.transfer(target,self.admin)
        self.assertEqual((preview['transferred'],preview['recipients'],preview['pending_jobs'],preview['sender_grants']),(False,1,1,1))
        self.assertEqual(channels.get(self.a)['org_id'],'A')
        with self.assertRaises(ValueError):channels.transfer({**target,'confirm':True},self.admin)
        with channels.use(self.a):dispatcher.cancel(job['job_id'],ADMIN)
        self.assertTrue(channels.transfer({**target,'confirm':True},self.admin)['transferred'])
        row=channels.get(self.a)
        self.assertEqual(row['org_id'],'C')
        with self.assertRaises(ValueError):channels.authorize(self.a,reports.account('boss@example.test'))
        with channels.use(self.a),app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT organization_id,department FROM recipients WHERE channel_id=current_channel()').fetchone(),('C',''))
            self.assertEqual(conn.execute('SELECT count(*) FROM dispatch_scopes WHERE channel_id=current_channel()').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM sender_grants WHERE channel_id=current_channel()').fetchone()[0],0)
        with app.database_connection() as conn:
            self.assertTrue(conn.execute("SELECT 1 FROM audit_events WHERE action='oa.transfer'").fetchone())


if __name__=='__main__':unittest.main()

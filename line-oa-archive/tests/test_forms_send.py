"""A2/A4/A5: existing Dispatcher, fake LINE, fresh authorization and failed-only retry."""
import unittest
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime,timezone,timedelta
import app,channels,forms,form_send,admin_server,reports,public_forms
import test_forms_permissions as permissions
from test_roles_and_permissions import ADMIN,ORG_ADMIN,COLLABORATOR,ORG_A,CONTACT_USER

class FormSendTests(unittest.TestCase):
    setUp=permissions.FormsPermissionsTests.setUp
    setup_roles_environment=permissions.FormsPermissionsTests.setup_roles_environment
    prepare=permissions.FormsPermissionsTests.prepare
    create=permissions.FormsPermissionsTests.create
    server=permissions.FormsPermissionsTests.server
    request=permissions.FormsPermissionsTests.request
    call=permissions.FormsPermissionsTests.call

    def ready(self):
        self.prepare();self.row=self.create()
        with channels.use('primary'):self.row=forms.transition(self.user,{'form_id':self.row['form_id'],'status':'collecting'})['form']
        self.second='U'+'2'*32;self.third='U'+'3'*32
        with app.database_connection() as conn:
            for identifier in (self.second,self.third):conn.execute("INSERT INTO recipients(channel_id,recipient_id,kind,organization_id,display_name) VALUES ('primary',?,'user',?,'fixture')",(identifier,ORG_A))
        p=patch.object(channels,'access_token',return_value='fake-only');p.start();self.addCleanup(p.stop)
        p=patch.object(admin_server,'send_push',return_value='fake-request');self.push=p.start();self.addCleanup(p.stop)
        self.dispatcher=admin_server.Dispatcher();self.addCleanup(self.dispatcher.close)
        p=patch.object(self.dispatcher.pool,'submit');p.start();self.addCleanup(p.stop)

    def payload(self,mode='invite',ids=None):
        return {'form_id':self.row['form_id'],'mode':mode,'ids':ids or [CONTACT_USER],'body':'請協助填寫問卷'}

    def preview(self,payload=None):
        with channels.use('primary'):return form_send.preview(self.user,payload or self.payload())

    def send(self,prepared=None,job_id=None):
        prepared=prepared or self.preview()
        with channels.use('primary'):return form_send.send(self.user,{**prepared,'job_id':job_id or str(uuid4())},self.dispatcher)['job']

    def history(self):
        with channels.use('primary'):return form_send.history(self.user,self.row['form_id'])

    def test_preview_confirmation_idempotency_shared_link_and_counts(self):
        self.ready();prepared=self.preview(self.payload(ids=[CONTACT_USER,self.second]));self.assertIn(self.row['public_url'],prepared['message'])
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM send_jobs').fetchone()[0],0)
        with channels.use('primary'),self.assertRaises(ValueError):form_send.send(self.user,{**prepared,'body':'changed','job_id':str(uuid4())},self.dispatcher)
        job=self.send(prepared);self.assertEqual(self.send(prepared,job['job_id'])['job_id'],job['job_id'])
        self.assertEqual(self.history()['counts']['notifications'],0)
        self.dispatcher.run(job['job_id']);self.assertEqual(self.push.call_count,2)
        self.assertEqual(self.history()['counts'],{'notifications':2,'responses':0})
        self.send(prepared,job['job_id']);self.dispatcher.run(job['job_id']);self.assertEqual(self.push.call_count,2)
        self.assertEqual({call.kwargs['text'] for call in self.push.call_args_list},{prepared['message']})

    def test_only_failed_retry_unknown_never_notified_or_retried(self):
        self.ready()
        def fake(token,recipient,*args,**kwargs):
            if recipient==self.second:raise ValueError('明確拒絕')
            if recipient==self.third:raise ValueError('結果不明')
            return 'accepted'
        self.push.side_effect=fake;job=self.send(self.preview(self.payload(ids=[CONTACT_USER,self.second,self.third])));self.dispatcher.run(job['job_id'])
        history=self.history();self.assertEqual(history['counts']['notifications'],1)
        self.assertEqual({d['status'] for d in history['jobs'][0]['deliveries']},{'accepted','failed','unknown'})
        with channels.use('primary'):prepared=form_send.retry_preview(self.user,{'form_id':self.row['form_id'],'retry_job_id':job['job_id']})
        self.assertEqual(prepared['ids'],[self.second]);self.push.side_effect=None
        retry=self.send(prepared);self.dispatcher.run(retry['job_id']);self.assertEqual(self.history()['counts']['notifications'],2)
        self.assertEqual(self.push.call_args.args[1],self.second)

    def test_reminder_does_not_exclude_responses(self):
        self.ready()
        # Response totals are intentionally independent of the notification audience.
        with app.database_connection() as conn:conn.execute('INSERT INTO form_submissions VALUES (?,?,?,?,?,?,?,?)',(uuid4().hex,self.row['form_id'],public_forms.secrets.token_urlsafe(32),public_forms.secrets.token_urlsafe(32),'{}','[]','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00'))
        prepared=self.preview(self.payload('remind'));self.assertIn('若已填寫，請忽略',prepared['message']);self.assertEqual(prepared['ids'],[CONTACT_USER])
        job=self.send(prepared);self.dispatcher.run(job['job_id']);history=self.history()
        self.assertEqual(history['counts'],{'notifications':1,'responses':1});self.assertTrue(history['notifications'][0]['last_reminded_at']);self.assertEqual(history['notifications'][0]['sent_at'],'')

    def test_stop_expiry_disabled_module_and_revoked_actor_before_worker(self):
        for change in ('stop','expiry','module','actor'):
            with self.subTest(change=change):
                if not hasattr(self,'dispatcher'):self.ready()
                with app.database_connection() as conn:
                    conn.execute("UPDATE forms SET status='collecting',deadline_at='' WHERE form_id=?",(self.row['form_id'],))
                    conn.execute('UPDATE organizations SET forms_enabled=1 WHERE org_id=?',(ORG_A,))
                    conn.execute('UPDATE organization_members SET active=1 WHERE email=?',(ORG_ADMIN,))
                job=self.send()
                with app.database_connection() as conn:
                    if change=='stop':conn.execute("UPDATE forms SET status='stopped' WHERE form_id=?",(self.row['form_id'],))
                    elif change=='expiry':conn.execute('UPDATE forms SET deadline_at=? WHERE form_id=?',((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),self.row['form_id']))
                    elif change=='module':conn.execute('UPDATE organizations SET forms_enabled=0 WHERE org_id=?',(ORG_A,))
                    else:conn.execute('UPDATE organization_members SET active=0 WHERE email=?',(ORG_ADMIN,))
                self.dispatcher.run(job['job_id']);self.push.assert_not_called()
                with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT status FROM send_deliveries WHERE job_id=?',(job['job_id'],)).fetchone()[0],'cancelled')

    def test_http_authorization_preview_hash_and_job_history(self):
        self.ready();server=self.server()
        p=patch.object(server.dispatcher.pool,'submit');p.start();self.addCleanup(p.stop)
        payload=self.payload()
        self.assertEqual(self.call(server,'/api/forms/send/preview',COLLABORATOR,payload)[0],403)
        self.assertEqual(self.request(server,'/api/forms/send/preview',ORG_ADMIN,payload,channel='wrong')[0],403)
        self.assertEqual(self.call(server,'/api/forms/send',ORG_ADMIN,{**payload,'job_id':str(uuid4())})[0],400)
        status,prepared=self.call(server,'/api/forms/send/preview',ORG_ADMIN,payload);self.assertEqual(status,200)
        status,result=self.call(server,'/api/forms/send',ORG_ADMIN,{**prepared,'job_id':str(uuid4())});self.assertEqual(status,200)
        server.dispatcher.run(result['job']['job_id']);self.push.assert_called_once()
        status,history=self.call(server,'/api/forms/send/history?form_id='+self.row['form_id'],COLLABORATOR);self.assertEqual(status,200);self.assertEqual(history['counts']['notifications'],1)
        self.assertEqual(self.call(server,'/api/forms/send/history?form_id='+self.row['form_id'],ADMIN,view_as=ORG_ADMIN,preview_org=ORG_A)[0],200)
        self.assertEqual(self.call(server,'/api/forms/send/preview',ADMIN,payload,view_as=ORG_ADMIN,preview_org=ORG_A)[0],403)
        with app.database_connection() as conn:self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action='vendor.view'").fetchone()[0],1)

    def test_bad_audience_link_message_and_pending_retry_denied(self):
        self.ready()
        for extra in ({'ids':[CONTACT_USER,CONTACT_USER]},{'ids':['foreign']},{'body':' '},{'body':'x'*5000},{'mode':'auto'}):
            with self.subTest(extra=extra),channels.use('primary'),self.assertRaises(ValueError):form_send.preview(self.user,{**self.payload(),**extra})
        with patch.object(app,'public_base_url',return_value='http://insecure.example'),self.assertRaises(ValueError):self.preview()
        job=self.send()
        with channels.use('primary'),self.assertRaises(ValueError):form_send.retry_preview(self.user,{'form_id':self.row['form_id'],'retry_job_id':job['job_id']})
        self.dispatcher.run(job['job_id'])
        with channels.use('primary'),self.assertRaises(ValueError):form_send.retry_preview(self.user,{'form_id':self.row['form_id'],'retry_job_id':job['job_id']})

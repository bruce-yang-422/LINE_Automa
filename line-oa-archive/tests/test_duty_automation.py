import unittest
import json
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
import app
import duty
import duty_automation as automation
import reports
import test_duty_people as people_tests
import test_roles_and_permissions as roles


class DutyAutomationTests(unittest.TestCase):
    setUp=people_tests.DutyPeopleTests.setUp
    prepare=people_tests.DutyPeopleTests.prepare
    setup_roles_environment=people_tests.DutyPeopleTests.setup_roles_environment
    server=people_tests.DutyPeopleTests.server
    request=people_tests.DutyPeopleTests.request

    def environment(self):
        user=self.prepare()
        one=duty.save_person(user,{'full_name':'範例員工01','effective_from':'2026-01-01'})['person_id']
        two=duty.save_person(user,{'full_name':'範例員工02','effective_from':'2026-01-01'})['person_id']
        task=duty.save_task(user,{'name':'倒垃圾','effective_from':'2026-01-01','items':[
            {'content':'打包垃圾並去倒垃圾','frequency':'weekly','weekdays':[0,3],'reminder_time':'16:00','reminder_enabled':True},
            {'content':'打包至一樓集中，等週一一起丟','frequency':'weekly','weekdays':[4],'reminder_time':'17:00','reminder_enabled':True}]})['task_id']
        return user,one,two,task

    def config(self,user,**changes):
        with patch.object(automation,'rebuild'):
            automation.save_settings(user,{'channel_id':'primary','expected_revision':automation.settings_view(user)['revision'],'config':{**automation.defaults(),'personal':True,**changes}})

    def subscribe(self,user,person):
        duty.save_binding(user,{'person_id':person,'channel_id':'primary','recipient_id':roles.CONTACT_USER})
        with app.database_connection() as conn:
            conn.execute('INSERT INTO duty_subscriptions VALUES (?,?,?,?,1,?)',(user['organization_id'],'primary',person,roles.CONTACT_USER,duty.now()))

    def publish(self,user,person,start='2026-10-01',end='2026-10-31',**extra):
        r=duty.create_draft(user,{'name':start,'period_type':'month','date_from':start,'date_to':end})['roster_id']
        record=duty.get_roster(user,r)
        for a in record['assignments']:a['person_ids']=[person]
        duty.save_draft(user,{'roster_id':r,'expected_updated_at':record['updated_at'],'assignments':record['assignments']})
        record=duty.get_roster(user,r)
        with patch.object(automation,'rebuild'):
            duty.publish_roster(user,{'roster_id':r,'expected_updated_at':record['updated_at'],'acknowledged':[c['key'] for c in record['checks']['warnings']],**extra})
        return r

    def test_settings_scope_change_confirmation_invalidates_bindings(self):
        user,one,_,_=self.environment();self.config(user);self.subscribe(user,one)
        self.assertEqual(duty.notification_oa(user['organization_id']),'primary')
        self.assertTrue(automation.settings_view(user)['channels'])
        payload={'channel_id':'','expected_revision':1,'config':automation.defaults()}
        with self.assertRaises(ValueError):automation.save_settings(user,payload)
        impacts=automation.settings_impacts(user)
        with patch.object(automation,'rebuild'):
            automation.save_settings(user,{**payload,'confirm_channel_change':True,'impacts':impacts,'reason':'停止使用'})
        self.assertFalse(duty.list_people(user)['people'][0]['bindings'])
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT subscribed FROM duty_subscriptions').fetchone()[0],0)
        with self.assertRaises(PermissionError):automation.save_settings(reports.account(roles.SENDER),payload)
        with self.assertRaises(PermissionError):automation.save_settings(user,{**payload,'org_id':roles.ORG_B})

    def test_reminder_weekdays_friday_and_cross_month_responsibility(self):
        user,one,two,task=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one)
        self.publish(user,one);self.publish(user,two,'2026-11-01','2026-11-30')
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            friday=automation.plans(conn,user['organization_id'],date(2026,10,30))
            self.assertEqual(friday['messages'][0]['time'],'17:00')
            self.assertIn('一樓集中',friday['messages'][0]['message'])
            monday=automation.plans(conn,user['organization_id'],date(2026,11,2))
            self.assertFalse(monday['messages']);self.assertEqual(monday['missing'][0]['person_id'],two)
            self.assertFalse(automation.plans(conn,user['organization_id'],date(2026,10,7))['messages'])

    def test_merge_daily_weekly_exclusions_and_missing_annual_time(self):
        user,one,_,task=self.environment();self.config(user,reminders_enabled=True,default_time='09:00');self.subscribe(user,one)
        current=duty.list_tasks(user)['tasks'][0]
        duty.save_task(user,{'task_id':task,'expected_updated_at':current['updated_at'],'name':'掃地','effective_from':'2026-01-01','items':[
            {'content':'掃地','frequency':'daily','reminder_enabled':True},
            {'content':'拖地','frequency':'weekly','weekdays':[1],'reminder_enabled':True},
            {'content':'年度消毒','frequency':'annual','reminder_enabled':True}]})
        self.publish(user,one)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            plan=automation.plans(conn,user['organization_id'],date(2026,10,6))
            self.assertEqual(len(plan['messages']),1);self.assertIn('拖地',plan['messages'][0]['message']);self.assertNotIn('年度消毒',plan['messages'][0]['message'])

    def test_notification_channels_are_selected_per_kind(self):
        user,one,_,_=self.environment()
        with self.assertRaises(ValueError):
            self.config(user,publish_enabled=True,type_channels={'publish':{'personal':False,'groups':False}})
        self.config(user,reminders_enabled=True,type_channels={
            'reminder':{'personal':True,'groups':False},
            'publish':{'personal':False,'groups':False}})
        self.subscribe(user,one);roster=self.publish(user,one)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            self.assertEqual(automation.plans(conn,user['organization_id'],date(2026,10,5))['push_count'],1)
            self.assertEqual(automation.plans(conn,user['organization_id'],date(2026,10,5),'publish',roster_id=roster)['push_count'],0)
        self.assertEqual(duty.notification_preview(user,roster)['push_count'],0)

    def queue(self,user,day=date(2026,10,5)):
        due=datetime(day.year,day.month,day.day,8,tzinfo=timezone.utc)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            result=automation.plans(conn,user['organization_id'],day)
            setting=automation.settings(conn,user['organization_id'])
            job=automation.enqueue(conn,user['organization_id'],setting,'reminder',result,due,user['email'])
            duplicate=automation.enqueue(conn,user['organization_id'],setting,'reminder',result,due,user['email'])
            self.assertEqual(job,duplicate)
            delivery=conn.execute('SELECT delivery_id FROM duty_notice_deliveries WHERE job_id=?',(job,)).fetchone()[0]
        return delivery,due

    def test_dispatch_dedup_fake_api_retry_unknown_and_restart(self):
        user,one,_,_=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one);self.publish(user,one)
        delivery,due=self.queue(user)
        with patch.object(channels:=(automation.channels),'access_token',return_value='fake'),patch.object(automation,'send_push',return_value='fake-request') as send:
            automation.dispatch(delivery,due);automation.dispatch(delivery,due)
            self.assertEqual(send.call_count,1)
        self.assertEqual(automation.notice_log(user)['deliveries'][0]['status'],'accepted')
        with app.database_connection() as conn:conn.execute("UPDATE duty_notice_deliveries SET status='sending' WHERE delivery_id=?",(delivery,))
        automation.recover()
        with patch.object(automation,'send_push') as send:automation.dispatch(delivery,due);send.assert_not_called()
        with self.assertRaises(ValueError):automation.notice_action(user,{'delivery_id':delivery,'expected_status':'unknown','action':'retry','confirm':True,'reason':'check'})
        automation.notice_action(user,{'delivery_id':delivery,'expected_status':'unknown','action':'confirm_received','reason':'已向本人確認'})

    def test_expired_disabled_unsubscribed_and_revoked_cancel(self):
        user,one,_,_=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one);self.publish(user,one)
        delivery,due=self.queue(user)
        with patch.object(automation,'send_push') as send:
            automation.dispatch(delivery,due+timedelta(minutes=1));send.assert_not_called()
        self.assertIn('逾期',automation.notice_log(user)['deliveries'][0]['error'])
        for sql in ("UPDATE duty_subscriptions SET subscribed=0","UPDATE organizations SET duty_enabled=0","UPDATE line_channels SET active=0"):
            with app.database_connection() as conn:
                conn.execute("UPDATE duty_notice_deliveries SET status='pending' WHERE delivery_id=?",(delivery,));conn.execute(sql)
            with patch.object(automation,'send_push') as send:automation.dispatch(delivery,due);send.assert_not_called()

    def test_republish_cancels_old_pending_keeps_accepted_history(self):
        user,one,two,_=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one);old=self.publish(user,one)
        delivery,due=self.queue(user)
        self.publish(user,two,reason='調整人員')
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT status FROM duty_notice_deliveries WHERE delivery_id=?',(delivery,)).fetchone()[0],'cancelled')
            self.assertEqual(conn.execute('SELECT status FROM duty_rosters WHERE roster_id=?',(old,)).fetchone()[0],'replaced')

    def test_monthly_all_staff_unpublished_and_unsubscribed_missing(self):
        user,one,two,_=self.environment();self.config(user,monthly_enabled=True);self.subscribe(user,one)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            self.assertIn('未完成',automation.plans(conn,user['organization_id'],date(2026,10,1),'monthly')['missing'][0]['reason'])
        self.publish(user,one)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            plan=automation.plans(conn,user['organization_id'],date(2026,10,1),'monthly')
            self.assertEqual(len(plan['messages']),1);self.assertEqual(plan['missing'][0]['person_id'],two)

    def rule(self,user,automatic=False):
        people=duty.list_people(user);task=duty.list_tasks(user)['tasks'][0]
        payload={'period_type':'month','target_date':'2026-01-01','effective_from':'2026-01-01','automatic':automatic,'expected_version':0,'config':{'baseline_date':'2026-01-01','boundary':1,'year_month':1,'direction':1,'step':1,'position_ids':[p['position_id'] for p in people['positions']],'task_ids':[task['task_id']]}}
        preview=automation.rule_preview(user,payload)
        result=automation.save_rule(user,{**payload,'signature':preview['signature'],'confirm_automatic':automatic})
        return payload,result

    def test_rotation_three_periods_fixed_boundary_and_idempotent_apply(self):
        user,one,two,_=self.environment();payload,_=self.rule(user)
        preview=automation.rule_preview(user,payload)
        self.assertEqual(len(preview['periods']),3)
        self.assertEqual(preview['periods'][0]['assignments'][0]['person_ids'],[one])
        self.assertEqual(preview['periods'][1]['assignments'][0]['person_ids'],[two])
        r=duty.create_draft(user,{'name':'2月','period_type':'month','date_from':'2026-02-01','date_to':'2026-02-28'})['roster_id']
        for _ in range(2):
            changes=automation.apply_rule(user,{'roster_id':r})
            automation.apply_rule(user,{'roster_id':r,'confirm':True,'signature':changes['signature']})
        self.assertEqual(duty.get_roster(user,r)['assignments'][0]['person_ids'],[two])
        config={**payload['config'],'fixed':{payload['config']['task_ids'][0]:payload['config']['position_ids'][0]}}
        fixed=automation.rule_preview(user,{**payload,'config':config})
        self.assertTrue(all(p['assignments'][0]['person_ids']==[one] for p in fixed['periods']))

    def test_rotation_vacancy_effective_replacement_and_rule_versions(self):
        user,one,two,_=self.environment();payload,result=self.rule(user)
        duty.remove_resource(user,{'kind':'person','id':two})
        previews=automation.rule_preview(user,payload)
        self.assertFalse(previews['periods'][1]['assignments'][0]['person_ids'])
        newer=automation.save_rule(user,{**payload,'expected_version':1,'effective_from':'2026-02-01','reason':'空缺處理'})
        self.assertEqual(newer['version'],2)
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            self.assertEqual(automation.rule_for(conn,user['organization_id'],'month','2026-01-01')['version'],1)

    def test_automatic_confirmation_publish_once_and_missing_keeps_draft(self):
        user,one,two,_=self.environment();payload,result=self.rule(user,True)
        now=datetime(2026,2,1,0,tzinfo=timezone.utc)
        with patch.object(automation,'rebuild'):
            automation.auto_rotate(user['organization_id'],now);automation.auto_rotate(user['organization_id'],now)
        rows=duty.roster_rows(user)['rosters'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'published')
        duty.remove_resource(user,{'kind':'person','id':one,'effective_from':'2026-03-01','reason':'離職','confirm_impacts':True,'impacts':duty.list_people(user)['people'][0]['impacts']})
        with patch.object(automation,'rebuild'):automation.auto_rotate(user['organization_id'],datetime(2026,3,1,0,tzinfo=timezone.utc))
        self.assertEqual(duty.roster_rows(user)['rosters'][0]['status'],'draft')

    def test_week_year_boundaries_and_invalid_scope(self):
        user,_,_,_=self.environment();config={'boundary':0,'year_month':1}
        self.assertEqual(automation.period_bounds(config,'week',date(2026,10,6))[0],date(2026,10,5))
        self.assertEqual(automation.period_bounds({**config,'boundary':1},'year',date(2026,10,6)),(date(2026,1,1),date(2026,12,31)))
        with self.assertRaises(PermissionError):automation.rule_rows({**user,'organization_id':roles.ORG_B})
        with self.assertRaises(PermissionError):automation.save_rule(user,{'org_id':roles.ORG_B},preview=True)
        self.assertEqual(automation.period_bounds({'boundary':31,'year_month':1},'month',date(2026,2,28))[0],date(2026,2,28))

    def test_manual_idempotence_fake_failure_retry_and_unknown(self):
        user,one,_,_=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one);roster=self.publish(user,one)
        payload={'kind':'test','date':'2026-10-05','roster_id':roster,'person_ids':[one]}
        preview=automation.notice_preview(user,payload)
        request={**payload,'confirm':True,'signature':preview['signature'],'request_id':'00000000-0000-4000-8000-000000000001'}
        job=automation.manual_notice(user,request)
        self.assertEqual(automation.manual_notice(user,request),job)
        with app.database_connection() as conn:delivery=conn.execute('SELECT delivery_id FROM duty_notice_deliveries WHERE job_id=?',(job['job_id'],)).fetchone()[0]
        with patch.object(automation.channels,'access_token',return_value='fake'),patch.object(automation,'send_push',side_effect=ValueError('LINE 拒絕 HTTP 400')):
            automation.dispatch(delivery)
        self.assertEqual(automation.notice_log(user)['deliveries'][0]['status'],'failed')
        retry={'delivery_id':delivery,'expected_status':'failed','action':'retry','confirm':True,'reason':'檢查完成','request_id':'00000000-0000-4000-8000-000000000002'}
        automation.notice_action(user,retry);automation.notice_action(user,retry)
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM duty_notice_jobs').fetchone()[0],2)
        next_delivery=next(r['delivery_id'] for r in automation.notice_log(user)['deliveries'] if r['status']=='pending')
        with patch.object(automation.channels,'access_token',return_value='fake'),patch.object(automation,'send_push',side_effect=ValueError('連線中斷，結果不明')) as send:
            automation.dispatch(next_delivery);automation.dispatch(next_delivery);self.assertEqual(send.call_count,1)
        self.assertTrue(any(r['status']=='unknown' for r in automation.notice_log(user)['deliveries']))

    def test_queue_rechecks_actor_grant_and_monthly_disabled_person(self):
        user,one,_,_=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one);self.publish(user,one)
        duty.grant(user,{'email':roles.SENDER,'duty_manager':True})
        operator=reports.account(roles.SENDER)
        self.config(operator,reminders_enabled=True)
        delivery,due=self.queue(operator)
        duty.grant(user,{'email':roles.SENDER,'duty_manager':False})
        with patch.object(automation,'send_push') as send:automation.dispatch(delivery,due);send.assert_not_called()
        with app.database_connection() as conn:
            conn.row_factory=__import__('sqlite3').Row
            conn.execute('UPDATE duty_people SET active=0 WHERE person_id=?',(one,))
            plan=automation.plans(conn,user['organization_id'],date(2026,10,1),'monthly')
            self.assertFalse(plan['messages']);self.assertIn('未完成',plan['missing'][0]['reason'])

    def test_trash_shortcut_shared_task_version_and_pending_rebuild(self):
        user,one,_,task=self.environment();self.config(user,reminders_enabled=True);self.subscribe(user,one)
        before=duty.list_tasks(user)['tasks'][0]
        automation.save_trash(user,{'task_id':task,'expected_updated_at':before['updated_at'],'effective_from':'2026-01-01','times':['15:30','16:10','17:20']})
        items=duty.list_tasks(user)['tasks'][0]['versions'][0]['items']
        self.assertEqual([i['weekdays'] for i in items],[[0],[3],[4]])
        self.assertEqual([i['reminder_time'] for i in items],['15:30','16:10','17:20'])
        self.publish(user,one)
        at=datetime(2026,10,5,0,tzinfo=timezone.utc)
        automation.rebuild(user['organization_id'],at)
        with app.database_connection() as conn:
            initial=conn.execute('SELECT COUNT(*) FROM duty_notice_jobs').fetchone()[0]
        automation.rebuild(user['organization_id'],at)
        with app.database_connection() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM duty_notice_jobs').fetchone()[0],initial)

"""Duty notification queue and deterministic, versioned rotation rules."""
import calendar
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import app
import channels
import duty
import limits
import reports
from send_image import send_push


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def clock_time(value,optional=True):
    if not isinstance(value,str) or not (optional and not value or re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value)):
        raise ValueError('時間請填 HH:MM。')
    return value


def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'數值須介於 {low}–{high}。')
    return value


def defaults():
    return {'monthly_enabled':False,'monthly_time':'08:30','personal':False,'groups':[],
            'reminders_enabled':False,'default_time':'','advance_days':0,
            'publish_enabled':False,'change_enabled':False,'catchup_minutes':0,'type_channels':{}}


def settings(conn,org_id):
    conn.row_factory=sqlite3.Row
    row=conn.execute('SELECT * FROM duty_notice_settings WHERE org_id=?',(org_id,)).fetchone()
    return {**dict(row),'config':{**defaults(),**json.loads(row['config'])}} if row else {'org_id':org_id,'channel_id':'','revision':0,'actor':'','updated_at':'','config':defaults()}


def settings_view(user):
    org_id=duty.managed_org(user,read=True)
    with app.database_connection() as conn:
        result=settings(conn,org_id)
        result['channels']=[dict(r) for r in conn.execute('SELECT channel_id,name FROM line_channels WHERE org_id=? AND active=1',(org_id,))]
        result['groups']=[dict(r) for r in conn.execute("SELECT recipient_id,display_name,custom_name FROM recipients WHERE channel_id=? AND organization_id=? AND active=1 AND kind IN ('group','room')",(result['channel_id'],org_id))]
        result['subscribed']=conn.execute('SELECT COUNT(*) FROM duty_subscriptions WHERE org_id=? AND channel_id=? AND subscribed=1',(org_id,result['channel_id'])).fetchone()[0]
        result['estimate']=monthly_estimate(conn,org_id)
        return result


def save_settings(user,payload,*,preview=False):
    org_id=duty.authorize(user,'notify_settings',organization_id=payload.get('org_id'),preview=preview)
    config=payload.get('config')
    if not isinstance(config,dict) or set(config)-set(defaults()):raise ValueError('通知設定格式不正確。')
    config={**defaults(),**config}
    for key in ('monthly_enabled','personal','reminders_enabled','publish_enabled','change_enabled'):
        config[key]=bool(duty.flag(config,key))
    modes=config['type_channels']
    if not isinstance(modes,dict) or set(modes)-{'monthly','reminder','publish','change'}:raise ValueError('各類通知管道不正確。')
    for mode in modes.values():
        if not isinstance(mode,dict) or set(mode)!={'personal','groups'} or any(type(v) is not bool for v in mode.values()):raise ValueError('各類通知管道必須為個人／群組的啟用值。')
    for kind,key in (('monthly','monthly_enabled'),('reminder','reminders_enabled'),('publish','publish_enabled'),('change','change_enabled')):
        mode=modes.get(kind,{'personal':config['personal'],'groups':bool(config['groups'])})
        if config[key] and not (mode['personal'] and config['personal'] or mode['groups'] and config['groups']):raise ValueError('啟用每類通知前，請選擇可用的個人或群組管道。')
    clock_time(config['monthly_time'],False);clock_time(config['default_time'])
    integer(config['catchup_minutes'],0,limits.DUTY_NOTICE_CATCHUP_MAX_MINUTES)
    integer(config['advance_days'],0,limits.DUTY_NOTICE_HORIZON_DAYS)
    if not isinstance(config['groups'],list) or any(not isinstance(g,str) for g in config['groups']) or len(set(config['groups']))!=len(config['groups']):raise ValueError('群組設定不正確。')
    channel=payload.get('channel_id','')
    if not isinstance(channel,str):raise ValueError('通知 OA 不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old=settings(conn,org_id)
        if payload.get('expected_revision')!=old['revision']:raise ValueError('通知設定已更新，請重新載入。')
        if channel and not conn.execute('SELECT 1 FROM line_channels WHERE channel_id=? AND org_id=? AND active=1',(channel,org_id)).fetchone():raise ValueError('通知 OA 不屬於本組織或已停用。')
        if any(config[k] for k in ('monthly_enabled','reminders_enabled','publish_enabled','change_enabled')) and (not channel or not config['personal'] and not config['groups']):raise ValueError('啟用通知前請指定 OA 與通知管道。')
        for group in config['groups']:
            if not conn.execute("SELECT 1 FROM recipients WHERE channel_id=? AND recipient_id=? AND organization_id=? AND kind IN ('group','room') AND active=1",(channel,group,org_id)).fetchone():raise ValueError('只能選擇通知 OA 的本組織有效群組。')
        if old['channel_id'] and old['channel_id']!=channel:
            impacts={'bindings':conn.execute('SELECT COUNT(*) FROM duty_person_bindings WHERE org_id=?',(org_id,)).fetchone()[0],
                     'pending':conn.execute("SELECT COUNT(*) FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE j.org_id=? AND d.status='pending'",(org_id,)).fetchone()[0]}
            if payload.get('confirm_channel_change') is not True or payload.get('impacts')!=impacts:raise ValueError('變更通知 OA 會解除 LINE 綁定及取消待發通知，請重新確認影響。')
            duty.text(payload,'reason',required=True,maximum=limits.DUTY_CONTENT_MAX)
            conn.execute('DELETE FROM duty_person_bindings WHERE org_id=?',(org_id,))
            conn.execute('UPDATE duty_subscriptions SET subscribed=0,updated_at=? WHERE org_id=?',(duty.now(),org_id))
        conn.execute("UPDATE duty_notice_deliveries SET status='cancelled',error='通知設定變更' WHERE status='pending' AND job_id IN (SELECT job_id FROM duty_notice_jobs WHERE org_id=?)",(org_id,))
        revision=old['revision']+1
        conn.execute('INSERT INTO duty_notice_settings VALUES (?,?,?,?,?,?) ON CONFLICT(org_id) DO UPDATE SET channel_id=excluded.channel_id,config=excluded.config,revision=excluded.revision,actor=excluded.actor,updated_at=excluded.updated_at',
                     (org_id,channel,encode(config),revision,user['email'],duty.now()))
        reports.audit(conn,user['email'],'duty.notice.settings',org_id,encode({'revision':revision,'channel':channel,'reason':payload.get('reason','')}),org_id)
    warning=safe_rebuild(org_id)
    return {'revision':revision,'warning':warning}


def settings_impacts(user):
    org=duty.managed_org(user,read=True)
    with app.database_connection() as conn:
        return {'bindings':conn.execute('SELECT COUNT(*) FROM duty_person_bindings WHERE org_id=?',(org,)).fetchone()[0],
                'pending':conn.execute("SELECT COUNT(*) FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE j.org_id=? AND d.status='pending'",(org,)).fetchone()[0]}


def active_org(conn,org_id):
    return bool(conn.execute('SELECT 1 FROM organizations WHERE org_id=? AND active=1 AND duty_enabled=1',(org_id,)).fetchone())


def staff_user(conn,org_id):
    row=conn.execute("SELECT email FROM organization_members WHERE org_id=? AND role='org_admin' AND active=1 ORDER BY email",(org_id,)).fetchall()
    return next((user for r in row if (user:=reports.account(r[0],org_id)) and duty.capabilities(user)['edit']),None)


def current_rosters(conn,org_id,day):
    conn.row_factory=sqlite3.Row
    return [dict(r) for r in conn.execute("SELECT * FROM duty_rosters WHERE org_id=? AND status='published' AND date_from<=? AND date_to>=? ORDER BY date_from DESC",(org_id,day,day))]


def assignments(conn,rosters):
    result={}
    for roster in rosters:
        for row in conn.execute('SELECT * FROM duty_assignments WHERE roster_id=?',(roster['roster_id'],)):
            item=dict(row);item['snapshot']=json.loads(item['snapshot']);item['person_ids']=json.loads(item['person_ids']);item['roster']=roster
            # The period that owns a rotation takes precedence over inherited copies.
            if item['task_id'] not in result or not item['snapshot'].get('inherited'):
                result[item['task_id']]=item
    return list(result.values())


def effective_people(conn,assignment,day):
    subs=[dict(s) for s in conn.execute('SELECT * FROM duty_substitutions WHERE assignment_id=? AND date_from<=? AND date_to>=?',(assignment['assignment_id'],day,day))]
    return [next((s['substitute_person_id'] for s in subs if s['original_person_id']==p),p) for p in assignment['person_ids']]


def person_target(conn,org,channel,person_id,*,test=False):
    person=conn.execute('SELECT * FROM duty_people WHERE org_id=? AND person_id=? AND active=1 AND deleted=0',(org,person_id)).fetchone()
    if not person:return None,'人員已停用'
    binding=conn.execute('SELECT recipient_id FROM duty_person_bindings WHERE org_id=? AND channel_id=? AND person_id=?',(org,channel,person_id)).fetchone()
    if not binding:return None,'未綁定通知 OA'
    recipient=conn.execute("SELECT * FROM recipients WHERE channel_id=? AND recipient_id=? AND organization_id=? AND active=1 AND kind='user'",(channel,binding[0],org)).fetchone()
    if not recipient:return None,'LINE 對象停用、封鎖或歸屬已變更'
    if not test and not conn.execute('SELECT 1 FROM duty_subscriptions WHERE org_id=? AND channel_id=? AND person_id=? AND recipient_id=? AND subscribed=1',(org,channel,person_id,binding[0])).fetchone():return None,'未訂閱值日生'
    return {'person_id':person_id,'recipient_id':binding[0],'kind':'user','label':person['full_name']},''


def matches(item,day):
    if day.isoformat() in item['excluded_dates']:return False
    frequency=item['frequency']
    return frequency=='daily' or frequency=='weekly' and day.weekday() in item['weekdays'] or frequency=='monthly' and item['day_start']<=day.day<=item['day_end'] or frequency=='annual' and item['annual_date']==day.strftime('%m-%d')


def plans(conn,org,day,kind='reminder',roster_id=None,task_ids=None,person_ids=None,test=False,at=None):
    setting=settings(conn,org);config=setting['config'];channel=setting['channel_id']
    mode=config['type_channels'].get(kind,{'personal':config['personal'],'groups':True})
    rosters=current_rosters(conn,org,day.isoformat())
    if roster_id:
        rosters=[dict(r) for r in conn.execute("SELECT * FROM duty_rosters WHERE org_id=? AND roster_id=? AND status='published'",(org,roster_id))]
    work=assignments(conn,rosters);missing=[];buckets={}
    all_people=[r[0] for r in conn.execute('SELECT person_id FROM duty_people WHERE org_id=? AND active=1 AND deleted=0',(org,))]
    all_notice=kind in ('monthly','publish','change','manual','test')
    if all_notice and not rosters:
        return {'messages':[],'missing':[{'name':'本期班表','reason':'當月班表未完成，尚無有效已發布班表'}],'push_count':0,'estimate_complete':False,'roster_ids':[]}
    if all_notice:
        targets=person_ids if person_ids is not None else all_people
        for person in targets:buckets.setdefault(at or 'now',{}).setdefault(person,[])
    for assignment in work:
        if task_ids is not None and assignment['task_id'] not in task_ids:continue
        snapshot=assignment['snapshot']
        if snapshot['kind']!='normal' and not all_notice:continue
        responsible=effective_people(conn,assignment,day.isoformat())
        if all_notice:
            pieces=[snapshot['name']]+[v for v in (snapshot.get('description'),snapshot.get('area')) if v]+[i['content'] for i in snapshot['items']]
            slots={at or 'now':pieces}
        else:
            slots={}
            for item in snapshot['items']:
                if not item['reminder_enabled'] or not matches(item,day):continue
                time=item['reminder_time'] or config['default_time']
                if time:slots.setdefault(time,[]).append(snapshot['name']+'：'+item['content']+('；'+snapshot['description'] if snapshot.get('description') else '')+('；範圍：'+snapshot['area'] if snapshot.get('area') else ''))
        for time,pieces in slots.items():
            for person in responsible:
                if person_ids is not None and person not in person_ids:continue
                if all_notice and person not in buckets.get(time,{}):continue
                buckets.setdefault(time,{}).setdefault(person,[]).append({'task_id':assignment['task_id'],'contents':pieces,'roster_id':assignment['roster']['roster_id'],'version':assignment['roster']['version']})
    invalid=False
    if kind=='monthly':
        for assignment in work:
            if assignment['snapshot']['kind']!='normal':continue
            if not conn.execute('SELECT 1 FROM duty_tasks WHERE org_id=? AND task_id=? AND active=1 AND deleted=0',(org,assignment['task_id'])).fetchone():invalid=True
            for p in effective_people(conn,assignment,day.isoformat()):
                if not conn.execute('SELECT 1 FROM duty_people WHERE org_id=? AND person_id=? AND active=1 AND deleted=0',(org,p)).fetchone():invalid=True
    if kind=='monthly' and (invalid or not any(r['period_type']=='month' and r['date_from'][:7]==day.isoformat()[:7] for r in rosters) or any(a['snapshot']['kind']=='normal' and not a['person_ids'] for a in work)):
        return {'messages':[],'missing':[{'name':'本期班表','reason':'當月班表未完成，不發送舊班表'}],'push_count':0,'estimate_complete':True,'roster_ids':[r['roster_id'] for r in rosters]}
    messages=[]
    for time,personal in buckets.items():
        group_lines=[]
        for person,items in personal.items():
            row=conn.execute('SELECT full_name FROM duty_people WHERE person_id=? AND org_id=? AND active=1 AND deleted=0',(person,org)).fetchone()
            if not row:
                missing.append({'name':person,'person_id':person,'reason':'人員已停用或離職，請重新分配班表'})
                continue
            label=row[0]
            heading={'monthly':'月初值日生班表','reminder':'值日生提醒','publish':'值日生班表發布','change':'班表異動','manual':'值日生通知','test':'測試'}[kind]
            body='\n'.join('；'.join(i['contents']) for i in items) or '本期沒有分配工作'
            versions='、'.join(sorted({a['roster']['name']+' v'+str(a['roster']['version']) for a in work if any(a['task_id']==i['task_id'] for i in items)}))
            message=f'【{heading}】{day.isoformat()}\n{versions}\n負責人：{label}\n{body}'
            group_lines.append(label+'：'+body)
            if config['personal'] and mode['personal'] or test:
                target,reason=person_target(conn,org,channel,person,test=test)
                if target:messages.append({**target,'time':time,'message':message,'task_ids':sorted({i['task_id'] for i in items}),'roster_ids':sorted({i['roster_id'] for i in items}) or [r['roster_id'] for r in rosters]})
                else:missing.append({'name':label,'person_id':person,'reason':reason})
        if not test and mode['groups']:
            for group in config['groups']:
                row=conn.execute("SELECT * FROM recipients WHERE channel_id=? AND recipient_id=? AND organization_id=? AND active=1 AND kind IN ('group','room')",(channel,group,org)).fetchone()
                if row:
                    messages.append({'recipient_id':group,'person_id':'','kind':row['kind'],'label':row['custom_name'] or row['display_name'] or '群組','time':time,'message':'【值日生公告】'+day.isoformat()+'\n'+'\n'.join(group_lines),'task_ids':sorted({i['task_id'] for items in personal.values() for i in items}),'roster_ids':[r['roster_id'] for r in rosters]})
    return {'messages':messages,'missing':missing,'times':list(buckets),'roster_ids':[r['roster_id'] for r in rosters],'push_count':sum(m['kind']=='user' for m in messages),'estimate_complete':not any(m['kind']!='user' for m in messages),'group_count':sum(m['kind']!='user' for m in messages)}


def notice_preview(user,payload):
    org=duty.authorize(user,organization_id=payload.get('org_id'))
    day=duty.checked_date(payload.get('date') or duty.today().isoformat())
    kind=payload.get('kind','manual')
    if kind not in ('monthly','reminder','publish','change','manual','test'):raise ValueError('通知類型不正確。')
    if not duty.capabilities(user)['edit']:
        raise PermissionError('沒有通知預覽權限。')
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        if payload.get('roster_id'):duty.get_roster(user,payload['roster_id'],conn=conn)
        for key,table,column in (('person_ids','duty_people','person_id'),('task_ids','duty_tasks','task_id')):
            if payload.get(key) is not None:
                if not isinstance(payload[key],list) or any(not isinstance(v,str) for v in payload[key]):raise ValueError('通知選擇格式不正確。')
                for value in payload[key]:duty.scoped(conn,table,column,value,org)
        result=plans(conn,org,day,kind,payload.get('roster_id'),payload.get('task_ids'),payload.get('person_ids'),kind=='test')
        result['signature']=digest([result,settings(conn,org)['revision']])
        return result


def monthly_estimate(conn,org):
    config=settings(conn,org)['config'];today=duty.today();known,groups,missing=0,0,0
    complete=True
    for number in range(1,calendar.monthrange(today.year,today.month)[1]+1):
        day=date(today.year,today.month,number)
        kinds=(['monthly'] if number==1 and config['monthly_enabled'] else [])+(['reminder'] if config['reminders_enabled'] else [])
        for kind in kinds:
            result=plans(conn,org,day,kind,at=config['monthly_time'] if kind=='monthly' else None)
            known+=result['push_count'];groups+=result.get('group_count',0);missing+=len(result['missing'])
            complete=complete and result.get('estimate_complete',True) and bool(result['roster_ids'])
    return {'month':today.isoformat()[:7],'personal_push':known,'group_requests':groups,'missing':missing,'complete':complete,'note':'只估自動公告與提醒；群組成員數未知、未發布期間及通知缺漏會使估算不完整。'}


def enqueue(conn,org,setting,kind,result,due,actor,event_token=''):
    rosters=[dict(r) for r in conn.execute('SELECT roster_id,name,version,status FROM duty_rosters WHERE org_id=? AND roster_id IN ('+','.join('?' for _ in result['roster_ids'])+')',(org,*result['roster_ids']))] if result['roster_ids'] else []
    key=digest([org,kind,event_token]) if kind in ('manual','test') and event_token else digest([org,kind,rosters,due.isoformat(),setting['revision']])
    existing=conn.execute('SELECT job_id FROM duty_notice_jobs WHERE event_key=?',(key,)).fetchone()
    if existing and kind in ('test','manual'):return existing[0]
    if existing:
        job_id=existing[0]
        if due>=datetime.now(timezone.utc):conn.execute('UPDATE duty_notice_jobs SET missing=? WHERE job_id=?',(encode(result['missing']),job_id))
    else:
        if conn.execute('SELECT COUNT(*) FROM duty_notice_jobs WHERE org_id=?',(org,)).fetchone()[0]>=limits.DUTY_NOTICE_JOBS_PER_ORG:raise ValueError('通知紀錄數量已達上限。')
        job_id=uuid4().hex
        expires=due+timedelta(minutes=setting['config']['catchup_minutes'])
        conn.execute('INSERT INTO duty_notice_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,org,key,kind,encode(rosters),due.isoformat(),expires.isoformat(),setting['channel_id'],setting['revision'],actor,encode(result['missing']),duty.now()))
    for target in result['messages']:
        # A settings edit must not cause a second accepted/uncertain request for the same event.
        prior=conn.execute("SELECT 1 FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE j.org_id=? AND j.kind=? AND j.scheduled_at=? AND j.roster_ids=? AND d.recipient_id=? AND d.status IN ('accepted','sending','unknown')",(org,kind,due.isoformat(),encode(rosters),target['recipient_id'])).fetchone()
        if prior and kind not in ('test','manual'):continue
        messages=split_text(target['message'])
        conn.execute('INSERT OR IGNORE INTO duty_notice_deliveries(delivery_id,job_id,recipient_id,person_id,kind,label,task_ids,message,retry_key) VALUES (?,?,?,?,?,?,?,?,?)',
                     (uuid4().hex,job_id,target['recipient_id'],target['person_id'],target['kind'],target['label'],encode(target['task_ids']),encode(messages),str(uuid4())))
    return job_id


def split_text(text):
    # LINE text length is measured in UTF-16 units. Keep a single persisted request.
    chunks=[];chunk='';units=0
    for character in text:
        size=len(character.encode('utf-16-le'))//2
        if units+size>limits.TEXT_MESSAGE_MAX:chunks.append({'type':'text','text':chunk});chunk='';units=0
        chunk+=character;units+=size
    if chunk:chunks.append({'type':'text','text':chunk})
    if len(chunks)>5:raise ValueError('通知內容過長，請縮小工作範圍。')
    return chunks


def manual_notice(user,payload,*,preview=False):
    org=duty.authorize(user,'send',organization_id=payload.get('org_id'),preview=preview)
    if payload.get('kind') not in ('manual','test'):raise ValueError('手動通知類型不正確。')
    if payload['kind']=='test' and len(payload.get('person_ids',[]))!=1:raise ValueError('試送請選一位已綁定人員。')
    result=notice_preview(user,payload)
    if payload.get('confirm') is not True or payload.get('signature')!=result['signature']:raise ValueError('通知內容或對象已變更，請重新預覽。')
    if not result['roster_ids'] or not result['messages']:raise ValueError('没有有效已發布班表或可發送對象。')
    request_id=payload.get('request_id')
    try:request_id=str(__import__('uuid').UUID(request_id))
    except (ValueError,TypeError,AttributeError):raise ValueError('請重新建立通知。') from None
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');setting=settings(conn,org)
        return {'job_id':enqueue(conn,org,setting,payload['kind'],result,datetime.now(timezone.utc),user['email'],request_id)}


def rebuild(org,now=None):
    now=now or datetime.now(timezone.utc);day=now.astimezone(duty.TAIPEI).date()
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');setting=settings(conn,org);config=setting['config']
        if not active_org(conn,org) or not setting['channel_id'] or not (config['monthly_enabled'] or config['reminders_enabled']):return
        user=reports.account(setting['actor'],org)
        if not user or not duty.capabilities(user)['notify_settings']:return
        for offset in range(limits.DUTY_NOTICE_HORIZON_DAYS):
            target_day=day+timedelta(days=offset)
            if config['monthly_enabled'] and target_day.day==1:
                result=plans(conn,org,target_day,'monthly',at=config['monthly_time'])
                due=datetime.fromisoformat(target_day.isoformat()+'T'+config['monthly_time']).replace(tzinfo=duty.TAIPEI).astimezone(timezone.utc)
                enqueue(conn,org,setting,'monthly',result,due,setting['actor'])
            if config['reminders_enabled']:
                result=plans(conn,org,target_day)
                for time in sorted(result.get('times',[])):
                    due=datetime.fromisoformat(target_day.isoformat()+'T'+time).replace(tzinfo=duty.TAIPEI).astimezone(timezone.utc)-timedelta(days=config['advance_days'])
                    subset={**result,'messages':[m for m in result['messages'] if m['time']==time]}
                    enqueue(conn,org,setting,'reminder',subset,due,setting['actor'])


def record_error(org,error):
    with app.database_connection() as conn:
        detail=duty.today().isoformat()+'｜'+str(error)
        previous=conn.execute("SELECT detail FROM audit_events WHERE organization_id=? AND action='duty.automation.error' ORDER BY event_id DESC LIMIT 1",(org,)).fetchone()
        if not previous or previous[0]!=detail:reports.audit(conn,'值日生排程','duty.automation.error',org,detail,org)


def safe_rebuild(org,now=None):
    try:rebuild(org,now);return ''
    except (ValueError,PermissionError) as exc:record_error(org,exc);return str(exc)


def on_publish(conn,user,roster_id,previous=None,send_now=False):
    org=user['organization_id'];setting=settings(conn,org)
    if previous:
        for job in conn.execute('SELECT job_id,roster_ids FROM duty_notice_jobs WHERE org_id=?',(org,)):
            if any(r['roster_id']==previous for r in json.loads(job['roster_ids'])):
                conn.execute("UPDATE duty_notice_deliveries SET status='cancelled',error='班表版本已被取代' WHERE job_id=? AND status='pending'",(job['job_id'],))
    kind='change' if previous else 'publish'
    if send_now:
        if not setting['channel_id'] or not setting['config'][kind+'_enabled']:raise ValueError('請先啟用對應的班表通知。')
        affected=None
        if previous:
            before=duty.get_roster(user,previous,conn=conn);after=duty.get_roster(user,roster_id,conn=conn)
            affected=set()
            def substitution_key(assignment):return [{k:s[k] for k in ('original_person_id','substitute_person_id','date_from','date_to')} for s in assignment['substitutions']]
            for assignment in after['assignments']:
                old=next((a for a in before['assignments'] if a['task_id']==assignment['task_id']),None)
                if not old or old['person_ids']!=assignment['person_ids'] or substitution_key(old)!=substitution_key(assignment) or old['note']!=assignment['note'] or old['snapshot']['version_id']!=assignment['snapshot']['version_id']:
                    affected.update(assignment['person_ids'])
                    if old:affected.update(old['person_ids'])
                    for source in ([old,assignment] if old else [assignment]):
                        affected.update(s['substitute_person_id'] for s in source['substitutions'])
            affected=sorted(affected)
        result=plans(conn,org,duty.today(),kind,roster_id=roster_id,person_ids=affected)
        if previous:
            before=duty.get_roster(user,previous,conn=conn)
            after=duty.get_roster(user,roster_id,conn=conn)
            old_people={p for a in before['assignments'] for p in a['person_ids']} & set(affected)
            new_people={m['person_id'] for m in result['messages']}
            for p in old_people-new_people:
                target,reason=person_target(conn,org,setting['channel_id'],p)
                if target and setting['config']['personal'] and setting['config']['type_channels'].get(kind,{'personal':True})['personal']:result['messages'].append({**target,'message':'【班表異動】'+after['name']+'\n原分配已變更，請查看新版班表。','task_ids':[],'roster_ids':[roster_id]})
                elif reason:result['missing'].append({'person_id':p,'name':p,'reason':reason})
            changes=json.loads(conn.execute("SELECT detail FROM audit_events WHERE target=? AND action='duty.roster.publish' ORDER BY event_id DESC LIMIT 1",(roster_id,)).fetchone()[0]).get('differences',[])
            summary='\n'.join(c['work']+'：原 '+c['before']+' → 新 '+c['after'] for c in changes)
            for message in result['messages']:message['message']+='\n異動：\n'+summary
        enqueue(conn,org,setting,kind,result,datetime.now(timezone.utc),user['email'])


def recover():
    with app.database_connection() as conn:
        conn.execute("UPDATE duty_notice_deliveries SET status='unknown',error='服務中斷，請先確認是否收到，不自動重送' WHERE status='sending'")
        conn.execute("UPDATE duty_rotation_runs SET status='blocked',error='自動發布時服務中斷，請檢查草稿後手動發布' WHERE status='ready'")


def delivery_valid(conn,job,delivery):
    org=job['org_id'];setting=settings(conn,org)
    if not active_org(conn,org) or setting['channel_id']!=job['channel_id'] or setting['revision']!=job['settings_revision']:return False,'組織或通知設定已失效'
    user=reports.account(job['actor'],org)
    if not user or not duty.capabilities(user)['send']:return False,'管理權已撤銷'
    if not conn.execute('SELECT 1 FROM line_channels WHERE org_id=? AND channel_id=? AND active=1',(org,job['channel_id'])).fetchone():return False,'通知 OA 已停用'
    for roster in json.loads(job['roster_ids']):
        if not conn.execute("SELECT 1 FROM duty_rosters WHERE org_id=? AND roster_id=? AND version=? AND status='published'",(org,roster['roster_id'],roster['version'])).fetchone():return False,'班表版本已失效'
    for task in json.loads(delivery['task_ids']):
        if not conn.execute('SELECT 1 FROM duty_tasks WHERE org_id=? AND task_id=? AND active=1 AND deleted=0',(org,task)).fetchone():return False,'工作已停用'
    kind=job['kind'];config=setting['config']
    if kind in ('monthly','reminder','publish','change') and not config[{'reminder':'reminders_enabled','monthly':'monthly_enabled','publish':'publish_enabled','change':'change_enabled'}[kind]]:return False,'通知已停用'
    mode=config['type_channels'].get(kind,{'personal':config['personal'],'groups':True})
    if kind!='test' and (delivery['kind']=='user' and not (mode['personal'] and config['personal']) or delivery['kind']!='user' and not mode['groups']):return False,'此類通知管道已停用'
    if delivery['kind']=='user':
        target,reason=person_target(conn,org,job['channel_id'],delivery['person_id'],test=kind=='test')
        if not target or target['recipient_id']!=delivery['recipient_id']:return False,reason or '綁定已變更'
    elif delivery['recipient_id'] not in config['groups'] or not conn.execute("SELECT 1 FROM recipients WHERE channel_id=? AND recipient_id=? AND organization_id=? AND active=1 AND kind IN ('group','room')",(job['channel_id'],delivery['recipient_id'],org)).fetchone():return False,'群組授權已失效'
    return True,''


def dispatch(delivery_id,now=None):
    now=now or datetime.now(timezone.utc)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');conn.row_factory=sqlite3.Row
        delivery=conn.execute('SELECT * FROM duty_notice_deliveries WHERE delivery_id=?',(delivery_id,)).fetchone()
        if not delivery or delivery['status']!='pending':return
        job=conn.execute('SELECT * FROM duty_notice_jobs WHERE job_id=?',(delivery['job_id'],)).fetchone()
        valid,reason=delivery_valid(conn,job,delivery)
        # Zero catch-up permits the scheduler's current minute, never a later minute.
        expired=now.replace(second=0,microsecond=0)>datetime.fromisoformat(job['expires_at'])
        if not valid or expired:
            conn.execute("UPDATE duty_notice_deliveries SET status='cancelled',error=? WHERE delivery_id=?",('逾期，未補發' if expired else reason,delivery_id));return
        conn.execute("UPDATE duty_notice_deliveries SET status='sending' WHERE delivery_id=? AND status='pending'",(delivery_id,))
    status,request,error='accepted','',''
    try:
        with channels.use(job['channel_id']):
            token=channels.access_token()
            if not token:raise ValueError('通知 OA 憑證未設定')
            request=send_push(token,delivery['recipient_id'],'',retry_key=delivery['retry_key'],messages=json.loads(delivery['message']))
    except ValueError as exc:
        error=str(exc);status='unknown' if '不明' in error else 'failed'
    except Exception:
        status,error='unknown','發送中斷，結果不明；請先確認收件人'
    with app.database_connection() as conn:
        row=conn.execute('SELECT attempts FROM duty_notice_deliveries WHERE delivery_id=?',(delivery_id,)).fetchone()
        attempts=json.loads(row[0])+[{'time':now.isoformat(),'status':status,'request_id':request,'error':error}]
        conn.execute('UPDATE duty_notice_deliveries SET status=?,request_id=?,error=?,attempts=? WHERE delivery_id=?',(status,request,error,encode(attempts),delivery_id))
        if status=='accepted':
            for index,message in enumerate(json.loads(delivery['message'])):
                conn.execute('''INSERT OR IGNORE INTO line_messages(channel_id,message_id,conversation_type,conversation_id,message_type,text_content,sent_at,received_at,direction,sent_by,send_method,delivery_status)
                    VALUES (?,?,?,?,'text',?,?,?,'outbound',?,'push','sent')''',
                    (job['channel_id'],'duty_'+delivery_id+'_'+str(index),delivery['kind'],delivery['recipient_id'],message['text'],now.isoformat(),now.isoformat(),job['actor']))


def notice_log(user,query=None):
    org=duty.authorize(user);query=query or {}
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        clauses=['j.org_id=?'];args=[org]
        for key,column in (('status','d.status'),('kind','j.kind'),('person_id','d.person_id')):
            if query.get(key):clauses.append(column+'=?');args.append(query[key])
        if query.get('from'):
            day=duty.checked_date(query['from']);clauses.append('j.scheduled_at>=?');args.append(datetime.combine(day,datetime.min.time(),duty.TAIPEI).astimezone(timezone.utc).isoformat())
        if query.get('to'):
            day=duty.checked_date(query['to'])+timedelta(days=1);clauses.append('j.scheduled_at<?');args.append(datetime.combine(day,datetime.min.time(),duty.TAIPEI).astimezone(timezone.utc).isoformat())
        rows=[dict(r) for r in conn.execute('SELECT d.*,j.kind AS notice_kind,j.scheduled_at,j.roster_ids,j.actor FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE '+' AND '.join(clauses)+' ORDER BY j.scheduled_at DESC LIMIT ?',(*args,limits.DUTY_NOTICE_PAGE_SIZE))]
        for row in rows:
            for key in ('task_ids','message','roster_ids','attempts'):row[key]=json.loads(row[key])
            row.pop('recipient_id',None);row.pop('retry_key',None)
        stats={r[0]:r[1] for r in conn.execute('SELECT d.status,COUNT(*) FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE j.org_id=? GROUP BY d.status',(org,))}
        missing=[]
        for row in conn.execute("SELECT scheduled_at,missing FROM duty_notice_jobs WHERE org_id=? AND kind='monthly' ORDER BY scheduled_at DESC,created_at DESC",(org,)):
            if row['scheduled_at']<=datetime.now(timezone.utc).isoformat():missing=json.loads(row['missing']);break
        errors=[dict(r) for r in conn.execute("SELECT created_at,detail FROM audit_events WHERE organization_id=? AND action='duty.automation.error' ORDER BY event_id DESC LIMIT ?",(org,limits.DUTY_NOTICE_PAGE_SIZE))]
        return {'deliveries':rows,'stats':stats,'missing':missing,'limit':limits.DUTY_NOTICE_PAGE_SIZE,'errors':errors}


def notice_action(user,payload,*,preview=False):
    org=duty.authorize(user,'send',organization_id=payload.get('org_id'),preview=preview)
    action=payload.get('action')
    if action not in ('retry','cancel','confirm_received','resend'):raise ValueError('通知操作不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT d.* FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE j.org_id=? AND d.delivery_id=?',(org,payload.get('delivery_id'))).fetchone()
        if not row or row['status']!=payload.get('expected_status'):raise ValueError('通知狀態已變更。')
        if action=='cancel' and row['status']=='pending':conn.execute("UPDATE duty_notice_deliveries SET status='cancelled',error='管理人員取消' WHERE delivery_id=?",(row['delivery_id'],))
        elif action=='confirm_received' and row['status']=='unknown':
            duty.text(payload,'reason',required=True,maximum=limits.DUTY_CONTENT_MAX)
            conn.execute("UPDATE duty_notice_deliveries SET status='accepted',error='收件人確認已收到' WHERE delivery_id=?",(row['delivery_id'],))
        elif action in ('retry','resend') and row['status']==('failed' if action=='retry' else 'unknown'):
            if payload.get('confirm') is not True:raise ValueError('請先檢查收件人與內容並確認。')
            duty.text(payload,'reason',required=True,maximum=limits.DUTY_CONTENT_MAX)
            try:request_id=str(__import__('uuid').UUID(payload.get('request_id')))
            except (ValueError,TypeError,AttributeError):raise ValueError('請重新開啟通知確認。') from None
            job=conn.execute('SELECT * FROM duty_notice_jobs WHERE job_id=?',(row['job_id'],)).fetchone()
            valid,reason=delivery_valid(conn,job,row)
            if not valid:raise ValueError(reason)
            # Preserve original history and enqueue a distinct, explicitly approved request.
            setting=settings(conn,org)
            target={'recipient_id':row['recipient_id'],'person_id':row['person_id'],'kind':row['kind'],'label':row['label'],'message':'\n'.join(m['text'] for m in json.loads(row['message'])),'task_ids':json.loads(row['task_ids'])}
            enqueue(conn,org,setting,'manual',{'roster_ids':[r['roster_id'] for r in json.loads(job['roster_ids'])],'missing':[],'messages':[target]},datetime.now(timezone.utc),user['email'],row['delivery_id']+action+request_id)
        else:raise ValueError('此狀態不可執行此操作。')
        reports.audit(conn,user['email'],'duty.notice.'+action,row['delivery_id'],payload.get('reason',''),org)
    return {'ok':True}


def rule_rows(user):
    org=duty.authorize(user)
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        rows=[dict(r) for r in conn.execute('SELECT * FROM duty_rotation_versions WHERE org_id=? ORDER BY period_type,version DESC',(org,))]
        for row in rows:row['config']=json.loads(row['config'])
        runs=[dict(r) for r in conn.execute('SELECT rr.* FROM duty_rotation_runs rr JOIN duty_rotation_versions v ON v.rule_version_id=rr.rule_version_id WHERE v.org_id=? ORDER BY rr.updated_at DESC LIMIT ?',(org,limits.DUTY_NOTICE_PAGE_SIZE))]
    return {'rules':rows,'runs':runs}


def rule_config(conn,org,payload):
    config=payload.get('config')
    if not isinstance(config,dict):raise ValueError('輪替規則格式不正確。')
    period=payload.get('period_type')
    if period not in ('week','month','year'):raise ValueError('輪換週期不正確。')
    baseline=duty.checked_date(config.get('baseline_date')).isoformat()
    boundary=integer(config.get('boundary',0 if period=='week' else 1),0 if period=='week' else 1,6 if period=='week' else 31)
    month=integer(config.get('year_month',1),1,12)
    step=integer(config.get('step',1),1,limits.DUTY_ROTATION_STEP_MAX)
    direction=config.get('direction',1)
    if type(direction) is not int or direction not in (-1,1):raise ValueError('輪換方向不正確。')
    positions=config.get('position_ids',[]);tasks=config.get('task_ids',[])
    if not isinstance(positions,list) or not positions or not all(isinstance(v,str) for v in positions) or len(set(positions))!=len(positions) or len(positions)>limits.DUTY_PEOPLE_PER_ORG:raise ValueError('請設定不重複的人員位置順序。')
    if not isinstance(tasks,list) or not tasks or not all(isinstance(v,str) for v in tasks) or len(set(tasks))!=len(tasks) or len(tasks)>limits.DUTY_TASKS_PER_ORG:raise ValueError('請設定不重複的工作順序。')
    for position in positions:duty.scoped(conn,'duty_positions','position_id',position,org)
    base=config.get('base',{});fixed=config.get('fixed',{})
    if not isinstance(base,dict) or not isinstance(fixed,dict) or set(base)-set(tasks) or set(fixed)-set(tasks):raise ValueError('基準或固定分配不正確。')
    for task in tasks:
        row=duty.scoped(conn,'duty_tasks','task_id',task,org)
        snapshot=duty.task_snapshot(conn,task,baseline)
        if not snapshot or snapshot['rotation'] not in (period,'fixed') or not row['active'] or row['deleted']:raise ValueError('工作尚未生效、已停用或輪換週期不符合。')
        if snapshot['rotation']=='fixed' and task not in fixed:raise ValueError('固定負責人的工作需指定固定位置。')
        if base.get(task,positions[tasks.index(task)%len(positions)]) not in positions or task in fixed and fixed[task] not in positions:raise ValueError('分配位置不在輪替順序中。')
    result={'baseline_date':baseline,'boundary':boundary,'year_month':month,'step':step,'direction':direction,'position_ids':positions,'task_ids':tasks,'base':{t:base.get(t,positions[i%len(positions)]) for i,t in enumerate(tasks)},'fixed':fixed}
    if period_bounds(result,period,duty.checked_date(baseline))[0].isoformat()!=baseline:raise ValueError('基準日期須為週期起始日。')
    return result


def period_bounds(config,period,day):
    boundary=config['boundary']
    def anchor(year,month):return date(year,month,min(boundary,calendar.monthrange(year,month)[1]))
    if period=='week':
        first=day-timedelta(days=(day.weekday()-boundary)%7);return first,first+timedelta(days=6)
    if period=='month':
        year,month=day.year,day.month
        if day<anchor(year,month):
            month-=1
            if month==0:year-=1;month=12
        first=anchor(year,month);next_year,next_month=(year+1,1) if month==12 else (year,month+1)
        return first,anchor(next_year,next_month)-timedelta(days=1)
    year=day.year;month=config['year_month']
    if day<anchor(year,month):year-=1
    first=anchor(year,month);return first,anchor(year+1,month)-timedelta(days=1)


def rotation_result(conn,org,period,config,target):
    first,last=period_bounds(config,period,target);baseline=duty.checked_date(config['baseline_date'])
    if first<baseline:raise ValueError('目標期間不可早於基準日期。')
    count=(first-baseline).days//7 if period=='week' else (first.year-baseline.year)*12+first.month-baseline.month if period=='month' else first.year-baseline.year
    positions=config['position_ids'];items=[];warnings=[]
    if len(positions)!=len(config['task_ids']):warnings.append('人員位置與工作數不一致，請檢查兼任及未分配工作。')
    for task in config['task_ids']:
        row=duty.scoped(conn,'duty_tasks','task_id',task,org);snapshot=duty.task_snapshot(conn,task,first.isoformat())
        if not row['active'] or row['deleted'] or not snapshot or snapshot['rotation'] not in (period,'fixed'):
            warnings.append('規則中的工作已停用或週期變更，請更新規則。');continue
        index=positions.index(config['base'][task]);position=config['fixed'].get(task) or positions[(index+config['direction']*config['step']*count)%len(positions)]
        people=conn.execute('''SELECT p.person_id,p.full_name FROM duty_position_members m JOIN duty_people p ON p.person_id=m.person_id
            WHERE m.position_id=? AND m.effective_from<=? AND (m.effective_to IS NULL OR m.effective_to>=?) AND p.org_id=? AND p.active=1 AND p.deleted=0''',(position,first.isoformat(),first.isoformat(),org)).fetchall()
        person=dict(people[0]) if len(people)==1 else None
        if not person:warnings.append(snapshot['name']+' 落在空缺位置，未分配。')
        items.append({'task_id':task,'work':snapshot['name'],'position_id':position,'person_ids':[person['person_id']] if person else [],'name':person['full_name'] if person else '未分配','kind':snapshot['kind']})
    covered={i['task_id'] for i in items}
    for row in conn.execute('SELECT task_id FROM duty_tasks WHERE org_id=? AND active=1 AND deleted=0',(org,)):
        snapshot=duty.task_snapshot(conn,row['task_id'],first.isoformat())
        if snapshot and snapshot['rotation'] in (period,'fixed') and snapshot['kind']=='normal' and row['task_id'] not in covered:warnings.append(snapshot['name']+' 尚未納入規則。')
    return {'date_from':first.isoformat(),'date_to':last.isoformat(),'assignments':items,'warnings':warnings}


def rule_preview(user,payload):
    org=duty.managed_org(user,payload,read=True)
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        config=rule_config(conn,org,payload);period=payload['period_type']
        target=duty.checked_date(payload.get('target_date')) if payload.get('target_date') else max(duty.today(),duty.checked_date(payload.get('effective_from') or config['baseline_date']),duty.checked_date(config['baseline_date']))
        results=[]
        for _ in range(limits.DUTY_ROTATION_PREVIEW_PERIODS):
            result=rotation_result(conn,org,period,config,target);results.append(result);target=duty.checked_date(result['date_to'])+timedelta(days=1)
        setting=settings(conn,org);scope={'channel_id':setting['channel_id'],'monthly_enabled':setting['config']['monthly_enabled'],'time':setting['config']['monthly_time'],'personal':setting['config']['personal'],'groups':setting['config']['groups'],'revision':setting['revision'],'messages':[],'missing':[]}
        mode=setting['config']['type_channels'].get('monthly',{'personal':True,'groups':True})
        scope['personal']=scope['personal'] and mode['personal']
        if not mode['groups']:scope['groups']=[]
        for person in conn.execute('SELECT person_id,full_name FROM duty_people WHERE org_id=? AND active=1 AND deleted=0',(org,)):
            responsible=[i['work'] for i in results[0]['assignments'] if person['person_id'] in i['person_ids']]
            scope['messages'].append({'name':person['full_name'],'text':'【月初值日生班表】'+results[0]['date_from']+'\n負責人：'+person['full_name']+'\n'+('、'.join(responsible) or '此規則沒有分配工作')})
            _,reason=person_target(conn,org,setting['channel_id'],person['person_id'])
            if reason:scope['missing'].append({'name':person['full_name'],'reason':reason})
        return {'periods':results,'notice_scope':scope,'signature':digest([org,period,config,results,scope])}


def save_rule(user,payload,*,preview=False):
    org=duty.authorize(user,'edit',organization_id=payload.get('org_id'),preview=preview)
    effective=duty.checked_date(payload.get('effective_from')).isoformat();automatic=bool(duty.flag(payload,'automatic'))
    previewed=rule_preview(user,payload)
    if automatic and (payload.get('confirm_automatic') is not True or payload.get('signature')!=previewed['signature']):raise ValueError('啟用自動輪換前請確認接下來三期、全員通知範圍與內容。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');conn.row_factory=sqlite3.Row;config=rule_config(conn,org,payload)
        latest=conn.execute('SELECT * FROM duty_rotation_versions WHERE org_id=? AND period_type=? ORDER BY version DESC LIMIT 1',(org,payload['period_type'])).fetchone()
        if payload.get('expected_version',0)!=(latest['version'] if latest else 0):raise ValueError('規則已更新，請重新載入。')
        if latest:
            duty.text(payload,'reason',required=True,maximum=limits.DUTY_CONTENT_MAX)
            if effective<latest['effective_from']:raise ValueError('新版生效日不可早於舊版。')
        if effective<config['baseline_date']:raise ValueError('生效日不可早於基準日期。')
        version=latest['version']+1 if latest else 1;rule=uuid4().hex
        conn.execute('INSERT INTO duty_rotation_versions VALUES (?,?,?,?,?,?,?,?,?)',(rule,org,payload['period_type'],version,effective,encode(config),automatic,user['email'],duty.now()))
        reports.audit(conn,user['email'],'duty.rotation.save',rule,encode({'version':version,'effective_from':effective,'automatic':automatic,'reason':payload.get('reason','')}),org)
    return {'rule_version_id':rule,'version':version}


def rule_for(conn,org,period,day):
    row=conn.execute('SELECT * FROM duty_rotation_versions WHERE org_id=? AND period_type=? AND effective_from<=? ORDER BY effective_from DESC,version DESC LIMIT 1',(org,period,day)).fetchone()
    return {**dict(row),'config':json.loads(row['config'])} if row else None


def apply_rule(user,payload,*,preview=False):
    org=duty.authorize(user,'edit',organization_id=payload.get('org_id'),preview=preview)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');conn.row_factory=sqlite3.Row
        roster=duty.get_roster(user,payload.get('roster_id'),conn=conn)
        if roster['status']!='draft':raise ValueError('只能套用到草稿。')
        rule=rule_for(conn,org,roster['period_type'],roster['date_from'])
        if not rule:raise ValueError('本期間尚無生效輪替規則。')
        result=rotation_result(conn,org,roster['period_type'],rule['config'],duty.checked_date(roster['date_from']))
        if result['date_from']!=roster['date_from'] or result['date_to']!=roster['date_to']:raise ValueError('草稿期間與規則邊界不同。')
        differences=[]
        for item in result['assignments']:
            assignment=next((a for a in roster['assignments'] if a['task_id']==item['task_id'] and not a['snapshot'].get('inherited')),None)
            if assignment and assignment['person_ids']!=item['person_ids']:
                differences.append({'task_id':item['task_id'],'work':item['work'],'before':assignment['person_ids'],'after':item['person_ids'],'name':item['name']})
        signature=digest([rule['rule_version_id'],roster['updated_at'],result,differences])
        if payload.get('confirm') is True:
            if payload.get('signature')!=signature:raise ValueError('規則或草稿已更新，請重新預覽差異。')
            for item in result['assignments']:
                assignment=next((a for a in roster['assignments'] if a['task_id']==item['task_id'] and not a['snapshot'].get('inherited')),None)
                if assignment:assignment['person_ids']=item['person_ids'];assignment['substitutions']=[]
            duty.save_draft(user,{'roster_id':roster['roster_id'],'expected_updated_at':roster['updated_at'],'assignments':roster['assignments']},conn=conn)
            reports.audit(conn,user['email'],'duty.rotation.apply',roster['roster_id'],encode(differences),org)
        return {'differences':differences,'warnings':result['warnings'],'signature':signature}


def auto_rotate(org,now):
    day=now.astimezone(duty.TAIPEI).date()
    # Annual precedes monthly; monthly precedes weekly, for inherited assignments.
    for period in ('year','month','week'):
        with app.database_connection() as conn:
            conn.execute('BEGIN IMMEDIATE');conn.row_factory=sqlite3.Row
            if not active_org(conn,org):return
            rule=rule_for(conn,org,period,day.isoformat())
            if not rule or not rule['automatic']:continue
            user=reports.account(rule['actor'],org)
            if not user or not duty.capabilities(user)['publish']:continue
            first,last=period_bounds(rule['config'],period,day)
            if first.isoformat()<rule['effective_from']:continue
            if conn.execute('SELECT 1 FROM duty_rotation_runs WHERE rule_version_id=? AND date_from=?',(rule['rule_version_id'],first.isoformat())).fetchone():continue
            if conn.execute("SELECT 1 FROM duty_rosters WHERE org_id=? AND date_from=? AND date_to=? AND status IN ('draft','published')",(org,first.isoformat(),last.isoformat())).fetchone():
                conn.execute('INSERT INTO duty_rotation_runs VALUES (?,?,?,?,?,?)',(rule['rule_version_id'],first.isoformat(),'','blocked','既有草稿或正式班表，保留人工分配',duty.now()));continue
            result=rotation_result(conn,org,period,rule['config'],first)
            record=duty.create_draft(user,{'name':first.isoformat()+' 自動輪換','period_type':period,'date_from':first.isoformat(),'date_to':last.isoformat()},conn=conn)
            roster=duty.get_roster(user,record['roster_id'],conn=conn)
            for item in result['assignments']:
                assignment=next((a for a in roster['assignments'] if a['task_id']==item['task_id'] and not a['snapshot'].get('inherited')),None)
                if assignment:assignment['person_ids']=item['person_ids']
            duty.save_draft(user,{'roster_id':roster['roster_id'],'expected_updated_at':roster['updated_at'],'assignments':roster['assignments']},conn=conn)
            roster=duty.get_roster(user,roster['roster_id'],conn=conn)
            incomplete=any(a['snapshot']['kind']=='normal' and not a['person_ids'] and (period=='month' or not a['snapshot'].get('inherited')) for a in roster['assignments'])
            serious=[w for w in result['warnings'] if '數不一致' not in w]
            status='blocked' if serious or roster['checks']['blocking'] or incomplete else 'ready'
            error='；'.join(result['warnings']+[c['message'] for c in roster['checks']['blocking']]) or ('有未分配工作，請檢查草稿' if incomplete else '')
            conn.execute('INSERT INTO duty_rotation_runs VALUES (?,?,?,?,?,?)',(rule['rule_version_id'],first.isoformat(),roster['roster_id'],status,error,duty.now()))
        if status=='ready':
            # No open write transaction when calling publish.
            try:
                latest=duty.get_roster(user,roster['roster_id'])
                duty.publish_roster(user,{'roster_id':latest['roster_id'],'expected_updated_at':latest['updated_at'],'acknowledged':[c['key'] for c in latest['checks']['warnings']],'send_now':False,'reason':'已確認規則的自動輪換'})
                with app.database_connection() as conn:conn.execute("UPDATE duty_rotation_runs SET status='published',updated_at=? WHERE rule_version_id=? AND date_from=?",(duty.now(),rule['rule_version_id'],first.isoformat()))
            except (ValueError,PermissionError) as exc:
                with app.database_connection() as conn:conn.execute("UPDATE duty_rotation_runs SET status='blocked',error=?,updated_at=? WHERE rule_version_id=? AND date_from=?",(str(exc),duty.now(),rule['rule_version_id'],first.isoformat()))


_planned_minutes={}


def tick(now=None,closing=None):
    now=now or datetime.now(timezone.utc)
    if closing and closing.is_set():return
    with app.database_connection() as conn:
        orgs=[r[0] for r in conn.execute('SELECT org_id FROM organizations WHERE active=1 AND duty_enabled=1')]
    for org in orgs:
        if closing and closing.is_set():return
        key=(str(app.DATABASE_PATH),org);minute=now.replace(second=0,microsecond=0).isoformat()
        if _planned_minutes.get(key)!=minute:
            try:auto_rotate(org,now)
            except (ValueError,PermissionError) as exc:record_error(org,exc)
            safe_rebuild(org,now)
            _planned_minutes[key]=minute
    with app.database_connection() as conn:
        due=[r[0] for r in conn.execute("SELECT d.delivery_id FROM duty_notice_deliveries d JOIN duty_notice_jobs j ON j.job_id=d.job_id WHERE d.status='pending' AND j.scheduled_at<=? ORDER BY j.scheduled_at LIMIT ?",(now.isoformat(),limits.DUTY_NOTICE_PAGE_SIZE))]
    for delivery in due:
        if closing and closing.is_set():return
        dispatch(delivery,now)


def save_trash(user,payload,*,preview=False):
    duty.authorize(user,'notify_settings',organization_id=payload.get('org_id'),preview=preview)
    task=next((t for t in duty.list_tasks(user)['tasks'] if t['task_id']==payload.get('task_id')),None)
    if not task or not task['active']:raise ValueError('請選擇啟用的倒垃圾工作。')
    if task['updated_at']!=payload.get('expected_updated_at'):raise ValueError('工作已變更，請重新整理。')
    values=payload.get('times')
    if not isinstance(values,list) or len(values)!=3:raise ValueError('請設定週一、週四及週五時間。')
    for value in values:clock_time(value)
    data=task['versions'][0]
    # These are shortcuts to the task's real weekly execution items, never a second reminder store.
    items=[i for i in data['items'] if not(i['frequency']=='weekly' and i['weekdays'] in ([0],[3],[4],[0,3]))]
    for weekday,time,content in zip((0,3,4),values,('打包垃圾，然後拿去倒垃圾（含一樓集中垃圾）','打包垃圾，然後拿去倒垃圾','打包垃圾，拿到一樓集中，等下週一一起丟')):
        old=next((i for i in data['items'] if i['frequency']=='weekly' and weekday in i['weekdays']),{})
        items.append({**old,'frequency':'weekly','weekdays':[weekday],'content':content,'reminder_time':time,'reminder_enabled':bool(time),'day_start':old.get('day_start',1),'day_end':old.get('day_end',31),'annual_date':'','excluded_dates':old.get('excluded_dates',[])})
    result=duty.save_task(user,{**data,**payload,'name':data['name'],'active':bool(task['active']),'items':items,'effective_from':payload.get('effective_from') or duty.today().isoformat()},preview=preview)
    return {**result,'message':'已存為工作新版本；已發布班表仍保留快照，請重新發布受影響班表後啟用新版提醒。'}

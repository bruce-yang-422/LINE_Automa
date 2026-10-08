"""Form notifications through the existing Dispatcher, jobs and LINE delivery records."""
import hashlib
import json
import sqlite3
from datetime import datetime,timezone
from uuid import UUID
from urllib.parse import urlsplit
import app
import channels
import forms
import reports
import limits
import recipients


def preview(user,payload,*,preview=False):
    user=forms.authorize(user,'send',preview=preview)
    row=forms.invitation_form(user,payload.get('form_id'),preview=preview)
    mode=payload.get('mode','invite')
    if mode not in ('invite','remind'):raise ValueError('通知類型不正確。')
    ids=payload.get('ids')
    if not isinstance(ids,list) or not ids or len(ids)>limits.FORM_SEND_RECIPIENTS_MAX or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError(f'請選擇 1 至 {limits.FORM_SEND_RECIPIENTS_MAX} 個不重複的聯絡對象。')
    with app.database_connection() as conn:
        contacts=[r for r in recipients.list_contacts(conn) if r['recipient_id'] in ids and r['active'] and reports.allowed_contact(user,r)]
    if len(contacts)!=len(ids):raise ValueError('部分收件人已停用、被撤銷或不在授權範圍。')
    body=payload.get('body','')
    if not isinstance(body,str) or not body.strip():raise ValueError('請輸入通知訊息。')
    link=row['public_url'];base=urlsplit(app.public_base_url())
    if base.scheme!='https' or not base.hostname or base.username or base.password or base.query or base.fragment or base.path not in ('','/'):raise ValueError('公開網址必須為 HTTPS 網站根網址。')
    if not link:raise ValueError('尚未設定問卷分享連結。')
    message=body.strip()+('\n若已填寫，請忽略此提醒。' if mode=='remind' else '')+'\n'+link
    if len(message.encode('utf-16-le'))//2>limits.TEXT_MESSAGE_MAX:raise ValueError('訊息加上連結後超過 LINE 文字上限。')
    value={'form_id':row['form_id'],'mode':mode,'ids':sorted(ids),'body':body.strip(),'message':message,'version':row['updated_at']}
    digest=hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {**value,'preview_hash':digest,'contacts':[{'recipient_id':r['recipient_id'],'label':r['custom_name'] or r['display_name'] or r['recipient_id'][-8:]} for r in contacts]}


def send(user,payload,dispatcher,*,actor=None,preview_mode=False):
    prepared=preview(user,payload,preview=preview_mode)
    if payload.get('preview_hash')!=prepared['preview_hash']:raise ValueError('問卷、名單或訊息已變更，請重新預覽確認。')
    job_id=str(UUID(str(payload.get('job_id',''))))
    result=dispatcher.submit({'job_id':job_id,'audience':'selected','ids':prepared['ids'],'message_text':prepared['message']},actor=user['email'],organization=user['organization_id'],form_context=prepared)
    return {'job':result}


def history(user,form_id,*,preview=False):
    user=forms.authorize(user,'view',preview=preview)
    with app.database_connection() as conn:
        form=forms._find(conn,user,form_id);conn.row_factory=sqlite3.Row
        jobs=[]
        for job in conn.execute('SELECT j.job_id,j.status,j.created_at,f.mode FROM send_jobs j JOIN form_send_jobs f ON f.job_id=j.job_id WHERE f.form_id=? AND j.channel_id=? AND j.organization_id=? ORDER BY j.created_at DESC,j.job_id',(form_id,*forms._scope(user))).fetchall():
            jobs.append({**dict(job),'deliveries':[dict(r) for r in conn.execute('SELECT recipient_id,label,status,error FROM send_deliveries WHERE job_id=?',(job['job_id'],))]})
        notifications=[dict(r) for r in conn.execute('SELECT recipient_id,sent_at,last_reminded_at FROM form_notifications WHERE form_id=?',(form_id,))]
        return {'jobs':jobs,'counts':forms._counts(conn,form_id),'notifications':notifications}


def retry_preview(user,payload,*,preview=False):
    user=forms.authorize(user,'send',preview=preview)
    with app.database_connection() as conn:
        form=forms._find(conn,user,payload.get('form_id'));conn.row_factory=sqlite3.Row
        job=conn.execute('SELECT f.* FROM form_send_jobs f JOIN send_jobs j ON j.job_id=f.job_id WHERE f.form_id=? AND f.job_id=? AND j.channel_id=? AND j.organization_id=?',(form['form_id'],payload.get('retry_job_id'),*forms._scope(user))).fetchone()
        if not job:raise PermissionError('找不到授權範圍內的發送工作。')
        if conn.execute("SELECT 1 FROM send_deliveries WHERE job_id=? AND status IN ('pending','sending')",(job['job_id'],)).fetchone():raise ValueError('此工作仍在處理，請稍後確認結果。')
        failed={r[0] for r in conn.execute("SELECT recipient_id FROM send_deliveries WHERE job_id=? AND status='failed'",(job['job_id'],))}
        valid=[r['recipient_id'] for r in recipients.list_contacts(conn) if r['recipient_id'] in failed and r['active'] and reports.allowed_contact(user,r)]
    if not valid:raise ValueError('沒有可重試的失敗收件人；結果不明者不會重送。')
    return globals()['preview'](user,{'form_id':form['form_id'],'mode':job['mode'],'body':job['body'],'ids':valid},preview=preview)


def active(conn,context,channel_id,organization_id):
    row=conn.execute('SELECT f.status,f.deadline_at,o.active,o.forms_enabled FROM forms f JOIN organizations o ON o.org_id=f.organization_id WHERE f.form_id=? AND f.channel_id=? AND f.organization_id=?',(context['form_id'],channel_id,organization_id)).fetchone()
    return bool(row and row[0]=='collecting' and row[2] and row[3] and (not row[1] or datetime.fromisoformat(row[1])>datetime.now(timezone.utc)))


def accepted(conn,context,recipient_id):
    job=conn.execute('SELECT channel_id FROM send_jobs WHERE job_id=?',(context['job_id'],)).fetchone();now=datetime.now(timezone.utc).isoformat()
    from uuid import uuid4
    conn.execute("INSERT INTO form_notifications VALUES (?,?,?,?,?,?) ON CONFLICT(form_id,recipient_id) DO UPDATE SET sent_at=CASE WHEN excluded.sent_at<>'' THEN excluded.sent_at ELSE form_notifications.sent_at END,last_reminded_at=CASE WHEN excluded.last_reminded_at<>'' THEN excluded.last_reminded_at ELSE form_notifications.last_reminded_at END",(uuid4().hex,context['form_id'],job[0],recipient_id,now if context['mode']=='invite' else '',now if context['mode']=='remind' else ''))

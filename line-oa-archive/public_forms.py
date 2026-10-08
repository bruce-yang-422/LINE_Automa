"""Shareable public forms, separate from administrator authentication."""
import html
import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import app
import channels
import forms
import forms_validation
import limits
import form_attachments
import form_content

ASSETS = Path(__file__).with_name('web')
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; frame-src https://www.youtube-nocookie.com; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"

class PublicError(ValueError):
    def __init__(self, code, message):
        self.code=code
        super().__init__(message)


def ensure_link(user, form_id, *, preview=False):
    user=forms.authorize(user,'maintain',preview=preview)
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=forms._find(conn,user,form_id)
        forms._ensure_public_link(conn,form_id)
        return {'form_id':form_id,'token':conn.execute('SELECT token FROM form_public_links WHERE form_id=?',(form_id,)).fetchone()[0]}


def lookup(conn, form_id, token):
    conn.row_factory=sqlite3.Row
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise PublicError(404,'連結無效，請向問卷提供者取得分享連結。')
    link=conn.execute('SELECT 1 FROM form_public_links WHERE token=? AND form_id=?',(token,form_id)).fetchone()
    if not link:raise PublicError(404,'連結無效或問卷已刪除，請聯絡問卷提供者。')
    row=conn.execute('SELECT * FROM forms WHERE form_id=?',(form_id,)).fetchone()
    if not row:raise PublicError(404,'此問卷已刪除。')
    with channels.use(row['channel_id']):
        oa=channels.get()
        if not oa or oa['org_id']!=row['organization_id'] or not channels.operational(oa):raise PublicError(403,'此問卷目前無法使用。')
    org=conn.execute('SELECT active,forms_enabled FROM organizations WHERE org_id=?',(row['organization_id'],)).fetchone()
    if not org or not org['active'] or not org['forms_enabled']:raise PublicError(403,'此問卷目前無法使用。')
    if row['status']=='draft':raise PublicError(403,'此問卷尚未發布。')
    if row['status']=='stopped':raise PublicError(403,'此問卷已停止收件。')
    if row['deadline_at'] and datetime.fromisoformat(row['deadline_at'])<=datetime.now(timezone.utc):raise PublicError(403,'此問卷已截止，無法送出或修改回覆。')
    return dict(row)


def find_response(conn,form_id,edit_token):
    if not isinstance(edit_token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',edit_token):raise PublicError(404,'回覆修改連結無效。')
    response=conn.execute('SELECT * FROM form_submissions WHERE form_id=? AND edit_token=?',(form_id,edit_token)).fetchone()
    if not response:raise PublicError(404,'回覆修改連結無效。')
    return response



def view(form_id,token,edit_token=None):
    with app.database_connection() as conn:
        row=lookup(conn,form_id,token)
        response=find_response(conn,form_id,edit_token) if edit_token is not None else None
        questions=json.loads(row['questions_json'])
        # Keep the stored snapshot intact. Project only still-compatible IDs into current controls.
        answers={}
        if response:
            stored=json.loads(response['answers_json']);old={q['id']:q for q in json.loads(response['questions_snapshot_json'])}
            for q in questions:
                if q['id'] in stored and q['id'] in old and q['type']==old[q['id']]['type']:
                    answer=stored[q['id']]
                    if q['type'] in forms_validation.RULES['choice_types'] and forms_validation.validate_answers([{**q,'required':False,'validation':{'enabled':False}}],{q['id']:answer}):continue
                    answers[q['id']]=answer
        draft_key=secrets.token_urlsafe(32)
        form_attachments.new_draft(conn,form_id,draft_key,response['response_id'] if response else None)
        attachment_rows=conn.execute("SELECT * FROM form_attachments WHERE form_id=? AND response_id=? AND status='saved'",(form_id,response['response_id'])).fetchall() if response else []
        return {'draft_key':draft_key,'attachments':[form_attachments.metadata(r) for r in attachment_rows],'form':{k:row[k] for k in ('name','description','deadline_at','submission_message','updated_at')},'questions':questions,'answers':answers,'submitted':bool(response),'definition_changed':bool(response and json.loads(response['questions_snapshot_json'])!=questions),'first_submitted_at':response['first_submitted_at'] if response else '', 'response_updated_at':response['updated_at'] if response else '', 'submission_key':draft_key if not response else '', 'rules':forms_validation.configuration()}


def submit(form_id,token,payload,edit_token=None):
    if not isinstance(payload,dict) or any(k not in ('answers','submission_key','expected_updated_at','expected_response_updated_at','draft_key') for k in payload):raise PublicError(400,'提交格式不正確。')
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=lookup(conn,form_id,token)
        response=find_response(conn,form_id,edit_token) if edit_token is not None else None
        if payload.get('expected_updated_at')!=row['updated_at']:raise PublicError(409,'問卷內容已更新。輸入已保留，請重新開啟連結確認最新題目。')
        if response is None and isinstance(payload.get('submission_key'),str):
            response=conn.execute('SELECT * FROM form_submissions WHERE form_id=? AND submission_key=?',(form_id,payload['submission_key'])).fetchone()
        questions=forms_validation.validate_questions(json.loads(row['questions_json']));answers=payload.get('answers')
        errors=forms_validation.validate_answers(questions,answers)
        if not errors:
            attachment_errors,attachment_ids=form_attachments.validate(conn,form_id,payload.get('draft_key'),response,questions,answers)
            errors.update(attachment_errors)
        if errors:return 422,{'error':'請修正標示的題目。','errors':errors}
        serialized=json.dumps(answers,ensure_ascii=False);snapshot=json.dumps(questions,ensure_ascii=False)
        if response is None:
            key=payload.get('submission_key')
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',key):raise PublicError(400,'提交識別碼不正確，請重新開啟分享連結。')
            response=conn.execute('SELECT * FROM form_submissions WHERE form_id=? AND submission_key=?',(form_id,key)).fetchone()
            if response and (json.loads(response['answers_json'])!=answers or json.loads(response['questions_snapshot_json'])!=questions):raise PublicError(409,'此份回覆已送出，請使用修改連結或重新開啟問卷填寫新回覆。')
        if response and edit_token is None and (json.loads(response['answers_json'])!=answers or json.loads(response['questions_snapshot_json'])!=questions):raise PublicError(409,'此份回覆已送出，請使用修改連結。')
        if response and edit_token is not None:
            unchanged=json.loads(response['answers_json'])==answers and json.loads(response['questions_snapshot_json'])==questions
            if not unchanged:
                if payload.get('expected_response_updated_at')!=response['updated_at']:raise PublicError(409,'回覆已在其他頁面更新。輸入已保留，請重新開啟修改連結。')
                conn.execute('UPDATE form_submissions SET answers_json=?,questions_snapshot_json=?,updated_at=? WHERE response_id=?',(serialized,snapshot,datetime.now(timezone.utc).isoformat(),response['response_id']))
                response=conn.execute('SELECT * FROM form_submissions WHERE response_id=?',(response['response_id'],)).fetchone()
        if response is None:
            response_id=uuid4().hex;secret=secrets.token_urlsafe(32);now=datetime.now(timezone.utc).isoformat()
            conn.execute('INSERT INTO form_submissions VALUES (?,?,?,?,?,?,?,?)',(response_id,form_id,key,secret,serialized,snapshot,now,now))
            response=conn.execute('SELECT * FROM form_submissions WHERE response_id=?',(response_id,)).fetchone()
        form_attachments.save(conn,form_id,payload.get('draft_key'),response['response_id'],attachment_ids)
        return 200,{'message':row['submission_message'],'first_submitted_at':response['first_submitted_at'],'updated_at':response['updated_at'],'edit_url':'/forms/'+form_id+'?token='+token+'&edit='+response['edit_token']}


def check_origin(handler):
    origin=handler.headers.get('Origin')
    if origin and (urlsplit(origin).netloc!=handler.headers.get('Host') or urlsplit(origin).scheme not in ('http','https')):raise PublicError(403,'提交來源不正確。')


def send(handler,code,body,content_type,extra_headers=None):
    data=body.encode('utf-8') if isinstance(body,str) else body
    handler.send_response(code)
    for key,value in {'Content-Type':content_type,'Content-Length':str(len(data)),'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':CSP,'X-Frame-Options':'DENY',**(extra_headers or {})}.items():handler.send_header(key,value)
    handler.end_headers()
    if handler.command!='HEAD':handler.wfile.write(data)


def page(title,content):
    return '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><link rel="stylesheet" href="/forms-assets/public-forms.css"></head><body><main>'+content+'</main></body></html>'


def handle(handler):
    path=urlsplit(handler.path);asset=path.path.removeprefix('/forms-assets/')
    if path.path.startswith('/forms-assets/'):
        files={'public-forms.js':'text/javascript; charset=utf-8','forms-validation.js':'text/javascript; charset=utf-8','public-forms.css':'text/css; charset=utf-8'}
        if handler.command not in ('GET','HEAD') or asset not in files:send(handler,404,'找不到資源','text/plain; charset=utf-8')
        else:send(handler,200,(ASSETS/asset).read_bytes(),files[asset])
        return True
    if not path.path.startswith('/forms/'):return False
    match=re.fullmatch(r'/forms/([0-9a-f]{32})(/submit|/upload|/content/[0-9a-f]{32}|/attachments/[0-9a-f]{32}/(?:thumb|view|download|remove))?',path.path)
    try:
        tokens=parse_qs(path.query).get('token',[])
        if not match or len(tokens)!=1:raise PublicError(404,'連結無效，請向問卷提供者取得分享連結。')
        form_id=match[1];token=tokens[0]
        edits=parse_qs(path.query,keep_blank_values=True).get('edit',[])
        if len(edits)>1:raise PublicError(404,'回覆修改連結無效。')
        edit_token=edits[0] if edits else None
        if match[2] and match[2]!='/submit':
            if match[2].startswith('/content/'):
                if handler.command not in ('GET','HEAD'):raise PublicError(405,'此連結不支援此操作。')
                try:
                    with app.database_connection() as conn:
                        row=lookup(conn,form_id,token)
                        content=form_content.public_read(conn,row,match[2].split('/')[2])
                except PublicError:raise
                except ValueError as exc:raise PublicError(404,str(exc)) from None
                send(handler,200,content,'image/png')
                return True
            with app.database_connection() as conn:lookup(conn,form_id,token)
            params=parse_qs(path.query,keep_blank_values=True);draft_key=params.get('draft',[''])[0]
            if match[2]=='/upload' and handler.command=='POST':
                check_origin(handler)
                if handler.headers.get('Content-Type','')!='application/octet-stream':raise PublicError(415,'請使用原始檔案上傳。')
                try:size=int(handler.headers.get('Content-Length',''))
                except ValueError:raise PublicError(411,'缺少有效的檔案長度。')
                if not 0<size<=limits.FORM_ATTACHMENT_MAX_BYTES:raise PublicError(413,'附件超過平台大小上限。')
                from urllib.parse import unquote
                try:name=unquote(handler.headers.get('X-Filename',''),errors='strict')
                except UnicodeError:raise PublicError(400,'附件檔名格式不正確。')
                keep=params.get('keep',[''])[0].split(',') if 'keep' in params else None
                if keep==['']:keep=[]
                result=form_attachments.upload(form_id,draft_key,params.get('question',[''])[0],name,handler.rfile.read(size),keep,params.get('upload_id',[None])[0])
                send(handler,200,json.dumps(result,ensure_ascii=False),'application/json; charset=utf-8')
            elif match[2].endswith('/remove') and handler.command=='POST':
                check_origin(handler);form_attachments.remove(form_id,draft_key,match[2].split('/')[2]);send(handler,200,'{}','application/json; charset=utf-8')
            elif handler.command in ('GET','HEAD') and match[2].startswith('/attachments/') and not match[2].endswith('/remove'):
                parts=match[2].split('/');content,kind,name=form_attachments.read(form_id,draft_key,parts[2],parts[3])
                from urllib.parse import quote
                send(handler,200,content,kind,{'Content-Disposition':('inline' if parts[3] in ('thumb','view') and kind.startswith('image/') else 'attachment')+"; filename*=UTF-8''"+quote(name)})
            else:raise PublicError(405,'此連結不支援此操作。')
        elif handler.command in ('GET','HEAD') and not match[2]:
            data=view(form_id,token,edit_token)
            content='<div id="public-form-data" hidden data-json="'+html.escape(json.dumps(data,ensure_ascii=False),quote=True)+'"></div><div id="public-form-root"></div><noscript>請開啟 JavaScript 後填寫此問卷。</noscript><script src="/forms-assets/forms-validation.js" defer></script><script src="/forms-assets/public-forms.js" defer></script>'
            send(handler,200,page(data['form']['name'],content),'text/html; charset=utf-8')
        elif handler.command=='POST' and match[2]:
            with app.database_connection() as conn:
                lookup(conn,form_id,token)
            origin=handler.headers.get('Origin')
            if origin and (urlsplit(origin).netloc!=handler.headers.get('Host') or urlsplit(origin).scheme not in ('http','https')):raise PublicError(403,'提交來源不正確。')
            if handler.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise PublicError(415,'請使用 JSON 提交答案。')
            try:size=int(handler.headers.get('Content-Length',''))
            except ValueError:raise PublicError(411,'缺少有效的提交長度。')
            if not 0<size<=limits.FORM_ANSWERS_MAX_BYTES:raise PublicError(413,'提交內容超過允許大小。')
            try:payload=json.loads(handler.rfile.read(size))
            except (ValueError,UnicodeError):raise PublicError(400,'提交格式不正確。')
            code,result=submit(form_id,token,payload,edit_token)
            send(handler,code,json.dumps(result,ensure_ascii=False),'application/json; charset=utf-8')
        else:raise PublicError(405,'此連結不支援此操作。')
    except form_attachments.AttachmentError as exc:
        send(handler,400,json.dumps({'error':str(exc)},ensure_ascii=False),'application/json; charset=utf-8')
    except PublicError as exc:
        if handler.command=='POST':send(handler,exc.code,json.dumps({'error':str(exc)},ensure_ascii=False),'application/json; charset=utf-8')
        else:send(handler,exc.code,page('問卷無法填寫','<section class="form-intro"><h1>問卷無法填寫</h1><p role="alert">'+html.escape(str(exc))+'</p></section>'),'text/html; charset=utf-8')
    except (sqlite3.Error, forms_validation.DefinitionError,OSError):
        message='問卷服務暫時無法使用，請稍後再試。'
        if handler.command=='POST':send(handler,503,json.dumps({'error':message},ensure_ascii=False),'application/json; charset=utf-8')
        else:send(handler,503,page('問卷暫時無法使用','<section class="form-intro"><h1>問卷暫時無法使用</h1><p role="alert">'+message+'</p></section>'),'text/html; charset=utf-8')
    return True

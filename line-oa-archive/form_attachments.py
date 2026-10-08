"""Private attachment storage, capability ownership and deferred file reclamation."""
import io
import json
import re
import sqlite3
import zipfile
import warnings
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
from PIL import Image,ImageOps,UnidentifiedImageError
import app
import forms_validation
import limits

class AttachmentError(ValueError):pass

def root():return app.BASE_DIR/'private'/'form-attachments'

def path(name):
    if not re.fullmatch(r'[0-9a-f]{32}(?:-thumb)?\.[a-z0-9]+',name):raise AttachmentError('附件儲存位置不正確。')
    file=(root()/name).resolve()
    if file.parent!=root().resolve():raise AttachmentError('附件儲存位置不正確。')
    return file

def draft(conn,form_id,key):
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',key):raise AttachmentError('回覆草稿無效。')
    conn.row_factory=sqlite3.Row
    row=conn.execute('SELECT * FROM form_upload_drafts WHERE form_id=? AND draft_key=?',(form_id,key)).fetchone()
    if not row or datetime.fromisoformat(row['created_at'])<datetime.now(timezone.utc)-timedelta(hours=limits.FORM_TEMP_RETENTION_HOURS):raise AttachmentError('回覆草稿已過期，請重新開啟填寫頁。')
    return row

def new_draft(conn,form_id,key,response_id=None):
    conn.execute('INSERT INTO form_upload_drafts VALUES (?,?,?,?)',(key,form_id,response_id,datetime.now(timezone.utc).isoformat()))

def metadata(row):
    return {k:row[k] for k in ('attachment_id','question_id','original_name','extension','byte_size','thumbnail_name')}

def owned(row,owner):
    return row['status']!='deleted' and (row['draft_key']==owner['draft_key'] or (row['status']=='saved' and owner['response_id'] and row['response_id']==owner['response_id']))

def inspect(ext,data):
    thumb=None
    if ext in ('jpg','jpeg','png'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format!=('PNG' if ext=='png' else 'JPEG'):raise AttachmentError('圖片內容與副檔名不符。')
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    image=ImageOps.exif_transpose(image);image.thumbnail((640,640));image=image.convert('RGB');out=io.BytesIO();image.save(out,format='JPEG',quality=85);thumb=out.getvalue()
        except (OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning,UnidentifiedImageError):raise AttachmentError('圖片損壞或尺寸無法處理。')
    elif ext in ('zip','docx','xlsx','pptx','odt','ods','odp'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names=set(archive.namelist())
                if ext in ('docx','xlsx','pptx'):
                    required={'docx':'word/document.xml','xlsx':'xl/workbook.xml','pptx':'ppt/presentation.xml'}[ext]
                    if not {'[Content_Types].xml',required}<=names:raise AttachmentError('Office 檔案結構不正確。')
                if ext in ('odt','ods','odp'):
                    expected={'odt':'text','ods':'spreadsheet','odp':'presentation'}[ext]
                    if 'mimetype' not in names or 'content.xml' not in names or archive.getinfo('mimetype').file_size>100 or archive.read('mimetype')!=('application/vnd.oasis.opendocument.'+expected).encode():raise AttachmentError('OpenDocument 檔案結構不正確。')
        except (zipfile.BadZipFile,KeyError,OSError,RuntimeError):raise AttachmentError('壓縮檔案內容不正確。')
    elif ext in ('doc','xls','ppt'):
        if not data.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):raise AttachmentError('舊版 Office 檔頭不正確。')
    elif ext=='pdf':
        if not data.startswith(b'%PDF-'):raise AttachmentError('PDF 檔頭不正確。')
    elif ext=='rar':
        if not data.startswith((b'Rar!\x1a\x07\x00',b'Rar!\x1a\x07\x01\x00')):raise AttachmentError('RAR 檔頭不正確。')
    elif ext=='mp3':
        if not (data.startswith(b'ID3') or (len(data)>1 and data[0]==255 and data[1]&224==224)):raise AttachmentError('MP3 檔頭不正確。')
    elif ext=='wav':
        if not (data.startswith(b'RIFF') and data[8:12]==b'WAVE'):raise AttachmentError('WAV 檔頭不正確。')
    elif ext in ('mp4','mov'):
        if len(data)<12 or data[4:8] not in ((b'ftyp',) if ext=='mp4' else (b'ftyp',b'moov',b'mdat',b'wide')):raise AttachmentError('影片檔頭不正確。')
    elif ext in ('txt','csv'):
        try:
            text=data.decode('utf-8-sig')
            if '\x00' in text:raise ValueError()
        except (UnicodeError,ValueError):raise AttachmentError('文字檔必須為 UTF-8 可解碼文字。')
    else:raise AttachmentError('不支援此附件格式。')
    return thumb

def upload(form_id,key,question_id,name,data,keep=None,upload_id=None):
    if not isinstance(name,str) or not name or len(name)>limits.FORM_TEXT_MAX or any(c in name for c in '/\\\r\n\x00'):raise AttachmentError('附件檔名不正確。')
    ext=Path(name).suffix[1:].lower()
    if upload_id is not None and (not isinstance(upload_id,str) or not re.fullmatch(r'[0-9a-f]{32}',upload_id)):raise AttachmentError('上傳識別碼不正確。')
    attachment_id=upload_id or uuid4().hex;file_name=attachment_id+'.'+ext
    written=[]
    try:
        with app.database_connection() as conn:
            conn.execute('BEGIN IMMEDIATE');owner=draft(conn,form_id,key)
            form=conn.execute('SELECT questions_json FROM forms WHERE form_id=?',(form_id,)).fetchone()
            q=next((q for q in json.loads(form[0]) if q['id']==question_id and q['type']=='attachment'),None) if form else None
            if not q:raise AttachmentError('附件題目不存在。')
            config=q['attachment']
            if ext not in config['extensions']:raise AttachmentError('此題不允許此附件格式。')
            if not 0<len(data)<=min(config['max_file_bytes'],limits.FORM_ATTACHMENT_MAX_BYTES):raise AttachmentError('附件大小超過限制或檔案為空。')
            existing=conn.execute('SELECT * FROM form_attachments WHERE attachment_id=?',(attachment_id,)).fetchone()
            if existing:
                if existing['form_id']==form_id and existing['draft_key']==key and existing['question_id']==question_id and existing['status']!='deleted' and existing['original_name']==name and path(existing['file_name']).read_bytes()==data:return metadata(existing)
                raise AttachmentError('此上傳識別碼已用於不同檔案。')
            rows=conn.execute("SELECT * FROM form_attachments WHERE form_id=? AND question_id=? AND status!='deleted'",(form_id,question_id)).fetchall()
            rows=[row for row in rows if owned(row,owner)]
            if keep is not None:
                if any(identifier not in {r['attachment_id'] for r in rows} for identifier in keep):raise AttachmentError('附件保留名單不正確。')
                rows=[r for r in rows if r['status']!='saved' or r['attachment_id'] in keep]
            if len(rows)>=config['max_files'] or sum(row['byte_size'] for row in rows)+len(data)>config['max_total_bytes']:raise AttachmentError('附件數量或合計大小超過限制（包含已保存附件）。')
            thumb=inspect(ext,data)
            thumb_name=attachment_id+'-thumb.jpg' if thumb else ''
            root().mkdir(parents=True,exist_ok=True)
            path(file_name).write_bytes(data);written.append(file_name)
            if thumb:path(thumb_name).write_bytes(thumb);written.append(thumb_name)
            conn.execute('INSERT INTO form_attachments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(attachment_id,form_id,question_id,key,None,name,ext,len(data),file_name,thumb_name,'temporary',datetime.now(timezone.utc).isoformat()))
            return metadata(conn.execute('SELECT * FROM form_attachments WHERE attachment_id=?',(attachment_id,)).fetchone())
    except Exception:
        for name in written:path(name).unlink(missing_ok=True)
        raise

def read(form_id,key,attachment_id,kind='download'):
    with app.database_connection() as conn:
        owner=draft(conn,form_id,key);row=conn.execute('SELECT * FROM form_attachments WHERE form_id=? AND attachment_id=?',(form_id,attachment_id)).fetchone()
        if not row or not owned(row,owner):raise AttachmentError('找不到有權限的附件。')
        file_name=row['thumbnail_name'] if kind=='thumb' else row['file_name']
        if not file_name:raise AttachmentError('此附件沒有縮圖。')
        data=path(file_name).read_bytes()
        content_type='image/jpeg' if kind=='thumb' else {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg'}.get(row['extension'],'application/octet-stream')
        return data,content_type,row['original_name']

def remove(form_id,key,attachment_id):
    with app.database_connection() as conn:
        owner=draft(conn,form_id,key);row=conn.execute('SELECT * FROM form_attachments WHERE form_id=? AND attachment_id=?',(form_id,attachment_id)).fetchone()
        if not row or not owned(row,owner):raise AttachmentError('找不到有權限的附件。')
        if row['status']=='temporary':conn.execute("UPDATE form_attachments SET status='deleted' WHERE attachment_id=?",(attachment_id,))
    cleanup()

def validate(conn,form_id,key,response,questions,answers):
    errors={};ids=[];owner=None
    for q in questions:
        if q['type']!='attachment':continue
        values=answers.get(q['id'],[]) or []
        if not values:continue
        try:
            if owner is None:owner=draft(conn,form_id,key)
            if owner['response_id'] and (not response or owner['response_id']!=response['response_id']):raise AttachmentError('附件不屬於此回覆。')
            rows=[]
            for identifier in values:
                row=conn.execute('SELECT * FROM form_attachments WHERE attachment_id=? AND form_id=? AND question_id=?',(identifier,form_id,q['id'])).fetchone()
                if not row or not owned(row,owner):raise AttachmentError('附件未完成上傳或不屬於此回覆。')
                rows.append(row)
            config=q['attachment']
            if len(rows)>config['max_files'] or sum(r['byte_size'] for r in rows)>config['max_total_bytes'] or any(r['extension'] not in config['extensions'] or r['byte_size']>config['max_file_bytes'] for r in rows):raise AttachmentError('附件超過目前題目限制。')
            ids.extend(values)
        except AttachmentError as exc:errors[q['id']]=str(exc)
    return errors,ids

def save(conn,form_id,key,response_id,ids):
    rows=conn.execute("SELECT attachment_id FROM form_attachments WHERE form_id=? AND response_id=? AND status='saved'",(form_id,response_id)).fetchall()
    for row in rows:
        if row[0] not in ids:conn.execute("UPDATE form_attachments SET status='deleted' WHERE attachment_id=?",(row[0],))
    for identifier in ids:conn.execute("UPDATE form_attachments SET status='saved',response_id=? WHERE attachment_id=?",(response_id,identifier))
    conn.execute('UPDATE form_upload_drafts SET response_id=? WHERE form_id=? AND draft_key=?',(response_id,form_id,key))

def cleanup(now=None):
    now=now or datetime.now(timezone.utc);cutoff=(now-timedelta(hours=limits.FORM_TEMP_RETENTION_HOURS)).isoformat()
    with app.database_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE form_attachments SET status='deleted' WHERE status='temporary' AND created_at<?",(cutoff,))
        rows=conn.execute("SELECT attachment_id,file_name,thumbnail_name FROM form_attachments WHERE status='deleted'").fetchall()
        for identifier,file_name,thumb in rows:
            for name in (file_name,thumb):
                if name:path(name).unlink(missing_ok=True)
            conn.execute('DELETE FROM form_attachments WHERE attachment_id=?',(identifier,))
        conn.execute('DELETE FROM form_upload_drafts WHERE created_at<?',(cutoff,))


def admin_read(user,form_id,attachment_id,kind='download',*,preview=False):
    import forms
    user=forms.authorize(user,'view',preview=preview)
    if kind not in ('thumb','view','download'):raise AttachmentError('附件操作不正確。')
    with app.database_connection() as conn:
        forms._find(conn,user,form_id);conn.row_factory=sqlite3.Row
        row=conn.execute("SELECT * FROM form_attachments WHERE form_id=? AND attachment_id=? AND status='saved'",(form_id,attachment_id)).fetchone()
        if not row:raise AttachmentError('找不到有權限的附件。')
        name=row['thumbnail_name'] if kind=='thumb' else row['file_name']
        if not name:raise AttachmentError('沒有預覽縮圖。')
        mime='image/jpeg' if kind=='thumb' else {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg'}.get(row['extension'],'application/octet-stream') if kind=='view' else 'application/octet-stream'
        return path(name).read_bytes(),mime,row['original_name']

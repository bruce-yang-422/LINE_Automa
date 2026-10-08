"""Scoped response reading and snapshot-based CSV; never joins contact identities."""
import csv
import io
import json
from datetime import datetime,time,timedelta,timezone

import app
import forms
import limits
import reports

TAIPEI=timezone(timedelta(hours=8))


def answer_text(question,value,attachments):
    kind=question['type']
    if value is None:return ''
    if kind=='attachment':
        return '\n'.join(f"{attachments[i]['original_name']} [{i}]" if i in attachments else f'附件已不存在 [{i}]' for i in (value if isinstance(value,list) else []))
    if kind in ('single_choice','multiple_choice','dropdown'):
        if isinstance(value,dict):
            selected=value.get('option_ids',[]) if kind=='multiple_choice' else [value.get('option_id','')]
            other=value.get('other','')
        else:selected=value if isinstance(value,list) else [value];other=''
        labels={o['id']:o['label'] for o in question.get('options',[])}
        return '、'.join(('其他：'+str(other) if i=='__other__' else labels.get(i,str(i))) for i in selected if i)
    return str(value)


def _attachments(conn,form_id):
    return {r['attachment_id']:dict(r) for r in conn.execute("SELECT attachment_id,response_id,question_id,original_name,extension,byte_size,thumbnail_name FROM form_attachments WHERE form_id=? AND status='saved'",(form_id,))}


def _readable(row,attachments):
    answers=json.loads(row['answers_json']);questions=json.loads(row['questions_snapshot_json'])
    own={i:a for i,a in attachments.items() if a['response_id']==row['response_id']}
    items=[]
    for q in questions:
        value=answers.get(q['id'])
        files=[{k:a[k] for k in ('attachment_id','original_name','extension','byte_size','thumbnail_name')} for i in (value if q['type']=='attachment' and isinstance(value,list) else []) if (a:=own.get(i)) and a['question_id']==q['id']]
        items.append({'question_id':q['id'],'title':q['title'],'description':q.get('description',''),'type':q['type'],'text':answer_text(q,value,own),'attachments':files})
    return {'response_id':row['response_id'],'first_submitted_at':row['first_submitted_at'],'updated_at':row['updated_at'],'items':items}


def _rows(conn,form_id,query):
    field=query.get('time_field','submitted')
    if field not in ('submitted','updated'):raise ValueError('請選擇提交或最後更新時間。')
    column='first_submitted_at' if field=='submitted' else 'updated_at'
    conditions=['form_id=?'];args=[form_id];start=end=None
    for key in ('date_from','date_to'):
        value=query.get(key,'')
        if not value:continue
        try:
            date=datetime.strptime(value,'%Y-%m-%d').date()
            if date.isoformat()!=value:raise ValueError()
            stamp=datetime.combine(date,time.min,TAIPEI)
        except (TypeError,ValueError):raise ValueError('篩選日期請使用 YYYY-MM-DD。') from None
        if key=='date_from':start=date;conditions.append(f'julianday({column})>=julianday(?)')
        else:end=date;stamp+=timedelta(days=1);conditions.append(f'julianday({column})<julianday(?)')
        args.append(stamp.isoformat())
    if start and end and start>end:raise ValueError('起始日期不能晚於結束日期。')
    search=query.get('query','')
    if not isinstance(search,str) or len(search)>limits.FORM_TEXT_MAX:raise ValueError('搜尋文字超過限制。')
    attachments=_attachments(conn,form_id);matches=[]
    for row in conn.execute('SELECT response_id,answers_json,questions_snapshot_json,first_submitted_at,updated_at FROM form_submissions WHERE '+' AND '.join(conditions)+f' ORDER BY julianday({column}) DESC,response_id',args):
        readable=_readable(row,attachments)
        haystack='\n'.join([readable['response_id'],*(item['text'] for item in readable['items'])]).casefold()
        if search.strip().casefold() not in haystack:continue
        matches.append((row,readable))
    return matches


def listing(user,query,*,preview=False):
    user=forms.authorize(user,'view',preview=preview)
    try:page=int(query.get('page','1'))
    except (ValueError,TypeError):raise ValueError('頁碼不正確。') from None
    if page<1:raise ValueError('頁碼不正確。')
    with app.database_connection() as conn:
        form=forms._find(conn,user,query.get('form_id'));rows=_rows(conn,form['form_id'],query)
        total=len(rows);pages=max(1,(total+limits.FORM_RESPONSE_PAGE_SIZE-1)//limits.FORM_RESPONSE_PAGE_SIZE);page=min(page,pages)
        records=[]
        for _,row in rows[(page-1)*limits.FORM_RESPONSE_PAGE_SIZE:page*limits.FORM_RESPONSE_PAGE_SIZE]:
            records.append({k:v for k,v in row.items() if k!='items'}|{'summary':' · '.join(f"{i['title']}：{i['text']}" for i in row['items'] if i['type'] not in ('section','attachment') and i['text'])[:300]})
        return {'responses':records,'total':total,'page':page,'pages':pages,'page_size':limits.FORM_RESPONSE_PAGE_SIZE}


def detail(user,form_id,response_id,*,preview=False):
    user=forms.authorize(user,'view',preview=preview)
    with app.database_connection() as conn:
        forms._find(conn,user,form_id)
        row=conn.execute('SELECT response_id,answers_json,questions_snapshot_json,first_submitted_at,updated_at FROM form_submissions WHERE form_id=? AND response_id=?',(form_id,response_id)).fetchone()
        if not row:raise PermissionError('找不到授權範圍內的回覆。')
        return {'response':_readable(row,_attachments(conn,form_id))}


def csv_cell(value,phone=False):
    text=str(value)
    return "'"+text if text and (phone or text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n'))) else text


def export(user,query,*,preview=False,actor=None):
    user=forms.authorize(user,'export',preview=preview)
    with app.database_connection() as conn:
        form=forms._find(conn,user,query.get('form_id'));rows=_rows(conn,form['form_id'],query)
        columns={}
        for row,_ in reversed(rows):
            for q in json.loads(row['questions_snapshot_json']):
                if q['type'] in ('section','content'):continue
                key=(q['id'],q['type']);columns.setdefault(key,[])
                if q['title'] not in columns[key]:columns[key].append(q['title'])
        out=io.StringIO(newline='');writer=csv.writer(out)
        headers=[]
        for key,titles in columns.items():
            label='／'.join(titles)+f' [{key[0]}]'
            if sum(other[0]==key[0] for other in columns)>1:label+='（'+forms.forms_validation.RULES['types'].get(key[1],key[1])+'）'
            headers.append(label)
        writer.writerow([csv_cell(v) for v in ['回覆代號','首次提交時間（台北）','最後更新時間（台北）',*headers]])
        for row,readable in rows:
            questions={ (q['id'],q['type']):q for q in json.loads(row['questions_snapshot_json']) }
            values={ (item['question_id'],item['type']):item['text'] for item in readable['items'] }
            cells=[row['response_id'],*(datetime.fromisoformat(row[k]).astimezone(TAIPEI).strftime('%Y-%m-%d %H:%M:%S') for k in ('first_submitted_at','updated_at'))]
            for key in columns:
                q=questions.get(key,{});phone=q.get('type')=='phone' or q.get('validation',{}).get('format')=='phone'
                cells.append(csv_cell(values.get(key,''),phone=phone))
            writer.writerow(cells)
        reports.audit(conn,actor or user['email'],'forms.export',form['form_id'],f"{form['name']} · {len(rows)} 份回覆",user['organization_id'])
        return out.getvalue().encode('utf-8-sig'),form['name']+'-回覆.csv'

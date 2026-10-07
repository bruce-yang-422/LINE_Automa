"use strict";
const formsUI={rows:[],templates:[],capabilities:{},selected:null,query:"",filter:"all",channel:""};
const formStatusNames={draft:"草稿",collecting:"收件中",stopped:"停止收件"};
const formTypeNames={short_text:"短文字",paragraph:"段落文字",single_choice:"單選",multiple_choice:"多選",dropdown:"下拉選單",number:"數字／數量",date:"日期",time:"時間",rating:"評分量表",attachment:"附件上傳"};
function formLocalTime(value){return value?new Date(new Date(value).getTime()+8*3600000).toISOString().slice(0,16):"";}
function formTimeLabel(value){return value?new Date(value).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false}):"未設定";}
function formCanLeave(){return !document.querySelector('[data-form-editor][data-dirty="true"]')||confirm("有未儲存變更，確定離開？");}
async function loadForms(){
  const visible=Boolean(state.session?.forms_capabilities?.view)&&lineDataReady()&&!superAdmin();
  document.querySelector('nav [data-view="forms"]').hidden=!visible;
  if(formsUI.channel!==lineUI.channel){formsUI.selected=null;formsUI.query="";formsUI.filter="all";}
  formsUI.channel=lineUI.channel;
  const data=visible?await api('/api/forms'):{forms:[],templates:[],capabilities:{}};
  formsUI.rows=data.forms;formsUI.templates=data.templates;formsUI.capabilities=data.capabilities;
  if(formsUI.selected&&!formsUI.rows.some(row=>row.form_id===formsUI.selected))formsUI.selected=null;
  if(state.view==='forms'&&!visible)state.view=superAdmin()?'organizations':'overview';
}
function formButton(title,action,id='',extra=''){
  return `<button type="button" class="btn small" data-action="form-${action}" data-id="${esc(id)}" ${extra}>${esc(title)}</button>`;
}
function formsPage(){
  const selected=formsUI.rows.find(row=>row.form_id===formsUI.selected);
  if(selected)return formEditorPage(selected);
  const rows=formsUI.rows.filter(row=>(formsUI.filter==='all'||row.status===formsUI.filter)&&(!formsUI.query||row.name.toLowerCase().includes(formsUI.query.toLowerCase())));
  return heading('表單','為目前 LINE OA 建立表單並管理收件狀態。',formsUI.capabilities.maintain?formButton('新增表單','new'):'')+
    `<section class="panel panel-body form-list-panel"><h2>表單清單</h2><div class="form-list-filters"><label class="field">搜尋表單<input id="form-search" type="search" value="${esc(formsUI.query)}" placeholder="輸入名稱"></label><label class="field">收件狀態<select id="form-filter">${options([['all','全部'],...Object.entries(formStatusNames)],formsUI.filter)}</select></label><p class="subtitle">${formsUI.rows.length} / ${cap('FORMS_PER_OA')} 份</p></div><div class="form-list">${rows.map(row=>`<article class="form-card"><div><h3>${esc(row.name)}</h3><p class="form-description">${esc(row.description)||'未填寫說明'}</p><p class="subtitle">${formStatusNames[row.status]}${row.expired?' · 已截止':''} · ${row.questions.length} 題</p><p class="subtitle">截止：${esc(formTimeLabel(row.deadline_at))}（台北時間）</p></div><div class="form-card-actions">${formButton(formsUI.capabilities.maintain?'編輯基本資料':'查看表單','open',row.form_id)}${formsUI.capabilities.maintain?formButton('複製','copy',row.form_id)+formButton('刪除','delete',row.form_id):''}</div></article>`).join('')||empty('沒有符合的表單','可新增空白表單或使用內建範本。')}</div></section>`;
}
function formEditorPage(row){
  const edit=formsUI.capabilities.maintain,readonly=edit?'':'disabled';
  return heading(row.name,'設定基本資料與收件狀態；截止時間以台北時間顯示。',formButton('返回清單','back'))+
    `<section class="panel panel-body"><h2>基本資料</h2><p class="form-status">${formStatusNames[row.status]}${row.expired?' · 已截止':''}${!edit?' · 唯讀':''}</p><form data-form-editor data-id="${esc(row.form_id)}" data-dirty="false" class="form-basic-editor"><label class="field">表單名稱<input name="name" value="${esc(row.name)}" required maxlength="${cap('FORM_NAME_MAX')}" ${readonly}></label><label class="field">說明<textarea name="description" rows="3" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(row.description)}</textarea></label><label class="field">截止時間（台北時間，留空不限期）<input name="deadline_at" type="datetime-local" value="${esc(formLocalTime(row.deadline_at))}" ${readonly}></label><label class="field">送出後提示<textarea name="submission_message" rows="2" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(row.submission_message)}</textarea></label><p class="form-save-status" role="status">${edit?'變更後請按儲存。':'目前角色只能查看。'}</p><p class="form-error" role="alert" hidden></p>${edit?'<div class="form-actions"><button type="submit" class="btn primary">儲存基本資料</button></div>':''}</form></section><section class="panel panel-body form-section"><h2>收件設定</h2><p>草稿不能發送邀請。發布後可停止收件；已截止時先儲存新的截止時間，再重新開放。</p><div class="form-actions">${formsUI.capabilities.publish?(row.status==='collecting'?formButton('停止收件','status',row.form_id,'data-status="stopped"'):formButton(row.status==='draft'?'發布表單':'重新開放收件','status',row.form_id,'data-status="collecting"')):''}</div></section><section class="panel panel-body form-section"><h2>題目內容</h2><ol class="form-question-summary">${row.questions.map(q=>`<li><h3>${esc(q.title)}${q.required?'（必填）':''}</h3><p>${esc(formTypeNames[q.type]||q.type)}</p>${q.options.length?`<p>${q.options.map(o=>esc(o.label)).join('、')}</p>`:''}</li>`).join('')}</ol>${row.questions.length?'':'<p>尚無題目；可從內建範本建立含題目的表單。</p>'}<p class="subtitle">題目內容為目前保存的設定。</p></section>`;
}
function formCreateModal(){
  modal('新增表單',`<form data-form-editor data-dirty="false" class="form-basic-editor"><label class="field">建立方式<select name="template_id"><option value="">空白表單</option>${formsUI.templates.map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select></label><label class="field">表單名稱<input name="name" required maxlength="${cap('FORM_NAME_MAX')}" placeholder="輸入名稱"></label><p class="subtitle">範本的題目與說明會一起複製，可先儲存為草稿。</p><p class="form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">建立草稿</button></div></form>`);
}
document.addEventListener('input',event=>{
  const form=event.target.closest('[data-form-editor]');
  if(form){form.dataset.dirty='true';const status=form.querySelector('.form-save-status');if(status)status.textContent='尚未儲存';renderWorkspaceTools();}
  if(event.target.id==='form-search'){formsUI.query=event.target.value;const pos=event.target.selectionStart;render();$('form-search').focus();$('form-search').setSelectionRange(pos,pos);}
});
document.addEventListener('change',event=>{
  if(event.target.id==='form-filter'){formsUI.filter=event.target.value;render();}
  const form=event.target.closest('[data-form-editor]');if(!form)return;form.dataset.dirty='true';
  if(event.target.name==='template_id'&&!form.elements.name.value)form.elements.name.value=formsUI.templates.find(t=>t.id===event.target.value)?.name||'';
  const status=form.querySelector('.form-save-status');if(status)status.textContent='尚未儲存';renderWorkspaceTools();
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.hasAttribute('data-form-editor'))return;
  event.preventDefault();const submit=form.querySelector('[type="submit"]'),error=form.querySelector('.form-error');
  if(submit.disabled||state.busy)return;submit.disabled=true;error.hidden=true;state.busy=true;
  const values=Object.fromEntries(new FormData(form)),isNew=!form.dataset.id;
  if(!isNew)values.form_id=form.dataset.id;
  if('deadline_at' in values)values.deadline_at=values.deadline_at?values.deadline_at+':00+08:00':'';
  try{
    const result=await api('/api/forms/save',values);formsUI.selected=result.form.form_id;
    await loadForms();form.dataset.dirty='false';if(isNew)$('modal').close();
    render();notice('表單已儲存。');
  }catch(exc){error.textContent=exc.message;error.hidden=false;submit.disabled=false;}
  finally{state.busy=false;}
});
document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-action^="form-"]');if(!target||target.disabled||state.busy)return;
  const action=target.dataset.action.slice(5),id=target.dataset.id;
  try{
    if(action==='new'){if(formCanLeave())formCreateModal();return;}
    if(action==='back'){if(!formCanLeave())return;formsUI.selected=null;render();return;}
    if(action==='open'){
      if(!formCanLeave())return;
      const result=await api('/api/forms/detail?form_id='+encodeURIComponent(id));
      formsUI.rows=formsUI.rows.map(row=>row.form_id===id?result.form:row);formsUI.selected=id;render();return;
    }
    if(action==='delete'){
      const result=await api('/api/forms/detail?form_id='+encodeURIComponent(id));const row=result.form;
      modal('刪除表單？',`<p>將刪除「${esc(row.name)}」、${row.counts.invitations} 份邀請、${row.counts.responses} 份回覆及其附件。刪除後專屬連結失效。</p><div class="form-actions">${formButton('確認刪除','confirm-delete',id,'data-invitations="'+row.counts.invitations+'" data-responses="'+row.counts.responses+'"')}</div>`);return;
    }
    if(action==='status'&&!formCanLeave())return;
    target.disabled=true;
    if(action==='copy'){const result=await api('/api/forms/copy',{form_id:id});formsUI.selected=result.form.form_id;}
    else if(action==='status')await api('/api/forms/status',{form_id:id,status:target.dataset.status});
    else if(action==='confirm-delete'){await api('/api/forms/delete',{form_id:id,confirm_counts:{invitations:Number(target.dataset.invitations),responses:Number(target.dataset.responses)}});$('modal').close();formsUI.selected=null;}
    else return;
    await loadForms();render();notice('表單已更新。');
  }catch(exc){target.disabled=false;if($('modal').open){$('modal-error').textContent=exc.message;$('modal-error').hidden=false;}else notice(exc.message,true);}
});

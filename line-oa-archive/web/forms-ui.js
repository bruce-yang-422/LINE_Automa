"use strict";
const formsUI={folders:[],folder:"all",layout:(()=>{try{return localStorage.getItem("forms-layout")==="grid"?"grid":"list";}catch{return "list";}})(),rows:[],templates:[],capabilities:{},selected:null,mode:"basic",query:"",filter:"all",channel:""};
const formStatusNames={draft:"草稿",collecting:"收件中",stopped:"停止收件"};
function formLocalTime(value){return value?new Date(new Date(value).getTime()+8*3600000).toISOString().slice(0,16):"";}
function formTimeLabel(value){return value?new Date(value).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false}):"未設定";}
function formCanLeave(){return !(formDesign.dirty||document.querySelector('[data-form-editor][data-dirty="true"], [data-form-designer][data-dirty="true"]'))||confirm("有未儲存變更，確定離開？");}
async function loadForms(){
  const visible=Boolean(state.session?.forms_capabilities?.view)&&lineDataReady()&&!superAdmin();
  document.querySelector('nav [data-view="forms"]').hidden=!visible;
  if(formsUI.channel!==lineUI.channel){formsUI.selected=null;formsUI.query="";formsUI.filter="all";formsUI.folder="all";}
  formsUI.channel=lineUI.channel;
  const data=visible?await api('/api/forms'):{forms:[],templates:[],capabilities:{}};
  formsUI.folders=data.folders||[];if(!["all","",...formsUI.folders.map(f=>f.folder_id)].includes(formsUI.folder))formsUI.folder="all";formsUI.rows=data.forms;formsUI.templates=data.templates;formsUI.capabilities=data.capabilities;if(data.rules)FormValidation.configure(data.rules);
  if(formsUI.selected&&!formsUI.rows.some(row=>row.form_id===formsUI.selected))formsUI.selected=null;
  if(state.view==='forms'&&!visible)state.view=superAdmin()?'organizations':'overview';
}
function formButton(title,action,id='',extra=''){
  return `<button type="button" class="btn small" data-action="form-${action}" data-id="${esc(id)}" ${extra}>${esc(title)}</button>`;
}
function formHomeCard(row){
  const edit=formsUI.capabilities.maintain,folder=formsUI.folders.find(f=>f.folder_id===row.folder_id),questions=row.questions.filter(q=>!['section','content'].includes(q.type));
  const thumb=formsUI.layout==='grid'?`<button class="form-thumbnail" type="button" data-action="form-open" data-id="${esc(row.form_id)}" aria-label="開啟 ${esc(row.name)}"><span class="form-paper" aria-hidden="true"><strong>${esc(row.name)}</strong>${questions.slice(0,3).map(q=>`<span>${esc(q.title)}</span><i></i>`).join('')||'<span>開始設計你的問卷</span><i></i><i></i>'}</span></button>`:'';
  return `<article class="form-card" data-form-card="${esc(row.form_id)}">${thumb}<div class="form-card-content"><h3><button type="button" class="form-title-button" data-action="form-open" data-id="${esc(row.form_id)}">${esc(row.name)}</button></h3><p class="form-description">${esc(row.description)||'未填寫說明'}</p><div class="form-home-meta"><span class="form-status-badge">${formStatusNames[row.status]}${row.expired?' · 已截止':''}</span><span>${questions.length} 題 · ${row.counts.responses} 份回覆</span></div><p class="subtitle">${esc(folder?.name||'未分類')} · 更新 ${esc(formTimeLabel(row.updated_at))}</p><p class="subtitle">截止：${esc(formTimeLabel(row.deadline_at))}（台北時間）</p><div class="form-card-actions">${formButton(edit?'編輯基本資料':'查看表單','open',row.form_id)}${formButton('預覽','preview',row.form_id)}${formButton('回覆管理','responses',row.form_id)}${edit?formButton('移動','move',row.form_id)+formButton('複製','copy',row.form_id)+formButton('刪除','delete',row.form_id):''}</div></div></article>`;
}
function formsPage(){
  const selected=formsUI.rows.find(row=>row.form_id===formsUI.selected);
  if(selected&&formsUI.mode==="responses")return formResponsePage(selected);
  if(selected)return formsUI.mode==="design"?formDesignerPage(selected):formsUI.mode==="preview"?formPreviewPage(selected):formEditorPage(selected);
  const rows=formsUI.rows.filter(row=>(formsUI.folder==='all'||row.folder_id===formsUI.folder)&&(formsUI.filter==='all'||row.status===formsUI.filter)&&(!formsUI.query||row.name.toLowerCase().includes(formsUI.query.toLowerCase())));
  const folder=formsUI.folders.find(f=>f.folder_id===formsUI.folder),edit=formsUI.capabilities.maintain;
  const folderButton=(id,name,count)=>`<button type="button" class="form-folder-button" data-action="form-folder-select" data-id="${esc(id)}" aria-pressed="${formsUI.folder===id}"><span>${esc(name)}</span><span>${count}</span></button>`;
  return heading('表單','整理問卷、設計題目並管理收件狀態。',edit?formButton('新增表單','new'):'')+
    `<div class="form-home"><aside class="panel panel-body form-folders" aria-label="問卷資料夾"><div class="form-folder-heading"><h2>資料夾</h2>${edit?formButton('新增資料夾','folder-new'):''}</div>${folderButton('all','全部問卷',formsUI.rows.length)}${folderButton('','未分類',formsUI.rows.filter(r=>!r.folder_id).length)}${formsUI.folders.map(f=>folderButton(f.folder_id,f.name,formsUI.rows.filter(r=>r.folder_id===f.folder_id).length)).join('')}</aside><section class="panel panel-body form-list-panel"><div class="form-folder-heading"><h2>${esc(folder?.name||(formsUI.folder==='all'?'全部問卷':'未分類'))}</h2>${folder&&edit?`<div class="form-actions">${formButton('重新命名','folder-rename',folder.folder_id)}${formButton('刪除資料夾','folder-delete',folder.folder_id)}</div>`:''}</div><div class="form-list-filters"><label class="field">搜尋表單<input id="form-search" type="search" value="${esc(formsUI.query)}" placeholder="輸入名稱"></label><label class="field">收件狀態<select id="form-filter">${options([['all','全部'],...Object.entries(formStatusNames)],formsUI.filter)}</select></label><div class="form-view-switch" role="group" aria-label="問卷檢視模式">${['list','grid'].map(mode=>`<button type="button" class="btn small" data-action="form-layout" data-id="${mode}" title="${mode==='list'?'條列式':'縮圖式'}" aria-label="${mode==='list'?'條列式':'縮圖式'}" aria-pressed="${formsUI.layout===mode}">${icon(mode==='list'?'menu':'grid')}</button>`).join('')}</div></div><p class="subtitle" role="status">顯示 ${rows.length} 份 · 總共 ${formsUI.rows.length} / ${cap('FORMS_PER_OA')} 份</p><div class="form-list ${formsUI.layout==='grid'?'form-grid':'form-rows'}">${rows.map(formHomeCard).join('')||empty('沒有符合的表單',formsUI.query||formsUI.filter!=='all'?'請調整搜尋或收件狀態。':'可新增表單，或將現有問卷移入此資料夾。')}</div></section></div>`;
}
function formFolderModal(action,id=''){
  const folder=formsUI.folders.find(f=>f.folder_id===id),moving=action==='move',deleting=action==='delete';
  modal(moving?'移動問卷':deleting?'刪除資料夾？':action==='rename'?'重新命名資料夾':'新增資料夾',`<form data-form-folder data-operation="${action}" data-id="${esc(id)}"><p>${moving?'選擇問卷的分類位置。':deleting?'刪除資料夾會將其中問卷移回未分類，保留所有問卷與內容。':'以活動、學期或用途整理問卷。'}</p>${moving?`<label class="field">移動至<select name="folder_id">${options([['','未分類'],...formsUI.folders.map(f=>[f.folder_id,f.name])],formsUI.rows.find(r=>r.form_id===id)?.folder_id||'')}</select></label>`:deleting?`<p>${esc(folder.name)}</p>`:`<label class="field">資料夾名稱<input name="name" required maxlength="${cap('FORM_NAME_MAX')}" value="${esc(folder?.name||'')}" placeholder="例如：家長回饋"></label>`}<p class="form-error" role="alert" hidden></p><button type="submit" class="btn primary">${moving?'確認移動':deleting?'確認刪除資料夾':'儲存資料夾'}</button></form>`);
}
function formEditorPage(row){
  const edit=formsUI.capabilities.maintain,readonly=edit?'':'disabled';
  return heading(row.name,'設定基本資料與收件狀態；截止時間以台北時間顯示。',formButton('返回清單','back')+formButton(edit?'設計題目':'查看題目','design',row.form_id)+formButton('填寫預覽','preview',row.form_id)+formButton('回覆管理','responses',row.form_id)+formButton('發送紀錄','send-history',row.form_id)+(formsUI.capabilities.send&&row.status==='collecting'&&!row.expired?formButton('發送問卷','send',row.form_id)+formButton('一般提醒','remind',row.form_id):''))+
    `<section class="panel panel-body"><h2>基本資料</h2><p class="form-status">${formStatusNames[row.status]}${row.expired?' · 已截止':''}${!edit?' · 唯讀':''}</p><form data-form-editor data-id="${esc(row.form_id)}" data-dirty="false" class="form-basic-editor"><label class="field">表單名稱<input name="name" value="${esc(row.name)}" required maxlength="${cap('FORM_NAME_MAX')}" ${readonly}></label><label class="field">說明<textarea name="description" rows="3" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(row.description)}</textarea></label><label class="field">截止時間（台北時間，留空不限期）<input name="deadline_at" type="datetime-local" value="${esc(formLocalTime(row.deadline_at))}" ${readonly}></label><label class="field">送出後提示<textarea name="submission_message" rows="2" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(row.submission_message)}</textarea></label><p class="form-save-status" role="status">${edit?'變更後請按儲存。':'目前角色只能查看。'}</p><p class="form-error" role="alert" hidden></p>${edit?'<div class="form-actions"><button type="submit" class="btn primary">儲存基本資料</button></div>':''}</form></section><section class="panel panel-body form-section"><h2>收件設定</h2>${row.public_url?`<label class="field">可分享問卷連結<input type="url" value="${esc(row.public_url)}" readonly aria-label="可分享問卷連結"></label><p class="subtitle">此連結不會帶入既有答案。填寫者送出後會取得各自的修改連結。</p>`:''}<p>草稿不能發送邀請。發布後可停止收件；已截止時先儲存新的截止時間，再重新開放。</p><div class="form-actions">${formsUI.capabilities.publish?(row.status==='collecting'?formButton('停止收件','status',row.form_id,'data-status="stopped"'):formButton(row.status==='draft'?'發布表單':'重新開放收件','status',row.form_id,'data-status="collecting"')):''}</div></section><section class="panel panel-body form-section"><h2>題目內容</h2><ol class="form-question-summary">${row.questions.map(q=>`<li><h3>${esc(q.title)}${q.required?'（必填）':''}</h3><p>${esc(FormValidation.rules?.types[q.type]||q.type)}</p>${q.options.length?`<p>${q.options.map(o=>esc(o.label)).join('、')}</p>`:''}</li>`).join('')}</ol>${row.questions.length?'':'<p>尚無題目；請選擇設計題目新增內容。</p>'}<p class="subtitle">題目內容為目前保存的設定。</p></section>`;
}
function formCreateModal(mode=''){
  if(!mode){
    modal('新增表單',`<p class="subtitle">選擇建立問卷的方式。</p><div class="form-create-options"><button type="button" class="form-create-card" data-form-create-mode="blank"><span class="form-create-icon" aria-hidden="true">${icon('plus')}</span><strong>空白問卷</strong><span>從頭開始設計您的專屬問卷</span></button><button type="button" class="form-create-card" data-form-create-mode="template"><span class="form-create-icon" aria-hidden="true">${icon('layers')}</span><strong>問卷範本</strong><span>從問卷範本中挑選建立</span></button></div>`);
    return;
  }
  const template=mode==='template';
  modal(template?'從問卷範本建立':'建立空白問卷',`<form data-form-editor data-dirty="false" class="form-basic-editor">${template?`<label class="field">選擇問卷範本<select name="template_id" required><option value="">請選擇範本</option>${formsUI.templates.map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select></label>`:'<input type="hidden" name="template_id" value="">'}<label class="field">問卷名稱<input name="name" required maxlength="${cap('FORM_NAME_MAX')}" placeholder="輸入名稱"></label><p class="subtitle">${template?'範本的題目與說明會一起複製，可先儲存為草稿。':'建立空白草稿後，即可加入題目、分區與說明內容。'}</p><p class="form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">建立草稿</button></div></form>`);
}
document.addEventListener('click',event=>{
  const choice=event.target.closest('[data-form-create-mode]');if(!choice||state.busy)return;
  formCreateModal(choice.dataset.formCreateMode);
});

const formSending={prepared:null,jobId:null,retryJobId:null,formId:null,channel:null};
const formReplies={formId:null,list:null,detail:null,filters:{query:'',time_field:'submitted',date_from:'',date_to:''},page:1,epoch:0};
function formReplyQuery(){return new URLSearchParams({form_id:formReplies.formId,...formReplies.filters,page:String(formReplies.page)}).toString();}
async function formLoadReplies(){
  const epoch=++formReplies.epoch,channel=lineUI.channel;
  const result=await api('/api/forms/responses?'+formReplyQuery());
  if(epoch!==formReplies.epoch||channel!==lineUI.channel||formsUI.mode!=='responses')return;
  formReplies.list=result;formReplies.page=result.page;formReplies.detail=null;render();
}
function formAttachmentButton(file,action,label){return formButton(label,action,file.attachment_id,'data-name="'+esc(file.original_name)+'"');}
function formResponsePage(row){
  const detail=formReplies.detail;
  if(detail)return heading('回覆詳細資料','依提交時的題目與選項快照顯示；內容由填寫者自述。',formButton('返回回覆清單','response-list',row.form_id))+
    `<section class="panel panel-body"><h2>回覆資訊</h2><p class="form-response-id">回覆代號：${esc(detail.response_id)}</p><p>首次提交：${esc(formTimeLabel(detail.first_submitted_at))}</p><p>最後更新：${esc(formTimeLabel(detail.updated_at))}</p></section>`+
    detail.items.map(item=>['section','content'].includes(item.type)?`<section class="panel panel-body form-section"><h2>${esc(item.title)}</h2><p class="form-response-text">${esc(item.description)}</p></section>`:`<section class="panel panel-body form-section"><h2>${esc(item.title)}</h2><p class="subtitle">${esc(FormValidation.rules.types[item.type]||item.type)}</p>${item.description?`<p class="form-response-text">${esc(item.description)}</p>`:''}${item.type==='attachment'?`<div class="form-response-attachments">${item.attachments.map(file=>`<article class="form-response-file">${file.thumbnail_name?`<button type="button" class="form-response-thumbnail" data-action="form-response-enlarge" data-id="${esc(file.attachment_id)}" data-name="${esc(file.original_name)}" aria-label="放大 ${esc(file.original_name)}"><img data-response-thumbnail="${esc(file.attachment_id)}" alt="${esc(file.original_name)}" hidden><span data-thumbnail-status>載入縮圖中</span></button>`:icon('file')}<div><h3>${esc(file.original_name)}</h3><p>${esc(file.extension.toUpperCase())} · ${(file.byte_size/1024).toFixed(1)} KiB</p>${formAttachmentButton(file,'response-download','下載附件')}</div></article>`).join('')||'<p>未提供附件，或附件已移除。</p>'}</div>`:`<p class="form-response-text">${esc(item.text)||'未填寫'}</p>`}</section>`).join('');
  const list=formReplies.list,f=formReplies.filters;
  return heading(row.name+' · 回覆管理','回覆筆數不等於填寫人數；姓名等內容由填寫者自述。',formButton('返回基本資料','open',row.form_id)+(formsUI.capabilities.export?formButton('匯出 CSV','response-export',row.form_id):''))+
    `<section class="panel panel-body"><h2>搜尋與篩選</h2><div class="form-response-filters"><label class="field">搜尋填寫內容或回覆代號<input id="form-response-query" type="search" maxlength="${cap('FORM_TEXT_MAX')}" value="${esc(f.query)}"></label><label class="field">篩選時間<select id="form-response-time">${options([['submitted','首次提交'],['updated','最後更新']],f.time_field)}</select></label><label class="field">起始日期（台北）<input id="form-response-from" type="date" value="${esc(f.date_from)}"></label><label class="field">結束日期（台北，含當日）<input id="form-response-to" type="date" value="${esc(f.date_to)}"></label></div>${formButton('套用篩選','response-filter',row.form_id)}<p class="subtitle">CSV 匯出目前篩選範圍的所有回覆；電話欄位以文字保護，保留前導零與 +。</p></section>`+
    `<section class="panel panel-body form-section"><h2>回覆清單</h2><p role="status">${list?'共 '+list.total+' 份回覆':'載入中…'}</p><div class="form-response-list">${list?.responses.map(reply=>`<article class="form-response-row"><div><h3 class="form-response-id">回覆 ${esc(reply.response_id)}</h3><p class="form-response-summary">${esc(reply.summary)||'未提供文字答案'}</p><p class="subtitle">首次提交：${esc(formTimeLabel(reply.first_submitted_at))}<br>最後更新：${esc(formTimeLabel(reply.updated_at))}</p></div>${formButton('查看答案','response-detail',reply.response_id)}</article>`).join('')||(!list?'':'<p>沒有符合篩選的回覆。</p>')}</div>${list?`<div class="form-actions">${formButton('上一頁','response-page',String(list.page-1),list.page<=1?'disabled':'')}<span>${list.page} / ${list.pages}</span>${formButton('下一頁','response-page',String(list.page+1),list.page>=list.pages?'disabled':'')}</div>`:''}</section>`;
}
async function formResponseBinary(url){
  const headers={};if(!remote)headers.Authorization='Bearer '+token;
  if(lineUI.channel)headers['X-Line-Channel']=lineUI.channel;
  if(organization)headers['X-Workspace-Organization']=encodeURIComponent(organization);
  if(viewAs){headers['X-Workspace-View-As']=viewAs;if(previewOrganization)headers['X-Workspace-Preview-Organization']=encodeURIComponent(previewOrganization);}
  let response;
  try{response=await fetch(url,{headers,credentials:'same-origin',redirect:'error',cache:'no-store'});}catch{throw Error('連線中斷，請稍後重試或重新登入。');}
  if(!response.ok){let message='下載失敗，請確認權限或重新登入。';try{message=(await response.json()).error||message;}catch{}throw Error(message);}
  return response.blob();
}
function formAttachmentApi(id,kind){return '/api/forms/attachment?'+new URLSearchParams({form_id:formReplies.formId,attachment_id:id,kind});}
function formBlobData(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('無法讀取圖片。'));reader.readAsDataURL(blob);});}
async function formLoadThumbnails(){
  const epoch=formReplies.epoch;
  await Promise.all([...document.querySelectorAll('[data-response-thumbnail]')].map(async img=>{
    const status=img.parentElement.querySelector('[data-thumbnail-status]');
    try{const src=await formBlobData(await formResponseBinary(formAttachmentApi(img.dataset.responseThumbnail,'thumb')));if(epoch!==formReplies.epoch||!img.isConnected)return;img.src=src;img.hidden=false;status.hidden=true;}
    catch(exc){if(img.isConnected)status.textContent=exc.message;}
  }));
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action="form-responses"],[data-action^="form-response-"]');if(!button||button.disabled||state.busy)return;
  const action=button.dataset.action.slice(5),id=button.dataset.id;
  try{
    if(action==='responses'){
      if(!formCanLeave())return;
      if(formReplies.formId!==id){formReplies.filters={query:'',time_field:'submitted',date_from:'',date_to:''};formReplies.page=1;formReplies.list=null;}
      formReplies.formId=id;formsUI.selected=id;formsUI.mode='responses';formDesignerReset();render();await formLoadReplies();return;
    }
    if(action==='response-filter'){
      formReplies.filters={query:$('form-response-query').value,time_field:$('form-response-time').value,date_from:$('form-response-from').value,date_to:$('form-response-to').value};formReplies.page=1;await formLoadReplies();return;
    }
    if(action==='response-page'){formReplies.page=Number(id);await formLoadReplies();return;}
    if(action==='response-list'){await formLoadReplies();return;}
    if(action==='response-detail'){
      const channel=lineUI.channel,epoch=++formReplies.epoch,result=await api('/api/forms/responses/detail?'+new URLSearchParams({form_id:formReplies.formId,response_id:id}));
      if(epoch!==formReplies.epoch||channel!==lineUI.channel||formsUI.mode!=='responses')return;
      formReplies.detail=result.response;render();await formLoadThumbnails();return;
    }
    button.disabled=true;
    if(action==='response-enlarge'){
      const src=await formBlobData(await formResponseBinary(formAttachmentApi(id,'view')));
      modal('圖片預覽',`<img class="form-response-image" src="${esc(src)}" alt="${esc(button.dataset.name)}"><p>${esc(button.dataset.name)}</p>`);
    }else{
      const blob=await formResponseBinary(action==='response-export'?'/api/forms/responses/export?'+formReplyQuery():formAttachmentApi(id,'download'));
      const link=document.createElement('a'),url=URL.createObjectURL(blob);link.href=url;link.download=action==='response-export'?(formsUI.rows.find(r=>r.form_id===formReplies.formId).name+'-回覆.csv'):button.dataset.name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  }catch(exc){notice(exc.message,true);}finally{button.disabled=false;}
});
function formSendModal(id,mode){
  const row=formsUI.rows.find(r=>r.form_id===id);formSending.prepared=null;formSending.retryJobId=null;formSending.formId=id;formSending.channel=lineUI.channel;
  const contacts=state.contacts.filter(r=>r.active);
  modal(mode==='remind'?'一般提醒':'發送問卷',`<form data-form-send data-id="${esc(id)}" data-mode="${mode}"><p>${esc(row.name)}：選擇聯絡對象，再預覽確認。</p><p class="subtitle">${mode==='remind'?'提醒會加上「若已填寫，請忽略」。':''}回覆不綁定聯絡對象，不判斷個人已填或未填。</p><fieldset class="form-send-contacts"><legend>聯絡對象</legend>${contacts.map(r=>`<label class="check-label"><input type="checkbox" name="ids" value="${esc(r.recipient_id)}">${esc(r.custom_name||r.display_name||r.recipient_id.slice(-8))}</label>`).join('')||'<p>沒有可接收訊息的聯絡對象。</p>'}</fieldset><label class="field">訊息內容<textarea name="body" rows="4" required maxlength="${cap('TEXT_MESSAGE_MAX')}">${esc(mode==='remind'?'提醒您填寫「'+row.name+'」。':'邀請您填寫「'+row.name+'」。')}</textarea></label><p class="form-error" role="alert" hidden></p><button type="submit" class="btn primary">預覽訊息</button><div data-send-preview></div></form>`);
}
function formSendPreview(prepared,retry=false){
  formSending.prepared=prepared;formSending.jobId=crypto.randomUUID();
  return `<section class="form-section"><h3>確認訊息與 ${prepared.contacts.length} 個聯絡對象</h3><p>${prepared.contacts.map(r=>esc(r.label)).join('、')}</p><pre class="form-send-message">${esc(prepared.message)}</pre><p>請確認後發送；LINE 接受訊息不代表已讀。</p>${formButton(retry?'確認重試失敗項目':'確認發送',retry?'send-retry-confirm':'send-confirm',prepared.form_id)}</section>`;
}
const formDeliveryNames={pending:'等待中',sending:'發送中',accepted:'發送成功',failed:'發送失敗',unknown:'結果不明',cancelled:'已取消'};
async function formSendHistory(id){
  const result=await api('/api/forms/send/history?form_id='+encodeURIComponent(id));
  const lastReminder=new Map(result.notifications.map(n=>[n.recipient_id,n.last_reminded_at]));
  const deliveries=result.jobs.flatMap(j=>j.deliveries),count=status=>deliveries.filter(d=>d.status===status).length;
  modal('問卷發送紀錄',`<p>通知聯絡對象：${result.counts.notifications} · 回覆：${result.counts.responses} 份（回覆數不等於人數）</p><p>發送成功：${count('accepted')} · 失敗：${count('failed')} · 結果不明：${count('unknown')}</p><p class="subtitle">僅能手動重試明確失敗項目；結果不明不會自動重送。</p>${formButton('重新整理','send-refresh',id)}${result.jobs.map(job=>`<section class="form-section"><h3>${job.mode==='remind'?'一般提醒':'問卷發送'} · ${esc(formTimeLabel(job.created_at))}</h3><ul>${job.deliveries.map(d=>`<li>${esc(d.label)}：${formDeliveryNames[d.status]||esc(d.status)}${d.error?' · '+esc(d.error):''}${lastReminder.get(d.recipient_id)?' · 最後提醒：'+esc(formTimeLabel(lastReminder.get(d.recipient_id))):''}</li>`).join('')}</ul>${formsUI.capabilities.send&&job.deliveries.some(d=>d.status==='failed')&&!job.deliveries.some(d=>['pending','sending'].includes(d.status))?formButton('重試失敗項目','send-retry',id,'data-job="'+esc(job.job_id)+'"'):''}</section>`).join('')||'<p>尚無發送紀錄。</p>'}`);
}
document.addEventListener('input',event=>{
  const form=event.target.closest('[data-form-send]');if(!form)return;
  formSending.prepared=null;form.querySelector('[data-send-preview]').replaceChildren();
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.hasAttribute('data-form-send'))return;event.preventDefault();if(state.busy)return;
  const error=form.querySelector('.form-error'),button=form.querySelector('[type="submit"]');button.disabled=true;error.hidden=true;state.busy=true;
  try{const prepared=await api('/api/forms/send/preview',{form_id:form.dataset.id,mode:form.dataset.mode,ids:new FormData(form).getAll('ids'),body:form.elements.body.value});form.querySelector('[data-send-preview]').innerHTML=formSendPreview(prepared);}
  catch(exc){error.textContent=exc.message;error.hidden=false;}finally{state.busy=false;button.disabled=false;}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action^="form-send"],[data-action="form-remind"]');if(!button||button.disabled||state.busy)return;
  const action=button.dataset.action.slice(5),id=button.dataset.id;
  try{
    if(action==='send'||action==='remind'){if(formCanLeave())formSendModal(id,action==='remind'?'remind':'invite');return;}
    if(action==='send-history'||action==='send-refresh'){await formSendHistory(id);return;}
    if(action==='send-retry'){
      const prepared=await api('/api/forms/send/retry-preview',{form_id:id,retry_job_id:button.dataset.job});formSending.retryJobId=button.dataset.job;formSending.channel=lineUI.channel;
      modal('重試失敗項目',formSendPreview(prepared,true));return;
    }
    if(!['send-confirm','send-retry-confirm'].includes(action)||!formSending.prepared)return;
    if(formSending.channel!==lineUI.channel)throw Error('OA 已切換，請重新選擇聯絡對象。');
    button.disabled=true;state.busy=true;
    await api(action==='send-retry-confirm'?'/api/forms/send/retry':'/api/forms/send',{...formSending.prepared,job_id:formSending.jobId,retry_job_id:formSending.retryJobId});
    formSending.prepared=null;await loadForms();render();await formSendHistory(id);
  }catch(exc){button.disabled=false;$('modal-error').textContent=exc.message;$('modal-error').hidden=false;}finally{state.busy=false;}
});
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
  const form=event.target;
  if(form.hasAttribute('data-form-folder')){
    event.preventDefault();if(state.busy)return;const button=form.querySelector('[type="submit"]'),error=form.querySelector('.form-error');button.disabled=true;state.busy=true;
    const action=form.dataset.operation,values=Object.fromEntries(new FormData(form));
    try{const result=await api('/api/forms/folder',{...values,action,...(action==='move'?{form_id:form.dataset.id}:{folder_id:form.dataset.id})});if(action==='create')formsUI.folder=result.folder_id;await loadForms();$('modal').close();render();notice('資料夾已更新。');}catch(exc){error.textContent=exc.message;error.hidden=false;button.disabled=false;}finally{state.busy=false;}return;
  }
  if(!form.hasAttribute('data-form-editor'))return;
  event.preventDefault();const submit=form.querySelector('[type="submit"]'),error=form.querySelector('.form-error');
  if(submit.disabled||state.busy)return;submit.disabled=true;error.hidden=true;state.busy=true;
  const values=Object.fromEntries(new FormData(form)),isNew=!form.dataset.id;
  if(!isNew)values.form_id=form.dataset.id;else values.folder_id=formsUI.folder==='all'?'':formsUI.folder;
  if('deadline_at' in values)values.deadline_at=values.deadline_at?values.deadline_at+':00+08:00':'';
  try{
    const result=await api('/api/forms/save',values);formsUI.selected=result.form.form_id;formsUI.mode="basic";formDesignerReset();
    await loadForms();form.dataset.dirty='false';if(isNew)$('modal').close();
    render();notice('表單已儲存。');
  }catch(exc){error.textContent=exc.message;error.hidden=false;submit.disabled=false;}
  finally{state.busy=false;}
});
document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-action^="form-"]');if(!target||target.disabled||state.busy)return;
  const action=target.dataset.action.slice(5),id=target.dataset.id;
  if(['responses','response-detail','response-list','response-filter','response-page','response-export','response-download','response-enlarge','send','remind','send-history','send-confirm','send-refresh','send-retry','send-retry-confirm'].includes(action))return;
  try{
    if(action==='layout'){formsUI.layout=id==='grid'?'grid':'list';try{localStorage.setItem('forms-layout',formsUI.layout);}catch{}render();return;}
    if(action==='folder-select'){formsUI.folder=id;render();return;}
    if(action==='folder-new'){formFolderModal('create');return;}
    if(action==='folder-rename'){formFolderModal('rename',id);return;}
    if(action==='folder-delete'){formFolderModal('delete',id);return;}
    if(action==='move'){formFolderModal('move',id);return;}
    if(action==='design'||action==='preview'){formEnterMode(action,id);return;}
    if(action==='new'){if(formCanLeave())formCreateModal();return;}
    if(action==='back'){if(!formCanLeave())return;formsUI.selected=null;formsUI.mode="basic";formDesignerReset();render();return;}
    if(action==='open'){
      if(!formCanLeave())return;
      const result=await api('/api/forms/detail?form_id='+encodeURIComponent(id));
      formsUI.rows=formsUI.rows.map(row=>row.form_id===id?result.form:row);formsUI.selected=id;formsUI.mode="basic";formDesignerReset();render();return;
    }
    if(action==='delete'){
      const result=await api('/api/forms/detail?form_id='+encodeURIComponent(id));const row=result.form;
      modal('刪除表單？',`<p>將刪除「${esc(row.name)}」、${row.counts.notifications} 份通知、${row.counts.responses} 份回覆及其附件。刪除後問卷與修改連結失效。</p><div class="form-actions">${formButton('確認刪除','confirm-delete',id,'data-notifications="'+row.counts.notifications+'" data-responses="'+row.counts.responses+'"')}</div>`);return;
    }
    if(action==='status'&&!formCanLeave())return;
    target.disabled=true;
    if(action==='copy'){const result=await api('/api/forms/copy',{form_id:id});formsUI.selected=result.form.form_id;formsUI.mode="basic";formDesignerReset();}
    else if(action==='status')await api('/api/forms/status',{form_id:id,status:target.dataset.status});
    else if(action==='confirm-delete'){await api('/api/forms/delete',{form_id:id,confirm_counts:{notifications:Number(target.dataset.notifications),responses:Number(target.dataset.responses)}});$('modal').close();formsUI.selected=null;}
    else return;
    await loadForms();render();notice('表單已更新。');
  }catch(exc){target.disabled=false;if($('modal').open){$('modal-error').textContent=exc.message;$('modal-error').hidden=false;}else notice(exc.message,true);}
});

"use strict";
(()=>{
 const data=JSON.parse(document.getElementById('public-form-data').dataset.json),root=document.getElementById('public-form-root');
 FormValidation.configure(data.rules);
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const params=new URLSearchParams(location.search),shareUrl=location.pathname+'?token='+encodeURIComponent(params.get('token'));
 let storageKey='public-form-draft:'+shareUrl+(params.has('edit')?'&edit='+encodeURIComponent(params.get('edit')):'');
 let restored=false,storageUnavailable=false,restoreMessage='',resetting=false,cached=null;
 try{cached=JSON.parse(localStorage.getItem(storageKey)||'null');}catch{storageUnavailable=true;}
 if(cached&&cached.answers&&typeof cached.answers==='object'&&!Array.isArray(cached.answers)){
  if(cached.responseUpdatedAt!==data.response_updated_at){restoreMessage='回覆已在其他頁面更新，已載入伺服器最新版本。';try{localStorage.removeItem(storageKey);}catch{}}
  else{
   for(const q of data.questions){
    if(q.type==='attachment'||cached.types?.[q.id]!==q.type||!(q.id in cached.answers))continue;
    data.answers[q.id]=cached.answers[q.id];
   }
   if(!data.submitted&&typeof cached.submissionKey==='string')data.submission_key=cached.submissionKey;
   restored=true;
   if(cached.formUpdatedAt!==data.form.updated_at)restoreMessage+=' 問卷內容已更新，請確認目前題目。';
   if(cached.hadAttachments)restoreMessage+=' 未提交的附件不保留，請重新選取並上傳。';
  }
 }
 const answers=structuredClone(data.answers),otherId=data.rules.other_id;
 const pages=FormValidation.pages(data.questions);
 let currentPage=restored?Math.max(0,Math.min(pages.length-1,Number.isInteger(cached.page)?cached.page:0)):0;
 function saveDraft(){
  if(resetting)return;
  try{
   localStorage.setItem(storageKey,JSON.stringify({page:currentPage,answers:Object.fromEntries(data.questions.filter(q=>q.type!=='attachment'&&!data.rules.display_types.includes(q.type)).filter(q=>q.id in answers).map(q=>[q.id,answers[q.id]])),submissionKey:data.submission_key,responseUpdatedAt:data.response_updated_at,formUpdatedAt:data.form.updated_at,types:Object.fromEntries(data.questions.map(q=>[q.id,q.type])),hadAttachments:[...uploads.values()].flat().length>0}));
   document.getElementById('draft-status').textContent='草稿已自動儲存於此瀏覽器，可關閉後繼續填寫。';
  }catch{document.getElementById('draft-status').textContent='此瀏覽器無法儲存草稿，關閉頁面可能遺失尚未送出的內容。';}
 }
 const uploads=new Map();for(const q of data.questions.filter(q=>q.type==='attachment'))uploads.set(q.id,(answers[q.id]||[]).map(id=>({meta:data.attachments.find(a=>a.attachment_id===id),status:'done'})).filter(item=>item.meta));
 const date=value=>value?new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}):'不限期';
 function hint(q){
  const v=q.validation||{},r=q.type==='rating'?(q.rating||data.rules.rating_default):null,h=[];
  if(r)h.push(`${r.min}：${r.lower_label||'最低'}；${r.max}：${r.upper_label||'最高'}`);
  if(v.enabled){
   if(v.format==='phone')h.push(data.rules.phone_modes[v.phone_mode||'tw_mobile']+(v.allow_extension?'（可含分機）':''));
   if(v.format==='email')h.push('例如 name@example.com');
   for(const [key,label,suffix] of [['min_length','至少','字'],['max_length','最多','字'],['min','最小',''],['max','最大',''],['count_min','至少選','項'],['count_max','最多選','項'],['count_exact','請選','項']])if(v[key]!==undefined)h.push(`${label} ${v[key]} ${suffix}`);
   if(v.integer)h.push('請填寫整數');if(v.date_min)h.push('自 '+v.date_min);if(v.date_max)h.push('至 '+v.date_max);
  }
  return h.join('；');
 }
 function control(q){
  const id=esc(q.id),value=answers[q.id],common=`data-answer="${id}" aria-describedby="description-${id} error-${id}"`,label=`${esc(q.title)}${q.required?' <span class="required">（必填）</span>':' <span class="optional">（選填）</span>'}`;
  if(data.rules.choice_types.includes(q.type)){
   const multi=q.type==='multiple_choice',selected=typeof value==='string'?[value]:multi?(Array.isArray(value)?value:value?.option_ids||[]):value?.option_id?[value.option_id]:[],items=q.options.concat(q.allow_other?[{id:otherId,label:'其他'}]:[]);
   const controls=q.type==='dropdown'?`<select id="answer-${id}" ${common}><option value="">請選擇</option>${items.map(o=>`<option value="${esc(o.id)}" ${selected.includes(o.id)?'selected':''}>${esc(o.label)}</option>`).join('')}</select>`:items.map(o=>`<label class="choice"><input ${common} type="${multi?'checkbox':'radio'}" name="choice-${id}" value="${esc(o.id)}" ${selected.includes(o.id)?'checked':''}><span>${esc(o.label)}</span></label>`).join('');
   return `<fieldset><legend>${label}</legend>${controls}${q.allow_other?`<label class="other" ${selected.includes(otherId)?'':'hidden'}>其他補充（選擇其他時必填）<input ${common} data-other type="text" value="${esc(value?.other||'')}"></label>`:''}</fieldset>`;
  }
  let input;
  if(q.type==='paragraph')input=`<textarea id="answer-${id}" ${common} rows="4">${esc(value||'')}</textarea>`;
  else if(q.type==='attachment'){const a=q.attachment;return `<label>${label}<input ${common} data-upload-q="${id}" type="file" multiple accept="${a.extensions.map(ext=>'.'+ext).join(',')}"></label><p class="hint">格式：${a.extensions.join('、')}；最多 ${a.max_files} 檔、單檔 ${a.max_file_bytes/1048576} MiB、合計 ${a.max_total_bytes/1048576} MiB。</p><div data-upload-list="${id}" aria-live="polite"></div>`;}
  else{
   const type=['date','time'].includes(q.type)?q.type:'text',mode=q.type==='number'||q.type==='rating'?'decimal':q.validation?.enabled&&q.validation.format==='phone'?'tel':q.validation?.enabled&&q.validation.format==='email'?'email':'text';
   input=`<input id="answer-${id}" ${common} type="${type}" inputmode="${mode}" value="${esc(value??'')}">`;
  }
  return `<label for="answer-${id}">${label}</label>${input}`;
 }
 root.innerHTML=`<header class="form-intro"><p class="eyebrow">問卷填寫</p><h1>${esc(data.form.name)}</h1><p class="description">${esc(data.form.description)}</p><p>截止：${esc(date(data.form.deadline_at))}（台北時間）</p><p class="required">標示「必填」的題目請務必填寫。</p></header><p id="response-status" role="status">${data.submitted?'已收到你的回覆，可在截止前修改。首次提交：'+esc(date(data.first_submitted_at)):''}${data.definition_changed?' 問卷內容已更新，請確認目前題目後再保存修改。':''}</p><section class="draft-tools"><p id="draft-status" role="status">${esc(storageUnavailable?'此瀏覽器無法儲存草稿，請保持頁面開啟。':restored?'已恢復關閉前的填寫草稿。 '+restoreMessage:restoreMessage||'填寫內容會自動儲存於此瀏覽器，送出後才建立正式回覆；未提交的附件重新開啟後需重傳。')}</p><button id="restart-answer" type="button">重新填寫（一鍵清除）</button></section><p id="form-error" class="error" role="alert" hidden></p><form id="public-form" novalidate>${pages.map((questions,index)=>`<div data-form-page="${index}" ${index===currentPage?'':'hidden'}>${questions.map(q=>q.type==='content'?FormValidation.contentMarkup(q,location.pathname+'/content/'+q.content.image_id+'?token='+encodeURIComponent(params.get('token')),true):q.type==='section'?`<section class="section"><h2>${esc(q.title)}</h2><p class="description">${esc(q.description)}</p></section>`:`<section class="question" data-question="${esc(q.id)}">${control(q)}<p class="description hint" id="description-${esc(q.id)}">${esc([q.description,hint(q)].filter(Boolean).join(' · '))}</p><p class="error" id="error-${esc(q.id)}" role="alert" hidden></p></section>`).join('')}</div>`).join('')}<p id="page-status" role="status"></p><div class="page-navigation"><button id="previous-page" type="button">上一頁</button><button id="next-page" type="button">下一頁</button><button id="submit-answer" type="submit">${data.submitted?'儲存修改':'送出回覆'}</button></div></form>`;
 function goPage(index,focus=true){
  currentPage=index;root.querySelectorAll('[data-form-page]').forEach(el=>el.hidden=Number(el.dataset.formPage)!==index);
  document.getElementById('previous-page').hidden=index===0;document.getElementById('next-page').hidden=index===pages.length-1;document.getElementById('submit-answer').hidden=index!==pages.length-1;
  const status=document.getElementById('page-status');status.textContent=`第 ${index+1} / ${pages.length} 頁`;
  if(focus){const block=root.querySelector(`[data-form-page="${index}"]`);block.tabIndex=-1;block.focus();block.scrollIntoView({block:'start'});saveDraft();}
 }
 function revealError(errors){const index=pages.findIndex(qs=>qs.some(q=>errors[q.id]));if(index>=0)goPage(index);root.querySelector('[aria-invalid="true"]')?.focus();}
 goPage(currentPage,false);
 document.getElementById('previous-page').addEventListener('click',()=>{if(!busy)goPage(currentPage-1);});
 document.getElementById('next-page').addEventListener('click',()=>{
  if(busy)return;const qs=pages[currentPage];qs.filter(q=>!data.rules.display_types.includes(q.type)).forEach(read);
  const values=Object.fromEntries(qs.filter(q=>q.id in answers).map(q=>[q.id,answers[q.id]]));
  const errors=FormValidation.validateAnswers(qs,values);show(errors);
  if(Object.keys(errors).length){revealError(errors);return;}
  if(qs.some(q=>(uploads.get(q.id)||[]).some(item=>item.status!=='done'))){show({_form:'請完成本頁附件上傳，或移除失敗的檔案。'});return;}
  goPage(currentPage+1);
 });
 function read(q){
  const block=root.querySelector(`[data-question="${CSS.escape(q.id)}"]`),inputs=[...block.querySelectorAll('[data-answer]:not([data-other])')];
  if(q.type==='attachment')return;
  if(data.rules.choice_types.includes(q.type)){
   const multi=q.type==='multiple_choice',selected=q.type==='dropdown'?inputs[0].value:inputs.filter(i=>i.checked).map(i=>i.value),ids=Array.isArray(selected)?selected:selected?[selected]:[],other=block.querySelector('[data-other]');
   if(other){other.closest('label').hidden=!ids.includes(otherId);}
   const extra=ids.includes(otherId)?other?.value||'':'';
   answers[q.id]=multi?{option_ids:ids,other:extra}:q.allow_other?{option_id:ids[0]||'',other:extra}:ids[0]||'';
  }else answers[q.id]=inputs[0].value;
 }
 function show(errors){
  const global=document.getElementById('form-error');global.hidden=!errors._form;global.textContent=errors._form||'';
  for(const q of data.questions){if(data.rules.display_types.includes(q.type))continue;const el=document.getElementById('error-'+q.id);el.textContent=errors[q.id]||'';el.hidden=!errors[q.id];root.querySelectorAll(`[data-answer="${CSS.escape(q.id)}"]`).forEach(input=>input.setAttribute('aria-invalid',String(Boolean(errors[q.id]))));}
 }
 function attachmentUrl(meta,kind){return location.pathname+`/attachments/${meta.attachment_id}/${kind}?token=${encodeURIComponent(new URLSearchParams(location.search).get('token'))}&draft=${encodeURIComponent(data.draft_key)}`;}
 function drawUploads(qid){
  const list=uploads.get(qid);answers[qid]=list.filter(item=>item.status==='done').map(item=>item.meta.attachment_id);
  root.querySelector(`[data-upload-list="${CSS.escape(qid)}"]`).innerHTML=list.map((item,index)=>`<div class="attachment-item">${item.local?`<img src="${esc(item.local)}" alt="本機圖片預覽">`:item.meta?.thumbnail_name?`<a href="${esc(attachmentUrl(item.meta,'view'))}" target="_blank" rel="noopener"><img src="${esc(attachmentUrl(item.meta,'thumb'))}" alt="${esc(item.meta.original_name)}"></a>`:`<span class="attachment-file-icon"><svg width="32" height="32" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h8l4 4v16H6zM14 2v5h4M9 12h6M9 16h6" fill="none" stroke="currentColor" stroke-width="2"/></svg><strong>${esc((item.meta?.extension||item.file.name.split('.').pop()).toUpperCase())}</strong></span>`}<div><strong>${esc(item.meta?.original_name||item.file.name)}</strong><p>${((item.meta?.byte_size||item.file.size)/1024).toFixed(1)} KiB · ${item.status==='uploading'?'上傳中':item.status==='failed'?'上傳失敗：'+esc(item.error):'上傳完成'}</p>${item.status==='done'?`<a href="${esc(attachmentUrl(item.meta,'download'))}">下載</a> `:''}${item.status==='failed'?`<button type="button" data-upload-retry="${esc(qid)}" data-index="${index}">重試</button>`:''}<button type="button" data-upload-remove="${esc(qid)}" data-index="${index}" ${item.status==='uploading'?'disabled':''}>移除／替換</button></div></div>`).join('');
 }
 async function uploadFile(qid,item){
  item.status='uploading';drawUploads(qid);
  try{
   const keep=(answers[qid]||[]).join(','),url=location.pathname+`/upload?token=${encodeURIComponent(new URLSearchParams(location.search).get('token'))}&draft=${encodeURIComponent(data.draft_key)}&question=${encodeURIComponent(qid)}&keep=${encodeURIComponent(keep)}&upload_id=${item.uploadId}`;
   const response=await fetch(url,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(item.file.name)},body:item.file});const result=await response.json();if(!response.ok)throw Error(result.error||'上傳失敗');item.meta=result;item.status='done';
   if(item.local){URL.revokeObjectURL(item.local);item.local=null;}
  }catch(exc){item.status='failed';item.error=exc instanceof TypeError?'連線失敗，請重試':exc.message;}
  drawUploads(qid);saveDraft();
 }
 for(const qid of uploads.keys())drawUploads(qid);
 root.addEventListener('change',async event=>{const qid=event.target.dataset.uploadQ;if(!qid)return;const files=[...event.target.files];event.target.value='';for(const file of files){const item={file,uploadId:crypto.randomUUID().replaceAll('-',''),status:'uploading',local:['image/jpeg','image/png'].includes(file.type)?URL.createObjectURL(file):null};uploads.get(qid).push(item);saveDraft();await uploadFile(qid,item);}});
 root.addEventListener('click',async event=>{
  const button=event.target.closest('[data-upload-remove],[data-upload-retry]');if(!button)return;const qid=button.dataset.uploadRemove||button.dataset.uploadRetry,list=uploads.get(qid),item=list[Number(button.dataset.index)];if(!item)return;
  if(button.hasAttribute('data-upload-retry')){await uploadFile(qid,item);return;}
  button.disabled=true;
  try{if(item.meta){const response=await fetch(attachmentUrl(item.meta,'remove'),{method:'POST',credentials:'omit'});if(!response.ok)throw Error('移除失敗，請重試。');}if(item.local)URL.revokeObjectURL(item.local);list.splice(Number(button.dataset.index),1);drawUploads(qid);saveDraft();}catch(exc){button.disabled=false;const el=document.getElementById('form-error');el.textContent=exc.message;el.hidden=false;}
 });
 let checked=false,busy=false;
 document.getElementById('restart-answer').addEventListener('click',()=>{
  if(busy)return;resetting=true;
  try{localStorage.removeItem(storageKey);localStorage.removeItem('public-form-draft:'+shareUrl);}catch{}
  for(const list of uploads.values())for(const item of list){if(item.local)URL.revokeObjectURL(item.local);if(item.meta)fetch(attachmentUrl(item.meta,'remove'),{method:'POST',credentials:'omit',keepalive:true}).catch(()=>{});}
  location.assign(shareUrl);
 });
 window.addEventListener('pagehide',()=>{if(!resetting&&!data.submitted)saveDraft();});
 root.addEventListener('input',event=>{const id=event.target.dataset.answer;if(!id)return;read(data.questions.find(q=>q.id===id));saveDraft();if(checked)show(FormValidation.validateAnswers(data.questions,answers));});
 root.addEventListener('change',event=>{const id=event.target.dataset.answer;if(!id)return;read(data.questions.find(q=>q.id===id));saveDraft();if(checked)show(FormValidation.validateAnswers(data.questions,answers));});
 document.getElementById('public-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;if(currentPage<pages.length-1){document.getElementById('next-page').click();return;}const pending=[...uploads.values()].flat().some(item=>item.status!=='done');if(pending){const el=document.getElementById('form-error');el.textContent='請等待附件上傳完成，並重試或移除失敗的檔案。';el.hidden=false;return;}checked=true;data.questions.filter(q=>!data.rules.display_types.includes(q.type)).forEach(read);
  const errors=FormValidation.validateAnswers(data.questions,answers);show(errors);
  if(Object.keys(errors).length){revealError(errors);return;}
  busy=true;const button=document.getElementById('submit-answer');button.disabled=true;button.textContent='送出中…';
  try{
   const response=await fetch(location.pathname+'/submit'+location.search,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers,expected_updated_at:data.form.updated_at,expected_response_updated_at:data.response_updated_at,submission_key:data.submission_key,draft_key:data.draft_key})});
   const result=await response.json();if(!response.ok){if(result.errors){show(result.errors);revealError(result.errors);}else throw Error(result.error||'送出失敗，請再試一次。');return;}
   try{localStorage.removeItem(storageKey);}catch{}
   resetting=true;
   history.replaceState(null,'',result.edit_url);data.submitted=true;data.response_updated_at=result.updated_at;data.first_submitted_at=result.first_submitted_at;storageKey='public-form-draft:'+result.edit_url;resetting=false;
   const status=document.getElementById('response-status');status.textContent=result.message+' 首次提交：'+date(result.first_submitted_at)+'；最後更新：'+date(result.updated_at);const link=document.createElement('a');link.href=result.edit_url;link.textContent='保存這份回覆的修改連結';status.append(document.createElement('br'),link);status.append(document.createTextNode('（此連結可查看及修改你的回覆，請自行保存且勿分享。）'));const fresh=document.createElement('a');fresh.href=result.edit_url.split('&edit=')[0];fresh.textContent='填寫另一份回覆';status.append(document.createElement('br'),fresh);status.tabIndex=-1;status.focus();
  }catch(exc){const el=document.getElementById('form-error');el.textContent=exc instanceof TypeError?'連線失敗，輸入已保留，請再試一次。':exc.message||'送出失敗，輸入已保留，請再試一次。';el.hidden=false;}
  finally{busy=false;button.disabled=false;button.textContent=data.submitted?'儲存修改':'送出回覆';}
 });
})();

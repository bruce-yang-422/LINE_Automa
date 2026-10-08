"use strict";
const formDesign={id:null,questions:[],version:'',dirty:false,errors:{},drag:null,previewAnswers:{},previewErrors:{},previewChecked:false,previewPage:0};
const formClone=value=>JSON.parse(JSON.stringify(value));
const formId=()=>crypto.randomUUID().replaceAll('-','');
function formDesignerReset(){Object.assign(formDesign,{id:null,questions:[],version:'',dirty:false,errors:{},drag:null,previewAnswers:{},previewErrors:{},previewChecked:false,previewPage:0});}
function formEnsureDesign(row){
  if(formDesign.id===row.form_id)return;
  formDesignerReset();formDesign.id=row.form_id;formDesign.version=row.updated_at;formDesign.questions=formClone(row.questions);
}
function formEnterMode(mode,id){
  const row=formsUI.rows.find(row=>row.form_id===id||row.form_id===formsUI.selected);if(!row)return;
  if(mode!=='basic'&&document.querySelector('#page [data-form-editor][data-dirty="true"]')&&!formCanLeave())return;
  if(mode==='basic'&&!formCanLeave())return;
  if(mode==='basic')formDesignerReset();else formEnsureDesign(row);
  formsUI.mode=mode;formsUI.selected=row.form_id;
  if(mode==='preview'){formDesign.previewErrors={};formDesign.previewChecked=false;formDesign.previewPage=0;}
  render();
}
function formDefaultQuestion(kind='short_text'){
  const q={id:formId(),title:kind==='section'?'新分區':kind==='content'?'新說明':'新題目',description:'',type:kind,required:false,options:[],allow_other:false,validation:{enabled:false}};
  if(kind==='section')q.page_break=true;
  if(kind==='content')q.content={kind:'text',image_id:'',youtube_url:''};
  if(FormValidation.rules.choice_types.includes(kind))q.options=[{id:formId(),label:'選項一'}];
  if(kind==='rating')q.rating=formClone(FormValidation.rules.rating_default);
  if(kind==='attachment')q.attachment={extensions:['jpg','jpeg','png','pdf'],max_files:cap('FORM_ATTACHMENTS_PER_QUESTION'),max_file_bytes:cap('FORM_ATTACHMENT_MAX_BYTES'),max_total_bytes:cap('FORM_ATTACHMENT_TOTAL_MAX_BYTES')};
  return q;
}
function formDesignControl(label,path,value,type='text',attrs=''){
  return `<label class="field">${esc(label)}<input data-q-field="${esc(path)}" type="${type}" value="${esc(value??'')}" ${attrs}></label>`;
}
function formDesignSelect(label,path,value,entries,attrs=''){
  return `<label class="field">${esc(label)}<select data-q-field="${esc(path)}" ${attrs}>${options(entries,value)}</select></label>`;
}
function formDesignCheck(label,path,checked,attrs=''){
  return `<label class="check-label"><input data-q-field="${esc(path)}" type="checkbox" ${checked?'checked':''} ${attrs}>${esc(label)}</label>`;
}
function formDesignButton(title,action,attrs=''){
  return `<button type="button" class="btn small" data-design-action="${action}" ${attrs}>${esc(title)}</button>`;
}
function formValidationFields(q,readonly){
  const v=q.validation||{enabled:false},supported=Boolean(FormValidation.rules.validation_keys[q.type]),off=readonly||!v.enabled?'disabled':'';
  if(!supported)return '';
  let fields='';
  if(['short_text','paragraph'].includes(q.type)){
    fields=formDesignControl('最少字數','validation.min_length',v.min_length,'number',`min="0" max="${cap('FORM_TEXT_MAX')}" ${off}`)+formDesignControl('最多字數','validation.max_length',v.max_length,'number',`min="0" max="${cap('FORM_TEXT_MAX')}" ${off}`);
    if(q.type==='short_text'){
      fields=formDesignSelect('格式','validation.format',v.format||'none',Object.entries(FormValidation.rules.formats),off)+fields;
      if(v.format==='phone')fields+=formDesignSelect('電話類型','validation.phone_mode',v.phone_mode||'tw_mobile',Object.entries(FormValidation.rules.phone_modes),off)+formDesignCheck('市話允許分機','validation.allow_extension',v.allow_extension,off);
    }
  }else if(q.type==='number')fields=formDesignCheck('只允許整數','validation.integer',v.integer,off)+formDesignControl('最小值','validation.min',v.min,'number',`step="any" ${off}`)+formDesignControl('最大值','validation.max',v.max,'number',`step="any" ${off}`);
  else if(q.type==='multiple_choice')fields=['min','max','exact'].map((key,i)=>formDesignControl(['最少選取數','最多選取數','恰好選取數'][i],'validation.count_'+key,v['count_'+key],'number',`min="0" max="${q.options.length+Number(Boolean(q.allow_other))}" ${off}`)).join('');
  else if(q.type==='date')fields=formDesignControl('最早日期','validation.date_min',v.date_min,'date',off)+formDesignControl('最晚日期','validation.date_max',v.date_max,'date',off);
  return `<details class="form-validation-settings" ${v.enabled?'open':''}><summary>答案驗證${v.enabled?'（已啟用）':'（未啟用）'}</summary>${formDesignCheck('啟用答案驗證','validation.enabled',v.enabled,readonly)}<div class="form-design-fields">${fields}${formDesignControl('自訂錯誤提示','validation.message',v.message,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${off}`)}</div></details>`;
}
function formQuestionCard(q,index,editable){
  const readonly=editable?'':'disabled',choice=FormValidation.rules.choice_types.includes(q.type),error=formDesign.errors[q.id]||formDesign.errors[String(index)]||'';
  const buttons=editable?`<div class="form-question-actions">${formDesignButton('上移','up',index===0?'disabled':'')}${formDesignButton('下移','down',index===formDesign.questions.length-1?'disabled':'')}${formDesignButton(q.type==='section'?'複製分區':q.type==='content'?'複製說明':'複製題目','copy')}${formDesignButton(q.type==='section'?'刪除分區':q.type==='content'?'刪除說明':'刪除題目','remove')}</div>`:'';
  if(q.type==='content')return `<article class="form-question-card form-content-editor" data-qid="${esc(q.id)}"><header><h3>說明 ${formDesign.questions.slice(0,index+1).filter(item=>item.type==='content').length}</h3><span class="form-card-kind">不需作答</span>${editable?`<button type="button" class="btn small form-drag-handle" draggable="true" data-form-drag="${esc(q.id)}" aria-label="拖曳說明內容">${icon('menu')}拖曳排序</button>`:''}</header><p class="form-error form-question-error" role="alert" ${error?'':'hidden'}>${esc(error)}</p><div class="form-design-fields form-question-primary">${formDesignControl('標題（選填）','title',q.title,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}${formDesignSelect('內容類型','content.kind',q.content.kind,Object.entries(FormValidation.rules.content_kinds),readonly)}</div><label class="field">說明文字（選填）<textarea data-q-field="description" rows="3" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(q.description)}</textarea></label>${q.content.kind==='image'?`<label class="field">上傳圖片（JPG／PNG，最多 8 MB）<input type="file" accept="image/jpeg,image/png" data-form-content-upload ${readonly}></label>${q.content.image_id?formDesignButton('移除圖片','content-image-remove',readonly):''}`:q.content.kind==='video'?formDesignControl('YouTube 影片連結','content.youtube_url',q.content.youtube_url,'url',`placeholder="https://www.youtube.com/watch?v=…" maxlength="1000" ${readonly}`):''}<div class="form-content-example"><p class="subtitle">內容示意</p>${FormValidation.contentMarkup(q)}</div>${editable?`<footer class="form-question-footer">${buttons}</footer>`:''}</article>`;
  const optionFields=choice?`<fieldset class="form-choice-settings"><legend>選項</legend>${q.options.map((o,i)=>`<div class="form-option-row" data-option-id="${esc(o.id)}"><label class="field">選項 ${i+1}<input data-q-field="option.label" value="${esc(o.label)}" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}></label>${editable?formDesignButton('上移','option-up',i===0?'disabled':'')+formDesignButton('下移','option-down',i===q.options.length-1?'disabled':'')+formDesignButton('移除','option-remove'):''}</div>`).join('')}${editable?formDesignButton('新增選項','option-add',q.options.length>=cap('FORM_OPTIONS_MAX')?'disabled':''):''}${q.type!=='dropdown'?formDesignCheck('開啟其他（選取後需補充文字）','allow_other',q.allow_other,readonly):''}${q.allow_other?`<div class="form-other-example" aria-label="其他選項示意"><span aria-hidden="true" class="form-other-marker ${q.type==='multiple_choice'?'multiple':''}"></span><label class="field">其他：<input type="text" placeholder="填寫者選取其他後，在此補充文字" disabled></label><small>填寫示意 · 選取後必須補充文字</small></div>`:''}</fieldset>`:'';
  let settings='';
  if(q.type==='rating'){
    const r=q.rating||FormValidation.rules.rating_default;
    settings=`<div class="form-design-fields">${formDesignControl('最低分','rating.min',r.min,'number',readonly)}${formDesignControl('最高分','rating.max',r.max,'number',readonly)}${formDesignControl('低分說明','rating.lower_label',r.lower_label,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}${formDesignControl('高分說明','rating.upper_label',r.upper_label,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}</div>`;
  }
  if(q.type==='attachment'){
    const a=q.attachment;
    settings=`<fieldset class="form-attachment-settings"><legend>附件限制</legend>${Object.entries(FormValidation.rules.attachment_groups).map(([group,extensions])=>`<details><summary>${esc(group)}</summary><div class="form-extension-list">${extensions.map(ext=>`<label class="check-label"><input data-q-field="attachment.extensions" type="checkbox" value="${ext}" ${a.extensions.includes(ext)?'checked':''} ${readonly}>${ext.toUpperCase()}</label>`).join('')}</div></details>`).join('')}<div class="form-design-fields">${formDesignControl('最多檔案數','attachment.max_files',a.max_files,'number',`min="1" max="${cap('FORM_ATTACHMENTS_PER_QUESTION')}" ${readonly}`)}${formDesignControl('單檔大小（MiB）','attachment.max_file_bytes',a.max_file_bytes/1048576,'number',`min="0" max="${cap('FORM_ATTACHMENT_MAX_BYTES')/1048576}" step="any" ${readonly}`)}${formDesignControl('每題總大小（MiB）','attachment.max_total_bytes',a.max_total_bytes/1048576,'number',`min="0" max="${cap('FORM_ATTACHMENT_TOTAL_MAX_BYTES')/1048576}" step="any" ${readonly}`)}</div></fieldset>`;
  }
  return `<article class="form-question-card" data-qid="${esc(q.id)}"><header><h3>${q.type==='section'?'分區':'題目'} ${formDesign.questions.slice(0,index+1).filter(item=>q.type==='section'?item.type==='section':!FormValidation.rules.display_types.includes(item.type)).length}</h3><span class="form-card-kind">${q.type==='section'?(q.page_break===true?'另起新頁':'同頁標題'):esc(FormValidation.rules.types[q.type])}</span>${editable?`<button type="button" class="btn small form-drag-handle" draggable="true" data-form-drag="${esc(q.id)}" aria-label="拖曳排序第 ${index+1} 個項目">${icon('menu')}拖曳排序</button>`:''}</header><p class="form-error form-question-error" role="alert" ${error?'':'hidden'}>${esc(error)}</p><div class="form-design-fields form-question-primary">${formDesignControl('標題','title',q.title,'text',`required maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}${q.type==='section'?'':formDesignSelect('題型','type',q.type,Object.entries(FormValidation.rules.types).filter(([type])=>!FormValidation.rules.display_types.includes(type)),readonly)}</div><label class="field">說明<textarea data-q-field="description" rows="2" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(q.description||'')}</textarea></label>${!FormValidation.rules.display_types.includes(q.type)?formDesignCheck('必填','required',q.required,readonly):formDesignCheck('從此分區開始新頁','page_break',q.page_break===true,readonly)+'<p class="subtitle">分區只顯示標題與說明；第一個分區不會產生空白頁。</p>'}${optionFields}${settings}${formValidationFields(q,readonly)}${editable?`<footer class="form-question-footer">${buttons}</footer>`:''}</article>`;
}
function formDesignerPage(row){
  formEnsureDesign(row);const editable=formsUI.capabilities.maintain;queueMicrotask(formLoadContentImages);
  return heading('設計題目',row.name,formDesignButton('返回基本資料','basic')+formDesignButton('填寫預覽','preview'))+
    `<form data-form-designer data-dirty="${formDesign.dirty}" novalidate><section class="panel panel-body form-designer-toolbar"><h2>題目與分區</h2><p class="subtitle">題目用來收集答案；分區設定換頁；說明可放文字、圖片或 YouTube 影片。新增分區預設另起新頁。</p><p>${formDesign.questions.filter(q=>!FormValidation.rules.display_types.includes(q.type)).length} 題 · ${formDesign.questions.filter(q=>q.type==='section').length} 個分區 · ${formDesign.questions.filter(q=>q.type==='content').length} 個說明 · ${FormValidation.pages(formDesign.questions).length} 頁 <span class="subtitle">（${formDesign.questions.length} / ${cap('FORM_QUESTIONS_MAX')} 個項目）</span></p><p class="form-save-status" role="status">${formDesign.dirty?'尚未儲存':'變更後請按儲存題目。'}</p><p class="form-error form-design-error" role="alert" hidden></p><div class="form-actions">${editable?formDesignButton('新增題目','add-question')+formDesignButton('新增分區','add-section')+formDesignButton('新增說明／圖片／影片','add-content')+'<button type="submit" class="btn primary">儲存題目</button>':'<p>目前角色只能查看。</p>'}</div></section>${row.counts.responses?'<p class="callout warn">已有回覆。刪題、改題型或修改選項會影響後續填寫；舊答案仍依提交時快照閱讀。</p>':''}<div class="form-question-cards">${formDesign.questions.map((q,i)=>formQuestionCard(q,i,editable)).join('')||empty('尚無題目','使用新增題目或新增分區開始設計。')}</div></form>`;
}
function formPreviewControl(q){
  const value=formDesign.previewAnswers[q.id],qid=esc(q.id),title=esc(q.title),v=q.validation||{},max=cap('FORM_TEXT_MAX');
  const common=`data-answer-id="${qid}" aria-describedby="form-preview-description-${qid} form-preview-error-${qid}"`;
  if(q.type==='paragraph')return `<label class="field">${title}<textarea ${common} rows="3">${esc(value||'')}</textarea></label>`;
  if(q.type==='short_text')return `<label class="field">${title}<input ${common} type="text" ${v.enabled&&v.format==='phone'?'inputmode="tel"':v.enabled&&v.format==='email'?'inputmode="email"':''} value="${esc(value||'')}"></label>`;
  if(q.type==='number'||q.type==='date'||q.type==='time')return `<label class="field">${title}<input ${common} type="${q.type==='number'?'text':q.type}" ${q.type==='number'?'inputmode="decimal"':''} value="${esc(value??'')}"></label>`;
  if(q.type==='rating'){
    const r=q.rating||FormValidation.rules.rating_default;
    return `<label class="field">${title}<input ${common} type="number" min="${r.min}" max="${r.max}" step="1" value="${esc(value??'')}"></label><p class="subtitle">${r.min}：${esc(r.lower_label)}；${r.max}：${esc(r.upper_label)}</p>`;
  }
  if(FormValidation.rules.choice_types.includes(q.type)){
    const multiple=q.type==='multiple_choice',chosen=typeof value==='string'?[value]:multiple?(value?.option_ids||[]):value?.option_id?[value.option_id]:[],items=q.options.concat(q.allow_other?[{id:FormValidation.rules.other_id,label:'其他'}]:[]);
    const controls=q.type==='dropdown'?`<select ${common}><option value="">請選擇</option>${items.map(o=>`<option value="${esc(o.id)}" ${chosen.includes(o.id)?'selected':''}>${esc(o.label)}</option>`).join('')}</select>`:`<div class="form-preview-choices">${items.map(o=>`<label class="check-label"><input ${common} name="choice-${qid}" type="${multiple?'checkbox':'radio'}" value="${esc(o.id)}" ${chosen.includes(o.id)?'checked':''}>${esc(o.label)}</label>`).join('')}</div>`;
    return `<fieldset><legend>${title}</legend>${controls}${q.allow_other?`<label class="field form-other-input" ${chosen.includes(FormValidation.rules.other_id)?'':'hidden'}>其他補充<input ${common} data-other="true" type="text" value="${esc(value?.other||'')}"></label>`:''}</fieldset>`;
  }
  if(q.type==='attachment'){
    const a=q.attachment;return `<label class="field">${title}<input type="file" disabled accept="${a.extensions.map(ext=>'.'+ext).join(',')}" multiple></label><p>最多 ${a.max_files} 檔、單檔 ${a.max_file_bytes/1048576} MiB、每題合計 ${a.max_total_bytes/1048576} MiB；格式 ${a.extensions.map(ext=>ext.toUpperCase()).join('、')}。</p><p class="subtitle">附件預覽僅顯示限制，不會上傳或保存檔案。</p>`;
  }
  return '';
}
function formPreviewHint(q){
  const v=q.validation||{};if(!v.enabled)return '';
  const hints=[];
  if(v.format==='phone')hints.push(FormValidation.rules.phone_modes[v.phone_mode||'tw_mobile']+(v.allow_extension?'（可含分機）':''));
  if(v.format==='email')hints.push('Email，例如 name@example.com');
  if(v.min_length!==undefined)hints.push(`至少 ${v.min_length} 字`);
  if(v.max_length!==undefined)hints.push(`最多 ${v.max_length} 字`);
  if(v.integer)hints.push('請填寫整數');
  if(v.min!==undefined)hints.push(`最小 ${v.min}`);
  if(v.max!==undefined)hints.push(`最大 ${v.max}`);
  if(v.count_min!==undefined)hints.push(`至少選 ${v.count_min} 項`);
  if(v.count_max!==undefined)hints.push(`最多選 ${v.count_max} 項`);
  if(v.count_exact!==undefined)hints.push(`請選 ${v.count_exact} 項`);
  if(v.date_min)hints.push(`自 ${v.date_min}`);
  if(v.date_max)hints.push(`至 ${v.date_max}`);
  return hints.join('；');
}
function formPreviewPage(row){
  formEnsureDesign(row);queueMicrotask(formLoadContentImages);
  return heading('填寫預覽',`${row.name} · 預覽不會建立回覆紀錄。`,formDesignButton('返回設計器','back-design')+formDesignButton('返回基本資料','basic'))+
    `<section data-form-designer data-dirty="${formDesign.dirty}"><form data-form-preview novalidate><div class="form-preview-status" role="status"></div><p class="form-error form-preview-global-error" role="alert" hidden></p>${FormValidation.pages(formDesign.questions).map((questions,index)=>`<div data-preview-page="${index}" ${index===formDesign.previewPage?'':'hidden'}>${questions.map(q=>q.type==='content'?FormValidation.contentMarkup(q):q.type==='section'?`<section class="panel panel-body form-section"><h2>${esc(q.title)}</h2><p class="form-description">${esc(q.description||'')}</p></section>`:`<section class="panel panel-body form-preview-question" data-preview-id="${esc(q.id)}">${q.required?'<p class="form-required">必填</p>':'<p class="subtitle">選填</p>'}${formPreviewControl(q)}<p class="form-description" id="form-preview-description-${esc(q.id)}">${esc([q.description,formPreviewHint(q)].filter(Boolean).join(" · "))}</p><p class="form-error" role="alert" id="form-preview-error-${esc(q.id)}" hidden></p></section>`).join('')}</div>`).join('')}<p data-preview-page-status role="status">第 ${formDesign.previewPage+1} / ${FormValidation.pages(formDesign.questions).length} 頁</p><div class="form-actions"><button type="button" class="btn" data-preview-previous ${formDesign.previewPage===0?'hidden':''}>上一頁</button><button type="button" class="btn primary" data-preview-next ${formDesign.previewPage===FormValidation.pages(formDesign.questions).length-1?'hidden':''}>下一頁</button><button type="submit" class="btn primary" ${formDesign.previewPage===FormValidation.pages(formDesign.questions).length-1?'':'hidden'}>驗證預覽答案</button></div></form></section>`;
}
function formPreviewGoPage(index){
  const pages=FormValidation.pages(formDesign.questions),form=document.querySelector('[data-form-preview]');
  formDesign.previewPage=index;
  form.querySelectorAll('[data-preview-page]').forEach(el=>el.hidden=Number(el.dataset.previewPage)!==index);
  form.querySelector('[data-preview-previous]').hidden=index===0;
  form.querySelector('[data-preview-next]').hidden=index===pages.length-1;
  form.querySelector('[type="submit"]').hidden=index!==pages.length-1;
  form.querySelector('[data-preview-page-status]').textContent=`第 ${index+1} / ${pages.length} 頁`;
  const block=form.querySelector(`[data-preview-page="${index}"]`);block.tabIndex=-1;block.focus();
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-preview-previous],[data-preview-next]');if(!button||state.busy)return;
  if(button.hasAttribute('data-preview-previous')){formPreviewGoPage(formDesign.previewPage-1);return;}
  const qs=FormValidation.pages(formDesign.questions)[formDesign.previewPage],answers=Object.fromEntries(qs.filter(q=>q.id in formDesign.previewAnswers).map(q=>[q.id,formDesign.previewAnswers[q.id]]));
  const errors=FormValidation.validateAnswers(qs,answers);formShowPreviewErrors(errors);
  if(Object.keys(errors).length){document.querySelector('[aria-invalid="true"]')?.focus();return;}
  formPreviewGoPage(formDesign.previewPage+1);
});
function formDesignDirty(){
  formDesign.dirty=true;formDesign.errors={};document.querySelector('#page [data-form-designer]')?.setAttribute('data-dirty','true');
  const status=document.querySelector('#page .form-save-status');if(status)status.textContent='尚未儲存';renderWorkspaceTools();
}
function formUpdateQuestionInput(el){
  const card=el.closest('[data-qid]'),q=formDesign.questions.find(q=>q.id===card?.dataset.qid);if(!q||!formsUI.capabilities.maintain)return;
  const path=el.dataset.qField;let value=el.type==='checkbox'?el.checked:el.value;
  if(path==='type'){
    const keepOptions=FormValidation.rules.choice_types.includes(q.type)&&FormValidation.rules.choice_types.includes(value),defaults=formDefaultQuestion(value);q.type=value;q.validation=defaults.validation;q.options=keepOptions?q.options:defaults.options;q.allow_other=value==='dropdown'?false:q.allow_other;q.required=value==='section'?false:q.required;
    if(!FormValidation.rules.choice_types.includes(value))q.allow_other=false;
    delete q.rating;delete q.attachment;if(defaults.rating)q.rating=defaults.rating;if(defaults.attachment)q.attachment=defaults.attachment;
  }else if(path==='option.label')q.options.find(o=>o.id===el.closest('[data-option-id]').dataset.optionId).label=value;
  else if(path==='attachment.extensions')q.attachment.extensions=[...card.querySelectorAll('[data-q-field="attachment.extensions"]:checked')].map(input=>input.value);
  else if(path.includes('.')){
    const [group,key]=path.split('.');q[group]??={};
    if(el.type==='number'){if(value===''){delete q[group][key];}else q[group][key]=Number(value)*(key.endsWith('_bytes')?1048576:1);}
    else q[group][key]=value;
  }else q[path]=value;
  formDesignDirty();
  if(q.type==='content'){const example=card.querySelector('.form-content-example');if(example){example.innerHTML='<p class="subtitle">內容示意</p>'+FormValidation.contentMarkup(q);formLoadContentImages();}}
}
function formShowPreviewErrors(errors){
  formDesign.previewErrors=errors;
  for(const q of formDesign.questions){if(FormValidation.rules.display_types.includes(q.type))continue;const el=$('form-preview-error-'+q.id);if(el){el.textContent=errors[q.id]||'';el.hidden=!errors[q.id];}for(const input of document.querySelectorAll(`[data-answer-id="${CSS.escape(q.id)}"]`))input.setAttribute('aria-invalid',errors[q.id]?'true':'false');}
  const global=document.querySelector('.form-preview-global-error');if(global){global.textContent=errors._form||'';global.hidden=!errors._form;}
  renderWorkspaceTools();
}
function formReadPreview(el){
  const id=el.dataset.answerId,q=formDesign.questions.find(q=>q.id===id);if(!q)return;
  const block=el.closest('[data-preview-id]');let value=el.value;
  if(FormValidation.rules.choice_types.includes(q.type)){
    const selected=q.type==='dropdown'?el.value:[...block.querySelectorAll('[data-answer-id]:checked')].map(input=>input.value);
    const ids=Array.isArray(selected)?selected:(selected?[selected]:[]),other=block.querySelector('[data-other]')?.value||'';
    value=q.type==='multiple_choice'?{option_ids:ids,other:ids.includes(FormValidation.rules.other_id)?other:''}:{option_id:ids[0]||'',other:ids.includes(FormValidation.rules.other_id)?other:''};
    const holder=block.querySelector('.form-other-input');if(holder)holder.hidden=!ids.includes(FormValidation.rules.other_id);
  }
  formDesign.previewAnswers[id]=value;
  const errors=FormValidation.validateAnswers(formDesign.questions,formDesign.previewAnswers);
  if(formDesign.previewChecked)formShowPreviewErrors(errors);else{const existing={...formDesign.previewErrors};if(errors[id])existing[id]=errors[id];else delete existing[id];formShowPreviewErrors(existing);}
}
document.addEventListener('input',event=>{if(event.target.dataset.qField&&!event.target.matches('select'))formUpdateQuestionInput(event.target);if(event.target.dataset.answerId)formReadPreview(event.target);});
document.addEventListener('change',event=>{
  const el=event.target;
  if(el.dataset.qField){formUpdateQuestionInput(el);if(['type','validation.enabled','validation.format','allow_other','page_break','content.kind'].includes(el.dataset.qField))render();}
  if(el.dataset.answerId)formReadPreview(el);
});
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-design-action]');if(!button||button.disabled||state.busy)return;
  const action=button.dataset.designAction;
  if(['preview','basic','back-design'].includes(action)){formEnterMode(action==='back-design'?'design':action,formsUI.selected);return;}
  if(!formsUI.capabilities.maintain)return;
  const qid=button.closest('[data-qid]')?.dataset.qid,index=formDesign.questions.findIndex(q=>q.id===qid),q=formDesign.questions[index];
  if(['add-question','add-section','add-content','copy'].includes(action)&&formDesign.questions.length>=cap('FORM_QUESTIONS_MAX')){notice('題目數量已達上限。',true);return;}
  if(['add-question','add-section','add-content'].includes(action))formDesign.questions.push(formDefaultQuestion(action==='add-section'?'section':action==='add-content'?'content':'short_text'));
  else if(action==='content-image-remove'){q.content.image_id='';}
  else if(action==='remove'){if(!confirm(q.type==='section'?'刪除此分區？儲存題目後生效。':q.type==='content'?'刪除此說明內容？儲存題目後生效。':'刪除此題目？儲存題目後生效。'))return;formDesign.questions.splice(index,1);delete formDesign.previewAnswers[qid];}
  else if(action==='copy'){const copy=formClone(q);copy.id=formId();copy.options=copy.options.map(o=>({...o,id:formId()}));formDesign.questions.splice(index+1,0,copy);}
  else if(action==='up'||action==='down'){const next=index+(action==='up'?-1:1);if(next<0||next>=formDesign.questions.length)return;[formDesign.questions[index],formDesign.questions[next]]=[formDesign.questions[next],q];}
  else if(action==='option-add'){if(q.options.length>=cap('FORM_OPTIONS_MAX'))return;q.options.push({id:formId(),label:'新選項'});}
  else if(action.startsWith('option-')){
    const i=q.options.findIndex(o=>o.id===button.closest('[data-option-id]').dataset.optionId);
    if(action==='option-remove')q.options.splice(i,1);
    else {const next=i+(action==='option-up'?-1:1);if(next<0||next>=q.options.length)return;[q.options[i],q.options[next]]=[q.options[next],q.options[i]];}
  }else return;
  formDesignDirty();render();const focus=document.querySelector(`[data-qid="${CSS.escape(qid||formDesign.questions.at(-1)?.id||'')}"] input`);focus?.focus({preventScroll:true});
});
document.addEventListener('dragstart',event=>{
  const handle=event.target.closest('[data-form-drag]');if(!handle||!formsUI.capabilities.maintain)return;formDesign.drag=handle.dataset.formDrag;formDragVisual(event,formDesign.drag);handle.closest('[data-qid]').classList.add('form-card-dragging');event.dataTransfer.setData('text/plain',formDesign.drag);event.dataTransfer.effectAllowed='move';
});
document.addEventListener('dragover',event=>{if(formDesign.drag&&event.target.closest('[data-qid]')){event.preventDefault();event.dataTransfer.dropEffect='move';}});
document.addEventListener('drop',event=>{
  const card=event.target.closest('[data-qid]');if(!card||!formDesign.drag||!formsUI.capabilities.maintain)return;event.preventDefault();
  const from=formDesign.questions.findIndex(q=>q.id===formDesign.drag),to=formDesign.questions.findIndex(q=>q.id===card.dataset.qid);formDesign.drag=null;
  if(from<0||to<0||from===to)return;const [q]=formDesign.questions.splice(from,1);formDesign.questions.splice(to,0,q);formDesignDirty();render();
});
document.addEventListener('dragend',()=>{formDesign.drag=null;});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.matches('form[data-form-designer],form[data-form-preview]'))return;event.preventDefault();
  if(formContentUploading){notice('請等待說明圖片上傳完成。',true);return;}
  if(state.busy)return;if(form.hasAttribute('data-form-preview')&&formDesign.previewPage<FormValidation.pages(formDesign.questions).length-1){form.querySelector('[data-preview-next]').click();return;}const button=form.querySelector('[type="submit"]');button.disabled=true;state.busy=true;
  try{
    if(form.hasAttribute('data-form-preview')){
      formDesign.previewChecked=true;formShowPreviewErrors(FormValidation.validateAnswers(formDesign.questions,formDesign.previewAnswers));
      const result=await api('/api/forms/preview',{form_id:formDesign.id,questions:formDesign.questions,answers:formDesign.previewAnswers});
      formShowPreviewErrors(result.errors);document.querySelector('.form-preview-status').textContent=result.valid?'預覽驗證通過；未保存回覆。':'請修正標示的題目。';
      if(!result.valid){const index=FormValidation.pages(formDesign.questions).findIndex(qs=>qs.some(q=>result.errors[q.id]));if(index>=0)formPreviewGoPage(index);document.querySelector('[aria-invalid="true"]')?.focus();}
    }else{
      const row=formsUI.rows.find(row=>row.form_id===formDesign.id);let confirmed=false;
      if(row.counts.responses){confirmed=confirm('已有回覆。刪題、改題型或修改選項會影響之後填寫，舊答案仍依提交快照閱讀。確定儲存？');if(!confirmed)return;}
      const result=await api('/api/forms/design',{form_id:formDesign.id,questions:formDesign.questions,expected_updated_at:formDesign.version,confirm_response_impact:confirmed});
      formDesign.questions=formClone(result.form.questions);formDesign.version=result.form.updated_at;formDesign.dirty=false;formDesign.errors={};form.dataset.dirty='false';
      await loadForms();render();notice('題目已儲存。');
    }
  }catch(exc){
    if(form.hasAttribute('data-form-preview')){const el=document.querySelector('.form-preview-global-error');el.textContent=exc.message;el.hidden=false;}
    else{formDesign.errors=exc.errors||{};render();const el=document.querySelector('.form-design-error');el.textContent=exc.message;el.hidden=false;document.querySelector('.form-question-error:not([hidden])')?.scrollIntoView({block:'center'});}
  }finally{state.busy=false;button.disabled=false;renderWorkspaceTools();}
});

function formSortTools(){
  const editable=formsUI.capabilities.maintain;
  let question=0,section=0,content=0,page=1;
  return `<p class="workspace-tools-intro">${editable?'拖曳把手調整順序，或使用上移／下移。點選標題可跳到題目；完成後請儲存題目。':'點選標題查看題目與分區，目前為唯讀。'}</p><ol class="form-sort-list" aria-label="題目與分區排序">${formDesign.questions.map((q,index)=>{
    if(index&&q.type==='section'&&q.page_break===true)page++;
    const label=q.type==='section'?`分區 ${++section}`:q.type==='content'?`說明 ${++content}`:`題目 ${++question}`;
    return `<li class="form-sort-item ${q.type==='section'?'form-sort-section':''}" data-form-sort-id="${esc(q.id)}">${editable?`<button type="button" class="form-sort-handle" draggable="true" data-form-sort-drag="${esc(q.id)}" aria-label="拖曳 ${esc(label)} ${esc(q.title)}" title="拖曳排序">${icon('menu')}</button>`:''}<button type="button" class="form-sort-title" data-form-sort-jump="${esc(q.id)}"><small>${esc(label)} · 第 ${page} 頁</small><strong>${esc(q.title)||(q.type==='content'?esc(FormValidation.rules.content_kinds[q.content.kind]):'未命名')}</strong><span>${esc(FormValidation.rules.types[q.type])}</span></button>${editable?`<div class="form-sort-controls"><button type="button" data-form-sort-move="up" data-id="${esc(q.id)}" aria-label="上移 ${esc(label)}" title="上移" ${index===0?'disabled':''}>↑</button><button type="button" data-form-sort-move="down" data-id="${esc(q.id)}" aria-label="下移 ${esc(label)}" title="下移" ${index===formDesign.questions.length-1?'disabled':''}>↓</button></div>`:''}</li>`;
  }).join('')||'<li class="subtitle">尚無題目，請先新增題目或分區。</li>'}</ol><p class="subtitle" role="status">${formDesign.dirty?'順序或內容尚未儲存。':'目前順序已儲存。'}</p>`;
}
function formSortMove(id,target){
  if(!formsUI.capabilities.maintain||state.busy||!document.querySelector('#page form[data-form-designer]'))return;
  const from=formDesign.questions.findIndex(q=>q.id===id);if(from<0||target<0||target>=formDesign.questions.length||from===target)return;
  const panel=document.getElementById('workspace-tools-body'),scroll=panel.scrollTop;
  const positions=new Map([...panel.querySelectorAll('[data-form-sort-id]')].map(el=>[el.dataset.formSortId,el.getBoundingClientRect().top]));
  const [q]=formDesign.questions.splice(from,1);formDesign.questions.splice(target,0,q);
  formDesignDirty();render();panel.scrollTop=scroll;
  requestAnimationFrame(()=>{
    panel.scrollTop=scroll;panel.querySelector(`[data-form-sort-jump="${CSS.escape(id)}"]`)?.focus({preventScroll:true});
    if(!matchMedia('(prefers-reduced-motion: reduce)').matches)for(const row of panel.querySelectorAll('[data-form-sort-id]')){const previous=positions.get(row.dataset.formSortId);if(previous!==undefined){const dy=previous-row.getBoundingClientRect().top;if(dy)row.animate([{transform:`translateY(${dy}px)`},{transform:'translateY(0)'}],{duration:260,easing:'ease-out'});}}
    const moved=panel.querySelector(`[data-form-sort-id="${CSS.escape(id)}"]`);moved?.classList.add('just-moved');setTimeout(()=>moved?.classList.remove('just-moved'),900);
  });
}
let formSortDrag=null;
document.addEventListener('click',event=>{
  const move=event.target.closest('[data-form-sort-move]');
  if(move){const from=formDesign.questions.findIndex(q=>q.id===move.dataset.id);formSortMove(move.dataset.id,from+(move.dataset.formSortMove==='up'?-1:1));return;}
  const jump=event.target.closest('[data-form-sort-jump]');if(!jump)return;
  const id=jump.dataset.formSortJump;if(!workspaceToolsDock.matches)workspaceToolsClose();
  const card=document.querySelector(`#page [data-qid="${CSS.escape(id)}"]`);card?.scrollIntoView({block:'start',behavior:'smooth'});card?.querySelector('[data-q-field="title"]')?.focus({preventScroll:true});
});
document.addEventListener('dragstart',event=>{
  const handle=event.target.closest('[data-form-sort-drag]');if(!handle||!formsUI.capabilities.maintain||state.busy)return;
  formSortDrag=handle.dataset.formSortDrag;formDragVisual(event,formSortDrag);event.dataTransfer.setData('text/plain',formSortDrag);event.dataTransfer.effectAllowed='move';handle.closest('li').classList.add('is-dragging');
});
document.addEventListener('dragover',event=>{
  const row=event.target.closest('[data-form-sort-id]');if(!row||!formSortDrag)return;
  event.preventDefault();event.dataTransfer.dropEffect='move';
  document.querySelectorAll('.form-sort-item.drop-before,.form-sort-item.drop-after').forEach(el=>el.classList.remove('drop-before','drop-after'));
  const rect=row.getBoundingClientRect();row.classList.add(event.clientY<rect.top+rect.height/2?'drop-before':'drop-after');
  const body=document.getElementById('workspace-tools-body'),bounds=body.getBoundingClientRect();if(event.clientY<bounds.top+40)body.scrollTop-=12;else if(event.clientY>bounds.bottom-40)body.scrollTop+=12;
});
document.addEventListener('drop',event=>{
  const row=event.target.closest('[data-form-sort-id]');if(!row||!formSortDrag)return;
  event.preventDefault();const id=formSortDrag;formSortDrag=null;
  const from=formDesign.questions.findIndex(q=>q.id===id),to=formDesign.questions.findIndex(q=>q.id===row.dataset.formSortId),rect=row.getBoundingClientRect();
  let target=to+(event.clientY>=rect.top+rect.height/2?1:0);if(from<target)target--;
  setTimeout(()=>{document.querySelector('.form-drag-ghost')?.remove();formSortMove(id,target);},100);
  document.querySelectorAll('.form-sort-item').forEach(el=>el.classList.remove('is-dragging','drop-before','drop-after'));
});
document.addEventListener('dragend',()=>{formSortDrag=null;document.querySelectorAll('.form-sort-item').forEach(el=>el.classList.remove('is-dragging','drop-before','drop-after'));});

function formDragVisual(event,id){
  document.querySelector('.form-drag-ghost')?.remove();
  const q=formDesign.questions.find(q=>q.id===id);if(!q)return;
  const ghost=document.createElement('div');ghost.className='form-drag-ghost';ghost.setAttribute('aria-hidden','true');
  ghost.innerHTML=`${icon('menu')}<div><small>${q.type==='section'?'移動分區':q.type==='content'?'移動說明':'移動題目'}</small><strong>${esc(q.title)||(q.type==='content'?esc(FormValidation.rules.content_kinds[q.content.kind]):'未命名')}</strong></div>`;
  document.body.append(ghost);event.dataTransfer.setDragImage(ghost,24,24);
}
document.addEventListener('dragend',()=>{document.querySelector('.form-drag-ghost')?.remove();document.querySelectorAll('.form-card-dragging').forEach(el=>el.classList.remove('form-card-dragging'));});

let formContentUploading=0;
const formContentPictures=new Map();
async function formLoadContentImages(){
  const id=formDesign.id,scope=lineUI.channel;
  await Promise.all([...document.querySelectorAll('#page [data-form-content-image]')].map(async img=>{
    if(img.dataset.loading)return;img.dataset.loading='true';
    const key=scope+':'+img.dataset.formContentImage,status=img.parentElement.querySelector('[data-content-image-status]');
    try{const src=formContentPictures.get(key)||await formBlobData(await formResponseBinary('/api/forms/content/image?'+new URLSearchParams({form_id:id,image_id:img.dataset.formContentImage})));formContentPictures.set(key,src);if(img.isConnected){img.src=src;img.hidden=false;if(status)status.hidden=true;}}
    catch(exc){if(status?.isConnected)status.textContent=exc.message;}
  }));
}
document.addEventListener('change',async event=>{
  const input=event.target;if(!input.matches('[data-form-content-upload]'))return;
  const file=input.files?.[0],id=input.closest('[data-qid]').dataset.qid,formId=formDesign.id,scope=lineUI.channel;if(!file)return;
  if(file.size>8*1048576){notice('說明圖片最多 8 MB。',true);input.value='';return;}
  formContentUploading++;input.disabled=true;
  try{const raw=await formBlobData(file),result=await api('/api/forms/content/upload',{form_id:formId,name:file.name,data:raw.split(',')[1]});
    if(formDesign.id!==formId||lineUI.channel!==scope)return;const q=formDesign.questions.find(q=>q.id===id);if(!q)return;
    q.content.image_id=result.asset_id;formContentPictures.set(scope+':'+result.asset_id,result.preview);formDesignDirty();render();
  }catch(exc){notice(exc.message,true);}finally{formContentUploading--;if(input.isConnected){input.disabled=false;input.value='';}}
});

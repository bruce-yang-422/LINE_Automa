"use strict";
const formDesign={id:null,questions:[],version:'',dirty:false,errors:{},drag:null,previewAnswers:{},previewErrors:{},previewChecked:false};
const formClone=value=>JSON.parse(JSON.stringify(value));
const formId=()=>crypto.randomUUID().replaceAll('-','');
function formDesignerReset(){Object.assign(formDesign,{id:null,questions:[],version:'',dirty:false,errors:{},drag:null,previewAnswers:{},previewErrors:{},previewChecked:false});}
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
  if(mode==='preview'){formDesign.previewErrors={};formDesign.previewChecked=false;}
  render();
}
function formDefaultQuestion(kind='short_text'){
  const q={id:formId(),title:kind==='section'?'新分區':'新題目',description:'',type:kind,required:false,options:[],allow_other:false,validation:{enabled:false}};
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
  const buttons=editable?`<div class="form-question-actions"><button type="button" class="btn small form-drag-handle" draggable="true" data-form-drag="${esc(q.id)}" aria-label="拖曳排序第 ${index+1} 題">${icon('menu')}拖曳排序</button>${formDesignButton('上移','up',index===0?'disabled':'')}${formDesignButton('下移','down',index===formDesign.questions.length-1?'disabled':'')}${formDesignButton('複製題目','copy')}${formDesignButton('刪除題目','remove')}</div>`:'';
  const optionFields=choice?`<fieldset class="form-choice-settings"><legend>選項</legend>${q.options.map((o,i)=>`<div class="form-option-row" data-option-id="${esc(o.id)}"><label class="field">選項 ${i+1}<input data-q-field="option.label" value="${esc(o.label)}" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}></label>${editable?formDesignButton('上移','option-up',i===0?'disabled':'')+formDesignButton('下移','option-down',i===q.options.length-1?'disabled':'')+formDesignButton('移除','option-remove'):''}</div>`).join('')}${editable?formDesignButton('新增選項','option-add',q.options.length>=cap('FORM_OPTIONS_MAX')?'disabled':''):''}${q.type!=='dropdown'?formDesignCheck('開啟其他（選取後需補充文字）','allow_other',q.allow_other,readonly):''}</fieldset>`:'';
  let settings='';
  if(q.type==='rating'){
    const r=q.rating||FormValidation.rules.rating_default;
    settings=`<div class="form-design-fields">${formDesignControl('最低分','rating.min',r.min,'number',readonly)}${formDesignControl('最高分','rating.max',r.max,'number',readonly)}${formDesignControl('低分說明','rating.lower_label',r.lower_label,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}${formDesignControl('高分說明','rating.upper_label',r.upper_label,'text',`maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}</div>`;
  }
  if(q.type==='attachment'){
    const a=q.attachment;
    settings=`<fieldset class="form-attachment-settings"><legend>附件限制</legend>${Object.entries(FormValidation.rules.attachment_groups).map(([group,extensions])=>`<details><summary>${esc(group)}</summary><div class="form-extension-list">${extensions.map(ext=>`<label class="check-label"><input data-q-field="attachment.extensions" type="checkbox" value="${ext}" ${a.extensions.includes(ext)?'checked':''} ${readonly}>${ext.toUpperCase()}</label>`).join('')}</div></details>`).join('')}<div class="form-design-fields">${formDesignControl('最多檔案數','attachment.max_files',a.max_files,'number',`min="1" max="${cap('FORM_ATTACHMENTS_PER_QUESTION')}" ${readonly}`)}${formDesignControl('單檔大小（MiB）','attachment.max_file_bytes',a.max_file_bytes/1048576,'number',`min="0" max="${cap('FORM_ATTACHMENT_MAX_BYTES')/1048576}" step="any" ${readonly}`)}${formDesignControl('每題總大小（MiB）','attachment.max_total_bytes',a.max_total_bytes/1048576,'number',`min="0" max="${cap('FORM_ATTACHMENT_TOTAL_MAX_BYTES')/1048576}" step="any" ${readonly}`)}</div></fieldset>`;
  }
  return `<article class="form-question-card" data-qid="${esc(q.id)}"><header><h3>${q.type==='section'?'分區':'題目'} ${index+1}</h3>${buttons}</header><p class="form-error form-question-error" role="alert" ${error?'':'hidden'}>${esc(error)}</p><div class="form-design-fields">${formDesignControl('標題','title',q.title,'text',`required maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}`)}${formDesignSelect('題型','type',q.type,Object.entries(FormValidation.rules.types),readonly)}</div><label class="field">說明<textarea data-q-field="description" rows="2" maxlength="${cap('FORM_TEXT_MAX')}" ${readonly}>${esc(q.description||'')}</textarea></label>${q.type!=='section'?formDesignCheck('必填','required',q.required,readonly):''}${optionFields}${settings}${formValidationFields(q,readonly)}</article>`;
}
function formDesignerPage(row){
  formEnsureDesign(row);const editable=formsUI.capabilities.maintain;
  return heading('設計題目',row.name,formDesignButton('返回基本資料','basic')+formDesignButton('填寫預覽','preview'))+
    `<form data-form-designer data-dirty="${formDesign.dirty}" novalidate><section class="panel panel-body form-designer-toolbar"><h2>題目與分區</h2><p>${formDesign.questions.length} / ${cap('FORM_QUESTIONS_MAX')} 個題目／分區</p><p class="form-save-status" role="status">${formDesign.dirty?'尚未儲存':'變更後請按儲存題目。'}</p><p class="form-error form-design-error" role="alert" hidden></p><div class="form-actions">${editable?formDesignButton('新增題目','add-question')+formDesignButton('新增分區','add-section')+'<button type="submit" class="btn primary">儲存題目</button>':'<p>目前角色只能查看。</p>'}</div></section>${row.counts.responses?'<p class="callout warn">已有回覆。刪題、改題型或修改選項會影響後續填寫；舊答案仍依提交時快照閱讀。</p>':''}<div class="form-question-cards">${formDesign.questions.map((q,i)=>formQuestionCard(q,i,editable)).join('')||empty('尚無題目','使用新增題目或新增分區開始設計。')}</div></form>`;
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
  formEnsureDesign(row);
  return heading('填寫預覽',`${row.name} · 預覽不會建立回覆紀錄。`,formDesignButton('返回設計器','back-design')+formDesignButton('返回基本資料','basic'))+
    `<section data-form-designer data-dirty="${formDesign.dirty}"><form data-form-preview novalidate><div class="form-preview-status" role="status"></div><p class="form-error form-preview-global-error" role="alert" hidden></p>${formDesign.questions.map(q=>q.type==='section'?`<section class="panel panel-body form-section"><h2>${esc(q.title)}</h2><p class="form-description">${esc(q.description||'')}</p></section>`:`<section class="panel panel-body form-preview-question" data-preview-id="${esc(q.id)}">${q.required?'<p class="form-required">必填</p>':'<p class="subtitle">選填</p>'}${formPreviewControl(q)}<p class="form-description" id="form-preview-description-${esc(q.id)}">${esc([q.description,formPreviewHint(q)].filter(Boolean).join(" · "))}</p><p class="form-error" role="alert" id="form-preview-error-${esc(q.id)}" hidden></p></section>`).join('')}<div class="form-actions"><button type="submit" class="btn primary">驗證預覽答案</button></div></form></section>`;
}
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
}
function formShowPreviewErrors(errors){
  formDesign.previewErrors=errors;
  for(const q of formDesign.questions){if(q.type==='section')continue;const el=$('form-preview-error-'+q.id);if(el){el.textContent=errors[q.id]||'';el.hidden=!errors[q.id];}for(const input of document.querySelectorAll(`[data-answer-id="${CSS.escape(q.id)}"]`))input.setAttribute('aria-invalid',errors[q.id]?'true':'false');}
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
  if(el.dataset.qField){formUpdateQuestionInput(el);if(['type','validation.enabled','validation.format','allow_other'].includes(el.dataset.qField))render();}
  if(el.dataset.answerId)formReadPreview(el);
});
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-design-action]');if(!button||button.disabled||state.busy)return;
  const action=button.dataset.designAction;
  if(['preview','basic','back-design'].includes(action)){formEnterMode(action==='back-design'?'design':action,formsUI.selected);return;}
  if(!formsUI.capabilities.maintain)return;
  const qid=button.closest('[data-qid]')?.dataset.qid,index=formDesign.questions.findIndex(q=>q.id===qid),q=formDesign.questions[index];
  if(['add-question','add-section','copy'].includes(action)&&formDesign.questions.length>=cap('FORM_QUESTIONS_MAX')){notice('題目數量已達上限。',true);return;}
  if(action==='add-question'||action==='add-section')formDesign.questions.push(formDefaultQuestion(action==='add-section'?'section':'short_text'));
  else if(action==='remove'){if(!confirm('刪除此題目？儲存題目後生效。'))return;formDesign.questions.splice(index,1);delete formDesign.previewAnswers[qid];}
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
  const handle=event.target.closest('[data-form-drag]');if(!handle||!formsUI.capabilities.maintain)return;formDesign.drag=handle.dataset.formDrag;event.dataTransfer.setData('text/plain',formDesign.drag);event.dataTransfer.effectAllowed='move';
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
  if(state.busy)return;const button=form.querySelector('[type="submit"]');button.disabled=true;state.busy=true;
  try{
    if(form.hasAttribute('data-form-preview')){
      formDesign.previewChecked=true;formShowPreviewErrors(FormValidation.validateAnswers(formDesign.questions,formDesign.previewAnswers));
      const result=await api('/api/forms/preview',{form_id:formDesign.id,questions:formDesign.questions,answers:formDesign.previewAnswers});
      formShowPreviewErrors(result.errors);document.querySelector('.form-preview-status').textContent=result.valid?'預覽驗證通過；未保存回覆。':'請修正標示的題目。';
      if(!result.valid)document.querySelector('[aria-invalid="true"]')?.focus();
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

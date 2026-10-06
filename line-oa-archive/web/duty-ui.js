"use strict";
const dutySetup={people:[],positions:[],tasks:[],query:"",department:"",status:"active",binding:"all",taskId:"",draft:null};
const dutyFrequencyNames={daily:"每日",weekly:"每週",monthly:"每月",annual:"年度指定日期"};
const dutyRotationNames={year:"每年",month:"每月",week:"每週",fixed:"固定負責人"};
const dutyWeekdays=["一","二","三","四","五","六","日"];
async function loadDutySetup(){
  if(!dutyContext?.can_inspect_setup){dutySetup.people=[];dutySetup.positions=[];dutySetup.tasks=[];return;}
  const organizationId=dutyContext.organization.org_id;
  if(dutySetup.organizationId!==organizationId){dutySetup.people=[];dutySetup.positions=[];dutySetup.tasks=[];dutySetup.organizationId=organizationId;}
  const [people,tasks]=await Promise.all([api('/api/duty/people'),api('/api/duty/tasks')]);
  Object.assign(dutySetup,{people:people.people,positions:people.positions,tasks:tasks.tasks});
}
function dutyCanLeave(){
  const dirty=[...document.querySelectorAll('[data-duty-form][data-dirty="true"]')].some(form=>!form.closest('dialog')||form.closest('dialog').open);
  return !dirty||confirm('有未儲存的值日生變更，確定離開？');
}
function dutyDate(){return dutyContext?.today||new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei'}).format(new Date());}
function dutyAction(title,action,id="",primary=false){return `<button type="button" class="btn ${primary?'primary':'small'}" data-duty-action="${action}" data-id="${esc(id)}">${esc(title)}</button>`;}
function dutyImpactLabel(impact){
  if(typeof impact==='string')return impact;
  const period=impact.date_from&&impact.date_to?`${impact.date_from} 至 ${impact.date_to}`:'';
  return [impact.name||'班表',dutyRosterStatuses[impact.status]||'狀態待確認',period].filter(Boolean).join('｜');
}
function dutyImpactFields(impacts){return impacts?.length?`<div class="callout warn"><strong>受影響項目</strong><ul>${impacts.map(i=>`<li>${esc(dutyImpactLabel(i))}</li>`).join('')}</ul><label class="check-label"><input type="checkbox" name="confirm_impacts" required>已確認受影響項目</label>${field('異動原因','reason','','required')}</div>`:'';}
function dutySetupPage(){return dutyTab==='tasks'?dutyTasksPage():dutyPeoplePage();}
function dutyPeoplePage(){
  const editable=dutyContext.capabilities.edit;
  const people=dutySetup.people.filter(p=>(dutySetup.status==='all'||Boolean(p.active)===(dutySetup.status==='active'))&&(!dutySetup.department||p.department===dutySetup.department)&&(dutySetup.binding==='all'||Boolean(p.bindings.length)===(dutySetup.binding==='bound'))&&[p.full_name,p.display_name,p.department,p.floor].join(' ').toLowerCase().includes(dutySetup.query.toLowerCase()));
  return `<section class="panel panel-body"><div class="duty-section-heading"><div><h2>值日人員（${dutySetup.people.length}／${cap('DUTY_PEOPLE_PER_ORG')}）</h2><p class="subtitle">不需後台帳號，用來排班與接收通知。</p></div><div class="duty-actions">${dutyCsvActions('people')}${editable?dutyAction('批次新增','bulk')+dutyAction('新增值日人員','person-new','',true):''}</div></div>
    <div class="duty-filters"><label>搜尋<input type="search" data-duty-filter="query" value="${esc(dutySetup.query)}" placeholder="姓名、暱稱、部門或樓層"></label><label>部門<select data-duty-filter="department">${options([['','全部'],...[...new Set(dutySetup.people.map(p=>p.department).filter(Boolean))].map(d=>[d,d])],dutySetup.department)}</select></label><label>狀態<select data-duty-filter="status">${options([['active','啟用'],['inactive','停用'],['all','全部']],dutySetup.status)}</select></label><label>LINE 綁定<select data-duty-filter="binding">${options([['all','全部'],['bound',`已綁定（${dutySetup.people.filter(p=>p.bindings.length).length}）`],['unbound',`未綁定（${dutySetup.people.filter(p=>!p.bindings.length).length}）`]],dutySetup.binding)}</select></label></div>
    <div class="duty-people-list">${people.map(p=>{
      const member=p.memberships.at(-1);
      return `<article class="duty-person-card"><div><span class="duty-person-avatar" aria-hidden="true">${esc(p.full_name.slice(-2))}</span><br><strong>${esc(p.display_name||p.full_name)}</strong><p>${esc(p.full_name)} · ${esc(p.department||'未填部門')} · ${esc(p.floor||'未填樓層')}</p><div class="duty-context">${badge(p.active?'啟用':'停用')}${badge(p.bindings.length?'已綁定 LINE':'未綁定')}${badge(member?(member.effective_from>dutyDate()?`${member.effective_from} 起加入`:`參與輪替｜代號 ${member.code}`):'不參與')}</div></div><div class="duty-actions">${editable?dutyAction('編輯','person-edit',p.person_id)+dutyAction('綁定','binding',p.person_id)+dutyAction(p.removal==='deactivate'?'停用':'刪除','person-remove',p.person_id):''}</div></article>`;
    }).join('')||empty('沒有符合的值日人員','新增人員或調整篩選條件。')}</div>
    ${dutySetup.positions.some(p=>p.vacant)?`<p class="callout">待補位：${dutySetup.positions.filter(p=>p.vacant).map(p=>esc(p.code)+'（X）').join('、')}。新增人員時可選擇接任空缺代號。</p>`:''}</section>`;
}
function dutyPersonForm(personId){
  const p=dutySetup.people.find(p=>p.person_id===personId);
  modal(p?'編輯值日人員':'新增值日人員',`<form data-duty-form="person" data-id="${esc(personId||'')}"><div class="form-grid">${field('全名','full_name',p?.full_name||'',`required maxlength="${cap('DUTY_NAME_MAX')}"`)}${field('顯示名稱／暱稱','display_name',p?.display_name||'')}${field('部門','department',p?.department||'')}${field('樓層','floor',p?.floor||'')}${field('加入輪替／異動生效日','effective_from',dutyDate(),'type="date" required')}${!p?selectField('接任空缺位置','position_id',[['','建立新代號'],...dutySetup.positions.filter(p=>p.vacant).map(p=>[p.position_id,`代號 ${p.code}（X）`])],'')+field('新代號（留空自動編號）','code','')+selectField('新位置排在誰之後','after_position_id',[['','排在最後'],...dutySetup.positions.map(p=>[p.position_id,'代號 '+p.code])],''):''}</div><label class="check-label"><input type="checkbox" name="active" ${!p||p.active?'checked':''}>啟用</label>${dutyImpactFields(p?.impacts)}<p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">儲存值日人員</button></div></form>`);
}
function dutyTasksPage(){
  let task=dutySetup.tasks.find(t=>t.task_id===dutySetup.taskId);
  if(!task&&dutySetup.tasks.length){task=dutySetup.tasks[0];dutySetup.taskId=task.task_id;}
  return `<section class="panel panel-body"><div class="duty-section-heading"><h2>工作項目（${dutySetup.tasks.length}／${cap('DUTY_TASKS_PER_ORG')}）</h2><div class="duty-actions">${dutyCsvActions('tasks')}${dutyContext.capabilities.edit?dutyAction('新增工作','task-new','',true):''}</div></div><div class="duty-task-layout"><aside class="duty-task-list" aria-label="工作項目清單">${dutySetup.tasks.map(t=>{const v=t.versions[0];return `<button type="button" data-duty-action="task-select" data-id="${esc(t.task_id)}" aria-pressed="${t.task_id===dutySetup.taskId}"><strong>${esc(v?.name||'尚未設定')}</strong><small>${esc(dutyRotationNames[v?.rotation]||'')} · ${t.active?'啟用':'停用'} · v${v?.version||1}${v?.effective_from>dutyDate()?'｜尚未生效':''}</small></button>`;}).join('')||'<p>尚未建立工作項目。</p>'}</aside><div id="duty-task-detail">${task?dutyTaskFormHtml(task.versions[0],task):empty('選擇或新增工作','換人週期與工作執行頻率分開設定。')}</div></div></section>`;
}
function dutyTaskItemHtml(item,index){
  return `<fieldset class="duty-item" data-duty-item><legend>執行子項目 ${index+1}</legend>${field('執行內容','content',item.content||'','required')}<div class="form-grid">${selectField('多久做一次','frequency',Object.entries(dutyFrequencyNames),item.frequency||'daily')}<div class="duty-frequency-fields" data-frequency="weekly" ${item.frequency==='weekly'?'':'hidden'}><span>星期</span><div class="duty-weekdays">${dutyWeekdays.map((d,i)=>`<label><input type="checkbox" name="weekdays" value="${i}" ${item.weekdays?.includes(i)?'checked':''}>${d}</label>`).join('')}</div></div><div class="duty-frequency-fields" data-frequency="monthly" ${item.frequency==='monthly'?'':'hidden'}><div class="form-grid">${field('每月起始日','day_start',item.day_start||1,'type="number" min="1" max="31"')}${field('每月結束日（31＝月底）','day_end',item.day_end||31,'type="number" min="1" max="31"')}</div><div class="duty-actions">${dutyAction('1–15 日','range-first',index)}${dutyAction('16 日–月底','range-last',index)}</div></div><div class="duty-frequency-fields" data-frequency="annual" ${item.frequency==='annual'?'':'hidden'}>${field('年度日期 MM-DD（留空待設定）','annual_date',item.annual_date||'','placeholder="MM-DD"')}</div>${field('提醒時間（留空待設定，不會發送）','reminder_time',item.reminder_time||'','type="time"')}${field('排除日期（逗號或換行分隔 YYYY-MM-DD）','excluded_dates',(item.excluded_dates||[]).join(', '))}</div><label class="check-label"><input type="checkbox" name="reminder_enabled" ${item.reminder_enabled?'checked':''}>啟用提醒（時間待設定時不提醒）</label>${dutyAction('移除子項目','item-remove',index)}</fieldset>`;
}
function dutyTaskFormHtml(data={},task=null){
  const disabled=!dutyContext.capabilities.edit;
  return `<form data-duty-form="task" data-id="${esc(task?.task_id||'')}"><fieldset ${disabled?'disabled':''}><legend>工作詳情${data.version?'｜v'+data.version:''}</legend><div class="form-grid">${field('名稱','name',data.name||'','required')}${field('區域','area',data.area||'')}${selectField('類型','kind',[['normal','一般'],['rest','休息'],['blank','空白欄']],data.kind||'normal')}${selectField('多久換人','rotation',Object.entries(dutyRotationNames),data.rotation||'month')}${field('生效日','effective_from',data.effective_from||dutyDate(),'type="date" required')}</div><label>說明<textarea name="description" rows="3">${esc(data.description||'')}</textarea></label><label class="check-label"><input type="checkbox" name="allow_multiple" ${data.allow_multiple?'checked':''}>允許多人共同負責</label><label class="check-label"><input type="checkbox" name="active" ${!task||task.active?'checked':''}>啟用工作</label><h3>執行子項目：多久做一次</h3><p class="subtitle">每日、每週、每月可同時生效；條件式工作保留在說明中。</p><div class="duty-items">${(data.items||[]).map(dutyTaskItemHtml).join('')}</div><div class="duty-actions">${dutyAction('新增執行子項目','item-add')}${dutyAction('預覽接下來 14 天','task-preview')}</div>${dutyImpactFields(task?.impacts)}<div class="duty-preview" aria-live="polite"></div><p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">儲存工作新版本</button>${task?(task.active&&task.impacts?.length?dutyAction('停用工作','task-remove',task.task_id):'')+dutyAction('從清單移除','task-archive',task.task_id):''}</div></fieldset></form>`;
}
function readDutyTask(form){
  const values=Object.fromEntries(new FormData(form));
  return {...values,active:form.elements.active.checked,allow_multiple:form.elements.allow_multiple.checked,
    items:[...form.querySelectorAll('[data-duty-item]')].map(card=>{
      const input=name=>card.querySelector(`[name="${name}"]`);
      return {content:input('content').value,frequency:input('frequency').value,weekdays:[...card.querySelectorAll('[name="weekdays"]:checked')].map(e=>Number(e.value)),day_start:Number(input('day_start').value),day_end:Number(input('day_end').value),annual_date:input('annual_date').value,reminder_time:input('reminder_time').value,reminder_enabled:input('reminder_enabled').checked,excluded_dates:input('excluded_dates').value.split(/[,，\s]+/).filter(Boolean)};
    })};
}
async function dutyRemove(kind,id,restore=false,mode='default'){
  const resource=kind==='person'?dutySetup.people.find(p=>p.person_id===id):dutySetup.tasks.find(t=>t.task_id===id);
  if(!restore){
    const deactivates=mode!=='archive'&&(kind==='person'?resource.removal==='deactivate':resource.impacts.length>0);
    modal(mode==='archive'?'移除工作':deactivates?'停用確認':'刪除確認',`<form data-duty-form="remove" data-kind="${kind}" data-id="${esc(id)}" data-mode="${mode}"><p>${mode==='archive'?'工作會從清單及現有草稿移除，不再加入新排班；已發布班表與歷史版本保留。':deactivates?'停用後不加入新輪替，歷史資料保留。':'刪除後移出清單，可使用復原提示恢復。'}</p>${field('生效日','effective_from',dutyDate(),'type="date" required')}${dutyImpactFields(resource.impacts)}<p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">確認${mode==='archive'?'移除':deactivates?'停用':'刪除'}</button></div></form>`);return;
  }
  await api('/api/duty/remove',{kind,id,restore:true});await load();render();notice('已復原。');
}
document.addEventListener('input',event=>{
  const form=event.target.closest('[data-duty-form]');if(form&&!event.target.hasAttribute('data-roster-period')&&!event.target.hasAttribute('data-roster-person-search'))form.dataset.dirty='true';
  const key=event.target.dataset.dutyFilter;if(!key||event.target.tagName==='SELECT')return;
  dutySetup[key]=event.target.value;const start=event.target.selectionStart;render();const input=document.querySelector(`[data-duty-filter="${key}"]`);input.focus();input.setSelectionRange(start,start);
});
document.addEventListener('change',event=>{
  const form=event.target.closest('[data-duty-form]');if(form&&!event.target.hasAttribute('data-roster-period')&&!event.target.hasAttribute('data-roster-person-search'))form.dataset.dirty='true';
  const key=event.target.dataset.dutyFilter;if(key){dutySetup[key]=event.target.value;render();}
  if(event.target.name==='frequency')event.target.closest('[data-duty-item]').querySelectorAll('[data-frequency]').forEach(e=>e.hidden=e.dataset.frequency!==event.target.value);
});
document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-duty-action]');if(!target)return;
  const action=target.dataset.dutyAction,id=target.dataset.id;
  try{
    if(['person-new','person-edit','task-new','task-select'].includes(action)&&!dutyCanLeave())return;
    if(action==='person-new'||action==='person-edit')dutyPersonForm(id);
    else if(action==='person-remove'||action==='task-remove')await dutyRemove(action==='person-remove'?'person':'task',id);
    else if(action==='task-archive')await dutyRemove('task',id,false,'archive');
    else if(action==='restore')await dutyRemove(target.dataset.kind,id,true);
    else if(action==='task-select'){dutySetup.taskId=id;render();}
    else if(action==='task-new'){modal('新增工作項目',dutyTaskFormHtml());}
    else if(['item-add','item-remove'].includes(action)){
      const form=target.closest('[data-duty-form]'),data=readDutyTask(form);
      if(action==='item-add'){
        if(data.items.length>=Number(cap('DUTY_ITEMS_PER_TASK')))throw Error('執行子項目已達上限。');
        data.items.push({frequency:'daily',weekdays:[],excluded_dates:[]});
      }else data.items.splice(Number(id),1);
      const task=dutySetup.tasks.find(t=>t.task_id===form.dataset.id);
      const holder=document.createElement('div');holder.innerHTML=dutyTaskFormHtml(data,task);
      form.replaceWith(holder.firstElementChild);document.querySelector('[data-duty-form="task"]').dataset.dirty='true';
    }else if(action==='range-first'||action==='range-last'){
      const item=target.closest('[data-duty-item]');item.querySelector('[name="day_start"]').value=action==='range-first'?1:16;item.querySelector('[name="day_end"]').value=action==='range-first'?15:31;target.closest('form').dataset.dirty='true';
    }else if(action==='task-preview'){
      const form=target.closest('form'),result=await api('/api/duty/tasks/preview',readDutyTask(form));
      form.querySelector('.duty-preview').innerHTML=`<h3>接下來 14 天執行預覽</h3>${result.days.map(d=>`<div class="duty-preview-day"><strong>${esc(d.date)}（${dutyWeekdays[d.weekday]}）</strong><p>${esc(d.due.join('＋')||'沒有到期工作')}</p><small>${d.reminders.length?d.reminders.map(r=>esc(r.time)+'：'+esc(r.contents.join('＋'))).join('；'):'沒有提醒（未啟用或時間待設定）'}</small></div>`).join('')}`;
    }else if(action==='bulk'){
      modal('批次新增值日人員',`<form data-duty-form="bulk"><label>貼上全名、顯示名稱、部門、樓層（CSV 或 Tab）<textarea name="text" rows="8" required></textarea></label>${field('加入輪替生效日','effective_from',dutyDate(),'type="date" required')}<div class="duty-bulk-preview"></div><p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">預覽人員</button></div></form>`);
    }else if(action==='binding'){
      const data=await api('/api/duty/bindings'),person=dutySetup.people.find(p=>p.person_id===id);
      modal('LINE 綁定：'+person.full_name,`<form data-duty-form="binding" data-id="${esc(id)}" data-channel="${esc(data.channel_id||'')}"><p>只列通知 OA 的個人聯絡對象，不依姓名自動配對。</p>${!data.channel_id?'<p class="callout">尚未指定通知 OA，請先到「通知設定」指定，再綁定個人聯絡對象。</p>':`<label>搜尋聯絡對象<input type="search" data-duty-binding-search></label><label>個人聯絡對象<select name="recipient_id"><option value="">解除綁定</option>${data.recipients.map(r=>`<option value="${esc(r.recipient_id)}" ${r.person_id&&r.person_id!==id?'disabled':''} ${person.bindings.some(b=>b.recipient_id===r.recipient_id)?'selected':''}>${esc(r.custom_name||r.display_name||'未命名')}${r.custom_name&&r.display_name?' · '+esc(r.display_name):''}${r.person_id&&r.person_id!==id?'｜已綁定：'+esc(r.bound_name):''}</option>`).join('')}</select></label>`}<p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary" ${!data.channel_id?'disabled':''}>儲存 LINE 綁定</button></div></form>`);
    }
  }catch(error){const form=target.closest('[data-duty-form]');if(form){const el=form.querySelector('.duty-form-error');el.textContent=error.message;el.hidden=false;}else notice(error.message,true);}
});
document.addEventListener('input',event=>{
  if(!event.target.hasAttribute('data-duty-binding-search'))return;
  const query=event.target.value.toLowerCase();event.target.closest('form').querySelectorAll('option').forEach(option=>option.hidden=Boolean(option.value)&&!option.textContent.toLowerCase().includes(query));
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.hasAttribute('data-duty-form')||form.dataset.dutyForm.startsWith('roster')||form.dataset.dutyForm==='csv-import'||form.dataset.dutyForm.startsWith('automation-'))return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');if(submit.disabled)return;submit.disabled=true;
  const values=Object.fromEntries(new FormData(form)),kind=form.dataset.dutyForm;
  const errorEl=form.querySelector('.duty-form-error');errorEl.hidden=true;
  try{
    if(kind==='person'){
      const person=dutySetup.people.find(p=>p.person_id===form.dataset.id);
      await api('/api/duty/people/save',{...values,person_id:person?.person_id,expected_updated_at:person?.updated_at,active:form.elements.active.checked,confirm_impacts:form.elements.confirm_impacts?.checked||false,impacts:person?.impacts||[]});
    }else if(kind==='task'){
      const task=dutySetup.tasks.find(t=>t.task_id===form.dataset.id);
      const result=await api('/api/duty/tasks/save',{...readDutyTask(form),task_id:task?.task_id,expected_updated_at:task?.updated_at,confirm_impacts:form.elements.confirm_impacts?.checked||false,impacts:task?.impacts||[]});dutySetup.taskId=result.task_id;
    }else if(kind==='binding')await api('/api/duty/bindings/save',{person_id:form.dataset.id,channel_id:form.dataset.channel,recipient_id:values.recipient_id});
    else if(kind==='bulk'){
      const confirmed=form.dataset.preview===values.text;
      const result=await api('/api/duty/people/bulk',{...values,confirm:confirmed});
      if(!confirmed){form.dataset.preview=values.text;form.querySelector('.duty-bulk-preview').innerHTML=`<h3>新增預覽</h3>${result.rows.map(r=>`<p>${esc(r.full_name)} · ${esc(r.display_name)} · ${esc(r.department)} · ${esc(r.floor)}${r.skip?'｜X 空缺，略過':''}</p>`).join('')}`;submit.textContent='確認新增';submit.disabled=false;return;}
    }else if(kind==='remove'){
      const resource=form.dataset.kind==='person'?dutySetup.people.find(p=>p.person_id===form.dataset.id):dutySetup.tasks.find(t=>t.task_id===form.dataset.id);
      await api('/api/duty/remove',{...values,kind:form.dataset.kind,id:form.dataset.id,mode:form.dataset.mode,confirm_impacts:form.elements.confirm_impacts?.checked||false,impacts:resource.impacts});
    }
    form.dataset.dirty='false';await load();render();if(form.closest('#modal'))$('modal').close();notice('值日生設定已儲存。');
    if(kind==='remove'&&form.dataset.mode==='archive')notice('工作已從清單與草稿移除，歷史班表保留。');
    if(kind==='remove'&&form.dataset.mode!=='archive')document.querySelector('#page').insertAdjacentHTML('afterbegin',`<div class="callout">資料已移出清單。<button class="btn small" type="button" data-duty-action="restore" data-kind="${esc(form.dataset.kind)}" data-id="${esc(form.dataset.id)}">復原</button></div>`);
  }catch(error){errorEl.textContent=error.message;errorEl.hidden=false;submit.disabled=false;}
});

function dutyCsvTemplateButton(kind){
  const label={people:'值日人員',tasks:'工作項目',rosters:'班表'}[kind];
  return `<button type="button" class="btn text small duty-csv-template" data-duty-csv="template" data-kind="${kind}" aria-label="下載${label} CSV 範本" title="下載${label} CSV 範本">CSV 範本</button>`;
}
function dutyCsvActions(kind){
  return `<button type="button" class="btn small" data-duty-csv="export" data-kind="${kind}">匯出 CSV</button>${dutyContext.capabilities.edit?`<button type="button" class="btn small" data-duty-csv="import" data-kind="${kind}">匯入 CSV</button>`:''}${dutyCsvTemplateButton(kind)}`;
}
async function dutyCsvDownload(kind,template=false,rosterId){
  const result=await api('/api/duty/csv/export',{kind,template,roster_id:rosterId});
  const url=URL.createObjectURL(new Blob([result.content],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download=result.filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-duty-csv]');if(!button)return;
  try{
    const kind=button.dataset.kind;
    if(button.dataset.dutyCsv==='export'||button.dataset.dutyCsv==='template')await dutyCsvDownload(kind,button.dataset.dutyCsv==='template',button.dataset.rosterId);
    else{
      if(!dutyCanLeave())return;
      modal('匯入'+({people:'值日人員',tasks:'工作項目',rosters:'班表'}[kind])+' CSV',`<form data-duty-form="csv-import" data-kind="${kind}"><p>匯入新增資料；同名且內容相同會略過，內容不同需從編輯頁更新。整批檢查通過後才會儲存。</p><p>${kind==='rosters'?'匯入建立新草稿；同期間已有草稿時請先編輯或刪除。人員填全名，多人以分號分隔；一列一個工作，有多筆代班時重複工作列。請先建立人員與工作，匯入後仍須檢查及發布。':kind==='people'?'可使用員工清單；「X」待補位標記會略過，不匯入 LINE 綁定。':'一列一個執行子項目，同一工作可占多列；星期填 1–7（週一至週日），多個星期或排除日期以分號分隔。匯出包含最新工作版本。'}</p><button type="button" class="btn small" data-duty-csv="template" data-kind="${kind}">下載 CSV 範本</button><label>CSV 檔案<input type="file" name="file" accept=".csv,text/csv" required></label>${selectField('檔案編碼','encoding',[['utf-8','UTF-8（建議）'],['big5','Big5（舊版 Excel）']],'utf-8')}${field('未填生效日時使用','effective_from',dutyDate(),'type="date" required')}<div class="duty-csv-preview" aria-live="polite"></div><p class="duty-form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="btn primary">預覽匯入</button></div></form>`);
    }
  }catch(error){notice(error.message,true);}
});
document.addEventListener('change',event=>{
  const form=event.target.closest('[data-duty-form="csv-import"]');if(!form)return;
  delete form.dataset.signature;delete form.dataset.source;
  form.querySelector('.duty-csv-preview').textContent='';form.querySelector('[type="submit"]').textContent='預覽匯入';
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(form.dataset.dutyForm!=='csv-import')return;event.preventDefault();
  const button=form.querySelector('[type="submit"]'),error=form.querySelector('.duty-form-error');button.disabled=true;error.hidden=true;
  try{
    const file=form.elements.file.files[0];if(!file)throw Error('請選擇 CSV 檔案。');
    if(file.size>Number(cap('DUTY_CSV_MAX_BYTES')))throw Error('CSV 檔案大小超過上限。');
    let text;try{text=new TextDecoder(form.elements.encoding.value,{fatal:true}).decode(await file.arrayBuffer());}catch{throw Error('檔案編碼不符，請選擇正確編碼或另存 UTF-8 CSV。');}
    const source=JSON.stringify([text,form.elements.effective_from.value]);
    const confirm=Boolean(form.dataset.signature&&form.dataset.source===source);
    const result=await api('/api/duty/csv/import',{kind:form.dataset.kind,text,effective_from:form.elements.effective_from.value,confirm,preview_signature:confirm?form.dataset.signature:undefined});
    if(!confirm){
      form.querySelector('.duty-csv-preview').innerHTML=`<h3>匯入預覽：新增 ${result.added} 項、略過 ${result.skipped} 項</h3>${result.rows.map(r=>`<p>第 ${r.line} 列｜${esc(r.name)}｜${esc(r.action)}${r.summary?'｜'+esc(r.summary):''}${r.message?'｜'+esc(r.message):''}</p>`).join('')}${result.errors.length?`<div class="duty-form-error"><strong>請修正 ${result.errors.length} 個錯誤後重新預覽</strong>${result.errors.map(e=>`<p>第 ${e.line} 列：${esc(e.message)}</p>`).join('')}</div>`:''}`;
      if(result.can_import){form.dataset.signature=result.preview_signature;form.dataset.source=source;button.textContent='確認匯入';}else{delete form.dataset.signature;button.textContent='重新預覽';}
      button.disabled=false;return;
    }
    form.dataset.dirty='false';await load();if(result.roster_ids?.length)await dutyOpenRoster(result.roster_ids[0],false);render();$('modal').close();notice(`CSV 匯入完成：新增 ${result.added} 項、略過 ${result.skipped} 項。`);
  }catch(exc){delete form.dataset.signature;button.textContent='重新預覽';error.textContent=exc.message;error.hidden=false;button.disabled=false;}
});

"use strict";
const dutyHome={month:new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Taipei'}).slice(0,7),person:'',records:[],organizationId:'',loading:false,request:0,error:''};
function dutyHomeSources(){
  const first=dutyHome.month+'-01',last=new Date(Number(dutyHome.month.slice(0,4)),Number(dutyHome.month.slice(5,7)),0).toLocaleDateString('sv-SE');
  const rows=dutyRoster.rows.filter(r=>['published','draft'].includes(r.status)&&r.date_from<=last&&r.date_to>=first);
  const choose=period=>rows.filter(r=>r.period_type===period).sort((a,b)=>Number(b.status==='published')-Number(a.status==='published')||b.version-a.version||b.date_from.localeCompare(a.date_from))[0];
  const weeks=new Map();
  for(const row of rows.filter(r=>r.period_type==='week').sort((a,b)=>Number(b.status==='published')-Number(a.status==='published')||b.version-a.version)){
    const key=row.date_from+'|'+row.date_to;if(!weeks.has(key))weeks.set(key,row);
  }
  return [choose('month'),choose('year'),...weeks.values()].filter(Boolean);
}
async function loadDutyHome(){
  const request=++dutyHome.request;dutyHome.loading=true;dutyHome.error='';
  const organizationId=dutyContext?.organization.org_id;
  if(dutyHome.organizationId!==organizationId){dutyHome.records=[];dutyHome.person='';dutyHome.organizationId=organizationId;}
  try{
    const records=await Promise.all(dutyHomeSources().map(r=>api('/api/duty/roster?roster_id='+encodeURIComponent(r.roster_id))));
    if(request===dutyHome.request&&dutyContext?.organization.org_id===organizationId)dutyHome.records=records.map(result=>result.roster);
  }catch(error){if(request===dutyHome.request){dutyHome.records=[];dutyHome.error=error.message;}}
  finally{if(request===dutyHome.request)dutyHome.loading=false;}
}
function dutyHomeItemLabel(item){
  const frequency={daily:'每天',weekly:'週'+item.weekdays.map(day=>'一二三四五六日'[day]).join('、'),monthly:`每月 ${item.day_start}–${item.day_end} 日`,annual:item.annual_date?'每年 '+item.annual_date:'年度日期待設定'}[item.frequency];
  return frequency+(item.reminder_enabled&&item.reminder_time?' · '+item.reminder_time:'');
}
function dutyHomePage(){
  const year=dutyHome.month.slice(0,4),month=Number(dutyHome.month.slice(5,7));
  const entries=dutyHome.records.flatMap(roster=>roster.assignments.filter(a=>!a.snapshot.inherited&&a.snapshot.kind!=='blank').map(assignment=>({roster,assignment})));
  const people=new Map();entries.forEach(({assignment:a})=>a.person_ids.forEach(id=>people.set(id,rosterPersonName(id,a))));
  const filtered=entries.filter(({assignment:a})=>!dutyHome.person||a.person_ids.includes(dutyHome.person));
  const monthly=dutyHome.records.find(r=>r.period_type==='month');
  return `<section class="duty-visual-header duty-home-header"><div class="duty-section-heading"><div><p class="duty-eyebrow">值日生首頁</p><h2>${Number(year)} 年 ${month} 月</h2><p>直接看誰負責什麼；點工作卡片可查看班表。</p></div><label>選擇月份<input type="month" data-duty-home-month value="${esc(dutyHome.month)}"></label></div><nav class="duty-month-strip" aria-label="月份選擇">${Array.from({length:12},(_,i)=>{const value=year+'-'+String(i+1).padStart(2,'0'),exists=dutyRoster.rows.some(r=>r.period_type==='month'&&['published','draft'].includes(r.status)&&r.date_from<=value+'-01'&&r.date_to>=value+'-01');return `<button type="button" data-duty-home-select="${value}" aria-pressed="${value===dutyHome.month}"><strong>${i+1} 月</strong><span>${exists?'有班表':'未排班'}</span></button>`;}).join('')}</nav></section>${dutyHome.loading?'<p role="status">正在載入班表…</p>':dutyHome.error?`<p class="duty-form-error" role="alert">${esc(dutyHome.error)}</p>`:`<div class="duty-home-summary"><div><strong>${people.size}</strong><span>位負責人</span></div><div><strong>${entries.length}</strong><span>項工作</span></div><div><strong>${entries.filter(({assignment:a})=>a.snapshot.kind==='normal'&&!a.person_ids.length).length}</strong><span>項待指派</span></div><div><strong>${monthly?dutyRosterStatuses[monthly.status]:'未排班'}</strong><span>本月班表</span></div></div>${!monthly?`<section class="duty-home-next"><h3>${month} 月還沒有月班表</h3><p>年度工作會另外顯示；每月輪換的工作要先建立本月班表。</p>${dutyContext.capabilities.edit?'<button type="button" class="btn primary" data-duty-home-create>建立本月班表</button>':'<p>請管理者發布本月班表後再查看。</p>'}</section>`:monthly.status==='draft'?'<p class="callout warn">這是草稿預覽，尚未發布，分配可能調整。</p>':''}<div class="duty-section-heading"><h3>本月工作與負責人</h3><label>只看某位同事<select data-duty-home-person>${options([['','所有人'],...people],dutyHome.person)}</select></label></div><div class="duty-home-board">${filtered.map(({roster:r,assignment:a})=>`<article class="duty-home-work"><div class="duty-section-heading"><span class="duty-home-cycle">${dutyPeriodLabels[r.period_type]} · ${dutyRosterStatuses[r.status]}</span>${a.snapshot.kind==='rest'?'<span>本期休息</span>':''}</div><h3>${esc(a.snapshot.name)}</h3><div class="duty-home-assignees">${a.person_ids.map(id=>{const name=rosterPersonName(id,a);return `<div><span class="duty-person-avatar" aria-hidden="true">${esc(name.slice(-2))}</span><strong>${esc(name)}</strong></div>`;}).join('')||'<strong>待指派</strong>'}</div>${a.snapshot.area?`<p>${esc(a.snapshot.area)}</p>`:''}<div class="duty-home-work-times">${(a.snapshot.items||[]).map(item=>`<details><summary>${esc(dutyHomeItemLabel(item))}</summary><p>${esc(item.content)}</p></details>`).join('')}</div>${a.substitutions.map(s=>`<p>代班：${esc(rosterPersonName(s.substitute_person_id,a))} · ${esc(s.date_from)} 至 ${esc(s.date_to)}</p>`).join('')}${a.note?`<p>備註：${esc(a.note)}</p>`:''}<button type="button" class="btn small" data-duty-home-open="${esc(r.roster_id)}" data-assignment-id="${esc(a.assignment_id)}">${r.status==='draft'&&dutyContext.capabilities.edit?'調整負責人':'查看班表'}</button></article>`).join('')||'<p>這個月份尚無可查看的工作分配。</p>'}</div>`}`;
}
document.addEventListener('change',async event=>{
  if(event.target.hasAttribute('data-duty-home-person')){dutyHome.person=event.target.value;render();}
  if(event.target.hasAttribute('data-duty-home-month')&&/^\d{4}-\d{2}$/.test(event.target.value)){dutyHome.month=event.target.value;dutyHome.person='';const pending=loadDutyHome();render();await pending;if(dutyTab==='home')render();}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-duty-home-select],[data-duty-home-open],[data-duty-home-create]');if(!button)return;
  try{
    if(button.dataset.dutyHomeSelect){dutyHome.month=button.dataset.dutyHomeSelect;dutyHome.person='';const pending=loadDutyHome();render();await pending;if(dutyTab==='home')render();return;}
    dutyTab='roster';history.replaceState(null,'','/?view=duty&tab=roster');
    if(button.hasAttribute('data-duty-home-create')){dutyRoster.record=null;render();rosterWizard('','month');const form=document.querySelector('[data-duty-form="roster-create"]');form.elements.name.value=dutyHome.month+' 值日生班表';form.elements.date_from.value=dutyHome.month+'-01';form.elements.date_to.value=new Date(Number(dutyHome.month.slice(0,4)),Number(dutyHome.month.slice(5,7)),0).toLocaleDateString('sv-SE');}
    else{await dutyOpenRoster(button.dataset.dutyHomeOpen);document.querySelector(`[data-duty-roster-action="choose"][data-id="${CSS.escape(button.dataset.assignmentId)}"]`)?.click();}
  }catch(error){notice(error.message,true);}
});

"use strict";
const dutyRoster={rows:[],record:null,draft:null,view:'work',period:'month'};
function dutyRosterCsvButton(id){return `<button type="button" class="btn small" data-duty-csv="export" data-kind="rosters" data-roster-id="${esc(id)}">匯出 CSV</button>`;}
const dutyRosterStatuses={draft:'草稿',published:'已發布',replaced:'已取代',cancelled:'已取消'};
async function loadDutyRosters(){
  if(!dutyContext){dutyRoster.rows=[];dutyRoster.record=null;return;}
  const organizationId=dutyContext.organization.org_id;
  if(dutyRoster.organizationId!==organizationId){dutyRoster.rows=[];dutyRoster.record=null;dutyRoster.draft=null;dutyRoster.organizationId=organizationId;}
  dutyRoster.rows=(await api('/api/duty/rosters')).rosters;
  if(dutyRoster.record&&dutyRoster.rows.some(r=>r.roster_id===dutyRoster.record.roster_id))await dutyOpenRoster(dutyRoster.record.roster_id,false);
  else{dutyRoster.record=null;dutyRoster.draft=null;}
}
async function dutyOpenRoster(id,draw=true){
  dutyRoster.record=(await api('/api/duty/roster?roster_id='+encodeURIComponent(id))).roster;
  dutyRoster.draft=structuredClone(dutyRoster.record.assignments);
  dutyRoster.period=dutyRoster.record.period_type;
  dutyRoster.view='work';
  if(draw)render();
}
function rosterAction(title,action,id='',primary=false){return `<button type="button" class="btn ${primary?'primary':'small'}" data-duty-roster-action="${action}" data-id="${esc(id)}">${esc(title)}</button>`;}
function rosterPersonName(id,assignment){return assignment?.snapshot?.people?.[id]?.full_name||dutySetup.people.find(p=>p.person_id===id)?.full_name||'未分配';}
function rosterActivityText(event){
  try{
    const detail=JSON.parse(event.detail);
    return `發布 v${detail.version}｜${detail.reason||'首次發布'}\n`+(detail.differences||[]).map(d=>`${d.work}：${d.before} → ${d.after}${d.note?'\n備註：'+d.note:''}`+(d.substitutions||[]).map(s=>`\n代班 ${s.date_from}–${s.date_to}：${s.original} → ${s.substitute}`).join('')).join('\n');
  }catch{return event.detail;}
}
function dutyRosterPage(){
  if(dutyRoster.record)return dutyRosterEditor();
  const manageable=dutyContext.capabilities.edit;
  return `<section class="duty-roster-header"><div class="duty-section-heading"><div><p class="duty-eyebrow">值日生</p><h2>排班管理</h2><p>先選擇班表週期，再開啟要調整的期間。</p></div><div class="duty-actions">${manageable?rosterAction('建立班表草稿','new','',true):''}</div></div><div class="duty-actions duty-secondary-actions">${manageable?'<button type="button" class="btn small" data-duty-csv="import" data-kind="rosters">匯入 CSV</button>':''}${dutyCsvTemplateButton('rosters')}</div></section><div class="duty-roster-period-groups">${['month','year','week'].map(period=>{
    const rows=dutyRoster.rows.filter(r=>r.period_type===period);
    return `<section class="duty-roster-content"><div class="duty-section-heading"><div><h3>${dutyPeriodLabels[period]}</h3><p>${period==='month'?'每月輪換的人員與工作分配':period==='year'?'每年輪換的固定年度工作':'每週輪換的人員與工作分配'}</p></div>${manageable?rosterAction('建立'+dutyPeriodLabels[period],'period-new',period):''}</div><div class="duty-roster-periods">${rows.map(r=>`<article class="duty-person-card"><div><strong>${esc(r.name)}</strong><p>${esc(r.date_from)} 至 ${esc(r.date_to)}</p><small>${esc(dutyRosterStatuses[r.status])}${r.version?' · v'+r.version:''}</small></div><div class="duty-actions">${rosterAction(r.status==='draft'&&manageable?'編輯分配':'查看班表','open',r.roster_id,r.status==='draft'&&manageable)}${dutyRosterCsvButton(r.roster_id)}${manageable?rosterAction('複製','copy',r.roster_id):''}${r.status==='draft'&&manageable?rosterAction('刪除草稿','delete',r.roster_id):''}</div></article>`).join('')||'<p>尚未建立此週期的班表。</p>'}</div></section>`;
  }).join('')}</div>${dutyRotationPanel()}`;
}

function rosterCheckPanel(checks){
  return `<aside class="duty-check-panel"><h3>發布前檢查</h3>${[['blocking','必須處理'],['warnings','需確認'],['info','資訊']].map(([key,label])=>`<details ${key==='blocking'?'open':''}><summary>${label}（${checks[key].length}）</summary>${checks[key].map(c=>c.task_id?`<button type="button" class="btn text small" data-duty-roster-action="focus" data-id="${esc(c.task_id)}">${esc(c.message)}</button>`:`<p>${esc(c.message)}</p>`).join('')}</details>`).join('')}</aside>`;
}
const dutyPeriodLabels={month:'每月班表',year:'年度班表',week:'每週班表'};
function rosterForPeriod(period){
  const current=dutyRoster.record,day=dutyDate();
  const rows=dutyRoster.rows.filter(r=>r.period_type===period&&['draft','published'].includes(r.status)&&(!current||r.date_from<=current.date_to&&r.date_to>=current.date_from));
  return rows.sort((a,b)=>Number(b.date_from<=day&&b.date_to>=day)-Number(a.date_from<=day&&a.date_to>=day)||Number(b.status==='draft')-Number(a.status==='draft')||b.date_from.localeCompare(a.date_from))[0];
}
function rosterPeriodNavigation(){
  return `<nav class="duty-period-navigation" aria-label="切換班表週期">${['month','year','week'].map(period=>{
    const selected=dutyRoster.record?.period_type===period,target=rosterForPeriod(period);
    return `<button type="button" data-duty-roster-action="period-open" data-id="${period}" aria-current="${selected?'page':'false'}" ${dutyRoster.saving||!target&&!dutyContext.capabilities.edit?'disabled':''}>${dutyPeriodLabels[period]}${!target?' · 尚未建立':''}</button>`;
  }).join('')}</nav>`;
}
function rosterRelatedAction(period){
  if(rosterForPeriod(period))return rosterAction('開啟'+dutyPeriodLabels[period],'period-open',period);
  return dutyContext.capabilities.edit?rosterAction('建立'+dutyPeriodLabels[period],'period-new',period):'<span>尚未發布此週期班表</span>';
}
function rosterAssignmentCard(a,editable,suffix=''){
  const names=a.person_ids.map(id=>rosterPersonName(id,a)).join('、')||'尚未指派';
  return `<article class="duty-assignment-card" data-roster-task="${esc(a.task_id)}" id="duty-assignment-${esc(a.task_id+suffix)}"><div class="duty-assignment-main"><div><h4>${esc(a.snapshot.name)}</h4><p class="duty-assignment-person">${esc(names)}</p>${a.snapshot.area?`<p class="subtitle">${esc(a.snapshot.area)}</p>`:''}${a.substitutions.map(s=>`<p>代班：${esc(rosterPersonName(s.substitute_person_id,a))} · ${esc(s.date_from)} 至 ${esc(s.date_to)}<br>原負責人：${esc(rosterPersonName(s.original_person_id,a))}</p>`).join('')}</div><div class="duty-actions">${editable?rosterAction('編輯負責人：'+names,'choose',a.assignment_id):''}${editable&&a.person_ids.length?rosterAction('設定代班','substitute',a.assignment_id):''}</div></div>${editable?`<label class="duty-assignment-note">當期備註<input aria-label="${esc(a.snapshot.name)} 當期備註" data-roster-note="${esc(a.assignment_id)}" value="${esc(a.note)}" placeholder="選填"></label>`:a.note?`<p>備註：${esc(a.note)}</p>`:''}</article>`;
}
function dutyRosterEditor(){
  const r=dutyRoster.record,draft=dutyRoster.draft,editable=r.status==='draft'&&dutyContext.capabilities.edit;
  const own=draft.filter(a=>!a.snapshot.inherited),inherited=draft.filter(a=>a.snapshot.inherited);
  const unassigned=own.filter(a=>a.snapshot.kind==='normal'&&!a.person_ids.length);
  const ids=[...new Set(own.flatMap(a=>a.person_ids))];
  const workList=own.map(a=>rosterAssignmentCard(a,editable)).join('')||'<p>此週期沒有工作。請到工作項目設定輪換週期。</p>';
  const personal=ids.map(id=>`<section class="duty-person-group"><h3>${esc(rosterPersonName(id,own.find(a=>a.person_ids.includes(id))))}</h3>${own.filter(a=>a.person_ids.includes(id)).map(a=>rosterAssignmentCard(a,editable,'-'+id)).join('')}</section>`).join('')+`${own.some(a=>!a.person_ids.length)?`<section class="duty-person-group"><h3>尚未指派與空白欄</h3>${own.filter(a=>!a.person_ids.length).map(a=>rosterAssignmentCard(a,editable)).join('')}</section>`:''}`;
  const related=inherited.length?`<details class="duty-related-work"><summary>其他週期工作 · ${inherited.length} 項</summary><p>這些工作由各自的班表管理。切換班表後可調整負責人。</p>${['year','month','week'].filter(period=>inherited.some(a=>a.snapshot.rotation===period)).map(period=>`<section><div class="duty-section-heading"><h3>${dutyPeriodLabels[period]}</h3>${rosterRelatedAction(period)}</div>${inherited.filter(a=>a.snapshot.rotation===period).map(a=>`<p><strong>${esc(a.snapshot.name)}</strong> · ${a.person_ids.length?a.person_ids.map(id=>esc(rosterPersonName(id,a))).join('、'):'尚未帶入已發布分配'}</p>`).join('')}</section>`).join('')}</details>`:'';
  return `<section class="duty-roster-header"><div class="duty-section-heading"><div><p class="duty-eyebrow">${dutyPeriodLabels[r.period_type]}</p><h2>${esc(r.name)}</h2><p>${esc(r.date_from)} 至 ${esc(r.date_to)}</p></div>${rosterAction('返回期間清單','back')}</div>${rosterPeriodNavigation()}<p class="callout ${r.status==='draft'?'warn':''}">${r.status==='draft'?'草稿｜尚未發布，不會發送任何通知':esc(dutyRosterStatuses[r.status])+' v'+r.version+'｜'+esc(r.published_by)+' · '+esc(r.published_at)}</p><div class="duty-actions duty-secondary-actions">${rosterAction('版本與異動紀錄','versions')}${dutyRosterCsvButton(r.roster_id)}${dutyCsvTemplateButton('rosters')}${!editable&&dutyContext.capabilities.edit?rosterAction('建立修訂草稿','copy',r.roster_id):''}</div></section><form data-duty-form="roster-editor" class="duty-roster-form"><section class="duty-roster-content"><div class="duty-section-heading"><div><h3>${editable?'調整本期分配':'本期分配'}</h3><p>本期工作 ${own.length} 項${unassigned.length?' · 尚未指派 '+unassigned.length+' 項':''}。${editable?'修改負責人後，按「儲存草稿」。':''}${r.period_type==='year'?'年度工作的人員分配適用整個期間。':''}</p></div><div class="segmented" aria-label="分配檢視">${[['work','依工作'],['person','依人員']].map(([id,title])=>`<button type="button" data-duty-roster-action="view" data-id="${id}" aria-pressed="${dutyRoster.view===id}">${title}</button>`).join('')}</div></div><div class="duty-assignment-list">${dutyRoster.view==='person'?personal:workList}</div></section>${related}${editable?`<details class="duty-publish-checks"><summary>發布前檢查 · 必須處理 ${r.checks.blocking.length} 項 · 需確認 ${r.checks.warnings.length} 項</summary>${rosterCheckPanel(r.checks)}</details>`:''}<div class="duty-roster-footer"><p class="duty-save-state">已儲存 ${esc(when(r.updated_at))}</p><p class="duty-form-error" role="alert" hidden></p><div class="duty-actions">${editable?`<button type="submit" class="btn primary">儲存草稿</button>${rosterAction('預覽通知','preview')}${dutyAutoButton('套用輪替規則','apply-rule')}${r.checks.blocking.length?'<button type="button" class="btn" disabled>發布…</button>':rosterAction('發布…','publish')}`:''}</div></div></form>`;
}

function rosterDirty(){const form=document.querySelector('[data-duty-form="roster-editor"]');if(form){form.dataset.dirty='true';form.querySelector('.duty-save-state').textContent='有未儲存變更｜發布前請先儲存';}}
function rosterWizard(copyFrom='',periodOverride=''){
  const source=dutyRoster.rows.find(r=>r.roster_id===copyFrom);
  const selected=periodOverride||source?.period_type||'month',today=dutyDate();
  let first=today.slice(0,7)+'-01',year=Number(first.slice(0,4)),month=Number(first.slice(5,7));
  let last=new Date(Date.UTC(year,month,0)).toISOString().slice(0,10);
  if(selected==='year'){first=year+'-01-01';last=year+'-12-31';}
  if(selected==='week'){const date=new Date(today+'T00:00:00Z');date.setUTCDate(date.getUTCDate()-(date.getUTCDay()+6)%7);first=date.toISOString().slice(0,10);date.setUTCDate(date.getUTCDate()+6);last=date.toISOString().slice(0,10);}
  modal('建立班表草稿',`<form data-duty-form="roster-create" data-step="1"><div class="steps"><span class="step">1 期間</span><span class="step">2 起始方式</span><span class="step">3 確認</span></div><section data-roster-step="1"><div class="form-grid">${field('班表名稱','name',first.slice(0,7),'required')}${selectField('期間類型','period_type',[['week','週'],['month','月'],['year','年']],selected)}${field('起始日','date_from',source?.date_from||first,'type="date" required')}${field('結束日','date_to',source?.date_to||last,'type="date" required')}</div></section><section data-roster-step="2" hidden>${selectField('起始方式','start_mode',[['empty','空白手動排班'],['copy','複製上一期'],['rotation','建立後預覽輪替差異']],copyFrom?'copy':'empty')}${selectField('來源班表','copy_from',[['','選擇班表'],...dutyRoster.rows.map(r=>[r.roster_id,r.name+' '+(r.version?'v'+r.version:'草稿')])],copyFrom)}<p class="subtitle">輪替分配先顯示差異，確認後才套用到草稿。</p></section><section data-roster-step="3" hidden><div class="duty-create-summary"></div><p>同期間已有草稿時會開啟既有草稿；此操作不發布或發送通知。</p></section><p class="duty-form-error" role="alert" hidden></p><div class="form-actions">${rosterAction('上一步','wizard-prev')}${rosterAction('下一步','wizard-next')}<button type="submit" class="btn primary" hidden>建立草稿</button></div></form>`);
}
function wizardStep(form,step){form.dataset.step=step;form.querySelectorAll('[data-roster-step]').forEach(s=>s.hidden=Number(s.dataset.rosterStep)!==step);form.querySelector('[data-duty-roster-action="wizard-prev"]').hidden=step===1;form.querySelector('[data-duty-roster-action="wizard-next"]').hidden=step===3;form.querySelector('[type="submit"]').hidden=step!==3;}
async function publishWizard(){
  if(document.querySelector('[data-duty-form="roster-editor"][data-dirty="true"]'))throw Error('請先儲存草稿再發布。');
  const r=dutyRoster.record,preview=await api('/api/duty/roster/preview?roster_id='+r.roster_id);
  const previous=dutyRoster.rows.some(row=>row.status==='published'&&row.date_from===r.date_from&&row.date_to===r.date_to);
  modal('發布班表',`<form data-duty-form="roster-publish" data-step="1"><div class="steps"><span class="step">1 檢查</span><span class="step">2 通知預覽</span><span class="step">3 確認</span></div><section data-roster-step="1"><h3>需確認項目</h3>${r.checks.warnings.map(w=>`<label class="check-label"><input type="checkbox" name="acknowledged" value="${esc(w.key)}" required>已知悉：${esc(w.message)}</label>`).join('')||'<p>沒有需確認項目。</p>'}</section><section data-roster-step="2" hidden><h3>個人通知預覽（${preview.messages.length} 人）</h3>${preview.messages.map(m=>`<details><summary>${esc(m.name)}</summary><pre class="duty-message-preview">${esc(m.text)}</pre></details>`).join('')}<details><summary>群組公告預覽</summary><pre class="duty-message-preview">${esc(preview.group_message)}</pre></details><details><summary>缺漏名單（${preview.missing.length} 人）</summary>${preview.missing.map(m=>`<p>${esc(m.name)}：${esc(m.reason)}</p>`).join('')}</details><p>本次 push 則數：${preview.push_count}；群組成員用量${preview.estimate_complete?'已確認':'待確認'}。</p></section><section data-roster-step="3" hidden>${field('異動原因'+(previous?'（重新發布必填）':'（選填）'),'reason','',previous?'required':'')}<p>將發布正式版本，舊正式版本保留為已取代。舊版本尚未開始的提醒會取消，依新版本重建。</p><label class="check-label"><input type="checkbox" name="send_now" ${preview.enabled?'':'disabled'}>同時立即發送（需先啟用發布／異動通知）</label></section><p class="duty-form-error" role="alert" hidden></p><div class="form-actions">${rosterAction('上一步','wizard-prev')}${rosterAction('下一步','wizard-next')}<button type="submit" class="btn primary" hidden>確認發布</button></div></form>`);
  wizardStep(document.querySelector('[data-duty-form="roster-publish"]'),1);
}
document.addEventListener('input',event=>{
  if(event.target.dataset.rosterNote){const a=dutyRoster.draft.find(a=>a.assignment_id===event.target.dataset.rosterNote);a.note=event.target.value;rosterDirty();}
  if(event.target.hasAttribute('data-roster-person-search')){const form=event.target.closest('form'),q=event.target.value.trim().toLowerCase();form.querySelectorAll('[data-person-choice]').forEach(row=>row.hidden=!row.dataset.search.includes(q));form.querySelector('[data-person-empty]').hidden=[...form.querySelectorAll('[data-person-choice]')].some(row=>!row.hidden);}
});
function rosterChoiceSummary(form){
  const chosen=[...form.querySelectorAll('[name="person_ids"]:checked')];
  form.querySelector('[data-person-selection]').textContent=chosen.length?'已選擇：'+chosen.map(input=>input.dataset.name).join('、'):'尚未指定負責人';
}
document.addEventListener('change',event=>{
  const form=event.target.closest('[data-duty-form="roster-choose"]');if(!form)return;
  if(event.target.name==='person_ids'&&event.target.checked)form.elements.unassigned.checked=false;
  if(event.target.name==='unassigned'&&event.target.checked)form.querySelectorAll('[name="person_ids"]').forEach(input=>input.checked=false);
  rosterChoiceSummary(form);
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-duty-roster-action]');if(!button)return;
  const action=button.dataset.dutyRosterAction,id=button.dataset.id;
  if(dutyRoster.saving)return;
  try{
    if(['open','back','new','copy','versions','period-open','period-new'].includes(action)&&!dutyCanLeave())return;
    if(action==='new'||action==='copy')rosterWizard(id);
    else if(action==='open')await dutyOpenRoster(id);
    else if(action==='period-new'){rosterWizard('',id);}
    else if(action==='period-open'){
      const target=rosterForPeriod(id);
      if(target)await dutyOpenRoster(target.roster_id);
      else if(dutyContext.capabilities.edit)rosterWizard('',id);
    }
    else if(action==='back'){dutyRoster.record=null;dutyRoster.draft=null;render();}
    else if(action==='view'){const dirty=Boolean(document.querySelector('[data-duty-form="roster-editor"][data-dirty="true"]'));dutyRoster.view=id;render();if(dirty)rosterDirty();}
    else if(action==='focus'){const card=document.querySelector(`[data-roster-task="${CSS.escape(id)}"]`);if(card){const details=card.closest('details');if(details)details.open=true;card.scrollIntoView({block:'center'});card.querySelector('button')?.focus();}else notice('這項工作由其他週期管理，請開啟「其他週期工作」切換班表。');}
    else if(action==='choose'){
      const a=dutyRoster.draft.find(a=>a.assignment_id===id);
      modal('選擇負責人：'+a.snapshot.name,`<form class="duty-person-picker" data-duty-form="roster-choose" data-id="${esc(id)}"><p class="duty-picker-hint">${a.snapshot.allow_multiple?'可選擇多位人員共同負責。':'點選一位人員負責這項工作。'} 本期：${esc(dutyRoster.record.date_from)} 至 ${esc(dutyRoster.record.date_to)}</p><label class="duty-picker-search">搜尋人員<input type="search" placeholder="姓名、暱稱或部門" data-roster-person-search></label><div class="duty-person-choice-grid">${dutySetup.people.filter(p=>p.active).map(p=>`<label class="duty-person-choice" data-person-choice data-search="${esc([p.full_name,p.display_name,p.department].filter(Boolean).join(' ').toLowerCase())}"><input type="${a.snapshot.allow_multiple?'checkbox':'radio'}" name="person_ids" value="${esc(p.person_id)}" data-name="${esc(p.full_name)}" ${a.person_ids.includes(p.person_id)?'checked':''}><span class="duty-person-avatar" aria-hidden="true">${esc(p.full_name.slice(0,1))}</span><span class="duty-choice-info"><strong title="${esc(p.full_name)}">${esc(p.full_name)}</strong><span>${esc([p.display_name!==p.full_name?p.display_name:'',p.department].filter(Boolean).join(' · ')||'值日人員')}</span><span class="duty-choice-workload">本期 ${dutyRoster.draft.filter(row=>row.person_ids.includes(p.person_id)).length} 項工作</span></span></label>`).join('')}</div><p class="duty-picker-empty" data-person-empty hidden>找不到符合的人員，試試其他姓名或部門。</p><p class="duty-picker-hint">LINE 綁定影響通知接收，不影響排班；可至「值日人員」管理綁定。</p><label class="duty-unassigned-choice"><input type="checkbox" name="unassigned" ${a.person_ids.length?'':'checked'}><span><strong>暫不指定</strong><small>保留未分配，稍後再安排。</small></span></label><p class="duty-form-error" role="alert" hidden></p><div class="duty-picker-footer"><p data-person-selection aria-live="polite"></p><button type="submit" class="btn primary">套用負責人</button></div></form>`);
      const form=document.querySelector('[data-duty-form="roster-choose"]');rosterChoiceSummary(form);form.querySelector('[data-roster-person-search]').focus({preventScroll:true});
    }else if(action==='substitute'){
      const a=dutyRoster.draft.find(a=>a.assignment_id===id),r=dutyRoster.record;
      modal('設定代班',`<form data-duty-form="roster-substitute" data-id="${esc(id)}">${selectField('原負責人','original_person_id',a.person_ids.map(pid=>[pid,rosterPersonName(pid,a)]),a.person_ids[0])}${selectField('代班人員','substitute_person_id',dutySetup.people.filter(p=>p.active).map(p=>[p.person_id,p.full_name]),'')}${field('代班開始日','date_from',r.date_from,'type="date" required')}${field('代班結束日','date_to',r.date_from,'type="date" required')}<p>只影響此期間，不改變後續輪替基準。</p>${a.substitutions.map((s,i)=>`<p>原：${esc(rosterPersonName(s.original_person_id,a))} → 代：${esc(rosterPersonName(s.substitute_person_id,a))} ${esc(s.date_from)}–${esc(s.date_to)} ${rosterAction('移除此代班','remove-sub',id+'|'+i)}</p>`).join('')}<p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">套用代班</button></form>`);
    }else if(action==='remove-sub'){const [aid,index]=id.split('|');dutyRoster.draft.find(a=>a.assignment_id===aid).substitutions.splice(Number(index),1);$('modal').close();render();rosterDirty();}
    else if(action==='publish')await publishWizard();
    else if(action==='preview'){const result=await api('/api/duty/roster/preview?roster_id='+dutyRoster.record.roster_id);modal('已儲存班表通知預覽',result.messages.map(m=>`<pre class="duty-message-preview">${esc(m.text)}</pre>`).join('')+'<p>只供預覽，不會發送 LINE 訊息。</p>');}
    else if(action==='delete'){
      const r=dutyRoster.rows.find(r=>r.roster_id===id);
      if(!confirm('確定刪除草稿 '+r.name+'？'))return;
      await api('/api/duty/roster/delete',{roster_id:id,expected_updated_at:r.updated_at});await load();render();
    }else if(action==='versions'){
      const r=dutyRoster.record,versions=dutyRoster.rows.filter(v=>v.date_from===r.date_from&&v.date_to===r.date_to);
      const activity=(await api('/api/duty/roster/activity?roster_id='+r.roster_id)).events;
      modal('版本與異動紀錄',`<h3>版本</h3>${versions.map(v=>rosterAction(v.name+' '+(v.version?'v'+v.version:'草稿')+' '+dutyRosterStatuses[v.status],'version-open',v.roster_id)).join('')}<h3>異動紀錄</h3>${activity.map(e=>`<article><strong>${esc(e.actor)} · ${when(e.created_at)}</strong><pre class="duty-message-preview">${esc(rosterActivityText(e))}</pre></article>`).join('')}`);
    }else if(action==='version-open'){$('modal').close();await dutyOpenRoster(id);}
    else if(action==='wizard-prev'||action==='wizard-next'){
      const form=button.closest('form'),step=Number(form.dataset.step),next=step+(action==='wizard-next'?1:-1);
      if(next>step){for(const input of form.querySelector(`[data-roster-step="${step}"]`).querySelectorAll('input,select,textarea'))if(!input.reportValidity())return;}
      if(form.dataset.dutyForm==='roster-create'&&next===3){const v=Object.fromEntries(new FormData(form));if(v.start_mode==='copy'&&!v.copy_from)throw Error('請選擇來源班表。');form.querySelector('.duty-create-summary').textContent=`${v.name}｜${v.date_from}–${v.date_to}｜${dutySetup.tasks.filter(t=>t.active).length} 項工作｜${v.start_mode==='copy'?'複製既有分配':v.start_mode==='rotation'?'建立後預覽輪替差異':'空白手動分配'}`;}
      wizardStep(form,next);
    }
  }catch(error){notice(error.message,true);}
});
document.addEventListener('submit',async event=>{
  const form=event.target,kind=form.dataset.dutyForm;if(!kind?.startsWith('roster'))return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');if(submit.disabled)return;submit.disabled=true;
  const v=Object.fromEntries(new FormData(form));
  try{
    if(kind==='roster-choose'){const a=dutyRoster.draft.find(a=>a.assignment_id===form.dataset.id);a.person_ids=form.elements.unassigned.checked?[]:new FormData(form).getAll('person_ids');a.substitutions=a.substitutions.filter(s=>a.person_ids.includes(s.original_person_id));$('modal').close();render();rosterDirty();return;}
    if(kind==='roster-substitute'){if(v.original_person_id===v.substitute_person_id||v.date_from>v.date_to||v.date_from<dutyRoster.record.date_from||v.date_to>dutyRoster.record.date_to)throw Error('代班人員或期間不正確。');dutyRoster.draft.find(a=>a.assignment_id===form.dataset.id).substitutions.push(v);$('modal').close();render();rosterDirty();return;}
    let result;
    dutyRoster.saving=true;
    document.querySelectorAll('.duty-period-navigation button').forEach(button=>button.disabled=true);
    if(kind==='roster-create')result=await api('/api/duty/roster/create',{...v,copy_from:v.start_mode==='copy'?v.copy_from:undefined});
    else if(kind==='roster-editor'){const r=dutyRoster.record;await api('/api/duty/roster/save',{roster_id:r.roster_id,expected_updated_at:r.updated_at,assignments:dutyRoster.draft});result={roster_id:r.roster_id};}
    else if(kind==='roster-publish'){const r=dutyRoster.record;result=await api('/api/duty/roster/publish',{roster_id:r.roster_id,expected_updated_at:r.updated_at,acknowledged:new FormData(form).getAll('acknowledged'),reason:v.reason,send_now:form.elements.send_now?.checked||false});}
    form.dataset.dirty='false';await load();await dutyOpenRoster(result.roster_id,false);dutyRoster.saving=false;render();if(form.closest('#modal'))$('modal').close();notice(kind==='roster-publish'?'班表已發布。':'班表草稿已儲存。');if(kind==='roster-create'&&v.start_mode==='rotation')document.querySelector('[data-duty-auto="apply-rule"]')?.click();
  }catch(error){dutyRoster.saving=false;document.querySelectorAll('.duty-period-navigation button').forEach(button=>button.disabled=!rosterForPeriod(button.dataset.id)&&!dutyContext.capabilities.edit);const el=form.querySelector('.duty-form-error');el.textContent=error.message;el.hidden=false;submit.disabled=false;}
});

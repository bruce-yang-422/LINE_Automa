"use strict";
const dutyAutomation={settings:null,impacts:{},rules:[],runs:[],log:{deliveries:[],stats:{},missing:[]},ruleDraft:null};
const dutyNoticeTypes={monthly:'月初公告',reminder:'工作提醒',publish:'班表發布',change:'班表異動',manual:'手動通知',test:'試送'};
async function loadDutyAutomation(){
  dutyAutomation.settings=null;dutyAutomation.rules=[];dutyAutomation.runs=[];dutyAutomation.log={deliveries:[],stats:{},missing:[]};
  if(!dutyContext)return;
  const [rules,log]=await Promise.all([api('/api/duty/rotation/rules'),api('/api/duty/notice/log')]);
  Object.assign(dutyAutomation,{rules:rules.rules,runs:rules.runs,log});
  if(dutyContext.can_inspect_setup){const [settings,impacts]=await Promise.all([api('/api/duty/notice/settings'),api('/api/duty/notice/impacts')]);Object.assign(dutyAutomation,{settings,impacts});}
}
function dutyAutoButton(title,action,id=''){return `<button type="button" class="btn small" data-duty-auto="${action}" data-id="${esc(id)}">${esc(title)}</button>`;}
function dutyAutoCheck(label,name,value){return `<label class="check-label"><input type="checkbox" name="${name}" ${value?'checked':''}>${label}</label>`;}
function dutyTypeChannels(kind,config){
  const mode=config.type_channels?.[kind]||{personal:config.personal,groups:Boolean(config.groups.length)};
  return `<div>${dutyAutoCheck('此類通知發個人私訊',kind+'_personal',mode.personal)}${dutyAutoCheck('此類通知發授權群組',kind+'_groups',mode.groups)}</div>`;
}
function dutyNoticeIcon(kind){
  const paths={calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 5h2m4 0h2"/>',person:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',send:'<path d="m3 11 18-8-8 18-2-8-8-2Zm8 2L21 3"/>'};
  return `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${paths[kind]||paths.bell}</svg>`;
}
function dutyNoticeCard(kind,title,description,enabledKey,fields){
  const c=dutyAutomation.settings.config,enabled=c[enabledKey];
  return `<section class="duty-notice-card" data-notice-card="${kind}"><div class="duty-visual-card-heading"><span class="duty-visual-icon">${dutyNoticeIcon(kind==='monthly'?'calendar':kind==='reminder'?'bell':'send')}</span><div><h3>${title}</h3><p>${description}</p></div></div><label class="duty-switch"><input type="checkbox" name="${enabledKey}" ${enabled?'checked':''}><span class="duty-switch-track" aria-hidden="true"></span><span>啟用${title}</span></label><div class="duty-notice-flow"><div><span>何時</span><strong data-notice-when>${kind==='monthly'?'每月 1 日 '+c.monthly_time:kind==='reminder'?'依工作日期與時間':'管理者確認'+(kind==='change'?'新版班表':'發布')+'時'}</strong></div><span class="duty-flow-arrow" aria-hidden="true">${dutyNoticeIcon('send')}</span><div><span>通知誰</span><strong>${kind==='monthly'?'所有值日人員':kind==='change'?'原、新負責人':'當期負責人'}</strong></div></div><p class="duty-notice-status" data-notice-status>${enabled?'已啟用，依下方設定發送':'目前關閉，不會發送'}</p><details class="duty-notice-options" ${enabled?'open':''}><summary>設定時間與收件方式</summary>${fields}<h4>傳送到哪裡？</h4>${dutyTypeChannels(kind,c)}<div class="duty-chat-example"><span>訊息範例</span><p>${kind==='monthly'?'【月初值日生班表】<br>本月負責：掃地與擦拭':kind==='reminder'?'【值日生提醒】<br>今天請打包垃圾，並帶去倒垃圾':kind==='change'?'【班表異動】<br>您的分配已更新，請查看新版班表':'【值日生班表發布】<br>您的值日工作已安排，請查看班表'}</p><small>範例文字；實際內容依已發布班表產生。</small></div></details></section>`;
}
function dutyNotificationPage(){
  const s=dutyAutomation.settings;if(!s)return empty('通知設定僅供管理人員使用','請聯絡組織管理員。');
  const c=s.config,disabled=!dutyContext.capabilities.notify_settings;
  return `<section class="duty-visual-page"><header class="duty-visual-header"><h2>安排提醒</h2><p>選擇 LINE 帳號，再開啟需要的提醒。儲存前不會生效。</p><ol class="duty-visual-steps"><li><span>1</span>選 LINE 帳號</li><li><span>2</span>選通知對象</li><li><span>3</span>開啟提醒</li></ol></header><form data-duty-form="automation-settings"><fieldset class="duty-visual-form" ${disabled?'disabled':''}><legend>提醒設定</legend><section class="duty-visual-section duty-notification-channel"><div class="duty-visual-card-heading"><span class="duty-step-number">1</span><div><h3>用哪個 LINE 帳號通知？</h3><p>值日提醒將由這個帳號傳送。</p></div></div>${selectField('通知 OA','channel_id',[['','請選擇 LINE 帳號'],...s.channels.map(o=>[o.channel_id,o.name])],s.channel_id)}${s.channel_id?`<details data-notice-oa-change><summary>更換帳號的影響</summary><p>會解除 ${dutyAutomation.impacts.bindings||0} 筆綁定，取消 ${dutyAutomation.impacts.pending||0} 筆待發通知。更換時需確認並填原因。</p>${dutyAutoCheck('確認變更通知 OA 的影響','confirm_channel_change',false)}${field('變更 OA 原因','reason','')}</details>`:`<input type="hidden" name="reason" value=""><p class="duty-notice-status">先選擇並儲存帳號，再綁定人員或選擇所屬群組。</p>`}</section><section class="duty-visual-section duty-notification-recipients"><div class="duty-visual-card-heading"><span class="duty-step-number">2</span><div><h3>提醒要傳到哪裡？</h3><p>個人收到自己的工作；群組收到彙整公告。</p></div></div><div class="duty-recipient-options"><label class="duty-recipient-choice">${dutyNoticeIcon('person')}<input type="checkbox" name="personal" ${c.personal?'checked':''}><strong>個人 LINE</strong><span>限已綁定且訂閱的人員 · 已訂閱 ${s.subscribed} 人</span></label><div class="duty-recipient-choice">${dutyNoticeIcon('send')}<strong>LINE 群組</strong><div class="duty-notification-groups">${s.groups.map(g=>`<label class="check-label"><input type="checkbox" name="groups" value="${esc(g.recipient_id)}" ${c.groups.includes(g.recipient_id)?'checked':''}>${esc(g.custom_name||g.display_name||'未命名群組')}</label>`).join('')||'<span>儲存 LINE 帳號後，再選擇可用群組。</span>'}</div></div></div></section><section class="duty-visual-section duty-notification-reminders"><div class="duty-visual-card-heading"><span class="duty-step-number">3</span><div><h3>哪些事情需要提醒？</h3><p>開啟卡片上的開關，展開設定時間及收件方式。</p></div></div><div class="duty-notice-card-grid">${dutyNoticeCard('monthly','月初公告','每月公布新的值日分配','monthly_enabled',field('公告時間（台北時間）','monthly_time',c.monthly_time,'type="time" required'))}${dutyNoticeCard('reminder','工作提醒','在需要做事的時間提醒負責人','reminders_enabled',field('預設提醒時間（留空不發送）','default_time',c.default_time,'type="time"')+field('提前幾天提醒','advance_days',c.advance_days,`type="number" min="0" max="${cap('DUTY_NOTICE_HORIZON_DAYS')}"`)+'<p>工作自訂時間優先；同一人同時段合併通知。</p>')}${dutyNoticeCard('publish','班表發布','發布班表時可選擇通知','publish_enabled','<p>發布班表時，還需要勾選「同時立即發送」。</p>')}${dutyNoticeCard('change','分配異動','新版發布時通知受影響人員','change_enabled','<p>重新發布班表時，還需要勾選發送。</p>')}</div></section><details class="duty-visual-advanced"><summary>進階：錯過時間後如何處理</summary>${field('允許補發的分鐘數（0＝不補發）','catchup_minutes',c.catchup_minutes,`type="number" min="0" max="${cap('DUTY_NOTICE_CATCHUP_MAX_MINUTES')}"`)}</details><div class="duty-visual-save"><p>設定完成後儲存；關閉的提醒不會發送。</p><p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">儲存通知設定</button></div></fieldset></form><details class="duty-visual-advanced"><summary>試送、手動通知與用量</summary><div class="duty-actions">${dutyAutoButton('預覽通知與用量','preview-notice')}${dutyContext.capabilities.send?dutyAutoButton('建立手動通知','manual')+dutyAutoButton('試送給…','test'):''}</div><p>${esc(s.estimate.month)}：個人 ${s.estimate.personal_push} 則；群組 ${s.estimate.group_requests} 次請求，成員用量待確認；缺漏 ${s.estimate.missing} 項。</p><p>${esc(s.estimate.note)}</p></details><details class="duty-visual-advanced duty-trash-shortcut"><summary>倒垃圾：設定週一、週四、週五的提醒</summary>${dutyTrashPanel()}</details></section>`;
}
document.addEventListener('change',event=>{
  const form=event.target.closest('[data-duty-form="automation-settings"]');if(!form)return;
  const card=event.target.closest('[data-notice-card]');
  if(card&&['monthly_enabled','reminders_enabled','publish_enabled','change_enabled'].includes(event.target.name)){
    card.querySelector('details').open=event.target.checked;
    card.querySelector('[data-notice-status]').textContent=event.target.checked?'已啟用，請確認時間與收件方式':'目前關閉，不會發送';
  }
  if(event.target.name==='monthly_time')form.querySelector('[data-notice-card="monthly"] [data-notice-when]').textContent='每月 1 日 '+event.target.value;
  if(event.target.name==='channel_id'){const change=form.querySelector('[data-notice-oa-change]');if(change)change.open=event.target.value!==dutyAutomation.settings.channel_id;}
});

function dutyTrashPanel(){
  return `<section class="panel panel-body section-space"><h2>倒垃圾提醒捷徑</h2><p>週一、週四打包並倒垃圾；週五打包至一樓集中。與工作子項目共用設定，儲存為工作新版本後需重新發布受影響班表。</p><form data-duty-form="automation-trash"><fieldset ${dutyContext.capabilities.edit?'':'disabled'}>${selectField('倒垃圾工作','task_id',[['','選擇工作'],...dutySetup.tasks.filter(t=>t.active&&t.versions[0]?.kind==='normal').map(t=>[t.task_id,t.versions[0].name])],'')}<div class="duty-notice-grid">${[['週一垃圾車','monday'],['週四垃圾車','thursday'],['週五下班前','friday']].map(([title,key])=>`<section class="duty-check-panel"><h3>${title}</h3>${field('通知時間（留空不啟用）',key,'','type="time"')}</section>`).join('')}</div>${field('生效日','effective_from',dutyDate(),'type="date" required')}<div class="duty-trash-impacts"></div><p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">儲存倒垃圾子項目</button></fieldset></form></section>`;
}
function dutyNotificationLog(){
  const l=dutyAutomation.log;
  return `<section class="panel panel-body"><h2>通知紀錄</h2>${(l.errors||[]).map(e=>`<p class="callout warn">${when(e.created_at)}：${esc(e.detail)}</p>`).join('')}<p>LINE 已接受不代表已讀或完成。結果不明不自動重送。</p><div class="duty-context">${['pending','sending','accepted','failed','cancelled','unknown'].map(s=>badge((statusNames[s]||s)+' '+(l.stats[s]||0))).join('')}</div><form data-duty-form="automation-log"><div class="duty-filters">${selectField('類型','kind',[['','全部'],...Object.entries(dutyNoticeTypes)],'')}${selectField('狀態','status',[['','全部'],...['pending','sending','accepted','failed','cancelled','unknown'].map(s=>[s,statusNames[s]])],'')}${field('期間起日','from','','type="date"')}${field('期間迄日','to','','type="date"')}</div>${selectField('人員','person_id',[['','全部'],...dutySetup.people.map(p=>[p.person_id,p.full_name])],'')}<button type="submit" class="btn small">篩選／重新整理</button><p class="duty-form-error" role="alert" hidden></p></form><p>顯示最新 ${l.limit||cap('DUTY_NOTICE_PAGE_SIZE')} 筆符合條件的紀錄。</p>${l.deliveries.map(d=>`<details class="history-item"><summary>${esc(d.label)} · ${esc(dutyNoticeTypes[d.notice_kind])} · ${when(d.scheduled_at)} ${badge(statusNames[d.status])}</summary><p>操作者：${esc(d.actor)}</p><p>班表版本：${d.roster_ids.map(r=>esc(r.name||r.roster_id)+' v'+r.version).join('、')}</p><pre class="duty-message-preview">${esc(d.message.map(m=>m.text).join('\n'))}</pre>${d.error?`<p class="callout warn">${esc(d.error)}</p>`:''}<h4>嘗試紀錄</h4>${d.attempts.map(a=>`<p>${when(a.time)} · ${esc(statusNames[a.status])} · ${esc(a.error||a.request_id)}</p>`).join('')||'<p>尚未開始發送。</p>'}${dutyContext.capabilities.send?({'pending':dutyAutoButton('取消','delivery-cancel',d.delivery_id),'failed':dutyAutoButton('檢查後重試','delivery-retry',d.delivery_id),'unknown':dutyAutoButton('已確認收到','delivery-confirm_received',d.delivery_id)+dutyAutoButton('確認後重新發送','delivery-resend',d.delivery_id)}[d.status]||''):''}</details>`).join('')||empty('尚無通知紀錄','啟用通知或建立手動通知後在此查看。')}<details><summary>最近月初公告缺漏名單（${l.missing.length}）</summary>${l.missing.map(m=>`<p>${esc(m.name)}：${esc(m.reason)}</p>`).join('')||'<p>沒有缺漏紀錄。</p>'}</details></section>`;
}
function dutyRotationPanel(){
  const latest=['year','month','week'].map(p=>dutyAutomation.rules.find(r=>r.period_type===p)).filter(Boolean);
  return `<section class="panel panel-body section-space"><div class="duty-section-heading"><h2>輪替規則</h2>${dutyContext.capabilities.edit?dutyAutoButton('新增輪替規則','rule-new'):''}</div>${latest.map(r=>`<article class="duty-person-card"><div><strong>${esc(dutyRotationNames[r.period_type])} v${r.version}</strong><p>${esc(r.effective_from)} 起生效 · ${r.automatic?'自動輪換已啟用':'手動套用'} · ${r.config.position_ids.length} 個位置／${r.config.task_ids.length} 項工作</p></div>${dutyContext.capabilities.edit?dutyAutoButton('編輯新版本','rule-edit',r.rule_version_id):''}</article>`).join('')||'<p>尚未設定輪替規則。</p>'}<details><summary>自動輪換執行紀錄</summary>${dutyAutomation.runs.map(r=>`<p>${esc(r.date_from)} · ${esc({blocked:'待處理',ready:'待發布',published:'已發布'}[r.status]||r.status)} · ${esc(r.error)} ${r.roster_id?`<button type="button" class="btn text small" data-duty-roster-action="open" data-id="${esc(r.roster_id)}">查看班表</button>`:''}</p>`).join('')||'<p>尚無執行紀錄。</p>'}</details></section>`;
}
function ruleOrderHtml(type,ids){
  return ids.map((id,i)=>`<div class="duty-order-row" data-order-id="${esc(id)}"><span>${esc(type==='positions'?'代號 '+(dutySetup.positions.find(p=>p.position_id===id)?.code||''):(dutySetup.tasks.find(t=>t.task_id===id)?.versions[0]?.name||'工作'))}</span>${dutyAutoButton('上移','order-up',type+'|'+i)}${dutyAutoButton('下移','order-down',type+'|'+i)}</div>`).join('');
}
function ruleSelectionHtml(period){
  const c=dutyAutomation.ruleDraft;
  return `<h3>參與輪替的位置</h3>${dutySetup.positions.map(p=>`<label class="check-label"><input type="checkbox" data-rule-include="positions" value="${esc(p.position_id)}" ${c.position_ids.includes(p.position_id)?'checked':''}>代號 ${esc(p.code)}${p.vacant?'（X 待補位）':''}</label>`).join('')}<h3>參與輪替的工作</h3>${dutySetup.tasks.filter(t=>t.active&&[period,'fixed'].includes(t.versions[0]?.rotation)).map(t=>`<label class="check-label"><input type="checkbox" data-rule-include="tasks" value="${esc(t.task_id)}" ${c.task_ids.includes(t.task_id)?'checked':''}>${esc(t.versions[0].name)}</label>`).join('')}`;
}
function ruleBaseHtml(){
  const c=dutyAutomation.ruleDraft;
  return c.task_ids.map((id,i)=>`<div class="form-grid" data-rule-task="${esc(id)}">${selectField(dutySetup.tasks.find(t=>t.task_id===id)?.versions[0]?.name||'工作','base',c.position_ids.map(p=>[p,'代號 '+(dutySetup.positions.find(s=>s.position_id===p)?.code||'')]),c.base[id]||c.position_ids[i%c.position_ids.length])}${dutyAutoCheck('固定在此位置，不參與輪替','fixed',Boolean(c.fixed[id]))}</div>`).join('');
}
function ruleForm(rule){
  const period=rule?.period_type||'month';const c=rule?.config||{baseline_date:dutyDate().slice(0,7)+'-01',boundary:1,year_month:1,direction:1,step:1,position_ids:dutySetup.positions.map(p=>p.position_id),task_ids:dutySetup.tasks.filter(t=>t.active&&t.versions[0]?.rotation==='month').map(t=>t.task_id),base:{},fixed:{}};
  dutyAutomation.ruleDraft=structuredClone(c);
  modal('輪替規則',`<form data-duty-form="automation-rule" data-version="${rule?.version||0}"><div class="form-grid">${selectField('輪換週期','period_type',[['year','每年'],['month','每月'],['week','每週']],period)}${field('基準日期','baseline_date',c.baseline_date,'type="date" required')}${field('生效日','effective_from',rule?.effective_from||c.baseline_date,'type="date" required')}${field('週起始日 0–6／每月或每年換班日 1–31','boundary',c.boundary,'type="number" min="0" max="31" required')}${field('年度起始月份','year_month',c.year_month,'type="number" min="1" max="12" required')}${selectField('移動方向','direction',[['1','向後'],['-1','向前']],String(c.direction))}${field('每期移動步數','step',c.step,`type="number" min="1" max="${cap('DUTY_ROTATION_STEP_MAX')}" required`)}</div><div class="duty-rule-selection">${ruleSelectionHtml(period)}</div><h3>人員位置順序（含待補位）</h3><div data-rule-order="positions">${ruleOrderHtml('positions',c.position_ids)}</div><h3>工作順序與基準分配</h3><div data-rule-order="tasks">${ruleOrderHtml('tasks',c.task_ids)}</div><div class="duty-rule-base">${c.task_ids.map((id,i)=>`<div class="form-grid" data-rule-task="${esc(id)}">${selectField(dutySetup.tasks.find(t=>t.task_id===id)?.versions[0]?.name||'工作','base',[...c.position_ids.map(p=>[p,'代號 '+(dutySetup.positions.find(s=>s.position_id===p)?.code||'')])],c.base[id]||c.position_ids[i%c.position_ids.length])}${dutyAutoCheck('固定在此位置，不參與輪替','fixed',Boolean(c.fixed[id]))}</div>`).join('')}</div>${dutyAutoCheck('啟用自動輪換','automatic',Boolean(rule?.automatic))}${dutyAutoCheck('已確認接下來三期、全員公告範圍與通知內容','confirm_automatic',false)}<p>自動輪換遇到未分配、規則缺漏或既有草稿時停止並提示。月初公告對所有值日人員，個人通知仍須訂閱，群組依通知設定。請先在通知設定預覽內容。</p>${field('異動原因（修改版本必填）','reason','',rule?'required':'')}<div class="duty-rule-preview"></div><p class="duty-form-error" role="alert" hidden></p><div class="form-actions">${dutyAutoButton('預覽接下來三期','rule-preview')}<button type="submit" class="btn primary">儲存規則新版本</button></div></form>`);
}
function readRule(form){
  const v=Object.fromEntries(new FormData(form)),c=dutyAutomation.ruleDraft;
  const base={},fixed={};for(const row of form.querySelectorAll('[data-rule-task]')){base[row.dataset.ruleTask]=row.querySelector('[name="base"]').value;if(row.querySelector('[name="fixed"]').checked)fixed[row.dataset.ruleTask]=base[row.dataset.ruleTask];}
  return {...v,expected_version:Number(form.dataset.version),automatic:form.elements.automatic.checked,confirm_automatic:form.elements.confirm_automatic.checked,config:{...c,baseline_date:v.baseline_date,boundary:Number(v.boundary),year_month:Number(v.year_month),direction:Number(v.direction),step:Number(v.step),base,fixed}};
}
document.addEventListener('change',event=>{
  const form=event.target.closest('[data-duty-form]');if(!form)return;
  if(form.dataset.dutyForm==='automation-rule'&&event.target.name==='period_type'){
    const period=event.target.value,c=dutyAutomation.ruleDraft;
    c.task_ids=dutySetup.tasks.filter(t=>t.active&&['fixed',period].includes(t.versions[0]?.rotation)).map(t=>t.task_id);c.base={};c.fixed={};
    form.querySelector('[data-rule-order="tasks"]').innerHTML=ruleOrderHtml('tasks',c.task_ids);
    form.querySelector('.duty-rule-base').innerHTML=ruleBaseHtml();
    form.querySelector('.duty-rule-selection').innerHTML=ruleSelectionHtml(period);
    const today=new Date(dutyDate()+'T00:00:00Z');
    form.elements.boundary.value=period==='week'?0:1;
    if(period==='week')today.setUTCDate(today.getUTCDate()-((today.getUTCDay()+6)%7));
    form.elements.baseline_date.value=period==='week'?today.toISOString().slice(0,10):period==='year'?dutyDate().slice(0,4)+'-01-01':dutyDate().slice(0,7)+'-01';
    form.elements.effective_from.value=form.elements.baseline_date.value;
  }
  if(form.dataset.dutyForm==='automation-rule'&&event.target.dataset.ruleInclude){
    const c=dutyAutomation.ruleDraft;
    for(const row of form.querySelectorAll('[data-rule-task]')){c.base[row.dataset.ruleTask]=row.querySelector('[name="base"]').value;if(row.querySelector('[name="fixed"]').checked)c.fixed[row.dataset.ruleTask]=c.base[row.dataset.ruleTask];else delete c.fixed[row.dataset.ruleTask];}
    const kind=event.target.dataset.ruleInclude,key=kind==='positions'?'position_ids':'task_ids',id=event.target.value;
    if(event.target.checked&&!c[key].includes(id))c[key].push(id);else if(!event.target.checked)c[key]=c[key].filter(v=>v!==id);
    for(const task of Object.keys(c.base))if(!c.task_ids.includes(task)||!c.position_ids.includes(c.base[task]))delete c.base[task];
    for(const task of Object.keys(c.fixed))if(!c.task_ids.includes(task)||!c.position_ids.includes(c.fixed[task]))delete c.fixed[task];
    form.querySelector(`[data-rule-order="${kind}"]`).innerHTML=ruleOrderHtml(kind,c[key]);form.querySelector('.duty-rule-base').innerHTML=ruleBaseHtml();
  }
  if(form.dataset.dutyForm==='automation-trash' &&event.target.name==='task_id'){
    const task=dutySetup.tasks.find(t=>t.task_id===event.target.value);if(!task)return;
    for(const [weekday,key] of [[0,'monday'],[3,'thursday'],[4,'friday']])form.elements[key].value=task.versions[0].items.find(i=>i.frequency==='weekly'&&i.weekdays.includes(weekday))?.reminder_time||'';
    form.querySelector('.duty-trash-impacts').innerHTML=dutyImpactFields(task.impacts);
  }
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-duty-auto]');if(!button)return;const action=button.dataset.dutyAuto,id=button.dataset.id;
  try{
    if(['rule-new','rule-edit','manual','test'].includes(action)&&!dutyCanLeave())return;
    if(action==='rule-new'||action==='rule-edit')ruleForm(dutyAutomation.rules.find(r=>r.rule_version_id===id));
    else if(action==='order-up'||action==='order-down'){
      const [kind,index]=id.split('|'),c=dutyAutomation.ruleDraft,key=kind==='positions'?'position_ids':'task_ids',i=Number(index),next=i+(action==='order-up'?-1:1);
      if(next>=0&&next<c[key].length){[c[key][i],c[key][next]]=[c[key][next],c[key][i]];const form=button.closest('form');form.dataset.dirty='true';form.querySelector(`[data-rule-order="${kind}"]`).innerHTML=ruleOrderHtml(kind,c[key]);}
    }else if(action==='rule-preview'){
      const form=button.closest('form'),result=await api('/api/duty/rotation/preview',readRule(form));form.dataset.signature=result.signature;
      form.querySelector('.duty-rule-preview').innerHTML=result.periods.map(p=>`<h3>${esc(p.date_from)}–${esc(p.date_to)}</h3>${p.assignments.map(a=>`<p>${esc(a.work)}：${esc(a.name)}</p>`).join('')}${p.warnings.map(w=>`<p class="callout warn">${esc(w)}</p>`).join('')}`).join('')+`<h4>全員通知範圍與內容摘要</h4><p>全部值日人員 ${result.notice_scope.messages.length} 人｜月初 ${esc(result.notice_scope.time)}｜${result.notice_scope.monthly_enabled?'公告啟用':'公告未啟用'}｜個人${result.notice_scope.personal?'啟用':'停用'}｜群組 ${result.notice_scope.groups.length} 個</p>${result.notice_scope.messages.map(m=>`<details><summary>${esc(m.name)}</summary><pre class="duty-message-preview">${esc(m.text)}</pre></details>`).join('')}<details><summary>個人通知缺漏 ${result.notice_scope.missing.length} 人</summary>${result.notice_scope.missing.map(m=>`<p>${esc(m.name)}：${esc(m.reason)}</p>`).join('')}</details><p>摘要只列此條規則，正式通知還會合併其他週期工作並檢查完整班表。</p>`;
    }else if(action==='apply-rule'){
      const r=dutyRoster.record,result=await api('/api/duty/rotation/apply',{roster_id:r.roster_id});
      modal('套用輪替差異',`<form data-duty-form="automation-apply" data-signature="${result.signature}">${result.differences.map(d=>`<p>${esc(d.work)}：${esc(d.before.map(p=>dutySetup.people.find(s=>s.person_id===p)?.full_name||'未分配').join('、')||'未分配')} → ${esc(d.name)}</p>`).join('')||'<p>分配結果相同。</p>'}${result.warnings.map(w=>`<p class="callout warn">${esc(w)}</p>`).join('')}<p>套用會移除被套用工作的當期代班，請重新確認。</p><p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">確認套用到草稿</button></form>`);
    }else if(['manual','test','preview-notice'].includes(action)){
      modal(action==='test'?'指定對象試送':'通知預覽',`<form data-duty-form="automation-manual" data-request="${crypto.randomUUID()}">${selectField('類型','kind',action==='test'?[['test','試送']]:[['manual','手動通知'],['monthly','月初公告預覽'],['reminder','工作提醒預覽']],'')}${field('執行日期','date',dutyDate(),'type="date" required')}${selectField('已發布期間（留空使用執行日期）','roster_id',[['','依日期'],...dutyRoster.rows.filter(r=>r.status==='published').map(r=>[r.roster_id,r.name+' v'+r.version])],'')}<h3>選擇人員（未選＝全部；試送只選一人）</h3>${dutySetup.people.filter(p=>p.active).map(p=>`<label class="check-label"><input type="checkbox" name="person_ids" value="${esc(p.person_id)}">${esc(p.full_name)}</label>`).join('')}<h3>工作範圍（未選＝全部）</h3>${dutySetup.tasks.filter(t=>t.active).map(t=>`<label class="check-label"><input type="checkbox" name="task_ids" value="${esc(t.task_id)}">${esc(t.versions[0]?.name)}</label>`).join('')}<div class="duty-manual-preview"></div><p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">預覽通知</button></form>`);
    }else if(action.startsWith('delivery-')){
      const d=dutyAutomation.log.deliveries.find(d=>d.delivery_id===id),mode=action.slice(9);
      modal('通知操作確認',`<form data-duty-form="automation-delivery" data-request="${crypto.randomUUID()}" data-id="${esc(id)}" data-action="${mode}" data-status="${d.status}"><p>${esc(d.label)}｜${esc(statusNames[d.status])}</p><pre class="duty-message-preview">${esc(d.message.map(m=>m.text).join('\n'))}</pre>${mode==='cancel'?'':field('確認結果／操作原因','reason','','required')}<p>結果不明請先向收件人確認；重新發送可能造成重複訊息。</p><p class="duty-form-error" role="alert" hidden></p><button type="submit" class="btn primary">確認操作</button></form>`);
    }
  }catch(error){notice(error.message,true);}
});
document.addEventListener('submit',async event=>{
  const form=event.target,kind=form.dataset.dutyForm;if(!kind?.startsWith('automation-'))return;event.preventDefault();const button=form.querySelector('[type="submit"]'),error=form.querySelector('.duty-form-error');button.disabled=true;error.hidden=true;const v=Object.fromEntries(new FormData(form));
  try{
    if(kind==='automation-settings'){
      const config={};for(const key of ['monthly_enabled','personal','reminders_enabled','publish_enabled','change_enabled'])config[key]=form.elements[key].checked;
      for(const key of ['monthly_time','default_time'])config[key]=v[key];for(const key of ['catchup_minutes','advance_days'])config[key]=Number(v[key]);config.groups=new FormData(form).getAll('groups');config.type_channels={};for(const type of ['monthly','reminder','publish','change'])config.type_channels[type]={personal:form.elements[type+'_personal'].checked,groups:form.elements[type+'_groups'].checked};
      await api('/api/duty/notice/settings',{channel_id:v.channel_id,config,expected_revision:dutyAutomation.settings.revision,confirm_channel_change:Boolean(form.elements.confirm_channel_change?.checked),impacts:dutyAutomation.impacts,reason:v.reason});
    }else if(kind==='automation-trash'){
      const task=dutySetup.tasks.find(t=>t.task_id===v.task_id);if(!task)throw Error('請選擇倒垃圾工作。');
      await api('/api/duty/notice/trash',{...v,task_id:task.task_id,expected_updated_at:task.updated_at,times:[v.monday,v.thursday,v.friday],confirm_impacts:form.elements.confirm_impacts?.checked||false,impacts:task.impacts});
    }else if(kind==='automation-rule'){
      await api('/api/duty/rotation/save',{...readRule(form),signature:form.dataset.signature});
    }else if(kind==='automation-apply'){
      await api('/api/duty/rotation/apply',{roster_id:dutyRoster.record.roster_id,confirm:true,signature:form.dataset.signature});
    }else if(kind==='automation-manual'){
      const data=new FormData(form),selected=data.getAll('person_ids'),tasks=data.getAll('task_ids');const payload={...v,roster_id:v.roster_id||undefined,person_ids:selected.length?selected:undefined,task_ids:tasks.length?tasks:undefined};
      const source=JSON.stringify(payload);
      if(form.dataset.source===source&&form.dataset.signature&&['manual','test'].includes(v.kind)){
        await api('/api/duty/notice/send',{...payload,confirm:true,signature:form.dataset.signature,request_id:form.dataset.request});
      }else{
        const result=await api('/api/duty/notice/preview',payload);form.dataset.signature=result.signature;form.dataset.source=source;
        form.querySelector('.duty-manual-preview').innerHTML=`<h3>預覽 ${result.messages.length} 個聊天室</h3>${result.messages.map(m=>`<details><summary>${esc(m.label)} · ${esc(m.time)}</summary><pre class="duty-message-preview">${esc(m.message)}</pre></details>`).join('')}<p>已知個人 push：${result.push_count}；群組 ${result.group_count||0} 個（成員數待確認）</p><h3>缺漏名單</h3>${result.missing.map(m=>`<p>${esc(m.name)}：${esc(m.reason)}</p>`).join('')||'<p>沒有缺漏。</p>'}`;
        button.textContent=['manual','test'].includes(v.kind)&&result.messages.length?'確認發送':'重新預覽';button.disabled=false;return;
      }
    }else if(kind==='automation-delivery')await api('/api/duty/notice/action',{...v,delivery_id:form.dataset.id,action:form.dataset.action,expected_status:form.dataset.status,confirm:true,request_id:form.dataset.request});
    else if(kind==='automation-log'){
      const q=new URLSearchParams(Object.entries(v).filter(([,value])=>value));dutyAutomation.log=await api('/api/duty/notice/log?'+q);form.dataset.dirty='false';render();return;
    }
    form.dataset.dirty='false';await load();render();if(form.closest('#modal'))$('modal').close();notice(kind==='automation-trash'?'已保存工作新版本，請重新發布受影響班表。':'設定已儲存。');
  }catch(exc){error.textContent=exc.message;error.hidden=false;button.disabled=false;}
});

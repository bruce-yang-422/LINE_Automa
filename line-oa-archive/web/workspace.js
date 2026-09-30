"use strict";
// These views use only data returned by the authenticated, scoped APIs.
const workspaceUI={reportQuery:"",reportLayout:"list",reportDetail:"",contactDetail:"",scheduleFilter:"scheduled"};

function workspaceHeader(){
  if(!state.contacts.some(r=>r.recipient_id===workspaceUI.contactDetail))workspaceUI.contactDetail="";
  if(!state.reports.some(r=>r.report_id===workspaceUI.reportDetail))workspaceUI.reportDetail="";
  const user=state.session.user;
  const context=document.getElementById("workspace-context-name");
  context.textContent=superAdmin()?"平台工作區":orgName(user.company);
  document.getElementById("workspace-context-kind").textContent=superAdmin()?"跨組織管理":roleName(state.session.role);
  document.getElementById("workspace-context").hidden=lineUI.registry||!document.getElementById("organization-select").hidden;
  if(lineUI.registry)document.getElementById("organization-select").hidden=true;
  document.querySelector('nav [data-view="schedule"]').hidden=!admin();
}

function reportDetailPanel(r){
  if(!r)return "";
  return `<aside class="detail-panel" id="report-detail" aria-labelledby="report-detail-title" tabindex="-1"><div class="detail-heading"><div><h2 id="report-detail-title">${esc(r.title)}</h2><p class="subtitle">報告詳情</p></div>${button("✕","close-report-detail","icon-button",'aria-label="關閉報告詳情"')}</div><div class="detail-body"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><dl><dt>狀態</dt><dd>${reportBadge(r)}</dd><dt>可見範圍</dt><dd>${esc(scope(r))}</dd><dt>最後更新</dt><dd>${esc(when(r.modified_at))}</dd><dt>檔案大小</dt><dd>${r.size?Math.ceil(r.size/1024)+" KB":"尚無檔案"}</dd></dl><div class="detail-actions">${button("放大預覽","preview","",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`)}${canSend()?button("建立發送","choose-report","primary",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`):""}</div>${superAdmin()?`<div class="detail-actions">${r.report_id!=="weather"?button("設定來源","edit-report","",`data-id="${esc(r.report_id)}"`):""}${button("移除報告","remove-report","text",`data-id="${esc(r.report_id)}"`)}</div>`:""}</div></aside>`;
}

function workspaceReports(wizard=false){
  if(wizard)return null;
  const rows=state.reports.filter(r=>(state.reportFilter==="all"||r.category===state.reportFilter)&&`${r.title} ${scope(r)}`.toLowerCase().includes(workspaceUI.reportQuery.toLowerCase()));
  const detail=rows.find(r=>r.report_id===workspaceUI.reportDetail);
  return heading("報告中心","集中查看報告、確認內容與來源，再選擇發送對象。",superAdmin()?(state.settings.weather_report_removed?button("恢復天氣報告","restore-weather",""):"")+button(icon("plus")+"新增報告來源","new-report","primary"):"")+
  `<div class="library-toolbar"><label class="search-field">${icon("search")}<input id="report-search" type="search" value="${esc(workspaceUI.reportQuery)}" placeholder="搜尋報告名稱或可見範圍" aria-label="搜尋報告"></label><div class="segmented">${[["all","所有報告"],...(state.reports.some(r=>r.category==="weather")?[["weather","天氣報告"]]:[]),["company","組織報表"],["other","其他報告"]].map(([id,text])=>`<button data-action="report-filter" data-id="${id}" aria-pressed="${state.reportFilter===id}" class="${state.reportFilter===id?"active":""}">${text}</button>`).join("")}</div><div class="segmented layout-picker" role="group" aria-label="報告顯示方式">${[["list","清單","menu"],["grid","卡片","grid"]].map(([id,t,i])=>`<button data-action="report-layout" data-id="${id}" aria-label="${t}" title="${t}" aria-pressed="${workspaceUI.reportLayout===id}" class="${workspaceUI.reportLayout===id?"active":""}">${icon(i)}</button>`).join("")}</div></div>`+
  `<div class="library-split ${detail?"has-detail":""}"><div><p class="subtitle" role="status">共 ${rows.length} 份報告</p><div class="report-grid ${workspaceUI.reportLayout==="list"?"list-layout":""}">${rows.map(r=>`<article class="panel report-card ${r.report_id===workspaceUI.reportDetail?"selected":""}"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><div class="report-card-body">${reportBadge(r)}<h3>${esc(r.title)}</h3><div class="report-meta"><span>${esc(scope(r))}</span><span>${icon("clock")} ${when(r.modified_at)}${r.size?` · ${Math.ceil(r.size/1024)} KB`:""}</span></div><div class="report-card-bottom">${button("查看詳情","report-detail","",`data-id="${esc(r.report_id)}" aria-expanded="${r.report_id===workspaceUI.reportDetail}"`)}${canSend()?button("建立發送","choose-report","primary",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`):""}</div>${superAdmin()?`<div class="report-card-bottom">${r.report_id!=="weather"?button("設定來源","edit-report","text small",`data-id="${esc(r.report_id)}"`):""}${button("移除報告","remove-report","text small",`data-id="${esc(r.report_id)}"`)}</div>`:""}</div></article>`).join("")}</div>${rows.length?"":empty("沒有符合的報告",workspaceUI.reportQuery?"試著換一個關鍵字，或切換報告分類。":"新增來源或取得授權後，報告會顯示在這裡。")}</div>${reportDetailPanel(detail)}</div>`;
}

function contactDetailPanel(){
  const r=state.contacts.find(r=>r.recipient_id===workspaceUI.contactDetail);
  if(!r)return "";
  return `<aside class="detail-panel" id="contact-detail" aria-labelledby="contact-detail-title" tabindex="-1"><div class="detail-heading"><div><h2 id="contact-detail-title">${esc(label(r))}</h2><p class="subtitle">${r.kind==="user"?"個人聊天室":"LINE 群組"}</p></div>${button("✕","close-contact-detail","icon-button",'aria-label="關閉收件者詳情"')}</div><div class="detail-body">${person(r)}<dl><dt>狀態</dt><dd>${badge(r.active?"可接收":"已停用",r.active?"good":"")}</dd><dt>所屬組織</dt><dd>${esc(r.company?orgName(r.company):"尚未分類")}</dd><dt>部門</dt><dd>${esc(r.department||"尚未分類")}</dd><dt>備註名稱</dt><dd>${esc(r.alias||"尚未設定")}</dd><dt>最近互動</dt><dd>${esc(when(r.last_seen))}</dd>${weatherModule()?`<dt>天氣通知</dt><dd>${badge(r.weather_subscribed?"已訂閱":"未訂閱",r.weather_subscribed?"good":"")}</dd>`:""}</dl><details><summary>聊天室識別資料</summary><p class="contact-id">${esc(r.recipient_id)}</p></details>${manager()?`<div class="detail-actions">${button("編輯收件者","edit-contact","primary",`data-id="${esc(r.recipient_id)}"`)}</div>`:""}</div></aside>`;
}

function schedulePage(){
  const scheduled=state.jobs.filter(j=>j.status==="scheduled").sort((a,b)=>String(a.scheduled_at).localeCompare(String(b.scheduled_at)));
  const issues=state.jobs.filter(j=>["missed","interrupted"].includes(j.status)||j.deliveries.some(d=>["unknown","failed"].includes(d.status)));
  const rows=workspaceUI.scheduleFilter==="scheduled"?scheduled:workspaceUI.scheduleFilter==="issues"?issues:state.jobs.filter(j=>j.scheduled_at);
  return heading("排程管理","安排單次傳送時間，查看預約與執行結果。",canSend()?button(icon("plus")+"建立預約","start-send","primary"):"")+
  `<div class="schedule-summary">${stat("待執行預約",scheduled.length,"筆","到期前仍可取消","clock")}${stat("下一次執行",scheduled[0]?esc(scheduleLabel(scheduled[0].scheduled_at)):"—","","台北時間 UTC+08:00","send")}${stat("需要處理",issues.length,"筆","已載入紀錄中的異常工作","shield")}</div><section class="panel schedule-list"><div class="toolbar segmented">${[["scheduled","單次預約"],["recent","已載入預約紀錄"],["issues","需要處理"]].map(([id,t])=>`<button data-action="schedule-filter" data-id="${id}" aria-pressed="${workspaceUI.scheduleFilter===id}" class="${workspaceUI.scheduleFilter===id?"active":""}">${t}</button>`).join("")}</div>${rows.length?historyList(rows):empty("目前沒有符合的預約","建立發送時選擇「指定日期與時間」，即可在這裡查看及取消。")}</section><p class="subtitle section-space">電腦與服務需要持續執行。超過預約時間 10 分鐘的工作標記逾期，避免恢復連線後發出過時通知。</p>`;
}

function workspaceAction(action,id){
  if(action==="report-layout"){workspaceUI.reportLayout=id==="grid"?"grid":"list";render();return true;}
  if(action==="report-detail"){workspaceUI.reportDetail=id;render();document.getElementById("report-detail")?.focus({preventScroll:true});if(innerWidth<1200)document.getElementById("report-detail")?.scrollIntoView({block:"start"});return true;}
  if(action==="close-report-detail"){const previous=workspaceUI.reportDetail;workspaceUI.reportDetail="";render();document.querySelector(`[data-action="report-detail"][data-id="${CSS.escape(previous)}"]`)?.focus();return true;}
  if(action==="contact-detail"){workspaceUI.contactDetail=id;render();document.getElementById("contact-detail")?.focus({preventScroll:true});if(innerWidth<1200)document.getElementById("contact-detail")?.scrollIntoView({block:"start"});return true;}
  if(action==="close-contact-detail"){const previous=workspaceUI.contactDetail;workspaceUI.contactDetail="";render();document.querySelector(`[data-action="contact-detail"][data-id="${CSS.escape(previous)}"]`)?.focus();return true;}
  if(action==="schedule-filter"){workspaceUI.scheduleFilter=id;render();return true;}
  return false;
}

function commandEntries(query){
  const q=query.trim().toLowerCase();
  const allowedViews=["overview","reports",...(admin()?["contacts","schedule","history"]:[]),...(canSend()?["send"]:[]),...(weatherModule()?["subscriptions"]:[]),...(manager()?["settings"]:[]),...(superAdmin()?["organizations"]:[])];
  const entries=allowedViews.map(id=>({kind:"page",id,title:titles[id],detail:"前往頁面",symbol:"grid"}));
  if(q){
    entries.push(...state.reports.map(r=>({kind:"report",id:r.report_id,title:r.title,detail:scope(r),symbol:"file"})));
    if(admin())entries.push(...state.contacts.map(r=>({kind:"contact",id:r.recipient_id,title:label(r),detail:orgName(r.company)+" · "+(r.kind==="user"?"個人":"群組"),symbol:"users"})));
  }
  return entries.filter(r=>`${r.title} ${r.detail}`.toLowerCase().includes(q)).slice(0,30);
}
function renderCommands(){
  const rows=commandEntries(document.getElementById("command-search").value);
  document.getElementById("command-results").innerHTML=rows.map(r=>`<button class="command-result" data-command-kind="${r.kind}" data-command-id="${esc(r.id)}">${icon(r.symbol)}<span>${esc(r.title)}<small>${esc(r.detail)}</small></span>${icon("arrow")}</button>`).join("")||empty("找不到符合項目","搜尋目前可存取的頁面、報告與收件者。");
  document.getElementById("command-count").textContent=`${rows.length} 個結果；只搜尋目前已載入且有權限的資料。`;
}
function openCommand(){
  if(!state.loaded||state.busy||document.getElementById("modal").open)return;
  const dialog=document.getElementById("command-dialog");
  document.getElementById("command-search").value="";renderCommands();dialog.showModal();document.getElementById("command-search").focus();
}
document.addEventListener("input",e=>{
  if(e.target.id==="command-search")renderCommands();
  if(e.target.id==="report-search"){
    workspaceUI.reportQuery=e.target.value;const cursor=e.target.selectionStart;
    render();const input=document.getElementById("report-search");input.focus({preventScroll:true});try{input.setSelectionRange(cursor,cursor);}catch(_){}
  }
});
document.addEventListener("click",e=>{
  if(e.target.closest("#command-open"))openCommand();
  if(e.target.closest("#command-close"))document.getElementById("command-dialog").close();
  const result=e.target.closest("[data-command-kind]");if(!result)return;
  document.getElementById("command-dialog").close();
  if(result.dataset.commandKind==="page")navigate(result.dataset.commandId);
  if(result.dataset.commandKind==="report"){state.reportFilter="all";workspaceUI.reportQuery="";workspaceUI.reportDetail=result.dataset.commandId;navigate("reports");document.getElementById("report-detail")?.focus();}
  if(result.dataset.commandKind==="contact"){
    workspaceUI.contactDetail=result.dataset.commandId;navigate("contacts");
    const index=filteredContacts().findIndex(r=>r.recipient_id===workspaceUI.contactDetail);
    state.page=Math.max(1,Math.floor(index/10)+1);render();document.getElementById("contact-detail")?.focus();
  }
});
document.addEventListener("keydown",e=>{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();openCommand();}
  if(!document.getElementById("command-dialog").open)return;
  if(e.key==="Escape"){e.preventDefault();document.getElementById("command-dialog").close();return;}
  const buttons=[...document.querySelectorAll(".command-result")];
  const index=buttons.indexOf(document.activeElement);
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();buttons[(index+(e.key==="ArrowDown"?1:-1)+buttons.length)%buttons.length]?.focus();}
  if(e.key==="Enter"&&document.activeElement.id==="command-search"){e.preventDefault();buttons[0]?.click();}
});

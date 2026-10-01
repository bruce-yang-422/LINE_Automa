"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const paths = {grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',layers:'<path d="m12 2 10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5"/>',file:'<path d="M14 2H5v20h14V7zM14 2v6h5M8 12h8M8 16h6"/>',send:'<path d="m22 2-7 20-4-9-9-4zM11 13 22 2"/>',users:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v2"/>',bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',settings:'<path d="M3 7h18M3 17h18"/><rect x="6" y="4" width="4" height="6" rx="1"/><rect x="14" y="14" width="4" height="6" rx="1"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',refresh:'<path d="M20 7a9 9 0 1 0 1 8M20 2v6h-6"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',plus:'<path d="M12 4v16M4 12h16"/>',image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',check:'<path d="m5 12 4 4L19 6"/>',copy:'<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',shield:'<path d="m12 2 8 3v6c0 6-8 11-8 11S4 17 4 11V5zM8 12l3 3 5-6"/>',folder:'<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',message:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.file}</svg>`;
document.querySelectorAll("[data-icon]").forEach(el => {el.innerHTML=icon(el.dataset.icon);});
const remote = location.hostname !== "127.0.0.1";
let authCsrf="";
const token = remote ? "" : location.hash.slice(1) || sessionStorage.getItem("lineAdminToken") || "";
if(location.hash){if(!remote)sessionStorage.setItem("lineAdminToken",token);history.replaceState(null,"",location.pathname+location.search);}
$("logout").hidden=!remote;
const state={session:null,view:new URLSearchParams(location.search).get("view")||"overview",reports:[],contacts:[],tags:[],jobs:[],cases:[],caseFilter:"all",casePriority:"all",caseQuery:"",savedFilters:[],chatNotes:new Map(),settings:{users:[]},events:[],previews:new Map(),selected:new Set(),report:null,step:1,audience:"selected",search:"",kind:"all",company:"",department:"",tagFilter:"",page:1,reportFilter:"all",historyFilter:"all",subFilter:"all",busy:false,loaded:false,authLost:false};
const titles={overview:"工作總覽","oa-list":"OA 一覽",chat:"聊天對話",reports:"報告中心",send:"建立發送",cases:"案件管理",contacts:"聯絡對象",subscriptions:"天氣訂閱",history:"發送紀錄",schedule:"排程管理",personnel:"人員與權限","org-settings":"組織設定",settings:"平台設定",organizations:"組織管理",channels:"LINE OA 管理"};
const admin=()=>["administrator","company_admin","sender","assistant"].includes(state.session?.role);
const manager=()=>["administrator","company_admin"].includes(state.session?.role);
const canSend=()=>["company_admin","sender"].includes(state.session?.role)&&Boolean(state.session?.modules?.messaging);
const superAdmin=()=>state.session?.role==="administrator";
const roleName=role=>({administrator:"平台管理員",company_admin:"組織管理員",sender:"營運人員",assistant:"協助人員"}[role]||role);
const weatherModule=()=>superAdmin()&&state.reports.some(r=>r.report_id==="weather");
let viewAs="",viewKey="",viewOptions=[],principalSession=null,organization="",previewOrganization="",organizationKey="";
const orgName=id=>(state.organizations||[]).find(o=>o.org_id===id)?.name||id||"未指定組織";
const orgKinds={company:"公司",unit:"單位",association:"社團",club:"俱樂部",family:"家庭",personal:"個人工作室",other:"其他"};
const label=r=>r.alias||r.custom_name||r.display_name||(r.kind==="user"?"未命名個人":"未命名群組");
const caseStatusNames={pending:"待處理",processing:"處理中",waiting:"等待中",ready_to_close:"待結案",closed:"已結案"};
const caseStatusTones={pending:"warn",processing:"primary",waiting:"secondary",ready_to_close:"info",closed:"good"};
const casePriorityNames={low:"低",normal:"一般",high:"高",urgent:"緊急"};
const casePriorityTones={low:"",normal:"good",high:"warn",urgent:"bad"};
const waitingPartyNames={internal:"內部團隊",case_subject:"案件主體（聯絡對象）",third_party:"第三方廠商／單位"};
const APPLE_TAG_COLORS=[
  {name:"經典藍",hex:"#007AFF"},
  {name:"青蔥綠",hex:"#34C759"},
  {name:"活力橘",hex:"#FF9500"},
  {name:"優雅紫",hex:"#AF52DE"},
  {name:"番茄紅",hex:"#FF3B30"},
  {name:"石板灰",hex:"#8E8E93"},
  {name:"薄荷青",hex:"#30B0C7"},
  {name:"星空靛",hex:"#5856D6"},
  {name:"玫瑰粉",hex:"#FF2D55"},
  {name:"琥珀黃",hex:"#FFCC00"}
];
const contactTypeNames={organization:"組織／團體",person_business:"公務對象個人",person_private:"一般個人"};
const contactTypeBadge=type=>type?badge(contactTypeNames[type]||type,"good"):badge("未分類");
const tagBadge=tag=>{const c=tag.color||'#007AFF';return `<span class="tag-badge" data-color="${esc(c)}"><span class="tag-dot" data-color="${esc(c)}"></span>${esc(tag.name)}</span>`;};
const when=value=>value?new Date(value).toLocaleString("zh-TW",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}):"尚未產生";
const badge=(text,tone="")=>`<span class="badge ${tone}">${esc(text)}</span>`;
const button=(text,action,cls="",attrs="")=>`<button class="btn ${cls}" data-action="${action}" ${attrs}>${text}</button>`;
const empty=(title,text)=>`<div class="empty">${icon("file")}<h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
const field=(text,name,value="",attrs="")=>`<label class="field">${esc(text)}<input name="${name}" value="${esc(value)}" ${attrs}></label>`;
const options=(items,value)=>items.map(([v,t])=>`<option value="${esc(v)}" ${v===value?"selected":""}>${esc(t)}</option>`).join("");
const selectField=(text,name,items,value)=>`<label class="field">${esc(text)}<select name="${name}">${options(items,value)}</select></label>`;
const person=r=>{
  const primary=label(r);
  const hasCustom=Boolean(r.alias||r.custom_name);
  const showLineName=hasCustom&&r.display_name&&r.display_name!==primary;
  const truncatedId=r.recipient_id?(r.recipient_id.length>12?r.recipient_id.slice(0,4)+'...'+r.recipient_id.slice(-4):r.recipient_id):'';
  const tags=r.tags||[];
  return `<div class="person"><span class="avatar ${r.kind!=="user"?"group":""}">${esc(primary.slice(0,1))}</span><div><div class="person-title"><strong>${esc(primary)}</strong>${showLineName?`<span class="line-name muted" style="font-size:12px;margin-left:6px;">（LINE: ${esc(r.display_name)}）</span>`:''}</div><div class="person-sub"><small class="muted">${r.kind==="user"?"個人聊天室":"群組聊天室"}${!r.active?" · 已停用":""}${truncatedId?` · <span class="line-id-chip">${esc(truncatedId)}</span>`:""}</small></div>${tags.length?`<div class="contact-tags">${tags.map(t=>tagBadge(t)).join("")}</div>`:""}</div></div>`;
};
const scope=r=>r.category==="composition"?(r.company?orgName(r.company):"平台個人素材"):r.scope==="module"?"天氣模組（依帳號／組織授權）":r.category==="text"?"自訂文字訊息":r.scope==="all"?"所有登入使用者":r.scope==="personal"?`${orgName(r.company)} · 個人專屬`:r.scope==="department"?`${orgName(r.company)} / ${r.department}`:`${orgName(r.company)} · 全組織`;
const reportBadge=r=>r.status!=="ready"?badge(r.status==="missing"?"等待報告":"無法使用","bad"):r.stale?badge("非今日更新","warn"):badge(admin()?"可發送":"可查看","good");
function notice(message,error=false){$("notice").textContent=message;$("notice").className="notice"+(error?" error":"");$("notice").hidden=!message;}
async function api(path,payload,original=false,root=false){
  const headers={"Content-Type":"application/json"};if(!remote)headers.Authorization=`Bearer ${token}`;
  if(payload!==undefined&&authCsrf)headers['X-CSRF-Token']=authCsrf;
  if(lineUI.ready&&lineUI.channel&&!root)headers['X-Line-Channel']=lineUI.channel;
  if(organization&&!root)headers['X-Workspace-Organization']=encodeURIComponent(organization);
  if(viewAs&&!original&&!root){headers['X-Workspace-View-As']=viewAs;if(previewOrganization)headers['X-Workspace-Preview-Organization']=encodeURIComponent(previewOrganization);}
  let response;
  try{response=await fetch(path,{method:payload===undefined?"GET":"POST",headers,credentials:"same-origin",redirect:"error",cache:"no-store",body:payload===undefined?undefined:JSON.stringify(payload)});}
  catch(_){throw new Error("連線中斷或登入已逾時。請重新整理登入；發送中的工作請先查紀錄，避免重複發送。");}
  if(!response.headers.get("Content-Type")?.includes("application/json")){state.authLost=true;throw new Error("登入已逾時，請重新整理並登入。");}
  const result=await response.json();
  if(result.auth)authCsrf=result.auth.csrf||"";
  if(response.status===401&&result.login_url==='/login'){location.replace('/login');throw new Error('登入已逾時，請重新登入。');}
  if(!response.ok){const error=new Error(result.error||"操作未完成。");error.status=response.status;if(response.status===401)state.authLost=true;throw error;}
  return result;
}
async function load(){
  lineUI.ready=false;
  const rootSession=await api("/api/session",undefined,true,true);
  $("logout").hidden=!remote&&rootSession.auth?.method!=="password";
  organizationKey="lineWorkspaceOrganization:"+rootSession.identity;
  let remembered="";try{remembered=localStorage.getItem(organizationKey)||"";}catch(_){}
  const memberOptions=rootSession.memberships||[];
  organization=rootSession.role==="administrator"?"":(memberOptions.some(m=>m.org_id===remembered)?remembered:(rootSession.user.company||""));
  principalSession=organization?await api("/api/session",undefined,true):rootSession;
  $("organization-select").hidden=rootSession.role==="administrator"||!memberOptions.length;
  $("organization-select").innerHTML=options(memberOptions.map(m=>[m.org_id,m.name+" · "+roleName(m.role)]),organization);
  viewKey="lineWorkspaceView:"+principalSession.identity+":"+organization;
  viewOptions=["administrator","company_admin"].includes(principalSession.role)?(await api("/api/view-options",undefined,true)).users:[];
  let saved="";try{saved=localStorage.getItem(viewKey)||"";}catch(_){}
  const chosen=viewOptions.find(user=>user.email+"|"+user.company===saved);
  viewAs=chosen?.email||"";previewOrganization=chosen?.company||"";
  if(saved&&!viewAs){try{localStorage.removeItem(viewKey);}catch(_){}notice("已返回原帳號：先前預覽的成員資格已失效。",true);}
  state.session=viewAs?await api("/api/session"):principalSession;
  const orgData=await api("/api/organizations");state.organizations=orgData.organizations;state.memberships=orgData.memberships;
  await loadChannels();
  $("switch-view").hidden=!["administrator","company_admin"].includes(principalSession.role);
  $("view-banner").hidden=!state.session.preview;
  $("view-description").textContent=state.session.preview?`角色視角：${roleName(state.session.role)} · ${state.session.user.display_name||viewAs}（${viewAs} · ${orgName(state.session.user.company)}） · 實際登入：${principalSession.identity}`:"";
  $("account-name").textContent=state.session.user?.display_name||state.session.identity;
  $("account-role").textContent=(state.session.preview?"預覽 · ":"")+roleName(state.session.role)+(state.session.user?.company?" · "+orgName(state.session.user.company):"");
  $("avatar").textContent=($("account-name").textContent||"L").slice(0,1).toUpperCase();
  document.querySelectorAll("[data-admin]").forEach(el=>{el.hidden=!admin();});document.querySelectorAll("[data-platform]").forEach(el=>{el.hidden=!superAdmin();});
  const reportResult=lineDataReady()?await api("/api/reports"):{reports:[]};state.reports=reportResult.reports;
  if(admin()&&lineDataReady()){
    const results=await Promise.all([api("/api/contacts"),api("/api/jobs"),(manager()?api("/api/settings"):Promise.resolve({users:[]})),api("/api/activity"),api("/api/cases"),api("/api/saved-filters")]);
    state.contacts=results[0].contacts;state.tags=results[0].tags||[];state.jobs=results[1].jobs;state.settings=results[2];state.events=results[3].events;state.cases=results[4].cases||[];state.savedFilters=results[5].saved_filters||[];
    state.selected=new Set([...state.selected].filter(id=>state.contacts.some(r=>r.recipient_id===id&&r.active)));
    if(typeof loadChatRooms==="function")await loadChatRooms();
  }else{state.contacts=[];state.tags=[];state.jobs=[];state.cases=[];state.savedFilters=[];state.chatNotes.clear();state.events=[];state.settings=manager()?await api("/api/settings"):{users:[]};state.selected.clear();}
  document.querySelector('nav [data-view="subscriptions"]').hidden=!weatherModule();
  document.querySelector('nav [data-view="send"]').hidden=!admin()||!state.session.modules.messaging;
  document.querySelector('nav [data-view="settings"]').hidden=!manager();
  document.querySelector(".sidebar-bottom .nav-label").hidden=!manager();
  if(state.view==="settings"&&!manager())state.view="overview";
  if(state.view==="organizations"&&!superAdmin())state.view="reports";
  if(lineUI.registry&&!lineDataReady()&&!["settings","organizations","channels"].includes(state.view))state.view="channels";
  workspaceHeader();
  state.loaded=true;state.authLost=false;$("connection").innerHTML='<span class="status-dot"></span>已連線';
  $("sync-time").textContent="最後更新 "+new Date().toLocaleTimeString("zh-TW",{hour12:false});
  $("nav-report-count").textContent=state.reports.length;
  const activeCases=state.cases.filter(c=>c.status!=="closed").length;if($("nav-case-count"))$("nav-case-count").textContent=activeCases||"0";
  if((!admin()&&!['overview','reports'].includes(state.view))||(state.view==="subscriptions"&&!weatherModule()))state.view="reports";
}
function heading(title,subtitle,actions="",eyebrow="WORKSPACE"){return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="subtitle">${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`;}
function tile(r){if(r.category==="composition")return composerPreview(r.draft);if(r.category==="text")return `<div class="message-preview">${esc(r.message_text)}</div>`;const saved=state.previews.get(r.report_id);return `<div class="preview-tile">${saved?.version===r.version&&saved.preview?`<img src="${saved.preview}" alt="${esc(r.title)} 預覽">`:`<div class="preview-empty">${icon(r.category==="weather"?"image":"file")}<span>${r.status==="ready"?"載入預覽…":esc(r.reason)}</span></div>`}</div>`;}
async function hydratePreviews(){
  const visible=state.view==="overview"?state.reports.slice(0,1):state.view==="reports"||(state.view==="send"&&state.step===1)?state.reports:[];
  for(const report of visible.filter(r=>r.status==="ready")){
    if(state.previews.get(report.report_id)?.version===report.version)continue;
    try{const result=await api('/api/reports/'+report.report_id);state.previews.set(report.report_id,result);
      document.querySelectorAll('[data-preview]').forEach(el=>{if(el.dataset.preview===report.report_id)el.innerHTML=tile(result);});
    }catch(_){document.querySelectorAll('[data-preview]').forEach(el=>{if(el.dataset.preview===report.report_id)el.innerHTML=empty("預覽暫時無法載入","按重新整理再次讀取。");});}
  }
}
function stat(title,value,unit,note,symbol){return `<div class="stat"><div class="stat-top">${title}${icon(symbol)}</div><div class="stat-value">${value}<span>${unit}</span></div><p class="stat-note">${note}</p></div>`;}
function quick(title,description,view,symbol){return `<button class="quick" data-view="${view}"><span class="quick-icon">${icon(symbol)}</span><span><strong>${title}</strong><small>${description}</small></span>${icon("arrow")}</button>`;}
function renderOnboardingCard(){
  if(state.session?.role !== "company_admin") return "";
  const orgId = state.session?.user?.company || "";
  let dismissed = false;
  try{ dismissed = Boolean(localStorage.getItem("lineOnboardingDismissed_" + orgId)); }catch(_){}
  if(dismissed) return "";
  
  const hasConnectedOA = (state.channels||[]).some(c => c.org_id === orgId && c.active);
  const hasTemplate = true;
  const hasColleagues = (state.memberships||[]).filter(m => m.org_id === orgId && m.active).length > 1;
  
  if(hasConnectedOA && hasTemplate && hasColleagues) return "";
  
  return `<section class="panel onboarding-panel" style="background:linear-gradient(135deg, #f0fdf4, #e6f4ea);border:1px solid #86efac;border-radius:16px;padding:16px 20px;margin-bottom:20px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 style="margin:0;font-size:15px;font-weight:700;color:#166534;display:flex;align-items:center;gap:6px;">🚀 開始使用</h3>
      <button type="button" class="btn text small" data-action="dismiss-onboarding" style="color:#166534;padding:2px 8px;">略過</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;">
      <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid ${hasConnectedOA?'#86efac':'#e2e8f0'};">
        <span style="font-size:16px;color:${hasConnectedOA?'#16a34a':'#94a3b8'};">${hasConnectedOA?'☑':'☐'}</span>
        <div><strong style="font-size:13px;display:block;">1. 確認 LINE OA 連線</strong><small style="color:#64748b;font-size:11px;">${hasConnectedOA?'已連結 OA':'請至 LINE OA 管理完成連線'}</small></div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid ${hasTemplate?'#86efac':'#e2e8f0'};">
        <span style="font-size:16px;color:${hasTemplate?'#16a34a':'#94a3b8'};">${hasTemplate?'☑':'☐'}</span>
        <div><strong style="font-size:13px;display:block;">2. 選擇範本包</strong><small style="color:#64748b;font-size:11px;">已預設啟用通用範本包</small></div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid ${hasColleagues?'#86efac':'#e2e8f0'};">
        <span style="font-size:16px;color:${hasColleagues?'#16a34a':'#94a3b8'};">${hasColleagues?'☑':'☐'}</span>
        <div><strong style="font-size:13px;display:block;">3. 新增同事</strong><small style="color:#64748b;font-size:11px;">${hasColleagues?'已建立同事帳號':'至人員與權限新增營運/協助人員'}</small></div>
      </div>
    </div>
  </section>`;
}

function overview(){
  const ready=state.reports.filter(r=>r.status==="ready").length, active=state.contacts.filter(r=>r.active).length, subscribed=state.contacts.filter(r=>r.active&&r.weather_subscribed).length;
  const pending=state.jobs.filter(j=>["scheduled","queued","running"].includes(j.status)).length;
  const date=new Date().toLocaleDateString("zh-TW",{month:"long",day:"numeric",weekday:"long"});
  const r=state.reports[0];
  return heading(admin()?"今天的工作，一目了然":"你的報告，都在這裡",`${esc(date)}　·　${admin()?"檢查報告、安排收件對象，掌握每次發送結果。":"依照你的公司、部門與個人權限，查看最新內容。"}`,canSend()?button(icon("plus")+"建立發送","start-send","primary"):button("瀏覽報告 "+icon("arrow"),"go-reports","primary"),"YOUR DAILY WORKSPACE")+
    renderOnboardingCard()+
    `<div class="stats">${stat("可用報告",ready,"份",`已登記 ${state.reports.length} 份報告`,"file")}${admin()?stat("有效聯絡對象",active,"個",`${state.contacts.filter(r=>r.active&&r.kind!=="user").length} 個群組聊天室`,"users")+(weatherModule()?stat("天氣訂閱",subscribed,"個","發送時檢查最新訂閱狀態","bell"):stat("所屬組織",esc(state.session.user?.company||"—"),"","資料依公司隔離","shield"))+stat("進行中的發送",pending,"筆","結果不明的請求不自動重送","send"):stat("所屬部門",esc(state.session.user?.department||"未指定"),"","只顯示獲授權內容","shield")}</div>
    <div class="dashboard-grid"><div class="stack"><section class="panel"><div class="panel-head"><div><h2>報告焦點</h2><p>先確認內容，再開始下一步</p></div><button class="btn text small" data-view="reports">所有報告 ${icon("arrow")}</button></div>${r?`<div class="feature"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><div>${reportBadge(r)}<h3>${esc(r.title)}</h3><p>最後更新　${when(r.modified_at)}</p><p>${esc(scope(r))}</p>${r.stale?'<p>此報告不是今日更新，發送前請確認。</p>':""}${button(canSend()?"預覽並建立發送 "+icon("arrow"):"開啟報告 "+icon("arrow"),canSend()?"choose-report":"preview","dark",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`)}</div></div>`:empty("還沒有可用報告","管理員設定報告來源與權限後，就會顯示在這裡。")}</section>${admin()?`<section class="panel"><div class="panel-head"><h2>最近發送</h2><button class="btn text small" data-view="history">查看全部 ${icon("arrow")}</button></div>${historyList(state.jobs.slice(0,3))}</section>`:""}</div><div class="stack"><section class="panel"><div class="panel-head"><h2>快速前往</h2></div><div class="quick-list">${admin()?quick("聊天對話","查看與回覆 LINE 即時訊息","chat","message"):""}${quick("報告中心","預覽獲授權的模組報告","reports","file")}${admin()?quick("聯絡對象","整理公司、部門與群組","contacts","users")+(weatherModule()?quick("天氣訂閱","管理持續接收通知的對象","subscriptions","bell"):""):""}</div></section><aside class="insight"><h3>${icon("shield")}${admin()?"分對對象，送對報告":"你的資料範圍"}</h3><p>${admin()?"組織報表依公司、部門或個人範圍選擇發送對象。聯絡對象只需在 LINE 收訊，不需後台帳號；需要操作後台的發送人員才須登入授權。":"此處只列出你獲授權的報告。若缺少需要的內容，請聯絡管理員確認公司及部門設定。"}</p></aside></div></div>`;
}
function reportsPage(wizard=false){
  if(!wizard)return workspaceReports();
  const rows=state.reports.filter(r=>state.reportFilter==="all"||r.category===state.reportFilter);
  return (wizard?"":heading("報告中心","預覽最新內容，依公司、部門與個人分配報告。",superAdmin()?(state.settings.weather_report_removed?button("恢復天氣報告","restore-weather",""):"")+button(icon("plus")+"新增報告來源","new-report","primary"):"","REPORT LIBRARY"))+
    `<div class="heading-actions section-space segmented">${[["all","所有報告"],...(state.reports.some(r=>r.category==="weather")?[["weather","天氣報告"]]:[]),["company","組織報表"],["other","其他報告"]].map(([id,text])=>`<button data-action="report-filter" data-id="${id}" class="${state.reportFilter===id?"active":""}">${text}</button>`).join("")}</div><div class="report-grid section-space">${rows.map(r=>`<article class="panel report-card"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><div class="report-card-body">${reportBadge(r)}<h3>${esc(r.title)}</h3><div class="report-meta"><span>${esc(scope(r))}</span><span>${icon("clock")} ${when(r.modified_at)}${r.size?` · ${Math.ceil(r.size/1024)} KB`:""}</span></div><div class="report-card-bottom">${button("預覽","preview","",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`)}${canSend()?button(wizard?"選擇這份報告":"建立發送","choose-report","primary",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`):""}</div>${superAdmin()?`<div class="report-card-bottom">${r.report_id!=="weather"?button("設定來源","edit-report","text small",`data-id="${esc(r.report_id)}"`):""}${button("移除報告","remove-report","text small",`data-id="${esc(r.report_id)}"`)}</div>`:""}</div></article>`).join("")}</div>${rows.length?"":empty("這裡還沒有報告",admin()?"新增來源後，外部程式產生的 PNG 就會顯示在報告中心。":"管理員授權報告後，你就能在這裡查看。")}`;
}
function eligible(r){const source=state.report;if(source?.category==="composition")return !source.company||r.company===source.company;if(!source||source.category==="text"||source.report_id==="weather")return true;if(r.company!==source.company)return false;if(source.scope==="department")return r.department===source.department;if(source.scope==="personal")return source.owner_recipient_id?r.recipient_id===source.owner_recipient_id:(state.memberships||[]).some(m=>m.active&&m.org_id===source.company&&m.email===source.owner_email&&m.recipient_id===r.recipient_id)||state.settings.users.some(u=>u.active&&u.company===source.company&&u.email===source.owner_email&&u.recipient_id===r.recipient_id);return true;}
function filteredContacts(){return state.contacts.filter(r=>{const q=state.search.toLowerCase();const tagMatch=!state.tagFilter||((r.tags||[]).some(t=>String(t.id)===String(state.tagFilter)||t.name===state.tagFilter));const searchMatch=!q||`${label(r)} ${r.display_name||""} ${r.recipient_id||""} ${r.company||""} ${r.department||""} ${r.notes||""} ${(r.tags||[]).map(t=>t.name).join(" ")}`.toLowerCase().includes(q);const kindMatch=state.kind==="all"||(state.kind==="group"?r.kind!=="user":r.kind===state.kind);const companyMatch=!state.company||r.company===state.company;const deptMatch=!state.department||r.department===state.department;const sendEligible=state.view!=="send"||(r.active&&eligible(r));const subMatch=state.view!=="subscriptions"||state.subFilter==="all"||Boolean(r.weather_subscribed)===(state.subFilter==="on");return tagMatch&&searchMatch&&kindMatch&&companyMatch&&deptMatch&&sendEligible&&subMatch;});}
function contactToolbar(){
  const companies=[...new Set(state.contacts.map(r=>r.company).filter(Boolean))],depts=[...new Set(state.contacts.filter(r=>!state.company||r.company===state.company).map(r=>r.department).filter(Boolean))];
  const tagOpts=[["","所有標籤"],...(state.tags||[]).map(t=>[t.id,t.name])];
  const filterOpts=[["","自訂篩選條件..."],...(state.savedFilters||[]).map(f=>[f.filter_id,f.name])];
  return `<div class="toolbar">
    <label class="search-field">${icon("search")}<input id="contact-search" value="${esc(state.search)}" placeholder="搜尋姓名、LINE 名稱、ID、備忘或標籤" aria-label="搜尋聯絡對象"></label>
    <select id="contact-kind" aria-label="聊天室類型">${options([["all","所有聊天室"],["user","個人"],["group","群組"]],state.kind)}</select>
    <select id="contact-tag-filter" aria-label="篩選標籤">${options(tagOpts,state.tagFilter)}</select>
    <select id="contact-company" aria-label="篩選公司">${options([["","所有組織"],...companies.map(c=>[c,orgName(c)])],state.company)}</select>
    <select id="contact-department" aria-label="篩選部門">${options([["","所有部門"],...depts.map(c=>[c,c])],state.department)}</select>
    ${state.savedFilters?.length?`<select id="apply-saved-filter" aria-label="套用自訂篩選">${options(filterOpts,"")}</select>`:""}
    ${manager()&&state.view==="contacts"?button("💾 儲存篩選","open-save-filter-modal","small")+button(icon("settings")+"標籤管理","manage-tags","small"):""}
  </div>`;
}
function contactList(){const rows=filteredContacts(),pages=Math.max(1,Math.ceil(rows.length/10));state.page=Math.min(state.page,pages);const visible=rows.slice((state.page-1)*10,state.page*10);const isSendAudience=state.view==="send"&&state.audience==="selected";const isContactsView=state.view==="contacts"&&manager();const showCheckboxes=isSendAudience||isContactsView;const selectedCount=state.selected.size;let bulkBar="";if(isContactsView&&selectedCount>0){bulkBar=`<div class="bulk-toolbar"><div><strong>已選取 ${selectedCount} 個聯絡對象</strong></div><div class="bulk-actions">${button("🏷️ 批次加標籤","bulk-add-tags","small")}${button("✂️ 批次移除標籤","bulk-remove-tags","small")}${weatherModule()?button("🔔 批次開啟訂閱","bulk-sub-on","small")+button("🔕 批次取消訂閱","bulk-sub-off","small"):""}${button("清除勾選","clear-selection","text small")}</div></div>`;}else if(isSendAudience){bulkBar=`<div class="toolbar">${button("勾選本頁","select-page","small")}${button("清除勾選","clear-selection","text small")}<small class="muted">共 ${rows.length} 個符合報告範圍的聊天室</small></div>`;}return `${bulkBar}<div class="table-scroll"><table class="contacts-table"><thead><tr><th class="select-cell">${showCheckboxes?`<input type="checkbox" id="select-all-visible" aria-label="全選本頁" ${visible.length&&visible.every(r=>state.selected.has(r.recipient_id))?"checked":""}>`:""}</th><th>聯絡對象</th><th>組織／部門</th>${weatherModule()?"<th>天氣訂閱</th>":""}<th>操作</th></tr></thead><tbody>${visible.map(r=>`<tr><td class="select-cell">${showCheckboxes?`<input type="checkbox" data-select="${esc(r.recipient_id)}" aria-label="選取 ${esc(label(r))}" ${state.selected.has(r.recipient_id)?"checked":""}>`:""}</td><td class="person-cell">${state.view==="contacts"?`<button class="contact-open" data-action="contact-detail" data-id="${esc(r.recipient_id)}" aria-label="查看 ${esc(label(r))} 詳情">${person(r)}</button>`:person(r)}</td><td class="meta-cell">${esc(r.company?orgName(r.company):"尚未分類")}<small class="muted">${r.department?" / "+esc(r.department):""}</small></td>${weatherModule()?`<td class="sub-cell">${badge(r.weather_subscribed?"已訂閱":"未訂閱",r.weather_subscribed?"good":"")}</td>`:""}<td class="action-cell">${manager()?button("管理","edit-contact","small",`data-id="${esc(r.recipient_id)}"`):badge("已授權")}</td></tr>`).join("")}</tbody></table></div>${!rows.length?empty("沒有符合的聯絡對象",state.view==="send"?"請確認聯絡對象的組織／部門分類符合報告範圍，並已與 Bot 互動。":"調整篩選條件，或請使用者向 Bot 傳送訊息以建立名單。"):""}<div class="pagination"><span>共 ${rows.length} 個聊天室</span><div>${button("上一頁","prev-page","small",state.page<=1?"disabled":"")}<span>${state.page} / ${pages}</span>${button("下一頁","next-page","small",state.page>=pages?"disabled":"")}</div></div>`;}
function contactsPage(subscriptions=false){return heading(subscriptions?"天氣訂閱":"聯絡對象",subscriptions?"訂閱決定持續接收通知的對象；每次發送仍由管理員確認。":"依公司與部門整理個人、群組，自訂名稱與筆記，讓報告送到正確的地方。",(manager()?button(icon("refresh")+"更新 LINE 名稱","profiles"):""),subscriptions?"SUBSCRIPTIONS":"CONTACT DIRECTORY")+(subscriptions?`<div class="insight"><h3>${icon("bell")}個人自行訂閱，群組由管理員設定</h3><p>私訊 Bot「訂閱天氣」「取消訂閱」「我的訂閱」即可管理個人訂閱。目前由管理員發送，可指定單次傳送時間，尚未啟用每日循環排程。</p></div><div class="segmented section-space">${[["all","全部"],["on","已訂閱"],["off","未訂閱"]].map(([id,t])=>`<button data-action="sub-filter" data-id="${id}" class="${state.subFilter===id?"active":""}">${t}</button>`).join("")}</div>`:"")+`<div class="library-split section-space ${!subscriptions&&workspaceUI.contactDetail?"has-detail":""}"><section class="panel">${contactToolbar()}<div id="contact-list">${contactList()}</div></section>${subscriptions?"":contactDetailPanel()}</div>`;}
function selectedRows(){return state.contacts.filter(r=>r.active&&eligible(r)&&(state.audience==="subscribers"?r.weather_subscribed:state.selected.has(r.recipient_id)));}
function selectionSummary(){const rows=selectedRows();return `<div class="panel selection-summary"><div class="panel-body">${tile(state.report)}<p class="eyebrow section-space">THIS DELIVERY</p><h3>${esc(state.report.title)}</h3><p class="subtitle">${esc(scope(state.report))}</p><div class="count-big">${rows.length}<small>個聊天室</small></div><div class="summary-list">${rows.map(r=>`<span>${esc(label(r))}</span>`).join("")||'<small class="muted">請從名單選擇發送對象</small>'}</div><p class="callout">每個聊天室會收到這次確認的內容。一次性勾選不會改變訂閱設定。</p></div></div>`;}
function sendPage(){const r=state.report;return heading("建立發送","依序確認報告、對象與內容，每次發送都有完整紀錄。","","NEW DELIVERY")+`<div class="steps">${["編輯內容","選擇對象","確認發送"].map((t,i)=>`${i?'<span class="step-line"></span>':""}<span class="step ${state.step===i+1?"active":""}"><b>${i+1}</b>${t}</span>`).join("")}</div>`+(state.step===1||!r?composerEditor()+`<section class="panel panel-body section-space"><h2>文字訊息</h2><p class="subtitle">輸入公告或提醒，下一步選擇發送對象與傳送時間。</p><textarea id="message-draft" maxlength="5000" rows="5" placeholder="輸入要傳送的文字">${esc(state.textDraft||"")}</textarea><div class="form-actions">${button("使用這段文字","choose-text","primary")}</div></section>`+reportsPage(true):state.step===2?`<div class="send-grid"><section class="panel"><div class="panel-head"><div><h2>這次要發給誰？</h2><p>僅列出符合報告組織／部門／個人範圍的有效聯絡對象</p></div></div>${r.report_id==="weather"?`<div class="toolbar segmented">${[["selected","手動選擇"],["subscribers","天氣訂閱名單"]].map(([id,t])=>`<button data-action="audience" data-id="${id}" class="${state.audience===id?"active":""}">${t}</button>`).join("")}</div>`:""}${state.audience==="selected"?contactToolbar()+`<div id="contact-list">${contactList()}</div>`:`<div class="panel-body"><p class="callout">目前有 ${selectedRows().length} 個有效天氣訂閱。發送時會再次檢查訂閱狀態，尚未送出的取消訂閱會自動排除。</p></div>`}<div class="selection-footer">${button("返回編輯","back-report")}${button("下一步：確認發送 "+icon("arrow"),"review","primary",`id="review-button" ${selectedRows().length?"":"disabled"}`)}</div></section><aside id="selection-summary">${selectionSummary()}</aside></div>`:confirmation());}
function confirmation(){const r=state.report,rows=selectedRows();return `<section class="panel"><div class="panel-head"><h2>確認這次的發送內容</h2>${reportBadge(r)}</div><div class="panel-body confirm-grid"><div>${["text","composition"].includes(r.category)?tile(r):`<img class="confirm-preview" src="${r.preview}" alt="${esc(r.title)} 完整預覽"><p class="subtitle">內容更新時間：${when(r.modified_at)}</p>`}</div><div><p class="eyebrow">DELIVERY SUMMARY</p><h2>${esc(r.title)}</h2><div class="detail-row"><span>發送方式</span><strong>${state.audience==="subscribers"?"天氣訂閱名單":"手動選擇"}</strong></div><div class="detail-row"><span>發送 OA</span><strong>${esc(selectedOA()?.name||"既有 OA")}</strong></div><div class="detail-row"><span>工作區</span><strong>${esc(selectedWorkspace()?.name||"目前工作區")}</strong></div><div class="detail-row"><span>收件聊天室</span><strong>${rows.length} 個（${rows.filter(x=>x.kind==="user").length} 個人／${rows.filter(x=>x.kind!=="user").length} 群組）</strong></div><div class="detail-row"><span>操作人</span><strong>${esc(state.session.identity)}</strong></div><div class="summary-list">${rows.map(x=>`<span>${esc(label(x))}</span>`).join("")}</div><p class="callout">送出前會再次檢查報告版本與收件範圍。LINE 已接受代表 API 受理，不代表對方已讀。</p>${scheduleFields()}${r.stale?'<p class="callout warn">這份報告不是今天更新。請確認日期與內容適用於這次發送。</p><label class="check-label"><input id="allow-stale" type="checkbox">我已確認，可以發送這份較早的報告</label>':""}<div class="form-actions">${button("上一步","back-recipients")}${button(icon("send")+`確認發送給 ${rows.length} 個聊天室`,"submit-send","primary",`id="submit-send" ${state.busy||!rows.length?"disabled":""}`)}</div></div></div></section>`;}
const statusNames={scheduled:"已預約",missed:"預約逾期／未發送",queued:"排隊中",running:"發送中",finished:"工作完成",interrupted:"工作中斷",pending:"等待發送",sending:"正在發送",accepted:"LINE 已接受",failed:"發送失敗",unknown:"狀態不明",cancelled:"未發送／已取消"};
function jobTone(job){return job.deliveries.some(d=>["failed","unknown"].includes(d.status))?"bad":job.status==="finished"?"good":"warn";}
function historyList(jobs){return jobs.length?jobs.map(j=>`<details class="history-item" data-job="${esc(j.job_id)}"><summary><span class="history-title"><strong>${esc(j.report_title||"手動圖片發送")}</strong><small>${j.status==="scheduled"?"預約 "+esc(scheduleLabel(j.scheduled_at)):when(j.created_at)} · ${esc(j.actor||"舊版未記錄操作人")}</small></span>${badge(`${j.deliveries.filter(d=>d.status==="accepted").length} / ${j.deliveries.length} 已接受`,jobTone(j))}${badge(statusNames[j.status]||j.status)}</summary><div class="job-detail">${j.scheduled_at?`<p class="callout">預約時間：${scheduleLabel(j.scheduled_at)}（台北時間）</p>`:""}${j.message_text?`<div class="message-preview">${esc(j.message_text)}</div>`:""}${j.status==="scheduled"?button("取消預約","cancel-schedule","danger",`data-id="${esc(j.job_id)}"`):""}${j.error?`<p class="callout warn">${esc(j.error)}</p>`:""}${j.deliveries.map(d=>`<div class="delivery"><span>${esc(d.label)}</span>${badge(statusNames[d.status]||d.status,d.status==="accepted"?"good":["failed","unknown"].includes(d.status)?"bad":"")}${d.error?`<small>${esc(d.error)}</small>`:""}</div>`).join("")}<p class="callout">發送失敗或狀態不明時，請先確認聊天室與 LINE 設定，再決定是否建立新的發送工作。</p><small class="contact-id">工作 ${esc(j.job_id)}</small></div></details>`).join(""):empty("還沒有發送紀錄","完成第一次發送後，可以在這裡查看每個聊天室的結果。");}
function historyPage(){const rows=state.jobs.filter(j=>state.historyFilter==="all"||(state.historyFilter==="issues"?(j.status==="missed"||j.deliveries.some(d=>["unknown","failed"].includes(d.status))):['scheduled','queued','running'].includes(j.status)));return heading("發送紀錄","逐筆確認結果。API 已接受不代表已讀；異常工作不會自動重送。",button("建立發送","start-send","primary"),"DELIVERY HISTORY")+`<section class="panel"><div class="toolbar segmented">${[["all","預約與最近紀錄"],["issues","需要處理"],["active","進行中"]].map(([id,t])=>`<button data-action="history-filter" data-id="${id}" class="${state.historyFilter===id?"active":""}">${t}</button>`).join("")}</div><div id="history-list">${historyList(rows)}</div></section>`;}

function filteredCases(){
  return (state.cases||[]).filter(c=>{
    const q=(state.caseQuery||"").toLowerCase();
    const statusMatch=state.caseFilter==="all"||c.status===state.caseFilter;
    const priorityMatch=state.casePriority==="all"||c.priority===state.casePriority;
    const subject=state.contacts.find(x=>x.recipient_id===c.case_subject_id);
    const searchMatch=!q||`${c.case_no||""} ${c.title||""} ${c.description||""} ${c.case_subject_id||""} ${label(subject||{})}`.toLowerCase().includes(q);
    return statusMatch&&priorityMatch&&searchMatch;
  });
}

function caseCard(c){
  const subject=state.contacts.find(x=>x.recipient_id===c.case_subject_id);
  const subjectName=subject?label(subject):(c.case_subject_id||"未知對象");

  return `<article class="case-card ${c.is_locked?'locked':''}">
    <div class="case-card-head">
      <div class="case-card-main-title">
        <span class="case-no-badge">${esc(c.case_no)}</span>
        <h3 class="case-title">${esc(c.title)}</h3>
        ${c.is_locked?'<span title="防誤觸鎖定中">🔒</span>':''}
      </div>
      <div class="case-card-badges">
        ${c.category?`<span class="badge">${esc(c.category)}</span>`:""}
        ${c.priority?`<span class="badge ${casePriorityTones[c.priority]||""}">${casePriorityNames[c.priority]||c.priority}優先度</span>`:""}
        <span class="badge ${caseStatusTones[c.status]||""}">${caseStatusNames[c.status]||c.status}</span>
      </div>
    </div>
    ${c.description?`<p class="case-desc">${esc(c.description)}</p>`:""}
    <div class="case-card-meta">
      <span><strong>案件主體：</strong><button class="btn text small link-style" data-action="contact-detail-from-case" data-id="${esc(c.case_subject_id)}">${esc(subjectName)}</button></span>
      ${c.ref_no?`<span><strong>參考號：</strong>${esc(c.ref_no)}</span>`:""}
      ${c.due_date?`<span><strong>期限：</strong>${esc(c.due_date)}</span>`:""}
      <span><strong>建立：</strong>${when(c.created_at)}</span>
      <span><strong>更新：</strong>${when(c.updated_at)}</span>
    </div>
    ${c.status==="waiting"?`<div class="case-waiting-info"><p><strong>⏳ 等待對象：</strong>${waitingPartyNames[c.waiting_party]||c.waiting_party||"未指定"}（自 ${when(c.waiting_since)}）</p><p><strong>原因：</strong>${esc(c.waiting_reason||"無")}</p></div>`:""}
    ${c.status==="closed"?`<div class="case-closed-info"><p><strong>✅ 結案說明：</strong>${esc(c.resolution||"已結案")}（結案於 ${when(c.closed_at)}）</p></div>`:""}
    <div class="case-card-actions">
      ${c.status==="pending"?button("開始處理","case-to-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="processing"?button("進入等待","open-case-waiting-modal","small",`data-id="${esc(c.case_id)}"`)+button("進入待結案","case-to-ready","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="waiting"?button("恢復處理","case-resume-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="ready_to_close"?button("退回處理","case-back-processing","small",`data-id="${esc(c.case_id)}"`)+button("執行結案","open-case-close-modal","good primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="closed"?badge("已完成結案","good"):""}
      <button class="btn text small" data-action="toggle-case-lock" data-id="${esc(c.case_id)}">${c.is_locked?'🔓 解鎖':'🔒 鎖定'}</button>
      <button class="btn text small" data-action="create-continuation-case" data-id="${esc(c.case_id)}">+ 延續案件</button>
      ${button("完整歷程","open-case-detail","small",`data-id="${esc(c.case_id)}"`)}
    </div>
  </article>`;
}

function casesPage(){
  const rows=filteredCases();
  const pendingCount=state.cases.filter(c=>c.status==="pending").length;
  const processingCount=state.cases.filter(c=>c.status==="processing").length;
  const waitingCount=state.cases.filter(c=>c.status==="waiting").length;
  const readyCount=state.cases.filter(c=>c.status==="ready_to_close").length;
  const closedCount=state.cases.filter(c=>c.status==="closed").length;

  const exportButtons = manager() ? `
    <div style="display:flex;gap:6px;">
      <button class="btn small" data-action="export-cases-csv">${icon("download")} 匯出 CSV</button>
      <button class="btn small" data-action="export-cases-xlsx">${icon("download")} 匯出 XLSX</button>
    </div>
  ` : '';

  return heading("案件管理","追蹤從對話與聯絡對象建立的案件，掌握各階段進度。",`<div style="display:flex;gap:8px;">${exportButtons}${button(icon("plus")+"建立案件","new-case-modal","primary")}</div>`,"CASE MANAGEMENT")+
    `<div class="stats">
      ${stat("待處理",pendingCount,"件","尚未開始處理的案件","clock")}
      ${stat("處理中",processingCount,"件","進行中需主動跟進","send")}
      ${stat("等待中",waitingCount,"件","等待內部、外部或對方回覆","bell")}
      ${stat("待結案",readyCount,"件","處理完畢等待結案確認","check")}
    </div>
    <section class="panel section-space">
      <div class="toolbar">
        <label class="search-field">${icon("search")}<input id="case-search" value="${esc(state.caseQuery)}" placeholder="搜尋案件編號、標題、描述、參考號或聯絡對象" aria-label="搜尋案件"></label>
        <select id="case-priority-filter" aria-label="優先度篩選">
          ${options([["all","所有優先度"],["urgent","緊急"],["high","高"],["normal","一般"],["low","低"]],state.casePriority)}
        </select>
      </div>
      <div class="toolbar segmented">
        ${[["all",`全部 (${state.cases.length})`],["pending",`待處理 (${pendingCount})`],["processing",`處理中 (${processingCount})`],["waiting",`等待中 (${waitingCount})`],["ready_to_close",`待結案 (${readyCount})`],["closed",`已結案 (${closedCount})`]].map(([id,t])=>`<button data-action="case-filter" data-id="${id}" class="${state.caseFilter===id?"active":""}">${t}</button>`).join("")}
      </div>
      <div class="cases-container section-space">
        ${rows.length?rows.map(c=>caseCard(c)).join(""):empty("沒有符合條件的案件",state.caseQuery?"請調整搜尋關鍵字或狀態篩選。":"可點選上方「建立案件」新增追蹤項目。")}
      </div>
    </section>`;
}

function createCaseModal(subject_id="", prefill={}){
  const contactOpts=[["","請選擇關聯的聯絡對象"],...state.contacts.filter(r=>r.active).map(r=>[r.recipient_id,label(r)+(r.kind==="user"?" (個人)":" (群組)")])];
  const title = prefill.title || "";
  const desc = prefill.description || "";
  const cat = prefill.category || "一般";
  const continuedFrom = prefill.continued_from_id || "";

  modal(continuedFrom ? "建立延續案件" : "建立新案件", `<form id="case-create-form">
    ${continuedFrom ? `<input type="hidden" name="continued_from_id" value="${esc(continuedFrom)}"><div class="callout" style="margin-bottom:12px;">🔗 此案件將作為延續案件關聯至前案歷程。</div>` : ''}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span class="muted" style="font-size:13px;">填寫案件需求或從範本包帶入</span>
      <button type="button" class="btn text small" data-action="open-template-picker" data-subject="${esc(subject_id)}">📋 從範本帶入</button>
    </div>
    <div class="form-grid">
      <div class="full">${field("案件標題","title",title,'required maxlength="100" placeholder="例如：詢問 10 月發票開立方式、報表格式問題"')}</div>
      ${selectField("案件主體（聯絡對象）","case_subject_id",contactOpts,subject_id)}
      ${field("案件類別","category",cat,'maxlength="50" placeholder="例如：一般、諮詢、維修、訂單"')}
      ${selectField("優先度","priority",[["normal","一般"],["low","低"],["high","高"],["urgent","緊急"]],prefill.priority||"normal")}
      ${field("參考編號（選填）","ref_no",prefill.ref_no||"",'maxlength="50" placeholder="例如：訂單號 #202610-A01、發票號"')}
      ${field("預計完成期限（選填）","due_date",prefill.due_date||"",'type="date"')}
      <div class="full"><label class="field">問題或需求描述（選填）<textarea name="description" rows="4" maxlength="2000" placeholder="詳細說明對方需求、對話重點、目前已知資訊...">${esc(desc)}</textarea></label></div>
    </div>
    <p class="callout">建立案件後初始狀態為「待處理」，自動編號格式為 {前綴}-{年月}-{4位流水號}。</p>
    <div class="form-actions"><button class="btn primary" type="submit">確認建立案件</button></div>
  </form>`);
}

function caseWaitingModal(case_id){
  const c=state.cases.find(x=>x.case_id===case_id);
  if(!c)return;
  modal(`案件進入等待：${esc(c.case_no)}`,`<form id="case-waiting-form" data-id="${esc(case_id)}">
    <div class="form-grid">
      ${selectField("等待對象（必選）","waiting_party",[["case_subject","案件主體（聯絡對象回覆）"],["internal","內部團隊（內部確認／協調）"],["third_party","第三方廠商／外部單位"]],"case_subject")}
      <div class="full">${field("等待原因說明（必填）","waiting_reason","",'required maxlength="500" placeholder="例如：已傳送確認信件，等待客戶回覆確認報價"')}</div>
    </div>
    <p class="callout">進入等待狀態會自動記錄等待起算時間與原因。待對方回覆後可隨時「恢復處理」。</p>
    <div class="form-actions"><button class="btn primary" type="submit">確認進入等待</button></div>
  </form>`);
}

function caseCloseModal(case_id){
  const c=state.cases.find(x=>x.case_id===case_id);
  if(!c)return;
  modal(`案件結案確認：${esc(c.case_no)}`,`<form id="case-close-form" data-id="${esc(case_id)}">
    <div class="form-grid">
      <div class="full"><label class="field">結案說明／處理結果（必填）<textarea name="resolution" rows="4" required maxlength="1000" placeholder="詳細記錄最終處理結果、客戶確認事項、完成日期等..."></textarea></label></div>
    </div>
    <p class="callout warn">案件結案為終態，結案後將不可再變更狀態。所有處理歷程將永久保存供日後查閱。</p>
    <div class="form-actions"><button class="btn primary good" type="submit">確認結案</button></div>
  </form>`);
}

async function caseDetailModal(case_id){
  modal("載入案件詳情…",'<div class="loading-panel"><span class="spinner"></span><p>讀取案件與歷史歷程…</p></div>');
  try{
    const res=await api(`/api/cases/${case_id}`);
    const c=res.case;
    const activities=res.activities||[];
    const subject=state.contacts.find(x=>x.recipient_id===c.case_subject_id);
    const subjectName=subject?label(subject):(c.case_subject_id||"未知對象");

    const timelineHtml=activities.length?activities.map(a=>{
      let desc="";
      if(a.action==="create_case")desc="建立案件";
      else if(a.action==="status_change")desc=`狀態變更：${caseStatusNames[a.details?.old_status]||a.details?.old_status} ➔ <strong>${caseStatusNames[a.details?.new_status]||a.details?.new_status}</strong>${a.details?.waiting_party?`（等待：${waitingPartyNames[a.details.waiting_party]||a.details.waiting_party}，原因：${esc(a.details.waiting_reason||"")}）`:""}${a.details?.resolution?`（結案說明：${esc(a.details.resolution)}）`:""}`;
      else if(a.action==="add_note")desc=`處理記事：${esc(a.details?.note||"")}`;
      else desc=esc(a.action);

      return `<div class="case-timeline-item">
        <span class="timeline-dot"></span>
        <div class="timeline-content">
          <div class="timeline-meta"><strong>${esc(a.actor||"管理員")}</strong> · ${when(a.created_at)}</div>
          <div class="timeline-body">${desc}</div>
        </div>
      </div>`;
    }).join(""):`<p class="muted">尚無活動紀錄</p>`;

    modal(`案件詳情：${esc(c.case_no)}`,`<div class="case-detail-view">
      <div class="case-detail-header">
        <div>
          <span class="case-no-badge">${esc(c.case_no)}</span>
          <h2>${esc(c.title)}</h2>
          ${c.is_locked?'<span title="防誤觸鎖定中">🔒 已鎖定</span>':''}
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
          ${c.category?`<span class="badge">${esc(c.category)}</span>`:""}
          ${badge(casePriorityNames[c.priority]||c.priority,casePriorityTones[c.priority]||"")}
          ${badge(caseStatusNames[c.status]||c.status,caseStatusTones[c.status]||"")}
        </div>
      </div>
      <dl class="case-info-dl">
        <dt>案件主體</dt><dd>${esc(subjectName)} <small class="muted">(${esc(c.case_subject_id)})</small></dd>
        ${c.ref_no?`<dt>參考編號</dt><dd>${esc(c.ref_no)}</dd>`:""}
        ${c.due_date?`<dt>期限</dt><dd>${esc(c.due_date)}</dd>`:""}
        <dt>建立時間</dt><dd>${when(c.created_at)}</dd>
        <dt>最後更新</dt><dd>${when(c.updated_at)}</dd>
        ${c.status==="waiting"?`<dt>等待對象</dt><dd>${waitingPartyNames[c.waiting_party]||c.waiting_party}（自 ${when(c.waiting_since)}）</dd><dt>等待原因</dt><dd>${esc(c.waiting_reason)}</dd>`:""}
        ${c.status==="closed"?`<dt>結案時間</dt><dd>${when(c.closed_at)}</dd><dt>結案說明</dt><dd>${esc(c.resolution)}</dd>`:""}
      </dl>
      ${c.description?`<div class="section-space"><h4>需求描述</h4><p class="case-desc-box">${esc(c.description)}</p></div>`:""}
      
      <div class="section-space">
        <h4>處理歷程與時間軸 (Timeline)</h4>
        <div class="case-timeline">${timelineHtml}</div>
      </div>

      ${c.status!=="closed" && !c.is_locked ? `<form id="case-add-note-form" data-id="${esc(c.case_id)}" class="section-space">
        <label class="field">新增處理紀錄 / 備忘<textarea name="note" rows="2" required maxlength="1000" placeholder="記錄最新溝通進度、待辦項目或內部確認事項..."></textarea></label>
        <div class="form-actions">${button("送出紀錄","","primary small",'type="submit"')}</div>
      </form>` : ''}
    </div>`);
  }catch(e){
    modal("載入失敗",`<p class="callout warn">${esc(e.message)}</p>`);
  }
}

async function loadChatNotes(recipient_id){
  try{
    const res=await api(`/api/chat-notes?recipient_id=${encodeURIComponent(recipient_id)}`);
    state.chatNotes.set(recipient_id,res.notes||[]);
    const container=$("chat-notes-list-container");
    if(container)container.innerHTML=renderChatNotesList(recipient_id);
  }catch(e){
    console.error("Failed to load chat notes:",e);
  }
}

function chatNoteModal(recipient_id,note_id="",prefill={}){
  const notes=state.chatNotes.get(recipient_id)||[];
  const existing=note_id?notes.find(n=>n.note_id===note_id):null;
  const title = prefill.title || existing?.title || "";
  const content = prefill.content || existing?.content || "";
  const note_type = prefill.note_type || existing?.note_type || "一般";
  const due_date = prefill.due_date || existing?.due_date || "";
  const tagsStr = prefill.tags || (existing?.tags ? existing.tags.join(", ") : "");
  const updated_at = existing?.updated_at || "";

  const typeOptions = [["一般","一般"], ["待辦","待辦"], ["約定事項","約定事項"], ["重要提醒","重要提醒"], ["交接","交接"]];

  modal(existing ? "編輯對話記事" : "新增對話記事", `<form id="chat-note-form" data-recipient="${esc(recipient_id)}" data-note-id="${esc(note_id)}">
    ${updated_at ? `<input type="hidden" name="expected_updated_at" value="${esc(updated_at)}">` : ''}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span class="muted" style="font-size:13px;">填寫對話重要記事或從範本包帶入</span>
      <button type="button" class="btn text small" data-action="open-note-template-picker" data-recipient="${esc(recipient_id)}">📋 從範本帶入</button>
    </div>
    <div class="form-grid">
      <div class="full">${field("記事標題（選填）", "title", title, 'maxlength="50" placeholder="例如：客戶詢問保固條件、確認發票開立"')}</div>
      ${selectField("記事類型", "note_type", typeOptions, note_type)}
      ${field("完成期限（選填）", "due_date", due_date, 'type="date"')}
      <div class="full">${field("記事標籤（以逗號分隔，最多 5 個）", "tags", tagsStr, 'maxlength="100" placeholder="例如：重要, 報修, 聯絡紀錄"')}</div>
      <div class="full"><label class="field">記事內容（1–1,000 字）<textarea name="content" rows="4" required minlength="1" maxlength="1000" placeholder="記錄該聊天室的重要交辦、對話摘要、待確認事項...">${esc(content)}</textarea></label></div>
    </div>
    <p class="callout">對話記事本獨立於聯絡對象筆記，專屬於此 OA 聊天室對話。支援置頂 (最多 5 筆)、鎖定防誤改與 30 天回收筒還原。</p>
    <div class="form-actions"><button class="btn primary" type="submit">${existing ? "儲存變更" : "新增記事"}</button></div>
  </form>`);
}

async function templatePickerModal(subject_id="", target_type="case"){
  modal(target_type === "note" ? "選擇範本帶入記事" : "選擇範本帶入案件", '<div class="loading-panel"><span class="spinner"></span><p>讀取範本庫…</p></div>');
  try{
    const res = await api('/api/template-packs/templates');
    const groups = (target_type === "note" ? res.note_template_groups : res.case_template_groups) || [];
    
    let totalCount = 0;
    groups.forEach(g => { totalCount += (g.templates || []).length; });

    if(!totalCount){
      modal("選擇範本", '<p class="muted" style="padding:1rem;">尚未啟用含有此類型範本的範本包。</p>');
      return;
    }

    const html = `<div class="template-picker-container" style="max-height:60vh;overflow-y:auto;padding-right:4px;">
      ${groups.map(g => `
        <div class="template-pack-group" style="margin-bottom:16px;">
          <h4 style="font-size:13px;font-weight:700;color:var(--text-subtle,#64748b);margin-bottom:8px;border-bottom:1px solid var(--line,#e2e8f0);padding-bottom:4px;">📦 範本包：${esc(g.pack_name)}</h4>
          <div style="display:grid;gap:8px;">
            ${(g.templates || []).map(t => {
              const title = t.rendered_title || t.title || "";
              const body = t.rendered_body || t.body || "";
              const cat = t.category_name || "一般";
              const pri = t.defaults?.priority || "normal";
              const tags = (t.defaults?.tags || []).join(", ");

              if (target_type === "note") {
                return `<div class="template-card" style="border:1px solid var(--line, #e2e8f0);border-radius:8px;padding:10px;background:var(--card-bg,#fff);">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong>${esc(t.name || t.title)}</strong>
                    <button type="button" class="btn small primary" data-action="apply-note-template" data-recipient="${esc(subject_id)}" data-title="${esc(title)}" data-body="${esc(body)}" data-cat="${esc(cat)}" data-tags="${esc(tags)}">套用此記事範本</button>
                  </div>
                  <div style="margin:4px 0;"><span class="badge" style="font-size:11px;">${esc(cat)}</span></div>
                  <p style="font-size:12px;color:var(--text-subtle,#64748b);margin:4px 0 0;white-space:pre-wrap;">${esc(body)}</p>
                </div>`;
              } else {
                return `<div class="template-card" style="border:1px solid var(--line, #e2e8f0);border-radius:8px;padding:10px;background:var(--card-bg,#fff);">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong>${esc(t.name || t.title)}</strong>
                    <button type="button" class="btn small primary" data-action="apply-case-template" data-subject="${esc(subject_id)}" data-title="${esc(title)}" data-desc="${esc(body)}" data-cat="${esc(cat)}" data-pri="${esc(pri)}">套用此案件範本</button>
                  </div>
                  <div style="margin:4px 0;"><span class="badge" style="font-size:11px;">${esc(cat)}</span></div>
                  <p style="font-size:12px;color:var(--text-subtle,#64748b);margin:4px 0 0;white-space:pre-wrap;">${esc(body)}</p>
                </div>`;
              }
            }).join("")}
          </div>
        </div>
      `).join("")}
    </div>`;
    modal(target_type === "note" ? "選擇記事範本帶入" : "選擇案件範本帶入", html);
  }catch(e){
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

function saveFilterModal(){
  const criteria={
    kind:state.kind!=="all"?state.kind:undefined,
    company:state.company||undefined,
    department:state.department||undefined,
    tag:state.tagFilter||undefined,
    search:state.search||undefined
  };
  const count=filteredContacts().length;
  modal("儲存目前篩選條件",`<form id="save-filter-form">
    <div class="form-grid">
      <div class="full">${field("篩選條件名稱","name","",'required maxlength="50" placeholder="例如：VIP 核心客戶、台北公務群組"')}</div>
    </div>
    <div class="filter-criteria-preview section-space">
      <h4>目前條件（符合 ${count} 個聊天室）</h4>
      <p class="subtitle">${esc(JSON.stringify(criteria,null,2))}</p>
    </div>
    <p class="callout">每個 OA 最多保存 10 組自訂篩選條件，同 OA 管理員共用。</p>
    <div class="form-actions"><button class="btn primary" type="submit">儲存篩選條件</button></div>
  </form>`);
}

function render(){
  if(lineUI.registry&&!lineDataReady()&&!["settings","organizations","channels","oa-list"].includes(state.view))state.view="channels";
  if(!titles[state.view])state.view="overview";
  $("crumb").textContent=titles[state.view]||"工作空間";document.title=(titles[state.view]||"工作台")+" · LINE 自動化";
  document.querySelectorAll("nav [data-view]").forEach(el=>{const current=el.dataset.view===state.view;el.classList.toggle("active",current);if(current)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  const pages={
    overview,
    "oa-list": oaListPage,
    chat:()=>chatPage(),
    reports:reportsPage,
    send:sendPage,
    cases:casesPage,
    contacts:()=>contactsPage(false),
    subscriptions:()=>contactsPage(true),
    history:historyPage,
    schedule:schedulePage,
    personnel:personnelPage,
    "org-settings":orgSettingsPage,
    settings:settingsPage,
    channels:channelsPage,
    organizations:organizationsPage
  };
  const pageFn = pages[state.view] || overview;
  $("page").innerHTML=pageFn();
  hydratePreviews();
}

function oaListPage(){
  const channelsList = state.channels || [];
  const q = (state.oaSearch || "").toLowerCase().trim();
  const filtered = channelsList.filter(c => !q || c.name.toLowerCase().includes(q) || (orgName(c.org_id)||"").toLowerCase().includes(q) || (c.basic_id||"").toLowerCase().includes(q));
  const currentId = channels.current_id();

  return heading("LINE OA 一覽", "查看並快速進入您獲授權存取的 LINE 官方帳號", `<div class="mg-tools" style="margin:0;"><input type="search" id="oa-list-search" value="${esc(state.oaSearch||"")}" placeholder="搜尋 OA 名稱或組織…" style="padding:6px 14px;border-radius:20px;border:1px solid var(--line,#e2e8f0);background:var(--card-bg,#fff);min-width:240px;"></div>`)+`
  <div class="dashboard-grid" style="grid-template-columns:1fr;">
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:8px;">
      ${filtered.map(c => `
        <div class="oa-card panel" style="display:flex;flex-direction:column;justify-content:space-between;padding:20px;border-radius:18px;background:var(--card-bg,#fff);border:1px solid ${c.channel_id===currentId?'#00B900':'var(--line,#e2e8f0)'};box-shadow:0 2px 10px rgba(0,0,0,0.03);position:relative;">
          ${c.channel_id===currentId ? '<span class="badge good" style="position:absolute;top:16px;right:16px;">目前使用中</span>' : ''}
          <div>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
              <div class="avatar" style="width:46px;height:46px;font-size:18px;background:#00B900;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;">${esc(c.name.slice(0,1))}</div>
              <div>
                <strong style="font-size:16px;display:block;">${esc(c.name)}</strong>
                <small style="color:var(--text-subtle,#64748b);font-size:12px;">${esc(c.basic_id || c.bot_user_id || "")} · ${esc(orgName(c.org_id))}</small>
              </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;background:var(--soft,#f8fafc);border-radius:12px;margin-bottom:16px;text-align:center;">
              <div><small style="color:var(--text-subtle,#64748b);font-size:11px;display:block;">有效好友</small><strong style="font-size:14px;">${state.contacts.filter(r=>r.channel_id===c.channel_id&&r.active).length || '—'}</strong></div>
              <div><small style="color:var(--text-subtle,#64748b);font-size:11px;display:block;">未讀訊息</small><strong style="font-size:14px;">${state.chatNotes.get(c.channel_id)?.length || 0}</strong></div>
              <div><small style="color:var(--text-subtle,#64748b);font-size:11px;display:block;">進行中案件</small><strong style="font-size:14px;">${state.cases.filter(cs=>cs.channel_id===c.channel_id&&cs.status!=='closed').length || 0}</strong></div>
            </div>
          </div>
          <div>
            <button class="btn ${c.channel_id===currentId?'dark':'primary'}" style="width:100%;justify-content:center;" data-action="switch-oa-direct" data-channel="${esc(c.channel_id)}" data-org="${esc(c.org_id)}">${c.channel_id===currentId?'進入工作總覽':'切換至此 OA'}</button>
          </div>
        </div>
      `).join("") || empty("查無符合的 LINE OA", "請確認是否已新增 LINE OA 或調整搜尋條件。")}
    </div>
  </div>`;
}

function personnelPage(){
  const org = mgCurrentOrg();
  if(!org) return empty("尚未選擇組織", "請先建立或選擇組織。");
  const members = state.memberships.filter(m => m.org_id === org.org_id);
  const rows = members.filter(m => mgMatches(management.peopleQuery, m.email, mgUser(m.email)?.display_name, m.department));
  const orgChannels = state.channels.filter(c => c.org_id === org.org_id);
  
  return heading("人員與權限", `管理「${esc(org.name)}」的營運與協助人員，指定可用 LINE OA。`, button("新增人員","new-personnel","primary"))+`
  <div class="management">
    <div class="mg-summary">
      <div class="mg-stat"><strong>${members.filter(m=>m.active).length}</strong><span>位後台人員</span></div>
      <div class="mg-stat"><strong>${members.filter(m=>m.active&&m.role==='sender').length}</strong><span>位營運人員</span></div>
      <div class="mg-stat"><strong>${members.filter(m=>m.active&&m.role==='assistant').length}</strong><span>位協助人員</span></div>
    </div>
    <section class="mg-card">
      <div class="mg-head">
        <div><h2>組織人員清單</h2><p>乙級組織管理員固定可存取本組織所有 OA；丙級（營運）與丁級（協助）可指定可用 OA。</p></div>
        <div class="mg-tools">${mgTools("mg-people-search","搜尋組織人員",management.peopleQuery,"姓名、Email 或部門")}</div>
      </div>
      <div class="mg-body">
        ${rows.map(m => {
          const u = mgUser(m.email);
          const key = esc(m.email + "|" + m.org_id);
          const enabled = m.active && u?.active;
          return `<div class="mg-row">
            <div class="mg-person">
              <span class="avatar" aria-hidden="true">${esc((u?.display_name || m.email).slice(0, 1))}</span>
              <div>
                <strong>${esc(u?.display_name || m.email)}</strong>
                <p>${esc(m.email)} · ${esc(m.department || "未分部門")}</p>
                <div class="mg-tags">
                  ${badge(roleName(m.role))}
                  ${!enabled ? badge("已停用") : badge("啟用中", "good")}
                </div>
              </div>
            </div>
            <div class="mg-actions">
              ${m.role !== 'administrator' ? button("編輯與 OA 授權", "edit-personnel", "small", `data-id="${key}"`) : ""}
              ${u?.active ? button("產生登入連結", "unused", "small", `data-security="invite" data-email="${esc(m.email)}"`) : ""}
            </div>
          </div>`;
        }).join("") || mgEmpty("尚無符合人員", "點選右上角「新增人員」開始指派夥伴。")}
      </div>
    </section>
  </div>`;
}

function orgSettingsPage(){
  const org = mgCurrentOrg();
  if(!org) return empty("尚未選擇組織", "請先建立或選擇組織。");
  return heading("組織設定", `檢視與設定「${esc(org.name)}」的基本資料、範本包與操作紀錄。`, "")+`
  <div class="management">
    <section class="mg-card">
      <div class="mg-head">
        <div><h2>組織基本資料</h2><p>組織代碼：${esc(org.org_id)} · 組織類型：${esc(orgKinds[org.kind]||org.kind)}</p></div>
        ${button("編輯組織資料", "edit-organization", "small", `data-id="${esc(org.org_id)}"`)}
      </div>
    </section>
    <section class="mg-card">
      <div class="mg-head">
        <div><h2>自訂範本包管理</h2><p>為組織建立自訂案件與記事範本包，各 OA 可勾選啟用。</p></div>
        ${button("管理自訂範本包", "open-template-packs-mgr", "primary small")}
      </div>
    </section>
    <section class="mg-card">
      <div class="mg-head">
        <div><h2>組織操作與查閱紀錄</h2><p>包含內部人員操作與供應商查看紀錄（透明稽核）。</p></div>
        ${badge(state.events.length + " 筆紀錄")}
      </div>
      <div class="mg-body">
        ${state.events.map(e => `
          <div class="activity-row" style="padding:10px 0;border-bottom:1px solid var(--line,#e2e8f0);">
            <div style="display:flex;justify-content:space-between;">
              <strong>${esc(e.detail || e.action)}</strong>
              <small class="muted">${when(e.created_at)}</small>
            </div>
            <small style="color:var(--text-subtle,#64748b);">${esc(e.actor)} · ${esc(e.action)}</small>
          </div>
        `).join("") || '<p class="muted">尚無操作紀錄。</p>'}
      </div>
    </section>
  </div>`;
}

function personnelForm(id){
  const org = mgCurrentOrg();
  if(!org) return;
  const m = id ? state.memberships.find(x => x.email + "|" + x.org_id === id) : null;
  const u = m ? mgUser(m.email) : null;
  const orgChannels = state.channels.filter(c => c.org_id === org.org_id);
  const existingChannelIds = m?.channel_ids || orgChannels.map(c => c.channel_id);
  
  const oaCheckboxes = orgChannels.map(c => `
    <label class="check-label" style="display:flex;align-items:center;gap:8px;padding:6px 0;">
      <input type="checkbox" name="channel_ids" value="${esc(c.channel_id)}" ${existingChannelIds.includes(c.channel_id) ? "checked" : ""}>
      <span><strong>${esc(c.name)}</strong> <small style="color:var(--text-subtle,#64748b);">${esc(c.basic_id||"")}</small></span>
    </label>
  `).join("") || '<p class="muted">此組織尚未連結任何 LINE OA。</p>';
  
  modal(id ? "編輯組織人員" : "新增組織人員", `<form id="personnel-form" data-id="${esc(id||"")}">
    <input type="hidden" name="org_id" value="${esc(org.org_id)}">
    <div class="form-grid">
      ${field("登入 Email", "email", m?.email || "", `type="email" required ${id ? "readonly" : ""} placeholder="user@example.com"`)}
      ${field("顯示名稱", "display_name", u?.display_name || "", 'maxlength="80" placeholder="方便同事識別的姓名"')}
      ${selectField("人員角色", "role", [["sender", "丙級 · 營運人員（可讀取並回覆對話、發送訊息、管理案件）"], ["assistant", "丁級 · 協助人員（可讀取對話、管理記事與案件，不可傳送訊息）"]], m?.role || "sender")}
      ${field("部門／分組（選填）", "department", m?.department || "", 'maxlength="80" placeholder="例如：客服組、維修部"')}
      <div class="full">
        <label class="field">
          <span>可使用的 LINE OA</span>
          <div class="permission-choices" style="margin-top:6px;max-height:160px;overflow-y:auto;border:1px solid var(--line,#e2e8f0);border-radius:10px;padding:8px 12px;background:var(--soft,#f8fafc);">
            ${oaCheckboxes}
          </div>
          <small class="muted">勾選該人員可操作的 LINE OA。未勾選的 OA 該人員登入後無法檢視或操作。</small>
        </label>
      </div>
      <div class="full">
        <label class="check-label" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" name="active" ${m?.active !== 0 ? "checked" : ""}>
          <span>啟用此人員帳號</span>
        </label>
      </div>
    </div>
    <div class="form-actions">
      <button class="btn primary" type="submit">${id ? "儲存設定" : "建立人員"}</button>
    </div>
  </form>`);
}

function myAccountModal(){
  const user = state.session?.user || {};
  const email = state.session?.identity || "";
  const role = state.session?.role || "";
  
  modal("我的帳號", `<div style="padding:4px 0;">
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--line,#e2e8f0);">
      <div class="avatar" style="width:50px;height:50px;font-size:22px;">${esc((user.display_name||email).slice(0,1).toUpperCase())}</div>
      <div>
        <h3 style="margin:0 0 4px;font-size:17px;">${esc(user.display_name || email)}</h3>
        <p style="margin:0;color:var(--text-subtle,#64748b);font-size:13px;">${esc(email)} · ${badge(roleName(role))}</p>
      </div>
    </div>
    <div style="display:grid;gap:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:var(--soft,#f8fafc);border-radius:12px;">
        <div>
          <strong style="font-size:14px;display:block;">登入密碼</strong>
          <small style="color:var(--text-subtle,#64748b);font-size:12px;">定期更新密碼以維護帳號安全</small>
        </div>
        <button type="button" class="btn small" data-security="password">修改密碼</button>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:var(--soft,#f8fafc);border-radius:12px;">
        <div>
          <strong style="font-size:14px;display:block;">登入裝置與階段</strong>
          <small style="color:var(--text-subtle,#64748b);font-size:12px;">查看目前已登入的瀏覽器與裝置</small>
        </div>
        <button type="button" class="btn small" data-security="devices">裝置清單</button>
      </div>
    </div>
    <div class="form-actions" style="margin-top:24px;border-top:1px solid var(--line,#e2e8f0);padding-top:16px;display:flex;justify-content:space-between;">
      <button type="button" class="btn text" onclick="$('modal').close()">關閉</button>
      <button type="button" class="btn danger small" data-action="confirm-logout">登出帳號</button>
    </div>
  </div>`);
}

function openOaSwitcherModal(){
  const allOas = state.channels || [];
  const currentId = channels.current_id();
  modal("切換 LINE OA", `<div class="oa-switcher-modal">
    <div style="margin-bottom:12px;display:flex;gap:8px;">
      <input type="search" id="oa-switcher-filter" placeholder="搜尋 LINE OA 名稱或組織…" style="flex:1;padding:8px 12px;border-radius:8px;border:1px solid var(--line,#e2e8f0);">
      <button type="button" class="btn" data-action="go-oa-list-from-switcher">📋 OA 一覽</button>
    </div>
    <div id="oa-switcher-items" style="max-height:55vh;overflow-y:auto;display:grid;gap:8px;">
      ${allOas.map(c => `
        <button type="button" class="oa-switcher-item" data-action="switch-oa-direct" data-channel="${esc(c.channel_id)}" data-org="${esc(c.org_id)}" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:10px;border:1px solid ${c.channel_id===currentId?'#00B900':'var(--line,#e2e8f0)'};background:${c.channel_id===currentId?'#f0fdf4':'var(--card-bg,#fff)'};cursor:pointer;text-align:left;width:100%;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="avatar" style="width:32px;height:32px;font-size:14px;background:#00B900;color:#fff;">${esc(c.name.slice(0,1))}</div>
            <div>
              <strong style="font-size:14px;display:block;">${esc(c.name)} ${c.channel_id===currentId?'(目前)':''}</strong>
              <small style="color:var(--text-subtle,#64748b);font-size:11px;">${esc(orgName(c.org_id))}</small>
            </div>
          </div>
          ${c.channel_id===currentId ? '<span style="color:#16a34a;font-weight:700;">✓</span>' : ''}
        </button>
      `).join("") || '<p class="muted">尚無可切換的 LINE OA。</p>'}
    </div>
  </div>`);
}
function navigate(view){if(state.busy)return;notice("");state.view=view;state.search="";state.kind="all";state.company="";state.department="";state.tagFilter="";state.page=1;setSidebarOpen(false);history.replaceState(null,"","/?view="+encodeURIComponent(view));render();window.scrollTo({top:0});}
function modal(title,html){$("modal-title").textContent=title;$("modal-body").innerHTML=html;$("modal-error").hidden=true;if(!$("modal").open)$("modal").showModal();$("modal").scrollTop=0;$("modal-close").focus({preventScroll:true});}
function editContact(id){
  const r=state.contacts.find(x=>x.recipient_id===id);
  if(!r)return;
  const tagIds=(r.tags||[]).map(t=>t.id);
  const tagCheckboxes=(state.tags||[]).map(t=>`<label class="check-label tag-chip"><input type="checkbox" name="tag_ids" value="${esc(t.id)}" ${tagIds.includes(t.id)?"checked":""}><span class="tag-dot" data-color="${esc(t.color||'#007AFF')}"></span>${esc(t.name)}</label>`).join("");
  const currentType=r.contact_type||"";
  modal("編輯聯絡對象",`<form id="contact-form" data-id="${esc(id)}">
    <div class="form-section">
      <h3 class="form-section-title">基本資訊</h3>
      <div class="form-grid">
        ${field("備註名稱（自訂名稱）","alias",r.alias||r.custom_name||"",'maxlength="80" placeholder="團隊內部備註名稱，不會寫回 LINE"')}
        <label class="field">LINE 顯示名稱（唯讀）<input value="${esc(r.display_name||"尚未取得")}" readonly class="muted"></label>
        <label class="field">LINE 聊天室識別碼（唯讀）<input value="${esc(r.recipient_id)}" readonly class="line-id-chip"></label>
        ${selectField("聯絡對象類型","contact_type",[["","未分類"],["organization","組織／團體"],["person_business","公務對象個人"],["person_private","一般個人"]],currentType)}
      </div>
    </div>
    <div class="form-section" id="contact-type-section">
      <h3 class="form-section-title">聯絡資訊</h3>
      <div class="form-grid" id="contact-dynamic-fields"></div>
    </div>
    <div class="form-section">
      <h3 class="form-section-title">系統設定</h3>
      <div class="form-grid">
        ${(superAdmin()?selectField("系統組織","company",oaOrganizationOptions(),r.company):field("系統組織","organization_label",orgName(r.company),'readonly')+`<input type="hidden" name="company" value="${esc(r.company)}">`)}
        ${field("系統部門","department",r.department,'maxlength="60" placeholder="例如：業務部"')}
        ${weatherModule()?`<label class="check-label full"><input name="subscribed" type="checkbox" ${r.weather_subscribed?"checked":""} ${r.active?"":"disabled"}>接收天氣通知</label>`:""}
      </div>
    </div>
    <div class="form-section">
      <h3 class="form-section-title">內部備忘與標籤</h3>
      <div class="form-grid">
        <div class="full"><label class="field">備忘筆記（Notes）<textarea name="notes" rows="3" maxlength="1000" placeholder="記錄該聯絡對象背景、注意事項、互動歷史備忘...">${esc(r.notes||"")}</textarea></label></div>
        <div class="full"><label class="field">分類標籤（Tags）</label><div class="permission-choices">${tagCheckboxes||'<p class="muted">尚未建立任何標籤，可於聯絡對象工具列點選「標籤管理」新增。</p>'}</div></div>
      </div>
    </div>
    <p class="callout">系統組織／部門決定可以收到哪些報表。自訂名稱、聯絡資訊與筆記僅供後台團隊檢視，不會傳送給 LINE 使用者。</p>
    <div class="form-actions"><button class="btn primary" type="submit">儲存聯絡對象</button></div>
  </form>`);
  const form=$("contact-form");
  const renderFields=type=>{
    const c=$("contact-dynamic-fields");if(!c)return;
    if(type==="organization"){
      c.innerHTML=`${field("對方組織名稱","organization_name",r.organization_name||"",'maxlength="80" placeholder="例如：台北市攝影同好會、宏昇生技"')}${field("代表電話","phone",r.phone||"",'maxlength="40" placeholder="例如：02-2345-6789"')}${field("代表 Email","email",r.email||"",'type="email" maxlength="120" placeholder="例如：contact@org.tw"')}${field("郵遞區號","postal_code",r.postal_code||"",'maxlength="10" placeholder="例如：100"')}<div class="full">${field("地址","address",r.address||"",'maxlength="200" placeholder="例如：台北市中正區重慶南路一段 10 號"')}</div>`;
    }else if(type==="person_business"){
      c.innerHTML=`${field("所屬對方組織","organization_name",r.organization_name||"",'maxlength="80" placeholder="例如：宏昇生技、北區家長會"')}${field("職稱","job_title",r.job_title||"",'maxlength="60" placeholder="例如：採購主任、總幹事"')}${field("公務電話","work_phone",r.work_phone||"",'maxlength="40" placeholder="例如：02-2345-6789"')}${field("公務分機","work_phone_ext",r.work_phone_ext||"",'maxlength="20" placeholder="例如：101"')}${field("公務 Email","work_email",r.work_email||"",'type="email" maxlength="120" placeholder="例如：john@company.com"')}${field("個人電話（選填）","phone",r.phone||"",'maxlength="40" placeholder="例如：0912-345-678"')}${field("個人 Email（選填）","email",r.email||"",'type="email" maxlength="120" placeholder="例如：john@gmail.com"')}${field("郵遞區號","postal_code",r.postal_code||"",'maxlength="10" placeholder="例如：100"')}<div class="full">${field("通訊地址","address",r.address||"",'maxlength="200" placeholder="例如：台北市中正區重慶南路一段 10 號"')}</div>`;
    }else{
      c.innerHTML=`${field("聯絡電話","phone",r.phone||"",'maxlength="40" placeholder="例如：0912-345-678"')}${field("Email","email",r.email||"",'type="email" maxlength="120" placeholder="例如：user@example.com"')}${field("郵遞區號","postal_code",r.postal_code||"",'maxlength="10" placeholder="例如：100"')}<div class="full">${field("地址","address",r.address||"",'maxlength="200" placeholder="例如：台北市中正區重慶南路一段 10 號"')}</div>`;
    }
  };
  renderFields(currentType);
  form.elements.contact_type?.addEventListener("change",e=>renderFields(e.target.value));
}
function tagManagerModal(){
  const tags=state.tags||[];
  const tagListHtml=tags.map(t=>{
    const count=state.contacts.filter(c=>(c.tags||[]).some(ct=>ct.id===t.id)).length;
    return `<div class="tag-row"><div class="tag-row-info">${tagBadge(t)}<span class="muted" style="font-size:12px;">${count} 個聯絡對象</span></div><div class="draft-actions">${button("編輯","edit-tag-modal","small",`data-id="${esc(t.id)}"`)}${button("刪除","delete-tag-btn","text small danger",`data-id="${esc(t.id)}"`)}</div></div>`;
  }).join("")||'<p class="muted">目前尚未建立任何標籤。</p>';
  const colorSwatches=APPLE_TAG_COLORS.map((c,i)=>`<label class="color-swatch-card ${i===0?'selected':''}" data-color="${c.hex}"><input type="radio" name="color" value="${c.hex}" ${i===0?"checked":""} class="color-radio-input"><span class="color-circle" data-color="${c.hex}"></span><span class="color-name">${c.name}</span></label>`).join("");
  modal("標籤管理",`<div><p class="subtitle">標籤可用於彈性分群聯絡對象，支援多對多關聯。</p><h3>現有標籤</h3><div class="tag-manager-list">${tagListHtml}</div><h3 class="section-space">新增標籤</h3><form id="tag-create-form"><div class="form-grid"><div class="full">${field("標籤名稱","name","",'required maxlength="30" placeholder="例如：VIP客戶、已簽約、北區廠商"')}</div><div class="full"><div class="field"><span>標籤顏色（Apple 色票）</span><div class="color-picker-grid">${colorSwatches}</div></div></div></div><div class="form-actions">${button("建立標籤","","primary",'type="submit"')}</div></form></div>`);
}
function tagEditModal(id){
  const t=(state.tags||[]).find(x=>x.id===id);
  if(!t)return;
  const colorSwatches=APPLE_TAG_COLORS.map(c=>{
    const checked=c.hex.toLowerCase()===(t.color||"").toLowerCase();
    return `<label class="color-swatch-card ${checked?'selected':''}" data-color="${c.hex}"><input type="radio" name="color" value="${c.hex}" ${checked?"checked":""} class="color-radio-input"><span class="color-circle" data-color="${c.hex}"></span><span class="color-name">${c.name}</span></label>`;
  }).join("");
  modal("編輯標籤",`<form id="tag-edit-form" data-id="${esc(id)}"><div class="form-grid"><div class="full">${field("標籤名稱","name",t.name,'required maxlength="30" placeholder="請輸入標籤名稱"')}</div><div class="full"><div class="field"><span>標籤顏色（Apple 色票）</span><div class="color-picker-grid">${colorSwatches}</div></div></div></div><div class="form-actions">${button("返回標籤清單","manage-tags","")}${button("儲存變更","","primary",'type="submit"')}</div></form>`);
}
function bulkAddTagsModal(){
  const count=state.selected.size;
  if(!count)throw new Error("請先選取聯絡對象。");
  const tagCheckboxes=(state.tags||[]).map(t=>`<label class="check-label tag-chip"><input type="checkbox" name="tag_ids" value="${esc(t.id)}"><span class="tag-dot" data-color="${esc(t.color||'#007AFF')}"></span>${esc(t.name)}</label>`).join("");
  modal(`批次新增標籤（已選取 ${count} 個聯絡對象）`,`<form id="bulk-add-tags-form"><p class="subtitle">勾選要加入這些聯絡對象的標籤：</p><div class="permission-choices section-space">${tagCheckboxes||'<p class="muted">尚未建立任何標籤。</p>'}</div><div class="form-actions"><button class="btn primary" type="submit">確認加入標籤</button></div></form>`);
}
function bulkRemoveTagsModal(){
  const count=state.selected.size;
  if(!count)throw new Error("請先選取聯絡對象。");
  const tagCheckboxes=(state.tags||[]).map(t=>`<label class="check-label tag-chip"><input type="checkbox" name="tag_ids" value="${esc(t.id)}"><span class="tag-dot" data-color="${esc(t.color||'#007AFF')}"></span>${esc(t.name)}</label>`).join("");
  modal(`批次移除標籤（已選取 ${count} 個聯絡對象）`,`<form id="bulk-remove-tags-form"><p class="subtitle">勾選要從這些聯絡對象移除的標籤：</p><div class="permission-choices section-space">${tagCheckboxes||'<p class="muted">尚未建立任何標籤。</p>'}</div><div class="form-actions"><button class="btn danger" type="submit">確認移除標籤</button></div></form>`);
}
async function bulkSubscription(subscribed){
  const count=state.selected.size;
  if(!count)throw new Error("請先選取聯絡對象。");
  await api('/api/contacts/bulk',{action:'set_subscription',contact_ids:[...state.selected],subscribed});
  await load();
  render();
  notice(`已將 ${count} 個聯絡對象設定為 ${subscribed?'開啟':'取消'} 天氣訂閱。`);
}
function reportForm(reportId){const source=(state.settings.report_sources||[]).find(r=>r.report_id===reportId);modal(source?"編輯報告來源":"新增報告來源",`<form id="report-form"><div class="form-grid">${field("報告名稱","title","",'required maxlength="80" placeholder="例如：每日業績報表"')}${selectField("報告類型","category",[["company","組織報表"],["weather","天氣報告"],["other","其他報告"]],"company")}${selectField("工作區","company",oaOrganizationOptions(),selectedWorkspace()?.org_id||"")}${selectField("可見範圍","scope",[["company","全組織"],["department","指定部門"],["personal","指定個人"]],"company")}${field("部門（部門報告必填）","department","",'maxlength="60"')}${selectField("LINE 個人聯絡對象（個人報告必填）","owner_recipient_id",[["","選擇聯絡對象"],...state.contacts.filter(r=>r.kind==="user"&&r.active).map(r=>[r.recipient_id,label(r)+" · "+orgName(r.company)])],"")}<div class="full"><input name="asset_id" type="hidden"><label class="upload-picker">${icon("image")}<strong>從裝置選擇報告圖片</strong><span>JPG／PNG，每張最多 8 MB</span><input id="report-file" type="file" accept="image/png,image/jpeg,.jpg,.jpeg,.png"></label><div id="report-upload-preview" role="status"></div><p class="subtitle">先選組織再上傳；保存本次檔案的副本。每日自動更新的報告可使用下方進階設定。</p><details><summary>進階設定：自動化報告來源</summary><label class="field section-space">伺服器 PNG 路徑<input name="source_path" placeholder="D:\\Reports\\daily.png"><small>外部程式更新此檔案後，報告中心會讀取最新版。目前支援 1 MB 以內 PNG。</small></label></details></div></div><div class="form-actions"><button class="btn primary" type="submit">儲存報告來源</button></div></form>`);if(source){const form=$("report-form");form.dataset.id=source.report_id;for(const key of ["title","category","company","scope","department","owner_recipient_id","source_path"])form.elements[key].value=source[key]||"";if(!source.owner_recipient_id&&source.owner_email)form.elements.owner_recipient_id.value=state.memberships.find(m=>m.email===source.owner_email&&m.org_id===source.company)?.recipient_id||"";}}
async function chooseReport(id){if(!state.session.modules.messaging)throw new Error("此組織未授權訊息發送模組。");if(sessionStorage.getItem("linePendingJob"))throw new Error("請先確認上次發送的狀態，再建立新的工作。");const r=await api('/api/reports/'+id);if(r.status!=="ready")throw new Error(r.reason);state.report=r;state.previews.set(id,r);state.step=2;state.selected.clear();state.audience="selected";navigate("send");}
async function submitSend(){
  if(state.busy)return;
  if(!state.session.modules.messaging)throw new Error("此組織未授權訊息發送模組。");
  if(state.session.preview)throw new Error("預覽不會實際發送，請返回原帳號操作。");
  if(sessionStorage.getItem("linePendingJob"))throw new Error("有一筆提交尚未確認。請先到發送紀錄檢查，再重新整理。");
  const allow=Boolean($("allow-stale")?.checked);if(state.report.stale&&!allow)throw new Error("請先確認這份較早的報告仍適合發送。");
  const id=crypto.randomUUID(),payload={job_id:id,allow_stale:allow,audience:state.audience,ids:selectedRows().map(r=>r.recipient_id)};
  if(state.report.category==="composition")payload.composition=state.report.composition;else if(state.report.category==="text")payload.message_text=state.report.message_text;else{payload.report_id=state.report.report_id;payload.report_version=state.report.version;}
  if($("send-timing").value==="scheduled"){const value=$("scheduled-time").value;const date=new Date(value+":00+08:00");if(!value||!Number.isFinite(date.getTime())||date.getTime()<Date.now()+30000)throw new Error("請選擇至少 30 秒後的台北時間。");payload.scheduled_at=date.toISOString();}
  state.busy=true;sessionStorage.setItem("linePendingJob",id);$("submit-send").disabled=true;$("submit-send").textContent="正在驗證並建立工作…";
  try{await api("/api/send",payload);sessionStorage.removeItem("linePendingJob");state.busy=false;await load();state.step=1;state.report=null;state.selected.clear();navigate("history");notice(payload.scheduled_at?"已建立預約，可於發送紀錄查看或取消。":"發送工作已建立，可以展開紀錄查看每個聊天室的結果。");const el=document.querySelector(`[data-job="${id}"]`);if(el)el.open=true;}
  catch(error){state.busy=false;if(error.status&&error.status<500)sessionStorage.removeItem("linePendingJob");render();throw error;}
}
async function recoverSubmission(){const id=sessionStorage.getItem("linePendingJob");if(!id||!admin())return;try{const result=await api('/api/jobs/'+id);if(result.jobs.length){sessionStorage.removeItem("linePendingJob");notice("上次提交已建立工作，請查看發送紀錄。",false);}}catch(error){if(error.status===404){notice("上次提交尚無紀錄；可能仍在處理。請稍後重新整理確認，避免重複發送。",true);modal("確認上次發送",`<p>伺服器目前找不到上次工作紀錄。請先確認聊天室沒有收到圖片，且原本的提交已結束，再解除保護。</p><p class="contact-id section-space">工作 ${esc(id)}</p><div class="form-actions">${button("我已確認，解除提交保護","clear-pending","danger")}</div>`);}else throw error;}}
function viewPicker(){
  modal("切換檢視視角",`<p class="subtitle">目前登入：${esc(principalSession.identity)}。預覽會套用該帳號的角色、公司、部門與個人資料權限，並禁止寫入操作。</p><div class="view-options">${button("返回原帳號視角","apply-view","",'data-id=""')}${viewOptions.map(user=>button(`<strong>${esc(user.display_name||user.email)}</strong><small>${esc(user.email)} · ${esc(roleName(user.role))} · ${esc(user.organization_name||orgName(user.company))} / ${esc(user.department||"未分部門")}</small>`,"apply-view",user.email===viewAs&&user.company===previewOrganization?"active":"",`data-id="${esc(user.email+"|"+user.company)}"`)).join("")}</div>${!viewOptions.length?'<p class="callout">目前沒有可預覽的帳號；平台管理員可在「帳號與設定」新增或調整角色。</p>':""}<p class="subtitle">本瀏覽器會記住選擇；預覽不會變更真正的登入帳號。Cloudflare 登入到期後仍需驗證。</p>`);
}
function switchView(email){
  if(email&&!viewOptions.some(user=>user.email+"|"+user.company===email))throw new Error("請重新整理可用帳號。");
  if(email)localStorage.setItem(viewKey,email);else localStorage.removeItem(viewKey);
  // A full navigation discards in-flight previews and all previous-role data.
  location.replace(location.pathname+"?view="+(email?"reports":"overview"));
}
document.addEventListener("click",async event=>{
  if(event.target.closest("#my-account-btn")){myAccountModal();return;}
  if(event.target.closest("#workspace-context")){openOaSwitcherModal();return;}
  const nav=event.target.closest("[data-view]");if(nav){navigate(nav.dataset.view);return;}
  const target=event.target.closest("[data-action]");if(!target||target.disabled||state.busy)return;
  const action=target.dataset.action,id=target.dataset.id;
  try{
    if(workspaceAction(action,id))return;
    if(managementAction(action,id))return;
    if(composerAction(action,id))return;
    if(typeof chatAction==="function"&&chatAction(action,id,target))return;
    if(action==="switch-oa-direct"){
      const channelId=target.dataset.channel;
      const orgId=target.dataset.org;
      if(channelId){
        localStorage.setItem("lineSelectedChannel",channelId);
        if(orgId)localStorage.setItem(organizationKey,orgId);
        location.replace(location.pathname+"?view="+encodeURIComponent(state.view||"overview"));
      }
    }
    else if(action==="go-oa-list-from-switcher"){$("modal").close();navigate("oa-list");}
    else if(action==="dismiss-onboarding"){
      const orgId=state.session?.user?.company||"";
      if(orgId)localStorage.setItem("lineOnboardingDismissed_"+orgId,"1");
      render();
    }
    else if(action==="new-personnel")personnelForm();
    else if(action==="edit-personnel")personnelForm(id);
    else if(action==="open-template-packs-mgr"){navigate("channels");$("modal").close();}
    else if(action==="confirm-logout"){
      if(principalSession?.auth?.method!=="password"){location.href="/cdn-cgi/access/logout";return;}
      try{await api('/api/auth/logout',{},true,true);sessionStorage.removeItem('lineAdminToken');location.replace('/login');}catch(error){notice(error.message,true);}
    }
    else if(action==="case-filter"){state.caseFilter=id;render();}
    else if(action==="new-case-modal")createCaseModal(id||"");
    else if(action==="open-case-detail")await caseDetailModal(id);
    else if(action==="contact-detail-from-case"){workspaceUI.contactDetail=id;navigate("contacts");await loadChatNotes(id);}
    else if(action==="export-cases-csv"){window.open('/api/cases/export?format=csv', '_blank');notice("已開始匯出 CSV。");}
    else if(action==="export-cases-xlsx"){window.open('/api/cases/export?format=xlsx', '_blank');notice("已開始匯出 XLSX。");}
    else if(action==="toggle-case-lock"){await api(`/api/cases/${id}/lock`);await load();render();notice("已更新案件鎖定狀態。");}
    else if(action==="create-continuation-case"){
      const c = state.cases.find(x=>x.case_id===id);
      if(c) createCaseModal(c.case_subject_id, {
        title: `延續：${c.title}`,
        description: `[延續前案 ${c.case_no}]\n`,
        continued_from_id: c.case_id,
        category: c.category || "一般",
        priority: c.priority || "normal"
      });
    }
    else if(action==="open-template-picker")await templatePickerModal(target.dataset.subject||"","case");
    else if(action==="open-note-template-picker")await templatePickerModal(target.dataset.recipient||"","note");
    else if(action==="apply-case-template"){
      createCaseModal(target.dataset.subject||"", {
        title: target.dataset.title||"",
        description: target.dataset.desc||"",
        category: target.dataset.cat||"一般",
        priority: target.dataset.pri||"normal"
      });
    }
    else if(action==="apply-note-template"){
      chatNoteModal(target.dataset.recipient||"", "", {
        title: target.dataset.title||"",
        content: target.dataset.body||"",
        note_type: target.dataset.cat||"一般",
        tags: target.dataset.tags||""
      });
    }
    else if(action==="case-to-processing"){await api(`/api/cases/${id}`,{status:"processing"});await load();render();notice("案件已轉為「處理中」。");}
    else if(action==="open-case-waiting-modal")caseWaitingModal(id);
    else if(action==="case-to-ready"){await api(`/api/cases/${id}`,{status:"ready_to_close"});await load();render();notice("案件已轉為「待結案」。");}
    else if(action==="case-resume-processing"){await api(`/api/cases/${id}`,{status:"processing"});await load();render();notice("案件已恢復為「處理中」。");}
    else if(action==="case-back-processing"){await api(`/api/cases/${id}`,{status:"processing"});await load();render();notice("案件已退回為「處理中」。");}
    else if(action==="open-case-close-modal")caseCloseModal(id);
    else if(action==="new-chat-note")chatNoteModal(id);
    else if(action==="edit-chat-note")chatNoteModal(target.dataset.recipient,id);
    else if(action==="delete-chat-note"){modal("刪除對話記事？",`<p>確定要刪除這筆記事嗎？刪除後無法恢復。</p><div class="form-actions">${button("確認刪除","confirm-delete-chat-note","danger",`data-id="${esc(id)}" data-recipient="${esc(target.dataset.recipient)}"`)}</div>`);}
    else if(action==="confirm-delete-chat-note"){await api("/api/chat-notes",{action:"delete",note_id:id});await loadChatNotes(target.dataset.recipient);$("modal").close();notice("記事已刪除。");}
    else if(action==="open-save-filter-modal")saveFilterModal();
    else if(action==="new-organization")organizationForm();
    else if(action==="edit-organization")organizationForm(id);
    else if(action==="new-membership")membershipForm();
    else if(action==="edit-membership")membershipForm(id);
    else if(action==="switch-view")viewPicker();
    else if(action==="apply-view")switchView(id||"");
    else if(action==="go-reports")navigate("reports");
    else if(action==="start-send"){state.step=1;state.report=null;state.reportFilter="all";navigate("send");}
    else if(action==="choose-text"){const text=$("message-draft").value;if(!text.trim())throw new Error("請先輸入文字。");if(sessionStorage.getItem("linePendingJob"))throw new Error("請先確認上次提交結果。");state.textDraft=text;state.report={category:"text",title:"文字訊息",message_text:text,status:"ready",scope:"text"};state.step=2;state.selected.clear();state.audience="selected";render();}
    else if(action==="cancel-schedule")modal("取消這筆預約？",`<p>取消後不會傳送。已開始處理的工作無法取消。</p><div class="form-actions">${button("確認取消預約","confirm-cancel-schedule","danger",`data-id="${esc(id)}"`)}</div>`);
    else if(action==="confirm-cancel-schedule"){await api('/api/jobs/cancel',{job_id:id});$("modal").close();await load();render();notice("預約已取消。");}
    else if(action==="choose-report")await chooseReport(id);
    else if(action==="preview"){const r=await api('/api/reports/'+id);if(r.status!=="ready")throw new Error(r.reason);modal(r.title,`<img class="modal-preview" src="${r.preview}" alt="${esc(r.title)}"><p class="subtitle">${when(r.modified_at)} · ${esc(scope(r))}</p>${r.stale?'<p class="callout warn">非今日更新，請留意資料日期。</p>':""}${admin()?`<div class="form-actions">${button("使用這份報告","preview-send","primary",`data-id="${esc(id)}"`)}</div>`:""}`);}
    else if(action==="preview-send"){$("modal").close();await chooseReport(id);}
    else if(action==="new-report")reportForm();
    else if(action==="edit-report"){reportForm(id);$("report-form").insertAdjacentHTML("beforeend",button("移除這個報告來源","remove-report","text small",`data-id="${esc(id)}" type="button"`));}
    else if(action==="remove-report")modal("移除報告來源",`<p>將從報告中心移除「${esc(state.reports.find(r=>r.report_id===id)?.title)}」。原始圖片與既有發送紀錄會保留，尚未開始的發送工作會取消；已開始或已送出的訊息無法撤回。${id==="weather"?"此設定對所有組織生效；之後可在報告中心恢復天氣報告。":""}</p><div class="form-actions">${button("確認移除","confirm-remove-report","danger",`data-id="${esc(id)}"`)}</div>`);
    else if(action==="confirm-remove-report"){await api('/api/reports/remove',{report_id:id});$("modal").close();state.reportFilter="all";state.report=null;await load();render();notice("報告來源已移除，尚未開始的發送工作已取消。");}
    else if(action==="restore-weather"){await api("/api/reports/restore-weather",{});state.reportFilter="all";await load();render();notice("天氣報告已恢復；已取消的發送不會恢復。");}
    else if(action==="report-filter"){state.reportFilter=id;render();}
    else if(action==="sub-filter"){state.subFilter=id;state.page=1;render();}
    else if(action==="history-filter"){state.historyFilter=id;render();}
    else if(action==="prev-page"||action==="next-page"){state.page+=action==="next-page"?1:-1;$("contact-list").innerHTML=contactList();}
    else if(action==="select-page"){filteredContacts().slice((state.page-1)*10,state.page*10).forEach(r=>state.selected.add(r.recipient_id));updateSelection();}
    else if(action==="clear-selection"){state.selected.clear();updateSelection();}
    else if(action==="manage-tags")tagManagerModal();
    else if(action==="edit-tag-modal")tagEditModal(id);
    else if(action==="delete-tag-btn")modal("刪除標籤？",`<p>確定要刪除標籤「${esc(state.tags.find(t=>t.id===id)?.name)}」嗎？已套用的聯絡對象將移除此標籤關聯。</p><div class="form-actions">${button("確認刪除標籤","confirm-delete-tag","danger",`data-id="${esc(id)}"`)}</div>`);
    else if(action==="confirm-delete-tag"){await api('/api/tags/delete',{id});await load();render();$("modal").close();notice("標籤已刪除。");}
    else if(action==="bulk-add-tags")bulkAddTagsModal();
    else if(action==="bulk-remove-tags")bulkRemoveTagsModal();
    else if(action==="bulk-sub-on")await bulkSubscription(true);
    else if(action==="bulk-sub-off")await bulkSubscription(false);
    else if(action==="edit-contact")editContact(id);
    else if(action==="new-dispatch-scope")dispatchScopeForm();
    else if(action==="edit-dispatch-scope")dispatchScopeForm(id);
    else if(action==="edit-sender-grant")senderGrantForm(id);
    else if(action==="new-account")accountForm();
    else if(action==="edit-account")accountForm(id);
    else if(action==="audience"){state.audience=id;render();}
    else if(action==="back-report"){state.step=1;render();}
    else if(action==="back-recipients"){state.step=2;render();}
    else if(action==="review"){if(!selectedRows().length)throw new Error("請先選擇有效的發送對象。");state.step=3;render();window.scrollTo({top:0});}
    else if(action==="submit-send")await submitSend();
    else if(action==="schedule-preset"){
      const input=$("scheduled-time");
      if(input){
        const now=new Date();let target=new Date(now.getTime()+15*60000);
        if(id==="15m")target=new Date(now.getTime()+15*60000);
        else if(id==="1h")target=new Date(now.getTime()+60*60000);
        else if(id==="tmr9")target=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1,9,0,0);
        else if(id==="tmr14")target=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1,14,0,0);
        else if(id==="nextmon"){const days=((1-now.getDay()+7)%7)||7;target=new Date(now.getFullYear(),now.getMonth(),now.getDate()+days,9,0,0);}
        const iso=new Date(target.getTime()-target.getTimezoneOffset()*60000).toISOString().slice(0,16);
        input.value=iso;input.focus();
      }
    }
    else if(action==="profiles"){target.disabled=true;const result=await api('/api/profiles',{});await load();render();notice(`已更新 ${result.updated} 個 LINE 名稱，${result.failed} 個未完成。`);}
  }catch(error){if($("modal").open){$("modal-error").textContent=error.message;$("modal-error").hidden=false;}else notice(error.message,true);target.disabled=false;}
});
function updateSelection(){if($("contact-list"))$("contact-list").innerHTML=contactList();if($("selection-summary"))$("selection-summary").innerHTML=selectionSummary();if($("review-button"))$("review-button").disabled=!selectedRows().length;}
document.addEventListener("input",event=>{
  if(event.target.id==="contact-search"){state.search=event.target.value;state.page=1;if($("contact-list"))$("contact-list").innerHTML=contactList();}
  if(event.target.id==="case-search"){state.caseQuery=event.target.value;if(state.view==="cases")render();}
  if(event.target.id==="chat-list-search"){if(typeof chatUI!=="undefined"){chatUI.query=event.target.value;if($("chat-room-list"))$("chat-room-list").innerHTML=renderChatRoomItems();}}
  if(event.target.id==="oa-switcher-filter"){
    const q=event.target.value.toLowerCase();
    document.querySelectorAll(".oa-switcher-item").forEach(item=>{
      item.style.display=item.textContent.toLowerCase().includes(q)?"flex":"none";
    });
  }
});
document.addEventListener("change",event=>{
  const el=event.target;
  if(el.name==="color"&&el.closest(".color-swatch-card")){
    el.closest(".color-picker-grid")?.querySelectorAll(".color-swatch-card").forEach(card=>card.classList.remove("selected"));
    el.closest(".color-swatch-card")?.classList.add("selected");
    return;
  }
  if(el.id==="organization-select"){localStorage.setItem(organizationKey,el.value);location.replace(location.pathname+"?view=overview");return;}
  if(el.id==="select-all-visible"){const visible=filteredContacts().slice((state.page-1)*10,state.page*10);if(el.checked)visible.forEach(r=>state.selected.add(r.recipient_id));else visible.forEach(r=>state.selected.delete(r.recipient_id));updateSelection();return;}
  if(el.id==="case-priority-filter"){state.casePriority=el.value;if(state.view==="cases")render();return;}
  if(el.id==="apply-saved-filter"){
    const sf=(state.savedFilters||[]).find(f=>f.filter_id===el.value);
    if(sf&&sf.criteria){
      const c=sf.criteria;
      state.kind=c.kind||"all";
      state.company=c.company||"";
      state.department=c.department||"";
      state.tagFilter=c.tag||"";
      state.search=c.search||"";
      state.page=1;
      render();
      notice(`已套用自訂篩選：「${sf.name}」`);
    }
    return;
  }
  if(el.id==="contact-tag-filter"){state.tagFilter=el.value;state.page=1;if($("contact-list"))$("contact-list").innerHTML=contactList();return;}
  if(el.id==="send-timing"){$("scheduled-time").hidden=el.value!=="scheduled";const wrap=$("scheduled-time-wrapper");if(wrap)wrap.hidden=el.value!=="scheduled";$("submit-send").textContent=el.value==="scheduled"?"確認預約":"確認立即發送";return;}
  if(el.dataset.select){el.checked?state.selected.add(el.dataset.select):state.selected.delete(el.dataset.select);updateSelection();}
  else if(["contact-kind","contact-company","contact-department"].includes(el.id)){state[{"contact-kind":"kind","contact-company":"company","contact-department":"department"}[el.id]]=el.value;state.page=1;if(el.id==="contact-company"){state.department="";render();}else $("contact-list").innerHTML=contactList();}
});
document.addEventListener("submit",async event=>{if(event.target.id==="password-form")return;event.preventDefault();const form=event.target,values=Object.fromEntries(new FormData(form)),submit=form.querySelector('[type="submit"]');if(!submit||submit.disabled)return;submit.disabled=true;$("modal-error").hidden=true;
  try{
    if(form.id==="chat-send-form"){
      const text=$("chat-message-input")?.value?.trim();
      if(!text)return;
      $("chat-message-input").value="";
      await sendChatMessage(form.dataset.id, text);
      return;
    }else if(form.id==="canned-reply-create-form"){
      await api("/api/chat/canned-replies/save", values);
      await cannedRepliesModal();
      notice("預設訊息已建立。");
      return;
    }else if(form.id==="case-create-form"){
      await api('/api/cases', values);
      $("modal").close();
      await load();
      render();
      notice("案件已建立。");
      return;
    }else if(form.id==="case-waiting-form"){
      await api(`/api/cases/${form.dataset.id}`, {status:"waiting", ...values});
      $("modal").close();
      await load();
      render();
      notice("案件已進入等待狀態。");
      return;
    }else if(form.id==="case-close-form"){
      await api(`/api/cases/${form.dataset.id}`, {status:"closed", ...values});
      $("modal").close();
      await load();
      render();
      notice("案件已結案。");
      return;
    }else if(form.id==="case-add-note-form"){
      await api(`/api/cases/${form.dataset.id}`, {action:"add_note", note:values.note});
      await caseDetailModal(form.dataset.id);
      await load();
      notice("已新增處理紀錄。");
      return;
    }else if(form.id==="chat-note-form"){
      const recipient_id = form.dataset.recipient;
      const note_id = form.dataset.noteId;
      const tags = values.tags ? values.tags.split(/[,，]/).map(s=>s.trim()).filter(Boolean) : [];
      await api('/api/chat-notes', {
        action: note_id ? "edit" : "add",
        recipient_id,
        note_id: note_id || undefined,
        title: values.title?.trim() || "",
        note_type: values.note_type || "一般",
        due_date: values.due_date || "",
        tags,
        expected_updated_at: values.expected_updated_at || undefined,
        content: values.content
      });
      await loadChatNotes(recipient_id);
      $("modal").close();
      notice(note_id ? "記事已更新。" : "記事已新增。");
      return;
    }else if(form.id==="save-filter-form"){
      const criteria = {
        kind: state.kind !== "all" ? state.kind : undefined,
        company: state.company || undefined,
        department: state.department || undefined,
        tag: state.tagFilter || undefined,
        search: state.search || undefined
      };
      await api('/api/saved-filters', { name: values.name, criteria });
      $("modal").close();
      await load();
      render();
      notice("自訂篩選條件已儲存。");
      return;
    }else if(form.id==="contact-form"){
      const tag_ids=new FormData(form).getAll('tag_ids');
      await api('/api/contact',{
        ...values,
        id:form.dataset.id,
        alias:values.alias,
        custom_name:values.alias,
        contact_type:values.contact_type||"",
        organization_name:values.organization_name||"",
        job_title:values.job_title||"",
        phone:values.phone||"",
        email:values.email||"",
        work_phone:values.work_phone||"",
        work_phone_ext:values.work_phone_ext||"",
        work_email:values.work_email||"",
        postal_code:values.postal_code||"",
        address:values.address||"",
        notes:values.notes||"",
        tag_ids,
        ...(superAdmin()?{subscribed:Boolean(form.elements.subscribed?.checked)}:{})
      });
    }else if(form.id==="tag-create-form"){
      await api('/api/tags/save',values);
    }else if(form.id==="tag-edit-form"){
      await api('/api/tags/save',{...values,id:form.dataset.id});
    }else if(form.id==="bulk-add-tags-form"){
      const tag_ids=new FormData(form).getAll('tag_ids');
      if(!tag_ids.length)throw new Error("請至少勾選一個標籤。");
      await api('/api/contacts/bulk',{action:'add_tags',contact_ids:[...state.selected],tag_ids});
    }else if(form.id==="bulk-remove-tags-form"){
      const tag_ids=new FormData(form).getAll('tag_ids');
      if(!tag_ids.length)throw new Error("請至少勾選一個標籤。");
      await api('/api/contacts/bulk',{action:'remove_tags',contact_ids:[...state.selected],tag_ids});
    }else if(form.id==="report-form")await api('/api/reports/save',{...values,report_id:form.dataset.id||undefined});
    else if(form.id==="organization-form")await api('/api/organizations/save',{...values,org_id:form.dataset.id||undefined,...Object.fromEntries(['active','reports_enabled','messaging_enabled','weather_enabled'].map(k=>[k,form.elements[k].checked]))});
    else if(form.id==="membership-form")await api('/api/memberships/save',{...values,active:form.elements.active.checked});
    else if(form.id==="dispatch-scope-form")await api('/api/dispatch-scopes/save',{...values,scope_id:form.dataset.id||undefined,active:form.elements.active.checked,recipient_ids:new FormData(form).getAll('recipient_ids')});
    else if(form.id==="sender-grant-form")await api('/api/sender-grants/save',{...values,scope_ids:new FormData(form).getAll('scope_ids'),report_ids:new FormData(form).getAll('report_ids'),...Object.fromEntries(['messaging','reports','weather'].map(k=>[k,form.elements[k].checked]))});
    else if(form.id==="personnel-form"){
      const channel_ids=new FormData(form).getAll('channel_ids');
      await api('/api/personnel/save',{
        email:values.email,
        org_id:values.org_id,
        display_name:values.display_name,
        role:values.role,
        department:values.department,
        active:form.elements.active.checked,
        channel_ids
      });
    }else if(form.id==="org-settings-form")await api('/api/org-settings/save',values);
    else if(form.id==="account-form")await api('/api/accounts/save',{...values,active:form.elements.active.checked});
    else return;
    $("modal").close();await load();managementAfterSave(form,values);render();notice("設定已儲存。");
  }catch(error){$("modal-error").textContent=error.message;$("modal-error").hidden=false;submit.disabled=false;}
});
$("modal-close").addEventListener("click",()=>$("modal").close());
$("menu").addEventListener("click",()=>setSidebarOpen(!$("sidebar").classList.contains("open")));
document.addEventListener("keydown",event=>{
  if(event.key==="Escape"){setSidebarOpen(false);}
  if(event.key==="Enter"&&!event.shiftKey&&event.target.id==="chat-message-input"){
    event.preventDefault();
    const form=$("chat-send-form");
    if(form)form.requestSubmit();
  }
});
$("logout").addEventListener("click",async()=>{if(principalSession?.auth?.method!=="password"){location.href="/cdn-cgi/access/logout";return;}try{await api('/api/auth/logout',{},true,true);sessionStorage.removeItem('lineAdminToken');location.replace('/login');}catch(error){notice(error.message,true);}});
$("refresh").addEventListener("click",async()=>{if(state.busy)return;$("refresh").disabled=true;try{await load();render();notice("資料已更新。");await recoverSubmission();}catch(error){notice(error.message,true);}finally{$("refresh").disabled=false;}});
async function boot(){try{await load();render();await recoverSubmission();}catch(error){$("page").innerHTML=empty("暫時無法開啟工作台",remote?"請重新整理登入，或聯絡管理員確認帳號已啟用。":"請確認 LINE 服務已更新並啟動，再從控制台重新開啟管理頁。");notice(error.message,true);$("connection").textContent="連線未完成";}}
boot();
let polling=false;
setInterval(async()=>{if(!state.loaded||!lineUI.ready||!lineDataReady()||!admin()||state.busy||state.authLost||document.hidden||polling||$("modal").open)return;polling=true;const requestedOA=lineUI.channel;try{const result=await api('/api/jobs');if(requestedOA!==lineUI.channel)return;if(JSON.stringify(result.jobs)!==JSON.stringify(state.jobs)){state.jobs=result.jobs;if(['overview','history','schedule'].includes(state.view)){const opened=[...document.querySelectorAll('[data-job][open]')].map(el=>el.dataset.job);render();document.querySelectorAll('[data-job]').forEach(el=>{el.open=opened.includes(el.dataset.job);});}}}catch(error){notice(error.message,true);}finally{polling=false;}},6000);

// Handle unreadable image content without leaving a broken thumbnail.
document.addEventListener("error",event=>{if(event.target instanceof HTMLImageElement){const replacement=document.createElement("p");replacement.className="callout warn";replacement.textContent="圖片無法顯示，請確認來源檔案格式並重新產生報告。";event.target.replaceWith(replacement);}},true);

function scheduleLabel(value){return new Date(value).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false});}
function scheduleFields(){return `<div class="schedule-fields"><label class="field">傳送時間<select id="send-timing"><option value="now">立即傳送</option><option value="scheduled">指定日期與時間</option></select></label><div id="scheduled-time-wrapper" hidden><label class="field">台北時間 UTC+08:00<input type="datetime-local" id="scheduled-time" hidden></label><div class="schedule-presets section-space"><span class="muted" style="font-size:11px;margin-right:6px;">快速預約：</span><button type="button" class="btn small" data-action="schedule-preset" data-id="15m">+15 分鐘</button><button type="button" class="btn small" data-action="schedule-preset" data-id="1h">+1 小時</button><button type="button" class="btn small" data-action="schedule-preset" data-id="tmr9">明天 09:00</button><button type="button" class="btn small" data-action="schedule-preset" data-id="tmr14">明天 14:00</button><button type="button" class="btn small" data-action="schedule-preset" data-id="nextmon">下週一 09:00</button></div></div><p class="subtitle">預約保存現在確認的文字或圖片與發送對象；到期再檢查帳號、收件範圍與訂閱。電腦與 LINE 服務需開啟，延遲超過 10 分鐘標記逾期，不補發。</p></div>`;}

function organizationOptions(){return [["","選擇組織"],...(state.organizations||[]).filter(o=>o.active).map(o=>[o.org_id,o.name])];}

// Mobile navigation behaves as a drawer; keyboard focus stays inside until closed.
const compactNavigation=window.matchMedia('(max-width:850px)');
function setSidebarOpen(open){
  open=Boolean(open&&compactNavigation.matches);
  const wasOpen=$('sidebar').classList.contains('open');
  $('sidebar').classList.toggle('open',open);
  $('menu').setAttribute('aria-expanded',String(open));
  $('nav-backdrop').hidden=!open;
  document.body.classList.toggle('nav-open',open);
  document.querySelector('.workspace').inert=open;
  $('sidebar').inert=compactNavigation.matches&&!open;
  if(open)$('sidebar-close').focus({preventScroll:true});
  else if(wasOpen&&compactNavigation.matches)$('menu').focus({preventScroll:true});
}
$('sidebar-close').addEventListener('click',()=>setSidebarOpen(false));
$('nav-backdrop').addEventListener('click',()=>setSidebarOpen(false));
compactNavigation.addEventListener('change',()=>setSidebarOpen(false));
setSidebarOpen(false);
document.addEventListener('keydown',event=>{
  if(event.key!=='Tab'||!$('sidebar').classList.contains('open'))return;
  const controls=[...$('sidebar').querySelectorAll('a[href],button:not(:disabled)')].filter(el=>el.getClientRects().length&&!el.hidden);
  const first=controls[0],last=controls.at(-1);
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
});

function checkChoices(name,items,selected=[]){return `<div class="permission-choices">${items.map(([id,text])=>`<label class="check-label"><input type="checkbox" name="${name}" value="${esc(id)}" ${selected.includes(id)?"checked":""}>${esc(text)}</label>`).join("")||'<p class="muted">目前沒有可選項目。</p>'}</div>`;}
function dispatchScopeForm(id){const s=(state.settings.dispatch_scopes||[]).find(s=>s.scope_id===id)||{company:management.org||state.organizations[0]?.org_id||"",name:"",kind:"department",department:"",recipient_ids:[],active:1};modal(id?"編輯發送範圍":"新增發送範圍",`<form id="dispatch-scope-form" data-id="${esc(id||"")}"><div class="form-grid">${selectField("所屬組織","company",oaOrganizationOptions(),selectedWorkspace()?.org_id||s.company)}${field("範圍名稱","name",s.name,'required maxlength="80" placeholder="例如：北區業務、網站改版專案"')}${selectField("範圍類型","kind",[["department","部門"],["project","專案"],["group","LINE 群組"]],s.kind)}${field("部門名稱（部門範圍必填）","department",s.department,'maxlength="60"')}<label class="check-label full"><input name="active" type="checkbox" ${s.active?"checked":""}>啟用範圍</label></div><fieldset class="permission-fieldset"><legend>範圍內聯絡對象</legend><div id="scope-recipient-options"></div></fieldset><p class="callout">部門會包含同組織、同部門分類的聊天室。專案可選多個對象；LINE 群組只能選一個。停用範圍會影響尚未執行的預約。</p><div class="form-actions"><button class="btn primary" type="submit">儲存範圍</button></div></form>`);const form=$("dispatch-scope-form");form.classList.add("management-form");if(id){form.elements.company.disabled=true;form.insertAdjacentHTML('beforeend',`<input type="hidden" name="company" value="${esc(s.company)}">`);}function choices(selected=[]){const company=id?s.company:form.elements.company.value,kind=form.elements.kind.value;$("scope-recipient-options").innerHTML=kind==="department"?'<p class="muted">依上方部門名稱自動比對，不需逐筆選人。</p>':checkChoices('recipient_ids',state.contacts.filter(r=>r.company===company&&(kind!=="group"||r.kind!=="user")).map(r=>[r.recipient_id,label(r)+(r.active?"":"（已停用）")]),selected);}choices(s.recipient_ids);form.addEventListener('change',e=>{if(['company','kind'].includes(e.target.name))choices();});}
function senderGrantForm(id){const m=state.memberships.find(m=>m.email+"|"+m.org_id===id);if(!m)return;const g=(state.settings.sender_grants||[]).find(g=>g.email===m.email&&g.company===m.org_id)||{scope_ids:[],report_ids:[]};modal("設定發送授權",`<form id="sender-grant-form" class="management-form"><input type="hidden" name="email" value="${esc(m.email)}"><input type="hidden" name="company" value="${esc(m.org_id)}"><p>${esc(m.email)} · ${esc(m.name)}</p><p class="mg-grant-summary" id="mg-grant-summary" role="status"></p><fieldset class="permission-fieldset"><legend>可用模組</legend>${[['messaging','訊息發送與預約'],['reports','報告中心'],['weather','個人天氣模組（組織也須啟用）']].map(([key,text])=>`<label class="check-label"><input type="checkbox" name="${key}" ${g[key]?"checked":""}>${text}</label>`).join('')}</fieldset><fieldset class="permission-fieldset"><legend>可發送對象範圍（可複選）</legend><p class="mg-help">先在組織的「發送範圍」建立部門、專案或群組，再回來勾選。</p>${checkChoices('scope_ids',(state.settings.dispatch_scopes||[]).filter(s=>s.company===m.org_id).map(s=>[s.scope_id,s.name+(s.active?'':'（已停用）')]),g.scope_ids)}</fieldset><fieldset class="permission-fieldset"><legend>可查看與發送的報告（可複選）</legend>${checkChoices('report_ids',(state.settings.report_sources||[]).filter(r=>r.company===m.org_id||r.report_id==='weather').map(r=>[r.report_id,r.title]),g.report_ids)}</fieldset><p class="callout">報告與收件範圍分別授權。勾選報告不會開放全部聯絡對象；同時仍須符合報告本身的部門／個人限制。只發文字或自訂圖片時，可不選報告。取消模組或範圍會在預約執行前重新檢查。</p><div class="form-actions"><button class="btn primary" type="submit">儲存授權</button></div></form>`);const form=$("sender-grant-form");const summarize=()=>{$("mg-grant-summary").textContent=`已選 ${form.querySelectorAll('[name="scope_ids"]:checked').length} 個範圍、${form.querySelectorAll('[name="report_ids"]:checked').length} 份報告。${form.elements.messaging.checked?"儲存後套用授權；組織也須開放模組。":"尚未勾選訊息發送，此人員不能發送。"}`;};form.addEventListener("change",summarize);summarize();}

function oaOrganizationOptions(){const w=selectedWorkspace();return w&&lineUI.registry?[[w.org_id,w.name]]:organizationOptions();}

// Read-only values get a copy shortcut. One observer covers every render (modals, OA cards); data-copy="off" opts out.
function addCopyButtons(){
  document.querySelectorAll('input[readonly]:not([type=hidden]):not([data-copy-ready]):not([data-copy="off"])').forEach(input=>{
    input.dataset.copyReady="1";input.tabIndex=-1;
    const name=(input.closest("label")?.firstChild?.textContent||"").replace(/（唯讀）/,"").trim()||"內容";
    const wrap=document.createElement("span");wrap.className="copy-field";input.replaceWith(wrap);wrap.append(input);
    wrap.insertAdjacentHTML("beforeend",`<button type="button" class="copy-button" data-label="複製${esc(name)}" aria-label="複製${esc(name)}" title="複製">${icon("copy")}</button><span class="copy-status" role="status"></span>`);
  });
}
new MutationObserver(addCopyButtons).observe(document.body,{childList:true,subtree:true});addCopyButtons();
document.addEventListener("click",async event=>{
  const b=event.target.closest(".copy-button");if(!b)return;
  event.preventDefault();
  const input=b.parentElement.querySelector("input"),status=b.parentElement.querySelector(".copy-status");
  try{await navigator.clipboard.writeText(input.value);}
  catch(_){input.focus();input.select();status.textContent="已選取，請按 Ctrl / ⌘ C 複製。";return;}
  b.innerHTML=icon("check");b.classList.add("copied");b.setAttribute("aria-label","已複製");status.textContent="已複製";
  clearTimeout(b.copyTimer);b.copyTimer=setTimeout(()=>{b.innerHTML=icon("copy");b.classList.remove("copied");b.setAttribute("aria-label",b.dataset.label);status.textContent="";},1600);
});

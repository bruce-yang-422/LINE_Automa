"use strict";
// Rendering and interaction only. Existing authenticated APIs enforce all permissions.
const management = {org:"",tab:"people",orgQuery:"",peopleQuery:"",accountQuery:"",role:"all"};
// 權限與角色規格第 2 節：畫面名稱旁附一行權限說明。
const roleDescriptions = {
  platform_admin:"建置平台、建立組織與管理員帳號、設定 LINE OA；對客戶的營運內容只能閱讀。",
  org_admin:"管理本組織的所有 OA 與人員；可對話、發送、處理案件與記事。",
  operator:"可閱讀並回覆被授權 OA 的對話、發送訊息、處理案件與記事。",
  collaborator:"可處理案件與記事，不能傳送訊息。"
};
function mgCurrentOrg(){
  if(!state.organizations.some(o=>o.org_id===management.org))management.org=state.organizations.find(o=>o.active)?.org_id||state.organizations[0]?.org_id||"";
  return state.organizations.find(o=>o.org_id===management.org);
}
function mgGrant(m){return (state.settings.sender_grants||[]).find(g=>g.email===m.email&&g.organization_id===m.org_id);}
function mgNeedsGrant(m){const g=mgGrant(m);return m.active&&m.role==="operator"&&(!g?.messaging||!g.scope_ids.some(id=>(state.settings.dispatch_scopes||[]).some(s=>s.scope_id===id&&s.active&&s.organization_id===m.org_id)));}
function mgUser(email){return state.settings.users.find(u=>u.email===email);}
function mgMatches(query,...values){return values.join(" ").toLowerCase().includes(query.trim().toLowerCase());}
function mgTools(id,labelText,value,placeholder){return `<label>${labelText}<input id="${id}" type="search" value="${esc(value)}" placeholder="${placeholder}"></label>`;}
function mgEmpty(title,text,action="",labelText=""){return `<div class="mg-empty"><strong>${title}</strong><p>${text}</p>${action?button(labelText,action,"primary"):""}</div>`;}
function mgStats(items){return `<div class="mg-summary">${items.map(([n,t])=>`<div class="mg-stat"><strong>${n}</strong><span>${t}</span></div>`).join("")}</div>`;}
function mgMembers(o){
  const members=state.memberships.filter(m=>m.org_id===o.org_id);
  const rows=members.filter(m=>mgMatches(management.peopleQuery,m.email,mgUser(m.email)?.display_name,m.department));
  return `<div class="mg-tools">${mgTools("mg-people-search","搜尋組織人員",management.peopleQuery,"姓名、Email 或部門")}${button("加入既有帳號","new-membership")}</div>
    <p class="mg-note">操作人員與協作人員由該組織的管理員在「人員與權限」建立；這裡只調整角色與客製模組授權。</p>
    ${rows.map(m=>{const u=mgUser(m.email),key=esc(m.email+"|"+m.org_id),enabled=m.active&&u?.active;return `<div class="mg-row"><div class="mg-person"><span class="avatar" aria-hidden="true">${esc((u?.display_name||m.email).slice(0,1))}</span><div><strong>${esc(u?.display_name||m.email)}</strong><p>${esc(m.email)}</p><p>${esc(m.department||"未分部門")}</p><div class="mg-tags">${badge(roleName(m.role))}${badge(!enabled?"已停用":mgNeedsGrant(m)?"待設定發送授權":"已設定",mgNeedsGrant(m)?"warn":"")}</div></div></div><div class="mg-actions">${m.role==="operator"?button("設定授權","edit-sender-grant","small",`data-id="${key}"`):""}${button("編輯角色","edit-membership","small",`data-id="${key}"`)}</div></div>`;}).join("")||mgEmpty(members.length?"沒有符合的人員":"加入第一位後台人員",members.length?"試試其他姓名或 Email。":"先建立登入帳號，再依工作需要授予角色。")}`;
}
function mgAdmins(o){
  const rows=(state.settings.users||[]).filter(u=>u.organization_id===o.org_id&&u.role==="org_admin");
  return `<div class="mg-head"><div><h3>管理員</h3><p>建立後按「設定登入」產生一次性登入設定連結交給本人；同事帳號由管理員自行建立。</p></div>${button("新增管理員","new-org-admin","primary",`data-id="${esc(o.org_id)}"`)}</div>
    ${rows.map(u=>`<div class="mg-row"><div class="mg-person"><span class="avatar" aria-hidden="true">${esc((u.display_name||u.email).slice(0,1))}</span><div><strong>${esc(u.display_name||u.email)}</strong><p>${esc(u.email)}</p><div class="mg-tags">${badge(roleName(u.role))}${!u.active?badge("已停用"):""}</div></div></div><div class="mg-actions">${button("編輯","edit-account","small",`data-id="${esc(u.email)}"`)}${u.active?button("設定登入","unused","small",`data-security="invite" data-email="${esc(u.email)}"`)+button("撤銷登入","unused","text small",`data-security="revoke" data-email="${esc(u.email)}"`):""}</div></div>`).join("")||mgEmpty("尚未建立管理員","每個組織至少需要一位管理員，才能自行新增同事與設定 OA。","new-org-admin","新增管理員",`data-id="${esc(o.org_id)}"`)}`;
}
// 平台管理員帳號：在權限規格第 9 節的首次設定與 create_admin.py 完成前，保留在此設定登入與停用。
function mgPlatformAdmins(){
  const rows=(state.settings.users||[]).filter(u=>u.role==="platform_admin");
  return `<details class="mg-card"><summary>平台管理員帳號 · ${rows.length} 位</summary><div class="mg-body">${rows.map(u=>`<div class="mg-row"><div class="mg-person"><span class="avatar" aria-hidden="true">${esc((u.display_name||u.email).slice(0,1))}</span><div><strong>${esc(u.display_name||u.email)}</strong><p>${esc(u.email)}</p><div class="mg-tags">${badge(roleName(u.role))}${!u.active?badge("已停用"):""}</div></div></div><div class="mg-actions">${button("編輯","edit-account","small",`data-id="${esc(u.email)}"`)}${u.active?button("設定登入","unused","small",`data-security="invite" data-email="${esc(u.email)}"`)+button("撤銷登入","unused","text small",`data-security="revoke" data-email="${esc(u.email)}"`):""}</div></div>`).join("")||'<p class="mg-note">尚無平台管理員帳號。</p>'}<p class="mg-note">新增平台管理員：按「新增管理員」後在角色選「平台管理員」。</p></div></details>`;
}
function mgScopes(o){
  const rows=(state.settings.dispatch_scopes||[]).filter(s=>s.organization_id===o.org_id);
  return `<div class="mg-head"><div><h3>發送範圍</h3><p>先把聯絡對象分成部門、專案或群組，再授權給人員。</p></div>${button("新增範圍","new-dispatch-scope","primary")}</div>${rows.map(s=>`<div class="mg-row"><div><strong>${esc(s.name)}</strong><p class="subtitle">${{department:"部門",project:"專案",group:"LINE 群組"}[s.kind]} · ${s.department?esc(s.department):s.recipient_ids.length+" 個對象"} · ${s.active?"啟用":"停用"}</p></div>${button("編輯","edit-dispatch-scope","small",`data-id="${esc(s.scope_id)}"`)}</div>`).join("")||mgEmpty("尚未設定發送範圍","例如：業務部、網站改版專案、家人群組。建立後可授權給多位操作人員。")}`;
}
function organizationsPage(){
  const o=mgCurrentOrg(),visible=state.organizations.filter(x=>mgMatches(management.orgQuery,x.name,orgKinds[x.kind]));
  const members=o?state.memberships.filter(m=>m.org_id===o.org_id):[];
  return heading("組織管理","先選擇組織，再設定人員、發送範圍與可用功能。",button("新增組織","new-organization","primary"))+`<div class="management">
    <div class="mg-guide"><div><strong>1 · 建立組織</strong><p>公司、社團、家庭都能獨立管理。</p></div><div><strong>2 · 加入後台人員</strong><p>選擇角色；只在 LINE 收訊的聯絡對象不用建帳號。</p></div><div><strong>3 · 指定發送範圍</strong><p>授權報告和對象，完成後即可發送。</p></div></div>
    <label class="mg-mobile-org">目前管理的組織<select id="mg-mobile-org">${options(state.organizations.map(x=>[x.org_id,x.name+(x.active?"":"（已停用）")]),o?.org_id||"")}</select></label>
    <div class="mg-shell"><aside class="mg-card" aria-label="組織清單"><div class="mg-body"><h2>我的組織 <small>${state.organizations.length}</small></h2><div class="mg-tools">${mgTools("mg-org-search","搜尋組織",management.orgQuery,"輸入組織名稱")}</div></div><div class="mg-picker">${visible.map(x=>`<button class="mg-org" data-action="mg-org" data-id="${esc(x.org_id)}" aria-pressed="${x.org_id===o?.org_id}"><strong>${esc(x.name)}</strong><small>${esc(orgKinds[x.kind]||"其他")} · ${x.active?"啟用":"停用"}</small></button>`).join("")||'<p class="mg-note">沒有符合的組織。</p>'}</div></aside>
    <section class="mg-card">${o?`<div class="mg-head"><div><h2>${esc(o.name)}</h2><p>${esc(orgKinds[o.kind]||"其他")} · ${o.active?"組織已啟用":"組織已停用"}</p></div>${button("編輯組織","edit-organization","small",`data-id="${esc(o.org_id)}"`)}</div><div class="mg-body">${mgStats([[members.filter(m=>m.active&&mgUser(m.email)?.active).length,"位後台人員"],[members.filter(mgNeedsGrant).length,"位待設定授權"],[(state.settings.dispatch_scopes||[]).filter(s=>s.organization_id===o.org_id&&s.active).length,"個啟用範圍"]])}</div>
      <div class="mg-tabs" role="group" aria-label="組織設定分類">${[["admins","管理員帳號"],["people","人員與權限"],["scopes","發送範圍"],["modules","可用模組"]].map(([id,t])=>`<button data-action="mg-tab" data-id="${id}" aria-pressed="${management.tab===id}">${t}</button>`).join("")}</div><div class="mg-body">${management.tab==="admins"?mgAdmins(o):management.tab==="scopes"?mgScopes(o):management.tab==="modules"?`<h3>這個組織可以使用什麼？</h3>${[["reports_enabled","報告中心","查看並分配組織報告"],["messaging_enabled","訊息發送與預約","發送通知、圖片與預約訊息"],["weather_enabled","個人天氣模組","額外授權的天氣報告"]].map(([k,t,d])=>`<div class="mg-row"><div><strong>${t}</strong><p class="subtitle">${d}</p></div>${badge(o[k]?"已開放":"未開放")}</div>`).join("")}<p class="mg-note">模組開放後，操作人員仍需要個別授權。</p>`:mgMembers(o)}</div>`:mgEmpty("建立第一個組織","先建立公司、社團或家庭，接著就能加入人員。","new-organization","建立組織")}</section></div>
    ${mgPlatformAdmins()}
    <details class="mg-card"><summary>最近操作 · ${state.events.length} 筆</summary><div class="mg-body">${state.events.map(e=>`<div class="activity-row">${esc(e.detail)}<small>${esc(e.actor)} · ${when(e.created_at)}</small></div>`).join("")||'<p>尚無操作紀錄。</p>'}</div></details></div>`;
}
function mgToggle(name,title,detail,checked){return `<label class="mg-toggle"><input type="checkbox" name="${name}" ${checked?"checked":""}><span><strong>${title}</strong><small>${detail}</small></span></label>`;}
function mgRoleHelp(form){const help=form.querySelector('.mg-role-help');if(help)help.textContent=roleDescriptions[form.elements.role.value]||"";}
function mgAttach(form){form.classList.add('management-form');mgRoleHelp(form);form.addEventListener('change',()=>mgRoleHelp(form));}
function organizationForm(id){
  if(!superAdmin())return organizationProfileForm(id);
  const o=state.organizations.find(x=>x.org_id===id)||{name:"",kind:"company",active:1,reports_enabled:1,messaging_enabled:1,weather_enabled:0,weather_image_path:""};
  modal(id?"編輯組織":"新增組織",`<form id="organization-form" data-id="${esc(id||"")}" class="management-form"><section class="mg-section"><h3>基本資料</h3><div class="form-grid">${field("組織名稱","name",o.name,'required maxlength="80" placeholder="例如：星河科技、我的家庭"')}${selectField("組織類型","kind",Object.entries(orgKinds),o.kind)}</div></section><section class="mg-section"><h3>開放哪些功能？</h3><p>先開放組織需要的模組，再設定人員可用的範圍。</p>${mgToggle('reports_enabled','報告中心','查看與分配報告',o.reports_enabled)}${mgToggle('messaging_enabled','訊息發送與預約','通知、圖片與定時發送',o.messaging_enabled)}${mgToggle('weather_enabled','天氣模組（客製）','選用功能，預設不開放；啟用時須填入圖片來源',o.weather_enabled)}${field("天氣圖片 PNG 路徑（伺服器上）","weather_image_path",o.weather_image_path||"",'maxlength="1024" placeholder="D:\\Reports\\weather_report.png"')}</section>${mgToggle('active','啟用組織','停用後無法切換進入，預約發送會重新檢查權限。',o.active)}<div class="form-actions"><button class="btn primary" type="submit">儲存組織</button></div></form>`);
}
// 管理員只能修改本組織名稱與類型；啟用狀態與模組由平台管理員在「組織」設定。
function organizationProfileForm(id){
  const o=state.organizations.find(x=>x.org_id===id)||{name:"",kind:"company"};
  modal("編輯組織資料",`<form id="org-settings-form" class="management-form"><section class="mg-section"><h3>基本資料</h3><div class="form-grid">${field("組織名稱","name",o.name,'required maxlength="80"')}${selectField("組織類型","kind",Object.entries(orgKinds),o.kind)}</div><p class="subtitle">可用模組與啟用狀態由平台管理員設定。</p></section><div class="form-actions"><button class="btn primary" type="submit">儲存</button></div></form>`);
}
function accountForm(email,preset={}){
  const u=state.settings.users.find(x=>x.email===email)||{email:"",display_name:"",role:"org_admin",organization_id:management.org,department:"",active:1,...preset};
  const roleChoices=[["org_admin","管理員"],["platform_admin","平台管理員"]];if(!roleChoices.some(([r])=>r===u.role))roleChoices.push([u.role,roleName(u.role)]);
  modal(email?"編輯登入帳號":"新增登入帳號",`<form id="account-form"><section class="mg-section"><h3>1 · 這位人員是誰？</h3><div class="form-grid">${field("登入 Email","email",u.email,`type="email" required ${email?"readonly":""} placeholder="name@example.com"`)}${field("顯示名稱","display_name",u.display_name,'maxlength="80" placeholder="方便同事辨認的名字"')}</div></section><section class="mg-section"><h3>2 · 他需要做什麼？</h3><div class="form-grid">${selectField("角色","role",roleChoices,u.role)}${selectField("主要組織（平台管理員可留空）","organization_id",organizationOptions(),u.organization_id)}</div><p class="mg-role-help"></p></section><details><summary>進階資料：部門（選填）</summary><div class="form-grid">${field("部門","department",u.department,'maxlength="60"')}</div></details>${mgToggle('active','啟用帳號','停用後將無法登入後台。',u.active)}<p class="mg-help">儲存後按「設定登入」產生一次性登入設定連結交給本人。</p><div class="form-actions"><button class="btn primary" type="submit">儲存帳號</button></div></form>`);mgAttach($('account-form'));
}
function membershipForm(id){
  const m=state.memberships.find(x=>x.email+"|"+x.org_id===id)||{email:"",org_id:management.org,role:"operator",department:"",active:1};
  modal("設定組織成員",`<form id="membership-form"><section class="mg-section"><h3>把既有帳號加入組織</h3><p>同一人可以加入多個組織，各自使用不同角色。</p><div class="form-grid">${selectField("登入帳號","email",[["","選擇既有帳號"],...state.settings.users.filter(u=>u.role!=="platform_admin"||u.email===m.email).map(u=>[u.email,(u.display_name?u.display_name+" · ":"")+u.email])],m.email)}${selectField("組織","org_id",state.organizations.map(o=>[o.org_id,o.name]),m.org_id)}${selectField("此組織的角色","role",[["operator","操作人員"],["org_admin","管理員"]],m.role)}${field("部門／分組","department",m.department,'maxlength="80"')}</div><p class="mg-role-help"></p></section>${mgToggle('active','啟用此成員資格','只影響這個組織，不會刪除登入帳號。',m.active)}<div class="form-actions"><button class="btn primary" type="submit">儲存成員資格</button></div></form>`);
  const form=$('membership-form');mgAttach(form);form.elements.email.required=true;
  if(id)for(const k of ['email','org_id']){form.elements[k].disabled=true;form.insertAdjacentHTML('beforeend',`<input type="hidden" name="${k}" value="${esc(m[k])}">`);}
}
function managementAction(action,id){
  if(!action.startsWith('mg-'))return false;
  if(action==='mg-org'){management.org=id;management.peopleQuery="";render();}
  else if(action==='mg-tab'){management.tab=id;render();}
  else if(action==='mg-person-org'){management.org=id;management.tab='people';management.peopleQuery="";navigate('organizations');}
  document.querySelector(`[data-action="${action}"][data-id="${CSS.escape(id)}"]`)?.focus({preventScroll:true});
  return true;
}
function managementAfterSave(form,values){
  if(form.id==='organization-form'){
    management.org=form.dataset.id||state.organizations.find(o=>o.name===values.name.trim())?.org_id||management.org;
    management.orgQuery='';management.tab='people';management.peopleQuery='';
  } else if(form.id==='membership-form'){
    management.org=values.org_id;management.tab='people';management.peopleQuery='';
  } else if(form.id==='account-form'&&values.organization_id){
    management.org=values.organization_id;management.tab=values.role==='org_admin'?'admins':'people';management.peopleQuery='';
  }
}
document.addEventListener('input',event=>{
  const key={'mg-org-search':'orgQuery','mg-people-search':'peopleQuery','mg-account-search':'accountQuery'}[event.target.id];if(!key)return;
  management[key]=event.target.value;const id=event.target.id,start=event.target.selectionStart;render();$(id).focus();$(id).setSelectionRange(start,start);
});
document.addEventListener('change',event=>{if(event.target.id==='mg-role-filter'){management.role=event.target.value;render();$('mg-role-filter').focus();}});
document.addEventListener('change',event=>{if(event.target.id==='mg-mobile-org'){management.org=event.target.value;management.peopleQuery='';render();$('mg-mobile-org').focus();}});

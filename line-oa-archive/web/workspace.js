"use strict";
// These views use only data returned by the authenticated, scoped APIs.
const workspaceUI={contactDetail:"",scheduleFilter:"scheduled"};

function workspaceHeader(){
  if(!state.contacts.some(r=>r.recipient_id===workspaceUI.contactDetail))workspaceUI.contactDetail="";
  const user=state.session?.user;
  const context=document.getElementById("workspace-context-name");
  const ch = typeof selectedOA === "function" ? selectedOA() : null;
  if(context) context.textContent=ch ? ch.name : (superAdmin()?"平台管理":orgName(user?.organization_id));
  const kind = document.getElementById("workspace-context-kind");
  const orgId = ch ? (ch.org_id || ch.workspace_id?.replace(/^o:/, "") || user?.organization_id) : user?.organization_id;
  if(kind) kind.textContent = ch ? (orgName(orgId) || "組織工作空間") : (superAdmin() ? "跨組織" : roleName(state.session?.role));
  const wrap = document.getElementById("workspace-context");
  // OA 切換器只給在 OA 內工作的人；平台管理員不進入 OA 營運畫面。
  if(wrap) wrap.hidden=superAdmin();
  if(document.getElementById("organization-select")) document.getElementById("organization-select").hidden=true;
}

function contactDetailPanel(){
  const r=state.contacts.find(r=>r.recipient_id===workspaceUI.contactDetail);
  if(!r)return "";
  const tags=r.tags||[];
  const tagsHtml=tags.length?tags.map(t=>tagBadge(t)).join(" "):'<span class="muted">無標籤</span>';
  const fullWorkPhone=[r.work_phone, r.work_phone_ext ? '分機 '+r.work_phone_ext : ''].filter(Boolean).join(' ');
  const fullAddress=[r.postal_code, r.address].filter(Boolean).join(' ');
  return `<aside class="detail-panel" id="contact-detail" aria-labelledby="contact-detail-title" tabindex="-1">
    <div class="detail-heading">
      <div>
        <h2 id="contact-detail-title">${esc(label(r))}</h2>
        <p class="subtitle">${r.kind==="user"?"個人聊天室":"LINE 群組"}</p>
      </div>
      ${button(icon("close"),"close-contact-detail","icon-button",'aria-label="關閉聯絡對象詳情"')}
    </div>
    <div class="detail-body">
      ${person(r)}
      <div class="section-space">
        <h4 data-s="s1aae5cd">聯絡資訊</h4>
        <dl>
          <dt>對象類型</dt><dd>${contactTypeBadge(r.contact_type)}</dd>
          ${r.organization_name?`<dt>對方組織</dt><dd>${esc(r.organization_name)}</dd>`:""}
          ${r.job_title?`<dt>職稱</dt><dd>${esc(r.job_title)}</dd>`:""}
          ${r.phone?`<dt>聯絡電話</dt><dd><a href="tel:${esc(r.phone)}">${esc(r.phone)}</a></dd>`:""}
          ${fullWorkPhone?`<dt>公務電話</dt><dd>${esc(fullWorkPhone)}</dd>`:""}
          ${r.email?`<dt>Email</dt><dd><a href="mailto:${esc(r.email)}">${esc(r.email)}</a></dd>`:""}
          ${r.work_email?`<dt>公務 Email</dt><dd><a href="mailto:${esc(r.work_email)}">${esc(r.work_email)}</a></dd>`:""}
          ${fullAddress?`<dt>地址</dt><dd>${esc(fullAddress)}</dd>`:""}
          <dt>自訂名稱</dt><dd>${esc(r.custom_name||"尚未設定")}</dd>
          <dt>LINE 名稱</dt><dd>${esc(r.display_name||"尚未取得")}</dd>
          <dt>分類標籤</dt><dd class="contact-tags">${tagsHtml}</dd>
        </dl>
      </div>
      <div class="section-space">
        <h4 data-s="s1aae5cd">系統設定</h4>
        <dl>
          <dt>系統組織</dt><dd>${esc(r.organization_id?orgName(r.organization_id):"尚未設定")}</dd>
          <dt>系統部門</dt><dd>${esc(r.department||"尚未設定")}</dd>
          <dt>接收狀態</dt><dd>${badge(r.active?"可接收":"已停用",r.active?"good":"")}</dd>
          <dt>最近互動</dt><dd>${esc(when(r.last_seen))}</dd>
        </dl>
      </div>
      <div class="full section-space">
        <label class="field" data-s="sd982937"><strong>備忘筆記（內部）</strong></label>
        ${r.notes?`<div class="contact-notes-box">${esc(r.notes)}</div>`:'<p class="muted">尚未填寫備忘筆記</p>'}
      </div>
      <div class="chat-notes-box section-space">
        <div class="case-context-header">
          <strong>${icon("file")} 對話記事本（此 OA 聊天室）</strong>
          ${button(icon("plus")+"新增記事","new-chat-note","btn small",`data-id="${esc(r.recipient_id)}"`)}
        </div>
        <div id="chat-notes-list-container">
          ${renderChatNotesList(r.recipient_id)}
        </div>
      </div>
      <div class="case-context-box">
        <div class="case-context-header">
          <strong>${icon("file")} 關聯案件歷史</strong>
          ${button(icon("plus")+"建立案件","new-case-modal","btn small",`data-id="${esc(r.recipient_id)}"`)}
        </div>
        ${renderContactCases(r.recipient_id)}
      </div>
      <details data-s="s88b9d5c"><summary class="muted" data-s="se71ae94">查看聊天室識別資料</summary><p class="contact-id">${esc(r.recipient_id)}</p></details>
      <div class="detail-actions">
        ${button(icon("message")+"開啟聊天","open-chat-from-contact","primary",`data-id="${esc(r.recipient_id)}"`)}
        ${manager()?button("編輯聯絡對象","edit-contact","",`data-id="${esc(r.recipient_id)}"`):""}
      </div>
    </div>
  </aside>`;
}

window.DEFAULT_TAG_COLORS = window.DEFAULT_TAG_COLORS || {
  "急件優先": "#FF3B30",
  "待主管確認": "#FFCC00",
  "已報價": "#007AFF",
  "重要協議": "#5856D6",
  "需二次回訪": "#30B0C7",
  "現場勘查": "#FF9500",
  "交接待辦": "#34C759",
  "處理中": "#8E8E93"
};

function tagPillHtml(tagName){
  const found = (state.noteTags || []).find(t => t.name === tagName);
  let color = found?.color || DEFAULT_TAG_COLORS[tagName];
  if(!color){
    const palette = ["#007AFF","#34C759","#FF9500","#AF52DE","#FF2D55","#5856D6","#30B0C7","#FF3B30","#FFCC00","#8E8E93"];
    let hash = 0;
    for(let i=0; i<tagName.length; i++) hash = (hash << 5) - hash + tagName.charCodeAt(i);
    color = palette[Math.abs(hash) % palette.length];
  }
  const bg = color.length === 7 ? color + "20" : "rgba(0,122,255,0.14)";
  const border = color.length === 7 ? color + "48" : "rgba(0,122,255,0.3)";
  return `<span class="apple-pill" data-color="${esc(color)}" style="background-color:${esc(bg)}!important;color:${esc(color)}!important;border-color:${esc(border)}!important;">${esc(tagName)}</span>`;
}

const chatWorkViews = new Map();
function chatWorkView(recipient){
  if(!chatWorkViews.has(recipient)) chatWorkViews.set(recipient,{tab:"notes",query:"",filter:"all",sort:"newest",page:1});
  return chatWorkViews.get(recipient);
}
function renderChatWorkPanel(recipient){
  const view=chatWorkView(recipient), notes=state.chatNotes?.get(recipient)||[];
  const cases=(state.cases||[]).filter(c=>c.case_subject_id===recipient);
  const isNotes=view.tab==="notes", all=isNotes?notes:cases;
  const pending=r=>isNotes?r.status!=="completed":r.status!=="closed";
  const query=view.query.trim().toLocaleLowerCase();
  const rows=all.filter(r=>(view.filter==="all" || (view.filter==="pending"?pending(r):view.filter==="completed"?!pending(r):Boolean(r.is_pinned))) &&
    [r.title,r.content,r.description,r.category_name,r.category,...(r.tags||[])].filter(Boolean).join(" ").toLocaleLowerCase().includes(query));
  rows.sort((a,b)=>Number(Boolean(b.is_pinned))-Number(Boolean(a.is_pinned)) || (view.sort==="oldest"?1:-1)*String(a.created_at||a.updated_at||"").localeCompare(String(b.created_at||b.updated_at||"")));
  const pages=Math.max(1,Math.ceil(rows.length/12)); view.page=Math.min(view.page,pages);
  const visible=rows.slice((view.page-1)*12,view.page*12);
  const overdue=cases.filter(c=>c.status!=="closed" && c.due_date && String(c.due_date).slice(0,10)<new Date().toLocaleDateString("sv-SE")).length;
  return `<section class="chat-work-panel chat-info-card" data-recipient="${esc(recipient)}" aria-label="對話工作紀錄">
    <div class="chat-work-summary">
      <div class="chat-summary-card"><span class="chat-summary-icon">${icon("message")}</span><div><span>對話記事</span><strong>${notes.length}</strong><small>${notes.filter(n=>n.status!=="completed").length} 個待處理</small></div></div>
      <div class="chat-summary-card cases"><span class="chat-summary-icon">${icon("folder")}</span><div><span>關聯案件</span><strong>${cases.length}</strong><small>${cases.filter(c=>c.status!=="closed").length} 個進行中</small></div></div>
      <div class="chat-summary-card overdue ${overdue?'chat-work-alert':''}"><span class="chat-summary-icon">${icon("alert")}</span><div><span>逾期案件</span><strong>${overdue}</strong><small>${overdue?"需要處理":"無逾期案件"}</small></div></div>
    </div>
    <div class="chat-work-tabs" role="tablist" aria-label="工作紀錄類型">${[["notes","對話記事",notes.length],["cases","關聯案件",cases.length]].map(([id,text,count])=>`<button type="button" role="tab" id="chat-work-tab-${id}" aria-selected="${view.tab===id}" aria-controls="chat-work-results" data-action="chat-work-tab" data-id="${id}" class="${view.tab===id?"active":""}">${text} <span>${count}</span></button>`).join("")}</div>
    <div class="chat-work-controls"><div class="chat-work-search-row"><label class="search-field">${icon("search")}<input id="chat-work-search" type="search" value="${esc(view.query)}" placeholder="搜尋標題、內容或標籤" aria-label="搜尋${isNotes?"記事":"案件"}"></label>${button(icon("plus")+"新增",isNotes?"new-chat-note":"new-case-modal","small",`data-id="${esc(recipient)}" aria-label="${isNotes?"新增記事":"建立案件"}"`)}</div>
    <div class="chat-work-filters" role="group" aria-label="篩選狀態">${[["all","全部",all.length],["pending","待處理",all.filter(pending).length],["completed",isNotes?"已完成":"已結案",all.filter(r=>!pending(r)).length],...(isNotes?[["pinned","已置頂",all.filter(r=>r.is_pinned).length]]:[])].map(([id,text,count])=>`<button type="button" data-action="chat-work-filter" data-id="${id}" aria-pressed="${view.filter===id}" class="${view.filter===id?"active":""}">${text} <span>${count}</span></button>`).join("")}<select id="chat-work-sort" aria-label="排序方式"><option value="newest" ${view.sort==="newest"?"selected":""}>最新建立</option><option value="oldest" ${view.sort==="oldest"?"selected":""}>最早建立</option></select></div></div>
    <div class="chat-work-results" id="chat-work-results" role="tabpanel" aria-labelledby="chat-work-tab-${view.tab}" tabindex="0">${visible.length?(isNotes?renderChatNotesList(recipient,visible):renderContactCases(recipient,visible)):`<div class="chat-work-empty">${icon(isNotes?"file":"folder")}<strong>${all.length?"沒有符合的紀錄":"尚無"+(isNotes?"記事":"案件")}</strong><span>${all.length?"調整搜尋或篩選條件。":"點選新增，記錄此對話的重要事項。"}</span></div>`}</div>
    <div class="chat-work-pagination"><span role="status">${rows.length?`${(view.page-1)*12+1}–${Math.min(view.page*12,rows.length)} / ${rows.length} 筆`:"0 筆"}</span><div>${isNotes?button(icon("trash"),"view-chat-notes-trash","small text",`data-recipient="${esc(recipient)}" title="回收筒" aria-label="記事回收筒"`):""}<button type="button" class="btn small text" data-action="chat-work-page" data-id="${view.page-1}" ${view.page===1?"disabled":""} aria-label="上一頁">‹</button><span>${view.page} / ${pages}</span><button type="button" class="btn small text" data-action="chat-work-page" data-id="${view.page+1}" ${view.page===pages?"disabled":""} aria-label="下一頁">›</button></div></div>
  </section>`;
}
function refreshChatWorkPanel(){
  const panel=document.querySelector(".chat-work-panel");
  if(panel) panel.outerHTML=renderChatWorkPanel(panel.dataset.recipient);
}

function sidebarThumbnail(content){
  const match=String(content||'').match(/!\[[^\]]*\]\((https?:\/\/[^\s)]+|\/api\/[^\s)]+)(?:\s+"[^"]*")?\)/);
  return match?`<img class="sidebar-thumbnail" src="${esc(match[1])}" alt="內容圖片" loading="lazy">`:"";
}
function sidebarRecordDate(value){
  const date=new Date(value||'');
  if(Number.isNaN(date.getTime()))return '—';
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);
  const part=name=>parts.find(p=>p.type===name)?.value||'';
  return `${part('month')}/${part('day')} ${part('hour')}:${part('minute')}`;
}
function renderSidebarGroups(records,isCase=false){
  const groups=new Map();
  for(const record of records){
    const date=new Date(record.created_at||record.updated_at||'');
    const title=record.is_pinned?'已釘選':Number.isNaN(date.getTime())?'未註明日期':`${date.getFullYear()}年 ${date.getMonth()+1}月`;
    if(!groups.has(title))groups.set(title,[]);
    groups.get(title).push(record);
  }
  const recipient=records[0]?.recipient_id||records[0]?.case_subject_id;
  const collapsed=recipient?(chatWorkView(recipient).collapsedGroups||{}):{};
  return `<div class="en-card-list">${[...groups].map(([title,rows])=>`<details class="chat-record-group ${title==='已釘選'?'pinned-group':''}" data-record-group="${esc(title)}" data-recipient="${esc(recipient||'')}" ${collapsed[title]?'':'open'}><summary>${icon(title==='已釘選'?'pin':'calendar')}<strong>${esc(title)}</strong><span>(${rows.length})</span><span class="group-chevron">${icon('chevron-down')}</span></summary>${rows.map(r=>renderSidebarSummary(r,isCase)).join('')}</details>`).join('')}</div>`;
}
function renderSidebarSummary(record,isCase=false){
  const id=isCase?record.case_id:record.note_id, content=isCase?record.description:record.content;
  const template=document.createElement('template');
  template.innerHTML=isCase?renderCaseContent(record):renderNoteContent(record);
  template.content.querySelectorAll('img,pre').forEach(el=>el.remove());
  const plain=(template.content.textContent||'').replace(/\s+/g,' ').trim();
  const thumbnail=sidebarThumbnail(content);
  const recipient=isCase?record.case_subject_id:record.recipient_id;
  const selected=chatWorkView(recipient).selected===id;
  const tags=isCase?[record.category,...(record.tags||[])]:[record.category_name,...(record.tags||[])];
  const completed=isCase?record.status==='closed':record.status==='completed';
  const status=isCase?(caseStatusNames[record.status]||'待處理'):(completed?'已完成':'待處理');
  const tone=completed?'completed':isCase&&record.status==='processing'?'processing':'pending';
  return `<article class="${isCase?'case-item':'chat-note-item'} evernote-summary ${selected?'selected':''} ${record.is_pinned?'pinned':''} ${thumbnail?'with-thumbnail':''}" ${isCase?'data-case-preview':'data-note-preview'}="${esc(id)}" tabindex="0" aria-label="${esc(record.title||'記事')}，雙擊或按 Enter 預覽">
    ${thumbnail}<div class="en-card-main"><div class="en-card-title"><span class="chat-record-icon">${icon(isCase?'folder':'message')}</span><span class="chat-card-title" title="${esc(record.title||'記事')}">${esc(record.title||'記事')}</span><time class="chat-note-time" title="${esc(when(record.created_at||record.updated_at))}">${esc(sidebarRecordDate(record.created_at||record.updated_at))}</time>${recordLockControl(record,isCase)}${!isCase && !state.preview && state.session?.role!=='platform_admin'?`<button type="button" class="chat-record-pin ${record.is_pinned?'active':''}" data-action="toggle-chat-note-pin" data-id="${esc(id)}" data-recipient="${esc(recipient)}" title="${record.is_pinned?'取消釘選':'釘選記事'}" aria-label="${record.is_pinned?'取消釘選':'釘選記事'}" aria-pressed="${Boolean(record.is_pinned)}">${icon('pin')}</button>`:''}</div>
    <div class="en-card-excerpt ${isCase?'chat-case-description':'chat-note-content'}" ${isCase?`data-case-id="${esc(id)}"`:`id="chat-note-content-${esc(id)}"`}>${esc(plain||'尚無內容')}</div>
    <div class="en-card-meta"><span class="chat-record-status ${tone}">${esc(status)}</span>${isCase?`<span class="case-no-badge">${esc(record.case_no||'')}</span>`:''}${tags.filter(Boolean).slice(0,3).map(t=>`<span class="en-card-tag" title="${esc(t)}">${esc(t)}</span>`).join('')}</div></div>
  </article>`;
}
function renderChatNotesList(recipient_id, visibleNotes=null){
  const notes = visibleNotes || state.chatNotes?.get(recipient_id) || [];
  if(visibleNotes!==null)return renderSidebarGroups(notes);
  const orgLockPolicy = noteLockPolicy();
  const canManageTax = ["platform_admin", "org_admin", "operator"].includes(state.session?.role) && manager();

  if(!notes.length) {
    return `<div class="chat-notes-empty">
      <div class="chat-empty-icon">${icon("file")}</div>
      <p class="chat-empty-text">目前尚無對話記事，可點選上方「新增記事」記錄重要事項。</p>
      <div class="chat-empty-actions">
        <button type="button" class="btn text small" data-action="view-chat-notes-trash" data-recipient="${esc(recipient_id)}">${icon("trash")} 最近刪除 (30天內可還原)</button>
        ${canManageTax ? `<button type="button" class="btn text small" data-action="manage-notes-taxonomy">${icon("tag")} 分類與標籤治理</button>` : ''}
      </div>
    </div>`;
  }
  
  const pinned = notes.filter(n => n.is_pinned);
  const normal = notes.filter(n => !n.is_pinned);
  const ordered = [...pinned, ...normal];

  return `<div class="chat-notes-container">
    <div class="chat-notes-toolbar" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--line);">
      <small class="muted">共 ${notes.length} 則（置頂 ${pinned.length}/5）</small>
      <div style="display:flex;gap:4px;">
        ${canManageTax ? `<button class="btn text small" data-action="manage-notes-taxonomy" title="分類與標籤管理">${icon("tag")} 治理</button>` : ''}
        <button class="btn text small" data-action="view-chat-notes-trash" data-recipient="${esc(recipient_id)}" title="查看回收筒">${icon("trash")} 回收筒</button>
      </div>
    </div>
    ${ordered.map(n=>{
      const isCompleted = n.status === "completed";
      const isLocked = Boolean(n.is_locked);
      const canUnlock = orgLockPolicy === "collaborative" || (orgLockPolicy === "strict_admin" && manager()) || orgLockPolicy === "disabled";
      const canEdit = !recordReadonly(n);
      const isLongContent = Boolean(n.content && (n.content.length > 140 || (n.content.match(/\n/g) || []).length >= 3));
      
      return `
      <div data-note-preview="${esc(n.note_id)}" tabindex="0" aria-label="${esc(n.title || "記事")}，按 Enter 或雙擊預覽" class="chat-note-item sidebar-summary-card ${sidebarThumbnail(n.content)?'has-thumbnail':''} ${n.is_pinned?'pinned':''} ${isLocked?'locked':''} ${isCompleted?'completed':''}">
        <div class="chat-note-title-row">
          <span class="chat-card-title">${esc(n.title || "記事")}</span>
          <span class="muted chat-note-time">· ${when(n.created_at)}</span>
        </div>
        ${sidebarThumbnail(n.content)}
        <div class="chat-note-header">
          <div class="chat-note-badges">
            ${n.category_name ? `<span class="tax-item-category-badge" style="font-size:11px;padding:1.5px 7px;gap:3.5px;">${icon("folder")}<span>${esc(n.category_name)}</span></span>` : ''}
            ${n.is_pinned ? `<span class="apple-pill" style="background:rgba(234,179,8,.18);color:#b45309;border-color:rgba(234,179,8,.3);padding:2px 7px;font-size:11px;">${icon("pin")} 置頂</span>` : ''}
            ${recordLockControl(n)}
            ${isCompleted ? `<span class="apple-pill" style="background:rgba(34,197,94,.18);color:#16a34a;border-color:rgba(34,197,94,.3);padding:2px 7px;font-size:11px;">${icon("check")} 已完成</span>` : ''}
          </div>

        </div>
        <div class="chat-note-content-wrapper">
          <div class="chat-note-content ${isLongContent ? 'collapsed' : ''}" id="chat-note-content-${esc(n.note_id)}">${renderNoteContent(n)}</div>
          ${isLongContent ? `<button type="button" class="chat-note-expand-btn" data-action="toggle-chat-note-expand" data-id="${esc(n.note_id)}">${icon("chevron-down")} 展開全文</button>` : ''}
        </div>
        ${((n.tags && n.tags.length) || n.due_date || n.linked_case_id) ? `
          <div class="chat-note-footer">
            ${(n.tags || []).map(t => (typeof tagPillHtml === 'function' ? tagPillHtml(t) : `<span class="apple-pill">${esc(t)}</span>`)).join("")}
            ${n.due_date ? `<span class="muted" style="display:inline-flex;align-items:center;gap:3px;font-size:11px;">${icon("clock")} 期限：${esc(n.due_date)}</span>` : ''}
            ${n.linked_case_id ? `<span class="apple-pill" style="background:rgba(88,86,214,.12);color:#5856D6;border-color:rgba(88,86,214,.25);cursor:pointer;" data-action="open-case-detail" data-id="${esc(n.linked_case_id)}">${icon("folder")} 關聯案件</span>` : ''}
          </div>
        ` : ''}
          <details class="chat-note-menu"><summary aria-label="記事操作">更多操作</summary><div class="note-actions">
            <button type="button" class="btn text small" data-action="open-note-detail" data-id="${esc(n.note_id)}" title="預覽記事">${icon("eye")} 預覽</button>
            <button type="button" class="btn text small" data-action="copy-chat-note-content" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="一鍵複製內容">${icon("copy")}</button>
            <button type="button" class="btn text small" data-action="toggle-chat-note-complete" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="${isCompleted?'標記未完成':'標記完成'}">${icon(isCompleted ? "refresh" : "check")}</button>
            <button type="button" class="btn text small" data-action="toggle-chat-note-pin" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="${n.is_pinned?'取消置頂':'置頂'}">${icon(n.is_pinned ? "unpin" : "pin")}</button>
            ${canToggleNoteLock(n) ? `<button type="button" class="btn text small" data-action="toggle-chat-note-lock" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-label="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-pressed="${isLocked}">${isLocked ? icon("unlock") : icon("lock")}</button>` : ''}
            ${canEdit && !isLocked ? `<button type="button" class="btn text small" data-action="edit-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="編輯記事">${icon("edit")}</button>` : ''}
            <button type="button" class="btn text small" data-action="convert-note-to-case" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="轉為案件">${icon("folder")}</button>
            ${canEdit && !isLocked ? `<button type="button" class="btn text small danger" data-action="delete-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}" title="刪除記事">${icon("trash")}</button>` : ''}
          </div></details>
      </div>`;
    }).join("")}
  </div>`;
}

function renderContactCases(recipient_id, visibleCases=null){
  const related = visibleCases || (state.cases || []).filter(c => c.case_subject_id === recipient_id);
  if(visibleCases!==null)return renderSidebarGroups(related,true);
  if(!related.length) {
    return `<div class="chat-cases-empty">
      <div class="chat-empty-icon">${icon("folder")}</div>
      <p class="chat-empty-text">目前無關聯案件，可點選上方「建立案件」追蹤此對象的問題或需求。</p>
    </div>`;
  }
  return `<div class="contact-cases-list">${related.map(c=>`<article class="case-item case-note-card sidebar-summary-card ${sidebarThumbnail(c.description)?'has-thumbnail':''}" data-case-preview="${esc(c.case_id)}" tabindex="0" aria-label="${esc(c.title)}，按 Enter 或雙擊預覽">
    ${sidebarThumbnail(c.description)}
    <div class="case-item-info">
      <div class="case-title-row">
        <span class="case-no-badge">${esc(c.case_no)}</span>
        <span class="chat-card-title">${esc(c.title)}</span>
        ${recordLockControl(c,true)}
        ${badge(caseStatusNames[c.status]||c.status, caseStatusTones[c.status]||"")}
      </div>
      <div>
        ${c.category ? `<span class="badge">${esc(c.category)}</span> ` : ''}
        ${c.ref_no ? `<span class="muted">參考號：${esc(c.ref_no)}</span> · ` : ''}
        <small class="muted">更新：${when(c.updated_at)}</small>
      </div>
    </div>
    ${c.description ? `<div class="chat-case-description md-preview-area" data-case-id="${esc(c.case_id)}">${renderCaseContent(c)}</div>` : ''}
    ${button("預覽","open-case-detail","small",`data-id="${esc(c.case_id)}"`)}
  </article>`).join("")}</div>`;
}


function schedulePage(){
  const scheduled=state.jobs.filter(j=>j.status==="scheduled").sort((a,b)=>String(a.scheduled_at).localeCompare(String(b.scheduled_at)));
  const issues=state.jobs.filter(j=>["missed","interrupted"].includes(j.status)||j.deliveries.some(d=>["unknown","failed"].includes(d.status)));
  const rows=workspaceUI.scheduleFilter==="scheduled"?scheduled:workspaceUI.scheduleFilter==="issues"?issues:state.jobs.filter(j=>j.scheduled_at);
  return heading("排程管理","安排單次傳送時間，查看預約與執行結果。",canSend()?button(icon("plus")+"建立預約","start-send","primary"):"")+
  `<div class="schedule-summary">${stat("待執行預約",scheduled.length,"筆","到期前仍可取消","clock")}${stat("下一次執行",scheduled[0]?esc(scheduleLabel(scheduled[0].scheduled_at)):"—","","台北時間 UTC+08:00","send")}${stat("需要處理",issues.length,"筆","已載入紀錄中的異常工作","shield")}</div><section class="panel schedule-list"><div class="toolbar segmented">${[["scheduled","單次預約"],["recent","已載入預約紀錄"],["issues","需要處理"]].map(([id,t])=>`<button data-action="schedule-filter" data-id="${id}" aria-pressed="${workspaceUI.scheduleFilter===id}" class="${workspaceUI.scheduleFilter===id?"active":""}">${t}</button>`).join("")}</div>${rows.length?historyList(rows):empty("目前沒有符合的預約","建立發送時選擇「指定日期與時間」，即可在這裡查看及取消。")}</section><p class="subtitle section-space">電腦與服務需要持續執行。超過預約時間 10 分鐘的工作標記逾期，避免恢復連線後發出過時通知。</p>`;
}

function workspaceAction(action,id){
  if(action.startsWith("chat-work-")){
    const panel=document.querySelector(".chat-work-panel"); if(!panel)return true;
    const view=chatWorkView(panel.dataset.recipient);
    if(action==="chat-work-tab"){view.tab=id;view.filter="all";view.query="";view.page=1;}
    if(action==="chat-work-filter"){view.filter=id;view.page=1;}
    if(action==="chat-work-page")view.page=Math.max(1,Number(id)||1);
    refreshChatWorkPanel();
    document.querySelector(`[data-action="${action}"][data-id="${CSS.escape(id)}"]`)?.focus({preventScroll:true});
    return true;
  }
  if(action==="contact-detail"){workspaceUI.contactDetail=id;render();if(typeof loadChatNotes==="function")loadChatNotes(id);document.getElementById("contact-detail")?.focus({preventScroll:true});if(innerWidth<1200)document.getElementById("contact-detail")?.scrollIntoView({block:"start"});return true;}
  if(action==="close-contact-detail"){const previous=workspaceUI.contactDetail;workspaceUI.contactDetail="";render();document.querySelector(`[data-action="contact-detail"][data-id="${CSS.escape(previous)}"]`)?.focus();return true;}
  if(action==="schedule-filter"){workspaceUI.scheduleFilter=id;render();return true;}
  return false;
}

function commandEntries(query){
  const q=query.trim().toLowerCase();
  const allowedViews=["overview","personal-settings",...(admin()?["contacts","schedule","history"]:[]),...(canSend()?["send"]:[]),...(superAdmin()?["organizations","channels"]:[]),...(state.session?.role==="org_admin"?["channels","personnel","org-settings","templates"]:[])];
  const entries=allowedViews.map(id=>({kind:"page",id,title:titles[id],detail:"前往頁面",symbol:"grid"}));
  if(q){
    if(admin())entries.push(...state.contacts.map(r=>({kind:"contact",id:r.recipient_id,title:label(r),detail:orgName(r.organization_id)+" · "+(r.kind==="user"?"個人":"群組"),symbol:"users"})));
  }
  return entries.filter(r=>`${r.title} ${r.detail}`.toLowerCase().includes(q)).slice(0,30);
}
function renderCommands(){
  const rows=commandEntries(document.getElementById("command-search").value);
  document.getElementById("command-results").innerHTML=rows.map(r=>`<button class="command-result" data-command-kind="${r.kind}" data-command-id="${esc(r.id)}">${icon(r.symbol)}<span>${esc(r.title)}<small>${esc(r.detail)}</small></span>${icon("arrow")}</button>`).join("")||empty("找不到符合項目","搜尋目前可存取的頁面、報告與聯絡對象。");
  document.getElementById("command-count").textContent=`${rows.length} 個結果；只搜尋目前已載入且有權限的資料。`;
}
function openCommand(){
  if(!state.loaded||superAdmin()||state.busy||document.getElementById("modal").open)return;
  const dialog=document.getElementById("command-dialog");
  document.getElementById("command-search").value="";renderCommands();dialog.showModal();document.getElementById("command-search").focus();
}
document.addEventListener("input",e=>{
  if(e.target.id==="chat-work-search"){
    if(e.isComposing)return;
    const cursor=e.target.selectionStart;
    const view=chatWorkView(e.target.closest(".chat-work-panel").dataset.recipient);
    view.query=e.target.value;view.page=1;refreshChatWorkPanel();
    const input=document.getElementById("chat-work-search");input?.focus({preventScroll:true});
    if(input && cursor!==null)input.setSelectionRange(cursor,cursor);
  }
  if(e.target.id==="command-search")renderCommands();
});
document.addEventListener("compositionend",e=>{
  if(e.target.id==="chat-work-search")e.target.dispatchEvent(new Event("input",{bubbles:true}));
});
document.addEventListener("keydown",e=>{
  const tab=e.target.closest('[data-action="chat-work-tab"]');
  if(!tab || !["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;
  e.preventDefault();workspaceAction("chat-work-tab",e.key==="Home"?"notes":e.key==="End"?"cases":tab.dataset.id==="notes"?"cases":"notes");
});
document.addEventListener("change",e=>{
  if(e.target.id==="chat-work-sort"){
    const view=chatWorkView(e.target.closest(".chat-work-panel").dataset.recipient);
    view.sort=e.target.value;view.page=1;refreshChatWorkPanel();document.getElementById("chat-work-sort")?.focus({preventScroll:true});
  }
});
document.addEventListener("click",e=>{
  const summary=e.target.closest(".sidebar-summary-card,.evernote-summary");
  if(summary){
    document.querySelectorAll(".sidebar-summary-card.selected,.evernote-summary.selected").forEach(card=>card.classList.remove("selected"));
    summary.classList.add("selected");
    const panel=summary.closest(".chat-work-panel");
    if(panel)chatWorkView(panel.dataset.recipient).selected=summary.dataset.notePreview||summary.dataset.casePreview;
  }
  if(e.target.closest("#command-open"))openCommand();
  if(e.target.closest("#command-close"))document.getElementById("command-dialog").close();
  const result=e.target.closest("[data-command-kind]");if(!result)return;
  document.getElementById("command-dialog").close();
  if(result.dataset.commandKind==="page")navigate(result.dataset.commandId);
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

document.addEventListener('toggle',event=>{
  const group=event.target;
  if(!group.matches?.('details[data-record-group]') || !group.dataset.recipient)return;
  const view=chatWorkView(group.dataset.recipient);
  view.collapsedGroups=view.collapsedGroups||{};
  view.collapsedGroups[group.dataset.recordGroup]=!group.open;
},true);

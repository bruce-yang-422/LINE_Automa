"use strict";

const chatUI = {
  rooms: [],
  selectedId: "",
  filter: "all",
  query: "",
  searchQuery: "",
  searchOpen: false,
  messages: [],
  activeReplyToken: null,
  replyExpiresIn: 0,
  chatStatus: "open",
  cannedReplies: [],
  loadingMessages: false,
  sending: false,
  // 規格 4.3：桌面寬度不足 1280px 時資訊面板預設收合
  infoOpen: window.innerWidth >= 1280,
  timerId: null,
  pollInterval: null
};

function formatChatTime(val) {
  if (!val) return "";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const isYesterday = new Date(now.getTime() - 86400000).toDateString() === d.toDateString();
  if (isToday) {
    return d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", hour12: false });
  } else if (isYesterday) {
    return "昨天 " + d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", hour12: false });
  } else {
    return d.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" });
  }
}

function formatChatDateHeader(val) {
  if (!val) return "";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-TW", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
}

function chatPage() {
  const selectedRoom = chatUI.rooms.find(r => r.recipient_id === chatUI.selectedId);
  const contact = state.contacts.find(r => r.recipient_id === chatUI.selectedId) || selectedRoom;
  const hasRoom = Boolean(selectedRoom);

  return `<div class="chat-page-layout ${hasRoom ? 'has-room' : 'no-room'} ${chatUI.infoOpen ? 'has-info' : ''}">
    <!-- 1. Left Sidebar: Chat List -->
    <aside class="chat-sidebar-col">
      <div class="chat-sidebar-header">
        <div style="display:flex;align-items:center;gap:8px;">
          <label class="search-field" style="flex:1;">
            ${icon("search")}
            <input id="chat-list-search" type="search" value="${esc(chatUI.query)}" placeholder="搜尋聯絡對象或訊息…" aria-label="搜尋聊天">
          </label>
          <button type="button" class="icon-button" data-action="open-chat-settings" title="聊天設定與容量管理" aria-label="聊天設定">${icon("settings")}</button>
        </div>
        <div class="chat-filter-tabs segmented section-space">
          ${[["all", "全部"], ["unread", "未讀"], ["pending", "待處理"], ["done", "處理完畢"]].map(([id, t]) => `
            <button data-action="chat-filter" data-id="${id}" class="${chatUI.filter === id ? 'active' : ''}">${t}</button>
          `).join("")}
        </div>
        ${canSend() ? `<div style="margin-top:8px;display:flex;justify-content:flex-end;">
          <button type="button" class="btn text small" data-action="send-to-chat-filtered" style="font-size:12px;padding:2px 8px;color:var(--primary,#00B900);">📨 對目前篩選對象發送</button>
        </div>` : ""}
      </div>
      <div class="chat-room-list" id="chat-room-list">
        ${renderChatRoomItems()}
      </div>
    </aside>

    <!-- 2. Center Column: Conversation -->
    <main class="chat-conversation-col" id="chat-conversation-view">
      ${selectedRoom ? renderConversationView(selectedRoom) : renderChatEmptyState()}
    </main>

    <!-- 3. Right Column: Info Panel -->
    <aside class="chat-info-col ${chatUI.infoOpen ? 'open' : ''}" id="chat-info-col">
      ${contact ? renderChatInfoContent(contact) : '<div class="empty"><p class="muted">選擇聊天室以檢視資訊</p></div>'}
    </aside>
  </div>`;
}

function renderChatRoomItems() {
  const filtered = chatUI.rooms.filter(r => {
    if (chatUI.filter === "unread" && r.unread_count === 0) return false;
    if (chatUI.filter === "pending" && r.status !== "pending") return false;
    if (chatUI.filter === "done" && r.status !== "done") return false;
    if (chatUI.query) {
      const q = chatUI.query.toLowerCase();
      const matchName = (r.name || "").toLowerCase().includes(q) || (r.display_name || "").toLowerCase().includes(q);
      const matchText = (r.last_message?.text_content || "").toLowerCase().includes(q);
      if (!matchName && !matchText) return false;
    }
    return true;
  });

  if (!filtered.length) {
    return `<div class="empty section-space">${icon("message")}<p class="muted">沒有符合條件的聊天室</p></div>`;
  }

  return filtered.map(r => {
    const isSelected = r.recipient_id === chatUI.selectedId;
    const initial = (r.name || r.display_name || "L").slice(0, 1).toUpperCase();
    const lastText = r.last_message ? (r.last_message.unsent_at ? "[對方已收回訊息]" : (r.last_message.text_content || `[${r.last_message.message_type}]`)) : "尚無訊息";
    const timeStr = formatChatTime(r.last_message?.sent_at || r.last_activity_at);
    const unread = r.unread_count > 0;

    return `<div class="chat-room-item ${isSelected ? 'active' : ''} ${unread ? 'has-unread' : ''}" data-action="select-chat-room" data-id="${esc(r.recipient_id)}">
      <div class="chat-room-avatar ${r.kind !== 'user' ? 'group' : ''}">${esc(initial)}</div>
      <div class="chat-room-body">
        <div class="chat-room-top">
          <strong class="chat-room-name">${esc(r.name || r.display_name)}</strong>
          <span class="chat-room-time">${esc(timeStr)}</span>
        </div>
        <div class="chat-room-bottom">
          <span class="chat-room-preview">${esc(lastText)}</span>
          <div class="chat-room-badges">
            ${r.status === 'pending' ? '<span class="status-badge pending">待處理</span>' : ''}
            ${r.status === 'done' ? '<span class="status-badge done">處理完畢</span>' : ''}
            ${unread ? `<span class="unread-pill">${r.unread_count}</span>` : ''}
          </div>
        </div>
      </div>
    </div>`;
  }).join("");
}

function renderChatEmptyState() {
  return `<div class="chat-empty-state">
    <div class="empty">
      ${icon("message")}
      <h2>選擇一個聊天室開始對話</h2>
      <p>在左側清單選擇要查看與回覆的 LINE 聯絡對象或群組。</p>
    </div>
  </div>`;
}

function renderConversationView(room) {
  const isGroup = room.kind !== "user";
  const title = room.name || room.display_name || "聊天室";

  return `<div class="conversation-header">
    <div class="conversation-header-left">
      <button type="button" class="chat-mobile-back-btn icon-button" data-action="chat-back-to-list" aria-label="返回聊天清單">${icon("arrow")}</button>
      <div class="avatar ${isGroup ? 'group' : ''}">${esc(title.slice(0, 1))}</div>
      <div>
        <h2 class="conversation-title">${esc(title)}</h2>
        <small class="muted">${isGroup ? 'LINE 群組' : '個人對話'} · ${room.active ? '可接收' : '已封鎖／已停用'}</small>
      </div>
    </div>
    <div class="conversation-header-actions">
      <div class="segmented" role="group" aria-label="聊天狀態">
        <button data-action="toggle-chat-status" data-id="${esc(room.recipient_id)}" data-status="pending" class="${chatUI.chatStatus === 'pending' ? 'active' : ''}">待處理</button>
        <button data-action="toggle-chat-status" data-id="${esc(room.recipient_id)}" data-status="done" class="${chatUI.chatStatus === 'done' ? 'active' : ''}">處理完畢</button>
      </div>
      <button class="icon-button ${chatUI.searchOpen ? 'active' : ''}" data-action="toggle-chat-search" title="在對話中搜尋" aria-label="在對話中搜尋">${icon("search")}</button>
      ${state.session?.role !== 'administrator' ? `<button class="btn small text" data-action="open-chat-export-modal" data-id="${esc(room.recipient_id)}" title="匯出對話紀錄">${icon("download")} 匯出</button>` : ''}
      <button class="btn small" data-action="open-case-modal-from-chat" data-id="${esc(room.recipient_id)}">${icon("folder")}+ 建立案件</button>
      <button class="icon-button" data-action="toggle-chat-info" aria-label="切換資訊面板">${icon("users")}</button>
    </div>
  </div>

  ${chatUI.searchOpen ? `
    <div class="chat-search-bar" style="display:flex;align-items:center;gap:8px;padding:8px 16px;background:var(--card-subtle,#f8fafc);border-bottom:1px solid var(--line,#e2e8f0);">
      <label class="search-field" style="flex:1;">
        ${icon("search")}
        <input id="chat-inner-search-input" type="search" placeholder="在對話中搜尋訊息關鍵字…" value="${esc(chatUI.searchQuery)}" autofocus>
      </label>
      ${chatUI.searchQuery ? `<span class="badge" style="font-size:12px;">找到 ${chatUI.messages.filter(m => (m.text_content || '').toLowerCase().includes(chatUI.searchQuery.toLowerCase())).length} 則</span>` : ''}
      <button type="button" class="btn text small" data-action="close-chat-search">關閉</button>
    </div>
  ` : ''}

  <div class="chat-messages-scroll" id="chat-messages-stream">
    ${renderMessageBubbles()}
  </div>

  <div class="chat-input-wrapper">
    ${state.session?.role === 'assistant' ? `
      <div class="callout muted text-center" style="padding:14px;background:var(--card-subtle,#f8fafc);border-radius:10px;margin:8px;">
        <p style="margin:0;font-size:13px;">ℹ️ <strong>協助人員無法傳送訊息</strong>（具備對話閱讀、記事本與案件管理權限）</p>
      </div>
    ` : state.session?.role === 'administrator' ? `
      <div class="callout muted text-center" style="padding:14px;background:var(--card-subtle,#f8fafc);border-radius:10px;margin:8px;">
        <p style="margin:0;font-size:13px;">👁️ <strong>平台管理員僅能檢視對話紀錄</strong>（唯讀模式）</p>
      </div>
    ` : `
      ${renderReplyTokenBanner()}
      <form id="chat-send-form" data-id="${esc(room.recipient_id)}">
        <div class="chat-input-controls">
          <textarea id="chat-message-input" rows="3" placeholder="輸入文字訊息（Enter 送出，Shift+Enter 換行）…" required maxlength="5000" ${!room.active ? 'disabled placeholder="此對象已封鎖或停用，無法傳送"' : ''}></textarea>
          <div class="chat-input-bottom-bar">
            <div class="chat-input-actions-left">
              <button type="button" class="btn text small" data-action="open-canned-modal">${icon("file")} 預設訊息</button>
            </div>
            <div class="chat-input-actions-right">
              <button type="submit" class="btn primary small" id="chat-submit-btn" ${!room.active ? 'disabled' : ''}>
                ${icon("send")} 傳送
              </button>
            </div>
          </div>
        </div>
      </form>
    `}
  </div>`;
}

function renderReplyTokenBanner() {
  if (chatUI.activeReplyToken && chatUI.replyExpiresIn > 0) {
    const isUrgent = chatUI.replyExpiresIn <= 10;
    return `<div class="chat-quota-banner free ${isUrgent ? 'urgent' : ''}">
      <span>⚡ 免費回覆機會有效中（剩餘 <strong>${chatUI.replyExpiresIn}</strong> 秒）· 本則以 Reply 送出不耗額度</span>
    </div>`;
  }
  return `<div class="chat-quota-banner push">
    <span>ℹ️ 本則將以 Push 送出（計入當月訊息額度）。亦可至 <a href="https://manager.line.biz" target="_blank" rel="noopener">LINE 官方後台</a> 免費手動回覆。</span>
  </div>`;
}

function highlightSearchText(text, q) {
  if (!q || !text) return esc(text).replace(/\n/g, '<br>');
  const safeQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${safeQ})`, 'gi'));
  return parts.map(p => p.toLowerCase() === q.toLowerCase() ? `<mark style="background:#fef08a;color:#854d0e;padding:1px 3px;border-radius:3px;font-weight:600;">${esc(p)}</mark>` : esc(p)).join("").replace(/\n/g, '<br>');
}

function renderMessageBubbles() {
  if (chatUI.loadingMessages) {
    return `<div class="loading-panel"><span class="spinner"></span><p>讀取訊息歷程…</p></div>`;
  }
  if (!chatUI.messages.length) {
    return `<div class="empty section-space"><p class="muted">尚無對話訊息紀錄</p></div>`;
  }

  const displayList = chatUI.searchQuery ? chatUI.messages.filter(m => (m.text_content || '').toLowerCase().includes(chatUI.searchQuery.toLowerCase())) : chatUI.messages;
  if (chatUI.searchQuery && !displayList.length) {
    return `<div class="empty section-space"><p class="muted">找不到符合「${esc(chatUI.searchQuery)}」的對話訊息</p></div>`;
  }

  let lastDateStr = "";
  let html = "";

  displayList.forEach(m => {
    const dateStr = formatChatDateHeader(m.sent_at);
    if (dateStr && dateStr !== lastDateStr) {
      html += `<div class="chat-date-divider"><span>${esc(dateStr)}</span></div>`;
      lastDateStr = dateStr;
    }

    const isOutbound = m.direction === "outbound";
    const timeStr = formatChatTime(m.sent_at);
    let bubbleContent = "";
    if (m.message_type === "image") {
      bubbleContent = `<div class="chat-media-image">
        <a href="/api/chat/media/${esc(m.message_id)}" target="_blank" title="點擊放大檢視圖片">
          <img src="/api/chat/media/${esc(m.message_id)}" alt="LINE 圖片" style="max-width:280px;max-height:280px;border-radius:8px;object-fit:cover;cursor:pointer;display:block;" loading="lazy" onerror="this.onerror=null;this.parentElement.innerHTML='<span class=\\'muted\\' style=\\'font-size:12px;\\'>🖼️ [圖片已過期或無法載入]</span>';">
        </a>
      </div>`;
    } else if (m.message_type === "video") {
      bubbleContent = `<div class="chat-media-video">
        <video src="/api/chat/media/${esc(m.message_id)}" controls style="max-width:320px;max-height:280px;border-radius:8px;display:block;background:#000;"></video>
        <div style="margin-top:4px;"><a href="/api/chat/media/${esc(m.message_id)}" download="video_${esc(m.message_id)}.mp4" class="btn text small" style="font-size:11px;padding:2px 0;">⬇️ 下載影片</a></div>
      </div>`;
    } else if (m.message_type === "audio") {
      bubbleContent = `<div class="chat-media-audio">
        <audio src="/api/chat/media/${esc(m.message_id)}" controls style="max-width:280px;display:block;"></audio>
      </div>`;
    } else if (m.message_type === "file") {
      bubbleContent = `<div class="chat-media-file">
        <a href="/api/chat/media/${esc(m.message_id)}" download class="btn small" style="display:inline-flex;align-items:center;gap:6px;">
          📁 下載傳送的檔案
        </a>
      </div>`;
    } else if (m.message_type === "sticker") {
      bubbleContent = `<div class="chat-media-sticker"><span class="badge" style="font-size:12px;">🌟 [貼圖]</span></div>`;
    } else {
      const text = m.text_content || `[${m.message_type}]`;
      bubbleContent = `<div class="chat-bubble-text">${highlightSearchText(text, chatUI.searchQuery)}</div>`;
    }

    html += `<div class="chat-message-row ${isOutbound ? 'outbound' : 'inbound'}">
      <div class="chat-bubble-container">
        <div class="chat-bubble-meta">
          <strong>${esc(m.sender_name || (isOutbound ? '管理員' : '使用者'))}</strong>
          ${isOutbound && m.send_method ? `<small class="method-tag">${m.send_method === 'reply' ? '免費回覆' : 'Push'}</small>` : ''}
        </div>
        <div class="chat-bubble ${isOutbound ? 'outbound' : 'inbound'} ${m.is_unsent ? 'unsent' : ''}">
          ${bubbleContent}
        </div>
        <div class="chat-bubble-footer">
          <small class="muted">${esc(timeStr)}</small>
        </div>
      </div>
    </div>`;
  });

  return html;
}

function renderChatInfoContent(r) {
  const tags = r.tags || [];
  const tagsHtml = tags.length ? tags.map(t => tagBadge(t)).join(" ") : '<span class="muted">無標籤</span>';

  return `<div class="chat-info-header">
    <h3>聯絡資訊與歷程</h3>
    <button class="icon-button" data-action="toggle-chat-info" aria-label="關閉面板">✕</button>
  </div>
  <div class="chat-info-body">
    ${person(r)}
    <div class="section-space">
      <h4 class="info-section-title">對象資訊</h4>
      <dl class="chat-info-dl">
        <dt>類型</dt><dd>${contactTypeBadge(r.contact_type)}</dd>
        ${r.organization_name ? `<dt>對方組織</dt><dd>${esc(r.organization_name)}</dd>` : ''}
        ${r.job_title ? `<dt>職稱</dt><dd>${esc(r.job_title)}</dd>` : ''}
        ${r.phone ? `<dt>電話</dt><dd><a href="tel:${esc(r.phone)}">${esc(r.phone)}</a></dd>` : ''}
        ${r.email ? `<dt>Email</dt><dd><a href="mailto:${esc(r.email)}">${esc(r.email)}</a></dd>` : ''}
        <dt>分類標籤</dt><dd class="contact-tags">${tagsHtml}</dd>
      </dl>
      ${manager() ? button("編輯聯絡資訊", "edit-contact", "btn small section-space", `data-id="${esc(r.recipient_id)}"`) : ''}
    </div>

    <div class="chat-notes-box section-space">
      <div class="case-context-header">
        <strong>${icon("file")} 對話記事本</strong>
        ${button(icon("plus") + "新增記事", "new-chat-note", "btn small", `data-id="${esc(r.recipient_id)}"`)}
      </div>
      <div id="chat-notes-list-container">
        ${renderChatNotesList(r.recipient_id)}
      </div>
    </div>

    <div class="case-context-box section-space">
      <div class="case-context-header">
        <strong>${icon("folder")} 關聯案件</strong>
        ${button(icon("plus") + "建立案件", "new-case-modal", "btn small", `data-id="${esc(r.recipient_id)}"`)}
      </div>
      ${renderContactCases(r.recipient_id)}
    </div>
  </div>`;
}

async function loadChatRooms() {
  try {
    const res = await api("/api/chat/rooms");
    chatUI.rooms = res.rooms || [];
    if ($("nav-chat-count")) {
      $("nav-chat-count").textContent = res.unread_count || "0";
    }
    const container = $("chat-room-list");
    if (container) {
      container.innerHTML = renderChatRoomItems();
    }
  } catch (e) {
    console.error("Failed to load chat rooms:", e);
  }
}

async function selectChatRoom(recipient_id) {
  chatUI.selectedId = recipient_id;
  chatUI.loadingMessages = true;
  if (state.view === "chat") {
    render();
  }

  try {
    const res = await api(`/api/chat/messages?recipient_id=${encodeURIComponent(recipient_id)}`);
    chatUI.messages = res.messages || [];
    chatUI.chatStatus = res.chat_status || "open";
    chatUI.activeReplyToken = res.active_reply_token;
    chatUI.replyExpiresIn = res.reply_token_expires_in || 0;
    chatUI.loadingMessages = false;

    // Start countdown timer if reply token is valid
    if (chatUI.timerId) clearInterval(chatUI.timerId);
    if (chatUI.replyExpiresIn > 0) {
      chatUI.timerId = setInterval(() => {
        if (chatUI.replyExpiresIn > 0) {
          chatUI.replyExpiresIn--;
          const banner = document.querySelector(".chat-quota-banner");
          if (banner) banner.outerHTML = renderReplyTokenBanner();
        } else {
          clearInterval(chatUI.timerId);
        }
      }, 1000);
    }

    // Mark read
    await api("/api/chat/mark-read", { recipient_id });
    await loadChatNotes(recipient_id);
    await loadChatRooms();

    if (state.view === "chat") {
      render();
      scrollChatToBottom();
    }
  } catch (e) {
    chatUI.loadingMessages = false;
    notice(e.message, true);
  }
}

function scrollChatToBottom() {
  const stream = $("chat-messages-stream");
  if (stream) {
    stream.scrollTop = stream.scrollHeight;
  }
}

async function sendChatMessage(recipient_id, text) {
  if (chatUI.sending) return;
  chatUI.sending = true;
  try {
    await api("/api/chat/send", {
      recipient_id,
      text,
      use_reply_token: Boolean(chatUI.activeReplyToken && chatUI.replyExpiresIn > 0)
    });
    chatUI.sending = false;
    await selectChatRoom(recipient_id);
    notice("訊息已送出。");
  } catch (e) {
    chatUI.sending = false;
    notice(e.message, true);
  }
}

async function cannedRepliesModal() {
  modal("預設訊息（範本庫）", '<div class="loading-panel"><span class="spinner"></span><p>讀取預設訊息…</p></div>');
  try {
    const res = await api("/api/chat/canned-replies");
    chatUI.cannedReplies = res.replies || [];

    const listHtml = chatUI.cannedReplies.length ? chatUI.cannedReplies.map(cr => `
      <div class="canned-reply-card">
        <div class="canned-reply-header">
          <strong>${esc(cr.title)}</strong>
          ${cr.category ? `<span class="badge">${esc(cr.category)}</span>` : ''}
          <div class="canned-reply-actions">
            <button class="btn text small" data-action="use-canned-reply" data-id="${esc(cr.id)}">帶入對話</button>
            ${manager() ? `<button class="btn text small danger" data-action="delete-canned-reply" data-id="${esc(cr.id)}">刪除</button>` : ''}
          </div>
        </div>
        <p class="canned-reply-content">${esc(cr.content)}</p>
      </div>
    `).join("") : '<p class="muted">尚未建立任何預設訊息範本。</p>';

    modal("預設訊息範本庫", `<div>
      <div class="canned-replies-list">${listHtml}</div>
      ${manager() ? `
        <h3 class="section-space">新增預設訊息（每 OA 上限 ${cap("CANNED_REPLIES_PER_OA")} 則）</h3>
        <form id="canned-reply-create-form">
          <div class="form-grid">
            <div class="full">${field("範本標題", "title", "", 'required maxlength="40" placeholder="例如：問候語、匯款帳號通知"')}</div>
            <div class="full">${field("分類名稱（選填）", "category", "", 'maxlength="20" placeholder="例如：常見問題、售後服務"')}</div>
            <div class="full"><label class="field">訊息內容<textarea name="content" rows="4" required maxlength="5000" placeholder="輸入常用訊息文字..."></textarea></label></div>
          </div>
          <div class="form-actions"><button class="btn primary" type="submit">建立預設訊息</button></div>
        </form>
      ` : ''}
    </div>`);
  } catch (e) {
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

// Global Chat Action dispatcher
function chatAction(action, id, target) {
  if (action === "chat-back-to-list") {
    chatUI.selectedId = "";
    if (state.view === "chat") render();
    return true;
  }
  if (action === "chat-filter") {
    chatUI.filter = id;
    if ($("chat-room-list")) $("chat-room-list").innerHTML = renderChatRoomItems();
    return true;
  }
  if (action === "select-chat-room") {
    selectChatRoom(id);
    return true;
  }
  if (action === "toggle-chat-info") {
    chatUI.infoOpen = !chatUI.infoOpen;
    render();
    return true;
  }
  if (action === "toggle-chat-status") {
    const nextStatus = target.dataset.status;
    api("/api/chat/status", { recipient_id: id, status: nextStatus }).then(() => {
      chatUI.chatStatus = nextStatus;
      loadChatRooms().then(() => render());
      notice(`聊天狀態已變更為「${nextStatus === 'pending' ? '待處理' : '處理完畢'}」。`);
    });
    return true;
  }
  if (action === "open-canned-modal") {
    cannedRepliesModal();
    return true;
  }
  if (action === "use-canned-reply") {
    const cr = chatUI.cannedReplies.find(r => r.id === id);
    if (cr && $("chat-message-input")) {
      $("chat-message-input").value = cr.content;
      $("modal").close();
      $("chat-message-input").focus();
    }
    return true;
  }
  if (action === "delete-canned-reply") {
    if (confirm("確定要刪除這則預設訊息範本嗎？")) {
      api("/api/chat/canned-replies/delete", { id }).then(() => {
        cannedRepliesModal();
        notice("預設訊息已刪除。");
      });
    }
    return true;
  }
  if (action === "open-case-modal-from-chat") {
    createCaseModal(id);
    return true;
  }
  if (action === "open-chat-from-contact") {
    navigate("chat");
    selectChatRoom(id);
    return true;
  }
  if (action === "toggle-chat-note-pin") {
    const recId = target.dataset.recipient || chatUI.selectedId;
    api("/api/chat-notes/pin", { note_id: id }).then(res => {
      loadChatNotes(recId);
      notice(res.is_pinned ? "記事已置頂。" : "已取消置頂。");
    }).catch(e => notice(e.message, true));
    return true;
  }
  if (action === "toggle-chat-note-lock") {
    const recId = target.dataset.recipient || chatUI.selectedId;
    api("/api/chat-notes/lock", { note_id: id }).then(res => {
      loadChatNotes(recId);
      notice(res.is_locked ? "記事已鎖定，防止誤改。" : "記事已解除鎖定。");
    }).catch(e => notice(e.message, true));
    return true;
  }
  if (action === "view-chat-notes-trash") {
    const recId = target.dataset.recipient || chatUI.selectedId;
    viewChatNotesTrashModal(recId);
    return true;
  }
  if (action === "restore-chat-note") {
    const recId = target.dataset.recipient || chatUI.selectedId;
    api("/api/chat-notes/restore", { note_id: id }).then(() => {
      loadChatNotes(recId);
      viewChatNotesTrashModal(recId);
      notice("記事已還原。");
    }).catch(e => notice(e.message, true));
    return true;
  }
  if (action === "convert-note-to-case") {
    const recId = target.dataset.recipient || chatUI.selectedId;
    const notes = state.chatNotes?.get(recId) || [];
    const note = notes.find(n => n.note_id === id);
    if (note) {
      createCaseModal(recId, {
        title: note.title || "從記事建立案件",
        description: note.content || "",
        category: note.note_type || "一般"
      });
    }
    return true;
  }
  if (action === "toggle-chat-search") {
    chatUI.searchOpen = !chatUI.searchOpen;
    if (!chatUI.searchOpen) chatUI.searchQuery = "";
    render();
    if (chatUI.searchOpen) setTimeout(() => $("chat-inner-search-input")?.focus(), 50);
    return true;
  }
  if (action === "close-chat-search") {
    chatUI.searchOpen = false;
    chatUI.searchQuery = "";
    render();
    return true;
  }
  if (action === "open-chat-export-modal") {
    openChatExportModal(id || chatUI.selectedId);
    return true;
  }
  if (action === "open-chat-settings") {
    openChatSettingsModal();
    return true;
  }
  if (action === "cleanup-expired-media") {
    api("/api/chat/media/cleanup", {}).then(res => {
      openChatSettingsModal();
      notice(`已清理過期媒體：刪除 ${res.deleted_count} 筆，釋放 ${res.freed_mb} MB。`);
    }).catch(e => notice(e.message, true));
    return true;
  }
  return false;
}

function openChatExportModal(recipient_id) {
  const r = chatUI.rooms.find(x => x.recipient_id === recipient_id) || { name: "聊天室" };
  const title = r.name || r.display_name || "聊天室";
  modal("匯出聊天紀錄", `<div>
    <p class="muted" style="margin-bottom:16px;">匯出 <strong>${esc(title)}</strong> 的完整對話訊息紀錄（文字與時間戳記，不含二進位媒體檔）：</p>
    <div style="display:flex;flex-direction:column;gap:12px;">
      <a href="/api/chat/export?chat_id=${encodeURIComponent(recipient_id)}&format=txt" download class="btn primary" style="display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;padding:10px 16px;">
        ${icon("file")} 下載純文字紀錄檔 (.txt)
      </a>
      <a href="/api/chat/export?chat_id=${encodeURIComponent(recipient_id)}&format=csv" download class="btn" style="display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;padding:10px 16px;">
        ${icon("download")} 下載試算表格式 (.csv, 含 UTF-8 BOM)
      </a>
    </div>
  </div>`);
}

async function openChatSettingsModal() {
  modal("聊天設定與容量管理", '<div class="loading-panel"><span class="spinner"></span><p>讀取設定中…</p></div>');
  try {
    const [hoursRes, statsRes] = await Promise.all([
      api("/api/chat/response-hours"),
      api("/api/chat/media/stats")
    ]);
    chatNotify.responseHours = hoursRes;
    const stats = statsRes || { total_mb: 0, percent: 0, file_count: 0 };
    modal("聊天設定與容量管理", `<div>
      <div class="card" style="margin-bottom:16px;">
        <h3 style="margin-top:0;">提醒偏好設定</h3>
        <p class="muted" style="font-size:13px;margin:4px 0 12px;">有新訊息時的提醒方式（依目前瀏覽器本機儲存）：</p>
        <p class="callout" id="chat-notify-permission" style="font-size:12px;margin:0 0 10px;">${esc(notificationPermissionText())}</p>
        <label style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:14px;cursor:pointer;">
          <input type="checkbox" id="chat-pref-notify" ${localStorage.getItem("chat_pref_notify") !== "0" ? "checked" : ""}>
          顯示瀏覽器桌面通知
        </label>
        <label style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:14px;cursor:pointer;">
          <input type="checkbox" id="chat-pref-sound" ${localStorage.getItem("chat_pref_sound") === "1" ? "checked" : ""}>
          播放新訊息提示音
        </label>
        <label style="display:flex;align-items:center;gap:8px;font-size:14px;cursor:pointer;">
          <input type="checkbox" id="chat-pref-preview" ${localStorage.getItem("chat_pref_preview") !== "0" ? "checked" : ""}>
          在通知中預覽訊息內容
        </label>
      </div>

      <div class="card" style="margin-bottom:16px;">
        <h3 style="margin-top:0;">回應時間設定</h3>
        <p class="muted" style="font-size:13px;margin:4px 0 12px;">設定每週回應時段（非回應時段將靜音並停止發出瀏覽器桌面通知）：</p>
        <form id="chat-response-hours-form">
          <label style="display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:14px;cursor:pointer;">
            <input type="checkbox" name="enabled" ${hoursRes.enabled ? "checked" : ""}>
            <strong>啟用回應時間排程通知過濾</strong>
          </label>
          <div class="form-grid">
            <div>${field("時區", "timezone", hoursRes.timezone || "Asia/Taipei", 'readonly')}</div>
          </div>
          ${renderResponseWeekly(hoursRes.weekly || {})}
          <label class="field" style="margin-top:12px;">例假日（每行一個日期，例如 2026-10-10；當天整天不通知）
            <textarea name="holidays" rows="3" placeholder="2026-10-10">${esc((hoursRes.holidays || []).join("\n"))}</textarea>
          </label>
          <div class="form-actions" style="margin-top:12px;">
            <button class="btn primary small" type="submit">儲存回應時間設定</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h3 style="margin-top:0;">媒體儲存容量與保存期限</h3>
        <p class="muted" style="font-size:13px;margin:4px 0 12px;">單台主機儲存上限：${stats.limit_gb} GB（單一檔案上限 ${stats.single_limit_mb} MB，媒體檔案保存 ${Math.round(stats.retention_days / 365)} 年）</p>
        <div style="background:var(--line,#e2e8f0);height:10px;border-radius:5px;overflow:hidden;margin-bottom:8px;">
          <div style="background:${stats.warning ? '#ef4444' : 'var(--accent,#00b900)'};width:${Math.min(100, Math.max(2, stats.percent))}%;height:100%;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:13px;">
          <span>已使用 <strong>${stats.total_mb} MB</strong> / ${stats.limit_gb} GB (${stats.percent}%) · 共 ${stats.file_count} 個媒體檔</span>
          <button type="button" class="btn small" data-action="cleanup-expired-media">🧹 清理過期媒體</button>
        </div>
      </div>
    </div>`);
  } catch (e) {
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

async function viewChatNotesTrashModal(recipient_id) {
  modal(`最近刪除的記事（${cap("NOTE_TRASH_DAYS")} 天內可還原）`, '<div class="loading-panel"><span class="spinner"></span><p>讀取回收筒…</p></div>');
  try {
    const res = await api(`/api/chat-notes/trash?recipient_id=${encodeURIComponent(recipient_id)}`);
    const trashed = res.trash || [];
    if (!trashed.length) {
      modal("最近刪除的記事", '<p class="muted" style="padding:1rem;">資源回收筒內目前沒有已刪除的記事。</p>');
      return;
    }
    const html = trashed.map(n => `
      <div class="chat-note-trash-item" style="border:1px solid var(--line, #e2e8f0);border-radius:8px;padding:8px 10px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;">
          <span><strong>${esc(n.title || "記事")}</strong> · <span class="muted">刪除於 ${when(n.deleted_at)}</span></span>
          <button class="btn small primary" data-action="restore-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(recipient_id)}">還原此記事</button>
        </div>
        <div style="font-size:13px;margin-top:4px;color:var(--text-subtle,#64748b);">${esc(n.content)}</div>
      </div>
    `).join("");
    modal(`最近刪除的記事（${cap("NOTE_TRASH_DAYS")} 天內可還原）`, `<div>${html}</div>`);
  } catch (e) {
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

// ----------------- 新訊息輪詢與瀏覽器通知（規格 4.3、12.1、12.4） -----------------
// 多個分頁只由一頁（leader）輪詢並通知；leader 每次輪詢更新心跳，逾時由其他分頁接手。
const CHAT_POLL_MS = 10000;
const CHAT_LEADER_KEY = "chat_poll_leader";
const CHAT_LEADER_STALE_MS = CHAT_POLL_MS * 3;
const CHAT_WEEKDAYS = [["1", "週一"], ["2", "週二"], ["3", "週三"], ["4", "週四"], ["5", "週五"], ["6", "週六"], ["0", "週日"]];
const chatNotify = {
  tabId: Math.random().toString(36).slice(2),
  seen: null,          // recipient_id → 最後一則訊息 ID；null 表示尚未建立基準
  channel: "",
  responseHours: null,
  polling: false
};

function chatPref(name, fallback) {
  try {
    const v = localStorage.getItem(`chat_pref_${name}`);
    return v === null ? fallback : v === "1";
  } catch (_) { return fallback; }
}

function setChatPref(name, on) {
  try { localStorage.setItem(`chat_pref_${name}`, on ? "1" : "0"); } catch (_) {}
}

function notificationPermissionText() {
  if (!("Notification" in window)) return "此瀏覽器不支援桌面通知。";
  if (Notification.permission === "granted") return "瀏覽器已允許通知。";
  if (Notification.permission === "denied") return "瀏覽器已封鎖通知：請點網址列左側的網站設定，將「通知」改為允許後重新整理。";
  return "尚未授權通知：勾選「顯示瀏覽器桌面通知」時瀏覽器會詢問是否允許。";
}

function renderResponseWeekly(weekly) {
  return `<div class="response-weekly" style="display:grid;gap:6px;margin-top:12px;">
    ${CHAT_WEEKDAYS.map(([d, name]) => {
      const slot = weekly[d];
      return `<div style="display:flex;align-items:center;gap:8px;font-size:13px;flex-wrap:wrap;">
        <label class="check-label" style="min-width:72px;"><input type="checkbox" name="day_${d}" ${slot ? "checked" : ""}>${name}</label>
        <input type="time" name="start_${d}" value="${esc(slot?.start || "09:00")}" aria-label="${name}開始時間">
        <span>至</span>
        <input type="time" name="end_${d}" value="${esc(slot?.end || "18:00")}" aria-label="${name}結束時間">
      </div>`;
    }).join("")}
  </div>`;
}

// 由回應時間表單讀出 weekly 與 holidays（admin.js 送出時使用）
function readResponseHoursForm(form) {
  const weekly = {};
  CHAT_WEEKDAYS.forEach(([d]) => {
    if (form.elements[`day_${d}`]?.checked) {
      weekly[d] = { start: form.elements[`start_${d}`].value || "00:00", end: form.elements[`end_${d}`].value || "23:59" };
    }
  });
  const holidays = (form.elements.holidays?.value || "").split(/\s+/).map(s => s.trim()).filter(Boolean);
  return { weekly, holidays };
}

// 未啟用回應時間 → 隨時通知；啟用後只在當天時段內、且非例假日通知。
function withinResponseHours(cfg, now = new Date()) {
  if (!cfg || !cfg.enabled) return true;
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: cfg.timezone || "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short"
  }).formatToParts(now).map(p => [p.type, p.value]));
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  if ((cfg.holidays || []).includes(date)) return false;
  const day = String(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(parts.weekday));
  const slot = (cfg.weekly || {})[day];
  if (!slot) return false;
  const time = `${parts.hour}:${parts.minute}`;
  return slot.start <= slot.end ? time >= slot.start && time < slot.end : time >= slot.start || time < slot.end;
}

function isChatPollLeader() {
  try {
    const cur = JSON.parse(localStorage.getItem(CHAT_LEADER_KEY) || "null");
    if (cur && cur.id !== chatNotify.tabId && Date.now() - cur.ts < CHAT_LEADER_STALE_MS) return false;
    localStorage.setItem(CHAT_LEADER_KEY, JSON.stringify({ id: chatNotify.tabId, ts: Date.now() }));
    return true;
  } catch (_) {
    return true;
  }
}

window.addEventListener("beforeunload", () => {
  try {
    const cur = JSON.parse(localStorage.getItem(CHAT_LEADER_KEY) || "null");
    if (cur && cur.id === chatNotify.tabId) localStorage.removeItem(CHAT_LEADER_KEY);
  } catch (_) {}
});

function notifyNewMessage(room) {
  if (!chatPref("notify", true) || !("Notification" in window) || Notification.permission !== "granted") return;
  if (!withinResponseHours(chatNotify.responseHours)) return;
  const name = room.name || room.display_name || "LINE 聊天室";
  const m = room.last_message || {};
  const body = chatPref("preview", true) ? (m.text_content || `[${m.message_type || "訊息"}]`) : "有新訊息";
  try {
    const n = new Notification(`LINE 新訊息：${name}`, { body, icon: "/assets/brand/line-automation-logo-light.png", tag: room.recipient_id });
    n.onclick = () => {
      window.focus();
      if (typeof navigate === "function") navigate("chat");
      selectChatRoom(room.recipient_id);
      n.close();
    };
  } catch (e) {
    console.warn("Desktop notification failed:", e);
  }
  if (chatPref("sound", false)) {
    try {
      new Audio("data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbqWE2Mmih2uOxYjg4bKLZ5LhkOjpupdznvWc9PW6o3unBaD9Ccazg6sRtQURxrOHrxXFEQ3St4evGcklFda7i68d1Skd3r+PryHhMR3mw5O3KfVBKfbHm782CUlCA").play().catch(() => {});
    } catch (_) {}
  }
}

// 比對各聊天室最後一則訊息；第一次輪詢或切換 OA 時只建立基準，不通知舊訊息。
function detectNewInbound(rooms) {
  const fresh = [];
  const next = new Map();
  rooms.forEach(r => {
    const id = r.last_message?.message_id || "";
    next.set(r.recipient_id, id);
    if (chatNotify.seen && id && chatNotify.seen.get(r.recipient_id) !== id && r.last_message.direction === "inbound") fresh.push(r);
  });
  chatNotify.seen = next;
  return fresh;
}

async function pollChat() {
  if (chatNotify.polling || typeof state === "undefined" || !state.loaded || !admin() || !lineDataReady() || state.authLost) return;
  const leader = isChatPollLeader();
  const viewingChat = state.view === "chat" && !document.hidden;
  if (!leader && !viewingChat) return;
  chatNotify.polling = true;
  try {
    if (chatNotify.channel !== lineUI.channel) {
      chatNotify.channel = lineUI.channel;
      chatNotify.seen = null;
      chatNotify.responseHours = await api("/api/chat/response-hours").catch(() => null);
    }
    const before = JSON.stringify(chatUI.rooms.map(r => [r.recipient_id, r.last_message?.message_id, r.unread_count, r.status]));
    await loadChatRooms();
    const fresh = detectNewInbound(chatUI.rooms);
    if (leader) {
      fresh.filter(r => !(viewingChat && r.recipient_id === chatUI.selectedId)).forEach(notifyNewMessage);
    }
    // 正在看的聊天室有新訊息時重新載入對話
    if (viewingChat && chatUI.selectedId && fresh.some(r => r.recipient_id === chatUI.selectedId) && !$("modal").open) {
      const typed = $("chat-message-input")?.value || "";
      await selectChatRoom(chatUI.selectedId);
      if (typed && $("chat-message-input")) $("chat-message-input").value = typed;
    } else if (before !== JSON.stringify(chatUI.rooms.map(r => [r.recipient_id, r.last_message?.message_id, r.unread_count, r.status])) && state.view === "overview" && !$("modal").open) {
      render();
    }
  } catch (e) {
    console.warn("Chat polling failed:", e);
  } finally {
    chatNotify.polling = false;
  }
}

setInterval(pollChat, CHAT_POLL_MS);

// 聊天設定的提醒偏好：勾選即存；開啟通知時向瀏覽器要求授權（需在使用者操作中呼叫）。
document.addEventListener("change", event => {
  const prefs = { "chat-pref-notify": "notify", "chat-pref-sound": "sound", "chat-pref-preview": "preview" };
  const name = prefs[event.target.id];
  if (!name) return;
  setChatPref(name, event.target.checked);
  if (name === "notify" && event.target.checked && "Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().then(() => {
      const el = $("chat-notify-permission");
      if (el) el.textContent = notificationPermissionText();
    });
  }
});



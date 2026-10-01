"use strict";

const chatUI = {
  rooms: [],
  selectedId: "",
  filter: "all",
  query: "",
  messages: [],
  activeReplyToken: null,
  replyExpiresIn: 0,
  chatStatus: "open",
  cannedReplies: [],
  loadingMessages: false,
  sending: false,
  infoOpen: true,
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
        <label class="search-field">
          ${icon("search")}
          <input id="chat-list-search" type="search" value="${esc(chatUI.query)}" placeholder="搜尋聯絡對象或訊息…" aria-label="搜尋聊天">
        </label>
        <div class="chat-filter-tabs segmented section-space">
          ${[["all", "全部"], ["unread", "未讀"], ["pending", "待處理"], ["done", "處理完畢"]].map(([id, t]) => `
            <button data-action="chat-filter" data-id="${id}" class="${chatUI.filter === id ? 'active' : ''}">${t}</button>
          `).join("")}
        </div>
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
      <button class="btn small" data-action="open-case-modal-from-chat" data-id="${esc(room.recipient_id)}">${icon("folder")}+ 建立案件</button>
      <button class="icon-button" data-action="toggle-chat-info" aria-label="切換資訊面板">${icon("users")}</button>
    </div>
  </div>

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

function renderMessageBubbles() {
  if (chatUI.loadingMessages) {
    return `<div class="loading-panel"><span class="spinner"></span><p>讀取訊息歷程…</p></div>`;
  }
  if (!chatUI.messages.length) {
    return `<div class="empty section-space"><p class="muted">尚無對話訊息紀錄</p></div>`;
  }

  let lastDateStr = "";
  let html = "";

  chatUI.messages.forEach(m => {
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
      bubbleContent = `<div class="chat-bubble-text">${esc(text).replace(/\\n/g, '<br>')}</div>`;
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
        <h3 class="section-space">新增預設訊息（每 OA 上限 100 則）</h3>
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
  return false;
}

async function viewChatNotesTrashModal(recipient_id) {
  modal("最近刪除的記事（30 天內可還原）", '<div class="loading-panel"><span class="spinner"></span><p>讀取回收筒…</p></div>');
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
    modal("最近刪除的記事（30 天內可還原）", `<div>${html}</div>`);
  } catch (e) {
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}


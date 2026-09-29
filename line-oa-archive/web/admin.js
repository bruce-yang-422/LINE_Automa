"use strict";
const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem("lineAdminToken") || "";
if (location.hash) { sessionStorage.setItem("lineAdminToken", token); history.replaceState(null, "", "/"); }
let contacts = [], selected = new Set(), pending = false, initialized = false;
const label = r => r.alias || r.display_name || `${r.kind === "user" ? "個人" : "群組"} · ${r.recipient_id.slice(-8)}`;
function notice(text, error = false) { $("notice").textContent = text; $("notice").classList.toggle("error", error); }
async function api(path, payload) {
  const response = await fetch(path, {method:payload === undefined ? "GET" : "POST", headers:{"Authorization":`Bearer ${token}`,"Content-Type":"application/json"}, body:payload === undefined ? undefined : JSON.stringify(payload), cache:"no-store"});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "操作未完成。");
  return result;
}
function counts() {
  const subscribers = contacts.filter(r => r.active && r.weather_subscribed).length;
  $("summary").textContent = `${contacts.length} 個聊天室 · ${subscribers} 個天氣訂閱 · 已勾選 ${selected.size} 個`;
  $("send-selected").textContent = `發給勾選對象（${selected.size}）`;
  $("send-subscribers").textContent = `發給天氣訂閱名單（${subscribers}）`;
  $("send-selected").disabled = pending || !selected.size;
  $("send-subscribers").disabled = pending || !subscribers;
}
function visibleRows() {
  const term = $("search").value.toLocaleLowerCase(), filter = $("filter").value;
  return contacts.filter(r => `${label(r)} ${r.display_name} ${r.recipient_id}`.toLocaleLowerCase().includes(term) &&
    (filter === "all" || (filter === "subscribed" ? r.active && r.weather_subscribed : filter === "group" ? r.kind !== "user" : r.kind === "user")));
}
function render() {
  $("contacts").replaceChildren();
  for (const row of visibleRows()) {
    const tr = document.createElement("tr");
    const cell = node => { const td = document.createElement("td"); if (typeof node === "string") td.textContent = node; else td.append(node); tr.append(td); };
    const check = document.createElement("input"); check.type = "checkbox"; check.checked = selected.has(row.recipient_id); check.disabled = !row.active;
    check.setAttribute("aria-label", `選取 ${label(row)}`);
    check.addEventListener("change", () => { check.checked ? selected.add(row.recipient_id) : selected.delete(row.recipient_id); counts(); }); cell(check);
    const name = document.createElement("div"); name.textContent = label(row); const id = document.createElement("small"); id.textContent = row.recipient_id; name.append(id); cell(name);
    cell(`${row.kind === "user" ? "個人" : "群組"} · ${row.active ? "可用" : "已封鎖／離開"}`);
    const alias = document.createElement("input"); alias.type = "text"; alias.value = row.alias; alias.maxLength = 80; alias.placeholder = "例如：王先生／業務群"; alias.setAttribute("aria-label", `備註 ${label(row)}`); cell(alias);
    const subscription = document.createElement("input"); subscription.type = "checkbox"; subscription.checked = !!row.weather_subscribed; subscription.disabled = !row.active; subscription.setAttribute("aria-label", `${label(row)} 的天氣訂閱`); cell(subscription);
    const save = document.createElement("button"); save.textContent = "儲存";
    save.addEventListener("click", async () => { save.disabled = true; try { await api("/api/contact",{id:row.recipient_id,alias:alias.value,subscribed:subscription.checked}); await refreshContacts(); notice("收件者設定已儲存。"); } catch(e) { notice(e.message,true); save.disabled=false; } }); cell(save);
    $("contacts").append(tr);
  }
  if (!$("contacts").children.length) { const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=6;td.className="empty";td.textContent="尚無符合的收件者。請先讓使用者向 Bot 傳送訊息。";tr.append(td);$("contacts").append(tr); }
  counts();
}
async function refreshContacts() {
  const data = await api("/api/contacts"); contacts = data.contacts;
  selected = new Set([...selected].filter(id => contacts.some(r => r.recipient_id === id && r.active)));
  if (!initialized) { $("image-path").value = data.default_image; initialized = true; }
  render();
}
const statusNames={queued:"排隊中",running:"發送中",finished:"已完成",interrupted:"已中斷",pending:"等待發送",sending:"正在發送",accepted:"LINE 已接受",failed:"失敗",unknown:"狀態不明，請確認聊天室",cancelled:"未發送／已取消"};
async function refreshJobs() {
  const {jobs} = await api("/api/jobs"); $("jobs").replaceChildren();
  for (const job of jobs) {
    const details=document.createElement("details"),summary=document.createElement("summary");
    const accepted=job.deliveries.filter(r => r.status === "accepted").length;
    summary.textContent=`${new Date(job.created_at).toLocaleString()} · ${statusNames[job.status] || job.status} · ${accepted}/${job.deliveries.length} 個已接受`;
    details.append(summary); if (["queued","running","interrupted"].includes(job.status)) details.open=true;
    for (const row of job.deliveries) { const item=document.createElement("div");item.className=`result ${row.status === "accepted" ? "good" : "bad"}`;item.textContent=`${row.label}：${statusNames[row.status] || row.status}${row.error ? " — "+row.error : ""}`;details.append(item); }
    if(job.error){const item=document.createElement("p");item.textContent=job.error;details.append(item);}
    $("jobs").append(details);
  }
  if (!jobs.length) $("jobs").textContent="尚無管理頁發送紀錄。";
  return jobs;
}
async function send(audience) {
  const rows = contacts.filter(r => r.active && (audience === "subscribers" ? r.weather_subscribed : selected.has(r.recipient_id)));
  if (!rows.length || pending) return;
  const imagePath=$("image-path").value.trim(); if(!imagePath){notice("請填入 PNG 圖片路徑。",true);return;}
  const names=rows.slice(0,12).map(label).join("、")+(rows.length>12?"…":"");
  if (!confirm(`將這張圖片傳給 ${rows.length} 個聊天室？\n${names}\n\n${imagePath}\n\n每個聊天室會收到一張圖片。`)) return;
  pending=true;counts();notice("正在檢查圖片並建立發送工作…");
  const jobId=crypto.randomUUID();
  try { await api("/api/send",{job_id:jobId,audience,ids:rows.map(r=>r.recipient_id),image_path:imagePath}); notice("已建立發送工作，請查看下方逐筆結果。"); await refreshJobs(); }
  catch(e) { notice(`${e.message} 請先查看發送紀錄，避免重複傳送。`,true); }
  finally { pending=false;counts(); }
}
$("search").addEventListener("input",render);$("filter").addEventListener("change",render);
$("select-visible").addEventListener("click",()=>{visibleRows().filter(r=>r.active).forEach(r=>selected.add(r.recipient_id));render();});
$("clear").addEventListener("click",()=>{selected.clear();render();});
$("send-selected").addEventListener("click",()=>send("selected"));$("send-subscribers").addEventListener("click",()=>send("subscribers"));
$("refresh").addEventListener("click",async()=>{try{await refreshContacts();await refreshJobs();notice("名單已更新。");}catch(e){notice(e.message,true);}});
$("profiles").addEventListener("click",async()=>{ $("profiles").disabled=true;notice("正在讀取 LINE 名稱，請稍候…");try{const result=await api("/api/profiles",{});await refreshContacts();notice(`已更新 ${result.updated} 個名稱；${result.failed} 個暫時無法取得，可先使用備註名稱。`);}catch(e){notice(e.message,true);}finally{$("profiles").disabled=false;} });
(async()=>{try{await refreshContacts();await refreshJobs();notice("名單已載入。可勾選發送，或管理天氣訂閱。");}catch(e){notice(e.message,true);}})();
setInterval(()=>refreshJobs().catch(()=>{}),4000);

"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const paths = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  layers:'<path d="m12 2 10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5"/>',
  file:'<path d="M14 2H5v20h14V7zM14 2v6h5M8 12h8M8 16h6"/>',
  send:'<path d="m22 2-7 20-4-9-9-4zM11 13 22 2"/>',
  users:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v2"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  settings:'<path d="M3 7h18M3 17h18"/><rect x="6" y="4" width="4" height="6" rx="1"/><rect x="14" y="14" width="4" height="6" rx="1"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  refresh:'<path d="M20 7a9 9 0 1 0 1 8M20 2v6h-6"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  plus:'<path d="M12 4v16M4 12h16"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  copy:'<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  shield:'<path d="m12 2 8 3v6c0 6-8 11-8 11S4 17 4 11V5zM8 12l3 3 5-6"/>',
  folder:'<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  message:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  pdf:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13h2a1.5 1.5 0 0 0 0-3H9v6"/><path d="M13 16v-6h2a2 2 0 0 1 0 4h-2"/>',
  doc:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  sheet:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h8M8 17h8M12 11v8"/>',
  slide:'<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/><circle cx="12" cy="10" r="3"/>',
  zip:'<path d="M10 2v20M14 2v20M4 6h16M4 10h16M4 14h16M4 18h16"/><rect x="4" y="2" width="16" height="20" rx="2"/>',
  audio:'<path d="M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"/>',
  video:'<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>',
  mic:'<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/>',
  star:'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  alert:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  close:'<path d="M18 6 6 18M6 6l12 12"/>',
  trash:'<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/>',
  pin:'<path d="M16 3l1 1-3 5v5l-2 2-2-2V9L7 4l1-1h8zM12 16v5"/>',
  unpin:'<path d="M16 3l1 1-3 5v5l-2 2-2-2V9L7 4l1-1h8zM12 16v5M2 2l20 20"/>',
  lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  unlock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
  calendar:'<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  tag:'<path d="m20.59 13.41-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01"/>',
  edit:'<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>',
  info:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
};
const solidIcons64 = {
  pdf: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#D32F2F"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#B71C1C"/><path d="M22.8 21.2C22.1 19.1 20.3 14.5 17.5 14.5C15.4 14.5 14.2 16.1 14.2 18.1C14.2 21.2 16.6 25.4 19.5 29.2C17.1 30.2 13.8 31.9 10 34C7.6 35.3 5.8 37.3 6.4 39C6.9 40.3 8.4 40.9 10 40.9C13.2 40.9 17.7 37.7 21.7 33C24.6 33.9 27.6 34.6 30 35C31.8 35.3 33.1 34.6 33.6 33.2C34.1 31.5 32.9 30.2 30.8 30.1C28.2 29.9 25.3 28.1 22.8 21.2ZM16.4 18.2C16.4 17.3 16.9 16.5 17.5 16.5C18.5 16.5 19.6 19.2 20.4 22.1C18.1 18.9 16.4 18.2 16.4 18.2ZM8.8 38.6C8.5 38.6 8.3 38.3 8.2 38C8 37.5 8.8 36.4 10.4 35.3C12.9 33.7 15.3 32.4 17.1 31.8C13.9 35.6 10.6 38.6 8.8 38.6ZM30.6 33C30.2 33.2 29 33.1 27.4 32.7C29.6 32.3 31.1 32 31.4 32.4C31.7 32.7 31.4 32.9 30.6 33Z" fill="#FFFFFF"/></svg>`,
  doc: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#1976D2"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#0D47A1"/><text x="18" y="34.5" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="21" font-weight="900" text-anchor="middle">W</text></svg>`,
  sheet: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#2E7D32"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#1B5E20"/><text x="18" y="34.5" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="22" font-weight="900" text-anchor="middle">X</text></svg>`,
  csv: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#0D9488"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#0F766E"/><text x="18" y="33.5" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="13.5" font-weight="900" text-anchor="middle" letter-spacing="-0.5">CSV</text></svg>`,
  slide: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#E65100"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#BF360C"/><text x="18" y="34.5" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="22" font-weight="900" text-anchor="middle">P</text></svg>`,
  zip: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#D97706"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#B45309"/><text x="18" y="33" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="-0.5">ZIP</text></svg>`,
  file: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#9E9E9E"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#757575"/><rect x="9" y="21" width="18" height="3.5" rx="1.75" fill="#FFFFFF"/><rect x="9" y="27" width="18" height="3.5" rx="1.75" fill="#FFFFFF"/><rect x="9" y="33" width="12" height="3.5" rx="1.75" fill="#FFFFFF"/></svg>`,
  audio: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#7C3AED"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#6D28D9"/><path d="M15 33V20L25 17V30M15 33A3 3 0 1 1 12 30C13.7 30 15 31.3 15 33ZM25 30A3 3 0 1 1 22 27C23.7 27 25 28.3 25 30Z" fill="#FFFFFF"/></svg>`,
  video: `<svg viewBox="0 0 36 44" fill="none" class="svg-doc-card" aria-hidden="true" style="stroke:none;"><path d="M4 0C1.79 0 0 1.79 0 4V40C0 42.21 1.79 44 4 44H32C34.21 44 36 42.21 36 40V12L24 0H4Z" fill="#0891B2"/><path d="M24 0V9C24 10.66 25.34 12 27 12H36L24 0Z" fill="#0E7490"/><circle cx="18" cy="28" r="9" fill="#FFFFFF" fill-opacity="0.25"/><polygon points="15,23 24,28 15,33" fill="#FFFFFF"/></svg>`,
  download_btn: `<svg viewBox="0 0 64 64" fill="none" class="svg-btn-download" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="#3B82F6"/><path d="M32 18V38M32 38L22 28M32 38L42 28M20 44H44" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  zoom: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-zoom" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="#1E293B" fill-opacity="0.85"/><circle cx="29" cy="29" r="11" stroke="#FFFFFF" stroke-width="3.5"/><line x1="38" y1="38" x2="48" y2="48" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><line x1="29" y1="23" x2="29" y2="35" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/><line x1="23" y1="29" x2="35" y2="29" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/></svg>`,
  image_error: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-img-error" aria-hidden="true"><rect x="8" y="10" width="48" height="44" rx="8" fill="#E2E8F0"/><circle cx="22" cy="24" r="5" fill="#94A3B8"/><path d="M12 48L26 32L36 42L44 34L52 44V46C52 49.3 49.3 52 46 52H18C14.7 52 12 49.3 12 46V48Z" fill="#94A3B8"/><circle cx="48" cy="18" r="8" fill="#EF4444"/><path d="M48 14V19M48 22V23" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/></svg>`,
  mic_round: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-mic-round" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="#475569"/><rect x="25" y="16" width="14" height="22" rx="7" fill="#FFFFFF"/><path d="M19 28C19 35.1797 24.8203 41 32 41C39.1797 41 45 35.1797 45 28" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><line x1="32" y1="41" x2="32" y2="48" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/></svg>`,
  sticker_star: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-sticker" aria-hidden="true"><polygon points="32,6 40,22 58,25 45,38 48,56 32,48 16,56 19,38 6,25 24,22" fill="#FBBF24" stroke="#D97706" stroke-width="2" stroke-linejoin="round"/></svg>`,
  toast_good: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-toast" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="#22C55E"/><path d="M20 32L28 40L44 24" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  toast_bad: `<svg viewBox="0 0 64 64" fill="none" class="svg-icon-toast" aria-hidden="true"><circle cx="32" cy="32" r="28" fill="#EF4444"/><path d="M32 18V36M32 44V46" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/></svg>`
};
const docIcon = name => solidIcons64[name] || solidIcons64.file;
const icon = name => `<svg viewBox="0 0 24 24" class="svg-icon svg-icon-${esc(name)}" aria-hidden="true">${paths[name] || paths.file}</svg>`;
document.querySelectorAll("[data-icon]").forEach(el => {el.innerHTML=icon(el.dataset.icon);});
const remote = location.hostname !== "127.0.0.1";
let authCsrf="";
const token = remote ? "" : location.hash.slice(1) || sessionStorage.getItem("lineAdminToken") || "";
if(location.hash){if(!remote)sessionStorage.setItem("lineAdminToken",token);history.replaceState(null,"",location.pathname+location.search);}
$("logout").hidden=!remote;
const state={session:null,view:new URLSearchParams(location.search).get("view")||"overview",reports:[],contacts:[],tags:[],jobs:[],cases:[],caseFilter:"all",casePriority:"all",caseQuery:"",savedFilters:[],chatNotes:new Map(),settings:{users:[]},events:[],previews:new Map(),selected:new Set(),tagAudienceMode:"any",selectedAudienceTags:new Set(),selectedFilterId:"",report:null,step:1,audience:"selected",search:"",kind:"all",organization_id:"",department:"",tagFilter:"",page:1,reportFilter:"all",historyFilter:"all",subFilter:"all",busy:false,loaded:false,authLost:false};
const titles={overview:"工作總覽","oa-list":"OA 一覽",chat:"聊天對話",reports:"報告中心",send:"建立發送",cases:"案件管理",contacts:"聯絡對象",subscriptions:"天氣訂閱",history:"發送紀錄",schedule:"排程管理",personnel:"人員與權限","org-settings":"組織設定",organizations:"組織管理",channels:"LINE OA 管理"};
const admin=()=>["platform_admin","org_admin","operator","collaborator"].includes(state.session?.role);
const manager=()=>["platform_admin","org_admin"].includes(state.session?.role);
// 數量上限只由後端 limits.py 定義，經 /api/session 取得
const cap=key=>state.session?.limits?.[key]??"—";
const canSend=()=>["org_admin","operator"].includes(state.session?.role)&&Boolean(state.session?.modules?.messaging);
const superAdmin=()=>state.session?.role==="platform_admin";
const roleName=role=>({platform_admin:"平台管理員",org_admin:"管理員",operator:"操作人員",collaborator:"協作人員"}[role]||role);
const weatherModule=()=>superAdmin()&&state.reports.some(r=>r.report_id==="weather");
let viewAs="",viewKey="",viewOptions=[],principalSession=null,organization="",previewOrganization="",organizationKey="";
const orgName=id=>(state.organizations||[]).find(o=>o.org_id===id)?.name||id||"未指定組織";
const orgKinds={company:"公司",unit:"單位",association:"社團",club:"俱樂部",family:"家庭",personal:"個人工作室",other:"其他"};
const label=r=>r.custom_name||r.display_name||(r.kind==="user"?"未命名個人":"未命名群組");
const caseStatusNames={pending:"待處理",processing:"處理中",waiting:"等待中",ready_to_close:"待結案",closed:"已結案"};
const caseStatusTones={pending:"warn",processing:"primary",waiting:"secondary",ready_to_close:"info",closed:"good"};
const casePriorityNames={low:"低",medium:"一般",high:"高",urgent:"緊急"};
const casePriorityTones={low:"",medium:"good",high:"warn",urgent:"bad"};
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
  const hasCustom=Boolean(r.custom_name);
  const showLineName=hasCustom&&r.display_name&&r.display_name!==primary;
  const truncatedId=r.recipient_id?(r.recipient_id.length>12?r.recipient_id.slice(0,4)+'...'+r.recipient_id.slice(-4):r.recipient_id):'';
  const tags=r.tags||[];
  return `<div class="person"><span class="avatar ${r.kind!=="user"?"group":""}">${esc(primary.slice(0,1))}</span><div><div class="person-title"><strong>${esc(primary)}</strong>${showLineName?`<span class="line-name muted" data-s="s102ad5b">（LINE: ${esc(r.display_name)}）</span>`:''}</div><div class="person-sub"><small class="muted">${r.kind==="user"?"個人聊天室":"群組聊天室"}${!r.active?" · 已停用":""}${truncatedId?` · <span class="line-id-chip">${esc(truncatedId)}</span>`:""}</small></div>${tags.length?`<div class="contact-tags">${tags.map(t=>tagBadge(t)).join("")}</div>`:""}</div></div>`;
};
const scope=r=>r.category==="composition"?(r.organization_id?orgName(r.organization_id):"平台個人素材"):r.scope==="module"?"天氣模組（依帳號／組織授權）":r.category==="text"?"自訂文字訊息":r.scope==="all"?"所有登入使用者":r.scope==="personal"?`${orgName(r.organization_id)} · 個人專屬`:r.scope==="department"?`${orgName(r.organization_id)} / ${r.department}`:`${orgName(r.organization_id)} · 全組織`;
const reportBadge=r=>r.status!=="ready"?badge(r.status==="missing"?"等待報告":"無法使用","bad"):r.stale?badge("非今日更新","warn"):badge(admin()?"可發送":"可查看","good");
let noticeTimeout = null;
function notice(message, error=false){
  const el = $("notice");
  if(el){
    el.textContent = message;
    el.className = "notice" + (error ? " error" : "");
    el.hidden = !message;
  }
  let toast = $("floating-toast");
  if(!toast){
    toast = document.createElement("div");
    toast.id = "floating-toast";
    toast.className = "floating-toast";
    document.body.appendChild(toast);
  }
  if(!message){
    toast.classList.remove("visible");
    return;
  }
  const toastSvg = error ? solidIcons64.toast_bad : solidIcons64.toast_good;
  toast.innerHTML = `<span class="toast-icon">${toastSvg}</span><span class="toast-text">${esc(message)}</span><button class="toast-close" type="button" aria-label="關閉通知">${icon("close")}</button>`;
  toast.className = "floating-toast visible" + (error ? " error" : "");
  const closeBtn = toast.querySelector(".toast-close");
  if(closeBtn) closeBtn.onclick = () => toast.classList.remove("visible");
  if(noticeTimeout) clearTimeout(noticeTimeout);
  noticeTimeout = setTimeout(() => {
    toast.classList.remove("visible");
  }, 4500);
}
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
  organization=rootSession.role==="platform_admin"?"":(memberOptions.some(m=>m.org_id===remembered)?remembered:(rootSession.user.organization_id||""));
  principalSession=organization?await api("/api/session",undefined,true):rootSession;
  $("organization-select").hidden=rootSession.role==="platform_admin"||!memberOptions.length;
  $("organization-select").innerHTML=options(memberOptions.map(m=>[m.org_id,m.name+" · "+roleName(m.role)]),organization);
  viewKey="lineWorkspaceView:"+principalSession.identity+":"+organization;
  viewOptions=["platform_admin","org_admin"].includes(principalSession.role)?(await api("/api/view-options",undefined,true)).users:[];
  let saved="";try{saved=localStorage.getItem(viewKey)||"";}catch(_){}
  const chosen=viewOptions.find(user=>user.email+"|"+user.organization_id===saved);
  viewAs=chosen?.email||"";previewOrganization=chosen?.organization_id||"";
  if(saved&&!viewAs){try{localStorage.removeItem(viewKey);}catch(_){}notice("已返回原帳號：先前預覽的成員資格已失效。",true);}
  state.session=viewAs?await api("/api/session"):principalSession;
  const orgData=await api("/api/organizations");state.organizations=orgData.organizations;state.memberships=orgData.memberships;
  await loadChannels();
  $("switch-view").hidden=!["platform_admin","org_admin"].includes(principalSession.role);
  $("view-banner").hidden=!state.session.preview;
  $("view-description").textContent=state.session.preview?`角色視角：${roleName(state.session.role)} · ${state.session.user.display_name||viewAs}（${viewAs} · ${orgName(state.session.user.organization_id)}） · 實際登入：${principalSession.identity}`:"";
  $("account-name").textContent=state.session.user?.display_name||state.session.identity;
  $("account-role").textContent=(state.session.preview?"預覽 · ":"")+roleName(state.session.role)+(state.session.user?.organization_id?" · "+orgName(state.session.user.organization_id):"");
  $("avatar").textContent=($("account-name").textContent||"L").slice(0,1).toUpperCase();
  document.querySelectorAll("[data-admin]").forEach(el=>{el.hidden=!admin();});document.querySelectorAll("[data-platform]").forEach(el=>{el.hidden=!superAdmin();});
  const reportResult=lineDataReady()&&!superAdmin()?await api("/api/reports"):{reports:[]};state.reports=reportResult.reports;
  // 平台管理員不進入 OA 營運畫面（權限規格 8.1），也不預先讀取客戶資料，避免在客戶操作紀錄留下查看紀錄。
  if(admin()&&lineDataReady()&&!superAdmin()){
    const results=await Promise.all([api("/api/contacts"),api("/api/jobs"),(manager()?api("/api/settings"):Promise.resolve({users:[]})),api("/api/activity"),api("/api/cases"),api("/api/saved-filters")]);
    state.contacts=results[0].contacts;state.tags=results[0].tags||[];state.jobs=results[1].jobs;state.settings=results[2];state.events=results[3].events;state.cases=results[4].cases||[];state.savedFilters=results[5].saved_filters||[];
    state.selected=new Set([...state.selected].filter(id=>state.contacts.some(r=>r.recipient_id===id&&r.active)));
    if(typeof loadChatRooms==="function")await loadChatRooms();
  }else{state.contacts=[];state.tags=[];state.jobs=[];state.cases=[];state.savedFilters=[];state.chatNotes.clear();state.events=[];state.settings=manager()?await api("/api/settings"):{users:[]};state.selected.clear();}
  document.querySelector('nav [data-view="subscriptions"]').hidden=!weatherModule();
  document.querySelector('nav [data-view="send"]').hidden=!admin()||!state.session.modules.messaging;
  // Management menu per level (spec 權限與角色規格 8.3): A sees 組織 + LINE OA, B sees LINE OA + 人員與權限 + 組織設定, C/D see none.
  const orgAdmin=state.session?.role==="org_admin";
  const navAllowed={platform:superAdmin(),org:orgAdmin,"platform-org":superAdmin()||orgAdmin};
  const managementItems=[...document.querySelectorAll("#management-nav [data-nav-role]")];
  managementItems.forEach(el=>{el.hidden=!navAllowed[el.dataset.navRole];});
  $("management-nav-label").hidden=!managementItems.some(el=>!el.hidden);
  // 平台管理員只有管理選單（組織、LINE OA）；工作空間的營運頁面屬於各組織。
  $("workspace-nav-label").hidden=superAdmin();$("workspace-nav").hidden=superAdmin();$("command-open").hidden=superAdmin();
  if(state.view==="settings")state.view=superAdmin()?"organizations":"overview";
  if(state.view==="organizations"&&!superAdmin())state.view="reports";
  if(["personnel","org-settings"].includes(state.view)&&!orgAdmin)state.view="overview";
  if(state.view==="channels"&&!navAllowed["platform-org"])state.view="overview";
  if(!lineDataReady()&&!["organizations","channels","oa-list"].includes(state.view))state.view=superAdmin()?"organizations":"channels";
  if(superAdmin()&&!["organizations","channels"].includes(state.view))state.view="organizations";
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
  if(state.session?.role !== "org_admin") return "";
  const orgId = state.session?.user?.organization_id || "";
  let dismissed = false;
  try{ dismissed = Boolean(localStorage.getItem("lineOnboardingDismissed_" + orgId)); }catch(_){}
  if(dismissed) return "";
  // 權限規格 8.6：完成一項自動打勾；全部完成或按「略過」後不再顯示。
  const hasConnectedOA = lineUI.channels.some(c => c.workspace_id === "o:" + orgId && c.active && !c.shared);
  const hasTemplate = true;
  const hasColleagues = (state.settings?.users||[]).filter(u => u.active && u.organization_id === orgId).length > 1;
  if(hasConnectedOA && hasTemplate && hasColleagues) return "";
  const step = (done, title, detail) => `<li class="onboarding-step ${done?"done":""}"><span class="onboarding-check" aria-hidden="true">${done?icon("check"):""}</span><div class="onboarding-step-body"><strong>${title}</strong><small>${detail}</small></div><span class="sr-only">${done?"已完成":"未完成"}</span></li>`;
  return `<section class="panel onboarding-panel" aria-labelledby="onboarding-title">
    <div class="onboarding-head"><h2 id="onboarding-title">開始使用</h2><button type="button" class="btn text small" data-action="dismiss-onboarding">略過</button></div>
    <ul class="onboarding-steps">
      ${step(hasConnectedOA, "確認 LINE OA 連線", hasConnectedOA ? "已連結 OA" : "請平台管理員在「LINE OA」完成連線")}
      ${step(hasTemplate, "選擇範本包", "已預設啟用通用範本包，可在「LINE OA」調整")}
      ${step(hasColleagues, "新增同事", hasColleagues ? "已建立同事帳號" : "到「人員與權限」新增操作人員或協作人員")}
    </ul>
  </section>`;
}

function overview(){
  const ready=state.reports.filter(r=>r.status==="ready").length, active=state.contacts.filter(r=>r.active).length, subscribed=state.contacts.filter(r=>r.active&&r.weather_subscribed).length;
  const pending=state.jobs.filter(j=>["scheduled","queued","running"].includes(j.status)).length;
  const date=new Date().toLocaleDateString("zh-TW",{month:"long",day:"numeric",weekday:"long"});
  const r=state.reports[0];
  const currentOrgName = orgName(state.session.user?.organization_id) || "—";
  return heading(admin()?"今天的工作，一目了然":"你的報告，都在這裡",`${esc(date)}　·　${admin()?"檢查報告、安排收件對象，掌握每次發送結果。":"依照你的公司、部門與個人權限，查看最新內容。"}`,canSend()?button(icon("plus")+"建立發送","start-send","primary"):button("瀏覽報告 "+icon("arrow"),"go-reports","primary"),"YOUR DAILY WORKSPACE")+
    renderOnboardingCard()+
    `<div class="stats">${stat("可用報告",ready,"份",`已登記 ${state.reports.length} 份報告`,"file")}${admin()?stat("有效聯絡對象",active,"個",`${state.contacts.filter(r=>r.active&&r.kind!=="user").length} 個群組聊天室`,"users")+(weatherModule()?stat("天氣訂閱",subscribed,"個","發送時檢查最新訂閱狀態","bell"):stat("所屬組織",esc(currentOrgName),"","資料依組織隔離","shield"))+stat("進行中的發送",pending,"筆","結果不明的請求不自動重送","send"):stat("所屬部門",esc(state.session.user?.department||"未指定"),"","只顯示獲授權內容","shield")}</div>
    <div class="dashboard-grid"><div class="stack"><section class="panel"><div class="panel-head"><div><h2>報告焦點</h2><p>先確認內容，再開始下一步</p></div><button class="btn text small" data-view="reports">所有報告 ${icon("arrow")}</button></div>${r?`<div class="feature"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><div>${reportBadge(r)}<h3>${esc(r.title)}</h3><p>最後更新　${when(r.modified_at)}</p><p>${esc(scope(r))}</p>${r.stale?'<p>此報告不是今日更新，發送前請確認。</p>':""}${button(canSend()?"預覽並建立發送 "+icon("arrow"):"開啟報告 "+icon("arrow"),canSend()?"choose-report":"preview","dark",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`)}</div></div>`:empty("還沒有可用報告","管理員設定報告來源與權限後，就會顯示在這裡。")}</section>${admin()?`<section class="panel"><div class="panel-head"><h2>最近發送</h2><button class="btn text small" data-view="history">查看全部 ${icon("arrow")}</button></div>${historyList(state.jobs.slice(0,3))}</section>`:""}</div><div class="stack"><section class="panel"><div class="panel-head"><h2>快速前往</h2></div><div class="quick-list">${admin()?quick("聊天對話","查看與回覆 LINE 即時訊息","chat","message"):""}${quick("報告中心","預覽獲授權的模組報告","reports","file")}${admin()?quick("聯絡對象","整理公司、部門與群組","contacts","users")+(weatherModule()?quick("天氣訂閱","管理持續接收通知的對象","subscriptions","bell"):""):""}</div></section><aside class="insight"><h3>${icon("shield")}${admin()?"分對對象，送對報告":"你的資料範圍"}</h3><p>${admin()?"組織報表依公司、部門或個人範圍選擇發送對象。聯絡對象只需在 LINE 收訊，不需後台帳號；需要操作後台的操作人員才須登入授權。":"此處只列出你獲授權的報告。若缺少需要的內容，請聯絡管理員確認公司及部門設定。"}</p></aside></div></div>`;
}
function reportsPage(wizard=false){
  if(!wizard)return workspaceReports();
  const rows=state.reports.filter(r=>state.reportFilter==="all"||r.category===state.reportFilter);
  return (wizard?"":heading("報告中心","預覽最新內容，依公司、部門與個人分配報告。",superAdmin()?(state.settings.weather_report_removed?button("恢復天氣報告","restore-weather",""):"")+button(icon("plus")+"新增報告來源","new-report","primary"):"","REPORT LIBRARY"))+
    `<div class="heading-actions section-space segmented">${[["all","所有報告"],...(state.reports.some(r=>r.category==="weather")?[["weather","天氣報告"]]:[]),["company","組織報表"],["other","其他報告"]].map(([id,text])=>`<button data-action="report-filter" data-id="${id}" class="${state.reportFilter===id?"active":""}">${text}</button>`).join("")}</div><div class="report-grid section-space">${rows.map(r=>`<article class="panel report-card"><div data-preview="${esc(r.report_id)}">${tile(r)}</div><div class="report-card-body">${reportBadge(r)}<h3>${esc(r.title)}</h3><div class="report-meta"><span>${esc(scope(r))}</span><span>${icon("clock")} ${when(r.modified_at)}${r.size?` · ${Math.ceil(r.size/1024)} KB`:""}</span></div><div class="report-card-bottom">${button("預覽","preview","",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`)}${canSend()?button(wizard?"選擇這份報告":"建立發送","choose-report","primary",`data-id="${esc(r.report_id)}" ${r.status!=="ready"?"disabled":""}`):""}</div>${superAdmin()?`<div class="report-card-bottom">${r.report_id!=="weather"?button("設定來源","edit-report","text small",`data-id="${esc(r.report_id)}"`):""}${button("移除報告","remove-report","text small",`data-id="${esc(r.report_id)}"`)}</div>`:""}</div></article>`).join("")}</div>${rows.length?"":empty("這裡還沒有報告",admin()?"新增來源後，外部程式產生的 PNG 就會顯示在報告中心。":"管理員授權報告後，你就能在這裡查看。")}`;
}
function eligible(r){const source=state.report;if(source?.category==="composition")return !source.organization_id||r.organization_id===source.organization_id;if(!source||source.category==="text"||source.report_id==="weather")return true;if(r.organization_id!==source.organization_id)return false;if(source.scope==="department")return r.department===source.department;if(source.scope==="personal")return r.recipient_id===source.owner_recipient_id;return true;}
function filteredContacts(){return state.contacts.filter(r=>{const q=state.search.toLowerCase();const tagMatch=!state.tagFilter||((r.tags||[]).some(t=>String(t.id)===String(state.tagFilter)||t.name===state.tagFilter));const searchMatch=!q||`${label(r)} ${r.display_name||""} ${r.recipient_id||""} ${r.organization_id||""} ${r.department||""} ${r.notes||""} ${(r.tags||[]).map(t=>t.name).join(" ")}`.toLowerCase().includes(q);const kindMatch=state.kind==="all"||(state.kind==="group"?r.kind!=="user":r.kind===state.kind);const companyMatch=!state.organization_id||r.organization_id===state.organization_id;const deptMatch=!state.department||r.department===state.department;const sendEligible=state.view!=="send"||(r.active&&eligible(r));const subMatch=state.view!=="subscriptions"||state.subFilter==="all"||Boolean(r.weather_subscribed)===(state.subFilter==="on");return tagMatch&&searchMatch&&kindMatch&&companyMatch&&deptMatch&&sendEligible&&subMatch;});}
function contactsMatchingTags(tagIds, mode="any"){
  if(!tagIds||!tagIds.length)return [];
  const tagSet=new Set(tagIds.map(String));
  return state.contacts.filter(r=>{
    if(!r.active||!eligible(r))return false;
    const cTags=(r.tags||[]).map(t=>String(t.id));
    if(mode==="all")return tagIds.every(tid=>cTags.includes(String(tid)));
    return (r.tags||[]).some(t=>tagSet.has(String(t.id)));
  });
}

function contactsMatchingFilter(criteria){
  if(!criteria)return [];
  return state.contacts.filter(r=>{
    if(!r.active||!eligible(r))return false;
    if(criteria.kind&&criteria.kind!=="all"&&r.kind!==criteria.kind)return false;
    if(criteria.organization_id&&r.organization_id!==criteria.organization_id)return false;
    if(criteria.department&&r.department!==criteria.department)return false;
    if(criteria.tag&&!(r.tags||[]).some(t=>String(t.id)===String(criteria.tag)||t.name===criteria.tag))return false;
    if(criteria.search){
      const q=criteria.search.toLowerCase();
      const match=`${label(r)} ${r.display_name||""} ${r.recipient_id||""} ${r.organization_id||""} ${r.department||""} ${r.notes||""} ${(r.tags||[]).map(t=>t.name).join(" ")}`.toLowerCase().includes(q);
      if(!match)return false;
    }
    return true;
  });
}

function renderAudienceTagsSelector(){
  const selectedTagIds=Array.from(state.selectedAudienceTags||[]);
  const matched=contactsMatchingTags(selectedTagIds,state.tagAudienceMode||"any");
  
  return `<div class="audience-filter-panel" data-s="sa4e96ca">
    <div data-s="sea15b2f">
      <div>
        <h3 data-s="s49d7aa6">依標籤篩選發送對象</h3>
        <p class="muted" data-s="s38f2a08">勾選一或多個標籤，自動計算符合條件的聯絡對象</p>
      </div>
      <div class="segmented" role="group" aria-label="標籤比對方式">
        <button type="button" class="${state.tagAudienceMode==='any'?'active':''}" data-action="tag-audience-mode" data-id="any">符合任一標籤（OR）</button>
        <button type="button" class="${state.tagAudienceMode==='all'?'active':''}" data-action="tag-audience-mode" data-id="all">符合全部標籤（AND）</button>
      </div>
    </div>
    <div data-s="se6302cf">
      ${(state.tags||[]).map(t=>{
        const count=state.contacts.filter(r=>r.active&&eligible(r)&&(r.tags||[]).some(x=>String(x.id)===String(t.id))).length;
        const isChecked=state.selectedAudienceTags.has(String(t.id));
        return `<label class="check-label" style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--soft,#f8fafc);border:1px solid ${isChecked?'var(--primary,#00B900)':'var(--line,#e2e8f0)'};border-radius:10px;cursor:pointer;">
          <div data-s="se3f6104">
            <input type="checkbox" name="audience-tag" value="${esc(t.id)}" ${isChecked?'checked':''}>
            ${tagBadge(t)}
          </div>
          <small class="muted">${count} 人</small>
        </label>`;
      }).join("")||'<p class="muted">目前尚未建立任何標籤。</p>'}
    </div>
    <div data-s="sc673a02">
      <div data-s="s5a9738f">
        <strong>符合對象預覽（共 ${matched.length} 個聊天室）</strong>
        <small class="muted">${selectedTagIds.length?`已選 ${selectedTagIds.length} 個標籤`:'請先勾選上方標籤'}</small>
      </div>
      <div data-s="s5a530b0">
        ${matched.map(r=>`<span class="badge good" data-s="se71ae94">${esc(label(r))}</span>`).join("")||'<small class="muted">尚無符合對象</small>'}
      </div>
    </div>
  </div>`;
}

function renderAudienceSavedFiltersSelector(){
  const chosenFilter=(state.savedFilters||[]).find(f=>f.filter_id===state.selectedFilterId);
  const matched=chosenFilter?contactsMatchingFilter(chosenFilter.criteria):[];
  
  return `<div class="audience-filter-panel" data-s="sa4e96ca">
    <div data-s="s79a1c5a">
      <h3 data-s="s49d7aa6">依自訂篩選條件傳訊</h3>
      <p class="muted" data-s="s38f2a08">選擇已儲存的篩選組合，帶入目前符合的對象</p>
    </div>
    <div data-s="se02dbda">
      ${(state.savedFilters||[]).map(f=>{
        const count=contactsMatchingFilter(f.criteria).length;
        const isSelected=state.selectedFilterId===f.filter_id;
        return `<label class="check-label" style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--soft,#f8fafc);border:1px solid ${isSelected?'var(--primary,#00B900)':'var(--line,#e2e8f0)'};border-radius:12px;cursor:pointer;">
          <div>
            <div data-s="se3f6104">
              <input type="radio" name="audience-saved-filter" value="${esc(f.filter_id)}" ${isSelected?'checked':''}>
              <strong>${esc(f.name)}</strong>
            </div>
          </div>
          <span class="badge ${count?'good':''}">${count} 人</span>
        </label>`;
      }).join("")||'<p class="muted">目前尚未建立自訂篩選條件。可在「聯絡對象」搜尋篩選後儲存。</p>'}
    </div>
    <div data-s="sc673a02">
      <div data-s="s5a9738f">
        <strong>符合對象預覽（共 ${matched.length} 個聊天室）</strong>
        <small class="muted">${chosenFilter?`條件：「${esc(chosenFilter.name)}」`:'請先選擇上方篩選條件'}</small>
      </div>
      <div data-s="s5a530b0">
        ${matched.map(r=>`<span class="badge good" data-s="se71ae94">${esc(label(r))}</span>`).join("")||'<small class="muted">尚無符合對象</small>'}
      </div>
    </div>
  </div>`;
}

function contactToolbar(){
  const organization_ids=[...new Set(state.contacts.map(r=>r.organization_id).filter(Boolean))],depts=[...new Set(state.contacts.filter(r=>!state.organization_id||r.organization_id===state.organization_id).map(r=>r.department).filter(Boolean))];
  const tagOpts=[["","所有標籤"],...(state.tags||[]).map(t=>[t.id,t.name])];
  const filterOpts=[["","自訂篩選條件..."],...(state.savedFilters||[]).map(f=>[f.filter_id,f.name])];
  return `<div class="toolbar">
    <label class="search-field">${icon("search")}<input id="contact-search" value="${esc(state.search)}" placeholder="搜尋姓名、LINE 名稱、ID、備忘或標籤" aria-label="搜尋聯絡對象"></label>
    <select id="contact-kind" aria-label="聊天室類型">${options([["all","所有聊天室"],["user","個人"],["group","群組"]],state.kind)}</select>
    <select id="contact-tag-filter" aria-label="篩選標籤">${options(tagOpts,state.tagFilter)}</select>
    <select id="contact-company" aria-label="篩選公司">${options([["","所有組織"],...organization_ids.map(c=>[c,orgName(c)])],state.organization_id)}</select>
    <select id="contact-department" aria-label="篩選部門">${options([["","所有部門"],...depts.map(c=>[c,c])],state.department)}</select>
    ${state.savedFilters?.length?`<select id="apply-saved-filter" aria-label="套用自訂篩選">${options(filterOpts,"")}</select>`:""}
    ${canSend()&&state.view==="contacts"?button(icon("send")+"對篩選對象發送 ("+filteredContacts().length+")","send-to-filtered","small primary"):""}
    ${manager()&&state.view==="contacts"?button("儲存篩選","open-save-filter-modal","small")+button(icon("settings")+"標籤管理","manage-tags","small"):""}
  </div>`;
}
function contactList(){const rows=filteredContacts(),pages=Math.max(1,Math.ceil(rows.length/10));state.page=Math.min(state.page,pages);const visible=rows.slice((state.page-1)*10,state.page*10);const isSendAudience=state.view==="send"&&state.audience==="selected";const isContactsView=state.view==="contacts"&&manager();const showCheckboxes=isSendAudience||isContactsView;const selectedCount=state.selected.size;let bulkBar="";if(isContactsView&&selectedCount>0){bulkBar=`<div class="bulk-toolbar"><div><strong>已選取 ${selectedCount} 個聯絡對象</strong></div><div class="bulk-actions">${canSend()?button(icon("send")+"對已選對象發送","send-to-selected","small primary"):""}${button("批次加標籤","bulk-add-tags","small")}${button("批次移除標籤","bulk-remove-tags","small")}${weatherModule()?button("批次開啟訂閱","bulk-sub-on","small")+button("批次取消訂閱","bulk-sub-off","small"):""}${button("清除勾選","clear-selection","text small")}</div></div>`;}else if(isSendAudience){bulkBar=`<div class="toolbar">${button("勾選本頁","select-page","small")}${button("清除勾選","clear-selection","text small")}<small class="muted">共 ${rows.length} 個符合報告範圍的聊天室</small></div>`;}return `${bulkBar}<div class="table-scroll"><table class="contacts-table"><thead><tr><th class="select-cell">${showCheckboxes?`<input type="checkbox" id="select-all-visible" aria-label="全選本頁" ${visible.length&&visible.every(r=>state.selected.has(r.recipient_id))?"checked":""}>`:""}</th><th>聯絡對象</th><th>組織／部門</th>${weatherModule()?"<th>天氣訂閱</th>":""}<th>操作</th></tr></thead><tbody>${visible.map(r=>`<tr><td class="select-cell">${showCheckboxes?`<input type="checkbox" data-select="${esc(r.recipient_id)}" aria-label="選取 ${esc(label(r))}" ${state.selected.has(r.recipient_id)?"checked":""}>`:""}</td><td class="person-cell">${state.view==="contacts"?`<button class="contact-open" data-action="contact-detail" data-id="${esc(r.recipient_id)}" aria-label="查看 ${esc(label(r))} 詳情">${person(r)}</button>`:person(r)}</td><td class="meta-cell">${esc(r.organization_id?orgName(r.organization_id):"尚未分類")}<small class="muted">${r.department?" / "+esc(r.department):""}</small></td>${weatherModule()?`<td class="sub-cell">${badge(r.weather_subscribed?"已訂閱":"未訂閱",r.weather_subscribed?"good":"")}</td>`:""}<td class="action-cell">${manager()?button("管理","edit-contact","small",`data-id="${esc(r.recipient_id)}"`):badge("已授權")}</td></tr>`).join("")}</tbody></table></div>${!rows.length?empty("沒有符合的聯絡對象",state.view==="send"?"請確認聯絡對象的組織／部門分類符合報告範圍，並已與 Bot 互動。":"調整篩選條件，或請使用者向 Bot 傳送訊息以建立名單。"):""}<div class="pagination"><span>共 ${rows.length} 個聊天室</span><div>${button("上一頁","prev-page","small",state.page<=1?"disabled":"")}<span>${state.page} / ${pages}</span>${button("下一頁","next-page","small",state.page>=pages?"disabled":"")}</div></div>`;}
function contactsPage(subscriptions=false){return heading(subscriptions?"天氣訂閱":"聯絡對象",subscriptions?"訂閱決定持續接收通知的對象；每次發送仍由管理員確認。":"依公司與部門整理個人、群組，自訂名稱與筆記，讓報告送到正確的地方。",(manager()?button(icon("refresh")+"更新 LINE 名稱","profiles"):""),subscriptions?"SUBSCRIPTIONS":"CONTACT DIRECTORY")+(subscriptions?`<div class="insight"><h3>${icon("bell")}個人自行訂閱，群組由管理員設定</h3><p>私訊 Bot「訂閱天氣」「取消訂閱」「我的訂閱」即可管理個人訂閱。目前由管理員發送，可指定單次傳送時間，尚未啟用每日循環排程。</p></div><div class="segmented section-space">${[["all","全部"],["on","已訂閱"],["off","未訂閱"]].map(([id,t])=>`<button data-action="sub-filter" data-id="${id}" class="${state.subFilter===id?"active":""}">${t}</button>`).join("")}</div>`:"")+`<div class="library-split section-space ${!subscriptions&&workspaceUI.contactDetail?"has-detail":""}"><section class="panel">${contactToolbar()}<div id="contact-list">${contactList()}</div></section>${subscriptions?"":contactDetailPanel()}</div>`;}
function selectedRows(){return state.contacts.filter(r=>r.active&&eligible(r)&&(state.audience==="subscribers"?r.weather_subscribed:state.selected.has(r.recipient_id)));}
function selectionSummary(){const rows=selectedRows();return `<div class="panel selection-summary"><div class="panel-body">${tile(state.report)}<p class="eyebrow section-space">THIS DELIVERY</p><h3>${esc(state.report.title)}</h3><p class="subtitle">${esc(scope(state.report))}</p><div class="count-big">${rows.length}<small>個聊天室</small></div><div class="summary-list">${rows.map(r=>`<span>${esc(label(r))}</span>`).join("")||'<small class="muted">請從名單選擇發送對象</small>'}</div><p class="callout">每個聊天室會收到這次確認的內容。一次性勾選不會改變訂閱設定。</p></div></div>`;}
function sendPage(){
  const r=state.report;
  const audienceOptions=[["selected","手動選擇"],["by-tags","依標籤傳訊"],["by-filter","依自訂條件"]];
  if(r?.report_id==="weather")audienceOptions.push(["subscribers","天氣訂閱名單"]);

  return heading("建立發送","依序確認報告、對象與內容，每次發送都有完整紀錄。","","NEW DELIVERY")+
    `<div class="steps">${["編輯內容","選擇對象","確認發送"].map((t,i)=>`${i?'<span class="step-line"></span>':""}<span class="step ${state.step===i+1?"active":""}"><b>${i+1}</b>${t}</span>`).join("")}</div>`+
    (state.step===1||!r?composerEditor()+`<section class="panel panel-body section-space"><h2>文字訊息</h2><p class="subtitle">輸入公告或提醒，下一步選擇發送對象與傳送時間。</p><textarea id="message-draft" maxlength="5000" rows="5" placeholder="輸入要傳送的文字">${esc(state.textDraft||"")}</textarea><div class="form-actions">${button("使用這段文字","choose-text","primary")}</div></section>`+reportsPage(true):
     state.step===2?`<div class="send-grid"><section class="panel"><div class="panel-head"><div><h2>這次要發給誰？</h2><p>僅列出符合報告組織／部門／個人範圍的有效聯絡對象</p></div></div>
     <div class="toolbar segmented">${audienceOptions.map(([id,t])=>`<button data-action="audience" data-id="${id}" class="${state.audience===id?"active":""}">${t}</button>`).join("")}</div>
     ${state.audience==="selected"?contactToolbar()+`<div id="contact-list">${contactList()}</div>`:
       state.audience==="by-tags"?renderAudienceTagsSelector():
       state.audience==="by-filter"?renderAudienceSavedFiltersSelector():
       `<div class="panel-body"><p class="callout">目前有 ${selectedRows().length} 個有效天氣訂閱。發送時會再次檢查訂閱狀態，尚未送出的取消訂閱會自動排除。</p></div>`}
     <div class="selection-footer">${button("返回編輯","back-report")}${button("下一步：確認發送 "+icon("arrow"),"review","primary",`id="review-button" ${selectedRows().length?"":"disabled"}`)}</div></section><aside id="selection-summary">${selectionSummary()}</aside></div>`:
     confirmation());
}
function confirmation(){
  const r=state.report,rows=selectedRows();
  const audienceText=state.audience==="subscribers"?"天氣訂閱名單":state.audience==="by-tags"?"依標籤傳訊":state.audience==="by-filter"?"依自訂篩選條件":"手動選擇";
  return `<section class="panel"><div class="panel-head"><h2>確認這次的發送內容</h2>${reportBadge(r)}</div><div class="panel-body confirm-grid"><div>${["text","composition"].includes(r.category)?tile(r):`<img class="confirm-preview" src="${r.preview}" alt="${esc(r.title)} 完整預覽"><p class="subtitle">內容更新時間：${when(r.modified_at)}</p>`}</div><div><p class="eyebrow">DELIVERY SUMMARY</p><h2>${esc(r.title)}</h2><div class="detail-row"><span>發送方式</span><strong>${audienceText}</strong></div><div class="detail-row"><span>發送 OA</span><strong>${esc(selectedOA()?.name||"既有 OA")}</strong></div><div class="detail-row"><span>工作區</span><strong>${esc(selectedWorkspace()?.name||"目前工作區")}</strong></div><div class="detail-row"><span>收件聊天室</span><strong>${rows.length} 個（${rows.filter(x=>x.kind==="user").length} 個人／${rows.filter(x=>x.kind!=="user").length} 群組）</strong></div><div class="detail-row"><span>操作人</span><strong>${esc(state.session.identity)}</strong></div><div class="summary-list">${rows.map(x=>`<span>${esc(label(x))}</span>`).join("")}</div><p class="callout warn" data-s="se9d9bb6">此類訊息一律計入當月訊息額度（預估使用 <strong>${rows.length} 則</strong>額度，群組聊天室依實際人數計扣）。</p><p class="callout">送出前會再次檢查報告版本與收件範圍。LINE 已接受代表 API 受理，不代表對方已讀。</p>${scheduleFields()}${r.stale?'<p class="callout warn">這份報告不是今天更新。請確認日期與內容適用於這次發送。</p><label class="check-label"><input id="allow-stale" type="checkbox">我已確認，可以發送這份較早的報告</label>':""}<div class="form-actions">${button("上一步","back-recipients")}${button(icon("send")+`確認發送給 ${rows.length} 個聊天室`,"submit-send","primary",`id="submit-send" ${state.busy||!rows.length?"disabled":""}`)}</div></div></div></section>`;
}
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
        ${c.is_locked?'<span class="badge warn" style="font-size:10px;">已鎖定</span>':''}
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
    ${c.status==="waiting"?`<div class="case-waiting-info"><p><strong>等待對象：</strong>${waitingPartyNames[c.waiting_party]||c.waiting_party||"未指定"}（自 ${when(c.waiting_since)}）</p><p><strong>原因：</strong>${esc(c.waiting_reason||"無")}</p></div>`:""}
    ${c.status==="closed"?`<div class="case-closed-info"><p><strong>結案說明：</strong>${esc(c.resolution||"已結案")}（結案於 ${when(c.closed_at)}）</p></div>`:""}
    <div class="case-card-actions">
      ${c.status==="pending"?button("開始處理","case-to-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="processing"?button("進入等待","open-case-waiting-modal","small",`data-id="${esc(c.case_id)}"`)+button("進入待結案","case-to-ready","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="waiting"?button("恢復處理","case-resume-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="ready_to_close"?button("退回處理","case-back-processing","small",`data-id="${esc(c.case_id)}"`)+button("執行結案","open-case-close-modal","good primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="closed"?badge("已完成結案","good"):""}
      <button class="btn text small" data-action="toggle-case-lock" data-id="${esc(c.case_id)}">${c.is_locked?'解鎖':'鎖定'}</button>
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
    <div data-s="s1d8943f">
      <button class="btn small" data-action="export-cases-csv">${icon("download")} 匯出 CSV</button>
      <button class="btn small" data-action="export-cases-xlsx">${icon("download")} 匯出 XLSX</button>
    </div>
  ` : '';

  return heading("案件管理","追蹤從對話與聯絡對象建立的案件，掌握各階段進度。",`<div data-s="sb9bbe54">${exportButtons}${button(icon("plus")+"建立案件","new-case-modal","primary")}</div>`,"CASE MANAGEMENT")+
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
          ${options([["all","所有優先度"],["urgent","緊急"],["high","高"],["medium","一般"],["low","低"]],state.casePriority)}
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
    ${continuedFrom ? `<input type="hidden" name="continued_from_id" value="${esc(continuedFrom)}"><div class="callout" data-s="s3ef1fa1">此案件將作為延續案件關聯至前案歷程。</div>` : ''}
    <div data-s="s40eee6f">
      <span class="muted" data-s="s9e6595f">填寫案件需求或從範本包帶入</span>
      <button type="button" class="btn text small" data-action="open-template-picker" data-subject="${esc(subject_id)}">從範本帶入</button>
    </div>
    <div class="form-grid">
      <div class="full">${field("案件標題","title",title,'required maxlength="100" placeholder="例如：詢問 10 月發票開立方式、報表格式問題"')}</div>
      ${selectField("案件主體（聯絡對象）","case_subject_id",contactOpts,subject_id)}
      ${field("案件類別","category",cat,'maxlength="50" placeholder="例如：一般、諮詢、維修、訂單"')}
      ${selectField("優先度","priority",[["medium","一般"],["low","低"],["high","高"],["urgent","緊急"]],prefill.priority||"medium")}
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
      else if(a.action==="status_change")desc=`狀態變更：${caseStatusNames[a.details?.old_status]||a.details?.old_status} <span class="status-change-arrow" aria-hidden="true">${icon("arrow")}</span> <strong>${caseStatusNames[a.details?.new_status]||a.details?.new_status}</strong>${a.details?.waiting_party?`（等待：${waitingPartyNames[a.details.waiting_party]||a.details.waiting_party}，原因：${esc(a.details.waiting_reason||"")}）`:""}${a.details?.resolution?`（結案說明：${esc(a.details.resolution)}）`:""}`;
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
          ${c.is_locked?'<span class="badge warn" style="font-size:10px;">已鎖定</span>':''}
        </div>
        <div data-s="sbabd711">
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
      
      <div class="section-space" data-s="s78cead6">
        ${canSend() && c.status !== "closed" ? `<button class="btn primary small" data-action="open-case-notify-modal" data-id="${esc(c.case_id)}">通知案件對象</button>` : ''}
        <button class="btn small" data-action="save-case-as-template" data-id="${esc(c.case_id)}">存為案件範本</button>
      </div>

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
    <div data-s="s40eee6f">
      <span class="muted" data-s="s9e6595f">填寫對話重要記事或從範本包帶入</span>
      <button type="button" class="btn text small" data-action="open-note-template-picker" data-recipient="${esc(recipient_id)}">從範本帶入</button>
    </div>
    <div class="form-grid">
      <div class="full">${field("記事標題（選填）", "title", title, 'maxlength="50" placeholder="例如：客戶詢問保固條件、確認發票開立"')}</div>
      ${selectField("記事類型", "note_type", typeOptions, note_type)}
      ${field("完成期限（選填）", "due_date", due_date, 'type="date"')}
      <div class="full">${field(`記事標籤（以逗號分隔，最多 ${cap("TAGS_PER_NOTE")} 個）`, "tags", tagsStr, 'maxlength="100" placeholder="例如：重要, 報修, 聯絡紀錄"')}</div>
      <div class="full"><label class="field">記事內容（1–1,000 字）<textarea name="content" rows="4" required minlength="1" maxlength="1000" placeholder="記錄該聊天室的重要交辦、對話摘要、待確認事項...">${esc(content)}</textarea></label></div>
    </div>
    <p class="callout">對話記事本獨立於聯絡對象筆記，專屬於此 OA 聊天室對話。支援置頂 (最多 ${cap("PINNED_NOTES_PER_ROOM")} 筆)、鎖定防誤改與 ${cap("NOTE_TRASH_DAYS")} 天回收筒還原。</p>
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
      modal("選擇範本", '<p class="muted" data-s="sc951e35">尚未啟用含有此類型範本的範本包。</p>');
      return;
    }

    const html = `<div class="template-picker-container" data-s="s2940a45">
      ${groups.map(g => `
        <div class="template-pack-group" data-s="s79a1c5a">
          <h4 data-s="s86a940d">範本包：${esc(g.pack_name)}</h4>
          <div data-s="sed54c91">
            ${(g.templates || []).map(t => {
              const title = t.rendered_title || t.title || "";
              const body = t.rendered_body || t.body || "";
              const cat = t.category_name || "一般";
              const pri = t.defaults?.priority || "medium";
              const tags = (t.defaults?.tags || []).join(", ");

              if (target_type === "note") {
                return `<div class="template-card" data-s="s1f15671">
                  <div data-s="s8129723">
                    <strong>${esc(t.name || t.title)}</strong>
                    <button type="button" class="btn small primary" data-action="apply-note-template" data-recipient="${esc(subject_id)}" data-title="${esc(title)}" data-body="${esc(body)}" data-cat="${esc(cat)}" data-tags="${esc(tags)}">套用此記事範本</button>
                  </div>
                  <div data-s="s60946a2"><span class="badge" data-s="se48b058">${esc(cat)}</span></div>
                  <p data-s="s0bcd782">${esc(body)}</p>
                </div>`;
              } else {
                return `<div class="template-card" data-s="s1f15671">
                  <div data-s="s8129723">
                    <strong>${esc(t.name || t.title)}</strong>
                    <button type="button" class="btn small primary" data-action="apply-case-template" data-subject="${esc(subject_id)}" data-title="${esc(title)}" data-desc="${esc(body)}" data-cat="${esc(cat)}" data-pri="${esc(pri)}">套用此案件範本</button>
                  </div>
                  <div data-s="s60946a2"><span class="badge" data-s="se48b058">${esc(cat)}</span></div>
                  <p data-s="s0bcd782">${esc(body)}</p>
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
    organization_id:state.organization_id||undefined,
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
    <p class="callout">每個 OA 最多保存 ${cap("SAVED_FILTERS_PER_OA")} 組自訂篩選條件，同 OA 管理員共用。</p>
    <div class="form-actions"><button class="btn primary" type="submit">儲存篩選條件</button></div>
  </form>`);
}

function caseNotifyModal(case_id){
  const c = (state.cases||[]).find(x=>x.case_id===case_id);
  if(!c) return;
  const subject = state.contacts.find(x=>x.recipient_id===c.case_subject_id);
  const subjectName = subject ? label(subject) : (c.case_subject_id || "案件對象");

  modal(`通知案件對象：${esc(c.case_no)}`, `<form id="case-notify-form" data-id="${esc(case_id)}">
    <div class="form-grid">
      <div class="full">
        <label class="field">接收對象（案件主體）
          <input value="${esc(subjectName)}" readonly>
        </label>
      </div>
      <div class="full">
        <label class="field">通知訊息內容（1 至 1,000 字）
          <textarea name="message_text" rows="5" required maxlength="1000" placeholder="例如：您好，您申請的報修案件（編號 ${esc(c.case_no)}）已完成零件更換，將於明日安排配送，謝謝！"></textarea>
        </label>
      </div>
    </div>
    <div class="callout warn" data-s="sd8a81ea">
      <strong>額度提醒：</strong>此訊息將透過 LINE 官方帳號以推播 (Push) 發送給 ${esc(subjectName)}，並計入本月發送額度。送出後將自動寫入案件處理紀錄。
    </div>
    <div class="form-actions">
      <button class="btn primary" type="submit">確認發送通知</button>
    </div>
  </form>`);
}

async function saveAsTemplateModal(source_type, source_id){
  modal("存成範本", '<div class="loading-panel"><span class="spinner"></span><p>讀取自訂範本包…</p></div>');
  try{
    const res = await api('/api/template-packs');
    const customPacks = (res.packs||[]).filter(p=>!p.is_preset&&!p.is_locked);
    if(!customPacks.length){
      modal("存成範本", '<p class="callout warn">目前沒有可編輯的自訂範本包。請先至「範本與分類」建立或複製自訂範本包。</p>');
      return;
    }
    const packOpts = customPacks.map(p=>[p.pack_id, p.name]);
    
    let defaultName = "";
    if(source_type === "case"){
      const c = (state.cases||[]).find(x=>x.case_id===source_id);
      defaultName = c ? `${c.title} 範本` : "新案件範本";
    } else {
      defaultName = "新記事範本";
    }

    modal("存成自訂範本", `<form id="save-as-template-form" data-type="${esc(source_type)}" data-id="${esc(source_id)}">
      <div class="form-grid">
        <div class="full">${selectField("目標自訂範本包", "target_pack_id", packOpts, packOpts[0][0])}</div>
        <div class="full">${field("新範本名稱", "name", defaultName, 'required maxlength="30" placeholder="例如：設備報修標準流程"')}</div>
      </div>
      <p class="callout">將由此${source_type==="case"?"案件":"記事"}提取標題、分類與內容建立新範本（不包含對象與處理歷史）。</p>
      <div class="form-actions"><button class="btn primary" type="submit">建立範本</button></div>
    </form>`);
  }catch(e){
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

let templatesTab = "packs";
let selectedPackKey = "universal";

async function templatesAndCategoriesPage(){
  const container = `<div class="templates-management-container">
    ${heading("範本與分類管理", "管理此 OA 啟用的範本包、自訂案件/記事範本與分類項目。", manager() ? `<div data-s="sb9bbe54"><button class="btn primary small" data-action="new-custom-pack">+ 新增自訂範本包</button></div>` : "", "TEMPLATES & CATEGORIES")}
    <div class="segmented toolbar section-space">
      <button data-action="templates-tab" data-id="packs" class="${templatesTab==='packs'?'active':''}">範本包與範本</button>
      <button data-action="templates-tab" data-id="note_types" class="${templatesTab==='note_types'?'active':''}">記事類型清單</button>
      <button data-action="templates-tab" data-id="case_categories" class="${templatesTab==='case_categories'?'active':''}">案件類別清單</button>
    </div>
    <div id="templates-tab-content">
      <div class="loading-panel"><span class="spinner"></span><p>讀取範本與分類資料…</p></div>
    </div>
  </div>`;
  setTimeout(()=>loadTemplatesTabContent(), 10);
  return container;
}

async function loadTemplatesTabContent(){
  const wrap = $("templates-tab-content");
  if(!wrap) return;
  try{
    if(templatesTab === "packs"){
      const [packsRes, catRes] = await Promise.all([api('/api/template-packs'), api('/api/categories')]);
      const packs = packsRes.packs || [];
      const currentPack = packs.find(p=>p.pack_id===selectedPackKey || p.key===selectedPackKey) || packs[0];
      if(currentPack) selectedPackKey = currentPack.pack_id || currentPack.key;

      wrap.innerHTML = `<div class="packs-layout" data-s="sddda873">
        <!-- Left: Packs list -->
        <div class="panel packs-sidebar" data-s="scf37034">
          <h4 data-s="s81cee80">範本包清單</h4>
          <div class="packs-nav-list" data-s="s9d3009e">
            ${packs.map(p=>{
              const isSelected = (p.pack_id === selectedPackKey || p.key === selectedPackKey);
              return `<div class="pack-nav-card ${isSelected?'selected':''}" style="border:1px solid ${isSelected?'#00B900':'var(--line,#e2e8f0)'};border-radius:8px;padding:10px;background:${isSelected?'rgba(0,185,0,0.05)':'var(--card-bg,#fff)'};display:flex;justify-content:space-between;align-items:center;">
                <div data-s="s692a5e9" data-action="select-template-pack" data-id="${esc(p.pack_id||p.key)}">
                  <strong>${esc(p.name)}</strong>
                  ${p.is_preset ? '<span class="badge" data-s="s2de18ee">預設</span>' : '<span class="badge primary" data-s="s2de18ee">自訂</span>'}
                  ${p.is_locked ? ' <span class="badge warn" style="font-size:10px;">已鎖定</span>' : ''}
                  <div data-s="s0fc87c1">${esc(p.description||"無說明")}</div>
                </div>
                <label data-s="sf086b8f">
                  <input type="checkbox" data-action="toggle-pack-enable" data-id="${esc(p.pack_id||p.key)}" ${p.is_enabled?'checked':''}>
                  啟用
                </label>
              </div>`;
            }).join("")}
          </div>
        </div>

        <!-- Right: Pack detail & templates -->
        <div class="panel pack-detail-content" data-s="s8cddc29">
          ${currentPack ? renderPackDetailSection(currentPack) : '<p class="muted">請選擇範本包</p>'}
        </div>
      </div>`;
    } else if(templatesTab === "note_types" || templatesTab === "case_categories"){
      const catRes = await api('/api/categories');
      const isCase = (templatesTab === "case_categories");
      const list = isCase ? catRes.case_categories : catRes.note_categories;
      const typeKey = isCase ? "case" : "note";

      wrap.innerHTML = `<div class="panel" data-s="s57342d1">
        <div data-s="sbcbb844">
          <div>
            <h3 data-s="sa8be156">${isCase?'案件類別':'記事類型'}清單（${list.length}/20 項）</h3>
            <p class="subtitle" data-s="s1da9fac">自訂目前 OA 的分類項目。「一般」為系統保留項目不可刪除或改名。</p>
          </div>
          ${manager() && list.length < 20 ? `<button class="btn primary small" data-action="new-single-category" data-type="${typeKey}">+ 新增${isCase?'類別':'類型'}</button>` : ''}
        </div>
        <div class="categories-list" data-s="sf67b86e">
          ${list.map((c, idx)=>`
            <div class="category-item-row" data-s="s96a60f9">
              <div data-s="se3f6104">
                <span class="muted" data-s="s2044f28">#${idx+1}</span>
                <strong>${esc(c.name)}</strong>
                ${c.name === '一般' ? '<span class="badge" data-s="s0c8a27e">系統保留</span>' : ''}
                <span class="muted" data-s="se71ae94">（使用中：${c.usage_count||0} 筆）</span>
              </div>
              ${manager() && c.name !== '一般' ? `
                <div data-s="s1d8943f">
                  <button class="btn text small" data-action="edit-single-category" data-type="${typeKey}" data-name="${esc(c.name)}">改名</button>
                  <button class="btn text small danger" data-action="delete-single-category" data-type="${typeKey}" data-name="${esc(c.name)}">刪除</button>
                </div>
              ` : ''}
            </div>
          `).join("")}
        </div>
      </div>`;
    }
  }catch(e){
    wrap.innerHTML = `<p class="callout warn">${esc(e.message)}</p>`;
  }
}

function renderPackDetailSection(p){
  const isPreset = p.is_preset;
  const isLocked = p.is_locked;
  const caseTemplates = p.case_templates || [];
  const noteTemplates = p.note_templates || [];

  return `<div>
    <div data-s="s60ad40f">
      <div>
        <h2 data-s="sa353e69">${esc(p.name)} ${isLocked?'<span class="badge warn" style="font-size:12px;vertical-align:middle;">已鎖定</span>':''}</h2>
        <p class="subtitle" data-s="s1da9fac">${esc(p.description||"無說明")}</p>
      </div>
      <div data-s="s1d8943f">
        <button class="btn small" data-action="preview-apply-categories" data-id="${esc(p.pack_id||p.key)}">套用此分類組合至 OA</button>
        <button class="btn small" data-action="copy-pack-modal" data-id="${esc(p.pack_id||p.key)}">複製為新範本包</button>
        ${!isPreset && manager() ? `
          <button class="btn small" data-action="toggle-pack-lock-btn" data-id="${esc(p.pack_id)}" data-locked="${isLocked?1:0}">${isLocked?'解鎖':'鎖定'}</button>
          ${!isLocked ? `<button class="btn small danger" data-action="delete-pack-btn" data-id="${esc(p.pack_id)}">刪除</button>` : ''}
        ` : ''}
      </div>
    </div>

    <!-- Case templates -->
    <div class="section-space">
      <div data-s="s40eee6f">
        <h3 data-s="s5a9a6de">案件範本 (${caseTemplates.length}/20)</h3>
        ${!isPreset && !isLocked && manager() && caseTemplates.length < 20 ? `<button class="btn small" data-action="new-template-modal" data-pack="${esc(p.pack_id)}" data-type="case">+ 新增案件範本</button>` : ''}
      </div>
      <div data-s="s53ab7d6">
        ${caseTemplates.map(t=>`
          <div class="template-card" data-s="s9bd711d">
            <div data-s="s8129723">
              <strong>${esc(t.name)}</strong>
              ${!isPreset && !isLocked && manager() ? `
                <div data-s="s597636a">
                  <button class="btn text small" data-action="edit-template-modal" data-id="${esc(t.template_id)}" data-pack="${esc(p.pack_id)}" data-type="case">編輯</button>
                  <button class="btn text small danger" data-action="delete-template-btn" data-id="${esc(t.template_id)}" data-type="case">刪除</button>
                </div>
              ` : ''}
            </div>
            <div data-s="s60946a2"><span class="badge" data-s="se48b058">${esc(t.category_name||"一般")}</span></div>
            <p data-s="s1a2e8fd">${esc(t.body)}</p>
          </div>
        `).join("")||'<p class="muted" data-s="s9e6595f">尚未建立案件範本</p>'}
      </div>
    </div>

    <!-- Note templates -->
    <div class="section-space" data-s="s9eb125f">
      <div data-s="s40eee6f">
        <h3 data-s="s5a9a6de">記事範本 (${noteTemplates.length}/20)</h3>
        ${!isPreset && !isLocked && manager() && noteTemplates.length < 20 ? `<button class="btn small" data-action="new-template-modal" data-pack="${esc(p.pack_id)}" data-type="note">+ 新增記事範本</button>` : ''}
      </div>
      <div data-s="s53ab7d6">
        ${noteTemplates.map(t=>`
          <div class="template-card" data-s="s9bd711d">
            <div data-s="s8129723">
              <strong>${esc(t.name)}</strong>
              ${!isPreset && !isLocked && manager() ? `
                <div data-s="s597636a">
                  <button class="btn text small" data-action="edit-template-modal" data-id="${esc(t.template_id)}" data-pack="${esc(p.pack_id)}" data-type="note">編輯</button>
                  <button class="btn text small danger" data-action="delete-template-btn" data-id="${esc(t.template_id)}" data-type="note">刪除</button>
                </div>
              ` : ''}
            </div>
            <div data-s="s60946a2"><span class="badge" data-s="se48b058">${esc(t.category_name||"一般")}</span></div>
            <p data-s="s1a2e8fd">${esc(t.body)}</p>
          </div>
        `).join("")||'<p class="muted" data-s="s9e6595f">尚未建立記事範本</p>'}
      </div>
    </div>
  </div>`;
}

// 權限規格第 9 節：尚無平台管理員時，本機入口只顯示「建立第一位平台管理員」。
function firstAdminPage(result){
  if(result)return heading("首次設定完成","請把下方一次性連結交給本人設定密碼（30 分鐘內有效）。設定後即可登入；此頁不會再出現。","")+`<section class="panel panel-body">
    <label class="field">在這台電腦設定<input readonly value="${esc(result.local_url)}"></label>
    ${result.url?`<label class="field section-space">從對外網址設定<input readonly value="${esc(result.url)}"></label>`:'<p class="subtitle">尚未設定 ADMIN_PUBLIC_HOST；只能在這台電腦開啟連結。</p>'}
    <p class="subtitle">連結只會在這裡顯示一次，不會寫入任何檔案或寄出 Email。</p></section>`;
  return heading("建立第一位平台管理員","系統還沒有平台管理員。建立後，本人以一次性連結設定密碼並登入。","")+`<section class="panel panel-body"><form id="first-admin-form" class="management-form">
    <div class="form-grid">${field("Email","email","",'type="email" required maxlength="254" autocomplete="off"')}${field("顯示名稱（選填）","display_name","",'maxlength="80"')}</div>
    <p class="subtitle">平台管理員負責建立組織、管理員帳號與 LINE OA 連線；對客戶的營運內容只能閱讀。</p>
    <p class="notice error" id="first-admin-error" role="alert" hidden></p>
    <div class="form-actions"><button class="btn primary" type="submit">建立並產生設定連結</button></div></form></section>`;
}
document.addEventListener("submit",async event=>{
  const form=event.target;if(form.id!=="first-admin-form")return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');submit.disabled=true;
  try{
    const result=await api('/api/setup/first-admin',Object.fromEntries(new FormData(form)));
    $("page").innerHTML=firstAdminPage(result);
  }catch(error){$("first-admin-error").textContent=error.message;$("first-admin-error").hidden=false;submit.disabled=false;}
});

function render(){
  if(state.session?.needs_setup){$("crumb").textContent="首次設定";document.title="首次設定 · LINE 自動化";$("page").innerHTML=firstAdminPage();return;}
  if(!lineDataReady()&&!["organizations","channels","oa-list"].includes(state.view))state.view=superAdmin()?"organizations":"channels";
  if(superAdmin()&&!["organizations","channels"].includes(state.view))state.view="organizations";
  if(!titles[state.view])state.view="overview";
  $("crumb").textContent=titles[state.view]||"工作空間";document.title=(titles[state.view]||"工作台")+" · LINE 自動化";
  document.querySelectorAll("nav [data-view]").forEach(el=>{const current=el.dataset.view===state.view;el.classList.toggle("active",current);if(current)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  applyNavRail();
  const pages={
    overview,
    "oa-list": oaListPage,
    chat:()=>chatPage(),
    reports:reportsPage,
    send:sendPage,
    cases:casesPage,
    templates:()=>templatesAndCategoriesPage(),
    contacts:()=>contactsPage(false),
    subscriptions:()=>contactsPage(true),
    history:historyPage,
    schedule:schedulePage,
    personnel:personnelPage,
    "org-settings":orgSettingsPage,
    channels:channelsPage,
    organizations:organizationsPage
  };
  const pageFn = pages[state.view] || overview;
  $("page").innerHTML=pageFn();
  hydratePreviews();
}

function oaListPage(){
  const channelsList = lineUI.channels || state.channels || [];
  const q = (state.oaSearch || "").toLowerCase().trim();
  const filtered = channelsList.filter(c => !q || c.name.toLowerCase().includes(q) || (orgName(c.org_id)||"").toLowerCase().includes(q) || (c.basic_id||"").toLowerCase().includes(q));
  const currentId = lineUI.channel;

  return heading("LINE OA 一覽", "查看並快速進入您獲授權存取的 LINE 官方帳號", `<div class="mg-tools" data-s="s1da9fac"><input type="search" id="oa-list-search" value="${esc(state.oaSearch||"")}" placeholder="搜尋 OA 名稱或組織…" data-s="s3d82166"></div>`)+`
  <div class="dashboard-grid" data-s="s3f2d80e">
    <div data-s="s4ac80f0">
      ${filtered.map(c => `
        <div class="oa-card panel" style="display:flex;flex-direction:column;justify-content:space-between;padding:20px;border-radius:18px;background:var(--card-bg,#fff);border:1px solid ${c.channel_id===currentId?'#00B900':'var(--line,#e2e8f0)'};box-shadow:0 2px 10px rgba(0,0,0,0.03);position:relative;">
          ${c.channel_id===currentId ? '<span class="badge good" data-s="sbfc9d19">目前使用中</span>' : ''}
          <div>
            <div data-s="sa5dc62c">
              <div class="avatar" data-s="s035b760">${esc(c.name.slice(0,1))}</div>
              <div>
                <strong data-s="s8304de5">${esc(c.name)}</strong>
                <small data-s="sa639cb1">${esc(c.basic_id || c.bot_user_id || "")} · ${esc(orgName(c.org_id))}</small>
              </div>
            </div>
            <div data-s="s9f30d58">
              <div><small data-s="s5cad321">有效好友</small><strong data-s="sba62946">${state.contacts.filter(r=>r.channel_id===c.channel_id&&r.active).length || '—'}</strong></div>
              <div><small data-s="s5cad321">未讀訊息</small><strong data-s="sba62946">${state.chatNotes.get(c.channel_id)?.length || 0}</strong></div>
              <div><small data-s="s5cad321">進行中案件</small><strong data-s="sba62946">${state.cases.filter(cs=>cs.channel_id===c.channel_id&&cs.status!=='closed').length || 0}</strong></div>
            </div>
          </div>
          <div>
            <button class="btn ${c.channel_id===currentId?'dark':'primary'}" data-s="s2976360" data-action="switch-oa-direct" data-channel="${esc(c.channel_id)}" data-org="${esc(c.org_id)}">${c.channel_id===currentId?'進入工作總覽':'切換至此 OA'}</button>
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
  
  return heading("人員與權限", `管理「${esc(org.name)}」的操作與協作人員，指定可用 LINE OA。`, button("新增人員","new-personnel","primary"))+`
  <div class="management">
    <div class="mg-summary">
      <div class="mg-stat"><strong>${members.filter(m=>m.active).length}</strong><span>位後台人員</span></div>
      <div class="mg-stat"><strong>${members.filter(m=>m.active&&m.role==='operator').length}</strong><span>位操作人員</span></div>
      <div class="mg-stat"><strong>${members.filter(m=>m.active&&m.role==='collaborator').length}</strong><span>位協作人員</span></div>
    </div>
    <section class="mg-card">
      <div class="mg-head">
        <div><h2>組織人員清單</h2><p>管理員可存取本組織所有 OA；操作人員與協作人員可依指派勾選可用 OA。</p></div>
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
              ${m.role !== 'platform_admin' ? button("編輯與 OA 授權", "edit-personnel", "small", `data-id="${key}"`) : ""}
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
          <div class="activity-row" data-s="sc907557">
            <div data-s="sda5a491">
              <strong>${esc(e.detail || e.action)}</strong>
              <small class="muted">${when(e.created_at)}</small>
            </div>
            <small data-s="sbcc8653">${esc(e.actor)} · ${esc(e.action)}</small>
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
    <label class="check-label" data-s="s15b9169">
      <input type="checkbox" name="channel_ids" value="${esc(c.channel_id)}" ${existingChannelIds.includes(c.channel_id) ? "checked" : ""}>
      <span><strong>${esc(c.name)}</strong> <small data-s="sbcc8653">${esc(c.basic_id||"")}</small></span>
    </label>
  `).join("") || '<p class="muted">此組織尚未連結任何 LINE OA。</p>';
  
  modal(id ? "編輯組織人員" : "新增組織人員", `<form id="personnel-form" data-id="${esc(id||"")}">
    <input type="hidden" name="org_id" value="${esc(org.org_id)}">
    <div class="form-grid">
      ${field("登入 Email", "email", m?.email || "", `type="email" required ${id ? "readonly" : ""} placeholder="user@example.com"`)}
      ${field("顯示名稱", "display_name", u?.display_name || "", 'maxlength="80" placeholder="方便同事識別的姓名"')}
      ${selectField("人員角色", "role", [["operator", "操作人員（可讀取並回覆對話、發送訊息、管理案件與記事）"], ["collaborator", "協作人員（可讀取對話、管理記事與案件，不可傳送訊息）"]], m?.role || "operator")}
      ${field("部門／分組（選填）", "department", m?.department || "", 'maxlength="80" placeholder="例如：客服組、維修部"')}
      <div class="full">
        <label class="field">
          <span>可使用的 LINE OA</span>
          <div class="permission-choices" data-s="s3f0710d">
            ${oaCheckboxes}
          </div>
          <small class="muted">勾選該人員可操作的 LINE OA。未勾選的 OA 該人員登入後無法檢視或操作。</small>
        </label>
      </div>
      <div class="full">
        <label class="check-label" data-s="se3f6104">
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
  
  modal("我的帳號", `<div data-s="s16b1638">
    <div data-s="sbcad3e4">
      <div class="avatar" data-s="s6341041">${esc((user.display_name||email).slice(0,1).toUpperCase())}</div>
      <div>
        <h3 data-s="sb5b046a">${esc(user.display_name || email)}</h3>
        <p data-s="sc14eaad">${esc(email)} · ${badge(roleName(role))}</p>
      </div>
    </div>
    <div data-s="sfe3fb0d">
      <div data-s="s8761676">
        <div>
          <strong data-s="s29fe999">登入密碼</strong>
          <small data-s="sa639cb1">定期更新密碼以維護帳號安全</small>
        </div>
        <button type="button" class="btn small" data-security="password">修改密碼</button>
      </div>
      <div data-s="s8761676">
        <div>
          <strong data-s="s29fe999">登入裝置與階段</strong>
          <small data-s="sa639cb1">查看目前已登入的瀏覽器與裝置</small>
        </div>
        <button type="button" class="btn small" data-security="devices">裝置清單</button>
      </div>
    </div>
    <div class="form-actions" data-s="s56ea235">
      <button type="button" class="btn text" onclick="$('modal').close()">關閉</button>
      <button type="button" class="btn danger small" data-action="confirm-logout">登出帳號</button>
    </div>
  </div>`);
}

function openOaSwitcherModal(){
  const allOas = lineUI.channels || state.channels || [];
  const currentId = lineUI.channel;
  modal("切換 LINE OA", `<div class="oa-switcher-modal">
    <div data-s="s7142fa2">
      <input type="search" id="oa-switcher-filter" placeholder="搜尋 LINE OA 名稱或組織…" data-s="sb48bce0">
      <button type="button" class="btn" data-action="go-oa-list-from-switcher">OA 一覽</button>
    </div>
    <div id="oa-switcher-items" data-s="s1666731">
      ${allOas.map(c => `
        <button type="button" class="oa-switcher-item" data-action="switch-oa-direct" data-channel="${esc(c.channel_id)}" data-org="${esc(c.org_id)}" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:10px;border:1px solid ${c.channel_id===currentId?'#00B900':'var(--line,#e2e8f0)'};background:${c.channel_id===currentId?'#f0fdf4':'var(--card-bg,#fff)'};cursor:pointer;text-align:left;width:100%;">
          <div data-s="s7e30d28">
            <div class="avatar" data-s="sf02b47b">${esc(c.name.slice(0,1))}</div>
            <div>
              <strong data-s="s29fe999">${esc(c.name)} ${c.channel_id===currentId?'(目前)':''}</strong>
              <small data-s="sd6859f9">${esc(orgName(c.org_id))}</small>
            </div>
          </div>
          ${c.channel_id===currentId ? `<span class="oa-checked-badge" data-s="se6630c1">${icon("check")}</span>` : ''}
        </button>
      `).join("") || '<p class="muted">尚無可切換的 LINE OA。</p>'}
    </div>
  </div>`);
}
function navigate(view){if(state.busy)return;notice("");state.view=view;state.search="";state.kind="all";state.organization_id="";state.department="";state.tagFilter="";state.page=1;setSidebarOpen(false);history.replaceState(null,"","/?view="+encodeURIComponent(view));render();window.scrollTo({top:0});}
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
        ${field("備註名稱（自訂名稱）","custom_name",r.custom_name||"",'maxlength="80" placeholder="團隊內部備註名稱，不會寫回 LINE"')}
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
        ${(superAdmin()?selectField("系統組織","organization_id",oaOrganizationOptions(),r.organization_id):field("系統組織","organization_label",orgName(r.organization_id),'readonly')+`<input type="hidden" name="organization_id" value="${esc(r.organization_id)}">`)}
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
    return `<div class="tag-row"><div class="tag-row-info">${tagBadge(t)}<span class="muted" data-s="se71ae94">${count} 個聯絡對象</span></div><div class="draft-actions">${button("編輯","edit-tag-modal","small",`data-id="${esc(t.id)}"`)}${button("刪除","delete-tag-btn","text small danger",`data-id="${esc(t.id)}"`)}</div></div>`;
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
function reportForm(reportId){const source=(state.settings.report_sources||[]).find(r=>r.report_id===reportId);modal(source?"編輯報告來源":"新增報告來源",`<form id="report-form"><div class="form-grid">${field("報告名稱","title","",'required maxlength="80" placeholder="例如：每日業績報表"')}${selectField("報告類型","category",[["company","組織報表"],["other","其他報告"]],"company")}${selectField("工作區","organization_id",oaOrganizationOptions(),selectedWorkspace()?.org_id||"")}${selectField("可見範圍","scope",[["company","全組織"],["department","指定部門"],["personal","指定個人"]],"company")}${field("部門（部門報告必填）","department","",'maxlength="60"')}${selectField("LINE 個人聯絡對象（個人報告必填）","owner_recipient_id",[["","選擇聯絡對象"],...state.contacts.filter(r=>r.kind==="user"&&r.active).map(r=>[r.recipient_id,label(r)+" · "+orgName(r.organization_id)])],"")}<div class="full"><input name="asset_id" type="hidden"><label class="upload-picker">${icon("image")}<strong>從裝置選擇報告圖片</strong><span>JPG／PNG，每張最多 8 MB</span><input id="report-file" type="file" accept="image/png,image/jpeg,.jpg,.jpeg,.png"></label><div id="report-upload-preview" role="status"></div><p class="subtitle">先選組織再上傳；保存本次檔案的副本。每日自動更新的報告可使用下方進階設定。</p><details><summary>進階設定：自動化報告來源</summary><label class="field section-space">伺服器 PNG 路徑<input name="source_path" placeholder="D:\\Reports\\daily.png"><small>外部程式更新此檔案後，報告中心會讀取最新版。目前支援 1 MB 以內 PNG。</small></label></details></div></div><div class="form-actions"><button class="btn primary" type="submit">儲存報告來源</button></div></form>`);if(source){const form=$("report-form");form.dataset.id=source.report_id;for(const key of ["title","category","organization_id","scope","department","owner_recipient_id","source_path"])form.elements[key].value=source[key]||"";}}
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
  modal("切換檢視視角",`<p class="subtitle">目前登入：${esc(principalSession.identity)}。預覽會套用該帳號的角色、公司、部門與個人資料權限，並禁止寫入操作。</p><div class="view-options">${button("返回原帳號視角","apply-view","",'data-id=""')}${viewOptions.map(user=>button(`<strong>${esc(user.display_name||user.email)}</strong><small>${esc(user.email)} · ${esc(roleName(user.role))} · ${esc(user.organization_name||orgName(user.organization_id))} / ${esc(user.department||"未分部門")}</small>`,"apply-view",user.email===viewAs&&user.organization_id===previewOrganization?"active":"",`data-id="${esc(user.email+"|"+user.organization_id)}"`)).join("")}</div>${!viewOptions.length?'<p class="callout">目前沒有可預覽的帳號；平台管理員可在「帳號與設定」新增或調整角色。</p>':""}<p class="subtitle">本瀏覽器會記住選擇；預覽不會變更真正的登入帳號。Cloudflare 登入到期後仍需驗證。</p>`);
}
function switchView(email){
  if(email&&!viewOptions.some(user=>user.email+"|"+user.organization_id===email))throw new Error("請重新整理可用帳號。");
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
      const targetChannel=(lineUI.channels||state.channels||[]).find(c=>c.channel_id===channelId);
      const targetWorkspace=targetChannel?.workspace_id||("o:"+(orgId||""));
      if($("modal").open)$("modal").close();
      if(channelId===lineUI.channel){
        navigate("overview");
      }else if(channelId){
        if(orgId&&organizationKey)try{localStorage.setItem(organizationKey,orgId);}catch(_){}
        changeLineContext(targetWorkspace, channelId);
      }
    }
    else if(action==="go-oa-list-from-switcher"){$("modal").close();navigate("oa-list");}
    else if(action==="dismiss-onboarding"){
      const orgId=state.session?.user?.organization_id||"";
      if(orgId)localStorage.setItem("lineOnboardingDismissed_"+orgId,"1");
      render();
    }
    else if(action==="new-personnel")personnelForm();
    else if(action==="edit-personnel")personnelForm(id);
    else if(action==="open-template-packs-mgr"){navigate("channels");$("modal").close();}
    else if(action==="confirm-logout"){
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
        priority: c.priority || "medium"
      });
    }
    else if(action==="open-template-picker")await templatePickerModal(target.dataset.subject||"","case");
    else if(action==="open-note-template-picker")await templatePickerModal(target.dataset.recipient||"","note");
    else if(action==="apply-case-template"){
      createCaseModal(target.dataset.subject||"", {
        title: target.dataset.title||"",
        description: target.dataset.desc||"",
        category: target.dataset.cat||"一般",
        priority: target.dataset.pri||"medium"
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
    else if(action==="new-org-admin")accountForm("",{role:"org_admin",organization_id:id||management.org});
    else if(action==="edit-account")accountForm(id);
    else if(action==="send-to-filtered"){
      state.selected = new Set(filteredContacts().filter(r=>r.active&&eligible(r)).map(r=>r.recipient_id));
      state.step = 1;
      state.report = null;
      state.audience = "selected";
      navigate("send");
    }
    else if(action==="send-to-selected"){
      state.step = 1;
      state.report = null;
      state.audience = "selected";
      navigate("send");
    }
    else if(action==="send-to-chat-filtered"){
      const chatRooms = (typeof chatUI !== "undefined" ? chatUI.rooms : []).filter(r => {
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
      state.selected = new Set(chatRooms.map(r=>r.recipient_id).filter(id => state.contacts.some(c=>c.recipient_id===id&&c.active)));
      state.step = 1;
      state.report = null;
      state.audience = "selected";
      navigate("send");
    }
    else if(action==="tag-audience-mode"){
      state.tagAudienceMode = id;
      const matched = contactsMatchingTags(Array.from(state.selectedAudienceTags), state.tagAudienceMode);
      state.selected = new Set(matched.map(r=>r.recipient_id));
      render();
    }
    else if(action==="audience"){
      state.audience=id;
      if(id==="by-tags"){
        const matched = contactsMatchingTags(Array.from(state.selectedAudienceTags), state.tagAudienceMode);
        state.selected = new Set(matched.map(r=>r.recipient_id));
      } else if(id==="by-filter"){
        const chosen = (state.savedFilters||[]).find(f=>f.filter_id===state.selectedFilterId);
        const matched = chosen ? contactsMatchingFilter(chosen.criteria) : [];
        state.selected = new Set(matched.map(r=>r.recipient_id));
      }
      render();
    }
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
    else if(action==="open-case-notify-modal")caseNotifyModal(id);
    else if(action==="save-case-as-template")saveAsTemplateModal('case', id);
    else if(action==="save-note-as-template")saveAsTemplateModal('note', id);
    else if(action==="toggle-chat-note-completed"){
      const rec = target.dataset.recipient;
      await api('/api/chat-notes/complete', {note_id: id});
      if(rec) await loadChatNotes(rec);
      await load();
      render();
      notice("已更新完成狀態。");
    }
    else if(action==="templates-tab"){templatesTab=id;loadTemplatesTabContent();document.querySelectorAll('[data-action="templates-tab"]').forEach(b=>b.classList.toggle('active',b.dataset.id===id));}
    else if(action==="select-template-pack"){selectedPackKey=id;loadTemplatesTabContent();}
    else if(action==="toggle-pack-enable"){
      const checked = target.checked;
      await api('/api/template-packs/toggle', {pack_key: id, enabled: checked});
      notice(checked ? "已啟用範本包。" : "已停用範本包。");
    }
    else if(action==="new-custom-pack"){
      modal("新增自訂範本包", `<form id="custom-pack-form">
        <div class="form-grid">
          <div class="full">${field("範本包名稱", "name", "", 'required maxlength="30" placeholder="例如：專案諮詢流程、展場接待"')}</div>
          <div class="full">${field("範本包說明（選填）", "description", "", 'maxlength="100" placeholder="簡述適用場景與對象"')}</div>
          <div class="full">${field(`記事類型（逗號分隔，最多 ${cap("CATEGORIES_PER_OA")} 項，預設含一般）`, "note_types", "一般, 待辦, 重要事項", 'maxlength="300"')}</div>
          <div class="full">${field(`案件類別（逗號分隔，最多 ${cap("CATEGORIES_PER_OA")} 項，預設含一般）`, "case_categories", "一般, 詢問, 報修", 'maxlength="300"')}</div>
        </div>
        <div class="form-actions"><button class="btn primary" type="submit">建立範本包</button></div>
      </form>`);
    }
    else if(action==="copy-pack-modal"){
      modal("複製為自訂範本包", `<form id="copy-pack-form" data-source="${esc(id)}">
        <div class="form-grid">
          <div class="full">${field("新範本包名稱", "name", "", 'required maxlength="30" placeholder="例如：自訂通用範本包"')}</div>
        </div>
        <p class="callout">將複製該範本包的分類組合及所有案件/記事範本為全新的自訂範本包。</p>
        <div class="form-actions"><button class="btn primary" type="submit">確認複製</button></div>
      </form>`);
    }
    else if(action==="toggle-pack-lock-btn"){
      const isLocked = Number(target.dataset.locked) === 1;
      await api('/api/template-packs/lock', {pack_id: id, is_locked: !isLocked});
      notice(!isLocked ? "範本包已鎖定。" : "範本包已解鎖。");
      await loadTemplatesTabContent();
    }
    else if(action==="delete-pack-btn"){
      modal("刪除自訂範本包？", `<p>確定要刪除此自訂範本包嗎？包內所有自訂範本將一併刪除（已建立的案件與記事不受影響）。</p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-pack", "danger", `data-id="${esc(id)}"`)}</div>`);
    }
    else if(action==="confirm-delete-pack"){
      await api('/api/template-packs/delete', {pack_id: id});
      $("modal").close();
      selectedPackKey = "universal";
      await loadTemplatesTabContent();
      notice("範本包已刪除。");
    }
    else if(action==="new-template-modal"){
      const packId = target.dataset.pack;
      const tmplType = target.dataset.type;
      modal(`新增${tmplType==="case"?"案件":"記事"}範本`, `<form id="template-form" data-pack="${esc(packId)}" data-type="${esc(tmplType)}">
        <div class="form-grid">
          <div class="full">${field("範本名稱", "name", "", 'required maxlength="30" placeholder="例如：一般詢問處理"')}</div>
          ${field("預設分類名稱", "category_name", "一般", 'maxlength="30"')}
          ${field("預設標題（支援 {聯絡對象}、{今天}、{OA}）", "title", "{聯絡對象} - ", 'maxlength="100"')}
          <div class="full"><label class="field">內容骨架（1 至 1,000 字）<textarea name="body" rows="4" maxlength="1000" placeholder="設定表單預設帶入的填寫欄位骨架..."></textarea></label></div>
        </div>
        <div class="form-actions"><button class="btn primary" type="submit">儲存範本</button></div>
      </form>`);
    }
    else if(action==="delete-template-btn"){
      const tmplType = target.dataset.type;
      modal("刪除範本？", `<p>確定要刪除此範本嗎？</p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-template", "danger", `data-id="${esc(id)}" data-type="${esc(tmplType)}"`)}</div>`);
    }
    else if(action==="confirm-delete-template"){
      const tmplType = target.dataset.type;
      await api('/api/templates/delete', {template_id: id, template_type: tmplType});
      $("modal").close();
      await loadTemplatesTabContent();
      notice("範本已刪除。");
    }
    else if(action==="preview-apply-categories"){
      modal("套用分類組合", '<div class="loading-panel"><span class="spinner"></span><p>計算分類差異…</p></div>');
      const prev = await api('/api/categories/preview', {pack_key: id, mode: "replace"});
      modal(`套用「${esc(prev.pack_name)}」分類組合至 OA`, `<div class="categories-preview-dialog">
        <div data-s="s3ef1fa1">
          <label data-s="s3066f84">套用方式：</label>
          <label data-s="s84eff7f"><input type="radio" name="apply_mode" value="replace" checked> 取代（未使用的舊項目移除）</label>
          <label><input type="radio" name="apply_mode" value="merge"> 合併（保留所有既有項目）</label>
        </div>
        <div data-s="s41de6d2">
          <div>
            <h4>記事類型 (${prev.note_types.length} 項)</h4>
            <ul data-s="sa8b3c59">
              ${prev.note_types.map(it=>`<li style="color:${it.action==='remove'?'#ef4444':it.action==='add'?'#10b981':'inherit'}">${esc(it.name)} (${it.action==='keep'?'保留':it.action==='add'?'新增':'移除'})</li>`).join("")}
            </ul>
          </div>
          <div>
            <h4>案件類別 (${prev.case_categories.length} 項)</h4>
            <ul data-s="sa8b3c59">
              ${prev.case_categories.map(it=>`<li style="color:${it.action==='remove'?'#ef4444':it.action==='add'?'#10b981':'inherit'}">${esc(it.name)} (${it.action==='keep'?'保留':it.action==='add'?'新增':'移除'})</li>`).join("")}
            </ul>
          </div>
        </div>
        <div class="callout" data-s="s9374e84">套用後若超過 ${cap("CATEGORIES_PER_OA")} 項上限，超出的項目將不予加入。被移除的項目中已有的案件/記事將自動轉為「一般」。</div>
        <div class="form-actions"><button class="btn primary" data-action="confirm-apply-categories" data-id="${esc(id)}">確認套用分類組合</button></div>
      </div>`);
    }
    else if(action==="confirm-apply-categories"){
      const mode = document.querySelector('input[name="apply_mode"]:checked')?.value || "replace";
      await api('/api/categories/apply', {pack_key: id, mode});
      $("modal").close();
      await loadTemplatesTabContent();
      notice("分類組合已套用至本 OA。");
    }
    else if(action==="new-single-category"){
      const catType = target.dataset.type;
      modal(`新增${catType==="case"?"案件類別":"記事類型"}`, `<form id="single-category-form" data-type="${esc(catType)}">
        <div class="form-grid">
          <div class="full">${field("分類名稱", "name", "", 'required maxlength="20" placeholder="例如：商品諮詢、退換貨"')}</div>
        </div>
        <div class="form-actions"><button class="btn primary" type="submit">新增分類</button></div>
      </form>`);
    }
    else if(action==="edit-single-category"){
      const catType = target.dataset.type;
      const oldName = target.dataset.name;
      modal(`修改${catType==="case"?"案件類別":"記事類型"}名稱`, `<form id="single-category-form" data-type="${esc(catType)}" data-old="${esc(oldName)}">
        <div class="form-grid">
          <div class="full">${field("分類名稱", "name", oldName, 'required maxlength="20"')}</div>
        </div>
        <p class="callout">修改後，目前所有使用「${esc(oldName)}」的案件或記事將自動更新為新名稱。</p>
        <div class="form-actions"><button class="btn primary" type="submit">儲存變更</button></div>
      </form>`);
    }
    else if(action==="delete-single-category"){
      const catType = target.dataset.type;
      const name = target.dataset.name;
      modal(`刪除${catType==="case"?"案件類別":"記事類型"}「${esc(name)}」？`, `<p>確定要刪除此分類嗎？刪除後，所有屬於此分類的既有案件或記事將自動改為「一般」。</p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-single-category", "danger", `data-type="${esc(catType)}" data-name="${esc(name)}"`)}</div>`);
    }
    else if(action==="confirm-delete-single-category"){
      const catType = target.dataset.type;
      const name = target.dataset.name;
      await api('/api/categories/delete', {category_type: catType, name});
      $("modal").close();
      await loadTemplatesTabContent();
      notice("分類已刪除，既有項目已轉為一般。");
    }
    else if(action==="profiles"){target.disabled=true;const result=await api('/api/profiles',{});await load();render();notice(`已更新 ${result.updated} 個 LINE 名稱，${result.failed} 個未完成。`);}
  }catch(error){if($("modal").open){$("modal-error").textContent=error.message;$("modal-error").hidden=false;}else notice(error.message,true);target.disabled=false;}
});
function updateSelection(){if($("contact-list"))$("contact-list").innerHTML=contactList();if($("selection-summary"))$("selection-summary").innerHTML=selectionSummary();if($("review-button"))$("review-button").disabled=!selectedRows().length;}
document.addEventListener("input",event=>{
  if(event.target.id==="contact-search"){state.search=event.target.value;state.page=1;if($("contact-list"))$("contact-list").innerHTML=contactList();}
  if(event.target.id==="case-search"){state.caseQuery=event.target.value;if(state.view==="cases")render();}
  if(event.target.id==="chat-list-search"){if(typeof chatUI!=="undefined"){chatUI.query=event.target.value;if($("chat-room-list"))$("chat-room-list").innerHTML=renderChatRoomItems();}}
  if(event.target.id==="chat-inner-search-input"){if(typeof chatUI!=="undefined"){chatUI.searchQuery=event.target.value;const stream=$("chat-messages-stream");if(stream)stream.innerHTML=renderMessageBubbles();}}
  if(event.target.id==="oa-list-search"){state.oaSearch=event.target.value;if(state.view==="oa-list")render();}
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
      state.organization_id=c.organization_id||"";
      state.department=c.department||"";
      state.tagFilter=c.tag||"";
      state.search=c.search||"";
      state.page=1;
      render();
      notice(`已套用自訂篩選：「${sf.name}」`);
    }
    return;
  }
  if(el.name==="audience-tag"){
    if(el.checked) state.selectedAudienceTags.add(el.value);
    else state.selectedAudienceTags.delete(el.value);
    const matched = contactsMatchingTags(Array.from(state.selectedAudienceTags), state.tagAudienceMode);
    state.selected = new Set(matched.map(r=>r.recipient_id));
    render();
    return;
  }
  if(el.name==="audience-saved-filter"){
    state.selectedFilterId = el.value;
    const chosen = (state.savedFilters||[]).find(f=>f.filter_id===el.value);
    const matched = chosen ? contactsMatchingFilter(chosen.criteria) : [];
    state.selected = new Set(matched.map(r=>r.recipient_id));
    render();
    return;
  }
  if(el.id==="contact-tag-filter"){state.tagFilter=el.value;state.page=1;if($("contact-list"))$("contact-list").innerHTML=contactList();return;}
  if(el.id==="send-timing"){$("scheduled-time").hidden=el.value!=="scheduled";const wrap=$("scheduled-time-wrapper");if(wrap)wrap.hidden=el.value!=="scheduled";$("submit-send").textContent=el.value==="scheduled"?"確認預約":"確認立即發送";return;}
  if(el.dataset.select){el.checked?state.selected.add(el.dataset.select):state.selected.delete(el.dataset.select);updateSelection();}
  else if(["contact-kind","contact-company","contact-department"].includes(el.id)){state[{"contact-kind":"kind","contact-company":"organization_id","contact-department":"department"}[el.id]]=el.value;state.page=1;if(el.id==="contact-company"){state.department="";render();}else $("contact-list").innerHTML=contactList();}
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
    }else if(form.id==="case-notify-form"){
      await api(`/api/cases/${form.dataset.id}/notify`, {message_text: values.message_text});
      $("modal").close();
      await caseDetailModal(form.dataset.id);
      notice("進度通知訊息已發送給對象並記錄於案件中。");
      return;
    }else if(form.id==="save-as-template-form"){
      await api('/api/templates/create-from-source', {
        source_type: form.dataset.type,
        source_id: form.dataset.id,
        target_pack_id: values.target_pack_id,
        name: values.name
      });
      $("modal").close();
      notice("已成功存為自訂範本。");
      return;
    }else if(form.id==="custom-pack-form"){
      const note_types = values.note_types ? values.note_types.split(/[,，]/).map(s=>s.trim()).filter(Boolean) : ["一般"];
      const case_categories = values.case_categories ? values.case_categories.split(/[,，]/).map(s=>s.trim()).filter(Boolean) : ["一般"];
      await api('/api/template-packs/save', {
        name: values.name,
        description: values.description,
        note_types,
        case_categories
      });
      $("modal").close();
      await loadTemplatesTabContent();
      notice("自訂範本包已建立。");
      return;
    }else if(form.id==="copy-pack-form"){
      await api('/api/template-packs/copy', {
        source_pack_key: form.dataset.source,
        name: values.name
      });
      $("modal").close();
      await loadTemplatesTabContent();
      notice("範本包已成功複製。");
      return;
    }else if(form.id==="template-form"){
      await api('/api/templates/save', {
        pack_id: form.dataset.pack,
        template_type: form.dataset.type,
        name: values.name,
        category_name: values.category_name || "一般",
        title: values.title || "",
        body: values.body || ""
      });
      $("modal").close();
      await loadTemplatesTabContent();
      notice("範本已建立。");
      return;
    }else if(form.id==="single-category-form"){
      await api('/api/categories/save', {
        category_type: form.dataset.type,
        name: values.name,
        old_name: form.dataset.old || ""
      });
      $("modal").close();
      await loadTemplatesTabContent();
      notice("分類已儲存。");
      return;
    }else if(form.id==="save-filter-form"){
      const criteria = {
        kind: state.kind !== "all" ? state.kind : undefined,
        organization_id: state.organization_id || undefined,
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
        custom_name:values.custom_name,
        custom_name:values.custom_name,
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
    }else if(form.id==="chat-response-hours-form"){
      const hours={
        enabled: Boolean(form.elements.enabled?.checked),
        timezone: values.timezone || "Asia/Taipei",
        ...readResponseHoursForm(form)
      };
      await api('/api/chat/response-hours/save', hours);
      chatNotify.responseHours=hours;
      $("modal").close();
      notice("回應時間設定已儲存。");
      return;
    }else if(form.id==="org-settings-form")await api('/api/org-settings/save',{name:values.name,kind:values.kind});
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
$("logout").addEventListener("click",async()=>{try{await api('/api/auth/logout',{},true,true);sessionStorage.removeItem('lineAdminToken');location.replace('/login');}catch(error){notice(error.message,true);}});
$("refresh").addEventListener("click",async()=>{if(state.busy)return;$("refresh").disabled=true;try{await load();render();notice("資料已更新。");await recoverSubmission();}catch(error){notice(error.message,true);}finally{$("refresh").disabled=false;}});
async function boot(){try{await load();render();await recoverSubmission();}catch(error){$("page").innerHTML=empty("暫時無法開啟工作台",remote?"請重新整理登入，或聯絡管理員確認帳號已啟用。":"請確認 LINE 服務已更新並啟動，再從控制台重新開啟管理頁。");notice(error.message,true);$("connection").textContent="連線未完成";}}
boot();
let polling=false;
setInterval(async()=>{if(!state.loaded||!lineUI.ready||!lineDataReady()||!admin()||state.busy||state.authLost||document.hidden||polling||$("modal").open)return;polling=true;const requestedOA=lineUI.channel;try{const result=await api('/api/jobs');if(requestedOA!==lineUI.channel)return;if(JSON.stringify(result.jobs)!==JSON.stringify(state.jobs)){state.jobs=result.jobs;if(['overview','history','schedule'].includes(state.view)){const opened=[...document.querySelectorAll('[data-job][open]')].map(el=>el.dataset.job);render();document.querySelectorAll('[data-job]').forEach(el=>{el.open=opened.includes(el.dataset.job);});}}}catch(error){notice(error.message,true);}finally{polling=false;}},6000);

// Handle unreadable image content without leaving a broken thumbnail.
document.addEventListener("error",event=>{if(event.target instanceof HTMLImageElement && !event.target.closest('.chat-media-image') && !event.target.classList.contains('chat-img-thumb')){const replacement=document.createElement("p");replacement.className="callout warn";replacement.textContent="圖片無法顯示，請確認來源檔案格式並重新產生報告。";event.target.replaceWith(replacement);}},true);

function scheduleLabel(value){return new Date(value).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false});}
function scheduleFields(){return `<div class="schedule-fields"><label class="field">傳送時間<select id="send-timing"><option value="now">立即傳送</option><option value="scheduled">指定日期與時間</option></select></label><div id="scheduled-time-wrapper" hidden><label class="field">台北時間 UTC+08:00<input type="datetime-local" id="scheduled-time" hidden></label><div class="schedule-presets section-space"><span class="muted" data-s="sbb2c29b">快速預約：</span><button type="button" class="btn small" data-action="schedule-preset" data-id="15m">+15 分鐘</button><button type="button" class="btn small" data-action="schedule-preset" data-id="1h">+1 小時</button><button type="button" class="btn small" data-action="schedule-preset" data-id="tmr9">明天 09:00</button><button type="button" class="btn small" data-action="schedule-preset" data-id="tmr14">明天 14:00</button><button type="button" class="btn small" data-action="schedule-preset" data-id="nextmon">下週一 09:00</button></div></div><p class="subtitle">預約保存現在確認的文字或圖片與發送對象；到期再檢查帳號、收件範圍與訂閱。電腦與 LINE 服務需開啟，延遲超過 10 分鐘標記逾期，不補發。</p></div>`;}

function organizationOptions(){return [["","選擇組織"],...(state.organizations||[]).filter(o=>o.active).map(o=>[o.org_id,o.name])];}

// 聊天頁左側選單維持標準寬度（不自動收合為窄欄）
function applyNavRail(){
  const chat=state.view==="chat";
  document.body.classList.toggle("chat-view",chat);
  document.body.classList.remove("nav-rail");
}
$("nav-rail-toggle")?.remove();

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
function dispatchScopeForm(id){const s=(state.settings.dispatch_scopes||[]).find(s=>s.scope_id===id)||{organization_id:management.org||state.organizations[0]?.org_id||"",name:"",kind:"department",department:"",recipient_ids:[],active:1};modal(id?"編輯發送範圍":"新增發送範圍",`<form id="dispatch-scope-form" data-id="${esc(id||"")}"><div class="form-grid">${selectField("所屬組織","organization_id",oaOrganizationOptions(),selectedWorkspace()?.org_id||s.organization_id)}${field("範圍名稱","name",s.name,'required maxlength="80" placeholder="例如：北區業務、網站改版專案"')}${selectField("範圍類型","kind",[["department","部門"],["project","專案"],["group","LINE 群組"]],s.kind)}${field("部門名稱（部門範圍必填）","department",s.department,'maxlength="60"')}<label class="check-label full"><input name="active" type="checkbox" ${s.active?"checked":""}>啟用範圍</label></div><fieldset class="permission-fieldset"><legend>範圍內聯絡對象</legend><div id="scope-recipient-options"></div></fieldset><p class="callout">部門會包含同組織、同部門分類的聊天室。專案可選多個對象；LINE 群組只能選一個。停用範圍會影響尚未執行的預約。</p><div class="form-actions"><button class="btn primary" type="submit">儲存範圍</button></div></form>`);const form=$("dispatch-scope-form");form.classList.add("management-form");if(id){form.elements.organization_id.disabled=true;form.insertAdjacentHTML('beforeend',`<input type="hidden" name="organization_id" value="${esc(s.organization_id)}">`);}function choices(selected=[]){const organization_id=id?s.organization_id:form.elements.organization_id.value,kind=form.elements.kind.value;$("scope-recipient-options").innerHTML=kind==="department"?'<p class="muted">依上方部門名稱自動比對，不需逐筆選人。</p>':checkChoices('recipient_ids',state.contacts.filter(r=>r.organization_id===organization_id&&(kind!=="group"||r.kind!=="user")).map(r=>[r.recipient_id,label(r)+(r.active?"":"（已停用）")]),selected);}choices(s.recipient_ids);form.addEventListener('change',e=>{if(['organization_id','kind'].includes(e.target.name))choices();});}
function senderGrantForm(id){const m=state.memberships.find(m=>m.email+"|"+m.org_id===id);if(!m)return;const g=(state.settings.sender_grants||[]).find(g=>g.email===m.email&&g.organization_id===m.org_id)||{scope_ids:[],report_ids:[]};modal("設定發送授權",`<form id="sender-grant-form" class="management-form"><input type="hidden" name="email" value="${esc(m.email)}"><input type="hidden" name="organization_id" value="${esc(m.org_id)}"><p>${esc(m.email)} · ${esc(m.name)}</p><p class="mg-grant-summary" id="mg-grant-summary" role="status"></p><fieldset class="permission-fieldset"><legend>可用模組</legend>${[['messaging','訊息發送與預約'],['reports','報告中心'],['weather','個人天氣模組（組織也須啟用）']].map(([key,text])=>`<label class="check-label"><input type="checkbox" name="${key}" ${g[key]?"checked":""}>${text}</label>`).join('')}</fieldset><fieldset class="permission-fieldset"><legend>可發送對象範圍（可複選）</legend><p class="mg-help">先在組織的「發送範圍」建立部門、專案或群組，再回來勾選。</p>${checkChoices('scope_ids',(state.settings.dispatch_scopes||[]).filter(s=>s.organization_id===m.org_id).map(s=>[s.scope_id,s.name+(s.active?'':'（已停用）')]),g.scope_ids)}</fieldset><fieldset class="permission-fieldset"><legend>可查看與發送的報告（可複選）</legend>${checkChoices('report_ids',(state.settings.report_sources||[]).filter(r=>r.organization_id===m.org_id||r.report_id==='weather').map(r=>[r.report_id,r.title]),g.report_ids)}</fieldset><p class="callout">報告與收件範圍分別授權。勾選報告不會開放全部聯絡對象；同時仍須符合報告本身的部門／個人限制。只發文字或自訂圖片時，可不選報告。取消模組或範圍會在預約執行前重新檢查。</p><div class="form-actions"><button class="btn primary" type="submit">儲存授權</button></div></form>`);const form=$("sender-grant-form");const summarize=()=>{$("mg-grant-summary").textContent=`已選 ${form.querySelectorAll('[name="scope_ids"]:checked').length} 個範圍、${form.querySelectorAll('[name="report_ids"]:checked').length} 份報告。${form.elements.messaging.checked?"儲存後套用授權；組織也須開放模組。":"尚未勾選訊息發送，此人員不能發送。"}`;};form.addEventListener("change",summarize);summarize();}

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

"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const paths = {
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
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
  phone:'<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.7 2z"/>',
  mail:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 6 10 7L22 6"/>',
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
  info:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  zap:'<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  sparkles:'<path d="m12 3 1.912 4.923L19 9.835l-4.088 1.912L13 16.67l-1.912-4.923L7 9.835l4.088-1.912z"/>',
  wand:'<path d="m15 4 5 2-5 2-2 5-2-5-5-2 5-2 2-5zM9 15l2 1-2 1-1 2-1-2-2-1 2-1 1-2zM2 22l10-10"/>',
  bookmark:'<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
  undo:'<path d="M3 7v6h6M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
  filter:'<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  more:'<circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="12" r="1.5"/>',
  case_icon:'<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
  note_icon:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  check_circle:'<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
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
const state={session:null,view:new URLSearchParams(location.search).get("view")||"overview",contacts:[],tags:[],jobs:[],cases:[],caseFilter:"all",casePriority:"all",caseQuery:"",savedFilters:[],chatNotes:new Map(),noteCategories:[],noteTags:[],globalNotes:[],globalNotesStats:null,globalNotesCategories:[],globalNotesTags:[],noteHubQuery:"",noteHubCategory:"",noteHubTag:"",noteHubStatus:"all",noteHubChannel:"",noteHubViewMode:"grid",settings:{users:[]},events:[],selected:new Set(),tagAudienceMode:"any",selectedAudienceTags:new Set(),selectedFilterId:"",orgSettingsTab:"general",report:null,step:1,audience:"selected",search:"",kind:"all",organization_id:"",department:"",tagFilter:"",page:1,historyFilter:"all",busy:false,loaded:false,authLost:false};
let dutyContext=null;
let dutyTab=new URLSearchParams(location.search).get("tab")||"home";
const titles={forms:"表單",duty:"值日生","personal-settings":"個人化設定",overview:"工作總覽","oa-list":"OA 一覽",chat:"聊天對話","chat-notes":"對話記事本",send:"建立發送",cases:"案件管理",templates:"範本與分類管理",contacts:"聯絡對象",history:"發送紀錄",schedule:"排程管理",personnel:"人員與權限","org-settings":"組織設定",organizations:"組織管理",channels:"LINE OA 管理"};
const admin=()=>["platform_admin","org_admin","operator","collaborator"].includes(state.session?.role);
const manager=()=>["platform_admin","org_admin"].includes(state.session?.role);
// 數量上限只由後端 limits.py 定義，經 /api/session 取得
const cap=key=>state.session?.limits?.[key]??"—";
const canSend=()=>["org_admin","operator"].includes(state.session?.role)&&Boolean(state.session?.modules?.messaging);
const superAdmin=()=>state.session?.role==="platform_admin";
const roleName=role=>({platform_admin:"平台管理員",org_admin:"管理員",operator:"操作人員",collaborator:"協作人員"}[role]||role);
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
window.DEFAULT_TAG_COLORS = window.DEFAULT_TAG_COLORS || {
  "急件優先": "#FF3B30",
  "待確認": "#FFCC00",
  "待追蹤": "#30B0C7"
};
var DEFAULT_TAG_COLORS = window.DEFAULT_TAG_COLORS;
const contactTypeNames={organization:"組織／團體",person_business:"公務對象個人",person_private:"一般個人"};
const contactTypeBadge=type=>type?badge(contactTypeNames[type]||type,"good"):badge("未分類");
const tagBadge=tag=>{const c=tag.color||'#007AFF';return `<span class="tag-badge" data-color="${esc(c)}"><span class="tag-dot" data-color="${esc(c)}"></span>${esc(tag.name)}</span>`;};
const when=value=>value?new Date(value).toLocaleString("zh-TW",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}):"尚未產生";
const badge=(text,tone="")=>`<span class="badge ${tone}">${esc(text)}</span>`;
const button=(text,action,cls="",attrs="")=>`<button class="btn ${cls}" data-action="${action}" ${attrs}>${text}</button>`;

function formatAuditAction(action){
  const actionMap = {
    "org.notes_policy": "記事治理",
    "chat.status": "聊天狀態",
    "chat.send": "傳送訊息",
    "chat_note.save": "儲存記事",
    "chat_note.delete": "刪除記事",
    "chat_note.pin": "置頂記事",
    "chat_note.lock": "鎖定記事",
    "chat_notes.tax_category_merge": "合併分類",
    "chat_notes.tax_tag_merge": "合併標籤",
    "case.create": "建立案件",
    "case.update": "更新案件",
    "case.status": "案件狀態",
    "case.notify_subject": "進度通知",
    "case.add_note": "案件紀錄",
    "cases.update_prefix": "案件前綴",
    "template_pack.save": "自訂範本包",
    "template_pack.delete": "刪除範本包",
    "template_pack.copy": "複製範本包",
    "template_pack.lock": "範本包鎖定",
    "template_case.save": "案件範本",
    "template_note.save": "記事範本",
    "category_case.rename": "類別改名",
    "category_case.add": "新增類別",
    "category_case.delete": "刪除類別",
    "category_note.rename": "類型改名",
    "category_note.add": "新增類型",
    "category_note.delete": "刪除類型",
    "canned_reply.save": "預設訊息",
    "canned_reply.delete": "刪除預設訊息",
    "response_hours.save": "回應時間",
    "saved_filter.save": "儲存篩選",
    "saved_filter.delete": "刪除篩選",
    "auth.login": "帳號登入",
    "auth.revoke": "撤銷登入",
    "auth.activation": "產生登入連結",
    "auth.password": "設定密碼",
    "organization.update": "更新組織",
    "membership.update": "成員權限",
    "account.update": "帳號設定",
    "oa.save": "LINE OA 設定",
    "oa.active": "LINE OA 啟停",
    "oa.share": "LINE OA 共享",
    "send.create": "建立發送",
    "send.cancel": "取消預約",
    "vendor.view": "透明稽核"
  };
  return actionMap[action] || action;
}

function formatAuditDetail(detail, action){
  if(!detail) return "";
  let s = String(detail);

  // 1. 聊天狀態轉換
  s = s.replace(/變更聊天狀態為\s*\[?(done|pending|in_progress|open)\]?/gi, (match, st) => {
    const statusMap = { done: "已完成", pending: "待處理", in_progress: "處理中", open: "一般（無狀態）" };
    return `變更聊天狀態為 [${statusMap[st.toLowerCase()] || st}]`;
  });

  // 2. 記事政策轉換（相容歷史字串與新格式）
  s = s.replace(/更新記事政策[（\(]鎖定=([^,]+),\s*標籤=([^）\)]+)[）\)]/g, (match, lock, tag) => {
    const lockMap = { disabled: "自由編輯模式", collaborative: "全員協作防護", strict_admin: "管理員嚴格管控" };
    const tagMap = { controlled: "集中規範管理", open: "全員自由自訂" };
    const lockTxt = lockMap[lock.trim()] || lock.trim();
    const tagTxt = tagMap[tag.trim()] || tag.trim();
    return `更新記事本政策：[防護模式：${lockTxt}] · [標籤管理：${tagTxt}]`;
  });

  // 3. 處理其他常見英文狀態與代號
  s = s.replace(/（push）/g, "（直接推播）")
       .replace(/（reply）/g, "（回覆訊息）")
       .replace(/（flex）/g, "（圖文卡片）");

  return s;
}
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
  const isGroup=r.kind!=="user";
  const initial=primary.slice(0,1).toUpperCase();
  const avatarHtml=r.picture_url?`<span class="avatar ${isGroup?"group":""}"><img src="/api/chat/avatar/${encodeURIComponent(r.recipient_id)}" class="avatar-img" alt="${esc(primary)}" onerror="this.outerHTML='<span class=\\'avatar-text\\'>${esc(initial)}</span>'"></span>`:`<span class="avatar ${isGroup?"group":""}"><span class="avatar-text">${esc(initial)}</span></span>`;
  return `<div class="person">${avatarHtml}<div><div class="person-title"><strong>${esc(primary)}</strong>${showLineName?`<span class="line-name muted" data-s="s102ad5b">（LINE: ${esc(r.display_name)}）</span>`:''}</div><div class="person-sub"><small class="muted">${isGroup?"群組聊天室":"個人聊天室"}${!r.active?" · 已停用":""}${truncatedId?` · <span class="line-id-chip">${esc(truncatedId)}</span>`:""}</small></div>${tags.length?`<div class="contact-tags">${tags.map(t=>tagBadge(t)).join("")}</div>`:""}</div></div>`;
};
const scope=r=>r.category==="composition"?(r.organization_id?orgName(r.organization_id):"平台個人素材"):"自訂文字訊息";
let noticeTimeout = null;
const personalDefaults={corner:'bottom-right',duration:5,reading:'standard',motion:'standard'};
function personalSettingsKey(){return 'linePersonalSettings:'+(principalSession?.identity||state.session?.identity||'local');}
function personalSettings(){
  let saved={};try{saved=JSON.parse(localStorage.getItem(personalSettingsKey())||'{}')||{};}catch(_){}
  return {
    corner:['bottom-right','bottom-left','top-right','top-left'].includes(saved.corner)?saved.corner:personalDefaults.corner,
    duration:[1,3,5,8,10,0].includes(Number(saved.duration))?Number(saved.duration):personalDefaults.duration,
    reading:['small','standard','large'].includes(saved.reading)?saved.reading:'standard',motion:saved.motion==='reduced'?'reduced':'standard'
  };
}
function applyPersonalSettings(){
  const settings=personalSettings();
  document.documentElement.dataset.reading=settings.reading;
  document.documentElement.dataset.motion=settings.motion;
  document.querySelectorAll('#floating-toast,.tmpl-undo-toast').forEach(toast=>toast.dataset.corner=settings.corner);
}
function personalSettingsPage(){
  const prefs=personalSettings();
  const options=(items,value)=>items.map(([id,label])=>`<option value="${id}" ${String(value)===String(id)?'selected':''}>${label}</option>`).join('');
  return heading('個人化設定','調整通知與閱讀體驗，變更後自動儲存於此瀏覽器，依登入帳號分開記住。')+`
    <div class="personal-settings-grid">
      <section class="panel"><div class="panel-head"><h2>${icon('bell')} 通知</h2></div><div class="panel-body">
        <label class="field">顯示位置<select data-personal-setting="corner">${options([['bottom-right','右下角（預設）'],['bottom-left','左下角'],['top-right','右上角'],['top-left','左上角']],prefs.corner)}</select></label>
        <label class="field section-space">顯示時間<select data-personal-setting="duration">${options([[1,'1 秒'],[3,'3 秒'],[5,'5 秒（預設）'],[8,'8 秒'],[10,'10 秒'],[0,'手動關閉']],prefs.duration)}</select></label>
        <p class="muted">適用於所有頁面的操作結果與警告通知。</p>
        <div class="form-actions">${button('預覽資訊通知','personal-preview-info')}${button('預覽警告通知','personal-preview-warning')}</div>
      </div></section>
      <section class="panel"><div class="panel-head"><h2>${icon('settings')} 閱讀與動態效果</h2></div><div class="panel-body">
        <label class="field">文字大小<select data-personal-setting="reading">${options([['small','小'],['standard','中（預設，依螢幕調整）'],['large','大']],prefs.reading)}</select></label>
        <label class="field section-space">動態效果<select data-personal-setting="motion">${options([['standard','標準'],['reduced','減少動畫']],prefs.motion)}</select></label>
        <p class="muted">放大文字會同步調整內文、控制項與功能選單。</p>
      </div></section>
    </div><div class="form-actions">${button('還原預設設定','personal-reset')}</div>`;
}
function notice(message, error=false){
  const el = $("notice");
  if(el){
    el.textContent = "";
    el.hidden = true;
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
  toast.dataset.corner=personalSettings().corner;
  toast.setAttribute('role',error?'alert':'status');
  const closeBtn = toast.querySelector(".toast-close");
  if(closeBtn) closeBtn.onclick = () => toast.classList.remove("visible");
  if(noticeTimeout) clearTimeout(noticeTimeout);
  const seconds=personalSettings().duration;
  noticeTimeout = seconds ? setTimeout(() => {
    toast.classList.remove("visible");
  }, seconds*1000) : null;
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
  if(!response.ok){const error=new Error(result.error||"操作未完成。");error.status=response.status;error.errors=result.errors||{};if(response.status===401)state.authLost=true;throw error;}
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
  if(state.session.role==='org_admin'){
    const personnel=await api('/api/personnel');
    const access=new Map(personnel.members.map(m=>[m.email,m.channel_ids]));
    for(const member of state.memberships)if(member.org_id===state.session.user.organization_id&&access.has(member.email))member.channel_ids=access.get(member.email);
  }
  $("switch-view").hidden=!["platform_admin","org_admin"].includes(principalSession.role);
  $("view-banner").hidden=!state.session.preview;
  $("view-description").textContent=state.session.preview?`角色視角：${roleName(state.session.role)} · ${state.session.user.display_name||viewAs}（${viewAs} · ${orgName(state.session.user.organization_id)}） · 實際登入：${principalSession.identity}`:"";
  $("account-name").textContent=state.session.user?.display_name||state.session.identity;
  $("account-role").textContent=(state.session.preview?"預覽 · ":"")+roleName(state.session.role)+(state.session.user?.organization_id?" · "+orgName(state.session.user.organization_id):"");
  $("avatar").textContent=($("account-name").textContent||"L").slice(0,1).toUpperCase();
  document.querySelectorAll("[data-admin]").forEach(el=>{el.hidden=!admin();});document.querySelectorAll("[data-platform]").forEach(el=>{el.hidden=!superAdmin();});
  // 平台管理員不進入 OA 營運畫面（權限規格 8.1），也不預先讀取客戶資料，避免在客戶操作紀錄留下查看紀錄。
  if(admin()&&lineDataReady()&&!superAdmin()){
    const results=await Promise.all([api("/api/contacts"),api("/api/jobs"),(manager()?api("/api/settings"):Promise.resolve({users:[]})),api("/api/activity"),api("/api/cases"),api("/api/saved-filters")]);
    state.contacts=results[0].contacts;state.tags=results[0].tags||[];state.jobs=results[1].jobs;state.settings=results[2];state.events=results[3].events;state.cases=results[4].cases||[];state.savedFilters=results[5].saved_filters||[];
    state.selected=new Set([...state.selected].filter(id=>state.contacts.some(r=>r.recipient_id===id&&r.active)));
    if(typeof loadChatRooms==="function")await loadChatRooms();
  }else{state.contacts=[];state.tags=[];state.jobs=[];state.cases=[];state.savedFilters=[];state.chatNotes.clear();state.events=[];state.settings=manager()?await api("/api/settings"):{users:[]};state.selected.clear();}
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
  if(state.view==="organizations"&&!superAdmin())state.view="overview";
  if(["personnel","org-settings","templates"].includes(state.view)&&!orgAdmin&&!admin())state.view="overview";
  if(state.view==="channels"&&!navAllowed["platform-org"])state.view="overview";
  if(!lineDataReady()&&!["organizations","channels","oa-list","personnel","org-settings","templates","personal-settings","duty"].includes(state.view))state.view=superAdmin()?"organizations":"channels";
  if(superAdmin()&&!["organizations","channels","personal-settings"].includes(state.view))state.view="organizations";
  await loadForms();
  const dutyVisible=Boolean(state.session.duty_capabilities?.view);
  $("duty-nav-label").hidden=!dutyVisible&&!state.session.forms_capabilities?.view;
  document.querySelector('nav [data-view="duty"]').hidden=!dutyVisible;
  dutyContext=dutyVisible?await api("/api/duty"):null;
  await loadDutySetup();
  await loadDutyRosters();
  await loadDutyAutomation();
  if(dutyContext)await loadDutyHome();
  if(state.view==="duty"&&!dutyVisible)state.view=superAdmin()?"organizations":"overview";
  workspaceHeader();
  state.loaded=true;state.authLost=false;$("connection").innerHTML='<span class="status-dot"></span>已連線';
  $("sync-time").textContent="最後更新 "+new Date().toLocaleTimeString("zh-TW",{hour12:false});
  const activeCases=state.cases.filter(c=>c.status!=="closed").length;if($("nav-case-count"))$("nav-case-count").textContent=activeCases||"0";
  if(["reports","subscriptions"].includes(state.view))state.view="overview";
}
function heading(title,subtitle,actions="",eyebrow="WORKSPACE"){return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="subtitle">${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`;}
function tile(r){return r.category==="composition"?composerPreview(r.draft):`<div class="message-preview">${esc(r.message_text)}</div>`;}
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
  const active=state.contacts.filter(r=>r.active).length, groups=state.contacts.filter(r=>r.active&&r.kind!=="user").length;
  const pending=state.jobs.filter(j=>["scheduled","queued","running"].includes(j.status)).length;
  const openCases=state.cases.filter(c=>c.status!=="closed").length;
  const date=new Date().toLocaleDateString("zh-TW",{month:"long",day:"numeric",weekday:"long"});
  const currentOrgName = orgName(state.session.user?.organization_id) || "—";
  return heading("今天的工作，一目了然",`${esc(date)}　·　查看對話、追蹤案件，掌握每次發送結果。`,canSend()?button(icon("plus")+"建立發送","start-send","primary"):"","YOUR DAILY WORKSPACE")+
    renderOnboardingCard()+
    `<div class="stats">${stat("有效聯絡對象",active,"個",`${groups} 個群組聊天室`,"users")}${stat("未結案案件",openCases,"件","依案件狀態追蹤","folder")}${stat("所屬組織",esc(currentOrgName),"","資料依組織隔離","shield")}${stat("進行中的發送",pending,"筆","結果不明的請求不自動重送","send")}</div>
    <div class="dashboard-grid"><div class="stack"><section class="panel"><div class="panel-head"><h2>最近發送</h2><button class="btn text small" data-view="history">查看全部 ${icon("arrow")}</button></div>${historyList(state.jobs.slice(0,3))}</section></div><div class="stack"><section class="panel"><div class="panel-head"><h2>快速前往</h2></div><div class="quick-list">${quick("聊天對話","查看與回覆 LINE 即時訊息","chat","message")}${quick("案件管理","追蹤需要處理的事項","cases","folder")}${quick("聯絡對象","整理公司、部門與群組","contacts","users")}</div></section></div></div>`;
}
function eligible(r){const source=state.report;if(source?.category==="composition")return !source.organization_id||r.organization_id===source.organization_id;return true;}
function filteredContacts(){return state.contacts.filter(r=>{const q=state.search.toLowerCase();const tagMatch=!state.tagFilter||((r.tags||[]).some(t=>String(t.id)===String(state.tagFilter)||t.name===state.tagFilter));const searchMatch=!q||`${label(r)} ${r.display_name||""} ${r.recipient_id||""} ${r.organization_id||""} ${r.department||""} ${r.notes||""} ${(r.tags||[]).map(t=>t.name).join(" ")}`.toLowerCase().includes(q);const kindMatch=state.kind==="all"||(state.kind==="group"?r.kind!=="user":r.kind===state.kind);const companyMatch=!state.organization_id||r.organization_id===state.organization_id;const deptMatch=!state.department||r.department===state.department;const sendEligible=state.view!=="send"||(r.active&&eligible(r));return tagMatch&&searchMatch&&kindMatch&&companyMatch&&deptMatch&&sendEligible;});}
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
    <select id="contact-department" aria-label="篩選內部分組">${options([["","所有內部分組"],...depts.map(c=>[c,c])],state.department)}</select>
    ${state.savedFilters?.length?`<select id="apply-saved-filter" aria-label="套用自訂篩選">${options(filterOpts,"")}</select>`:""}
    ${canSend()&&state.view==="contacts"?button(icon("send")+"對篩選對象發送 ("+filteredContacts().length+")","send-to-filtered","small primary"):""}
    ${manager()&&state.view==="contacts"?button("儲存篩選","open-save-filter-modal","small")+button(icon("settings")+"標籤管理","manage-tags","small"):""}
  </div>`;
}
function contactList(){const rows=filteredContacts(),pages=Math.max(1,Math.ceil(rows.length/10));state.page=Math.min(state.page,pages);const visible=rows.slice((state.page-1)*10,state.page*10);const isSendAudience=state.view==="send"&&state.audience==="selected";const isContactsView=state.view==="contacts"&&manager();const showCheckboxes=isSendAudience||isContactsView;const selectedCount=state.selected.size;let bulkBar="";if(isContactsView&&selectedCount>0){bulkBar=`<div class="bulk-toolbar"><div><strong>已選取 ${selectedCount} 個聯絡對象</strong></div><div class="bulk-actions">${canSend()?button(icon("send")+"對已選對象發送","send-to-selected","small primary"):""}${button("批次加標籤","bulk-add-tags","small")}${button("批次移除標籤","bulk-remove-tags","small")}${button("清除勾選","clear-selection","text small")}</div></div>`;}else if(isSendAudience){bulkBar=`<div class="toolbar">${button("勾選本頁","select-page","small")}${button("清除勾選","clear-selection","text small")}<small class="muted">共 ${rows.length} 個可發送的聊天室</small></div>`;}return `${bulkBar}<div class="table-scroll"><table class="contacts-table"><thead><tr><th class="select-cell">${showCheckboxes?`<input type="checkbox" id="select-all-visible" aria-label="全選本頁" ${visible.length&&visible.every(r=>state.selected.has(r.recipient_id))?"checked":""}>`:""}</th><th>聯絡對象</th><th>組織／內部分組</th><th>操作</th></tr></thead><tbody>${visible.map(r=>`<tr><td class="select-cell">${showCheckboxes?`<input type="checkbox" data-select="${esc(r.recipient_id)}" aria-label="選取 ${esc(label(r))}" ${state.selected.has(r.recipient_id)?"checked":""}>`:""}</td><td class="person-cell">${state.view==="contacts"?`<button class="contact-open" data-action="contact-detail" data-id="${esc(r.recipient_id)}" aria-label="查看 ${esc(label(r))} 詳情">${person(r)}</button>`:person(r)}</td><td class="meta-cell">${esc(r.organization_id?orgName(r.organization_id):"尚未分類")}<small class="muted">${r.department?" / "+esc(r.department):""}</small></td><td class="action-cell">${manager()?button("管理","edit-contact","small",`data-id="${esc(r.recipient_id)}"`):badge("已授權")}</td></tr>`).join("")}</tbody></table></div>${!rows.length?empty("沒有符合的聯絡對象",state.view==="send"?"請確認聯絡對象屬於本組織，並已與 Bot 互動。":"調整篩選條件，或請使用者向 Bot 傳送訊息以建立名單。"):""}<div class="pagination"><span>共 ${rows.length} 個聊天室</span><div>${button("上一頁","prev-page","small",state.page<=1?"disabled":"")}<span>${state.page} / ${pages}</span>${button("下一頁","next-page","small",state.page>=pages?"disabled":"")}</div></div>`;}
function contactsPage(){return heading("聯絡對象","依公司與部門整理個人、群組，自訂名稱與筆記，讓訊息送到正確的地方。",(manager()?button(icon("download")+"匯出 CSV","export-contacts-csv")+button(icon("refresh")+"更新 LINE 名稱","profiles"):""),"CONTACT DIRECTORY")+`<div class="library-split section-space ${workspaceUI.contactDetail?"has-detail":""}"><section class="panel">${contactToolbar()}<div id="contact-list">${contactList()}</div></section>${contactDetailPanel()}</div>`;}
function contactExportRows(scope){
  if(scope==='selected')return state.contacts.filter(r=>state.selected.has(r.recipient_id));
  return scope==='filtered'?filteredContacts():state.contacts;
}
function contactExportModal(){
  if(!manager()||!lineDataReady())return;
  modal('匯出聯絡對象 CSV',`<p>LINE OA：${esc(selectedOA().name)}。包含聯絡資訊、內部分組、標籤與備忘。</p><div class="stack">${[['filtered','目前篩選結果'],['all','此 OA 全部聯絡對象'],['selected','已勾選的聯絡對象']].map(([id,title])=>`<label class="check-label"><input type="radio" name="contact-export-scope" value="${id}" ${id==='filtered'?'checked':''} ${contactExportRows(id).length?'':'disabled'}>${title}（${contactExportRows(id).length} 筆）</label>`).join('')}</div><p class="muted">CSV 使用 UTF-8，Excel 可直接開啟。電話及郵遞區號以文字格式匯出。</p><div class="form-actions">${button('下載 CSV','download-contacts-csv','primary')}</div>`);
}
function downloadContactsCsv(){
  if(!manager()||!lineDataReady())throw new Error('目前無法匯出聯絡對象。');
  const scope=document.querySelector('[name="contact-export-scope"]:checked')?.value;
  if(!['all','filtered','selected'].includes(scope))throw new Error('請選擇匯出範圍。');
  const rows=contactExportRows(scope);if(!rows.length)throw new Error('沒有可匯出的聯絡對象。');
  const fields=[['LINE OA',()=>selectedOA().name],['聊天室識別碼',r=>r.recipient_id],['聊天室類型',r=>({user:'個人',group:'群組',room:'多人聊天室'}[r.kind]||r.kind)],['LINE 顯示名稱',r=>r.display_name],['備註名稱',r=>r.custom_name],['系統組織',r=>orgName(r.organization_id)],['內部分組',r=>r.department],['聯絡對象類型',r=>({organization:'組織／團體',person_business:'公務對象個人',person_private:'一般個人'}[r.contact_type]||'未分類')],['對方組織',r=>r.organization_name],['部門',r=>r.work_department],['職稱',r=>r.job_title],['聯絡電話',r=>r.phone,true],['Email',r=>r.email],['公務電話',r=>r.work_phone,true],['分機',r=>r.work_phone_ext,true],['公務 Email',r=>r.work_email],['郵遞區號',r=>r.postal_code,true],['地址',r=>r.address],['標籤',r=>(r.tags||[]).map(t=>t.name).join('；')],['內部備忘',r=>r.notes],['狀態',r=>r.active?'可接收':'已停用']];
  const cell=(value,text=false)=>{
    let result=String(value??'');
    if(result&&(text||/^[\s\uFEFF]*[=+@-]/.test(result)||/^[\t\r\n]/.test(result)))result="'"+result;
    return '"'+result.replace(/"/g,'""')+'"';
  };
  const csv='\uFEFF'+[fields.map(([title])=>cell(title)).join(','),...rows.map(r=>fields.map(([,get,text])=>cell(get(r),text)).join(','))].join('\r\n')+'\r\n';
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');
  link.href=url;link.download='聯絡對象_'+selectedOA().name.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_')+'_'+new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Taipei'})+'.csv';
  document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('modal').close();notice('已匯出 '+rows.length+' 筆聯絡對象。');
}
function selectedRows(){return state.contacts.filter(r=>r.active&&eligible(r)&&state.selected.has(r.recipient_id));}
function selectionSummary(){const rows=selectedRows();return `<div class="panel selection-summary"><div class="panel-body">${tile(state.report)}<p class="eyebrow section-space">THIS DELIVERY</p><h3>${esc(state.report.title)}</h3><p class="subtitle">${esc(scope(state.report))}</p><div class="count-big">${rows.length}<small>個聊天室</small></div><div class="summary-list">${rows.map(r=>`<span>${esc(label(r))}</span>`).join("")||'<small class="muted">請從名單選擇發送對象</small>'}</div><p class="callout">每個聊天室會收到這次確認的內容。</p></div></div>`;}
function sendPage(){
  const r=state.report;
  const audienceOptions=[["selected","手動選擇"],["by-tags","依標籤傳訊"],["by-filter","依自訂條件"]];

  return heading("建立發送","依序確認內容、對象與時間，每次發送都有完整紀錄。","","NEW DELIVERY")+
    `<div class="steps">${["編輯內容","選擇對象","確認發送"].map((t,i)=>`${i?'<span class="step-line"></span>':""}<span class="step ${state.step===i+1?"active":""}"><b>${i+1}</b>${t}</span>`).join("")}</div>`+
    (state.step===1||!r?composerEditor()+`<section class="panel panel-body section-space"><h2>文字訊息</h2><p class="subtitle">輸入公告或提醒，下一步選擇發送對象與傳送時間。</p><textarea id="message-draft" maxlength="5000" rows="5" placeholder="輸入要傳送的文字">${esc(state.textDraft||"")}</textarea><div class="form-actions">${button("使用這段文字","choose-text","primary")}</div></section>`:
     state.step===2?`<div class="send-grid"><section class="panel"><div class="panel-head"><div><h2>這次要發給誰？</h2><p>僅列出本組織的有效聯絡對象</p></div></div>
     <div class="toolbar segmented">${audienceOptions.map(([id,t])=>`<button data-action="audience" data-id="${id}" class="${state.audience===id?"active":""}">${t}</button>`).join("")}</div>
     ${state.audience==="selected"?contactToolbar()+`<div id="contact-list">${contactList()}</div>`:
       state.audience==="by-tags"?renderAudienceTagsSelector():
       renderAudienceSavedFiltersSelector()}
     <div class="selection-footer">${button("返回編輯","back-report")}${button("下一步：確認發送 "+icon("arrow"),"review","primary",`id="review-button" ${selectedRows().length?"":"disabled"}`)}</div></section><aside id="selection-summary">${selectionSummary()}</aside></div>`:
     confirmation());
}
function confirmation(){
  const r=state.report,rows=selectedRows();
  const audienceText=state.audience==="by-tags"?"依標籤傳訊":state.audience==="by-filter"?"依自訂篩選條件":"手動選擇";
  return `<section class="panel"><div class="panel-head"><h2>確認這次的發送內容</h2>${badge("可發送","good")}</div><div class="panel-body confirm-grid"><div>${tile(r)}</div><div><p class="eyebrow">DELIVERY SUMMARY</p><h2>${esc(r.title)}</h2><div class="detail-row"><span>發送方式</span><strong>${audienceText}</strong></div><div class="detail-row"><span>發送 OA</span><strong>${esc(selectedOA()?.name||"既有 OA")}</strong></div><div class="detail-row"><span>工作區</span><strong>${esc(selectedWorkspace()?.name||"目前工作區")}</strong></div><div class="detail-row"><span>收件聊天室</span><strong>${rows.length} 個（${rows.filter(x=>x.kind==="user").length} 個人／${rows.filter(x=>x.kind!=="user").length} 群組）</strong></div><div class="detail-row"><span>操作人</span><strong>${esc(state.session.identity)}</strong></div><div class="summary-list">${rows.map(x=>`<span>${esc(label(x))}</span>`).join("")}</div><p class="callout warn" data-s="se9d9bb6">此類訊息一律計入當月訊息額度（預估使用 <strong>${rows.length} 則</strong>額度，群組聊天室依實際人數計扣）。</p><p class="callout">送出前會再次檢查收件範圍。LINE 已接受代表 API 受理，不代表對方已讀。</p>${scheduleFields()}<div class="form-actions">${button("上一步","back-recipients")}${button(icon("send")+`確認發送給 ${rows.length} 個聊天室`,"submit-send","primary",`id="submit-send" ${state.busy||!rows.length?"disabled":""}`)}</div></div></div></section>`;
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

  return `<article class="case-card ${c.is_locked?'locked':''}" data-case-preview="${esc(c.case_id)}" tabindex="0">
    <div class="case-card-head">
      <div class="case-card-main-title">
        <span class="case-no-badge">${esc(c.case_no)}</span>
        <h3 class="case-title">${esc(c.title)}</h3>
        ${recordLockControl(c,true)}
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
      ${!recordReadonly(c,true) && c.status==="pending"?button("開始處理","case-to-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${!recordReadonly(c,true) && c.status==="processing"?button("進入等待","open-case-waiting-modal","small",`data-id="${esc(c.case_id)}"`)+button("進入待結案","case-to-ready","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${!recordReadonly(c,true) && c.status==="waiting"?button("恢復處理","case-resume-processing","primary small",`data-id="${esc(c.case_id)}"`):""}
      ${!recordReadonly(c,true) && c.status==="ready_to_close"?button("退回處理","case-back-processing","small",`data-id="${esc(c.case_id)}"`)+button("執行結案","open-case-close-modal","good primary small",`data-id="${esc(c.case_id)}"`):""}
      ${c.status==="closed"?badge("已完成結案","good"):""}

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
  const cat = prefill.category || "一般備忘";
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
      ${field("案件類別","category",cat,'maxlength="50" placeholder="例如：一般備忘、商務往來、問題處理、待辦交接"')}
      ${selectField("優先度","priority",[["medium","一般"],["low","低"],["high","高"],["urgent","緊急"]],prefill.priority||"medium")}
      ${field("參考編號（選填）","ref_no",prefill.ref_no||"",'maxlength="50" placeholder="例如：訂單號 #202610-A01、發票號"')}
      ${field("預計完成期限（選填）","due_date",prefill.due_date||"",'type="date"')}
      ${renderDualFormatEditor("description", "case-description-input", desc, null, "問題或需求描述（選填）", 12, "詳細說明對方需求、對話重點、目前已知資訊...", false)}
    </div>
    <p class="callout">建立案件後初始狀態為「待處理」，自動編號格式為 {前綴}-{年月}-{4位流水號}。</p>
    <div class="form-actions"><button class="btn primary" type="submit">確認建立案件</button></div>
  </form>`);
}

function editCaseModal(case_id){
  const c=state.casePreview?.case_id===case_id?state.casePreview:state.cases.find(x=>x.case_id===case_id);
  if(!c || c.is_locked || c.status==="closed" || state.preview || state.session?.role==="platform_admin")return;
  modal("編輯案件",`<form id="case-edit-form" data-id="${esc(case_id)}"><div class="form-grid">
    <div class="full">${field("案件標題","title",c.title,'required maxlength="100"')}</div>
    ${field("分類","category",c.category||"",'maxlength="50"')}
    ${selectField("優先度","priority",[["medium","一般"],["low","低"],["high","高"],["urgent","緊急"]],c.priority||"medium")}
    ${field("參考編號","ref_no",c.ref_no||"",'maxlength="60"')}
    ${field("預計完成期限","due_date",c.due_date||"",'type="date"')}
      ${renderDualFormatEditor("description","case-edit-description",c.description||"",null,"需求描述",8,"記錄需求、進度與待辦事項",false,true)}
    </div><div class="form-actions">${button("返回預覽","open-case-detail","",`data-id="${esc(case_id)}" type="button"`)}<button type="submit" class="btn primary">儲存變更</button></div></form>`);
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
    state.casePreview = c;
    const activities=res.activities||c.activities||[];
    const subject=state.contacts.find(x=>x.recipient_id===c.case_subject_id);
    const subjectName=subject?label(subject):"未命名聯絡對象";

    const timelineHtml=activities.length?activities.map(a=>{
      let desc="";
      if(a.action==="create_case")desc="建立案件";
      else if(a.action==="status_change")desc=`狀態變更：${caseStatusNames[a.details?.old_status]||a.details?.old_status} <span class="status-change-arrow" aria-hidden="true">${icon("arrow")}</span> <strong>${caseStatusNames[a.details?.new_status]||a.details?.new_status}</strong>${a.details?.waiting_party?`（等待：${waitingPartyNames[a.details.waiting_party]||a.details.waiting_party}，原因：${esc(a.details.waiting_reason||"")}）`:""}${a.details?.resolution?`（結案說明：${esc(a.details.resolution)}）`:""}`;
      else if(a.action==="add_note" || a.action==="note")desc=`處理記事：${esc(a.content || a.details?.note || "")}`;
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
          ${recordLockControl(c,true)}
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
      ${c.description?`<div class="section-space"><h4>需求描述</h4><div class="case-desc-box case-description-preview md-preview-area">${renderCaseContent(c)}</div></div>`:""}

      <div class="section-space" data-s="s78cead6">
        ${button(icon('copy')+'複製內容','copy-case-content','small',`data-id="${esc(c.case_id)}"`)}
        ${!c.is_locked && c.status!=="closed" && !state.preview && state.session?.role!=="platform_admin" ? button(icon("edit")+"編輯案件","edit-case-modal","primary small",`data-id="${esc(c.case_id)}"`):""}
        ${canSend() && c.status !== "closed" ? `<button class="btn primary small" data-action="open-case-notify-modal" data-id="${esc(c.case_id)}">通知案件對象</button>` : ''}
        <button class="btn small" data-action="save-case-as-template" data-id="${esc(c.case_id)}">存為案件範本</button>
      </div>

      <div class="section-space">
        <h4>處理歷程與時間軸 (Timeline)</h4>
        <div class="case-timeline">${timelineHtml}</div>
      </div>

      ${!recordReadonly(c,true) ? `<form id="case-add-note-form" data-id="${esc(c.case_id)}" class="section-space">
        <label class="field">新增處理紀錄 / 備忘<textarea name="note" rows="2" required maxlength="1000" placeholder="記錄最新溝通進度、待辦項目或內部確認事項..."></textarea></label>
        <div class="form-actions">${button("送出紀錄","","primary small",'type="submit"')}</div>
      </form>` : ''}
    </div>`);
  }catch(e){
    modal("載入失敗",`<p class="callout warn">${esc(e.message)}</p>`);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  notice("記事內容已複製至剪貼簿。");
}

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

function categoryPillHtml(categoryName){
  if(!categoryName) return '';
  return `<span class="tax-item-category-badge" style="font-size:11.5px;padding:2px 8px;gap:5px;">${icon("folder")}<span>${esc(categoryName)}</span></span>`;
}

async function loadChatNotes(recipient_id){
  try{
    const res=await api(`/api/chat-notes?recipient_id=${encodeURIComponent(recipient_id)}`);
    state.chatNotes.set(recipient_id,res.notes||[]);
    const container=$("chat-notes-list-container");
    if(document.querySelector(".chat-work-panel"))refreshChatWorkPanel();
    else if(container)container.innerHTML=renderChatNotesList(recipient_id);
  }catch(e){
    console.error("Failed to load chat notes:",e);
  }
}

async function loadTaxonomyCaches(){
  try{
    const [catsRes, tagsRes] = await Promise.all([
      api("/api/chat-notes/categories"),
      api("/api/chat-notes/tags")
    ]);
    state.noteCategories = catsRes.categories || [];
    state.noteTags = tagsRes.tags || [];
  }catch(_){}
}

function renderCategoryScopedTagsHtml(categoryId, selectedTagsList = []){
  const cat = (state.noteCategories||[]).find(c => c.category_id === categoryId);
  const catName = cat?.name || "";

  const sortedTags = [...(state.noteTags||[])].sort((a,b) => {
    const aCatScore = (a.category_usage?.[categoryId] || (catName && a.category_usage?.[catName]) || 0);
    const bCatScore = (b.category_usage?.[categoryId] || (catName && b.category_usage?.[catName]) || 0);
    const aTotal = a.note_count || a.usage_count || 0;
    const bTotal = b.note_count || b.usage_count || 0;

    // 優先依照該分類下的專屬熱門度（引用次數）排序；次之依照 OA 總次數
    if(bCatScore !== aCatScore) return bCatScore - aCatScore;
    return bTotal - aTotal;
  });

  if(!sortedTags.length) return "";

  const hintText = catName ? `「${catName}」專屬熱門` : "依使用熱門度排序";

  return `
    <div class="quick-tag-wrapper">
      <div class="quick-tag-label">
        <div class="quick-tag-label-left">${icon("tag")} <span>${catName ? `「${esc(catName)}」常用推薦標籤：` : '常用熱門標籤（點選帶入）：'}</span></div>
        <small class="muted" style="font-size:11px;">${esc(hintText)}</small>
      </div>
      <div class="quick-tag-pills">
        ${sortedTags.map(t => {
          let color = t.color || DEFAULT_TAG_COLORS[t.name];
          if(!color){
            const palette = ["#007AFF","#34C759","#FF9500","#AF52DE","#FF2D55","#5856D6","#30B0C7","#FF3B30","#FFCC00","#8E8E93"];
            let hash = 0;
            for(let i=0; i<t.name.length; i++) hash = (hash << 5) - hash + t.name.charCodeAt(i);
            color = palette[Math.abs(hash) % palette.length];
          }
          const bg = color.length === 7 ? color + "20" : "rgba(0,122,255,0.14)";
          const border = color.length === 7 ? color + "48" : "rgba(0,122,255,0.3)";
          const isSelected = selectedTagsList.includes(t.name);
          const catCount = (t.category_usage?.[categoryId] || (catName && t.category_usage?.[catName]) || 0);
          const totalCount = t.note_count || t.usage_count || 0;
          const tip = catName && catCount > 0 ? `${catName}分類引用 ${catCount} 次 · 全OA總計 ${totalCount} 次` : `全OA引用 ${totalCount} 次`;
          return `<button type="button" class="apple-tag-pill ${isSelected?'active-selected':''}" aria-pressed="${isSelected}" data-action="quick-add-note-tag" data-tag="${esc(t.name)}" data-color="${esc(color)}" style="background-color:${esc(isSelected ? color : bg)}!important;color:${esc(isSelected ? '#ffffff' : color)}!important;border-color:${esc(isSelected ? color : border)}!important;" title="${esc(tip)}">${isSelected ? '✓ ' : ''}${esc(t.name)}</button>`;
        }).join("")}
      </div>
    </div>
  `;
}

async function chatNoteModal(recipient_id,note_id="",prefill={}){
  if(!state.noteCategories.length || !state.noteTags.length){
    await loadTaxonomyCaches();
  }
  const notes=recipient_id? (state.chatNotes.get(recipient_id)||[]) : [];
  const existing=note_id?(notes.find(n=>n.note_id===note_id) || state.globalNotes?.find(n=>n.note_id===note_id) || (state.notePreview?.note_id===note_id?state.notePreview:null)):null;
  const title = prefill.title || existing?.title || "";
  const content = prefill.content || existing?.content || "";

  let category_id = prefill.category_id || existing?.category_id || "";
  if(!category_id && prefill.category_name){
    const matchedCat = (state.noteCategories||[]).find(c => c.name === prefill.category_name);
    if(matchedCat) category_id = matchedCat.category_id;
  }
  if(!category_id){
    category_id = state.noteCategories[0]?.category_id || "";
  }

  const due_date = prefill.due_date || existing?.due_date || "";
  const tagsList = prefill.tags ? (Array.isArray(prefill.tags) ? prefill.tags : prefill.tags.split(/[,，]/).map(s=>s.trim()).filter(Boolean)) : (existing?.tags || []);
  const tagsStr = tagsList.join(", ");
  const updated_at = existing?.updated_at || "";

  const catOptions = (state.noteCategories||[]).map(c => [c.category_id, c.name]);
  if(!catOptions.length) catOptions.push(["", "一般備忘"]);

  const contactOpts = [["", "請選擇關聯的聯絡對象 / 聊天室"], ...state.contacts.filter(r => r.active).map(r => [r.recipient_id, label(r) + (r.kind === "user" ? " (個人)" : " (群組)")])];

  modal(existing ? "編輯對話記事" : "新增對話記事", `<form id="chat-note-form" data-recipient="${esc(recipient_id)}" data-note-id="${esc(note_id)}" data-dirty="false">
    ${updated_at ? `<input type="hidden" name="expected_updated_at" value="${esc(updated_at)}">` : ''}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <span class="muted" style="font-size:12px;">記錄對話重要承諾、待辦、工務或商務摘要</span>
      ${recipient_id ? `<button type="button" class="btn text small" data-action="open-note-template-picker" data-recipient="${esc(recipient_id)}">從範本帶入</button>` : ''}
    </div>
    <div class="form-grid">
      ${!recipient_id ? `<div class="full">${selectField("關聯聯絡對象（必選）", "recipient_id", contactOpts, "")}</div>` : ''}
      <div class="full">${field("記事標題（選填）", "title", title, 'maxlength="50" placeholder="例如：客戶詢問合約條件、報修現況、會議結論"')}</div>
      ${selectField("記事分類", "category_id", catOptions, category_id)}
      ${field("完成期限（選填）", "due_date", due_date, 'type="date"')}
      <div class="full">
        <label class="field">記事標籤（從清單選擇，最多 ${cap("TAGS_PER_NOTE")} 個）
          <input type="hidden" name="tags" id="chat-note-tags-input" value="${esc(tagsStr)}"><span id="chat-note-selected-tags" class="muted">${esc(tagsStr || "尚未選擇標籤")}</span>
        </label>
        <div id="chat-note-quick-tags-container">
          ${renderCategoryScopedTagsHtml(category_id, tagsList)}
        </div>
      </div>
      ${renderDualFormatEditor("content", "chat-note-content-input", content, null, "記事內容（1–2,000 字）", 12, "記錄該對話的重要交辦、協商細節、政策討論、客戶訴求...", true,Boolean(existing))}
    </div>
    <p class="callout" style="font-size:12px;">手動點選「儲存」以生效。未儲存前離開將彈出防呆警示；鎖定後支援唯讀複製，防止其他人誤改。</p>
    <div class="form-actions"><button class="btn primary" type="submit">${existing ? "儲存變更" : "新增記事"}</button></div>
  </form>`);

  const form = $("chat-note-form");
  if(form){
    form.addEventListener("input", () => { form.dataset.dirty = "true"; });
    form.addEventListener("change", () => { form.dataset.dirty = "true"; });

    // 切換分類時，智慧重排專屬熱門標籤
    const catSelect = form.querySelector('select[name="category_id"]');
    if(catSelect){
      catSelect.addEventListener("change", (e) => {
        const input = $("chat-note-tags-input");
        const curList = input ? input.value.split(/[,，]/).map(s=>s.trim()).filter(Boolean) : [];
        const container = $("chat-note-quick-tags-container");
        if(container){
          container.innerHTML = renderCategoryScopedTagsHtml(e.target.value, curList);
        }
      });
    }
  }
}

function noteRecipientLabel(note){
  const contact = state.contacts.find(r => r.recipient_id === note.recipient_id);
  if(contact) {
    const name = label(contact);
    return name === note.recipient_id ? "未命名聯絡對象" : name;
  }
  return note.recipient_name && note.recipient_name !== note.recipient_id ? note.recipient_name : "未命名聯絡對象";
}

function notePreviewMetadata(note){
  return `<dl class="note-preview-meta">
    <div><dt>關聯對象</dt><dd><button type="button" class="note-recipient-link" data-action="open-chat-from-contact" data-id="${esc(note.recipient_id)}">${esc(noteRecipientLabel(note))}</button></dd></div>
    <div><dt>建立時間</dt><dd>${when(note.created_at)}</dd></div>
    <div><dt>分類</dt><dd>${categoryPillHtml(note.category_name || note.note_type || "未分類")}</dd></div>
    <div><dt>標籤</dt><dd>${(note.tags || []).length ? note.tags.map(tagPillHtml).join(" ") : '<span class="muted">無標籤</span>'}</dd></div>
  </dl>`;
}

function recordReadonly(record,isCase=false){
  return Boolean(record.is_locked || (isCase && record.status==="closed") || state.preview || state.session?.role==="platform_admin");
}
function readonlyIcon(record,isCase=false){
  if(!recordReadonly(record,isCase))return "";
  const reason=record.is_locked?"已上鎖，僅可閱覽":isCase && record.status==="closed"?"已結案，僅可閱覽":"目前視角僅可閱覽";
  return `<span class="record-readonly" title="${reason}" aria-label="${reason}">${icon("lock")}</span>`;
}
function noteLockPolicy(){
  const orgId=state.session?.user?.organization_id;
  const org=(state.organizations||[]).find(o=>o.org_id===orgId);
  return org?.note_lock_policy || state.session?.org_settings?.note_lock_policy || 'disabled';
}
function canToggleNoteLock(record=null){
  const role=state.session?.role, policy=noteLockPolicy();
  if(state.preview || role==='platform_admin')return false;
  if(policy==='strict_admin')return role==='org_admin';
  if(policy==='collaborative' && role==='operator' && record?.is_locked && record.author!==state.session?.identity)return false;
  return policy!=='collaborative' || role!=='collaborator';
}
function recordLockControl(record,isCase=false){
  if(state.preview || state.session?.role==="platform_admin" || (isCase && record.status==="closed"))return readonlyIcon(record,isCase);
  const policy=noteLockPolicy();
  if(policy==="collaborative" && state.session?.role==="collaborator")return readonlyIcon(record,isCase);
  if(policy==="strict_admin" && state.session?.role!=="org_admin")return readonlyIcon(record,isCase);
  if(policy==="collaborative" && record.is_locked && state.session?.role==="operator" && (isCase?record.created_by:record.author)!==state.session?.identity)return readonlyIcon(record,isCase);
  if(!isCase && !canToggleNoteLock(record))return readonlyIcon(record);
  const action=isCase?"record-lock-case":"record-lock-note";
  const label=record.is_locked?"解除鎖定":"鎖定";
  return `<button type="button" class="record-lock-control ${record.is_locked?'locked':''}" data-action="${action}" data-id="${esc(record.case_id||record.note_id)}" data-recipient="${esc(record.recipient_id||record.case_subject_id||'')}" title="${label}" aria-label="${label}" aria-pressed="${Boolean(record.is_locked)}">${icon(record.is_locked?'lock':'unlock')}</button>`;
}

function renderNoteContent(note){
  return renderMarkdown(note.content, {noteId: note.note_id, editable: !note.is_locked && !state.preview && state.session?.role !== "platform_admin"});
}

function noteReadingCopy(content){
  const preserved=[];
  const marker=`COPY${Math.random().toString(36).slice(2)}BLOCK`;
  const preserve=text=>{const token=`${marker}${preserved.length}END`;preserved.push([token,text]);return token;};
  const protectedContent=content.replace(/^```[^\r\n]*\r?\n[\s\S]*?^```[ \t]*$/gm,block=>preserve(block));
  const root=document.createElement('div');
  root.innerHTML=renderMarkdown(protectedContent,{noteId:'copy',editable:false});
  root.querySelectorAll('input[type="checkbox"]').forEach(input=>input.replaceWith(document.createTextNode(input.checked?'☑ ':'☐ ')));
  root.querySelectorAll('li').forEach(li=>{
    const prefix=li.parentElement.tagName==='OL'?`${li.hasAttribute('value')?li.value:Number(li.parentElement.getAttribute('start')||1)+Array.from(li.parentElement.children).indexOf(li)}. `:'• ';
    li.prepend(document.createTextNode(prefix));
  });
  root.querySelectorAll('img').forEach(img=>img.replaceWith(document.createTextNode(img.alt||'')));
  root.querySelectorAll('table').forEach(table=>{
    const csvCell=text=>/[",\r\n]/.test(text)?`"${text.replace(/"/g,'""')}"`:text;
    const csv=Array.from(table.rows).map(row=>Array.from(row.cells).map(cell=>csvCell(cell.textContent.trim())).join(',')).join('\n');
    table.replaceWith(document.createTextNode(`\n${preserve(csv)}\n\n`));
  });
  root.querySelectorAll('p,h2,h3,h4,h5,blockquote,pre,ul,ol,.md-gap').forEach(el=>el.append(document.createTextNode('\n\n')));
  root.querySelectorAll('li,.md-check-item').forEach(el=>el.append(document.createTextNode('\n')));
  root.querySelectorAll('br,hr').forEach(el=>el.replaceWith(document.createTextNode('\n')));
  let text=root.textContent.replace(/\n{3,}/g,'\n\n').trim();
  preserved.forEach(([token,value])=>{text=text.replace(token,()=>value);});
  return text;
}

async function copyNoteText(text){
  if(navigator.clipboard?.writeText){
    try { await navigator.clipboard.writeText(text);notice('記事內容已複製至剪貼簿。');return; } catch (_) {}
  }
  fallbackCopy(text);
}

async function noteCopyOptions(noteId){
  let note=[state.notePreview,...(state.globalNotes||[]),...Array.from(state.chatNotes?.values()||[]).flat()].find(n=>n?.note_id===noteId);
  if(!note) note=(await api(`/api/chat-notes/detail?note_id=${encodeURIComponent(noteId)}`)).note;
  if(!note) throw new Error('找不到記事內容。');
  await recordCopyOptions(note.content||'','記事');
}

async function recordCopyOptions(content,label){
  if(!/(^\s*(?:#{1,6}\s|[-*]\s|\d+[.)]\s|>\s|```|\|)|\*\*|\[[^\]]+\]\()/m.test(content)){
    await copyNoteText(content);return;
  }
  state.noteCopyContent=content;
  modal(`複製${label}內容`,`<p>閱讀版保留 ☐／☑ 與程式碼區塊，表格轉為 CSV；Markdown 原文保留完整語法。</p><div class="form-actions"><button type="button" class="btn primary" data-action="copy-note-version" data-id="reading">${icon('copy')} 閱讀版</button><button type="button" class="btn" data-action="copy-note-version" data-id="markdown">${icon('file')} Markdown 原文</button><button type="button" class="btn" data-action="close-modal">關閉</button></div>`);
}

function renderCaseContent(c){
  return renderMarkdown(c.description, {caseId: c.case_id, editable: !c.is_locked && c.status !== "closed" && !state.preview && state.session?.role !== "platform_admin"});
}

async function chatNoteDetailModal(note_id){
  let note = null;
  if(state.globalNotes){
    note = state.globalNotes.find(n => n.note_id === note_id);
  }
  if(!note && state.chatNotes){
    for(const list of state.chatNotes.values()){
      const found = (list || []).find(n => n.note_id === note_id);
      if(found){ note = found; break; }
    }
  }

  if(!note){
    try {
      const res = await api(`/api/chat-notes/detail?note_id=${encodeURIComponent(note_id)}`);
      note = res.note;
    } catch(_){}
  }

  if(!note){
    notice("找不到該筆記事資料。", true);
    return;
  }

  const isCompleted = note.status === "completed";
  const isLocked = Boolean(note.is_locked);
  const orgLockPolicy = noteLockPolicy();
  const canUnlock = orgLockPolicy === "collaborative" || (orgLockPolicy === "strict_admin" && manager()) || orgLockPolicy === "disabled";
  const canEdit = !isLocked || canUnlock;

  state.notePreview = note;
  const mdHtml = renderNoteContent(note);

  modal("記事預覽", `
    <div class="note-detail-view" style="display:flex;flex-direction:column;gap:14px;">
      <div class="note-detail-header" style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:12px;">
        <div style="min-width:0;flex:1 1 200px;">
          <h3 style="margin:0 0 6px 0;font-size:16px;font-weight:700;color:var(--ink);line-height:1.35;word-break:break-word;">${esc(note.title || "無標題記事")}</h3>
          <div style="font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            ${note.due_date ? `<span>· ${icon("clock")} 期限：<strong style="color:var(--ink);">${esc(note.due_date)}</strong></span>` : ''}
          </div>
        </div>
        <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;flex-shrink:0;">
          ${note.is_pinned ? `<span class="apple-pill" style="background:rgba(234,179,8,.18);color:#b45309;border-color:rgba(234,179,8,.3);">${icon("pin")} 置頂</span>` : ''}
          ${recordLockControl(note)}
          ${isCompleted ? `<span class="apple-pill" style="background:rgba(34,197,94,.18);color:#16a34a;border-color:rgba(34,197,94,.3);">${icon("check")} 已完成</span>` : ''}
        </div>
      </div>

      ${notePreviewMetadata(note)}

      <div class="note-detail-body" style="background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:14px 16px;max-height:420px;overflow-y:auto;">
        <div class="md-preview-area">${mdHtml}</div>
      </div>

      <div class="form-actions" style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;gap:8px;flex-wrap:wrap;">
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="btn small" data-action="copy-chat-note-content" data-id="${esc(note.note_id)}">${icon("copy")} 複製內容</button>
          <button type="button" class="btn small" data-action="convert-note-to-case" data-id="${esc(note.note_id)}" data-recipient="${esc(note.recipient_id)}">${icon("folder")} 轉為案件</button>
          ${!recordReadonly(note) ? `<button type="button" class="btn small" data-action="edit-chat-note" data-id="${esc(note.note_id)}" data-recipient="${esc(note.recipient_id)}">${icon("edit")} 編輯記事</button>` : ''}
        </div>
        ${!recordReadonly(note)?button(icon("trash")+"刪除記事","delete-chat-note","small danger",`data-id="${esc(note.note_id)}" data-recipient="${esc(note.recipient_id)}"`):""}
        <button type="button" class="btn primary small" data-action="close-modal">關閉</button>
      </div>
    </div>
  `);
}

async function manageNotesTaxonomyModal(initialTab = "categories"){
  modal("分類與標籤治理", '<div class="loading-panel"><span class="spinner"></span><p>讀取分類與標籤資料…</p></div>');
  try{
    const [catsRes, tagsRes] = await Promise.all([
      api("/api/chat-notes/categories"),
      api("/api/chat-notes/tags")
    ]);
    state.noteCategories = catsRes.categories || [];
    state.noteTags = tagsRes.tags || [];

    const orphanTagsCount = state.noteTags.filter(t => !t.note_count).length;

    const html = `
      <div class="tax-container">
        <div class="segmented" style="margin-bottom:8px;">
          <button type="button" class="${initialTab==='categories'?'active':''}" data-action="switch-tax-tab" data-tab="categories">${icon("folder")} 記事分類 (${state.noteCategories.length})</button>
          <button type="button" class="${initialTab==='tags'?'active':''}" data-action="switch-tax-tab" data-tab="tags">${icon("tag")} 記事標籤 (${state.noteTags.length})</button>
        </div>

        <!-- 記事分類治理分頁 -->
        <div id="tax-tab-categories" ${initialTab!=='categories'?'hidden':''}>
          <div class="tax-meta-bar">
            <p class="tax-meta-hint">設定對話記事的大項業務分類（如商務、工務、教務），統一團隊規範。</p>
          </div>

          <!-- 內嵌極速建立列 (Apple Inline Creation Bar) -->
          <form id="tax-category-create-form" class="tax-quick-create-bar">
            <span style="color:var(--muted);display:inline-flex;align-items:center;padding-left:4px;">${icon("folder")}</span>
            <input name="name" class="tax-quick-input" required maxlength="20" placeholder="輸入新分類名稱（如：售後服務、簽約保固、工務工程）…" autocomplete="off">
            <button class="btn primary tax-quick-submit" type="submit">${icon("plus")} 新增分類</button>
          </form>

          <!-- 分組列表 (Apple Inset Grouped Table) -->
          <div class="tax-grouped-card">
            <div class="tax-grouped-list">
              ${state.noteCategories.map(c => `
                <div class="tax-item-row">
                  <div class="tax-item-left">
                    <span class="tax-item-category-badge">
                      ${icon("folder")}
                      <span>${esc(c.name)}</span>
                    </span>
                    <span class="tax-item-usage-bubble ${c.note_count?'':'zero'}">${c.note_count ? `${c.note_count} 則引用` : '無引用'}</span>
                    ${c.is_default ? '<span class="apple-pill" style="background:var(--soft);color:var(--muted);font-size:10px;padding:2px 7px;">預設</span>' : ''}
                  </div>
                  <div class="tax-item-actions">
                    <button type="button" class="tax-icon-btn" data-action="edit-category-modal" data-id="${esc(c.category_id)}" data-name="${esc(c.name)}" title="編輯分類名稱">${icon("edit")}</button>
                    <button type="button" class="tax-icon-btn" data-action="merge-category-modal" data-id="${esc(c.category_id)}" data-name="${esc(c.name)}" title="批次合併轉移至其他分類">${icon("layers")}</button>
                    <button type="button" class="tax-icon-btn danger" data-action="delete-category-btn" data-id="${esc(c.category_id)}" data-name="${esc(c.name)}" title="刪除分類">${icon("trash")}</button>
                  </div>
                </div>
              `).join("") || '<div style="padding:28px;text-align:center;color:var(--muted);font-size:13px;">目前尚無分類，請於上方輸入新增。</div>'}
            </div>
          </div>
        </div>

        <!-- 記事標籤治理分頁 -->
        <div id="tax-tab-tags" ${initialTab!=='tags'?'hidden':''}>
          <div class="tax-meta-bar">
            <p class="tax-meta-hint">集中管理記事標籤，避免相同概念標籤氾濫；支援同義詞合併與孤立清理。</p>
            ${orphanTagsCount ? `<button type="button" class="btn small text" data-action="cleanup-orphan-tags-btn" style="color:var(--orange);font-size:12px;padding:2px 8px;">${icon("trash")} 清理 ${orphanTagsCount} 個無引用標籤</button>` : ''}
          </div>

          <!-- 內嵌極速建立列 (Apple Inline Creation Bar) -->
          <form id="tax-tag-create-form" class="tax-quick-create-bar">
            <div style="position:relative;display:inline-flex;align-items:center;">
              <button type="button" id="tag-create-color-btn" class="tax-inline-color-trigger" data-color="#007AFF" style="background-color:#007AFF!important;" data-action="toggle-color-picker" data-target="tag-color-popover" title="選擇代表色"></button>
              <div id="tag-color-popover" class="tax-color-picker" style="position:absolute;top:36px;left:0;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:10px;box-shadow:0 10px 30px rgba(0,0,0,.15);z-index:20;width:190px;" hidden>
                ${APPLE_TAG_COLORS.map(c => `<button type="button" class="tax-color-dot ${c.hex==='#007AFF'?'selected':''}" data-action="select-inline-color" data-color="${c.hex}" data-input="tag-create-color-input" data-trigger="tag-create-color-btn" data-popover="tag-color-popover" style="background-color:${c.hex}!important;" title="${c.name}"></button>`).join("")}
              </div>
              <input type="hidden" name="color" id="tag-create-color-input" value="#007AFF">
            </div>
            <input name="name" class="tax-quick-input" required maxlength="30" placeholder="輸入新標籤（如：VIP客戶、緊急處理、待回電）…" autocomplete="off">
            <button class="btn primary tax-quick-submit" type="submit">${icon("plus")} 新增標籤</button>
          </form>

          <!-- 分組列表 (Apple Inset Grouped Table) -->
          <div class="tax-grouped-card">
            <div class="tax-grouped-list">
              ${state.noteTags.map(t => {
                const color = t.color || '#007AFF';
                const bg = color.length === 7 ? color + "20" : "rgba(0,122,255,0.14)";
                const border = color.length === 7 ? color + "48" : "rgba(0,122,255,0.3)";
                return `
                <div class="tax-item-row">
                  <div class="tax-item-left">
                    <span class="tax-item-tag-preview apple-pill" data-color="${esc(color)}" style="background-color:${esc(bg)}!important;color:${esc(color)}!important;border-color:${esc(border)}!important;">
                      ${esc(t.name)}
                    </span>
                    <span class="tax-item-usage-bubble ${t.note_count?'':'zero'}">${t.note_count ? `${t.note_count} 則引用` : '無引用'}</span>
                    ${t.is_default ? '<span class="apple-pill" style="background:var(--soft);color:var(--muted);font-size:10px;padding:2px 7px;">預設</span>' : ''}
                  </div>
                  <div class="tax-item-actions">
                    <button type="button" class="tax-icon-btn" data-action="edit-tag-modal" data-id="${esc(t.tag_id)}" data-name="${esc(t.name)}" data-color="${esc(color)}" title="編輯標籤名稱與代表色">${icon("edit")}</button>
                    <button type="button" class="tax-icon-btn" data-action="merge-tag-modal" data-id="${esc(t.tag_id)}" data-name="${esc(t.name)}" title="合併至其他同義標籤">${icon("layers")}</button>
                    <button type="button" class="tax-icon-btn danger" data-action="delete-note-tag-btn" data-id="${esc(t.tag_id)}" data-name="${esc(t.name)}" title="刪除標籤">${icon("trash")}</button>
                  </div>
                </div>`;
              }).join("") || '<div style="padding:28px;text-align:center;color:var(--muted);font-size:13px;">目前尚無標籤，請於上方輸入新增。</div>'}
            </div>
          </div>
        </div>
      </div>
    `;
    modal("分類與標籤治理", html);
  }catch(e){
    modal("載入失敗", `<p class="callout warn">${esc(e.message)}</p>`);
  }
}

async function loadGlobalChatNotes(){
  const query = state.noteHubQuery || "";
  const cat = state.noteHubCategory || "";
  const tag = state.noteHubTag || "";
  const status = state.noteHubStatus || "all";
  const channel = state.noteHubChannel || "";

  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (cat) params.set("category_id", cat);
  if (tag) params.set("tag", tag);
  if (status !== "all") params.set("status", status);
  if (channel) params.set("channel_id", channel);

  try{
    const res = await api(`/api/chat-notes/global?${params.toString()}`);
    state.globalNotes = res.notes || [];
    state.globalNotesStats = res.stats || { total: 0, pinned: 0, locked: 0, completed: 0 };
    state.globalNotesCategories = res.categories || [];
    state.globalNotesTags = res.tags || [];
    if (state.view === "chat-notes") {
      const container = $("global-notes-content");
      if (container) container.innerHTML = renderGlobalNotesBody();
      if($("notes-hub-browse"))$("notes-hub-browse").innerHTML=notesHubBrowse();
      if ($("nav-note-count")) $("nav-note-count").textContent = state.globalNotesStats.total || "0";
    }
  }catch(e){
    console.error("Failed to load global chat notes:", e);
  }
}

function renderGlobalNotesBody(){
  const notes = [...(state.globalNotes || [])].sort((a,b)=>Number(Boolean(b.is_pinned))-Number(Boolean(a.is_pinned)) || (state.noteHubSort==="oldest"?1:-1)*String(a.created_at||"").localeCompare(String(b.created_at||"")));
  if(!notes.length){
    return empty("查無符合的對話記事", "請確認搜尋關鍵字或調整分類、標籤與狀態篩選條件。");
  }

  const orgLockPolicy = noteLockPolicy();

  if(state.noteHubViewMode === "table"){
    return `
      <div class="table-scroll" style="background:var(--surface);border-radius:14px;border:1px solid var(--line);">
        <table class="contacts-table">
          <thead>
            <tr>
              <th style="width:40px;">置頂</th>
              <th>記事標題與內容</th>
              <th>分類與標籤</th>
              <th>對話對象 / OA</th>
              <th>建立時間</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
            ${notes.map(n => {
              const isLocked = Boolean(n.is_locked);
              const isCompleted = n.status === "completed";
              const canUnlock = orgLockPolicy === "collaborative" || (orgLockPolicy === "strict_admin" && manager()) || orgLockPolicy === "disabled";
              const canEdit = !isLocked || canUnlock;

              return `
              <tr class="${n.is_pinned?'pinned':''} ${isLocked?'locked':''} ${isCompleted?'completed':''}">
                <td>
                  ${n.is_pinned ? `<span style="color:#b45309;" title="置頂">${icon("pin")}</span>` : ''}
                  ${recordLockControl(n)}
                </td>
                <td style="max-width:320px;">
                  <strong style="display:block;margin-bottom:3px;">${esc(n.title || "記事")}</strong>
                  <div class="chat-note-content" id="chat-note-content-${esc(n.note_id)}" style="font-size:12.5px;color:var(--muted);max-height:48px;overflow:hidden;text-overflow:ellipsis;">${esc(n.content)}</div>
                </td>
                <td>
                  ${n.category_name ? categoryPillHtml(n.category_name) : ''}
                  <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">
                    ${(n.tags||[]).map(t => tagPillHtml(t)).join("")}
                  </div>
                </td>
                <td>
                  <button type="button" class="btn text small" data-action="open-chat-from-contact" data-id="${esc(n.recipient_id)}" style="padding:0;font-size:12px;text-align:left;">
                    <strong>${esc(noteRecipientLabel(n))}</strong>
                    <small class="muted" style="display:block;">${esc(n.channel_name || "")}</small>
                  </button>
                </td>
                <td style="font-size:12px;color:var(--muted);white-space:nowrap;">
                  ${when(n.created_at)}
                  <small style="display:block;">${esc(n.author||"")}</small>
                </td>
                <td style="text-align:right;white-space:nowrap;">
                  <button type="button" class="btn text small" data-action="copy-chat-note-content" data-id="${esc(n.note_id)}" title="一鍵複製內容">${icon("copy")}</button>
                  <button type="button" class="btn text small" data-action="toggle-chat-note-complete" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${isCompleted?'標記未完成':'標記完成'}">${icon(isCompleted?"refresh":"check")}</button>
                  <button type="button" class="btn text small" data-action="toggle-chat-note-pin" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${n.is_pinned?'取消置頂':'置頂'}">${icon(n.is_pinned?"unpin":"pin")}</button>
                  ${canToggleNoteLock(n) ? `<button type="button" class="btn text small" data-action="toggle-chat-note-lock" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-label="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-pressed="${isLocked}">${isLocked?icon("unlock"):icon("lock")}</button>` : ''}
                  ${canEdit && !isLocked ? `<button type="button" class="btn text small" data-action="edit-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="編輯">${icon("edit")}</button>` : ''}
                  <button type="button" class="btn text small" data-action="convert-note-to-case" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="轉為案件">${icon("folder")}</button>
                  ${canEdit && !isLocked ? `<button type="button" class="btn text small danger" data-action="delete-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="刪除">${icon("trash")}</button>` : ''}
                </td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  return `
    <div class="notes-hub-grid">
      ${notes.map(n => {
        const isLocked = Boolean(n.is_locked);
        const isCompleted = n.status === "completed";
        const canUnlock = orgLockPolicy === "collaborative" || (orgLockPolicy === "strict_admin" && manager()) || orgLockPolicy === "disabled";
        const canEdit = !isLocked || canUnlock;

        const isLongContent = Boolean(n.content && (n.content.length > 180 || (n.content.match(/\n/g) || []).length >= 4));
        return `
        <div class="notes-hub-card ${n.is_pinned?'pinned':''} ${isLocked?'locked':''} ${isCompleted?'completed':''}" data-id="${esc(n.note_id)}">
          <div class="notes-hub-card-header">
            <div>
              <h4 class="notes-hub-card-title">${esc(n.title || "記事")}</h4>
            </div>
            <div class="notes-hub-card-badges">
              ${n.is_pinned ? `<span class="apple-pill" style="background:rgba(234,179,8,.18);color:#b45309;border-color:rgba(234,179,8,.3);">${icon("pin")} 置頂</span>` : ''}
              ${recordLockControl(n)}
              ${isCompleted ? `<span class="apple-pill" style="background:rgba(34,197,94,.18);color:#16a34a;border-color:rgba(34,197,94,.3);">${icon("check")} 已完成</span>` : ''}
            </div>
          </div>
          <div class="notes-card-meta">${icon("users")}<span>${esc(noteRecipientLabel(n))}</span>${icon("calendar")}<time>${esc(sidebarRecordDate(n.created_at))}</time></div><div class="notes-card-tags">${categoryPillHtml(n.category_name)}${(n.tags||[]).map(tagPillHtml).join('')}</div>
          <div class="chat-note-content-wrapper">
            <div class="notes-hub-card-body ${isLongContent ? 'collapsed' : ''}" id="chat-note-content-${esc(n.note_id)}">${renderNoteContent(n)}</div>
            ${isLongContent ? `<button type="button" class="chat-note-expand-btn" data-action="toggle-chat-note-expand" data-id="${esc(n.note_id)}">${icon("chevron-down")} 展開全文</button>` : ''}
          </div>
          <div class="notes-hub-card-footer">
            <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">
              ${n.due_date ? `<span class="muted" style="display:inline-flex;align-items:center;gap:3px;font-size:11px;">${icon("clock")} 期限：${esc(n.due_date)}</span>` : ''}
              ${n.linked_case_id ? `<span class="apple-pill" style="background:rgba(88,86,214,.12);color:#5856D6;cursor:pointer;" data-action="open-case-detail" data-id="${esc(n.linked_case_id)}">${icon("folder")} 關聯案件</span>` : ''}
            </div>
            <div class="notes-hub-card-actions">
              <button type="button" class="btn text small" data-action="open-note-detail" data-id="${esc(n.note_id)}" title="查看完整記事詳情">${icon("eye")}</button>
              <button type="button" class="btn text small" data-action="copy-chat-note-content" data-id="${esc(n.note_id)}" title="一鍵複製內容">${icon("copy")}</button>
              <button type="button" class="btn text small" data-action="toggle-chat-note-complete" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${isCompleted?'標記未完成':'標記完成'}">${icon(isCompleted?"refresh":"check")}</button>
              <button type="button" class="btn text small" data-action="toggle-chat-note-pin" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${n.is_pinned?'取消置頂':'置頂'}">${icon(n.is_pinned?"unpin":"pin")}</button>
              ${canToggleNoteLock(n) ? `<button type="button" class="btn text small" data-action="toggle-chat-note-lock" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-label="${isLocked?'解除鎖定':'鎖定防誤改'}" aria-pressed="${isLocked}">${isLocked?icon("unlock"):icon("lock")}</button>` : ''}
              ${canEdit && !isLocked ? `<button type="button" class="btn text small" data-action="edit-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="編輯">${icon("edit")}</button>` : ''}
              <button type="button" class="btn text small" data-action="convert-note-to-case" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="轉為案件">${icon("folder")}</button>
              ${canEdit && !isLocked ? `<button type="button" class="btn text small danger" data-action="delete-chat-note" data-id="${esc(n.note_id)}" data-recipient="${esc(n.recipient_id)}" title="刪除">${icon("trash")}</button>` : ''}
            </div>
          </div>
        </div>`;
      }).join("")}
    </div>
  `;
}

function notesHubBrowse(){
  const stats=state.globalNotesStats||{total:0,pinned:0,completed:0};
  return `<div class="notes-browse-bar"><div class="notes-status-tabs" role="group" aria-label="記事狀態">${[['all','全部',stats.total],['active','待追蹤',Math.max(0,stats.total-stats.completed)],['completed','已完成',stats.completed],['pinned','已釘選',stats.pinned]].map(([id,title,count])=>`<button type="button" data-action="notes-status-tab" data-id="${id}" aria-pressed="${(state.noteHubStatus||'all')===id}" class="${(state.noteHubStatus||'all')===id?'active':''}">${title} (${count})</button>`).join('')}</div><select id="notes-hub-sort" aria-label="記事排序"><option value="newest" ${state.noteHubSort!=='oldest'?'selected':''}>建立時間（新→舊）</option><option value="oldest" ${state.noteHubSort==='oldest'?'selected':''}>建立時間（舊→新）</option></select></div>`;
}
function chatNotesPage(){
  if (!state.globalNotesLoaded) {
    state.globalNotesLoaded = true;
    state.noteHubViewMode = state.noteHubViewMode || "grid";
    loadGlobalChatNotes();
  }
  const stats = state.globalNotesStats || { total: 0, pinned: 0, locked: 0, completed: 0 };
  const canManageTax = manager();

  return heading("對話記事本", "跨 OA 集中查閱、搜尋、治理與追蹤所有對話重要記事與待辦事項", `
    <div class="segmented icon-segmented" role="group" aria-label="檢視模式">
      <button type="button" class="${state.noteHubViewMode==='grid'?'active':''}" data-action="toggle-notes-view-mode" data-id="grid" title="切換為卡片模式">${icon("grid")}</button>
      <button type="button" class="${state.noteHubViewMode==='table'?'active':''}" data-action="toggle-notes-view-mode" data-id="table" title="切換為列表模式">${icon("menu")}</button>
    </div>
    <button type="button" class="btn small" data-action="export-chat-notes-modal">${icon("download")} 匯出記事</button>
    ${canManageTax ? `<button type="button" class="btn small" data-action="manage-notes-taxonomy">${icon("tag")} 分類與標籤治理</button>` : ''}
  `) + `
  <div class="notes-hub-stats">
    ${stat("全部記事", stats.total, "則", "所有已記錄的對話記事", "file")}
    ${stat("重要置頂", stats.pinned, "則", "置頂於對話頂端", "pin")}
    ${stat("待追蹤", Math.max(0,stats.total-stats.completed), "則", "需要後續跟進的記事", "clock")}
    ${stat("處理完畢", stats.completed, "則", "已標記完成事項", "check")}
  </div>

  <div class="notes-hub-toolbar">
    <div class="notes-hub-toolbar-row">
      <div class="search-field" style="flex:2;min-width:240px;">
        ${icon("search")}
        <input type="search" id="notes-hub-search" value="${esc(state.noteHubQuery||'')}" placeholder="搜尋記事標題、內容或對話對象…">
      </div>
      ${(state.channels||[]).length > 1 ? `
        <select id="notes-hub-channel-filter" style="flex:1;min-width:160px;">
          <option value="">全部 LINE OA</option>
          ${(state.channels||[]).map(c => `<option value="${esc(c.channel_id)}" ${state.noteHubChannel===c.channel_id?'selected':''}>${esc(c.name)}</option>`).join("")}
        </select>
      ` : ''}
      <select id="notes-hub-category-filter" style="flex:1;min-width:140px;">
        <option value="">全部分類</option>
        ${(state.globalNotesCategories||[]).map(c => `<option value="${esc(c.category_id)}" ${state.noteHubCategory===c.category_id?'selected':''}>${esc(c.name)} (${c.note_count||0})</option>`).join("")}
      </select>
      <select id="notes-hub-tag-filter" style="flex:1;min-width:140px;">
        <option value="">全部標籤</option>
        ${(state.globalNotesTags||[]).map(t => `<option value="${esc(t.name)}" ${state.noteHubTag===t.name?'selected':''}>${esc(t.name)} (${t.note_count||0})</option>`).join("")}
      </select>
      <select id="notes-hub-status-filter" style="flex:1;min-width:130px;">
        <option value="all" ${state.noteHubStatus==='all'?'selected':''}>全部狀態</option>
        <option value="active" ${state.noteHubStatus==='active'?'selected':''}>進行中</option>
        <option value="completed" ${state.noteHubStatus==='completed'?'selected':''}>已完成</option>
        <option value="pinned" ${state.noteHubStatus==='pinned'?'selected':''}>已置頂</option>
        <option value="locked" ${state.noteHubStatus==='locked'?'selected':''}>已鎖定</option>
      </select>
    </div>
  </div>

  <div id="notes-hub-browse">${notesHubBrowse()}</div>
  <div id="global-notes-content">
    ${renderGlobalNotesBody()}
  </div>
  `;
}

function exportChatNotesModal(){
  const query = state.noteHubQuery || "";
  const cat = state.noteHubCategory || "";
  const tag = state.noteHubTag || "";
  const status = state.noteHubStatus || "all";
  const channel = state.noteHubChannel || "";

  const q = new URLSearchParams();
  if (query) q.set("query", query);
  if (cat) q.set("category_id", cat);
  if (tag) q.set("tag", tag);
  if (status !== "all") q.set("status", status);
  if (channel) q.set("channel_id", channel);

  modal("匯出對話記事本", `
    <div>
      <p class="muted" style="margin-bottom:16px;">依據目前的篩選條件匯出對話記事資料，支援 CSV (Excel 格式含 UTF-8 BOM)、Markdown 文件與 JSON 格式：</p>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <a href="/api/chat-notes/export?${q.toString()}&format=csv" download class="btn primary" style="display:flex;align-items:center;gap:8px;">
          ${icon("download")} 下載試算表格式 (.csv)
        </a>
        <a href="/api/chat-notes/export?${q.toString()}&format=markdown" download class="btn" style="display:flex;align-items:center;gap:8px;">
          ${icon("file")} 下載 Markdown 文件 (.md)
        </a>
        <a href="/api/chat-notes/export?${q.toString()}&format=json" download class="btn" style="display:flex;align-items:center;gap:8px;">
          ${icon("file")} 下載 JSON 資料檔 (.json)
        </a>
      </div>
    </div>
  `);
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

    const html = `<div class="tmpl-grid">
      ${groups.map(g => (g.templates || []).map(t => {
        const title = t.rendered_title || t.title || "";
        const body = t.rendered_body || t.body || "";
        const cat = t.category_name || "一般備忘";
        const pri = t.defaults?.priority || "medium";
        const tags = (t.defaults?.tags || []).join(", ");
        const isNote = target_type === "note";

        return `
          <div class="tmpl-card">
            <div class="tmpl-card-head">
              <div class="tmpl-card-title-row">
                <span class="tmpl-type-tag ${isNote?'note':'case'}">${isNote?icon("note_icon"):icon("case_icon")} ${isNote?'記事範本':'案件範本'}</span>
                <h4 class="tmpl-card-title">${esc(t.name || t.title)}</h4>
              </div>
            </div>
            <p class="tmpl-card-desc">${esc(body || title || "無詳細內容")}</p>
            <div class="tmpl-card-meta">
              <span class="badge" style="font-size:11px;">${icon("folder")} ${esc(cat)}</span>
              <small class="muted" style="font-size:11px;">群組：${esc(g.pack_name)}</small>
            </div>
            <div class="tmpl-card-foot">
              <div></div>
              <button type="button" class="btn small primary" ${isNote ? `data-action="apply-note-template" data-recipient="${esc(subject_id)}" data-title="${esc(title)}" data-body="${esc(body)}" data-cat="${esc(cat)}" data-tags="${esc(tags)}"` : `data-action="apply-case-template" data-subject="${esc(subject_id)}" data-title="${esc(title)}" data-desc="${esc(body)}" data-cat="${esc(cat)}" data-pri="${esc(pri)}"`}>${icon("check")} 套用此範本</button>
            </div>
          </div>
        `;
      }).join("")).join("")}
    </div>`;
    modal(target_type === "note" ? "選擇記事範本帶入" : "選擇案件範本帶入", html);
  }catch(e){
    modal("載入失敗", `<p class="callout warn">${icon("alert")} ${esc(e.message)}</p>`);
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

let templatesTab = "home";
let templatesSubFilter = "all";
let templatesSearchQuery = "";
let selectedPackKey = "universal";
let lastDeletedTemplate = null;
let selectedTemplateItems = new Map();

function parseMdInline(str){
  if(!str) return "";
  let s = esc(str);
  // Inline code: `code`
  s = s.replace(/`([^`\n]+)`/g, '<code class="md-inline-code">$1</code>');
  // Bold: **text** or __text__
  s = s.replace(/\*\*([^\*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
  // Italic: *text* or _text_
  s = s.replace(/(?<!\*)\*([^\*\n\s](?:[^\*\n]*?[^\*\n\s])?)\*(?!\*)/g, '<em>$1</em>');
  s = s.replace(/(?<!_)_([^_\n\s](?:[^_\n]*?[^_\n\s])?)_(?!_)/g, '<em>$1</em>');
  // Strikethrough: ~~text~~ or -text-
  s = s.replace(/~~([^~\n]+)~~/g, '<s>$1</s>');
  s = s.replace(/(?<=\s|^)-([^\-\n\s](?:[^\-\n]*?[^\-\n\s])?)-(?=\s|$)/g, '<s>$1</s>');
  // Links: [text](url)
  s = s.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/)[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>');
  return s;
}

function renderMarkdown(md, taskOptions = null){
  if(!md || !md.trim()) return '<span class="muted">（無內容）</span>';

  // 1. Extract fenced code blocks
  const codeBlocks = [];
  let processed = md.replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (match, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre class="md-code-block"><code>${esc(code.trimEnd())}</code></pre>`);
    return `@@MD_CODE_BLOCK_${idx}@@`;
  });

  const lines = processed.split(/\r?\n/);
  const out = [];
  let currentList = null; // 'ul' | 'ol'
  let taskIndex = 0;

  function closeList(){
    if(currentList === 'ul'){
      out.push('</ul>');
      currentList = null;
    } else if(currentList === 'ol'){
      out.push('</ol>');
      currentList = null;
    }
  }

  function tableCells(line){
    return line.trim().replace(/^\|/,'').replace(/(?<!\\)\|$/,'').split(/(?<!\\)\|/).map(cell=>cell.trim().replace(/\\\|/g,'|'));
  }

  for(let i = 0; i < lines.length; i++){
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Check code block placeholder
    const codeMatch = trimmed.match(/^@@MD_CODE_BLOCK_(\d+)@@$/);
    if(codeMatch){
      closeList();
      const idx = parseInt(codeMatch[1], 10);
      out.push(codeBlocks[idx] || '');
      continue;
    }

    if(!trimmed){
      closeList();
      if(out.length > 0 && !out[out.length - 1].includes('class="md-gap"')){
        out.push('<div class="md-gap"></div>');
      }
      continue;
    }

    // Pipe tables: render header, alignment and body instead of raw Markdown.
    if(trimmed.includes('|') && i+1<lines.length){
      const heads=tableCells(trimmed), separators=tableCells(lines[i+1]);
      if(heads.length===separators.length && separators.every(cell=>/^:?-{3,}:?$/.test(cell))){
        closeList();
        const alignment=separators.map(cell=>cell.startsWith(':')&&cell.endsWith(':')?'center':cell.endsWith(':')?'right':'left');
        const cells=(row,tag)=>heads.map((_,idx)=>`<${tag} class="md-align-${alignment[idx]}">${parseMdInline(row[idx]||'')}</${tag}>`).join('');
        out.push(`<div class="md-table-scroll"><table class="md-table"><thead><tr>${cells(heads,'th')}</tr></thead><tbody>`);
        i+=2;
        while(i<lines.length && lines[i].trim() && lines[i].includes('|')){
          out.push(`<tr>${cells(tableCells(lines[i]),'td')}</tr>`);i++;
        }
        i--;
        out.push('</tbody></table></div>');continue;
      }
    }

    // Horizontal Rule: ---, ***, ___
    if(/^(\-{3,}|\*{3,}|_{3,})$/.test(trimmed)){
      closeList();
      out.push('<hr class="md-hr">');
      continue;
    }

    // Headers: #, ##, ###, ####, #####, ###### (supports with or without space after hashes)
    const headerMatch = trimmed.match(/^(#{1,6})\s*(.+)$/);
    if(headerMatch){
      closeList();
      const level = Math.min(headerMatch[1].length + 1, 5); // # -> h2, ## -> h3, ### -> h4, etc.
      const headingText = parseMdInline(headerMatch[2]);
      out.push(`<h${level} class="md-h${level}">${headingText}</h${level}>`);
      continue;
    }

    // Blockquote: > text
    const quoteMatch = trimmed.match(/^>\s*(.*)$/);
    if(quoteMatch){
      closeList();
      out.push(`<blockquote class="md-quote">${parseMdInline(quoteMatch[1])}</blockquote>`);
      continue;
    }

    // Checklist / Task items: - [ ] or - [x] or * [ ] or * [x]
    const checkMatch = trimmed.match(/^[\*\-]\s+\[([ xX])\]\s*(.*)$/);
    if(checkMatch){
      closeList();
      const isDone = checkMatch[1].toLowerCase() === 'x';
      const itemContent = parseMdInline(checkMatch[2]);
      if(taskOptions){
        const taskAttrs = taskOptions.caseId ? `data-case-task="${taskIndex}" data-case-id="${esc(taskOptions.caseId)}"` : `data-note-task="${taskIndex}" data-note-id="${esc(taskOptions.noteId)}"`;
        out.push(`<label class="md-check-item ${isDone ? 'done' : ''}"><input type="checkbox" ${taskAttrs} ${isDone ? 'checked' : ''} ${taskOptions.editable ? '' : 'disabled'} aria-label="${esc(checkMatch[2] || '待辦項目')}"><span>${itemContent}</span></label>`);
      } else if(isDone){
        out.push(`<div class="md-check-item done"><span class="md-checkbox done">✓</span> <s>${itemContent}</s></div>`);
      } else {
        out.push(`<div class="md-check-item"><span class="md-checkbox">○</span> ${itemContent}</div>`);
      }
      taskIndex++;
      continue;
    }

    // Unordered List: - item or * item
    const ulMatch = trimmed.match(/^[\*\-]\s+(.+)$/);
    if(ulMatch){
      if(currentList === 'ol') closeList();
      if(!currentList){
        out.push('<ul class="md-ul">');
        currentList = 'ul';
      }
      out.push(`<li class="md-li">${parseMdInline(ulMatch[1])}</li>`);
      continue;
    }

    // Ordered List: 1. item or 1) item
    const olMatch = trimmed.match(/^(\d+)[\.\)]\s+(.+)$/);
    if(olMatch){
      if(currentList === 'ul') closeList();
      if(!currentList){
        out.push(`<ol class="md-ol" start="${Number(olMatch[1])}">`);
        currentList = 'ol';
      }
      out.push(`<li class="md-oli" value="${Number(olMatch[1])}">${parseMdInline(olMatch[2])}</li>`);
      continue;
    }

    // Regular paragraph line
    closeList();
    out.push(`<p class="md-p">${parseMdInline(trimmed)}</p>`);
  }

  closeList();

  return `<div class="md-rendered-content">${out.join("")}</div>`;
}

function getPreferredEditorFormat(){
  return localStorage.getItem("preferred_editor_format") || "plain";
}

function setPreferredEditorFormat(fmt){
  const f = fmt === "markdown" ? "markdown" : "plain";
  localStorage.setItem("preferred_editor_format", f);
  return f;
}

function renderDualFormatEditor(fieldName, fieldId, value = "", format = null, labelText = "內容骨架 / 檢查清單", rows = 6, placeholder = "", isRequired = false, existing = false){
  let chosenFormat = format;
  if(!chosenFormat){
    if(value && (/^\s*(?:#{1,6}\s|[-*]\s|\d+[.)]\s|>\s|\|)|\*\*|```/m.test(value))){
      chosenFormat = "markdown";
    } else {
      chosenFormat = getPreferredEditorFormat();
    }
  }
  const isMd = chosenFormat === "markdown";
  const previewFirst = existing && isMd && Boolean(value.trim());
  const defaultPlaceholder = isMd
    ? '支援 Markdown 語法，例如：\n### 1. 狀況確認\n- [ ] 詢問設備型號與故障現象\n- [ ] 拍照存證\n\n### 2. 處置措施\n* **優先等級**：重要處理\n* **備註**：安排工程窗口'
    : '填寫標準內容流程或檢查清單...';
  const finalPlaceholder = placeholder || defaultPlaceholder;
  return `
    <div class="full tmpl-editor-container" data-field="${esc(fieldId)}" data-format="${isMd?'markdown':'plain'}" data-subtab="${previewFirst?'preview':'write'}">
      <div class="tmpl-editor-header">
        <label for="${esc(fieldId)}" class="tmpl-editor-label">${esc(labelText)}</label>
        <div class="tmpl-editor-controls">
          <div class="tmpl-format-pill-group" role="group" aria-label="格式選擇">
            <button type="button" class="tmpl-pill-btn ${!isMd?'active':''}" data-action="set-editor-format" data-target="${esc(fieldId)}" data-format="plain">純文字</button>
            <button type="button" class="tmpl-pill-btn ${isMd?'active':''}" data-action="set-editor-format" data-target="${esc(fieldId)}" data-format="markdown">Markdown</button>
          </div>

          <div class="tmpl-md-subtabs" role="group" aria-label="編輯模式切換">
            <button type="button" class="tmpl-subtab-btn ${previewFirst?'':'active'}" data-action="set-md-subtab" data-target="${esc(fieldId)}" data-tab="write">✍️ 編輯</button>
            <button type="button" class="tmpl-subtab-btn ${previewFirst?'active':''}" data-action="set-md-subtab" data-target="${esc(fieldId)}" data-tab="preview">👁️ 預覽</button>
          </div>
        </div>
      </div>

      <div class="tmpl-editor-write-box">
        <textarea id="${esc(fieldId)}" name="${esc(fieldName)}" rows="${rows}" ${isRequired ? 'required minlength="1"' : ''} maxlength="2000" placeholder="${esc(finalPlaceholder)}">${esc(value)}</textarea>
        <small class="muted tmpl-md-hint">💡 支援標題 (###)、檢查清單 (- [ ])、條列 (-)、粗體 (**文字**)、引用 (>)、程式碼區塊等 Markdown 語法</small>
      </div>

      <div class="tmpl-editor-preview-box md-preview-area">${previewFirst?renderMarkdown(value):''}</div>
    </div>
  `;
}

function showUndoToast(msg, onUndo){
  const existing = document.querySelector(".tmpl-undo-toast");
  if(existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "tmpl-undo-toast";
  toast.dataset.corner=personalSettings().corner;
  toast.setAttribute('role','status');
  toast.innerHTML = `<span>${esc(msg)}</span><button type="button" class="tmpl-undo-btn">${icon("undo")} 復原</button><button type="button" class="toast-close" aria-label="關閉通知">${icon('close')}</button>`;
  toast.querySelector('.toast-close').onclick=()=>toast.remove();
  toast.querySelector(".tmpl-undo-btn").addEventListener("click", async () => {
    toast.remove();
    if(typeof onUndo === "function") await onUndo();
  });
  document.body.appendChild(toast);
  const seconds=personalSettings().duration;
  if(seconds)setTimeout(() => { if(toast.parentNode) toast.remove(); }, seconds*1000);
}

function templatesAndCategoriesPage(){
  return `
    <div class="tmpl-mgmt-wrap">
      ${heading("範本與分類", "建立常用內容與標準流程，之後處理對話與案件時可一鍵快速套用。", `<div class="tmpl-heading-btns"><button class="btn primary small" data-action="open-template-wizard">${icon("plus")} 建立新範本</button>${manager()?`<button class="btn text small" data-action="templates-switch-tab" data-tab="packs">${icon("settings")} 進階群組</button>`:''}</div>`, "TEMPLATES & CATEGORIES")}

      <div class="tmpl-search-bar">
        ${icon("search")}
        <input type="search" id="templates-search-input" value="${esc(templatesSearchQuery)}" placeholder="搜尋範本名稱、內容大綱或標籤關鍵字（例如：報修、客訴、報價、教務）…" autocomplete="off">
      </div>

      <div class="segmented toolbar tmpl-main-nav">
        <button type="button" class="${templatesTab==='home'?'active':''}" data-action="templates-switch-tab" data-tab="home">${icon("sparkles")} 首頁推薦</button>
        <button type="button" class="${templatesTab==='my_templates'?'active':''}" data-action="templates-switch-tab" data-tab="my_templates">${icon("file")} 我的範本庫</button>
        <button type="button" class="${templatesTab==='taxonomy'?'active':''}" data-action="templates-switch-tab" data-tab="taxonomy">${icon("tag")} 分類與標籤</button>
        ${manager()?`<button type="button" class="${templatesTab==='packs'?'active':''}" data-action="templates-switch-tab" data-tab="packs">${icon("layers")} 範本群組 (進階)</button>`:''}
      </div>

      <div id="templates-tab-content">
        <div class="loading-panel"><span class="spinner"></span><p>讀取範本與分類資料…</p></div>
      </div>
    </div>
  `;
}

async function loadTemplatesTabContent(){
  const wrap = $("templates-tab-content");
  if(!wrap) return;

  try {
    const [packsRes, catRes, tagsRes] = await Promise.all([
      api('/api/template-packs'),
      api('/api/categories'),
      api('/api/chat-notes/tags')
    ]);

    const packs = packsRes.packs || [];
    const caseCats = catRes.case_categories || [];
    const noteCats = catRes.note_categories || [];
    const noteTags = tagsRes.tags || [];

    // 整合所有已啟用或自訂範本
    let allTemplates = [];
    packs.forEach(p => {
      (p.case_templates || []).forEach(t => {
        allTemplates.push({ ...t, type: 'case', pack_name: p.name, pack_id: p.pack_id || p.key, is_preset: p.is_preset });
      });
      (p.note_templates || []).forEach(t => {
        allTemplates.push({ ...t, type: 'note', pack_name: p.name, pack_id: p.pack_id || p.key, is_preset: p.is_preset });
      });
    });

    const q = templatesSearchQuery.toLowerCase();
    let filtered = allTemplates;
    if(q){
      filtered = allTemplates.filter(t =>
        (t.name||"").toLowerCase().includes(q) ||
        (t.title||"").toLowerCase().includes(q) ||
        (t.body||"").toLowerCase().includes(q) ||
        (t.category_name||"").toLowerCase().includes(q) ||
        (t.pack_name||"").toLowerCase().includes(q)
      );
    }

    if(templatesTab === "home"){
      wrap.innerHTML = `
        <!-- 你想做什麼？兩大任務卡 -->
        <div class="tmpl-task-grid">
          <button type="button" class="tmpl-task-btn" data-action="open-template-wizard">
            <div class="tmpl-task-icon-wrap">${icon("plus")}</div>
            <div class="tmpl-task-info">
              <strong>建立新範本</strong>
              <small>引導式 3 步建立案件或記事標準流程，之後一鍵帶入</small>
            </div>
          </button>

          <button type="button" class="tmpl-task-btn" data-action="templates-switch-tab" data-tab="taxonomy">
            <div class="tmpl-task-icon-wrap green">${icon("tag")}</div>
            <div class="tmpl-task-info">
              <strong>管理分類與標籤</strong>
              <small>設定單選業務類別與 Apple HIG 色彩標籤庫</small>
            </div>
          </button>
        </div>

        <!-- 常用推薦範本清單 -->
        <div class="tmpl-section-header">
          <h3 class="tmpl-section-title">
            ${icon("sparkles")} 常用推薦範本 (${filtered.length})
          </h3>
          <div style="display:flex;gap:8px;align-items:center;">
            ${manager() && selectedTemplateItems.size > 0 ? `
              <button type="button" class="btn text small danger" data-action="batch-delete-templates">${icon("trash")} 批次刪除 (${selectedTemplateItems.size})</button>
              <button type="button" class="btn text small" data-action="clear-selected-templates">取消選取</button>
            ` : ''}
            <button type="button" class="btn text small" data-action="templates-switch-tab" data-tab="my_templates">查看全部範本 ➔</button>
          </div>
        </div>

        ${filtered.length ? `
          <div class="tmpl-grid">
            ${filtered.slice(0, 6).map(t => renderTmplCard(t)).join("")}
          </div>
        ` : `
          <div class="panel tmpl-empty-box">
            <p class="muted">找不到符合「${esc(templatesSearchQuery)}」的範本。</p>
            <button type="button" class="btn primary small" data-action="open-template-wizard">${icon("plus")} 立即建立此範本</button>
          </div>
        `}
      `;
    } else if(templatesTab === "my_templates"){
      let typeFiltered = filtered;
      if(templatesSubFilter === "case") typeFiltered = filtered.filter(t => t.type === 'case');
      if(templatesSubFilter === "note") typeFiltered = filtered.filter(t => t.type === 'note');
      const isAllSelected = typeFiltered.length > 0 && typeFiltered.every(t => selectedTemplateItems.has(t.template_id));

      wrap.innerHTML = `
        <div class="tmpl-toolbar-row">
          <div class="segmented tmpl-segmented-sm">
            <button type="button" class="${templatesSubFilter==='all'?'active':''}" data-action="templates-subfilter" data-id="all">全部範本 (${filtered.length})</button>
            <button type="button" class="${templatesSubFilter==='case'?'active':''}" data-action="templates-subfilter" data-id="case">${icon("case_icon")} 案件範本 (${filtered.filter(t=>t.type==='case').length})</button>
            <button type="button" class="${templatesSubFilter==='note'?'active':''}" data-action="templates-subfilter" data-id="note">${icon("note_icon")} 記事範本 (${filtered.filter(t=>t.type==='note').length})</button>
          </div>
          <div class="tmpl-toolbar-right-btns">
            ${manager() && typeFiltered.length > 0 ? `
              <label class="tmpl-select-all-label">
                <input type="checkbox" id="tmpl-select-all-cb" data-action="toggle-select-all-templates" ${isAllSelected ? 'checked' : ''}>
                <span>${selectedTemplateItems.size > 0 ? `已選 ${selectedTemplateItems.size} 項` : '全選'}</span>
              </label>
            ` : ''}
            ${manager() && selectedTemplateItems.size > 0 ? `
              <button type="button" class="btn text small danger" data-action="batch-delete-templates" title="批次刪除選取的範本">${icon("trash")} 批次刪除 (${selectedTemplateItems.size})</button>
              <button type="button" class="btn text small" data-action="clear-selected-templates">取消選取</button>
            ` : ''}
            <button type="button" class="btn primary small" data-action="open-template-wizard">${icon("plus")} 新增範本</button>
          </div>
        </div>

        ${typeFiltered.length ? `
          <div class="tmpl-grid">
            ${typeFiltered.map(t => renderTmplCard(t)).join("")}
          </div>
        ` : `
          <div class="panel tmpl-empty-box">
            <p class="muted">目前尚無範本，可點選建立新範本。</p>
            <button type="button" class="btn primary small" data-action="open-template-wizard">${icon("plus")} 建立第一個範本</button>
          </div>
        `}
      `;
    } else if(templatesTab === "taxonomy"){
      wrap.innerHTML = `
        <div class="tmpl-taxonomy-grid">
          <!-- 記事分類 (單選) -->
          <div class="panel category-panel">
            <div class="category-panel-head">
              <div>
                <h3 class="category-panel-title">${icon("folder")} 記事分類清單</h3>
                <small class="muted">單選：標記這筆記事主要屬於哪一類業務</small>
              </div>
              ${manager() && noteCats.length < 20 ? `<button class="btn primary small" data-action="new-single-category" data-type="note">${icon("plus")} 新增分類</button>` : ''}
            </div>
            <div class="categories-list">
              ${noteCats.map((c, idx) => `
                <div class="category-item-row">
                  <div class="category-item-info">
                    <span class="muted category-idx">#${idx+1}</span>
                    <strong class="category-name">${esc(c.name)}</strong>
                    ${c.name === '一般備忘' ? '<span class="badge">系統保留</span>' : ''}
                    <span class="muted category-count">(${c.usage_count||0} 筆)</span>
                  </div>
                  ${manager() && c.name !== '一般備忘' ? `
                    <div class="category-item-actions">
                      <button class="btn text small" data-action="edit-single-category" data-type="note" data-name="${esc(c.name)}">${icon("edit")} 改名</button>
                      <button class="btn text small danger" data-action="delete-single-category" data-type="note" data-name="${esc(c.name)}">${icon("trash")} 刪除</button>
                    </div>
                  ` : ''}
                </div>
              `).join("")}
            </div>
          </div>

          <!-- 案件類別 (單選) -->
          <div class="panel category-panel">
            <div class="category-panel-head">
              <div>
                <h3 class="category-panel-title">${icon("case_icon")} 案件類別清單</h3>
                <small class="muted">單選：標記此案件所屬的工單流程類別</small>
              </div>
              ${manager() && caseCats.length < 20 ? `<button class="btn primary small" data-action="new-single-category" data-type="case">${icon("plus")} 新增類別</button>` : ''}
            </div>
            <div class="categories-list">
              ${caseCats.map((c, idx) => `
                <div class="category-item-row">
                  <div class="category-item-info">
                    <span class="muted category-idx">#${idx+1}</span>
                    <strong class="category-name">${esc(c.name)}</strong>
                    ${c.name === '一般備忘' ? '<span class="badge">系統保留</span>' : ''}
                    <span class="muted category-count">(${c.usage_count||0} 筆)</span>
                  </div>
                  ${manager() && c.name !== '一般備忘' ? `
                    <div class="category-item-actions">
                      <button class="btn text small" data-action="edit-single-category" data-type="case" data-name="${esc(c.name)}">${icon("edit")} 改名</button>
                      <button class="btn text small danger" data-action="delete-single-category" data-type="case" data-name="${esc(c.name)}">${icon("trash")} 刪除</button>
                    </div>
                  ` : ''}
                </div>
              `).join("")}
            </div>
          </div>
        </div>

        <!-- 標籤色彩庫 (多選) -->
        <div class="panel section-space tags-panel">
          <div class="category-panel-head">
            <div>
              <h3 class="category-panel-title">${icon("tag")} 標籤色彩治理庫 (${noteTags.length} 項)</h3>
              <small class="muted">多選：為案件與記事標記特徵屬性，支援 Apple HIG 柔和色彩</small>
            </div>
            ${manager() ? `<button class="btn primary small" data-action="manage-notes-taxonomy">${icon("tag")} 治理與新增標籤</button>` : ''}
          </div>
          <div class="tags-cloud">
            ${noteTags.map(t => {
              const color = t.color || DEFAULT_TAG_COLORS[t.name] || "#007AFF";
              const bg = color.length === 7 ? color + "20" : "rgba(0,122,255,0.14)";
              const border = color.length === 7 ? color + "48" : "rgba(0,122,255,0.3)";
              return `<span class="apple-pill" data-color="${esc(color)}" style="background-color:${esc(bg)}!important;color:${esc(color)}!important;border-color:${esc(border)}!important;">${icon("tag")} ${esc(t.name)} <small class="pill-count">(${t.note_count||t.usage_count||0})</small></span>`;
            }).join("")}
          </div>
        </div>
      `;
    } else if(templatesTab === "packs"){
      const currentPack = packs.find(p => p.pack_id === selectedPackKey || p.key === selectedPackKey) || packs[0];
      if(currentPack) selectedPackKey = currentPack.pack_id || currentPack.key;

      wrap.innerHTML = `
        <div class="category-panel-head">
          <div>
            <h3 class="category-panel-title">${icon("layers")} 範本群組管理 (進階)</h3>
            <small class="muted">管理組織啟用的範本群組、匯出/匯入與跨 OA 派發</small>
          </div>
          ${manager() ? `<button class="btn primary small" data-action="new-custom-pack">${icon("plus")} 新增自訂群組</button>` : ''}
        </div>

        <div class="packs-layout">
          <div class="panel packs-sidebar">
            <h4 class="packs-sidebar-title">${icon("bookmark")} 範本群組清單</h4>
            <div class="packs-nav-list">
              ${packs.map(p => {
                const isSelected = (p.pack_id === selectedPackKey || p.key === selectedPackKey);
                return `
                  <div class="pack-nav-card ${isSelected?'selected':''}" data-action="select-template-pack" data-id="${esc(p.pack_id||p.key)}">
                    <div class="pack-nav-card-head">
                      <strong>${esc(p.name)}</strong>
                      ${p.is_preset ? '<span class="badge">系統預設</span>' : '<span class="badge primary">自訂</span>'}
                    </div>
                    <div class="pack-nav-card-desc">${esc(p.description||"無說明")}</div>
                  </div>
                `;
              }).join("")}
            </div>
          </div>

          <div class="panel pack-detail-content">
            ${currentPack ? renderPackDetailSection(currentPack) : '<p class="muted">請選擇範本群組</p>'}
          </div>
        </div>
      `;
    }
  } catch(e) {
    wrap.innerHTML = `<p class="callout warn">${icon("alert")} 載入失敗：${esc(e.message)}</p>`;
  }
}

function renderTmplCard(t){
  const isCase = t.type === 'case';
  const iconHtml = isCase ? icon("case_icon") : icon("note_icon");
  const typeLabel = isCase ? "案件範本" : "記事範本";
  const catName = t.category_name || "一般備忘";
  const priority = t.priority || "medium";
  const priNames = { urgent: "緊急優先", high: "重要處理", medium: "一般進度", low: "低優先度" };

  return `
    <article class="tmpl-card ${selectedTemplateItems.has(t.template_id)?'selected':''}">
      <div class="tmpl-card-head">
        <div class="tmpl-card-title-row">
          ${manager() ? `<input type="checkbox" class="tmpl-card-select-cb" data-id="${esc(t.template_id)}" data-type="${esc(t.type)}" data-name="${esc(t.name)}" ${selectedTemplateItems.has(t.template_id)?'checked':''} title="選取此範本">` : ''}
          <span class="tmpl-type-tag ${isCase?'case':'note'}">${iconHtml} ${typeLabel}</span>
          <h4 class="tmpl-card-title">${esc(t.name)}</h4>
        </div>
        ${manager() ? `
          <div class="tmpl-card-head-actions">
            <button type="button" class="tmpl-icon-btn" data-action="edit-template-modal" data-id="${esc(t.template_id)}" data-name="${esc(t.name)}" data-pack="${esc(t.pack_id)}" data-type="${esc(t.type)}" title="編輯範本">${icon("edit")}</button>
            <button type="button" class="tmpl-icon-btn danger" data-action="delete-template-btn" data-id="${esc(t.template_id)}" data-name="${esc(t.name)}" data-type="${esc(t.type)}" title="刪除範本">${icon("trash")}</button>
          </div>
        ` : ''}
      </div>

      <p class="tmpl-card-desc">${esc(t.body || t.title || "無詳細說明")}</p>

      <div class="tmpl-card-meta">
        <span class="badge">${icon("folder")} ${esc(catName)}</span>
        ${isCase ? `<span class="badge tmpl-priority-badge ${priority}"><span class="priority-dot"></span>${priNames[priority]||"一般進度"}</span>` : ''}
        ${t.is_preset ? '<span class="badge">範本範例</span>' : '<span class="badge primary">自訂範本</span>'}
      </div>

      <div class="tmpl-card-foot">
        <small class="muted">群組：${esc(t.pack_name||"通用")}</small>
        <div class="tmpl-card-actions">
          <button type="button" class="btn small" data-action="preview-template-modal" data-id="${esc(t.template_id)}" data-name="${esc(t.name)}" data-pack="${esc(t.pack_id)}" data-type="${esc(t.type)}">${icon("file")} 檢視大綱</button>
          ${manager() ? `
            <button type="button" class="btn small" data-action="edit-template-modal" data-id="${esc(t.template_id)}" data-name="${esc(t.name)}" data-pack="${esc(t.pack_id)}" data-type="${esc(t.type)}">${icon("edit")} 編輯</button>
          ` : ''}
        </div>
      </div>
    </article>
  `;
}

function renderPackDetailSection(p){
  const isPreset = p.is_preset;
  const isLocked = p.is_locked;
  const caseTemplates = p.case_templates || [];
  const noteTemplates = p.note_templates || [];

  return `<div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
      <div>
        <h2 style="font-size:18px;margin:0 0 4px 0;">${esc(p.name)} ${isLocked?'<span class="badge warn" style="font-size:11px;">已鎖定</span>':''}</h2>
        <p class="subtitle" style="margin:0;">${esc(p.description||"提供組織標準流程與快速帶入。")}</p>
      </div>
      <div style="display:flex;gap:6px;">
        <button class="btn small" data-action="copy-pack-modal" data-id="${esc(p.pack_id||p.key)}">${icon("copy")} 複製群組</button>
        ${!isPreset && manager() ? `
          <button class="btn small" data-action="toggle-pack-lock-btn" data-id="${esc(p.pack_id)}" data-locked="${isLocked?1:0}">${isLocked?icon("unlock")+' 解鎖':icon("lock")+' 鎖定'}</button>
          ${!isLocked ? `<button class="btn small danger" data-action="delete-pack-btn" data-id="${esc(p.pack_id)}">${icon("trash")} 刪除</button>` : ''}
        ` : ''}
      </div>
    </div>

    <!-- 案件範本區 -->
    <div style="margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <h4 style="font-size:14px;margin:0;display:flex;align-items:center;gap:6px;">${icon("case_icon")} 案件範本 (${caseTemplates.length})</h4>
        ${!isPreset && !isLocked && manager() ? `<button class="btn small" data-action="new-template-modal" data-pack="${esc(p.pack_id)}" data-type="case">${icon("plus")} 新增案件範本</button>` : ''}
      </div>
      <div class="tmpl-grid">
        ${caseTemplates.map(t => renderTmplCard({ ...t, type: 'case', pack_name: p.name, pack_id: p.pack_id, is_preset: isPreset })).join("") || '<p class="muted">此群組尚無案件範本</p>'}
      </div>
    </div>

    <!-- 記事範本區 -->
    <div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <h4 style="font-size:14px;margin:0;display:flex;align-items:center;gap:6px;">${icon("note_icon")} 記事範本 (${noteTemplates.length})</h4>
        ${!isPreset && !isLocked && manager() ? `<button class="btn small" data-action="new-template-modal" data-pack="${esc(p.pack_id)}" data-type="note">${icon("plus")} 新增記事範本</button>` : ''}
      </div>
      <div class="tmpl-grid">
        ${noteTemplates.map(t => renderTmplCard({ ...t, type: 'note', pack_name: p.name, pack_id: p.pack_id, is_preset: isPreset })).join("") || '<p class="muted">此群組尚無記事範本</p>'}
      </div>
    </div>
  </div>`;
}

// ----------------- Step-by-Step 3 步引導精靈 (Wizard) -----------------

async function openTemplateWizard(step = 1, wizardState = {}){
  const stateData = {
    targetType: wizardState.targetType || "case",
    name: wizardState.name || "",
    title: wizardState.title || "",
    body: wizardState.body || "",
    category: wizardState.category || "一般備忘",
    priority: wizardState.priority || "medium",
    tags: wizardState.tags || [],
    packId: wizardState.packId || selectedPackKey || "universal",
    ...wizardState
  };

  const [packsRes, catRes, tagsRes] = await Promise.all([
    api('/api/template-packs'),
    api('/api/categories'),
    api('/api/chat-notes/tags')
  ]);

  const customPacks = (packsRes.packs || []).filter(p => !p.is_preset && !p.is_locked);
  const defaultPackId = customPacks[0]?.pack_id || (packsRes.packs || [])[0]?.pack_id || "universal";
  if(!stateData.packId || stateData.packId === "universal") stateData.packId = defaultPackId;

  const cats = (stateData.targetType === "case" ? catRes.case_categories : catRes.note_categories) || [];
  const availableTags = tagsRes.tags || [];

  let stepContent = "";

  if(step === 1){
    stepContent = `
      <div class="tmpl-wizard-steps">
        <div class="tmpl-wizard-step-dot active">1</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot">2</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot">3</div>
      </div>
      <h3 style="font-size:16px;text-align:center;margin:0 0 6px 0;">這個範本主要會用在什麼場合？</h3>
      <p class="subtitle" style="text-align:center;margin-bottom:20px;">選擇適用的工作場景，系統將為您準備最佳欄位。</p>

      <div class="tmpl-wizard-choice-grid">
        <div class="tmpl-wizard-choice-card ${stateData.targetType==='case'?'selected':''}" data-action="wizard-select-type" data-type="case">
          <h4>${icon("case_icon")} 處理案件任務</h4>
          <p>適合設備報修、客訴處理、請款核銷、跨部門交辦等需追蹤狀態的工單流程。</p>
        </div>

        <div class="tmpl-wizard-choice-card ${stateData.targetType==='note'?'selected':''}" data-action="wizard-select-type" data-type="note">
          <h4>${icon("note_icon")} 記錄對話記事</h4>
          <p>適合客戶來電摘要、會議結論、現場場勘、日常交接備忘等通訊記錄。</p>
        </div>
      </div>

      <div class="form-actions" style="margin-top:24px;justify-content:flex-end;">
        <button type="button" class="btn primary" data-action="wizard-next-step" data-next="2">下一步：填寫內容 ${icon("arrow")}</button>
      </div>
    `;
  } else if(step === 2){
    stepContent = `
      <div class="tmpl-wizard-steps">
        <div class="tmpl-wizard-step-dot done">${icon("check")}</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot active">2</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot">3</div>
      </div>
      <h3 style="font-size:16px;text-align:center;margin:0 0 6px 0;">填寫範本內容與骨架</h3>
      <p class="subtitle" style="text-align:center;margin-bottom:16px;">設定預先準備好的檢查清單或大綱，同事使用時只需填空。</p>

      <div class="form-grid">
        <div class="full">
          <label class="field">
            範本名稱（必填）
            <input type="text" id="wz-name" value="${esc(stateData.name)}" required maxlength="30" placeholder="例如：設備報修處理標準流程、客戶訪談備忘">
            <small class="muted">此名稱用於在範本選單中辨識</small>
          </label>
        </div>

        <div class="full">
          <label class="field">
            預設標題（選填）
            <input type="text" id="wz-title" value="${esc(stateData.title)}" maxlength="60" placeholder="例如：客戶設備故障報修 - ">
            <small class="muted">套用此範本時會自動帶入的案件或記事標題</small>
          </label>
        </div>

        ${renderDualFormatEditor("body", "wz-body", stateData.body, stateData.format || null)}
      </div>

      <div class="form-actions" style="margin-top:20px;justify-content:space-between;">
        <button type="button" class="btn" data-action="wizard-prev-step" data-prev="1">🠔 上一步</button>
        <button type="button" class="btn primary" data-action="wizard-next-step" data-next="3">下一步：整理與預覽 ${icon("arrow")}</button>
      </div>
    `;
  } else if(step === 3){
    const isCase = stateData.targetType === "case";
    const priLabels = { urgent: "🔴 緊急優先", high: "🟠 重要處理", medium: "⚪ 一般進度", low: "低優先度" };

    stepContent = `
      <div class="tmpl-wizard-steps">
        <div class="tmpl-wizard-step-dot done">${icon("check")}</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot done">${icon("check")}</div>
        <div class="tmpl-wizard-step-line"></div>
        <div class="tmpl-wizard-step-dot active">3</div>
      </div>
      <h3 style="font-size:16px;text-align:center;margin:0 0 6px 0;">整理方式與即時預覽</h3>
      <p class="subtitle" style="text-align:center;margin-bottom:16px;">選擇所屬分類與優先程度，確認無誤後即可建立。</p>

      <div class="form-grid">
        <div class="full">
          <label class="field">
            所屬分類（單選：主要屬於哪一類業務）
            <select id="wz-category">
              ${cats.map(c => `<option value="${esc(c.name)}" ${stateData.category===c.name?'selected':''}>${esc(c.name)}</option>`).join("")}
              ${!cats.some(c=>c.name==='一般備忘')?'<option value="一般備忘">一般備忘</option>':''}
            </select>
          </label>
        </div>

        ${isCase ? `
          <div class="full">
            <label class="field">
              預設優先程度
              <select id="wz-priority">
                <option value="urgent" ${stateData.priority==='urgent'?'selected':''}>🔴 緊急優先</option>
                <option value="high" ${stateData.priority==='high'?'selected':''}>🟠 重要處理</option>
                <option value="medium" ${stateData.priority==='medium'?'selected':''}>⚪ 一般進度</option>
                <option value="low" ${stateData.priority==='low'?'selected':''}>低優先度</option>
              </select>
            </label>
          </div>
        ` : ''}

        ${customPacks.length ? `
          <div class="full">
            <details style="font-size:12px;margin-top:4px;">
              <summary class="muted" style="cursor:pointer;">${icon("settings")} 進階設定：選擇儲存之範本群組</summary>
              <div style="margin-top:8px;">
                <select id="wz-pack">
                  ${customPacks.map(p => `<option value="${esc(p.pack_id)}" ${stateData.packId===p.pack_id?'selected':''}>${esc(p.name)}</option>`).join("")}
                </select>
              </div>
            </details>
          </div>
        ` : ''}
      </div>

      <!-- 即時完成卡片預覽 (支援 Markdown 渲染) -->
      <div class="tmpl-live-preview-box">
        <h5>${icon("sparkles")} 完成後卡片與 Markdown 預覽</h5>
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
          <div>
            <span class="tmpl-type-tag ${isCase?'case':'note'}" style="margin-bottom:4px;">${isCase?icon("case_icon")+' 案件範本':icon("note_icon")+' 記事範本'}</span>
            <strong style="display:block;font-size:15px;margin:3px 0 2px 0;">${esc(stateData.name || "未命名範本")}</strong>
            <small class="muted">${esc(stateData.category || "一般")} ${isCase?'· '+priLabels[stateData.priority||'medium']:''}</small>
          </div>
          <span class="badge primary">${icon("check")} 預覽就緒</span>
        </div>
        <div class="tmpl-live-md-box" style="background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px;margin-top:8px;">
          ${renderMarkdown(stateData.body)}
        </div>
      </div>

      <div class="form-actions" style="margin-top:20px;justify-content:space-between;">
        <button type="button" class="btn" data-action="wizard-prev-step" data-prev="2">🠔 上一步</button>
        <button type="button" class="btn primary" data-action="wizard-submit-final">${icon("check")} 完成並建立範本</button>
      </div>
    `;
  }

  modal("建立新範本", `<div id="template-wizard-container" data-step="${step}" data-state='${esc(JSON.stringify(stateData))}'>${stepContent}</div>`);
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
  applyPersonalSettings();
  if(state.session?.needs_setup){$("crumb").textContent="首次設定";document.title="首次設定 · LINE 自動化";$("page").innerHTML=firstAdminPage();renderWorkspaceTools();return;}
  if(!lineDataReady()&&!["organizations","channels","oa-list","personnel","org-settings","templates","personal-settings","duty"].includes(state.view))state.view=superAdmin()?"organizations":"channels";
  if(superAdmin()&&!["organizations","channels","personal-settings"].includes(state.view))state.view="organizations";
  if(!titles[state.view])state.view="overview";
  if(state.view==="forms"&&!state.session?.forms_capabilities?.view)state.view=superAdmin()?"organizations":"overview";
  if(state.view==="duty"&&!state.session?.duty_capabilities?.view)state.view=superAdmin()?"organizations":"overview";
  $("crumb").textContent=titles[state.view]||"工作空間";document.title=(titles[state.view]||"工作台")+" · LINE 自動化";
  document.querySelectorAll("nav [data-view]").forEach(el=>{const current=el.dataset.view===state.view;el.classList.toggle("active",current);if(current)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  applyNavRail();
  const pages={
    overview,
    duty:dutyPage,
    forms:formsPage,
    "oa-list": oaListPage,
    chat:()=>chatPage(),
    "chat-notes": chatNotesPage,
    send:sendPage,
    cases:casesPage,
    templates:()=>templatesAndCategoriesPage(),
    contacts:()=>contactsPage(),
    history:historyPage,
    schedule:schedulePage,
    personnel:personnelPage,
    "org-settings":orgSettingsPage,
    "personal-settings":personalSettingsPage,
    channels:channelsPage,
    organizations:organizationsPage
  };
  const pageFn = pages[state.view] || overview;
  $("page").innerHTML=pageFn();
  renderWorkspaceTools();
  if(state.view === "templates"){
    loadTemplatesTabContent();
  }
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
  const orgChannels = state.channels.filter(c => c.workspace_id === 'o:'+org.org_id && c.active);

  return heading("人員與權限", `管理「${esc(org.name)}」的操作與協作人員，指定可用 LINE OA。`, button("新增人員","new-personnel","primary"))+`
  <div class="management">
    <div class="mg-summary">
      <div class="mg-stat"><strong>${members.filter(m=>m.active&&m.role==='org_admin').length}</strong><span>位管理員</span></div>
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
              ${org.duty_enabled&&m.role==="operator"?`<form class="duty-grant-form" data-email="${esc(m.email)}" data-org="${esc(org.org_id)}" data-saved="${m.duty_manager?'true':'false'}"><label class="check-label"><input name="duty_manager" type="checkbox" ${m.duty_manager?"checked":""} ${!enabled||state.session.preview?"disabled":""}>值日生管理</label>${enabled&&!state.session.preview?'<button type="submit" class="btn small" disabled>儲存管理權</button>':'<small>停用帳號或視角預覽不可授權</small>'}<small class="duty-grant-status" role="status">${m.duty_manager?'已授予管理權':'尚未授予管理權'}</small></form>`:""}
              ${['operator','collaborator'].includes(m.role) ? button("編輯與 OA 授權", "edit-personnel", "small", `data-id="${key}"`) : ""}
              ${u?.active && ['operator','collaborator'].includes(m.role) ? button("產生登入連結", "unused", "small", `data-security="invite" data-email="${esc(m.email)}"`) : ""}
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
  const tab = state.orgSettingsTab || "general";
  const lockPolicy = org.note_lock_policy || "disabled";
  const tagPolicy = org.note_tag_policy || "controlled";

  const tabButtons = [
    ["general", "基本資料與治理政策", "settings"],
    ["audit", `操作與查閱紀錄 (${state.events.length})`, "clock"]
  ].map(([id, title, iconName]) => `
    <button type="button" data-action="org-settings-tab" data-id="${id}" class="${tab === id ? 'active' : ''}" aria-pressed="${tab === id}">
      ${icon(iconName)} ${title}
    </button>
  `).join("");

  return heading("組織設定", `檢視與設定「${esc(org.name)}」的基本資料、記事本治理政策、範本包與透明稽核紀錄。`, "")+`
  <div class="management">
    <div class="segmented org-subtabs-bar" role="tablist" style="margin-bottom:20px;display:inline-flex;gap:6px;background:var(--soft);padding:6px;border-radius:14px;border:1px solid var(--line);">
      ${tabButtons}
    </div>

    ${tab === "general" ? `
      <!-- 分頁一：基本資料與治理政策 -->
      <section class="mg-card">
        <div class="mg-head">
          <div><h2>組織基本資料</h2><p>組織代碼：${esc(org.org_id)} · 組織類型：${esc(orgKinds[org.kind]||org.kind)}</p></div>
          ${button("編輯組織資料", "edit-organization", "small", `data-id="${esc(org.org_id)}"`)}
        </div>
      </section>

      <section class="mg-card policy-governance-section">
        <div class="mg-head">
          <div>
            <h2>對話記事本治理政策</h2>
            <p>設定組織層級的記事鎖定防誤改機制與分類標籤管理權限，確保團隊協作順暢且資料有序。</p>
          </div>
        </div>
        <div class="mg-body" style="padding:22px 24px;">
          <form id="org-notes-policy-form" data-org="${esc(org.org_id)}">

            <!-- 1. 記事與案件防護及防誤改模式 -->
            <div class="policy-group">
              <div class="policy-group-header">
                <span class="policy-group-icon">${icon("shield")}</span>
                <div>
                  <h3 class="policy-group-title">記事與案件防護及防誤改模式</h3>
                  <p class="policy-group-desc">統一管理記事與案件的上鎖、解鎖權限。上鎖後內容為唯讀，避免多人協作時誤改或誤刪。</p>
                </div>
              </div>

              <div class="policy-cards-grid policy-cards-3">
                <!-- 自由編輯模式 (disabled) -->
                <label class="policy-card ${lockPolicy==='disabled'?'selected':''}">
                  <input type="radio" name="note_lock_policy" value="disabled" ${lockPolicy==='disabled'?'checked':''}>
                  <div class="policy-card-top">
                    <span class="policy-badge-icon zap">${icon("zap")}</span>
                    <div class="policy-card-titles">
                      <strong class="policy-card-name">自由編輯模式</strong>
                      <span class="policy-badge-pill good">⚡ 預設推薦 · 輕快敏捷</span>
                    </div>
                    <span class="policy-radio-indicator"></span>
                  </div>
                  <p class="policy-card-desc">適合 1–3 人或即時溝通型團隊。全員可新增與編輯記事及案件，也可自由上鎖或解鎖；上鎖後內容為唯讀。</p>
                  <div class="policy-card-footer">
                    <span class="policy-rule-tag">${icon("check")} 全員可上鎖與解鎖 · 上鎖後唯讀</span>
                  </div>
                </label>

                <!-- 全員協作防護模式 (collaborative) -->
                <label class="policy-card ${lockPolicy==='collaborative'?'selected':''}">
                  <input type="radio" name="note_lock_policy" value="collaborative" ${lockPolicy==='collaborative'?'checked':''}>
                  <div class="policy-card-top">
                    <span class="policy-badge-icon shield">${icon("shield")}</span>
                    <div class="policy-card-titles">
                      <strong class="policy-card-name">全員協作防護</strong>
                      <span class="policy-badge-pill">🛡️ 多人協作 · 防誤觸改</span>
                    </div>
                    <span class="policy-radio-indicator"></span>
                  </div>
                  <p class="policy-card-desc">適合多人共編團隊。組織管理員與操作人員可上鎖記事及案件；協作人員不可操作鎖頭；操作人員只能解鎖自己建立的記事或案件。上鎖後所有人僅能閱覽與複製。</p>
                  <div class="policy-card-footer">
                    <span class="policy-rule-tag">${icon("check")} 管理員與操作人員可鎖定／解鎖 · 排除協作人員</span>
                  </div>
                </label>

                <!-- 管理員嚴格管控模式 (strict_admin) -->
                <label class="policy-card ${lockPolicy==='strict_admin'?'selected':''}">
                  <input type="radio" name="note_lock_policy" value="strict_admin" ${lockPolicy==='strict_admin'?'checked':''}>
                  <div class="policy-card-top">
                    <span class="policy-badge-icon lock">${icon("lock")}</span>
                    <div class="policy-card-titles">
                      <strong class="policy-card-name">管理員嚴格管控</strong>
                      <span class="policy-badge-pill warm">🔒 管理員專屬管控</span>
                    </div>
                    <span class="policy-radio-indicator"></span>
                  </div>
                  <p class="policy-card-desc">適合分工嚴謹或具審查制度的團隊。僅「組織管理員」可對記事及案件執行上鎖與解鎖；其他成員對已鎖定內容僅能閱讀與複製。</p>
                  <div class="policy-card-footer">
                    <span class="policy-rule-tag">${icon("check")} 僅管理員可解鎖 · 操作人員唯讀</span>
                  </div>
                </label>
              </div>
            </div>

            <!-- 2. 標籤與分類管理權限 -->
            <div class="policy-group" style="margin-top:28px;">
              <div class="policy-group-header">
                <span class="policy-group-icon">${icon("tag")}</span>
                <div>
                  <h3 class="policy-group-title">標籤與分類管理權限</h3>
                  <p class="policy-group-desc">規範誰可以建立與管理分類標籤庫，維持組織知識庫的整潔與一致性。</p>
                </div>
              </div>

              <div class="policy-cards-grid policy-cards-2">
                <!-- 集中規範模式 (controlled) -->
                <label class="policy-card ${tagPolicy==='controlled'?'selected':''}">
                  <input type="radio" name="note_tag_policy" value="controlled" ${tagPolicy==='controlled'?'checked':''}>
                  <div class="policy-card-top">
                    <span class="policy-badge-icon tag">${icon("tag")}</span>
                    <div class="policy-card-titles">
                      <strong class="policy-card-name">集中規範管理</strong>
                      <span class="policy-badge-pill good">📋 預設推薦 · 規範整潔</span>
                    </div>
                    <span class="policy-radio-indicator"></span>
                  </div>
                  <p class="policy-card-desc">適合希望維持標籤整潔、避免標籤氾濫的團隊。僅「組織管理員」可新增與管理分類標籤；操作人員與協作人員從現有標籤庫挑選套用。</p>
                  <div class="policy-card-footer">
                    <span class="policy-rule-tag">${icon("check")} 管理員統一管理 · 團隊成員選用標籤庫</span>
                  </div>
                </label>

                <!-- 開放自訂模式 (open) -->
                <label class="policy-card ${tagPolicy==='open'?'selected':''}">
                  <input type="radio" name="note_tag_policy" value="open" ${tagPolicy==='open'?'checked':''}>
                  <div class="policy-card-top">
                    <span class="policy-badge-icon spark">${icon("sparkles")}</span>
                    <div class="policy-card-titles">
                      <strong class="policy-card-name">全員自由自訂</strong>
                      <span class="policy-badge-pill">✨ 彈性靈活 · 隨開隨用</span>
                    </div>
                    <span class="policy-radio-indicator"></span>
                  </div>
                  <p class="policy-card-desc">適合業務多變或講求高度靈活的團隊。所有團隊成員在建立或編輯對話記事時，皆可直接輸入並建立全新的自訂標籤。</p>
                  <div class="policy-card-footer">
                    <span class="policy-rule-tag">${icon("check")} 全員皆可隨時自創新標籤與自訂分類</span>
                  </div>
                </label>
              </div>
            </div>

            <div class="form-actions" style="margin-top:24px;border-top:1px solid var(--line);padding-top:18px;">
              <button class="btn primary" type="submit">${icon("check")} 儲存記事本治理政策</button>
            </div>
          </form>
        </div>
      </section>

      <section class="mg-card">
        <div class="mg-head">
          <div><h2>自訂範本包管理</h2><p>為組織建立自訂案件與記事範本包，各 OA 可勾選啟用。</p></div>
          ${button("管理自訂範本包", "open-template-packs-mgr", "primary small")}
        </div>
      </section>
    ` : `
      <!-- 分頁二：組織操作與查閱紀錄（透明稽核） -->
      <section class="mg-card">
        <div class="mg-head">
          <div>
            <h2>組織操作與查閱紀錄</h2>
            <p>包含內部人員操作與供應商查看紀錄（透明稽核）。所有資料存取與設定變更均完整留存供稽核。</p>
          </div>
          ${badge(state.events.length + " 筆紀錄", "good")}
        </div>
        <div class="mg-body">
          ${state.events.map(e => `
            <div class="activity-row" data-s="sc907557" style="display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-bottom:1px solid var(--line);">
              <div data-s="sda5a491">
                <strong style="font-size:13.5px;color:var(--ink);display:block;line-height:1.5;">${esc(formatAuditDetail(e.detail, e.action) || formatAuditAction(e.action))}</strong>
                <small class="muted" style="display:block;margin-top:4px;">${when(e.created_at)}</small>
              </div>
              <div style="text-align:right;flex-shrink:0;margin-left:12px;">
                <span class="badge" style="font-size:11px;background:var(--soft);color:var(--ink);border:1px solid var(--line);">${esc(e.actor || "系統")}</span>
                <span class="badge good" style="font-size:11px;margin-left:4px;">[${esc(formatAuditAction(e.action))}]</span>
              </div>
            </div>
          `).join("") || '<p class="muted" style="padding:24px 0;text-align:center;">尚無操作紀錄。</p>'}
        </div>
      </section>
    `}
  </div>`;
}

function personnelForm(id){
  const org = mgCurrentOrg();
  if(!org) return;
  const m = id ? state.memberships.find(x => x.email + "|" + x.org_id === id) : null;
  const u = m ? mgUser(m.email) : null;
  const orgChannels = state.channels.filter(c => c.workspace_id === 'o:'+org.org_id && c.active);
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
      <button type="button" class="btn text" data-action="close-modal">關閉</button>
      <button type="button" class="btn danger small" data-action="confirm-logout">登出帳號</button>
    </div>
  </div>`);
}

function closeOaSwitcher(restoreFocus=false){
  $('oa-switcher-dropdown')?.remove();
  $('workspace-context')?.setAttribute('aria-expanded','false');
  if(restoreFocus)$('workspace-context')?.focus();
}
function toggleOaSwitcher(){
  if($('oa-switcher-dropdown')){closeOaSwitcher(true);return;}
  const trigger=$('workspace-context'),rect=trigger.getBoundingClientRect();
  const dropdown=document.createElement('div');
  dropdown.id='oa-switcher-dropdown';dropdown.className='oa-switcher-dropdown';
  dropdown.setAttribute('role','region');dropdown.setAttribute('aria-label','切換 LINE OA');
  const width=Math.min(440,window.innerWidth-24);
  dropdown.style.width=width+'px';
  dropdown.style.left=Math.max(12,Math.min(rect.left,window.innerWidth-width-12))+'px';
  dropdown.style.top=(rect.bottom+8)+'px';
  dropdown.style.maxHeight=Math.max(120,window.innerHeight-rect.bottom-24)+'px';
  trigger.setAttribute('aria-expanded','true');trigger.setAttribute('aria-controls',dropdown.id);
  const allOas=lineUI.channels||state.channels||[],currentId=lineUI.channel;
  dropdown.innerHTML=`<div class="oa-switcher-modal">
    <div class="oa-switcher-toolbar"><label class="oa-switcher-search">${icon('search')}<input type="search" id="oa-switcher-filter" placeholder="搜尋 LINE OA 名稱或組織…" aria-label="搜尋 LINE OA 名稱或組織"></label><button type="button" class="btn" data-action="go-oa-list-from-switcher">OA 一覽</button></div>
    <div id="oa-switcher-items" class="oa-switcher-items">
      ${allOas.map(c=>{const current=c.channel_id===currentId,orgId=c.org_id||c.workspace_id?.replace(/^o:/,'')||'';return `<button type="button" class="oa-switcher-item ${current?'is-current':''}" data-action="switch-oa-direct" data-channel="${esc(c.channel_id)}" data-org="${esc(orgId)}" aria-current="${current?'true':'false'}">
        <span class="oa-switcher-avatar" aria-hidden="true">${esc(c.name.slice(0,1))}</span>
        <span class="oa-switcher-text"><strong>${esc(c.name)}</strong><small>${esc(c.workspace_name||orgName(orgId))}</small></span>
        <span class="oa-switcher-status">${current?`<span class="sr-only">目前使用</span>${icon('check')}`:''}</span>
      </button>`;}).join('')||'<p class="muted">尚無可切換的 LINE OA。</p>'}
    </div><p id="oa-switcher-empty" class="muted" hidden>找不到符合的 LINE OA。</p>
  </div>`;
  document.body.appendChild(dropdown);
  $('oa-switcher-filter').focus({preventScroll:true});
}

function dutyPage(){
  if(!dutyContext)return empty("值日生模組尚未開放","請聯絡組織管理員。");
  const allTabs=[["home","首頁"],["roster","排班管理"],["people","人員與工作"],["notify","通知設定"],["log","通知紀錄"]];
  const tabs=dutyContext.can_inspect_setup?allTabs:allTabs.filter(([id])=>["home","roster","log"].includes(id));
  if(!["home","roster","people","tasks","notify","log"].includes(dutyTab))dutyTab="home";
  if(!dutyContext.can_inspect_setup&&!["home","roster","log"].includes(dutyTab))dutyTab="home";
  const selected=dutyTab==="tasks"?"people":dutyTab;
  const content={
    home:["本月值日班表","檢視工作與負責人。"],
    roster:["尚未建立班表","先建立值日人員與工作項目，再建立排班。"],
    people:["尚未建立值日人員","值日人員不需後台帳號，用來排班與接收通知。"],
    tasks:["尚未建立工作項目","工作可設定年、月、週輪換，以及每日、每週、每月執行子項目。"],
    notify:["尚未指定通知 OA","通知與提醒尚未啟用，請先設定通知 OA 與時間。"],
    log:["尚無通知紀錄","值日生通知將在這裡記錄，不混入一般發送紀錄。"]
  }[dutyTab];
  const readonly=state.session.preview?"視角預覽僅供檢視，請返回原帳號管理值日生。":!dutyContext.capabilities.edit?"你目前只能檢視班表":"";
  return heading("值日生","管理排班輪換與工作提醒。")+
    `<div class="duty-context" aria-label="值日生班表資訊">${badge("組織："+dutyContext.organization.name)}${badge("通知 OA："+(dutyAutomation.settings?.channels.find(o=>o.channel_id===dutyContext.notification_oa)?.name||dutyContext.notification_oa||"尚未指定"))}${badge("有效版本："+(dutyContext.effective_version?dutyContext.effective_version.name+" v"+dutyContext.effective_version.version:"尚未發布"))}</div>`+
    (readonly?`<p class="callout">${esc(readonly)}</p>`:"")+
    `<div class="msg-nav-segmented duty-tabs" role="group" aria-label="值日生分頁">${tabs.map(([id,title])=>`<button type="button" class="btn ${selected===id?"active":""}" data-duty-tab="${id}" aria-pressed="${selected===id}">${title}</button>`).join("")}</div>`+
    (selected==="people"?`<div class="segmented duty-subtabs" role="group" aria-label="人員與工作分類">${[["people","值日人員"],["tasks","工作項目"]].map(([id,title])=>`<button type="button" data-duty-tab="${id}" aria-pressed="${dutyTab===id}">${title}</button>`).join("")}</div>`:"")+
    (selected==="home"?dutyHomePage():selected==="roster"?dutyRosterPage():selected==="people"&&dutyContext.can_inspect_setup?dutySetupPage():selected==="notify"?dutyNotificationPage():selected==="log"?dutyNotificationLog():`<section class="panel panel-body duty-empty">${empty(content[0],content[1])}<p class="subtitle">${dutyContext.capabilities.edit?"目前已開放模組與管理權限；此功能將於後續階段提供。":"僅顯示已發布內容；目前沒有可檢視的資料。"}</p></section>`);
}
document.addEventListener("click",event=>{
  const target=event.target.closest("[data-duty-tab]");if(!target)return;
  if(!dutyCanLeave())return;
  document.querySelectorAll('[data-duty-form][data-dirty="true"]').forEach(form=>form.dataset.dirty="false");
  dutyTab=target.dataset.dutyTab;navigate("duty");
  document.querySelector(`[data-duty-tab="${CSS.escape(dutyTab)}"]`)?.focus({preventScroll:true});
});
document.addEventListener("change",event=>{
  const form=event.target.closest('.duty-grant-form');
  if(form){
    const changed=String(form.elements.duty_manager.checked)!==form.dataset.saved;
    form.dataset.dirty=String(changed);
    const submit=form.querySelector('[type="submit"]');if(submit){submit.disabled=!changed;submit.textContent='儲存管理權';}
    const status=form.querySelector('.duty-grant-status');status.dataset.state=changed?'pending':'';
    status.textContent=changed?'尚未儲存 · 點選儲存後生效':form.elements.duty_manager.checked?'已授予管理權':'尚未授予管理權';
  }
});
window.addEventListener("beforeunload",event=>{
  if(document.querySelector('.duty-grant-form[data-dirty="true"], [data-duty-form][data-dirty="true"], [data-form-editor][data-dirty="true"], [data-form-designer][data-dirty="true"]')){event.preventDefault();event.returnValue="";}
});
function navigate(view){if(state.busy)return;if(document.querySelector('.duty-grant-form[data-dirty="true"], [data-duty-form][data-dirty="true"], [data-form-editor][data-dirty="true"], [data-form-designer][data-dirty="true"]')&&!confirm("有未儲存變更，確定離開？"))return;notice("");if(state.view==="forms"&&view!=="forms"){formsUI.mode="basic";formDesignerReset();}state.view=view;state.search="";state.kind="all";state.organization_id="";state.department="";state.tagFilter="";state.page=1;setSidebarOpen(false);history.replaceState(null,"","/?view="+encodeURIComponent(view)+(view==="duty"?"&tab="+encodeURIComponent(dutyTab):""));render();$("content").scrollTo({top:0});window.scrollTo({top:0});}
function modal(title,html){$("modal-title").textContent=title;$("modal-body").innerHTML=html;$("modal-error").hidden=true;if(!$("modal").open)$("modal").showModal();$("modal").scrollTop=0;$("modal-close").focus({preventScroll:true});}
async function editContact(id){
  let r=state.contacts.find(x=>x.recipient_id===id);
  if(!r){
    const channel=lineUI.channel;
    notice('正在載入聯絡資料…');
    const data=await api('/api/contacts');
    if(channel!==lineUI.channel)return;
    state.contacts=data.contacts;state.tags=data.tags||[];
    r=state.contacts.find(x=>x.recipient_id===id);
    if(!r){notice('找不到可編輯的聯絡對象，請更新聊天清單後再試。',true);return;}
    notice('');
  }
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
        ${field("內部分組","department",r.department,'maxlength="60" placeholder="例如：網路部、北區客戶"')}
      </div>
    </div>
    <div class="form-section">
      <h3 class="form-section-title">內部備忘與標籤</h3>
      <div class="form-grid">
        <div class="full"><label class="field">備忘筆記（Notes）<textarea name="notes" rows="3" maxlength="1000" placeholder="記錄該聯絡對象背景、注意事項、互動歷史備忘...">${esc(r.notes||"")}</textarea></label></div>
        <div class="full"><label class="field">分類標籤（Tags）</label><div class="permission-choices">${tagCheckboxes||'<p class="muted">尚未建立任何標籤，可於聯絡對象工具列點選「標籤管理」新增。</p>'}</div></div>
      </div>
    </div>
    <p class="callout">系統組織表示資料所屬工作空間；內部分組用於搜尋、篩選與選取發送對象，不會授予權限。聯絡資訊的部門表示對方實際任職部門。自訂名稱、聯絡資訊與筆記僅供後台團隊檢視，不會傳送給 LINE 使用者。</p>
    <div class="form-actions"><button class="btn primary" type="submit">儲存聯絡對象</button></div>
  </form>`);
  const form=$("contact-form");
  const renderFields=type=>{
    const c=$("contact-dynamic-fields");if(!c)return;
    if(type==="organization"){
      c.innerHTML=`${field("對方組織名稱","organization_name",r.organization_name||"",'maxlength="80" placeholder="例如：台北市攝影同好會、宏昇生技"')}${field("代表電話","phone",r.phone||"",'maxlength="40" placeholder="例如：02-2345-6789"')}${field("代表 Email","email",r.email||"",'type="email" maxlength="120" placeholder="例如：contact@org.tw"')}${field("郵遞區號","postal_code",r.postal_code||"",'maxlength="10" placeholder="例如：100"')}<div class="full">${field("地址","address",r.address||"",'maxlength="200" placeholder="例如：台北市中正區重慶南路一段 10 號"')}</div>`;
    }else if(type==="person_business"){
      c.innerHTML=`${field("所屬對方組織","organization_name",r.organization_name||"",'maxlength="80" placeholder="例如：宏昇生技、北區家長會"')}${field("部門","work_department",r.work_department||"",'maxlength="60" placeholder="對方任職部門，例如：採購部"')}${field("職稱","job_title",r.job_title||"",'maxlength="60" placeholder="例如：採購主任、總幹事"')}${field("公務電話","work_phone",r.work_phone||"",'maxlength="40" placeholder="例如：02-2345-6789"')}${field("公務分機","work_phone_ext",r.work_phone_ext||"",'maxlength="20" placeholder="例如：101"')}${field("公務 Email","work_email",r.work_email||"",'type="email" maxlength="120" placeholder="例如：john@company.com"')}${field("個人電話（選填）","phone",r.phone||"",'maxlength="40" placeholder="例如：0912-345-678"')}${field("個人 Email（選填）","email",r.email||"",'type="email" maxlength="120" placeholder="例如：john@gmail.com"')}${field("郵遞區號","postal_code",r.postal_code||"",'maxlength="10" placeholder="例如：100"')}<div class="full">${field("通訊地址","address",r.address||"",'maxlength="200" placeholder="例如：台北市中正區重慶南路一段 10 號"')}</div>`;
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
async function submitSend(){
  if(state.busy)return;
  if(!state.session.modules.messaging)throw new Error("此組織未授權訊息發送模組。");
  if(state.session.preview)throw new Error("預覽不會實際發送，請返回原帳號操作。");
  if(sessionStorage.getItem("linePendingJob"))throw new Error("有一筆提交尚未確認。請先到發送紀錄檢查，再重新整理。");
  const id=crypto.randomUUID(),payload={job_id:id,audience:"selected",ids:selectedRows().map(r=>r.recipient_id)};
  if(state.report.category==="composition")payload.composition=state.report.composition;else payload.message_text=state.report.message_text;
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
  if(!formCanLeave())return;
  if(email&&!viewOptions.some(user=>user.email+"|"+user.organization_id===email))throw new Error("請重新整理可用帳號。");
  if(email)localStorage.setItem(viewKey,email);else localStorage.removeItem(viewKey);
  // A full navigation discards in-flight previews and all previous-role data.
  location.replace(location.pathname+"?view=overview");
}
document.addEventListener("dblclick", async event => {
  const caseCard=event.target.closest("[data-case-preview]");
  if(caseCard){
    if(state.busy || event.target.closest("button,a,input,label,select,textarea,summary"))return;
    try{await caseDetailModal(caseCard.dataset.casePreview);}catch(error){notice(error.message,true);}
    return;
  }
  const card = event.target.closest("[data-note-preview], .notes-hub-card");
  if (!card || state.busy || event.target.closest("[data-action], button, a, input, select, textarea")) return;
  try {
    await chatNoteDetailModal(card.dataset.notePreview || card.dataset.id);
  } catch (error) {
    notice(error.message, true);
  }
});
document.addEventListener("keydown",event=>{
  if(event.key==="Enter" && event.target.matches("[data-note-preview]")){
    event.preventDefault();chatNoteDetailModal(event.target.dataset.notePreview).catch(error=>notice(error.message,true));
  }
  if(event.key==="Enter" && event.target.matches("[data-case-preview]")){
    event.preventDefault();caseDetailModal(event.target.dataset.casePreview).catch(error=>notice(error.message,true));
  }
});
document.addEventListener("click",async event=>{
  const touchPreview=event.pointerType==='touch'||window.matchMedia('(pointer:coarse)').matches||window.matchMedia('(max-width:850px)').matches;
  if(touchPreview && !state.busy && !$("modal").open && !event.target.closest('button,a,input,label,select,textarea,summary')){
    const card=event.target.closest('[data-case-preview],[data-note-preview],.notes-hub-card');
    if(card){
      try{
        if(card.dataset.casePreview)await caseDetailModal(card.dataset.casePreview);
        else await chatNoteDetailModal(card.dataset.notePreview||card.dataset.id);
      }catch(error){notice(error.message,true);}
      return;
    }
  }
  if(event.target.closest("#my-account-btn")){myAccountModal();return;}
  if(event.target.closest("#workspace-context")){toggleOaSwitcher();return;}
  const nav=event.target.closest("[data-view]");if(nav){navigate(nav.dataset.view);return;}
  const target=event.target.closest("[data-action]");if(!target||target.disabled||state.busy)return;
  if(target.matches(".chat-note-item,.case-item") && event.target.closest("input, label, textarea, select, a, summary")) return;
  const action=target.dataset.action,id=target.dataset.id;
  try{
    if(action==="personal-preview-info"){notice("這是資訊通知預覽。");return;}
    if(action==="personal-preview-warning"){notice("這是警告通知預覽。",true);return;}
    if(action==="personal-reset"){localStorage.removeItem(personalSettingsKey());render();notice("已還原個人化預設設定。");return;}
    if(workspaceAction(action,id))return;
    if(action==='chat-room-marker'){
      const room=chatUI.rooms.find(r=>r.recipient_id===id);if(!room || room._saving)return;
      const kind=target.dataset.marker;
      const payload={recipient_id:id,is_pinned:kind==='pin'?!room.is_pinned:Boolean(room.is_pinned),marker:kind==='pin'?(room.marker||''):room.marker===kind?'':kind};
      room._saving=true;try{Object.assign(room,await api('/api/chat/room-preference',payload));}finally{room._saving=false;}
      $('chat-room-list').innerHTML=renderChatRoomItems();return;
    }

    if(action==="record-lock-note"){
      const previewOpen=Boolean(document.querySelector('#modal[open] .note-detail-view'));
      const result=await api("/api/chat-notes/lock",{note_id:id});
      const records=[...(state.globalNotes||[]),...Array.from(state.chatNotes?.values()||[]).flat(),state.notePreview].filter(Boolean);
      records.filter(n=>n.note_id===id).forEach(n=>Object.assign(n,result));
      await loadChatNotes(target.dataset.recipient);
      if(state.view==="chat-notes")await loadGlobalChatNotes();
      if(previewOpen)await chatNoteDetailModal(id);
      notice(result.is_locked?"記事已上鎖，僅可閱覽。":"記事已解鎖，可編輯。");return;
    }
    if(action==="record-lock-case"){
      const previewOpen=Boolean(document.querySelector('#modal[open] .case-detail-view'));
      await api(`/api/cases/${id}/lock`,{});await load();render();
      if(previewOpen)await caseDetailModal(id);return;
    }
    if(action==="notes-status-tab"){state.noteHubStatus=id;await loadGlobalChatNotes();return;}
    if(managementAction(action,id))return;
    if(composerAction(action,id))return;
    if(typeof chatAction==="function"&&chatAction(action,id,target))return;
    if(action==="switch-oa-direct"){
      closeOaSwitcher();
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
    else if(action==="close-modal"){$("modal").close();}
    else if(action==="go-oa-list-from-switcher"){closeOaSwitcher();navigate("oa-list");}
    else if(action==="dismiss-onboarding"){
      const orgId=state.session?.user?.organization_id||"";
      if(orgId)localStorage.setItem("lineOnboardingDismissed_"+orgId,"1");
      render();
    }
    else if(action==="new-personnel")personnelForm();
    else if(action==="edit-personnel")personnelForm(id);
    else if(action==="org-settings-tab"){state.orgSettingsTab=id;render();}
    else if(action==="open-template-packs-mgr"){navigate("templates");$("modal").close();}
    else if(action==="confirm-logout"){
      try{await api('/api/auth/logout',{},true,true);sessionStorage.removeItem('lineAdminToken');location.replace('/login');}catch(error){notice(error.message,true);}
    }
    else if(action==="case-filter"){state.caseFilter=id;render();}
    else if(action==="new-case-modal")createCaseModal(id||"");
    else if(action==="open-case-detail")await caseDetailModal(id);
    else if(action==="edit-case-modal")editCaseModal(id);
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
    else if(action==="open-note-detail")await chatNoteDetailModal(id);
    else if(action==="new-chat-note")chatNoteModal(id);
    else if(action==="edit-chat-note")chatNoteModal(target.dataset.recipient||chatUI.selectedId, id);
    else if(action==="delete-chat-note"){
      const recId = target.dataset.recipient || chatUI.selectedId || "";
      modal("刪除對話記事？",`<p>確定要刪除這筆記事嗎？刪除後移至回收筒（30 天內可還原）。</p><div class="form-actions">${button("確認刪除","confirm-delete-chat-note","danger",`data-id="${esc(id)}" data-recipient="${esc(recId)}"`)}</div>`);
    }
    else if(action==="confirm-delete-chat-note"){
      await api("/api/chat-notes",{action:"delete",note_id:id});
      if(target.dataset.recipient) await loadChatNotes(target.dataset.recipient);
      if(state.view === "chat-notes") await loadGlobalChatNotes();
      $("modal").close();
      notice("記事已刪除。");
    }
    else if(action==="toggle-chat-note-pin"){
      const recId = target.dataset.recipient || chatUI.selectedId;
      const res = await api("/api/chat-notes/pin", { note_id: id });
      if(recId) loadChatNotes(recId);
      if(state.view === "chat-notes") loadGlobalChatNotes();
      notice(res.is_pinned ? "記事已置頂。" : "已取消置頂。");
    }
    else if(action==="toggle-chat-note-lock"){
      const recId = target.dataset.recipient || chatUI.selectedId;
      const res = await api("/api/chat-notes/lock", { note_id: id });
      if(recId) loadChatNotes(recId);
      if(state.view === "chat-notes") loadGlobalChatNotes();
      notice(res.is_locked ? "記事已鎖定，防止誤改。" : "記事已解除鎖定。");
    }
    else if(action==="toggle-chat-note-complete"){
      const recId = target.dataset.recipient || chatUI.selectedId;
      const res = await api("/api/chat-notes/complete", { note_id: id });
      if(recId) loadChatNotes(recId);
      if(state.view === "chat-notes") loadGlobalChatNotes();
      notice(res.status === "completed" ? "記事已標記為完成。" : "記事已重新開啟。");
    }
    else if(action==="toggle-chat-note-expand"){
      const contentEl = document.getElementById("chat-note-content-" + id);
      if(!contentEl) return;
      const isCollapsed = contentEl.classList.contains("collapsed");
      if(isCollapsed){
        contentEl.classList.remove("collapsed");
        target.innerHTML = `${icon("chevron-up")} 收合內容`;
      } else {
        contentEl.classList.add("collapsed");
        target.innerHTML = `${icon("chevron-down")} 展開全文`;
      }
    }
    else if(action==="copy-chat-note-content"){
      await noteCopyOptions(id);
    }
    else if(action==="copy-note-version"){
      await copyNoteText(id==='markdown'?state.noteCopyContent:noteReadingCopy(state.noteCopyContent));
    }
    else if(action==="copy-case-content"){
      const record=state.cases.find(c=>c.case_id===id)||(await api(`/api/cases/${encodeURIComponent(id)}`)).case;
      if(!record)throw new Error('找不到案件內容。');
      await recordCopyOptions(record.description||'','案件');
    }
    else if(action==="toggle-notes-view-mode"){
      state.noteHubViewMode = id;
      if(state.view === "chat-notes") render();
    }
    else if(action==="manage-notes-taxonomy"){
      manageNotesTaxonomyModal();
    }
    else if(action==="export-chat-notes-modal"){
      exportChatNotesModal();
    }
    else if(action==="quick-add-note-tag"){
      const input = $("chat-note-tags-input");
      if(input){
        let current = input.value.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
        const tag = target.dataset.tag;
        if(tag){
          if(current.includes(tag)){
            current = current.filter(t => t !== tag);
            target.classList.remove("active-selected");
          } else {
            if(current.length >= 5){
              notice("每則記事最多設定 5 個標籤。", true);
              return;
            }
            current.push(tag);
            target.classList.add("active-selected");
          }
          input.value = current.join(", ");
          $("chat-note-selected-tags").textContent=current.join("、") || "尚未選擇標籤";
          $("chat-note-quick-tags-container").innerHTML=renderCategoryScopedTagsHtml(input.closest("form").querySelector('select[name="category_id"]').value,current);
          const form = input.closest("form");
          if(form) form.dataset.dirty = "true";
        }
      }
    }
    else if(action==="switch-tax-tab"){
      manageNotesTaxonomyModal(target.dataset.tab || "categories");
    }
    else if(action==="toggle-color-picker"){
      const popover = $(target.dataset.target);
      if(popover) popover.hidden = !popover.hidden;
    }
    else if(action==="select-inline-color"){
      const color = target.dataset.color || "#007AFF";
      const input = $(target.dataset.input);
      const trigger = $(target.dataset.trigger);
      const popover = $(target.dataset.popover);
      if(input) input.value = color;
      if(trigger) {
        trigger.style.backgroundColor = color;
        trigger.dataset.color = color;
      }
      if(popover){
        popover.querySelectorAll(".tax-color-dot").forEach(d => d.classList.remove("selected"));
        target.classList.add("selected");
        popover.hidden = true;
      }
    }
    else if(action==="pick-tax-color"){
      const picker = target.closest(".tax-color-picker");
      if(picker){
        picker.querySelectorAll(".tax-color-dot").forEach(d => d.classList.remove("selected"));
        target.classList.add("selected");
        const hiddenInput = picker.parentElement.querySelector('input[name="color"]');
        if(hiddenInput) hiddenInput.value = target.dataset.color || "#007AFF";
      }
    }
    else if(action==="edit-category-modal"){
      modal("編輯記事分類", `<form id="tax-category-edit-form" data-id="${esc(id)}">
        <div class="form-grid">
          <div class="full"><label class="field">分類名稱<input name="name" value="${esc(target.dataset.name||"")}" required maxlength="20" placeholder="例如：商務商談、工程工務、售後客服"></label></div>
        </div>
        <div class="form-actions"><button class="btn primary small" type="submit">儲存變更</button></div>
      </form>`);
    }
    else if(action==="merge-category-modal"){
      const otherCats = (state.noteCategories||[]).filter(c => c.category_id !== id);
      if(!otherCats.length){
        notice("目前沒有其他分類可供合併轉移。", true);
        return;
      }
      const opts = otherCats.map(c => `<option value="${esc(c.category_id)}">${esc(c.name)} (${c.note_count||0} 則)</option>`).join("");
      modal("合併轉移記事分類", `<form id="tax-category-merge-form" data-source="${esc(id)}">
        <div class="tax-merge-flow">
          <div class="tax-merge-node">
            <small class="muted" style="display:block;margin-bottom:6px;font-size:11px;">來源分類（即將移除）</small>
            <span class="tax-item-category-badge" style="font-size:13px;padding:4px 12px;">
              ${icon("folder")}
              <span>${esc(target.dataset.name)}</span>
            </span>
          </div>
          <div class="tax-merge-arrow">
            ${icon("arrow")}
            <small style="font-size:10.5px;color:var(--muted);font-weight:600;">批次整併</small>
          </div>
          <div class="tax-merge-node">
            <small class="muted" style="display:block;margin-bottom:6px;font-size:11px;">目標分類（接收全部記事）</small>
            <select name="target_category_id" required style="font-size:13px;padding:6px 10px;min-height:36px;width:100%;">${opts}</select>
          </div>
        </div>
        <p class="callout" style="font-size:12px;">確認合併後，原分類下的所有歷史記事將自動遷移至目標分類，並自動清理原分類名稱。</p>
        <div class="form-actions"><button class="btn primary small" type="submit">確認合併轉移</button></div>
      </form>`);
    }
    else if(action==="delete-category-btn"){
      modal("刪除記事分類？", `<p>確定要刪除分類「<strong>${esc(target.dataset.name)}</strong>」嗎？<br><br><span class="muted" style="font-size:12px;">若該分類下已有歷史記事，記事將自動轉移至預設分類，避免資料遺失。</span></p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-note-category", "danger", `data-id="${esc(id)}"`)}</div>`);
    }
    else if(action==="confirm-delete-note-category"){
      await api("/api/chat-notes/categories/delete", { category_id: id });
      $("modal").close();
      await manageNotesTaxonomyModal("categories");
      notice("記事分類已刪除。");
    }
    else if(action==="edit-tag-modal"){
      const color = target.dataset.color || "#007AFF";
      const colorOptionsHtml = APPLE_TAG_COLORS.map(c =>
        `<button type="button" class="tax-color-dot ${c.hex===color?'selected':''}" data-action="pick-tax-color" data-color="${c.hex}" style="background:${c.hex};" title="${c.name}"></button>`
      ).join("");
      modal("編輯記事標籤", `<form id="tax-tag-edit-form" data-id="${esc(id)}" data-old-name="${esc(target.dataset.name)}">
        <div class="form-grid">
          <div class="full"><label class="field">標籤名稱<input name="name" value="${esc(target.dataset.name||"")}" required maxlength="30" placeholder="例如：VIP客戶、緊急處理"></label></div>
          <div class="full">
            <label class="field">標籤代表色
              <div class="tax-color-picker">${colorOptionsHtml}</div>
              <input type="hidden" name="color" value="${esc(color)}">
            </label>
          </div>
        </div>
        <div class="form-actions"><button class="btn primary small" type="submit">儲存變更</button></div>
      </form>`);
    }
    else if(action==="merge-tag-modal"){
      const otherTags = (state.noteTags||[]).filter(t => t.tag_id !== id);
      if(!otherTags.length){
        notice("目前沒有其他標籤可供合併。", true);
        return;
      }
      const sourceColor = target.dataset.color || (state.noteTags.find(t=>t.tag_id===id)?.color || "#007AFF");
      const opts = otherTags.map(t => `<option value="${esc(t.tag_id)}">${esc(t.name)} (${t.note_count||0} 則)</option>`).join("");
      modal("同義詞標籤合併", `<form id="tax-tag-merge-form" data-source="${esc(id)}">
        <div class="tax-merge-flow">
          <div class="tax-merge-node">
            <small class="muted" style="display:block;margin-bottom:6px;font-size:11px;">來源同義詞（即將移除）</small>
            <span class="apple-pill" style="background:${esc(sourceColor)}18;color:${esc(sourceColor)};border-color:${esc(sourceColor)}33;font-size:13px;padding:4px 12px;">
              ${esc(target.dataset.name)}
            </span>
          </div>
          <div class="tax-merge-arrow">
            ${icon("arrow")}
            <small style="font-size:10.5px;color:var(--muted);font-weight:600;">同義整併</small>
          </div>
          <div class="tax-merge-node">
            <small class="muted" style="display:block;margin-bottom:6px;font-size:11px;">目標正式標籤（保留）</small>
            <select name="target_tag_id" required style="font-size:13px;padding:6px 10px;min-height:36px;width:100%;">${opts}</select>
          </div>
        </div>
        <p class="callout" style="font-size:12px;">確認後將自動將帶有來源標籤的所有記事更新為目標標籤，有效防止團隊同義標籤氾濫。</p>
        <div class="form-actions"><button class="btn primary small" type="submit">確認合併標籤</button></div>
      </form>`);
    }
    else if(action==="delete-note-tag-btn"){
      modal("刪除記事標籤？", `<p>確定要刪除標籤「<strong>${esc(target.dataset.name)}</strong>」嗎？<br><br><span class="muted" style="font-size:12px;">刪除後所有既有記事將自動移除此標籤關聯。</span></p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-note-tag", "danger", `data-id="${esc(id)}"`)}</div>`);
    }
    else if(action==="cleanup-orphan-tags-btn"){
      modal("清理無引用孤立標籤？", `<p>將一鍵清除目前沒有任何記事引用的孤立標籤（預設標籤會保留）。</p>
        <div class="form-actions">${button("確認清理", "confirm-cleanup-orphan-tags", "danger")}</div>`);
    }
    else if(action==="confirm-cleanup-orphan-tags"){
      const res = await api("/api/chat-notes/tags/cleanup-orphans", {});
      $("modal").close();
      await manageNotesTaxonomyModal("tags");
      notice(`清理完成：共移除 ${res.deleted_count} 個無引用標籤。`);
    }
    else if(action==="delete-note-tag-btn"){
      modal("刪除記事標籤？", `<p>確定要刪除標籤「${esc(target.dataset.name)}」嗎？記事將移除此標籤關聯。</p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-note-tag", "danger", `data-id="${esc(id)}"`)}</div>`);
    }
    else if(action==="confirm-delete-note-tag"){
      await api("/api/chat-notes/tags/delete", { tag_id: id });
      $("modal").close();
      await manageNotesTaxonomyModal("tags");
      notice("標籤已刪除。");
    }
    else if(action==="open-save-filter-modal")saveFilterModal();
    else if(action==="new-organization")organizationForm();
    else if(action==="edit-organization")organizationForm(id);
    else if(action==="new-membership")membershipForm();
    else if(action==="edit-membership")membershipForm(id);
    else if(action==="switch-view")viewPicker();
    else if(action==="apply-view")switchView(id||"");
    else if(action==="start-send"){state.step=1;state.report=null;navigate("send");}
    else if(action==="choose-text"){const text=$("message-draft").value;if(!text.trim())throw new Error("請先輸入文字。");if(sessionStorage.getItem("linePendingJob"))throw new Error("請先確認上次提交結果。");state.textDraft=text;state.report={category:"text",title:"文字訊息",message_text:text,status:"ready",scope:"text"};state.step=2;state.selected.clear();state.audience="selected";render();}
    else if(action==="cancel-schedule")modal("取消這筆預約？",`<p>取消後不會傳送。已開始處理的工作無法取消。</p><div class="form-actions">${button("確認取消預約","confirm-cancel-schedule","danger",`data-id="${esc(id)}"`)}</div>`);
    else if(action==="confirm-cancel-schedule"){await api('/api/jobs/cancel',{job_id:id});$("modal").close();await load();render();notice("預約已取消。");}
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
    else if(action==="export-contacts-csv")contactExportModal();
    else if(action==="download-contacts-csv")downloadContactsCsv();
    else if(action==="edit-contact")await editContact(id);
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
    else if(action==="templates-switch-tab"){
      templatesTab = target.dataset.tab || id;
      loadTemplatesTabContent();
      document.querySelectorAll('[data-action="templates-switch-tab"]').forEach(b => b.classList.toggle('active', b.dataset.tab === templatesTab));
    }
    else if(action==="templates-subfilter"){
      templatesSubFilter = id || "all";
      loadTemplatesTabContent();
    }
    else if(action==="open-template-wizard"){
      openTemplateWizard(1);
    }
    else if(action==="wizard-select-type"){
      const choiceCard = target.closest(".tmpl-wizard-choice-card");
      if(choiceCard){
        const wzWrap = choiceCard.closest("#template-wizard-container");
        let wzState = {};
        try { wzState = JSON.parse(wzWrap.dataset.state || "{}"); } catch(_){}
        wzState.targetType = choiceCard.dataset.type || "case";
        wzWrap.querySelectorAll(".tmpl-wizard-choice-card").forEach(c => c.classList.toggle("selected", c === choiceCard));
        wzWrap.dataset.state = JSON.stringify(wzState);
      }
    }
    else if(action==="wizard-next-step"){
      const wzWrap = target.closest("#template-wizard-container");
      let wzState = {};
      try { wzState = JSON.parse(wzWrap?.dataset.state || "{}"); } catch(_){}
      const curStep = Number(wzWrap?.dataset.step || "1");
      const nextStep = Number(target.dataset.next || "2");

      if(curStep === 2){
        const nameVal = $("wz-name") ? $("wz-name").value.trim() : "";
        if(!nameVal){
          notice("請填寫範本名稱。", true);
          $("wz-name")?.focus();
          return;
        }
        wzState.name = nameVal;
        wzState.title = $("wz-title") ? $("wz-title").value.trim() : "";
        wzState.body = $("wz-body") ? $("wz-body").value.trim() : "";
      }

      openTemplateWizard(nextStep, wzState);
    }
    else if(action==="wizard-prev-step"){
      const wzWrap = target.closest("#template-wizard-container");
      let wzState = {};
      try { wzState = JSON.parse(wzWrap?.dataset.state || "{}"); } catch(_){}
      const curStep = Number(wzWrap?.dataset.step || "1");
      const prevStep = Number(target.dataset.prev || "1");

      if(curStep === 2){
        wzState.name = $("wz-name") ? $("wz-name").value.trim() : wzState.name;
        wzState.title = $("wz-title") ? $("wz-title").value.trim() : wzState.title;
        wzState.body = $("wz-body") ? $("wz-body").value.trim() : wzState.body;
      } else if(curStep === 3){
        wzState.category = $("wz-category") ? $("wz-category").value : wzState.category;
        wzState.priority = $("wz-priority") ? $("wz-priority").value : wzState.priority;
        wzState.packId = $("wz-pack") ? $("wz-pack").value : wzState.packId;
      }

      openTemplateWizard(prevStep, wzState);
    }
    else if(action==="set-editor-format"){
      const format = target.dataset.format || "plain";
      setPreferredEditorFormat(format);
      const editorWrap = target.closest(".tmpl-dual-editor-wrap") || target.closest(".tmpl-editor-container");
      if(!editorWrap) return;

      editorWrap.dataset.format = format;
      editorWrap.dataset.subtab = "write";
      const isMd = format === "markdown";

      // Update format switch button active state
      editorWrap.querySelectorAll('[data-action="set-editor-format"]').forEach(b => {
        b.classList.toggle("active", b.dataset.format === format);
      });

      const subtabs = editorWrap.querySelector(".tmpl-md-subtabs");
      if(subtabs){
        subtabs.querySelectorAll('[data-action="set-md-subtab"]').forEach(b => {
          b.classList.toggle("active", b.dataset.tab === "write");
        });
      }

      const textarea = editorWrap.querySelector("textarea");
      if(textarea){
        textarea.placeholder = isMd
          ? '支援 Markdown 語法，例如：\n### 1. 狀況確認\n- [ ] 詢問設備型號與故障現象\n- [ ] 拍照存證\n\n### 2. 處置措施\n* **優先等級**：重要處理\n* **備註**：安排工程窗口'
          : '填寫標準內容流程或檢查清單...';
      }
    }
    else if(action==="set-md-subtab"){
      const subtab = target.dataset.tab || "write";
      const targetId = target.dataset.target;
      const editorWrap = target.closest(".tmpl-dual-editor-wrap") || target.closest(".tmpl-editor-container");
      if(!editorWrap) return;

      editorWrap.dataset.subtab = subtab;

      const subtabs = editorWrap.querySelector(".tmpl-md-subtabs");
      if(subtabs){
        subtabs.querySelectorAll('[data-action="set-md-subtab"]').forEach(b => {
          b.classList.toggle("active", b.dataset.tab === subtab);
        });
      }

      const previewBox = editorWrap.querySelector(".tmpl-editor-preview-box");
      const textarea = $(targetId) || editorWrap.querySelector("textarea");

      if(subtab === "write"){
        if(textarea) textarea.focus();
      } else if(subtab === "preview"){
        if(previewBox){
          const text = textarea ? textarea.value : "";
          previewBox.innerHTML = text.trim()
            ? renderMarkdown(text)
            : '<span class="muted" style="font-size:12px;">（目前尚無內容可預覽，請切換回「✍️ 編輯」輸入文字）</span>';
        }
      }
    }
    else if(action==="wizard-submit-final"){
      const wzWrap = target.closest("#template-wizard-container");
      let wzState = {};
      try { wzState = JSON.parse(wzWrap?.dataset.state || "{}"); } catch(_){}

      const category = $("wz-category") ? $("wz-category").value : (wzState.category || "一般");
      const priority = $("wz-priority") ? $("wz-priority").value : (wzState.priority || "medium");
      const packId = $("wz-pack") ? $("wz-pack").value : (wzState.packId || "universal");

      const tmplType = wzState.targetType || "case";
      const name = wzState.name || "未命名範本";
      const title = wzState.title || "";
      const body = wzState.body || "";

      try {
        await api('/api/templates/save', {
          pack_id: packId,
          template_type: tmplType,
          name,
          title,
          body,
          category_name: category,
          priority
        });
        $("modal").close();
        notice(`已成功建立「${name}」範本。`);
        await loadTemplatesTabContent();
      } catch(err){
        notice("建立失敗：" + err.message, true);
      }
    }
    else if(action==="preview-template-modal"){
      const tmplId = target.dataset.id;
      const tmplName = target.dataset.name;
      const packId = target.dataset.pack;
      const tmplType = target.dataset.type;

      const packsRes = await api('/api/template-packs');
      const pack = (packsRes.packs || []).find(p => p.pack_id === packId || p.key === packId);
      const list = tmplType === 'case' ? pack?.case_templates : pack?.note_templates;
      const tmpl = (list || []).find(t => t.template_id === tmplId || t.name === tmplName);

      if(!tmpl){
        notice("找不到該範本。", true);
        return;
      }

      const isCase = tmplType === 'case';
      const priNames = { urgent: "緊急優先", high: "重要處理", medium: "一般進度", low: "低優先度" };

      modal(`檢視範本：${esc(tmpl.name)}`, `
        <div class="case-detail-view">
          <div class="case-detail-header">
            <div>
              <span class="tmpl-type-tag ${isCase?'case':'note'}">${isCase?icon("case_icon")+' 案件範本':icon("note_icon")+' 記事範本'}</span>
              <h2 style="font-size:17px;margin:6px 0 2px 0;">${esc(tmpl.name)}</h2>
              <small class="muted">所屬群組：${esc(pack?.name||"通用範本群組")}</small>
            </div>
            <div class="modal-badge-group">
              <span class="badge">${icon("folder")} ${esc(tmpl.category_name||"一般")}</span>
              ${isCase ? `<span class="badge tmpl-priority-badge ${tmpl.priority||'medium'}"><span class="priority-dot"></span>${priNames[tmpl.priority||'medium']||'一般進度'}</span>` : ''}
              ${pack?.is_preset ? '<span class="badge">系統預設</span>' : '<span class="badge primary">自訂</span>'}
            </div>
          </div>

          ${tmpl.title ? `
            <div class="section-space">
              <h4 style="font-size:13px;margin:0 0 4px 0;color:var(--muted);">預設帶入標題</h4>
              <p style="margin:0;font-weight:600;">${esc(tmpl.title)}</p>
            </div>
          ` : ''}

          <div class="section-space">
            <h4 style="font-size:13px;margin:0 0 6px 0;color:var(--muted);">內容大綱 / SOP 檢查清單</h4>
            <div class="tmpl-live-md-box" style="background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:14px;font-size:13px;line-height:1.6;">
              ${tmpl.body ? renderMarkdown(tmpl.body) : '<span class="muted">（無內容骨架）</span>'}
            </div>
          </div>

          <div class="callout" style="font-size:12.5px;">
            💡 <strong>使用提示</strong>：此頁面為管理中心，用於建立與維護標準 SOP。在處理「聊天對話」或「案件管理」時，側欄記事本與工單視窗均支援「從範本帶入」一鍵套用。
          </div>

          <div class="form-actions tmpl-modal-footer">
            <button type="button" class="btn small" data-action="copy-template-text" data-text="${esc(tmpl.body||tmpl.title||tmpl.name)}">${icon("copy")} 複製大綱文字</button>
            <div class="tmpl-modal-footer-right">
              ${manager() ? `
                <button type="button" class="btn small danger" data-action="delete-template-btn" data-id="${esc(tmpl.template_id)}" data-name="${esc(tmpl.name)}" data-type="${esc(tmplType)}">${icon("trash")} 刪除範本</button>
                <button type="button" class="btn primary small" data-action="edit-template-modal" data-id="${esc(tmpl.template_id)}" data-name="${esc(tmpl.name)}" data-pack="${esc(packId)}" data-type="${esc(tmplType)}">${icon("edit")} 編輯此範本</button>
              ` : ''}
              <button type="button" class="btn small" data-action="close-modal">關閉</button>
            </div>
          </div>
        </div>
      `);
    }
    else if(action==="copy-template-text"){
      const text = target.dataset.text || "";
      if(navigator.clipboard && navigator.clipboard.writeText){
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy(text);
      }
      notice("已複製範本大綱內容至剪貼簿。");
    }
    else if(action==="toggle-pack-enable"){
      const checked = target.checked;
      await api('/api/template-packs/toggle', {pack_key: id, enabled: checked});
      notice(checked ? "已啟用範本包。" : "已停用範本包 brass");
    }
    else if(action==="new-custom-pack"){
      modal("新增自訂範本群組", `<form id="custom-pack-form">
        <div class="form-grid">
          <div class="full">${field("群組名稱", "name", "", 'required maxlength="30" placeholder="例如：客服與維修標準流程、商務業務專用"')}</div>
          <div class="full">${field("群組說明（選填）", "description", "", 'maxlength="100" placeholder="簡述適用場景與對象"')}</div>
        </div>
        <div class="form-actions"><button class="btn primary" type="submit">建立範本群組</button></div>
      </form>`);
    }
    else if(action==="copy-pack-modal"){
      modal("複製為自訂範本群組", `<form id="copy-pack-form" data-source="${esc(id)}">
        <div class="form-grid">
          <div class="full">${field("新群組名稱", "name", "", 'required maxlength="30" placeholder="例如：自訂通用範本群組"')}</div>
        </div>
        <p class="callout">將複製該群組內所有的案件與記事範本為全新的自訂群組。</p>
        <div class="form-actions"><button class="btn primary" type="submit">確認複製</button></div>
      </form>`);
    }
    else if(action==="toggle-pack-lock-btn"){
      const isLocked = Number(target.dataset.locked) === 1;
      await api('/api/template-packs/lock', {pack_id: id, is_locked: !isLocked});
      notice(!isLocked ? "群組已鎖定。" : "群組已解鎖。");
      await loadTemplatesTabContent();
    }
    else if(action==="delete-pack-btn"){
      modal("刪除自訂範本群組？", `<p>確定要刪除此群組嗎？群組內所有範本將一併刪除（既有已建立的案件與記事不受影響）。</p>
        <div class="form-actions">${button("確認刪除", "confirm-delete-pack", "danger", `data-id="${esc(id)}"`)}</div>`);
    }
    else if(action==="confirm-delete-pack"){
      await api('/api/template-packs/delete', {pack_id: id});
      $("modal").close();
      selectedPackKey = "universal";
      await loadTemplatesTabContent();
      notice("範本群組已刪除。");
    }
    else if(action==="new-template-modal"){
      const packId = target.dataset.pack;
      const tmplType = target.dataset.type;
      openTemplateWizard(2, { targetType: tmplType, packId });
    }
    else if(action==="customize-preset-template"){
      const tmplId = target.dataset.id;
      const tmplName = target.dataset.name;
      const packId = target.dataset.pack;
      const tmplType = target.dataset.type;

      const packsRes = await api('/api/template-packs');
      const pack = (packsRes.packs || []).find(p => p.pack_id === packId || p.key === packId);
      const list = tmplType === 'case' ? pack?.case_templates : pack?.note_templates;
      const tmpl = (list || []).find(t => t.template_id === tmplId || t.name === tmplName);

      if(!tmpl){
        notice("找不到該範本。", true);
        return;
      }

      openTemplateWizard(2, {
        targetType: tmplType,
        name: tmpl.name,
        title: tmpl.title || "",
        body: tmpl.body || "",
        category: tmpl.category_name || "一般",
        priority: tmpl.priority || "medium"
      });
    }
    else if(action==="edit-template-modal"){
      const tmplId = target.dataset.id;
      const tmplName = target.dataset.name;
      const packId = target.dataset.pack;
      const tmplType = target.dataset.type;

      const packsRes = await api('/api/template-packs');
      const pack = (packsRes.packs || []).find(p => p.pack_id === packId || p.key === packId);
      const list = tmplType === 'case' ? pack?.case_templates : pack?.note_templates;
      const tmpl = (list || []).find(t => t.template_id === tmplId || t.name === tmplName);

      if(!tmpl){
        notice("找不到該範本。", true);
        return;
      }

      modal(`編輯${tmplType==="case"?"案件":"記事"}範本`, `<form id="template-form" data-pack="${esc(packId||'universal')}" data-type="${esc(tmplType)}" data-id="${esc(tmpl.template_id)}">
        <div class="form-grid">
          <div class="full">${field("範本名稱", "name", tmpl.name, 'required maxlength="30"')}</div>
          ${field("預設分類名稱", "category_name", tmpl.category_name||"一般", 'maxlength="30"')}
          ${field("預設標題", "title", tmpl.title||"", 'maxlength="100"')}
          ${renderDualFormatEditor("body", "tmpl-edit-body", tmpl.body || "", null,"內容骨架 / 檢查清單",6,"",false,true)}
        </div>
        <div class="form-actions" style="justify-content:space-between;margin-top:16px;">
          <button type="button" class="btn text danger" data-action="delete-template-btn" data-id="${esc(tmpl.template_id)}" data-name="${esc(tmpl.name)}" data-type="${esc(tmplType)}">${icon("trash")} 刪除範本</button>
          <button class="btn primary" type="submit">儲存修改</button>
        </div>
      </form>`);
    }
    else if(action==="delete-template-btn"){
      const tmplType = target.dataset.type;
      const tmplId = target.dataset.id || id;
      const tmplName = target.dataset.name || "";
      modal("確認刪除範本？", `<p>確定要刪除「${esc(tmplName || "此範本")}」嗎？既有已建立的案件或對話記事不受影響。</p>
        <div class="form-actions" style="justify-content:flex-end;gap:8px;">
          <button type="button" class="btn" data-action="close-modal">取消</button>
          <button type="button" class="btn danger" data-action="confirm-delete-template" data-id="${esc(tmplId)}" data-type="${esc(tmplType)}">確認刪除</button>
        </div>`);
    }
    else if(action==="confirm-delete-template"){
      const tmplType = target.dataset.type;
      await api('/api/templates/delete', {template_id: id, template_type: tmplType});
      selectedTemplateItems.delete(id);
      $("modal").close();
      await loadTemplatesTabContent();
      notice("範本已成功刪除。");
    }
    else if(action==="batch-delete-templates"){
      if(selectedTemplateItems.size === 0){
        notice("尚未勾選任何範本。", true);
        return;
      }
      const items = Array.from(selectedTemplateItems.values());
      const count = items.length;
      const previewNames = items.slice(0, 5).map(it => `「${esc(it.name)}」`).join("、") + (count > 5 ? ` 等 ${count} 個範本` : "");

      modal(`確認批次刪除 ${count} 個範本？`, `
        <div class="form-grid">
          <p>確定要刪除所勾選的 ${count} 個範本嗎？</p>
          <div class="callout" style="max-height:140px;overflow-y:auto;font-size:12.5px;">
            ${previewNames}
          </div>
          <p class="muted" style="font-size:12px;">💡 刪除後，既有已建立的案件或對話記事不會受到任何影響。</p>
        </div>
        <div class="form-actions" style="justify-content:flex-end;gap:8px;margin-top:16px;">
          <button type="button" class="btn" data-action="close-modal">取消</button>
          <button type="button" class="btn danger" data-action="confirm-batch-delete-templates">${icon("trash")} 確認批次刪除 (${count})</button>
        </div>
      `);
    }
    else if(action==="confirm-batch-delete-templates"){
      const items = Array.from(selectedTemplateItems.values()).map(it => ({
        template_id: it.template_id || it.id,
        template_type: it.template_type || it.type
      }));
      target.disabled = true;
      const res = await api('/api/templates/batch-delete', { items });
      const delCount = res.deleted_count || items.length;
      selectedTemplateItems.clear();
      $("modal").close();
      await loadTemplatesTabContent();
      notice(`已成功批次刪除 ${delCount} 項範本。`);
    }
    else if(action==="clear-selected-templates"){
      selectedTemplateItems.clear();
      loadTemplatesTabContent();
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
  if(event.target.id==="templates-search-input"){
    templatesSearchQuery = event.target.value.trim();
    loadTemplatesTabContent();
  }
  if(event.target.id==="oa-switcher-filter"){
    const q=event.target.value.toLowerCase();
    document.querySelectorAll(".oa-switcher-item").forEach(item=>{
      item.hidden=!item.textContent.toLowerCase().includes(q);
    });
    $("oa-switcher-empty").hidden=Boolean(document.querySelector(".oa-switcher-item:not([hidden])"));
  }
});
document.addEventListener("change", async event => {
  const checkbox = event.target.closest("input[data-case-task]");
  if(!checkbox) return;
  const caseId = checkbox.dataset.caseId;
  const records = [...state.cases, state.casePreview].filter(Boolean);
  const c = records.find(record => record.case_id === caseId);
  if(!c) { checkbox.checked = !checkbox.checked; return; }
  const controls = Array.from(document.querySelectorAll("input[data-case-task]")).filter(el => el.dataset.caseId === caseId);
  controls.forEach(el => { el.disabled = true; });
  try {
    const res = await api("/api/cases/task", {case_id: caseId, task_index: Number(checkbox.dataset.caseTask), checked: checkbox.checked, expected_content: c.description});
    records.filter(record => record.case_id === caseId).forEach(record => Object.assign(record, res.case));
    document.querySelectorAll(".chat-case-description").forEach(el => { if(el.dataset.caseId === caseId) el.innerHTML = renderCaseContent(c); });
    if(document.querySelector(".chat-work-panel"))refreshChatWorkPanel();
    if(state.casePreview?.case_id === caseId && $("modal").open){
      const preview = document.querySelector(".case-description-preview");
      if(preview) preview.innerHTML = renderCaseContent(c);
    }
  } catch(error) {
    checkbox.checked = !checkbox.checked;
    notice(error.message, true);
  } finally {
    controls.forEach(el => { el.disabled = Boolean(c.is_locked) || c.status === "closed" || Boolean(state.preview) || state.session?.role === "platform_admin"; });
  }
});
document.addEventListener("change", async event => {
  const checkbox = event.target.closest("input[data-note-task]");
  if(!checkbox) return;
  const noteId = checkbox.dataset.noteId;
  const notes = [...(state.globalNotes || []), ...Array.from(state.chatNotes?.values() || []).flat(), state.notePreview].filter(Boolean);
  const note = notes.find(n => n.note_id === noteId);
  if(!note) { checkbox.checked = !checkbox.checked; return; }
  const controls = Array.from(document.querySelectorAll("input[data-note-task]")).filter(el => el.dataset.noteId === noteId);
  controls.forEach(el => { el.disabled = true; });
  try {
    const res = await api("/api/chat-notes/task", {note_id: noteId, task_index: Number(checkbox.dataset.noteTask), checked: checkbox.checked, expected_content: note.content});
    notes.filter(n => n.note_id === noteId).forEach(n => Object.assign(n, res.note));
    const cardBody = document.getElementById("chat-note-content-" + noteId);
    if(cardBody) cardBody.innerHTML = renderNoteContent(note);
    if(document.querySelector(".chat-work-panel"))refreshChatWorkPanel();
    if(state.notePreview?.note_id === noteId && $("modal").open){
      const preview = document.querySelector(".note-detail-body .md-preview-area");
      if(preview) preview.innerHTML = renderNoteContent(note);
    }
  } catch(error) {
    checkbox.checked = !checkbox.checked;
    notice(error.message, true);
  } finally {
    controls.forEach(el => { el.disabled = Boolean(note.is_locked) || Boolean(state.preview) || state.session?.role === "platform_admin"; });
  }
});
document.addEventListener("change",event=>{
  const el=event.target;
  if(el.dataset.personalSetting){
    const prefs=personalSettings();
    prefs[el.dataset.personalSetting]=el.dataset.personalSetting==='duration'?Number(el.value):el.value;
    try{localStorage.setItem(personalSettingsKey(),JSON.stringify(prefs));}
    catch(_){notice('無法儲存個人化設定，請確認瀏覽器允許網站儲存資料。',true);return;}
    applyPersonalSettings();notice('個人化設定已儲存。');return;
  }
  if(el.name==="color"&&el.closest(".color-swatch-card")){
    el.closest(".color-picker-grid")?.querySelectorAll(".color-swatch-card").forEach(card=>card.classList.remove("selected"));
    el.closest(".color-swatch-card")?.classList.add("selected");
    return;
  }
  if(el.classList.contains("tmpl-card-select-cb")){
    const tid = el.dataset.id;
    const ttype = el.dataset.type;
    const tname = el.dataset.name;
    if(el.checked){
      selectedTemplateItems.set(tid, { template_id: tid, template_type: ttype, name: tname });
    } else {
      selectedTemplateItems.delete(tid);
    }
    loadTemplatesTabContent();
    return;
  }
  if(el.id === "tmpl-select-all-cb"){
    const isChecked = el.checked;
    const cbs = document.querySelectorAll(".tmpl-card-select-cb");
    cbs.forEach(cb => {
      const tid = cb.dataset.id;
      const ttype = cb.dataset.type;
      const tname = cb.dataset.name;
      if(isChecked){
        selectedTemplateItems.set(tid, { template_id: tid, template_type: ttype, name: tname });
      } else {
        selectedTemplateItems.delete(tid);
      }
    });
    loadTemplatesTabContent();
    return;
  }
  if(el.id==="organization-select"){if(!formCanLeave()){el.value=organization;return;}localStorage.setItem(organizationKey,el.value);location.replace(location.pathname+"?view=overview");return;}
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
  if(el.name==="note_lock_policy" || el.name==="note_tag_policy"){
    const container = el.closest(".policy-cards-grid");
    if(container){
      container.querySelectorAll(".policy-card").forEach(card => {
        const radio = card.querySelector("input[type=radio]");
        card.classList.toggle("selected", Boolean(radio && radio.checked));
      });
    }
    return;
  }
  if(el.dataset.select){el.checked?state.selected.add(el.dataset.select):state.selected.delete(el.dataset.select);updateSelection();}
  else if(["contact-kind","contact-company","contact-department"].includes(el.id)){state[{"contact-kind":"kind","contact-company":"organization_id","contact-department":"department"}[el.id]]=el.value;state.page=1;if(el.id==="contact-company"){state.department="";render();}else $("contact-list").innerHTML=contactList();}
});
document.addEventListener("submit",async event=>{if(event.target.id==="password-form"||event.target.hasAttribute("data-duty-form")||event.target.hasAttribute("data-form-editor")||event.target.hasAttribute("data-form-designer")||event.target.hasAttribute("data-form-preview"))return;event.preventDefault();const form=event.target,values=Object.fromEntries(new FormData(form)),submit=form.querySelector('[type="submit"]');if(!submit||submit.disabled)return;submit.disabled=true;$("modal-error").hidden=true;
  try{
    if(form.classList.contains("duty-grant-form")){
      const checked=form.elements.duty_manager.checked,status=form.querySelector('.duty-grant-status');
      submit.textContent='儲存中…';form.elements.duty_manager.disabled=true;form.setAttribute('aria-busy','true');
      status.dataset.state='pending';status.textContent='正在儲存管理權…';
      try{
        await api('/api/duty/grants',{email:form.dataset.email,org_id:form.dataset.org,duty_manager:checked});
        const member=state.memberships.find(m=>m.email===form.dataset.email&&m.org_id===form.dataset.org);
        if(member)member.duty_manager=checked?1:0;
        form.dataset.saved=String(checked);form.dataset.dirty='false';
        submit.textContent='已儲存';status.dataset.state='success';
        status.textContent=checked?'儲存成功 · 已授予值日生管理權':'儲存成功 · 已取消值日生管理權';
        notice(status.textContent);
      }catch(error){
        submit.disabled=false;submit.textContent='重試儲存';status.dataset.state='error';status.textContent='儲存失敗：'+error.message;
        notice(error.message,true);
      }finally{form.elements.duty_manager.disabled=false;form.removeAttribute('aria-busy');}
      return;
    }else if(form.id==="chat-send-form"){
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
    }else if(form.id==="case-edit-form"){
      const result=await api('/api/cases', {case_id:form.dataset.id,...values});
      state.cases=state.cases.map(c=>c.case_id===result.case.case_id?result.case:c);
      state.casePreview=result.case;
      render();await caseDetailModal(result.case.case_id);
      notice("案件已儲存。");return;
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
      const recipient_id = form.dataset.recipient || values.recipient_id;
      if(!recipient_id){
        notice("請選擇關聯的聯絡對象。", true);
        submit.disabled = false;
        return;
      }
      const note_id = form.dataset.noteId;
      const tags = values.tags ? values.tags.split(/[,，]/).map(s=>s.trim()).filter(Boolean) : [];
      await api('/api/chat-notes', {
        action: note_id ? "edit" : "add",
        recipient_id,
        note_id: note_id || undefined,
        title: values.title?.trim() || "",
        category_id: values.category_id || undefined,
        due_date: values.due_date || "",
        tags,
        expected_updated_at: values.expected_updated_at || undefined,
        content: values.content
      });
      form.dataset.dirty = "false";
      if(recipient_id) await loadChatNotes(recipient_id);
      if(state.view === "chat-notes") await loadGlobalChatNotes();
      $("modal").close();
      notice(note_id ? "記事已更新。" : "記事已新增。");
      return;
    }else if(form.id==="tax-category-create-form"){
      await api("/api/chat-notes/categories/save", {
        name: values.name
      });
      $("modal").close();
      await manageNotesTaxonomyModal("categories");
      notice("記事分類已新增。");
      return;
    }else if(form.id==="tax-category-edit-form"){
      await api("/api/chat-notes/categories/save", {
        category_id: form.dataset.id,
        name: values.name
      });
      $("modal").close();
      await manageNotesTaxonomyModal("categories");
      notice("記事分類已更新。");
      return;
    }else if(form.id==="tax-category-merge-form"){
      await api("/api/chat-notes/categories/merge", {
        source_category_id: form.dataset.source,
        target_category_id: values.target_category_id
      });
      $("modal").close();
      await manageNotesTaxonomyModal("categories");
      notice("記事分類已合併轉移。");
      return;
    }else if(form.id==="tax-tag-create-form"){
      await api("/api/chat-notes/tags/save", {
        name: values.name,
        color: values.color || "#007AFF"
      });
      $("modal").close();
      await manageNotesTaxonomyModal("tags");
      notice("記事標籤已新增。");
      return;
    }else if(form.id==="tax-tag-edit-form"){
      await api("/api/chat-notes/tags/save", {
        tag_id: form.dataset.id,
        name: values.name,
        color: values.color || "#007AFF",
        old_name: form.dataset.oldName
      });
      $("modal").close();
      await manageNotesTaxonomyModal("tags");
      notice("記事標籤已更新。");
      return;
    }else if(form.id==="tax-tag-merge-form"){
      await api("/api/chat-notes/tags/merge", {
        source_tag_id: form.dataset.source,
        target_tag_id: values.target_tag_id
      });
      $("modal").close();
      await manageNotesTaxonomyModal("tags");
      notice("同義記事標籤已合併。");
      return;
    }else if(form.id==="org-notes-policy-form"){
      await api("/api/org-settings/notes-policy", {
        org_id: form.dataset.org,
        note_lock_policy: values.note_lock_policy,
        note_tag_policy: values.note_tag_policy
      });
      await load();
      render();
      notice("記事本治理政策已儲存。");
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
        template_id: form.dataset.id || undefined,
        template_type: form.dataset.type,
        name: values.name,
        category_name: values.category_name || "一般",
        title: values.title || "",
        body: values.body || ""
      });
      $("modal").close();
      await loadTemplatesTabContent();
      notice(form.dataset.id ? "範本已更新。" : "範本已建立。");
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
        work_department:values.work_department||"",
        phone:values.phone||"",
        email:values.email||"",
        work_phone:values.work_phone||"",
        work_phone_ext:values.work_phone_ext||"",
        work_email:values.work_email||"",
        postal_code:values.postal_code||"",
        address:values.address||"",
        notes:values.notes||"",
        tag_ids
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
    }
    else if(form.id==="organization-form")await api('/api/organizations/save',{...values,org_id:form.dataset.id||undefined,...Object.fromEntries(['active','messaging_enabled','duty_enabled','forms_enabled'].map(k=>[k,form.elements[k].checked]))});
    else if(form.id==="membership-form")await api('/api/memberships/save',{...values,active:form.elements.active.checked});
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
    }else if(form.id==="chat-sticker-reply-form"){
      const status=form.querySelector('[data-sticker-reply-status]'),enabled=form.elements.sticker_reply_enabled.checked;
      form.elements.sticker_reply_enabled.disabled=true;
      status.textContent='儲存中…';submit.textContent='儲存中…';
      try{
        await api('/api/chat/response-hours/save',{sticker_reply_enabled:enabled});
        status.textContent=enabled?'已儲存 · 貼圖自動回覆已啟用':'已儲存 · 貼圖自動回覆已關閉';
        submit.textContent='已儲存';notice(status.textContent);
      }catch(error){status.textContent='儲存失敗：'+error.message;submit.textContent='重試儲存';throw error;}
      finally{submit.disabled=false;form.elements.sticker_reply_enabled.disabled=false;}
      return;
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
  }catch(error){if(form.classList.contains("duty-grant-form")){notice(error.message,true);}else{$("modal-error").textContent=error.message;$("modal-error").hidden=false;}submit.disabled=false;}
});
function closeModalSafely(){
  const form = document.querySelector("#modal form");
  if(form && form.dataset.dirty === "true"){
    if(!confirm("您有尚未儲存的變更，確定要放棄修改並離開嗎？")){
      return false;
    }
  }
  $("modal").close();
  return true;
}

$("modal-close").addEventListener("click", () => {
  closeModalSafely();
});

$("modal").addEventListener("cancel", (event) => {
  if(!closeModalSafely()){
    event.preventDefault();
  }
});

document.addEventListener("input", event => {
  if(event.target.id === "notes-hub-search"){
    state.noteHubQuery = event.target.value;
    if(state.view === "chat-notes") loadGlobalChatNotes();
  }
});

document.addEventListener("change", event => {
  if(event.target.id === "notes-hub-sort"){state.noteHubSort=event.target.value;$("global-notes-content").innerHTML=renderGlobalNotesBody();return;}
  if(event.target.id === "notes-hub-category-filter"){
    state.noteHubCategory = event.target.value;
    if(state.view === "chat-notes") loadGlobalChatNotes();
  } else if(event.target.id === "notes-hub-tag-filter"){
    state.noteHubTag = event.target.value;
    if(state.view === "chat-notes") loadGlobalChatNotes();
  } else if(event.target.id === "notes-hub-status-filter"){
    state.noteHubStatus = event.target.value;
    if(state.view === "chat-notes") loadGlobalChatNotes();
  } else if(event.target.id === "notes-hub-channel-filter"){
    state.noteHubChannel = event.target.value;
    if(state.view === "chat-notes") loadGlobalChatNotes();
  }
});
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
$("refresh").addEventListener("click",async()=>{if(state.busy||!formCanLeave())return;$("refresh").disabled=true;try{await load();render();notice("資料已更新。");await recoverSubmission();}catch(error){notice(error.message,true);}finally{$("refresh").disabled=false;}});
async function boot(){try{await load();render();await recoverSubmission();}catch(error){$("page").innerHTML=empty("暫時無法開啟工作台",remote?"請重新整理登入，或聯絡管理員確認帳號已啟用。":"請確認 LINE 服務已更新並啟動，再從控制台重新開啟管理頁。");notice(error.message,true);$("connection").textContent="連線未完成";}}
boot();
let polling=false;
setInterval(async()=>{if(!state.loaded||!lineUI.ready||!lineDataReady()||!admin()||state.busy||state.authLost||document.hidden||polling||$("modal").open)return;polling=true;const requestedOA=lineUI.channel;try{const result=await api('/api/jobs');if(requestedOA!==lineUI.channel)return;if(JSON.stringify(result.jobs)!==JSON.stringify(state.jobs)){state.jobs=result.jobs;if(['overview','history','schedule'].includes(state.view)){const opened=[...document.querySelectorAll('[data-job][open]')].map(el=>el.dataset.job);render();document.querySelectorAll('[data-job]').forEach(el=>{el.open=opened.includes(el.dataset.job);});}}}catch(error){notice(error.message,true);}finally{polling=false;}},6000);

// Handle unreadable image content without leaving a broken thumbnail.
document.addEventListener("error",event=>{if(event.target instanceof HTMLImageElement && (event.target.classList.contains('sidebar-thumbnail') || event.target.closest('.chat-profile-avatar'))){event.target.hidden=true;return;}if(event.target instanceof HTMLImageElement && !event.target.closest('.chat-media-image') && !event.target.classList.contains('chat-img-thumb') && !event.target.classList.contains('avatar-img') && !event.target.closest('.avatar') && !event.target.closest('.chat-room-avatar')){const replacement=document.createElement("p");replacement.className="callout warn";replacement.textContent="圖片無法顯示，請確認檔案格式後重新上傳。";event.target.replaceWith(replacement);}},true);

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

document.addEventListener('click',event=>{
  if(!event.target.closest('#oa-switcher-dropdown,#workspace-context'))closeOaSwitcher();
});
document.addEventListener('keydown',event=>{
  if(event.target.closest('#workspace-context') && ['Enter',' '].includes(event.key)){
    event.preventDefault();toggleOaSwitcher();return;
  }
  const dropdown=$('oa-switcher-dropdown');
  if(!dropdown)return;
  if(event.key==='Escape'){event.preventDefault();closeOaSwitcher(true);return;}
  if(event.target.closest('#oa-switcher-dropdown') && ['ArrowDown','ArrowUp'].includes(event.key)){
    const items=[...dropdown.querySelectorAll('.oa-switcher-item:not([hidden])')];
    if(!items.length)return;
    event.preventDefault();const current=items.indexOf(document.activeElement);
    items[(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length].focus();
  }
});
document.addEventListener('focusin',event=>{
  if(!event.target.closest('#oa-switcher-dropdown,#workspace-context'))closeOaSwitcher();
});
window.addEventListener('resize',()=>closeOaSwitcher());

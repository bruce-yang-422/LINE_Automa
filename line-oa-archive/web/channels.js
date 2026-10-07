"use strict";
const lineUI={ready:false,registry:false,spaces:[],channels:[],workspace:"",channel:"",key:""};
const selectedOA=()=>lineUI.channels.find(c=>c.channel_id===lineUI.channel);
const selectedWorkspace=()=>lineUI.spaces.find(w=>w.id===lineUI.workspace);
// 所有營運資料都屬於某個 OA；尚未選定啟用中的 OA 時不讀取。
const lineDataReady=()=>Boolean(selectedOA()?.active);

async function loadChannels(){
  const previousChannel=lineUI.channel;
  const data=await api('/api/channels');
  lineUI.registry=data.registry_enabled;lineUI.spaces=data.workspaces;lineUI.channels=data.channels;
  state.channels=data.channels || [];
  lineUI.key='lineOA:'+state.session.identity+':'+(previewOrganization||'');
  let saved={};try{saved=JSON.parse(sessionStorage.getItem(lineUI.key)||'{}');}catch(_){}
  const scopedWorkspace=state.session.role!=="platform_admin"?lineUI.spaces.find(w=>w.org_id===state.session.user.organization_id):null;
  lineUI.workspace=scopedWorkspace?.id||(lineUI.spaces.some(w=>w.id===saved.workspace)?saved.workspace:(lineUI.channels.find(c=>c.active)?.workspace_id||lineUI.spaces[0]?.id||''));
  const available=lineUI.channels.filter(c=>c.workspace_id===lineUI.workspace&&c.active);
  lineUI.channel=available.some(c=>c.channel_id===saved.channel)?saved.channel:(available[0]?.channel_id||'');
  if(previousChannel&&previousChannel!==lineUI.channel){
    state.report=null;state.step=1;state.selected.clear();state.textDraft='';
    messageDraft.items=[];messageDraft.organization_id='';
  }
  lineUI.ready=true;
  if(lineUI.channel)state.session=await api('/api/session');
  if(lineUI.registry&&!messageDraft.items.length)messageDraft.organization_id=selectedWorkspace()?.org_id||"";
  // 頂欄採用統一現代化圖形切換器（workspace-context），隱藏舊版原生下拉選單
  const oldContext = document.getElementById('line-context');
  if(oldContext) oldContext.hidden = true;
  if(document.getElementById('line-workspace-select')) document.getElementById('line-workspace-select').innerHTML=options(lineUI.spaces.map(w=>[w.id,w.name]),lineUI.workspace);
  if(document.getElementById('line-oa-select')) document.getElementById('line-oa-select').innerHTML=options(available.length?available.map(c=>[c.channel_id,c.name]):[['','尚未設定 OA']],lineUI.channel);
}

function changeLineContext(workspace,channel){
  if(!formCanLeave())return;
  if(state.busy||sessionStorage.getItem('linePendingJob')){notice('請先確認這次提交的結果，再切換 OA。',true);return;}
  const draft=state.report||state.textDraft||messageDraft.items.length||document.getElementById('message-draft')?.value||document.querySelector('#composer-file-preview img');
  if(draft&&!window.confirm('切換 OA 會清除本頁尚未送出的內容與勾選對象。是否切換？'))return;
  sessionStorage.setItem(lineUI.key,JSON.stringify({workspace,channel}));
  const nextWorkspace=lineUI.spaces.find(w=>w.id===workspace);
  if(!state.session.preview&&state.session.role!=="platform_admin"&&nextWorkspace?.org_id)localStorage.setItem(organizationKey,nextWorkspace.org_id);
  // Navigation discards pending reads, selected recipients and drafts from the previous OA.
  location.replace('/?view='+(['settings','organizations','channels','duty'].includes(state.view)?state.view:'overview'));
}

function channelsPage(){
  const w=selectedWorkspace(),rows=lineUI.channels.filter(c=>c.workspace_id===lineUI.workspace);
  const orgPicker=superAdmin()?`<label class="field oa-org-picker">組織<select id="channels-org-select" aria-label="選擇組織">${options(lineUI.spaces.map(s=>[s.id,s.name]),lineUI.workspace)}</select></label>`:'';
  return heading('LINE OA 管理',superAdmin()?'選擇組織，設定該組織的 LINE 官方帳號連線。':'一個組織可以連結多個 OA。',
    orgPicker+(w?.can_manage?'<button class="btn primary" data-line-action="add">'+icon('plus')+'新增 LINE OA</button>':''))+
    `<section class="panel panel-body"><div class="oa-section-heading"><div><h2>${esc(w?.name||'選擇工作區')}</h2><p class="subtitle">依組織角色與發送範圍授權。</p></div>${badge(rows.length+' 個 OA')}</div>
    <div class="oa-grid">${rows.map(oaCard).join('')||empty('這個工作區還沒有 OA',w?.can_manage?'新增 OA 後，就能接收訊息、管理名單與建立發送。':'請管理員先連結 LINE OA。')}</div></section>
    <section class="panel panel-body section-space"><h2>連結完成後</h2><ol class="oa-steps"><li>在 LINE Developers 設定這個 OA 的 Webhook URL，按「Verify」，再開啟 Use webhook。</li><li>用 LINE 傳一則訊息給該 OA，確認「Webhook 最近到達」與聯絡對象名單更新。</li><li>建立發送時，先確認頂端 OA；預約也會固定使用當時選擇的 OA。</li></ol><p class="subtitle">驗證連線只讀取官方帳號資料，不會傳送測試訊息。停用 OA 會停止收訊與尚未執行的發送，資料仍保留。</p>
    <p class="subtitle">共用：平台管理員可把 OA 共用給其他工作區，再由擁有者指派各工作區能使用的聯絡對象。各工作區的發送紀錄與排程分開，但 LINE 訊息額度與 LINE 使用者看到的 OA 名稱是同一個。</p></section>`;
}

function oaCard(c){
  const current=c.channel_id===lineUI.channel;
  const use=c.active&&!superAdmin()?`<button class="btn ${current?'':'primary'}" data-line-action="use" data-id="${c.channel_id}" ${current?'disabled':''}>${current?'目前使用':'使用此 OA'}</button>`:'';
  const head=`<div class="oa-card-heading"><span class="avatar">${icon('send')}</span><div><h3>${esc(c.name)}</h3><p class="subtitle">${esc(c.basic_id||'LINE 官方帳號')}</p></div>${c.shared?badge('共用'):''}${badge(c.active?'啟用中':'已停用',c.active?'good':'')}</div>`;
  if(c.shared)return `<article class="oa-card">${head}<p class="callout">由「${esc(c.owner_workspace_name)}」共用。憑證、Webhook 與可用聯絡對象由擁有者管理；這裡的發送紀錄與排程只屬於本工作區。</p><div class="oa-actions">${use}</div></article>`;
  const shares=c.shares?`<div class="oa-shares"><h4>共用給其他工作區</h4>${c.shares.map(s=>`<div class="oa-share-row"><strong>${esc(s.workspace_name)}</strong>${badge(s.active?s.recipients+' 位聯絡對象':'已暫停',s.active?'':'warn')}${s.active?`<button class="btn small" data-line-action="assign" data-id="${s.share_id}">指派聯絡對象</button>`:''}${superAdmin()?`<button class="btn small text ${s.active?'danger':''}" data-line-action="share-active" data-id="${c.channel_id}" data-workspace="${esc(s.workspace_id)}" data-active="${!s.active}">${s.active?'暫停共用':'恢復共用'}</button>`:''}</div>`).join('')||'<p class="subtitle">尚未共用給其他工作區。</p>'}</div>`:'';
  return `<article class="oa-card">${head}
    <dl class="oa-meta"><dt>API 最近驗證</dt><dd>${esc(when(c.verified_at))}</dd><dt>Webhook 最近到達</dt><dd>${c.webhook_seen_at?esc(when(c.webhook_seen_at)):'等待 LINE 驗證或新訊息'}</dd></dl>
    <label class="field">Webhook URL<input readonly value="${esc(c.webhook_url)}" aria-label="${esc(c.name)} Webhook URL"></label>
    <p class="subtitle">將此網址貼到 LINE Developers 的 Messaging API 設定。</p>
    <div class="oa-actions">${use}${c.can_manage?`<button class="btn" data-line-action="verify" data-id="${c.channel_id}">驗證連線</button><button class="btn" data-line-action="edit" data-id="${c.channel_id}">設定憑證</button>`:''}${c.can_manage&&superAdmin()?`<button class="btn" data-line-action="share" data-id="${c.channel_id}">共用給工作區</button><button class="btn" data-line-action="transfer" data-id="${c.channel_id}">移轉歸屬</button>`:''}${c.can_manage?`<button class="btn text ${c.active?'danger':''}" data-line-action="active" data-id="${c.channel_id}">${c.active?'停用':'啟用'}</button>`:''}</div>${shares}</article>`;
}

// Workspaces that may receive this OA: not the owner and not already sharing it.
function otherSpaces(c){
  const taken=new Set([c.workspace_id,...(c.shares||[]).map(s=>s.workspace_id)]);
  return lineUI.spaces.filter(w=>!taken.has(w.id)).map(w=>[w.id,w.name]);
}

function shareForm(id){
  const c=lineUI.channels.find(c=>c.channel_id===id),spaces=otherSpaces(c);
  modal('共用 LINE OA',`<form id="line-share-form" data-id="${esc(id)}"><p class="subtitle">「${esc(c.name)}」歸屬於 ${esc(c.workspace_name)}。共用後，對方工作區可以選用這個 OA 發送，但只看得到你指派的聯絡對象；憑證與 Webhook 仍由擁有者管理。</p>
    ${spaces.length?selectField('共用給','workspace_id',spaces,spaces[0][0]):'<p class="callout">沒有其他可共用的工作區。</p>'}
    <p class="subtitle">LINE 訊息額度與 LINE 使用者看到的 OA 名稱由所有共用工作區共同使用。</p>
    <div class="form-actions"><button type="submit" class="btn primary" ${spaces.length?'':'disabled'}>共用並指派聯絡對象</button></div></form>`);
}

async function assignForm(shareId){
  const data=await api('/api/channels/shares/'+shareId);
  const items=data.recipients.map(r=>[r.recipient_id,`${label(r)} · ${r.kind==='user'?'個人':'群組'}${r.active?'':' · 已封鎖或離開'}`]);
  modal('指派聯絡對象',`<form id="line-assign-form" data-share="${esc(shareId)}"><p class="subtitle">勾選「${esc(data.workspace_name)}」可以看到並發送的「${esc(data.oa_name)}」聯絡對象。取消勾選會移除該工作區的這位聯絡對象與其分類、備註；你的名單不受影響。</p>
    <fieldset class="permission-fieldset"><legend>聯絡對象（${items.length}）</legend>${checkChoices('recipient_ids',items,data.recipients.filter(r=>r.assigned).map(r=>r.recipient_id))}</fieldset>
    <div class="form-actions"><button type="button" class="btn" data-line-action="assign-all">全選</button><button type="submit" class="btn primary">儲存指派</button></div></form>`);
}

function transferForm(id){
  const c=lineUI.channels.find(c=>c.channel_id===id),spaces=otherSpaces(c);
  modal('移轉 OA 歸屬',`<form id="line-transfer-form" data-id="${esc(id)}"><p class="subtitle">「${esc(c.name)}」目前歸屬 ${esc(c.workspace_name)}。移轉後由新工作區管理憑證、Webhook 與共用；Webhook 網址不變。</p>
    ${spaces.length?selectField('移轉到','workspace_id',spaces,spaces[0][0]):'<p class="callout">沒有其他可移轉的工作區。</p>'}
    <div id="transfer-impact"></div>
    <div class="form-actions"><button type="submit" class="btn primary" ${spaces.length?'':'disabled'}>檢查影響</button></div></form>`);
}

function transferImpact(r){
  return `<div class="callout"><strong>${esc(r.from)} → ${esc(r.to)}</strong><ul>
    <li>聯絡對象 ${r.recipients} 位、素材 ${r.assets} 個、發送紀錄 ${r.jobs} 筆會跟著移轉；聯絡對象的部門分類會清除。</li>
    ${r.shares?`<li>目前共用給 ${r.shares} 個工作區，共用設定保留。</li>`:''}
    ${r.pending_jobs?`<li><strong>還有 ${r.pending_jobs} 筆預約或進行中的發送，須先取消或等待完成才能移轉。</strong></li>`:''}</ul></div>`;
}

function channelForm(id){
  const c=lineUI.channels.find(c=>c.channel_id===id),w=selectedWorkspace();
  const spaces=lineUI.spaces.filter(w=>w.can_manage);
  modal(c?'設定 LINE OA':'新增 LINE OA',`<form id="line-channel-form" data-id="${esc(id||'')}"><section class="mg-section"><h3>1 · 帳號歸屬</h3>${selectField('所屬工作區','workspace_id',spaces.map(w=>[w.id,w.name]),c?.workspace_id||w?.id||'')}<p class="subtitle">建立後固定於此工作區；聯絡對象與發送紀錄會分開保存。</p>${field('顯示名稱（選填）','name',c?.name||'','maxlength="80" placeholder="留空使用 LINE OA 名稱"')}</section>
    ${`<section class="mg-section"><h3>2 · Messaging API 憑證</h3><p class="subtitle">到 LINE Developers → 此 OA 的 Channel。Secret 與 Token 必須來自同一個 OA。${c?'不更換的欄位留空即可。':''}</p>${field('Channel secret','secret','','type="password" autocomplete="new-password" maxlength="32" '+(c?'':'required'))}${field('Channel access token','access_token','','type="password" autocomplete="new-password" maxlength="4096" '+(c?'':'required'))}<p class="subtitle">儲存前會向 LINE 查驗 Token 的 OA 身分；Secret 要在 LINE Developers 按 Verify 驗證。</p></section>`}
    <div class="form-actions"><button type="submit" class="btn primary">驗證並儲存</button></div></form>`);
  if(c){const el=document.querySelector('#line-channel-form [name="workspace_id"]');el.disabled=true;}
}

document.addEventListener('change',event=>{
  if(event.target.id==='line-workspace-select'||event.target.id==='channels-org-select')changeLineContext(event.target.value,'');
  if(event.target.id==='line-oa-select')changeLineContext(lineUI.workspace,event.target.value);
});
document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-line-action]');if(!el||el.disabled)return;
  const action=el.dataset.lineAction,id=el.dataset.id,c=lineUI.channels.find(c=>c.channel_id===id);
  try{
    if(action==='add'||action==='edit'){channelForm(id);return;}
    if(action==='use'){changeLineContext(c.workspace_id,id);return;}
    if(action==='share'){shareForm(id);return;}
    if(action==='transfer'){transferForm(id);return;}
    if(action==='assign-all'){el.closest('form').querySelectorAll('[name="recipient_ids"]').forEach(box=>box.checked=true);return;}
    el.disabled=true;
    if(action==='assign'){await assignForm(id);return;}
    if(action==='share-active'){
      const active=el.dataset.active==='true';
      if(!active&&!window.confirm('暫停後對方工作區暫時不能使用這個 OA，已指派的聯絡對象與紀錄會保留。是否暫停？'))return;
      await api('/api/channels/share',{channel_id:id,workspace_id:el.dataset.workspace,active});await load();render();notice(active?'已恢復共用。':'已暫停共用。');
    }
    if(action==='verify'){
      el.textContent = '驗證中...';
      el.disabled = true;
      try {
        const r = await api('/api/channels/verify', {channel_id: id});
        await load();
        render();
        notice(`連線成功！OA：${r.name || 'LINE 官方帳號'}（${r.note}）`);
      } catch(err) {
        notice(`連線驗證失敗：${err.message}`, true);
      } finally {
        el.disabled = false;
      }
      return;
    }
    if(action==='active'){
      if(c.active&&!window.confirm(`停用「${c.name}」後將停止收訊與未執行的發送，資料仍保留。是否停用？`))return;
      await api('/api/channels/active',{channel_id:id,active:!c.active});await load();render();notice('OA 狀態已更新。');
    }
  }catch(error){notice(error.message,true);}finally{el.disabled=false;}
});
const modalError=message=>{const box=document.getElementById('modal-error');box.textContent=message;box.hidden=false;};
document.addEventListener('submit',async event=>{
  const form=event.target;if(!['line-share-form','line-assign-form','line-transfer-form'].includes(form.id))return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');submit.disabled=true;
  try{
    if(form.id==='line-share-form'){
      const result=await api('/api/channels/share',{channel_id:form.dataset.id,workspace_id:form.elements.workspace_id.value,active:true});
      await load();render();await assignForm(result.share_id);notice('已共用。請勾選對方可以使用的聯絡對象。');return;
    }
    if(form.id==='line-assign-form'){
      const ids=[...form.querySelectorAll('[name="recipient_ids"]:checked')].map(box=>box.value);
      const result=await api('/api/channels/assign',{share_id:form.dataset.share,recipient_ids:ids});
      document.getElementById('modal').close();await load();render();notice(`已指派 ${result.assigned} 位聯絡對象（新增 ${result.added}、移除 ${result.removed}）。`);return;
    }
    const payload={channel_id:form.dataset.id,workspace_id:form.elements.workspace_id.value};
    if(form.dataset.stage!=='confirm'){
      const impact=await api('/api/channels/transfer',payload);
      document.getElementById('transfer-impact').innerHTML=transferImpact(impact);
      form.elements.workspace_id.disabled=true;
      if(!impact.pending_jobs){form.dataset.stage='confirm';submit.textContent='確認移轉';submit.classList.add('danger');submit.disabled=false;}
      return;
    }
    const result=await api('/api/channels/transfer',{...payload,confirm:true});
    document.getElementById('modal').close();
    if(lineUI.channel===result.channel_id)sessionStorage.setItem(lineUI.key,JSON.stringify({workspace:result.workspace_id,channel:result.channel_id}));
    await load();render();notice(`已移轉到「${result.to}」。`);
  }catch(error){modalError(error.message);submit.disabled=false;}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(form.id!=='line-channel-form')return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');submit.disabled=true;
  const values=Object.fromEntries(new FormData(form)),c=lineUI.channels.find(c=>c.channel_id===form.dataset.id);
  try{
    const result=await api('/api/channels/save',{...values,workspace_id:c?.workspace_id||values.workspace_id,channel_id:c?.channel_id,active:c?Boolean(c.active):true});
    form.reset();document.getElementById('modal').close();
    sessionStorage.setItem(lineUI.key,JSON.stringify({workspace:result.workspace_id,channel:result.channel_id}));
    await load();render();notice('OA 已儲存。請在 LINE Developers 驗證 Webhook，確認 Secret 與接收網址。');
  }catch(error){document.getElementById('modal-error').textContent=error.message;document.getElementById('modal-error').hidden=false;submit.disabled=false;}
});

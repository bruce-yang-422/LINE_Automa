"use strict";
const lineUI={ready:false,registry:false,spaces:[],channels:[],workspace:"",channel:"",key:"",canImport:false};
const selectedOA=()=>lineUI.channels.find(c=>c.channel_id===lineUI.channel);
const selectedWorkspace=()=>lineUI.spaces.find(w=>w.id===lineUI.workspace);
const lineDataReady=()=>!lineUI.registry||Boolean(selectedOA()?.active);

async function loadChannels(){
  const previousChannel=lineUI.channel;
  const data=await api('/api/channels');
  lineUI.registry=data.registry_enabled;lineUI.spaces=data.workspaces;lineUI.channels=data.channels;lineUI.canImport=data.can_import;
  lineUI.key='lineOA:'+state.session.identity+':'+(previewOrganization||'');
  let saved={};try{saved=JSON.parse(sessionStorage.getItem(lineUI.key)||'{}');}catch(_){}
  lineUI.workspace=lineUI.spaces.some(w=>w.id===saved.workspace)?saved.workspace:(lineUI.channels.find(c=>c.active)?.workspace_id||lineUI.spaces[0]?.id||'');
  const available=lineUI.channels.filter(c=>c.workspace_id===lineUI.workspace&&c.active);
  lineUI.channel=available.some(c=>c.channel_id===saved.channel)?saved.channel:(available[0]?.channel_id||'');
  if(previousChannel&&previousChannel!==lineUI.channel){
    state.report=null;state.step=1;state.selected.clear();state.previews.clear();state.textDraft='';
    messageDraft.items=[];messageDraft.company='';
  }
  lineUI.ready=true;
  if(lineUI.channel)state.session=await api('/api/session');
  if(lineUI.registry&&!messageDraft.items.length)messageDraft.company=selectedWorkspace()?.org_id||"";
  document.getElementById('line-context').hidden=!lineUI.registry&&!superAdmin();
  document.getElementById('line-workspace-select').innerHTML=options(lineUI.spaces.map(w=>[w.id,w.name]),lineUI.workspace);
  document.getElementById('line-oa-select').innerHTML=options(available.length?available.map(c=>[c.channel_id,c.name]):[['','尚未設定 OA']],lineUI.channel);
}

function changeLineContext(workspace,channel){
  if(state.busy||sessionStorage.getItem('linePendingJob')){notice('請先確認這次提交的結果，再切換 OA。',true);return;}
  const draft=state.report||state.textDraft||messageDraft.items.length||document.getElementById('message-draft')?.value||document.querySelector('#composer-file-preview img');
  if(draft&&!window.confirm('切換 OA 會清除本頁尚未送出的內容與勾選對象。是否切換？'))return;
  sessionStorage.setItem(lineUI.key,JSON.stringify({workspace,channel}));
  // Navigation discards pending reads, selected recipients and drafts from the previous OA.
  location.replace('/?view='+(['settings','organizations','channels'].includes(state.view)?state.view:'overview'));
}

function channelsPage(){
  const w=selectedWorkspace(),rows=lineUI.channels.filter(c=>c.workspace_id===lineUI.workspace);
  return heading('LINE OA 管理','一個工作區可以連結多個 OA。先選擇工作區，再設定要使用的官方帳號。',
    w?.can_manage&&!lineUI.canImport?'<button class="btn primary" data-line-action="add">'+icon('plus')+'新增 LINE OA</button>':'')+
    `<section class="panel panel-body"><div class="oa-section-heading"><div><h2>${esc(w?.name||'選擇工作區')}</h2><p class="subtitle">${w?.kind==='personal'?'個人工作區：由本人與平台管理員管理。':'組織工作區：依組織角色與發送範圍授權。'}</p></div>${badge(rows.length+' 個 OA')}</div>
    ${lineUI.canImport?'<div class="callout oa-import"><div><strong>接續目前使用的 OA</strong><p>匯入伺服器已設定的 OA、收件者與紀錄；保留原本的 Webhook 網址。歸屬將固定在你選擇的工作區。</p></div><button class="btn primary" data-line-action="import">匯入既有 OA</button></div>':''}
    <div class="oa-grid">${rows.map(c=>`<article class="oa-card"><div class="oa-card-heading"><span class="avatar">${icon('send')}</span><div><h3>${esc(c.name)}</h3><p class="subtitle">${esc(c.basic_id||'LINE 官方帳號')}</p></div>${badge(c.active?'啟用中':'已停用',c.active?'good':'')}</div>
    <dl class="oa-meta"><dt>API 最近驗證</dt><dd>${esc(when(c.verified_at))}</dd><dt>Webhook 最近到達</dt><dd>${c.webhook_seen_at?esc(when(c.webhook_seen_at)):'等待 LINE 驗證或新訊息'}</dd></dl>
    <label class="field">Webhook URL<input readonly value="${esc(c.webhook_url)}" aria-label="${esc(c.name)} Webhook URL"></label>
    <p class="subtitle">${c.legacy_webhook?'原本的 /webhook 入口仍可使用。':'將此網址貼到 LINE Developers 的 Messaging API 設定。'}</p>
    <div class="oa-actions">${c.active?`<button class="btn ${c.channel_id===lineUI.channel?'':'primary'}" data-line-action="use" data-id="${c.channel_id}" ${c.channel_id===lineUI.channel?'disabled':''}>${c.channel_id===lineUI.channel?'目前使用':'使用此 OA'}</button>`:''}${c.can_manage?`<button class="btn" data-line-action="verify" data-id="${c.channel_id}">驗證連線</button><button class="btn" data-line-action="edit" data-id="${c.channel_id}">設定憑證</button><button class="btn text ${c.active?'danger':''}" data-line-action="active" data-id="${c.channel_id}">${c.active?'停用':'啟用'}</button>`:''}</div></article>`).join('')||empty('這個工作區還沒有 OA',w?.can_manage?'新增或匯入 OA 後，就能接收訊息、管理名單與建立發送。':'請組織管理員先連結 LINE OA。')}</div></section>
    <section class="panel panel-body section-space"><h2>連結完成後</h2><ol class="oa-steps"><li>在 LINE Developers 設定這個 OA 的 Webhook URL，按「Verify」，再開啟 Use webhook。</li><li>用 LINE 傳一則訊息給該 OA，確認「Webhook 最近到達」與收件者名單更新。</li><li>建立發送時，先確認頂端 OA；預約也會固定使用當時選擇的 OA。</li></ol><p class="subtitle">驗證連線只讀取官方帳號資料，不會傳送測試訊息。停用 OA 會停止收訊與尚未執行的發送，資料仍保留。</p></section>`;
}

function channelForm(id,importing=false){
  const c=lineUI.channels.find(c=>c.channel_id===id),w=selectedWorkspace();
  const spaces=lineUI.spaces.filter(w=>w.can_manage);
  modal(importing?'匯入既有 LINE OA':c?'設定 LINE OA':'新增 LINE OA',`<form id="line-channel-form" data-id="${esc(id||'')}" data-import="${importing}"><section class="mg-section"><h3>1 · 帳號歸屬</h3>${selectField('所屬工作區','workspace_id',spaces.map(w=>[w.id,w.name]),c?.workspace_id||w?.id||'')}<p class="subtitle">建立後固定於此工作區；收件者、報告與發送紀錄會分開保存。</p>${field('顯示名稱（選填）','name',c?.name||'','maxlength="80" placeholder="留空使用 LINE OA 名稱"')}</section>
    ${importing?'<p class="callout">將使用伺服器既有憑證，不需重新輸入。現有資料不會清除。</p>':`<section class="mg-section"><h3>2 · Messaging API 憑證</h3><p class="subtitle">到 LINE Developers → 此 OA 的 Channel。Secret 與 Token 必須來自同一個 OA。${c?'不更換的欄位留空即可。':''}</p>${field('Channel secret','secret','','type="password" autocomplete="new-password" maxlength="32" '+(c?'':'required'))}${field('Channel access token','access_token','','type="password" autocomplete="new-password" maxlength="4096" '+(c?'':'required'))}<p class="subtitle">儲存前會向 LINE 查驗 Token 的 OA 身分；Secret 要在 LINE Developers 按 Verify 驗證。</p></section>`}
    <div class="form-actions"><button type="submit" class="btn primary">${importing?'確認歸屬並匯入':'驗證並儲存'}</button></div></form>`);
  if(c){const el=document.querySelector('#line-channel-form [name="workspace_id"]');el.disabled=true;}
}

document.addEventListener('change',event=>{
  if(event.target.id==='line-workspace-select')changeLineContext(event.target.value,'');
  if(event.target.id==='line-oa-select')changeLineContext(lineUI.workspace,event.target.value);
});
document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-line-action]');if(!el||el.disabled)return;
  const action=el.dataset.lineAction,id=el.dataset.id,c=lineUI.channels.find(c=>c.channel_id===id);
  try{
    if(action==='add'||action==='import'||action==='edit'){channelForm(id,action==='import');return;}
    if(action==='use'){changeLineContext(c.workspace_id,id);return;}
    el.disabled=true;
    if(action==='verify'){const r=await api('/api/channels/verify',{channel_id:id});await load();render();notice(r.note);}
    if(action==='active'){
      if(c.active&&!window.confirm(`停用「${c.name}」後將停止收訊與未執行的發送，資料仍保留。是否停用？`))return;
      await api('/api/channels/active',{channel_id:id,active:!c.active});await load();render();notice('OA 狀態已更新。');
    }
  }catch(error){notice(error.message,true);}finally{el.disabled=false;}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(form.id!=='line-channel-form')return;event.preventDefault();
  const submit=form.querySelector('[type="submit"]');submit.disabled=true;
  const values=Object.fromEntries(new FormData(form)),c=lineUI.channels.find(c=>c.channel_id===form.dataset.id);
  try{
    const result=await api('/api/channels/save',{...values,workspace_id:c?.workspace_id||values.workspace_id,channel_id:c?.channel_id,active:c?Boolean(c.active):true,import_existing:form.dataset.import==='true'});
    form.reset();document.getElementById('modal').close();
    sessionStorage.setItem(lineUI.key,JSON.stringify({workspace:result.workspace_id,channel:result.channel_id}));
    await load();render();notice('OA 已儲存。請在 LINE Developers 驗證 Webhook，確認 Secret 與接收網址。');
  }catch(error){document.getElementById('modal-error').textContent=error.message;document.getElementById('modal-error').hidden=false;submit.disabled=false;}
});

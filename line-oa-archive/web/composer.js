"use strict";
// Draft images stay private until the user confirms a delivery.
const messageFormats={images:["單圖／多圖","依序傳送 1–5 張圖片"],card:["圖文卡片","圖片、標題、說明與連結按鈕"],carousel:["輪播卡片","橫向滑動，最多 12 張卡片"],imagemap:["圖文訊息","一張圖片，分區點擊不同連結"]};
const mapLayouts={one:["全圖 1 區",1],two:["左右 2 區",2],four:["四宮格",4],six:["六宮格",6]};
let messageDraft={format:"images",alt_text:"圖片訊息",organization_id:"",items:[],layout:"one",areas:[{label:"區塊 1",url:""}]};
const mapPreviewState={area:0,mode:"edit",tapped:null,cache:{}};
const composerState={tab:"compose",templateCategory:"all"};

const builtinTemplates=[
  {
    id:"tpl_announcement",
    title:"系統維護公告",
    category:"announcement",
    categoryName:"公告通知",
    format:"text",
    alt_text:"系統例行維護通知",
    text:"【系統例行維護通知】\n親愛的用戶您好：\n為提供更穩定優質的服務，本系統將於本週日 02:00 ~ 06:00 進行伺服器例行性升級維護。\n維護期間將暫時停止服務，造成不便敬請見諒。\n若有任何緊急事項，請隨時聯繫客服中心。",
    badge:"系統公告"
  },
  {
    id:"tpl_promo",
    title:"限時特惠促銷",
    category:"promotion",
    categoryName:"活動促銷",
    format:"card",
    alt_text:"本季限時尊榮特惠活動",
    cardTitle:"✨ 本季限時尊榮特惠",
    cardText:"感謝您一直以來的支持！即日起至本月底，全館指定商品享專屬 85 折優惠，數量有限，售完為止。",
    cardLabel:"立即領取優惠",
    cardUrl:"https://line.me/R/ti/p/@example",
    badge:"熱門優惠"
  },
  {
    id:"tpl_event",
    title:"活動與會議提醒",
    category:"event",
    categoryName:"會議活動",
    format:"text",
    alt_text:"線上交流會即將開始提醒",
    text:"【活動即將開始提醒】\n您好！提醒您報名的「LINE 商業自動化交流會」將於明日 14:00 準時開始。\n📍 會議連結：https://meet.google.com/abc-defg-hij\n建議提早 5 分鐘進入會議室測試設備，期待您的參與！",
    badge:"活動提醒"
  },
  {
    id:"tpl_greeting",
    title:"日常問候與關懷",
    category:"greeting",
    categoryName:"客戶關懷",
    format:"text",
    alt_text:"新週問候與客戶關懷",
    text:"【週一問候】\n早安！新的一週開始了，祝福您工作順利、事事順心！\n若有任何需要協助的地方，歡迎隨時透過此官方帳號與我們聯繫 ✨",
    badge:"日常關懷"
  },
  {
    id:"tpl_summary",
    title:"每週營運重點摘要",
    category:"announcement",
    categoryName:"數據報告",
    format:"text",
    alt_text:"每週營運數據重點回顧",
    text:"【每週營運數據速報】\n本週重點指標如下：\n• 活躍客戶互動率：+18.5%\n• 訊息回覆完成率：99.2%\n• 滿意度評分：4.9 / 5.0\n詳細報告請登入後台報告中心查看完整分析。",
    badge:"業務簡報"
  }
];

function getDraftStorageKey(){
  return 'lineMsgDrafts:'+(state.session?.identity||'local')+':'+(lineUI.workspace||'default');
}
function getTemplateStorageKey(){
  return 'lineMsgTemplates:'+(state.session?.identity||'local')+':'+(lineUI.workspace||'default');
}

function loadSavedDrafts(){
  try{return JSON.parse(localStorage.getItem(getDraftStorageKey())||'[]');}catch(_){return [];}
}
function saveDraftsList(list){
  try{localStorage.setItem(getDraftStorageKey(),JSON.stringify(list));}catch(_){}
}
function loadCustomTemplates(){
  try{return JSON.parse(localStorage.getItem(getTemplateStorageKey())||'[]');}catch(_){return [];}
}
function saveCustomTemplatesList(list){
  try{localStorage.setItem(getTemplateStorageKey(),JSON.stringify(list));}catch(_){}
}

function mapLayoutPicker(draft){return `<fieldset class="map-layout-picker section-space"><legend>點擊區域版型</legend><div class="map-layout-options">${Object.entries(mapLayouts).map(([key,[label,count]])=>`<button type="button" class="map-layout-option ${draft.layout===key?'active':''}" data-action="map-layout" data-id="${key}" aria-pressed="${draft.layout===key}"><span class="layout-diagram map-${key}" aria-hidden="true">${Array.from({length:count},(_,i)=>`<span>${i+1}</span>`).join('')}</span><strong>${label}</strong></button>`).join('')}</div></fieldset>`;}

function imagemapPreview(draft,interactive){
  const simulation=interactive&&mapPreviewState.mode==='simulate',picture=draft.items[0];
  const selected=mapPreviewState.area;
  return `${interactive?`<div class="map-preview-toolbar" role="group" aria-label="圖片預覽模式">${button('編輯區域','map-mode',simulation?'small':'small dark','data-id="edit" aria-pressed="'+!simulation+'"')}${button('模擬點擊','map-mode',simulation?'small dark':'small','data-id="simulate" aria-pressed="'+simulation+'"')}</div>`:''}<div class="imagemap-preview ${picture?'':'map-placeholder'}">${picture?`<img src="${picture.preview}" alt="圖文訊息預覽">`:'<div class="map-demo-background" aria-hidden="true"></div>'}<div class="map-zones map-${draft.layout} ${simulation?'map-simulation':''}">${draft.areas.map((area,i)=>{const tag=interactive?'button':'span';return `<${tag} class="map-region ${interactive&&selected===i&&!simulation?'selected':''}" ${interactive?`type="button" data-action="map-region" data-id="${i}" aria-label="${simulation?'模擬點擊':'編輯'}區塊 ${i+1}"`:''} title="${esc(area.url||'尚未設定連結')}">${simulation?'':`<b>${i+1}</b>`}</${tag}>`;}).join('')}</div></div>${!picture?'<p class="subtitle">版型示意；選擇圖片後會直接套在圖片上。</p>':''}${interactive?`<p class="subtitle">${simulation?'點擊圖片測試各區目的地；此處只顯示連結，不會開啟網站或發送訊息。':'點擊編號區塊，直接編輯它的連結。框線與編號不會出現在實際訊息。'}</p><div class="map-feedback" role="status" aria-live="polite">${simulation?(mapPreviewState.tapped===null?'請點擊圖片上的任一區塊。':`區塊 ${mapPreviewState.tapped+1} → ${esc(draft.areas[mapPreviewState.tapped]?.url||'尚未設定連結')}`):`正在編輯區塊 ${selected+1} · ${esc(draft.areas[selected]?.url||'尚未設定連結')}`}</div>`:'<p class="subtitle">編號顯示點擊區域，實際訊息不會顯示編號。</p>'}`;
}

function composerPreview(draft,interactive=false){
  if(draft.format==="imagemap")return imagemapPreview(draft,interactive);
  if(!draft.items.length)return empty("選擇圖片，開始編輯","支援 JPG、PNG；可從這台裝置直接上傳。");
  return `<div class="composed-preview ${draft.format==='carousel'?'carousel-preview':''}">${draft.items.map((item,i)=>`<article class="line-card"><img src="${item.preview}" alt="第 ${i+1} 張：${esc(item.name||item.title)}">${['card','carousel'].includes(draft.format)?`<div class="line-card-body"><strong>${esc(item.title||"卡片標題")}</strong><p>${esc(item.text||"說明文字")}</p><span class="line-card-button">${esc(item.label||"開啟連結")}</span></div>`:""}</article>`).join("")}</div>`;
}

function composerFields(){const d=messageDraft;return d.items.map((item,i)=>`<article class="asset-editor"><div class="asset-heading"><strong>${i+1}. ${esc(item.name)}</strong><div>${button("↑","asset-up","small",`data-id="${i}" aria-label="上移第 ${i+1} 張" ${i===0?'disabled':''}`)}${button("↓","asset-down","small",`data-id="${i}" aria-label="下移第 ${i+1} 張" ${i===d.items.length-1?'disabled':''}`)}${button("移除","asset-remove","small",`data-id="${i}"`)}</div></div>${['card','carousel'].includes(d.format)?`<div class="form-grid">${field("標題","card_title_"+i,item.title,`data-card="${i}" data-prop="title" maxlength="80"`)}${field("按鈕文字","card_label_"+i,item.label,`data-card="${i}" data-prop="label" maxlength="20"`)}<label class="field full">說明<textarea data-card="${i}" data-prop="text" maxlength="500" rows="3">${esc(item.text)}</textarea></label><label class="field full">按鈕連結<input type="url" value="${esc(item.url)}" data-card="${i}" data-prop="url" maxlength="1000" placeholder="https://..."></label></div>`:""}</article>`).join("")+ (d.format==='imagemap'?`${mapLayoutPicker(d)}<div class="form-grid section-space">${d.areas.map((area,i)=>`<label class="field map-area-field ${mapPreviewState.area===i?'selected':''}" data-area-field="${i}">區塊 ${i+1} 的連結<input type="url" data-area="${i}" value="${esc(area.url)}" maxlength="1000" placeholder="https://..."></label>`).join("")}</div>`:"");}

function templatesView(){
  const custom=loadCustomTemplates();
  const all=[...builtinTemplates,...custom];
  const filtered=composerState.templateCategory==="all"?all:all.filter(t=>t.category===composerState.templateCategory);
  return `<section class="panel panel-body section-space">
    <div class="panel-head" style="padding:0 0 16px;">
      <div><h2>常用訊息範本庫</h2><p class="subtitle">選取範本一鍵套入編輯器，加速通知與訊息製作。</p></div>
      ${button(icon("plus")+"將目前內容存為新範本","save-as-template","small")}
    </div>
    <div class="segmented section-space" role="group" aria-label="範本類別">
      ${[["all","全部範本"],["announcement","公告通知"],["promotion","活動促銷"],["event","會議活動"],["greeting","客戶關懷"]].map(([id,name])=>`<button data-action="template-category" data-id="${id}" class="${composerState.templateCategory===id?'active':''}">${name}</button>`).join('')}
    </div>
    <div class="template-grid section-space">
      ${filtered.map(t=>`<article class="panel template-card">
        <div class="template-head">
          <div><span class="badge ${t.category==='promotion'?'good':t.category==='announcement'?'warn':''}">${esc(t.badge||t.categoryName||'範本')}</span><h3>${esc(t.title)}</h3></div>
          ${t.isCustom?button("✕","delete-custom-template","icon-button small",`data-id="${esc(t.id)}" title="刪除自訂範本"`):''}
        </div>
        <p class="template-preview-text">${esc(t.format==='card'?`${t.cardTitle}\n${t.cardText}`:(t.text||t.alt_text))}</p>
        <div class="template-footer">
          <small class="muted">${t.format==='card'?'圖文卡片範本':t.format==='carousel'?'輪播卡片範本':'純文字範本'}</small>
          ${button("套用此範本 →","apply-template","primary small",`data-id="${esc(t.id)}"`)}
        </div>
      </article>`).join('')}
    </div>
  </section>`;
}

function draftsView(){
  const drafts=loadSavedDrafts();
  return `<section class="panel panel-body section-space">
    <div class="panel-head" style="padding:0 0 16px;">
      <div><h2>草稿箱</h2><p class="subtitle">隨時保存編輯進度，可於多台裝置或下次登入時繼續編輯。</p></div>
      ${button("儲存目前編輯為草稿","save-current-draft","primary small")}
    </div>
    ${drafts.length?`<div class="draft-list">${drafts.map(d=>`<article class="panel draft-card">
      <div class="draft-info">
        <div class="draft-title-row">
          <span class="badge">${esc(d.format==='text'?'文字訊息':messageFormats[d.format]?.[0]||d.format)}</span>
          <strong>${esc(d.title||d.alt_text||'未命名草稿')}</strong>
        </div>
        <p class="subtitle">${esc(d.summary||d.textDraft||'圖片與互動訊息草稿')}</p>
        <small class="muted">儲存時間：${esc(when(d.savedAt))}</small>
      </div>
      <div class="draft-actions">
        ${button("載入編輯","load-draft","primary small",`data-id="${esc(d.id)}"`)}
        ${button("刪除","delete-draft","text small danger",`data-id="${esc(d.id)}"`)}
      </div>
    </article>`).join('')}</div>`:empty("目前沒有已儲存的草稿","在編輯器填寫訊息後，點擊「儲存草稿」即可暫存於此。")}
  </section>`;
}

function composerEditor(){
  const d=messageDraft;
  return `<div class="msg-nav-segmented section-space">
    <button data-action="composer-tab" data-id="compose" class="${composerState.tab==='compose'?'active':''}">${icon("send")} 訊息編輯器</button>
    <button data-action="composer-tab" data-id="templates" class="${composerState.tab==='templates'?'active':''}">${icon("file")} 常用範本庫 (${builtinTemplates.length+loadCustomTemplates().length})</button>
    <button data-action="composer-tab" data-id="drafts" class="${composerState.tab==='drafts'?'active':''}">${icon("clock")} 草稿箱 (${loadSavedDrafts().length})</button>
  </div>`+
  (composerState.tab==='templates'?templatesView():
   composerState.tab==='drafts'?draftsView():
   `<section class="panel section-space">
      <div class="panel-head">
        <div>
          <h2>圖片與互動訊息</h2>
          <p class="subtitle">選擇格式、上傳圖片或編排互動按鈕，再安排收件對象與時間。</p>
        </div>
        <div class="composer-quick-actions">
          ${button("儲存草稿","save-current-draft","small")}
          ${badge('JPG / PNG')}
        </div>
      </div>
      <div class="panel-body">
        <div class="format-picker">${Object.entries(messageFormats).map(([key,[title,note]])=>`<button class="format-option ${d.format===key?'active':''}" data-action="message-format" data-id="${key}" aria-pressed="${d.format===key}"><strong>${title}</strong><small>${note}</small></button>`).join("")}</div>
        <div class="composer-grid section-space">
          <div class="composer-controls">
            ${superAdmin()?`<label class="field">圖片所屬組織<select id="asset-company">${options(lineUI.registry?oaOrganizationOptions():[["","平台個人素材"],...organizationOptions().slice(1)],d.organization_id)}</select><small>組織素材只能傳給同組織的發送對象。</small></label>`:''}
            <label class="field section-space">${d.format==='images'?'訊息名稱（方便管理紀錄）':'通知摘要（顯示於 LINE 聊天列表）'}<input id="composition-alt" maxlength="400" value="${esc(d.alt_text)}"></label>
            <label class="upload-picker section-space">${icon('image')}<strong>點選並選擇圖片</strong><span>每張最多 8 MB，支援 JPG／PNG</span><input id="composition-files" type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" ${['images','carousel'].includes(d.format)?'multiple':''}></label>
            <p class="subtitle">上傳後會調整尺寸與壓縮，保存本次選擇的副本。${d.format==='imagemap'?'圖文訊息高寬比須介於 1:2 至 2:1。':''}</p>
            <p id="upload-status" role="status" aria-live="polite"></p>
            <div id="composition-fields">${composerFields()}</div>
          </div>
          <aside class="composer-phone">
            <p class="eyebrow">訊息預覽</p>
            <div id="composition-preview">${composerPreview(d,true)}</div>
            <p class="subtitle">版面示意；字體與裁切以 LINE 裝置顯示為準。</p>
          </aside>
        </div>
        <div class="form-actions">
          ${button("清空編輯內容","clear-composition","text small")}
          ${button("使用這則訊息 →","choose-composition","primary",`id="choose-composition" ${d.items.length?'':'disabled'}`)}
        </div>
      </div>
    </section>`);
}

function refreshComposer(){if($("composition-fields"))$("composition-fields").innerHTML=composerFields();refreshComposerPreview();if($("choose-composition"))$("choose-composition").disabled=!messageDraft.items.length;}
function refreshComposerPreview(){if($("composition-preview"))$("composition-preview").innerHTML=composerPreview(messageDraft,true);}
async function uploadFile(file,organization_id){
  if(!file||file.size>8*1024*1024)throw new Error("請選擇 8 MB 以內的 JPG／PNG。");
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('無法讀取選擇的檔案。'));reader.readAsDataURL(file);});
  return api('/api/assets/upload',{name:file.name,data,organization_id});
}
function compositionPayload(draft){return {format:draft.format,alt_text:draft.alt_text,layout:draft.layout,areas:draft.areas.map(a=>({label:a.label,url:a.url})),items:draft.items.map(({asset_id,title,text,label,url})=>({asset_id,title,text,label,url}))};}
function validateComposition(draft){
  if(!draft.items.length)throw new Error('請先選擇圖片。');
  if(!draft.alt_text.trim())throw new Error('請填寫訊息名稱或通知摘要。');
  const actions=draft.format==='imagemap'?draft.areas:['card','carousel'].includes(draft.format)?draft.items:[];
  if(['card','carousel'].includes(draft.format)&&draft.items.some(i=>!i.title.trim()))throw new Error('請填寫每張卡片的標題。');
  for(const a of actions){let url;try{url=new URL(a.url);}catch(_){throw new Error('請填寫每個按鈕／區塊的 HTTPS 連結。');}if(url.protocol!=='https:'||url.username||url.password||!a.label.trim())throw new Error('請填寫有效的 HTTPS 連結及按鈕名稱。');}
  if(draft.format==='imagemap'){const i=draft.items[0];if(i.height/i.width<.5||i.height/i.width>2)throw new Error('圖文訊息高寬比須介於 1:2 至 2:1。');}
}

function composerAction(action,id){
  if(action==='composer-tab'){
    composerState.tab=id;render();return true;
  }
  if(action==='template-category'){
    composerState.templateCategory=id;render();return true;
  }
  if(action==='apply-template'){
    const all=[...builtinTemplates,...loadCustomTemplates()];
    const t=all.find(x=>x.id===id);
    if(!t)throw new Error('找不到該範本。');
    if(t.format==='text'){
      state.textDraft=t.text||'';
      const draftEl=$('message-draft');if(draftEl)draftEl.value=t.text||'';
      notice(`已套用「${t.title}」範本至文字訊息。`);
      composerState.tab='compose';render();
      window.scrollTo({top:document.getElementById('message-draft')?.offsetTop||0,behavior:'smooth'});
    }else if(t.format==='card'){
      messageDraft.format='card';
      messageDraft.alt_text=t.alt_text||t.title;
      messageDraft.items=[{name:'範本示意圖',preview:'/assets/brand/line-automation-logo-light.png',title:t.cardTitle||t.title,text:t.cardText||'',label:t.cardLabel||'開啟連結',url:t.cardUrl||'https://line.me'}];
      composerState.tab='compose';render();
      notice(`已套用「${t.title}」圖文卡片範本，請上傳正式主圖。`);
    }
    return true;
  }
  if(action==='save-as-template'){
    const text=state.textDraft||$('message-draft')?.value||'';
    const alt=messageDraft.alt_text||'';
    if(!text.trim()&&!messageDraft.items.length)throw new Error('目前沒有可儲存為範本的內容。請先輸入文字或排版訊息。');
    const title=window.prompt('請輸入新範本名稱：',messageDraft.items.length?alt:(text.slice(0,16)||'自訂範本'));
    if(!title||!title.trim())return true;
    const custom=loadCustomTemplates();
    const isText=Boolean(text.trim())&&!messageDraft.items.length;
    const newTpl={
      id:'custom_'+Date.now(),
      title:title.trim(),
      category:'announcement',
      categoryName:'自訂範本',
      format:isText?'text':messageDraft.format,
      alt_text:isText?title.trim():messageDraft.alt_text,
      text:isText?text.trim():undefined,
      cardTitle:messageDraft.items[0]?.title||title.trim(),
      cardText:messageDraft.items[0]?.text||'',
      cardLabel:messageDraft.items[0]?.label||'開啟連結',
      cardUrl:messageDraft.items[0]?.url||'https://line.me',
      isCustom:true,
      badge:'自訂範本'
    };
    custom.unshift(newTpl);
    saveCustomTemplatesList(custom);
    notice(`已儲存「${title.trim()}」至自訂範本庫。`);
    render();
    return true;
  }
  if(action==='delete-custom-template'){
    let custom=loadCustomTemplates();
    custom=custom.filter(t=>t.id!==id);
    saveCustomTemplatesList(custom);
    notice('自訂範本已刪除。');
    render();
    return true;
  }
  if(action==='save-current-draft'){
    const text=state.textDraft||$('message-draft')?.value||'';
    if(!text.trim()&&!messageDraft.items.length&&!messageDraft.alt_text.trim())throw new Error('目前沒有可儲存的草稿內容。');
    const drafts=loadSavedDrafts();
    const title=messageDraft.items.length?messageDraft.alt_text:(text.slice(0,24)||'未命名草稿');
    const newDraft={
      id:'draft_'+Date.now(),
      savedAt:new Date().toISOString(),
      format:messageDraft.items.length?messageDraft.format:'text',
      title,
      summary:messageDraft.items.length?`${messageFormats[messageDraft.format][0]} · ${messageDraft.items.length} 個素材`:text.slice(0,60),
      messageDraft:structuredClone(messageDraft),
      textDraft:text
    };
    drafts.unshift(newDraft);
    if(drafts.length>30)drafts.pop();
    saveDraftsList(drafts);
    notice(`草稿「${title}」已成功儲存。`);
    render();
    return true;
  }
  if(action==='load-draft'){
    const drafts=loadSavedDrafts();
    const d=drafts.find(x=>x.id===id);
    if(!d)throw new Error('找不到該草稿。');
    if(d.messageDraft)messageDraft=structuredClone(d.messageDraft);
    if(d.textDraft){state.textDraft=d.textDraft;const el=$('message-draft');if(el)el.value=d.textDraft;}
    composerState.tab='compose';
    render();
    notice(`已載入草稿「${d.title}」。`);
    return true;
  }
  if(action==='delete-draft'){
    let drafts=loadSavedDrafts();
    drafts=drafts.filter(d=>d.id!==id);
    saveDraftsList(drafts);
    notice('草稿已刪除。');
    render();
    return true;
  }
  if(action==='clear-composition'){
    if(!window.confirm('確定要清空目前的圖片與互動訊息內容嗎？'))return true;
    messageDraft={format:"images",alt_text:"圖片訊息",organization_id:"",items:[],layout:"one",areas:[{label:"區塊 1",url:""}]};
    render();
    notice('已清空編輯內容。');
    return true;
  }

  if(action==='map-layout'){
    if(!mapLayouts[id])return true;
    messageDraft.areas.forEach((area,i)=>mapPreviewState.cache[i]={...area});
    messageDraft.layout=id;
    messageDraft.areas=Array.from({length:mapLayouts[id][1]},(_,i)=>mapPreviewState.cache[i]||{label:'區塊 '+(i+1),url:''});
    mapPreviewState.area=0;mapPreviewState.tapped=null;refreshComposer();
    document.querySelector(`[data-action="map-layout"][data-id="${id}"]`)?.focus({preventScroll:true});return true;
  }
  if(action==='map-mode'){
    mapPreviewState.mode=id==='simulate'?'simulate':'edit';mapPreviewState.tapped=null;refreshComposerPreview();
    document.querySelector(`[data-action="map-mode"][data-id="${mapPreviewState.mode}"]`)?.focus({preventScroll:true});return true;
  }
  if(action==='map-region'){
    const i=Number(id);if(!messageDraft.areas[i])return true;
    if(mapPreviewState.mode==='simulate'){
      mapPreviewState.tapped=i;refreshComposerPreview();
      document.querySelector(`[data-action="map-region"][data-id="${i}"]`)?.focus({preventScroll:true});
    }else{
      mapPreviewState.area=i;updateMapSelection();refreshComposerPreview();
      const input=document.querySelector(`[data-area="${i}"]`);input?.focus({preventScroll:true});input?.scrollIntoView({block:'nearest',behavior:'instant'});
    }
    return true;
  }

  if(action==='message-format'){
    if(!messageFormats[id])return true;
    messageDraft.format=id;
    const limit={images:5,card:1,carousel:12,imagemap:1}[id];
    if(messageDraft.items.length>limit){messageDraft.items=messageDraft.items.slice(0,limit);notice(`此格式最多 ${limit} 張，已保留前 ${limit} 張圖片。`);}
    render();return true;
  }
  if(['asset-up','asset-down','asset-remove'].includes(action)){
    const i=Number(id),items=messageDraft.items;if(!items[i])return true;
    if(action==='asset-remove')items.splice(i,1);else{const j=i+(action==='asset-up'?-1:1);if(items[j])[items[i],items[j]]=[items[j],items[i]];}
    refreshComposer();return true;
  }
  if(action==='choose-composition'){
    if(sessionStorage.getItem('linePendingJob'))throw new Error('請先確認上次提交結果。');
    validateComposition(messageDraft);
    const draft=structuredClone(messageDraft);
    state.report={category:'composition',title:messageFormats[draft.format][0]+'：'+draft.alt_text,status:'ready',scope:'composition',organization_id:superAdmin()?draft.organization_id:state.session.user.organization_id,composition:compositionPayload(draft),draft};
    state.step=2;state.selected.clear();state.audience='selected';render();window.scrollTo({top:0});return true;
  }
  return false;
}
document.addEventListener('input',event=>{const el=event.target;
  if(el.id==='composition-alt')messageDraft.alt_text=el.value;
  if(el.dataset.card!==undefined){messageDraft.items[Number(el.dataset.card)][el.dataset.prop]=el.value;refreshComposerPreview();}
  if(el.dataset.area!==undefined){messageDraft.areas[Number(el.dataset.area)].url=el.value;refreshComposerPreview();}
  if(el.id==='message-draft')state.textDraft=el.value;
  if(el.form?.id==='report-form'&&el.name==='source_path'&&el.value){el.form.elements.asset_id.value='';$('report-upload-preview').innerHTML='';}
});
document.addEventListener('change',async event=>{
  const el=event.target;
  try{
    if(el.id==='asset-company'){messageDraft.organization_id=el.value;messageDraft.items=[];refreshComposer();notice('已切換素材歸屬，請重新選擇圖片。');}
    if(el.form?.id==='report-form'&&el.name==='organization_id'){el.form.elements.asset_id.value='';el.form.querySelector('#report-upload-preview').innerHTML='';}
    if(!['composition-files','report-file'].includes(el.id))return;
    if(state.session.preview)throw new Error('視角預覽僅供檢視，請返回原帳號上傳。');
    const files=[...el.files];if(!files.length)return;
    const form=el.form;
    if(form&&!form.elements.organization_id.value)throw new Error('請先選擇報告所屬組織，再選擇圖片。');
    const limit={images:5,card:1,carousel:12,imagemap:1}[messageDraft.format];
    if(!form&&messageDraft.items.length+files.length>limit)throw new Error(`此格式最多 ${limit} 張；請先移除不需要的圖片。`);
    state.busy=true;el.disabled=true;
    const submit=form?.querySelector('[type="submit"]');if(submit)submit.disabled=true;
    const companySelect=form?.elements.organization_id||$('asset-company');if(companySelect)companySelect.disabled=true;
    const status=form?$('report-upload-preview'):$('upload-status');status.textContent='正在上傳並處理圖片…';
    try{
      for(const file of files){
        const asset=await uploadFile(file,form?form.elements.organization_id.value:messageDraft.organization_id);
        if(form){form.elements.asset_id.value=asset.asset_id;form.elements.source_path.value='';status.innerHTML=`<img class="upload-thumbnail" src="${asset.preview}" alt="已選圖片"><p>${esc(asset.name)} · ${asset.width} × ${asset.height} · ${Math.ceil(asset.size/1024)} KB</p>`;}
        else{messageDraft.items.push({...asset,title:file.name.replace(/\.[^.]+$/,'').slice(0,80),text:'',label:'開啟連結',url:''});refreshComposer();status.textContent=`已選擇 ${messageDraft.items.length} 張圖片。`;notice('');}
      }
    }finally{state.busy=false;el.disabled=false;el.value='';if(submit)submit.disabled=false;if(companySelect)companySelect.disabled=false;}
  }catch(error){el.value='';if($('modal').open){$('modal-error').textContent=error.message;$('modal-error').hidden=false;}else notice(error.message,true);}
});

function updateMapSelection(){document.querySelectorAll('[data-area-field]').forEach(el=>el.classList.toggle('selected',Number(el.dataset.areaField)===mapPreviewState.area));}
document.addEventListener('focusin',event=>{if(event.target.dataset.area!==undefined){const i=Number(event.target.dataset.area);if(mapPreviewState.area!==i){mapPreviewState.area=i;updateMapSelection();refreshComposerPreview();}}});

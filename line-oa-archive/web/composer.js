"use strict";
// Draft images stay private until the user confirms a delivery.
const messageFormats={images:["單圖／多圖","依序傳送 1–5 張圖片"],card:["圖文卡片","圖片、標題、說明與連結按鈕"],carousel:["輪播卡片","橫向滑動，最多 12 張卡片"],imagemap:["圖文訊息","一張圖片，分區點擊不同連結"]};
const mapLayouts={one:["全圖 1 區",1],two:["左右 2 區",2],four:["四宮格",4],six:["六宮格",6]};
let messageDraft={format:"images",alt_text:"圖片訊息",company:"",items:[],layout:"one",areas:[{label:"區塊 1",url:""}]};
const mapPreviewState={area:0,mode:"edit",tapped:null,cache:{}};
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
function composerEditor(){const d=messageDraft;return `<section class="panel section-space"><div class="panel-head"><div><h2>圖片與互動訊息</h2><p>選擇格式、上傳圖片，再安排收件對象與時間。</p></div>${badge('JPG / PNG')}</div><div class="panel-body"><div class="format-picker">${Object.entries(messageFormats).map(([key,[title,note]])=>`<button class="format-option ${d.format===key?'active':''}" data-action="message-format" data-id="${key}" aria-pressed="${d.format===key}"><strong>${title}</strong><small>${note}</small></button>`).join("")}</div><div class="composer-grid section-space"><div class="composer-controls">${superAdmin()?`<label class="field">圖片所屬組織<select id="asset-company">${options([["","平台個人素材"],...organizationOptions().slice(1)],d.company)}</select><small>組織素材只能傳給同組織的收件者。</small></label>`:''}<label class="field section-space">${d.format==='images'?'訊息名稱（方便管理紀錄）':'通知摘要（顯示於 LINE 聊天列表）'}<input id="composition-alt" maxlength="400" value="${esc(d.alt_text)}"></label><label class="upload-picker section-space">${icon('image')}<strong>點選並選擇圖片</strong><span>每張最多 8 MB，支援 JPG／PNG</span><input id="composition-files" type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" ${['images','carousel'].includes(d.format)?'multiple':''}></label><p class="subtitle">上傳後會調整尺寸與壓縮，保存本次選擇的副本。${d.format==='imagemap'?'圖文訊息高寬比須介於 1:2 至 2:1。':''}</p><p id="upload-status" role="status" aria-live="polite"></p><div id="composition-fields">${composerFields()}</div></div><aside class="composer-phone"><p class="eyebrow">訊息預覽</p><div id="composition-preview">${composerPreview(d,true)}</div><p class="subtitle">版面示意；字體與裁切以 LINE 裝置顯示為準。</p></aside></div><div class="form-actions">${button("使用這則訊息 →","choose-composition","primary",`id="choose-composition" ${d.items.length?'':'disabled'}`)}</div></div></section>`;}
function refreshComposer(){if($("composition-fields"))$("composition-fields").innerHTML=composerFields();refreshComposerPreview();if($("choose-composition"))$("choose-composition").disabled=!messageDraft.items.length;}
function refreshComposerPreview(){if($("composition-preview"))$("composition-preview").innerHTML=composerPreview(messageDraft,true);}
async function uploadFile(file,company){
  if(!file||file.size>8*1024*1024)throw new Error("請選擇 8 MB 以內的 JPG／PNG。");
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('無法讀取選擇的檔案。'));reader.readAsDataURL(file);});
  return api('/api/assets/upload',{name:file.name,data,company});
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
    state.report={category:'composition',title:messageFormats[draft.format][0]+'：'+draft.alt_text,status:'ready',scope:'composition',company:superAdmin()?draft.company:state.session.user.company,composition:compositionPayload(draft),draft};
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
    if(el.id==='asset-company'){messageDraft.company=el.value;messageDraft.items=[];refreshComposer();notice('已切換素材歸屬，請重新選擇圖片。');}
    if(el.form?.id==='report-form'&&el.name==='company'){el.form.elements.asset_id.value='';el.form.querySelector('#report-upload-preview').innerHTML='';}
    if(!['composition-files','report-file'].includes(el.id))return;
    if(state.session.preview)throw new Error('視角預覽僅供檢視，請返回原帳號上傳。');
    const files=[...el.files];if(!files.length)return;
    const form=el.form;
    if(form&&!form.elements.company.value)throw new Error('請先選擇報告所屬組織，再選擇圖片。');
    const limit={images:5,card:1,carousel:12,imagemap:1}[messageDraft.format];
    if(!form&&messageDraft.items.length+files.length>limit)throw new Error(`此格式最多 ${limit} 張；請先移除不需要的圖片。`);
    state.busy=true;el.disabled=true;
    const submit=form?.querySelector('[type="submit"]');if(submit)submit.disabled=true;
    const companySelect=form?.elements.company||$('asset-company');if(companySelect)companySelect.disabled=true;
    const status=form?$('report-upload-preview'):$('upload-status');status.textContent='正在上傳並處理圖片…';
    try{
      for(const file of files){
        const asset=await uploadFile(file,form?form.elements.company.value:messageDraft.company);
        if(form){form.elements.asset_id.value=asset.asset_id;form.elements.source_path.value='';status.innerHTML=`<img class="upload-thumbnail" src="${asset.preview}" alt="已選圖片"><p>${esc(asset.name)} · ${asset.width} × ${asset.height} · ${Math.ceil(asset.size/1024)} KB</p>`;}
        else{messageDraft.items.push({...asset,title:file.name.replace(/\.[^.]+$/,'').slice(0,80),text:'',label:'開啟連結',url:''});refreshComposer();status.textContent=`已選擇 ${messageDraft.items.length} 張圖片。`;notice('');}
      }
    }finally{state.busy=false;el.disabled=false;el.value='';if(submit)submit.disabled=false;if(companySelect)companySelect.disabled=false;}
  }catch(error){el.value='';if($('modal').open){$('modal-error').textContent=error.message;$('modal-error').hidden=false;}else notice(error.message,true);}
});

function updateMapSelection(){document.querySelectorAll('[data-area-field]').forEach(el=>el.classList.toggle('selected',Number(el.dataset.areaField)===mapPreviewState.area));}
document.addEventListener('focusin',event=>{if(event.target.dataset.area!==undefined){const i=Number(event.target.dataset.area);if(mapPreviewState.area!==i){mapPreviewState.area=i;updateMapSelection();refreshComposerPreview();}}});

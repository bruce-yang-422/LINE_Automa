"use strict";
function passwordForm(){
  const own=principalSession?.auth;
  if(own?.method==='local'){modal('設定網站登入',`<p class="callout">目前由本機控制台管理。請到「組織」頁的「管理員帳號」，在要啟用的 Email 旁按「設定登入」，產生一次性設定連結。</p>${button('前往組織管理員帳號','security-accounts','primary')}`);return;}
  modal(own?.password_set?'修改登入密碼':'啟用網站登入',`<form id="password-form"><p class="callout">${esc(principalSession.principal)}<br>密碼使用 15～128 個字元。變更後，所有裝置的網站登入都會失效。</p>${own?.password_set?'<label class="field">目前密碼<input name="current_password" type="password" autocomplete="current-password" required maxlength="128"></label>':''}<label class="field">新密碼<input name="password" type="password" autocomplete="new-password" required minlength="15" maxlength="128"></label><label class="field">再次輸入新密碼<input name="confirm" type="password" autocomplete="new-password" required minlength="15" maxlength="128"></label><div class="form-actions"><button type="submit" class="btn primary">儲存密碼</button></div></form>`);
}
document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-security]');
  if(event.target.closest('[data-action="security-accounts"]')){$('modal').close();management.tab='admins';navigate('organizations');}
  if(!target||state.busy)return;
  const action=target.dataset.security;
  if(action==='password'){passwordForm();return;}
  if(action==='invite'){
    modal('設定網站登入',`<p class="callout">為 ${esc(target.dataset.email)} 產生有效 30 分鐘的一次性連結。對方可自行設定密碼；完成後撤銷該帳號的既有網站登入。</p>${button('產生連結','unused','primary',`data-security="create-invite" data-email="${esc(target.dataset.email)}"`)}`);return;
  }
  if(action==='revoke'){
    modal('撤銷網站登入',`<p>將登出 ${esc(target.dataset.email)} 的所有裝置，並使未使用的設定連結失效。</p>${button('確認撤銷','unused','danger',`data-security="confirm-revoke" data-email="${esc(target.dataset.email)}"`)}`);return;
  }
  target.disabled=true;
  try{
    if(action==='create-invite'){
      const data=await api('/api/auth/invite',{email:target.dataset.email},true,true);
      modal('一次性密碼設定連結',`<p class="callout">30 分鐘內使用一次。請透過你信任的方式交給帳號本人。</p><label class="field">設定連結<input id="activation-link" readonly data-copy="off" value="${esc(data.url)}"></label><div class="form-actions">${button('複製連結','unused','primary','data-security="copy"')}${data.local_url?`<a class="btn" href="${esc(data.local_url)}" target="_blank" rel="noopener noreferrer">在這台電腦設定</a>`:''}</div>`);
    }else if(action==='confirm-revoke'){
      await api('/api/auth/revoke',{email:target.dataset.email},true,true);$('modal').close();notice('已撤銷網站登入及尚未使用的設定連結。');
    }else if(action==='copy'){
      const input=$('activation-link');input.select();
      try{await navigator.clipboard.writeText(input.value);target.textContent='已複製';}catch(_){notice('已選取連結，請按 Ctrl / ⌘ C 複製。');}
    }
  }catch(error){$('modal-error').textContent=error.message;$('modal-error').hidden=false;}
  finally{target.disabled=false;}
});
document.addEventListener('submit',async event=>{
  if(event.target.id!=='password-form')return;event.preventDefault();
  const form=event.target,payload=Object.fromEntries(new FormData(form));
  if(payload.password!==payload.confirm){$('modal-error').textContent='兩次密碼不相同。';$('modal-error').hidden=false;return;}
  const submit=form.querySelector('button[type=submit]');submit.disabled=true;
  try{
    await api('/api/auth/password',{current_password:payload.current_password||'',password:payload.password},true,true);
    form.reset();$('modal').close();
    if(principalSession.auth.method==='password')location.replace('/login');
    else{await load();render();notice('網站密碼已設定。入口切換完成後即可使用帳密登入。');}
  }catch(error){$('modal-error').textContent=error.message;$('modal-error').hidden=false;}
  finally{submit.disabled=false;}
});

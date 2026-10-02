"use strict";
const el=id=>document.getElementById(id);
const activation=new URLSearchParams(location.hash.slice(1)).get('setup')||'';
if(location.hash)history.replaceState(null,'',location.pathname);
// Activation tokens stay in memory; no query strings, browser storage or telemetry.
if(activation){
  el('login-title').textContent='設定你的登入密碼';
  el('login-description').textContent='使用 15～128 個字元，可用一段容易記住的句子。完成後需重新登入。';
  el('login-email-field').hidden=true;el('login-email').required=false;
  el('login-password').autocomplete='new-password';el('login-password').minLength=15;
  el('login-confirm-field').hidden=false;el('login-confirm').required=true;
  el('login-remember-field').hidden=true;el('login-submit').textContent='設定密碼';
  el('login-help').hidden=true;el('login-back').hidden=false;
}
// 尚無平台管理員時不能登入；首次設定只能從本機控制台進行。
if(!activation)fetch('/api/auth/setup-state',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json()).then(d=>{if(!d.initialized){el('login-setup').hidden=false;el('login-form').hidden=true;}}).catch(()=>{});
function show(message,error=true){el('login-notice').textContent=message;el('login-notice').className='notice'+(error?' error':'');el('login-notice').hidden=false;}
el('password-visibility').addEventListener('click',()=>{const showPassword=el('login-password').type==='password';el('login-password').type=showPassword?'text':'password';el('password-visibility').textContent=showPassword?'隱藏':'顯示';el('password-visibility').setAttribute('aria-label',showPassword?'隱藏密碼':'顯示密碼');el('password-visibility').setAttribute('aria-pressed',String(showPassword));});
el('login-form').addEventListener('submit',async event=>{
  event.preventDefault();if(el('login-submit').disabled)return;
  if(activation&&el('login-password').value!==el('login-confirm').value){show('兩次輸入的密碼不相同。');return;}
  el('login-submit').disabled=true;el('login-notice').hidden=true;
  try{
    const payload=activation?{token:activation,password:el('login-password').value}:{email:el('login-email').value,password:el('login-password').value,remember:el('login-remember').checked};
    const response=await fetch(activation?'/api/auth/activate':'/api/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),redirect:'error'});
    const data=await response.json();if(!response.ok)throw Error(data.error||'登入未完成，請稍後再試。');
    el('login-password').value='';el('login-confirm').value='';
    if(activation){el('login-form').hidden=true;show('密碼已設定，請返回登入使用 Email 與新密碼。',false);el('login-back').focus();}
    else{sessionStorage.removeItem('lineAdminToken');location.replace('/');}
  }catch(error){show(error.message==='Failed to fetch'?'連線中斷，請稍後再試。':error.message);}
  finally{el('login-submit').disabled=false;}
});

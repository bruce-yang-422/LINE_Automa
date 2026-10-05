// Isolated, mocked LINE fixture; never sends a real message or reads production credentials.
const fs=require('fs'),path=require('path'),{spawn}=require('child_process'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function contrast(page,label){
  const result=await page.evaluate(()=>{
    const failures=[],pairs=new Map();let checked=0;
    const parse=value=>{const parts=value.match(/[\d.]+/g)?.map(Number);return parts?.length>=3?[...parts.slice(0,3),parts[3]??1]:[0,0,0,0];};
    const blend=(fg,bg)=>fg.slice(0,3).map((n,i)=>n*fg[3]+bg[i]*(1-fg[3]));
    const luminance=rgb=>rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((v,n,i)=>v+n*[.2126,.7152,.0722][i],0);
    const background=el=>{const chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);return chain.reduce((bg,p)=>blend(parse(getComputedStyle(p).backgroundColor),bg),[255,255,255]);};
    function check(el,style,text,bg,kind='text'){
      const fg=blend(parse(style.color),bg),a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
      const key=style.color+' / '+bg.map(n=>Math.round(n)).join(',');pairs.set(key,ratio);checked++;
      if(ratio<4.5)failures.push({element:el.tagName+'.'+el.className,kind,text:text.slice(0,65),ratio:Number(ratio.toFixed(3)),colors:key});
    }
    for(const el of document.querySelectorAll('body *')){
      const style=getComputedStyle(el),rect=el.getBoundingClientRect();
      if(!rect.width||!rect.height||rect.right<=0||style.visibility!=='visible'||['SCRIPT','STYLE','OPTION'].includes(el.tagName)||el.closest('svg'))continue;
      const text=[...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join('').trim();
      const bg=background(el);
      if(text)check(el,style,text,bg);
      if(el.matches('input:not([type=checkbox]):not([type=hidden]),textarea,select')){
        check(el,style,el.value||el.tagName,bg,'control');
        if(el.placeholder)check(el,getComputedStyle(el,'::placeholder'),el.placeholder,bg,'placeholder');
      }
      if(el.matches('input[type=file]')){
        const pseudo=getComputedStyle(el,'::file-selector-button');check(el,pseudo,'選擇檔案',blend(parse(pseudo.backgroundColor),bg),'file button');
      }
      for(const pseudo of ['::before','::after']){
        const s=getComputedStyle(el,pseudo);
        if(s.content&&!['none','normal','""'].includes(s.content))check(el,s,s.content,blend(parse(s.backgroundColor),bg),pseudo);
      }
    }
    return {checked,minimum:Math.min(...pairs.values()),pairs:Object.fromEntries(pairs),failures};
  });
  assert.equal(result.failures.length,0,label+': '+JSON.stringify(result.failures));
  return {label,...result};
}
(async()=>{
 const dir=path.resolve('test-results/channels_browser');fs.mkdirSync(dir,{recursive:true});
 const file=path.join(dir,`oa-fixture-${Date.now()}.json`),stop=file.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',file,'--multi-oa'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 let stderr='',browser;child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<100&&!fs.existsSync(file);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(file,'utf8')),url=`http://127.0.0.1:${access.port}/#${access.token}`;
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({reducedMotion:'reduce',viewport:{width:1440,height:1050}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
  assert.equal(await page.locator('#line-oa-select option').count(),2);
  await page.locator('nav [data-view="channels"]').click();
  assert.equal(await page.locator('.oa-card').count(),2);
  const second=await page.locator('#line-oa-select option').nth(1).getAttribute('value');
  await page.locator('#line-oa-select').selectOption(second);
  await page.waitForFunction(id=>document.querySelector('#line-oa-select')?.value===id&&document.querySelector('.oa-card'),second);
  await page.locator('nav [data-view="contacts"]').click();
  await page.getByText('門市客戶',{exact:true}).waitFor();
  assert.equal(await page.locator('.person strong').count(),1);
  await page.locator('nav [data-view="channels"]').click();
  await page.locator('[data-line-action="verify"]').first().click();
  await page.getByText('Token 可連線；Channel secret 須以 LINE Webhook 驗證確認。',{exact:true}).waitFor();
  await page.locator('[data-line-action="add"]').click();
  await page.locator('#line-channel-form [name="name"]').fill('客服 OA');
  await page.locator('#line-channel-form [name="secret"]').fill('d'.repeat(32));
  await page.locator('#line-channel-form [name="access_token"]').fill('support-token');
  await page.getByRole('button',{name:'驗證並儲存',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.oa-card').length===3);
  assert.equal(await page.locator('#line-oa-select option:checked').textContent(),'客服 OA');
  assert(!await page.locator('body').innerText().then(t=>t.includes('support-token')));
  // An OA in a different personal workspace has a completely empty recipient list.
  await page.locator('#line-workspace-select').selectOption('p:admin@example.test');
  await page.waitForFunction(()=>document.querySelector('#line-oa-select option:checked')?.textContent==='個人小幫手');
  await page.locator('nav [data-view="contacts"]').click();
  assert.equal(await page.locator('.person strong').count(),0);
  // A personal report can use the UI file picker without an organization ID.
  await page.locator('nav [data-view="reports"]').click();
  await page.locator('[data-action="new-report"]').click();
  await page.locator('#report-form [name="title"]').fill('個人報告');
  await page.locator('#report-file').setInputFiles(access.sample_image);
  await page.locator('#report-upload-preview img').waitFor();
  await page.getByRole('button',{name:'儲存報告來源',exact:true}).click();
  await page.getByRole('heading',{name:'個人報告',exact:true}).waitFor();
  await page.locator('nav [data-view="channels"]').click();
  await page.screenshot({path:path.join(dir,'oa-desktop.png'),fullPage:true});
  for(const theme of ['light']){
   await page.waitForTimeout(250);
   await contrast(page,'OA desktop '+theme);
   await page.setViewportSize({width:390,height:844});
   await contrast(page,'OA mobile '+theme);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:path.join(dir,`oa-mobile-${theme}.png`),fullPage:true});
   await page.locator('[data-line-action="edit"]').click();
   await contrast(page,'OA credential form '+theme);
   await page.locator('#modal-close').click();
   await page.setViewportSize({width:1440,height:1050});
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({oa_create:'passed',switch_isolation:'passed',verify:'passed',personal_upload:'passed',mobile_light:'passed',text_contrast_AA:'passed',browser_errors:0,real_send_requests:0}));
 }finally{
  if(browser)await browser.close();fs.writeFileSync(stop,'stop');
  for(let i=0;i<100&&child.exitCode===null;i++)await delay(100);
  if(child.exitCode===null)child.kill();
  for(const p of [file,stop])if(fs.existsSync(p))fs.unlinkSync(p);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});

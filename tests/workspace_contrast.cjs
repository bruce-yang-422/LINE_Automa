// Checks rendered text pairs, placeholders and control states against WCAG sRGB contrast.
// Uses only the isolated fixture; no production credentials or LINE messages.
const fs=require('fs'),path=require('path'),{spawn}=require('child_process'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
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
  const dir=path.resolve('line-oa-archive/instance');fs.mkdirSync(dir,{recursive:true});
  const stateFile=path.join(dir,`contrast-fixture-${Date.now()}.json`),stopFile=stateFile.replace(/\.json$/,'.stop');
  const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',stateFile],{windowsHide:true,stdio:['ignore','ignore','pipe']});
  let stderr='',browser;child.stderr.on('data',data=>stderr+=data);
  try{
    for(let i=0;i<100&&!fs.existsSync(stateFile);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
    const access=JSON.parse(fs.readFileSync(stateFile,'utf8'));
    browser=await chromium.launch({channel:'chrome',headless:true});
    const theme=process.env.WORKSPACE_THEME||'light';
    const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',colorScheme:theme}),results=[];
    await page.goto(`http://127.0.0.1:${access.port}/#${access.token}`);
    await page.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    for(const view of ['overview','reports','send','contacts','subscriptions','history','organizations','settings']){
      await page.locator(`nav [data-view="${view}"]`).click();
      results.push(await contrast(page,view));
      const primary=page.locator('.btn.primary:visible').first();
      if(await primary.count()){
        await primary.hover();results.push(await contrast(page,view+' hover'));
        await primary.focus();results.push(await contrast(page,view+' focus'));await primary.blur();
      }
    }
    for(const [view,action] of [['reports','new-report'],['contacts','edit-contact'],['settings','new-account'],['organizations','new-organization'],['organizations','new-dispatch-scope'],['organizations','edit-sender-grant']]){
      await page.locator(`nav [data-view="${view}"]`).click();await page.locator(`[data-action="${action}"]`).first().click();
      results.push(await contrast(page,action));await page.locator('#modal-close').click();
    }
    await page.locator('nav [data-view="send"]').click();
    await page.locator('[data-action="message-format"][data-id="imagemap"]').click();
    results.push(await contrast(page,'visual layout without an uploaded image'));
    await page.locator('#composition-files').setInputFiles(access.sample_image);
    await page.waitForFunction(()=>document.querySelector('#upload-status').textContent.includes('已選擇 1 張'));
    await page.locator('[data-action="map-layout"][data-id="six"]').click();
    results.push(await contrast(page,'imagemap numbers over arbitrary image'));
    await page.locator('[data-action="map-region"][data-id="1"]').click();
    results.push(await contrast(page,'selected region and focused link field'));
    await page.locator('[data-action="map-mode"][data-id="simulate"]').click();
    await page.locator('[data-action="map-region"][data-id="1"]').click();
    results.push(await contrast(page,'simulated region feedback'));
    await page.locator('[data-action="message-format"][data-id="carousel"]').click();
    results.push(await contrast(page,'carousel preview'));
    await page.evaluate(()=>notice('請確認內容後再傳送。',true));results.push(await contrast(page,'error message'));
    await page.setViewportSize({width:390,height:844});
    results.push(await contrast(page,'mobile composer'));
    await page.screenshot({path:path.join(dir,`palette-${theme}-mobile.png`),fullPage:true,animations:'disabled'});
    await page.locator('#menu').click();results.push(await contrast(page,'mobile navigation'));
    await page.locator('nav [data-view="overview"]').click();
    await page.locator('#menu').click();await page.locator('nav [data-view="reports"]').click();
    await page.locator('[data-action="new-report"]').click();results.push(await contrast(page,'mobile bottom sheet'));
    await page.locator('#modal-close').click();
    await page.locator('#menu').click();await page.locator('nav [data-view="overview"]').click();
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(dir,`palette-${theme}-desktop.png`),fullPage:true,animations:'disabled'});
    await page.locator('#switch-view').click();results.push(await contrast(page,'role picker'));
    await page.locator('[data-action="apply-view"][data-id="employee@example.test|示範公司"]').click();
    await page.locator('#view-banner').waitFor();results.push(await contrast(page,'employee preview banner'));
    const summary={screens:results.length,checked:results.reduce((n,r)=>n+r.checked,0),minimum:Number(Math.min(...results.map(r=>r.minimum)).toFixed(3)),failures:0};
    fs.writeFileSync(path.join(dir,`contrast-audit-${theme}.json`),JSON.stringify({summary,results},null,2));
    console.log(JSON.stringify(summary));
  }finally{
    if(browser)await browser.close();fs.writeFileSync(stopFile,'stop');
    for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);
    if(child.exitCode===null)child.kill();
    for(const f of [stateFile,stopFile])if(fs.existsSync(f))fs.unlinkSync(f);
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});

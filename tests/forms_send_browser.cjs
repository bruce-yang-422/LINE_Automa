// Real admin UI and Dispatcher; the isolated fixture replaces every LINE push.
const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test'),contrast=require('./rendered_contrast.cjs');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=path.resolve('test-results/forms_send_browser');fs.mkdirSync(dir,{recursive:true});
 const file=path.join(dir,`fixture-${Date.now()}.json`),stop=file.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',file,'--public-forms','--form-sends'],{windowsHide:true,stdio:['ignore','ignore','pipe']});let stderr='',browser;
 child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<150&&!fs.existsSync(file);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(file,'utf8'));browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:390,height:960},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),page=await context.newPage(),errors=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);
  await page.locator(`[data-form-card="${access.form_id}"] [data-action=form-open]`).first().click();
  await page.locator('#page [data-action=form-send]').click();
  for(const [kind,n] of [['C',1],['U',2],['U',3]])await page.locator(`[data-form-send] input[value="${kind+n.toString(16).padStart(32,'0')}"]`).check();
  await page.getByRole('button',{name:'預覽訊息',exact:true}).click();await page.getByRole('button',{name:'確認發送',exact:true}).waitFor({timeout:8000}).catch(async e=>{console.error(await page.locator('#modal').innerText());console.error(errors);throw e;});
  assert((await page.locator('.form-send-message').textContent()).includes('?token='));
  const noJobs=await page.evaluate(async id=>(await api('/api/forms/send/history?form_id='+id)).jobs.length,access.form_id);assert.equal(noJobs,0);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));results.push(await contrast(page,'send preview '+width));await page.screenshot({path:path.join(dir,`preview-${width}.png`),fullPage:true});}
  await page.getByRole('button',{name:'確認發送',exact:true}).click();await page.getByRole('heading',{name:'問卷發送紀錄',exact:true}).waitFor();
  for(let i=0;i<30;i++){const history=await page.evaluate(async id=>await api('/api/forms/send/history?form_id='+id),access.form_id);if(history.jobs[0]?.status==='finished')break;await delay(100);}
  await page.locator('#modal [data-action=form-send-refresh]').click();await page.waitForLoadState('networkidle');await page.getByRole('button',{name:'重試失敗項目',exact:true}).waitFor();
  assert((await page.locator('#modal').innerText()).includes('發送成功：1 · 失敗：1 · 結果不明：1'));
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});results.push(await contrast(page,'send results '+width));await page.screenshot({path:path.join(dir,`results-${width}.png`),fullPage:true});}
  await page.getByRole('button',{name:'重試失敗項目',exact:true}).click();await page.getByRole('button',{name:'確認重試失敗項目',exact:true}).waitFor();
  assert((await page.locator('#modal').innerText()).includes('1 個聯絡對象'));assert(!(await page.locator('#modal').innerText()).includes('同事 3'));
  await page.getByRole('button',{name:'確認重試失敗項目',exact:true}).click();await page.getByRole('heading',{name:'問卷發送紀錄',exact:true}).waitFor();
  for(let i=0;i<30;i++){const result=await page.evaluate(async id=>await api('/api/forms/send/history?form_id='+id),access.form_id);if(result.counts.notifications===2)break;await delay(100);}
  await page.locator('#modal [data-action=form-send-refresh]').click();await page.waitForLoadState('networkidle');assert((await page.locator('#modal').innerText()).includes('通知聯絡對象：2'));
  await page.waitForFunction(()=>!state.busy);await page.locator('#modal-close').click();await page.waitForFunction(()=>!document.getElementById('modal').open);await page.locator('#page [data-action=form-remind]').click();
  await page.locator(`[data-form-send] input[value="C${'1'.padStart(32,'0')}"]`).check();await page.getByRole('button',{name:'預覽訊息',exact:true}).click();await page.getByRole('button',{name:'確認發送',exact:true}).waitFor();assert((await page.locator('.form-send-message').textContent()).includes('若已填寫，請忽略'));
  await page.getByRole('button',{name:'確認發送',exact:true}).click();await page.getByRole('heading',{name:'問卷發送紀錄',exact:true}).waitFor();await delay(300);await page.locator('#modal [data-action=form-send-refresh]').click();await page.waitForLoadState('networkidle');assert((await page.locator('#modal').innerText()).includes('最後提醒：'));
  await page.evaluate(()=>document.getElementById('modal').close());
  await page.evaluate(id=>api('/api/forms/status',{form_id:id,status:'stopped'}),access.form_id);await page.reload();await page.locator(`[data-form-card="${access.form_id}"] [data-action=form-open]`).first().click();assert.equal(await page.locator('#page [data-action=form-send]').count(),0);
  const collaborator=await browser.newContext({extraHTTPHeaders:{'X-Fixture-Role':'collaborator'}}),read=await collaborator.newPage();await read.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);await read.locator(`[data-form-card="${access.form_id}"] [data-action=form-open]`).first().click();assert.equal(await read.locator('#page [data-action=form-send]').count(),0);await read.locator('#page [data-action=form-send-history]').click();await read.getByRole('heading',{name:'問卷發送紀錄',exact:true}).waitFor();assert.equal(await read.locator('[data-action=form-send-retry]').count(),0);
  fs.writeFileSync(path.join(dir,'contrast.json'),JSON.stringify(results,null,2));assert.deepEqual(errors,[]);await collaborator.close();await context.close();console.log('Form send browser checks passed (fake LINE only)');
 }finally{if(browser)await browser.close();fs.writeFileSync(stop,'stop');for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);if(child.exitCode===null)child.kill();for(const item of [file,stop])if(fs.existsSync(item))fs.unlinkSync(item);}
})().catch(e=>{console.error(e);process.exitCode=1;});

// Isolated responses and attachments; no production database or LINE calls.
const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test'),contrast=require('./rendered_contrast.cjs');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=path.resolve('test-results/forms_responses_browser');fs.mkdirSync(dir,{recursive:true});
 const file=path.join(dir,`fixture-${Date.now()}.json`),stop=file.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',file,'--form-responses'],{windowsHide:true,stdio:['ignore','ignore','pipe']});let stderr='',browser;
 child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<150&&!fs.existsSync(file);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(file,'utf8'));browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:390,height:960},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),page=await context.newPage(),errors=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));const origin=`http://127.0.0.1:${access.port}`;
  // Ignore the workstation antivirus's external requests; assert failures from this app.
  page.on('console',m=>{if(m.type()==='error'&&m.location().url.startsWith(origin)&&!m.text().includes('kaspersky-labs.com'))errors.push(m.text());});
  page.on('requestfailed',r=>{if(r.url().startsWith(origin))errors.push(r.failure().errorText+' '+new URL(r.url()).pathname);});
  await page.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);
  await page.locator(`[data-form-card="${access.form_id}"] [data-action=form-responses]`).click();await page.getByText('共 3 份回覆',{exact:true}).waitFor();
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));results.push(await contrast(page,'response list '+width));await page.screenshot({path:path.join(dir,`list-${width}.png`),fullPage:true});}
  await page.locator('#form-response-query').fill('自述 1');await page.locator('#page [data-action=form-response-filter]').click();await page.getByText('共 1 份回覆',{exact:true}).waitFor();
  let downloaded=page.waitForEvent('download');await page.locator('#page [data-action=form-response-export]').click();let download=await downloaded;await download.saveAs(path.join(dir,'filtered.csv'));
  let csv=fs.readFileSync(path.join(dir,'filtered.csv'),'utf8');assert(csv.startsWith('\ufeff'));assert(csv.includes('0912 345-678'));assert(csv.includes('意見 [notes]'));assert(csv.includes('中文照片.PNG'));assert(!csv.includes(access.invitation_token));assert(!csv.includes('自述 2'));
  await page.locator('#page [data-action=form-response-detail]').click();await page.getByRole('heading',{name:'回覆資訊',exact:true}).waitFor();await page.getByAltText('中文照片.PNG',{exact:true}).waitFor();
  assert((await page.locator('#page').innerText()).includes('中文,逗號'));assert((await page.locator('#page').innerText()).includes('選項 A'));assert(!(await page.locator('#page').innerText()).includes('改名後的選項'));assert((await page.locator('#page').innerText()).includes('其他：多選補充'));
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));results.push(await contrast(page,'response detail '+width));await page.screenshot({path:path.join(dir,`detail-${width}.png`),fullPage:true});}
  await page.locator('#page [data-action=form-response-enlarge]').click();await page.locator('#modal .form-response-image').waitFor();assert(await page.locator('#modal .form-response-image').evaluate(img=>img.complete&&img.naturalWidth===480));results.push(await contrast(page,'response enlarged 390'));await page.locator('#modal-close').click();
  downloaded=page.waitForEvent('download');await page.locator('#page [data-action=form-response-download]').click();download=await downloaded;assert.equal(download.suggestedFilename(),'中文照片.PNG');await download.saveAs(path.join(dir,'downloaded.png'));assert(fs.readFileSync(path.join(dir,'downloaded.png')).equals(fs.readFileSync(access.sample_image)));
  await page.locator('#page [data-action=form-response-list]').click();await page.locator('#form-response-query').waitFor();await page.locator('#form-response-query').fill('');await page.locator('#form-response-from').fill('2026-10-08');await page.locator('#form-response-to').fill('2026-10-08');await page.locator('#form-response-time').selectOption('updated');await page.locator('#page [data-action=form-response-filter]').click();await page.getByText('共 2 份回覆',{exact:true}).waitFor();
  downloaded=page.waitForEvent('download');await page.locator('#page [data-action=form-response-export]').click();download=await downloaded;await download.saveAs(path.join(dir,'updated-date.csv'));csv=fs.readFileSync(path.join(dir,'updated-date.csv'),'utf8');assert(csv.includes("'=SUM(1,2)"));assert(csv.includes('文件.pdf'));assert(!csv.includes('自述 1'));
  await page.locator('#page [data-action=form-response-detail]').first().click();await page.getByRole('heading',{name:'文件.pdf',exact:true}).waitFor();assert.equal(await page.locator('[data-response-thumbnail]').count(),0);
  const readerContext=await browser.newContext({extraHTTPHeaders:{'X-Fixture-Role':'collaborator'}}),reader=await readerContext.newPage();await reader.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);await reader.locator(`[data-form-card="${access.form_id}"] [data-action=form-responses]`).click();await reader.getByText('共 3 份回覆',{exact:true}).waitFor();assert.equal(await reader.locator('[data-action=form-response-export]').count(),0);await reader.locator('[data-action=form-response-detail]').first().click();await reader.getByRole('heading',{name:'回覆資訊',exact:true}).waitFor();
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(dir,'contrast.json'),JSON.stringify(results,null,2));await readerContext.close();await context.close();console.log('Form responses browser checks passed');
 }finally{if(browser)await browser.close();fs.writeFileSync(stop,'stop');for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);if(child.exitCode===null)child.kill();for(const item of [file,stop])if(fs.existsSync(item))fs.unlinkSync(item);}
})().catch(e=>{console.error(e);process.exitCode=1;});

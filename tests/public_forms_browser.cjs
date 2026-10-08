// Independent public-service fixture; no admin credential is used to fill the form.
const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process');
const contrast=require('./rendered_contrast.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const dir=path.resolve('test-results/public_forms_browser');fs.mkdirSync(dir,{recursive:true});
 const stateFile=path.join(dir,`fixture-${Date.now()}.json`),stop=stateFile.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',stateFile,'--public-forms'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 let stderr='',browser;child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<150&&!fs.existsSync(stateFile);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(stateFile,'utf8')),base=`http://127.0.0.1:${access.public_port}`,url=base+`/forms/${access.form_id}?token=${access.invitation_token}`;
  browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:390,height:844}}),errors=[];let page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));const contrastResults=[];
  const input=id=>page.locator(`[data-answer="${id}"]:not([data-other])`).first();
  await page.goto(url);await page.getByRole('heading',{name:'公開問卷驗收',exact:true}).waitFor();
  assert(await page.locator('.form-intro').textContent().then(v=>v.includes('測試問卷說明')));
  assert.equal(await context.cookies().then(v=>v.length),0);const guest=await context.newPage();await guest.goto(url);await guest.getByRole('button',{name:'送出回覆',exact:true}).waitFor();
  await input('phone').fill('清除測試');await input('notes').fill('一鍵清除測試');await page.getByRole('button',{name:'重新填寫（一鍵清除）',exact:true}).click();await page.getByRole('button',{name:'送出回覆',exact:true}).waitFor();assert.equal(await input('phone').inputValue(),'');assert.equal(await input('notes').inputValue(),'');
  await page.getByRole('button',{name:'送出回覆',exact:true}).click();assert(await page.locator('#error-phone').isVisible());contrastResults.push(await contrast(page,'required errors 390'));
  let upload=page.locator('[data-upload-q=attachment]');
  await upload.setInputFiles({name:'偽裝.pdf',mimeType:'application/pdf',buffer:Buffer.from('not a PDF')});await page.getByText('上傳失敗：PDF 檔頭不正確。').waitFor();
  await page.getByRole('button',{name:'送出回覆',exact:true}).click();assert((await page.locator('#form-error').textContent()).includes('附件上傳完成'));
  await page.getByRole('button',{name:'移除／替換',exact:true}).click();
  // Simulate a response lost after the server stored the file, then retry the same upload.
  await page.route('**/upload?*',async route=>{await route.fetch();await route.abort();});
  await upload.setInputFiles({name:'照片.PNG',mimeType:'image/png',buffer:fs.readFileSync(access.sample_image)});await page.getByText('上傳失敗：連線失敗，請重試').waitFor();assert(await page.getByAltText('本機圖片預覽').isVisible());
  await page.unroute('**/upload?*');await page.getByRole('button',{name:'重試',exact:true}).click();await page.getByText(/KiB · 上傳完成/).waitFor();assert(await page.getByAltText('照片.PNG').isVisible());
  let originalDownload=await page.getByRole('link',{name:'下載',exact:true}).getAttribute('href');
  const otherDraft=await guest.evaluate(()=>JSON.parse(document.getElementById('public-form-data').dataset.json).draft_key);
  assert.equal((await context.request.get(base+originalDownload.replace(/draft=[^&]+/,'draft='+otherDraft))).status(),400);
  await input('phone').fill('0912 345-678');await input('free').fill('not a phone');await input('email').fill('invalid');await input('notes').fill('中文意見\n第二行');
  await page.locator('[data-answer="single"][value="__other__"]').check();
  await page.locator('[data-answer="multi"][value="multi-0"]').check();await page.locator('[data-answer="multi"][value="__other__"]').check();await page.locator('[data-answer="multi"][data-other]').fill('多選補充');
  await input('dropdown').selectOption('dropdown-1');await input('number').fill('1.5');await input('date').fill('2025-12-31');await input('time').fill('23:59');await input('rating').fill('8');
  await page.getByRole('button',{name:'送出回覆',exact:true}).click();
  for(const id of ['email','single','number','date','rating'])assert(await page.locator('#error-'+id).isVisible());
  assert.equal(await input('phone').inputValue(),'0912 345-678');assert.equal(await input('notes').inputValue(),'中文意見\n第二行');
  await page.close();page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url);await page.getByRole('button',{name:'送出回覆',exact:true}).waitFor();upload=page.locator('[data-upload-q=attachment]');
  assert((await page.locator('#draft-status').textContent()).includes('已恢復'));assert.equal(await input('phone').inputValue(),'0912 345-678');assert.equal(await input('email').inputValue(),'invalid');assert.equal(await input('notes').inputValue(),'中文意見\n第二行');assert.equal(await input('number').inputValue(),'1.5');assert.equal(await input('dropdown').inputValue(),'dropdown-1');assert(await page.locator('[data-answer="single"][value="__other__"]').isChecked());assert.equal(await page.locator('[data-answer="multi"][data-other]').inputValue(),'多選補充');assert.equal(await page.getByAltText('照片.PNG').count(),0);assert((await page.locator('#draft-status').textContent()).includes('附件不保留'));assert(await page.evaluate(()=>Object.values(localStorage).filter(v=>v.includes('submissionKey')).every(v=>!('attachment' in JSON.parse(v).answers))));await upload.setInputFiles({name:'照片.PNG',mimeType:'image/png',buffer:fs.readFileSync(access.sample_image)});await page.getByText(/KiB · 上傳完成/).waitFor();originalDownload=await page.getByRole('link',{name:'下載',exact:true}).getAttribute('href');
  await input('email').fill('');await page.locator('[data-answer="single"][data-other]').fill('單選補充');await input('number').fill('2');await input('date').fill('2026-10-08');await input('rating').fill('7');
  await page.route('**/submit?*',route=>route.abort());await page.getByRole('button',{name:'送出回覆',exact:true}).click();await page.locator('#form-error:not([hidden])').waitFor();
  assert((await page.locator('#form-error').textContent()).includes('輸入已保留'));assert.equal(await input('phone').inputValue(),'0912 345-678');await page.unroute('**/submit?*');
  const submitted=page.waitForResponse(r=>r.url().includes('/submit?')&&r.status()===200);await page.getByRole('button',{name:'送出回覆',exact:true}).click();const first=await (await submitted).json();
  await page.getByRole('button',{name:'儲存修改',exact:true}).waitFor();assert((await page.locator('#response-status').textContent()).includes('感謝你的回覆'));
  await guest.locator('[data-answer=phone]').fill('0976543210');await guest.getByRole('button',{name:'送出回覆',exact:true}).click();await guest.getByRole('button',{name:'儲存修改',exact:true}).waitFor();await guest.reload();assert.equal(await guest.locator('[data-answer=phone]').inputValue(),'0976543210');await guest.close();
  const other=await context.newPage();await other.goto(url);await other.getByRole('button',{name:'送出回覆',exact:true}).waitFor();assert.equal(await other.locator('[data-answer=phone]').inputValue(),'');await other.close();
  await page.reload();await page.getByRole('button',{name:'儲存修改',exact:true}).waitFor();
  assert.equal(await input('phone').inputValue(),'0912 345-678');assert.equal(await input('free').inputValue(),'not a phone');assert.equal(await input('notes').inputValue(),'中文意見\n第二行');
  assert(await page.locator('[data-answer="single"][value="__other__"]').isChecked());assert.equal(await page.locator('[data-answer="single"][data-other]').inputValue(),'單選補充');assert(await page.locator('[data-answer="multi"][value="multi-0"]').isChecked());
  assert.equal(await page.locator('[data-answer="multi"][data-other]').inputValue(),'多選補充');
  await input('free').fill('尚未送出的修改');await page.reload();await page.getByRole('button',{name:'儲存修改',exact:true}).waitFor();assert.equal(await input('free').inputValue(),'尚未送出的修改');
  assert(await page.getByAltText('照片.PNG').isVisible());await page.getByRole('button',{name:'移除／替換',exact:true}).click();
  await input('phone').fill('bad');await page.getByRole('button',{name:'儲存修改',exact:true}).click();assert.equal((await context.request.get(base+originalDownload)).status(),200);
  await upload.setInputFiles({name:'替換文件.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.7\nfixture')});await page.getByText(/KiB · 上傳完成/).waitFor();
  await input('phone').fill('0987654321');const changed=page.waitForResponse(r=>r.url().includes('/submit?')&&r.status()===200);await page.getByRole('button',{name:'儲存修改',exact:true}).click();const updated=await (await changed).json();assert.equal(updated.first_submitted_at,first.first_submitted_at);assert.notEqual(updated.updated_at,first.updated_at);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));contrastResults.push(await contrast(page,'filled '+width));await page.screenshot({path:path.join(dir,`filled-${width}.png`),fullPage:true,animations:'disabled'});}
  // Real server still rejects invalid data even when the front-end validator is bypassed.
  const invalid=await page.evaluate(async()=>{const data=JSON.parse(document.getElementById('public-form-data').dataset.json);const response=await fetch(location.pathname+'/submit'+location.search,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:{phone:'invalid'},expected_updated_at:data.form.updated_at,submission_key:data.submission_key})});return {code:response.status,data:await response.json()};});
  assert.equal(invalid.code,422);assert(invalid.data.errors.phone);
  const adminContext=await browser.newContext({extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),admin=await adminContext.newPage();await admin.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);try{await admin.locator('[data-action="form-new"]').waitFor();}catch(exc){console.log(await admin.locator('body').innerText());console.log(await admin.evaluate(()=>({view:state.view,session:state.session?.role})));throw exc;}
  const counts=await admin.evaluate(async id=>(await api('/api/forms/detail?form_id='+id)).form.counts,access.form_id);assert.deepEqual(counts,{notifications:0,responses:2});
  await admin.evaluate(id=>api('/api/forms/status',{form_id:id,status:'stopped'}),access.form_id);await page.reload();await page.getByRole('heading',{name:'問卷無法填寫'}).waitFor();assert((await page.locator('[role="alert"]').textContent()).includes('停止收件'));
  await admin.evaluate(id=>api('/api/forms/delete',{form_id:id,confirm_counts:{notifications:0,responses:2}}),access.form_id);await page.reload();assert((await page.locator('[role="alert"]').textContent()).includes('已刪除'));
  await page.goto(url.replace(access.invitation_token,'bad'));assert((await page.locator('[role="alert"]').textContent()).includes('連結無效'));
  contrastResults.push(await contrast(page,'invalid link 390'));fs.writeFileSync(path.join(dir,'contrast.json'),JSON.stringify(contrastResults,null,2));assert(!stderr.includes(access.invitation_token),'Invitation token leaked into server logs');assert.deepEqual(errors,[]);await adminContext.close();await context.close();console.log('Public form browser checks passed');
 }finally{if(browser)await browser.close();fs.writeFileSync(stop,'stop');for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);if(child.exitCode===null)child.kill();for(const file of [stateFile,stop])if(fs.existsSync(file))fs.unlinkSync(file);}
})().catch(e=>{console.error(e);process.exitCode=1;});

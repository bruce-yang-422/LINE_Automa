const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const contrast=require('./rendered_contrast.cjs');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const dir=path.resolve('test-results/forms_content_browser');fs.mkdirSync(dir,{recursive:true});
 const stateFile=path.join(dir,`fixture-${Date.now()}.json`),stop=stateFile.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',stateFile,'--public-forms'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 let stderr='',browser;child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<150&&!fs.existsSync(stateFile);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(stateFile,'utf8'));
  browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),admin=await context.newPage(),errors=[];admin.on('pageerror',e=>errors.push(e.message));
  await admin.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);await admin.locator('[data-action=form-new]').click();await admin.locator('[data-form-create-mode=blank]').click();await admin.locator('#modal [name=name]').fill('多媒體說明驗收');await admin.getByRole('button',{name:'建立草稿',exact:true}).click();await admin.locator('#page [data-form-editor]').waitFor();
  const formId=await admin.locator('#page [data-form-editor]').getAttribute('data-id');await admin.locator('[data-action=form-design]').click();
  const card=id=>admin.locator(`[data-qid="${id}"]`),field=(id,name)=>card(id).locator(`[data-q-field="${name}"]`);
  async function addContent(kind,title,description=''){
   await admin.locator('[data-design-action=add-content]').click();const id=await admin.locator('[data-qid]').last().getAttribute('data-qid');
   await field(id,'content.kind').selectOption(kind);await field(id,'title').fill(title);await field(id,'description').fill(description);return id;
  }
  const text=await addContent('text','閱讀須知','這是說明文字，不需要回答。');assert.equal(await card(text).locator('[data-q-field=required]').count(),0);
  const image=await addContent('image','交通示意','請參考圖片。');await card(image).locator('[data-form-content-upload]').setInputFiles(access.sample_image);await card(image).locator('[data-form-content-image]:visible').waitFor();
  const picture=await addContent('image','');await card(picture).locator('[data-form-content-upload]').setInputFiles(access.sample_image);await card(picture).locator('[data-form-content-image]:visible').waitFor();
  const video=await addContent('video','活動介紹');await field(video,'content.youtube_url').fill('https://youtu.be/abcdefghijk');
  await admin.locator('[data-design-action=add-question]').click();const answer=await admin.locator('[data-qid]').last().getAttribute('data-qid');await field(answer,'title').fill('姓名');await field(answer,'required').check();
  await admin.getByRole('button',{name:'儲存題目',exact:true}).click();await admin.waitForFunction(()=>!state.busy&&document.querySelector('[data-form-designer]').dataset.dirty==='false');
  await admin.locator('[data-design-action=preview]').first().click();await admin.locator('[data-form-content-image]:visible').first().waitFor();assert.equal(await admin.locator('.form-content-video-link').count(),1);assert.equal(await admin.locator('[data-answer-id]').count(),1);
  await admin.evaluate(id=>api('/api/forms/status',{form_id:id,status:'collecting'}),formId);const row=await admin.evaluate(async id=>(await api('/api/forms/detail?form_id='+id)).form,formId);
  const token=new URL(row.public_url).searchParams.get('token'),guestContext=await browser.newContext({viewport:{width:390,height:844}}),guest=await guestContext.newPage();guest.on('pageerror',e=>errors.push(e.message));
  await guest.route('https://www.youtube-nocookie.com/**',route=>route.fulfill({contentType:'text/html',body:'<html><body>Isolated YouTube iframe fixture</body></html>'}));
  const url=`http://127.0.0.1:${access.public_port}/forms/${formId}?token=${token}`;await guest.goto(url);assert.equal(await guest.locator('.form-content-block').count(),4);assert.equal(await guest.locator('[data-answer]').count(),1);
  assert.equal(await guest.locator('iframe').getAttribute('src'),'https://www.youtube-nocookie.com/embed/abcdefghijk');await guest.locator('iframe').scrollIntoViewIfNeeded();await guest.frameLocator('iframe').getByText('Isolated YouTube iframe fixture').waitFor();assert.equal(await guest.locator('.form-content-block img').count(),2);
  await guest.waitForFunction(()=>[...document.querySelectorAll('.form-content-block img')].every(img=>img.complete&&img.naturalWidth>0));
  const imageId=await admin.evaluate(id=>formDesign.questions.find(q=>q.id===id).content.image_id,image);
  assert.equal((await guest.request.get(`${url.split('?')[0]}/content/${imageId}?token=invalid`)).status(),404);
  assert.equal((await guest.request.get(`${url.split('?')[0]}/content/${'0'.repeat(32)}?token=${token}`)).status(),404);
  await guest.locator('#submit-answer').click();assert(await guest.locator(`#error-${answer}`).isVisible());await guest.locator(`[data-answer="${answer}"]`).fill('測試姓名');await guest.locator('#submit-answer').click();await guest.waitForURL('**/*&edit=*');
  const csv=await admin.evaluate(async id=>await (await formResponseBinary('/api/forms/responses/export?form_id='+id)).text(),formId);assert(csv.includes('測試姓名'));assert(!csv.includes('閱讀須知'));assert(!csv.includes('交通示意'));assert(!csv.includes('活動介紹'));
  const checks=[];for(const width of [1440,768,390]){await guest.setViewportSize({width,height:1000});checks.push(await contrast(guest,`public content ${width}`));assert(await guest.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await guest.screenshot({path:path.join(dir,`public-${width}.png`),fullPage:true});await admin.setViewportSize({width,height:1000});checks.push(await contrast(admin,`preview content ${width}`));}
  fs.writeFileSync(path.join(dir,'contrast.json'),JSON.stringify(checks,null,2));assert.deepEqual(errors,[]);await guestContext.close();console.log('Form content browser checks passed');
 }finally{if(browser)await browser.close();fs.writeFileSync(stop,'stop');for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);if(child.exitCode===null)child.kill();for(const file of [stateFile,stop])if(fs.existsSync(file))fs.unlinkSync(file);}
})().catch(e=>{console.error(e);process.exitCode=1;});

const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process');
const contrast=require('./rendered_contrast.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const dir=path.resolve('test-results/forms_pages_browser');fs.mkdirSync(dir,{recursive:true});
 const stateFile=path.join(dir,`fixture-${Date.now()}.json`),stop=stateFile.replace(/\.json$/,'.stop');
 const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',stateFile,'--public-forms','--form-pages'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 let stderr='',browser;child.stderr.on('data',v=>stderr+=v);
 try{
  for(let i=0;i<150&&!fs.existsSync(stateFile);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
  const access=JSON.parse(fs.readFileSync(stateFile,'utf8'));
  browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${access.public_port}/forms/${access.form_id}?token=${access.invitation_token}`);
  assert.equal(await page.locator('#page-status').textContent(),'第 1 / 2 頁');assert(await page.locator('#submit-answer').isHidden());
  await page.locator('#next-page').click();assert(await page.locator('#error-phone').isVisible());assert.equal(await page.locator('#page-status').textContent(),'第 1 / 2 頁');
  await page.locator('[data-answer=phone]').fill('0912345678');await page.locator('#next-page').click();
  assert.equal(await page.locator('#page-status').textContent(),'第 2 / 2 頁');assert(await page.locator('#next-page').isHidden());assert(await page.locator('#submit-answer').isVisible());
  await page.locator('[data-answer=notes]').fill('跨頁草稿');await page.reload();assert.equal(await page.locator('#page-status').textContent(),'第 2 / 2 頁');assert.equal(await page.locator('[data-answer=notes]').inputValue(),'跨頁草稿');
  await page.locator('#previous-page').click();assert.equal(await page.locator('[data-answer=phone]').inputValue(),'0912345678');await page.locator('#next-page').click();
  await page.locator('[data-answer=multi][value=multi-0]').check();
  await page.locator('#submit-answer').click();assert(await page.locator('#error-multi').isVisible());
 await page.locator('[data-answer=multi][value=multi-1]').check();
  await page.locator('#submit-answer').click();await page.waitForURL('**/*&edit=*');assert((await page.locator('#response-status').textContent()).includes('感謝你的回覆'));
  const admin=await context.newPage();await admin.setExtraHTTPHeaders({'X-Fixture-Role':'org_admin'});await admin.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);await admin.locator('[data-action=form-new]').waitFor();
  await admin.evaluate(id=>{formsUI.selected=id;formsUI.mode='design';render();},access.form_id);
  assert.equal(await admin.locator('[data-qid=page-two] [data-q-field=type]').count(),0);assert(await admin.locator('[data-qid=page-two] [data-q-field=page_break]').isChecked());
  assert.equal(await admin.locator('[data-qid=phone] [data-q-field=type] option[value=section]').count(),0);
  const other=admin.locator('[data-qid=single] .form-other-example');assert(await other.isVisible());
  await admin.locator('[data-qid=single] [data-q-field=allow_other]').uncheck();assert.equal(await other.count(),0);
  await admin.locator('[data-qid=single] [data-q-field=allow_other]').check();assert(await other.isVisible());assert(await other.locator('input').isDisabled());
  await admin.locator('[data-qid=page-two] [data-q-field=page_break]').uncheck();assert((await admin.locator('.form-designer-toolbar').textContent()).includes('1 頁'));
  await admin.locator('[data-qid=page-two] [data-q-field=page_break]').check();assert((await admin.locator('.form-designer-toolbar').textContent()).includes('2 頁'));
  await admin.setViewportSize({width:1920,height:1000});
  await admin.locator('[data-workspace-tool=related]').click();
  await admin.getByRole('heading',{name:'題目排序',exact:true}).waitFor();
  const sort=id=>admin.locator(`[data-form-sort-id="${id}"]`);
  await sort('notes').locator('[data-form-sort-move=up]').click();
  await admin.waitForFunction(()=>formDesign.questions[4].id==='notes');assert.equal(await admin.locator('[data-qid]').nth(4).getAttribute('data-qid'),'notes');
  await sort('notes').locator('[data-form-sort-move=down]').click();await admin.waitForFunction(()=>formDesign.questions[5].id==='notes');
  await sort('notes').locator('[data-form-sort-drag]').dragTo(sort('phone'),{targetPosition:{x:70,y:8}});
  await admin.waitForFunction(()=>formDesign.questions[1].id==='notes');assert.equal(await admin.locator('[data-qid]').nth(1).getAttribute('data-qid'),'notes');
  assert.equal(await admin.locator('.form-drag-ghost').count(),0);
  await admin.waitForFunction(()=>document.getAnimations().every(animation=>animation.playState!=='running'));
  await sort('page-two').scrollIntoViewIfNeeded();
  const targetBounds=await sort('page-two').boundingBox();
  await sort('notes').locator('[data-form-sort-drag]').dragTo(sort('page-two'),{targetPosition:{x:70,y:targetBounds.height-8}});
  await admin.waitForFunction(()=>formDesign.questions[5].id==='notes');
  assert.equal(await admin.locator('form[data-form-designer]').getAttribute('data-dirty'),'true');
  await sort('notes').locator('[data-form-sort-jump]').click();assert.equal(await admin.locator('[data-qid=notes] [data-q-field=title]').evaluate(el=>el===document.activeElement),true);
  const sortChecks=[];
  for(const width of [1920,768,390]){
   await admin.setViewportSize({width,height:1000});
   sortChecks.push(await contrast(admin,`sort panel ${width}`));assert(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await admin.screenshot({path:path.join(dir,`sort-${width}.png`)});
  }
  await admin.locator('[data-workspace-tool-close]').click();
  await admin.locator('[data-design-action=preview]').first().click();await admin.locator('[data-preview-next]').click();assert(await admin.locator('#form-preview-error-phone').isVisible());
  await admin.locator('[data-answer-id=phone]').fill('0912345678');await admin.locator('[data-preview-next]').click();assert.equal(await admin.locator('[data-preview-page-status]').textContent(),'第 2 / 2 頁');
  await admin.locator('[data-answer-id=notes]').fill('預覽答案');await admin.locator('[data-preview-previous]').click();await admin.locator('[data-preview-next]').click();assert.equal(await admin.locator('[data-answer-id=notes]').inputValue(),'預覽答案');
  const checks=sortChecks;
  for(const width of [1440,768,390]){
   await admin.setViewportSize({width,height:1000});
   checks.push(await contrast(admin,`preview ${width}`));
   assert((await admin.locator('section[data-form-designer]').boundingBox()).width<=720);
   assert(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await admin.screenshot({path:path.join(dir,`preview-${width}.png`),fullPage:true});
   await admin.locator('[data-design-action=back-design]').click();
   assert((await admin.locator('form[data-form-designer]').boundingBox()).width<=960);
   assert(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   checks.push(await contrast(admin,`designer ${width}`));
   await admin.screenshot({path:path.join(dir,`designer-${width}.png`),fullPage:true});
   await admin.locator('[data-design-action=preview]').first().click();
  }
  fs.writeFileSync(path.join(dir,'contrast.json'),JSON.stringify(checks,null,2));
  assert.deepEqual(errors,[]);console.log('Form pagination browser checks passed');
 }finally{if(browser)await browser.close();fs.writeFileSync(stop,'stop');for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);if(child.exitCode===null)child.kill();for(const file of [stateFile,stop])if(fs.existsSync(file))fs.unlinkSync(file);}
})().catch(e=>{console.error(e);process.exitCode=1;});

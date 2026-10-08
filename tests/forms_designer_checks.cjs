const assert=require('assert'),fs=require('fs');
module.exports=async function formsDesignerChecks(browser,access,contrast){
  const context=await browser.newContext({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),page=await context.newPage(),errors=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));
  const card=id=>page.locator(`[data-qid="${id}"]`),field=(id,path)=>card(id).locator(`[data-q-field="${path}"]`);
  const check=async label=>{assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),label+' overflows');if(contrast)results.push(await contrast(page,'forms designer '+label));};
  async function add(kind,title){
    await page.locator('[data-design-action="add-question"]').click();
    let id=await page.locator('[data-qid]').last().getAttribute('data-qid');
    if(kind!=='short_text')await field(id,'type').selectOption(kind);
    await field(id,'title').fill(title);return id;
  }
  const enable=async id=>{if(!await field(id,'validation.enabled').isVisible())await card(id).locator('.form-validation-settings summary').click();await field(id,'validation.enabled').check();};
  async function save(){
    await page.getByRole('button',{name:'儲存題目',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('form[data-form-designer]')?.dataset.dirty==='false');
  }
  async function submitPreview(){
    const response=page.waitForResponse(r=>r.url().endsWith('/api/forms/preview')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'驗證預覽答案',exact:true}).click();
    const data=await (await response).json();
    await page.waitForFunction(()=>!document.querySelector('form[data-form-preview] button[type="submit"]').disabled);return data;
  }
  try{
    await page.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);
    await page.locator('[data-action="form-new"]').click();await page.locator('[data-form-create-mode=blank]').click();await page.locator('#modal [name="name"]').fill('設計器驗收');
    await page.getByRole('button',{name:'建立草稿',exact:true}).click();await page.locator('#page [data-form-editor]').waitFor();
    const formId=await page.locator('#page [data-form-editor]').getAttribute('data-id');
    await page.locator('[data-action="form-design"]').click();await page.locator('form[data-form-designer]').waitFor();
    await page.locator('[data-design-action="add-section"]').click();const section=await page.locator('[data-qid]').last().getAttribute('data-qid');
    await field(section,'title').fill('聯絡資訊');await field(section,'description').fill('請提供聯絡方式');
    const phone=await add('short_text','驗證手機');await field(phone,'required').check();await enable(phone);await field(phone,'validation.format').selectOption('phone');
    await card(phone).locator('[data-design-action="copy"]').click();const free=await page.locator('[data-qid]').last().getAttribute('data-qid');
    assert.notEqual(free,phone);await field(free,'title').fill('不驗證電話');await field(free,'required').uncheck();await field(free,'validation.enabled').uncheck();
    const email=await add('short_text','Email');await enable(email);await field(email,'validation.format').selectOption('email');
    const paragraph=await add('paragraph','意見');await enable(paragraph);await field(paragraph,'validation.max_length').fill('1000');
    const single=await add('single_choice','單選其他'),multi=await add('multiple_choice','多選其他'),dropdown=await add('dropdown','下拉選單');
    for(const id of [single,multi,dropdown]){
      await card(id).locator('[data-design-action="option-add"]').click();
      await card(id).locator('[data-q-field="option.label"]').nth(0).fill('選項 A');await card(id).locator('[data-q-field="option.label"]').nth(1).fill('選項 B');
    }
    await field(single,'allow_other').check();await field(multi,'allow_other').check();await enable(multi);await field(multi,'validation.count_exact').fill('2');
    const numeric=await add('number','數量');await enable(numeric);await field(numeric,'validation.integer').check();await field(numeric,'validation.min').fill('1');await field(numeric,'validation.max').fill('3');
    const date=await add('date','日期');await enable(date);await field(date,'validation.date_min').fill('2026-01-01');await field(date,'validation.date_max').fill('2026-12-31');
    const time=await add('time','時間'),rating=await add('rating','評分');await field(rating,'rating.max').fill('7');await field(rating,'rating.lower_label').fill('不滿意');await field(rating,'rating.upper_label').fill('滿意');
    const attachment=await add('attachment','附件');await field(attachment,'attachment.max_files').fill('2');
    assert.equal(await page.locator('[data-qid]').count(),13);
    // Rename and option sorting preserve both question and option IDs.
    const optionIds=await card(single).locator('[data-option-id]').evaluateAll(elements=>elements.map(e=>e.dataset.optionId));
    await card(single).locator('[data-design-action="option-down"]').first().click();
    assert.deepEqual(await card(single).locator('[data-option-id]').evaluateAll(elements=>elements.map(e=>e.dataset.optionId)),optionIds.slice().reverse());
    const dropdownOptions=await card(dropdown).locator('[data-option-id]').evaluateAll(elements=>elements.map(e=>e.dataset.optionId));
    await card(dropdown).locator('[data-design-action="copy"]').click();const copyId=await page.evaluate(id=>formDesign.questions[formDesign.questions.findIndex(q=>q.id===id)+1].id,dropdown);
    const copiedOptions=await card(copyId).locator('[data-option-id]').evaluateAll(elements=>elements.map(e=>e.dataset.optionId));
    assert(copiedOptions.every(id=>!dropdownOptions.includes(id)));
    page.once('dialog',dialog=>dialog.accept());await card(copyId).locator('[data-design-action="remove"]').click();assert.equal(await card(copyId).count(),0);
    // Move with keyboard, then drag; existing IDs remain unchanged.
    await card(phone).locator('[data-design-action="up"]').focus();await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-qid]').first().getAttribute('data-qid'),phone);
    await card(phone).locator('.form-validation-settings summary').click();
    await card(phone).locator('[data-form-drag]').dragTo(card(section).locator('[data-form-drag]'));
    assert.equal(await page.locator('[data-qid]').first().getAttribute('data-qid'),section);
    await field(multi,'validation.count_exact').fill('9');
    await page.getByRole('button',{name:'儲存題目',exact:true}).click();
    await page.locator('.form-design-error:not([hidden])').waitFor();assert(await card(multi).locator('.form-question-error').isVisible());
    assert.equal(await field(multi,'validation.count_exact').inputValue(),'9');
    await field(multi,'validation.count_exact').fill('2');
    let prevented=false;page.once('dialog',async dialog=>{prevented=true;await dialog.dismiss();});
    await page.evaluate(()=>navigate('overview'));assert(prevented);assert(await page.locator('form[data-form-designer]').isVisible());
    await page.locator('[data-workspace-tool="related"]').click();assert.equal(await page.locator('[data-form-sort-id]').count(),13);
    await page.locator('[data-workspace-tool-close]').click();await page.getByRole('button',{name:'儲存題目',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('form[data-form-designer]')?.dataset.dirty==='false');
    if(await page.locator('[data-workspace-tool-close]').isVisible())await page.locator('[data-workspace-tool-close]').click();
    const stored=await page.evaluate(id=>api('/api/forms/detail?form_id='+id),formId);
    assert.equal(stored.form.questions.length,13);assert.equal(stored.form.questions.find(q=>q.id===free).validation.enabled,false);
    assert.equal(stored.form.questions.find(q=>q.id===phone).validation.format,'phone');
    for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});await check('cards '+width);}
    await page.locator('[data-design-action="preview"]').click();await page.locator('form[data-form-preview]').waitFor();
    const preview=id=>page.locator(`[data-preview-id="${id}"]`),input=id=>preview(id).locator('input[data-answer-id]').first();
    let result=await submitPreview();assert.equal(result.valid,false);assert(result.errors[phone]);
    await input(phone).fill('0912 345-678');await input(free).fill('not a phone');await input(email).fill('invalid');
    await preview(single).locator('input[value="__other__"]').check();
    const multiOption=stored.form.questions.find(q=>q.id===multi).options[0].id;
    await preview(multi).locator(`input[value="${multiOption}"]`).check();await preview(multi).locator('input[value="__other__"]').check();
    await preview(multi).locator('[data-other]').fill('補充選項');await input(numeric).fill('1.5');await input(date).fill('2025-12-31');await input(time).fill('23:59');await input(rating).fill('8');
    result=await submitPreview();assert.equal(result.valid,false);for(const id of [email,single,numeric,date,rating])assert(result.errors[id]);
    assert(!result.errors[phone]);assert(!result.errors[free]);assert(!result.errors[multi]);
    assert.equal(await input(phone).inputValue(),'0912 345-678');assert.equal(await input(free).inputValue(),'not a phone');
    await input(email).fill('');await preview(single).locator('[data-other]').fill('其他內容');await input(numeric).fill('2');await input(date).fill('2026-01-01');await input(rating).fill('7');
    result=await submitPreview();assert.equal(result.valid,true);assert.equal(result.answers[phone],'0912 345-678');assert.equal(result.answers[single].other,'其他內容');assert.equal(result.answers[multi].option_ids.length,2);
    assert((await page.locator('.form-preview-status').textContent()).includes('未保存回覆'));
    for(const width of [1440,768,390]){await page.setViewportSize({width,height:960});await check('preview '+width);if(!contrast)await page.screenshot({path:`test-results/workspace_browser/forms-preview-${width}.png`,fullPage:true});}
    await page.locator('[data-design-action="back-design"]').click();await page.locator('form[data-form-designer]').waitFor();
    await field(phone,'title').fill('已改名稱');await page.locator('[data-design-action="preview"]').click();
    assert.equal(await input(phone).inputValue(),'0912 345-678');await page.locator('[data-design-action="back-design"]').click();
    assert.equal(await field(phone,'title').inputValue(),'已改名稱');assert.equal(await page.locator('form[data-form-designer]').getAttribute('data-dirty'),'true');
    // Existing responses require a visible confirmation before saving destructive changes.
    await page.evaluate(id=>{formsUI.rows.find(row=>row.form_id===id).counts.responses=1;},formId);
    let impact=false;page.once('dialog',async dialog=>{impact=dialog.message().includes('舊答案');await dialog.dismiss();});
    await page.getByRole('button',{name:'儲存題目',exact:true}).click();assert(impact);
    await page.evaluate(id=>{formsUI.rows.find(row=>row.form_id===id).counts.responses=0;},formId);
    await save();assert.equal((await page.evaluate(id=>api('/api/forms/detail?form_id='+id),formId)).form.questions.find(q=>q.id===phone).id,phone);
    await page.evaluate(id=>api('/api/forms/delete',{form_id:id,confirm_counts:{notifications:0,responses:0}}),formId);
    assert.deepEqual(errors,[]);
    if(contrast)fs.writeFileSync('test-results/workspace_contrast/forms-designer-contrast.json',JSON.stringify(results,null,2));
  }finally{await context.close();}
};

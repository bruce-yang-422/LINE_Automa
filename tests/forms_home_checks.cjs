const assert=require('assert'),fs=require('fs');
module.exports=async function(browser,access,contrast){
 const context=await browser.newContext({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),page=await context.newPage(),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(`http://127.0.0.1:${access.port}/?view=forms#${access.token}`);
  await page.locator('[data-action="form-folder-new"]').click();await page.locator('[data-form-folder] [name="name"]').fill('活動問卷');
  await page.getByRole('button',{name:'儲存資料夾',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  const folder=await page.evaluate(()=>formsUI.folder);assert.notEqual(folder,'all');
  await page.locator('[data-action="form-new"]').click();await page.locator('[data-form-create-mode=template]').click();await page.locator('#modal [name="template_id"]').selectOption('group_buy');await page.locator('#modal [name="name"]').fill('首頁驗收問卷');
  await page.getByRole('button',{name:'建立草稿',exact:true}).click();await page.locator('[data-form-editor][data-id]').waitFor();
  const id=await page.locator('[data-form-editor][data-id]').getAttribute('data-id');
  assert.equal(await page.evaluate(id=>formsUI.rows.find(r=>r.form_id===id).folder_id,id),folder);
  await page.locator('[data-action="form-back"]').click();
  await page.locator('[data-action="form-folder-rename"]').click();await page.locator('[data-form-folder] [name="name"]').fill('家長與活動');await page.getByRole('button',{name:'儲存資料夾',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:960});
   for(const mode of ['list','grid']){
    await page.locator(`[data-action="form-layout"][data-id="${mode}"]`).click();
    assert.equal(await page.locator(`[data-action="form-layout"][data-id="${mode}"]`).getAttribute('aria-pressed'),'true');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(await page.locator('[data-form-card]').count(),1);
    if(mode==='grid')assert(await page.locator('.form-thumbnail').isVisible());
    if(contrast)results.push(await contrast(page,`forms home ${mode} ${width}`));
    else await page.screenshot({path:`test-results/workspace_browser/forms-home-${mode}-${width}.png`,fullPage:true,animations:'disabled'});
   }
  }
  await page.reload();await page.locator('.form-grid').waitFor();
  await page.locator('[data-action="form-folder-select"]').filter({hasText:'家長與活動'}).click();
  await page.locator('[data-action="form-move"]').click();await page.locator('[data-form-folder] select').selectOption('');await page.getByRole('button',{name:'確認移動',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});assert.equal(await page.locator('[data-form-card]').count(),0);
  await page.locator('[data-action="form-folder-select"][data-id=""]').click();assert.equal(await page.locator('[data-form-card]').count(),1);
  await page.locator('[data-action="form-move"]').click();await page.locator('[data-form-folder] select').selectOption(folder);await page.getByRole('button',{name:'確認移動',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  await page.locator(`[data-action="form-folder-select"][data-id="${folder}"]`).click();await page.locator('[data-action="form-folder-delete"]').click();await page.getByRole('button',{name:'確認刪除資料夾',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  assert.equal(await page.locator('[data-form-card]').count(),1);assert.equal(await page.evaluate(id=>formsUI.rows.find(r=>r.form_id===id).folder_id,id),'');
  await page.locator('#form-search').fill('查無問卷');assert.equal(await page.locator('[data-form-card]').count(),0);await page.locator('#form-search').fill('');
  await page.evaluate(id=>api('/api/forms/delete',{form_id:id,confirm_counts:{notifications:0,responses:0}}),id);
  assert.deepEqual(errors,[]);
  if(contrast)fs.writeFileSync('test-results/workspace_contrast/forms-home-contrast.json',JSON.stringify(results,null,2));
 }finally{await context.close();}
};

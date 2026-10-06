// Shared phase-one checks, using only the isolated workspace fixture.
const assert=require('assert');
module.exports=async function dutyChecks(browser,access,contrast){
  const url=`http://127.0.0.1:${access.port}/?view=duty&tab=notify#${access.token}`;
  const context=await browser.newContext({extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto(url);
    await page.getByRole('heading',{name:'值日生',exact:true}).waitFor({timeout:10000});
    assert(await page.locator('[data-view="duty"]').isVisible());
    assert((await page.locator('.duty-context[aria-label="值日生班表資訊"]').textContent()).includes('組織：示範公司'));
    for(const width of [1440,768,390]){
      await page.setViewportSize({width,height:960});
      for(const tab of ['home','roster','people','tasks','notify','log']){
        await page.locator(`[data-duty-tab="${tab}"]`).click();
        assert(new URL(page.url()).searchParams.get('tab')===tab);
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        assert.equal(await page.locator('.duty-tabs button[aria-pressed="true"]').count(),1);
        if(contrast)await contrast(page,`duty ${tab} ${width}`);
      }
    }
    await require('./duty_setup_checks.cjs')(page,contrast);
    await require('./duty_roster_checks.cjs')(page,contrast);
    await require('./duty_csv_checks.cjs')(page,contrast);
    await require('./duty_automation_checks.cjs')(page,contrast);
    await page.goto(url.replace('&tab=notify',''));
    await page.locator('[data-duty-tab="home"][aria-pressed="true"]').waitFor();
    await page.locator('[data-duty-home-month]').fill('2026-11');
    await page.waitForFunction(()=>!dutyHome.loading&&dutyHome.month==='2026-11');
    await page.locator('.duty-home-work').filter({hasText:'CSV工作'}).waitFor();
    const assignedName=await page.evaluate(()=>{const assignment=dutyHome.records.find(r=>r.period_type==='month').assignments.find(a=>a.snapshot.name==='CSV工作');return rosterPersonName(assignment.person_ids[0],assignment);});
    assert((await page.locator('.duty-home-work').filter({hasText:'CSV工作'}).textContent()).includes(assignedName));
    assert((await page.locator('.duty-home-work').filter({hasText:'CSV工作'}).textContent()).includes('草稿'));
    for(const width of [1440,768,390]){
      await page.setViewportSize({width,height:1000});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      if(width<=850)await page.waitForFunction(()=>document.querySelector('#sidebar').getBoundingClientRect().right<=1);
      if(contrast)await contrast(page,'duty visual home '+width);
      else await page.screenshot({path:`test-results/workspace_browser/duty-home-${width}.png`,fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('.duty-home-work').filter({hasText:'CSV工作'}).locator('[data-duty-home-open]').click();
    await page.locator('[data-duty-form="roster-choose"]').waitFor();
    await page.locator('#modal-close').click();
    // Grant is saved explicitly; merely checking the box does not change the API.
    await page.setViewportSize({width:1440,height:960});
    await page.evaluate(()=>navigate('personnel'));
    const form=page.locator('.duty-grant-form[data-email="sender@example.test"]');
    await form.waitFor();
    await form.locator('input').check();
    const saved=page.waitForResponse(r=>r.url().includes('/api/duty/grants'));
    await form.locator('button').click();
    const response=await saved;assert.equal(response.status(),200,await response.text());
    await page.waitForFunction(()=>document.querySelector('#floating-toast')?.textContent.includes('值日生管理權已儲存。')||!document.querySelector('#modal-error').hidden);
    assert.equal(await page.locator('#modal-error').isHidden(),true,await page.locator('#modal-error').textContent());
    assert(await page.locator('.duty-grant-form[data-email="sender@example.test"] input').isChecked());
    if(contrast)await contrast(page,'duty grant controls');
    const operator=await browser.newContext({extraHTTPHeaders:{'X-Fixture-Role':'operator'}});
    const operatorPage=await operator.newPage();
    await operatorPage.goto(url);
    await operatorPage.getByRole('heading',{name:'值日生',exact:true}).waitFor({timeout:10000});
    assert.equal(await operatorPage.getByText('你目前只能檢視班表',{exact:true}).count(),0);
    await page.locator('.duty-grant-form[data-email="sender@example.test"] input').uncheck();
    const revoked=page.waitForResponse(r=>r.url().includes('/api/duty/grants'));
    await page.locator('.duty-grant-form[data-email="sender@example.test"] button').click();
    assert.equal((await revoked).status(),200);
    await page.waitForFunction(()=>document.querySelector('#floating-toast')?.textContent.includes('值日生管理權已儲存。')||!document.querySelector('#modal-error').hidden);
    assert.equal(await page.locator('#modal-error').isHidden(),true,await page.locator('#modal-error').textContent());
    await operatorPage.reload();
    await operatorPage.getByText('你目前只能檢視班表',{exact:true}).waitFor({timeout:10000});
    assert.equal(await operatorPage.locator('[data-duty-tab="people"]').count(),0);
    if(contrast)await contrast(operatorPage,'duty read only');
    await operator.close();
    // A different organization without any OA can still open the duty module.
    await page.locator('#organization-select').selectOption('無OA組織',{force:true});
    await page.waitForFunction(()=>document.querySelector('#account-role').textContent.includes('無OA組織'));
    await page.evaluate(()=>navigate('duty'));
    await page.getByRole('heading',{name:'值日生',exact:true}).waitFor({timeout:10000});
    assert((await page.locator('.duty-context[aria-label="值日生班表資訊"]').textContent()).includes('無OA組織'));
    assert((await page.locator('.duty-context[aria-label="值日生班表資訊"]').textContent()).includes('尚未指定'));
    if(contrast)await contrast(page,'duty without OA');
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
};

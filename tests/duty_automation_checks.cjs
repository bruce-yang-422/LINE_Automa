const assert=require('assert');
module.exports=async function dutyAutomationChecks(page,contrast){
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-duty-tab="notify"]').click();
  const settings=page.locator('[data-duty-form="automation-settings"]');
  await settings.locator('[name="channel_id"]').selectOption({label:'總公司通知 OA'});
  await settings.locator('[name="personal"]').check();
  await settings.locator('[name="publish_enabled"]').check();
  await settings.locator('[name="publish_personal"]').check();
  await settings.locator('[type="submit"]').click();
  await page.waitForFunction(()=>dutyAutomation.settings?.revision===1);
  for(const width of [1440,1920,2560,3840,768,390]){
    await page.setViewportSize({width,height:1000});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(width>=1440){
      assert(await page.evaluate(()=>{
        const left=document.querySelector('.duty-notification-channel').getBoundingClientRect(),right=document.querySelector('.duty-notification-reminders').getBoundingClientRect();
        return left.right<right.left&&Math.abs(left.top-right.top)<2;
      }),'PC settings must show LINE setup beside reminder cards');
    }
    if(width>=2200)assert.equal(await page.locator('.duty-notice-card-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),4);
    if(contrast)await contrast(page,'duty notice settings '+width);
    if(!contrast){await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:`test-results/workspace_browser/duty-notifications-${width}.png`,fullPage:true});}
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-duty-tab="people"]').click();
  const person=page.locator('.duty-person-card').filter({hasText:'CSV人員'});
  await person.locator('[data-duty-action="binding"]').click();
  await page.locator('[data-duty-form="binding"] [name="recipient_id"]').selectOption({index:1});
  await page.locator('[data-duty-form="binding"] [type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#modal')?.open===false);
  await page.locator('[data-duty-tab="notify"]').click();
  await page.locator('.duty-visual-advanced').filter({hasText:'試送、手動通知與用量'}).locator('summary').click();
  await page.locator('[data-duty-auto="test"]').click();
  const manual=page.locator('[data-duty-form="automation-manual"]');
  await manual.locator('label').filter({hasText:'CSV人員'}).locator('input').check();
  await manual.locator('[name="roster_id"]').selectOption({index:1});
  await manual.locator('[type="submit"]').click();
  await manual.locator('[type="submit"]').filter({hasText:'確認發送'}).waitFor();
  assert((await manual.locator('.duty-manual-preview').textContent()).includes('預覽 1 個聊天室'));
  await manual.locator('[type="submit"]').click();
  await manual.waitFor({state:'hidden'});
  await page.locator('[data-duty-tab="log"]').click();
  await page.locator('.history-item').first().waitFor();
  assert((await page.locator('.history-item').first().textContent()).includes('試送'));
  if(contrast)await contrast(page,'duty notice log');
  await page.locator('[data-duty-tab="roster"]').click();
  await page.locator('[data-duty-roster-action="back"]').click();
  await page.locator('[data-duty-auto="rule-new"]').click();
  const rule=page.locator('[data-duty-form="automation-rule"]');
  await rule.locator('[name="baseline_date"]').fill('2026-10-01');
  await rule.locator('[name="effective_from"]').fill('2026-10-01');
  for(const checkbox of await rule.locator('[data-rule-include="tasks"]').all()){
    if(!(await checkbox.locator('..').textContent()).includes('CSV工作'))await checkbox.uncheck();
  }
  const positions=await rule.locator('[data-rule-include="positions"]').all();
  for(let i=2;i<positions.length;i++)await positions[i].uncheck();
  await rule.locator('[data-duty-auto="order-down"]').first().click();
  await rule.locator('[data-duty-auto="rule-preview"]').click();
  await rule.locator('.duty-rule-preview h3').first().waitFor();
  assert.equal(await rule.locator('.duty-rule-preview h3').count(),3);
  if(contrast)await contrast(page,'duty rotation preview');
  await rule.locator('[type="submit"]').click();
  await rule.waitFor({state:'hidden'});
  await page.getByText('每月 v1',{exact:true}).waitFor();
  await page.locator('[data-duty-roster-action="open"]').filter({hasText:'編輯'}).first().click();
  await page.locator('[data-duty-auto="apply-rule"]').click();
  const apply=page.locator('[data-duty-form="automation-apply"]');
  await apply.waitFor();
  assert((await apply.textContent()).includes('CSV工作'));
  await apply.locator('[type="submit"]').click();
  await apply.waitFor({state:'hidden'});
};

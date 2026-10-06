const assert=require('assert');
module.exports=async function dutyCsvChecks(page,contrast){
  async function download(kind,action='export'){
    const pending=page.waitForEvent('download');
    await page.locator(`[data-duty-csv="${action}"][data-kind="${kind}"]:visible`).first().click();
    const result=await pending;
    assert(result.suggestedFilename().endsWith('.csv'));
    const stream=await result.createReadStream(),chunks=[];
    for await(const chunk of stream)chunks.push(chunk);
    const text=Buffer.concat(chunks).toString('utf8');
    assert(text.startsWith('\ufeff'));return text;
  }
  async function importCsv(kind,text){
    await page.locator(`[data-duty-csv="import"][data-kind="${kind}"]`).click();
    const form=page.locator('[data-duty-form="csv-import"]');
    await form.locator('[type="file"]').setInputFiles({name:'值日生測試.csv',mimeType:'text/csv',buffer:Buffer.from(text,'utf8')});
    await form.locator('[type="submit"]').click();
    await form.locator('[type="submit"]').filter({hasText:'確認匯入'}).waitFor();
    assert.equal(await form.locator('.duty-csv-preview .duty-form-error').count(),0);
    if(contrast)await contrast(page,'duty csv '+kind+' preview');
    await form.locator('[type="submit"]').click();
    await form.waitFor({state:'hidden'});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-duty-tab="people"]').click();
  assert((await download('people')).includes('姓名'));
  assert.equal((await download('people','template')).trim().split(/\r?\n/).length,1);
  await importCsv('people','姓名,英文名/暱稱,部門,樓層,代號,生效日,啟用\r\nCSV人員,CSV測試,管理部,2F,,2026-01-01,1\r\n');
  await page.locator('.duty-person-card').filter({hasText:'CSV人員'}).waitFor();
  await page.locator('[data-duty-tab="tasks"]').click();
  assert((await download('tasks')).includes('執行內容'));
  assert.equal((await download('tasks','template')).trim().split(/\r?\n/).length,1);
  await importCsv('tasks','工作名稱,生效日,執行內容,執行頻率,星期\r\nCSV工作,2026-01-01,打包垃圾,每週,1;4\r\n');
  await page.locator('.duty-task-list button').filter({hasText:'CSV工作'}).waitFor();
  await page.locator('[data-duty-tab="roster"]').click();
  assert((await download('rosters')).includes('代班人員'));
  assert.equal((await download('rosters','template')).trim().split(/\r?\n/).length,1);
  await page.locator('[data-duty-roster-action="back"]').click();
  const csv='班表名稱,期間類型,起始日,結束日,工作名稱,負責人,當期備註,代班原負責人,代班人員,代班起始日,代班結束日\r\nCSV十一月,月,2026-11-01,2026-11-30,CSV工作,CSV人員,CSV備註,,,,\r\n';
  await importCsv('rosters',csv);
  await page.getByRole('heading',{name:'CSV十一月',exact:true}).waitFor();
  assert((await page.locator('.callout').first().textContent()).includes('草稿'));
  const result=await download('rosters');
  assert(result.includes('CSV人員'));
  assert(result.includes('CSV備註'));
};

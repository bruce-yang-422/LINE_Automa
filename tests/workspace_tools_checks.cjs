const assert=require('assert');
const fs=require('fs');
module.exports=async function workspaceToolsChecks(browser,access,contrast){
  const context=await browser.newContext({viewport:{width:2560,height:1080},extraHTTPHeaders:{'X-Fixture-Role':'org_admin'}}),page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const url=`http://127.0.0.1:${access.port}/?view=duty#${access.token}`;
  try{
    await page.goto(url);await page.locator('[data-workspace-tool="summary"]').waitFor();
    await page.locator('[data-workspace-tool="summary"]').click();
    assert((await page.locator('#workspace-tools-body').textContent()).includes('必須處理'));
    for(const [width,height] of [[2560,1080],[3440,1440],[1920,1080],[1440,900],[768,960],[390,844]]){
      await page.setViewportSize({width,height});
      await page.waitForFunction(docked=>document.querySelector('#workspace-tools-panel').getAttribute('role')===(docked?'complementary':'dialog'),width>=1600);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert(await page.evaluate(()=>Math.abs(document.querySelector('.topbar').getBoundingClientRect().right-innerWidth)<2),'top bar must extend to the right screen edge');
      assert(await page.locator('#workspace-tools-panel').isVisible());
      assert(await page.evaluate(()=>{
        const header=document.querySelector('.duty-home-header'),strip=header.querySelector('.duty-month-strip'),style=getComputedStyle(header),buttons=[...strip.querySelectorAll('button')];
        return Math.abs(strip.getBoundingClientRect().right-(header.getBoundingClientRect().right-parseFloat(style.paddingRight)-parseFloat(style.borderRightWidth)))<2&&buttons.every(b=>Math.abs(b.getBoundingClientRect().width-buttons[0].getBoundingClientRect().width)<1);
      }),'month cards should evenly fill the available header width');
      const bounds=await page.locator('#workspace-tools-panel').boundingBox();
      assert(bounds.x>=0&&bounds.x+bounds.width<=width&&bounds.y+bounds.height<=height);
      if(width>=1600)assert(await page.evaluate(()=>document.querySelector('#content').getBoundingClientRect().right<=document.querySelector('#workspace-tools-panel').getBoundingClientRect().left+1));
      else assert.equal(await page.locator('#workspace-tools-panel').getAttribute('aria-modal'),'true');
      if(contrast)await contrast(page,'workspace tools summary '+width);
      if(width>1100)assert(await page.evaluate(()=>getComputedStyle(document.querySelector('#content')).overflowY==='auto'&&document.querySelector('.page-footer').getBoundingClientRect().bottom<=innerHeight+1));
      if(!contrast)await page.screenshot({path:`test-results/workspace_browser/workspace-tools-${width}.png`,fullPage:true});
    }
    await page.keyboard.press('Escape');assert(await page.locator('#workspace-tools-panel').isHidden());
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.workspaceTool),'summary');
    await page.setViewportSize({width:2560,height:1080});
    await page.locator('[data-workspace-tool="summary"]').click();
    const resize=page.locator('.workspace-tools-resize');await resize.focus();await page.keyboard.press('ArrowLeft');
    assert.equal(await resize.getAttribute('aria-valuenow'),'380');
    const handle=await resize.boundingBox();await page.mouse.move(handle.x+4,handle.y+20);await page.mouse.down();await page.mouse.move(handle.x-56,handle.y+20);await page.mouse.up();
    assert.equal(await resize.getAttribute('aria-valuenow'),'440');
    assert(await page.evaluate(()=>Math.abs(document.querySelector('.topbar').getBoundingClientRect().right-innerWidth)<2),'resizing the sidebar must preserve the full-width top bar');
    await page.locator('[data-workspace-tool-close]').click();
    assert(await page.evaluate(()=>Math.abs(document.querySelector('.topbar').getBoundingClientRect().right-innerWidth)<2));
    await page.locator('[data-workspace-tool="outline"]').click();
    assert(await page.locator('.workspace-tools-outline button').count()>0);
    await page.locator('.workspace-tools-outline button').first().click();
    assert(await page.evaluate(()=>document.activeElement.matches('#page h2,#page h3,#page h4')));
    await page.evaluate(async()=>{
      dutyTab='roster';if(!dutyRoster.rows.length){await api('/api/duty/roster/create',{name:'右側檢查測試',period_type:'month',date_from:'2026-10-01',date_to:'2026-10-31'});await loadDutyRosters();}await dutyOpenRoster(dutyRoster.rows[0].roster_id,false);
      const taskId=dutyRoster.record.assignments[0].task_id;
      dutyRoster.record.checks={blocking:[{message:'測試必須處理',task_id:taskId}],warnings:[{message:'測試需確認'}],info:[{message:'測試資訊'}]};render();
    });
    await page.locator('[data-workspace-tool-tab="summary"]').click();
    assert((await page.locator('#workspace-tools-body').textContent()).includes('測試必須處理'));
    if(!contrast)await page.screenshot({path:'test-results/workspace_browser/workspace-checks.png',fullPage:true});
    await page.locator('#workspace-tools-body button').filter({hasText:'測試必須處理'}).click();
    assert(await page.evaluate(()=>document.activeElement.closest('[data-roster-task]')!==null));
    await page.locator('[data-workspace-tool="related"]').click();
    await page.locator('#page [data-duty-tab="people"]').click();await page.locator('#page [data-duty-tab="tasks"]').click();
    assert.equal(await page.evaluate(()=>dutyTab),'tasks');
    await page.locator('[data-workspace-tool-tab="summary"]').click();
    assert(!(await page.locator('#workspace-tools-body').textContent()).includes('測試必須處理'));
    await page.locator('.duty-task-list button').first().click();
    const name=page.locator('#duty-task-detail [name="name"]');await name.fill('未儲存側欄測試');
    await name.evaluate(el=>el.dataset.probe='same-node');
    for(const tab of ['summary','related','outline','help']){
      await page.locator(`[data-workspace-tool-tab="${tab}"]`).click();
      assert.equal(await name.inputValue(),'未儲存側欄測試');assert.equal(await name.getAttribute('data-probe'),'same-node');
      assert.equal(await page.locator('#duty-task-detail form').getAttribute('data-dirty'),'true');
    }
    await page.locator('[data-workspace-tool="related"]').click();
    assert(await page.locator('[data-workspace-tool-action]').filter({hasText:'新增工作'}).count()>0);
    assert(await page.evaluate(()=>{
      const main=document.getElementById('content'),side=document.getElementById('workspace-tools-body');
      main.scrollTop=300;const position=main.scrollTop;side.scrollTop=120;
      return position>0&&main.scrollTop===position;
    }),'main and secondary panels must scroll independently');
    if(!contrast)await page.screenshot({path:'test-results/workspace_browser/workspace-subfunctions.png',fullPage:true});
    assert.equal(await page.locator('[data-workspace-tool-view]').count(),0);assert.equal(await page.locator('[data-workspace-tool-action]').filter({hasText:'排班管理'}).count(),0);
    page.once('dialog',dialog=>dialog.dismiss());await page.locator('#page [data-duty-tab="notify"]').click();
    assert.equal(await page.evaluate(()=>state.view),'duty');
    assert.equal(await page.evaluate(()=>dutyTab),'tasks');
    await page.locator('[data-workspace-tool-tab="summary"]').click();
    assert(!(await page.locator('#workspace-tools-body').textContent()).includes('測試必須處理'));
    assert((await page.locator('#workspace-tools-body').textContent()).includes('有未儲存變更'));
    assert((await page.locator('#workspace-workbench-status').textContent()).includes('未儲存變更'));
    await page.locator('[data-workspace-tool-tab="related"]').click();
    page.once('dialog',dialog=>dialog.accept());await page.locator('#page [data-duty-tab="notify"]').click();
    assert.equal(await page.evaluate(()=>dutyTab),'notify');
    await page.evaluate(()=>navigate('contacts'));
    assert.equal(await page.evaluate(()=>state.view),'contacts');
    assert.equal(await page.locator('#workspace-tools-context').textContent(),'聯絡對象');
    await page.evaluate(()=>{
      const row=state.contacts[0];row.custom_name='CSV匯出驗證';row.work_department='採購部';row.department='北區客戶';row.phone='0912345678';row.notes='=公式測試,"引號"\n第二行';
      state.search='CSV匯出驗證';state.selected=new Set([row.recipient_id]);render();
    });
    for(const scope of ['filtered','all','selected']){
      await page.locator('[data-action="export-contacts-csv"]').click();
      await page.locator(`[name="contact-export-scope"][value="${scope}"]`).check();
      const downloadEvent=page.waitForEvent('download');
      await page.locator('[data-action="download-contacts-csv"]').click();
      const download=await downloadEvent,bytes=fs.readFileSync(await download.path()),csv=bytes.toString('utf8');
      assert.deepEqual([...bytes.subarray(0,3)],[239,187,191]);
      assert(download.suggestedFilename().endsWith('.csv'));
      assert(csv.includes('"內部分組"')&&csv.includes('"部門"'));
      assert(csv.includes('"北區客戶"')&&csv.includes('"採購部"'));
      assert(csv.includes('"\'0912345678"'));
      assert(csv.includes('"\'=公式測試,""引號""\n第二行"'));
      assert(!csv.includes('第二公司'));
      if(scope!=='all')assert.equal((csv.match(/總公司通知 OA/g)||[]).length,1);
    }
    await page.evaluate(()=>{state.search='';state.selected.clear();render();});
    for(const view of ['chat','cases','templates','schedule','history','personnel','org-settings','channels','personal-settings']){
      await page.evaluate(view=>navigate(view),view);
      if(view==='chat'){
        for(const width of [2560,390]){
          await page.setViewportSize({width,height:1080});
          assert(await page.locator('#workspace-tools-rail').isHidden());
          assert(await page.locator('#workspace-tools-panel').isHidden());
          assert(await page.locator('#workspace-tools-backdrop').isHidden());
          assert(await page.evaluate(()=>!document.body.classList.contains('workspace-tools-enabled')&&!document.body.classList.contains('workspace-tools-open')));
          assert(await page.evaluate(()=>Math.abs(document.querySelector('.workspace').getBoundingClientRect().right-innerWidth)<2));
          assert(await page.locator('[aria-label="聊天設定"]').isVisible());
          assert(await page.evaluate(()=>{
            const button=document.querySelector('[data-action="open-chat-settings"]'),rect=button.getBoundingClientRect(),sidebar=button.closest('.chat-sidebar-col').getBoundingClientRect(),icon=button.querySelector('svg').getBoundingClientRect();
            return rect.left>=sidebar.left&&rect.right<=sidebar.right&&rect.height>=36&&icon.left>=rect.left&&icon.right<=rect.right;
          }),'chat settings label and icon must remain inside the visible sidebar');
        }
        await page.setViewportSize({width:2560,height:1080});
        await page.evaluate(async()=>{
          chatUI.infoOpen=true;await selectChatRoom(chatUI.rooms[0].recipient_id);
          state.contacts=state.contacts.filter(r=>r.recipient_id!==chatUI.selectedId);render();
        });
        await page.locator('.chat-profile-edit-btn').click();
        await page.locator('#contact-form').waitFor();
        const contactId=await page.locator('#contact-form').getAttribute('data-id');
        assert.equal(contactId,await page.evaluate(()=>chatUI.selectedId));
        await page.locator('#contact-form [name="custom_name"]').fill('聊天編輯回歸測試');
        assert((await page.locator('#contact-form').textContent()).includes('內部分組'));
        await page.locator('#contact-form [name="contact_type"]').selectOption('person_business');
        await page.locator('#contact-form [name="work_department"]').fill('採購部');
        await page.locator('#contact-form [name="department"]').fill('北區客戶');
        await page.locator('#contact-form button[type="submit"]').click();
        await page.waitForFunction(()=>!document.getElementById('modal').open);
        await page.waitForFunction(()=>state.contacts.some(r=>r.custom_name==='聊天編輯回歸測試'));
        await page.waitForFunction(()=>document.querySelector('.chat-profile-name')?.textContent.includes('聊天編輯回歸測試'));
        await page.locator('[aria-label="編輯聯絡人標籤"]').click();
        await page.locator('#contact-form').waitFor();
        assert.equal(await page.locator('#contact-form [name="work_department"]').inputValue(),'採購部');
        assert.equal(await page.locator('#contact-form [name="department"]').inputValue(),'北區客戶');
        await page.evaluate(()=>document.getElementById('modal').close());
        await page.locator('[data-action="open-chat-settings"]').click();
        await page.locator('#chat-sticker-reply-form').waitFor();
        assert(!(await page.locator('#chat-sticker-reply-form input').isChecked()));
        for(const enabled of [true,false]){
          await page.locator('#chat-sticker-reply-form input').setChecked(enabled);
          await page.locator('#chat-sticker-reply-form button').click();
          await page.waitForFunction(enabled=>document.querySelector('[data-sticker-reply-status]')?.textContent===(enabled?'已儲存 · 貼圖自動回覆已啟用':'已儲存 · 貼圖自動回覆已關閉'),enabled);
          await page.evaluate(()=>document.getElementById('modal').close());
          await page.locator('[data-action="open-chat-settings"]').click();
          await page.locator('#chat-sticker-reply-form').waitFor();
          assert.equal(await page.locator('#chat-sticker-reply-form input').isChecked(),enabled);
        }
        await page.evaluate(()=>document.getElementById('modal').close());
        continue;
      }
      if(view==='personnel'){
        const grant=page.locator('.duty-grant-form[data-email="sender@example.test"]'),grantButton=grant.locator('button[type="submit"]');
        const original=await grant.locator('input').isChecked();
        assert(await grantButton.isDisabled());
        await grant.locator('input').setChecked(!original);
        assert((await grant.locator('[role="status"]').textContent()).includes('尚未儲存'));
        await page.route('**/api/duty/grants',async route=>{
          await new Promise(resolve=>setTimeout(resolve,300));
          await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'測試儲存失敗'})});
        },{times:1});
        await grantButton.click();
        assert.equal(await grantButton.textContent(),'儲存中…');
        assert(await grant.locator('input').isDisabled());
        await page.waitForFunction(()=>document.querySelector('.duty-grant-form [data-state="error"]'));
        assert(await grantButton.isEnabled());
        assert.equal(await grant.locator('input').isChecked(),!original);
        await grantButton.click();
        await page.waitForFunction(()=>document.querySelector('.duty-grant-form [data-state="success"]'));
        assert((await grant.locator('[role="status"]').textContent()).includes('儲存成功'));
        assert(await grantButton.isDisabled());
        await grant.locator('input').setChecked(original);
        await grantButton.click();
        await page.waitForFunction(()=>document.querySelector('.duty-grant-form[data-email="sender@example.test"]').dataset.dirty==='false');
        assert((await grant.locator('[role="status"]').textContent()).includes(original?'已授予':'已取消'));
        await page.evaluate(()=>personnelForm());
        const form=page.locator('#personnel-form');
        assert.equal(await form.locator('[name="channel_ids"]').count(),1);
        assert((await form.textContent()).includes('總公司通知 OA'));
        assert(!(await form.textContent()).includes('第二公司 OA'));
        await page.evaluate(()=>document.getElementById('modal').close());
        await page.evaluate(async()=>{
          const channel=state.channels.find(c=>c.workspace_id==='o:示範公司');
          await api('/api/personnel/save',{email:'sender@example.test',display_name:'專案發送人員',role:'operator',department:'',active:true,channel_ids:[channel.channel_id]});
          await load();render();personnelForm('sender@example.test|示範公司');
        });
        assert(await page.locator('#personnel-form [name="channel_ids"]').isChecked());
        await page.locator('#personnel-form [name="channel_ids"]').uncheck();
        await page.locator('#personnel-form button[type="submit"]').click();
        await page.waitForFunction(()=>!document.getElementById('modal').open);
        await page.waitForFunction(()=>state.memberships.find(m=>m.email==='sender@example.test'&&m.org_id==='示範公司')?.channel_ids?.length===0);
        await page.evaluate(()=>personnelForm('sender@example.test|示範公司'));
        assert(!(await page.locator('#personnel-form [name="channel_ids"]').isChecked()));
        await page.evaluate(()=>document.getElementById('modal').close());
      }
      assert.equal(await page.locator('#workspace-tools-context').textContent(),await page.evaluate(()=>titles[state.view]));
      await page.locator('[data-workspace-tool="help"]').click();
      assert(await page.locator('.workspace-tools-help li').count()>0);
      await page.locator('[data-workspace-tool="related"]').click();
      assert.equal(await page.locator('[data-workspace-tool-view]').count(),0);
    }
    await page.setViewportSize({width:390,height:844});await page.locator('[data-workspace-tool-close]').focus();
    await page.keyboard.press('Shift+Tab');assert(await page.evaluate(()=>document.querySelector('#workspace-tools-panel').contains(document.activeElement)));
    await page.locator('#workspace-tools-backdrop').click({position:{x:5,y:5}});assert(await page.locator('#workspace-tools-panel').isHidden());
    assert.deepEqual(errors,[]);
    for(const role of ['operator','platform_admin']){
      const extra=role==='operator'?{'X-Fixture-Role':role}:{},restricted=await browser.newContext({viewport:{width:1920,height:1080},extraHTTPHeaders:extra}),other=await restricted.newPage();
      try{
        await other.goto(url);await other.locator('[data-workspace-tool="related"]').click();
        assert.equal(await other.locator('[data-workspace-tool-view]').count(),0);
        if(role==='operator')assert.equal(await other.locator('[data-workspace-tool-action]').filter({hasText:'工作項目'}).count(),0);
        else assert.equal(await other.locator('[data-workspace-tool-action]').filter({hasText:'值日人員'}).count(),0);
      }finally{await restricted.close();}
    }
  }catch(error){
    console.error('Workspace tools failure context',await page.evaluate(()=>({view:state.view,role:state.session?.role,tab:dutyTab,tools:workspaceTools.tab,dirty:[...document.querySelectorAll('[data-dirty="true"]')].map(el=>el.dataset.dutyForm),tabs:[...document.querySelectorAll('[data-duty-tab]')].map(el=>el.dataset.dutyTab)})));
    throw error;
  }finally{await context.close();}
};

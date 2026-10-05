// Isolated browser validation; never opens the production database or sends LINE messages.
const fs = require('fs'), path = require('path'), assert = require('assert'), {spawn} = require('child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  const dir = path.resolve('test-results/compact_browser');
  fs.mkdirSync(dir, {recursive: true});
  const stateFile = path.join(dir, `compact-fixture-${Date.now()}.json`), stopFile = stateFile.replace(/\.json$/, '.stop');
  const child = spawn(path.resolve('.venv/Scripts/python.exe'), ['tests/workspace_fixture.py', stateFile], {windowsHide: true, stdio: ['ignore', 'ignore', 'pipe']});
  let stderr = '', browser;
  child.stderr.on('data', data => { stderr += data; });
  try {
    for (let i = 0; i < 100 && !fs.existsSync(stateFile); i++) { if (child.exitCode !== null) throw Error(stderr); await delay(100); }
    const access = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    browser = await chromium.launch({channel: 'chrome', headless: true});
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, extraHTTPHeaders: {'X-Fixture-Role': 'org_admin'}});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${access.port}/#${access.token}`);
    await page.locator('nav [data-view="templates"]').waitFor();
    await page.waitForFunction(()=>state.loaded&&lineUI.channels.length>0);
    await page.evaluate(()=>{
      window.originalSwitcherChannels=lineUI.channels;
      const current=lineUI.channels.find(c=>c.channel_id===lineUI.channel)||lineUI.channels[0];
      lineUI.channels=[current,{...current,channel_id:'switcher-other',name:'第二個 OA'}];
      openOaSwitcherModal();
    });
    const switcherRows=await page.locator('.oa-switcher-item').evaluateAll(rows=>rows.map(row=>({height:row.getBoundingClientRect().height,width:row.getBoundingClientRect().width,display:getComputedStyle(row).display,text:row.textContent})));
    assert.equal(switcherRows[0].height,switcherRows[1].height);
    assert.equal(switcherRows[0].width,switcherRows[1].width);
    assert.equal(switcherRows[0].display,'grid');
    assert(!switcherRows[0].text.includes('未指定組織'));
    await page.locator('#oa-switcher-filter').fill('不存在的 OA');
    assert(await page.locator('#oa-switcher-empty').isVisible());
    await page.locator('#modal-close').click();
    await page.evaluate(()=>{lineUI.channels=window.originalSwitcherChannels;});
    for(const width of [1920,2560,3840]){
      await page.setViewportSize({width,height:1080});
      await page.locator('nav [data-view="oa-list"]').click();
      const fullWidth=await page.locator('#content').evaluate(el=>el.getBoundingClientRect().width);
      assert.equal(await page.locator('#content').evaluate(el=>getComputedStyle(el).maxWidth),'none');
      await page.evaluate(()=>{state.globalNotesLoaded=true;state.globalNotes=[];state.globalNotesStats=null;navigate('chat-notes');});
      assert.equal(await page.locator('.notes-hub-grid').count(),0);
      assert.equal(await page.locator('#content').evaluate(el=>el.getBoundingClientRect().width),fullWidth);
      assert.equal(await page.locator('#content').evaluate(el=>getComputedStyle(el).maxWidth),'none');
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('nav [data-view="personnel"]').click();
    await page.locator('.mg-summary').waitFor();
    const personnel=await page.evaluate(()=>({counts:Array.from(document.querySelectorAll('.mg-summary .mg-stat')).map(el=>el.textContent),members:state.memberships,org:state.session.user.organization_id}));
    assert(personnel.counts[0].includes('1位管理員'),JSON.stringify(personnel.counts));
    assert(personnel.members.length>0);
    assert(personnel.members.every(member=>member.org_id===personnel.org));
    assert.equal(await page.locator('.mg-row').filter({hasText:'company-admin@example.test'}).locator('[data-action="edit-personnel"]').count(),0);
    await page.locator('nav [data-view="templates"]').click();
    const markdownCheck=await page.evaluate(()=>{
      const content='## 四、後續待辦事項\n\n1. **內部簽核與授權**\n* [ ] 於 `10/08` 前確認。\n* [ ] 諮詢法務。\n\n2. **外部客戶交付**\n* [ ] 寄送報價單。\n* [x] ~~已完成~~\n\n| 項目 | 狀態 |\n| :--- | ---: |\n| **付款條件** | 待確認 |';
      const root=document.createElement('div');root.innerHTML=renderMarkdown(content,{noteId:'md-regression',editable:true});
      return {starts:Array.from(root.querySelectorAll('ol')).map(el=>el.start),values:Array.from(root.querySelectorAll('ol li')).map(el=>el.value),checks:root.querySelectorAll('input[type="checkbox"]').length,table:root.querySelector('table')?.textContent,right:root.querySelector('th:last-child')?.className,copy:noteReadingCopy(content)};
    });
    assert.deepEqual(markdownCheck.starts,[1,2]);
    assert.deepEqual(markdownCheck.values,[1,2]);
    assert.equal(markdownCheck.checks,4);
    assert(markdownCheck.table.includes('付款條件'));
    assert.equal(markdownCheck.right,'md-align-right');
    assert(markdownCheck.copy.includes('2. 外部客戶交付')&&markdownCheck.copy.includes('☑ 已完成'),markdownCheck.copy);
    const copyFormats=await page.evaluate(()=>noteReadingCopy('前言\n\n```javascript\nconst x = 1;\n\n\n// 保留空行\n```\n\n| 項目 | 備註 |\n| --- | --- |\n| **付款** | A,B |\n| 合約 | 他說 "好" |'));
    assert(copyFormats.includes('```javascript\nconst x = 1;\n\n\n// 保留空行\n```'),copyFormats);
    assert(copyFormats.includes('項目,備註\n付款,"A,B"\n合約,"他說 ""好"""'),copyFormats);
    const editorDefaults=await page.evaluate(()=>{
      const mode=(existing,format,value)=>{const root=document.createElement('div');root.innerHTML=renderDualFormatEditor('content','test-editor',value,format,'內容',6,'',false,existing);return {mode:root.firstElementChild.dataset.subtab,text:root.querySelector('.tmpl-editor-preview-box').textContent};};
      return {fresh:mode(false,'markdown','## 新增'),saved:mode(true,'markdown','## 已儲存'),plain:mode(true,'plain','純文字'),empty:mode(true,'markdown','')};
    });
    assert.equal(editorDefaults.fresh.mode,'write');
    assert.equal(editorDefaults.saved.mode,'preview');
    assert(editorDefaults.saved.text.includes('已儲存'));
    assert.equal(editorDefaults.plain.mode,'write');
    assert.equal(editorDefaults.empty.mode,'write');
    await page.locator('nav [data-view="personal-settings"]').click();
    await page.locator('[data-personal-setting="corner"]').waitFor();
    await page.locator('[data-action="personal-preview-info"]').click();
    assert.equal(await page.locator('#floating-toast').getAttribute('data-corner'),'bottom-right');
    assert.equal(await page.locator('#notice').isVisible(),false);
    await page.locator('[data-personal-setting="corner"]').selectOption('bottom-left');
    await page.locator('[data-personal-setting="duration"]').selectOption('0');
    await page.locator('[data-personal-setting="reading"]').selectOption('large');
    const largeUi=await page.evaluate(()=>({button:document.querySelector('[data-action="personal-preview-info"]').getBoundingClientRect().height,padding:parseFloat(getComputedStyle(document.querySelector('.personal-settings-grid .panel-body')).paddingTop)}));
    assert.equal(largeUi.button,46);
    assert.equal(largeUi.padding,20);
    await page.locator('[data-personal-setting="motion"]').selectOption('reduced');
    assert.equal(await page.evaluate(()=>noticeTimeout),null);
    assert.equal(await page.locator('html').getAttribute('data-reading'),'large');
    await page.reload();
    await page.locator('[data-personal-setting="corner"]').waitFor();
    assert.equal(await page.locator('[data-personal-setting="corner"]').inputValue(),'bottom-left');
    assert.equal(await page.locator('[data-personal-setting="duration"]').inputValue(),'0');
    await page.locator('[data-personal-setting="reading"]').selectOption('small');
    assert.equal(await page.locator('html').getAttribute('data-reading'),'small');
    await page.waitForFunction(()=>parseFloat(getComputedStyle(document.querySelector('.personal-settings-grid .panel-body')).paddingTop)===10);
    const smallUi=await page.evaluate(()=>({button:document.querySelector('[data-action="personal-preview-info"]').getBoundingClientRect().height,padding:parseFloat(getComputedStyle(document.querySelector('.personal-settings-grid .panel-body')).paddingTop)}));
    assert.equal(smallUi.button,32);
    assert.equal(smallUi.padding,10);
    await page.locator('[data-personal-setting="reading"]').selectOption('standard');
    assert.equal(await page.locator('[data-personal-setting="reading"] option').count(),3);
    await page.locator('[data-personal-setting="duration"]').selectOption('1');
    await page.locator('[data-action="personal-preview-warning"]').click();
    assert.equal(await page.locator('#floating-toast').getAttribute('role'),'alert');
    await page.waitForFunction(()=>!document.querySelector('#floating-toast').classList.contains('visible'));
    await page.locator('[data-action="personal-reset"]').click();
    await page.locator('nav [data-view="templates"]').click();
    await page.locator('.tmpl-grid .tmpl-card').first().waitFor();
    await page.locator('[data-action="templates-switch-tab"][data-tab="my_templates"]').first().click();
    await page.getByRole('button', {name: '全部範本 (6)', exact: true}).waitFor();
    assert.equal(await page.locator('.tmpl-grid .tmpl-card').count(), 6);
    for (const width of [1920, 2560, 3840]) {
      await page.setViewportSize({width, height:1080});
      const layout = await page.evaluate(() => {
        const content=document.querySelector('#content'), wrap=document.querySelector('.tmpl-mgmt-wrap');
        return {max:getComputedStyle(content).maxWidth, inner:content.clientWidth-parseFloat(getComputedStyle(content).paddingLeft)-parseFloat(getComputedStyle(content).paddingRight), width:wrap.getBoundingClientRect().width};
      });
      assert.equal(layout.max, 'none');
      assert(Math.abs(layout.inner-layout.width)<2, JSON.stringify(layout));
      await page.locator('nav [data-view="cases"]').click();
      await page.locator('#case-search').waitFor();
      assert.equal(await page.locator('#content').evaluate(el=>getComputedStyle(el).maxWidth), 'none');
      await page.locator('nav [data-view="templates"]').click();
      await page.locator('.tmpl-mgmt-wrap').waitFor();
      await page.locator('.tmpl-toolbar-row .btn.primary').waitFor();
    }
    await page.setViewportSize({width:1440,height:1000});
    const dimensions = await page.evaluate(() => ({
      heading: parseFloat(getComputedStyle(document.querySelector('.page-heading')).marginBottom),
      main: parseFloat(getComputedStyle(document.querySelector('main')).paddingTop),
      button: document.querySelector('.tmpl-toolbar-row .btn.primary').getBoundingClientRect().height,
      nav: document.querySelector('nav [data-view="templates"]').getBoundingClientRect().height,
    }));
    assert(dimensions.heading <= 14 && dimensions.main <= 18 && dimensions.button <= 38 && dimensions.nav >= 42 && dimensions.nav <= 46, JSON.stringify(dimensions));
    await page.evaluate(() => {
      state.globalNotesLoaded = true;
      state.globalNotes = [{note_id: 'preview-test', recipient_id: 'contact', recipient_name: '很長的聯絡對象名稱測試', title: '預覽測試', content: '完整記事內容', category_name: '商務商談', is_pinned: true, is_locked: true, status: 'completed'}];
      navigate('chat-notes');
    });
    await page.locator('.notes-hub-card-title').dblclick();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    assert((await page.locator('.note-detail-body').textContent()).includes('完整記事內容'));
    await page.locator('#modal-close').click();
    await page.locator('[data-action="open-note-detail"]').click();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    await page.locator('#modal-close').click();
    await page.evaluate(async () => {
      const recipient = state.contacts.find(r => r.kind === 'user');
      const result = await api('/api/chat-notes', {recipient_id: recipient.recipient_id, title: '互動待辦測試', content: '```text\n- [ ] 程式範例\n```\n- [ ] 第一項\n* [x] 第二項'});
      window.taskTestId = result.note.note_id;
      await loadGlobalChatNotes();
    });
    const tasks = page.locator('.notes-hub-card input[data-note-task]');
    await tasks.first().waitFor();
    assert.equal(await tasks.count(), 2);
    const metadata = await page.locator('.note-preview-meta').first().textContent();
    for(const field of ['關聯對象', '建立時間', '分類', '標籤']) assert(metadata.includes(field));
    assert(!/U[0-9a-f]{32}/i.test(metadata));
    await tasks.first().check();
    await page.waitForFunction(() => state.globalNotes[0].content.includes('- [x] 第一項'));
    await page.locator('[data-action="open-note-detail"]').click();
    const previewTasks = page.locator('.note-detail-body input[data-note-task]');
    await previewTasks.first().waitFor();
    assert(await previewTasks.first().isChecked());
    await previewTasks.nth(1).uncheck();
    await page.waitForFunction(() => state.notePreview.content.includes('* [ ] 第二項'));
    await page.evaluate(() => {
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copiedNoteText=text;}}});
    });
    await page.locator('#modal [data-action="copy-chat-note-content"]').click();
    await page.waitForTimeout(200);
    assert(await page.locator('[data-action="copy-note-version"]').count(),JSON.stringify(await page.evaluate(()=>({busy:state.busy,content:state.notePreview.content,copied:window.copiedNoteText,error:document.querySelector('#modal-error').textContent}))));
    await page.locator('[data-action="copy-note-version"][data-id="reading"]').click();
    const readingCopy=await page.evaluate(()=>window.copiedNoteText);
    assert(readingCopy.includes('☑ 第一項') && readingCopy.includes('☐ 第二項'),readingCopy);
    assert(readingCopy.includes('- [ ] 程式範例'),readingCopy);
    assert(readingCopy.includes('```text\n- [ ] 程式範例\n```'),readingCopy);
    await page.locator('[data-action="copy-note-version"][data-id="markdown"]').click();
    assert.equal(await page.evaluate(()=>window.copiedNoteText),await page.evaluate(()=>state.notePreview.content));
    assert.equal(await page.evaluate(()=>noteReadingCopy('# 標題\n\n1. **第一點**\n2. 第二點\n\n- [ ] 未完成\n- [x] 已完成')),'標題\n\n1. 第一點\n2. 第二點\n\n☐ 未完成\n☑ 已完成');
    await page.locator('#modal-close').click();
    await page.evaluate(() => loadGlobalChatNotes());
    assert(await tasks.first().isChecked());
    assert.equal(await tasks.nth(1).isChecked(), false);
    await page.evaluate(() => { state.globalNotes[0].is_locked = true; document.getElementById('global-notes-content').innerHTML = renderGlobalNotesBody(); });
    assert(await tasks.first().isDisabled());
    for (const width of [1440, 980, 390]) {
      await page.setViewportSize({width, height: 1000});
      const overflow = await page.locator('.notes-hub-card-badges').evaluate(el => {
        const card = el.closest('.notes-hub-card').getBoundingClientRect();
        return [...el.children].some(child => { const r = child.getBoundingClientRect(); return r.right > card.right - 4 || r.left < card.left; });
      });
      assert.equal(overflow, false, `Badges overflow at ${width}px`);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Horizontal overflow at ${width}px`);
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(async () => {
      await loadGlobalChatNotes();
      const recipientId = state.globalNotes[0].recipient_id;
      const result = await api('/api/cases', {case_subject_id: recipientId, title: '聊天案件待辦測試', description: '- [ ] 案件第一項\n- [x] 案件第二項'});
      window.chatTaskCaseId = result.case.case_id;
      state.cases.push(result.case);
      await loadChatNotes(recipientId);
      chatUI.selectedId = recipientId;
      state.contacts.find(r=>r.recipient_id===recipientId).notes='聯絡人備註測試\n下午聯絡 <請先確認>';
      Object.assign(state.contacts.find(r=>r.recipient_id===recipientId), {phone:'0912-345-678',email:'customer@example.test',contact_type:'person_private',tags:[{name:'待追蹤',color:'#007AFF'}]});
      chatUI.loadingMessages = false;
      navigate('chat');
    });

    await page.locator('.chat-room-markers').first().waitFor();
    const markerId=await page.locator('.chat-room-item').first().getAttribute('data-id');
    const markerRow=page.locator('.chat-room-item[data-id="'+markerId+'"]');
    const originalOrder=await page.locator('.chat-room-item').evaluateAll(rows=>rows.map(r=>r.dataset.id).join(','));
    await markerRow.getByRole('button',{name:'星號',exact:true}).click();
    await markerRow.locator('.star.active').waitFor();
    assert.equal(await page.locator('.chat-room-item').evaluateAll(rows=>rows.map(r=>r.dataset.id).join(',')),originalOrder);
    await markerRow.getByRole('button',{name:'釘選',exact:true}).click();
    await markerRow.locator('.pin.active').waitFor();
    await markerRow.getByRole('button',{name:'紅旗',exact:true}).click();
    await markerRow.locator('.flag.active').waitFor();
    assert(await page.evaluate(async id=>{const r=(await api('/api/chat/rooms')).rooms.find(r=>r.recipient_id===id);return r.is_pinned && r.marker==='flag';},markerId));
    await page.evaluate(async id=>{await api('/api/chat/room-preference',{recipient_id:id,is_pinned:false,marker:''});await loadChatRooms();},markerId);
    const sideNote = page.locator('.chat-info-col .chat-note-item');
    assert((await page.locator('.chat-contact-note').textContent()).includes('下午聯絡 <請先確認>'));
    await page.evaluate(async()=>{
      await api('/api/org-settings/notes-policy',{note_lock_policy:'disabled',note_tag_policy:'controlled'});
      state.organizations=(await api('/api/organizations')).organizations;render();
      const org=state.organizations.find(o=>o.org_id===state.session.user.organization_id);
      if(org.note_lock_policy!=='disabled')throw Error('Policy did not persist');
    });
    await sideNote.locator('[data-action="record-lock-note"]').click();
    await sideNote.locator('.record-lock-control.locked').waitFor();
    await sideNote.locator('.chat-card-title').dblclick();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    assert.equal(await page.locator('#modal [data-action="edit-chat-note"]').count(),0);
    assert(await page.locator('.note-detail-body input[data-note-task]').first().isDisabled());
    await page.locator('#modal [data-action="record-lock-note"]').click();
    await page.locator('#modal [data-action="edit-chat-note"]').waitFor();
    await page.locator('#modal-close').click();
    await sideNote.locator('.record-lock-control svg').waitFor({state:'visible'});
    assert(await sideNote.locator('.record-lock-control').evaluate(el=>{const a=el.getBoundingClientRect(),b=el.closest('.evernote-summary').getBoundingClientRect();return a.width>=30 && a.right<=b.right && a.left>=b.left;}));

    assert.equal(await page.locator('.chat-profile-channels a[href="tel:0912-345-678"]').count(),1);
    assert.equal(await page.locator('.chat-profile-channels a[href="mailto:customer@example.test"]').count(),1);
    assert((await page.locator('.chat-profile-tags').textContent()).includes('待追蹤'));
    await sideNote.getByRole('button',{name:'釘選記事',exact:true}).click();
    await page.getByRole('button',{name:'取消釘選',exact:true}).waitFor();
    assert((await page.locator('.pinned-group > summary').textContent()).includes('已釘選'));
    await page.getByRole('button',{name:'取消釘選',exact:true}).click();
    await sideNote.getByRole('button',{name:'釘選記事',exact:true}).waitFor();
    await sideNote.locator('.chat-card-title').dblclick();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    await page.locator('.note-detail-body input[data-note-task]').first().uncheck();
    await page.waitForFunction(() => !state.globalNotes[0].content.includes('- [x] 第一項'));
    await page.locator('#modal-close').click();
    assert.equal(await page.locator('#modal').evaluate(el => el.open), false);
    await sideNote.locator('.chat-note-time').dblclick();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    await page.locator('#modal [data-action="delete-chat-note"]').waitFor();
    await page.locator('#modal [data-action="edit-chat-note"]').click();
    assert.equal(await page.locator('#chat-note-tags-input').getAttribute('type'),'hidden');
    assert.equal(await page.locator('#chat-note-form .tmpl-editor-container').getAttribute('data-subtab'),'preview');
    assert(await page.locator('#chat-note-form .tmpl-editor-preview-box').isVisible());
    await page.locator('#chat-note-form [data-action="set-md-subtab"][data-tab="write"]').click();
    assert(await page.locator('#chat-note-content-input').evaluate(el=>el.getBoundingClientRect().height>=280));
    await page.locator('[data-action="quick-add-note-tag"]').first().click();
    assert((await page.locator('#chat-note-selected-tags').textContent()).trim().length>0);
    await page.locator('#chat-note-form button[type="submit"]').click();
    await page.waitForFunction(()=>!document.getElementById('modal').open);
    assert(await page.evaluate(async()=>{try{await api('/api/chat-notes',{recipient_id:chatUI.selectedId,content:'不應建立',tags:['清單外禁止標籤']});return false;}catch(e){return e.message.includes('既有標籤');}}));
    await page.locator('[data-action="chat-work-tab"][data-id="cases"]').click();
    const sideCase = page.locator('.chat-info-col .case-item');
    await sideCase.locator('.chat-card-title').dblclick();
    await page.locator('#modal[open] .case-detail-view').waitFor();
    await page.locator('.case-description-preview input[data-case-task]').first().check();
    await page.waitForFunction(() => state.cases.some(c => c.case_id === window.chatTaskCaseId && c.description.includes('- [x] 案件第一項')));
    await page.locator('#modal-close').click();
    assert.equal(await page.locator('#modal').evaluate(el => el.open), false);
    await sideCase.locator('.chat-card-title').dblclick();
    await page.locator('#modal[open] .case-detail-view').waitFor();
    await page.locator('.case-description-preview input[data-case-task]').nth(1).uncheck();
    await page.waitForFunction(() => state.casePreview.description.includes('- [ ] 案件第二項'));
    await page.locator('#modal-close').click();
    assert.equal(await sideCase.locator('input[data-case-task]').count(), 0);
    const persistedCase = await page.evaluate(async () => (await api('/api/cases/' + window.chatTaskCaseId)).case.description);
    assert.equal(persistedCase, '- [x] 案件第一項\n- [ ] 案件第二項');
    await sideCase.locator('.record-lock-control').click();
    await sideCase.locator('.record-lock-control.locked').waitFor();
    await sideCase.locator('.chat-card-title').dblclick();
    await page.locator('#modal[open] .case-detail-view').waitFor();
    assert.equal(await page.locator('#modal [data-action="edit-case-modal"]').count(),0);
    assert(await page.locator('.case-description-preview input[data-case-task]').first().isDisabled());
    await page.locator('#modal .record-lock-control').click();
    await page.locator('#modal [data-action="edit-case-modal"]').waitFor();
    await page.locator('#modal-close').click();
    await sideCase.locator('.case-no-badge').click();
    assert.equal(await page.locator('#modal').evaluate(el=>el.open),false);
    await sideCase.locator('.case-no-badge').dblclick();
    await page.locator('#modal[open] .case-detail-view').waitFor();
    await page.locator('[data-action="edit-case-modal"]').click();
    await page.locator('#case-edit-form input[name="title"]').fill('卡片編輯後的案件');
    await page.locator('#case-edit-form button[type="submit"]').click();
    await page.locator('#modal[open] .case-detail-header h2').filter({hasText:'卡片編輯後的案件'}).waitFor();
    await page.locator('#modal-close').click();
    assert((await sideCase.textContent()).includes('卡片編輯後的案件'));
    assert.equal(await page.evaluate(async()=>(await api('/api/cases/'+window.chatTaskCaseId)).case.title),'卡片編輯後的案件');
    for(const width of [1920, 1440, 1280]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.locator('.chat-info-col').evaluate(el => el.scrollWidth > el.clientWidth + 1), false, `Side panel overflows at ${width}px`);
      assert(await page.locator('.chat-page-layout').evaluate(el => el.getBoundingClientRect().width >= innerWidth - 300));
    }
    await page.screenshot({path: path.join(dir, 'chat-sidebar-previews.png')});
    await page.evaluate(() => {
      const recipient=chatUI.selectedId;
      window.originalWorkNotes=state.chatNotes.get(recipient);
      window.originalWorkCases=state.cases;
      state.chatNotes.set(recipient, Array.from({length:41},(_,i)=>({note_id:'density-'+i,recipient_id:recipient,title:'大量記事 '+i,content:'專案進度與交接事項\n- [ ] 待確認事項',created_at:'2026-10-'+String(1+i%5).padStart(2,'0')+'T10:00:00',status:i%3===0?'completed':'pending',is_pinned:i<2,tags:['待確認'],category_name:'商務往來'})));
      state.cases=Array.from({length:26},(_,i)=>({case_id:'density-case-'+i,case_subject_id:recipient,title:'案件 '+i,status:i%3===0?'closed':'open',created_at:'2026-10-05',description:'- [ ] 追蹤進度'}));
      chatWorkView(recipient).tab='notes';refreshChatWorkPanel();
    });
    assert.equal(await sideNote.count(),12);
    assert((await sideNote.first().locator('.en-card-excerpt').textContent()).startsWith('專案進度與交接事項'));
    assert.equal(await page.locator('.chat-summary-card strong').allTextContents().then(values=>values.join(',')), '41,26,0');
    assert.equal(await page.locator('.chat-record-group').first().locator('.pinned').count(),2);
    assert((await page.locator('.chat-record-group > summary').allTextContents()).some(title=>title.includes('2026年 10月')));
    await page.locator('.pinned-group > summary').click();
    assert.equal(await page.locator('.pinned-group').evaluate(el=>el.open),false);
    await page.locator('.pinned-group > summary').click();
    await page.getByRole('button',{name:'下一頁',exact:true}).click();
    assert((await page.locator('.chat-work-pagination').textContent()).includes('13–24 / 41'));
    await page.locator('#chat-work-search').fill('大量記事 40');
    assert.equal(await sideNote.count(),1);
    await page.locator('#chat-work-search').fill('不存在的紀錄');
    await page.getByText('沒有符合的紀錄',{exact:true}).waitFor();
    await page.locator('#chat-work-search').fill('');
    await page.locator('[data-action="chat-work-filter"][data-id="pinned"]').click();
    assert.equal(await sideNote.count(),2);
    await sideNote.first().locator('.chat-card-title').click();
    assert(await sideNote.first().evaluate(el=>el.classList.contains('selected')));
    assert.equal(await page.locator('#modal').evaluate(el=>el.open),false);
    await page.locator('[data-action="chat-work-filter"][data-id="all"]').click();
    for(const width of [1920,1440,1280]){
      await page.setViewportSize({width,height:900});
      const geometry=await page.locator('.chat-work-panel').evaluate(el=>({bottom:el.getBoundingClientRect().bottom,viewport:innerHeight,overflow:el.scrollWidth>el.clientWidth+1,scroll:el.querySelector('.chat-work-results').scrollHeight>el.querySelector('.chat-work-results').clientHeight}));
      assert(geometry.bottom<=geometry.viewport && !geometry.overflow,JSON.stringify(geometry));
    }
    await page.setViewportSize({width:1920,height:1080});
    await page.evaluate(()=>{
      const notes=state.chatNotes.get(chatUI.selectedId);
      notes[1].content='![附件](/api/chat/avatar/'+chatUI.selectedId+')\n專案協商摘要：確認報價、安排導入與追蹤交付。';
      refreshChatWorkPanel();
    });
    const imageCard=page.locator('.evernote-summary.with-thumbnail').first();
    assert(await imageCard.evaluate(el=>el.querySelector('img').getBoundingClientRect().right<=el.querySelector('.en-card-main').getBoundingClientRect().left));
    assert.equal(await imageCard.locator('.chat-note-header,.chat-note-menu,.chat-note-expand-btn').count(),0);
    await page.screenshot({path:path.join(dir,'chat-work-panel-redesign.png')});
    await page.locator('[data-action="chat-work-tab"][data-id="cases"]').click();
    assert.equal(await sideCase.count(),12);
    await page.locator('[data-action="chat-work-filter"][data-id="completed"]').click();
    assert.equal(await sideCase.count(),9);
    await page.setViewportSize({width:850,height:800});
    await page.evaluate(()=>{chatUI.infoOpen=true;render();});
    assert.equal(await page.locator('.chat-info-col').evaluate(el=>getComputedStyle(el).display),'flex');
    assert(await page.locator('.chat-work-panel').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight));
    await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().right<=1);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1), 'Chat overflows on a phone');
    assert(await page.locator('.chat-work-results').evaluate(el=>el.clientHeight>100 && el.scrollHeight>el.clientHeight), 'Phone work list must remain scrollable');
    assert.equal(await page.locator('.chat-work-filters').evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
    assert(await page.locator('.chat-work-panel').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight), 'Phone panel extends below the viewport');
    await page.screenshot({path:path.join(dir,'chat-demo-mobile.png')});
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(()=>{state.chatNotes.set(chatUI.selectedId,window.originalWorkNotes);state.cases=window.originalWorkCases;});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(()=>{const view=chatWorkView(chatUI.selectedId);view.tab='notes';view.filter='all';render();});
    for(const [width,height,size] of [[1920,1080,14],[2560,1440,15],[3840,2160,16]]){
      await page.setViewportSize({width,height});
      const reading=await page.evaluate(()=>({room:parseFloat(getComputedStyle(document.querySelector('.chat-room-name')).fontSize),card:parseFloat(getComputedStyle(document.querySelector('.en-card-title .chat-card-title')).fontSize),button:parseFloat(getComputedStyle(document.querySelector('.conversation-header .btn')).fontSize),header:document.querySelector('.conversation-header').scrollWidth>document.querySelector('.conversation-header').clientWidth+1,panel:document.querySelector('.chat-work-panel').getBoundingClientRect().bottom<=innerHeight}));
      assert(reading.room>=size && reading.card>=size && reading.button>=size && !reading.header && reading.panel,JSON.stringify(reading));
      await page.screenshot({path:path.join(dir,'chat-reading-'+width+'.png')});
    }
    await page.evaluate(() => {
      chatUI.messages = [{message_id: 'msg-test', sender_user_id: 'member', sender_name: '成員 U12345', sender_name_resolved: false, direction: 'inbound', message_type: 'text', text_content: '回報進度', sent_at: '2026-10-05T04:57:00Z'}];
      chatUI.loadingMessages = false;
      chatUI.selectedId = 'contact';
      chatUI.rooms = [{recipient_id: 'contact', name: '營運群組', kind: 'group', unread_count: 0}];
      navigate('chat');
    });
    await page.locator('#chat-messages-stream').waitFor();
    assert((await page.locator('.chat-bubble-meta').textContent()).includes('成員（名稱待同步）'));
    await page.route('**/api/chat/messages?recipient_id=contact', route => route.fulfill({json: {messages: [{sender_user_id: 'member', sender_name: '王小明', sender_name_resolved: true}]}}));
    await page.evaluate(() => refreshVisibleMemberNames());
    assert.equal((await page.locator('.chat-bubble-meta').textContent()).trim(), '王小明');
    for (const width of [1440, 1280]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.getByRole('group', {name: '聊天狀態'}).evaluate(el => [...el.children].some(button => button.scrollHeight > button.clientHeight + 2)), false, `Chat status wraps at ${width}px`);
      assert.equal(await page.locator('.conversation-header').evaluate(el => el.scrollWidth > el.clientWidth + 1), false, `Chat header overflows at ${width}px`);
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.screenshot({path: path.join(dir, 'compact-chat.png')});
    await page.evaluate(()=>{
      const base=state.globalNotes[0];
      state.globalNotes=Array.from({length:12},(_,i)=>({...base,note_id:'reading-'+i,title:'客戶協商與專案交接紀錄 '+(i+1),content:'確認客戶需求、報價條件及後續安排。\n追蹤內部審核與交付時程。',is_pinned:i===0,is_locked:false,status:'active'}));
      state.globalNotesStats={total:12,pinned:1,completed:0,locked:0};state.globalNotesLoaded=true;navigate('chat-notes');
    });
    for(const [width,height,columns] of [[1920,1080,3],[2560,1440,4],[3840,2160,4]]){
      await page.setViewportSize({width,height});
      const layout=await page.locator('.notes-hub-grid').evaluate(el=>({columns:getComputedStyle(el).gridTemplateColumns.split(' ').length,overflow:document.documentElement.scrollWidth>innerWidth+1,font:parseFloat(getComputedStyle(el.querySelector('.notes-hub-card-title')).fontSize)}));
      assert.equal(layout.columns,columns);assert(!layout.overflow);assert(layout.font>=17);
      const before=await page.locator('#sidebar').evaluate(el=>el.getBoundingClientRect().width);
      await page.evaluate(()=>navigate('chat'));
      const after=await page.locator('#sidebar').evaluate(el=>el.getBoundingClientRect().width);
      assert.equal(after,before,JSON.stringify(await page.locator('#sidebar').evaluate(el=>({beforeWidth:window.innerWidth,computed:getComputedStyle(el).width,variable:getComputedStyle(el).getPropertyValue('--nav-width'),root:getComputedStyle(document.documentElement).getPropertyValue('--nav-width'),bodyClass:document.body.className,style:el.getAttribute('style')})))+' before='+before+' after='+after);
      assert(await page.locator('#sidebar nav [data-view="templates"]').evaluate(el=>getComputedStyle(el).whiteSpace==='nowrap' && el.scrollWidth<=el.clientWidth+1));
      await page.evaluate(()=>navigate('chat-notes'));

      const navigation=await page.locator('.sidebar nav [data-view="chat-notes"]').evaluate(el=>({font:parseFloat(getComputedStyle(el).fontSize),height:el.getBoundingClientRect().height,overflow:el.scrollWidth>el.clientWidth+1}));
      assert(navigation.font>=(width>=3200?18:width>=2300?16:15));assert(navigation.height>=42);assert(!navigation.overflow);

      await page.screenshot({path:path.join(dir,'notebook-reading-'+width+'.png')});
    }
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>{
      state.globalNotesLoaded=true;
      state.globalNotes=[{note_id:'phone-preview',title:'手機單次點擊預覽',content:'## 手機閱讀內容',recipient_id:'contact',category_name:'一般備忘',tags:[]}];
      navigate('chat-notes');
    });
    await page.locator('.notes-hub-card-title').click();
    await page.locator('#modal[open] .note-detail-view').waitFor();
    assert((await page.locator('.note-detail-body').textContent()).includes('手機閱讀內容'));
    await page.locator('#modal-close').click();
    const login = await context.newPage();
    await login.goto(`http://127.0.0.1:${access.port}/login`);
    assert(await login.locator('#login-submit').evaluate(el => el.getBoundingClientRect().height <= 34));
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Compact layout, six templates, preview, responsive badges and automatic member names passed');
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(stopFile, 'stop');
    for (let i = 0; i < 50 && child.exitCode === null; i++) await delay(100);
    if (child.exitCode === null) child.kill();
    for (const file of [stateFile, stopFile]) if (fs.existsSync(file)) fs.unlinkSync(file);
  }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});

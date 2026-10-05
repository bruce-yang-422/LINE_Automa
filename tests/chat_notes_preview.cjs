const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('line-oa-archive/web/admin.js', 'utf8');
const handlers = {};
const previews = [];
const context = vm.createContext({
  state: { globalNotes: [{ note_id: 'note-1', title: '測試記事', content: '完整內容', category_name: '商務商談' }], contacts: [] },
  document: { addEventListener: (name, handler) => { handlers[name] = handler; } },
  modal: (title, body) => previews.push({ title, body }),
  esc: value => value || '', icon: () => '', when: () => '',
  categoryPillHtml: name => name, renderMarkdown: text => text,
  button: text => text,
  notice: message => { throw new Error(message); },
});
vm.runInContext(source.slice(source.indexOf('function noteRecipientLabel('), source.indexOf('async function manageNotesTaxonomyModal(')), context);
vm.runInContext(source.slice(source.indexOf('document.addEventListener("dblclick"'), source.indexOf('document.addEventListener("click",async event=>{')), context);
(async () => {
  assert.equal(vm.runInContext('readonlyIcon({is_locked:false})', context), '');
  assert(vm.runInContext('readonlyIcon({is_locked:true})', context).includes('已上鎖，僅可閱覽'));
  assert(vm.runInContext('readonlyIcon({status:"closed"},true)', context).includes('已結案，僅可閱覽'));
  assert(!vm.runInContext('readonlyIcon({is_locked:true})', context).includes('<span>唯讀</span>'));
  await handlers.dblclick({ target: { closest: selector => selector === '[data-note-preview], .notes-hub-card' ? { dataset: { id: 'note-1' } } : null } });
  assert.equal(previews.length, 1);
  assert(previews[0].body.includes('完整內容'));
  assert(previews[0].body.includes('商務商談'));
  await handlers.dblclick({ target: { closest: () => ({ dataset: { id: 'note-1' } }) } });
  assert.equal(previews.length, 1, 'Interactive controls must not trigger a second preview');
  context.state.busy = true;
  await handlers.dblclick({ target: { closest: () => ({ dataset: { id: 'note-1' } }) } });
  assert.equal(previews.length, 1);
  assert(source.includes('else if(action==="open-note-detail")await chatNoteDetailModal(id);'));
  console.log('Chat note preview checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });

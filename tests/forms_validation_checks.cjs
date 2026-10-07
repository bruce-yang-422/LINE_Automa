// The same JSON vectors are consumed by Python and the browser validation module.
const assert=require('assert'),fs=require('fs');
const validation=require('../line-oa-archive/web/forms-validation.js');
const rules=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
validation.configure(rules);
const cases=JSON.parse(fs.readFileSync('line-oa-archive/tests/form_validation_vectors.json','utf8'));
for(const test of cases){
  const before=JSON.stringify(test.answers),expected=Object.fromEntries(Object.entries(test.expected).map(([id,code])=>[id,code==='custom'?test.questions.find(q=>q.id===id).validation.message:rules.messages[code]]));
  assert.deepStrictEqual(validation.validateAnswers(test.questions,test.answers),expected,test.name);
  assert.equal(JSON.stringify(test.answers),before,'mutated answer: '+test.name);
}
console.log(`${cases.length} JavaScript form validation vectors passed`);

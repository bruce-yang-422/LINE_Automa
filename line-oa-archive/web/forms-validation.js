"use strict";
// Algorithms mirror forms_validation.py; patterns, labels and limits come from one JSON definition.
const FormValidation=(()=>{
  let rules=null;
  const configure=value=>{rules=value;};
  const match=(name,value)=>{if(typeof value!=='string')return false;const pattern=rules.patterns[name].replaceAll('\\s',rules.patterns.space.slice(1,-1)),found=new RegExp(pattern).exec(value);return Boolean(found&&found.index===0&&found[0]===value);};
  const trim=value=>value.replace(new RegExp('^'+rules.patterns.space+'+|'+rules.patterns.space+'+$','g'),'');
  function number(value){
    if(!['number','string'].includes(typeof value))return null;
    if(typeof value==='string'&&!match('number',trim(value)))return null;
    const result=Number(typeof value==='string'?trim(value):value);return Number.isFinite(result)?result:null;
  }
  function validDate(value){
    if(!match('date',value))return false;
    const [y,m,d]=value.split('-').map(Number),leap=y%4===0&&(y%100!==0||y%400===0),days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
    return y>=1&&m>=1&&m<=12&&d>=1&&d<=days[m-1];
  }
  const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
  const length=value=>Array.from(value).length;
  function answerError(q,value){
    const kind=q.type,v=q.validation||{},enabled=v.enabled||false;
    let other='',selections=null;
    if(rules.choice_types.includes(kind)&&value!==null&&value!==undefined){
      const multiple=kind==='multiple_choice';let selected;
      if(plain(value)){
        if(Object.keys(value).some(k=>!(multiple?['option_ids','other']:['option_id','other']).includes(k)))return ['structure',false];
        const key=multiple?'option_ids':'option_id';selected=Object.hasOwn(value,key)?value[key]:(multiple?[]:'');other=Object.hasOwn(value,'other')?value.other:'';
      }else selected=value;
      selections=multiple?selected:(selected===''?[]:[selected]);
      if(!Array.isArray(selections)||selections.some(item=>typeof item!=='string')||new Set(selections).size!==selections.length||typeof other!=='string')return ['structure',false];
      const valid=new Set(q.options.map(o=>o.id));if(q.allow_other)valid.add(rules.other_id);
      if(selections.some(item=>!valid.has(item)))return ['choice',false];
      if(length(other)>rules.limits.FORM_TEXT_MAX)return ['text_limit',false];
      if(selections.includes(rules.other_id)&&!trim(other))return ['other',false];
      if(trim(other)&&!selections.includes(rules.other_id))return ['choice',false];
    }
    const empty=value===null||value===undefined||(typeof value==='string'&&!trim(value))||(selections!==null&&!selections.length)||(kind==='attachment'&&Array.isArray(value)&&value.length===0);
    if(empty)return [q.required?'required':null,false];
    if(rules.text_types.includes(kind)){
      if(typeof value!=='string')return ['text',false];
      if(length(value)>rules.limits.FORM_TEXT_MAX)return ['text_limit',false];
      if(enabled){
        if(length(value)<(v.min_length??0)||length(value)>(v.max_length??rules.limits.FORM_TEXT_MAX))return ['length',true];
        if(v.format==='email'&&!match('email',trim(value)))return ['email',true];
        if(v.format==='phone'){
          const mode=v.phone_mode||'tw_mobile';let phone=value.replace(new RegExp(rules.patterns.space+'|-','g'),'');
          const extension=new RegExp(rules.patterns.extension).exec(phone);
          if(extension){if(mode!=='tw_landline'||!v.allow_extension)return ['phone',true];phone=phone.slice(0,extension.index);}
          if(!match(mode,phone))return ['phone',true];
        }
      }
    }else if(kind==='number'||kind==='rating'){
      const numeric=number(value);if(numeric===null)return ['number',false];
      const conditions=kind==='rating'?(q.rating||rules.rating_default):(enabled?v:{});
      if((kind==='rating'||conditions.integer)&&!Number.isInteger(numeric))return ['integer',kind!=='rating'];
      if(('min' in conditions&&numeric<conditions.min)||('max' in conditions&&numeric>conditions.max))return ['range',kind!=='rating'];
    }else if(kind==='multiple_choice'&&enabled){
      const count=selections.length;
      if(count<(v.count_min??0)||count>(v.count_max??(q.options.length+Number(Boolean(q.allow_other))))||('count_exact' in v&&count!==v.count_exact))return ['count',true];
    }else if(kind==='date'){
      if(!validDate(value))return ['date',false];
      if(enabled&&(value<(v.date_min??'0001-01-01')||value>(v.date_max??'9999-12-31')))return ['date_range',true];
    }else if(kind==='time'){
      if(!match('time',value))return ['time',false];
    }else if(kind==='attachment')return ['attachment',false];
    return [null,false];
  }
  function validateAnswers(questions,answers){
    if(!plain(answers))return {_form:rules.messages.structure};
    const errors={},active=new Set(questions.filter(q=>q.type!=='section').map(q=>q.id));
    if(Object.keys(answers).some(id=>!active.has(id)))errors._form=rules.messages.unknown;
    for(const q of questions){if(q.type==='section')continue;const [code,custom]=answerError(q,answers[q.id]);if(code)errors[q.id]=custom&&q.validation?.message?q.validation.message:rules.messages[code];}
    return errors;
  }
  return {configure,validateAnswers,validDate,number,trim,get rules(){return rules;}};
})();
if(typeof module!=='undefined')module.exports=FormValidation;

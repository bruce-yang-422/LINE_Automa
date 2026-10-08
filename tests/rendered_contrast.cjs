const assert=require('assert');
async function contrast(page,label){
  const result=await page.evaluate(()=>{
    const failures=[],pairs=new Map();let checked=0;
    const parse=value=>{const parts=value.match(/[\d.]+/g)?.map(Number);return parts?.length>=3?[...parts.slice(0,3),parts[3]??1]:[0,0,0,0];};
    const blend=(fg,bg)=>fg.slice(0,3).map((n,i)=>n*fg[3]+bg[i]*(1-fg[3]));
    const luminance=rgb=>rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((v,n,i)=>v+n*[.2126,.7152,.0722][i],0);
    const background=el=>{const chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);return chain.reduce((bg,p)=>blend(parse(getComputedStyle(p).backgroundColor),bg),[255,255,255]);};
    function check(el,style,text,bg,kind='text'){
      const fg=blend(parse(style.color),bg),a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
      const key=style.color+' / '+bg.map(n=>Math.round(n)).join(',');pairs.set(key,ratio);checked++;
      if(ratio<4.5)failures.push({element:el.tagName+'.'+el.className,kind,text:text.slice(0,65),ratio:Number(ratio.toFixed(3)),colors:key});
    }
    for(const el of document.querySelectorAll('body *')){
      const style=getComputedStyle(el),rect=el.getBoundingClientRect();
      if(!rect.width||!rect.height||rect.right<=0||style.visibility!=='visible'||['SCRIPT','STYLE','OPTION'].includes(el.tagName)||el.closest('svg'))continue;
      const text=[...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join('').trim();
      const bg=background(el);
      if(text)check(el,style,text,bg);
      if(el.matches('input:not([type=checkbox]):not([type=hidden]),textarea,select')){
        check(el,style,el.value||el.tagName,bg,'control');
        if(el.placeholder)check(el,getComputedStyle(el,'::placeholder'),el.placeholder,bg,'placeholder');
      }
      if(el.matches('input[type=file]')){
        const pseudo=getComputedStyle(el,'::file-selector-button');check(el,pseudo,'選擇檔案',blend(parse(pseudo.backgroundColor),bg),'file button');
      }
      for(const pseudo of ['::before','::after']){
        const s=getComputedStyle(el,pseudo);
        if(s.content&&!['none','normal','""'].includes(s.content))check(el,s,s.content,blend(parse(s.backgroundColor),bg),pseudo);
      }
    }
    return {checked,minimum:Math.min(...pairs.values()),pairs:Object.fromEntries(pairs),failures};
  });
  assert.equal(result.failures.length,0,label+': '+JSON.stringify(result.failures));
  return {label,...result};
}
module.exports=contrast;

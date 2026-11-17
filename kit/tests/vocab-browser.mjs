// 单次匿名离线浏览器覆盖17配方、6转场、3层；不访问网络和个人浏览器。
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {prepareVocab,VOCAB_TRANSITIONS,VOCAB_LAYERS} from '../template/vocab-props.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../template');
const require=createRequire(path.join(root,'package.json'));
const {chromium}=require(process.env.YICE_PLAYWRIGHT_MODULE||'playwright-core');
const gsapFile=process.env.YICE_GSAP_PATH;
if(!gsapFile||!fs.existsSync(gsapFile))throw new Error('离线浏览器单测需要 YICE_GSAP_PATH 指向本机 gsap.min.js');
const examples=JSON.parse(fs.readFileSync(path.join(root,'vocab-examples.json'))),results={};
const fixture=`<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/assets/frame.css"><link rel="stylesheet" href="/assets/vocab.css"><script src="/gsap.js"></script><script src="/assets/yice.js"></script><script src="/assets/vocab.js"></script><body style="margin:0"><div id="fixture" style="position:relative;width:1920px;height:1080px"></div>`;
const server=http.createServer((req,res)=>{
  const name=decodeURIComponent(req.url.split('?')[0]);
  if(name==='/'){res.setHeader('Content-Type','text/html');res.end(fixture);return;}
  const file=name==='/gsap.js'?gsapFile:path.join(root,name);
  if(!file.startsWith(root)&&file!==gsapFile){res.writeHead(403).end();return;}
  if(!fs.existsSync(file)){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(fs.readFileSync(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true,channel:'chrome'}),page=await browser.newPage({viewport:{width:1920,height:1080}});
try{
  for(const [kind,names]of [['recipe',Object.keys(examples)],['transition',VOCAB_TRANSITIONS],['layer',VOCAB_LAYERS],['layout',['title-free']]])for(const name of names){
    let errors=[];const onError=e=>errors.push(e.message);page.on('pageerror',onError);
    try{
      const recipe=kind==='recipe'?name:kind==='layout'?'device-stage':'headline-slam',props={...examples[recipe],...(kind==='layout'?{showTitle:false}:{})},prepared=prepareVocab({recipe,props,stage:props.stage||'paper-cool'});
      await page.goto(`http://127.0.0.1:${server.address().port}/`);await page.evaluate(()=>document.fonts.ready);
      const value=await page.evaluate(({kind,name,recipe,prepared})=>{
        const sid='test',holder=document.getElementById('fixture'),source='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#E4E6E2"/><path d="M0 540H1920M960 0V1080" stroke="#2C57C9"/></svg>');
        const spec={props:prepared.props,stage:prepared.props.stage||'paper-cool',dur:3,enter:kind==='transition'?name:'cut',exit:'cut',chapterTitle:'单测',episodeId:'test',t0:0,layers:kind==='layer'?[{kind:name,items:[{text:'已下载'}]}]:[]};
        holder.innerHTML=`<div id="test-root"><div id="test-holder">${prepared.media.map((_,i)=>`<img id="test-m${i}" src="${source}">`).join('')}</div><script type="application/json" id="test-spec">${JSON.stringify(spec).replace(/</g,'\\u003c')}</script></div>`;
        window.__timelines={};
        YV.render(recipe,YF.ctx(sid,document.getElementById('test-root')));
        const tl=window.__timelines[sid];tl.seek(.2,false);const before=holder.innerHTML;tl.seek(2.2,false);const after=holder.innerHTML;
        const styles=[...holder.querySelectorAll('[style]')].map(e=>e.getAttribute('style'));
const luminance=color=>color.match(/[\d.]+/g).slice(0,3).map(v=>{const c=+v/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
        const checks={timeline:tl.duration()>=.5,finite:!styles.some(s=>/NaN|Infinity/.test(s)),motion:before!==after,rendered:!!holder.querySelector('.yv'),text:holder.innerText.length>0,frameHud:!!holder.querySelector('.yf-hud .ruler-t')&&!!holder.querySelector('.yf-hud .tc')};
        const heading=holder.querySelector('.v-heading');
        if(heading){tl.seek(.7,false);checks.titleVisible=+getComputedStyle(heading).opacity>.99;tl.seek(spec.dur-.5,false);checks.titleRetiresBeforeOverlap=+getComputedStyle(heading).opacity===0;tl.seek(2.2,false);}
        if(kind==='layout')checks.titleFree=!heading;
        if(['headline-slam','word-swap'].includes(name))checks.intrinsicTitleFree=!heading;
        if(name==='word-swap')checks.wordsHaveContrast=[...holder.querySelectorAll('.v-swap-word')].every(e=>{const v=getComputedStyle(e);return (luminance(v.backgroundColor)+.05)/(luminance(v.color)+.05)>=4.5;});
        if(name==='social-post')checks.redaction=!holder.innerText.includes('需要隐去的姓名')&&!holder.innerText.includes('@private');
        if(name==='cursor-zoom'){const a=holder.querySelector('.v-world').style.transform;tl.seek(.3,false);tl.seek(2.2,false);checks.deterministic=a===holder.querySelector('.v-world').style.transform;}
        if(name==='rank-race'){
          const widths=()=>[...holder.querySelectorAll('.v-race-bar')].map(e=>parseFloat(e.style.width));
          checks.frameRelativeScale=Math.max(...widths())>940;
          checks.compactCard=parseFloat(holder.querySelector('.v-race-card').style.height)<450;
          tl.seek(0,false);checks.growsFromZero=Math.max(...widths())===0;tl.seek(2.2,false);
          const remaining=new Set(prepared.props.frames.at(-1).items.map(x=>x.label));
          checks.departedRowsStayHidden=[...holder.querySelectorAll('.v-race-row')].filter(e=>!remaining.has(e.dataset.label)).every(e=>+e.style.opacity===0);
          checks.rankLabelsDoNotCross=true;
          for(let time=.2;time<2.6;time+=.2){tl.seek(time,false);const labels=[...holder.querySelectorAll('.v-race-row > .v-label')].filter(e=>+getComputedStyle(e).opacity*+getComputedStyle(e.parentElement).opacity>.1).map(e=>e.getBoundingClientRect());for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++)if(labels[i].top<labels[j].bottom&&labels[j].top<labels[i].bottom)checks.rankLabelsDoNotCross=false;}
          tl.seek(2.2,false);
        }
        if(name==='terminal-run'){
          const box=holder.querySelector('.v-terminal'),row=getComputedStyle(holder.querySelector('.v-terminal-row')),stamp=getComputedStyle(holder.querySelector('.v-terminal-stamp'));
          checks.terminal30px=parseFloat(row.fontSize)===30;
          checks.sixLineHeight=parseFloat(box.style.height)>=6*parseFloat(row.lineHeight)+76;
          checks.compactTerminal=parseFloat(box.style.height)<520;
          checks.stampContrast=(luminance(stamp.backgroundColor)+.05)/(luminance(stamp.color)+.05)>=4.5;
        }
        if(name==='bar-compare'){
          const bars=[...holder.querySelectorAll('.v-bar-column')];
          checks.narrowBars=bars.every(e=>parseFloat(e.style.width)>=120&&parseFloat(e.style.width)<=160);
          checks.paperTexture=bars.every(e=>getComputedStyle(e,'::after').backgroundImage!=='none');
          if(prepared.props.items.length===2){const delta=(prepared.props.items[1].value/prepared.props.items[0].value-1)*100;checks.measuredChange=holder.querySelector('.v-measure-label')?.textContent===(delta<0?'−':'+')+Math.abs(delta).toFixed(1)+'%';}
        }
        if(name==='photo-path'){
          checks.photos=holder.querySelectorAll('.v-media').length===prepared.props.images.length;
          const cards=[...holder.querySelectorAll('.v-card')];
          checks.dimNotTransparent=cards.filter((_,i)=>i!==prepared.props.focus).every(e=>getComputedStyle(e).opacity==='1'&&getComputedStyle(e).filter==='brightness(0.6)');
          checks.photoFillsPrint=[...holder.querySelectorAll('.v-media')].every(e=>getComputedStyle(e).objectFit==='cover');
        }
        if(name==='news-card')checks.highlights=holder.querySelectorAll('.v-highlight').length===prepared.props.highlight.length;
        if(name==='code-diff')checks.diff=holder.querySelectorAll('.v-code-row.del').length>0&&holder.querySelectorAll('.v-code-row.add').length>0;
        if(kind==='layer'){checks.layer=!!holder.querySelector(name==='grain-overlay'?'.v-grain':name==='light-sweep-pass'?'.v-sweep':'.v-notification');if(name==='grain-overlay')checks.strength=getComputedStyle(holder.querySelector('.v-grain')).opacity==='0.06';}
        return {checks,ok:Object.values(checks).every(Boolean)};
      },{kind,name,recipe,prepared});
      results[kind+':'+name]={...value,errors,ok:value.ok&&!errors.length};
    }catch(error){results[kind+':'+name]={ok:false,error:error.stack?.slice(0,1800)||error.message};}
    page.off('pageerror',onError);
  }
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
console.log(JSON.stringify(results));

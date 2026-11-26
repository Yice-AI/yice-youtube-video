const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const os = require('node:os');
const search = [process.cwd(), __dirname, path.join(os.homedir(),'.codex/skills/guizang-social-card-skill'),
                ...((process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean))];
const { chromium } = require(process.env.YICE_PLAYWRIGHT_MODULE || require.resolve('playwright-core',{paths:search}));

async function measure(page, {entry,seconds}) {
  await page.goto(pathToFileURL(entry).href);
  const fragment = await page.locator('head > template, body > template').first().evaluateAll(nodes=>nodes[0]?.innerHTML);
  if (fragment) {
    await page.evaluate(html=>{document.open(); document.write('<!doctype html><meta charset="utf-8">'+html); document.close();}, fragment);
    await page.waitForFunction(()=>window.__seek || Object.keys(window.__timelines || {}).length,{},{timeout:5000});
  }
  await page.addStyleTag({content:'html,body{margin:0}'});
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(Array.from(document.images, image => image.decode()));
    await window.__ready;
  });
  const frames = [];
  const duration = await page.evaluate(span => {
    const authored = window.__meta?.dur ?? Object.values(window.__timelines || {})[0]?.duration();
    if (!(authored > 0)) throw Error('缺少可定位的合成时间轴');
    return Math.min(span || authored, authored);
  }, seconds);
  const witnesses = [0.03,0.12,0.25,0.38,0.5,0.63,0.75,0.88,0.97];
  const phases = new Set([...witnesses,...Array.from({length:Math.ceil(duration*30)},(_,i)=>i/30/duration)]);
  for (const phase of [...phases].sort((a,b)=>a-b)) {
    const boxes = await page.evaluate(({phase,duration}) => {
      const timeline = Object.values(window.__timelines || {})[0];
      if (window.__seek) window.__seek(phase * duration);
      else if (timeline) timeline.seek(phase * duration, false);
      else throw Error('缺少可定位的合成时间轴');
      const visible = el => {
        let opacity = 1;
        for (let node = el; node; node = node.parentElement) {
          const style = getComputedStyle(node);
          if (style.visibility === 'hidden' || style.display === 'none') return false;
          opacity *= Number(style.opacity);
        }
        return opacity > 0.15;
      };
      function rects(selector) {
        return Array.from(document.querySelectorAll(selector)).filter(visible).map(el => {
          const r = el.getBoundingClientRect();
          return [Math.max(0,r.left), Math.max(0,r.top), Math.min(innerWidth,r.right), Math.min(innerHeight,r.bottom)];
        }).filter(([x,y,r,b]) => r>x && b>y);
      }
      const subjects = '[data-spatial-subject],.orbit-card,.node,.old-card,.model,[data-spatial-layer],.file-card,.slidecard,.station,.file,.locked-shot,.slots,.plan-lines';
      const titles = rects('[data-spatial-title], header, h1, [role="heading"], .headline, .slide-title');
      const cards = rects(subjects);
      const overlaps = titles.flatMap(t => cards.map(c => Math.max(0,Math.min(c[2],t[2])-Math.max(c[0],t[0])) *
        Math.max(0,Math.min(c[3],t[3])-Math.max(c[1],t[1])))).filter(a => a>0);
      const stations = phase >= .38 && phase <= .51 ? Array.from(document.querySelectorAll('[data-overview-station]'), el => {
        const bounds=el.getBoundingClientRect();
        return [bounds.left,bounds.right];
      }) : [];
      return {phase, overlaps, cards, titles, stations, exploded:!!document.querySelector('[data-spatial-recipe="layer_explode_3d"]')};
    }, {phase,duration});
    if ([0.12,0.5,0.88].includes(phase)) {
      const image = await page.screenshot();
      boxes.samples = await page.evaluate(async encoded => {
        const img = new Image(); img.src='data:image/png;base64,'+encoded; await img.decode();
        const canvas = document.createElement('canvas'); canvas.width=img.width; canvas.height=img.height;
        const ctx=canvas.getContext('2d'); ctx.drawImage(img,0,0); const data=ctx.getImageData(0,0,img.width,img.height).data;
        const groups={}, hues={};
        for (let y=3; y<img.height; y+=6) for (let x=3; x<img.width; x+=6) {
          const i=4*(y*img.width+x), r=data[i], g=data[i+1], b=data[i+2];
          const hi=Math.max(r,g,b), lo=Math.min(r,g,b), chroma=hi-lo, luma=.2126*r+.7152*g+.0722*b;
          if (luma<135 || chroma<55) continue;
          const hue=(360+60*(hi===r?(g-b)/chroma:hi===g?2+(b-r)/chroma:4+(r-g)/chroma))%360;
          const band=Math.floor((hue+15)%360/30);
          hues[band]=(hues[band] || 0)+1;
        }
        for (let y=5; y<innerHeight; y+=10) for (let x=5; x<innerWidth; x+=10) {
          const stack=document.elementsFromPoint(x,y);
          const layer=stack.map(el => el.closest('[data-spatial-layer]')).find(Boolean);
          const margin=x<70 || x>innerWidth-70 || y<45 || y>innerHeight-70;
          const group=layer?.dataset.spatialLayer || (margin && 'background');
          if (!group) continue;
          const i=4*(y*img.width+x), r=data[i], g=data[i+1], b=data[i+2];
          const luma=.2126*r+.7152*g+.0722*b, chroma=Math.max(r,g,b)-Math.min(r,g,b);
          const value=groups[group] ||= {n:0,sum:0,chroma:0,light:[]};
          value.n++; value.sum+=luma; value.chroma+=chroma;
          if (chroma>=55) value.light.push(luma);
        }
        const samples={highlights:hues};
        for (const [key,v] of Object.entries(groups)) {
          v.light.sort((a,b)=>b-a);
          const bright=v.light.slice(0,Math.ceil(v.n*.10));
          samples[key]={n:v.n,luma:v.sum/v.n,chroma:v.chroma/v.n,lit:bright.length,
                        highlightLuma:bright.length?bright.reduce((a,b)=>a+b)/bright.length:0};
        }
        return samples;
      }, image.toString('base64'));
    }
    if (witnesses.includes(phase) || boxes.overlaps.length || boxes.titles.some(([x,y,r,b])=>x<760 && y<210 && b-y>34)) frames.push(boxes);
  }
  return frames;
}

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.YICE_CHROME_EXECUTABLE || undefined});
  const results = {};
  try {
    for (const [id,entry] of Object.entries(JSON.parse(fs.readFileSync(0,'utf8')))) {
      const page=await browser.newPage({viewport:{width:1920,height:1080}});
      await page.route(/^https?:/,route=>route.abort());
      try { results[id]={frames:await measure(page,entry)}; }
      catch (e) { results[id]={error:String(e.message)}; }
      finally { await page.close(); }
    }
    process.stdout.write(JSON.stringify(results));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});

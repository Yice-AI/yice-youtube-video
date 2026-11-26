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
      const titles = rects('[data-spatial-title], header, h1');
      const cards = rects(subjects);
      const overlaps = titles.flatMap(t => cards.map(c => Math.max(0,Math.min(c[2],t[2])-Math.max(c[0],t[0])) *
        Math.max(0,Math.min(c[3],t[3])-Math.max(c[1],t[1])))).filter(a => a>0);
      return {phase, overlaps, cards, titles, exploded:!!document.querySelector('[data-spatial-recipe="layer_explode_3d"]')};
    }, {phase,duration});
    if (phase === 0.88) {
      const image = await page.screenshot();
      boxes.samples = await page.evaluate(async encoded => {
        const img = new Image(); img.src='data:image/png;base64,'+encoded; await img.decode();
        const canvas = document.createElement('canvas'); canvas.width=img.width; canvas.height=img.height;
        const ctx=canvas.getContext('2d'); ctx.drawImage(img,0,0); const data=ctx.getImageData(0,0,img.width,img.height).data;
        const groups={};
        for (let y=10; y<innerHeight; y+=20) for (let x=10; x<innerWidth; x+=20) {
          const stack=document.elementsFromPoint(x,y);
          const layer=stack.map(el => el.closest('[data-spatial-layer]')).find(Boolean);
          const margin=x<70 || x>innerWidth-70 || y<45 || y>innerHeight-70;
          const group=layer?.dataset.spatialLayer || (margin && 'background');
          if (!group) continue;
          const i=4*(y*img.width+x), rgb=[data[i],data[i+1],data[i+2]];
          const g=groups[group] ||= {n:0,sum:0,chroma:0};
          g.n++; g.sum+=rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722; g.chroma+=Math.max(...rgb)-Math.min(...rgb);
        }
        return Object.fromEntries(Object.entries(groups).map(([key,g])=>[key,{n:g.n,luma:g.sum/g.n,chroma:g.chroma/g.n}]));
      }, image.toString('base64'));
    }
    if (witnesses.includes(phase) || boxes.overlaps.length) frames.push(boxes);
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

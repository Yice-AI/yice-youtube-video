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
    await Promise.all(Array.from(document.images, image => image.decode().catch(()=>{})));
    await Promise.all(Array.from(document.querySelectorAll('video'), v =>
      v.readyState >= 1 ? Promise.resolve() : new Promise(res => {
        const done = () => res();
        v.addEventListener('loadedmetadata', done, {once:true});
        v.addEventListener('error', done, {once:true});
        setTimeout(done, 2500);
      })
    ));
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
    const syncVideos = witnesses.includes(phase);
    const boxes = await page.evaluate(async ({phase,duration,syncVideos}) => {
      const timeline = Object.values(window.__timelines || {})[0];
      const t = phase * duration;
      if (window.__seek) window.__seek(t);
      else if (timeline) timeline.seek(t, false);
      else throw Error('缺少可定位的合成时间轴');
      if (syncVideos) {
        const vids = Array.from(document.querySelectorAll('video'));
        await Promise.all(vids.map(v => {
          const d = (Number.isFinite(v.duration) && v.duration > 0) ? v.duration : duration;
          const target = Math.min(Math.max(0, d - 0.05), Math.max(0, t % d));
          if (Math.abs(v.currentTime - target) < 0.02 && v.readyState >= 2) return Promise.resolve();
          return new Promise(res => {
            const done = () => res();
            v.addEventListener('seeked', done, {once:true});
            v.addEventListener('error', done, {once:true});
            v.currentTime = target;
            setTimeout(done, 800);
          });
        }));
      }
      const visible = el => {
        let opacity = 1;
        for (let node = el; node; node = node.parentElement) {
          const style = getComputedStyle(node);
          if (style.visibility === 'hidden' || style.display === 'none') return false;
          opacity *= Number(style.opacity);
        }
        return opacity > 0.15;
      };
      function rects(selector, excludeIntentional = false) {
        return Array.from(document.querySelectorAll(selector)).filter(el => {
          if (!visible(el)) return false;
          if (!excludeIntentional) return true;
          const holder = el.dataset?.titleKind ? el : el.closest('[data-title-kind]');
          const kind = holder?.dataset?.titleKind;
          if (!kind) return true;
          const r = holder.getBoundingClientRect();
          if (kind === 'editorial_single' && r.height <= 68) return false;
          if (kind === 'archive_plaque' && r.width <= 380 && r.height <= 160) return false;
          return true;
        }).map(el => {
          const r = el.getBoundingClientRect();
          return [Math.max(0,r.left), Math.max(0,r.top), Math.min(innerWidth,r.right), Math.min(innerHeight,r.bottom)];
        }).filter(([x,y,r,b]) => r>x && b>y);
      }
      const subjects = '[data-spatial-subject],.orbit-card,.node,.old-card,.model,[data-spatial-layer],.file-card,.slidecard,.station,.file,.locked-shot,.slots,.plan-lines,.fan-card,.bento-col,.doc-frame,.doc-anatomy-card,.tree-branch,.tree-child,.sim-card,.chain-frame,.compare-stage,.race-col';
      const titleSel = '[data-spatial-title], header, h1, [role="heading"], .headline, .slide-title';
      const allTitles = rects(titleSel, false);
      const titles = rects(titleSel, true);
      const cards = rects(subjects);
      const overlaps = allTitles.flatMap(t => cards.map(c => Math.max(0,Math.min(c[2],t[2])-Math.max(c[0],t[0])) *
        Math.max(0,Math.min(c[3],t[3])-Math.max(c[1],t[1])))).filter(a => a>0);
      const stations = phase >= .38 && phase <= .51 ? Array.from(document.querySelectorAll('[data-overview-station]'), el => {
        const bounds=el.getBoundingClientRect();
        return [bounds.left,bounds.right];
      }) : [];
      const aspectCrops = [];
      for (const el of document.querySelectorAll('img,video')) {
        if (!visible(el) || el.matches('.media-aspect-bg,[data-allow-crop="true"]')) continue;
        if (el.matches('.curtain-panel video') && !el.closest('[data-allow-crop="false"]')) continue;
        const box = el.getBoundingClientRect();
        if (box.width < 120 || box.height < 90 || box.right <= 0 || box.bottom <= 0 ||
            box.left >= innerWidth || box.top >= innerHeight || getComputedStyle(el).objectFit !== 'cover') continue;
        const nw = el.videoWidth || el.naturalWidth, nh = el.videoHeight || el.naturalHeight;
        if (!nw || !nh || !el.clientHeight) continue;
        const ratio = (el.clientWidth / el.clientHeight) / (nw / nh);
        const crop = 1 - Math.min(ratio, 1 / ratio);
        if (crop > .12) aspectCrops.push({reason:'excessive_aspect_crop', source:el.getAttribute('src'),
          natural:[nw,nh], layout:[el.clientWidth,el.clientHeight], crop_ratio:+crop.toFixed(4)});
      }
      const containerOverflows = [];
      const textBoxViolations = [];
      if (phase >= 0.35) {
        const containers = Array.from(document.querySelectorAll('.bento-box,.sim-panel,.tree-branch'));
        for (const box of containers) {
          if (!visible(box)) continue;
          const pr = box.getBoundingClientRect();
          if (pr.width < 20 || pr.height < 20) continue;
          const kids = box.querySelectorAll('.bento-item,.bento-logo-wrap,.bento-item-name,.sim-bar-group');
          for (const kid of kids) {
            if (!visible(kid)) continue;
            const kr = kid.getBoundingClientRect();
            if (kr.top < pr.top - 4 || kr.bottom > pr.bottom + 4 || kr.left < pr.left - 4 || kr.right > pr.right + 4) {
              containerOverflows.push(Math.round(Math.max(pr.top - kr.top, kr.bottom - pr.bottom, pr.left - kr.left, kr.right - pr.right)));
            }
          }
          const cat = box.parentElement?.querySelector('.bento-cat');
          if (cat && visible(cat)) {
            const cr = cat.getBoundingClientRect();
            if (pr.bottom > cr.top + 2) {
              containerOverflows.push(Math.round(pr.bottom - cr.top));
            }
          }
        }
        const parseRgb = str => {
          const m = str && str.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?/);
          return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
        };
        const relLum = ([r, g, b]) => {
          const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
          return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
        };
        const effectiveBg = el => {
          for (let cur = el; cur && cur !== document.documentElement; cur = cur.parentElement) {
            const st = getComputedStyle(cur);
            const c = parseRgb(st.backgroundColor);
            if (c && c[3] >= 0.65) return c;
            if (st.backgroundImage && st.backgroundImage !== 'none') {
              const stops = [...st.backgroundImage.matchAll(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?\)/g)]
                .map(m => [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]]).filter(x => x[3] >= 0.5);
              if (stops.length) {
                const avg = [0, 1, 2].map(k => stops.reduce((s, v) => s + v[k], 0) / stops.length);
                return [...avg, 1];
              }
            }
          }
          return null;
        };
        const boxSelectors = '.tree-branch,.tree-child,.node,.bento-item,.workbench-chip,.workbench-label,.pill-src,.pill-dst,.chain-badge,.fan-badge,.fan-label,.hanging-plaque,.torn-main,.slidecard,.station,.stamp,.compare-pill,.compare-summary-card,.drawer-cell,.cheat-save-pill,.cheat-sheet-card';
        for (const el of document.querySelectorAll(boxSelectors)) {
          if (!visible(el)) continue;
          const br = el.getBoundingClientRect();
          if (br.width < 24 || br.height < 18 || br.right <= 0 || br.left >= innerWidth) continue;
          if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 3) {
            textBoxViolations.push({reason:'text_scroll_overflow', selector:el.className || el.tagName,
              text:el.innerText.trim().slice(0, 36), scrollWidth:el.scrollWidth, clientWidth:el.clientWidth});
            continue;
          }
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          let tn, outPx = 0;
          while ((tn = walker.nextNode())) {
            if (!tn.nodeValue || !tn.nodeValue.trim()) continue;
            const p = tn.parentElement;
            if (p && (p.classList.contains('tree-no') || getComputedStyle(p).position === 'absolute')) continue;
            const range = document.createRange();
            range.selectNodeContents(tn);
            const rr = range.getBoundingClientRect();
            if (!rr.width || !rr.height) continue;
            outPx = Math.max(outPx, br.left - rr.left, rr.right - br.right, br.top - rr.top - 2, rr.bottom - br.bottom - 2);
          }
          if (outPx > 2.5) {
            textBoxViolations.push({reason:'text_exceeds_box', selector:el.className || el.tagName,
              text:el.innerText.trim().slice(0, 36), overflow_px:+outPx.toFixed(1)});
          }
        }
        for (const txtEl of document.querySelectorAll('.node h2,.node p,.tree-branch,.tree-child,.bento-item-name,.workbench-chip')) {
          if (!visible(txtEl) || !txtEl.innerText.trim()) continue;
          const fg = parseRgb(getComputedStyle(txtEl).color);
          const bg = effectiveBg(txtEl);
          if (fg && bg) {
            const l1 = relLum(fg), l2 = relLum(bg);
            const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
            if (ratio < 3.0) {
              textBoxViolations.push({reason:'low_box_text_contrast', selector:txtEl.className || txtEl.tagName,
                text:txtEl.innerText.trim().slice(0, 36), contrast:+ratio.toFixed(2)});
            }
          }
        }
      }
      const root = document.querySelector('[data-composition-id]') || document.body;
      const backdrop = root?.dataset?.onetakeRecipe === 'split_wipe_compare' ? root.querySelector('.compare-stage') : root;
      return {
        phase, overlaps, containerOverflows, textBoxViolations, aspectCrops, cards, titles, stations,
        countClaim: root.querySelector('header')?.innerText || '',
        enumeratedItems: Array.from(root.querySelectorAll('.bento-item-name,.sim-label,.tree-branch,.chain-badge'))
          .filter(visible).map(el=>el.innerText.trim()).filter(Boolean),
        unsafeCoreText: root.dataset.stageLook === 'swiss_paper' ? Array.from(root.querySelectorAll(
          'header,.sim-label,.bento-item-name,.bento-cat,.tree-branch,.tree-child,.display-word,.chain-badge,.workbench-chip,.workbench-label,.workbench-heading,.drawer-title,.cheat-row'
        )).filter(el=>visible(el) && el.textContent.trim() && el.getBoundingClientRect().bottom >= 860)
          .map(el=>el.innerText.trim()) : [],
        stageLook: root?.dataset?.stageLook || null,
        recipe: root?.dataset?.spatialRecipe || root?.dataset?.onetakeRecipe || null,
        fullComparison: Array.from(root?.querySelectorAll('.compare-stage canvas') || [], canvas => {
          const bounds = canvas.getBoundingClientRect();
          return bounds.width >= 1918 && bounds.height >= 1078 && canvas.width >= 1918;
        }),
        backdrop: backdrop ? getComputedStyle(backdrop).backgroundColor : null,
        curtainColumns: Array.from(root?.querySelectorAll('.curtain-panel video') || [], video => {
          const bounds = video.parentElement.getBoundingClientRect();
          return { width: bounds.width, height: bounds.height, decoded: video.videoWidth > 0 };
        }),
        exploded: !!document.querySelector('[data-spatial-recipe="layer_explode_3d"]')
      };
    }, {phase,duration,syncVideos});
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

function findChromeExecutable() {
  if (process.env.YICE_CHROME_EXECUTABLE && fs.existsSync(process.env.YICE_CHROME_EXECUTABLE)) return process.env.YICE_CHROME_EXECUTABLE;
  const home = os.homedir();
  for (const base of [path.join(home, 'Library/Caches/ms-playwright'), path.join(home, '.cache/ms-playwright'), path.join(home, '.cache/hyperframes/chrome/chrome-headless-shell')]) {
    if (!fs.existsSync(base)) continue;
    for (const d1 of fs.readdirSync(base).sort().reverse()) {
      const p1 = path.join(base, d1);
      if (!fs.statSync(p1).isDirectory()) continue;
      for (const d2 of fs.readdirSync(p1).sort().reverse()) {
        const bin = path.join(p1, d2, 'chrome-headless-shell');
        if (fs.existsSync(bin)) return bin;
      }
    }
  }
  return undefined;
}

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:findChromeExecutable()});
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

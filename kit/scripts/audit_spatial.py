"""v10 source-motion proof and visual comparisons for tutorial compositions."""
import re
import subprocess

from audit_v7 import RIGS, capture_frame, shot_span, stage_mode, visual_fingerprint


def composition_motion(source, declared=None):
    scripts = '\n'.join(re.findall(r'<script\b[^>]*>(.*?)</script\s*>', source, re.I | re.S))
    scripts = re.sub(r'/\*.*?\*/|(?m:^\s*//[^\n]*)', '', scripts, flags=re.S)
    tween = bool(re.search(r'\b(?:tl|gsap)\.(?:to|fromTo)\s*\(', scripts))
    depth = bool(re.search(r'\b(?:rotation[XY]|z|rx|ry)\s*:\s*(?!0\b)[-\w.]', scripts))
    layered = bool(re.search(r'forEach\(|\bstagger\s*:|\bfor\s*\(', scripts))
    camera = bool(re.search(r'OM\.camera\(',scripts) and re.search(r'OM\.(?:view|screenTravel)\(',scripts)
                  and len(set(re.findall(r'zoom\s*:\s*([\d.]+)',scripts))) > 1)
    spatial = bool((tween and 'preserve-3d' in source and depth and layered) or (camera and layered and (depth or re.search(r'OM\.view\(|OM\.lattice\(', scripts))))
    recipe = re.search(r'data-spatial-recipe=[\'"]([\w-]+)', source)
    process = recipe and recipe[1] in ('literal_action_stage','roadmap_thread_camera')
    if tween and process:
        return spatial, 'M3'
    if spatial:
        return True, 'M1'
    if declared == 'M3' and (tween or camera):
        return False, 'M3'
    return False, None


def three_mode_symphony_gate(timeline, duration, verified=None, *, tutorial=None):
    verified = verified or {}
    seconds = dict(M1=0., M2=0., M3=0.)
    shots, violations = {}, []
    for shot in timeline['shots']:
        mode = stage_mode(shot)
        category = verified.get(shot['id'])
        if mode in RIGS or mode == 'studio_ui':
            category = 'M2'
        elif mode == 'explainer_clip':
            category = 'M3'
        if category in seconds:
            seconds[category] += shot_span(shot)
        shots[shot['id']] = category
    ratios = {mode:value/duration if duration else 0. for mode,value in seconds.items()}
    required = timeline.get('episode_kind')=='tool_tutorial' if tutorial is None else tutorial
    if required:
        for name,lo,hi in [('M1',.15,1),('M2',.30,.58),('M3',.20,1)]:
            if not lo-1e-8 <= ratios[name] <= hi+1e-8:
                violations.append(dict(mode=name, range=[lo,hi]))
        if any(not value for value in shots.values()):
            violations.append(dict(unclassified=[key for key,value in shots.items() if not value]))
    return dict(ok=not violations,required=required,ratios=ratios,shots=shots,violations=violations)


def page_signature(image, region=None):
    import numpy as np
    from PIL import Image
    image = image.convert('RGB')
    if region is not None:
        if (not isinstance(region,(tuple,list)) or len(region)!=4 or not all(type(x) in (int,float) for x in region)
                or not 0<=region[0]<region[2]<=1 or not 0<=region[1]<region[3]<=1):
            raise ValueError('page_region 须为归一化的左、上、右、下边界')
        w,h=image.size
        image=image.crop((round(region[0]*w),round(region[1]*h),round(region[2]*w),round(region[3]*h)))
    else:
        # Find the dominant slide rectangle from its horizontal/vertical edges.
        sample=np.asarray(image.resize((160,90)),dtype=float)
        dx=np.abs(np.diff(sample,axis=1)).mean(axis=(0,2));dy=np.abs(np.diff(sample,axis=0)).mean(axis=(1,2))
        def edges(profile,left,right):
            part=profile[left:right];i=left+int(part.argmax());return i+1 if profile[i]>8 else None
        x1,x2=edges(dx,0,60),edges(dx,102,159);y1,y2=edges(dy,0,32),edges(dy,58,89)
        if None not in (x1,x2,y1,y2) and 1.4 < (x2-x1)/(y2-y1) < 2.2:
            w,h=image.size;image=image.crop((x1*w//160,y1*h//90,x2*w//160,y2*h//90))
    small=np.asarray(image.resize((16,9),Image.Resampling.LANCZOS),dtype=float)
    return visual_fingerprint(image), small


def subpage_repeats(shots,project,rendered):
    import numpy as np
    from pathlib import Path
    seen=[];errors=[]
    for shot in shots:
        if stage_mode(shot) not in RIGS | {'studio_ui'}:
            continue
        try:
            files = shot.get('files') or shot.get('sources') or [shot.get('source','')]
            video=next((p for p in files if Path(p).suffix.lower() in {'.mp4','.webm','.mov'}),None)
            if stage_mode(shot) == 'studio_ui' and video is None:
                continue
            frame=capture_frame(shot,Path(project),rendered,shot_span(shot)/2,video)
            fingerprint,colors=page_signature(frame,shot.get('page_region'))
            if fingerprint is not None:
                seen.append((shot['id'],fingerprint,colors))
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            errors.append(dict(shot=shot['id'],reason=str(exc)))
    groups=set()
    for _,fingerprint,colors in seen:
        group=tuple(k for k,h,c in seen if (fingerprint^h).bit_count()<=6 and np.abs(colors-c).mean()<12)
        if len(group)>2: groups.add(group)
    return errors+[dict(reason='repeated_slide_page',shots=list(g)) for g in sorted(groups)]


def sample_choreography(entry, *, environ=None):
    """Measure the registered GSAP timeline by seeking the actual headless composition."""
    import json
    import os
    from pathlib import Path
    env = dict(os.environ if environ is None else environ)
    script = r"""
const {chromium} = require(process.env.YICE_PLAYWRIGHT_MODULE || 'playwright');
const {pathToFileURL} = require('node:url');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.YICE_CHROME_EXECUTABLE || undefined});
  try {
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    await page.route(/^https?:/, route => route.abort());
    await page.goto(pathToFileURL(process.argv[1]).href);
    await page.evaluate(() => document.fonts.ready);
    const report = await page.evaluate(() => Object.entries(window.__timelines || {}).map(([id, timeline]) => {
      const root = document.getElementById(id);
      const nodes = [...root.querySelectorAll('*')].filter(el =>
        !el.matches('.film-grain,.bloom,.stage-light,.streak,script,style') &&
        (el.children.length === 0 || el.matches('.world,.orbit-card,.layer,.node')));
      const duration = timeline.duration();
      const tweens = timeline.getChildren(true, true, false).map(t => ({
        start:t.startTime(), end:t.endTime(), targets:t.targets().length,
        properties:Object.keys(t.vars).filter(k => !['ease','duration','onUpdate','immediateRender','parent','overwrite','delay'].includes(k))
      }));
      const measure = t => {
        timeline.seek(t,false);
        return nodes.map(el => {
          const r=el.getBoundingClientRect(), s=getComputedStyle(el);
          return [r.x,r.y,r.width,r.height,Number(s.opacity)*100,s.transform,s.strokeDashoffset,el.textContent.trim().slice(0,48)];
        });
      };
      const samples = Array.from({length:6},(_,i) => i*duration/5);
      const states = samples.map(measure);
      const changes = states.slice(1).map((state,i) => state.reduce((sum,v,j) => {
        const old=states[i][j];
        const moves=v.slice(0,5).some((n,k)=>Math.abs(n-old[k])>=.5) || v.slice(5).some((n,k)=>n!==old[k+5]);
        return sum+Number(moves);
      },0));
      const revisit=measure(samples[2]);
      const seekSafe=states[2].every((v,i)=>v.every((n,k)=>typeof n==='number' ? Math.abs(n-revisit[i][k])<=.51 : n===revisit[i][k]));
      return {id,duration,tweens,samples,changes,seekSafe,deadZones:changes.flatMap((n,i)=>n?[]:[[samples[i],samples[i+1]]])};
    }));
    console.log(JSON.stringify(report));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(['node','-e',script,str(Path(entry).resolve())],env=env,
                            capture_output=True,text=True,check=True,timeout=90)
    timelines = json.loads(result.stdout)
    return dict(ok=bool(timelines) and all(t['tweens'] and t['seekSafe'] and not t['deadZones']
                                           for t in timelines),timelines=timelines)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description='用本机无头浏览器检查空间合成的动作与回跳')
    parser.add_argument('entry', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = sample_choreography(args.entry)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)

#!/usr/bin/env python3
"""采集项目作者公开的原片，标准化画幅并从真实运动中挑选高光。"""
import argparse
import base64
import hashlib
import html
import http.client
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib import parse, request

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from produce_asset import append_ledger, now

footage = importlib.import_module("harvest-episode-footage")
BLOCKED_CREATOR_DOMAINS = (*footage.BLOCKED_CREATOR_DOMAINS, "youtube-nocookie.com", "b23.tv")
VIDEO_PATH = re.compile(r"\.(mp4|webm|mov)$", re.I)
LINK = re.compile(r"""(?:^|["'\s(=])([^\s"'<>()[\]]+?\.(?:mp4|mov|webm)(?:\?[^\s"'<>()[\]]*)?)(?=$|["'\s)<>\]])""", re.I)
UA = "Mozilla/5.0 (compatible; YiceShowcase/1.0)"


def allowed(url):
    parts = parse.urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    return bool(footage.is_allowed_demo_url(url) and not parts.username and not parts.password
                and not any(host == item or host.endswith("."+item) for item in BLOCKED_CREATOR_DOMAINS))


def video_url(url):
    path=parse.urlsplit(url).path
    attachment=(parse.urlsplit(url).hostname=='github.com'
                and re.fullmatch(r'/user-attachments/assets/[0-9a-fA-F-]{32,36}',path))
    return allowed(url) and bool(VIDEO_PATH.search(path) or attachment)


BROWSER = r"""
const fs = require('node:fs');
const {chromium} = require(process.env.YICE_PLAYWRIGHT_MODULE || (() => {
  try { return require.resolve('playwright'); } catch { return '/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core'; }
})());
(async () => {
  const input = JSON.parse(fs.readFileSync(0,'utf8'));
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.YICE_CHROME_EXECUTABLE || process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined});
  try {
    const page = await browser.newPage({viewport:{width:input.width || 1440,height:860},colorScheme:'dark'});
    if (input.sheet) {
      await page.setContent(input.sheet);
      await page.evaluate(() => Promise.all([...document.images].map(i=>i.decode())));
      await page.screenshot({path:input.output,type:'jpeg',quality:93,fullPage:true});
      return;
    }
    const forbidden = url => {const h=new URL(url).hostname.toLowerCase().replace(/\.$/,'');return input.blocked.some(d=>h===d||h.endsWith('.'+d));};
    await page.route('**/*', route => forbidden(route.request().url()) ? route.abort() : route.continue());
    const network = new Set();
    page.on('response', r => {
      if (r.request().frame()===page.mainFrame() && /^video\/(mp4|webm|quicktime)/i.test(r.headers()['content-type'] || '')) network.add(r.url());
    });
    const response = await page.goto(input.url,{waitUntil:'commit',timeout:30000});
    if (!response || !response.ok()) throw Error('page HTTP '+response?.status());
    try {
      await page.waitForLoadState('domcontentloaded',{timeout:15000});
    } catch (error) {
      // A stalled third-party script need not invalidate native sources already parsed by Chromium.
      if (!await page.locator('video[src],video source[src],video[data-src],a[href$=".mp4"]').count()) throw error;
    }
    await page.evaluate(async () => {
      for(const v of document.querySelectorAll('video')) {
        v.scrollIntoView();v.muted=true;v.preload='metadata';
        if(!v.currentSrc) v.load();
      }
      window.scrollTo(0,document.body.scrollHeight);
      await new Promise(resolve => setTimeout(resolve,500));
    });
    const data=await page.evaluate(()=>({base:document.baseURI,title:document.title,
      native:[...document.querySelectorAll('video,video source')].flatMap(e=>[e.currentSrc,e.getAttribute('src'),e.dataset.src].filter(Boolean)),
      links:[...document.querySelectorAll('video,video source,a[href]')].flatMap(e=>
        [e.currentSrc,e.getAttribute('src'),e.dataset.src,e.getAttribute('href')].filter(Boolean)),
      scripts:[...document.scripts].filter(e=>!e.src).map(e=>e.textContent).join('\n')}));
    data.native.push(...network);console.log(JSON.stringify(data));
  } finally {await browser.close();}
})().catch(err=>{console.error(err.message);process.exitCode=1;});
"""


def browser_job(options):
    env=os.environ.copy()
    if not env.get('YICE_CHROME_EXECUTABLE') and not env.get('PLAYWRIGHT_EXECUTABLE_PATH'):
        cached=Path.home()/'Library/Caches/ms-playwright'
        binaries=sorted(cached.glob('chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell'),key=lambda p:p.stat().st_mtime)
        if binaries:env['YICE_CHROME_EXECUTABLE']=str(binaries[-1])
    proc = subprocess.run(["node","-e",BROWSER],input=json.dumps(options),capture_output=True,text=True,timeout=55,env=env)
    if proc.returncode:
        raise ValueError(proc.stderr.strip()[-450:] or "无头浏览器读取失败")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def discover(url):
    if not allowed(url):
        raise ValueError("需要允许的 HTTPS 一手项目页")
    if video_url(url):
        return parse.urlsplit(url).hostname, [url]
    page = browser_job(dict(url=url,blocked=BLOCKED_CREATOR_DOMAINS))
    return page['title'], extract_links(page)


def extract_links(page):
    urls = []
    scripts = page['scripts'].replace(r'\/','/').replace(r'\u0026','&')
    for raw in [*page['links'],*LINK.findall(scripts)]:
        target = parse.urljoin(page['base'],html.unescape(raw))
        if video_url(target):
            urls.append(target)
    for raw in page.get('native',[]):
        target=parse.urljoin(page['base'],raw)
        if allowed(target) and not parse.urlsplit(target).path.lower().endswith(('.m3u8','.mpd')):
            urls.append(target)
    return list(dict.fromkeys(urls))


class SourceRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError("媒体重定向到了被拦截的来源")
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def download(url, target, limit):
    if not allowed(url):
        raise ValueError("不允许的媒体网址")
    opener=request.build_opener(SourceRedirect())
    total=0
    expected=None
    validator=None
    for attempt in range(2):
        headers={'User-Agent':UA}
        if total:
            headers['Range']=f'bytes={total}-'
            if validator:headers['If-Range']=validator
        with opener.open(request.Request(url,headers=headers),timeout=35) as response:
            if response.status==206:
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if not match or int(match[1])!=total or (expected is not None and expected!=int(match[3])):
                    raise ValueError("原片续传范围不一致")
                expected=int(match[3])
            else:
                total=0
                length=response.headers.get('Content-Length')
                expected=int(length) if length is not None else None
            validator=response.headers.get('ETag') or response.headers.get('Last-Modified')
            if expected is not None and expected>limit:
                raise ValueError("原片超过下载上限")
            interrupted=False
            with target.open('ab' if total else 'wb') as fh:
                try:
                    while chunk:=response.read(256*1024):
                        total+=len(chunk)
                        if total>limit:raise ValueError("原片超过下载上限")
                        fh.write(chunk)
                except (TimeoutError,ConnectionError,http.client.IncompleteRead):
                    interrupted=True
            if not interrupted and total and (expected is None or total==expected):
                return
            if not total or attempt:break
    raise ValueError("原片下载不完整")


def ffmpeg(args):
    command=['ffmpeg','-nostdin','-loglevel','error','-y','-filter_threads','2','-filter_complex_threads','2',*map(str,args)]
    proc=subprocess.run(command,capture_output=True)
    if proc.returncode:
        raise ValueError(proc.stderr.decode(errors='replace')[-450:])
    return proc.stdout


def probe(path):
    raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'stream=width,height,avg_frame_rate,sample_aspect_ratio:stream_side_data=rotation:format=duration','-of','json',str(path)],stderr=subprocess.DEVNULL)
    obj=json.loads(raw)
    if not obj['streams']:
        raise ValueError('原片没有视频轨')
    stream=obj['streams'][0]
    return dict(width=stream['width'],height=stream['height'],fps=stream['avg_frame_rate'],
                sar=stream.get('sample_aspect_ratio','1:1'),rotation=next((v['rotation'] for v in stream.get('side_data_list',[]) if 'rotation' in v),0),
                duration=float(obj['format']['duration']))


ENCODE=['-an','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart']


def normalize_showcase_video(source, output, max_seconds=25):
    info=probe(source)
    try:
        a,b=map(int,info['sar'].split(':'));sar=a/b if a and b else 1.
    except (TypeError,ValueError,ZeroDivisionError):
        sar=1.
    ratio=info['width']*sar/info['height']
    if abs(info['rotation'])%180==90:
        ratio=1/ratio
    # Bake display aspect into square pixels before splitting the background and foreground.
    base="scale='max(2,trunc(ih*"+str(ratio)+"/2)*2)':ih,setsar=1,fps=30"
    if 1.65<=ratio<=1.90:
        mode='crop'
        graph=base+',scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1'
        filters=['-vf',graph]
    else:
        mode='blur_dark'
        graph=('[0:v:0]'+base+',split[back][front];[back]scale=1920:1080:force_original_aspect_ratio=increase,'
               'crop=1920:1080,boxblur=28:4,eq=brightness=-0.28:saturation=0.85[bg];'
               '[front]scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];'
               '[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[out]')
        filters=['-filter_complex',graph,'-map','[out]']
    ffmpeg(['-i',source,'-t',max_seconds,*filters,*ENCODE,output])
    return mode


def rank_highlights(path, top=1):
    duration=probe(path)['duration']
    window=4.5
    if duration<window:
        return []
    width,height,fps=160,90,4
    raw=ffmpeg(['-i',path,'-vf',f'fps={fps},scale={width}:{height}','-pix_fmt','rgb24','-f','rawvideo','-threads','1','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,height,width,3).astype(np.float32)
    candidates=[]
    for start in np.arange(0,duration-window+.001,2):
        clip=frames[round(start*fps):round((start+window)*fps)]
        if len(clip)<window*fps:continue
        gray=clip @ np.array([.2126,.7152,.0722],dtype=np.float32)
        light=gray.mean(axis=(1,2))
        # Per-frame zooms or animated text on a single flat background should not win on motion alone.
        gradx=np.abs(np.diff(gray,axis=2));grady=np.abs(np.diff(gray,axis=1))
        edge=(gradx.mean(axis=(1,2))+grady.mean(axis=(1,2)))/2
        flat=np.array([np.bincount((f.astype(np.uint8)//12).ravel(),minlength=22).max()/f.size for f in gray])
        if np.any(light<14) or np.median(light)<30 or np.mean((flat>.85)&(edge<6))>.5:continue
        changes=np.abs(np.diff(clip,axis=0)).mean(axis=(1,2,3))
        # A single edit can create a large difference between two otherwise still pictures.
        motion=float(.65*np.median(changes)+.35*np.mean(changes))
        if motion<1.1 or np.mean(changes>1.3)<.3:continue
        detail=float(edge.mean())
        color=float(np.mean(clip.max(axis=3)-clip.min(axis=3)))
        seam=float(max(gradx[:,:,width//2-1].mean(),grady[:,height//2-1,:].mean()))
        score=round(100*(.5*min(motion/32,1)+.27*min(detail/27,1)+.18*min(color/82,1)+.05*min(seam/50,1)),2)
        # Publish a representative frame from inside the cut, avoiding fades and flat title frames.
        preview_quality=edge*np.minimum(light/65,1)*np.minimum((255-light)/55,1)*(1-flat)
        offset=2+int(np.argmax(preview_quality[2:-2]))
        candidates.append(dict(start=float(start),end=float(start+window),score=score,
                               motion=round(motion,2),preview_offset=offset/fps))
    chosen=[]
    for row in sorted(candidates,key=lambda item:-item['score']):
        if all(row['end']<=old['start'] or old['end']<=row['start'] for old in chosen):
            chosen.append(row)
        if len(chosen)==top:break
    return chosen


def tweet_media(payload):
    """Accept both the installed CLI's normalized media and the original video_info variants."""
    found=[]
    def visit(value):
        if isinstance(value,list):
            for node in value:visit(node)
        if not isinstance(value,dict):return
        author=value.get('author') or value.get('user') or {}
        name=author.get('screenName') or author.get('screen_name')
        ident=str(value.get('id') or value.get('id_str') or '')
        if name and ident.isdigit():
            media=value.get('media') or value.get('extended_entities',{}).get('media',[])
            for item in media if isinstance(media,list) else []:
                variants=[v for v in item.get('video_info',{}).get('variants',[])
                          if v.get('content_type')=='video/mp4' and video_url(v.get('url',''))]
                url=max(variants,key=lambda v:v.get('bitrate',0))['url'] if variants else item.get('url','')
                if (variants or item.get('type') in ('video','animated_gif')) and video_url(url):
                    found.append(dict(url=url,sourceUrl=f'https://x.com/{name}/status/{ident}',sourceName='@'+name))
        else:
            for node in value.values():
                if isinstance(node,(list,dict)):visit(node)
    visit(payload)
    return found


def collect_x(query,urls,binary=None):
    if not query and not urls:return [],'not_requested'
    cli=Path(binary or Path.home()/'.local/bin/twitter')
    if not cli.is_file():return [],'cli_unavailable'
    tasks=[['search',query,'-n','12','--json']] if query else []
    for url in urls:
        if not re.fullmatch(r'https://(?:www\.)?(?:x|twitter)\.com/[\w]+/status/\d+(?:\?[^ ]*)?',url):
            raise ValueError('需要具体的 X 推文地址')
        tasks.append(['tweet',url,'-n','0','--json'])
    clips=[];failed=False
    for args in tasks:
        try:
            p=subprocess.run([str(cli),*args],capture_output=True,text=True,timeout=40,check=True)
            clips.extend(tweet_media(json.loads(p.stdout)))
        except (OSError,ValueError,subprocess.SubprocessError):
            failed=True
    if failed:return clips,'partially_available' if clips else 'unavailable'
    return clips,'available' if clips else 'no_video'


def candidate_sheet(root,rows):
    cards=[]
    for row in rows:
        full=root/row['path']
        thumb=ffmpeg(['-ss',row['preview_offset'],'-i',full,'-frames:v','1','-vf','scale=528:297','-c:v','mjpeg','-threads','1','-f','image2pipe','-'])
        src=base64.b64encode(thumb).decode()
        domain=html.escape(parse.urlsplit(row['sourceUrl']).hostname)
        cards.append(f'<article><img src="data:image/jpeg;base64,{src}"><b>{html.escape(row["id"])}</b>'
                     f'<span>{html.escape(row["sourceName"])} · {domain}</span><span>1920×1080 · {row["start"]:.1f}–{row["end"]:.1f}s · {row["score"]:.1f}</span></article>')
    css="""*{box-sizing:border-box}body{margin:0;padding:24px;background:#0b1018;color:#edf5ff;font:17px system-ui}
    main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}article{min-width:0;background:#171f2e;padding-bottom:14px}
    img{width:100%;display:block}b,span{display:block;margin:9px 14px 0}span{color:#a5bbcf;font-size:16px}"""
    doc='<meta charset=utf-8><style>'+css+'</style><main>'+''.join(cards)+'</main>'
    browser_job(dict(sheet=doc,output=str(root/'showcase-candidates.jpg'),width=1680))


def harvest(args):
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    for folder in ('originals','normalized','highlights'):(root/folder).mkdir(exist_ok=True)
    pages=[dict(url=u) for u in args.urls]
    if args.plan:
        plan=json.loads(args.plan.read_text())
        entries=plan if isinstance(plan,list) else plan['urls']
        pages.extend(dict(url=item) if isinstance(item,str) else item for item in entries)
    media,x_status=collect_x(args.x_query,args.x_urls)
    issues=[]
    for item in pages:
        try:
            name,links=discover(item['url'])
            selected=item.get('media')
            if selected is not None:
                missing=set(selected)-set(links)
                if missing:issues.append(dict(source=item['url'],reason='页面未发现指定原片',missing=sorted(missing)))
                links=[link for link in links if link in selected]
            media.extend(dict(url=link,sourceUrl=item['url'],sourceName=item.get('name') or name) for link in links)
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            issues.append(dict(source=item['url'],reason=str(exc)))
    sources=[];highlights=[];seen=set()
    for candidate in media:
        url=candidate['url']
        if url in seen:continue
        seen.add(url)
        key='clip-'+hashlib.sha256(url.encode()).hexdigest()[:12]
        suffix=Path(parse.urlsplit(url).path).suffix.lower()
        original=root/'originals'/(key+(suffix if suffix in ('.mp4','.mov','.webm') else '.media'))
        normal=root/'normalized'/(key+'.mp4')
        try:
            with tempfile.TemporaryDirectory(dir=root) as tmp:
                temp=Path(tmp);raw=temp/original.name
                if not original.is_file():
                    download(url,raw,int(args.max_mb*1024**2))
                    original_info=probe(raw);raw.replace(original)
                else:
                    if original.stat().st_size>args.max_mb*1024**2:raise ValueError('原片超过下载上限')
                    original_info=probe(original)
                mode=normalize_showcase_video(original,temp/'normalized.mp4',args.max_seconds)
                (temp/'normalized.mp4').replace(normal)
                source=dict(id=key,originalSha256=footage.sha256_file(original),originalBytes=original.stat().st_size,sourceUrl=candidate['sourceUrl'],sourceName=candidate['sourceName'],mediaUrl=url,
                            original=original.relative_to(root).as_posix(),originalInfo=original_info,
                            path=normal.relative_to(root).as_posix(),fit=mode,usage='editorial_commentary_muted',
                            width=1920,height=1080,duration=probe(normal)['duration'],kind='motion-video',
                            licenseUrl=candidate['sourceUrl'],tool='harvest-showcase-media')
                append_ledger(root,dict(source,sourceType='official_demo',capturedAt=now(),status='captured'))
                sources.append(source)
                if not args.rank_highlights:continue
                for i,win in enumerate(rank_highlights(normal,args.top),1):
                    ident=f'{key}-{i}'
                    target=root/'highlights'/(ident+'.mp4')
                    ffmpeg(['-ss',win['start'],'-i',normal,'-t',win['end']-win['start'],*ENCODE,temp/'highlight.mp4'])
                    (temp/'highlight.mp4').replace(target)
                    row=dict(source,**win)
                    row.update(id=ident,parent=key,path=target.relative_to(root).as_posix(),sourceType='official_demo',
                               width=1920,height=1080,fps=30,duration=win['end']-win['start'],capturedAt=now(),status='captured',
                               files=[dict(path=target.relative_to(root).as_posix(),sha256=footage.sha256_file(target))])
                    append_ledger(root,row);highlights.append(row)
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
            issues.append(dict(source=url,reason=str(exc)))
    highlights.sort(key=lambda row:-row['score'])
    if args.rank_highlights:candidate_sheet(root,highlights)
    result=dict(sources=sources,highlights=highlights,x_status=x_status,issues=issues)
    path=root/'manifest.json';temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--urls',nargs='+',default=[])
    parser.add_argument('--plan',type=Path,help='URL 列表或 {"urls":[{"url":"项目页","name":"署名","media":["页面内的直链"]}]}')
    parser.add_argument('--x-query')
    parser.add_argument('--x-urls',nargs='+',default=[])
    parser.add_argument('--rank-highlights',action='store_true')
    parser.add_argument('--aspect-fit',choices=['blur_dark'],default='blur_dark')
    parser.add_argument('--max-mb',type=float,default=120)
    parser.add_argument('--max-seconds',type=float,default=25)
    parser.add_argument('--top',type=int,choices=(1,2),default=1)
    args=parser.parse_args()
    args.urls=[u.strip() for value in args.urls for u in value.split(',') if u.strip()]
    args.x_urls=[u.strip() for value in args.x_urls for u in value.split(',') if u.strip()]
    if not(args.urls or args.plan or args.x_query or args.x_urls):parser.error('请提供项目页、计划或 X 查询')
    if not(0<args.max_mb and 0<args.max_seconds and math.isfinite(args.max_mb) and math.isfinite(args.max_seconds)):
        parser.error('下载和时长上限须为正数')
    result=harvest(args)
    print(json.dumps(dict(sources=len(result['sources']),highlights=len(result['highlights']),x_status=result['x_status'],
                          issues=len(result['issues'])),ensure_ascii=False))
    return int(not result['sources'] and bool(result['issues']))


if __name__=='__main__':
    raise SystemExit(main())

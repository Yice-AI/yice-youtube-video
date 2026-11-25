"""将真实项目的媒体、片段、代码、日志和采样波形排到可寻址的工程台上。"""
from html import escape
import json
import unicodedata

INK, PANEL, PAPER, MUTED, CORAL = "#151c20", "#252e33", "#e7e9df", "#a5b7b6", "#ff8369"


def label(x, y, value, size=32, color=PAPER, *, decorative=False, fit=None):
    layout = ' data-layout-ignore' if decorative else ''
    if fit is not None:
        layout += f' textLength="{fit}" lengthAdjust="spacingAndGlyphs"'
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="Menlo,PingFang SC,sans-serif"{layout}>{escape(str(value))}</text>'


def box(x, y, w, h, fill=PANEL, attrs=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {attrs}/>'


def waveform(samples, x, y, w, h):
    if not samples:
        raise ValueError("工程台需要实际音频采样")
    points = []
    for i, peak in enumerate(samples):
        px = x + w*i/max(1, len(samples)-1)
        amplitude = min(1, abs(float(peak))) * h / 2
        points.append(f'M{px:.1f},{y-amplitude:.1f}v{2*amplitude:.1f}')
    return '<path d="'+' '.join(points)+'" stroke="#8cbbb1" stroke-width="3"/>'


def _nle(stage, start, end, data):
    monitor = data['monitor']
    stage.add_video(start,end,monitor,830,150,900,375,fit="contain",tone="natural")
    body = '<g class="nle-bin">' + label(80,190,"媒体箱",34)
    for i, media in enumerate(data['media'][:5]):
        body += label(85,250+54*i,media,29)
    body += label(85,492,f"镜长  {end-start:.2f}s",28,MUTED) + '</g>'
    body += label(835,131,"节目监视器",24,MUTED,decorative=True)
    body += box(829, 487, 245, 39, INK)
    body += '<g class="monitor-time">' + label(845,516,"00:00:00:00",24,decorative=True) + '</g>'
    body += box(74,547,1765,325) + label(90,587,"剪辑序列",30)
    for i, name in enumerate(("V3 动效","V2 实录","V1 主画面","A1 人声","A2 配乐")):
        y=609+i*48
        body+=label(94,y+28,name,24,decorative=True)+box(300,y,1470,35,"#1d2529")
        if i < 3:
            for clip in data['tracks'][i]:
                left,right=clip
                if not 0<=left<right<=1: raise ValueError("时间轴块必须位于序列范围内")
                body+=box(300+1470*left,y,1470*(right-left),35,("#756d78","#567f70","#60717b")[i],
                          f'class="track-clip" data-in="{left}" data-out="{right}"')
        else:
            body+=waveform(data['voice' if i==3 else 'bed'],300,y+17,1470,34)
    return body+box(300,603,4,242,CORAL,'class="playhead"'), [monitor]


def _code(data):
    body=box(74,151,430,710)+box(520,151,1320,710)
    for i, file in enumerate(data['tree'][:11]):
        body+=label(95,205+48*i,file,25,MUTED)
    body+=label(555,211,data['file'],31)
    lines,size = fitted_lines(data['lines'][:12],1180)
    focus = set(data.get('focus_lines',[]))
    for i,(line,fit) in enumerate(lines):
        color = "#b6d5a8" if line.startswith("+") else "#f2a491" if line.startswith("-") else PAPER
        y = 279+i*41
        strip = box(542,y-27,1259,36,'#82aac0','rx="6" opacity=".17"') if i+1 in focus else ''
        body+=f'<g class="entry">'+strip+label(550,y,f'{i+1:02}',23,MUTED)+label(625,y,line,size,color,fit=fit)+'</g>'
    return body+label(550,831,data['status'],24,MUTED)


def _terminal(data):
    body=box(76,165,1760,689)+label(110,226,data['command'],32,"#b9d5bf")
    lines,size = fitted_lines(data['lines'][:11],1676)
    focus = set(data.get('focus_lines',[]))
    for i,(line,fit) in enumerate(lines):
        y = 301+i*46
        strip = box(100,y-30,1700,41,'#82aac0','rx="6" opacity=".17"') if i+1 in focus else ''
        body+='<g class="entry">'+strip+label(111,y,line,size,fit=fit)+'</g>'
    return body


def fitted_lines(lines, width):
    display = [line if len(line)<=110 else line[:109]+'…' for line in lines]
    units = [sum(1 if unicodedata.east_asian_width(char) in 'FW' else .62 for char in line) for line in display]
    size = max(20,min(28,int(width/max([1,*units]))))
    return [(line,width if unit*size>width else None) for line,unit in zip(display,units)],size


def _daw(data):
    body=box(74,168,1770,686)
    for i,(tag, key) in enumerate([('人声','voice'),('伴奏','bed')]):
        y=332+i*230
        body+=label(100,y,tag,30)+waveform(data[key],289,y,1450,167)
    for left,right in data['drops']:
        body+=box(289+1450*left,213,max(2,1450*(right-left)),515,'#e49870','opacity=".23"')
    body += label(270,802,data['meter'],30)
    body += box(1760,225,25,485,"#1a2527") + box(1760,225,25,485,"#89b58e",'class="peak-meter"')
    return body + box(289,210,4,510,CORAL,'class="playhead"')


def add_workbench(stage, start, end, style, title, data):
    """在 EditorialStage 中挂入工程台；时间轴所在区间内播放头只扫描一次。"""
    if end<=start: raise ValueError("工程台时长必须为正")
    if style=="nle_timeline":
        body, files=_nle(stage,start,end,data)
    else:
        renderers={"vscode_workbench":_code,"terminal_pipeline":_terminal,"audio_daw":_daw}
        body=renderers[style](data)
        files=list(data['evidence'])
    name=stage.add_plate(start,end,title,label(78,100,title,47)+body,bg=INK,animate=False,kind="studio_ui",files=files)
    stage.shots[-1].update(studio_style=style,layout="fullbleed",outer_scale=1.0)
    if style == "nle_timeline":
        # 时间码和剪辑高亮都由同一渲染时钟驱动，可逐帧 seek。
        stage.scripts.append(f"""{{let play={{fraction:0}};
            const tc=document.querySelector('#{name} .monitor-time text');
            const clips=document.querySelectorAll('#{name} .track-clip');
            tl.to(play,{{fraction:1,ease:'none',duration:{end-start:.6f},onUpdate:()=>{{
                const frame=Math.floor((play.fraction*{end-start:.6f}+{float(data.get('source_start',0))})*30);
                tc.textContent=[Math.floor(frame/108000),Math.floor(frame/1800)%60,
                  Math.floor(frame/30)%60,frame%30].map(n=>String(n).padStart(2,'0')).join(':');
                for(const clip of clips) clip.setAttribute('stroke',
                  play.fraction>=Number(clip.dataset.in)&&play.fraction<Number(clip.dataset.out)?'#ff8369':'none');
            }}}},{start:.6f});}}""")
    if style == "audio_daw":
        peaks = json.dumps([max(0,min(1,float(v))) for v in data["voice"]], allow_nan=False)
        stage.scripts.append(f"""{{const peaks={peaks}, cursor={{index:0}};
            const meter=document.querySelector('#{name} .peak-meter');
            tl.to(cursor,{{index:peaks.length-1,ease:'none',duration:{end-start:.6f},onUpdate:()=>{{
                const level=485*peaks[Math.round(cursor.index)];
                meter.setAttribute('y',710-level);meter.setAttribute('height',level);
            }}}},{start:.6f});}}""")
    if style in {"nle_timeline","audio_daw"}:
        stage.scripts.append(f"tl.to('#{name} .playhead',{{x:1450,duration:{end-start:.5f},ease:'none'}},{start:.5f});")
    else:
        step=min(.45,(end-start)*.7/max(1,len(data['lines'])))
        stage.scripts.append(f"tl.fromTo('#{name} .entry',{{opacity:0,y:8}},{{opacity:1,y:0,duration:.28,stagger:{step:.4f},immediateRender:false}},{start:.5f});")
    return name

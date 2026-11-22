#!/usr/bin/env python3
"""按 1 秒步进生成动态胶片条，并报告相邻帧差。"""
from __future__ import annotations
import argparse, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat

def frame(video: Path, at: float, size=(320,180)) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix='.jpg') as tmp:
        subprocess.run(['ffmpeg','-v','error','-y','-ss',f'{at:.3f}','-i',str(video),'-frames:v','1','-vf',f'scale={size[0]}:{size[1]}',tmp.name],check=True)
        return Image.open(tmp.name).convert('RGB').copy()

def build(video: Path, out: Path, start: float, end: float, step: float = 1.0) -> dict:
    times=[]; t=start
    while t <= end + 1e-6:
        times.append(round(t,3)); t += step
    cols=5; cell=(320,210); rows=(len(times)+cols-1)//cols
    sheet=Image.new('RGB',(cols*cell[0],rows*cell[1]),'#0d1514'); draw=ImageDraw.Draw(sheet)
    previous=None; diffs=[]
    for i,at in enumerate(times):
        img=frame(video,at)
        x=(i%cols)*cell[0]; y=(i//cols)*cell[1]
        sheet.paste(img,(x,y)); draw.text((x+8,y+184),f'{at:.1f}s',fill='#fffaf0')
        if previous is not None: diffs.append({'at':at,'mad':round(ImageStat.Stat(ImageChops.difference(previous,img)).mean[0],3)})
        previous=img
    sheet.save(out,quality=92)
    return {'start':start,'end':end,'step':step,'frames':len(times),'max_mad':max((d['mad'] for d in diffs),default=0),'diffs':diffs}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('video',type=Path); ap.add_argument('--out-dir',type=Path,required=True); ap.add_argument('--start',type=float,required=True); ap.add_argument('--end',type=float,required=True); ap.add_argument('--name',required=True)
    a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True); result=build(a.video,a.out_dir/(a.name+'.jpg'),a.start,a.end); (a.out_dir/(a.name+'.json')).write_text(__import__('json').dumps(result,ensure_ascii=False,indent=2)+'\n'); print(result)
if __name__=='__main__': main()

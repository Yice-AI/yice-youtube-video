#!/usr/bin/env python3
"""用FFmpeg/ffprobe做本地交付检查；接触表只作检视，不改原视频。"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def sheet(video, out, duration, every):
    from PIL import Image, ImageDraw, ImageFont
    times = [round(i * every, 3) for i in range(max(1, math.ceil(duration / every)))]
    folder = out / f'frames-{every}s'
    folder.mkdir(exist_ok=True)
    font = ImageFont.load_default()
    columns, per_page = 5, 40
    pages = []
    for page in range(math.ceil(len(times) / per_page)):
        part = times[page * per_page:(page + 1) * per_page]
        canvas = Image.new('RGB', (1600, math.ceil(len(part) / columns) * 204), '#20201e')
        draw = ImageDraw.Draw(canvas)
        for i, t in enumerate(part):
            frame = folder / f'{t:010.3f}.jpg'
            run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2','-q:v','2',str(frame)])
            with Image.open(frame) as im:
                x, y = (i % columns) * 320, (i // columns) * 204
                canvas.paste(im, (x, y))
                draw.text((x + 8, y + 184), f'{t:.3f}s', fill='white', font=font)
        name = out / f'contact-{every}s-{page+1:02d}.jpg'
        canvas.save(name, quality=94)
        pages.append(str(name))
    return pages


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mp4', type=Path)
    p.add_argument('--at', default='', help='额外抽帧秒数，如 1,5.5,12')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    video = a.mp4.resolve()
    info = json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)]).stdout)
    duration = float(info['format']['duration'])
    out = (a.out or video.parent / (video.stem + '-review')).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ffprobe.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
    check = run(['ffmpeg','-hide_banner','-i',str(video),'-vf','blackdetect=d=0.1:pix_th=0.10','-an','-f','null','-'])
    (out / 'blackdetect.log').write_text(check.stderr)
    black = [dict(start=float(x),end=float(y),duration=float(z)) for x,y,z in re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',check.stderr)]
    contacts = {str(step): sheet(video, out, duration, step) for step in (3, 40)}
    extra = []
    for value in filter(None, a.at.split(',')):
        t = float(value)
        if not 0 <= t < duration:
            raise ValueError(f'抽帧时间超出视频：{t}')
        target = out / f'at-{t:010.3f}.png'
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1',str(target)])
        extra.append(str(target))
    audio = [dict(codec=s['codec_name'],sample_rate=s.get('sample_rate'),channels=s.get('channels'),duration=s.get('duration')) for s in info['streams'] if s['codec_type']=='audio']
    result = dict(video=str(video),duration_seconds=duration,audio_tracks=audio,has_audio=bool(audio),black_intervals=black,contact_sheets=contacts,extra_frames=extra)
    (out / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

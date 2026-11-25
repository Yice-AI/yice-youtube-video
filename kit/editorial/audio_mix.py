"""一策看片室 v4 的底乐瞬抽与动作音效元数据辅助器。

实际音频仍由项目自己的 ffmpeg/HyperFrames 混音脚本负责，这里提供一个小而稳定的
参数层，避免每个剧集重复拼接滤镜字符串。
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile


@dataclass(frozen=True)
class MusicDrop:
    start: float
    end: float


def normalise_music_drops(drops: list[tuple[float, float]] | None) -> list[MusicDrop]:
    result = []
    for start, end in drops or []:
        start, end = float(start), float(end)
        if start < 0 or end <= start:
            raise ValueError("Music Drop 的结束时间必须晚于开始时间，且开始时间不得为负数")
        result.append(MusicDrop(start, end))
    return sorted(result, key=lambda item: item.start)


def music_drop_volume_filter(drops: list[tuple[float, float]] | None) -> str:
    """生成 0.18 秒淡出、0.22 秒恢复的真实底乐音量自动化。"""
    expression = "1"
    target = 0.005
    for drop in reversed(normalise_music_drops(drops)):
        fade_out = min(0.18, max(0.01, drop.end - drop.start))
        fade_in = 0.22
        out_end = drop.start + fade_out
        in_end = drop.end + fade_in
        expression = (
            f"if(lt(t,{drop.start:.3f}),{expression},"
            f"if(lt(t,{out_end:.3f}),{target}+(1-{target})*0.5*(1+cos(PI*(t-{drop.start:.3f})/{fade_out:.3f})),"
            f"if(lt(t,{drop.end:.3f}),{target},"
            f"if(lt(t,{in_end:.3f}),{target}+(1-{target})*0.5*(1-cos(PI*(t-{drop.end:.3f})/{fade_in:.3f})),{expression}))))"
        )
    return f"volume='{expression}':eval=frame" if expression != "1" else "anull"


def render_bed_only(bed: str | Path, output: str | Path,
                    drops: list[tuple[float, float]] | None) -> Path:
    """按同一 Music Drop 窗口导出纯伴奏轨，供 audit-v4 做声学验收。"""
    bed, output = Path(bed), Path(output)
    if not bed.is_file():
        raise FileNotFoundError(f"底乐不存在：{bed}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(bed), "-af", music_drop_volume_filter(drops),
        "-acodec", "pcm_s16le", str(output)
    ], check=True)
    return output


def action_mark(kind: str, at: float) -> dict[str, object]:
    allowed = SFX_KINDS | {'slap', 'music_drop'}
    if kind not in allowed:
        raise ValueError(f"未知动作音效类型：{kind}")
    return {"kind": kind, "at": round(float(at), 5)}


SFX_KINDS = {'tick', 'whoosh', 'pop', 'marker', 'stamp', 'riser'}


class EpisodeAudioMixer:
    """Produce one physical master and its corresponding music-only track."""

    def __init__(self, sample_rate=48000, target_lufs=-14.5):
        if sample_rate < 8000 or not -15.3 <= target_lufs <= -13.7:
            raise ValueError('采样率或母带响度目标不符')
        self.rate = sample_rate
        self.target_lufs = target_lufs

    def _read(self, path):
        import soundfile as sf
        from scipy.signal import resample_poly

        audio, rate = sf.read(path, always_2d=True, dtype='float32')
        if not len(audio):
            raise ValueError('音频文件为空')
        divisor = math.gcd(rate, self.rate)
        return resample_poly(audio.mean(axis=1), self.rate//divisor, rate//divisor)

    def _default_music(self, frames):
        import numpy as np
        from scipy.signal import butter, sosfilt

        t = np.arange(frames) / self.rate
        chord = sum(gain*np.sin(2*np.pi*(freq*t+depth*np.sin(2*np.pi*.09*t))+phase)
                    for freq,gain,depth,phase in ((82.41,.72,.009,.7),(110.,.41,.014,1.4),
                                                  (164.81,.31,.011,.2),(220.,.14,.012,2.)))
        pad = chord*(.84+.16*np.cos(2*np.pi*t/11))
        return sosfilt(butter(2,min(520,self.rate*.45),fs=self.rate,output='sos'),pad)

    def _loop_music(self, source, frames):
        import numpy as np

        if frames<=len(source):
            return source[:frames].copy()
        overlap = min(round(2.5*self.rate),(len(source)-1)//2)
        phase = np.linspace(0,np.pi/2,overlap)
        fade_out,fade_in = np.cos(phase),np.sin(phase)
        result = np.empty(frames,dtype=source.dtype)
        result[:len(source)] = source
        written = len(source)
        while written<frames:
            if overlap:
                seam = result[written-overlap:written]
                seam[:] = seam*fade_out+source[:overlap]*fade_in
            count = min(frames-written,len(source)-overlap)
            result[written:written+count] = source[overlap:overlap+count]
            written += count
        return result

    def _music(self, paths, frames, cuts, crossfade):
        import numpy as np

        if not paths:
            paths = [None]
        if not 1 <= len(paths) <= 3:
            raise ValueError('底乐支持一至三首曲目')
        if cuts is None:
            cuts = [frames/self.rate*i/len(paths) for i in range(1,len(paths))]
        if len(cuts) != len(paths)-1 or list(cuts) != sorted(set(cuts)) or any(
                not 0 < c < frames/self.rate for c in cuts):
            raise ValueError('每次切换曲目须对应一个递增的全片切点')
        edges = [0, *[round(x*self.rate) for x in cuts], frames]
        width = max(1,min(round(crossfade*self.rate/2), min(b-a for a,b in zip(edges,edges[1:]))//2))
        music = np.zeros(frames, dtype='float32')
        for i, path in enumerate(paths):
            source = self._read(path) if path is not None else self._default_music(frames)
            rms = float(np.sqrt(np.mean(source**2)))
            if rms < 1e-6:
                raise ValueError('底乐曲目没有可用信号')
            a = edges[i] - (width if i else 0)
            b = edges[i+1] + (width if i+1 < len(paths) else 0)
            segment = self._loop_music(source,b-a) * (.25/rms)
            if i:
                segment[:2*width] *= .5-.5*np.cos(np.linspace(0,np.pi,2*width))
            if i+1 < len(paths):
                segment[-2*width:] *= .5+.5*np.cos(np.linspace(0,np.pi,2*width))
            music[a:b] += segment
        return music

    def _duck(self, voice):
        import numpy as np
        from scipy.ndimage import maximum_filter1d

        hop = max(1,round(self.rate*.01))
        padded = np.pad(voice,(0,(-len(voice))%hop)).reshape(-1,hop)
        rms = np.sqrt(np.mean(padded**2,axis=1))
        activity = np.clip((rms-.006)/.025,0,1)
        ahead = maximum_filter1d(activity,size=13,origin=-6,mode='nearest')
        envelope = np.empty_like(ahead)
        value = ahead[0]
        for i, target in enumerate(ahead):
            decay = math.exp(-.01/(.025 if target > value else .32))
            value = target+(value-target)*decay
            envelope[i] = value
        db = np.interp(np.arange(len(voice))/hop,np.arange(len(envelope)),-13-9*envelope)
        return (10**(db/20)).astype('float32')

    def _effect(self, kind):
        import numpy as np
        from scipy.signal import butter, sosfilt

        seconds = {'tick':.09,'pop':.16,'marker':.30,'stamp':.30,'whoosh':.48,'riser':.80}[kind]
        t = np.arange(round(seconds*self.rate))/self.rate
        u = t/seconds
        noise = np.random.default_rng(17).normal(size=len(t))
        def filtered(low, high):
            high = min(high,self.rate*.47)
            return sosfilt(butter(2,(min(low,high*.8),high),fs=self.rate,btype='bandpass',output='sos'),noise)

        if kind=='tick':
            resonances = sum(gain*np.sin(2*np.pi*hz*t)*np.exp(-t/decay)
                             for hz,gain,decay in ((810,1.,.012),(1370,.48,.008),(2180,.24,.005)))
            tone = resonances+.24*filtered(1350,4500)*np.exp(-t/.007)
        elif kind=='pop':
            phase = 2*np.pi*(440*t+58*seconds*(1-np.exp(-t/.038)))
            tone = (np.sin(phase)+.29*np.sin(2*phase)+.10*np.sin(4*phase))*u**.4*np.exp(-t/.034)
        elif kind=='stamp':
            pulse = np.sin(2*np.pi*(75*t-52*t*u))*(1-np.exp(-t/.008))*np.exp(-t/.058)
            paper = .21*filtered(350,2700)*np.exp(-t/.042)
            tone = sosfilt(butter(2,min(35,self.rate*.2),fs=self.rate,btype='highpass',output='sos'),pulse+paper)
        elif kind=='marker':
            pressure = (.66+.24*np.sin(2*np.pi*9*t)**2)*np.sin(np.pi*u)**1.6
            tone = (.72*filtered(550,3000)+.28*filtered(1500,6100))*pressure
        else:
            bands = ((290,1100),(510,1900),(880,3300),(1260,4800))
            tone = sum(filtered(low,high)*np.exp(-((u-(.15+.22*i))/.23)**2)
                       for i,(low,high) in enumerate(bands))
            tone *= np.sin(np.pi*u)**1.7*(u if kind=='riser' else 1)
        edge = min(len(t)//2,max(1,round(.005*self.rate)))
        tone[:edge] *= np.linspace(0,1,edge)
        tone[-edge:] *= np.linspace(1,0,edge)
        return tone/(np.max(np.abs(tone)) or 1)

    def mix(self, duration, voice_tracks, output, *, bgm=(), bgm_cuts=None,
            music_drops=(), sound_marks=(), sfx_library=None, intro_fade_in=0., crossfade=6.):
        import numpy as np
        import soundfile as sf

        if not math.isfinite(duration) or duration <= 0 or not 0 <= intro_fade_in <= .35 or not 5 <= crossfade <= 7:
            raise ValueError('混音时长或淡化参数不符')
        output = Path(output)
        output.mkdir(parents=True,exist_ok=True)
        frames = round(duration*self.rate)
        voice = np.zeros(frames,dtype='float32')
        for row in voice_tracks:
            audio = self._read(row['path'])
            at = round(float(row.get('at',0))*self.rate)
            if at < 0 or at+len(audio) > frames+1:
                raise ValueError('人声音轨超出全片边界')
            n = min(len(audio),frames-at)
            voice[at:at+n] += audio[:n]
        bed = self._music(bgm,frames,bgm_cuts,crossfade)*self._duck(voice)
        intro = round(intro_fade_in*self.rate)
        if intro:
            bed[:intro] *= .5-.5*np.cos(np.linspace(0,np.pi,intro))
        for drop in normalise_music_drops(music_drops):
            if drop.end > duration:
                raise ValueError('Music Drop 超出全片时长')
            start,end = round(drop.start*self.rate),round(drop.end*self.rate)
            out = min(start,round(.18*self.rate)); back = min(frames-end,round(.22*self.rate))
            floor = 10**(-46/20)
            bed[start-out:start] *= floor+(1-floor)*(.5+.5*np.cos(np.linspace(0,np.pi,out)))
            bed[start:end] *= floor
            bed[end:end+back] *= floor+(1-floor)*(.5-.5*np.cos(np.linspace(0,np.pi,back)))
        mixed = voice+bed
        applied = []
        library = sfx_library or {}
        for event in sound_marks:
            kind, at = event['kind'],float(event['at'])
            if kind == 'music_drop':
                continue
            if kind == 'slap':
                kind = 'stamp'
            gain = float(event.get('gain',.18))
            if kind not in SFX_KINDS or not 0 <= at < duration or not 0 < gain <= 1:
                raise ValueError('音效类型、时间或增益无效')
            effect = self._read(library[kind]) if kind in library else self._effect(kind)
            i = round(at*self.rate); n = min(len(effect),frames-i)
            mixed[i:i+n] += gain*effect[:n]
            applied.append({**event,'kind':kind,'at':at,'gain':gain})
        sf.write(output/'bed-only.wav',bed,self.rate,subtype='PCM_24')
        spec = importlib.util.spec_from_file_location('voice_master_levels',Path(__file__).parents[1]/'scripts/voice-post.py')
        post = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(post)
        with tempfile.TemporaryDirectory(dir=output) as tmp:
            raw = Path(tmp)/'premaster.wav'
            sf.write(raw,mixed,self.rate,subtype='FLOAT')
            levels = post.normalize_lufs(raw,output/'mix.wav',self.target_lufs)
        if abs(levels['measured_lufs']-self.target_lufs) > .8 or levels['true_peak_dbtp'] > -1.:
            raise ValueError('母带响度或真峰值未达标')
        report = {**levels,'sound_marks':applied,'mix':'mix.wav','bed':'bed-only.wav'}
        (output/'audio-mix-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return report


def mix_episode_audio(config, duration, output, *, root=Path('.'), sound_marks=(), bgm_cuts=None):
    root = Path(root)
    clips = [{**item, 'path':root/item['path']} for item in config.get('voice_tracks', [])]
    library = {key:root/path for key,path in config.get('sfx_library', {}).items()}
    drops = [(item['start'],item['end']) if isinstance(item,dict) else tuple(item)
             for item in config.get('music_drops', [])]
    return EpisodeAudioMixer().mix(duration,clips,output,bgm=[root/path for path in config.get('bgm',[])],
           bgm_cuts=config.get('bgm_cuts',bgm_cuts),music_drops=drops,
           sound_marks=[*config.get('sound_marks',[]), *sound_marks],sfx_library=library,
           intro_fade_in=float(config.get('intro_fade_in',0.)),crossfade=float(config.get('crossfade',6.)))

"""Offline regression coverage for the v9 director, renderer and audit."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
assemble = importlib.import_module('assemble-episode')
bridge = importlib.import_module('render-onetake-clip')
scout = importlib.import_module('scout-video-scenes')
scaffold = importlib.import_module('scaffold-manifest')
import audit_v7 as audit
import workspace


def shot(key, start=0, end=5, mode='fullbleed_rig', **fields):
    return dict(id=key,start=start,end=end,stage_mode=mode,semantic_binding='exact_tool_capture',**fields)


def test_subtitle_band_uses_visible_pixels(tmp_path):
    video = tmp_path/'cross.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=320x180:d=2:r=30',
                    '-f','lavfi','-i','color=white:s=320x180:d=2:r=30','-filter_complex','concat=n=2:v=1:a=0',
                    '-threads','2',str(video)],check=True)
    for frame in ('studio_window','perspective_3d','fullbleed'):
        row = shot('clip',end=4,framing=frame,spoken_topic='实录',media=[video],media_start=0.,motion='hold')
        stage = assemble.build_act([row],tmp_path,tmp_path/frame,'实录',subprocess.run)
        if frame=='fullbleed':
            assert len(stage.light_zones)==1
            assert stage.light_zones[0]==pytest.approx((2.,4.),abs=1/30)
            stage.add_captions([dict(text='跨切点',start=1.5,end=2.5)])
            assert len(stage.captions)==2 and 'caption-on-light' in stage.captions[1]
            stage.write_project(tmp_path/'caption-review')
            page=(tmp_path/'caption-review/index.html').read_text()
            base=page.split('.cap span{',1)[1].split('}',1)[0]
            assert 'background:rgba(12,18,24,.88)' in base and 'border-radius:12px' in base
        else:
            assert not stage.light_zones


def test_render_workers_priority_and_quality_cache(tmp_path,monkeypatch):
    monkeypatch.delenv('YICE_RENDER_WORKERS',raising=False)
    monkeypatch.delenv('YICE_RENDER_NICE',raising=False)
    assert workspace.render_workers()==2
    if os.name=='posix':
        nice = subprocess.check_output([sys.executable,'-c','import os;print(os.nice(0))'],
                                       **workspace.render_priority(),text=True)
        assert int(nice)>=10
    for name in ('assets/mix.wav','vendor/gsap.min.js','index.html'):
        path = tmp_path/name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    stage = SimpleNamespace(duration=5,shots=[])
    calls = []
    def run(cmd,**options):
        if os.name=='posix':
            assert callable(options['preexec_fn'])
        if cmd[1]=='render':
            calls.append((cmd[cmd.index('--workers')+1],cmd[cmd.index('--quality')+1]))
            (tmp_path/cmd[cmd.index('--output')+1]).touch()
    monkeypatch.setattr(assemble,'probe_video',lambda _:5)
    def render(**options):
        return assemble.render_act(tmp_path,stage,['hf'],{},run,**options)
    assert render()=='rendered'
    monkeypatch.setenv('YICE_RENDER_WORKERS','1')
    assert render()=='reused'
    assert render(draft=True)=='rendered'
    assert render(workers=2)=='rendered'
    assert calls==[('2','looks'),('1','draft'),('2','looks')]
    with pytest.raises(ValueError):
        workspace.render_workers(0)


def test_onetake_default_workers(tmp_path,monkeypatch):
    monkeypatch.delenv('YICE_RENDER_WORKERS',raising=False)
    monkeypatch.setattr(bridge,'resolve_onetake',lambda:tmp_path)
    monkeypatch.setattr(bridge,'stage_composition',lambda *a,**k:tmp_path/'comp.html')
    monkeypatch.setattr(bridge,'validate_probe',lambda *a:None)
    def run(cmd,**options):
        if os.name=='posix':
            assert callable(options['preexec_fn'])
        if '--workers' in cmd:
            assert cmd[cmd.index('--workers')+1]=='2'
            output=Path(cmd[cmd.index('--out')+1])
            output.touch()
            output.with_suffix('.render.json').write_text(json.dumps(dict(fps=30,size=[1920,1080],shutter=180,frames=0)))
        elif cmd[0]=='ffmpeg':
            assert cmd[cmd.index('-threads')+1]=='2'
            Path(cmd[-1]).touch()
        return SimpleNamespace(stdout='{}')
    monkeypatch.setattr(bridge.subprocess,'run',run)
    bridge.render_clip(tmp_path/'comp.html',tmp_path/'clip.mp4',span=1)


def test_caption_boundaries_are_scaffold_anchors(tmp_path):
    voice=tmp_path/'voice.json'
    voice.write_text(json.dumps(dict(total_duration=14,scene_timing=[dict(id='A',firstCharTime=0,text='操作')])))
    (tmp_path/'captions.json').write_text(json.dumps([dict(startMs=t,endMs=end,text=str(t))
                             for t,end in ((0,2400),(2400,4500),(4500,9400),(9400,14000))]))
    draft=scaffold.scaffold(voice,None,tmp_path/'manifest.json','演示')
    shots=draft['shots']
    assert [s['start'] for s in shots]==[0,4.5,9.4]
    assert all(3.5<=audit.shot_span(s)<=6 for s in shots)
    assert [s['stage_mode'] for s in shots] == ['hyperframes_block','onetake_clip','fullbleed_rig']
    assert [s['visual_mode'] for s in shots] == ['M1','M3','M2']
    assert shots[0]['composition'] and shots[1]['comp'] and shots[2]['source']
    assert shots[1]['shutter']==180 and shots[1]['look']=='paper'
    cues={c['id']:c['firstCharTime'] for c in draft['cues']}
    assert all(abs(cues[s['anchor_cue_id']]-s['start'])<=.22 for s in shots)
    (tmp_path/'captions.json').unlink()
    assert scaffold.scaffold(voice,None,tmp_path/'fallback.json','演示')['shots'][0]['needs_subcut']


def test_rhythm_and_framing_thresholds():
    shots=[shot(str(i),i*5,i*5+5,mode='explainer_clip' if i%3==0 else 'callout_rig') for i in range(20)]
    assert audit.pacing_and_rhythm_gate(shots,100)['ok']
    assert audit.framing_and_variety_gate(shots,100)['ok']
    shots[-1]['end']+=7
    assert not audit.pacing_and_rhythm_gate(shots,107)['ok']
    shots[-1].update(stage_mode='triptych_cards',cards=[dict(source=f'{i}.mp4',reveal_at=i) for i in range(2)])
    assert audit.pacing_and_rhythm_gate(shots,107)['ok']
    for s in shots[1:3]:
        s['framing']='studio_window'
    framed=audit.framing_and_variety_gate(shots,107)
    assert not framed['ok'] and framed['max_consecutive_windowed_shots']==2


def test_studio_density_and_adjacent_panels_are_independent():
    shots=[shot(str(i),i,i+1,mode='explainer_clip' if i%2 else 'fullbleed_rig') for i in range(50)]
    for i in range(0,45,5):
        shots[i]['stage_mode']='studio_ui'
    assert audit.framing_and_variety_gate(shots,50)['ok']
    shots[47]['stage_mode']='studio_ui'
    assert {v['reason'] for v in audit.framing_and_variety_gate(shots,50)['violations']} == {'studio_ui_ratio'}
    shots[47]['stage_mode']='explainer_clip'
    shots[5]['stage_mode']='explainer_clip'
    shots[1]['stage_mode']='studio_ui'
    assert {v['reason'] for v in audit.framing_and_variety_gate(shots,50)['violations']} == {'adjacent_studio_ui'}


def test_richness_and_manifest_precheck(tmp_path,monkeypatch):
    rng=np.random.default_rng(4)
    rich=Image.fromarray(rng.integers(0,255,(180,320,3),dtype='uint8'))
    flat=Image.new('RGB',(320,180),'white')
    shots=[shot('blank',source='blank.mp4'),shot('rich',5,10,source='rich.mp4',framing='studio_window')]
    monkeypatch.setattr(audit,'capture_frame',lambda s,*args: flat if s['id']=='blank' else rich)
    report=audit.visual_richness_gate(dict(shots=shots),tmp_path,None)
    assert [v['shot'] for v in report['violations']]==['blank']
    assert audit.visual_richness_gate(dict(shots=shots[1:]),tmp_path,None)['ok']
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(shots=shots)))
    monkeypatch.setattr(scout,'frame_at',lambda file,_:flat.copy() if file.stem=='blank' else rich.copy())
    scout.write_verification(manifest,tmp_path)
    rows=json.loads((tmp_path/'manifest-visual-verify.json').read_text())
    assert [s['shot'] for s in rows['low_density_shell_shots']]==['blank']


def test_craft_and_cross_stage_dedup(tmp_path):
    folder=tmp_path/'block'
    folder.mkdir()
    src=folder/'index.html'
    image=Image.fromarray(np.random.default_rng(3).integers(0,255,(180,320,3),dtype='uint8'))
    image.save(folder/'one.png')
    image.save(folder/'two.png')
    src.write_text('<img src="one.png"><img src="two.png">')
    block=shot('block',mode='hyperframes_block',composition='block/index.html')
    assert not audit.dual_engine_craft_gate([block],tmp_path)['ok']
    src.write_text('<img src="one.png">')
    assert audit.dual_engine_craft_gate([block],tmp_path)['ok']
    motion=shot('motion',mode='onetake_clip',comp='block/index.html')
    assert not audit.dual_engine_craft_gate([motion],tmp_path)['ok']
    src.write_text('<script>OM.morphRect(t,0,1,a,b)</script><img src="one.png">')
    assert audit.dual_engine_craft_gate([motion],tmp_path)['ok']
    cards=shot('cards',mode='triptych_cards',cards=[dict(source='block/two.png')])
    spot=shot('spot',mode='evidence_spotlight',source='block/one.png')
    def dedup(shots):
        return audit.cross_stage_asset_dedup_gate(dict(shots=shots),tmp_path,None)
    assert dedup([block,cards])['ok']
    assert dedup([block,cards,spot])['violations'][0]['shots']==['block','cards','spot']
    assert dedup([block,cards,dict(spot,callback_of='cards')])['ok']


def test_tutorial_requires_process_and_interactive_result():
    process=shot('input',mode='studio_ui',studio_style='terminal_pipeline',files=['session.txt'])
    result=shot('result',5,10,source='capture.mp4',visual_subject='点击成品查看详情')
    def gate(shots):
        return audit.tutorial_workflow_gate(dict(episode_kind='tool_tutorial',shots=shots))
    assert gate([process,result])['ok']
    assert gate([result])['violations']==['missing_input_or_execution']
    assert gate([process])['violations']==['missing_interactive_result']

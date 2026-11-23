"""Synthetic, offline exercise of the v7 pipeline and its adversarial gates."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT/'scripts')]
from audit_v7 import (breath_integrity_gate, first_half_motion_density_gate,
                      opener_bgm_and_sfx_gate, semantic_binding_gate, timeline_gates)
from kit.editorial.audio_mix import EpisodeAudioMixer
from kit.editorial.autopilot import Beat, SemanticBeatPlanner
from kit.editorial.editorial import EditorialStage
import voice

assemble = importlib.import_module('assemble-episode')
quality = importlib.import_module('voice-quality')
post = importlib.import_module('voice-post')
RATE = 24000


def tone(seconds, level=.15, frequency=220):
    return level*np.sin(2*np.pi*frequency*np.arange(round(seconds*RATE))/RATE)


def wave(path, samples):
    sf.write(path,samples,RATE,subtype='PCM_24')
    return path


def test_long_paragraph_keeps_text_and_breath(tmp_path):
    text = '先公布结果，再展示步骤。'*17
    assert voice.chapter_chunks(text)==[text]
    longer = '接下来介绍使用场景。'*54
    chunks = voice.chapter_chunks(longer)
    assert len(chunks)==2 and ''.join(chunks)==longer and max(map(len,chunks))<=380
    assert voice.chapter_chunks(longer,'whole_chapter')==[longer]
    assert len(voice.chapter_chunks(longer,'legacy_chunk'))>2
    breath = tone(.16,.0038,520)
    a = wave(tmp_path/'one.wav',np.r_[tone(.4),tone(.15,.00035)])
    b = wave(tmp_path/'two.wav',np.r_[tone(.08,.00035),breath,tone(.4)])
    merged = tmp_path/'joined.wav'
    voice._concat_wavs([a,b],merged,pauses={1:.6})
    data,rate = sf.read(merged)
    assert rate==RATE
    boundary = len(data)-round(.4*rate)
    np.testing.assert_allclose(data[boundary-len(breath):boundary],breath,atol=4/32768)
    assert np.sqrt(np.mean(data[round(.55*rate):round(.80*rate)]**2))>1e-4


def test_natural_post_preserves_planned_pause_and_ordinary_breath(tmp_path):
    source = np.r_[tone(.25),tone(.20,.0039),tone(.25)]
    path = wave(tmp_path/'source.wav',source)
    out = tmp_path/'clean.wav'
    alignment = dict(text='甲。乙。',mapped=[dict(charStart=0,charEnd=1,s=0,e=.25),
                                          dict(charStart=2,charEnd=3,s=.45,e=.70)],planned_pauses={'1':.2})
    aligned,edits = post.preserve_breaths(path,alignment,out)
    assert not edits and aligned['mapped']==alignment['mapped']
    data,_ = sf.read(out)
    np.testing.assert_allclose(data,source,atol=2e-7)


def test_natural_asr_only_waives_equal_pronunciations_and_spellings():
    audit = quality.audit('逐帧录屏，用 Playwright。',{'text':'逐针路屏，用 Play-wright。'},auto_homophone=True)
    assert audit['ok'] and audit['auto_homophone']
    assert not quality.audit('三段音轨',{'text':'二段音轨'},auto_homophone=True)['ok']
    assert not quality.audit('先找再剪',{'text':'先找再见'},auto_homophone=True)['ok']
    assert not quality.audit('逐帧展示',{'text':'展示'},auto_homophone=True)['ok']


def test_music_and_effects_start_with_first_frame(tmp_path):
    src = wave(tmp_path/'voice.wav',tone(5.))
    bgm = wave(tmp_path/'music.wav',tone(5.,.12,100))
    effects = [dict(kind='tick',at=0),dict(kind='whoosh',at=.65),dict(kind='stamp',at=1.1)]
    result = EpisodeAudioMixer(sample_rate=RATE).mix(5,[{'path':src}],tmp_path/'out',
                     bgm=[bgm],sound_marks=effects,music_drops=[(2,2.5)])
    assert result['sound_marks'][0]['at']==0
    assert abs(result['measured_lufs']+14.5)<=.8 and result['true_peak_dbtp']<=-1
    bed = tmp_path/'out/bed-only.wav'
    assert opener_bgm_and_sfx_gate(bed,effects,5)['ok']
    y,_ = sf.read(bed)
    assert np.any(y[:100])
    assert np.std(y[2*RATE:int(2.5*RATE)])<np.std(y[:RATE])/100
    blank = wave(tmp_path/'silent-bed.wav',np.zeros(RATE*5))
    assert not opener_bgm_and_sfx_gate(blank,effects,5)['ok']
    assert not opener_bgm_and_sfx_gate(bed,effects[:2],5)['ok']


def test_overlay_primitives_emit_real_actions():
    stage = EditorialStage('实操样片',duration=14)
    stage.add_cold_open_ab(0,4,'left.mp4','right.mp4',hook='哪段更清楚？')
    stage.add_title_sequence(4,6,['实操','现场'],highlight='现场')
    stage.add_callout_rig(6,10,'source.mp4',overlays=[{'kind':'spotlight_box','at':.3,'label':'执行按钮'},
              {'kind':'stat_badge','at':1.5,'label':'实测','value':16.5,'unit':' 秒'}])
    stage.add_callout_rig(10,14,'more.mp4',overlays=[{'kind':'strikethrough_list','at':0,'label':'排查',
               'items':['重新安装','重跑步骤']},{'kind':'verdict_stamp','at':2,'label':'通过'}])
    assert len(stage.shots)==4 and all(shot['has_motion_overlay'] for shot in stage.shots)
    assert [at for kind,at in stage.sound_marks if kind=='tick']==[1,2,3]
    assert {'tick','whoosh','stamp','marker','pop'} <= {kind for kind,_ in stage.sound_marks}
    assert 'stat-readout' in ''.join(stage.plates+stage.scripts)


def test_semantic_gate_rejects_unrelated_website_and_recognizes_exact_capture():
    shot = dict(id='a',stage_mode='fullbleed_rig',spoken_topic='素材优先级清单',visual_subject='FFmpeg 官网',
                semantic_tags=['FFmpeg'],semantic_binding='physical_prop')
    assert not semantic_binding_gate([shot])['ok']
    tool = dict(shot,spoken_topic='使用 HyperFrames 处理画面',semantic_binding='exact_tool_capture')
    assert not semantic_binding_gate([tool])['ok']
    assert semantic_binding_gate([dict(tool,visual_subject='HyperFrames 工程',semantic_tags=['HyperFrames'])])['ok']
    overlay = dict(shot,stage_mode='callout_rig',has_motion_overlay=True,semantic_tags=['素材优先级'],
                   semantic_binding='callback_cut',overlays=[{'kind':'stat_badge','label':'素材优先级清单'}])
    assert semantic_binding_gate([overlay])['ok']
    suggestion = SemanticBeatPlanner().balance_visual_rhythm([Beat('a',0,4,'这一条素材优先级清单'),
                                                               Beat('b',4,8,'点开官网页面')])
    assert [row['suggested_kind'] for row in suggestion]==['explainer_graphic','web_cam']


def test_motion_gate_requires_two_halves_and_caps_bare_footage():
    bare = [{'start':0,'end':15,'stage_mode':'fullbleed_rig'},
            {'start':15,'end':17,'stage_mode':'title_sequence'},
            {'start':17,'end':30,'stage_mode':'explainer_clip'}]
    result = first_half_motion_density_gate(bare,30)
    assert not result['ok'] and result['longest_bare_video_seconds']==15
    bare[0].update(stage_mode='callout_rig',has_motion_overlay=True,overlays=[{'kind':'spotlight_box'}])
    assert first_half_motion_density_gate(bare,30)['ok']


def test_breath_gate_catches_digital_zero_and_insertion_log(tmp_path):
    path = wave(tmp_path/'voice.wav',np.r_[tone(.4),np.zeros(round(.08*RATE)),tone(.4)])
    value = {'voice_tracks':[{'id':'first','path':path.name}]}
    assert breath_integrity_gate(tmp_path,value)['violations'][0]['duration_ms']==pytest.approx(80,abs=.15)
    wave(path,np.r_[tone(.4),tone(.08,.0004),tone(.4)])
    assert breath_integrity_gate(tmp_path,value)['ok']
    log = tmp_path/'post.json'
    log.write_text(json.dumps({'semantic_pause_edits':[{'kind':'insert'}]}))
    value['voice_processing_logs']=[log.name]
    assert not breath_integrity_gate(tmp_path,value)['ok']


def test_concat_cli_uses_authored_pause_room_tone_and_fade(tmp_path):
    blank = np.zeros(round(.25*RATE))
    one = wave(tmp_path/'segment-a.wav',np.r_[tone(.35),blank])
    two = wave(tmp_path/'segment-b.wav',np.r_[blank,tone(.35)])
    target = tmp_path/'chapter.wav'
    result = subprocess.run([sys.executable,str(KIT/'scripts/voice.py'),'--concat-wavs',str(one),str(two),
                             '--pause','1=3.0','--crossfade-ms','80','--room-tone-dbfs','-60',
                             '--output',str(target)],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout)['crossfade_ms']==80
    data,rate = sf.read(target)
    assert len(data)/rate==pytest.approx(3.7,abs=.004)
    central = data[rate:3*rate]
    assert 20*np.log10(np.sqrt(np.mean(central**2)))==pytest.approx(-60.,abs=.15)
    assert breath_integrity_gate(tmp_path,{'voice_tracks':[{'path':target.name}]})['ok']


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='需要本地 ffmpeg')
def test_assemble_episode_end_to_end(tmp_path):
    def footage(path,color,duration):
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                        f'color={color}:s=1920x1080:r=30:d={duration}',
                        '-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)

    footage(tmp_path/'left.mp4','#527a74',4.5)
    footage(tmp_path/'right.mp4','#825b64',4.5)
    wave(tmp_path/'voice.wav',tone(8.5))
    live = os.environ.get('YICE_TEST_HYPERFRAMES') == '1'
    gsap = os.environ.get('YICE_GSAP_PATH')
    if not live:
        gsap = tmp_path/'gsap.min.js'
        gsap.write_text('// runtime substituted by the renderer fixture')
    input_data = dict(filename='sample',gsap=str(gsap),duration=8.5,
            audio={'voice_tracks':[{'path':'voice.wav','at':0}]},
            cues=[{'id':'0-1','firstCharTime':0,'end':3.5,'text':'比较样片。'},
                  {'id':'0-2','firstCharTime':4,'end':6.2,'text':'今天看这个主题。'},
                  {'id':'0-3','firstCharTime':6.5,'end':8.1,'text':'先核对清单。'}],
            shots=[dict(id='a',act='opening',anchor_cue_id='0-1',start=0,end=4,stage_mode='cold_open_ab',
                        sources=['left.mp4','right.mp4'],semantic_binding='callback_cut',spoken_topic='样片对照',
                        visual_subject='原片和修订片',semantic_tags=['样片']),
                   dict(id='b',act='title',anchor_cue_id='0-2',start=4,end=6.5,stage_mode='title_sequence',
                        title='今天的主题',semantic_binding='conceptual_explainer',spoken_topic='介绍主题',
                        visual_subject='主题扉页',semantic_tags=['主题']),
                   dict(id='c',act='title',anchor_cue_id='0-3',start=6.5,end=8.5,stage_mode='explainer_clip',
                        semantic_binding='conceptual_explainer',spoken_topic='核对清单',
                        visual_subject='实质核验清单',semantic_tags=['清单'],
                        spec={'grammar':'t6_swiss_card','data':{'title':'核对清单'},
                              'cues':[{'at':.2,'kind':'point','text':'核对输入'}]})])
    path = tmp_path/'episode-manifest.json'
    path.write_text(json.dumps(input_data,ensure_ascii=False))
    rendered = []

    def runner(command,**kwargs):
        if 'hyperframes' in command and 'render' in command:
            folder = kwargs['cwd']
            duration = json.loads((folder/'shot-timeline.json').read_text())['end']
            footage(folder/'render.mp4','#526760',duration)
            rendered.append(folder.name)
        elif any(arg.endswith('/render-explainer-clip.sh') for arg in command):
            spec = json.loads(Path(command[command.index('--spec')+1]).read_text())
            footage(Path(command[command.index('--out')+1]),'#394e57',spec['duration'])
        elif 'hyperframes' not in command:
            return subprocess.run(command,**kwargs)

    output = tmp_path/'out'
    result = assemble.assemble(path,output,run=subprocess.run if live else runner)
    assert result['ok'] and (output/'sample.mp4').is_file()
    assert rendered==['opening','title'] or live
    timeline = json.loads((output/'shot-timeline.json').read_text())
    assert timeline_gates(timeline,output,8.5)['ok']
    assert semantic_binding_gate(timeline['shots'])['ok']
    assert opener_bgm_and_sfx_gate(output/'bed-only.wav',timeline['sound_marks'],8.5)['ok']
    assert first_half_motion_density_gate(timeline['shots'],8.5)['ok']
    assert '00:00:04,000' in (output/'sample.srt').read_text()

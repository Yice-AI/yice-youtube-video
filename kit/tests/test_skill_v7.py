"""Synthetic, offline exercise of the v7 pipeline and its adversarial gates."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from urllib.parse import urlsplit
import urllib.request

import numpy as np
import pytest
import soundfile as sf

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT/'scripts')]
from audit_v7 import (breath_integrity_gate, first_half_motion_density_gate,
                      opener_bgm_and_sfx_gate, semantic_binding_gate,
                      spotlight_restraint_gate, timeline_gates)
from kit.editorial.audio_mix import EpisodeAudioMixer
from kit.editorial.autopilot import Beat, SemanticBeatPlanner
from kit.editorial.editorial import EditorialStage
import voice
from workspace import load_environment

assemble = importlib.import_module('assemble-episode')
quality = importlib.import_module('voice-quality')
post = importlib.import_module('voice-post')
RATE = 24000


def tone(seconds, level=.15, frequency=220):
    return level*np.sin(2*np.pi*frequency*np.arange(round(seconds*RATE))/RATE)


def wave(path, samples):
    sf.write(path,samples,RATE,subtype='PCM_24')
    return path


@pytest.fixture
def kaggle_http(monkeypatch, tmp_path):
    audio = wave(tmp_path/'sample.wav', tone(.1)).read_bytes()
    reference = tmp_path/'sample.wav'
    monkeypatch.setattr(voice, '_clone_reference', lambda brand: (reference, '参考旁白', 'Chinese'))
    monkeypatch.setenv('KAGGLE_TTS_ENDPOINT_URL', 'https://tts.invalid/tts')
    monkeypatch.setenv('KAGGLE_TTS_TOKEN', 'mock-token')
    monkeypatch.delenv('YICE_TTS_TIMEOUT', raising=False)
    real_urlopen = urllib.request.urlopen
    job_id = '0011223344556677'
    requests = []
    sleeps = []
    monkeypatch.setattr(voice, 'time', SimpleNamespace(monotonic=voice.time.monotonic, sleep=sleeps.append))

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.command, self.path, self.headers.get('Authorization'), payload))
            if self.path == '/tts_async':
                if self.server.legacy:
                    self.respond(404, {'detail': 'route missing'})
                else:
                    self.respond(200, {'status': 'running', 'job_id': job_id})
            elif self.path == '/tts':
                self.respond(200, {'outputs': self.server.outputs})
            else:
                self.respond(404, {})

        def do_GET(self):
            requests.append((self.command, self.path, self.headers.get('Authorization'), None))
            if self.path != '/tts_job/' + job_id:
                self.respond(404, {})
                return
            self.server.poll_count += 1
            if self.server.poll_count < 3:
                self.respond(200, {'status': 'running'})
            else:
                self.respond(200, {'status': 'done', 'outputs': self.server.outputs})

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        server.legacy = False
        server.poll_count = 0
        server.timeouts = []
        server.outputs = [{'audio_base64': base64.b64encode(audio).decode()}]

        def open_local(request, *, timeout):
            server.timeouts.append(timeout)
            local = urllib.request.Request(
                f'http://127.0.0.1:{server.server_port}' + urlsplit(request.full_url).path,
                data=request.data, headers=dict(request.header_items()), method=request.method,
            )
            return real_urlopen(local, timeout=timeout)

        monkeypatch.setattr(voice.urllib.request, 'urlopen', open_local)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server, requests, sleeps, job_id, audio
        finally:
            server.shutdown()
            worker.join()


def test_kaggle_async_polls_until_whole_chapter_audio(kaggle_http):
    _, requests, sleeps, job_id, audio = kaggle_http
    chapter = '先公布结果，再完整展示操作步骤。' * 24
    assert voice._remote_batch([chapter], 'test', 'kaggle', .7) == [audio]
    assert [(method, route) for method, route, _, _ in requests] == [
        ('POST', '/tts_async'), *[('GET', '/tts_job/' + job_id)] * 3,
    ]
    assert all(auth == 'Bearer mock-token' for _, _, auth, _ in requests)
    assert requests[0][3]['text'] == [chapter]
    assert sleeps == [2.5, 2.5, 2.5]


def test_kaggle_async_404_falls_back_to_sync(kaggle_http):
    server, requests, sleeps, _, audio = kaggle_http
    server.legacy = True
    paragraph = '这一整段使用旧服务合成。' * 15
    assert voice._remote_batch([paragraph], 'test', 'kaggle', .7) == [audio]
    assert [(method, route) for method, route, _, _ in requests] == [
        ('POST', '/tts_async'), ('POST', '/tts'),
    ]
    assert requests[0][3] == requests[1][3]
    assert requests[1][3]['text'] == [paragraph]
    assert sleeps == []


def test_kaggle_submit_uses_longer_timeout_than_poll(kaggle_http, monkeypatch):
    server, _, _, _, audio = kaggle_http
    monkeypatch.setattr(voice.time, 'monotonic', lambda: 0.)
    assert voice._remote_batch(['整章。'], 'test', 'kaggle', .7) == [audio]
    assert server.timeouts == [60., 15., 15., 15.]

    monkeypatch.setenv('YICE_TTS_TIMEOUT', '12')
    server.timeouts.clear()
    server.poll_count = 0
    assert voice._remote_batch(['整章。'], 'test', 'kaggle', .7) == [audio]
    assert server.timeouts == [12., 12., 12., 12.]


def test_chinese_tts_text_removes_ascii_spaces_without_shifting_scenes(tmp_path, kaggle_http):
    _, requests, _, _, audio = kaggle_http
    script = tmp_path/'script.md'
    script.write_text(
        '## 00 开场\n| 0-1 | 开 始游戏 。 |\n| 0-2 | 左边 看 Johnny Harris 。 |\n'
        '| 0-3 | Johnny |\n| 0-4 | Harris |\n',
    )
    chapter, = voice.parse_script(script)
    assert chapter['text'] == '开始游戏。左边看Johnny Harris。Johnny Harris'
    spans = [(scene['id'], start, end) for scene, start, end in voice.scene_text_spans(chapter)]
    assert spans == [('0-1', 0, 5), ('0-2', 5, 22), ('0-3', 22, 28), ('0-4', 29, 35)]

    raw = '开始游戏。  左边 看 Johnny Harris ！'
    assert voice._remote_batch([raw], 'test', 'kaggle', .7) == [audio]
    assert requests[0][3]['text'] == ['开始游戏。左边看Johnny Harris！']


def test_whisper_model_precedence_and_workspace_config(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.delenv('YICE_ASR_MODEL', raising=False)
    assert voice.resolve_asr_model() == 'mlx-community/whisper-large-v3-turbo'

    local = tmp_path/'yice-demo/我的视频/models/Whisper-Large-v3-Turbo'
    local.parent.mkdir(parents=True)
    local.touch()
    assert voice.resolve_asr_model() == 'mlx-community/whisper-large-v3-turbo'
    local.unlink()
    local.mkdir()
    (local/'config.json').write_text('{}')
    (local/'weights.safetensors').touch()
    assert voice.resolve_asr_model() == str(local)

    config = tmp_path/'.config/yice-video/env'
    config.parent.mkdir(parents=True)
    config.write_text('YICE_ASR_MODEL="$HOME/模型/本地 Whisper"\n')
    config_env = {'HOME': str(tmp_path)}
    load_environment(config_env)
    assert config_env['YICE_ASR_MODEL'] == str(tmp_path/'模型/本地 Whisper')
    config_env['YICE_ASR_MODEL'] = 'org/environment-model'
    load_environment(config_env)
    monkeypatch.setenv('YICE_ASR_MODEL', config_env['YICE_ASR_MODEL'])
    assert voice.resolve_asr_model() == 'org/environment-model'
    assert voice.resolve_asr_model('org/cli-model') == 'org/cli-model'


def test_whisper_model_with_broken_symlinks_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.delenv('YICE_ASR_MODEL', raising=False)
    local = tmp_path/'yice-demo/我的视频/models/Whisper-Large-v3-Turbo'
    local.mkdir(parents=True)
    config = tmp_path/'config.json'
    weights = tmp_path/'weights.safetensors'
    (local/'config.json').symlink_to(config)
    (local/'weights.safetensors').symlink_to(weights)
    fallback = 'mlx-community/whisper-large-v3-turbo'
    assert voice.resolve_asr_model() == fallback
    weights.touch()
    assert voice.resolve_asr_model() == fallback
    weights.unlink()
    config.write_text('{}')
    assert voice.resolve_asr_model() == fallback
    for name in ('weights.safetensors', 'model.safetensors', 'weights.npz'):
        target = weights if name == weights.name else local/name
        target.touch()
        assert voice.resolve_asr_model() == str(local)
        target.unlink()


def test_long_paragraph_keeps_text_and_breath(tmp_path):
    sentence = '甲'*19 + '。'
    text = sentence*5
    assert voice.chapter_chunks(text)==[text]
    assert voice.chapter_chunks(sentence*10)==[text, text]
    assert voice.chapter_chunks(sentence*12)==[sentence*4]*3
    assert voice.chapter_chunks('好。'*6)==['好。'*5, '好。']
    quoted = '“' + '甲'*21 + '！”'
    assert voice.chapter_chunks(quoted*8)==[quoted*4]*2
    longer = sentence*54
    chunks = voice.chapter_chunks(longer)
    assert ''.join(chunks)==longer and all(65<=len(chunk)<=115 for chunk in chunks)
    assert voice.chapter_chunks(longer,'whole_chapter')==[longer]
    assert len(voice.chapter_chunks(longer,'legacy_chunk'))>2
    assert voice.chapter_chunks('甲'*114 + '。')==['甲'*114 + '。']
    with pytest.raises(ValueError, match='单句超过 115 字'):
        voice.chapter_chunks('甲'*58 + '\n' + '乙'*57)
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


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='需要本地 ffmpeg')
def test_master_gain_limits_transients_without_changing_frame_count(tmp_path, monkeypatch):
    seconds = 32
    time = np.arange(seconds*RATE)/RATE
    voicebed = (.8*np.sin(2*np.pi*212*time)+.2*np.sin(2*np.pi*340*time))
    voicebed *= np.repeat([.05,.4,.05,.05],8*RATE) * (.5+.5*np.sin(2*np.pi*2.8*time)**2)
    for at in (3,8,13,18,23,28):
        voicebed[at*RATE:at*RATE+round(1.1*RATE)] = 0
    for at in (4,9,14,19,24,29):
        voicebed[at*RATE:at*RATE+24] = .95*np.hanning(24)
    source, target = tmp_path/'premaster.wav', tmp_path/'master.wav'
    sf.write(source,voicebed,RATE,subtype='FLOAT')
    measurements = []
    measure = post.loudness

    def record(path, target_lufs):
        levels = measure(path,target_lufs)
        measurements.append(levels)
        return levels

    monkeypatch.setattr(post,'loudness',record)
    result = post.normalize_lufs(source,target,-14.5)
    first_lufs = float(measurements[1]['input_i'])
    first_peak = float(measurements[1]['input_tp'])
    assert first_lufs < -15.3 and first_peak + (-14.5-first_lufs) > -1.1
    assert sf.info(target).frames == sf.info(source).frames == result['samples']
    assert abs(result['measured_lufs']+14.5)<=.35
    assert result['true_peak_dbtp']<=-1.05
    print('首轮',first_lufs,first_peak,'补偿后',result['measured_lufs'],result['true_peak_dbtp'],'采样帧',result['samples'])


def test_overlay_primitives_emit_real_actions():
    stage = EditorialStage('实操样片',duration=14)
    stage.add_cold_open_ab(0,4,'left.mp4','right.mp4',hook='哪段更清楚？')
    stage.add_title_sequence(4,6,['实操','现场'],highlight='现场')
    stage.add_callout_rig(6,10,'source.mp4',overlays=[{'kind':'spotlight_box','at':.3,'label':'执行按钮',
              'box':[650,240,420,220],'target_verified':True,'target_note':'按钮像素边界'},
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
    bare = [{'start':0,'end':17,'stage_mode':'fullbleed_rig'},
            {'start':17,'end':19,'stage_mode':'studio_ui'},
            {'start':19,'end':36,'stage_mode':'explainer_clip'}]
    result = first_half_motion_density_gate(bare,36)
    assert not result['ok'] and result['longest_bare_video_seconds']==17
    bare[0].update(stage_mode='callout_rig',has_motion_overlay=True,overlays=[{'kind':'corner_tag'}])
    assert first_half_motion_density_gate(bare,36)['ok']


def test_spotlight_requires_verified_target_and_rejects_reuse():
    stage = EditorialStage('标注',duration=4)
    overlay = dict(kind='spotlight_box',at=0,label='大小列',box=[350,220,420,240],
                   target_verified=True,target_note='右上区域大小列标题')
    for invalid, message in ((dict(overlay,target_verified=False),'像素目标'),
                             (dict(overlay,box=[350,220,1180,485]),'尺寸过大'),
                             (dict(overlay,box=None),'显式 box')):
        with pytest.raises(ValueError,match=message):
            stage.add_callout_rig(0,4,'source.mp4',overlays=[invalid])
    shots = [dict(id=str(index),overlays=[dict(overlay,box=[350+index*.01,220,420,240])])
             for index in range(4)]
    report = spotlight_restraint_gate(shots)
    assert not report['ok'] and report['spotlight_count']==4 and report['maximum']==3
    assert any('复制粘贴' in item['reason'] for item in report['violations'])
    assert any('8%' in item['reason'] for item in report['violations'])
    assert not spotlight_restraint_gate([dict(id='bad',stage_mode='reference_breakdown',channel='Fireship')])['ok']
    assert spotlight_restraint_gate([shots[0]])['ok']


def test_v7_ocr_channel_exemption_is_scoped_to_declared_shot_and_keeps_privacy():
    audit = importlib.import_module('audit-v3')
    timeline = {'shots': [
        {'start':0,'end':2,'stage_mode':'reference_breakdown','channel':'Johnny Harris'},
        {'start':2,'end':4,'stage_mode':'triptych_cards','cards':[{'label':'画面引用 · Fireship'}],
         'semantic_tags':['Johnny Harris 对照']},
        {'start':4,'end':6,'stage_mode':'fullbleed_rig','semantic_tags':['Johnny Harris','Fireship']},
        {'start':6,'end':8,'stage_mode':'triptych_cards','cards':[{'source':'fireship.mp4'}],
         'semantic_tags':['NotFireshipClone']},
    ]}
    privacy = ['sample-owner','/Users/','alias@example.test','192.0.2.23']
    rows = [{'text':'画面引用 · JOHNNY HARRIS / Fireship','box':[80,110,500,40]},
            {'text':'Johnny Harris /Users/sample-owner alias@example.test 192.0.2.23','box':[80,160,720,40]},
            {'text':'alias@example.test','box':[80,980,460,40]}]

    def hits(second, citations=timeline, terms=privacy):
        return [row['term'] for row in audit.frame_ocr_hits(rows,second,terms,citation_timeline=citations)]

    assert set(hits(1)) == {*privacy,'Fireship'}
    assert set(hits(2)) == set(privacy)
    assert hits(2).count('alias@example.test') == 2
    for second in (4,6,8):
        assert set(hits(second)) == {*privacy,'Johnny Harris','Fireship'}
    assert set(hits(1,None)) == {*privacy,'Johnny Harris','Fireship'}
    assert 'Johnny Harris' in hits(1,terms=[*privacy,'Johnny Harris'])


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='需要本地 ffmpeg')
def test_reference_breakdown_and_restraint_offline(tmp_path):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=#475853:s=320x180:r=30:d=5',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(tmp_path/'clip.mp4')],check=True)
    overlay = dict(kind='spotlight_box',at=.5,duration=2.6,label='执行按钮',box=[680,105,380,240],
                   target_verified=True,target_note='画面上方按钮像素边界')
    shots = [
        dict(id='reference',start=0,end=4,stage_mode='reference_breakdown',source='clip.mp4',
             anchor_cue_id='a',spoken_topic='Johnny Harris 的剪辑节奏',visual_subject='Johnny Harris 参考片',
             semantic_binding='conceptual_explainer',semantic_tags=['Johnny Harris','剪辑节奏'],
             channel='Johnny Harris',claim='剪辑节奏',cut_points=[1.25,2.5],metrics=[dict(label='平均镜长',value='1.25 秒')]),
        dict(id='capture',start=4,end=8,stage_mode='callout_rig',source='clip.mp4',
             anchor_cue_id='b',spoken_topic='看高亮区域',visual_subject='现场',semantic_binding='exact_tool_capture',
             semantic_tags=['现场'],overlays=[dict(kind='corner_tag',at=.15,label='录屏实测',sublabel='现场 A'),overlay]),
    ]
    cues = {'a':{'firstCharTime':0},'b':{'firstCharTime':4}}
    prepared,_ = assemble.prepare_shots({'shots':shots},tmp_path,cues)
    stage = assemble.build_act(prepared,tmp_path,tmp_path,'原片拆解',subprocess.run)
    row,tags = stage.shots
    assert row['stage_mode']=='reference_breakdown' and row['cut_count']==3 and row['beats']==[0.,1.25,2.5]
    assert row['channel']=='Johnny Harris' and row['claim']=='剪辑节奏' and row['metrics']==shots[0]['metrics']
    assert tags['overlays'][1]['target_verified'] is True
    assert 'left:80px;top:156px;width:1152px;height:648px' in stage.media_layers[0] and 'muted' in stage.media_layers[0]
    html = ''.join(stage.plates)
    assert all(word in html for word in ('画面引用 · Johnny Harris','镜头 #01','平均镜长','1.25 秒','#101b1b42','#172322eb'))
    assert 'drop-shadow' not in html and 'y="353.0"' in html
    assert "textContent:'镜头 #03',immediateRender:false},2.50000)" in ''.join(stage.scripts)
    assert dict(kind='pop',at=4.15,gain=.10) in stage.sound_events()
    assert dict(kind='tick',at=2.5,gain=.10) in stage.sound_events()
    assert spotlight_restraint_gate(stage.shots)['ok']
    props = dict(shots[0],stage_mode='fullbleed_rig',visual_subject='书和笔',semantic_tags=['书和笔'],semantic_binding='physical_prop')
    assert semantic_binding_gate([props])['ok']
    assert not semantic_binding_gate([dict(props,spoken_topic='Johnny 用 FFmpeg 展示书和笔')])['ok']
    if os.environ.get('YICE_TEST_REF_LAYOUT')=='1':
        assemble.install_asset(Path(os.environ['YICE_GSAP_PATH']),tmp_path/'vendor/gsap.min.js')
        wave(tmp_path/'assets/mix.wav',tone(8.,.1))
        stage.write_project(tmp_path,timeline_out=tmp_path/'shot-timeline.json')
        result = subprocess.run(['npx','--offline','hyperframes','check','.'],cwd=tmp_path,
                                text=True,capture_output=True)
        output = result.stdout+result.stderr
        print(output)
        assert result.returncode==0
        for section, following in (('Layout','Motion'),('Craft','Audio')):
            body = output.split(f'\n{section}\n',1)[1].split(f'\n{following}\n',1)[0]
            assert re.search(r'\b0 (?:issues|errors?)\b',body)
        counter = subprocess.run(['node','-e',"""
            const {chromium} = require(process.env.YICE_PLAYWRIGHT_MODULE);
            const {pathToFileURL} = require('node:url');
            (async () => {
                const browser = await chromium.launch({channel:'chrome'});
                try {
                    const page = await browser.newPage();
                    await page.goto(pathToFileURL(process.argv[1]).href);
                    const readings = await page.evaluate(() => {
                        const timeline = window.__timelines.main;
                        const counter = document.querySelector('.ref-cut-counter');
                        return [0, 2, 3, .5, 2.6].map(time => {
                            timeline.seek(time);
                            return counter.textContent;
                        });
                    });
                    process.stdout.write(JSON.stringify(readings));
                } finally {
                    await browser.close();
                }
            })().catch(error => { console.error(error); process.exitCode = 1; });
        """,str(tmp_path/'index.html')],check=True,capture_output=True,text=True)
        assert json.loads(counter.stdout)==['镜头 #01','镜头 #02','镜头 #03','镜头 #01','镜头 #03']
        print('Chrome 正向及逆向 seek 的镜头计数均正确')


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
                             '--pause','1=3.0','--crossfade-ms','80',
                             '--output',str(target)],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout)['crossfade_ms']==80
    assert json.loads(result.stdout)['room_tone_dbfs']==-68.
    data,rate = sf.read(target)
    assert len(data)/rate==pytest.approx(3.7,abs=.004)
    central = data[rate:3*rate]
    assert 20*np.log10(np.sqrt(np.mean(central**2)))==pytest.approx(-68.,abs=.15)
    assert breath_integrity_gate(tmp_path,{'voice_tracks':[{'path':target.name}]})['ok']


def test_concat_removes_dc_and_fades_across_the_protected_windows(tmp_path):
    quiet = tone(.25,.0012,400)
    one = wave(tmp_path/'tail.wav',np.r_[tone(.4),quiet] + .025)
    two = wave(tmp_path/'lead.wav',np.r_[quiet,tone(.4)] - .025)
    target = tmp_path/'seam.wav'
    voice._concat_wavs([one,two],target,pauses={1:.8})
    samples, rate = sf.read(target)
    assert len(samples)/rate == pytest.approx(1.6,abs=.002)
    assert abs(samples[:round(.35*rate)].mean()) < 1e-5
    assert abs(samples[-round(.35*rate):].mean()) < 1e-5

    def rms(start, end):
        return np.sqrt(np.mean(samples[round(start*rate):round(end*rate)]**2))

    assert rms(.41,.43) > 2*rms(.51,.53)
    assert rms(1.17,1.19) > 1.7*rms(1.09,1.11)
    voice._concat_wavs([two],target)
    assert sf.info(target).duration == pytest.approx(.625)


def test_decode_pocket_room_floor_and_stat_badge_plate(tmp_path):
    breath = tone(.1,.0038,400)
    source = wave(tmp_path/'raw.wav',np.r_[tone(.3),tone(.05,10**(-95/20),460),breath,tone(.3)])
    target = tmp_path/'chapter.wav'
    voice._concat_wavs([source],target)
    assert sf.info(target).frames==sf.info(source).frames
    assert breath_integrity_gate(tmp_path,{'voice_tracks':[{'path':target.name}]})['ok']
    audio,rate = sf.read(target)
    pocket = audio[round(.3*rate):round(.35*rate)]
    assert 20*np.log10(np.sqrt(np.mean(pocket**2)))==pytest.approx(-68.,abs=.25)
    audible = np.abs(breath) > 10**(-68/20)
    np.testing.assert_allclose(audio[round(.35*rate):round(.45*rate)][audible],breath[audible],atol=1e-6)

    stage = EditorialStage('读数',duration=3)
    stage.add_callout_rig(0,3,'terminal.mp4',overlays=[dict(kind='stat_badge',at=.5,label='响应',value=9)])
    assert 'fill="#172322fa"' in ''.join(stage.plates)
    assert 'stroke="#7aaba0"' in ''.join(stage.plates) and 'data-layout-allow-overlap' in ''.join(stage.plates)


def test_concat_rejects_periodically_silent_room_tone(tmp_path):
    poisoned = np.r_[tone(.015,10**(-60/20),400),tone(.045,10**(-95/20),400)]
    bridge = voice.room_tone(poisoned[:,None],RATE,3*RATE,dbfs=-68.)
    energy = np.r_[0.,np.cumsum(bridge[:,0]**2)]
    block = round(.01*RATE)
    rms_dbfs = 10*np.log10((energy[block:]-energy[:-block])/block)
    assert np.all(np.abs(rms_dbfs+68.)<=3.)

    voiced = np.resize([.12,-.12],round(.35*RATE))
    one = wave(tmp_path/'source-with-pocket.wav',np.r_[voiced,poisoned])
    two = wave(tmp_path/'source-clean.wav',voiced)
    target = tmp_path/'joined.wav'
    voice._concat_wavs([one,two],target,pauses={1:3.})
    assert sf.info(target).frames==round(3.7*RATE)
    gate = breath_integrity_gate(tmp_path,{'voice_tracks':[{'path':target.name}]})
    assert gate['ok'] and gate['violations']==[]


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


def test_studio_ui_reuses_callout_overlays(tmp_path):
    overlays = [
        {'kind':'strikethrough_list','at':.3,'label':'排疑','items':['第一项','第二项']},
        {'kind':'verdict_stamp','at':1.,'label':'通过'},
    ]
    shot = dict(id='studio',stage_mode='studio_ui',anchor_cue_id='a',start=0,end=3,
                studio_style='terminal_pipeline',data={'command':'pytest','lines':['passed']},
                overlays=overlays,spoken_topic='核验结果',visual_subject='终端结果',
                semantic_binding='conceptual_explainer',semantic_tags=['核验'])
    shots,_ = assemble.prepare_shots({'shots':[shot]},tmp_path,{'a':{'firstCharTime':0}})
    stage = assemble.build_act(shots,tmp_path,tmp_path,'Studio',subprocess.run)
    row, = stage.shots
    assert row['stage_mode']=='studio_ui' and row['has_motion_overlay']
    assert row['overlays']==overlays
    assert ('marker',.3) in stage.sound_marks and ('stamp',1.) in stage.sound_marks
    assert 'strike-0' in ''.join(stage.plates) and '通过' in ''.join(stage.plates)
    assert first_half_motion_density_gate([row],3)['motion_shots_by_half']==[1,0]


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='需要本地 ffmpeg')
def test_nle_strikethrough_replaces_bin_without_invading_monitor(tmp_path):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=#475853:s=320x180:r=30:d=4.5',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(tmp_path/'monitor.mp4')],check=True)
    shot = dict(id='studio',stage_mode='studio_ui',anchor_cue_id='a',start=0,end=4,
                studio_style='nle_timeline',data={'monitor':'monitor.mp4','media':['早期样片','升级成片'],
                'tracks':[[(0,.45)],[(.45,1)],[]],'voice':[.2,.6,.3],'bed':[.1,.2,.2]},
                overlays=[{'kind':'strikethrough_list','at':.8,'duration':2.,'label':'先排疑',
                           'items':['核对素材','复查画面','对齐旁白','确认节奏']}],
                spoken_topic='核验镜头',visual_subject='剪辑工作台和排疑卡',
                semantic_binding='conceptual_explainer',semantic_tags=['核验'])
    shots,_ = assemble.prepare_shots({'shots':[shot]},tmp_path,{'a':{'firstCharTime':0}})
    stage = assemble.build_act(shots,tmp_path,tmp_path,'Studio',subprocess.run)
    body = ''.join(stage.plates)
    rect = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="#172322f5"',body)
    assert rect is not None
    x,y,w,h = map(float,rect.groups())
    assert x+w<830 and y+h<547
    assert '<g class="nle-bin">' in body and 'data-layout-allow-overlap' in body
    assert 'data-layout-ignore>节目监视器' in body
    scripts = '\n'.join(stage.scripts)
    assert "tl.set('#s0 .nle-bin',{autoAlpha:0,display:'none'},0.80000);" in scripts
    assert "tl.set('#s0 .nle-bin',{autoAlpha:1,display:'inline'},2.80000);" in scripts
    if os.environ.get('YICE_TEST_NLE_LAYOUT')=='1':
        assemble.install_asset(Path(os.environ['YICE_GSAP_PATH']),tmp_path/'vendor/gsap.min.js')
        wave(tmp_path/'assets/mix.wav',tone(4.,.1))
        stage.write_project(tmp_path)
        result = subprocess.run(['npx','--offline','hyperframes','check','.'],cwd=tmp_path,
                                text=True,capture_output=True)
        output = result.stdout+result.stderr
        print(output)
        assert result.returncode==0 and re.search(r'(?m)^Layout[ \t]*\n[^\n]*\b0 (?:issues|errors?)\b',output)


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='需要本地 ffmpeg')
def test_triptych_cards_reveal_and_check_video_tail(tmp_path):
    from PIL import Image

    Image.new('RGB',(64,64),'white').save(tmp_path/'still.png')
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=64x64:r=30:d=2',
                    '-an','-c:v','libx264',str(tmp_path/'clip.mp4')],check=True)
    shot = dict(id='cards',stage_mode='triptych_cards',anchor_cue_id='b',start=0,end=2,
                heading='对照片段',spoken_topic='对照',visual_subject='截图与录屏',
                semantic_binding='conceptual_explainer',semantic_tags=['对照'],
                cards=[{'label':'截图','source':'still.png','reveal_at':0},
                       {'label':'录屏','sublabel':'关键操作','source':'clip.mp4','reveal_at':.8,'media_start':.3}])
    cues = {'b':{'id':'b','firstCharTime':0}}
    shots,_ = assemble.prepare_shots({'shots':[shot]},tmp_path,cues)
    stage = assemble.build_act(shots,tmp_path,tmp_path,'Cards',subprocess.run)
    row, = stage.shots
    assert row['beats']==[0.,.8] and stage.sound_marks==[('pop',0.),('pop',.8)]
    html = ''.join(stage.media_layers)
    assert '<img' in html and 'data-start="0.80000" data-duration="1.20000" data-media-start="0.300"' in html
    assert ' loop' not in html and '关键操作' in ''.join(stage.plates)
    assert first_half_motion_density_gate([row],2)['motion_shots_by_half']==[1,0]
    timeline = {'shots':[row],'cues':list(cues.values())}
    assert not timeline_gates(timeline,tmp_path,2)['invalid_triptych_media']
    row['cards'][1]['media_start'] = .8
    assert timeline_gates(timeline,tmp_path,2)['invalid_triptych_media']==['cards']
    shot['cards'][1]['media_start'] = .8
    with pytest.raises(ValueError,match='余量'):
        assemble.prepare_shots({'shots':[shot]},tmp_path,cues)

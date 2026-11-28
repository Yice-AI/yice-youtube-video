from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT/'scripts')]
from kit.spatial.block import build
from audit_spatial import composition_motion, three_mode_symphony_gate, subpage_repeats
import audit_spatial
from audit_v7 import dual_engine_craft_gate


@pytest.fixture
def materials(tmp_path):
    paths = []
    for i in range(5):
        name=f'material-{i}.png'
        Image.new('RGB',(60,32),(i*40,20,70)).save(tmp_path/name)
        paths.append(name)
    gsap=tmp_path/'gsap.js'
    gsap.write_text('// test runtime')
    return paths, gsap


@pytest.mark.parametrize('recipe,data,expected',[
    ('carousel_3d_select',dict(selected_index=2,select_at=2), 'M1'),
    ('layer_explode_3d',dict(boxes=[[.1,.2,.3,.4]],vector_shapes=[[.12,.22,.60,.045]],count=24), 'M1'),
    ('roadmap_thread_camera',dict(steps=[dict(no=i,title='步骤',sub='说明',at=.7*i) for i in range(3)],focus_step=0), 'M3'),
    ('literal_action_stage',dict(action='bad_slides_pileup',labels=['甲','乙','丙'],warning='重复'), 'M3'),
    ('literal_action_stage',dict(action='dead_image_locked',warning='无法修改'), 'M3'),
    ('literal_action_stage',dict(action='slot_lock_fill',labels=['甲','乙','丙']), 'M3'),
    ('literal_action_stage',dict(action='folder_pack_outro',folder='技能',command='install'), 'M3'),
])
def test_portable_recipes(tmp_path,materials,recipe,data,expected):
    paths,gsap=materials
    spec=dict(id='demo',duration=5,recipe=recipe,data=dict(data,images=paths,image=paths[0]))
    p=build(spec,tmp_path,tmp_path/'outputs'/'demo',gsap)
    assert composition_motion(p.read_text())[1] == expected
    if recipe=='layer_explode_3d':
        assert '<rect x="120.00" y="123.75" width="600.00"' in p.read_text()
        spec['data']['count_at'] = 3.25
        timed = build(spec, tmp_path, tmp_path/'timed', gsap).read_text()
        assert '"count_at": 3.25' in timed
        spec['data']['count_at'] = 4.95
        with pytest.raises(ValueError, match='count_at'):
            build(spec, tmp_path, tmp_path/'late', gsap)

    assert (p.parent/'vendor/gsap.min.js').is_file()
    assert 'paused:true' in p.read_text() and str(tmp_path) not in p.read_text()
    assert dual_engine_craft_gate([dict(id='demo',stage_mode='hyperframes_block',composition=p)],tmp_path,v10=True)['ok']


def test_shot_labels_and_static_depth_cannot_certify_spatial_motion():
    flat = '<style>.grid{transform-style:preserve-3d;transform:translateZ(20px)}</style><script>tl.to(cards,{opacity:1,stagger:.2})</script>'
    assert composition_motion(flat,'M1')==(False,None)
    unused_camera=flat.replace('tl.to(cards', "const cam={z:0,rx:0};function draw(){return 'rotateX('+cam.rx+')'};tl.to(cards")
    assert composition_motion(unused_camera,'M1')==(False,None)
    shots=[dict(id=k,start=a,end=b,stage_mode=m) for k,a,b,m in [
        ('a',0,2,'hyperframes_block'),('b',2,7,'fullbleed_rig'),('c',7,10,'explainer_clip')]]
    t=dict(episode_kind='tool_tutorial',shots=shots)
    assert not three_mode_symphony_gate(t,10)['ok']
    assert three_mode_symphony_gate(t,10,{'a':'M1'})['ratios']==dict(M1=.2,M2=.5,M3=.3)


def test_slide_repeated_in_different_wrappers(monkeypatch,tmp_path):
    texture=Image.fromarray(np.random.default_rng(7).integers(0,255,(100,180,3),dtype=np.uint8))
    shots=[];images={}
    for i,(x,y) in enumerate([(12,8),(44,30),(30,20)]):
        frame=Image.new('RGB',(260,160),(32*i,10,80));frame.paste(texture,(x,y))
        key=str(i);images[key]=frame
        shots.append(dict(id=key,start=i,end=i+1,stage_mode='fullbleed_rig',page_region=[x/260,y/160,(x+180)/260,(y+100)/160]))
    monkeypatch.setattr(audit_spatial,'capture_frame',lambda s,*args:images[s['id']])
    assert subpage_repeats(shots,tmp_path,None)==[{'reason':'repeated_slide_page','shots':['0','1','2']}]
    assert subpage_repeats(shots[:2],tmp_path,None)==[]


def test_seek_sampling_distinguishes_camera_motion_from_static_art(tmp_path, materials):
    import os
    from workspace import resolve_gsap_runtime

    if not os.environ.get('YICE_PLAYWRIGHT_MODULE') or not os.environ.get('YICE_CHROME_EXECUTABLE'):
        pytest.skip('需要本机 Playwright 与无头 Chromium')
    runtime = resolve_gsap_runtime()
    pictures,_ = materials
    entry = build(dict(id='orbit',recipe='carousel_3d_select',duration=5,
                       data=dict(images=pictures,selected_index=2,select_at=2)),
                  tmp_path,tmp_path/'orbit',runtime)
    measured = audit_spatial.sample_choreography(entry)
    assert measured['ok'] and len(measured['timelines'][0]['changes']) == 5
    static = tmp_path/'still.html'
    static.write_text('<script src="orbit/vendor/gsap.min.js"></script><div id="still"><b>静止</b></div>'
                      '<script>window.__timelines={still:gsap.timeline({paused:true}).to({},{duration:5})}</script>')
    frozen = audit_spatial.sample_choreography(static)
    assert not frozen['ok'] and len(frozen['timelines'][0]['deadZones']) == 5


def test_dual_engine_counts_time_and_measured_palette():
    modes = ['hyperframes_block']*2 + ['onetake_clip']*3
    shots = [dict(id=str(i),stage_mode=mode,start=i,end=i+1) for i,mode in enumerate(modes)]
    measured = {s['id']:dict(frames=[dict(phase=.88,overlaps=[],exploded=False,
                samples={'background':dict(n=200,luma=20,chroma=10),'highlights':{str(int(s['id'])%2):100}})]) for s in shots}
    gate = audit_spatial.spatial_frame_gates
    assert gate(shots,10,measured,True)['dual_engine_symphony_gate']['ok']
    assert not gate(shots,30,measured,True)['dual_engine_symphony_gate']['ok']
    assert not gate(shots[:-1],10,measured,True)['dual_engine_symphony_gate']['ok']
    name='unified_cyber_stage_and_accent_gate'
    assert gate(shots,10,measured,True)[name]['ok']
    for sample in measured.values():
        sample['frames'][0]['samples']['highlights']={'2':100}
    assert not gate(shots,10,measured,True)[name]['ok']
    measured['0']['frames'][0]['samples']['background']['luma']=43
    measured['0']['frames'][0]['titles']=[[74,60,400,96]]
    gates=gate(shots,10,measured,True)
    assert any(v['reason']=='bright_stage_background' for v in gates[name]['violations'])
    assert gates['no_ppt_slide_header_gate']['violations'][0]['reason']=='ppt_slide_header_detected'


def test_seeked_pixels_and_visible_title_bounds(tmp_path):
    import os
    if not os.environ.get('YICE_PLAYWRIGHT_MODULE') or not os.environ.get('YICE_CHROME_EXECUTABLE'):
        pytest.skip('需要本机 Playwright 与无头 Chromium')
    entry = tmp_path/'frame.html'
    shot = dict(id='scene',stage_mode='hyperframes_block',composition=entry.name,start=0,end=5)
    fixture = """<style>*{margin:0}body{background:#181818}.plate{position:absolute;top:180px;width:250px;
        height:180px;background:COLOR}header{position:absolute;left:200px;top:TOPpx;width:100px;height:60px}</style>
        <section data-spatial-recipe="layer_explode_3d"><header data-spatial-title>标题</header>
        <div data-spatial-subject data-spatial-layer="base" class="plate" style="left:150px"></div>
        <div data-spatial-layer="skeleton" class="plate" style="left:450px"></div>
        <div data-spatial-layer="letters" class="plate" style="left:750px"></div></section>
        <script>window.__meta={dur:5};window.__seek=()=>{};</script>"""
    for color,top,ok in [('#242424','210',False),('#39cfef','65',True)]:
        markup = fixture.replace('COLOR',color).replace('TOP',top)
        entry.write_text('<!doctype html><template>'+markup+'</template>' if ok else markup)
        measured=audit_spatial.spatial_measurements([shot],tmp_path)
        gates=audit_spatial.spatial_frame_gates([shot],5,measured,False)
        assert gates['title_card_collision']['ok'] is ok
        assert gates['low_layer_contrast']['ok'] is ok
        assert gates['low_layer_contrast']['plates']['scene']['letters']['n']>0


@pytest.mark.parametrize(('recipe','data','marker'), [
    ('duplicate_laser_sweep',dict(cards=['一','二','三'],series='测试',caption='<caption>'),'OM.spring'),
    ('bitmap_lock_glitch',dict(image='material-0.png'),'OM.shake'),
    ('energy_roadmap_dive',dict(stations=[dict(image=f'material-{i}.png',label='站') for i in range(4)],target=3),'data-overview-station'),
    ('live_control_sync',dict(image='material-1.png',slider='强度',switch='锁定',canvas='预览'),'OM.cursor'),
    ('capsule_archive_seal',dict(images=['material-0.png','material-1.png'],project='档案',command='open <bundle>'),'OM.gather'),
])
def test_declarative_onetake_recipes_copy_real_inputs(tmp_path,materials,recipe,data,marker):
    from kit.onetake.scene import build as compile_scene
    output=tmp_path/'compiled'
    entry=compile_scene(dict(recipe=recipe,duration=5,hud='测试 <HUD>',data=data), tmp_path, output)
    html=entry.read_text()
    assert marker in html and 'OM.camera(' in html and 'window.__seek' in html
    assert '测试 &lt;HUD&gt;' in html and '@@' not in html
    if recipe=='energy_roadmap_dive':
        assert len(list(output.glob('*.png')))==4 and html.count('data-overview-station')==4
    if recipe=='capsule_archive_seal':
        assert 'open &lt;bundle&gt;' in html and '#E6F4FF' in html


def test_roadmap_gate_checks_unclipped_projected_bounds():
    shot=dict(id='r',stage_mode='onetake_clip',start=0,end=5)
    frame=dict(phase=.5,overlaps=[],stations=[[129,500],[1400,1791]])
    gate=audit_spatial.spatial_frame_gates([shot],5,{'r':dict(frames=[frame])},False)['roadmap_overview_safe_gate']
    assert not gate['ok'] and len(gate['violations'])==2


def test_progressive_cards_strip_raw_source_and_portrait_uses_contain(tmp_path):
    from PIL import Image
    from kit.spatial.block import build
    from audit_v7 import composition_material
    portrait = tmp_path / 'sub' / 'card-vertical.png'
    portrait.parent.mkdir()
    Image.new('RGB', (600, 800), (245, 245, 248)).save(portrait)
    gsap = tmp_path / 'gsap.min.js'
    gsap.write_text('// stub')
    out = tmp_path / 'comp'
    entry = build({
        'id': 'sim1',
        'recipe': 'progressive_sim_cards',
        'stage_look': 'cyber_glass',
        'duration': 4.5,
        'data': {
            'heading': '分层验证',
            'cards': [
                {'at': 0.2, 'kind': 'race_bars', 'label': '对比'},
                {'at': 0.8, 'source': 'sub/card-vertical.png', 'label': '竖卡'},
            ],
        },
    }, tmp_path, out, gsap)
    html = entry.read_text()
    assert 'sub/card-vertical.png' not in html
    assert 'media-aspect-box' in html
    _, images = composition_material(entry)
    assert images and all(p.is_file() for p in images)


def test_capture_stage_backgrounds_skips_fullbleed_and_samples_uncropped_window(tmp_path, monkeypatch):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (320, 180), (14, 18, 28))
    draw = ImageDraw.Draw(img)
    draw.rectangle((24, 24, 296, 144), fill=(240, 245, 255))
    monkeypatch.setattr(audit_spatial, '_raw_stage_frame', lambda *a, **kw: img)
    shots = [
        {'id': 'fb_bright', 'stage_mode': 'fullbleed_rig', 'framing': 'fullbleed', 'start': 0, 'end': 3},
        {'id': 'p3d_dark_stage', 'stage_mode': 'callout_rig', 'framing': 'perspective_3d', 'start': 3, 'end': 6},
    ]
    gate = {'backgrounds': {}, 'violations': [], 'ok': True}
    audit_spatial.capture_stage_backgrounds(shots, tmp_path, tmp_path / 'ep.mp4', gate)
    assert gate['ok'] and not gate['violations']
    assert 'fb_bright' not in gate['backgrounds'] and 'p3d_dark_stage' in gate['backgrounds']


def test_v13_widescreen_fan_adaptive_stamp_and_bundled_audio(tmp_path):
    from PIL import Image
    import numpy as np
    import soundfile as sf
    from kit.spatial.block import build
    from kit.editorial.editorial import EditorialStage, stamp
    from kit.editorial.audio_mix import EpisodeAudioMixer, resolve_bgm_path
    import importlib
    assemble_mod = importlib.import_module('assemble-episode')

    # 1. Stamp auto-widens for 9-char labels and stays inside 1920 safe zone
    long_svg = stamp(1400, 520, '光斑底图×独立字层')
    assert 'width="' in long_svg and 'translate(' in long_svg
    # 2. Fullbleed breathing without focus never zooms 1.27x
    st = EditorialStage('t', duration=6.0)
    st.add_callout_rig(0, 5, 'cli-04-render.mp4', overlays=[
        {'kind': 'corner_tag', 'at': 0.2, 'label': '04 · HyperFrames', 'sublabel': 'cli'},
        {'kind': 'hero_punch', 'at': 2.0, 'label': '全程零订阅费', 'sublabel': 'GitHub 免费开源'},
    ], motion='focus_push')
    joined = '\n'.join(st.scripts)
    assert '1.270' not in joined and 'punch-slam' in joined
    assert 'x="1' in '\n'.join(st.plates)  # CLI corner_tag auto-placed on top_right

    # 3. Widescreen fan default + 3-item bento strips raw logo paths & emits auto SFX
    pic = tmp_path / 'slide.png'
    Image.new('RGB', (1280, 720), (20, 40, 90)).save(pic)
    gsap = tmp_path / 'gsap.min.js'
    gsap.write_text('// stub')
    fan_html = build({
        'id': 'fan13', 'recipe': 'perspective_video_fan', 'duration': 6.0,
        'data': {
            'items': [{'source': 'slide.png', 'label': 'A'}, {'source': 'slide.png', 'label': 'B'}, {'source': 'slide.png', 'label': 'C'}],
            'punch_text': '零订阅费', 'punch_at': 4.2,
        }
    }, tmp_path, tmp_path / 'fan', gsap).read_text()
    assert '<div class="fan-stage">' in fan_html and 'fan-editorial-punch' in fan_html

    from audit_v7 import legacy_pink_outline
    assert not legacy_pink_outline(fan_html)
    assert '<i>✦</i>' not in fan_html

    bento_html = build({
        'id': 'bento13', 'recipe': 'logo_bento_stage', 'duration': 6.0,
        'data': {
            'brand': {'name': 'GitHub', 'tag': '5 Tools'},
            'modules': [
                {'category': '演示', 'at': 0.2, 'items': [{'name': 'A', 'logo': 'slide.png', 'at': 0.3}, {'name': 'B', 'at': 0.6}, {'name': 'C', 'at': 0.9}]},
                {'category': '视频', 'at': 1.2, 'items': [{'name': 'D', 'at': 1.4}]},
            ],
        }
    }, tmp_path, tmp_path / 'bento', gsap).read_text()
    assert 'data-item-count="3"' in bento_html and '"slide.png"' not in bento_html

    marks = assemble_mod._spatial_sound_marks({'recipe': 'logo_bento_stage', 'data': {'modules': [{'at': 0.2, 'items': [{'at': 0.5}, {'at': 0.9}]}]}}, 5.0)
    assert len(marks) >= 3

    # 4. Builtin groove BGM & bundled studio SFX mix cleanly
    bgm_file = resolve_bgm_path('builtin:city-groove')
    assert bgm_file.is_file()
    vpath = tmp_path / 'v.wav'
    t = np.linspace(0, 3.0, 24000 * 3, endpoint=False)
    sf.write(vpath, (0.18 * np.sin(2 * np.pi * 220 * t)).astype('float32'), 24000)
    res = EpisodeAudioMixer(sample_rate=24000).mix(
        3.0, [{'path': vpath}], tmp_path / 'mixout',
        bgm=[bgm_file],
        sound_marks=[{'kind': 'pop', 'at': 0.2}, {'kind': 'click', 'at': 0.6}, {'kind': 'impact', 'at': 1.4}],
    )
    assert len(res['sound_marks']) == 3 and abs(res['measured_lufs'] + 14.5) <= 0.8


def test_editorial_cinema_recipes_and_local_media(tmp_path, materials):
    from audit_v7 import case_monotony_gate, semantic_match_ledger
    pictures, gsap = materials
    clip = tmp_path/'example.mp4'
    clip.write_bytes(b'video element fixture')
    sample = dict(id='scene', duration=1.4, recipe='kinetic_title_bridge',
                  data=dict(words=[dict(text='按交付选', at=.1)], underline_at=.3))
    bridge = build(sample,tmp_path,tmp_path/'bridge',gsap).read_text()
    assert 'data-stage-look="swiss_paper"' in bridge and 'strokeDashoffset' in bridge
    sample.update(recipe='triptych_curtain',data=dict(videos=[clip.name]*3,words=[dict(text='成品',at=0)]))
    curtain = build(sample,tmp_path,tmp_path/'curtain',gsap).read_text()
    assert curtain.count('<video id=') == 3 and 'data-stage-look="cinema_black"' in curtain
    sample['data']['videos'][1] = pictures[0]
    with pytest.raises(ValueError,match='动态视频'):
        build(sample,tmp_path,tmp_path/'invalid',gsap)

    shots = [dict(id=str(i), start=i, end=i+1, anchor_cue_id=str(i), case_tag=str(i),
                  visual_subject='双击修改数字', spoken_topic='数字能改') for i in range(4)]
    rows = [dict(shot_id=s['id'],start=s['start'],end=s['end'],case_tag=s['case_tag'],
                 quote=s['spoken_topic'],evidence=s['visual_subject']) for s in shots]
    timeline = dict(shots=shots, cues=[dict(id=s['id'], text=s['spoken_topic']) for s in shots],
                    semantic_alignment=rows)
    assert case_monotony_gate(shots,4)['ok'] and semantic_match_ledger(timeline)['ok']
    shots[1]['case_tag'] = '0'
    assert not case_monotony_gate(shots,4)['ok'] and not semantic_match_ledger(timeline)['ok']
    shots[1]['case_tag'] = '1'
    timeline['cues'][0]['text'] = '点击后整张图片移动'
    assert semantic_match_ledger(timeline)['invalid'] == ['0']


def test_multi_case_wall_counts_visible_time_once_per_case():
    from audit_v7 import case_monotony_gate
    wall = dict(id='wall', start=0, end=3, case_tag='对照',
                case_windows=[dict(tag='甲',start=0,end=3),dict(tag='甲',start=1,end=2),
                              dict(tag='乙',start=1,end=3)])
    gate = case_monotony_gate([wall],10)
    assert gate['ok'] and gate['shares']=={'甲':.3,'乙':.2}
    wall['case_windows'][0]['start']=.8
    assert case_monotony_gate([wall],10)['missing']==['wall']

def test_curtains_use_distinct_sources_in_each_85_second_window(tmp_path):
    from importlib import import_module
    from audit_v7 import case_monotony_gate
    fingerprint = import_module('assemble-episode').file_fingerprint
    def wall(at, names):
        hashes = []
        for index, name in enumerate(names):
            path = tmp_path / f'{at}-{index}.mp4'
            path.write_bytes(name.encode())
            hashes.append(fingerprint(path)['sha256'])
        return dict(id=str(at), start=at, end=at+2, case_tag=str(at), curtain_source_hashes=hashes)
    a, b, c = wall(0, 'abc'), wall(14, 'def'), wall(50, 'ghi')
    assert case_monotony_gate([a, b], 85)['ok']
    assert not case_monotony_gate([a, wall(14, 'cde')], 85)['ok']
    assert not case_monotony_gate([a, b, c], 85)['ok']
    assert case_monotony_gate([a, b, wall(85, 'abc')], 90)['ok']


def test_director_two_lines_and_bento_count(tmp_path, materials):
    from kit.spatial.block import build
    from kit.editorial.editorial import EditorialStage
    _, gsap = materials
    video = tmp_path/'wall.mp4'
    video.write_bytes(b'fixture')
    spec = dict(id='intro', duration=3, recipe='triptych_curtain',
                data=dict(videos=[video.name]*3, words=[dict(text='第一行',at=0,line=1),
                                                        dict(text='第二行',at=.2,line=2)]))
    page = build(spec,tmp_path,tmp_path/'intro',gsap).read_text()
    assert '第一行</span><br><span class="display-word">第二行' in page
    spec.update(recipe='progressive_sim_cards',data=dict(board=True,cards=[
        dict(source=video.name,label=str(i),at=i*.4) for i in range(3)]))
    page = build(spec,tmp_path,tmp_path/'board',gsap).read_text()
    assert 'class="sim-row board"' in page and '"board": true' in page
    stage = EditorialStage('intro',duration=3)
    stage.add_callout_rig(0,3,video.name,overlays=[dict(kind='editorial_punch',at=.1,lines=['全程 0 元','订阅费'])])
    plate = ''.join(stage.plates)
    assert '全程 0 元' in plate and '订阅费' in plate and 'radialGradient' in plate
    spec.update(recipe='logo_bento_stage', data=dict(expected_items=5, modules=[
        dict(category='文件',items=['A']),dict(category='投屏',items=['B','C']),dict(category='短片',items=['D','E'])]))
    assert build(spec,tmp_path,tmp_path/'five',gsap).is_file()
    spec['data']['modules'][-1]['items'].pop()
    with pytest.raises(ValueError,match='工具总数'):
        build(spec,tmp_path,tmp_path/'four',gsap)


def test_physical_marks_and_marker_bed_duck(tmp_path):
    import numpy as np
    import soundfile as sf
    from kit.editorial.audio_mix import EpisodeAudioMixer
    rate = 24000
    t = np.arange(rate*3)/rate
    tone = tmp_path/'tone.wav'
    sf.write(tone,.17*np.sin(2*np.pi*300*t),rate)
    mixer = EpisodeAudioMixer(sample_rate=rate)
    kwargs = dict(duration=3,voice_tracks=[dict(path=tone)],bgm=[tone])
    mixer.mix(output=tmp_path/'plain',**kwargs)
    names = ['marker_stroke','card_thock','shutter_whip','counter_roll']
    result = mixer.mix(output=tmp_path/'marks',sound_marks=[
        dict(kind=k,at=.5+i*.5,gain=.30) for i,k in enumerate(names)],**kwargs)
    before,_ = sf.read(tmp_path/'plain/bed-only.wav')
    after,_ = sf.read(tmp_path/'marks/bed-only.wav')
    interval = slice(int(.52*rate),int(.64*rate))
    assert 20*np.log10(np.linalg.norm(after[interval])/np.linalg.norm(before[interval])) == pytest.approx(-4,abs=.02)
    assert np.array_equal(before[rate:],after[rate:])
    assert all(mark['gain'] == .30 for mark in result['sound_marks'])

def test_v14_sound_bank_resolves_27_files_and_aligns_audible_onset(tmp_path):
    from kit.editorial.audio_mix import ASSETS_DIR, BUNDLED_SFX_MAP, EpisodeAudioMixer, _action_excerpt
    import numpy as np
    import soundfile as sf
    files = {p.name for p in (ASSETS_DIR/'sfx').iterdir() if p.suffix in {'.mp3','.wav'}}
    assert len(files)==27 and set(BUNDLED_SFX_MAP.values())==files
    x = np.r_[np.zeros(1000),np.ones(300),np.zeros(700)]
    clip, offset = _action_excerpt(x,1000,'typing')
    assert .98 <= offset <= 1 and len(clip)==210 and np.argmax(clip>.12)<25
    rate=24000
    voice=tmp_path/'voice.wav'
    sf.write(voice,.15*np.sin(2*np.pi*220*np.arange(rate*5)/rate),rate)
    events=['punch_hit','punch_hit','wipe_sweep','wipe_sweep','wipe_sweep','card_thock','card_thock','card_thock']
    report=EpisodeAudioMixer(sample_rate=rate).mix(5,[dict(path=voice)],tmp_path/'mix',
            sound_marks=[dict(at=.3+i*.45,kind=k,gain=.30) for i,k in enumerate(events)])
    marks=report['sound_marks']
    assert [m['kind'] for m in marks[:5]]==['impact_bass_1','impact_bass_2','whoosh_cinematic','whoosh_short','whoosh']
    assert [m['playback_rate'] for m in marks[-3:]]==[.95,1.,1.06]
    assert all(len(m['source_sha256'])==64 for m in marks)


def test_v14_gate_rejects_unsynced_duplicate_and_mismatched_sounds():
    from audit_v7 import sfx_diversity_and_sync_gate
    events = ['error','click','typing','keypress','ping','chime','sparkle','whoosh']
    shot = dict(id='s',start=0.,end=35.,beats=list(range(8)))
    marks=[dict(kind=k,at=i,gain=.6 if k=='whoosh' else .32) for i,k in enumerate(events)]
    t=dict(shots=[shot],sound_marks=marks)
    assert sfx_diversity_and_sync_gate(t,8)['ok']
    marks[0]['at']=.14
    assert not sfx_diversity_and_sync_gate(t,8)['ok']
    marks[0]['at']=0
    for i in range(3):
        marks[i].update(source_file=f'alias{i}',source_sha256='samebytes')
    reasons={r['reason'] for r in sfx_diversity_and_sync_gate(t,35)['violations']}
    assert {'identical_three_in_a_row','single_file_above_28_percent'} <= reasons
    marks[1]['playback_rate']=1.06
    assert 'identical_three_in_a_row' not in {r['reason'] for r in sfx_diversity_and_sync_gate(t,35)['violations']}
    assert not sfx_diversity_and_sync_gate(dict(shots=[shot],sound_marks=marks[:2]),35)['ok']
    assert not sfx_diversity_and_sync_gate(dict(shots=[shot],sound_marks=[dict(kind='shutter_whip',at=0)]),5)['ok']


def test_automatic_foley_follows_visible_page_and_layer_changes():
    import importlib.util
    f=Path(__file__).parents[1]/'scripts/assemble-episode.py'
    spec=importlib.util.spec_from_file_location('v14_auto_assemble',f)
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    card=dict(source='primary.mp4',at=.1,pages=[dict(source='second.mp4',at=1.23)])
    marks=engine._spatial_sound_marks(dict(recipe='progressive_sim_cards',stage_look='swiss_paper',
                                           data=dict(cards=[card])),4)
    assert ('page_flip',1.23,.34) in marks
    names=[s[0] for s in engine._spatial_sound_marks(dict(recipe='layer_explode_3d',data=dict(count_at=.8)),4)]
    assert names==['zoom_swoosh','counter_roll','ping']


def test_foley_density_silence_and_gain_tiers():
    from audit_v7 import sfx_diversity_and_sync_gate
    sounds = ['page_flip','ui_lock_bonk','paper_slap','zoom_swoosh','click','typing']
    beats = list(range(30))
    shot = dict(id='s',start=0,end=30,beats=beats)
    marks = [dict(kind=sounds[i%6],at=i,gain=.63 if i%6==3 else .34) for i in beats]
    def check(rows):
        return sfx_diversity_and_sync_gate(dict(shots=[shot],sound_marks=rows),30)
    assert check(marks)['ok']
    for subset in (marks[4:], marks[:-4], marks[:5]+marks[9:]):
        assert 'long_sfx_gap' in {v['reason'] for v in check(subset)['violations']}
    edge = [dict(m,at=m['at']+.011) if i==4 else m for i,m in enumerate(marks) if i not in (1,2,3)]
    edge[0]=dict(edge[0],at=.40)
    assert check(edge)['max_sfx_gap']==pytest.approx(3.611)
    assert 'long_sfx_gap' in {v['reason'] for v in check(edge)['violations']}
    doubled = [dict(m) for m in marks[:15] for _ in range(2)]
    gate=check(doubled)
    assert gate['audible_action_points']==15
    assert 'sfx_density_below_minimum' in {v['reason'] for v in gate['violations']}
    gate=check([dict(marks[0],gain=.10),*marks[1:]])
    assert gate['audible_action_points']==29
    assert 'inaudible_sfx_padding' in {v['reason'] for v in gate['violations']}
    gate=check([dict(marks[0],gain=.7),*marks[1:3],dict(marks[3],gain=.4),*marks[4:]])
    assert sum(v['reason']=='sfx_gain_tier' for v in gate['violations'])==2


def test_v14_visual_gates_use_visible_items_command_frames_and_text_bounds():
    from audit_v7 import enumerated_count_gate,no_early_cli_gate,subtitle_safe_zone_gate
    s=dict(id='s', start=0,end=58,recipe='logo_bento_stage',spoken_topic='这五个神器',custom_layout=True)
    t=dict(episode_kind='tool_tutorial',shots=[s],captions=[dict(text='这一句是字幕',start=0,end=5)])
    f=dict(enumeratedItems=['A','B','C','D','E'])
    measured={'s':dict(frames=[f])}
    assert enumerated_count_gate([s],measured)['ok']
    assert not enumerated_count_gate([dict(s,expected_items=4)],measured)['ok']
    board=dict(id='board',recipe='progressive_sim_cards')
    measured_board={'board':dict(frames=[dict(countClaim='代码排版的三大\n降维打击',enumeratedItems=['甲','乙'])])}
    assert not enumerated_count_gate([board],measured_board)['ok']
    f['enumeratedItems'][-1]='A'
    assert not enumerated_count_gate([s],measured)['ok']
    for at,expect in [(54.99,False),(55.0,True)]:
        assert no_early_cli_gate(t,[(at,[dict(text='$ npm install foo')])])['ok']==expect
    assert not no_early_cli_gate(dict(t,shots=[dict(s,source_names=['cli-04.mp4'])]),[])['ok']
    caption=dict(text='这一句是字幕',box=[100,930,420,55])
    assert subtitle_safe_zone_gate(t,{},[(2,[caption])])['ok']
    assert not subtitle_safe_zone_gate(t,{},[(2,[dict(text='核心参数',box=[200,830,310,42])])])['ok']
    s['presenter_shortcuts'] = dict(text='翻页 · ESC 索引',box=[1610,1034,262,20])
    hint = dict(text='ESC 索引',box=[1782,1035,82,16])
    assert subtitle_safe_zone_gate(t,{},[(2,[hint])])['ok']
    assert not subtitle_safe_zone_gate(t,{},[(2,[dict(hint,box=[1600,1000,82,30])])])['ok']
    f['unsafeCoreText']=['底部参数'];f['phase']=.5
    assert not subtitle_safe_zone_gate(t,measured,[])['ok']


def test_v14_voice_gate_catches_cut_off_chapter_and_truncated_source(tmp_path):
    import hashlib
    import numpy as np
    import soundfile as sf
    from audit_v7 import chapter_voice_completeness_gate
    voice=tmp_path/'track.wav';sf.write(voice,np.ones(2000)*.1,1000)
    t=dict(shots=[dict(start=0.,end=2.)],voice_tracks=[dict(id='01',path='track.wav',at=0.)],
           captions=[dict(end=1.97)],chapter_reference=[dict(id='01',duration=2.,
           sha256=hashlib.sha256(voice.read_bytes()).hexdigest())])
    assert chapter_voice_completeness_gate(t,tmp_path,2)['ok']
    assert not chapter_voice_completeness_gate(t,tmp_path,1.5)['ok']
    early=dict(t,shots=[dict(start=0.,end=1.5,chapter='01'),dict(start=1.5,end=3.,chapter='02')])
    assert not chapter_voice_completeness_gate(early,tmp_path,3)['ok']
    sf.write(voice,np.ones(1500)*.1,1000)
    assert not chapter_voice_completeness_gate(t,tmp_path,2)['ok']

def test_dark_stage_outlines_and_fullbleed_source_titles():
    from audit_v7 import corner_title_violation, legacy_pink_outline
    for color in ('#ec4899', '#F43F5E88', 'rgba(244, 63, 94, .35)', '#ff5497cc'):
        assert legacy_pink_outline(f'.badge {{box-shadow:0 0 14px {color}}}')
    assert not legacy_pink_outline('.badge {border:1px solid rgba(255,255,255,.16)}')
    assert not legacy_pink_outline('.poster {color:#ec4899}')
    shot = dict(id='retail', framing='fullbleed')
    assert corner_title_violation(shot,dict(kind='corner_tag',position='top_left'))
    assert not corner_title_violation(shot,dict(kind='corner_tag',position='top_right'))

def test_parallel_delivery_cards_have_no_ordered_arrow(tmp_path,materials):
    _,gsap=materials
    branches=[dict(title='交文件给同事改字',children=[dict(label='已搞定')]),
              dict(title='自己上台投屏镇场',children=[dict(label='二选一')])]
    spec=dict(id='choice',recipe='step_tree_focus',duration=4,data=dict(branches=branches,relationship='parallel'))
    html=build(spec,tmp_path,tmp_path/'choice',gsap).read_text()
    assert '<path class="tree-link"' not in html and '<span class="tree-no">' not in html
    assert '交文件给同事改字' in html and '自己上台投屏镇场' in html

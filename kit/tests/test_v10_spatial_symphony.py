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
    assert '<div class="fan-stage">' in fan_html and 'fan-punch-box' in fan_html

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

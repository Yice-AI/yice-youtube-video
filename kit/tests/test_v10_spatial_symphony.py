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
    ('layer_explode_3d',dict(boxes=[[.1,.2,.3,.4]],count=24), 'M1'),
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
                samples={'background':dict(n=200,luma=190,chroma=20)})]) for s in shots}
    gate = audit_spatial.spatial_frame_gates
    assert gate(shots,10,measured,True)['dual_engine_symphony_gate']['ok']
    assert not gate(shots,30,measured,True)['dual_engine_symphony_gate']['ok']
    assert not gate(shots[:-1],10,measured,True)['dual_engine_symphony_gate']['ok']
    for sample in measured.values():
        sample['frames'][0]['samples']['background']['luma'] = 20
    assert not gate(shots,10,measured,True)['dual_engine_symphony_gate']['ok']


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
    for color,top,ok in [('#242424','210',False),('#dddddd','65',True)]:
        markup = fixture.replace('COLOR',color).replace('TOP',top)
        entry.write_text('<!doctype html><template>'+markup+'</template>' if ok else markup)
        measured=audit_spatial.spatial_measurements([shot],tmp_path)
        gates=audit_spatial.spatial_frame_gates([shot],5,measured,False)
        assert gates['title_card_collision']['ok'] is ok
        assert gates['low_layer_contrast']['ok'] is ok
        assert gates['low_layer_contrast']['plates']['scene']['letters']['n']>0

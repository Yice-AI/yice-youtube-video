import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw
import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT/'scripts'), str(KIT.parent)]
from kit.spatial.block import build
from audit_spatial import composition_motion, spatial_frame_gates
from audit_v7 import cross_stage_asset_dedup_gate, external_showcase_diversity_gate


def script(name):
    spec = importlib.util.spec_from_file_location(name, KIT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scene(tmp_path, recipe, data, **kwargs):
    Image.new('RGB', (320, 180)).save(tmp_path/'wide.png')
    gsap = tmp_path/'runtime.js'
    gsap.write_text('')
    return build(dict(id='example', duration=5, recipe=recipe, data=data, **kwargs),
                 tmp_path, tmp_path/'compiled', gsap).read_text()


@pytest.mark.parametrize('look', ['swiss_paper','cyber_glass','editorial_paper','cinema_black'])
def test_cards_preserve_wide_pages_and_exit_on_every_look(tmp_path, look):
    data = dict(cards=[dict(source='wide.png', label='甲'), dict(source='wide.png', label='乙',
                pages=[dict(source='wide.png', at=2)])], exit_zoom_index=0)
    source = scene(tmp_path, 'progressive_sim_cards', data, stage_look=look)
    assert source.count('class="sim-panel is-media" data-media-aspect="widescreen"') == 2
    assert 'if (!data.board && cards.length > 1)' in source
    assert '"exit_zoom_at": 4.52' in source
    assert ('click',4.52,.42) in script('assemble-episode')._spatial_sound_marks(dict(recipe='progressive_sim_cards',data=data),5)
    data['cards'][0]['zoom'] = 1.2
    assert 'data-allow-crop="true"' in scene(tmp_path, 'progressive_sim_cards', dict(data, board=True))
    with pytest.raises(ValueError, match='exit_zoom_index'):
        scene(tmp_path, 'progressive_sim_cards', dict(data, exit_zoom_index=2))


def test_workbench_and_iteration_sound(tmp_path):
    data = dict(prompt_chips=[dict(role='版式',text='保留留白',at=.3)], before_source='wide.png',
                after_source='wide.png', exit_zoom_after=True)
    source = scene(tmp_path,'prompt_iter_workbench',data)
    assert 'data-stage-look="swiss_paper"' in source and '默认直出' in source and '加词精修后' in source
    assert composition_motion(source)[1] == 'M3'
    marks = script('assemble-episode')._spatial_sound_marks(dict(recipe='prompt_iter_workbench',data=data),5)
    assert [(k,t) for k,t,_ in marks] == [('click_soft',.3),('page_flip',2.3),('click',4.54),('zoom_swoosh',4.54)]


def test_aspect_crop_gate_retains_shot_and_source():
    frame = dict(phase=.5, overlaps=[], cards=[], aspectCrops=[dict(reason='excessive_aspect_crop',
                 source='example.mp4',crop_ratio=.35)])
    shot = dict(id='a',stage_mode='hyperframes_block',start=0,end=1)
    gate = spatial_frame_gates([shot],1,{'a':{'frames':[frame]}},False)['aspect_crop_integrity_gate']
    assert not gate['ok'] and gate['violations'][0]['source'] == 'example.mp4'


def test_video_slots_are_counted_once_per_shot(tmp_path):
    image=Image.new('RGB',(160,90),'white')
    ImageDraw.Draw(image).rectangle((22,23,114,65),fill='#2b707b')
    image.save(tmp_path/'page.png')
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(tmp_path/'page.png'),'-t','0.5',
                    '-pix_fmt','yuv420p',str(tmp_path/'source.mp4')],check=True)
    (tmp_path/'index.html').write_text('<video src="source.mp4"></video>'*2)
    shots=[dict(id=k,stage_mode='hyperframes_block',composition='index.html',start=i,end=i+1) for i,k in enumerate('abc')]
    assert cross_stage_asset_dedup_gate({'shots':shots[:2]},tmp_path,None)['ok']
    gate=cross_stage_asset_dedup_gate({'shots':shots},tmp_path,None)
    assert gate['violations']==[dict(shots=['a','b','c'],reason='repeated_visual')]
    shots[-1]['callback_of']='a'
    assert cross_stage_asset_dedup_gate({'shots':shots},tmp_path,None)['ok']


def test_source_diversity_checks_real_records(tmp_path):
    timeline=dict(episode_kind='tool_tutorial',shots=[])
    samples=([(str(i), ((1<<10)-1)<<(10*i), None) for i in range(6)],[])
    (tmp_path/'actual.png').touch()
    def check(records):
        (tmp_path/'asset-ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in records))
        return external_showcase_diversity_gate(timeline,tmp_path,None,100,samples=samples)
    assert not check([])['ok']
    rows=[dict(tool=t,sourceUrl=f'https://www.example.org/{i}',path='actual.png')
          for i,t in enumerate(['collect-entity','harvest-showcase-media'])]
    assert check(rows)['ok']
    rows[1]['path']='missing.png'
    assert not check(rows)['ok']
    assert not external_showcase_diversity_gate(timeline,tmp_path,None,15)['required']


def test_natural_pause_and_labelled_cover_briefs():
    check=script('voice-check')
    cfg=check.thresholds_for('natural_v7')
    assert (cfg['nonpunct_pause_max_ms'], cfg['intra_word_drop_db'], cfg['intra_word_min_ms'])==(165,21.5,125)
    chars=[dict(w=w,s=i*.2,e=i*.2+.17,charStart=i,charEnd=i+1,sentence=0,duration_ms=d,
                active_ms=140,f0_change_st=0) for i,(w,d) in enumerate(zip('重抽',[150,300]))]
    boundary=dict(kind='none',index=0,context='重抽',pause_ms=170,asr_gap_ms=0)
    data=dict(characters=chars,boundaries=[boundary],db=[],median_char_ms=150,chunk_seams=[])
    assert 'nonpunct_pause' in check.detect(data,thresholds=cfg)[0]['reasons']
    boundary.update(pause_ms=145,asr_gap_ms=0)
    assert not check.detect(data,thresholds=cfg)
    thumb=script('thumbnail')
    briefs=[thumb.cover_brief('草图变成品','工业展台',archetype=a)[1] for a in thumb.ARCHETYPES]
    assert len(set(briefs))==3 and all('x>78%' in brief for brief in briefs)


def test_failed_rerolls_only_regenerate_flagged_sentence_and_keep_original(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    repair = script('voice-repair')
    text = '保留。重抽。'
    original = tmp_path/'original.wav'
    sf.write(original, np.zeros(16000), 16000)
    current = dict(seed=42, audio=str(original), alignment={'text':text}, asr={'ok':True},
                   check={'ok':False, 'alerts':[dict(kind='hesitation',sentence=1)]})
    monkeypatch.setattr(repair, 'cuts_for', lambda *args, **kwargs:
                        ([(0,3,'保留。'),(3,6,'重抽。')], [[],[]], ([0,.5,1],[1],[True])))
    requested = []
    def generate(jobs):
        requested.extend((j['text'],j['seed']) for j in jobs)
    def reject(path):
        raise ValueError('不接受未通过听写的替换')
    result=repair.repair(dict(text=text,id='01'),current,tmp_path/'repair',generate,reject,
                         profile='natural_v7',max_rounds=3,candidates_per_sentence=1)
    assert requested == [('重抽。',42+7919*i) for i in (1,2,3)]
    assert not result['check']['ok'] and result['audio']==str(original)


def test_onetake_middle_frame_matches_across_engines(tmp_path):
    sequence=tmp_path/'vframes_ab12'
    sequence.mkdir()
    Image.new('RGB',(160,90),'gray').save(sequence/'f_0001.jpg')
    frame=Image.new('RGB',(160,90),'white')
    draw=ImageDraw.Draw(frame)
    draw.ellipse((20,10,105,79),fill='navy')
    frame.save(sequence/'f_0002.jpg')
    frame.save(tmp_path/'page.jpg')
    (tmp_path/'comp.html').write_text(' '.join(f'<img src="vframes_ab12/f_000{i}.jpg">' for i in (1,2)))
    shots=[dict(id='motion',stage_mode='onetake_clip',comp='comp.html',start=0,end=1)]
    shots.extend(dict(id=k,stage_mode='evidence_spotlight',source='page.jpg',start=i,end=i+1)
                 for i,k in enumerate(['first','second'],1))
    assert cross_stage_asset_dedup_gate({'shots':shots},tmp_path,None)['violations'] == [
        dict(shots=['motion','first','second'],reason='repeated_visual')]


def test_natural_does_not_attribute_sentence_tail_to_last_two_characters(tmp_path):
    import numpy as np
    import soundfile as sf
    check = script('voice-check')
    rate = 16000
    data = np.zeros(rate)
    time = np.arange(round(.46 * rate)) / rate
    data[:len(time)] = .3*np.sin(2*np.pi*210*time)
    path = tmp_path/'tail.wav'
    sf.write(path,data,rate)
    aligned = dict(text='稳了。', mapped=[
        dict(charStart=0,charEnd=1,s=0,e=.42), dict(charStart=1,charEnd=2,s=.42,e=.50)])
    result = check.check_chapter(path,aligned,profile='natural_v7')
    assert result['measurement']['boundaries'][0]['pause_ms'] == 0
    assert not result['alerts']


@pytest.mark.parametrize('aspect',['widescreen','portrait'])
def test_fan_exit_removes_frame_and_fills_canvas(tmp_path, aspect):
    import os
    required = ['YICE_CHROME_EXECUTABLE','YICE_PLAYWRIGHT_MODULE','YICE_GSAP_PATH']
    if not all(os.environ.get(key) for key in required):
        pytest.skip('此几何回归需要已配置的离线 Chromium、Playwright 和 GSAP')
    Image.new('RGB',(160,90),'teal').save(tmp_path/'page.png')
    entry = build(dict(id='fan',recipe='perspective_video_fan',duration=5,data=dict(
        items=['page.png']*3,focus_index=1,card_aspect=aspect,exit_zoom=True)),tmp_path,
        tmp_path/'project',Path(os.environ['YICE_GSAP_PATH']))
    js = """
    const { chromium } = require(process.env.YICE_PLAYWRIGHT_MODULE);
    (async () => {
      const browser = await chromium.launch({executablePath:process.env.YICE_CHROME_EXECUTABLE});
      try {
        const page = await browser.newPage({viewport:{width:1920,height:1080}});
        await page.goto(require('node:url').pathToFileURL(process.argv[1]).href);
        const bounds = await page.evaluate(() => {
          window.__timelines.fan.seek(5, false);
          const panel = document.querySelectorAll('.fan-card-inner')[1].getBoundingClientRect();
          const canvas = document.querySelector('#fan').getBoundingClientRect();
          return [panel.x-canvas.x, panel.y-canvas.y, panel.width, panel.height];
        });
        console.log(JSON.stringify(bounds));
      } finally { await browser.close(); }
    })().catch(error => {console.error(error); process.exitCode=1;});
    """
    rect = json.loads(subprocess.check_output(['node','-e',js,str(entry)],text=True))
    assert rect == pytest.approx([0,0,1920,1080],abs=1)

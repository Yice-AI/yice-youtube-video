"""Unit and integration tests for yice-youtube-video v12.0 visual engine."""
import importlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT / 'scripts')]

from kit.spatial.block import build as build_spatial
from kit.onetake.scene import build as build_onetake
import audit_spatial
from audit_v7 import composition_material, dual_engine_craft_gate

assemble = importlib.import_module('assemble-episode')
scaffold = importlib.import_module('scaffold-manifest')


@pytest.fixture
def media_pack(tmp_path):
    """Create tiny offline PNG/SVG/MP4 fixtures plus a dummy GSAP runtime."""
    png_a = tmp_path / 'a.png'
    png_b = tmp_path / 'b.png'
    Image.new('RGB', (160, 90), (24, 52, 88)).save(png_a)
    Image.new('RGB', (160, 90), (140, 48, 72)).save(png_b)

    # Transparent cutout PNG with wide transparent margin to verify auto-trimming.
    cutout = Image.new('RGBA', (240, 180), (0, 0, 0, 0))
    subject = Image.new('RGBA', (60, 50), (210, 90, 40, 255))
    cutout.paste(subject, (90, 70))
    cutout.save(tmp_path / 'hero_cutout.png')
    cutout.save(tmp_path / 'prop_cutout.png')

    svg = tmp_path / 'logo.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="12" fill="#e61e72"/></svg>')

    mp4_a = tmp_path / 'clip_a.mp4'
    mp4_b = tmp_path / 'clip_b.mp4'
    for path, color in ((mp4_a, '0x1e3a5f'), (mp4_b, '0x5f1e3a')):
        subprocess.run(
            ['ffmpeg', '-nostdin', '-v', 'error', '-y',
             '-f', 'lavfi', '-i', f'color=c={color}:s=320x180:d=1.2:r=24',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)],
            check=True,
        )

    gsap = tmp_path / 'gsap.min.js'
    gsap.write_text('// test gsap runtime')
    return {
        'png_a': 'a.png',
        'png_b': 'b.png',
        'hero': 'hero_cutout.png',
        'prop': 'prop_cutout.png',
        'svg': 'logo.svg',
        'mp4_a': 'clip_a.mp4',
        'mp4_b': 'clip_b.mp4',
        'gsap': gsap,
    }


def test_spatial_video_texture_embed_and_unique_ids(tmp_path, media_pack):
    spec = {
        'id': 'fan-vid',
        'recipe': 'perspective_video_fan',
        'duration': 5,
        'data': {
            'badge': '✦ 修改后',
            'items': [
                {'source': media_pack['mp4_a'], 'label': '方案一'},
                {'source': media_pack['mp4_b'], 'label': '方案二'},
                {'source': media_pack['png_a'], 'label': '方案三'},
            ],
            'focus_index': 1,
            'focus_at': 2.2,
        },
    }
    entry = build_spatial(spec, tmp_path, tmp_path / 'out_fan', media_pack['gsap'])
    html = entry.read_text()
    assert '<video id="fan-vid-v1"' in html
    assert '<video id="fan-vid-v2"' in html
    assert 'data-start="0" data-duration="5"' in html
    assert 'data-stage-look="cyber_glass"' in html
    assert len(list((entry.parent / 'media').glob('*.mp4'))) == 2
    assert audit_spatial.composition_motion(html) == (True, 'M1')
    assert dual_engine_craft_gate([dict(id='fan-vid', stage_mode='hyperframes_block', composition=entry)], tmp_path, v10=True)['ok']


@pytest.mark.parametrize('recipe,data,expected_mode,expected_look', [
    (
        'logo_bento_stage',
        {
            'brand': {'name': 'OiiOii', 'tag': 'Stack', 'logo': 'logo.svg'},
            'modules': [
                {'category': '大模型', 'at': 0.3, 'items': [{'name': 'Opus', 'logo': 'logo.svg'}]},
                {'category': '生图', 'at': 1.0, 'items': [{'name': 'Seedream'}]},
            ],
        },
        'M1', 'editorial_paper',
    ),
    (
        'cutout_parallax_stage',
        {
            'hero': 'hero_cutout.png',
            'props': ['prop_cutout.png'],
            'banner': {'title': '唐 · 驿马', 'sub': '岑参'},
            'tiles': ['马', '上', '相', '逢'],
            'counter': {'prefix': '已行', 'start': 100, 'end': 180, 'unit': '里', 'sub': '三十里一驿'},
        },
        'M1', 'scroll_paper',
    ),
    (
        'documentary_ken_burns',
        {
            'image': 'a.png',
            'focal_from': [0.3, 0.4, 1.3],
            'focal_to': [0.5, 0.5, 1.05],
            'archive_tag': {'eyebrow': '第112窟', 'title': '反弹琵琶'},
            'formula': {'label': '敦煌科普', 'key': '风格：', 'highlight': '岩彩手绘'},
            'split_at': 2.5,
            'anatomy_cards': [
                {'crop': [0.05, 0.1, 0.3, 0.5], 'label': '局部分析一'},
                {'crop': [0.35, 0.1, 0.3, 0.5], 'label': '局部分析二'},
                {'crop': [0.65, 0.1, 0.3, 0.5], 'label': '局部分析三'},
            ],
        },
        'M1', 'editorial_paper',
    ),
    (
        'step_tree_focus',
        {
            'heading': '整体工作流',
            'branches': [
                {'no': '1', 'title': '写提示词', 'at': 0.3, 'children': [{'label': '风格', 'at': 1.0}, {'label': '内容', 'at': 1.4}]},
                {'no': '2', 'title': '优化迭代', 'at': 2.2},
            ],
            'focus_sequence': [{'index': 0, 'at': 0.5}, {'index': 1, 'at': 2.4}, {'index': 0, 'at': 3.6}],
        },
        'M3', 'editorial_paper',
    ),
    (
        'progressive_sim_cards',
        {
            'heading': {'text': '代码做视频的', 'highlight': '好处'},
            'cards': [
                {'kind': 'race_bars', 'label': '速度更快', 'at': 0.2, 'slow_end': 24, 'fast_end': 100},
                {'kind': 'live_media', 'label': '方便修改', 'at': 1.2, 'source': 'clip_a.mp4'},
                {'kind': 'live_media', 'label': '更有质感', 'at': 2.2, 'source': 'a.png'},
            ],
        },
        'M3', 'editorial_paper',
    ),
    (
        'formula_pill_chain',
        {
            'source_pill': '手绘质感',
            'target_pill': 'Canvas 逐帧绘制',
            'reveal_at': 1.4,
            'media': 'clip_a.mp4',
            'badge': '✦ 原视频',
        },
        'M3', 'ultramarine',
    ),
])
def test_v12_spatial_recipes_build_and_certify(tmp_path, media_pack, recipe, data, expected_mode, expected_look):
    spec = {'id': f'scene-{recipe[:6]}', 'recipe': recipe, 'duration': 5, 'data': data}
    entry = build_spatial(spec, tmp_path, tmp_path / recipe, media_pack['gsap'])
    html = entry.read_text()
    assert f'data-stage-look="{expected_look}"' in html
    assert 'paused:true' in html
    assert str(tmp_path) not in html
    assert audit_spatial.composition_motion(html)[1] == expected_mode
    assert f'class="look-{expected_look}"' not in html
    if recipe == 'documentary_ken_burns':
        # Embedded compositions rebase image sources, but not inline background URLs.
        painting = re.search(r'<img class="doc-painting" src="([^"]+)"', html).group(1)
        assert (entry.parent / painting).is_file()
        assert re.findall(r'<img class="doc-crop-bg" src="([^"]+)"', html) == [painting] * 3
    if recipe == 'cutout_parallax_stage':
        # Auto-trimmed hero PNG should be smaller than original 240x180 transparent canvas.
        trimmed_pngs = list((entry.parent / 'media').glob('*.png'))
        assert trimmed_pngs
        with Image.open(trimmed_pngs[0]) as im:
            assert im.width < 200 and im.height < 140


@pytest.mark.parametrize('mode', ['center_scan', 'diagonal_wipe', 'quad_race'])
def test_onetake_split_wipe_extracts_deterministic_video_frames(tmp_path, media_pack, mode):
    spec = {
        'recipe': 'split_wipe_compare',
        'duration': 3.5,
        'hud': 'COMPARE',
        'data': {
            'mode': mode,
            'before': media_pack['mp4_a'],
            'after': media_pack['mp4_b'],
            'before_label': '↺ 修改前',
            'after_label': '✦ 修改后',
        },
    }
    entry = build_onetake(spec, tmp_path, tmp_path / f'ot_{mode}')
    html = entry.read_text()
    assert 'window.__seek' in html and 'OM.camera(' in html and 'Promise.all' in html
    frame_dirs = list(entry.parent.glob('vframes_*'))
    assert len(frame_dirs) == 2
    assert all(len(list(d.glob('f_*.jpg'))) >= 20 for d in frame_dirs)
    # composition_material should collapse vframes_* sequence to representative f_0001.jpg
    _, imgs = composition_material(entry)
    assert len(imgs) == 2
    shot = dict(id='cmp', stage_mode='onetake_clip', comp=entry.relative_to(tmp_path).as_posix(), visual_mode='M3')
    assert dual_engine_craft_gate([shot], tmp_path, v10=True)['ok']


@pytest.mark.parametrize('style', ['pencil_watercolor', 'riso_halftone'])
def test_onetake_handdrawn_sketch_stage_offline(tmp_path, style):
    spec = {
        'recipe': 'handdrawn_sketch_stage',
        'duration': 4.0,
        'hud': 'SKETCH',
        'data': {
            'style': style,
            'title': '纯代码手绘',
            'monster': style == 'pencil_watercolor',
            'gauge': {'label': 'P(DOOM)', 'from': 10, 'to': 80},
            'nodes': [
                {'title': '步骤一', 'sub': '铅笔抖线', 'at': 0.3, 'icon': 'bulb'},
                {'title': '步骤二', 'sub': '水彩填充', 'at': 1.2, 'icon': 'chart'},
            ],
        },
    }
    entry = build_onetake(spec, tmp_path, tmp_path / f'sketch_{style}')
    html = entry.read_text()
    assert (entry.parent / 'sketch_brush.js').is_file()
    assert 'SKETCH.' in html and 'OM.camera(' in html
    assert audit_spatial.composition_motion(html, 'M3') == (True, 'M3')


def test_audit_spatial_dual_tone_and_consistency():
    shots = [
        dict(id='s0', stage_mode='hyperframes_block', start=0, end=3, stage_look='editorial_paper'),
        dict(id='s1', stage_mode='hyperframes_block', start=3, end=6, stage_look='editorial_paper'),
        dict(id='o0', stage_mode='onetake_clip', start=6, end=9, look='paper'),
        dict(id='o1', stage_mode='onetake_clip', start=9, end=12, look='paper'),
        dict(id='o2', stage_mode='onetake_clip', start=12, end=15, look='paper'),
    ]
    measured = {
        s['id']: dict(frames=[dict(
            phase=.88, overlaps=[], exploded=False, stageLook='editorial_paper',
            samples={'background': dict(n=200, luma=234, chroma=8), 'highlights': {str(i % 2): 90}},
        )])
        for i, s in enumerate(shots)
    }
    res = audit_spatial.spatial_frame_gates(shots, 20, measured, True)
    assert res['unified_cyber_stage_and_accent_gate']['ok']

    # Dim paper violates editorial_paper
    measured['s0']['frames'][0]['samples']['background']['luma'] = 95
    bad_dim = audit_spatial.spatial_frame_gates(shots, 20, measured, True)
    assert any(v['reason'] == 'dim_editorial_paper_background' for v in bad_dim['unified_cyber_stage_and_accent_gate']['violations'])

    # Mixing dark and light tones mid-film triggers inconsistent_stage_tone
    measured['s0']['frames'][0]['samples']['background']['luma'] = 20
    measured['s0']['frames'][0]['stageLook'] = 'cyber_glass'
    bad_mix = audit_spatial.spatial_frame_gates(shots, 20, measured, True)
    assert any(v['reason'] == 'inconsistent_stage_tone' for v in bad_mix['unified_cyber_stage_and_accent_gate']['violations'])


def test_assemble_inline_v12_and_light_zones(tmp_path, media_pack):
    voice_wav = tmp_path / 'v.wav'
    subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '10', str(voice_wav)],
        check=True,
    )
    manifest = {
        'title': 'v12装配测试',
        'filename': 'episode',
        'gsap': str(media_pack['gsap']),
        'cues': [
            {'id': 'c1', 'firstCharTime': 0.0, 'end': 5.0, 'text': '展示整体工作流分支。'},
            {'id': 'c2', 'firstCharTime': 5.0, 'end': 10.0, 'text': '手绘质感对比。'},
        ],
        'audio': {'voice_tracks': [{'id': '1', 'path': 'v.wav', 'at': 0.0}]},
        'shots': [
            {
                'id': 's1', 'act': 'act-1', 'anchor_cue_id': 'c1', 'start': 0.0, 'end': 5.0,
                'stage_mode': 'hyperframes_block', 'spoken_topic': '工作流', 'visual_subject': '工作流树',
                'semantic_tags': ['工作流'], 'semantic_binding': 'conceptual_explainer',
                'spatial_spec': {
                    'recipe': 'step_tree_focus',
                    'data': {
                        'heading': '整体工作流',
                        'branches': [{'no': '1', 'title': '写提示词', 'at': 0.3}, {'no': '2', 'title': '优化', 'at': 2.0}],
                        'focus_sequence': [{'index': 0, 'at': 0.5}, {'index': 1, 'at': 2.2}],
                    },
                },
            },
            {
                'id': 's2', 'act': 'act-1', 'anchor_cue_id': 'c2', 'start': 5.0, 'end': 10.0,
                'stage_mode': 'hyperframes_block', 'spoken_topic': '渐进卡片', 'visual_subject': '速度对比卡',
                'semantic_tags': ['代码做视频'], 'semantic_binding': 'conceptual_explainer',
                'spatial_spec': {
                    'recipe': 'progressive_sim_cards',
                    'data': {
                        'heading': {'text': '代码做视频的', 'highlight': '好处'},
                        'cards': [
                            {'kind': 'race_bars', 'label': '速度更快', 'at': 0.2},
                            {'kind': 'live_media', 'label': '方便修改', 'at': 1.2, 'source': media_pack['mp4_a']},
                        ],
                    },
                },
            },
        ],
    }
    manifest_path = tmp_path / 'episode-manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    out_dir = tmp_path / 'out'
    result = assemble.assemble(manifest_path, out_dir, build_only=True)
    assert result['ok'] and result['shots'] == 2
    act_html = (out_dir / 'acts/act-1/index.html').read_text()
    # Editorial paper shots should automatically turn captions into dark obsidian pills (caption-on-light).
    assert 'caption-on-light' in act_html


def test_headless_browser_sampling_for_v12_video_and_paper(tmp_path, media_pack):
    if not os.environ.get('YICE_PLAYWRIGHT_MODULE') or not os.environ.get('YICE_CHROME_EXECUTABLE'):
        pytest.skip('需要本机 Playwright 与无头 Chromium')
    from workspace import resolve_gsap_runtime
    runtime = resolve_gsap_runtime()
    entry = build_spatial(
        {
            'id': 'tree-test',
            'recipe': 'step_tree_focus',
            'duration': 4.5,
            'data': {
                'heading': '整体工作流',
                'branches': [
                    {'no': '1', 'title': '写提示词', 'at': 0.2, 'children': [{'label': '风格', 'at': 1.0}, {'label': '内容', 'at': 1.4}]},
                    {'no': '2', 'title': '优化迭代', 'at': 2.0},
                ],
                'focus_sequence': [{'index': 0, 'at': 0.4}, {'index': 1, 'at': 2.2}, {'index': 0, 'at': 3.3}],
            },
        },
        tmp_path, tmp_path / 'tree_out', runtime,
    )
    choreo = audit_spatial.sample_choreography(entry)
    assert choreo['ok'] and choreo['timelines'][0]['seekSafe']
    shot = dict(id='tree-test', stage_mode='hyperframes_block', composition='tree_out/index.html', start=0, end=4.5, stage_look='editorial_paper')
    measured = audit_spatial.spatial_measurements([shot], tmp_path)
    gates = audit_spatial.spatial_frame_gates([shot], 4.5, measured, False)
    assert gates['title_card_collision']['ok']
    assert gates['no_ppt_slide_header_gate']['ok']
    lumas = [f['samples']['background']['luma'] for f in measured['tree-test']['frames'] if 'samples' in f]
    assert lumas and all(l >= 185 for l in lumas)

def test_narrated_wipe_keeps_its_absolute_cue(tmp_path):
    from PIL import Image
    Image.new('RGB',(80,60),'red').save(tmp_path/'before.png')
    Image.new('RGB',(80,60),'blue').save(tmp_path/'after.png')
    data=dict(mode='diagonal_wipe',before='before.png',after='after.png',wipe_at=3.47)
    spec=dict(id='voice-cut',recipe='split_wipe_compare',duration=4.,data=data)
    html=build_onetake(spec,tmp_path,tmp_path/'comparison').read_text()
    assert '"wipe_at": 3.47' in html
    data['wipe_at']=3.95
    with pytest.raises(ValueError,match='口播擦切点'):
        build_onetake(spec,tmp_path,tmp_path/'invalid')

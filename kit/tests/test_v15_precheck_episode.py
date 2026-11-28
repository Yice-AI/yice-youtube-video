"""v15 制片前置三关（包装 / 口播稿 / 素材）的离线回归。"""
import importlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
precheck = importlib.import_module('precheck-episode')

WORKSPACE = Path(os.environ.get('YICE_WORKSPACE') or Path.home()/'Documents/Codex/个人IP')
HISTORY = Path(os.environ.get('YICE_PRECHECK_HISTORY') or WORKSPACE/'.scratch/youtube/episodes/ep04-v14-cleanroom')

GOOD_SCRIPT = """# 别再套丑模板了！一句话让 AI 做出发布会级 PPT、宣传短片和爆款封面

## 01 先看成品

| 幕号 | 旁白 | 画面 |
| --- | --- | --- |
| 1-1 | 同一份提纲，左边是默认直出的丑模板 PPT，右边是加了一句提示词后的发布会版本，差距一眼就能看出来。 | 左侧真实丑模板 PPT 截图打红叉，右侧精修成品斜切擦除揭晓 |
| 1-2 | 今天这四个免费工具，帮你把 PPT、宣传短片和封面一次做完，全程不花订阅费。 | 四款工具成品 3D 扇形墙 |

## 02 做 PPT

| 幕号 | 旁白 | 画面 |
| --- | --- | --- |
| 2-1 | 先输入「深色科技新品演示页」，默认直出的版式还很平。 | prompt_iter_workbench 左侧默认直出 |
| 2-2 | 再加上一句「Bento 网格与大字数据卡」，版式立刻变成发布会质感。 | prompt_iter_workbench 右侧加词精修后 |

## 03 做宣传短片

| 幕号 | 旁白 | 画面 |
| --- | --- | --- |
| 3-1 | 把同一份提纲丢给它，提示词写「十五秒新品短片，镜头推近数据卡」，默认直出节奏偏慢。 | 默认直出短片录屏 |
| 3-2 | 改成「每三秒切一个镜头」之后，短片节奏马上紧凑起来。 | 改后短片满屏播放 |

## 04 做封面

| 幕号 | 旁白 | 画面 |
| --- | --- | --- |
| 4-1 | 最后做封面，三套构图一次出三张候选，挑一张最清楚的。 | 三张封面候选并排 |
| 4-2 | 仓库链接都放在简介里，这周就能用上。 | 四款工具总览收束 |
"""

GOOD_PACKAGING = {
    'title': '别再套丑模板了！一句话让 AI 做出发布会级 PPT、宣传短片和爆款封面',
    'hook': '一句话出大片',
    'viewer_promise': '看完能用四个免费工具做 PPT、宣传短片和封面',
    'target_keywords': ['AI PPT', '宣传片', '封面'],
    'episode_kind': 'tool_tutorial',
}

EXTERNAL_LEDGER = [
    {'id': 'paper-demo', 'kind': 'showcase_video', 'sourceType': 'harvest-showcase-media',
     'url': 'https://example-lab.github.io/project/', 'path': 'media/shot-0.png'},
    {'id': 'official-site', 'kind': 'web_capture', 'sourceType': 'capture-web',
     'url': 'https://www.example-tool.com/', 'path': 'media/shot-1.png'},
    {'id': 'repo-readme', 'kind': 'entity', 'sourceType': 'collect-entity',
     'url': 'https://github.com/example/tool', 'path': 'media/shot-2.png'},
    {'id': 'local-demo', 'kind': 'web_cam_recording', 'url': 'http://127.0.0.1:4100/', 'path': 'media/shot-3.png'},
]


def block_image(path, seed, size=(1280, 720)):
    """随机 9×8 明暗块放大成高清图，不同种子得到差异很大的画面指纹。"""
    rng = random.Random(seed)
    cols, rows = 9, 8
    cells = [[rng.randint(0, 255) for _ in range(cols)] for _ in range(rows)]
    width, height = size
    data = bytearray()
    for y in range(height):
        row = cells[y * rows // height]
        line = bytes(row[x * cols // width] for x in range(width))
        data += line
    raw = path.with_suffix('.gray')
    raw.write_bytes(bytes(data))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{width}x{height}',
                    '-i', str(raw), '-frames:v', '1', str(path)], check=True)
    raw.unlink()


def still_video(image, video):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', str(image), '-t', '1', '-r', '10',
                    '-pix_fmt', 'yuv420p', '-threads', '1', str(video)], check=True)


def make_project(root, *, script=GOOD_SCRIPT, packaging=GOOD_PACKAGING, ledger=EXTERNAL_LEDGER, images=9):
    root.mkdir(parents=True, exist_ok=True)
    (root/'script.md').write_text(script, encoding='utf-8')
    if packaging is not None:
        (root/'packaging.json').write_text(json.dumps(packaging, ensure_ascii=False), encoding='utf-8')
    media = root/'media'
    media.mkdir(exist_ok=True)
    for index in range(images):
        block_image(media/f'shot-{index}.png', seed=index * 7919 + 13)
    if images:
        still_video(media/'shot-0.png', media/'shot-0.mp4')  # 同名海报与视频算同一份素材
    if ledger is not None:
        (root/'asset-ledger.jsonl').write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in ledger), encoding='utf-8')
    return root


def codes(report, stage):
    return [item['code'] for item in report['stages'][stage]['errors']]


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class GoodProjectTests(TempCase):
    @classmethod
    def setUpClass(cls):
        cls._shared = tempfile.TemporaryDirectory()
        cls.good = make_project(Path(cls._shared.name)/'ep')

    @classmethod
    def tearDownClass(cls):
        cls._shared.cleanup()

    def test_good_project_passes_all_stages(self):
        report = precheck.run(self.good, 'all')
        self.assertTrue(report['ok'], json.dumps(report, ensure_ascii=False, indent=1))
        self.assertGreaterEqual(report['stages']['assets']['metrics']['visual_clusters'], 8)
        self.assertGreaterEqual(len(report['stages']['script']['metrics']['prompt_loop_chapters']), 2)

    def test_cli_exit_codes_and_json_report(self):
        out = self.tmp/'report.json'
        done = subprocess.run([str(SCRIPTS/'precheck-episode.sh'), '--project', str(self.good), '--stage', 'all',
                               '--json', '--output', str(out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIs(json.loads(out.read_text())['ok'], True)
        self.assertEqual(json.loads(done.stdout)['stages'].keys(), {'packaging', 'script', 'assets'})
        missing = subprocess.run([str(SCRIPTS/'precheck-episode.sh'), '--project', str(self.tmp/'none')],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        bad_arg = subprocess.run([str(SCRIPTS/'precheck-episode.sh'), '--project', str(self.good), '--stage', 'voice'],
                                 capture_output=True, text=True)
        self.assertEqual(bad_arg.returncode, 2)


class PackagingTests(TempCase):
    def assert_bland(self, title):
        root = make_project(self.tmp/'ep', packaging={**GOOD_PACKAGING, 'title': title}, images=0)
        self.assertIn('bland_explanatory_title', codes(precheck.run(root, 'packaging'), 'packaging'))

    def test_bland_title_how_to_choose(self):
        self.assert_bland('AI 做 PPT 怎么选？同一份提案做成两种格式')

    def test_bland_title_user_guide(self):
        self.assert_bland('PPT 工具使用指南')

    def test_bland_title_shallow_talk(self):
        self.assert_bland('浅谈视频')

    def test_short_title_without_hook_is_blocked(self):
        root = make_project(self.tmp/'ep', packaging={'title': '视频工具'}, images=0)
        self.assertIn('bland_explanatory_title', codes(precheck.run(root, 'packaging'), 'packaging'))

    def test_packaging_markdown_keys_are_read(self):
        root = make_project(self.tmp/'ep', packaging=None, images=0)
        (root/'packaging.md').write_text('# 包装\n\n## 标题\n浅谈 PPT\n\n- 钩子：一句话\n', encoding='utf-8')
        report = precheck.run(root, 'packaging')
        self.assertEqual(report['stages']['packaging']['metrics']['title'], '浅谈 PPT')
        self.assertEqual(report['stages']['packaging']['metrics']['source'], 'packaging.md')
        self.assertIn('bland_explanatory_title', codes(report, 'packaging'))

    def test_title_promise_drift_is_blocked(self):
        drift = GOOD_SCRIPT.replace('PPT、宣传短片和封面', 'PPT').replace('做 PPT', '剪视频').replace(
            '深色科技新品演示页', '十五秒宣传短片').replace('Bento 网格与大字数据卡', '每个镜头配小红书封面')
        root = make_project(self.tmp/'ep', script=drift, images=0,
                            packaging={'title': '别再充 PPT 会员了！一句话做出发布会级 PPT'})
        report = precheck.run(root, 'packaging')
        self.assertIn('promise_body_drift', codes(report, 'packaging'))
        detail = next(e for e in report['stages']['packaging']['errors'] if e['code'] == 'promise_body_drift')
        self.assertGreater(detail['off_promise_ratio'], 0.5)
        self.assertIn('视频剪辑', detail['off_promise_categories'])

    def test_thumbnail_batch_needs_three_candidates(self):
        root = make_project(self.tmp/'ep', images=0)
        batch = root/'thumbnails'/'batch-1'
        batch.mkdir(parents=True)
        for name in ('candidate-1.png', 'candidate-2.png', 'thumbnail-contact-sheet.png'):
            (batch/name).write_bytes(b'x')
        self.assertIn('thumbnail_candidates_insufficient', codes(precheck.run(root, 'packaging'), 'packaging'))
        (batch/'candidate-3.png').write_bytes(b'x')
        self.assertTrue(precheck.run(root, 'packaging')['stages']['packaging']['ok'])
        empty = make_project(self.tmp/'none', images=0)
        self.assertIn('thumbnail_candidates_missing',
                      codes(precheck.run(empty, 'packaging', require_thumbnails=True), 'packaging'))


class ScriptTests(TempCase):
    def test_missing_script_is_input_error(self):
        (self.tmp/'ep').mkdir()
        self.assertEqual(precheck.main(['--project', str(self.tmp/'ep'), '--stage', 'script']), 2)

    def test_maker_plumbing_leak_reports_scene_and_sentence(self):
        leak = GOOD_SCRIPT.replace('最后做封面，三套构图一次出三张候选，挑一张最清楚的。',
                                   '截图脚本先等零点六秒再批量截图，导出来才不会发黑。')
        root = make_project(self.tmp/'ep', script=leak, images=0)
        report = precheck.run(root, 'script')
        leaks = [e for e in report['stages']['script']['errors'] if e['code'] == 'maker_plumbing_leak']
        self.assertTrue(leaks)
        self.assertEqual(leaks[0]['scene_id'], '4-1')
        self.assertIn('批量截图', leaks[0]['sentence'])
        self.assertLessEqual({'批量截图/导图', '截图等待秒数'}, set(leaks[0]['patterns']))

    def test_maker_topic_allows_engineering_terms(self):
        leak = GOOD_SCRIPT.replace('最后做封面', '用无头浏览器批量截图做封面')
        root = make_project(self.tmp/'ep', script=leak, images=0,
                            packaging={**GOOD_PACKAGING, 'maker_topic': True})
        self.assertNotIn('maker_plumbing_leak', codes(precheck.run(root, 'script'), 'script'))

    def test_slow_opener_and_early_command_are_blocked(self):
        slow = GOOD_SCRIPT.replace('同一份提纲，左边', '大家好我是一策，今天我们来聊聊 PPT。同一份提纲，左边').replace(
            '全程不花订阅费。', '先 git clone 仓库再 npm install。')
        root = make_project(self.tmp/'ep', script=slow, images=0)
        errors = precheck.run(root, 'script')['stages']['script']['errors']
        phrases = {e.get('phrase') for e in errors if e['code'] == 'slow_or_meta_opener'}
        self.assertIn('大家好我是', phrases)
        self.assertIn('git clone', phrases)

    def test_pain_point_without_counter_visual_is_blocked(self):
        unpaired = GOOD_SCRIPT.replace('左侧真实丑模板 PPT 截图打红叉，右侧精修成品斜切擦除揭晓', '四款工具 logo 依次出现')
        root = make_project(self.tmp/'ep', script=unpaired, images=0)
        report = precheck.run(root, 'script')
        self.assertEqual([e['scene_id'] for e in report['stages']['script']['errors']
                          if e['code'] == 'unpaired_pain_point_visual'], ['1-1'])
        (root/'episode-manifest.json').write_text(json.dumps({'shots': [
            {'anchor_cue_id': '1-1', 'stage_mode': 'onetake_clip',
             'onetake_spec': {'recipe': 'split_wipe_compare', 'data': {}}}]}), encoding='utf-8')
        self.assertNotIn('unpaired_pain_point_visual', codes(precheck.run(root, 'script'), 'script'))

    def test_inline_visual_note_pairs_pain_point(self):
        note = GOOD_SCRIPT.replace('| 1-1 | 同一份提纲', '| 1-1 | 〔画面：默认直出的丑模板原件〕同一份提纲').replace(
            '左侧真实丑模板 PPT 截图打红叉，右侧精修成品斜切擦除揭晓', '')
        root = make_project(self.tmp/'ep', script=note, images=0)
        self.assertNotIn('unpaired_pain_point_visual', codes(precheck.run(root, 'script'), 'script'))

    def test_feature_list_without_prompt_loop_is_blocked(self):
        dry = GOOD_SCRIPT
        for quote in ('「深色科技新品演示页」', '「Bento 网格与大字数据卡」', '「十五秒新品短片，镜头推近数据卡」', '「每三秒切一个镜头」'):
            dry = dry.replace(quote, '一些要求')
        root = make_project(self.tmp/'ep', script=dry, images=0)
        self.assertIn('missing_hands_on_prompt_loop', codes(precheck.run(root, 'script'), 'script'))


class AssetTests(TempCase):
    def test_renamed_duplicate_media_is_blocked(self):
        root = make_project(self.tmp/'ep')
        shutil.copy(root/'media'/'shot-3.png', root/'media'/'final-v2.png')
        still_video(root/'media'/'shot-4.png', root/'media'/'other-name.mp4')
        report = precheck.run(root, 'assets')
        groups = [sorted(e['files']) for e in report['stages']['assets']['errors']
                  if e['code'] == 'duplicate_asset_disguise']
        self.assertIn(['media/final-v2.png', 'media/shot-3.png'], groups)
        self.assertIn(['media/other-name.mp4', 'media/shot-4.png'], groups)

    def test_local_only_and_few_clusters_are_blocked(self):
        local = [{'id': f'page-{i}', 'kind': 'web_cam_recording', 'url': 'http://127.0.0.1:4100/',
                  'path': f'media/shot-{i}.png'} for i in range(4)]
        root = make_project(self.tmp/'ep', ledger=local, images=4)
        errors = codes(precheck.run(root, 'assets'), 'assets')
        self.assertIn('missing_external_showcase', errors)
        self.assertIn('insufficient_visual_clusters', errors)


class HistoryCounterexampleTests(unittest.TestCase):
    def test_history_counterexample_is_blocked(self):
        if not HISTORY.is_dir():
            self.skipTest('本机没有历史反面样片')
        report = precheck.run(HISTORY, 'all')
        self.assertFalse(report['ok'])
        leaks = [e for e in report['stages']['script']['errors'] if e['code'] == 'maker_plumbing_leak']
        self.assertTrue(leaks and any('秒' in e['sentence'] for e in leaks))
        packaging, assets = codes(report, 'packaging'), codes(report, 'assets')
        self.assertTrue('promise_body_drift' in packaging or 'missing_external_showcase' in assets)
        self.assertIn('missing_external_showcase', assets)


if __name__ == '__main__':
    unittest.main()

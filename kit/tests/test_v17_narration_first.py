"""v17 散文母稿优先：narration.md 直检、无损拆表、吹牛词拦截、不再逼短句。"""
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
precheck = importlib.import_module('precheck-episode')
n2s = importlib.import_module('narration_to_script')

PACKAGING = {
    'title': '不会写代码也能用：5 个免费 Skill 让 AI 做的小红书图、PPT 和动画不再廉价',
    'hook': '同一句话，装上 Skill 前后差一截',
    'viewer_promise': '看完会挑 Skill，并能用它做小红书套图、PPT 和数据动画',
    'target_keywords': ['AI PPT', '小红书', '动画', 'Skill'],
    'episode_kind': 'tool_tutorial',
}

NARRATION = """# 不会写代码也能用：5 个免费 Skill 让 AI 做的小红书图、PPT 和动画不再廉价

## 包装

备选标题：这一段不进口播。

## 01 为什么一眼廉价

〔画面：白底三蓝框的 PPT 原件，左右并排装上 Skill 后的版本〕
让 AI 直接做 PPT，十次有八次是白底加三个蓝框，看着就廉价。同一句话，装上一个免费 Skill 之后，出来的是网格大字的版式。这期把小红书图、PPT 和动画三件事一起讲清楚，后面所有工具都不花钱。

我一开始以为是模型不够强，换了好几个都差不多，后来发现它缺的是一套排版的规矩，就像新来的同事很聪明，但没人告诉他公司的模板放在哪里，所以每次都从白纸开始画。

## 02 做小红书图

〔演示：提示词工作台，两句话依次弹出〕
我输入「把这篇周末出游攻略做成小红书三比四套图」，默认直出是杂志风，干净但不显眼。再加一句「改成瑞士风」，立刻变成大字网格配一道克莱因蓝。

它不会修照片，美食和穿搭这种靠照片本身的帖子不适合用它。

## 03 做 PPT

〔演示：都行→白底，技术分享→深色代码风〕
它先问给谁看。我第一次回「都行」，默认出来是普通白底；改成「给技术同事做内部分享」之后，马上换成写代码那种深色配色。

它交出来的是网页，不是 pptx，公司要求交 PPT 文件就别用它。

## 04 做动画

〔画面：飘入式第一版和柱子弹起的第二版左右对比〕
我第一次写「做一段有高级感的数据动画」，默认直出就是数字往上飘。第二次写「三根柱子按顺序弹起来，镜头推近最高那根」，这回才像片子。

## 事实与仓库核对表

| 项 | 来源 |
| --- | --- |
| 协议 | 仓库 LICENSE |
"""


def project(root, narration=NARRATION, packaging=PACKAGING, script=None):
    root.mkdir(parents=True, exist_ok=True)
    (root/'narration.md').write_text(narration, encoding='utf-8')
    (root/'packaging.json').write_text(json.dumps(packaging, ensure_ascii=False), encoding='utf-8')
    if script is not None:
        (root/'script.md').write_text(script, encoding='utf-8')
    return root


def codes(report, key='errors'):
    return [item['code'] for item in report['stages']['script'][key]]


class NarrationFirstTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_narration_only_project_passes_script_and_packaging(self):
        root = project(self.tmp/'ep')
        report = precheck.run(root, 'script')
        self.assertTrue(report['ok'], json.dumps(report, ensure_ascii=False, indent=1))
        metrics = report['stages']['script']['metrics']
        self.assertEqual(metrics['source'], 'narration.md')
        self.assertEqual(metrics['chapters'], 4)
        self.assertGreaterEqual(len(metrics['prompt_loop_chapters']), 2)
        self.assertTrue(precheck.run(root, 'packaging')['ok'])

    def test_metadata_sections_are_not_spoken(self):
        doc = n2s.parse_narration(project(self.tmp/'ep')/'narration.md')
        spoken = n2s.spoken_text(doc)
        self.assertNotIn('备选标题', spoken)
        self.assertNotIn('LICENSE', spoken)
        self.assertNotIn('〔', spoken)
        self.assertEqual([c['num'] for c in doc['chapters']], [1, 2, 3, 4])

    def test_split_is_lossless_and_notes_land_in_third_column(self):
        root = project(self.tmp/'ep')
        done = subprocess.run([str(SCRIPTS/'split-narration.sh'), str(root/'narration.md')],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        table = (root/'script.md').read_text(encoding='utf-8')
        parsed = precheck.parse_script(root/'script.md')
        mother = n2s.spoken_text(n2s.parse_narration(root/'narration.md'))
        self.assertEqual(re.sub(r'\s', '', ''.join(s['text'] for s in parsed['scenes'])), re.sub(r'\s', '', mother))
        first = parsed['scenes'][0]
        self.assertEqual(first['id'], '1-1')
        self.assertIn('白底三蓝框', first['visual'])
        self.assertNotIn('〔', table.split('| --- | --- | --- |')[1].split('\n')[1].split('|')[2])
        self.assertTrue(all(len(s['text']) <= n2s.MAX_CHARS + n2s.MIN_CHARS for s in parsed['scenes']))
        report = precheck.run(root, 'script')
        self.assertTrue(report['ok'], json.dumps(report, ensure_ascii=False, indent=1))
        self.assertEqual(report['stages']['script']['metrics']['source'], 'script.md')
        self.assertNotIn('narration_script_out_of_sync', codes(report, 'warnings'))

    def test_split_scene_ids_match_narration_check(self):
        root = project(self.tmp/'ep')
        from_mother = [s['id'] for s in precheck.load_script(root)['scenes']]
        subprocess.run([str(SCRIPTS/'split-narration.sh'), str(root/'narration.md')], check=True, capture_output=True)
        from_table = [s['id'] for s in precheck.parse_script(root/'script.md')['scenes']]
        self.assertEqual(from_mother, from_table)

    def test_semicolon_list_stays_in_one_scene_and_prose_prompts_count(self):
        groups = n2s.sentence_groups('这期讲三件事：为什么廉价；怎么挑；怎么用。下一句。')
        self.assertEqual(len(groups), 1)
        prose = NARRATION.replace('我输入「把这篇周末出游攻略做成小红书三比四套图」', '我只说了一句：“做成小红书三比四套图”') \
            .replace('再加一句「改成瑞士风」', '我又加了一句：“改成瑞士风”')
        loops = precheck.run(project(self.tmp/'prose', narration=prose), 'script')['stages']['script']['metrics']['prompt_loop_chapters']
        self.assertIn(2, loops)

    def test_hand_edited_table_is_flagged_out_of_sync(self):
        root = project(self.tmp/'ep')
        subprocess.run([str(SCRIPTS/'split-narration.sh'), str(root/'narration.md')], check=True, capture_output=True)
        table = (root/'script.md').read_text(encoding='utf-8').replace('看着就廉价', '看着就很廉价')
        (root/'script.md').write_text(table, encoding='utf-8')
        self.assertIn('narration_script_out_of_sync', codes(precheck.run(root, 'script'), 'warnings'))

    def test_unverified_hype_claims_are_blocked(self):
        for phrase in ('这是全网最强的 PPT 神器', '用了它效率提升300%', '每天省下3小时', '直接吊打付费软件'):
            root = project(self.tmp/phrase[:4], narration=NARRATION.replace('后面所有工具都不花钱。', phrase + '。'))
            self.assertIn('unverified_hype_claim', codes(precheck.run(root, 'script')), phrase)

    def test_long_natural_sentences_and_analogies_are_not_warned(self):
        report = precheck.run(project(self.tmp/'ep'), 'script')
        self.assertNotIn('long_winded_clauses', codes(report, 'warnings'))
        self.assertNotIn('long_winded_clauses', codes(report))

    def test_numbered_method_points_are_not_flat_catalog(self):
        method = NARRATION.replace('〔演示：提示词工作台', '第一个门道是先看它能交出什么。\n\n〔演示：提示词工作台') \
            .replace('〔演示：都行', '第二个是看清它不能干什么。\n\n〔演示：都行') \
            .replace('〔画面：飘入式', '第三个是看协议。\n\n〔画面：飘入式')
        self.assertNotIn('flat_catalog_transitions', codes(precheck.run(project(self.tmp/'ep', narration=method), 'script')))
        catalog = NARRATION.replace('〔演示：提示词工作台', '先说小红书。\n\n〔演示：提示词工作台') \
            .replace('〔演示：都行', '再说 PPT。\n\n〔演示：都行') \
            .replace('〔画面：飘入式', '最后是动画。\n\n〔画面：飘入式')
        self.assertIn('flat_catalog_transitions', codes(precheck.run(project(self.tmp/'cat', narration=catalog), 'script')))

    def test_pain_word_without_note_warns_in_narration_but_blocks_in_table(self):
        bare = NARRATION.replace('〔画面：白底三蓝框的 PPT 原件，左右并排装上 Skill 后的版本〕\n', '')
        root = project(self.tmp/'ep', narration=bare)
        report = precheck.run(root, 'script')
        self.assertIn('unpaired_pain_point_visual', codes(report, 'warnings'))
        self.assertNotIn('unpaired_pain_point_visual', codes(report))
        subprocess.run([str(SCRIPTS/'split-narration.sh'), str(root/'narration.md')], check=True, capture_output=True)
        self.assertIn('unpaired_pain_point_visual', codes(precheck.run(root, 'script')))

    def test_missing_both_files_is_input_error_and_pipe_is_refused(self):
        (self.tmp/'empty').mkdir()
        self.assertEqual(precheck.main(['--project', str(self.tmp/'empty'), '--stage', 'script']), 2)
        root = project(self.tmp/'pipe', narration=NARRATION.replace('看着就廉价', '看着就廉价 | 很丑'))
        done = subprocess.run([sys.executable, str(SCRIPTS/'narration_to_script.py'), str(root/'narration.md')],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertFalse((root/'script.md').exists())


if __name__ == '__main__':
    unittest.main()

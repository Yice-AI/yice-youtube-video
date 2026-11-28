#!/usr/bin/env python3
"""制片前置三关：包装（标题承诺）、口播稿、素材池。任何一关不过，不进入下一步。

  packaging  未通过严禁写分镜
  script     未通过严禁跑配音
  assets     未通过严禁跑 assemble-episode.sh

只依赖标准库与 ffmpeg/ffprobe。返回码：全部通过 0，任一关不过 1，参数或文件缺失 2。
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

STAGES = ('packaging', 'script', 'assets')

# ---------- 包装 ----------
BLAND_TITLE_PATTERNS = (
    '怎么选', '如何选择', '对比评测', '评测对比', '两种格式', '使用指南', '入门教程', '浅谈', '初探',
    '简介', '介绍一下', '学习笔记', '心得体会', '一文读懂', '详解', '概述', '总结一下',
)
NARROW_GATEKEEP_RE = re.compile(
    r'^(?:什么是|一文看懂|深入理解)\s*[A-Za-z0-9\u4e00-\u9fa5_-]{2,14}[？?]?$|源码剖析|架构拆解|底层原理解析|协议规范详解|API\s*参数详解'
)
OUTCOME_RESCUE_RE = re.compile(r'做出|搞定|省下|免费|白嫖|一句话|不用写代码|不会写代码|零门槛|秒变|直接用')
HOOK_PATTERN = re.compile(
    r'\d|[零一二两三四五六七八九十百千万]+(个|款|种|倍|分钟|秒|块|元)|别再|不用|免费|白嫖|省|秒|爆|神器|翻车|踩坑|'
    r'真相|实测|竟然|居然|告别|狠|直接|一句话|再也|终于|必看|彻底|吊打|干掉|丑|惊艳|[!！?？]')
TITLE_PREFIX = re.compile(r'^.*?[｜|]\s*')

# 品类词典：用于判断标题承诺和正文是否讲的是同一类事情。
CATEGORIES = {
    '演示汇报': ('PPT', 'ppt', '幻灯片', '演示文稿', '演示稿', '汇报', '述职', '周报', '投屏', '讲方案', 'Keynote', 'keynote', 'slides', 'Slides'),
    '视频剪辑': ('视频', '短片', '剪辑', '宣传片', '成片', '时间轴', 'MP4', 'mp4', '动画片', '口播'),
    '社媒封面': ('小红书', '公众号', '社媒', '封面', '海报', '配图', '套图', '朋友圈', '抖音', '推文'),
    '网站页面': ('网站', '官网', '落地页', '着陆页', '克隆网站', '建站'),
    '生图修图': ('生图', '修图', '抠图', '画图', '插画', '绘图'),
    '文字写作': ('文案', '写作', '文章', '论文', '写稿'),
    '编程开发': ('写代码', '编程', '爬虫', '部署', '小程序', '后端'),
    '数据表格': ('Excel', 'excel', '表格', '数据分析', '报表'),
    '音频配音': ('配音', '音乐', '播客', '语音'),
}
DRIFT_LIMIT = 0.5

# ---------- 口播稿 ----------
MAKER_TOPIC = re.compile(r'爬虫|自动化脚本|Playwright|Puppeteer|无头浏览器|headless|脚本开发|写脚本')
NUM = r'[\d零〇一二两三四五六七八九十百点\.]+'
MAKER_LEAKS = (
    ('批量截图/导图', re.compile(r'批量(截图|截屏|导图|导出图片?|抓图)'), None),
    ('截图脚本', re.compile(r'截图脚本|用脚本(批量)?(截|导|抓)'), None),
    ('截图等待秒数', re.compile(rf'等(待)?\s*{NUM}\s*(毫秒|秒)'), re.compile(r'截|快门|导图|脚本|抓图|渲染')),
    ('sleep 延迟', re.compile(r'\bsleep\b|setTimeout|毫秒(级)?延迟'), None),
    ('无头浏览器', re.compile(r'无头浏览器|headless', re.I), None),
    ('临时目录', re.compile(r'临时目录|tmp\s*目录|缓存目录'), None),
    ('配置字段', re.compile(r'字段名|JSON\s*字段|配置字段|填字段'), None),
    ('脚手架内部', re.compile(r'脚手架|清单文件|manifest', re.I), None),
    ('渲染进程', re.compile(r'渲染进程|并发数|workers?\b', re.I), None),
)
META_OPENERS = re.compile(r'大家好[，, ]?我是|哈喽大家好|欢迎来到|今天我们来聊|今天(我们)?(来)?(聊聊|讲讲|说说)|废话不多说')
EARLY_COMMANDS = re.compile(
    r'git\s+clone|npm\s+(i|install)\b|npx\s|pip3?\s+install|brew\s+install|uv\s+(pip|run|tool)|curl\s+-|~/\.|/Users/|[A-Z]:\\')
SPEECH_CHARS_PER_SEC = 4.5
PAIN_WORDS = re.compile(r'难看|丑|重做|废片|模板感|翻车|死板|廉价|反例|灾难')
COUNTER_VISUAL = re.compile(
    r'反例|丑|难看|翻车|改前|修改前|[Bb]efore|BEFORE|默认直出|原件|红叉|对比|[Vv][Ss]|斜切|擦除|前后|土味|'
    r'粘连|发黑|抢拍|死图|糊|模板感|失败|报错|原稿|旧版|直出')
CONTRAST_RECIPES = {'split_wipe_compare', 'split_compare_wipe', 'prompt_iter_workbench', 'cold_open_ab',
                    'literal_action_stage', 'bitmap_lock_glitch'}
CONTRAST_TAGS = re.compile(r'反例|改前|修改前|before|翻车|对比|丑|bad', re.I)
QUOTED = re.compile(r'[「“"『‘]([^」”"』’]{4,})[」”"』’]')
PROMPT_VERBS = re.compile(r'输入|提示词|指令|加上一句|加一句|改成|告诉它|对它说|喂给它|丢给它|让它')
CHANGE_WORDS = re.compile(r'前后|改前|改后|之前|之后|秒变|变成|直出|默认|精修|对比|反差|立刻|马上')
LLM_HEDGING_RE = re.compile(r'一般来说|见仁见智|仁者见仁|因人而异|各有千秋吧?|平分秋色吧?|看个人喜好吧?|某种程度上来说|仅供参考哈?')
VERSION_DECIMAL_RE = re.compile(r'(?:[vV]\d+\.\d+(?:\.\d+)?|(?:Claude|GPT|Gemini|Qwen|DeepSeek|Python|Node|Apache|MIT|Web)\s*[-A-Za-z]*\s*\d+\.\d+|\b\d+\s*[:：比]\s*\d+\b)', re.I)
RAW_DECIMAL_RE = re.compile(r'\b\d+\.\d+%?')
HONEST_TRADEOFF_RE = re.compile(r'缺点|毛病|短板|坑|局限|不适合|别用|但要注意|只允许|非商业|非商用|需要授权|不能直接|没法直接|弱点|代价')

# ---------- 素材 ----------
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
VIDEO_EXT = {'.mp4', '.webm', '.mov'}
SKIP_DIRS = {'fonts', 'node_modules', '__pycache__', '.git'}
MIN_IMAGE_SIDE = (960, 540)
DHASH_DISTANCE = 8
MIN_CLUSTERS = 8
MIN_EXTERNAL_HOSTS = 2
MIN_EXTERNAL_SHARE = 0.25
EXTERNAL_ROUTES = re.compile(r'harvest|showcase|collect-entity|entity|capture-web|official|press|stock|open-media|commons', re.I)
LOCAL_HOSTS = {'', 'localhost', '127.0.0.1', '0.0.0.0', '::1'}


class InputError(Exception):
    pass


def issue(code, message, **detail):
    return dict(code=code, message=message, **detail)


# ---------- 读取 ----------

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


KEY_ALIASES = {
    'title': ('title', '标题'), 'hook': ('hook', '钩子', '封面钩子'),
    'viewer_promise': ('viewer_promise', '观众承诺', '承诺', '观众获得感'),
    'target_keywords': ('target_keywords', '目标关键词', '关键词', '搜索关键词'),
    'episode_kind': ('episode_kind', '题材类型'),
}


def parse_packaging_md(text):
    found, pending = {}, None
    lookup = {alias.lower(): key for key, aliases in KEY_ALIASES.items() for alias in aliases}
    first_h1 = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = re.match(r'^(#{1,6})\s*(.+?)\s*$', line)
        if heading:
            name = heading.group(2).strip('*：: ').lower()
            if name in lookup:
                pending = lookup[name]
                continue
            if heading.group(1) == '#' and first_h1 is None:
                first_h1 = heading.group(2)
            pending = None
            continue
        pair = re.match(r'^[-*]?\s*\**([^:：*]+?)\**\s*[:：]\s*(.+)$', line)
        if pair and pair.group(1).strip().lower() in lookup:
            found.setdefault(lookup[pair.group(1).strip().lower()], pair.group(2).strip())
            pending = None
            continue
        if pending:
            found.setdefault(pending, line.lstrip('-* ').strip())
            pending = None
    if 'title' not in found and first_h1:
        found['title'] = first_h1
    if isinstance(found.get('target_keywords'), str):
        found['target_keywords'] = [w for w in re.split(r'[,，、/\s]+', found['target_keywords']) if w]
    return found


def load_packaging(project, script):
    source = None
    data = {}
    if (project/'packaging.json').is_file():
        data = read_json(project/'packaging.json') or {}
        source = 'packaging.json'
    elif (project/'packaging.md').is_file():
        data = parse_packaging_md((project/'packaging.md').read_text(encoding='utf-8'))
        source = 'packaging.md'
    if not data.get('title'):
        manifest = read_json(project/'episode-manifest.json') or {}
        if manifest.get('title'):
            data['title'], source = manifest['title'], source or 'episode-manifest.json'
        elif script and script['title']:
            data['title'], source = script['title'], source or 'script.md'
    return data, source


def clean_narration(text):
    return re.sub(r'〔[^〕]*〕', '', text).replace('**', '').strip()


def parse_script(path):
    title, chapters, current = None, [], None
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith('# ') and title is None:
            title = TITLE_PREFIX.sub('', line[2:].strip())
            continue
        if line.startswith('## '):
            current = dict(title=line[3:].strip(), scenes=[])
            chapters.append(current)
            continue
        if not (line.startswith('|') and current is not None):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2 or set(cells[0]) <= set('-: ') or cells[0] in ('幕号', '幕', 'id', 'ID'):
            continue
        raw_text = cells[1]
        notes = ' '.join(re.findall(r'〔画面[:：]([^〕]*)〕', raw_text))
        visual = ' '.join(filter(None, [cells[2] if len(cells) > 2 else '', notes]))
        current['scenes'].append(dict(id=cells[0], text=clean_narration(raw_text), visual=visual,
                                      chapter=len(chapters)))
    return dict(title=title, chapters=chapters,
                scenes=[s for c in chapters for s in c['scenes']])


def shot_signals(project):
    """把分镜里的对比/反例镜头按幕号汇总，供“痛点配反例画面”核对。"""
    signals = {}

    def add(key, recipe, tags):
        if key is None:
            return
        hit = recipe in CONTRAST_RECIPES or bool(CONTRAST_TAGS.search(' '.join(map(str, tags))))
        signals[str(key)] = signals.get(str(key), False) or hit

    manifest = read_json(project/'episode-manifest.json') or {}
    for shot in manifest.get('shots', []) if isinstance(manifest, dict) else []:
        spec = shot.get('spatial_spec') or shot.get('onetake_spec') or {}
        tags = [shot.get('visual_subject', ''), shot.get('case_tag', ''), *(shot.get('semantic_tags') or [])]
        add(shot.get('anchor_cue_id'), spec.get('recipe') if isinstance(spec, dict) else None, tags)
    beats = read_json(project/'beats.json') or {}
    for beat in beats.get('scenes', []) if isinstance(beats, dict) else []:
        tags = [beat.get('label', ''), beat.get('note', ''), *(beat.get('tags') or [])]
        for sent in beat.get('sents', []) or []:
            add(sent, beat.get('recipe'), tags)
    return signals


# ---------- 第一关：包装 ----------

def categories_in(text):
    return {name: sum(text.count(word) for word in words) for name, words in CATEGORIES.items()
            if any(word in text for word in words)}


def promise_drift(packaging, script):
    promise = ' '.join(str(packaging.get(key) or '') for key in ('title', 'hook', 'viewer_promise'))
    promise += ' ' + ' '.join(packaging.get('target_keywords') or [])
    promised = set(categories_in(promise))
    if not promised or not script['scenes']:
        return None, {}
    total = off = 0
    off_scenes, off_categories = [], set()
    for scene in script['scenes']:
        hits = categories_in(scene['text'])
        on = sum(v for k, v in hits.items() if k in promised)
        other = {k: v for k, v in hits.items() if k not in promised}
        size = len(scene['text'])
        total += size
        if other:
            off += size
            off_categories |= set(other)
            off_scenes.append(scene['id'])
    ratio = off / total if total else 0.
    opening = ' '.join(s['text'] for c in script['chapters'][:2] for s in c['scenes'])
    opening_hit = bool(set(categories_in(opening)) & promised)
    metrics = dict(promised_categories=sorted(promised), off_promise_categories=sorted(off_categories),
                   off_promise_ratio=round(ratio, 3), off_promise_scenes=off_scenes,
                   opening_mentions_promise=opening_hit)
    if ratio > DRIFT_LIMIT or not opening_hit:
        reason = (f'标题只承诺了「{"、".join(sorted(promised))}」，但正文 {ratio:.0%} 的篇幅在讲'
                  f'「{"、".join(sorted(off_categories))}」' if ratio > DRIFT_LIMIT
                  else f'标题承诺「{"、".join(sorted(promised))}」，前两章却完全没讲到')
        return issue('promise_body_drift', reason + '。要么把标题改成能涵盖全片的说法，要么删掉跑题的段落。',
                     **metrics), metrics
    return None, metrics


def check_thumbnails(project, required):
    folder = project/'thumbnails'
    batches = sorted(p for p in folder.glob('batch-*') if p.is_dir()) if folder.is_dir() else []
    if not batches:
        return [issue('thumbnail_candidates_missing', '还没有封面候选，先跑 thumbnail.sh 生成至少 3 张候选和联系表。')] if required else []
    latest = batches[-1]
    candidates = sorted(latest.glob('candidate-*.*'))
    sheet = any(latest.glob('*contact-sheet*'))
    if len(candidates) >= 3 and sheet:
        return []
    return [issue('thumbnail_candidates_insufficient',
                  f'最新一批封面只有 {len(candidates)} 张候选{"" if sheet else "且缺联系表"}，至少要 3 张不同构图候选加联系表。',
                  batch=latest.name, candidates=len(candidates), contact_sheet=sheet)]


def stage_packaging(project, script, require_thumbnails):
    packaging, source = load_packaging(project, script)
    title = (packaging.get('title') or '').strip()
    if not title:
        raise InputError('找不到标题：请在项目里写 packaging.json 或 packaging.md（含 title），或给 script.md 写一级标题')
    errors, warnings = [], []
    if source not in ('packaging.json', 'packaging.md'):
        warnings.append(issue('packaging_file_missing', f'没有 packaging.json/md，标题暂取自 {source}；建议补齐钩子、观众承诺和关键词。'))
    bland = [p for p in BLAND_TITLE_PATTERNS if p in title]
    compact = re.sub(r'[\s\W_]', '', title)
    if bland:
        errors.append(issue('bland_explanatory_title',
                            f'标题「{title}」用了说明文腔「{"、".join(bland)}」，观众看不到结果或反差。改成“别再…/一句话…/N 款免费…”这类直接给结果的说法。',
                            title=title, patterns=bland))
    elif len(compact) < 10 and not HOOK_PATTERN.search(title):
        errors.append(issue('bland_explanatory_title',
                            f'标题「{title}」太短又没有痛点、收益或数字钩子。补上观众能得到的结果或一个数字。', title=title))
    maker_pkg = bool(packaging.get('maker_topic')) or bool(MAKER_TOPIC.search(title))
    if not maker_pkg and NARROW_GATEKEEP_RE.search(title) and not OUTCOME_RESCUE_RE.search(title):
        errors.append(issue('narrow_gatekeeping_title',
                            f'标题「{title}」给外行设了专业概念门槛，刷到前 2 秒过不了四问（跟我有关吗/在乎吗/反直觉吗/一秒看懂吗）。请改成“普通人处境 + 反常识结果”（例如“不会写代码的我，用 AI 做出了…”）。',
                            title=title))
    kws = [str(k).strip() for k in (packaging.get('target_keywords') or []) if str(k).strip()]
    search_surface = ' '.join(str(packaging.get(k) or '') for k in ('title', 'hook', 'viewer_promise', 'description'))
    if source in ('packaging.json', 'packaging.md'):
        if len(kws) < 2 or not any(k.lower() in search_surface.lower() for k in kws):
            warnings.append(issue('search_keywords_weak',
                                  'packaging 中建议至少配置 2 个核心搜索动作词（如 AI 视频、AI 做 PPT），并确保至少 1 个自然出现在标题或简介承诺中，方便搜索长尾与商务检索。',
                                  target_keywords=kws))
    metrics = dict(title=title, source=source, content_track=packaging.get('content_track', 'wide_funnel'))
    if script:
        drift, drift_metrics = promise_drift(packaging, script)
        metrics.update(drift_metrics)
        if drift:
            errors.append(drift)
    errors += check_thumbnails(project, require_thumbnails)
    return dict(ok=not errors, errors=errors, warnings=warnings, metrics=metrics)


# ---------- 第二关：口播稿 ----------

def is_tutorial(project, packaging, script):
    manifest = read_json(project/'episode-manifest.json') or {}
    kind = packaging.get('episode_kind') or (manifest.get('episode_kind') if isinstance(manifest, dict) else None)
    if kind:
        return kind == 'tool_tutorial'
    return bool(re.search(r'教程|手把手|神器|工具|Skill|开源|实测|安装', script['title'] or ''))


def stage_script(project, script):
    packaging, _ = load_packaging(project, script)
    errors, warnings = [], []
    maker_topic = bool(packaging.get('maker_topic')) or bool(MAKER_TOPIC.search(
        ' '.join(str(packaging.get(k) or '') for k in ('title', 'viewer_promise')) + ' ' + (script['title'] or '')))
    if not maker_topic:
        for scene in script['scenes']:
            for sentence in re.split(r'(?<=[。！？!?；;])', scene['text']):
                hits = [(label, found.group(0)) for label, pattern, context in MAKER_LEAKS
                        for found in [pattern.search(sentence)]
                        if found and (context is None or context.search(sentence))]
                if hits:
                    quoted = '、'.join(f'{label}「{word}」' for label, word in hits)
                    errors.append(issue('maker_plumbing_leak',
                                        f'{scene["id"]} 幕把制作端内部细节（{quoted}）念给观众听，观众不关心。删掉，或改成观众能照做的一步。',
                                        scene_id=scene['id'], sentence=sentence.strip(), patterns=[h[0] for h in hits]))
    for scene in script['scenes'][:2]:
        found = META_OPENERS.search(scene['text'])
        if found:
            errors.append(issue('slow_or_meta_opener',
                                f'{scene["id"]} 幕用「{found.group(0)}」慢热开场，前 15 秒应直接甩成品或结果。',
                                scene_id=scene['id'], phrase=found.group(0)))
    budget = 60 * SPEECH_CHARS_PER_SEC
    spent = 0.
    for scene in script['scenes']:
        if spent >= budget:
            break
        found = EARLY_COMMANDS.search(scene['text'])
        if found:
            errors.append(issue('slow_or_meta_opener',
                                f'{scene["id"]} 幕约第 {spent / SPEECH_CHARS_PER_SEC:.0f} 秒就念命令或文件路径「{found.group(0)}」，前 60 秒只讲结果和痛点，命令放简介或后面的实操段。',
                                scene_id=scene['id'], phrase=found.group(0)))
        spent += len(scene['text'])
    signals = shot_signals(project)
    for scene in script['scenes']:
        found = PAIN_WORDS.search(scene['text'])
        if not found:
            continue
        if COUNTER_VISUAL.search(scene['visual']) or signals.get(scene['id']):
            continue
        errors.append(issue('unpaired_pain_point_visual',
                            f'{scene["id"]} 幕口播说「{found.group(0)}」，但没规划对应的真实反例画面。在第 3 列写清放哪张难看原件或改前画面，或给这一幕配对比镜头。',
                            scene_id=scene['id'], word=found.group(0)))
    for scene in script['scenes']:
        hedge = LLM_HEDGING_RE.search(scene['text'])
        if hedge:
            errors.append(issue('llm_hedging_fluff',
                                f'{scene["id"]} 幕出现大模型和稀泥叠甲词「{hedge.group(0)}」。观众不想听两边不得罪的废话，请直接给出明确判断或适用边界。',
                                scene_id=scene['id'], phrase=hedge.group(0)))
        scrubbed = VERSION_DECIMAL_RE.sub('', scene['text'])
        decimals = RAW_DECIMAL_RE.findall(scrubbed)
        if len(decimals) >= 4:
            errors.append(issue('decimal_overload',
                                f'{scene["id"]} 幕单段塞入了 {len(decimals)} 个精确小数（{"、".join(decimals[:4])}），观众听完记不住。请改成“省一半、成本只有六分之一、十道题答对八道”这类体感比值。',
                                scene_id=scene['id'], decimals=decimals))
        elif len(decimals) == 3:
            warnings.append(issue('decimal_overload',
                                  f'{scene["id"]} 幕出现 3 个精确小数（{"、".join(decimals)}），建议换成更易记的体感分数。',
                                  scene_id=scene['id'], decimals=decimals))
    tutorial = is_tutorial(project, packaging, script)
    loops = []
    if tutorial and len(script['chapters']) >= 3:
        for index, chapter in enumerate(script['chapters'], 1):
            text = ' '.join(s['text'] for s in chapter['scenes'])
            prompt = bool(QUOTED.search(text)) and bool(PROMPT_VERBS.search(text)) or bool(re.search(r'(提示词|指令)[:：]', text))
            if prompt and CHANGE_WORDS.search(text):
                loops.append(index)
        if len(loops) < 2:
            errors.append(issue('missing_hands_on_prompt_loop',
                                f'教程只有 {len(loops)} 章给出了观众能照抄的中文提示词和前后变化，至少要 2 章。写出“输入「…」→ 默认直出哪里差 → 加一句「…」后变成什么样”。',
                                chapters_with_loop=loops))
        if len(script['chapters']) >= 4:
            full_text = ' '.join(s['text'] for s in script['scenes'])
            if not HONEST_TRADEOFF_RE.search(full_text):
                warnings.append(issue('missing_honest_tradeoff',
                                      '多工具教程全篇未见任何真实短板/适用边界提醒（如协议限制、不适合场景），全吹成神仙水会损失活人信任感，建议直接点明各工具边界。'))
    metrics = dict(chapters=len(script['chapters']), scenes=len(script['scenes']),
                   tutorial=tutorial, maker_topic=maker_topic, prompt_loop_chapters=loops)
    return dict(ok=not errors, errors=errors, warnings=warnings, metrics=metrics)


# ---------- 第三关：素材 ----------

def probe_size(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height:format=duration', '-of', 'json', str(path)],
                         capture_output=True, text=True)
    data = json.loads(out.stdout or '{}')
    stream = (data.get('streams') or [{}])[0]
    duration = float((data.get('format') or {}).get('duration') or 0) if path.suffix.lower() in VIDEO_EXT else 0.
    return int(stream.get('width') or 0), int(stream.get('height') or 0), duration


def dhash(path, at=None):
    """ffmpeg 缩成 9×8 灰度，按相邻像素明暗得到 64 位指纹。"""
    cmd = ['ffmpeg', '-v', 'error', '-threads', '1']
    if at is not None:
        cmd += ['-ss', f'{at:.3f}']
    cmd += ['-i', str(path), '-frames:v', '1', '-vf', 'scale=9:8:flags=area,format=gray',
            '-f', 'rawvideo', '-']
    pixels = subprocess.run(cmd, capture_output=True).stdout
    if len(pixels) < 72:
        return None
    value = 0
    for row in range(8):
        for col in range(8):
            value = value << 1 | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return value


def load_ledger(project):
    path = project/'asset-ledger.jsonl'
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def ledger_units(project, ledger):
    units = {}
    for row in ledger or []:
        for key in ('path', 'stillPath', 'trackPath', 'file', 'output'):
            value = row.get(key)
            if isinstance(value, str) and value:
                full = Path(value) if Path(value).is_absolute() else project/value
                identity = str(row.get('id') or value)
                units[str(full.resolve())] = identity
                units.setdefault(str(full.resolve().with_suffix('')), identity)
    return units


def collect_assets(project, ledger):
    units = ledger_units(project, ledger)
    assets = []
    for root in ('media', 'assets'):
        base = project/root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.is_symlink() or SKIP_DIRS & set(path.relative_to(project).parts):
                continue
            ext = path.suffix.lower()
            if ext not in IMAGE_EXT | VIDEO_EXT:
                continue
            width, height, duration = probe_size(path)
            if ext in IMAGE_EXT and (max(width, height) < MIN_IMAGE_SIDE[0] or min(width, height) < MIN_IMAGE_SIDE[1]):
                continue
            fingerprint = dhash(path, duration / 2 if ext in VIDEO_EXT else None)
            if fingerprint is None:
                continue
            rel = str(path.relative_to(project))
            stem = path.resolve().with_suffix('')
            unit = units.get(str(path.resolve())) or units.get(str(stem)) or str(path.with_suffix('').relative_to(project))
            assets.append(dict(path=rel, kind='video' if ext in VIDEO_EXT else 'image', unit=unit,
                               dhash=f'{fingerprint:016x}', sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return assets


def cluster(assets, distance):
    parent = list(range(len(assets)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hashes = [int(a['dhash'], 16) for a in assets]
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            if assets[i]['sha256'] == assets[j]['sha256'] or bin(hashes[i] ^ hashes[j]).count('1') <= distance:
                parent[find(j)] = find(i)
    groups = {}
    for i, asset in enumerate(assets):
        groups.setdefault(find(i), []).append(asset)
    return list(groups.values())


def external_sources(ledger):
    footage = [row for row in ledger or [] if 'thumbnail' not in str(row.get('kind', ''))]
    external, hosts = [], set()
    for row in footage:
        url = str(row.get('url') or row.get('sourceUrl') or row.get('source_url') or '')
        host = (urlparse(url).hostname or '') if url.startswith('http') else ''
        route = ' '.join(str(row.get(k) or '') for k in ('kind', 'sourceType', 'tool', 'route'))
        if not host and not url and EXTERNAL_ROUTES.search(route):
            host = str(row.get('source') or '')
        if host in LOCAL_HOSTS:
            continue
        external.append(row.get('id'))
        hosts.add(host)
    return footage, external, hosts


def stage_assets(project, script, distance, min_clusters):
    packaging, _ = load_packaging(project, script) if script else ({}, None)
    if not (project/'media').is_dir() and not (project/'assets').is_dir():
        raise InputError('项目里没有 media/ 或 assets/ 素材目录')
    ledger = load_ledger(project)
    assets = collect_assets(project, ledger)
    groups = cluster(assets, distance)
    errors, warnings = [], []
    if not assets:
        errors.append(issue('insufficient_visual_clusters', 'media/ 和 assets/ 里没有可用的视频或高清图片。'))
    for group in groups:
        units = sorted({a['unit'] for a in group})
        if len(units) >= 2:
            errors.append(issue('duplicate_asset_disguise',
                                f'{len(units)} 个不同名字的素材长得几乎一样（同一套画面换名存了多份）：{"、".join(a["path"] for a in group)}。只留一份，其余换成真正不同的画面。',
                                files=[a['path'] for a in group], units=units))
    manifest = read_json(project/'episode-manifest.json') or {}
    multi_tool = bool(packaging.get('multi_tool')) or packaging.get('tutorial_scope') == 'multi_tool' \
        or (isinstance(manifest, dict) and manifest.get('tutorial_scope') == 'multi_tool') \
        or bool(script and len(script['chapters']) >= 4)
    footage, external, hosts = external_sources(ledger)
    metrics = dict(assets=len(assets), visual_clusters=len(groups), multi_tool=multi_tool,
                   ledger_entries=len(footage), external_entries=len(external), external_hosts=sorted(hosts))
    if multi_tool:
        if len(groups) < min_clusters:
            errors.append(issue('insufficient_visual_clusters',
                                f'多工具教程只有 {len(groups)} 组真正不同的画面，至少要 {min_clusters} 组。去官网、论文页、仓库演示抓更多真实高光。',
                                visual_clusters=len(groups), required=min_clusters))
        share = len(external) / len(footage) if footage else 0.
        if ledger is None or len(hosts) < MIN_EXTERNAL_HOSTS or share < MIN_EXTERNAL_SHARE:
            errors.append(issue('missing_external_showcase',
                                f'素材几乎全是本地自己做的页面：外部真实来源只有 {len(hosts)} 个网站、占 {share:.0%}。'
                                f'至少要 {MIN_EXTERNAL_HOSTS} 个外部来源、占 {MIN_EXTERNAL_SHARE:.0%} 以上，用 harvest-showcase-media.sh、collect-entity.sh 或 capture-web.mjs 去采。',
                                external_hosts=sorted(hosts), external_share=round(share, 3)))
    if ledger is None:
        warnings.append(issue('asset_ledger_missing', '没有 asset-ledger.jsonl，素材来源和授权无法核对。'))
    return dict(ok=not errors, errors=errors, warnings=warnings, metrics=metrics,
                clusters=[[a['path'] for a in g] for g in groups])


# ---------- 入口 ----------

def run(project, stage='all', require_thumbnails=False, distance=DHASH_DISTANCE, min_clusters=MIN_CLUSTERS):
    project = Path(project).expanduser().resolve()
    if not project.is_dir():
        raise InputError(f'项目目录不存在：{project}')
    wanted = STAGES if stage == 'all' else (stage,)
    script_path = project/'script.md'
    if 'script' in wanted and not script_path.is_file():
        raise InputError('缺少 script.md，第二关无法检查')
    script = parse_script(script_path) if script_path.is_file() else None
    stages = {}
    if 'packaging' in wanted:
        stages['packaging'] = stage_packaging(project, script, require_thumbnails)
    if 'script' in wanted:
        stages['script'] = stage_script(project, script)
    if 'assets' in wanted:
        stages['assets'] = stage_assets(project, script, distance, min_clusters)
    return dict(ok=all(s['ok'] for s in stages.values()), project=project.name, stage=stage, stages=stages)


def render_text(report):
    lines = [f'前置检查 {report["project"]}：{"全部通过" if report["ok"] else "未通过"}']
    for name, result in report['stages'].items():
        lines.append(f'[{name}] {"通过" if result["ok"] else "不通过"}')
        for item in result['errors']:
            lines.append(f'  ✗ {item["code"]}：{item["message"]}')
        for item in result['warnings']:
            lines.append(f'  ! {item["code"]}：{item["message"]}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='制片前置三关检查')
    parser.add_argument('--project', required=True)
    parser.add_argument('--stage', choices=(*STAGES, 'all'), default='all')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--require-thumbnails', action='store_true')
    parser.add_argument('--dhash-distance', type=int, default=DHASH_DISTANCE)
    parser.add_argument('--min-clusters', type=int, default=MIN_CLUSTERS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        report = run(args.project, args.stage, args.require_thumbnails, args.dhash_distance, args.min_clusters)
    except InputError as exc:
        print(f'precheck-episode：{exc}', file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    print(text if args.json else render_text(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())

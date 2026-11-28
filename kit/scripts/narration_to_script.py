#!/usr/bin/env python3
"""把定稿的散文口播母稿 narration.md 无损拆成 script.md 分镜表。

母稿约定：
  # 主标题
  ## 01 章节名            ← 两位数字开头的二级标题才是口播章节
  一段连续口播……
  〔画面：……〕            ← 单独一行的画面/演示提示，落到紧随其后的那段口播
  ## 事实与仓库核对表      ← 不以数字开头的二级标题（包装、简介、核对表）不进口播

拆表时旁白一字不改：每段按自然句群切成若干幕，〔…〕提示落入第 3 列。
用法：narration_to_script.py narration.md [--output script.md] [--max-chars 90]
"""
import argparse
from pathlib import Path
import re
import sys

CHAPTER_RE = re.compile(r'^##\s+(\d{1,2})\b\s*(.*)$')
NOTE_RE = re.compile(r'〔([^〕]*)〕')
NOTE_ONLY_RE = re.compile(r'^(?:〔[^〕]*〕\s*)+$')
VISUAL_LABEL_RE = re.compile(r'^(?:画面|演示|录屏|实录|镜头)[:：]\s*')
SENTENCE_END_RE = re.compile(r'(?<=[。！？!?…])(?![”’」』）)…])|(?<=[。！？!?][”’」』）)])')  # 分号不断句：它常连着一串并列
TITLE_PREFIX = re.compile(r'^.*?[｜|]\s*')
MIN_CHARS, MAX_CHARS = 36, 90


def note_text(raw):
    """〔画面：A〕〔演示：B〕 → 'A；B'。"""
    return '；'.join(VISUAL_LABEL_RE.sub('', n).strip() for n in NOTE_RE.findall(raw) if n.strip())


def parse_narration(path):
    """返回 dict(title, chapters=[{num, title, paragraphs=[{text, notes:[(pos, note)]}]}])。

    pos 是该画面提示在本段口播里的字符位置（0 表示段首），用来把提示落到对应的句群。
    """
    title, chapters, current, pending = None, [], None, []
    buffer = []

    def flush():
        nonlocal buffer, pending
        if current is None or not buffer:
            buffer = []
            return
        raw = ' '.join(buffer)
        buffer = []
        if NOTE_ONLY_RE.match(raw):
            pending.append(note_text(raw))
            return
        notes, text, cursor = [(0, n) for n in pending], '', 0
        pending = []
        for part in re.split(r'(〔[^〕]*〕)', raw):
            if part.startswith('〔'):
                notes.append((len(text), note_text(part)))
            else:
                text += part.replace('**', '')
        text = re.sub(r'[ \t]*\n[ \t]*', '', text).strip()
        current['paragraphs'].append(dict(text=text, notes=[(min(p, len(text)), n) for p, n in notes if n]))

    for raw_line in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if line.startswith('# ') and title is None:
            title = TITLE_PREFIX.sub('', line[2:].strip())
            continue
        if line.startswith('## '):
            flush()
            if current is not None and pending and current['paragraphs']:
                current['paragraphs'][-1]['notes'].extend((len(current['paragraphs'][-1]['text']), n) for n in pending)
            pending = []
            found = CHAPTER_RE.match(line)
            current = dict(num=int(found.group(1)), title=found.group(2).strip(), paragraphs=[]) if found else None
            if current is not None:
                chapters.append(current)
            continue
        if line.startswith('#') or line.startswith('>') or line.startswith('|') or line.startswith('---'):
            flush()
            continue
        if not line:
            flush()
            continue
        if current is not None:
            buffer.append(line)
    flush()
    if current is not None and pending and current['paragraphs']:
        current['paragraphs'][-1]['notes'].extend((len(current['paragraphs'][-1]['text']), n) for n in pending)
    return dict(title=title, chapters=chapters)


def sentence_groups(text, min_chars=MIN_CHARS, max_chars=MAX_CHARS):
    """按句末标点切句，再把短句并成 min..max 字的句群；返回 [(start, end)]，拼回去与原文一字不差。"""
    bounds, start = [], 0
    for found in SENTENCE_END_RE.finditer(text):
        end = found.end()
        if end > start:
            bounds.append((start, end))
            start = end
    if start < len(text):
        bounds.append((start, len(text)))
    groups = []
    for s, e in bounds:
        if groups and (e - groups[-1][0] <= max_chars) and (groups[-1][1] - groups[-1][0] < min_chars):
            groups[-1] = (groups[-1][0], e)
        else:
            groups.append((s, e))
    if len(groups) > 1 and groups[-1][1] - groups[-1][0] < min_chars // 2 and \
            groups[-1][1] - groups[-2][0] <= max_chars + min_chars // 2:
        groups[-2:] = [(groups[-2][0], groups[-1][1])]
    return groups


def split_rows(doc, min_chars=MIN_CHARS, max_chars=MAX_CHARS):
    """返回 [{chapter_title, rows:[(id, text, visual)]}]。"""
    out = []
    for chapter in doc['chapters']:
        rows, n = [], 0
        for para in chapter['paragraphs']:
            groups = sentence_groups(para['text'], min_chars, max_chars)
            inherited = ''
            for gi, (s, e) in enumerate(groups):
                own = [note for pos, note in para['notes']
                       if (s <= pos < e) or (gi == 0 and pos < s) or (gi == len(groups) - 1 and pos >= e)]
                n += 1
                if own:
                    visual = '；'.join(own)
                    inherited = visual
                else:
                    visual = f'（续上）{inherited}' if inherited else ''
                rows.append((f'{chapter["num"]}-{n}', para['text'][s:e].strip(), visual))
        out.append(dict(title=f'{chapter["num"]:02d} {chapter["title"]}'.strip(), rows=rows))
    return out


def render_script(doc, min_chars=MIN_CHARS, max_chars=MAX_CHARS):
    parts = [f'# {doc["title"] or "未命名"}', '']
    for chapter in split_rows(doc, min_chars, max_chars):
        parts += [f'## {chapter["title"]}', '', '| 幕号 | 旁白 | 画面 |', '| --- | --- | --- |']
        for rid, text, visual in chapter['rows']:
            if '|' in text or '|' in visual:
                raise ValueError(f'{rid} 含竖线“|”，会打断表格，请在母稿里换成别的符号')
            parts.append(f'| {rid} | {text} | {visual} |')
        parts.append('')
    return '\n'.join(parts)


def spoken_text(doc):
    """母稿全部口播（不含画面提示），用于核对拆表是否无损。"""
    return ''.join(p['text'] for c in doc['chapters'] for p in c['paragraphs'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='把散文口播母稿 narration.md 无损拆成 script.md 分镜表')
    parser.add_argument('narration')
    parser.add_argument('--output', help='默认写到母稿同目录的 script.md')
    parser.add_argument('--min-chars', type=int, default=MIN_CHARS)
    parser.add_argument('--max-chars', type=int, default=MAX_CHARS)
    args = parser.parse_args(argv)
    src = Path(args.narration)
    if not src.is_file():
        print(f'narration_to_script：找不到 {src}', file=sys.stderr)
        return 2
    doc = parse_narration(src)
    if not doc['chapters']:
        print('narration_to_script：母稿里没有“## 01 章节名”这样的口播章节', file=sys.stderr)
        return 2
    try:
        table = render_script(doc, args.min_chars, args.max_chars)
    except ValueError as exc:
        print(f'narration_to_script：{exc}', file=sys.stderr)
        return 1
    joined = ''.join(t for c in split_rows(doc, args.min_chars, args.max_chars) for _, t, _ in c['rows'])
    if re.sub(r'\s', '', joined) != re.sub(r'\s', '', spoken_text(doc)):
        print('narration_to_script：拆表后口播与母稿不一致，已停止写出', file=sys.stderr)
        return 1
    out = Path(args.output) if args.output else src.with_name('script.md')
    out.write_text(table, encoding='utf-8')
    rows = sum(len(c['rows']) for c in split_rows(doc, args.min_chars, args.max_chars))
    chars = len(re.sub(r'\s', '', spoken_text(doc)))
    print(f'已写出 {out}：{len(doc["chapters"])} 章 {rows} 幕，口播 {chars} 字，与母稿一字不差')
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Explicit ASR exceptions, separate audit categories, and deterministic selection."""
import difflib
import math
import re
from functools import lru_cache

NUMBER = r'(?:\d+(?:\.\d+)?[万亿]?|[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二两三四五六七八九]+)?)'
DIGITS = dict(zip('零〇一二两三四五六七八九', [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
ENGLISH = {'Codex': ['CodeX', 'CODEX', 'Code X', 'codecs'],
           'Claude': ['Cloudo', 'Cloud', 'claude'],
           'Fireship': ['Fairship', 'Fire ship'],
           'Hugging Face': ['Hogging Face', 'HuggingFace'],
           'GitHub': ['Git Hub'], 'HyperFrames': ['Hyper Frames'], 'PPTX': ['PPT X', 'P P T X']}

# Conservative offline fallback. Sets contain one Mandarin reading including
# its tone. Numeral changes and characters with competing readings are not inferred.
READINGS = {
    char: reading for reading, group in {
        'zhēn': '针帧真珍', 'lù': '录路鹿', 'xiào': '效笑', 'cài': '菜蔡',
        'cǎi': '彩采踩', 'tā': '它他她', 'sù': '素速诉塑', 'zhàng': '账帐',
        'ruǎn': '软阮', 'liàn': '练炼链', 'hé': '合盒河', 'dìng': '定订锭',
        'jiǎn': '剪简减检捡', 'jiàn': '见建键件健', 'jì': '记计纪技际',
        'dú': '读独毒', 'yì': '译易意义异议', 'xiàng': '像象向项',
        'zài': '在再', 'xiān': '先仙', 'shì': '是式视试事市示', 'zhì': '制置智志质',
        'diàn': '电店垫', 'bù': '不布部步', 'yīn': '音因阴', 'gōng': '工公功',
        'zuò': '做作坐座', 'míng': '名明鸣', 'wén': '文闻纹', 'yuán': '原元源员',
        'suǒ': '所索锁', 'yóu': '由油游邮', 'lǐ': '里理礼李', 'shù': '述术树竖',
        'huì': '会汇绘惠', 'shū': '书输舒', 'chuán': '传船', 'shè': '摄设射社',
        'jī': '机基积激', 'tí': '提题', 'cháng': '常长尝', 'zhuāng': '装庄妆',
        'fēng': '风封峰蜂锋', 'róu': '柔揉', 'bǎn': '版板', 'zhèn': '阵振震镇',
        'xiàn': '现线县献限宪', 'chéng': '成程城呈诚承', 'shēng': '升声生牲',
        'gǎo': '稿搞镐', 'lán': '蓝栏兰拦篮', 'píng': '屏平评瓶凭', 'kuài': '块快筷',
        'shí': '实时识食石拾蚀',
    }.items() for char in group
}


@lru_cache(maxsize=2048)
def pronunciation(char):
    if not re.fullmatch(r'[\u4e00-\u9fff]', char) or numeric(char) is not None:
        return None
    try:
        from pypinyin import Style, pinyin
    except ImportError:
        return READINGS.get(char)
    readings = pinyin(char, style=Style.TONE, heteronym=True)[0]
    return readings[0] if len(readings) == 1 and readings[0] != char else READINGS.get(char)


def seeds(value):
    try:
        values = [int(item.strip()) for item in value.split(',')]
    except (ValueError, AttributeError):
        raise ValueError('seeds 须为逗号分隔的整数')
    if not values or len(set(values)) != len(values) or any(not 0 <= seed < 2**32 for seed in values):
        raise ValueError('seed 须唯一且在 0–2^32-1 之间')
    return values


def numeric(value):
    m = re.fullmatch(r'(\d+(?:\.\d+)?)([万亿])?', value)
    if m:
        scale = {'万': 1e4, '亿': 1e8, None: 1.0}[m[2]]
        return float(m[1]) * scale
    if '点' in value:
        whole, frac = value.split('点', 1)
        w_val = numeric(whole) if whole else 0.0
        if w_val is not None and frac and all(c in DIGITS for c in frac):
            return float(f"{int(w_val)}.{''.join(str(DIGITS[c]) for c in frac)}")
        return None
    if not re.fullmatch(r'[零〇一二两三四五六七八九十百千万亿]+', value):
        return None
    if all(char in DIGITS for char in value):
        return float(''.join(str(DIGITS[char]) for char in value))
    total = section = digit = 0
    has_unit = False
    for char in value:
        if char in DIGITS:
            if digit or (has_unit and digit):
                return None
            digit = DIGITS[char]
            if digit == 0 and not has_unit and not total:
                continue
        elif char in '十百千':
            has_unit = True
            section += (digit or 1) * {'十': 10, '百': 100, '千': 1000}[char]
            digit = 0
        elif char == '万':
            has_unit = True
            total += (section + digit) * 10000
            section = digit = 0
        else:
            has_unit = True
            total = (total + section + digit) * 100000000
            section = digit = 0
    return float(total + section + digit)


@lru_cache(maxsize=1)
def simplifier():
    try:
        from opencc import OpenCC
    except ImportError:
        table = str.maketrans("攝沒針員個兩邊這覺段間團隊裡裡說剪輯軟體樣視頻鏡頭開場實驗應該還錄終點時長", "摄没针员个两边这觉段间团队里里说剪辑软体样视频镜头开场实验应该还录终点时长")
        return lambda value: value.translate(table)
    return OpenCC('t2s').convert


def characters(value):
    value = simplifier()(value)
    value = value.translate(str.maketrans({'它': '他', '她': '他'}))
    return ''.join(char.lower() for char in value if char.isalnum())


def differences(expected, heard):
    expected, heard = characters(expected), characters(heard)
    return [{'kind': kind, 'expected': expected[a:b], 'heard': heard[c:d],
             'expected_start': a, 'heard_start': c}
            for kind, a, b, c, d in difflib.SequenceMatcher(None, expected, heard, autojunk=False).get_opcodes()
            if kind != 'equal']


def phrase_readings(text):
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        return [pronunciation(c) for c in text]
    return lazy_pinyin(text, style=Style.TONE3, neutral_tone_with_five=True,
                       errors=lambda chars: list(chars))


def audit(text, transcription, exceptions=None, threshold=.97, *, auto_homophone=False, pronunciations=None):
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError('ASR 匹配率阈值须在 (0,1]')
    raw = transcription.get('text')
    if raw is None:
        raw = ''.join(segment.get('text', ''.join(word['word'] for word in segment.get('words', [])))
                      for segment in transcription.get('segments', []))
    text, heard = simplifier()(text), simplifier()(raw)
    events, mappings = [], {}

    def replace(intended, recognized, kind, reason):
        nonlocal heard
        if not intended or not recognized:
            raise ValueError('ASR 放行短语不能为空')
        if intended == recognized or intended not in text:
            return
        actual = recognized
        if actual not in heard and kind == 'english_name':
            match = re.search(re.escape(recognized), heard, flags=re.IGNORECASE)
            if match:
                actual = match[0]
        if actual not in heard or actual == intended:
            return
        heard = heard.replace(actual, intended)
        # Keep original phrases for timestamp alignment, longest recognized first.
        mappings[intended] = actual
        events.append(dict(kind=kind, intended=intended, heard=actual, reason=reason))

    # Match complete number+unit phrases before isolated digits (3 must not eat 30).
    expected_units = list(re.finditer('(' + NUMBER + r')(兆字节|千字节|MB|KB|兆)', text, re.I))
    for match in list(re.finditer('(' + NUMBER + r')(兆字节|千字节|Mbps|MB|KB|兆|照)', heard, re.I))[::-1]:
        number, unit = match.groups()
        options = [item for item in expected_units if numeric(item[1]) == numeric(number)]
        for item in options:
            intended_unit = item[2].lower()
            aliases = {'兆': {'兆', 'mb', 'mbps', '照'}, '兆字节': {'兆字节', 'mb'},
                       '千字节': {'千字节', 'kb'}, 'mb': {'mb', '兆', '兆字节'},
                       'kb': {'kb', '千字节'}}
            if unit.lower() in aliases[intended_unit]:
                kind = 'homophone' if unit == '照' else 'number_unit'
                replace(item[0], match[0], kind, '同值数字单位写法；兆/Mbps 是已登记的 ASR 转写差异，朗读文本不改'
                        if unit.lower() == 'mbps' else '同值数字/单位；照→兆仅限数字单位位置')
                break
    # Equivalent percentage notation: 百分之七十三 <-> 73%
    expected_pct = [(m[0], numeric(m[1])) for m in re.finditer('百分之(' + NUMBER + ')', text)]
    for match in list(re.finditer('(' + NUMBER + r')%', heard))[::-1]:
        val = numeric(match[1])
        opts = list(dict.fromkeys(full for full, v in expected_pct if v is not None and v == val))
        if len(opts) == 1:
            replace(opts[0], match[0], 'number_unit', '同值百分比写法')
    # Equivalent ratio notation: 三比四 <-> 3:4 / 3-4
    expected_ratios = [(m[0], numeric(m[1]), numeric(m[2]))
                       for m in re.finditer('(' + NUMBER + ')比(' + NUMBER + ')', text)]
    for match in list(re.finditer('(' + NUMBER + r')\s*[:：/-]\s*(' + NUMBER + ')', heard))[::-1]:
        left, right = numeric(match[1]), numeric(match[2])
        opts = list(dict.fromkeys(full for full, a, b in expected_ratios
                                  if left is not None and right is not None and (a, b) == (left, right)))
        if len(opts) == 1:
            replace(opts[0], match[0], 'number_unit', '同值比例写法')
    expected_numbers = {}
    for match in re.finditer(NUMBER, text):
        expected_numbers.setdefault(numeric(match[0]), []).append(match[0])
    for match in list(re.finditer(r'\d+(?:\.\d+)?[万亿]?', heard))[::-1]:
        val = numeric(match[0])
        variants = list(dict.fromkeys(expected_numbers.get(val, [])))
        chosen = None
        if len(variants) == 1:
            chosen = variants[0]
        elif len(variants) > 1 and val == 2.0:
            nxt = heard[match.end():match.end() + 1]
            chosen = '两' if nxt in '秒家遍期段张个条次倍' and '两' in variants else variants[0]
        if chosen and chosen != match[0]:
            heard = heard[:match.start()] + chosen + heard[match.end():]
            mappings[chosen] = match[0]
            events.append(dict(kind='number_unit', intended=chosen, heard=match[0], reason='同值数字写法'))
    for intended, variants in ENGLISH.items():
        for variant in variants:
            replace(intended, variant, 'english_name', '明确英文专名别写')
    exceptions = exceptions or {}
    if not isinstance(exceptions, dict):
        raise ValueError('ASR 例外须为对象')
    categories = {'number_unit', 'english_name', 'homophone'}
    grouped = any(key in categories for key in exceptions)
    records = []
    if grouped:
        if set(exceptions) - categories:
            raise ValueError('例外类别只支持 number_unit/english_name/homophone')
        for kind, values in exceptions.items():
            if not isinstance(values, dict):
                raise ValueError('例外类别须为 原文→ASR别写 对象')
            for intended, recognized in values.items():
                variants = recognized if isinstance(recognized, list) else [recognized]
                records.extend((kind, intended, item) for item in variants)
    else:
        # Legacy flat mappings remain explicit, and are never silently fuzzy.
        for key, value in exceptions.items():
            variants = value if isinstance(value, list) else [value]
            if not isinstance(key, str) or any(not isinstance(item, str) for item in variants):
                raise ValueError('例外短语须为字符串')
            tag = 'english_name' if re.search('[A-Za-z]', key) else 'homophone'
            records.extend((tag, key, item) for item in variants)
    if any(not isinstance(row[1], str) or not isinstance(row[2], str) for row in records):
        raise ValueError('例外短语须为字符串')
    for kind, intended, recognized in sorted(records, key=lambda row: -len(row[2])):
        if kind == 'homophone' and len(characters(intended)) != len(characters(recognized)):
            continue
        a, b = numeric(intended), numeric(recognized)
        if a is not None and b is not None and a != b:
            continue  # Never waive a changed number, even via a legacy mapping.
        # ``百分之七十三`` contains the prefix ``百``; compare its numeric
        # payload with ``七十三%`` instead of treating that prefix as 100.
        intended_numeric_text = intended.replace('百分之', '')
        recognized_numeric_text = recognized.replace('%', '')
        intended_numbers = [numeric(match[0]) for match in re.finditer(NUMBER, intended_numeric_text)]
        heard_numbers = [numeric(match[0]) for match in re.finditer(NUMBER, recognized_numeric_text)]
        if intended_numbers and heard_numbers and intended_numbers != heard_numbers:
            continue
        replace(intended, recognized, kind, '调用者逐项提供的明确放行记录')
    normalized = characters(heard)
    if auto_homophone:
        words = set(re.findall(r'[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*', text))
        for word in sorted(words):
            letters = word.replace('-', '')
            if len(letters) < 2:
                continue
            pattern = r'(?<![A-Za-z0-9])' + r'[\s-]*'.join(map(re.escape, letters)) + r'(?![A-Za-z0-9])'
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match and match[0] != word:
                events.append(dict(kind='auto_homophone', intended=word, heard=match[0], reason='英文大小写、分词或连字符变体'))
        wanted_text=characters(text)
        marked=wanted_text
        for surface, reading in sorted((pronunciations or {}).items(), key=lambda pair: -len(pair[0])):
            if len(characters(surface)) == len(characters(reading)):
                marked=marked.replace(characters(surface),characters(reading))
        wanted_readings=phrase_readings(marked)
        heard_readings=phrase_readings(normalized)
        edited = list(normalized)
        for row in differences(text, heard):
            wanted, actual = row['expected'], row['heard']
            if row['kind'] != 'replace' or len(wanted) != len(actual):
                continue
            if not re.fullmatch(r'[一-鿿]+', wanted+actual) or re.search(NUMBER, wanted+actual):
                continue
            left, right = row['expected_start'], row['heard_start']
            if not all(a == b or (wanted_readings[left+i] and
                                   wanted_readings[left+i] == heard_readings[right+i])
                       for i, (a,b) in enumerate(zip(wanted,actual))):
                continue
            begin = row['heard_start']
            edited[begin:begin+len(actual)] = wanted
            events.append(dict(kind='auto_homophone', intended=wanted, heard=actual,
                               heard_start=begin, reason='与原稿逐字同音同调'))
        normalized = ''.join(edited)
    delta = differences(text, normalized)
    ratio = difflib.SequenceMatcher(None, characters(text), normalized, autojunk=False).ratio()
    return dict(ok=bool(characters(text)) and ratio >= threshold and not delta, ratio=ratio,
                threshold=threshold, differences=delta, raw_differences=differences(text, raw),
                events=events, number_unit=[e for e in events if e['kind'] == 'number_unit'],
                english_name=[e for e in events if e['kind'] == 'english_name'],
                homophone=[e for e in events if e['kind'] == 'homophone'],
                auto_homophone=[e for e in events if e['kind'] == 'auto_homophone'],
                homophone_suspect=[e for e in delta if e['kind'] != 'equal'],
                normalizations=dict(sorted(mappings.items(), key=lambda pair: -len(pair[1]))), raw_text=raw)


def rank(candidate):
    audit_result = candidate['asr']
    alerts = candidate['check']['alerts']
    return (not (audit_result['ok'] and not alerts), not audit_result['ok'],
            len(audit_result['differences']), len(alerts), -audit_result['ratio'], candidate['seed'])

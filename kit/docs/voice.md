# v7.2 配音生成、后期和韵律检测

`voice.sh` 每章多 seed 生成 → post → ASR 与韵律 check → 不通过就整句 repair（最多 3 轮）。只有全部章节匹配率达到阈值、差异已明确登记且零告警，才输出可组装的 `voice-manifest.json`、`voice-timing.json` 和 SRT。规则解释见 [配音规则](../../references/voice.md)。

## 环境

沿用 toolkit 的 MLX / Whisper 环境，另需 `numpy`、`scipy`、`soundfile`、`librosa` 和 PATH 中的 `ffmpeg`。安装器会把 `librosa==1.0.1`、`soundfile==0.14.0` 及缺失的 `scipy`、`numpy` 装入现有 `asr-venv`；版本正确且能导入的包跳过。只检查并补齐依赖、不修改 skill 软链接或路径配置时运行：

```bash
bash install.sh --check
```

`voice.sh` 使用 `YICE_ASR_PYTHON`（默认 toolkit 的 `local/asr-venv/bin/python`）；检测封装使用 `YICE_VOICE_PYTHON`，默认同一环境。`YICE_TTS_PYTHON` 仍专门运行生成模型。安装器优先用 `uv pip`，否则用该环境的 `python -m pip`，装后重新验证导入与版本；不会创建或重建 ASR 环境。若主动覆盖执行 Python，须在那个环境准备相同依赖。无需借用 `PYTHONPATH`；配音分析和后期工具本身不下载模型、不联网。

## 从脚本生成

```bash
bash kit/scripts/voice.sh episode/script.md --output episode/voice \
  --backend kaggle --chunk-mode long_paragraph --profile natural_v7 --speed 1.0 \
  --anchors episode/anchors.json --seeds 42,43
```

v7.2 默认 `long_paragraph` 按中文句末分为优先 65–115 字的自然段。已授权 Kaggle 用异步提交和轮询，配音保持 `1.000×` 原速。`natural_v7` 保留自然呼吸，拼缝以 −68 dBFS 室温底噪托底并用半余弦过渡。历史制品如需复现 `1.08` 提速及超过 `250ms` 的呼吸缩到 `150ms`，使用 `--profile legacy --speed 1.08`。

`--skip-post` 只跳过初始后期，检测及后续修复仍正常运行。内部生成子进程仅输出原音，可装配清单由完整检测流程签发。

`--seeds` 默认 `42,43`，每章每个 seed 连续生成一次，不逐句生成原章；保留所有候选。优先选择 ASR 与韵律都通过的候选，再按内容差异数、告警数、匹配率、seed 排序。`--asr-threshold` 默认 `0.97`；即使匹配率很高，未登记的中文差异仍不放行。`--chapters 00,01` 可只处理指定章节。

检测不通过时，定位有问题的整句，每句生成 3 个新 seed，筛选 ASR、韵律、音色代理余弦 ≥0.94 和音高中位数偏差 ≤3.5 半音；只在已验证的自然低能量句间替换，匹配有效发声 RMS，接缝 10ms 交叉淡化。每轮保留原片、所有候选、连续性指标和修改前后 1–2 秒切片，再整章 ASR/韵律重扫。`--max-repair-rounds` 默认 3、最大 3；无法安全定位或三轮仍不过就报失败，不导出组装清单。代理指标不代替试听。

自然档以 `--pause-after` 登记所需幕间留白，保留实测语音时间。每章输出最终字时间、`analysis/voice-check-章号.json` 和 `asr-audit-章号.json`，SRT 与锚点由最终时序生成。全片母带在装配时测量，目标 −14.5 ± 0.8 LUFS，真峰值 ≤ −1 dBTP。

## ASR 例外与复跑

数字和单位只接受同值写法，先替换完整长短语，避免 `3` 破坏 `30`。数字后的“兆”转写成 `Mbps` 作为转写差异登记，不修改朗读文本；数字后的“照→兆”明确登记为单位同音字，不替换“照片”的“照”。英文专名与同音别字独立留档，没有一般模糊匹配。额外规则可用 `--normalizations exceptions.json`：

```json
{"number_unit":{},"english_name":{"Example":"Example name"},"homophone":{"张数":"章数"}}
```

键是朗读原文，值是明确接受的 ASR 别写。每项分别写入审计；不同数值不会因为例外表就被放过。兼容旧的平面原文→别写对象，也会分类记录。`--asr-prompt` 仅用于提供领域词表，不把整段台词喂给识别器。原始和最终转写都保留，ASR 缓存绑定音频 SHA-256 与模型/词表设置。

要用已有原始候选重跑同一流程，传 `--reuse-candidates cache.json`。缓存为记录列表，每项含 `text`、`seed`、`brand`、`path`、`sha256`。原文、seed、品牌和文件哈希均匹配时复制到新输出目录并保留原文件。缺少匹配项时使用已选配音后端，并继续执行检测。示例：

```json
[{"text":"示例原文。","seed":42,"brand":"example","path":"/absolute/raw.wav","sha256":"填写原音的完整SHA256"}]
```

`raw/seed42/` 保存原始候选，`candidates/章号/selection.json` 保存选择依据，`repair/round-N/` 保存修复候选、接缝和切片，`repair-report.json` 保存每轮结果。输出目录须为空，不覆盖旧交付。

## 独立处理已有章音频

```bash
python3 kit/scripts/workspace.py voice-post.py --audio episode/raw.wav \
  --alignment episode/alignment.json --text-file episode/reading.txt \
  --output episode/post.wav --output-alignment episode/post-alignment.json

bash kit/scripts/voice-check.sh --audio episode/post.wav \
  --alignment episode/post-alignment.json --text-file episode/reading.txt \
  --chapter 01 --output episode/check.json --cache episode/acoustic.npz

bash kit/scripts/voice-repair.sh --audio episode/post.wav \
  --alignment episode/post-alignment.json --text-file episode/reading.txt \
  --output episode/repair
```

所有路径都由参数传入；`--timing` 是 `--alignment` 的别名。输入必须是**单字时间**，不能用只有句起止时间的字幕或句级 `voice-timing.json` 冒充字级对齐：

```json
{"text":"甲乙，丙丁。","mapped":[
  {"charStart":0,"charEnd":1,"s":0.0,"e":0.16},
  {"charStart":1,"charEnd":2,"s":0.16,"e":0.32},
  {"charStart":3,"charEnd":4,"s":0.56,"e":0.72},
  {"charStart":4,"charEnd":5,"s":0.72,"e":0.88}
]}
```

也接受同结构的 `characters` 列表或独立列表。索引是朗读文本中的字符位置，时间单位为秒、原点为章音频起点，所有读出的字母、数字、汉字必须完整覆盖；重叠、缺失或超出音频的时间会失败。后期输出保持此格式并附操作日志；再次检测必须使用新音频和新字时间，不能沿用旧时间。

检测 JSON 包含 `chapter`、`ok`、`alerts`、阈值和声学测量。退出码为 `0` 零告警、`1` 有告警、`2` 输入失败。`natural_v7` 默认允许句末和转折 0–1250ms、普通逗号 0–950ms，非标点停顿上限 340ms。可用 `--comma-ms`、`--contrast-ms`、`--sentence-ms` 设置区间。历史档才使用 150ms 非标点上限。每段低能量间隔只归属一个字边界，自动检测后仍须听审。

独立后期默认保留自然呼吸，保留输入文件并输出单声道 PCM24 WAV。特殊的历史静音方案可显式选用旧处理并传 `--scene-boundaries`（JSON 单字边界索引列表）和 `--scene-padding`。

## 离线测试与隐私

```bash
python -m unittest discover -s kit/tests -p 'test_*.py' -v
```

配音测试在临时目录用正弦波和噪声生成全部素材；不需要用户声音、参考录音或模型。真实项目的音频、字时间、缓存和复跑报告都放在调用者自己的目录，不加入本仓库。

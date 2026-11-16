# 配音生成、后期和韵律检测

`voice.sh` 按章生成 → Whisper 字级对齐 → 后期处理 → 预算内的换幕静音 → **最终章音频检测**。只有全部章节零告警，才输出可供组装的 `voice-manifest.json`、`voice-timing.json` 和 SRT。规则解释见 [配音规则](../../references/voice.md)。

## 环境

沿用 toolkit 的 MLX / Whisper 环境，另需 `numpy`、`scipy`、`soundfile`、`librosa` 和 PATH 中的 `ffmpeg`。安装器会把 `librosa==1.0.1`、`soundfile==0.14.0` 及缺失的 `scipy`、`numpy` 装入现有 `asr-venv`；版本正确且能导入的包跳过。只检查并补齐依赖、不修改 skill 软链接或路径配置时运行：

```bash
bash install.sh --check
```

`voice.sh` 使用 `YICE_ASR_PYTHON`（默认 toolkit 的 `local/asr-venv/bin/python`）；检测封装使用 `YICE_VOICE_PYTHON`，默认同一环境。`YICE_TTS_PYTHON` 仍专门运行生成模型。安装器优先用 `uv pip`，否则用该环境的 `python -m pip`，装后重新验证导入与版本；不会创建或重建 ASR 环境。若主动覆盖执行 Python，须在那个环境准备相同依赖。无需借用 `PYTHONPATH`；配音分析和后期工具本身不下载模型、不联网。

## 从脚本生成

```bash
bash kit/scripts/voice.sh episode/script.md --output episode/voice --anchors episode/anchors.json
```

默认后期：保音高提速 `1.08`；宽频低能量的呼吸候选压低 `12dB`，超过 `250ms` 缩到 `150ms`；剪切及补停顿边缘淡化 `10ms`。逗号停顿 `180–300ms`，转折和句末 `300–450ms`，已经在区间内的保留。声学候选不等于人工确认的呼吸声，日志保留原区间及实际操作。

`--speed`、`--breath-db`、`--breath-cut-ms`、`--breath-target-ms`、`--fade-ms` 可调整这些参数。`--skip-post` 只跳过后期，**没有跳过检测的开关**。内部生成子进程仅输出 raw 文件，不能产生已通过检测的组装清单。出现告警后应整句重生成、筛选并复查；不自动把异常压成“通过”。

默认 `--silence 0.2` 先计入语义停顿预算，再插入换幕静音，避免后期和组装各加一次长停顿。每章输出后期字时间、实际最终字时间及 `analysis/voice-check-章号.json`；SRT、章节和锚点由处理后的时间重新生成。后期不替代全片混音：章配音约 −16 LUFS，成片 −14 LUFS、真峰值 ≤ −1 dBTP 仍须在混音后测量。

## 独立处理已有章音频

```bash
python kit/scripts/voice-post.py --audio episode/raw.wav \
  --alignment episode/alignment.json --text-file episode/reading.txt \
  --output episode/post.wav --output-alignment episode/post-alignment.json

bash kit/scripts/voice-check.sh --audio episode/post.wav \
  --alignment episode/post-alignment.json --text-file episode/reading.txt \
  --chapter 01 --output episode/check.json --cache episode/acoustic.npz
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

检测 JSON 包含 `chapter`、`ok`、`alerts`、阈值和声学测量。退出码：`0` 零告警，`1` 有告警，`2` 参数或输入失败。可调默认值为 `--long-ratio 2.4`、`--active-ratio 2`、`--onset-ratio 1.7`、`--hesitation-ms 60`、`--nonpunct-max-ms 150`、`--fall-semitones 4`、`--pause-tolerance-ms 20`；停顿区间用 `--comma-ms`、`--contrast-ms`、`--sentence-ms` 的两个数设置。一个低能量间隔只归属一个字边界；降调还须同时满足前字拖长和低能量间隔，不能把汉语声调单独判错。

独立后期若要预留换幕静音，传 `--scene-boundaries`（JSON 单字边界索引列表）和 `--scene-padding`；未传则不预留。后期保留输入文件，输出为单声道 PCM24 WAV；`--speed 1` 不做变速。检测只给出候选，交付仍需听审。

## 离线测试与隐私

```bash
python -m unittest discover -s kit/tests -p 'test_*.py' -v
```

配音测试在临时目录用正弦波和噪声生成全部素材；不需要用户声音、参考录音或模型。真实项目的音频、字时间、缓存和复跑报告都放在调用者自己的目录，不加入本仓库。

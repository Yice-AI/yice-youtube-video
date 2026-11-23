---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频制片体系 v7.0。长段落原速配音、从开场起全片混音、双窗和真视频动态叠层、声明式分幕装配及对抗性成片审计。适用于旁白、真实录屏、分镜、成片和返修。
---

# 一策 YouTube 视频制作 v7.0

以旁白首字安排 1920×1080 实拍、实录与解说画面，使用 `clean_cinema` 字幕并保留 `y ≥ 900` 字幕安全区。

## 制片入口

1. 整理实测底账、旁白与逐镜画面。每镜注明实际画面主体、语义绑定和首字锚点。公开网页用 `kit/scripts/record-web-cam.sh` 采集深色实录，实操优先连续多点跟焦，概念及数据用解说动效或语义对应叠层。
2. 执行 `kit/scripts/voice.sh script.md --output voice --backend kaggle --speed 1.0`，也可显式选择已授权端点。默认 `--chunk-mode long_paragraph` 和 `--profile natural_v7`，380 字以内整章一次生成，较长章节在自然句界切成至多两段。`--pause-after 0-3=3.0` 登记一处设计留白。Kaggle 默认异步提交并每 2.5 秒轮询，等待上限 900 秒（可用 `YICE_TTS_TIMEOUT` 调整），异步提交返回 HTTP 404 时自动回退同步接口。
3. 写成 `episode-manifest.json` 后执行 `bash kit/scripts/assemble-episode.sh episode-manifest.json --output out`。装配会校验媒体时长、切点和语义，渲染所需动效，合成母带并运行 HyperFrames check 和 render。输出 MP4、SRT、`shot-timeline.json`、`bed-only.wav` 与 `acts/`。`--build-only` 可用于检查分幕工程和母带。
4. 执行 `bash kit/scripts/audit-v3.sh --v7 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4`，结合成片目检交付。

## episode-manifest.json

所有时间用秒。镜头 `start`、`end`、旁白 `at` 和 `firstCharTime` 以全片起点为零。`overlays[].at` 是镜内相对时间。素材路径相对清单解析。

```json
{
  "title": "实操样片",
  "filename": "episode",
  "gsap": "vendor/gsap.min.js",
  "voice_manifest": "voice/voice-manifest.json",
  "voice_timing": "voice/voice-timing.json",
  "audio": {
    "bgm": [
      "media/bed.wav"
    ],
    "sfx_library": {
      "stamp": "media/stamp.wav"
    },
    "music_drops": [
      {
        "start": 4.5,
        "end": 5
      }
    ]
  },
  "shots": [
    {
      "id": "opening",
      "act": "act-1",
      "anchor_cue_id": "0-1",
      "start": 0,
      "end": 5,
      "stage_mode": "cold_open_ab",
      "sources": [
        "media/before.mp4",
        "media/after.mp4"
      ],
      "hook": "哪一条更清楚？",
      "labels": [
        "初版",
        "修订版"
      ],
      "countdown": 3,
      "spoken_topic": "比较两版的画面",
      "visual_subject": "两版实录对照",
      "semantic_tags": [
        "样片",
        "同段对照"
      ],
      "semantic_binding": "callback_cut"
    }
  ]
}
```

- `gsap` 可由清单本地路径、`YICE_GSAP_PATH` 或已安装的 GSAP 包提供。`YICE_HYPERFRAMES_BIN` 可指定本机命令，默认使用 `npx --offline hyperframes`。
- 源 `voice_manifest` 可读取已有配音章清单。也可在 `audio.voice_tracks` 直接提供 `{id,path,at}` 数组。`audio.voice_processing_logs` 可列人声处理记录，供真空断崖检查。
- `cues` 可直接提供 `{id,firstCharTime,text}`，也可读 `voice_timing` 路径或母带清单内的 `scene_timing`。字幕使用 `captions` 数组或 JSON 路径，行格式为 `{text,start,end}` 或 `{text,startMs,endMs}`；若未指定，则从有 `text` 和 `end` 的 `cues` 生成。
- `shots` 按时间展开，完整覆盖全片。同一 `act` 的镜头连续出现。切点与首字相差至多 0.22 秒。每镜须带 `spoken_topic`、`visual_subject`、`semantic_tags` 及 `semantic_binding`。绑定类别为 `exact_tool_capture`、`conceptual_explainer`、`physical_prop`、`callback_cut`。可用 `spoken_entity` 命名额外工具。
- `cold_open_ab` 需要两个 `sources`，可传 `hook`、`labels`、`countdown`。`title_sequence` 需要一至两行 `title`，可传 `subtitle`、`brand`、`highlight`、`paper`，时长 1.8–3.2 秒。
- `callout_rig` 与 `fullbleed_rig` 使用一个 `source`，可设 `media_start` 与 `motion`。源片需覆盖入点、镜长和 0.2 秒尾部余量。`callout_rig` 传一至两个 `overlays`。`spotlight_box` 传 `box` 坐标，`stat_badge` 传 `value`、`unit`，`strikethrough_list` 传 `items`，`verdict_stamp` 传短标签。所有贴图均提供 `kind`、`at`、`label`，可设 `duration`。
- `studio_ui` 使用 `studio_style`、实际工作台 `data` 和取证文件 `sources`。支持剪辑台、代码编辑器、终端和音频工程台。`explainer_clip` 使用内嵌 `spec` 或本地 spec 路径，支持 Vox 文档、白板推导、图表、蓝图、数据尺与瑞士网格等语法。
- `audio.bgm` 支持一至三首，可设 `bgm_cuts` 指定切换点。`audio.sound_marks` 支持 `{kind,at,gain}`，类型有 `tick`、`whoosh`、`pop`、`marker`、`stamp`、`riser`。片头、倒数和贴图会自行登记事件。需要单独混音时执行 `python3 kit/scripts/workspace.py mix-episode-audio.py audio.json --output out`，音频清单顶层带 `duration`。

## 应用与审计

- `natural_v7` 保留呼吸。段间采用室温底噪及余弦过渡，独立后期默认 `--preserve-natural-breath`，只收紧验证过的超长静音，保留登记的戏剧留白。Whisper 的同音同调及英文拼写变体会单独留档，漏读和实质错读进入整句修复。历史项目可指定 `--chunk-mode legacy_chunk` 和 `--profile legacy`。
- 已有多段原音可执行 `kit/scripts/voice.sh --concat-wavs part-a.wav part-b.wav --pause 1=3.0 --crossfade-ms 80 --room-tone-dbfs -60 --output chapter.wav`。边界编号从 1 起，表示第一段与第二段之间。默认 60 ms 余弦淡化、-60 dBFS 底噪。拼接保留每侧可用的 140 ms 呼吸保护区。
- `EpisodeAudioMixer` 从 0 秒铺入底乐，人声 -22 dB、留白 -13 dB 闪避，跨幕余弦换曲，支持 Music Drop。母带目标 -14.5 ± 0.8 LUFS，真峰值 ≤ -1.0 dBTP。
- v7 审计核对语义对口、首字切点、真实视频底图占比 45%–72%、同源素材最多三次回扣。前 15 秒底乐高于 -42 dBFS，前 45 秒至少三处动作音效。前后半程各至少 35% 动效，连续裸视频至多 14 秒。原始人声和处理记录参加真空检查，成片参加像素、OCR、黑帧与重复审计。

实测数字保留可核对底账。参考频道只作研究，成片使用自己的录屏、实拍及有授权的公开素材。Claude 桌面只使用脱敏静态截图，参考音频仅走已授权云端端点，画面移除本机路径、私人会话和凭据。

相关参考见 [配音规则](references/voice.md)、[导演层](references/director-layer.md) 和 [审片门禁](references/review-gates.md)。

---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频制片体系 v8.2。Onetake 多风格快门渲染、HyperFrames 原生子合成、3D 实录视窗、跨时窗遮挡校验、原速配音与声学母带。适用于旁白、真实录屏、分镜、成片和返修。
---

# 一策 YouTube 视频制作 v8.2

以旁白首字安排 1920×1080 实拍、实录与解说画面，使用 `clean_cinema` 字幕并保留 `y ≥ 900` 字幕安全区。

## 制片入口

1. **拆稿定证据。** 每句注明要证明的事实、实际画面主体、语义绑定和首字锚点。「第一遍挡住、第二遍移开」「改前、改后」按可辨认的画面状态和台词时序编排。
2. **按主体找素材。** 以下入口均在 `kit/scripts/`，保留素材来源和可复查的时间窗。
   - 本机实操用 `rec-demo.sh` 或常驻录屏师，保留连续操作。
   - 公开网页、文档与开源仓库用 `record-web-cam.sh` 录制深色高倍率画面。
   - 官方产品页的原生视频、图标和矢量标志用 `collect-entity.sh`。
   - 往期成片或长录屏用 `scout-video-scenes.sh long.mp4 --output scout` 找互不重叠、画面不同且信息量高的选段，默认过滤大面积纯色字卡。
   - 具象实物特写和人物抠像分别用 `find-media.sh`、`people-add.sh`。
   - 对原片内容或剪辑的具体评论可用 `reference_breakdown`，原片静音，明确频道署名和实测切点。
3. **配音并验帧。** 执行 `kit/scripts/voice.sh script.md --output voice --backend kaggle --speed 1.0`。默认 `long_paragraph` 优先 65–115 字、最多 5 句，`natural_v7` 保留呼吸。`--pause-after 0-3=3.0` 可登记留白。Kaggle 异步每 2.5 秒轮询，默认总等待 900 秒，异步提交 HTTP 404 才回退。清单写好后运行 `kit/scripts/scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify`，按首、中、尾帧逐镜核对台词及因果顺序。
4. **装配与审片。** 黄金前 8 秒、机制高潮与片尾核心结论优先用 `onetake_clip`。多阶段机制用 `hyperframes_block`，数值关系可用 `t3_finance_chart`，实录用 `perspective_3d` 或 `studio_window`。用 `kit/scripts/assemble-episode.sh episode-manifest.json --output out` 装片，输出 MP4、SRT、`shot-timeline.json`、`bed-only.wav` 和分幕工程。输入一致的幕可复用，`--force-render` 强制刷新，`--build-only` 生成工程与母带。最后执行 `kit/scripts/audit-v3.sh --v7 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4`，并目检、听审。

5. **封面与打包。** 用 `kit/scripts/thumbnail.sh --project . --title "标题" --summary "内容摘要"` 走 `image2` 原生直出，默认生成 3 张候选。打开 `thumbnail-contact-sheet.png` 对照信息流尺寸和右下角时长警示。用同一入口加 `--select 1` 导出小于 2 MB 的高清 JPG，默认存入 `thumbnails/` 并登记账本。

## 反简陋 PPT 铁律

风格以贴合内容和画面质量为准。同一套皮肤能服务叙事时可以继续用。跨题材先用 `kit/scripts/visual-palette.sh` 查看 Onetake 六套色板或从真实产品截图吸色，再按镜头任务选择 HyperFrames 蓝图、原子动效、转场和 Registry 组件。

| 镜头任务 | 视觉路由 |
| --- | --- |
| 黄金前 8 秒的钩子、核心机制高潮、全片结论 | `onetake_clip` 用 OM 弹簧、运镜和跨拍变形，默认 180° 真实快门积分。三张纯文字方框逐页切换不能承担这些镜头。 |
| 多阶段架构、3D 卡片阵列、交互状态推演 | `hyperframes_block` 按口播推进实体、光轨和状态，复用 HyperFrames Registry 组件和 Animation 蓝图。 |
| 真实网页与录屏实证，目标至少占全片 50% | `perspective_3d` / `studio_window` 保持操作可读。需要时用前景实物或同步跨镜转场保留注意力。 |

`t7_editorial_board` 保留旧项目兼容。合成契约、清单用法与离线验收见 [双擎高阶视觉路由](references/10-双擎高阶视觉路由.md)。

抠图默认校验主体轮廓。清单核验会对前景抠图的首、中、尾帧检查底层文字，`overlay_text_collisions` 有命中时按报告时间回看，并调整贴图位置或存续时间。

## episode-manifest.json

所有时间用秒。镜头 `start`、`end`、旁白 `at` 和 `firstCharTime` 以全片起点为零。`overlays[].at` 是镜内相对时间。素材路径相对清单解析。

用 `kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 从首字时间生成 30 fps 分镜草稿，再用核对过的画面替换占位镜头。清单和单镜可设 `theme` 为 `pine`、`obsidian`、`aurora_indigo`、`paper_cool` 或 `paper_warm`。

`gsap` 是可选覆盖项。省略时自动发现本机 GSAP，包括 toolkit 的 `local/vendor/gsap.min.js`。

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
- `callout_rig` 与 `fullbleed_rig` 使用一个 `source`，可设 `media_start` 与 `motion`。源片需覆盖入点、镜长和 0.2 秒尾部余量。`callout_rig` 传一至两个 `overlays`，贴图均提供 `kind`、`at`、`label`，可设 `duration`。角落补充信息用 `corner_tag`，可设 `sublabel` 或 `silent`。`spotlight_box` 只用于已经核对的局部像素目标，必须填写 `target_verified: true`、`target_note` 与 `box: [x, y, w, h]`，尺寸限 64–680 × 48–340。跨镜头复用同坐标会触发审计，使用总数上限为三处或全片镜头的 8% 向下取整，取较大者。`stat_badge` 传 `value`、`unit`，`strikethrough_list` 传 `items`，`verdict_stamp` 传短标签。
- `studio_ui` 使用 `studio_style`、实际工作台 `data` 和取证文件 `sources`。剪辑台、代码编辑器、终端和音频工程台均可添加与 `callout_rig` 相同的 `overlays`。
- `triptych_cards` 使用 `heading` 与两至四张 `cards`。每张卡片支持 `{label, sublabel?, source, logo?, media_start?, reveal_at}`，按镜内 `reveal_at` 点亮并登记 `pop`。支持 PNG、JPEG、WebP、安全 SVG、GIF 和视频。装配时 WebP 转为无损 PNG，GIF 转为单次播放的 30 fps MP4，必要时定格尾帧。普通视频须覆盖从入点到镜尾的时长及 0.2 秒余量。
- `evidence_spotlight` 用一个 `source` 检视原文、截图或架构图。可设 `heading`、`source_credit`、`logo`。传入网页采集的 `capture_meta` 可复用已定位的原文框和来源，也可给出原图像素 `highlight_box: [x, y, w, h]` 与镜内 `highlight_at`。
- `title_sequence` 和 `corner_tag` 可填 `logo`。在 `callout_rig`、`studio_ui` 或 `evidence_spotlight` 中，可用 `prop_badge`、`reaction_cutout` 加入透明素材。叠层填 `source`、`at`，可选 `label`、`duration`、`side` 和 140–260 像素的 `size`。
- `reference_breakdown` 将一条 `source` 放入 1152×648 静音检视窗，填 `channel` 署名和 `claim` 拆解主张。可设 `media_start`、严格升序的镜内 `cut_points` 及最多三项 `metrics`（`{label,value}`）。每处切点自动更新镜头计数并登记轻音量 `tick`。
- `explainer_clip` 使用内嵌 `spec` 或本地 spec 路径，支持 Vox 文档、白板推导、图表、蓝图、数据尺与瑞士网格等语法。
- `focus_push` 和 `spring_glide` 提供两段式运镜。实录可用 `framing: "studio_window"` 和 `window_title` 装入暗场圆角窗，保留独立字幕区。`highlighter_sweep`、`hand_circle` 与 `spotlight_box` 共用像素核验和使用上限。代码或终端可用从 1 起算的 `data.focus_lines` 标出当前行。
- 配音目录的 `captions.json` 优先用于短句字幕，清单可显式覆盖。浅色舞台和亮底实录自动切换为深底白字胶囊。自定义审计词表可填 `custom_entities` 名称数组或名称到别名的字典。
- `audio.bgm` 支持一至三首，可设 `bgm_cuts` 指定切换点。`audio.sound_marks` 支持 `{kind,at,gain}`，类型有 `tick`、`whoosh`、`pop`、`marker`、`stamp`、`riser`。片头、倒数和贴图会自行登记事件。需要单独混音时执行 `python3 kit/scripts/workspace.py mix-episode-audio.py audio.json --output out`，音频清单顶层带 `duration`。

## 应用与审计

- `natural_v7` 保留呼吸。段间采用室温底噪及余弦过渡，独立后期默认 `--preserve-natural-breath`，只收紧验证过的超长静音，保留登记的戏剧留白。Whisper 的同音同调及英文拼写变体会单独留档，漏读和实质错读进入整句修复。历史项目可指定 `--chunk-mode legacy_chunk` 和 `--profile legacy`。
- 已有多段原音可执行 `kit/scripts/voice.sh --concat-wavs part-a.wav part-b.wav --pause 1=3.0 --crossfade-ms 80 --room-tone-dbfs -68 --output chapter.wav`。边界编号从 1 起，表示第一段与第二段之间。默认使用 −68 dBFS 底噪，并在拼接处以半余弦包络融入 110 ms 前导和 130 ms 尾音。
- `EpisodeAudioMixer` 从 0 秒铺入底乐，人声 -22 dB、留白 -13 dB 闪避，跨幕余弦换曲，支持 Music Drop。母带目标 -14.5 ± 0.8 LUFS，真峰值 ≤ -1.0 dBTP。
- v7 审计核对语义、首字切点和 45%–72% 真视频底图。同源视频常规使用至多两次，窗口重叠超过 0.25 秒触发门禁，另可明确用 `callback_of` 登记一次回扣。多栏视频也纳入复用检查。跨镜相似帧至多出现两次。低于 26 字又缺少图表、图像或结构卡的解说会被拦截。前 15 秒底乐高于 −42 dBFS，前 45 秒至少三处动作音效，前后半各至少 35% 动效，连续裸视频至多 16 秒。人声参加真空检查，成片参加像素、OCR 和黑帧审计。

实测数字保留可核对底账。`reference_breakdown` 与对比双卡支持符合合理使用（Fair Use）条件的参考短切片拆解。原片音轨全程静音，显式声明并展示 `channel` 来源署名，配合实测切点和针对原片的分析。使用 `spotlight_box` 的非静止实录围绕核验坐标同心跟焦，角落标识、数字角标保持固定。Claude 桌面使用脱敏静态截图，参考音频仅走已授权云端端点，画面移除本机路径、私人会话和凭据。

相关参考见 [配音规则](references/voice.md)、[导演层](references/director-layer.md) 和 [审片门禁](references/review-gates.md)。

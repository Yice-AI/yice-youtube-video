# v15.0 成片审计与签发

## 前置三关（动笔、配音、装片之前）

```bash
kit/scripts/precheck-episode.sh --project <剧集目录> --stage <packaging|script|assets|all> [--json] [--output report.json]
```

| 关卡 | 未通过严禁 | 报告项 |
| --- | --- | --- |
| `packaging` | 写分镜 | `bland_explanatory_title`、`promise_body_drift`、`thumbnail_candidates_insufficient` / `thumbnail_candidates_missing`（`--require-thumbnails`） |
| `script` | 跑配音 | `maker_plumbing_leak`（报幕号与原句）、`slow_or_meta_opener`、`unpaired_pain_point_visual`、`missing_hands_on_prompt_loop` |
| `assets` | 跑 `assemble-episode.sh` | `duplicate_asset_disguise`、`insufficient_visual_clusters`、`missing_external_showcase` |

返回码 0 全部通过，1 有拦截，2 参数或文件缺失。包装缺 `packaging.json/md` 时标题取自清单或剧本一级标题并给出提醒。

## 成片审计

素材入箱时保留来源、许可或授权记录、文件哈希和实测底账。装配先运行各幕 HyperFrames `check`（及 Onetake 连续性探针），之后对实际导出成片运行统一审计：

```bash
kit/scripts/audit-v3.sh --v10 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4
```

## 双调性、三态与防碰撞门禁

教程须有至少 2 个 HyperFrames 镜头（占全片 ≥ 15%），以及至少 3 个 Onetake 镜头（占 ≥ 18%）。`dual_engine_symphony_gate` 检查双擎占比；`three_mode_symphony_gate` 校验 M1/M2/M3 三态比例。

`unified_cyber_stage_and_accent_gate` 逐镜核对**暗场看作品、瑞士亮场讲逻辑**：
- **`cyber_glass`**（默认）：合成与实录边缘亮度 `luma <= 42`，且双擎镜头需出现至少两种主高光色相（亮度 ≥ 135、色差 ≥ 55）。
- **`editorial_paper` / `scroll_paper`**：声明暖纸母版后，边缘亮度须满足 `luma >= 185`（带锦缎边与土坡的 `scroll_paper` 须 `luma >= 115`），且 `assemble-episode.py` 自动切为深色胶囊字幕保证高对比度。
- **`inconsistent_stage_tone`**：影院暗场 `cinema_black` 展作品与对比，瑞士暖白 `swiss_paper` 讲并列选择、步骤与证据。按叙事换场，旧版单场项目仍核对调性一致。

`no_ppt_slide_header_gate` 继续拦截左上角（`x < 760, y < 210`）高度超过 34 px 的丑陋说明大标题，同时**放行两类合规标题**：
1. 编辑部单行划线短题 / 品牌胶囊（`data-title-kind="editorial_single"`，高度 ≤ 68 px）；
2. 文物 / 古画角标铭牌（`data-title-kind="archive_plaque"`，紧凑尺寸且无文字遮挡）。

`title_card_collision` 依然在 30 fps 全帧检查**所有**可见标题（含合规短题与角标）与主体 `[data-spatial-subject]` 的相交面积，任何重叠直接拦截。`low_layer_contrast` 在 `layer_explode_3d` 展开态检查三层高亮与背景亮度差 ≥ 26。

## v9 六项画面检查

| 报告项 | 硬性条件 |
|---|---|
| `pacing_and_rhythm_gate` | 目标 4–6 秒，均值 ≤ 6.5 秒，P90 ≤ 9 秒。普通镜 ≤ 10.5 秒，多视频接力或复合镜 ≤ 13 秒。超过 10.5 秒镜数 ≤ max(1, 总镜数整除 20)。 |
| `framing_and_variety_gate` | 满屏 ≥ 实录时长的 70%，斜框 ≤ 全片 15%，带框镜头不相邻。连续满屏实录 ≤ 5 镜且 ≤ 35 秒，连续图形 ≤ 4 镜且 ≤ 28 秒。 |
| `visual_richness_gate` | 抽查实录有效画面的首、中、尾，拦截大面积平坦且边缘稀少的空壳镜头。 |
| `dual_engine_craft_gate` | 双擎不得陈列两张及以上静态截图（`.mp4` 预解帧序列 `vframes_*` 自动按单视频源归并，不误判为多图画廊）。Onetake 须有相机深度变化、连续变形或确定性 `SKETCH.` 绘制。 |
| `cross_stage_asset_dedup_gate` | 对双擎、对照卡、证据台及实录查文件与画面指纹；v15 起对 `hyperframes_block` 内嵌 `<video>`、`onetake_clip` 预解帧 `vframes_*` 与实录视频抽中帧指纹和 16×9 色彩版式签名。同一视觉模板跨镜超过 2 次即拦截（可登记一次 `callback_of`），堵住同一套网页或 PPT 换文件名反复播放。 |
| `tutorial_workflow_gate` | 工具教程须有可核验的实际输入／执行镜和复杂成品交互镜。 |
| `aspect_crop_integrity_gate` | 无头浏览器逐帧比对 `<video>` / `<img>` 原始宽高比与实际渲染框，无 `zoom > 1.05` 特写声明却因 `object-fit: cover` 裁掉宽或高超过 12% 的，报 `excessive_aspect_crop`。 |
| `external_showcase_diversity_gate` | `tool_tutorial` 长片（≥ 90 秒）独立视觉指纹簇 ≥ max(6, ⌈时长/30⌉)，且须含 `harvest-showcase-media.sh`、`collect-entity.sh`、`capture-web.mjs` 等多源真实画面，不许全靠本地自编三四个页面撑满全片。 |

## 八项硬门禁与前置防线

| 门禁 | 验收 |
|---|---|
| `v7_timeline_gate` | 镜头连续，切点距首字 ≤ 0.22 秒，真视频底图占 45%–72%（现行放宽为 30%–65%）。同源视频常规使用至多两次，重叠 ≤ 0.25 秒，另可用 `callback_of` 登记一次回扣。 |
| `semantic_binding_gate` | 台词主题、实际画面主体和素材标签相符。点名工具的实录须指向对应实体。 |
| `spotlight_restraint_gate` | 局部框登记像素核验，最大 680×340，禁止跨镜复制相同坐标，数量上限为 max(3, int(总镜数 * 0.08))。 |
| `opener_bgm_and_sfx_gate` | 0 秒起铺底乐，前 15 秒底乐 > −42 dBFS，前 45 秒至少 3 处动作音效。 |
| `first_half_motion_density_gate` | 前后半各有 ≥ 35% 动效镜头，无叠层连续全屏实拍至多 16 秒。 |
| `breath_integrity_gate` | 原人声不得有 > 40 ms 且 < −80 dBFS 的句间真空断崖。配音阶段 `voice-check.py` 的 `natural_v7` 另拦截句内无标点停顿超 165 ms、词内能量塌陷 ≥ 16 dB（110–260 ms）与句中犹豫拖音，异常分段由 `voice.py` 自动换 seed 重抽，最多 3 轮。 |
| `explainer_density_gate` | 解说画面至少 26 字或具备图表、图像、结构卡等内容。 |
| `onetake_craft_gate` | 所有 `onetake_clip` 须具备 `.onetake-probe.json` 与 `.render.json`，无 `__seek` 报错、启用快门动态模糊（`shutter > 0`），禁止无承接硬切（除非声明 `allow_staccato`）。 |

前置防线：`cutout.py` 默认拦截残次抠图；`scout-video-scenes.sh --verify-manifest` 对贴图可见期首中尾跑底层文字 OCR 防撞字。交付为 1920×1080、30fps H.264，母带 −14.5 ± 0.8 LUFS、真峰值 ≤ −1.0 dBTP。成片时长以清单末镜为准，片尾可按剧本设计 2–4 秒留白，历史项目沿用成片时长等于 episode.end 的约定。

## 动态盲审与新增门禁

主脑交片前关字幕、有声连看全章。逐项确认反例与真实操作看得懂、口播数量与同屏成品一致、没有连续三秒的死镜、前六十秒不出现终端、字幕带不压核心文字、每种声音都对应可见动作。

| 代码门禁 | 复核依据 |
| --- | --- |
| `no_early_cli_gate` | 工具教程前 55 秒核对原素材名、终端舞台和成片识别到的命令行。导演连看延伸到前 60 秒。 |
| `enumerated_count_gate` | 数量取 `expected_items` 或讲解列举的口播／标题，与实际显示的独立胶囊、卡片或步骤逐个核对。 |
| `subtitle_safe_zone_gate` | 瑞士画布的核心文字、贴图和自建页面不得进入 y ≥ 860 区域。按文字位置与底层画面核对，排除字幕自身。自建实录登记 `custom_layout: true`。 |
| `chapter_voice_completeness_gate` | 最后一个镜头须覆盖每章人声与最后一句字幕。节选章可用 `chapter_reference_manifest` 指向完整原声清单，核对实际声轨时长和内容。 |
| `sfx_diversity_and_sync_gate` | 所有动作点增益至少 0.24，过低记为 inaudible_sfx_padding。转场、重锤、划线增益 0.55–0.74，翻页、点击、打字、胶囊展开 0.28–0.44。满 30 秒每秒至少 0.72 个不同帧的有效动作点，含片头片尾的最大空档不超过 3.6 秒。至少六个不同底层文件，任一文件占比不超过 28%。同文件同音高不能三连，落点距切点、贴图、子项或真实交互不超过 0.12 秒。 |

三联幕布每 85 秒最多两次，六个槽位按文件内容去重。工具按交付对象并列显示，工作流跟随实际步骤。大字采用双行高对比；优势卡默认居中弹出后依次推开，横屏素材零裁边；多卡接单卡全屏用点中推近；原件改字使用真实操作；骂丑的口播同镜出现真实反例。

# v11.0 导演层与画面路由

按旁白首字安排画面，先确定本句要证明的事实与叙事角色，再选色板与舞台。默认输出 `1920×1080`、`30fps`，支持五套主舞台主题（`obsidian`、`aurora_indigo`、`paper_cool`、`paper_warm`、`pine`）以及 `onetake` 六套电影色板（`paper`、`dusk`、`tabletop`、`ultramarine`、`riso`、`ember`）或产品截图自动吸色（`look_from_shots`），一切以贴合内容气质与视觉高级感为准。字幕统一保留 `y ≥ 900` 安全区。

教程前 5 秒放官方复杂成品，接着实录命令或提示词与 Agent 执行过程，长等待注明倍速。随后用满屏多点推焦拆解真实成品并验证边界。以 4–6 秒一个镜头排台词，全片均值 ≤6.5 秒，满屏占实录 ≥70%，斜框占全片 ≤15%，带框镜不相邻。跨图对照选冲印台或分栏卡，多贴图只用于有实际空间调度的合成。

## 选材、选型与因果核验

1. **视觉选型**：开拍前可用 `kit/scripts/visual-palette.sh` 检索本机 6 套电影色板、产品吸色、22 套 HyperFrames 动态分镜蓝图、原子动效规则、39 种 Onetake 物理原语与近 400 个 Registry 组件，详情见 [10-双擎高阶视觉路由](10-双擎高阶视觉路由.md)。
2. **六路实证素材**：分别使用本机 `rec-demo.sh`、公开网页 `record-web-cam.sh` / `capture-web.mjs`（`30fps` 高倍率净屏）、官方原生 `<video>` 与矢量标志 `collect-entity.sh`、往期长片 `scout-video-scenes.sh`（自动剔除纯色字卡、硬切与旧烧录字幕）、免版税高清横屏图库与人物/实物抠像 `find-media.sh` / `people-add.sh` / `cutout.py`、静音原片评论拆解 `reference_breakdown`。
3. **装片前验帧**：渲染前运行 `kit/scripts/scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify`，逐镜对照首、中、尾帧和台词因果顺序（如「改前/改后」「挡住/移开」），并自动执行贴图存续期首、中、尾三点 OCR 防撞字检查，确保贴图不遮挡底层画面文字。

## 声明式分幕与十一类舞台

在 `episode-manifest.json` 中填 `anchor_cue_id`、`spoken_topic`、`visual_subject`、`semantic_tags` 与 `semantic_binding`。首字锚点与真实切点相差至多 `0.22` 秒。每幕连排，连续覆盖成片时长。同幕第 2 镜起可声明 `transition_in`（`whip_push`、`zoom_through`、`iris_reveal`、`blur_crossfade`）做入退场同步耦合转场。

| 舞台 | 用途与核心字段 |
|---|---|
| `onetake_clip` | **单主体相机推拉、连续变形与机制高潮**。新镜填 `onetake_spec` 的配方与数据，已有合成可填 `comp`。填 `shutter`（默认 `180`），可选 `look` 或 `look_from_shots`。用 `OM` 物理弹簧/相机跟随/连续变形（Carry）与真实快门动态模糊替代多框文字堆砌。 |
| `hyperframes_block` | **多阶段架构、3D 卡片阵列、数据流与交互状态推演**。新镜填 `spatial_spec` 直编空间动效，已有项目可填 `composition` 挂载独立子合成（Registry 组件或 Animation 22 套蓝图），自动离线注入 GSAP 与打包字体。 |
| `callout_rig` / `fullbleed_rig` | **真实网页与实操录屏主力舞台**。填 `source`、`media_start`、`motion`（支持 `focus_push` / `spring_glide` 两段呼吸运镜），默认采用 `fullbleed` 满屏跟焦，暗场视窗只用于单镜强调。 |
| `evidence_spotlight` | **原文、截图或架构图局部推近检视台**。传网页采集的 `capture_meta` 自动复用原文像素框与来源署名，或显式填 `highlight_box` 与 `highlight_at`。 |
| `triptych_cards` | **两至四项多格式对照展台**（支持视频、GIF、WebP、PNG、安全 SVG）。现代主题下自动启用圆角毛玻璃立体展台卡与逐卡 `reveal_at` 弹性点亮。 |
| `cold_open_ab` | **两条真视频同窗 A/B 对照**，填 `sources`、`labels`、`hook` 与 `countdown`。 |
| `reference_breakdown` | **1152×648 静音原片拆解检视窗**，填 `channel` 署名、`claim`、实测 `cut_points` 与最多三项 `metrics`。 |
| `studio_ui` | **剪辑台、代码编辑器、终端或音频工程台**，支持 `data.focus_lines` 聚光高亮当前核心代码/输出行。 |
| `title_sequence` | **简洁章标题扉页**（`1.8–3.2` 秒），支持品牌 `logo` 与遮罩滑入。 |
| `explainer_clip` | **数据图表与轻量参数化解说**（档案用 `y2_vox` 暖纸冲印，数值用 `t5_data_ruler` 或 `t3_finance_chart`）。`t7_editorial_board` 仅保留旧项目兼容，新片结论与高潮统一走 `onetake_clip` 或 `hyperframes_block`，禁止堆砌三框纯文字 PPT。 |

## 叠层、破框贴图与运镜纪律

- `corner_tag` 位于左上安全区，支持嵌入官方矢量 `logo`、副标题或静音弹出。
- `spotlight_box`、`highlighter_sweep`（通透荧光笔涂抹）与 `hand_circle`（双圈手绘椭圆）只标识已核对的局部像素目标，必须填写 `box`、`target_verified: true` 和 `target_note`，尺寸限 `64–680 × 48–340`，共用全片 `8%`（或至少 3 处）克制上限，严禁跨镜盲套同坐标。
- `prop_badge`、`reaction_cutout` 支持常规侧下角标（`140–260px`）或 `placement: "foreground_hero"` 大尺寸前景视差破框贴图（`340–460px`，左/右侧避开中间字幕带）；素材须通过 `cutout.py` 主体完整性门禁，严禁把带大片桌面底板的残缺抠图贴上画面。
- 合理使用（Fair Use）参考短切片全程静音并显式展示 `channel` 来源署名；任何私人路径、账号名、邮箱与受限会话必须在素材层先行脱敏清除。

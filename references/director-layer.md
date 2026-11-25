# v7.3 导演层与画面路由

按旁白首字安排画面，先确定本句要证明的东西，再选择舞台。统一使用 1920×1080、30fps、深松墨绿与暖纸色、L 角取景框与珊瑚红重点标注。字幕保留 y ≥ 900 安全区。工具操作用自己的实录，公开网页用深色高倍录屏，抽象结论和规则使用解说动效或有明确语义的实证回扣。

## 选材与因果核验

六路素材分别使用本机 `rec-demo.sh`、公开网页 `record-web-cam.sh`、官方视频和标志 `collect-entity.sh`、往期长片 `scout-video-scenes.sh`、实物图库和人物抠像 `find-media.sh` / `people-add.sh`、静音原片评论拆解 `reference_breakdown`。长片选段优先保留高信息量画面，避开纯色字卡、近似画面和重复时间窗。

渲染前运行 `scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify`，逐镜对照首、中、尾帧和台词。顺序镜头按实际状态辨认，例如第一次鼠标挡字、第二次移动到留白处。看不清状态就换源或改切点。

## 声明式分幕

在 `episode-manifest.json` 中填 `anchor_cue_id`、`spoken_topic`、`visual_subject`、`semantic_tags` 与 `semantic_binding`。首字锚点与真实切点相差至多 0.22 秒。每幕连排，连续覆盖成片时长。

| 舞台 | 用途与字段 |
|---|---|
| `cold_open_ab` | 两条真视频同窗对比，填 `sources`、`labels`、钩子与倒数。 |
| `title_sequence` | 短片名或章标题，用一至两行标题和可选副标题。 |
| `triptych_cards` | 两至四张图或静音短切片，填 `heading`、`cards` 与逐卡 `reveal_at`。可加 `card.logo`。引用卡写明对应频道。 |
| `evidence_spotlight` | 单一原文、架构图或视频检视台。传 `capture_meta` 复用来源名和原文坐标，也可填写 `source_credit`、`highlight_box` 和 `highlight_at`。 |
| `reference_breakdown` | 1152×648 静音原片检视窗，填 `channel` 署名、`claim`、实测 `cut_points` 与最多三项 `metrics`。 |
| `studio_ui` | 剪辑台、代码编辑器、终端或音频工作台。排疑卡出现时干净替换剪辑台左侧媒体箱，退场恢复。 |
| `callout_rig` | 满屏真实视频加一个或两个信息叠层，填 `source`、`media_start` 与 `motion`。 |
| `explainer_clip` | 用内嵌或本地 `spec` 解释概念、数据及步骤。分步总结用 `t7_editorial_board`，数值关系用 `t3_finance_chart`。 |

单纯满屏实证可显式选 `fullbleed_rig`。视频源保留 0.2 秒尾部余量，媒体只在可用区间内播放。单窗或多窗对比都优先放与当前旁白直接相关的素材。

## 叠层与运镜

- `corner_tag` 是默认标注，放在左上安全区，可写副标题或设静音。
- `stat_badge` 用高不透明底板显示实测数字和单位。排除错误方向用 `strikethrough_list`，短结论用 `verdict_stamp`。
- `spotlight_box` 只标识实际核对过的局部像素目标，显式写 `box`、`target_verified: true` 和 `target_note`，最大 680×340。禁止盲贴、跨镜套用同坐标或压暗大片画面。非 `hold` 运镜中，取景框与底图围绕同一核验点连续推近，角落铭牌与数字角标保持固定。
- `prop_badge`、`reaction_cutout` 将透明 PNG、WebP 或 SVG 放到镜头下方侧区。填写 `source` 和镜内 `at`，可选 `duration`、`label`、`side: left|right` 和 `size: 140..260`。`title_sequence`、`corner_tag` 和 `evidence_spotlight` 的 `logo` 位于铭牌左侧。
- 默认 `push`、`pull`、`glide` 和 `punch` 按整镜时间推进。`hold` 仅用于内容本身有足够运动或需要静止检视的镜头。

合理使用条件下的参考短切片用于具体评论或分析，原片音轨全程静音。署名、画面和拆解指标在同一段内互相可核。审核可辨识私人信息及受限会话时，先在素材层移除。

`t7_editorial_board` 按 `title`、一至四个 `card`、可选 `footer` 建看板。卡片写明可执行结论，用 `sub` 补步骤、`data.bad` 和 `data.good` 做正反对照，`data.tag` 写实测指标。长文案优先 `data.layout: "rows"`，短项可并排。纯文字解说须有至少 26 字的有效信息，白板绘制须指定可识别的图标。

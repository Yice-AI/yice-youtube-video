---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频制片体系 v16.0。动笔前用 precheck-episode 三关硬拦截温吞/设门槛窄标题、标题正文脱节、大模型和稀泥叠甲词、制作端自嗨台词、密集小数堆砌和素材单一；按脑科学「前 10 秒砸预期摆抽屉 + 2 分钟防走神爆点 + 门槛递减 + 片尾截屏速查表」编排，支持横竖屏零裁切与克制动作音效。
---

# 一策 YouTube 视频制作 v16.0

以旁白首字安排 1920×1080 实拍、实录与解说画面，使用 `clean_cinema` 字幕并保留 `y ≥ 900` 字幕安全区。作品与操作用全屏暗场，方法拆解、选型与过场切到 `swiss_paper` 暖白点阵、黑色硬框和信号橙或克莱因蓝。

先按[破圈选题与包装](references/00-破圈选题与包装铁律.md)定标题与封面，再按[爆款逐字稿四遍炼金法](references/03-爆款逐字稿四遍炼金法.md)与[高留存叙事与三态画面](references/01-高留存叙事与三态画面铁律.md)打磨逐字稿，按[一手高光素材与代码造画](references/02-一手高光素材与代码造画母法.md)备素材。

## 前置三关：没过关不许往下走

```bash
kit/scripts/precheck-episode.sh --project <剧集目录> --stage <packaging|script|assets|all> [--json] [--output report.json]
```

| 关卡 | 不过关就不许 | 拦截项 |
| --- | --- | --- |
| `packaging` | 写分镜 | `bland_explanatory_title`（怎么选、使用指南、浅谈等说明文腔）；`narrow_gatekeeping_title`（“什么是大模型 / XX 架构拆解”这类给外行设门槛的窄标题，过不了前 2 秒四问：跟我有关吗/在乎吗/反直觉吗/一秒懂吗）；`promise_body_drift`（标题正文承诺脱节）；`thumbnail_candidates_insufficient`（封面候选不足 3 张或缺联系表）；并检查 `target_keywords` 搜索动作词埋点 |
| `script` | 跑配音 | `maker_plumbing_leak`（截图等几秒、无头浏览器、临时目录等内部细节）；`llm_hedging_fluff`（“一般来说、见仁见智、因人而异”等大模型和稀泥叠甲词）；`decimal_overload`（单幕堆砌 ≥4 个冷冰冰精确小数，须改成“省一半 / 六分之一”体感账）；`slow_or_meta_opener`（报幕、“不知道你有没有过这种经历”电视购物慢热铺垫、或前 60 秒念命令）；`flat_catalog_transitions`（平铺报菜名转场）；`chapter_closure_stop_signal`（章尾“XX搞定了/省心了，要是做另一件事怎么办”催人下车的假衔接结案词）；`unpaired_pain_point_visual`（痛点无真实反例画面）；`missing_hands_on_prompt_loop`（少于 2 章给可照抄提示词与前后变化）；并检查多工具教程是否讲清前置安装底座（`late_or_missing_setup_onboarding`）、是否直说真实边界/短板（`missing_honest_tradeoff`）及是否含空泛导购套话 |
| `assets` | 跑 `assemble-episode.sh` | `duplicate_asset_disguise`（同一画面换名存多份）；`insufficient_visual_clusters`（多工具教程独立画面少于 8 组）；`missing_external_showcase`（外部真实来源少于 2 个网站或不足 25%） |

包装写在剧集目录的 `packaging.json` 或 `packaging.md`（`title`、`hook`、`viewer_promise`、`target_keywords`、可选 `episode_kind`）。剧本第 3 列写画面规划，也可在旁白里用 `〔画面：…〕` 注明反例原件。专门教写脚本或自动化的选题在包装里写 `"maker_topic": true` 放行工程术语。返回码 0 通过、1 有拦截、2 参数或文件缺失。

## 导演与机房分工

- **主脑导演**（Gemini Neon / Claude 等顶级模型）独占审美与叙事：定明暗换场、写去 AI 腔口播稿、看 `showcase-candidates.jpg` 挑高光、为缺画面的段落写 `image2` 提示词、填 `episode-manifest.json`（优先用内建 14 套 `spatial_spec` 与 7 套 `onetake_spec`，严禁执行端手写一次性页面），成片后亲眼逐张核对抽帧图墙。
- **执行机房**（Codex / 后台任务）只做确定性工作：抓片、配音、录屏、抠图、温控压片（`workers=2, nice=10`）与门禁检查，不改色板、字号与版式，不自造静态字卡。

## 工具教程五条铁律（v15.0）

1. **标题与正文一个承诺。** 标题说“省 PPT 会员”，全片就讲 PPT；要讲 PPT、短片和封面，标题就写出这三样。先过 `packaging` 关再写分镜。
2. **口播只讲观众能照做的事。** 截图等几秒、临时目录、字段怎么填、渲染进程数都是制作端细节，一律不念。
3. **骂丑就放丑。** 每句说难看、模板感、翻车的口播，同镜必须出现真实的难看原件或默认直出画面，用 `split_wipe_compare`、`prompt_iter_workbench` 或 `literal_action_stage` 做前后反差。
4. **实操用提示词迭代台，不用黑底终端。** 讲工具用法时优先 `prompt_iter_workbench`：顶部大白话提示词胶囊逐拍落位，`16:9` 零裁边展示「↺ 默认直出」，到 `iter_at` 换成「✦ 加词精修后」，再推近接下一镜全屏交互。终端只留安装那一下，且放在第一分钟之后。
5. **素材先外采再自造。** 每期先跑 `harvest-showcase-media.sh --rank-highlights` 抓官网、论文项目页、公开演示原片，`collect-entity.sh` 取标志与 README 演示，`capture-web.mjs` 录官网；本地自造页面只补缺口，同一套页面不许换名字反复播。

叙事与实操按五分钟高完播率「一环扣一环」四道锁编排：① **前 15 秒亮成品立赌约 + 埋跨章悬念扣**（禁报幕与“不知道你有没有过…”慢热铺垫）：第一秒亮出桌面上**同一个工作文件夹**生出来的全套成品，用 3 格任务抽屉减负，并埋下留到后半程揭晓的红线悬念；② **前置 25 秒打通零基础底座 + 单文件夹一鱼多吃通关**：进第 1 个工具前先演清建空文件夹、粘链接装好并敲 `/` 调用；全片死咬同一份日常底料连续闯关（上一步的产出直接变成下一步的输入，严禁每章换无关新案例）；③ **章尾危机硬咬合（禁写“搞定了/省心了”结案休止符）**：每章结尾必须是上一环成品当场撞上下一环的现实死结（如手机竖图没法投会议室横屏电视、干录静态翻页发短视频没人看），`precheck` 硬查 `chapter_closure_stop_signal` 与 `flat_catalog_transitions`；④ **每 45 秒微观翻车秒修 + 第 2 分钟强爽点**：每个工具走完「拖入具体素材 → 具体结构/动作指令 → **V1 真瑕疵当场修成 V2**（如第 2 分钟实录按 `T` 秒切 36 套配色、按 `S` 弹隐藏提词器，或截图修第 4 秒错位高亮）→ 能力死角与协议红线」，砍光导购空话与叠甲词；⑤ **同文件夹大验收闭环 + 截屏速查表**：片尾拉回同一个文件夹核验全套成品首尾闭合，再用 `saveable_cheat_sheet` 停稳拉收藏，交稿前必过盲评五问。

## 多卡与跨镜衔接（v15.0）

- `progressive_sim_cards` 不写 `board`：所有 `stage_look` 下都是首卡居中弹簧跃出、后续卡片按词级 `at` 依次推开落位。`board` 开关（三框自开场全在位）只留给确需静态对照的个别镜头，不作默认。
- 传入 `16:9` 横屏媒体且 `zoom == 1` 时面板按 `16:9` 原画幅零裁边展示，严禁把横屏 PPT 或网页塞进窄竖框 `object-fit: cover` 裁切。**竖版作品（小红书 `3:4`、手机 `9:16`）严禁用 `16:9` 横屏浏览器窗口截半截录屏**：必须用 `kit/scripts/export-html-cards.sh --project . --url file:///.../cards.html --selector ".poster.xhs" --prefix xhs-v1` 直接导出原比例完整竖图（或 `record-web-cam.sh --aspect 3:4`），放入 `prompt_iter_workbench`（单张 `before_source`/`after_source` 自动立为 `3:4` 竖框，或多张 `before_sources`/`after_sources` 整套竖排平铺）、`progressive_sim_cards`、`split_wipe_compare` 或 `fullbleed_rig`（`framing: "portrait_card"`）。要看局部特写才显式填 `zoom > 1.05` 与百分比 `focus_x/focus_y`。
- 多卡总览下一镜接某张卡的全屏实操或成品时，填 `"exit_zoom_index": 1`（目标卡下标）与可选 `"exit_zoom_at"`（默认镜末前 `0.48s`），镜头点中目标卡并推近撑满 `1920×1080` 接下一镜，禁止生硬直切。`perspective_video_fan` 用 `"exit_zoom": true` + `"exit_zoom_at"` 推近 `focus_index` 焦点卡。
- 看板的 `cards[].pages: [{source,at}]` 在同一帧切换画面并配翻页声。大字用 `words[].line` 或 `editorial_punch.lines` 分两行。

```json
{"stage_mode":"hyperframes_block","spatial_spec":{"recipe":"prompt_iter_workbench","stage_look":"swiss_paper","data":{
  "heading":"一句话提示词改出发布会质感",
  "prompt_chips":[{"role":"主体","text":"深色科技新品演示页","at":0.15},{"role":"版式","text":"+ Bento 网格与大字数据卡","at":1.1},{"role":"约束","text":"+ 禁紫粉渐变模板感","at":2.0}],
  "before_source":"media/raw-v1.mp4","after_source":"media/polished-v2.mp4",
  "before_label":"↺ 默认直出","after_label":"✦ 加词精修后","iter_at":2.6,"exit_zoom_after":true,"exit_zoom_at":4.9}}}
```

## 制片入口

0. **定题与包装。** 按[破圈选题与包装](references/00-破圈选题与包装铁律.md)三圈交叉选题、五维提案卡拍板，写好 `packaging.json`。封面优先用**片中真实成品原图多图参考** `kit/scripts/thumbnail.sh --project . --title "主标题" --summary "一句精炼副标" --ref 成品1.png --ref 成品2.png --ref 成品3.png` 并行出 3 张高活力真图封面（超大数字电光蓝撞色、科技亮底扇形、暗调发光视窗，兼顾冲击力与呼吸感，严禁脑补假软件图标或塞死板坐标长约束）；尚未产生成品图时可用默认零约束直出。**运行 `precheck-episode.sh --stage packaging`，过关才写分镜。**
1. **四遍炼稿 + 前 30 秒双钩子盲测。** 严格执行[爆款逐字稿四遍炼金法](references/03-爆款逐字稿四遍炼金法.md)：先立「闯关实战线」或「破案算账线」单主脊椎（严禁平行报菜名），先出 2 版前 30 秒短句钩子择优，再对初稿连削四刀（卖产品痛感前置 → 写小说章尾留扣与 2 分钟爆点 → 脑科学抽屉节拍 → 出声砍三成水分压到 8–15 字短句）。剧本第 3 列写清每幕画面，痛点幕写明反例原件。**运行 `--stage script`（拦截 `flat_catalog_transitions` 平铺转场、`llm_hedging_fluff` 等），过关才配音。**
2. **素材与造画。** 入口均在 `kit/scripts/`，全部登记 `asset-ledger.jsonl`：
   - `harvest-showcase-media.sh --rank-highlights` 抓 `*.github.io`、官网、公开演示的高清 `.mp4`，自动切 4.5s 高光（非 16:9 自动 `blur_dark` 同源暗底）；`collect-entity.sh` 取标志与 README 演示；`capture-web.mjs` / `record-web-cam.sh` 录公开网页。
   - `rec-demo.sh` 录本机连续实操；`image2` + `cutout.sh` 造剪纸与壁画，喂 `cutout_parallax_stage`、`documentary_ken_burns`；`scout-video-scenes.sh long.mp4 --output scout` 从长片挑段；`find-media.sh`、`people-add.sh` 取实物与人物。
   - **运行 `--stage assets`，过关才装片。**
3. **配音并验帧。** `kit/scripts/voice.sh script.md --output voice --backend kaggle --speed 1.0`（可用 `--tts-model` 换云端开源语音底座），`natural_v7` 拦截句内无标点停顿超 165ms、词内能量塌陷 ≥ 16dB（110–260ms）与句中拖音，异常分段自动换 seed 重抽最多 3 轮。清单写好后跑 `kit/scripts/scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify` 逐镜核对首中尾帧。
4. **装配与审片。** `kit/scripts/assemble-episode.sh episode-manifest.json --output out`（默认 2 个低优先级进程，`--draft` 快速试片），再跑 `kit/scripts/audit-v3.sh --v10 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4`，并目检、听审。
5. **封面定稿与多平台画幅适配。** 成片或样稿齐备后用 `thumbnail.sh --ref ...` 带入真实作品截图定稿（YouTube 默认 `--aspect 16:9`；同步发抖音中视频必须另外跑 `--aspect 3:4` 竖封面与 `--aspect 4:3` 横封面原生重排，严禁把 `16:9` 横图硬裁成 `3:4` 切掉左右大字），再用 `thumbnail.sh --select` 导出 `< 2 MB` JPG 并入账；选图必查**全图零错别字、零脑补假软件图标、右下角无伪造时长框、缩略图一眼抓人**。

## 视觉路由

| 镜头任务 | 路由（详见[双擎高阶视觉路由](references/10-双擎高阶视觉路由.md)） |
| --- | --- |
| 连续变形、前后擦除、竞速、手绘线沸 | `onetake_clip`：`split_wipe_compare`、`handdrawn_sketch_stage`、`duplicate_laser_sweep`、`bitmap_lock_glitch`、`energy_roadmap_dive`、`live_control_sync`、`capsule_archive_seal`（默认 180° 快门积分） |
| 提示词迭代、章节抽屉、截屏速查表、多视频 3D 阵、剪纸视差、焦点树、渐进卡 | `hyperframes_block`：`prompt_iter_workbench`、`chapter_drawer_grid`、`saveable_cheat_sheet`、`triptych_curtain`、`kinetic_title_bridge`、`perspective_video_fan`、`logo_bento_stage`、`cutout_parallax_stage`、`documentary_ken_burns`、`step_tree_focus`、`progressive_sim_cards`、`formula_pill_chain`、`carousel_3d_select`、`layer_explode_3d`、`roadmap_thread_camera`、`literal_action_stage` |
| 真实网页与录屏实证 | `fullbleed_rig` / `callout_rig` 配 `focus_push` 或分段 `camera_moves` |

目标每镜 4–6 秒，全片均值 ≤ 6.5 秒；满屏占实录时长 ≥ 70%，斜框 ≤ 全片 15%，带框镜头不相邻。亮场桥 `kinetic_title_bridge` 用 1.2–1.8 秒、按口播触发的 `words: [{text, at}]` 与 `underline_at`。三联幕布每次三条不同视频，85 秒内最多两次。

## episode-manifest.json

时间单位为秒，镜头 `start`、`end`、旁白 `at` 和 `firstCharTime` 以全片起点为零，`overlays[].at` 为镜内相对时间，素材路径相对清单。`kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 生成 30fps 分镜草稿。清单声明 `episode_kind: "tool_tutorial"`，每镜填 `case_tag`，并以 `semantic_alignment` 引用逐镜台账（`shot_id, start, end, quote, evidence, case_tag`）；同镜并列多个作品用 `case_windows: [{tag,start,end}]`，单一作品占比不超过 30%。

```json
{"id":"fan-open","act":"act-1","anchor_cue_id":"0-1","start":0,"end":5,"stage_mode":"hyperframes_block",
 "spatial_spec":{"recipe":"perspective_video_fan","data":{"badge":"✦ 修改后",
   "items":[{"source":"media/demo-1.mp4","label":"01 · 3D 视窗"},{"source":"media/demo-2.mp4","label":"02 · 物理弹簧"},{"source":"media/demo-3.mp4","label":"03 · 核心高光"}],
   "focus_index":2,"focus_at":2.2,"exit_zoom":true}},
 "spoken_topic":"先看重制后的多组真实动效成品","visual_subject":"多卡片 3D 扇形动态视频墙",
 "semantic_tags":["动效","修改后对比"],"semantic_binding":"conceptual_explainer"}
```

音频与人声轨、`captions`、`callout_rig` / `fullbleed_rig`、`triptych_cards`、`evidence_spotlight`、`reference_breakdown`、`studio_ui` 字段保持向下兼容；浅底舞台自动登记 `light_zones` 并切深底白字胶囊字幕。录屏入口记录实际点击、键入、拖动和翻页，镜头内用 `interactions: [{action, at}]` 标注可见动作。新脚手架的 `review_pack` 随组装导出全镜头图墙、480p 有声版与两段无字幕盲审片。

## 声音与审计

- 内置 5 首公有领域节奏型 BGM（`builtin:forward-drive`、`city-groove`、`focus-minimal`、`bright-step`、`calm-tech`）与 27 款真实动作音效（`kit/assets/sfx/`）。**音效奉行克制点缀（每分钟约 8–22 次，严禁无动作乱塞）**：只在章节换场、卡片弹入、点中推近、前后擦切等真实可见动作点轻配音效，正常口播与展示留足安静呼吸感（允许最长 18 秒安静讲述）。`EpisodeAudioMixer` 校准 −14.5 ± 0.8 LUFS、真峰值 ≤ −1.0 dBTP。
- `audit-v3.sh --v10` 包含 `aspect_crop_integrity_gate`（无 `zoom > 1.05` 声明却被裁掉超过 12% 判 `excessive_aspect_crop`）、`portrait_aspect_integrity_gate`（口播承诺展示 `3:4` / 小红书套图等竖版成品却塞入横屏截半录屏直接拦截）、`text_box_containment_gate`（组件方框文字戳破右边界或字色对比度 `< 3.0` 直接拦截）、视频帧级 `cross_stage_asset_dedup_gate`（同一视觉模板跨镜 > 2 次拦截，可登记一次 `callback_of`）、`external_showcase_diversity_gate`（90 秒以上教程独立画面簇 ≥ max(6, ⌈时长/30⌉) 且含多源外采）、`sfx_diversity_and_sync_gate`（拦截每分钟超 22.8 次的音效轰炸与 1.8s 连响 ≥ 4 次的杂乱堆叠）与 `recipe_monotony_and_workbench_gate`（单类结构框图全片上限 `max(3, 6%镜数)`、`roadmap_thread_camera` 上限 2 次，无真实 `logo` 时星号白框最多 1 次，且 120 秒以上实操教程至少 2 镜使用 `prompt_iter_workbench`）。完整门禁见[审片门禁](references/review-gates.md)。
- 精修参考音用 `./install.sh --configure-voice 参考音.wav 原文.txt` 保存，换机私下复制 `~/.config/yice-youtube-video/`。公开画面严禁出现私人路径、用户名、邮箱或凭据。

主脑交片前关字幕、有声连看全章：反例与真实操作看得懂、口播数量与同屏成品一致、没有连续三秒的死镜、前六十秒不出现终端、字幕带不压核心文字、每种声音都对应可见动作。相关参考：[配音](references/voice.md)、[导演层](references/director-layer.md)、[素材采集](references/media-acquisition.md)。

---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频制片体系 v12.0。双擎 .mp4 真动态视频贴图、7 大类空间/Onetake 新配方（3D 视频墙、Bento 拼装、剪纸视差、纪录片 2.5D 解剖、工作流焦点树、渐进装置卡、因果胶囊链、中线/斜切/竞速擦除、8fps 铅笔水彩与 Riso 半调）、双调性母版、满屏实操与机器门禁。适用于旁白、真实录屏、分镜、成片和返修。
---

# 一策 YouTube 视频制作 v12.0

以旁白首字安排 1920×1080 实拍、实录与解说画面，使用 `clean_cinema` 字幕并保留 `y ≥ 900` 字幕安全区。

先按[五拍叙事与三态画面](references/01-高留存叙事与三态画面铁律.md)排口播、镜头形态与跨镜承接，再按[一手高光素材与代码造画母法](references/02-一手高光素材与代码造画母法.md)打通 `.mp4` 真动态视频贴图与三套代码造画配方。整片统一选用 `cyber_glass`（暗黑玻璃，13–16px 胶囊标状态）或 `editorial_paper` / `scroll_paper`（暖米白画布，自动切换深色胶囊字幕）其中之一贯穿全片。

## 导演 × 机房分工与新题三层防翻车铁律

1. **角色死边界（锁死审美下限，严禁手搓一次性丑页面）**
   - **主脑导演（Gemini Neon / Claude 等顶级模型）**：独占全部审美与叙事决策——① 定整片唯一调性母版（`cyber_glass` 或 `editorial_paper` 二选一锁死到底）；② 写去 AI 腔口播稿；③ 审看 `showcase-candidates.jpg` 挑高光原片，为无现成画面的段落撰写 `image2` 生图提示词；④ 编写 `episode-manifest.json`（优先直接调用内建 11 套 `spatial_spec` + 7 套 `onetake_spec` 成品模具，**严禁让执行端临时手写简陋 HTML/CSS 页面**）；⑤ 成片产出后**必须亲眼逐张打开抽帧/动作条图片核验**，不盲信脚本 JSON 通过。
   - **执行机房（Codex / 后台任务）**：仅承担零审美自由度的确定性苦力——运行 `harvest-showcase-media.sh` 抓片、`voice.sh` 原速配音、`record-web-cam.sh` 深色实操录屏、`cutout.sh` 抠图、`assemble-episode.sh` 温控压片（`workers=2, nice=10`）与 `audit-v3.sh --v10` 门禁检查，**严禁擅自改动色板、字号、版式或自造静态字卡凑数**。
2. **换任何新主题的三层素材兜底漏斗（期期必有高光画面）**
   - **第一层（有公开炫酷演示的新模型/视觉工具）**：先跑 `harvest-showcase-media.sh --rank-highlights` 无损抓取 `*.github.io` 论文项目页、官网发布站、GitHub/X 原生高清 `.mp4`（非 16:9 自动合成 `blur_dark` 同源模糊暗底），自动剔除白底文字死页并切出 4.5s 最高分动态切片，喂入 `perspective_video_fan`、`split_wipe_compare` 或 `formula_pill_chain`。
   - **第二层（官网朴素的干货工具/命令行插件）**：严禁傻滚白底文档凑时长！只录最核心的深色真实操作闭环（输入 → 执行 → 结果交互，占 30%–55%），其余优势对比与流程拆解一律套用 `progressive_sim_cards`（`1% vs 100%` 实时进度 + 动态小窗）、`step_tree_focus`（连线逐笔生长 + 焦点在 `① → ② → ①` 动态跳转）、`layer_explode_3d` 或 `handdrawn_sketch_stage`。
   - **第三层（零现成视频的抽象观点/故事/历史机制）**：直接启用 `image2` + 代码造画三公式——`cutout_parallax_stage`（白底生图抠图 + 4px 奶油剪纸白边 + 三层视差卷轴 + 烟尘粒子 + 实时计步）、`documentary_ken_burns`（16:9 艺术大图 2.5D 慢推摇飘金粉 + 一图拆三卡局部解剖）、`handdrawn_sketch_stage`（8fps 铅笔水彩微抖 / Riso 半调网点），凭空造出纪录片级动态画面。

## 工具教程

清单声明 `episode_kind: "tool_tutorial"`。前 0–5 秒展示官方复杂成品或高冲击改前/改后结果。接着录下真实安装命令、输入提示词、提交与 Agent 执行，等待加速时标出倍速。最后用 1080p 满屏跟焦演示真实成品的点击、修改和边界验证。每个工具使用自己的输入与真实输出，禁止虚构六行提纲或留白网页代拍。

目标每镜 4–6 秒，全片均值 ≤ 6.5 秒。满屏占实录时长至少 70%，斜框占全片至多 15%，带框镜头不能相邻。多贴图与视频墙配方均使用独立 3D 空间运动并通过 v10/v12 审计；平面静态拼贴仍会拦截。

## 制片入口

0. **定题与破圈包装（动笔前必做）。** 未定题或冷启动选品时，按 [破圈选题与包装铁律](references/00-破圈选题与包装铁律.md) 执行「小号高倍黑马库 × 本人真实底牌库 × 第 1 秒视觉炸场度」三圈交叉筛选，用五维提案卡供拍板。**先定高点击标题与封面构图，第 0–5 秒直接甩最终惊艳成品立住信任。**
1. **五拍拆稿定证据。** 依[本机 Skill 协同表](references/01-高留存叙事与三态画面铁律.md#本机-skill-协同表)用 hyperframes-creative 排证据顺序、humanizer-zh 审口播、cheat-score 查钩子。动效与物理接力优先直接填写 v12.0 内建 `spatial_spec`（11 套空间配方）与 `onetake_spec`（7 套快门配方）。每句注明要证明的事实、实际画面主体、语义绑定和首字锚点。
2. **按主体找素材与代码造画。** 以下入口均在 `kit/scripts/`，保留素材来源和可复查的时间窗。
   - 本机实操用 `rec-demo.sh` 或常驻录屏师，保留连续操作。
   - 公开网页、文档与开源仓库用 `record-web-cam.sh` 录制深色高倍率画面。
   - 学术论文主页（`*.github.io`）、官方发布站与公开演示帖的一手高清 `.mp4` 原片用 `harvest-showcase-media.sh` 无损抓取并自动筛出 4.5s 高光切片（竖片/方片自动 `blur_dark` 同源暗底；可直接喂入 `perspective_video_fan`、`split_wipe_compare`、`progressive_sim_cards` 与 `formula_pill_chain`！）；品牌标志与页面档案用 `collect-entity.sh`。
   - `image2` + `cutout.sh` 生产独立剪纸/壁画高光资产，喂入 `cutout_parallax_stage` 与 `documentary_ken_burns`。
   - 往期成片或长录屏用 `scout-video-scenes.sh long.mp4 --output scout` 筛选选段。
   - 具象实物特写和人物抠像分别用 `find-media.sh`、`people-add.sh`。
   - 原片拆解评论使用 `reference_breakdown`，原片静音，明确频道署名和实测切点。
3. **配音并验帧。** 执行 `kit/scripts/voice.sh script.md --output voice --backend kaggle --speed 1.0`。默认 `long_paragraph` 优先 65–115 字、最多 5 句，`natural_v7` 保留呼吸。清单写好后运行 `kit/scripts/scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify`，按首、中、尾帧逐镜核对台词及因果顺序。
4. **装配与审片。**
   - 需要连续光学变形、前后擦除（`split_wipe_compare`）或 8fps 手绘/Riso（`handdrawn_sketch_stage`）的镜头用 `onetake_clip`。
   - 多视频 3D 墙（`perspective_video_fan`）、Bento 拼装（`logo_bento_stage`）、剪纸视差（`cutout_parallax_stage`）、纪录片解剖（`documentary_ken_burns`）、工作流焦点树（`step_tree_focus`）、渐进装置卡（`progressive_sim_cards`）和因果胶囊链（`formula_pill_chain`）用 `hyperframes_block`。
   - 实录优先用 `fullbleed_rig` 满屏跟焦。
   - 执行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out` 装片（默认 2 个低优先级进程，`--draft` 快速试片）。最后执行 `kit/scripts/audit-v3.sh --v10 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4`，并目检、听审。
5. **封面与打包。** 用 `kit/scripts/thumbnail.sh --project . --title "标题" --summary "内容摘要"` 走 `image2` 原生直出 3 张候选与联系表，`--select` 导出 `< 2 MB` 高清 JPG 并入账。

## 反简陋 PPT 铁律

| 镜头任务 | 视觉路由（详见 [双擎高阶视觉路由](references/10-双擎高阶视觉路由.md)） |
| --- | --- |
| 需要连续变形、激光擦除对比、2×2 竞速或手绘线沸 | `onetake_clip`：`split_wipe_compare`、`handdrawn_sketch_stage`、`duplicate_laser_sweep`、`bitmap_lock_glitch`、`energy_roadmap_dive`、`live_control_sync`、`capsule_archive_seal`（默认 180° 真实快门积分）。 |
| 多视频 3D 阵、剪纸视差、古画拆卡、焦点树与渐进对比卡 | `hyperframes_block`：`perspective_video_fan`、`logo_bento_stage`、`cutout_parallax_stage`、`documentary_ken_burns`、`step_tree_focus`、`progressive_sim_cards`、`formula_pill_chain`、`carousel_3d_select`、`layer_explode_3d`、`roadmap_thread_camera`、`literal_action_stage`。 |
| 真实网页与录屏实证（目标占全片 ≥ 50%） | `fullbleed_rig` / `callout_rig` 配合 `focus_push` 或分段 `camera_moves`。 |

新片直接在 `episode-manifest.json` 填 `spatial_spec` 或 `onetake_spec`，引用本地真实截图或 `.mp4/.webm` 视频。`sample-spatial-frames.cjs` 采样时自动 seek `<video>` 并等待 `seeked`；Onetake 构建期自动预解 24fps 确定性帧序列，彻底杜绝闪黑与死截图。

## episode-manifest.json

所有时间用秒。镜头 `start`、`end`、旁白 `at` 和 `firstCharTime` 以全片起点为零。`overlays[].at` 是镜内相对时间。素材路径相对清单解析。

用 `kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 生成 30 fps 分镜草稿（轮换 HyperFrames v12 空间配方、Onetake v12 过程配方和满屏实录）。清单和单镜可设 `theme` 为 `pine`、`obsidian`、`aurora_indigo`、`paper_cool` 或 `paper_warm`，并在双擎 spec 中统一 `stage_look`（`cyber_glass` 或 `editorial_paper` / `scroll_paper`）。

`gsap` 是可选覆盖项，省略时自动发现本机 GSAP。

```json
{
  "title": "实操样片",
  "filename": "episode",
  "voice_manifest": "voice/voice-manifest.json",
  "shots": [
    {
      "id": "fan-open",
      "act": "act-1",
      "anchor_cue_id": "0-1",
      "start": 0,
      "end": 5,
      "stage_mode": "hyperframes_block",
      "spatial_spec": {
        "recipe": "perspective_video_fan",
        "data": {
          "badge": "✦ 修改后",
          "items": [
            {"source": "media/demo-1.mp4", "label": "01 · 3D 视窗"},
            {"source": "media/demo-2.mp4", "label": "02 · 物理弹簧"},
            {"source": "media/demo-3.mp4", "label": "03 · 核心高光"}
          ],
          "focus_index": 2,
          "focus_at": 2.2
        }
      },
      "spoken_topic": "先看重制后的多组真实动效成品",
      "visual_subject": "多卡片 3D 扇形动态视频墙",
      "semantic_tags": ["动效", "修改后对比"],
      "semantic_binding": "conceptual_explainer"
    }
  ]
}
```

- 音频与人声轨、字幕 `captions`、实录框 `callout_rig` / `fullbleed_rig`、`triptych_cards`、`evidence_spotlight`、`reference_breakdown` 与 `studio_ui` 字段契约保持向下兼容。
- 轻量化浅底舞台（`editorial_paper`、`scroll_paper`、`pencil_watercolor`、`paper` / `tabletop` / `riso` / `ember`）装配时自动登记 `light_zones`，字幕自动切为烟熏深底白字胶囊保证对比度。

## 应用与审计

- `natural_v7` 保留自然呼吸；`EpisodeAudioMixer` 校准 −14.5 ± 0.8 LUFS、真峰值 ≤ −1.0 dBTP。
- `audit-v3.sh --v10` 统一执行双调性一致性校验、合规短题/文物角标放行、标题与主体 30fps 防碰撞检查、三态与双擎占比校验、`vframes_*` 单视频归并去重、OCR 防泄露与声学母带验收。
- 实测数字保留可核对底账，严禁公开屏幕出现私人本机路径、用户名、邮箱或凭据。

相关参考见 [一手高光素材与代码造画母法](references/02-一手高光素材与代码造画母法.md)、[双擎高阶视觉路由](references/10-双擎高阶视觉路由.md)、[配音规则](references/voice.md)、[导演层](references/director-layer.md) 和 [审片门禁](references/review-gates.md)。

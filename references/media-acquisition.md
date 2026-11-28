# 素材采集（v15.0）

先说明画面要证明什么，再找素材。需求单可用 `kit/template/asset-needs.example.md` 规划，用同目录 JSON 模板驱动批量网页采集。每项写清：论点、素材类型、候选 URL、截取方式（静帧/滚动秒数/高亮原句）、许可和镜头号；采集结果统一原子写入每期 `asset-ledger.jsonl`。文件下载成功不等于该使用方式已获授权。

**外采优先，装片前过第三关。** 每期先跑外部采集再录本地页面；素材备齐后运行 `kit/scripts/precheck-episode.sh --project . --stage assets`，它按画面指纹拦截换名重复的素材（`duplicate_asset_disguise`），要求多工具教程至少 8 组独立画面（`insufficient_visual_clusters`），并要求账本里至少 2 个外部网站、占 25% 以上（`missing_external_showcase`）。账本每条写清 `url`（外部原始地址）与 `sourceType`（如 `harvest-showcase-media`、`collect-entity`、`capture-web`），本机 `127.0.0.1` 页面不算外采。成片阶段 `external_showcase_diversity_gate` 再按成片核对：90 秒以上教程独立画面簇 ≥ max(6, ⌈时长/30⌉) 且含多源外采。

## 核心采集路线

| 路线 | 适用画面 | 执行与交付 |
|---|---|---|
| 一手高光动态原片猎手 | 学术论文 `*.github.io` 项目主页、官方 Release 演示页、公开实机推文中的高冲击对比/3D/实机视频 | `harvest-showcase-media.sh --rank-highlights` 无损抓取原生 MP4/WebM 流（拦截二创视频站域名），非 16:9 画幅自动合成 `blur_dark` 同源高斯模糊暗底，按运动能量与细节密度自动切出 `4.5s` 高光切片并输出 `showcase-candidates.jpg` 直通双擎 `.mp4` 贴图。 |
| 网页与文档净屏实拍 | 官方发布页、技术博客、公开仓库、文档，用页面原文支撑具体论点 | `capture-web.mjs`（`30fps`、`1.25x+` 倍率、预滚解码懒加载图、自动隐藏弹窗横幅）导出 `1920×1080` 静帧、6–8 秒滚动视频及含原文像素框的 `capture.json`（直通 `evidence_spotlight`）；深色交互式操作用 `record-web-cam.sh`。 |
| AI 产品与开源实体深扒 | 产品官网首屏、GitHub README 演示视频、官方 SVG 标志 | `collect-entity.sh` 下载官网/README 演示流并提取 `.svg` 矢量标志冻结入账（直通 `logo_bento_stage` 与角标）。 |
| `image2` 美术与剪纸造画 | 无现成视频的抽象概念、人文历史剧场、高细节壁画/剖面拆解 | 由主脑导演撰写提示词调用 `image2.py` 生成白底独立主体（经 `cutout.sh` 抠图喂入 `cutout_parallax_stage` 三层剪纸视差）或 16:9 艺术大图（喂入 `documentary_ken_burns` 2.5D 推摇与一图拆三卡）。 |
| 开放授权高清影像与抠像 | 真实物理特写空镜、历史公有领域资料、百科人物与实物贴图 | `find-media.sh` / `open-media.mjs` 检索 Pexels、Pixabay、Commons、Openverse，视频硬筛 `≥1920px` 横屏源；人物与实物经 `people-add.sh` / `cutout.py` 抠图并通过主体完整性校验。 |
| 公开数据动态重绘 | 增长曲线、对比指标、架构关系 | 记录原始数据数值、单位、时间范围与来源，用 `hyperframes_block`、`onetake_clip` 或 `t3_finance_chart` 原生动态重绘，不直接搬用他人低清静态截图。 |

本机实操录屏（`rec-demo.sh`）和封面生成（`thumbnail.sh` 原生调用 `image2`）按各自标准入口执行并登记同一账本。更多命令细节见 [kit 素材入口](../kit/docs/assets.md) 与 [实体采集入口](../kit/docs/entities.md)。

## 许可账本与优先级

每件素材至少保留 `id`、镜头、类型、原始来源 URL、采集日期、作者、许可名称/URL、署名文本、本地文件和 SHA-256。素材优先顺序：

1. 本人实测录屏与真实运行输出。
2. 官网、官方发布页与官方原生演示 `<video>`（成片引用静音、短段、带来源域名）。
3. 官方 press kit / 媒体包与矢量标志。
4. GitHub / Hugging Face 仓库实证。
5. 论文、基准榜单与权威报道。
6. 高清免版税实拍特写（只作比喻空镜，不冒充产品实测）。
7. `image2`（用于 `thumbnail.sh` 封面直出，以及无现成实拍素材时配合 `cutout_parallax_stage` / `documentary_ken_burns` 进行高审美代码造画，严禁伪造产品实测截图）。

## 底线与洁净室原则

- 只截取支撑论点所需的短片段，标明来源；长视频选段先跑 `scout-video-scenes.sh` 自动剔除纯色字卡、跨镜硬切与底部旧烧录字幕。
- 第三方创作者画面仅用于针对其内容或剪辑的评论拆解（Fair Use），全程静音并在 `reference_breakdown` 或对比卡显式标注 `channel` 署名。
- 无头采集不复制个人浏览器登录态；遇到登录墙、付费墙或人机验证码如实跳过回报，改用脱敏截图或 `onetake` `UIK` 动态界面重建。
- 同一套网页或 PPT 不许换文件名反复播放；成片的 `cross_stage_asset_dedup_gate` 会对内嵌视频中帧和版式色彩签名去重，同一视觉模板跨镜超过 2 次（除一次 `callback_of`）直接拦截。
- 洁净室纪律：迭代 Skill 代码的会话不触碰历史已发布剧集目录；制作新剧集时统一调用 `kit/scripts/` 标准 CLI，不在剧集目录私写一次性拼片脚本绕过门禁。

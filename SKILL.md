---
name: yice-youtube-video
description: 一策 YouTube 中文教程视频的整套制作体系（v2）：旁白稿 → Modal GPU 克隆配音与五维卡顿检测 → 逐句「画面需求 → 工具」路由与当场生产素材 → 高阶动效版式组件库装配 → HyperFrames 本机渲染 → 机器质感门禁与抽帧审片。8–10 分钟、不露脸、AI 工具实战。Use when 用户要做/剪/规划/返修一期一策 YouTube 视频、写分镜或节拍表、按句生产画面素材、调用工具示范镜头、审片、开新一期，或提到“下一期视频”“剪出来”“YouTube 教程”“hf-ep”“导演层”。
---

# 一策 YouTube 视频制作（v2）

一期视频由三层协同完成：
1. **逐句导演与即时制片层**：每句话先判断“观众这一秒该看见什么”，再查**「画面需求 → 生产工具 → 高阶组件」路由表**；手里没有严丝合缝的画面，**剪辑当下直接调工具造出来**（录屏、网页抓取、图库实拍、`image2` 写实概念图/透明道具、精密 SVG 蓝图、Modal GPU `ltx2` 动态视频），绝不拿无关旧素材硬凑。
2. **高阶动效与版式组件库（`$KIT/template/recipes/`）**：统一承载影棚级光影、景深推拉、锚点动效与排版，**执行代理只往现成组件槽位里填素材和实测数据，严禁手搓裸 HTML/CSS/SVG 贴画，严禁把 16:9 横屏画面竖裁成窄条**。
3. **HyperFrames 确定性渲染层（锁定 `@0.9.52`）**：本机把组建好的工程渲染为 1080p30 成片，配合混音母带（−14 LUFS）与双重质感门禁出片。

- **kit**：`$KIT` = 本 skill 目录下的 `kit/`（软链接安装后同步到 `~/.claude/skills/yice-youtube-video/kit`、`~/.codex/skills/yice-youtube-video/kit`、`~/.gemini/config/skills/yice-youtube-video/kit`）。命令见 [kit/README.md](kit/README.md)，工具示范镜头见 [kit/docs/tool-demos.md](kit/docs/tool-demos.md)，组件字段见 [kit/docs/recipes.md](kit/docs/recipes.md)。
- **环境**：`~/.config/yice-video/env` 配置 `YICE_WORKSPACE`（个人IP 工作区）与 `YICE_TOOLKIT`（`claude-code-video-toolkit`）。

---

## 角色与分工（不越位、不靠中心亲手搓全片）

**核心目标**：靠本 skill 的明确路由规则、高阶预设组件库、工具示范镜头和硬门禁，让执行代理（Codex）独立稳定剪出“很厉害、很高级、能直接发”的成片；中心只做规划、写稿把关、抽帧审质感与拍板，不耗费中心额度逐镜手搓 HTML。

- **中心（总调度）**：定选题与旁白稿、审配音试听切片、审每章接触表与 100% 原尺寸质感抽帧、核对实测数字与隐私打码、开具编号返修单、向用户交付结果。需要补充新组件类型时，先做出金样组件合入 `kit`，再交执行代理填空复用。
- **Codex（通过 `codex-commander` 派活）**：
  - 跑 Modal GPU 克隆配音、五维卡顿体检与单句热修；
  - **剪辑与即时制片一体化执行**：逐句对照 `references/director-layer.md` 的「画面需求 → 工具 → 组件」表，已有合格素材直接绑定，缺画面当场调用 `kit/scripts/produce-asset.sh` 生产（`image2` / `props` / `ltx2` / `capture-web` / `find-media` / 生成录屏单）并自动记入 `asset-ledger.jsonl`；
  - 严格选用 `kit` 组件库与 `kit/docs/tool-demos.md` 示范镜头参数生成 `beats.json`，构建、跑过 `kit check`（含画幅防竖裁、近静止检测、空框截字门）、混音渲染成片、导出逐句/3 秒接触表。
- **录屏执行（`rec-shot` 确定性脚本 / DeepSeek Harness 常驻代理）**：桌面软件实操走 `rec-shot` 或投递 `.scratch/youtube/dsh-inbox/` 由 Harness 录制；公开网页滚动与交互录屏由 Codex 用 Playwright（`capture-web.mjs`）直接完成；Claude 界面只用打码截图，绝不录屏。
- **用户**：只看成片结果；只拍板必须本人决定的事（系统权限弹窗、敏感外部操作、最终发布）。

---

## 一期标准流程（剪辑与制片融合闭环）

1. **旁白稿** `$YICE_WORKSPACE/.scratch/youtube/episodes/<ep>/script.md`
   - 按章分节，每句独立编号（如 `0-1`、`3-14a`），口语短句（单句 ≤20 字），前 15 秒亮出反常识结果或硬核实测对比。
   - 中英之间不加空格，数字写顺口读法；所有数字必须有实测底账〔出处〕支撑（〔〕注记不朗读）。8–10 分钟正片约 2,300–2,900 字。
2. **GPU 克隆配音与五维韵律门禁**（`kit/scripts/voice.sh`，详见 [references/voice.md](references/voice.md)）
   - **默认走 Modal GPU（A10G bf16 `Qwen3-TTS-12Hz-1.7B-Base`）**，不再默认跑本机 MLX 8bit（避免卡电脑及 8bit 长上下文韵律崩坏）；Modal 不可用时才按配置切云端备用（Kaggle）或 `--backend local`。
   - **语义句组批处理**：每章按语义切为 3–5 句一组（约 12–22 秒/组），单次请求传入句组列表共享同一个 `voice_clone_prompt` 连续生成，既保上下文语气连贯，又杜绝几十句整章单次自回归导致的吞字、句中微卡顿与降调。
   - 生成后必过 **ASR 字面/同音核对 + 重校准五维 `voice-check.py`（拖字、无标点犹豫、句内相对能量骤降 micro-dip、异常降调、句组接缝跳变）**，告警清零并留存试听切片后才进剪辑。
3. **逐句视觉路由与当场生产素材**（详见 [references/director-layer.md](references/director-layer.md) 与 [kit/docs/tool-demos.md](kit/docs/tool-demos.md)）
   - **彻底废除“只用已有素材硬凑”**：逐句先填「旁白句号 → 观众这一秒要看见的具体事物 → 画面类型 → 生产工具 → 承载组件」。
   - 盘点现有素材库：有完全匹配、清晰且运动充足的真实画面才复用（填充素材同文件每章 ≤2 次、全片 ≤4 次，且不复用同一入点）。
   - **但凡缺画面、对不上旁白关键词、或源区间近静止 >1.8 秒，剪辑环节当场运行 `kit/scripts/produce-asset.sh` 造出来**：
     - 真实软件/命令行操作 → `rec-shot.sh` / Harness 录屏单 / `capture-web.mjs`
     - 公开网页、论文、GitHub、新闻证据 → `capture-web.mjs` / `collect-entity.sh`
     - 抽象概念、比喻、具象场景图 → `produce-asset.sh --kind metaphor-image`（`image2` 16:9 `r_plus` 多候选挑优）或 `--kind prop-cutout`（透明实物道具）
     - 架构、流程、拆解关系 → 直接用高阶组件 `blueprint-diagram`（填结构化节点/连线 JSON 生成精密工程蓝图动画，禁手画简陋贴纸）
     - 需要真实物理动态而图库没有的场景 → `produce-asset.sh --kind motion-video`（Modal GPU `ltx2` 生成 3–5 秒 16:9 写实动态镜头，同批热容器集中跑）
     - 纪实空镜与人物反应 → `find-media.sh`（Pexels/Pixabay 1080p，单期 ≤60 次）+ `people-add.sh`
     - 实测数据对比 → 绑定底账 JSON 走 `shot-wall` / `ruler-measure` / `bar-compare` / `num-split`
4. **高阶组件库装配（`beats.json` → `build.mjs`）**
   - 对照 `kit/docs/tool-demos.md` 中的标准示范镜头（`D1`–`D7`）填参，执行者只填组件 `props` 槽位与口播锚点 `@关键词`，**严禁自写裸 HTML/CSS/SVG 图形充当画面**。
   - **16:9 画幅铁律**：两条横屏成片或界面做对比时，必须用 `split-compare` 的**双 16:9 完整视窗模式**（左右/错落完整 16:9 画框 + 点名侧放大聚焦、对侧压暗），**严禁把 16:9 视频 `object-fit: cover` 竖裁进半宽窄条**。
5. **混音、渲染与机器质感硬门**
   - 接入原创/曲库 BGM（Demucs 人声机测合格，配音段自动压低 24dB）与克制的动作音效，母带归一到 `−14 LUFS / ≤ −1 dBTP`。
   - 先跑 `npm run check -- --visual-only` 预检，渲染完跑 `npm run check -- --rendered <mp4>`：自动拦截 HyperFrames 错误、16:9 横屏被竖裁、源画面 >1.8s 近静止、空框/黑帧、截断字/占位词、重复超限。
6. **中心 100% 质感审片与交付**
   - 中心用 `review.sh` 看全片 3 秒接触表、逐句匹配表及关键帧 100% 原尺寸截图，按 [references/review-gates.md](references/review-gates.md) 审自然度与高级感。过关后交付成片 mp4、SRT、账本报告、缩略图 3 选 1 与标题备选；未经用户明确同意，绝不上传或发布。

---

## 什么叫“很厉害、很高级”（成片硬标准）

- **第 0 帧定乾坤，前 15 秒强反差**：开场第一眼就是饱满、有景深与光影层次的完整画面，缩略图与开场是同一个视觉锤。
- **句句有真凭实据，绝不图文脱节**：旁白说到哪个词，画面上必须看得见那个具体物件、操作、数据或精确比喻，不允许拿泛泛的打字手或空桌面糊弄。
- **完整画幅与光学质感**：横屏录屏与成片完整呈现关键区并推近到字高 ≥28px；暗调影棚（`#0c0d0e` 径向顶光 + `#efe8dc` 暖白思源宋/等宽字 + `#ff4a2b` 朱红功能标 + 6% 动态胶片颗粒 + 四角光学暗角）与精密纸面工作台（光纤/接触双层阴影、玻璃微反光）统一全片气质，无廉价平涂色块、无简陋矢量小贴画、无赛博霓虹。
- **镜头永远活在呼吸里**：每个镜头都有线性推拉（`drift 1.00→1.08`）与锚点驱动的二次动作（焦点框缩进、高亮扫过、工单流转、播放头点亮、印章落下微震），无超过 1.8 秒的死画面。
- **配音像真人在对面聊**：Modal bf16 语义句组合成，吐字清晰、换气克制、转折停顿自然，无吞字、无句中卡壳、无机械播音腔。

---

## 硬规矩与预算红线（任何会话不得逾越）

- **版权与参考片禁令**：片中**严禁出现参考片（Johnny Harris、Fireship 等）的任何原片画面或缩略图**；做逐镜测量对比一律用自绘 `shot-wall` / `ruler-measure` 色块尺子加纯文字频道名。
- **隐私打码铁律**：
  - **Claude 界面只用打码截图，严禁录屏**；
  - 所有用户名、`$HOME` 及本地项目路径、邮箱、IP、无关会话标题、旁屏头像，必须用跟随镜头运动的 `.redact` 遮罩（模糊 + 深色叠底）逐段打码并抽帧复核；
  - **用户本人声音参考样本绝不公开、绝不上传公开桶或进仓库**（调用 Modal `qwen3_tts` 时仅走 HTTPS 请求体内存 Base64 直传，容器用完即焚，不写 R2）。
- **实测数字铁律**：片中出现的任何时间、占比、次数、金额、跑分，必须在账本中有真实实测记录，严禁编造。
- **整期预算红线**：
  - **Modal GPU**：`spend_limit` 锁定 `$0`（只用每月免费额度）；`qwen3_tts`、`ltx2`、`music_gen` 同类任务集中成批调用以复用热容器，不设 `min_containers`。
  - **image2（生图/透明道具）**：作为常规视觉手段按整期管理，单期累计预算上限 `$5.00`（`produce-asset.sh` 自动记账，超额停下汇报）。
  - **Pexels / Pixabay 图库**：与共用 key 守卫联动，单期 API 调用 `≤ 60` 次。
- **仓库与外部动作禁令**：
  - 技能代码改在本仓库（`~/Documents/Codex/yice-youtube-video`），成片、音频和生产素材一律放 `$YICE_WORKSPACE/.scratch/youtube/`，绝不进公开仓库；
  - 不改 `claude-code-video-toolkit` 中被 git 跟踪的文件；不碰 SEO 项目（`~/Documents/Codex/yice-seo-site/`）；
  - GitHub 固定且只用 `Yice-AI`（`251089126+Yice-AI@users.noreply.github.com`）；**未经用户明确同意，不发布、不上传、不推送远端、不打标签**。

---

## 参考文档索引

- [references/director-layer.md](references/director-layer.md)：逐句剪辑五步循环、「画面需求 → 工具 → 组件」路由总表、16:9 画幅保护与节奏规则
- [references/models-and-skills.md](references/models-and-skills.md)：Modal GPU / image2 / 图库 / 录屏工具调用策略、整期预算与 D1–D7 示范镜头映射
- [references/voice.md](references/voice.md)：Modal GPU bf16 语义句组配音、写稿顺口规范、重校准五维卡顿检测与单句热修
- [references/review-gates.md](references/review-gates.md)：机器质感硬门 + 中心 100% 抽帧审片清单 + EP01–EP03 踩坑账本
- [references/recording.md](references/recording.md)：`rec-shot` 与 Harness 录屏规范、动态隐私遮罩
- [references/media-acquisition.md](references/media-acquisition.md)：资讯截图、实体证据与开放图库采集规范
- [references/breakdown.md](references/breakdown.md)：参考片逐帧量化拆解方法（只学结构与参数，不引原片画面）
- [kit/docs/tool-demos.md](kit/docs/tool-demos.md)、[kit/docs/recipes.md](kit/docs/recipes.md)、[kit/template/frame.md](kit/template/frame.md)：7 大工具标准示范镜头、组件参数契约与视觉 Token

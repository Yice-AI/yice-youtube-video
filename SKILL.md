---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频的整套制作体系（v3.1）：旁白稿 → Modal GPU 克隆配音与五维卡顿检测 → 五路真实第三方与深色高倍录屏素材装箱（Playwright 1.5x 深色虚拟摄影师、官网演示视频、高分终端回放、打码实操录屏）→ 「一策看片室」原生 HyperFrames 编辑部版式编排（kit/editorial 开放原语、四角取景框、20px 刻度尺、单主视窗跟焦推近与珊瑚红底线字幕）→ 硬红线门禁与中心抽帧审片。8–10 分钟、不露脸、AI 工具实战。Use when 用户要做/剪/规划/返修一期一策 YouTube 视频、采集第三方或录屏素材、审片、开新一期，或提到“下一期视频”“剪出来”“YouTube 教程”“导演层”。
---

# 一策 YouTube 视频制作（v3.1 · 看片室编辑部体系 + 单点实证视窗）

## 核心架构铁律（经双盲盲测 A 获胜与 v3 反例复盘确立）

1. **统一「一策看片室」编辑部美学世界 + 100% 开放原生 HyperFrames**：
   - 使用原生 `hyperframes` 技能族配合开放式版式原语库 **`$KIT/editorial/editorial.py`** 构建标准 HTML/SVG/GSAP 工程：深松墨绿微网格主舞台（`#172322`）+ 暖米纸档案扉页（`#e7ddc5`）+ 顶部常驻刊头（`一策 | 栏目` + 右侧等宽档案号）+ 衬线大字标题 + 四角 L 型取景框（`printframe`）+ 20px 精密刻度尺 + 珊瑚红底线黑底字幕（`#ff745a`）。
   - **严禁两类失败做法**：
     - 严禁回退旧版 `kit/template` 的 `beats.json → build.mjs` 封闭预制盒；
     - 严禁脱离编辑部版式手写简陋无衬线白框贴图脚本（严禁裸 `<div>` 阴影贴膏药）。
2. **多用真实第三方与录屏素材，但严守「单点主视窗 + 严禁图库壁纸与多宫格碎框」**：
   - 观众要的是**在统一的编辑部精密取景框里看清真实第三方网页、GitHub 仓库、命令行与软件实操**，绝不是看杂乱拼贴：
     - **同屏最多 1 个主视窗或 1 组 `A/B` 双视窗**（仅团队总览允许最多 `3` 张等宽角色卡），**彻底禁用 `3×4` / `9–12` 宫格蚂蚁字证据墙**；
     - **严禁拿 Pexels/Pixabay 图库视频铺满全屏当壁纸**（如卡尺、胶片机、单反镜头、蓝光机房糊满底图），全片图库空镜占比 **`≤ 15%`** 且只能装在取景框内作具象辅证；
     - **网页取证默认走深色高倍视口**：`record-web-cam.sh` 默认以 `colorScheme: dark` + `1.5x` Retina 视口录制 `1920×1080` 视频，白底静态图/终端日志必须经 `.tone-paper-tint` 或 `.tone-invert-log` 调和并局部推近至字迹清晰可读（严禁刺眼纯白大图或裁断文字边缘）。
3. **克隆配音全走云端 GPU + `1.000x` 原速零拉伸**：
   - 默认走 Modal A10G bf16 `Qwen3-TTS` 语义句组生成（`$KIT/scripts/voice.sh`），过长章静音切分 ASR（`1.00`）与五维 `voice-check.py` 零告警；成片混音**严禁 `atempo` 变速**，叙事留白（看片对比、3 秒倒计时、片名与章节扉页）一律在句间静音点展开。

---

## 角色与分工（中心把控审美与物证，Codex 负责重执行）

- **中心（总调度）**：定选题与旁白稿、把关分镜视窗路由（确认每句放入 `printframe` 的唯一核心物证）、100% 目视审查成片接触表与关键帧原图、核对实测数字与隐私打码、签发交付。
- **Codex（通过 `codex-commander` 派活）**：
  1. 跑 `$KIT/scripts/voice.sh` 签发零卡顿克隆人声与 `voice-timing.json`；
  2. 按分镜表运行素材脚本（`record-web-cam.sh` 深色 1.5x 网页录屏、`collect-entity.sh`、`produce-asset.sh`）装满 `assets/` 并落盘 `asset-ledger.jsonl`；
  3. 基于 `$KIT/editorial/editorial.py` 与原生 HyperFrames 编排 1080p30 工程，混入随人声自动闪避的合成纪实底乐与动作音效（`-14.0 LUFS ± 0.8 LU`）；
  4. 跑过 `npx hyperframes check`（`0 error`）与 `$KIT/scripts/audit-v3.sh`（实证覆盖率 `≥ 55%`、同屏视窗 `≤ 3`、图库空镜 `≤ 15%`、零 `atempo`、Apple Vision 本地 OCR 零泄露），交回成片与接触表。

---

## 一期标准六步闭环

1. **实测底账与旁白稿**（`script.md`）
   - 口语短句（单句 ≤ 20 字），前 15 秒直接摆真实前后样片对比；所有数字必须有实测底账支撑。
2. **Modal GPU 克隆配音**（`$KIT/scripts/voice.sh`，详见 [references/voice.md](references/voice.md)）
   - 语义句组共享声纹生成，签发 `chapter-*.wav`、`voice-timing.json`、`voice.srt`。
3. **真实第三方与录屏素材装箱**（详见 [references/models-and-skills.md](references/models-and-skills.md)）
   - **第一路（主力，占实证镜头 50%+）· Playwright 深色 `1.5x` 虚拟摄影师网页录屏**：用 `$KIT/scripts/record-web-cam.sh` 打开真实 GitHub 仓库/PR、官方文档、工具主页或 Web 应用，默认深色模式 + `1.5x` 大字号视口平滑移动、点击、珊瑚红荧光划线，导出 `1920×1080@30fps` 视频与 `cursor-track.json`；
   - **第二路 · 真实工作流与软件操作录屏**：本机成片样片、剪辑时间轴、Codex 终端执行、自动化浏览器取景实录（打码脱敏）；
   - **第三路 · 产品官网演示 `<video>` 与官方矢量标志**：用 `$KIT/scripts/collect-entity.sh` 抓取官方 SVG/PNG 标志与产品内嵌演示切片；
   - **第四路 · CLI/日志暗色调和回放**：真实命令输出与构建日志（若原片为白底小字，必须裁取核心区域并用 `.tone-invert-log` 转为暗底可读视窗）；
   - **第五路（严格受限 `≤ 15%`）· 具象实景辅证 / 静态打码截图**：Claude 桌面端只用打码静态图加 `.tone-paper-tint` 暖纸调和；具象图库特写严禁铺满全屏。
4. **素材装箱门禁预检**（`$KIT/scripts/audit-v3.sh --precheck`）
   - 开写 HTML 前核验每 60 秒至少备齐 `≥ 5` 件独立真实素材并入账 `asset-ledger.jsonl`。
5. **「一策看片室」原生 HyperFrames 编排与混音渲染**（详见 [references/director-layer.md](references/director-layer.md)）
   - 沿用 `kit/editorial/editorial.py` 统一母版：左栏衬线论点（`caseleft`）+ 右侧 `16:9` L 型取景框（`printframe`）或 `A/B` 并排双框，视窗内做 `1.0 → 1.15` 克制推近，保留片名齿孔页、暖米纸章节扉页与红章揭晓的呼吸留白，底部常驻珊瑚红底线字幕，母带响度 `-14 LUFS`。
6. **硬红线门禁与中心逐帧审片**（详见 [references/review-gates.md](references/review-gates.md)）
   - 必过 `npx hyperframes check`（`0 error`）+ `$KIT/scripts/audit-v3.sh` + 中心 2s 接触表与关键帧 1080p 原图逐格比对。

---

## 不可逾越的硬规矩

- **零参考片画面**：成片严禁出现 Johnny Harris、Fireship 等任何参考频道的视频帧、人物或缩略图。
- **Claude 界面只截图不录屏**：涉及 Claude 桌面端一律只用打码后的静态截图，严禁录屏。
- **100% 隐私打码**：成片任意一帧不得露出本机用户名、`Users/...`、`$HOME`、邮箱、IP、私人会话标题或头像；克隆参考音频严禁上传 R2 或任何公开桶。
- **实测数字铁律**：片中所有数字必须来自可复核实测底账，严禁编造。
- **外部操作红线**：GitHub 只用 `Yice-AI` 账号；未经用户明确同意，严禁 `git push`、打标签、上传或发布视频；Modal 严守 `spend_limit_usd = 0`；绝不触碰 `/Users/micra/Documents/Codex/yice-seo-site/`。

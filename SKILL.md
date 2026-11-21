---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频的整套制作体系（v3）：旁白稿 → Modal GPU 克隆配音与五维卡顿检测 → 五路真实第三方与跟焦录屏素材装箱（Playwright 虚拟摄影师、官网演示视频、高分终端回放、Pexels/Pixabay 实景与人物抠图）→ 原生 HyperFrames 自由编排（含 Screen Studio 推近、多宫格证据墙、三层景深叠放与内嵌字幕）→ 硬红线门禁与中心抽帧审片。8–10 分钟、不露脸、AI 工具实战。Use when 用户要做/剪/规划/返修一期一策 YouTube 视频、采集第三方或录屏素材、审片、开新一期，或提到“下一期视频”“剪出来”“YouTube 教程”“导演层”。
---

# 一策 YouTube 视频制作（v3 · 原生 HyperFrames + 五路实证引擎）

## 核心架构铁律（经双盲实测确立）

1. **停用封闭模板笼子，100% 走原生 HyperFrames 编排**：
   - 视觉编排、镜头留白、GSAP 动效与内嵌字幕**直接使用原生 `hyperframes` 技能族**（`hyperframes` / `hyperframes-core` / `hyperframes-animation` / `hyperframes-audio` / `hyperframes-cli`）编写标准 HTML/CSS/GSAP 工程；
   - **不再使用旧版 `kit/template` 的 `beats.json → build.mjs` 封闭预制盒渲染器**（旧目录仅保留作历史单测兼容），彻底杜绝把生动台词塞进字小框碎的死板卡片、杜绝为凑指标滥用马赛克/闪白等廉价转场。
2. **无实证不剪辑（五路真实素材装箱前置）**：
   - 观众觉得“高级、细节密、像大博主”，靠的是**高频穿插真实世界物证与丝滑操作录屏**，绝不是靠纯文字排版卡或空洞 AI 生成氛围图硬撑。
   - 开工写 HyperFrames 页面前，必须先跑通**五路素材采集管线**把素材箱装满（每分钟至少 `≥ 5` 件不同真实外部/录屏素材，全片实证与录屏画面占比 `≥ 55%`，连续纯文字排版卡 `≤ 5.0` 秒），由 `$KIT/scripts/audit-v3.sh --precheck` 验箱放行后才准进剪辑渲染。
3. **克隆配音全走云端 GPU + 五维卡顿清零**：
   - 默认走 Modal A10G bf16 `Qwen3-TTS` 语义句组生成（`$KIT/scripts/voice.sh`），过长章静音切分 ASR（`1.00`）与五维 `voice-check.py` 零告警门禁。

---

## 角色与分工（中心把控审美与物证，Codex 负责重执行）

- **中心（总调度）**：定选题与旁白稿、把关素材装箱单（核对每段用哪类真实物证）、100% 目视审查成片接触表与关键帧原图、核对实测数字与隐私打码、签发交付。
- **Codex（通过 `codex-commander` 派活）**：
  1. 跑 `$KIT/scripts/voice.sh` 签发零卡顿克隆人声与字级时间轴 `voice-timing.json`；
  2. 按剧本逐段运行五路素材脚本（`record-web-cam.sh`、`collect-entity.sh`、`find-media.sh`、`people-add.sh`、`produce-asset.sh`）装满 `assets/` 并落盘 `asset-ledger.jsonl`；
  3. 用原生 HyperFrames 编排 1080p30 工程（标配 Screen Studio 跟焦推近、多宫格证据墙、Vox 三层实拍叠放、先分后合留白对比与常驻底部内嵌白字字幕），混入侧链闪避 BGM 与动作音效（`-14 LUFS`）；
  4. 跑过 `npx hyperframes check`（`0 error`）与 `$KIT/scripts/audit-v3.sh`（实证密度、响度、16:9 画幅、Apple Vision 本地 OCR 隐私零泄露），交回成片与接触表。

---

## 一期标准六步闭环

1. **实测底账与旁白稿**（`script.md`）
   - 口语短句（单句 ≤ 20 字），前 15 秒直接摆反常识结果或真实前后对比；所有数字必须有实测底账出处支撑，严禁编造。
2. **Modal GPU 克隆配音**（`$KIT/scripts/voice.sh`，详见 [references/voice.md](references/voice.md)）
   - 语义句组（3–5 句）共享克隆声纹连续生成，长章静音中点切分转写，ASR 准确率与五维韵律告警清零后产出 `chapter-*.wav`、`voice-timing.json`、`voice.srt`。
3. **五路真实素材装箱**（详见 [references/models-and-skills.md](references/models-and-skills.md)）
   - **第一路（主力，占第三方素材 40%+）· Playwright 虚拟摄影师网页/Web 工具录屏**：用 `$KIT/scripts/record-web-cam.sh` 在隔离干净视口打开真实 GitHub 仓库/PR、官方文档、定价表、论文、社区讨论或 Web 工具，自动滚动、输入、点击、荧光笔划出关键句，导出 1080p30 `.mp4` 与精确 `cursor-track.json` 供镜头自动跟焦推近；
   - **第二路 · 产品官网 `<video>` 演示、SVG 标志与多宫格证据墙**：用 `$KIT/scripts/collect-entity.sh` 与 `npx hyperframes media-use resolve --type logo` 抓取官网首屏、官方矢量 Logo、内嵌演示 `<video>`（静音裁 `≤ 5s` 标明来源合理引用）及 GitHub 动图；同类多案例（9–15 件）拼成滚动证据墙再推近单点；
   - **第三路 · CLI/代码真跑高分回放**：真实执行命令记录原始输出与耗时，用高分大字号终端/代码视窗按真实时间戳回放并局部推近关键行，配键盘与提示音效；
   - **第四路 · Pexels/Pixabay 具象实景 B-Roll + Wikimedia 人物抠图**：用 `$KIT/scripts/find-media.sh`（只搜具象物理特写词如 `35mm film strip`、`server rack macro`，禁搜摆拍白领空镜）与 `$KIT/scripts/people-add.sh`（Apple Vision 本机人物抠图加纸感白边）做 Vox 三层景深叠放；
   - **第五路 · 登录态网页 / 原生桌面软件 / 极少量概念插画兜底**：登录态页面走本机 `ego-browser` + 自动隐私模糊；原生独占桌面软件派单常驻 `Harness`；仅现实世界不存在的抽象隐喻才允许用 `image2` / `ltx2`（整片占比 `≤ 10%`，严禁放无信息量的空洞 AI 图）。
4. **素材装箱门禁预检**（`$KIT/scripts/audit-v3.sh --precheck`）
   - 开写 HTML 前核验素材箱：每 60 秒成片时长至少备齐 `5` 件独立真实素材文件，且全部登记在 `asset-ledger.jsonl`。
5. **原生 HyperFrames 电影级编排与混音渲染**（详见 [references/director-layer.md](references/director-layer.md)）
   - 遵循头部博主四大镜头语法（Screen Studio 光标推近 + 手绘红圈、多宫格证据墙、三层实拍 B-Roll 叠放、先单看后并排的留白对比），冷暖底色按章节交替（深墨绿/暗炭调查底 ↔ 暖米纸档案底），90% 采用干净硬切（`cut`）与主体延续运镜（`carry`），底部常驻清晰白字内嵌字幕，配齐自动闪避 BGM 与物理音效，母带归一 `-14 LUFS ± 1.0 LU`。
6. **硬红线门禁与中心逐帧审片**（详见 [references/review-gates.md](references/review-gates.md)）
   - 必过 `npx hyperframes check`（`0 error`）+ `$KIT/scripts/audit-v3.sh`（实证覆盖率 `≥ 55%`、连续纯字卡 `≤ 5.0s`、`-14 LUFS`、Apple Vision 本地 OCR 零隐私泄露）+ 中心 2s 接触表逐帧验真。

---

## 不可逾越的硬规矩

- **零参考片画面**：成片严禁出现 Johnny Harris、Fireship 等任何参考频道的视频帧、人物或缩略图。
- **Claude 界面只截图不录屏**：涉及 Claude 桌面端一律只用打码后的静态截图，严禁录屏。
- **100% 隐私打码**：成片任意一帧不得露出本机用户名、`Users/...`、`$HOME`、邮箱、IP、私人会话标题或头像；克隆参考音频严禁上传 R2 或任何公开桶。
- **实测数字铁律**：片中所有数字必须来自可复核实测底账，严禁编造。
- **外部操作红线**：GitHub 只用 `Yice-AI` 账号；未经用户明确同意，严禁 `git push`、打标签、上传或发布视频；Modal 严守 `spend_limit_usd = 0`；绝不触碰 `/Users/micra/Documents/Codex/yice-seo-site/`。

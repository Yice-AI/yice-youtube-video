# 模型、五路素材采集与外部技能调用规范（v3）

## 1. 五路真实素材工具链（按优先级选用）

### 第一路：Playwright 虚拟摄影师（网页 / GitHub / 文档 / Web 工具交互录屏）
- **脚本**：`$KIT/scripts/record-web-cam.sh`（底层 `record-web-cam.mjs`，复用本机已装 Chrome + `playwright-core`，匿名干净上下文，零个人登录态泄露）
- **能力**：打开任意公开 URL 或本地 Web Demo（`1920×1080`），按动作脚本执行平滑滚动（`scroll`）、可见光标移动与点击波纹（`click`）、输入框打字（`type`）、关键文本定位与荧光笔高亮（`highlight`），导出：
  - `video.mp4`（30fps H.264 `yuv420p`）
  - `still.png`（关键帧高清静图）
  - `cursor-track.json`（记录每次动作精确秒数 `t`、坐标 `x,y` 与目标元素 `rect`，供 HyperFrames 自动生成 Screen Studio 推近关键帧）
  - 自动追加来源 URL、抓取时间与 SHA-256 至项目 `asset-ledger.jsonl`。
- **兼容快速入口**：纯网页滚动与原文高亮也可继续调用 `$KIT/scripts/capture-web.mjs`。

### 第二路：官方产品实体采集（官网 `<video>` 演示 + 矢量 Logo + GitHub 动图）
- **脚本**：`$KIT/scripts/collect-entity.sh --name '<名称>' --site <官网URL> [--github owner/repo] --out <目录>`
- **能力**：自动抓取官网首屏 1080p 截图、平滑滚动视频、页面内嵌自动播放的高清产品演示 `<video>`（成片引用须 **静音、`≤ 5s`、右上/左上角标明官方来源域名**，仅限评论教学语境），以及通过 `npx hyperframes media-use resolve --type logo` 获取官方原始 SVG/高清标志（绝不手画变形山寨图标）。

### 第三路：CLI / 代码真实运行高分回放
- 在沙盒/工作目录真实执行命令，将实测输出、文件体积与真实耗时保存为结构化 JSON，在 HyperFrames 中用大字号（`≥ 26px` 等宽字体）高对比终端/代码视窗按真实节奏逐行上屏并推近高亮关键结果行，严禁直接录满屏芝麻小字且带私人路径的原始终端。

### 第四路：开放授权实景 B-Roll 与百科人物原生抠图
- **实景视频与照片**：`$KIT/scripts/find-media.sh`（自动聚合本机 `~/.config/yice-video/stock.env` 中的 **Pexels + Pixabay** 双商业可用图库，以及 **Wikimedia Commons + NASA + Internet Archive Prelinger** 公有领域影像）。
  - **检索铁律**：必须搜**具象物理特写英文词**（如 `'35mm film strip macro'`、`'cinema lens focus'`、`'server rack lights'`、`'caliper ruler'`），**严禁搜空泛词**（如 `'business'`、`'office team'`、`'artificial intelligence'` 导致出现廉价摆拍假人或丑陋 3D 脑图）。
  - **预算守卫**：Pexels + Pixabay 单期合计 **`≤ 60` 次** API 请求（月上限 `1,500` 次，24h 自动缓存，可随时用 `$KIT/scripts/media-usage.sh` 核对）。
- **人物抠图拼贴**：`$KIT/scripts/people-add.sh` 从 Wikimedia Commons 拉取 CC/PD 授权人物照，调用本机 Apple Vision（`vision-cutout.swift`）完成发丝级抠图与纸感白边，自动把作者与 CC 署名写入 `asset-ledger.jsonl`。

### 第五路：登录态页面 / 原生桌面软件 / AI 生成兜底
- **需登录网页**：调用本机 `ego-browser` 截取或录制后，必须先经本机 Apple Vision OCR 扫描并在像素层高斯模糊所有账号名、邮箱、路径后再拷入工程。
- **原生独占 Mac 软件**：投递任务单至 `.scratch/youtube/dsh-inbox/` 由常驻 `Harness` 录制（**硬禁令：Claude 桌面端只准使用打码静态截图，绝不录屏**）。
- **AI 生成画面（严格兜底，整片占比 `≤ 10%`）**：只有当现实世界确实不存在对应画面时，才通过 `$KIT/scripts/produce-asset.sh` 调用 `image2`（整期预算 **`≤ $5.00`**）或 Modal `ltx2`（严守 `spend_limit_usd = 0`），且严禁单放一张无信息量的空洞 AI 概念图。

---

## 2. 配音与渲染核心底座

- **Modal GPU 克隆配音**：`$KIT/scripts/voice.sh`
  - 端点由 `$YICE_TOOLKIT/.env` 的 `MODAL_QWEN3_TTS_ENDPOINT_URL` 提供；克隆参考音频直走 HTTPS Base64 内存传输，**绝不上传 R2 或任何外部存储桶**；Modal 账户锁定 `spend_limit_usd = 0`（只用 Starter 免费额度）。
- **原生 HyperFrames 编排与渲染**：
  - 优先复用本机已安装的 `hyperframes`（`0.9.52+`）、`gsap` 与 `playwright-core`；渲染输出 `1920×1080`、`30fps`、H.264 `yuv420p` MP4。

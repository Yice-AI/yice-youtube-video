# 模型、五路素材采集与双擎调用规范（v8.2）

## 1. 五路真实素材工具链（按优先级选用）

### 第一路：Playwright 虚拟摄影师（网页 / GitHub / 文档 / Web 工具后台高清录屏）
- **交互录屏脚本**：`$KIT/scripts/record-web-cam.sh`（底层 `record-web-cam.mjs`，复用本机 Chrome + `playwright-core`，无头后台静默运行，零个人登录态泄露），默认 `--theme dark --scale 1.5` 输出原生 `1920×1080 30fps`，同时生成 `still.png` 与 `cursor-track.json`。
- **净屏滚动与原文取证入口**：`$KIT/scripts/capture-web.mjs`（默认 `30fps`、`scale=1.25`、`-crf 17`），开拍前自动预滚动解码懒加载图片并隐藏 Cookie 横幅、客服悬浮窗与订阅弹窗，定位指定引文像素坐标写入 `capture.json`（直通 `evidence_spotlight` 自动推近高亮）。

### 第二路：官方产品实体深扒（原生 `<video>` 演示流 + 矢量 Logo + 发布动态）
- **脚本**：`$KIT/scripts/collect-entity.sh --name '<名称>' --site <官网URL> [--github owner/repo] --out <目录>`
- **能力**：直接识别并下载官网或 GitHub README 内嵌原生 `<video>`（含 `user-attachments` MP4/WebM）归一化为静音 `1920×1080 30fps` 视频（杜绝网页逐帧截图导致的跳帧加速），优先提取官方 `.svg` 矢量标志并冻结入账。

### 第三路：CLI / 代码真实运行高分回放与本地实操录制
- CLI / 代码输出优先采集真实运行结果 JSON，通过 `studio_ui`（支持 `data.focus_lines` 聚光高亮核心行，不硬截断长行）或 `hyperframes_block` 高对比渲染；需要连续窗口交互时使用 `$KIT/scripts/rec-demo.sh`。

### 第四路：开放授权高清横屏 B-Roll 与主体完整性抠像
- **实景视频与照片**：`$KIT/scripts/find-media.sh`（聚合 **Pexels + Pixabay + Wikimedia Commons + Openverse**），视频强制筛选 **`width >= 1920` 且横屏（`16:9`）** 的高清源，直接剔除竖屏与低清素材；检索须用具象物理特写英文词，单期 API 请求 `≤ 60` 次。
- **长片挑镜清洗**：`$KIT/scripts/scout-video-scenes.sh` 自动剔除纯色字卡、跨镜硬切与底部含旧烧录字幕的片段。
- **人物与实物抠图**：`$KIT/scripts/people-add.sh` / `$KIT/scripts/cutout.py` 调用本机 Apple Vision 抠图，内置主体完整性门禁（自动拒绝触碰多条画幅边界或连带大片桌面底板的残次品）。

### 第五路：登录态页面 / 原生桌面软件 / AI 生成封面与兜底
- **需登录/验证码页面**：无头采集遇到登录墙或真人验证会自动停手回报；可由用户在已登录 `ego-browser` 截取脱敏图，或用 `onetake` 的 `UIK` + `look.py from-shot` 1:1 重建高清可推近动态界面。
- **原生独占 Mac 软件**：投递任务单至 `.scratch/youtube/dsh-inbox/` 由常驻 `Harness` 录制（Claude 桌面端仅用脱敏静态截图）。
- **封面直出与极少量概念图**：YouTube 封面统一走 `$KIT/scripts/thumbnail.sh`（绑定 `tts-venv`，零额外劣化约束原生调用 `image2.py --role thumbnail --guard light --thumb-guard r_plus`，出 3 张候选 + `640/320/168px` 预览板 + 假时长角标警示 + `<2MB` JPG 入账）。正片内 AI 生图仅作无现实画面时的兜底（占比 `≤ 10%`）。

---

## 2. 配音、双擎视觉与母带底座

- **原速克隆配音**：`$KIT/scripts/voice.sh`，正片默认 `--backend kaggle --speed 1.0`（异步轮询 + 自然呼吸保留 + 自动导出短句无句尾标点 `captions.json`）；单句离线补录可用 `--backend local --allow-slow-local`；严禁未授权调用 `--backend modal`。
- **Onetake + HyperFrames 混合双擎舞台**：
  - 主舞台 `$KIT/editorial/editorial.py` 支持五套主题、`perspective_3d` / `studio_window` 悬浮实录窗、环境呼吸光晕与胶片微噪点、现代立体 `triptych_cards` 及四类同步跨镜转场 `transition_in`；
  - 高光钩子与片尾结论调用 `$KIT/scripts/render-onetake-clip.sh`（`stage_mode: "onetake_clip"`，`OM` 39 种物理运镜/弹簧/流体原语 + 6 套电影 `looks` / 截图吸色 + `probe.py` 连续变形门禁 + `180°` 真实快门动态模糊）；
  - 多阶段机制与动态图表调用 `stage_mode: "hyperframes_block"`（直通 `hyperframes-registry` 近 400 组件与 `hyperframes-animation` 22 套蓝图，可用 `$KIT/scripts/visual-palette.sh` 一键检索）。
- **声学母带**：`EpisodeAudioMixer` 采用 `2.5s` 等功率余弦无缝循环底乐、物理包络动作轻音效与动态人声闪避，统一校准至 `-14.5 ± 0.8 LUFS`、`≤ -1.0 dBTP`。

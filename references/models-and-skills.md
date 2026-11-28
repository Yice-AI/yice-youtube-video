# 模型分工、六路素材采集与双擎调用规范（v15.0）

## 0. 主脑导演 × 执行机房协作铁律

- **主脑导演（Gemini Neon / Claude 等顶级模型）**：负责选题包装（写 `packaging.json` 并让包装、剧本两关 `precheck-episode.sh` 通过）、按作品展示和讲解段落选择影院暗场、瑞士暖白画布、去 AI 腔口播定稿、审看 `showcase-candidates.jpg` 挑高光原片、撰写 `image2` 生图提示词、编写 `episode-manifest.json`（调用内建 21 套 `spatial_spec` / `onetake_spec` 模具，讲工具用法优先 `prompt_iter_workbench`，**禁止手写一次性简陋 HTML 页面**），并在渲染后**亲眼逐张审看关键帧与早中晚动作图墙**。
- **执行机房（Codex / 后台命令行）**：仅执行无审美自由度的确定性任务——运行采集、`precheck-episode.sh` 三关检查、配音、抠图、温控压片（`workers=2, nice=10`）与 `audit-v3.sh --v10` 门禁检查，不得擅自修改视觉样式或用白底文字截图凑数。

---

## 1. 六路真实素材与造画工具链（外采优先，按新题三层漏斗选用）

素材备齐后先跑 `$KIT/scripts/precheck-episode.sh --project . --stage assets`：多工具教程至少 8 组独立画面，`asset-ledger.jsonl` 至少 2 个外部网站且占 25% 以上，换名重复的素材会被列出。

### 第一路：一手高光动态原片猎手（学术 `*.github.io` / 官方发布页 / X 实机视频）
- **脚本**：`$KIT/scripts/harvest-showcase-media.sh --urls <URL列表> [--x-query "<关键词>"] --output <目录> --rank-highlights`
- **能力**：无损提取公开论文项目页（`*.github.io`）、官方发布博客与公开演示贴中的原生高清 `<video>` / MP4 / WebM（自动拦截第三方二创视频站域名）；非 `16:9` 竖片/方片自动合成 `blur_dark` 同源高斯模糊暗压背景；内置视觉冲击力评分器自动剔除黑屏与白底文字死页，切出 `4.5s` 高光切片并生成 `showcase-candidates.jpg`，直接喂入双擎动态视频贴图。

### 第二路：Playwright 深色虚拟摄影师（Web 工具交互实操 / 文档净屏取证）
- **交互录屏**：`$KIT/scripts/record-web-cam.sh`（默认 `--theme dark --scale 1.5`、`--hide-selectors` 隐藏干扰栏），输出原生 `1920×1080 30fps`、`still.png` 与 `cursor-track.json`。
- **原文取证**：`$KIT/scripts/capture-web.mjs` 自动隐藏弹窗横幅并定位引文像素框写入 `capture.json`（直通 `evidence_spotlight`）。

### 第三路：品牌实体与矢量标志提取
- **脚本**：`$KIT/scripts/collect-entity.sh --name '<名称>' --site <官网URL> [--github owner/repo] --out <目录>`，优先提取官方 `.svg` 矢量标志冻结入账（直通 `logo_bento_stage` 模块舱与角标）。

### 第四路：`image2` + Vision 代码造画资产管线（零现成视频题材必杀技）
- **白底贴纸 + 剪纸视差**：由主脑导演调用 `$YICE_TOOLKIT/local/tools/image2.py` 生成干净白底独立角色/道具图，经 `$KIT/scripts/cutout.sh`（Apple Vision）抠出透明 PNG 后喂入 `cutout_parallax_stage`（自动加 4px 奶油剪纸白边、三层视差卷轴与粒子烟尘）。
- **16:9 艺术大图 + 2.5D 纪录片拆卡**：调用 `image2.py --aspect 16:9` 生成高细节岩彩/手稿/剖面大图，喂入 `documentary_ken_burns`（阻尼慢推摇 + 金粉微尘 + `split_at` 一图拆三张局部特写竖卡）。

### 第五路：CLI / 本地实操录制与开放授权高清图库
- CLI 输出与真实运行实操使用 `studio_ui`（`data.focus_lines`）或 `$KIT/scripts/rec-demo.sh`；开放横屏实拍与人物抠像使用 `$KIT/scripts/find-media.sh`、`scout-video-scenes.sh`、`people-add.sh`。

### 第六路：封面直出与登录墙兜底
- 封面统一走 `$KIT/scripts/thumbnail.sh --archetype diverse`（调用 `image2.py` 按 `treasure_fan`、`versus_shock`、`power_desk` 三套构图各出 1 张候选 + 联系表 + `<2MB` JPG 入账）；遇到登录墙/验证码如实回报，改用脱敏截图或 `onetake` `UIK` 动态界面重建。

---

## 2. 配音、双擎 `.mp4` 真视频贴图与母带底座

- **原速克隆配音**：`$KIT/scripts/voice.sh`（默认 `--backend kaggle --speed 1.0` 或本机离线 MLX，`--tts-model` 切换云端开源语音底座，`natural_v7` 异常分段自动换 seed 重抽最多 3 轮，保留自然呼吸与短句 `captions.json`；严禁未授权调用 Modal）。
- **HyperFrames + Onetake 双擎声明式模具**：
  - `hyperframes_block`（14 套内建 `spatial_spec`）：原生嵌入可寻帧 `<video>`，涵盖 `prompt_iter_workbench`、`triptych_curtain`、`kinetic_title_bridge`、`perspective_video_fan`、`logo_bento_stage`、`cutout_parallax_stage`、`documentary_ken_burns`、`step_tree_focus`、`progressive_sim_cards`、`formula_pill_chain`、`carousel_3d_select`、`layer_explode_3d`、`roadmap_thread_camera`、`literal_action_stage`；多卡接单卡全屏用 `exit_zoom_index` / `exit_zoom` 推近，横屏素材零裁边；
  - `onetake_clip`（7 套内建 `onetake_spec`）：视频源自动预解 24fps 确定性帧序列配合 `180°` 真实快门模糊，涵盖 `split_wipe_compare`（`center_scan` / `diagonal_wipe` / `quad_race`）、`handdrawn_sketch_stage`（8fps 铅笔水彩微抖 / Riso 半调）、`duplicate_laser_sweep`、`bitmap_lock_glitch`、`energy_roadmap_dive`、`live_control_sync`、`capsule_archive_seal`。
- **声学母带与终审**：`EpisodeAudioMixer` 校准至 `-14.5 ± 0.8 LUFS`、`≤ -1.0 dBTP`；浅底舞台自动切 `caption-on-light` 烟熏深色胶囊字幕；终审运行 `$KIT/scripts/audit-v3.sh --v10`。

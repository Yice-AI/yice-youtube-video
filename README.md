# 一策 YouTube 视频制作 v12.0

把中文深度科技与商业视频的导演方法、素材采集、原速配音、**Onetake + HyperFrames 双擎真动态视频贴图与代码造画**、封面直出与机器审片整合在一套可复现工具链中：**`SKILL.md` 管导演路由与审美铁律，`kit/` 管采集、配音、双擎渲染、混音和成片门禁**。公开仓库只分发方法、代码与离线测试，不放私人录音、成片或凭据。

先按[五拍叙事与三态画面](references/01-高留存叙事与三态画面铁律.md)排口播、镜头形态与跨镜承接，再按[一手高光素材与代码造画母法](references/02-一手高光素材与代码造画母法.md)为双擎接入真实 `.mp4` 视频贴图与代码造画配方。

## 核心能力一览（v12.0）

- **双擎 `.mp4 / .webm` 真动态视频贴图（告别卡片死截图）**。`kit/spatial/block.py` 原生嵌入可寻帧 `<video>` 并在离线采样前自动 seek 等待 `seeked`；`kit/onetake/scene.py` 构建期用 `ffmpeg` 预解 24fps 确定性帧序列并全量预解码，在 180° 快门模糊下实现丝滑无闪黑的动态视频对比与擦除。
- **第 1/3 类画面 9 大高阶配方 + 双调性母版**。HyperFrames 新增 `perspective_video_fan`（3D 视频扇形墙）、`logo_bento_stage`（Bento 模块拼装）、`cutout_parallax_stage`（剪纸白边三层视差）、`documentary_ken_burns`（2.5D 纪录片推摇 + 一图拆三卡）、`step_tree_focus`（SVG 生长树焦点跳转）、`progressive_sim_cards`（1% vs 100% 渐进装置卡）、`formula_pill_chain`（因果胶囊链）；Onetake 新增 `split_wipe_compare`（中线扫描 / 45° 斜切擦除 / 双栏竞速）与 `handdrawn_sketch_stage`（离线 `sketch_brush.js` 8fps 铅笔水彩 + Riso 半调）。支持 `cyber_glass` 暗黑玻璃与 `editorial_paper` / `scroll_paper` 暖米白画布双母版贯穿全片。
- **工具教程三段实拍与高清净屏采集**。0–5 秒展示复杂成品或改前改后对比，跟拍输入命令与 Agent 执行，1080p 满屏多点跟焦验证交互。满屏占实录 ≥ 70%，斜框 ≤ 全片 15%。五路采集脚本覆盖高倍率网页录屏、官网原生 `<video>`/SVG 提取、横屏图库、长片去重复与 Vision 抠图防撞字。
- **原速克隆配音、精排字幕与广播级母带**。Kaggle 免费 GPU 原速配音保留自然呼吸，`captions.json` 配合深浅自适应烟熏胶囊字幕（浅底舞台自动切换），BGM 等功率余弦循环与 `-14.5 ± 0.8 LUFS` 校准。
- **`image2` 封面直出与 `v10/v12` 机器审片**。`thumbnail.sh` 直出 3 张候选与联系表，`audit-v3.sh --v10` 执行双调性一致性、合规短题/文物角标放行、标题防碰撞、双擎动效与声学门禁。

## 在新电脑安装与体检

```bash
./install.sh
env -i HOME="$HOME" PATH="$PATH" ./install.sh --check
```

安装器自动将仓库根目录软链接至本机技能目录并写入 `~/.config/yice-video/env`（路径优先级：**环境变量 → 本机 env 配置 → 默认值**）。`--check` 输出 JSON 体检（含 `onetake_ready` 状态），不修改已有链接。

## 依赖

| 依赖 | 用途 |
|---|---|
| macOS（Apple 芯片）、Node/npm、Python 3、`uv`、FFmpeg/ffprobe、Chrome | 本地脚本、离线 HyperFrames CLI、Playwright 采集/渲染与音视频检查。 |
| `claude-code-video-toolkit` | 位于 `$YICE_TOOLKIT`；提供 `tools/captions.py`、`local/vendor/gsap.min.js`、`local/tools/local_voiceover.py`、`local/tools/image2.py`、`local/tools/rec/`。 |
| `local/tts-venv`、`local/asr-venv` | 前者供本机 MLX 配音与 `thumbnail.sh`（`image2.py`）运行；后者提供 `mlx-whisper`、`librosa`、`soundfile`、`scipy`、`Pillow`。 |
| 本机 `onetake` 与 `hyperframes-*` 技能库 | 分别提供 `OM`/`UIK`/`looks`/快门模糊渲染器与 22 套动态蓝图、原子动效规则及组件目录。 |

## 开新一期标准流程

1. **初始化与母版选型**：运行 `kit/scripts/new-episode.sh ep04` 创建工程，用 `kit/scripts/visual-palette.sh` 选择色板与蓝图，确定整片使用 `cyber_glass` 或 `editorial_paper` 母版。
2. **配音与分镜草稿**：运行 `kit/scripts/voice.sh script.md --backend kaggle --speed 1.0 --output voice`，再用 `kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 生成对齐首字时间的 30fps 骨架。
3. **高清采集、造画与验帧**：用 `collect-entity.sh`、`record-web-cam.sh`、`find-media.sh`、`image2` + `cutout.sh` 备齐真视频、截图与透明剪纸素材，填好 `episode-manifest.json`，跑 `scout-video-scenes.sh --verify-manifest` 做首中尾帧与贴图防撞字核验。
4. **装片、终审与封面**：运行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out` 导出成片与字幕，执行 `kit/scripts/audit-v3.sh --v10` 终审，最后用 `kit/scripts/thumbnail.sh` 生成并选定封面。

完整字段契约与路由细则见 [SKILL.md](SKILL.md) 与 [references/10-双擎高阶视觉路由.md](references/10-双擎高阶视觉路由.md)。

## 许可

自行编写的代码和文档使用 [MIT](LICENSE)。思源黑体、思源宋体、Source Code Pro 使用 SIL OFL 1.1；Registry 组件来自 [heygen-com/hyperframes（Apache-2.0）](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)；`onetake` 桥接调用遵循其本地安装许可。详见 [NOTICE](NOTICE) 与 [PRIVACY-SCAN.md](PRIVACY-SCAN.md)。

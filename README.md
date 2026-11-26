# 一策 YouTube 视频制作 v11.0

把中文深度科技与商业视频的导演方法、素材采集、原速配音、**Onetake + HyperFrames 双擎动态视觉**、封面直出与机器审片整合在一套可复现工具链中：**`SKILL.md` 管导演路由与审美铁律，`kit/` 管采集、配音、双擎渲染、混音和成片门禁**。公开仓库只分发方法、代码与离线测试，不放私人录音、成片或凭据。

先按[五拍叙事与三态画面](references/01-高留存叙事与三态画面铁律.md)排口播、镜头形态与跨镜承接。用空间积木生成子合成，用真实录屏证明输入与输出。

## 核心能力一览（v11.0）

- **工具教程三段实拍**。0–5 秒展示官方复杂成品，再拍输入命令或提示词、Agent 执行，最后用 1080p 满屏多点跟焦验证成品交互。目标每镜 4–6 秒，平均不超过 6.5 秒；满屏占实录至少 70%，斜框占全片至多 15%，带框镜头不能相邻。
- **按素材选舞台**。暖纸冲印用 `y2_vox`，数据尺和图表用 `t5_data_ruler` / `t3_finance_chart`，真实终端用 `studio_ui`，并排比较用 `triptych_cards`。Onetake 与 HyperFrames 用于连续运镜、矢量变形与状态推演，禁止在双擎内拼贴两张及以上静态截图。
- **五路后台高清净屏采集与防废片清洗**：`30fps` 高倍率网页净屏实拍（预滚解码懒加载图 + 自动隐藏弹窗 + 带回原文高亮坐标）、GitHub/官网原生 `<video>` 演示流直下与 `.svg` 矢量标志提取、`≥1920px` 横屏图库硬筛、长片自动剔除硬切与旧字幕、Apple Vision 抠图主体完整性门禁与贴图首中尾 OCR 防撞字核验。
- **原速克隆配音、精排字幕与广播级母带**：默认走授权 Kaggle 免费 GPU（`--backend kaggle --speed 1.0`）保留自然呼吸，自动生成短句去句尾标点 `captions.json` 与深浅自适应烟熏黑曜石胶囊字幕；BGM `2.5s` 等功率余弦无缝循环 + 物理包络轻音效，母带校准 `-14.5 ± 0.8 LUFS`、`≤ -1.0 dBTP`。
- **`image2` 封面零劣化直出闭环**：`kit/scripts/thumbnail.sh` 绑定 `tts-venv` 原生直调 `image2`，一次生成 3 张候选 + `640/320/168px` 三尺寸预览联系表 + 右下角假时长水印 OCR 警示 + `<2MB` 高清 JPG 选定入账。

## 在新电脑安装与体检

```bash
./install.sh
env -i HOME="$HOME" PATH="$PATH" ./install.sh --check
# 需要自定义本机路径时：
./install.sh --workspace "$HOME/Documents/Codex/个人IP" \
  --toolkit "$HOME/Documents/Codex/个人IP/claude-code-video-toolkit"
```

安装器自动将仓库根目录软链接至 `~/.claude/skills/`、`~/.codex/skills/` 及（若存在）`~/.gemini/config/skills/`，并写入 `~/.config/yice-video/env`（路径优先级：**环境变量 → 本机 env 配置 → 默认值**）。`--check` 输出 JSON 体检（含 `onetake_ready` 状态），不修改已有链接。

## 依赖

| 依赖 | 用途 |
|---|---|
| macOS（Apple 芯片）、Node/npm、Python 3、`uv`、FFmpeg/ffprobe、Chrome | 本地脚本、离线 HyperFrames CLI、Playwright 采集/渲染与音视频检查。 |
| `claude-code-video-toolkit` | 位于 `$YICE_TOOLKIT`；提供 `tools/captions.py`、`local/vendor/gsap.min.js`、`local/tools/local_voiceover.py`、`local/tools/image2.py`、`local/tools/rec/`。 |
| `local/tts-venv`、`local/asr-venv` | 前者供本机 MLX 配音与 `thumbnail.sh`（`image2.py`）运行；后者提供 `mlx-whisper`、`librosa`、`soundfile`、`scipy`、`Pillow`。 |
| 本机 `onetake` 与 `hyperframes-*` 技能库 | 分别提供 `OM`/`UIK`/`looks`/快门模糊渲染器与 22 套动态蓝图、原子动效规则及组件目录。 |

## 开新一期标准流程

1. **初始化与视觉选型**：运行 `kit/scripts/new-episode.sh ep04` 创建剧集工程，用 `kit/scripts/visual-palette.sh` 按本期题材挑选契合的色板（或 `--from-shot` 从产品截图吸色）与动态蓝图。
2. **配音与分镜草稿**：运行 `kit/scripts/voice.sh script.md --backend kaggle --speed 1.0 --output voice`，再用 `kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 生成对齐首字时间的 30fps 骨架。
3. **高清采集与验帧**：用 `collect-entity.sh`、`record-web-cam.sh`、`find-media.sh`、`scout-video-scenes.sh` 采集实证素材，填好 `episode-manifest.json`（高光段填 `onetake_spec` 的配方与内容，空间机制填 `spatial_spec`，装配时自动编译，实录优先用 `fullbleed` + `focus_push`），跑 `scout-video-scenes.sh --verify-manifest` 做首中尾帧与贴图防撞字核验。
4. **装片、终审与封面**：运行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out` 以两个低优先级进程导出成片与字幕，可用 `--draft` 试片，执行 `kit/scripts/audit-v3.sh --v10` 检查可见标题与主体碰撞、展开层板亮度、双擎时长与配色、节奏、画幅、空壳、双擎动效、跨镜重复、教程过程，以及既有像素与声学要求，最后用 `kit/scripts/thumbnail.sh` 生成并选定封面。

完整字段契约与路由细则见 [SKILL.md](SKILL.md) 与 [references/10-双擎高阶视觉路由.md](references/10-双擎高阶视觉路由.md)。

## 许可

自行编写的代码和文档使用 [MIT](LICENSE)。思源黑体、思源宋体、Source Code Pro 使用 SIL OFL 1.1；Registry 组件来自 [heygen-com/hyperframes（Apache-2.0）](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)；`onetake` 桥接调用遵循其本地安装许可。详见 [NOTICE](NOTICE) 与 [PRIVACY-SCAN.md](PRIVACY-SCAN.md)。

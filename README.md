# 一策 YouTube 视频制作 v15.0

把中文深度科技与商业视频的前置三关、导演方法、素材采集、原速配音、**Onetake + HyperFrames 双擎真动态视频贴图与代码造画**、封面直出与机器审片整合在一套可复现工具链中：**`SKILL.md` 管导演路由与审美铁律，`kit/` 管采集、配音、双擎渲染、混音和成片门禁**。公开仓库只分发方法、代码与离线测试，不放私人录音、成片或凭据。

先按[五拍叙事与三态画面](references/01-高留存叙事与三态画面铁律.md)排口播、镜头形态与跨镜承接，再按[一手高光素材与代码造画母法](references/02-一手高光素材与代码造画母法.md)为双擎接入真实 `.mp4` 视频贴图与代码造画配方。

## 核心能力一览（v15.0）

- **前置三关硬拦截。** `kit/scripts/precheck-episode.sh --project <剧集目录> --stage <packaging|script|assets|all>` 在写分镜、配音和装片前分别拦下温吞说明文标题、标题与正文承诺脱节、口播里的制作端内部细节（批量截图等几秒、临时目录、字段名）、骂丑却不放丑的痛点台词、缺少可照抄提示词的干讲教程，以及换名重复、只有本地自造页面的素材池。
- **提示词迭代台教实操。** 第 14 套空间配方 `prompt_iter_workbench` 把大白话提示词拆成胶囊逐拍落位，`16:9` 零裁边展示「默认直出 → 加词精修后」，再推近接下一镜全屏交互，取代黑底终端敲命令。
- **多卡点中推近衔接。** `progressive_sim_cards` 在所有画布下居中弹出再依次推开，横屏素材按原画幅零裁边展示；`exit_zoom_index` / `exit_zoom_at` 点中目标卡推近撑满全屏接下一镜，`perspective_video_fan` 用 `exit_zoom` 推近焦点卡。
- **双擎 `.mp4 / .webm` 真动态视频贴图。** `kit/spatial/block.py` 嵌入可寻帧 `<video>`，采样前 seek 并等待 `seeked`；`kit/onetake/scene.py` 构建期预解 24fps 确定性帧序列，在 180° 快门模糊下丝滑擦除与竞速。
- **影院暗场与瑞士亮场。** 作品与对比用暗场，方法与选型切 `swiss_paper`；`triptych_curtain` 开场、`kinetic_title_bridge` 划线转场，配 `perspective_video_fan`、`logo_bento_stage`、`cutout_parallax_stage`、`documentary_ken_burns`、`step_tree_focus`、`formula_pill_chain` 等配方与 Onetake `split_wipe_compare`、`handdrawn_sketch_stage`。
- **外采优先的三层素材漏斗。** 先用 `harvest-showcase-media.sh` 抓官网、论文项目页和公开演示原片，`collect-entity.sh` 取标志与 README 演示，`capture-web.mjs` 录官网；再录深色实操；最后用 `image2` 剪纸视差与 2.5D 壁画补缺。
- **原速配音与广播级母带。** Kaggle 免费 GPU 原速配音，`--tts-model` 可换开源语音底座；`natural_v7` 拦截句内 165ms 以上无标点停顿与词内能量塌陷并自动换 seed 重抽；深浅自适应字幕，`-14.5 ± 0.8 LUFS` 校准。
- **三套高点击封面母版与成片审计。** `thumbnail.sh --archetype diverse` 一次出 `treasure_fan`、`versus_shock`、`power_desk` 三种构图候选；`audit-v3.sh --v10` 新增画幅裁切、视频帧级去重与外采多样性门禁。

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

1. **定题、包装与第一关**：运行 `kit/scripts/new-episode.sh ep04` 创建工程，写 `packaging.json`（标题、钩子、观众承诺、关键词），`thumbnail.sh --archetype diverse` 出 3 张候选，然后 `kit/scripts/precheck-episode.sh --project . --stage packaging`。
2. **写稿与第二关**：剧本第 3 列写清每幕画面，痛点幕注明反例原件，实操章写出可照抄的提示词与前后变化；`--stage script` 通过后运行 `kit/scripts/voice.sh script.md --backend kaggle --speed 1.0 --output voice`，再用 `kit/scripts/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.json` 生成 30fps 骨架。
3. **外采、造画与第三关**：按三层漏斗运行 `harvest-showcase-media.sh`、`collect-entity.sh`、`capture-web.mjs` / `record-web-cam.sh`、`find-media.sh` 或 `image2` + `cutout.sh`，全部登记 `asset-ledger.jsonl`；`--stage assets` 通过后由主脑导演填 `episode-manifest.json`，跑 `scout-video-scenes.sh --verify-manifest` 核对首中尾帧。
4. **装片、终审与封面**：运行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out`，执行 `kit/scripts/audit-v3.sh --v10` 并由主脑导演逐张目检图墙，最后 `thumbnail.sh --select` 定稿封面。

完整字段契约与路由细则见 [SKILL.md](SKILL.md) 与 [references/10-双擎高阶视觉路由.md](references/10-双擎高阶视觉路由.md)。

## 许可

自行编写的代码和文档使用 [MIT](LICENSE)。思源黑体、思源宋体、Source Code Pro 使用 SIL OFL 1.1；Registry 组件来自 [heygen-com/hyperframes（Apache-2.0）](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)；`onetake` 桥接调用遵循其本地安装许可。详见 [NOTICE](NOTICE) 与 [PRIVACY-SCAN.md](PRIVACY-SCAN.md)。

## 换电脑迁移配音

在本人电脑上运行 `./install.sh --configure-voice 精修参考音.wav 对应原文.txt`。端点配置和声纹都保存在 `~/.config/yice-youtube-video/`。换电脑时只需私下拷贝这个目录，保持文件权限 0600，再运行安装检查。未配置私人参考音时使用工具包品牌配置。

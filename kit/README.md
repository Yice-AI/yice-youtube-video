# 一策视频工具包

已把 EP01 的配方、配音和本地渲染流程封装为新一期骨架。保留既有视觉体系，HyperFrames 固定 **0.9.52**。本包负责执行；制作方法论由独立的 yice-youtube-video skill 维护。

先运行仓库根目录的 install.sh。脚本按“环境变量 → ~/.config/yice-video/env → 默认 $HOME/Documents/Codex/个人IP”读取机器路径。然后执行：

```bash
KIT="$HOME/.claude/skills/yice-youtube-video/kit"
. "$HOME/.config/yice-video/env"
EP_ID=ep02
PROJECT="$YICE_TOOLKIT/local/episodes/$EP_ID"
NOTES="$YICE_WORKSPACE/.scratch/youtube/episodes/$EP_ID"
"$KIT/scripts/new-episode.sh" "$EP_ID"
# 填写 NOTES 的 script.md、anchors.json、asset-needs.md、beat-table.md
"$KIT/scripts/voice.sh" "$NOTES/script.md" --output "$PROJECT/voice"
# 准备素材；按实际配音调整 PROJECT 的 episode.json、beats.json
cd "$PROJECT"
npm run build
DO_NOT_TRACK=1 npm run check
"$KIT/scripts/render.sh" "$PROJECT"
"$KIT/scripts/review.sh" "$PROJECT/renders/render-时间戳.mp4" --at 1,5,12
```

| 环节 | 使用方式与产物 |
|---|---|
| 新一期 | 默认项目放 toolkit/local/episodes，可用 `new-episode.sh ep02 --dir /项目目录` 指定。已有剧本目录可继续用；只补缺少的文件，保留已有剧本、幕表和配置。目录里的 episode.id 不符则停止。 |
| 配音 | 每章一次连续 MLX 8bit 生成，默认每幕前插 0.2 秒静音；〔核〕不朗读。voice/ 输出章 WAV、firstCharTime/anchors 时间轴、manifest、voice.srt；raw/ 和 analysis/ 保留原音与对齐依据。重新生成用新的空输出目录。 |
| 素材 | 手工素材放 assets/local；道具和库存图放 assets/props、assets/stock。assets/media 由 build 重建。录屏复用 toolkit/local/tools/rec/rec.sh，例如 `rec.sh 60 /绝对路径/demo.mov`，同时保存独立鼠标轨迹。 |
| 道具 | `props.sh props.json --case-dir /本案统一道具目录 --budget 2`；计划格式见 template/props.example.json，每件 candidates=N。图片在 images/，深炭检查图在 checks/；把 images 路径填进 episode.json 的 @assets/。所有批次必须共用同一个 case-dir，成功候选不重复付费。 |
| 预算 | 每次请求默认预留 $0.20；累计已用+预留超过全案预算即停。费用不明或中断请求会保留预留并停止，失败不自动重试。usage 费用为网关单价估算，非最终账单；预留不是服务端硬限额。凭证仍从原文件读取，不复制进 kit。 |
| 渲染与审片 | render 前台等待退出码，日志与 MP4 在 renders/；review 输出每 3 秒接触表、每 40 秒拼图、blackdetect、时长/音轨 JSON 和 --at 抽帧。 |
| 混音 | episode.audio 指向音频配置，或 `node build.mjs --audio audio-config.json`；A/B/C 音乐、语音避让、音效锚点和 −14 LUFS / −1 dBTP 母带一并构建。见 [音频配置](docs/audio.md)。 |

`npm run check` 除 HyperFrames 检查外，还按 30fps 实际渲染视频转场检查空画面；可用 `--rendered /完整成片.mp4` 复用成片。单段验证加 `--video-scenes S5-6 --rendered /片段.mp4 --rendered-start 139`，报告会写出实际检查的窗口。原生视频构建时自动归零异常的源时间戳并预加载，源素材不变。

依赖本机 Node/npm、FFmpeg，及 toolkit 既有 tts-venv、asr-venv、离线模型和 yice 声音配置。路径可用 YICE_WORKSPACE、YICE_TOOLKIT 覆盖；解释器可用 YICE_TTS_PYTHON、YICE_ASR_PYTHON、YICE_IMAGE_PYTHON、YICE_REVIEW_PYTHON 覆盖。录屏工具需已有 macOS 屏幕录制权限。组件、字体及许可随 template 带入。

接口详见 [配方与视觉词汇](docs/recipes.md) 和 [幕表字段](docs/beats-schema.md)。例稿是四幕结构示例，新题材须填写自己的剧本、锚点、素材和 end。

**已有验证：** 参考片 70 幕、78 个 composition 文件 **diff=0**；20 秒样片 check **0 error**、有音轨、黑帧 0；短稿实跑 3 句 9.48 秒，原 PCM 保留，原 ASR 的 96 字时间重放无差异。道具脚本已实测累计预算停止与重跑防重复。视频、声音及原始核验素材不随公开仓库分发；本次迁移验证见 [PRIVACY-SCAN.md](../PRIVACY-SCAN.md)。

离线复验：`"$YICE_TOOLKIT/local/tts-venv/bin/python" -m unittest discover -s "$KIT/tests" -v`。安装与依赖见[仓库首页](../README.md)。


参考片粗拆：`"$KIT/scripts/breakdown.sh" <视频> <输出目录> [起点秒=60] [长度秒=180]`，输出切点统计、每 2 秒帧墙、开头 30 秒逐秒帧。方法见仓库 `references/breakdown.md`。

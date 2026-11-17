# 一策 YouTube 视频制作

把中文教程视频的制作方法与执行工具放在一起：**skill 管内容与导演方法，kit 管配方、配音、渲染和审片**。适合不露脸的 AI 工具实操教程，素材和渲染留在本机。

画面使用纸张、实物与真实录屏，配合重点词、台账、标注和镜头推近。既有叙事配方与首批 17 项视觉词汇可组合成不同节奏；字体和组件随模板提供。第一条参考片已有 8 章、70 幕，公开仓库只分发方法、代码与空骨架，不放成片或私人素材。

## 在新电脑安装

先把本仓库克隆到自己选定的目录，再进入目录运行：

```bash
./install.sh
# 需要自定义本机路径时：
./install.sh --workspace "$HOME/Documents/Codex/个人IP" \
  --toolkit "$HOME/Documents/Codex/个人IP/claude-code-video-toolkit"
```

安装器会把 Claude 与 Codex 的 yice-youtube-video skill 目录链接到仓库根目录，写入 `~/.config/yice-video/env`。已有目标先移到 `~/.config/yice-video/backups/` 下（不留在 skills 目录里，免得被当成第二个 skill），并打印备份位置；已正确链接时重复运行不会重复备份。依赖只检查、列出缺项，不自动安装。每台电脑独立配置路径；仓库更新后，软链接直接读取新版方法与代码。

默认工作区为 `$HOME/Documents/Codex/个人IP`，默认 toolkit 为工作区下的 claude-code-video-toolkit。执行脚本的路径优先级为：**环境变量 → 本机 env 配置 → 默认值**。

## 依赖

| 依赖 | 用途 |
|---|---|
| macOS、Node/npm、Python 3、FFmpeg/ffprobe | 本地命令、HyperFrames 0.9.52、视频检查；录屏与 MLX 配音针对 Apple 芯片 Mac。 |
| claude-code-video-toolkit | 单独准备在 `$YICE_TOOLKIT`；需要 tools/captions.py，以及 local/tools/local_voiceover.py、image2.py、rec/。这些本机附加工具不由本仓库安装。 |
| local/tts-venv、local/asr-venv | 前者提供 MLX 配音、Pillow、requests、python-dotenv，后者提供 mlx-whisper；两者都须能读取 toolkit 的工具依赖。 |
| 离线模型 | toolkit/local/models 下 Qwen3-TTS-12Hz-1.7B-Base-8bit；本机缓存的 mlx-community/whisper-large-v3-turbo。 |
| 本机声音配置与录屏权限 | yice 声音配置、本人授权的参考录音；macOS 屏幕录制权限由使用者自己授权。参考录音不进入仓库。 |
| 生图服务配置 | 只在调用 props 时需要。凭证通过外部 image2.py 的本机配置读取；此仓库没有账号或凭证。 |

## 开新一期

从 [kit/README.md](kit/README.md) 的命令开始，再按 [SKILL.md](SKILL.md) 准备剧本、素材表和节拍表。[配方说明](kit/docs/recipes.md)与[幕表格式](kit/docs/beats-schema.md)描述实际支持的字段。

| 目录 | 内容 |
|---|---|
| SKILL.md、references/ | 制作方法、导演规则、录屏与审片要求。 |
| kit/template/ | 叙事配方、首批视觉词汇、6 个转场、3 个质感层、样例及字体。 |
| kit/scripts/、kit/tests/、kit/docs/ | 新一期、配音、渲染、审片、透明道具脚本与离线检查。 |
| `$YICE_TOOLKIT/local/episodes/<ep>` | 本机项目、配音、素材和渲染结果。 |
| `$YICE_WORKSPACE/.scratch/youtube/episodes/<ep>` | 本机剧本、表格与核验资料。 |

多电脑协作只同步本仓库的方法和代码。模型、录音、录屏、成片、凭证及机器路径各自留在本机；`.gitignore` 已排除常见生成物。发布前扫描与安装验证记录见 [PRIVACY-SCAN.md](PRIVACY-SCAN.md)。

## 许可

自行编写的代码和文档使用 [MIT](LICENSE)。思源黑体、思源宋体、Source Code Pro 使用 SIL OFL 1.1，原始许可随字体附带；registry 组件来自 [heygen-com/hyperframes，Apache-2.0](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)。详见 [NOTICE](NOTICE)。本仓库不包含第三方图库素材。

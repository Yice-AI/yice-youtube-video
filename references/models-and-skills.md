# 模型、云 GPU 与各 skill 怎么搭配

## 为什么 EP01 几乎没用云 GPU

画面的主力是**真实录屏**和**真实物件**：教程的可信度来自真东西。AI 生成的视频片段容易显假，又贴不住具体操作，所以 EP01 没有用。

EP01 的配音在本机 MLX 上跑，透明道具用 image2，所以 Modal 花费是 $0。

这不代表模型没用。下面几处**该用就用**，用得好画面会更饱满：

| 需求 | 首选 | 何时用云 GPU（Modal，toolkit 工具） | 预算与注意 |
|---|---|---|---|
| 配音 | 本机 MLX Qwen3-TTS 8bit（kit `voice.sh`） | 本机内存不够或要批量重做时，用 `qwen3_tts` | 每章一次连续生成，不要逐句生成 |
| **背景音乐** | toolkit `music_gen.py`（ACE-Step，Modal），也可以用 `pick_music.py` 从免费曲库挑 | ✔ 首选云 GPU | 音量压在人声下 −18 到 −22 dB；人声出现时自动压低（ducking）；章节换场时音乐跟着变化。**EP01 没有背景音乐，这是下一期最该补的一层** |
| 音效（纸、章、点击、快进） | 免费音效库（逐件登记许可） | 不需要 | 只在物件落下、盖章、划线、快进时出现，音量要小 |
| 透明道具 | image2（`props.sh`，原生透明） | `flux2.py` 免费，但没有原生透明，需要抠图 | 每期累计 $3 停 |
| 第三方空镜 | Pexels / Unsplash / Pixabay | 找不到合适的，才用 `ltx2.py` 生成 3–5 秒空镜 | 生成的片段只能当氛围镜头，不能冒充真实操作；先出一条小样，每条记账 |
| 缩略图 | image2 `--role thumbnail --guard light --candidates 3` | — | 人工挑掉画了假时长、出现占位框的候选 |
| 字幕 | voice.sh 输出的 SRT | — | 上传 YouTube 时附上 |

Modal 的规则：Starter 套餐每月 $30 免费额度，spend limit 设为 $0（超出就停，不会扣钱）。重新部署前先看 toolkit 的文档；同类素材要批量生成时，复用已经热起来的容器。

## 各 skill / 仓库的分工

```
yice-youtube-video（本 skill）        决定拍什么、怎么排、怎么验收
 ├─ kit/（本仓库）                     配方、视觉规范、配音/渲染/审片/道具脚本
 ├─ HyperFrames skills（渲染层）       把 HTML 画面渲染成 mp4
 │    hyperframes          入口：工作循环、渲染契约
 │    hyperframes-core     写或改配方前必读（data-* 时序、子合成、确定性渲染）
 │    hyperframes-animation / -keyframes   入场、推镜、转场
 │    hyperframes-registry 缺效果时先搜现成组件（约 450 个），装进 template 后回写 kit
 │    hyperframes-cli      check / render / snapshot 排错
 │    hyperframes-audio    给背景音乐和音效做压低、淡入淡出、混音
 │    （hyperframes-creative 不用：视觉方向以 frame.md 为准）
 ├─ claude-code-video-toolkit（工具仓库）
 │    local/：tts-venv、image2.py、rec/ 录屏、episodes/ 项目目录（我们加的附加工具）
 │    tools/：music_gen、pick_music、ltx2、flux2、contact_sheet（Modal 工具，按上表使用）
 │    它的 Remotion 模板不再使用
 └─ codex-commander                    给 Codex 派执行活、监听状态
```

## 什么时候调用哪个

| 场景 | 调用 |
|---|---|
| 开新一期 | 本 skill → `kit/scripts/new-episode.sh` |
| 写 beats、改配方参数 | 本 skill 的 director-layer，加 kit `docs/recipes.md` |
| 新写一个配方 | `hyperframes-core`，再加 `hyperframes-animation`；写完放进 `kit/template/recipes/_src`，运行 wrap.py |
| 想要某种效果（光扫、撕纸、计数） | 先查 `hyperframes-registry`，找不到再自己写 |
| 渲染报错 | `hyperframes-cli` |
| 混背景音乐和音效 | toolkit `music_gen.py` 或 `pick_music.py` 准备素材，`hyperframes-audio` 混音 |
| 批量执行（配音、生图、素材、脚本维护） | `codex-commander` 派给 Codex |

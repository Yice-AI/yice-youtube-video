# 模型、云 GPU、生图工具与各 skill 协同策略（v2）

## 1. 核心转变：生成与采集工具全部进入“剪辑常规武器库”

早期为了省成本，曾把生成视频写成“极少用”、把 `image2` 限制为“只当氛围镜头且满 $3 即停”，导致执行代理在剪 8 分钟长片时不敢造新画面，只能拿两三段旧录屏来回切，剪出来像简陋 PPT。

**v2 确立的新原则**：
- **围绕成片高级感按句选工具，缺画面当场生产**（统一通过 `kit/scripts/produce-asset.sh` 调用并自动记账）。
- **真假边界清晰**：真实软件操作、真实命令输出、公开新闻与实测数据，100% 用真实录屏、网页抓取和底账数据驱动组件呈现；抽象概念、比喻隐喻、实物道具、以及图库搜不到的物理动态场景，大胆使用 `image2`、`blueprint-diagram` 和 Modal GPU `ltx2` 造出影棚级画面。
- **按整期设总预算、同批热容器集中跑**：既保证每分钟画面饱满不重样，又严格守住 Modal `$0` 实付与 API 额度红线。

---

## 2. 工具矩阵、使用场景与整期预算红线

| 画面/音频需求 | 标准调用入口 | 底层模型 / 服务 | 什么时候当场用 | 整期预算与操作纪律 | 标准示范 |
|---|---|---|---|---|---|
| **克隆本人声音配音** | `kit/scripts/voice.sh`（默认 `--backend modal`） | Modal GPU A10G · `Qwen3-TTS-12Hz-1.7B-Base`（bf16） | 每期配音、补录、单句热修默认首选（彻底替代本机 MLX 8bit）；Modal 故障时切 Kaggle 或 `--backend local` | Modal 免费额度内约 `$0.15–$0.35`/期；按 3–5 句语义句组单次 batch 请求共享 `voice_clone_prompt`；**参考音频仅走 HTTPS Base64 内存直传，禁传 R2 或公开桶** | — |
| **软件与终端真实操作** | `kit/scripts/rec-shot.sh` / Harness 收件箱 `.scratch/youtube/dsh-inbox/` | 本机 OCR 确定性录制 / DeepSeek Harness | 讲“具体怎么点、怎么跑、AI 怎么干活” | `$0`；**Claude 界面禁录屏（只用打码截图）**；所有隐私路径/账号必须绑 `.redact` | `D1-recording` |
| **公开网页 / GitHub / 论文 / 榜单证据** | `kit/scripts/produce-asset.sh --kind web-capture`（调 `capture-web.mjs` / `collect-entity.sh`） | 本机 Playwright 高清视口截图 + 平滑滚动录屏 | 讲官网、开源仓库、新闻报道、官方跑分 | `$0`；记录来源 URL 与采集日期进 `asset-ledger.jsonl` | `D2-web-evidence` |
| **纪实空镜 / 真实人物与手部动作** | `kit/scripts/produce-asset.sh --kind stock-footage`（调 `find-media.sh`） | Pexels / Pixabay / Wikimedia 1080p | 讲现实工作场景、行业动态、快切蒙太奇 | `~/.config/yice-video/stock.env` 共用 key，**单期 API 调用 ≤ 60 次**（脚本硬拦截），逐件登记许可 | `D3-stock-footage` |
| **概念隐喻大图 / 透明实物道具 / 缩略图备选** | `kit/scripts/produce-asset.sh --kind metaphor-image` 或 `--kind prop-cutout`（底层 `image2.py` / `props.sh`） | `image2`（16:9 `r_plus` 轻护栏多候选；透明底 PNG 道具） | 讲抽象概念、正反比喻（如“案板两样菜”“金鱼记忆”）、桌面实物拼贴 | **常规使用，整期合并预算上限 `$5.00`**（每镜 2–3 候选挑最佳，防重缓存不重复扣费；超 `$5` 停下汇报） | `D4-image2-metaphor` |
| **技术架构 / 流程步骤 / 因果拆解动画** | 直接在 `beats.json` 选用 `blueprint-diagram` 组件 | `kit` 内置精密工程蓝图 SVG + GSAP 引擎 | 讲系统分工、多步流水线、模块关系、机制拆解 | `$0`；执行者只传结构化节点与边 JSON，**严禁手写简陋贴画** | `D5-svg-blueprint` |
| **图库找不到的写实物理动态场景** | `kit/scripts/produce-asset.sh --kind motion-video`（底层 Modal `tools/ltx2.py`） | Modal GPU A100 · `LTX-2`（3–5 秒 16:9 写实动态视频） | 画面必须真正在动（翻动厚重档案、聚光灯扫过工作台、特写物理隐喻动作）且图库无贴切实拍时常规调用 | Modal `spend_limit=$0` 免费额度内管理（每期建议 **3–8 段**，约 `$0.60–$1.80` 额度）；**同章需求集中成批连续提交以复用热容器**，不设 `min_containers`；不可冒充真实软件录屏 | `D6-modal-ltx2` |
| **实测数据尺 / 对比柱图 / 代码差异** | `beats.json` 选用 `shot-wall` / `ruler-measure` / `bar-compare` / `code-diff` | `kit` 数据驱动可视化组件 | 讲逐镜测量、耗时体积对比、前后指标提升 | `$0`；只绑实测底账 JSON，禁编数字、禁引参考片画面 | `D7-data-chart` |
| **原创背景音乐与分轨验收** | Modal `tools/music_gen.py`（ACE-Step）+ 本机 Demucs 人声机测，或 `pick_music.py` | Modal GPU + 本机音频母带链（`audio.mjs`） | 每期 A/B/C 情绪段落配乐 | Modal 免费额度约 `$0.10`/期；入选前必过 Demucs 无人声机测（P90 ≤ −20dB）；人声段压低 24dB，成片 −14 LUFS | — |

---

## 3. 各仓库与 Skill 的边界

```text
yice-youtube-video（~/Documents/Codex/yice-youtube-video，公开仓库 Yice-AI）
 ├─ SKILL.md + references/            导演方法论、逐句选工具总表、配音与质感审片标准（中心把控）
 └─ kit/                              高阶动效版式组件库、produce-asset 即时制片 CLI、GPU 配音与卡顿检测、D1–D7 示范镜头、kit check 门禁

HyperFrames skills（本机确定性渲染底座，锁定 @0.9.52）
 ├─ hyperframes / hyperframes-core    HTML→MP4 确定性时间轴与子合成契约（维护 kit 组件时遵守）
 ├─ hyperframes-animation / -audio    组件内部缓动编排与多轨混音压低
 └─ hyperframes-cli                   check / snapshot / render 排错（严禁使用云渲染、publish、share）

claude-code-video-toolkit（$YICE_TOOLKIT，只调工具与环境，不改 git 跟踪文件）
 ├─ tools/qwen3_tts.py, ltx2.py, music_gen.py, flux2.py   Modal 云 GPU 端点调用器
 └─ local/                            image2.py、asr-venv、tts-venv、yice 声音私有配置（git 排除）

codex-commander                       中心向 Codex 派发重执行任务、令牌管理与 watch.py 监听
```

---

## 4. 七大工具标准示范镜头（`kit/docs/tool-demos.md`）

为了让执行代理不再“凭想象从零画画面”，`kit` 内置 7 个做好的影棚级示范镜头（`D1`–`D7`），每个示范都包含**生成该素材的精确命令 + 完整 `beats.json` 片段 + 100% 审片级渲染成片**：
- 执行代理剪辑任何一幕时，先定位它属于 `D1`–`D7` 哪一类，直接照搬示范镜头的组件结构、光影层级与动效节奏，只替换当句内容与锚点。

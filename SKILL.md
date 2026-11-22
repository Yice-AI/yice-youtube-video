---
name: yice-youtube-video
description: 一策 YouTube 中文教程与深度科技视频的整套制作体系（v4.0）：旁白稿 → Modal GPU 克隆配音与五维卡顿检测 → 逐镜语义《镜头表》 → 满屏连续多点跟焦实录（Playwright 1.5x 深色虚拟摄影师、软件真操作微距）× 花叔 8 大解说动画语法引擎（kit/explainer：y2_vox 调查桌胶带剪报与 12fps 荧光笔、t3_finance_chart 经济学人动态柱线图、t2_keynote_ui 展开、y3_whiteboard 推导链、y5_kinetic_type 动态重音）→ 通透无黑盒字幕与 Music Drop 母带混音 → audit-v3.py --v4 真像素防死镜/防黑帧/dHash防重硬门禁。8–10 分钟、不露脸、AI 工具实战。Use when 用户要做/剪/规划/返修一期一策 YouTube 视频、采集第三方或录屏素材、审片、开新一期，或提到“下一期视频”“剪出来”“YouTube 教程”“导演层”。
---

# 一策 YouTube 视频制作（v4.0 · 满屏实操跟焦 × 解说动画引擎 × 真像素硬门禁）

## 核心架构铁律（对标子木 #6 / 松小鼠 #1 / Vox #7 与花叔开源体系确立）

1. **拒绝“左字右小框 PPT”与“常驻页眉”，全片采用「满屏真操作 + 8 大解说动画语法」双引擎**：
   - **正片去掉常驻顶部页眉栏 `mast()`**（固定页眉与页码是“一眼 PPT”头号病根，仅 `≤ 1.8s` 章节过渡页可带刊头）；字幕默认使用无黑底框通透电影白字（`clean_cinema`），底部 `y ≥ 900` 设为字幕安全禁区，严禁叠放其他标题文字。
   - **实操与网页取证走 `1920×1080` 满屏连续多点跟焦（`$KIT/editorial/editorial.py` 的 `add_fullbleed_rig`）**：运镜遵循「有来有回」（`hold` 停稳、`push` 缓推、`glide` 横移、`pull` 拉远、`punch` 仅给重音反转，**严禁连续三镜单向 zoom-in**）。
   - **概念、档案、数据对比与清单全面调用 `$KIT/scripts/render-explainer-clip.sh`（集成 MIT 开源 `alchaincyf/huashu-art-motion` 8 大解说语法，统一注入看片室深松绿 `#172322` / 暖米纸 `#e7ddc5` + 珊瑚红 `#ff745a` 色板）**：
     - 有截图、原话、报告、被毙提案论证 → **`y2_vox`（Vox 调查桌）**：胶带冲印相纸 + 左下撕边黑标 + `12fps` 毛边荧光笔与手绘红圈（`image` + `highlight`，不提前盖纯黑 `title` 条）；
     - 有多组实测数字对比 → **`t3_finance_chart`（经济学人动态图表）**：先出坐标系，柱/线从 0 生长并同步计数（`series` 传 `[{"label":..., "value":...}]` 字典数组）；
     - 讲角色分工与步骤展开 → **`t2_keynote_ui`**；
     - 讲闭环流程与规则推导 → **`y3_whiteboard`**（交替使用 `draw` + `point`，防图标叠字）；
     - 讲章节重音与金句总结 → **`y5_kinetic_type`**。
2. **100% 逐镜语义锁死，严禁轮询塞片与超时黑帧**：
   - 开写合成脚本前必须先落盘逐镜《`镜头表.md`》，每一句口播只能绑定真正在讲这件事的专属画面，**严禁 `MEDIA_POOLS` / `% N` 轮询无关视频充数**；
   - HyperFrames 离散 seek 渲染下 `<video>` 的物理文件时长必须严格 `≥ 镜头时长 + 0.2s`，杜绝尾段黑帧；单素材文件全片出现次数硬上限 **`≤ 4` 次**。
3. **Modal GPU 克隆原速人声（`1.000x`）+ `Music Drop` 戏剧留白混音**：
   - 配音走 `$KIT/scripts/voice.sh --backend modal --speed 1.0`（过静音切分 ASR `≥ 0.99` 与五维 `voice-check.py` 零告警，**严禁 `atempo` 变速**）；
   - 母带混音采用真实多段配乐跨幕交叉淡化（口播闪避 `-24 dB`、留白回升 `-13 dB`），并在全片至少 `4` 处核心反转句前设置 **真 `Music Drop`（纯伴奏轨余弦瞬抽衰减 `≥ 22 dB`）** + 推近/画圈/拍纸/盖章/读秒动作音效，综合响度 `-14 ± 1 LUFS`。

---

## 一期标准六步闭环

1. **实测底账与口语短句稿**（`script.md`）
   - 单句 `≤ 20` 字，前 15 秒直接摆真实对比；片尾占比等统计句在全片 `shot-timeline.json` 实测出真值后再合成，确保“报告 == 图表 == 口播”三处数字分毫不差。
2. **Modal GPU 克隆配音与校准**（`$KIT/scripts/voice.sh`，详见 [references/voice.md](references/voice.md)）
3. **逐镜语义《镜头表》与双路素材生产**（详见 [references/director-layer.md](references/director-layer.md)、[references/models-and-skills.md](references/models-and-skills.md)）
   - 路 A（真实取证）：`$KIT/scripts/record-web-cam.sh`（默认 `--theme dark --scale 1.5` 输出 `1920×1080@30fps`）、本机无隐私实操录屏与局部微距裁切特写；
   - 路 B（参数化解说动画）：编写 spec JSON 调 `$KIT/scripts/render-explainer-clip.sh --spec <x.json> --out <x.mp4> --audit`（逐 `0.25s` 自动拦截出界与叠字）。
4. **分幕 HyperFrames 编排、原速母带混音与无损拼接**
   - 长片按 4 幕独立子工程（`act1..act4`）过 `hyperframes check`（`0 error`）并渲染后 `ffmpeg -f concat` 拼接，导出同步 `.srt`。
5. **`audit-v3.py --v4` 真像素与真声学硬门禁**（详见 [references/review-gates.md](references/review-gates.md)）
   - 直接读取成片 MP4 检验：**`pixel_gate`（2fps 连续帧差防死镜）**、**`black_frame_gate`（防超时黑帧）**、**`dhash_gate`（跨镜感知哈希防改名重复）**、**`max_file_reuse ≤ 4`**、**`immersive_ratio ≥ 65%` & `split_box_ratio ≤ 22%`**、**`bed-only.wav` 真声学衰减**、**`subzone_gate`（`y ≥ 900` 防撞字幕）** 与 **Apple Vision OCR 零泄露**。
6. **中心 5s 全片接触表 + 外部头部标杆同屏对比终审**
   - 必看全片接触表与对标帧并排图；未获用户本人明确满意结案前，Codex 会话一律发 `wait_user` 保持 `await_next.py` 常驻在线，**严禁提前 `stop`**。

---

## 不可逾越的硬规矩

- **零参考片画面**：成片严禁出现 Johnny Harris、Fireship、子木等任何参考频道的视频帧、人物或缩略图。
- **Claude 界面只截图不录屏**：涉及 Claude 桌面端一律只用打码后的静态截图（如贴入 `y2_vox` 相纸），严禁任何动态录屏。
- **100% 隐私打码**：成片任意一帧不得露出本机用户名、`Users/...`、`$HOME`、邮箱、IP、私人会话标题或头像；克隆参考音频严禁上传公开存储。
- **实测数字铁律**：片中所有数字必须来自可复核实测底账，严禁编造或逻辑自相矛盾。
- **外部操作红线**：GitHub 固定使用 `Yice-AI <251089126+Yice-AI@users.noreply.github.com>`；未经用户明确同意，严禁 `git push`、打标签、上传或发布；Modal 严守 `spend_limit_usd = 0`；绝不触碰 `/Users/micra/Documents/Codex/yice-seo-site/`。

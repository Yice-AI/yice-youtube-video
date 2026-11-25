# v8.2 成片审计与签发

素材入箱时保留来源、许可或授权记录、文件哈希和实测底账。装配先运行各幕 HyperFrames check（及 Onetake 连续性探针），之后对实际导出成片运行统一审计：

```bash
kit/scripts/audit-v3.sh --v7 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4
```

## 八项硬门禁与前置防线

| 门禁 | 验收 |
|---|---|
| `v7_timeline_gate` | 镜头连续，实际切点距首字至多 0.22 秒，真视频底图占 45%–72%。同一 SHA-256 的视频含多栏卡在内可常规使用两次，重叠不得超过 0.25 秒。另可用 `callback_of` 登记一次回扣。 |
| `semantic_binding_gate` | 台词主题、实际画面主体和素材标签相符。点名工具的实录须指向对应实体。 |
| `spotlight_restraint_gate` | 局部框登记像素核验，最大 680×340。跨镜相同坐标会被拦截，数量上限为 3 或镜头数的 8% 向下取整，取较大者。参考拆解台须有署名与主张。 |
| `opener_bgm_and_sfx_gate` | 0 秒起铺底乐，前 15 秒底乐高于 −42 dBFS，前 45 秒至少三处动作音效。 |
| `first_half_motion_density_gate` | 前后半各有至少 35% 动效镜头，无叠层的连续全屏实拍至多 16 秒。 |
| `breath_integrity_gate` | 原人声不得有超过 40 毫秒且低于 −80 dBFS 的句间断崖，处理记录不得出现数字静音插入。 |
| `explainer_density_gate` | 解说画面至少 26 字或具备图表、图像、结构卡等内容。白板绘制必须有有效图标。 |
| `onetake_craft_gate` | 所有 `onetake_clip` 镜头须具备 `.onetake-probe.json` 与 `.render.json` 探针及渲染记录，全程无 `__seek` 报错、开启真实快门动态模糊（`shutter > 0`），且禁止无承接的纯幻灯片硬换（除非单镜显式声明 `allow_staccato`）。 |

前置素材与贴图防线：`cutout.py` 默认拦截触碰多条画幅边界或含大面积背景底板的残次抠图；`scout-video-scenes.sh --verify-manifest` 在装片前对贴图可见期首、中、尾三点跑底层文字 OCR，防止贴纸中途撞上视频原字。

交付为 1920×1080、30fps H.264 和可读字幕。母带目标 −14.5 ± 0.8 LUFS，真峰值 ≤ −1.0 dBTP。成片时长以清单末镜为准，片尾可按剧本设计 2–4 秒留白。历史项目沿用成片时长等于 episode.end 的约定。逐幕复核黑帧、像素运动和字幕安全区。v7 跨镜 dHash 相似画面至多出现两次。

## OCR 与人工签发

抽帧 OCR 的频道豁免仅适用于 `--v7` 且已声明对应频道的 `reference_breakdown` 或 `triptych_cards` 时间窗。私人路径、用户名、邮箱、IP、会话与凭据始终按全帧规则检查，项目特有词加入 `--forbid`。引用片段原音须静音，来源署名清晰，画面紧贴解说。

逐处核对实测数字与百分比。每处从原始观察和实测底账查回样本范围、分子、分母和舍入方式，再核对旁白、屏幕读数与字幕一致。抽听各章多音字、句尾和拼缝，并在关键 1080p 帧上确认字与主体完整（含跨镜转场中间帧与快门动态模糊瞬态帧）。只在机器门禁和实际观看、听辨结果均通过后签发。

`spotlight_box`、`highlighter_sweep` 与 `hand_circle` 共用局部核验上限。看原图首、中、尾帧，确认标注跟随焦点。亮底实录和浅色舞台核对烟熏深色胶囊字幕对比度，跨深浅切点的字幕分别取帧。解说片段默认预留顶部 56 px 和底部 172 px。

# 首批视觉词汇的来源与适配

来源为 HyperFrames registry 0.9.58；上游 [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) 使用 [Apache-2.0](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)。仓库既有 NOTICE 保留，以下逐项登记适配关系。配方采用原件的运动结构，重新接入 Yice 的舞台、纸卡、字体、素材槽与同一条 GSAP 时间线，不保留原件的整页示例、品牌、字体或配色。

| Yice 配方 | registry 原件 | 保留与适配 |
|---|---|---|
| news-card | 阶段A news-card-prototype | 纸卡/胶带、荧光刷出，局部框1.6倍移到右侧 |
| social-post | reddit-post | 帖子层级、计数；移除平台品牌，默认隐去个人信息 |
| chat-bubble | chat-message | 气泡逐条弹出、三点等待，按锚点进入 |
| device-stage | browser-device-stage | settle和换屏，按规格改横推与三灰点 |
| laptop-3d | app-showcase | 设备透视与缓推；去掉手机/霓虹CTA，换成桌面笔记本 |
| filmed-screen | filmed-screen | 透视与确定性手持漂移，降低扫描线强度，保留清晰度 |
| cursor-zoom | cursor-zoom-follow | 跟随、点击环；真实日志、0.12平滑与可重复seek |
| terminal-run | code-terminal-run | 逐行输出、末尾成功状态，炭色终端 |
| code-diff | code-diff | 删除/新增行错位进入；按规格用红/蓝底 |
| bar-compare | animated-bar-chart / chart-story | 柱从底部生长、计数与刻度 |
| progress-ring | conic-progress-ring | 进度揭示；改用可seek的SVG环与完成章 |
| rank-race | bar-chart-race | 值和排名在关键帧之间平滑插值，强制来源 |
| concept-hub | constellation-hub | 中心辐射关系、连线与节点逐个点亮 |
| photo-path | carousel-path-2 | 波浪路径流动、聚焦图放大，其余压暗 |
| hand-mark | hw-arrow / hw-callout-circle / hw-underline / hw-box-label | 路径描线、轻微boil，合并为kind接口 |
| word-swap | kinetic-type-swap | 关键词竖向推换，统一宋体与荧光 |
| headline-slam | headline-slam | 字符砸入及回弹，位移收敛为2px |

转场保留 directional-wipe、cinematic-zoom、grid-pixelate-wipe、halftone-dissolve、flash-through-white、chromatic-aberration-wipe；统一0.5秒。色散改用红章/蓝墨薄边，移除RGB霓虹；半调使用网点遮罩，网格使用分块揭示，均不采样外部画面。

质感层保留 grain-overlay、light-sweep-pass、notification-stack：纤维强度0.06、卡片扫光、纸色通知。没有纳入规格“不收”的glitch/扭曲、星空/极光等效果，也没有替换为未列出的同族原件。

第一批表头写“16”，逐项A1–G2实际17个，按列名全覆盖。接口和中文样例见 [recipes.md](recipes.md#首批视觉词汇a1g2) 与模板 `vocab-examples.json`。

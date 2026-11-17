# 成片的三条画面硬门

构建后先用 `npm run check -- --visual-only` 做结构预检；渲染后运行：

```bash
npm run check -- --rendered renders/成片.mp4
# 只复验下面三门，不启动原生布局与转场检查
node check.mjs --cinema-only --rendered renders/成片.mp4 --json
```

默认阈值放在 `episode.json` 的 `cinema.limits`，可只覆盖需要的项：

```json
{"cinema":{"limits":{"maxStillSeconds":2.5,"minReadTextPx":28,"maxNoCameraRatio":0.5}}}
```

| 门 | 判定与证据 |
|---|---|
| 静止 | 同一镜头内无可见变化的连续区间 **>2.5s** 拦截。读取完整 MP4，24fps/256×144 亮度帧，3×3 平滑后与上次变化的帧累计比较，缓慢推近也能被识别。默认亮度差 >10 且变化面积 ≥0.2%；只分析主体区域 x=5%–95%、y=7%–91%，避免边缘 HUD/时间码及低幅纸纹将静画假计为变化。`pixelDelta`、`changedFraction` 可调。 |
| 重点字高 | 在 1920×1080 本地 composition 的阅读时刻截取实际重点区域，由 Apple Vision 测像素字高；**<28px** 拦截并提示 zoom/crop。不是原图字号或 CSS font-size。区域不可见/无法测量会报告缺少证据，不能算通过。 |
| 机位运动 | 实测机位层的推近/平移/视差变换；无运动的镜头**数量比例 >50%** 拦截。每 0.1s 采样，剔除统一入场/退场的各0.5s。识别 `.yf-cam`、`[data-camera]`、媒体 `.v-world`，以及 laptop/filmed 的真实机位容器；卡片/文字入场不计机位。 |

机位门测 composition 的机位层，素材视频自身的摄影机运动未单独做光流分类。给素材加明确的推/移机位层即可获得可复核证据。微小变化的默认容差是平移 0.5px、缩放 0.001，可用 `minTranslationPx`、`minScaleChange` 调整。比例采用镜头数，不能用一个长运动镜头抵消多个静止短镜头。

阅读区可在单幕写 `readingRegions:[{name:"headline",media:0,rect:{x:400,y:100,w:800,h:100},at:1.5}]`：rect 是原媒体像素，media 是媒体槽，at 是 composition 内秒数；也支持 `selector` 指向指定图片，或 `screenRect:{x,y,w,h}` 使用画布像素。news-card 默认使用 highlight 区域并选择可见的放大副本；hand-mark 的网页截图默认测 target。未标重点的网页画面会在 `unmarkedReadingScenes` 列出，背景截图不自动当作全文阅读材料。

输出 `cinema-check-report.json`（每镜静止区间、机位采样、字高与失败镜头）及 `reading-regions/` 像素证据。检查只访问本机文件和匿名本地 Chrome，不访问外网；需要已有 Playwright、Chrome、FFmpeg，以及 macOS Vision/Swift。Playwright 可用 `YICE_PLAYWRIGHT_MODULE` 指定；GSAP 从本期 HyperFrames 依赖读取，也可指定已有的 `YICE_GSAP_PATH`。

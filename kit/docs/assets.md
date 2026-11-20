# 素材入口与许可账本

## 剪辑时按需造画面

六类素材统一从 `produce-asset.sh` 进入。命令会在项目根目录原子更新 `asset-ledger.jsonl`，并在请求前检查 image2 `$5.00` 与图库 60 次整期预算。

```bash
KIT=/绝对路径/yice-youtube-video/kit
"$KIT/scripts/produce-asset.sh" --kind metaphor-image --project "$EPISODE" \
  --id opening-metaphor --prompt '真实摄影感的中文教程开场隐喻' --json
"$KIT/scripts/produce-asset.sh" --kind motion-video --project "$EPISODE" \
  --id moving-screen --prompt '夜间工作台上的电脑界面反光' --duration 4 --json
"$KIT/scripts/produce-asset.sh" --kind rec-task --project "$EPISODE" \
  --id rec-home --input /项目目录 --prompt '录制首页操作与点击轨迹' --json
```

`motion-video` 只有在 `YICE_MODAL_SPEND_LIMIT_USD=0` 或 `YICE_MODAL_GUARD_FILE` 明确记录 `spend_limit_usd: 0` 时才会提交。`prop-cutout` 复用既有 `props.py`，`web-capture`、`stock-footage`、`rec-task` 分别复用本目录的网页、图库和录屏入口。

所有入口均不登录、不注册。素材落盘后将来源 URL、抓取日期、许可链接、作者/署名、镜头号、文件与 SHA-256 记入每期 `asset-ledger.jsonl`（字段见模板）。媒体库 `.media/manifest.jsonl` 负责文件复用，不能代替许可账本。

## icon / 官方标志

```bash
npx --yes hyperframes@0.9.58 media-use resolve --type logo --entity 'Google Chrome' \
  --intent '教程中识别浏览器' --project "$EPISODE" --candidates --json
npx --yes hyperframes@0.9.58 media-use resolve --type logo --entity 'Google Chrome' \
  --intent '教程中识别浏览器' --project "$EPISODE" --json
```

先查缓存，只有实体一致才复用。核对 resolver 的实体、域名和原图；例如只写 Codex 可能误命中 codex.com，不能当作 OpenAI Codex。收藏/代码仓库声称 CC0 也不代表品牌商标授权。

若搜索不支持、返回低清 favicon 或需要账号，使用已核验的官方直链，不登录兜底服务：

```bash
npx --yes hyperframes@0.9.58 media-use resolve --type logo --entity 'Google Chrome' \
  --intent '官网原始标志，保持比例与颜色' \
  --from 'https://www.google.com/chrome/static/images/chrome-logo-m100.svg' --project "$EPISODE" --json
# icon 同样支持 --from <官方图片直链或已下载本地文件>
```

没有文件扩展名的 Apple 图片直链会被 resolver 拒绝；先验证 HTTP Content-Type 为 image/*，下载到本地，再 `--type icon --from <本地文件>`，账本仍保留原始 URL。icon 的搜索服务并非全部免费可匿名；`--from` 导入免费且不需账号。不要重绘、改色或拉伸品牌图标，不把“抓到文件”写成“可任意商用”。

## 网页静帧和滚动片段

原生入口可提取公开页面、截图、样式和素材清单，不会自动产出滚动 MP4：

```bash
npx --yes hyperframes@0.9.58 capture https://example.com --output capture-example \
  --skip-vision --max-screenshots 3 --timeout 30s --json
```

本套件补齐真实浏览器滚动：在每期目录先 `npm install`（模板固定 `playwright-core`，复用已安装 Chrome；不下载浏览器、不导入登录态），然后：

```bash
node "$KIT/scripts/capture-web.mjs" --project "$EPISODE" --url https://example.com \
  --id example-com --scene S1 --seconds 7 --source 'Example Domain'
```

输出 `assets/web/<id>/still.png`（1920×1080）、`scroll.mp4`（6–8 秒/15fps）和 `capture.json`；同时写账本。页面足够短时没有滚动距离，报告为 `short_page_hold_no_scroll_range`，不伪造滚动。可用 `YICE_CHROME_EXECUTABLE` 指定 Chrome，或用 `YICE_PLAYWRIGHT_MODULE` 指向已有 playwright-core 包。

批量采集读 `asset-needs.example.json` 的结构：每项包含论点、类型、候选 URL、镜头、许可和截取方式。复制成 `asset-needs.json` 后执行：

```bash
node "$KIT/scripts/capture-web.mjs" --project "$EPISODE" --needs "$EPISODE/asset-needs.json"
```

只处理 `type: news_capture`；同一项依次尝试候选 URL，首个成功即停止。`capture.seconds` 为 6–8 秒；`capture.highlight` 指定要定位的一句话，记录文字框供 [news-card](recipes.md#news-card) 高亮与推近。批次报告 `web-capture-report.json` 区分 `captured`、`skipped`、`failed`，一页失败不影响其他项。同一素材 id 重新采集会替换账本旧行，避免旧文件校验信息残留。

## 开放授权图像与视频

优先使用三源候选入口，检索阶段只保存缩略图，不下载原件：

```bash
"$KIT/scripts/find-media.sh" --q 'laptop' --type photo --n 8 --out "$EPISODE/candidates/laptop"
"$KIT/scripts/find-media.sh" --q 'city night' --type video --n 8 --out "$EPISODE/candidates/city"
# 中心选定 candidates.png 中的 ID 后，再下载并入账
"$KIT/scripts/find-media.sh" --download "$EPISODE/candidates/city/candidates.json" \
  --select archive-选定ID --project "$EPISODE" --scene S3 --max-mib 25
```

合并 Commons、NASA、Archive；本机有密钥时优先加入 Pexels、Pixabay。按来源轮流取候选，输出 `candidates.png` 和 `candidates.json`。可用 `--sources nasa,archive` 指定来源。报告保留原始页面、逐件许可、作者、署名义务、分辨率、视频时长和查询错误；源未给出尺寸/时长时明确写 `null`，不编造。某源限流或不可达时记 `test_limit` 并继续其他源，不绕过访问限制。

Pexels/Pixabay 密钥**只从**本机 `~/.config/yice-video/stock.env` 读取（变量 `PEXELS_API_KEY` / `PIXABAY_API_KEY`）；缺少即跳过。密钥不打印、不复制到项目；API 返回 URL 中的 key 参数在缓存前移除。Pexels 使用请求头认证；Pixabay 的请求参数只存在于内存。两图库照片和视频可商用，成品无需署名，但来源页与作者仍入账；素材展示说明为 **Photos/Videos provided by Pexels** / **Content provided by Pixabay**，并保留作者与来源链接。不要单独转售或把原件重新分发为图库。依据：[Pexels 许可](https://www.pexels.com/license/)、[Pixabay 许可](https://pixabay.com/service/license-summary/)。

视频可加 `--min-width 1920 --min-height 1080 --max-duration 15`；先在单页搜索响应中筛选，不自动翻页，不批量预下载。两图库优先选 1920×1080 版本。

### 本线 API 预算

所有 API 响应（含失败）缓存 **24 小时**；同源、关键词（去首尾空格/合并空格/忽略大小写）、素材类型相同，即使 `--n` 改变也复用缓存。默认先查缓存，命中不记调用。每次 `find-media` 最多 **3 次 API 请求**，包含 NASA/Archive 补元数据的请求；预算用完的源记 `deferred_budget`，保留已取得的候选，不自动发起下一轮。缩略图与显式选定的媒体下载不算 API 请求。

搜索时用 `--project "$EPISODE"` 标识本期（默认当前目录）。Pexels+Pixabay 合计**每期 60 次、本线每个 UTC 自然月 1,500 次**；请求前预留，网络失败也保守计数，超限拒绝新请求，缓存仍可用。共享密钥还用于 Prezto，本线预算和账号总额度独立。

```bash
"$KIT/scripts/media-usage.sh" --project "$EPISODE"
```

输出分别列出 `youtubeLine`（本线每日/本月/本期已用）和 `sharedAccountRemaining`（共享账户最后观测的剩余量/重置时间）。用量计只读本机私有 `~/.config/yice-video/usage.jsonl`，不调用 API；日志仅时间、来源、关键词、额度响应头，不含密钥。Pexels reset 为 Unix 时间，Pixabay reset 为相对秒数；过期窗口标记 `stale`，不将旧数当实时余额。预算和缓存也在同一私有目录，测试注入临时目录与 mock 响应，真实测试调用由 `YICE_MEDIA_OFFLINE=1` 拒绝。依据：[Pexels 额度头](https://help.pexels.com/hc/en-us/articles/900005368726-How-do-I-see-how-many-requests-I-have-remaining)、[Pixabay 缓存与速率](https://pixabay.com/api/docs/)。

Commons 接收 PD、CC0、CC BY、CC BY-SA；NC/ND 一律过滤。BY-SA 素材须署名、附许可、标明修改，并对改编作品履行同许可共享义务。NASA 仅接收有 NASA 机构/作者依据且无第三方版权声明的素材，保留原始元数据；[NASA 媒体规则](https://www.nasa.gov/nasa-brand-center/images-and-media/)允许许多编辑用途，但不授权暗示 NASA 背书，人物/标志的广告用途须另核。Archive 的许可由上传者填写，因此此入口限定其 Prelinger 公有领域影片和 NASA 图像馆藏，并仍逐件要求 PD/CC0 标记；不会把任意上传者标注的“public domain”视为可靠授权。

显式选择后复用许可账本；视频原件保留，webm/ogv 等经 FFmpeg 转为 H.264/AAC MP4，FFprobe 补齐实际尺寸/时长，账本同时记录原件与输出哈希。默认单件上限 25MiB，可用 `--max-mib` 调整；转码失败不会登记为成功。接口依据：[NASA API](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf)、[Archive 元数据](https://archive.org/developers/md-read.html)、[Commons 机器可读许可](https://commons.wikimedia.org/wiki/Commons:Machine-readable_data)。

以下兼容入口会自动下载首个许可齐全的候选；需要先挑选时使用上面的新入口：

```bash
node "$KIT/scripts/open-media.mjs" --provider commons --query 'image compression' \
  --project "$EPISODE" --scene S2
node "$KIT/scripts/open-media.mjs" --provider openverse --query laptop \
  --project "$EPISODE" --scene S3
```

匿名 API 搜索；API 不可用时只尝试正常公开搜索页。Commons 支持图像与视频，当前 Openverse 入口使用图像 API。依次核对最多 5 件候选，下载第一件作者、来源与许可齐全的素材（上限 25MiB），保存到 `assets/open/`，写入 `asset-ledger.jsonl` 和 `open-media-<provider>-report.json`。

当前入口接受逐件 CC BY、CC BY-SA、CC0 或公有领域标记，不把整个图库视为统一授权；NC、ND、未知许可不自动下载。Openverse 是索引，下载前还要到原始来源页核对许可链接。账本保留作者、原始页面、许可链接、署名文本、文件 SHA-256 和镜头；使用时保留署名，改编时标明修改并遵守相同方式共享等条款。许可依据：[Commons 使用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)、[Openverse API](https://api.openverse.org/v1/)、[Openverse 条款](https://docs.openverse.org/terms_of_service.html)。

访问挑战、登录墙或限流会记录失败/跳过原因；`skipped` 不是下载成功，也不应填成片占位。2026-11-17 实测 Commons 的公开页面流程成功；本机 Openverse API 与搜索页均返回 403，成功下载样例尚待可访问环境验证。

## 透明抠图与剪报

```bash
"$KIT/scripts/cutout.sh" /本地/照片.jpg --project "$EPISODE" --id subject-01 \
  --source-json /本地/来源记录.json --scene S2 --angle -3
# 可选 --crop x,y,width,height：先按原图像素裁出主体
```

来源记录填写 `sourceUrl`、`licenseUrl`、`license`、`creator`（已有素材账本行可直接使用）。输出 `assets/cutouts/<id>/transparent.png` 与 `paper.png`，后者有 12px 白边、轻纸纹、柔和投影和 −3°～+3° 倾斜；源图、已有透明度和主体颜色保留。账本记录原始哈希、裁切、处理参数、输出哈希和修改声明，衍生图继续受原许可约束。

本地后端使用 [Apple Vision 前景分割](https://developer.apple.com/documentation/vision/vninstancemaskobservation/generatemaskedimage%28ofinstances%3Afrom%3Acroppedtoinstancesextent%3A%29)，需要 macOS 14+ 和 Xcode Command Line Tools；不登录、不上传、不下载第三方模型。图片经 EXIF 方向归正，最长边缩至 1600px 后分割。无主体、没有有效透明度或系统分割失败时明确报错，不把整张图当作成功抠图。Python/Pillow 复用道具环境，可用 `YICE_IMAGE_PYTHON` 覆盖。

只点击“拒绝非必要 cookie”；登录墙、付费墙、验证码/访问挑战跳过并记录原因，不掩盖遮挡、不绕过。只截短片段、标明来源和日期；不下载别人 YouTube/抖音的视频放入成片。网页和品牌素材按具体使用语境核对许可，开放图库按逐件许可处理。

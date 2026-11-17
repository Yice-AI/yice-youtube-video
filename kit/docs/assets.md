# 素材入口与许可账本

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

```bash
node "$KIT/scripts/open-media.mjs" --provider commons --query 'image compression' \
  --project "$EPISODE" --scene S2
node "$KIT/scripts/open-media.mjs" --provider openverse --query laptop \
  --project "$EPISODE" --scene S3
```

匿名 API 搜索；API 不可用时只尝试正常公开搜索页。Commons 支持图像与视频，当前 Openverse 入口使用图像 API。依次核对最多 5 件候选，下载第一件作者、来源与许可齐全的素材（上限 25MiB），保存到 `assets/open/`，写入 `asset-ledger.jsonl` 和 `open-media-<provider>-report.json`。

当前入口接受逐件 CC BY、CC BY-SA、CC0 或公有领域标记，不把整个图库视为统一授权；NC、ND、未知许可不自动下载。Openverse 是索引，下载前还要到原始来源页核对许可链接。账本保留作者、原始页面、许可链接、署名文本、文件 SHA-256 和镜头；使用时保留署名，改编时标明修改并遵守相同方式共享等条款。许可依据：[Commons 使用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)、[Openverse API](https://api.openverse.org/v1/)、[Openverse 条款](https://docs.openverse.org/terms_of_service.html)。

访问挑战、登录墙或限流会记录失败/跳过原因；`skipped` 不是下载成功，也不应填成片占位。2026-11-17 实测 Commons 的公开页面流程成功；本机 Openverse API 与搜索页均返回 403，成功下载样例尚待可访问环境验证。

只点击“拒绝非必要 cookie”；登录墙、付费墙、验证码/访问挑战跳过并记录原因，不掩盖遮挡、不绕过。只截短片段、标明来源和日期；不下载别人 YouTube/抖音的视频放入成片。网页和品牌素材按具体使用语境核对许可，开放图库按逐件许可处理。

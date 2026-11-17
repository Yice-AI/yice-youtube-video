# 实体采集

```sh
kit/scripts/collect-entity.sh --name 'OpenAI Codex' \
  --site https://openai.com/codex/ --github openai/codex \
  --out /本期/entities/openai-codex
```

`--site`、`--github owner/repo`、`--press URL` 至少给一个。浏览器使用本机 Chrome 的全新匿名上下文，不读个人登录状态。可用 `YICE_PLAYWRIGHT_MODULE` 指向已有 Playwright；`YICE_HYPERFRAMES_CLI` 可指向本机 HyperFrames CLI 文件，未设时使用已安装的 `npx --no-install hyperframes`。

官网首屏与关键段落为 1920×1080；平滑滚动 8 秒；页面自带演示按真实播放状态录 6 秒静音片段。没有演示、播放需要操作、登录/付费墙、自动访问拒绝都记录具体原因。单页先采前 3 个关键标题、前 6 个可见演示；超出部分在清单注明，避免把无限加载页面变成整站镜像。采集 6 秒供剪辑，官方视频在成片里的实际引用仍须 **≤5 秒、静音、带来源，仅用于评论语境**。

logo 通过 media-use 冻结，优先官网原始图片/品牌 SVG。商标仍归权利人，不能写成 PD。媒体包只有页面明确声明可供媒体使用才下载图片，并保留声明原文；“Media kit”标题本身不视为授权。GitHub README GIF 保留原作者权利说明，不假定代码许可覆盖媒体。公告优先按官方列表日期选择最新一篇；没有日期时标记“列表首篇，日期未核实”。

输出 `manifest.json`、`asset-ledger.jsonl`、`overview.png` 和 `harness-draft.md`。每项包含 URL、抓取时间、类型、用途建议、许可说明、文件与哈希，跳过项包含原因。交互入口、匿名 Hugging Face Spaces 和试用框只生成导演口吻的录屏草稿，**不操作试用、不派发任务、不写 dsh-inbox**；中心审核后另行交给 Harness。

幕表直接引用清单：

```json
{
  "id": "S1",
  "recipe": "news-card",
  "props": {
    "entity": {"manifest": "entities/openai-codex/manifest.json", "item": "site-hero"},
    "headline": "用 Codex 做压图工具"
  }
}
```

`social-post` 使用同样的 `entity` 引用，默认显示官网标题摘录和来源，不生成虚构账号互动量。素材自动冻结到本期构建并登记来源账本；缺失、失败、哈希改变或越出实体目录的文件会报错。`date` 是抓取日期，不能冒充发布日期。

离线测试使用模拟响应和本地网页；不消耗 Pexels/Pixabay 额度。该入口实际采集官网及 GitHub，不调用图库搜索 API。

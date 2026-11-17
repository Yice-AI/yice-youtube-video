# 素材需求

写稿时逐条填写；机器采集读同名 JSON（见 `asset-needs.example.json`）。类型映射：资讯实拍=`news_capture`；开放授权图视频=`open_media`；数据图表=`data_chart`；录屏=`recording`；image2=`image2`。

| ID / 用在哪一镜 | 论点 / 画面要证明什么 | 素材类型 | 候选 URL | 截取方式 | 许可与署名 |
|---|---|---|---|---|---|
| codex-announcement / S1 | 用官方发布信息确认产品定位 | 资讯实拍 | https://openai.com/index/introducing-codex/ | 静帧 + 滚动7秒；高亮 Introducing Codex | 页面版权保留，短段引用，标来源日期 |
| compression-photo / S3 | 让观众看到图像压缩的视觉差异 | 开放授权图视频 | 写检索候选文件页 URL | 下载1件，使用原图或短片段 | 逐件写 CC 版本、作者、许可链接 |
| compression-data / S4 | 132MB 到 14.8MB 的变化 | 数据图表 | 本期测量证据 / 公开数据源 URL | 代码绘制对比图 | 数据来源与采集日期，不截别人图表 |

| 幕号 | 素材 | sourceType | 来源 URL / 许可链接 | 署名 | 文件 | 状态 |
|---|---|---|---|---|---|---|
| 0-1 | 透明实物PNG | image2 | 原创/生成记录 | 本期制作 | assets/props/demo-prop-01.png | 待准备 |
| 0-4 | 真实录屏 | recording | 本人操作 | 本人 | assets/local/demo-rec.mp4 | 待准备 |
| 0-5 | 官方 logo / icon | third_party | 填官网原图与品牌条款；不把收藏库许可当商标授权 | 品牌权利人 | assets/stock/logo.svg | 核对实体、比例和许可 |
| 0-6 | 公开网页 | web_capture | 填页面 URL；短片段引用用途待核对 | 来源名 + 日期 | assets/web/page/still.png | 不登录采集 |

每条实际文件须同步记入 `asset-ledger.jsonl`，模板为 `asset-ledger.example.jsonl`。入口见 `kit/docs/assets.md`。

# 私有人物素材库

库位于工作区 `ip-tools/data/people-library`，不打包进公开 skill。`YICE_PEOPLE_LIBRARY` 或 `episode.peopleLibrary` 可改位置。

```sh
kit/scripts/people-add.sh --name 'Sam Altman' --src ./source.jpg \
  --tier default --mood 思考 --source-json ./source.json
```

来源 JSON 必填 `sourceUrl`、`license`；default 另需 `sourceType: official_press|official_event|commons`。应带作者、许可链接和许可核对依据；不得把官方保留版权照片写成 CC/PD。commentary 不传来源文件时仅记录原权利人保留。公开视频可加 `--frame 秒`，多人照片可加 `--crop x,y,width,height`，不改原件和真实表情。

工具复用 Apple Vision，输出 1080×1080 透明 PNG，主体长边 860px，白边 10px、轻纸纹、投影。原件、哈希、裁切坐标、处理方式保存在 manifest；没有有效主体会失败。只有边缘透明的 PNG 仍需分割。同一原图/同一视频帧不能换 mood 标签凑数。mood 是可见表情与手势的检索分类，不声称人物的实际内心活动。

```json
{"recipe":"reaction-cutout","props":{"personRef":{"name":"Sam Altman","mood":"思考"},"text":"先看实测","ink":"blue"}}
```

build 按姓名+mood 查库，默认优先 default，核验哈希后冻结进本期，并把 tier/来源/作者/许可写入账本。default 可用于正文和缩略图；commentary 只在正文评论语境用。缩略图须在 `episode.thumbnail.assets` 或 `thumbnail-manifest.json` 的 `assets` 中声明账本 ID；引用 commentary 时 check 拦截，也支持按场景 ID 声明 `scenes`。这是素材引用检查，不是人脸识别。

不收政治人物、敏感历史照片；不改造表情、不丑化、不编造人物台词、不暗示代言。人物旁文字是我们的评论，不能加引号伪装其原话。CC BY/BY-SA 保留作者、许可与修改说明；BY-SA 在片尾或发布简介署名，投诉时替换来源。

原创反应角色复用 `scripts/props.sh` / `props.py` 的 image2 接口，只生成原创非真人角色。每批指定全期共用 `--case-dir` 和既有 `--budget`；请求前预留，单张 usage 成本记账，不得新建账本绕开累计预算。本批只生成一张样例。

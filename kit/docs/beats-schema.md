# beats.json 与 episode.json

依据本包 `template/build.mjs` 和 `template/assets/yice.js`。画布 1920×1080，单位为秒与像素；图片坐标百分比只用于明确标出的录屏/文档区域。HyperFrames 固定 0.9.52。

## 一期配置

```json
{
  "id": "ep02",
  "voiceDir": "voice",
  "mediaRoots": {
    "@media/": "assets/local",
    "@assets/": "assets/props",
    "@stock/": "assets/stock"
  },
  "chapters": {"00": {"title": "开场", "stage": "charcoal"}},
  "end": 20
}
```

`id`、`voiceDir`、`chapters` 必填；`voiceDir` 含 voice-timing.json、voice-manifest.json 和配音。所有配置路径相对项目根目录，也可写绝对路径。别名必须以 `/` 结尾；`@vo/` 自动指向 voiceDir。chapters 的键对应 manifest 章号，用于章标题和默认舞台色。end 优先于 beats.end，必须为正数。

可选 `assetBase` 指定外部素材复制后的文件名参照根，默认项目根。正常新一期无需设置；复刻旧构建时指向旧构建器的素材根，保持 compositions 中的 URL 一致。构建只向当前项目写入，不改被引用的源素材。

## 幕表

```json
{
  "end": 20,
  "scenes": [{
    "id": "S0-1",
    "sents": ["0-1"],
    "recipe": "photo-word",
    "stage": "charcoal",
    "enter": "cut",
    "media": [{"src": ["@assets/mic.png", "@media/mic-photo.jpg"]}],
    "spec": {"word": {"text": "声音", "at": "@声音"}, "obj": {"x": 1000, "y": 180, "w": 700}},
    "fallbackSpec": {"obj": {"x": 960, "y": 180, "w": 750, "photo": true}}
  }]
}
```

| 字段 | 实际行为 |
|---|---|
| scenes | 有序数组，顺序即播放顺序；必须至少一幕。 |
| id | 唯一幕 id；生成文件名时转小写并把非字母数字下划线/连字符替换为 `_`。避免转义后重名。 |
| sents | voice-timing 句子 id 数组，至少一个。多句幕使用 `0-6.1` 等句子 id；不是剧本幕号的自动展开。 |
| recipe | [15 个配方](recipes.md)中的名称，不带 `.html`。 |
| stage | 覆盖章默认色：`paper-cool`、`paper-warm`、`paper-gray`、`charcoal`。 |
| enter | `cut` 默认，或 `pan`、`push`、`match`、`lift`、`rise`。第一幕强制 cut。 |
| media | 顺序即配方里的 m0、m1；不用素材的配方可省略。 |
| spec | 配方输入，字段按 recipes.md。 |
| fallbackSpec | 任一 media 用了第二个及以后候选时，浅合并到 spec。嵌套对象整项替换，不深合并。 |

第一幕边界 B=0；后续 B=该幕首句 firstCharTime−0.2。结束 E=下一幕 B，末幕 E=episode.end。非 cut 入场提前 0.5 秒开始，覆盖上一幕末尾；退出动画自动取下一幕 enter。`match` 是入场淡入，其余退出行为见 yice.js。不要手写 start/duration/exit，它们由构建器生成。章归属按 B 落在哪个 manifest 区间计算。

## 时间与语音锚点

构建器只递归转换键名 **at、strike、markAt**：数值或 `"+0.4"` 表示 B 后的秒数；`"@声音"` 查 sents 中 anchors 的同名短语；`"@声音#2"` 取第 2 次出现；`"first:0-1"` 取指定句 firstCharTime。锚点查不到直接报错。转换后时间相对该幕提前入场后的 start。

`d`、`rate` 等不是时间锚点字段。`media.at` 也不走 spec 转换，是视频在幕内的起播秒数。大字 word/title/lead.at 和 single-line.at 最迟被压到 B+0.9 秒；这是旧版既有行为。运行时 c.at 把时间限制在 0 到 dur−0.2，以免动作跑出幕外。

voice.sh 默认读取剧本旁的 anchors.json：`[{"scene":"0-1","phrase":"声音"}]`。画面标签与口播不同可写 `spoken_phrase` 指向原文；找不到原稿就报错，不凭空猜锚点。输出 firstCharTime 和 anchors 都是全片时间，不是章内时间。

## 素材选择与复制

src 可为字符串或候选数组，按顺序找第一个存在的文件；文件名支持 `*`，同一模式中按名称排序取第一个，不递归目录。所有候选都不存在会停止构建。不要把空候选当“可选”。

视频按扩展名 mp4/mov/webm 识别，默认静音；`start` 为源视频入点，`rate` 为播放倍率，`at` 为幕内启动时间。`kind` 只进构建报告，不决定视频类型。`optionalFirst` 当前不改变回退判定，不要依赖它忽略错误。构建器注入 `mediaFallback[]` 给配方判断备选素材。

外部素材复制到 assets/media；项目 assets/ 下素材直接使用。**每次 build 会清空 assets/media 再生成**，手工素材请放 assets/local、assets/props、assets/stock。voice.sh 的 manifest 音频 path 相对 voiceDir，也兼容旧版绝对路径。

## 构建与检查

`npm run build` 生成 index.html、compositions/scenes 和 build-report.json。`node build.mjs --from 10 --to 30` 裁主时间线；`--only S0-1,S0-2` 只筛主页面引用，不删除时间轴空档，也仍生成全部子幕。日常完整片直接 build，不用 only。

构建后 `npm run check`，再用 render.sh 和 review.sh。build 成功仅证明时间、路径及配方替换完成，不能代替运行时检查和看图。

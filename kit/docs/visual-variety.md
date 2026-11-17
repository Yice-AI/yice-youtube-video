# 画面单调度与每期视觉指纹

在每期工程运行 `node check.mjs --visual-only --json`，或正常 `npm run check`。先检查镜头表；未通过则退出 1，不启动昂贵的渲染检查。输出 `visual-fingerprint.json`、`visual-check-report.json` 和总 `check-report.json`。通过后仍需原有视频/技术/人工审片。

输入为 `beats.json` 的 `scenes`（也接受 `shots`）。使用正片的 B/E 边界，优先显式 B/E 或 start/end，其次当前配音 timing，最后 build-report；转场重叠不重复计时。所有时间单位为秒。写镜头表时可直接填数值边界，无须先渲染。

在 `episode.json` 配置：

```json
{
  "visual": {
    "previousFingerprint": "../ep01/visual-fingerprint.json",
    "limits": {
      "maxBareRecordingSeconds": 20,
      "minNonRecordingRatio": 0.4,
      "minSourceTypes": 3,
      "maxRecipeUses": 4,
      "minTransitionKinds": 3,
      "maxPreviousRecipeOverlap": 0.7,
      "minNewRecipes": 1,
      "minRecordingContainerKinds": 2,
      "minTitleFreeRatio": 0.4,
      "maxConsecutiveLayout": 3
    }
  }
}
```

首期没有上一期时设 `previousFingerprint: null`，报告会明确显示没有比较；后续必须填写上一期指纹路径。不得把不同期的指纹覆盖成同一个文件。

默认硬门：无叠加层/插镜的录屏连续 **>20 秒**；非录屏主画面 **<40%**；五源 **<3 类**；同配方 **>4 次**；转场 **<3 类**；本期配方集合复用上一期的比例 **>70%**，或 **没有新增配方**。复用率定义为交集数量÷本期不同配方数量；不是按镜头使用次数算。正好 20 秒、40%、4 次、3 类和 70% 均在允许边界内。

五源字段 `sourceType`：`recording`（录屏含其静帧）、`code_animation`（代码动画/图表）、`third_party`（第三方图/视频/icon/logo）、`web_capture`（公开网页实拍）、`image2`。每个镜头可写主源，每个 media 可写各自来源：

新增第8条：用于录屏主画面的 B 族容器必须至少2种，固定集合为 `device-stage / laptop-3d / filmed-screen / cursor-zoom`；同一容器多次出现只算一种，承载网页/图片而非录屏时不计。指纹保存 `recordingContainers`。原有 `rec-zoom` 是固定框推近，不能冒充新B族。新 `props` 媒体槽同样参与来源统计；grain/light-sweep 不作为信息层中断连续裸录屏。

第9、10条：至少40%的镜头不出左上标题；同一版式骨架连续超过3镜就拦。新配方用 `props.showTitle:false`；headline-slam/word-swap天然无左上标题。有标题的不同配方都归为同一“左上标题+中心内容”骨架，不能仅换配方名称绕过；无标题时按设备、满幅屏幕、图墙、金句等实际结构分组。旧配方依据 `spec.title` 识别标题，其余保留配方结构标识，人工审片仍须核对。指纹新增 `titleFreeScenes/titleFreeRatio/layoutRuns`，恰好40%和连续3镜允许。

```json
{
  "id": "S1", "recipe": "rec-zoom", "start": 0, "end": 30,
  "sourceType": "recording",
  "media": [{"src": "assets/demo.mp4", "sourceType": "recording"}],
  "overlays": [{"at": 8, "duration": 3}],
  "inserts": [{"at": 18, "duration": 5, "sourceType": "web_capture"}]
}
```

`overlays` / `inserts` 是实际画面时间表的描述，不会自行画出元素；须与配方里渲出的动作一致。`at` 相对 B，可用数字、`+秒数`、`@锚词#次数` 或 `first:句号`，`duration` 省略表示持续到镜头末尾。支持同样的 `visual.overlays` / `visual.inserts`，以及 media 的 `role: overlay|insert`。已有配方的 title/tag/hl/hls/notes/props/clip/stamp/circle 会自动作为信息叠层计算。

非录屏占比仅计算非录屏主画面和插镜的时间并集，往录屏上加一个小 logo 不会把整段算成非录屏。来源时长按各来源的出现区间分别取并集，同源重叠不叠加；不同源同屏可同时计时，来源时长之和可以大于片长。连续录屏会跨镜头边界合并，再扣除叠加/插镜区间，不能靠拆成几个短镜头绕过 20 秒限制。

旧镜头表兼容推断：rec-zoom→录屏；doc-zoom/news-card→网页；stock-shot→第三方；道具路径 `@assets/`、`/props/`、`/image-数字`→image2；其余无素材配方→代码动画。所有推断记在报告 `assumptions` 中，新素材请显式声明，避免把下载视频误判为录屏。模板里的短演示 beats 不是通过整期硬门的成片范例。

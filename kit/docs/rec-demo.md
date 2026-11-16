# 一份参数录完一期演示

`rec-demo` 复用 [rec-shot](rec-shot.md) 的动作和守卫。它不调用网络或大模型，不需要 Claude 看屏幕。输入消息、完成标志和已知界面状态由参数文件明确指定；没有规则覆盖的状态停下处理。

## 入口

```sh
# 纯预演：不启动界面后端，不截图、移动鼠标、输入、编译或创建文件。
bash kit/scripts/rec-demo.sh /absolute/evidence/demo-params.json --dry-run
```

审核预演结果后，中心通过已经从授权终端启动的 [rec-bridge](rec-bridge.md) 投递：

```json
{"action":"rec-demo","params":"/absolute/evidence/demo-params.json"}
```

请求先写临时文件，再原子移入 `queue/`。`params` 是唯一参数，不能附带任意命令或运行选项。已有 bridge 进程需由中心加载支持这个动作的版本后再投递，改源码不会让旧进程自动更新。队列串行运行；同名请求不重放。bridge 的总超时须大于所有镜头超时之和及录制/裁切耗时。

真实执行需要 macOS、Python 3、Xcode Command Line Tools、ffmpeg/ffprobe，以及执行进程已有的屏幕录制和辅助功能权限。系统授权、登录、信任确认由用户本人处理。参数本身必须在已授权的演示范围内。

## 参数示例

以下是合成示例，路径和界面文字需换成当期真实值，不可直接实录。

```json
{
  "version": 1,
  "project": "示例项目",
  "output_dir": "/absolute/evidence/demo",
  "process": "ChatGPT",
  "title_contains": ["示例项目", "演示对话"],
  "reference_window": [0, 0, 1200, 800],
  "input": {
    "region": [120, 560, 960, 120],
    "empty_text": "给示例发消息",
    "empty_texts": ["继续发送消息"],
    "suggestions": ["检查一下演示结果。"]
  },
  "ocr": [
    {"region": [0, 0, 1200, 800], "must_not_contain": ["其他私有对话"]}
  ],
  "ui": {
    "region": [120, 180, 960, 500],
    "question_markers": ["请选择演示界面颜色"],
    "skip_text": "跳过",
    "forbidden": ["需要你的批准"]
  },
  "messages": [
    {"text": "做一个带“@示例”水印的本地演示页。", "completion_text": "用时", "timeout": 1800},
    {"text": "把按钮字号调大一点。", "completion_text": "用时", "timeout": 600}
  ],
  "before": [],
  "after": []
}
```

- 必填：`version/project/output_dir/messages`，以及至少一项已知输入框占位文字或建议句。每条消息必须有 `text/completion_text/timeout`，超时单位为秒。
- `process` 默认 `ChatGPT`，`title_contains` 默认项目名。标题必须足以唯一识别目标窗口；消息过程中标题若变成未获准的标题，会停止，不猜测新窗口身份。
- `reference_window` 是参数中坐标所属的参考窗口，默认 `[0,0,1200,800]`；真实执行读取匹配窗口的位置和尺寸，换算区域、坐标，再找唯一已知占位文字/建议句。开录后使用辅助功能取得输入框边界，适应输入框移位和增长。
- `input.region` 可省略，初始参考区域取窗口下部。若输入框无法通过已知文字或已确认焦点定位，会停止；不会用默认位置盲点。`initial_text` 必须为空。
- 问题卡片必须同时出现一个白名单 `question_markers` 和唯一 `skip_text` 才会点跳过。只填当期已知问题，不填宽泛词。出现未登记的跳过、提交、允许或批准控件文字也会停止。灰色建议应填完整文字；未知建议、弹窗或不匹配的 OCR 会留图停止。
- `completion_text` 选真正的完成标志，不能用“正在思考”。发送前记录已有标志数量；须看到标志消失再出现，或数量增加，才认作本条完成。若界面一直保留同一个标志，不能确定新任务结束，就超时停止。

## 浏览器和访达镜头

`before` 在消息前执行，`after` 在消息后执行；列表内部保持顺序。每项只有 `name/target/steps`，`target` 与 rec-shot 相同，步骤使用既有 `click/click_text/key/paste/wait/wait_text/guard` 类型。不要写 `rec_start/rec_stop`，入口统一负责启停与输出名。

```json
{
  "name": "查看演示素材大小",
  "target": {
    "process": "Finder",
    "title_contains": ["演示素材"],
    "region": [0, 0, 1000, 700],
    "input": {"region": [750, 10, 200, 30], "initial_text": "", "empty_text": "搜索"}
  },
  "steps": [
    {"type": "click_text", "region": [200, 50, 300, 40], "text": "大小", "timeout": 5},
    {"type": "wait", "sec": 3}
  ]
}
```

窗口须预先打开；脚本只激活唯一匹配的已有窗口，不启动应用或导航。浏览器可用同样格式指定 `Google Chrome` 和页面标题。加载后才出现的按钮用 `click_text.timeout` 等待。文件选择器、权限框等未知弹窗会停止，不尝试跨过；需要这些步骤时先由用户准备好界面。

## 执行与产物

先对整份参数预演校验，再逐段重新标定、写出镜头单和预演计划、开录、执行、停录。只有录制进程仍存活且文件持续写入后才允许输入；发送前从输入框复制回读，除显式字符等价表外逐字一致。录制失败或输出异常不会继续输入。具体等价表、标题重试和停录策略见 rec-shot 文档。

每次创建 `output_dir/demo-take01/`，重跑自动加号。旧素材保留，不覆盖：

- `dry-run.json`、`01-shot.json`、`01-dry-run.json`：参数预演和当次窗口标定后的镜头单。
- `01-take.mov` 及 `.rec/events.json`、`cursor.json`、`capture.log`：原片与日志。
- `.rec/take-trimmed.mov` 和 `trimmed-events.json`：依据事件裁掉静止首尾的成片和移位事件；无需裁切时直接引用原片。中间等待保留。
- 根 `events.json`：各段产物清单；`index.md`：原片/裁后时长、像素、关键事件，需模糊区域留给审核填写。
- `failure.json`：成功时 `failure:null`；失败时写段名、具体步骤、原因和私有截图位置。失败后不继续下一段，不自动重放已发消息。

坐标使用屏幕逻辑点；视频尺寸通过 ffprobe 读取。事件相对原生录制启动计时，首帧偏移未经校准，裁切前后各保留 0.4 秒，并保留原片供修正。无法推断所有未声明的非模态界面变化，隐私守卫和已知状态需按当期配置。

预演和合成测试通过，只代表编排和守卫通过；真实 macOS 权限、当前界面与采集能力仍需中心在授权演示环境验收。开发验证不得把预演请求替换成真实队列任务。

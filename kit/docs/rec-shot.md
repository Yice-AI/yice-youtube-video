# 用镜头单录 Codex App

`rec-shot` 按 JSON 顺序执行本机操作。OCR 使用 Apple Vision，不把截图、文字或录屏发送给网络或模型 API。真实运行会输入文字和发送请求，只使用已经获准录制的演示会话。

## 准备与权限

需要 macOS、Python 3、Xcode Command Line Tools（`xcrun swiftc`）、`ffmpeg` 和 `ffprobe`。源码位于 `kit/tools/`；首次真实执行在本机编译，生成的二进制已加入 `.gitignore`。仅 dry-run 不编译、不截屏、不调用辅助功能，也不创建文件。

**运行它的进程（Codex App）需要用户本人在 macOS“系统设置 → 隐私与安全性”里，一次性授予“屏幕录制”和“辅助功能”权限。** 如系统要求允许控制 System Events，也由用户本人处理。脚本不点权限弹窗，不改 Codex 设置。已授权的浏览器或 Finder 镜头也可录制，遇到系统授权框立即停止。权限尚未处理时先用 dry-run，不用真实运行探测权限。

先由用户收起侧栏、关闭无关会话和通知，再核对项目、会话标题、输入框位置。截图守卫不能推断未列入规则的所有隐私内容。把侧栏可能出现的其他会话名写进私有镜头单的 `must_not_contain`，不要提交这些名字。

```sh
bash kit/scripts/rec-shot.sh "$YICE_WORKSPACE/shots/s4b-4.json" --dry-run
# 用户已确认窗口、授权发送且授予系统权限后：
bash kit/scripts/rec-shot.sh "$YICE_WORKSPACE/shots/s4b-4.json"
```

## 镜头单格式

完整示例：[rec-shot.example.json](rec-shot.example.json)。它改写 EP01 S4b-4 的“按旁白重新对齐。”：先确认窗口，开录，缓动点击输入框，分块输入，发送，等待“正在思考”，收尾。这个信号只表示开始处理，不代表对齐完成；如要录最终结果，将 `wait_text.text` 改为实际结果文字。

**示例所有坐标、标题、侧栏文字都是占位值，不是通用的可点击位置。** 复制到 `$YICE_WORKSPACE/shots/` 后按当次窗口填写；不要直接真实运行示例。`region` 为 `[x,y,width,height]`，使用 macOS 全局逻辑点、左上原点，Retina 不手动乘 2；可用负 x/y 表示左侧/上方显示器。一个区域应在同一显示器内。

`version` 固定为 1，`target` 每份必填：

| 字段 | 含义 |
|---|---|
| `process` | 前台进程必须完全一致；Codex App 通常为 `ChatGPT`，以当前系统实际名称为准 |
| `title_contains` | 非空字符串数组，窗口标题必须同时包含，填能够区分目标项目和会话的文字；不匹配就停 |
| `region` | 出错时保存的截图区域，应覆盖目标窗口 |
| `input.region` | 只框输入文字区域，排除按钮、模型选择器和附件，不要包含聊天历史 |
| `input.initial_text` | 开始时已在输入框里的准确内容，一般为空字符串 |
| `input.empty_text` | 输入框空时可见占位文字，默认空；按实际 OCR 填写 |
| `input.empty_texts` / `input.suggestions` | 其他已知占位文字 / 建议句的完整白名单 |
| `ui` | 可选 `region`、`question_markers`、`skip_text`（默认“跳过”）、`forbidden`；只有已知问题标记和唯一跳过按钮同时出现才处理 |
| `ocr` | 可选区域守卫列表，每项有 `region`、`must_contain` / `must_not_contain` 字符串数组 |

OCR 比对忽略空白和 NFC 差异，并使用显式字符等价表：`＠/﹫ → @`，全角/弯引号转半角引号，`，：！？（）` 转 `,:!?()`，全角空格转半角空格。**发送前用输入框复制回读逐字核对，只允许该表内替换，大小写、空格、换行和其他字符必须完全一致。** OCR 漏掉 `@` 时也须通过此回读，不能直接删掉 `@` 比较；回读后恢复原剪贴板。长文本若在输入框滚动或被遮住，OCR 不完整会停止；应缩短单次请求或扩大输入框后重新标定，不要关闭检查。

| `type` | 字段与行为 |
|---|---|
| `guard` | 总是检查目标窗口和输入框；可加 `process`、`title_contains`，或 `region` + `must_contain` / `must_not_contain` |
| `click` | `x,y`，600ms 缓动；点击发送按钮必须标 `send:true` |
| `click_text` | `region,text`，匹配唯一完整 OCR 文字框再点中心；重复就停，未出现可按 `timeout`（默认 0）等候；发送按钮同样标 `send:true` |
| `prepare_input` | 定位已知输入框，Cmd+A/Delete 清掉建议和选区，确认空白；之后不再次点击 |
| `paste` | `text`，每块最多 3 个字符，`pbcopy` 后反复检查 `pbpaste` 完全一致才 Cmd+V |
| `key` | `key`，如 `return`、`cmd+return`、`escape`、`tab`、方向键、home/end/pageup/pagedown；可加 cmd/ctrl/alt/shift；文字必须用 paste |
| `wait` | `sec`，保持画面等待 |
| `wait_text` | `region,text,timeout`，每 2 秒做本地 OCR，出现后记录 `result`，到时未出现就停止；`fresh:true` 要求发送后标志消失再出现，或数量增加，避免把上一条结果当完成 |
| `rec_start` | `region,out`，启动原生录制，确认进程存活且文件持续增长后才放行；重名自动追加 `-take02` 等编号，路径支持环境变量 |
| `rec_stop` | 停录并写入视频尺寸、时长及索引；每个 start 必须配一个 stop，不可嵌套 |

## 不能关闭的防误发检查

每次 paste 前、每个 3 字块粘贴前、输入完成后，以及每次 key/click 前，都重新核对前台进程、目标标题和输入框 OCR；因此通过键盘、文字按钮或坐标按钮发送也必须经过守卫。`return/enter`（含组合键）、文字“发送/Send”、`send:true` 都被记作发送事件，发送后预期输入重置为空。用坐标发送时须标 `send:true`，否则后续输入框检查会因预期未重置而中止。

**没有确认开录，就不能点击、输入或发送。** 镜头单校验和运行时检查均强制执行，录制途中退出也会阻止下一次输入。标题读取异常首次失败后再重试 3 次；读到明确不匹配的标题立即停。已知提问卡片只点唯一“跳过”，建议句先清空再输入；未知弹窗、卡片、输入文字或不明确的焦点会停下留图。

预期输入由镜头单初始文字和已经粘贴的内容累积而成。不能用选中覆盖、删除键或手动编辑改变它；需要编辑时拆成新的镜头单并重新确认初始文字。OCR 或标题不符会非 0 退出，保留失败截图并停止活动录制，不继续盲点。已开始的日志标为 `aborted`，不写成功索引。

失败截图默认放在 `~/Library/Application Support/yice-video/rec-shot/private/`（目录权限 700，文件 600）；可通过 `--private-dir` 改到另一个私有位置。不要把此目录、私人镜头单、截图或录屏提交到公开仓库。真实运行的临时 OCR 帧在退出时清理，只有失败帧保留。

## 产物与时间

每段 `take.mov` 旁边生成 `take.mov.rec/`，包含 `events.json`、`cursor.json`、`capture.log`。事件包括 `click`、`key`、`ui_recovery`、`input_start/end`、`send`、`result` 和启停时间。依据 `events.json` 的首尾有效事件，前后各留 0.4 秒，自动裁掉静止首尾；中间等待保留，无有效事件则保留整段。原始 take 保留，裁后视频为 `.rec/take-trimmed.mov`，`trimmed-events.json` 记录移位后的时间。视频所在目录的 `index.md` 自动追加一行：文件、实际像素、时长、关键时间点，**需模糊区域留空给中心填**。

事件是相对录制进程启动的秒数。`screencapture` 不提供首帧时间戳，`video_start_offset_seconds` 保持 `null`，不可将其称作帧级同步；需要时用可见点击手工校准。录制不加 `-C/-k/-g`，不烘焙独立光标、不录麦克风，不放大伪装原生像素。

停录直接管理原生子进程，不依赖后台 shell 的信号状态。子进程重置 SIGINT；先同时通知录制器与光标日志结束，超时依次 TERM/KILL 并报失败，不把强制结束的片段当成功。共享录制锁阻止 toolkit 录制器重叠启动；不检测其他软件手动开的录屏。

每期多段录制优先使用 [rec-demo](rec-demo.md)，由参数文件统一开录、输入、等结果和收尾。

## 本机静态 OCR 与测试

```sh
xcrun swiftc -O kit/tools/ocr/ocr.swift -o kit/tools/ocr/ocr
kit/tools/ocr/ocr "$YICE_WORKSPACE/evidence/static.png"
kit/tools/ocr/ocr "$YICE_WORKSPACE/evidence/static.png" --region 100,100,800,400
python3 -m unittest discover -s kit/tests -v
```

OCR 输入是已有图片，可选区域使用**图片像素**，输出 `{width,height,coordinate_space,results:[{text,box:[x,y,w,h],confidence}]}`；框也为原图像素、左上原点。本机执行器负责把框中心转换回屏幕逻辑点。

单元测试全部使用替身，不会移动鼠标或发送消息。真实录制、权限弹窗和操作系统焦点切换仍需在已授权的演示环境验收；dry-run 与静态 OCR 通过不代表实录通过。

实现依据：[Apple VNRecognizeTextRequest](https://developer.apple.com/documentation/vision/vnrecognizetextrequest)。

# 本机鼠标与原生录屏源码

从已有录制工具复用 `mouse.swift`、`cursorlog.swift`、`rec.sh`。不分发本机二进制；需要时用 `xcrun swiftc -O` 编译，同名可执行文件已忽略。

- `mouse click X Y [ms]`：全局逻辑点、缓动移动后点击；`move` 只移动，`pos` 读位置。
- `cursorlog seconds out.json epoch [x,y,w,h]`：60Hz 记录鼠标位置和按钮，SIGINT/SIGTERM 后写出已采样内容。记录不自申请权限。
- `bash rec.sh seconds "$YICE_WORKSPACE/evidence/take.mov" x,y,w,h`：固定时长的低层原生录制，不含镜头单防误发守卫。Codex 实操请使用 [rec-shot](../../docs/rec-shot.md)。

区域采用逻辑点，保留原生像素；`screencapture` 首帧时间未知，启动时钟不能当作已验证帧同步。录屏和光标分开保存，实际倍率需通过视频尺寸复核。低层工具不负责审核个人信息，素材留在私有工作区。

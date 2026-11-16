# 本地录屏中转器

从已经具有屏幕录制、辅助功能权限的终端启动；它不申请或更改系统权限。

    bash "$HOME/Documents/Codex/yice-youtube-video/kit/scripts/rec-bridge.sh" --timeout 3600

默认队列根目录是 ~/Library/Application Support/yice-video/rec-bridge/。
也可用 --queue-dir 指定私有目录。根目录及子目录权限为 700，结果、日志、
镜头单快照和 probe 截图权限为 600。Ctrl-C 或 TERM 会停止当前录制后退出。

先把请求写到临时文件，再原子重命名到 queue/ 内，以免读取半写入内容。
文件名只用 ASCII 字母、数字、点、下划线和连字符，建议使用递增编号，
例如 000001-ping.json。按文件名字典顺序串行执行。
结果位于 done/ 下同名文件；包括 exit_code、stdout/stderr 摘要及 artifacts。
摘要各保留末尾 8192 字节，完整日志在 private/ 下。

只接受以下四种 JSON 请求；多余字段、其他动作和任意 shell 命令均拒绝：

    {"action":"ping"}
    {"action":"probe","region":[0,0,1920,1080]}
    {"action":"rec-shot","shot":"/absolute/evidence/shot.json","dry_run":true}
    {"action":"rec-demo","params":"/absolute/evidence/params.json"}

rec-shot 的 dry_run 可省略或设为 false，等价于现有 rec-shot.sh 的 --dry-run。
镜头单及录像输出必须位于证据目录或本中转器的 private/ 目录内，
路径须为绝对路径，支持 ~ 和已定义环境变量；解析符号链接后仍检查边界。
证据目录默认复用 workspace.py 的工作区配置下 .scratch/youtube/evidence，
可在启动时以 --evidence-root 指定（允许重复）。不要把整个磁盘作为证据目录。
验证后生成私有镜头单快照，继续执行原有窗口、输入框及 OCR 守卫。

rec-demo 只有 params 路径参数；拒绝 dry_run、shell、command 等额外字段。参数文件与 output_dir 都须通过同样的路径边界检查。附加镜头不能自行指定录制输出；先完整校验，再冻结到 private/params.json，运行固定 rec-demo.sh。它内部先预演，再实录；仅预演请直接使用 `rec-demo.sh params.json --dry-run`，不要往真实队列放请求。已有 daemon 需由中心在审核后加载新版本，源文件更新不会热更新正在运行的白名单。

probe 返回前台进程、窗口标题、位置、尺寸、指定区域 OCR 与截图路径。
坐标是 macOS 屏幕点；截图只保存在私有目录，不向远程服务发送。
权限或信任确认由本人处理。

--timeout 控制每个动作的最长运行时间（默认 1800 秒），超时返回 124。
超时先通知 rec-shot 正常停录，最多等待 --stop-grace 秒（默认 35），
再终止该请求独立进程组中的残留进程。超时或强制终止的素材不可视为成功。
同时启动第二实例会被拒绝；重复请求名不重放。异常退出后的未完成请求
在重启时标记为 125/interrupted，检查已有素材后改用新请求名重试。

测试以替身 rec-shot 验证拒绝、排序、权限、单实例锁和超时停录，
不执行真实截屏、鼠标或粘贴。真实录屏要由操作员审核并启动后另行验收。

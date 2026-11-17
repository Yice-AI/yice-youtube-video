# 构建时混音

把 `audio.example.json` 复制为本期 `audio-config.json`，填入音乐和音效路径，再在 episode.json 设置 `"audio":"audio-config.json"`。也可直接放对象，或运行 `node build.mjs --audio audio-config.json`。没有 audio 配置时沿用逐章旁白。

路径相对项目根目录，支持与画面相同的 mediaRoots 别名和绝对路径。只读源素材；输出 `assets/audio/{voice-stem,music-stem,sfx-stem,premaster,master}.wav`、`audio-report.json`。index.html 自动使用一条 master 音轨，避免叠加两遍旁白。所有处理中保留旁白原时间位置，母带精确到 episode.end 的 48kHz 采样数；结尾画面和音乐可延续 2–4 秒。

`bgm:{A,B,C}` 指定三段音乐。默认 A 从 0 到第二章起点，B 到最后一章起点，C 到 episode.end；少于三章或不同分段时显式填 `segments:{A:[0,8],B:[8,30],C:[30,36]}`，三段连续且最后等于 episode.end。各源音乐应足够长，A/B 还要覆盖 0.6 秒交叠；不足时报告具体段名，不静默循环。

沿用 EP01 v7 的相对混音参数：音乐低于旁白 24dB，空隙抬高 4dB，避让起落 0.1/0.6 秒，录屏密集段额外降 3dB，交叠 0.6 秒，结尾淡出 3 秒；bgm_trim_db 为 0.6。音效普通/重点分别低 18/12dB，trim 为 −1/−2.3dB，提前 2 帧。输入响度自动测量，短音效补足 0.4 秒测量窗；已有校准数据可显式填 voice_lufs、bgm_lufs、sfx_file_lufs。旁白默认不额外提响，可显式设 voice_gain_db。

`events:[{scene:"S2-1",at:"@完成",name:"stamp"}]` 复用幕的语音锚点；at 为数值时相对该幕边界 B。省略 scene 时 at 是全片秒数。`stamp`、`counter` 默认重点音效，也可用 `key:true/false` 覆盖。文件从 sfx_dir 的 `<name>.wav`、sfx_files 的映射或事件 src 读取。

master 默认 `{lufs:-14,truepeak_ceiling_db:-1,gain_db:-0.59}`。两遍响度处理后重新测量，结果进入报告。改变音乐或音效后重新 build 即可，不需要后处理脚本替换 HTML。

## 按幕表自动配音效

在音频配置中加 `"auto_sfx":{"enabled":true,"density":1}`。build 根据 `beats.json` 的配方、转场、气泡入场点、通知卡片、数字和高亮生成事件：whoosh（非硬切转场）、tick（数字/排名）、pop（气泡/卡片）、thump（盖章/物件落定）、swipe（划线）。`density` 为 0–1，0 关闭自动事件，1 保留全部候选；中间值稳定抽稀，重建不会随机换点。

默认复用本地 `sfx_dir` 中的 `whoosh.wav`、`fast-tick.wav`、`mouse-click.wav`、`stamp.wav`、`underline.wav`。也可用 `sfx_files` 或 `auto_sfx.bank.<音效名>:{src,sourceUrl,creator,license,licenseUrl}` 指向现有或已下载的 CC0 音效；工具不联网、不把来源不明的本地音效称作 CC0。用到的文件复制入 `assets/audio/sfx/` 并登记许可账本。

普通/重点仍分别相对旁白 −18/−12dB（以及上述 trim）；thump 为重点，其他普通。自动层开启后，与手填事件合并，按文件哈希去重，同一声音跨镜头也至少间隔 1 秒。`auto-sfx-report.json` 列出保留/舍弃的事件、密度、素材和电平；实际输入响度与增益仍由 `audio-report.json` 核验。

需要精确贴动作时，在某幕写 `"sfx":[{"name":"thump","at":0.6}]`，会取代该幕自动推断（at 相对该幕 composition 开始）；`"sfx":false` 禁用该幕。普通音频配置里的手填 events 仍按边界 B/语音锚点解释。无旁白样片可显式设置 `voice_lufs` 作为混音参考值，并用空的 voice manifest 与明确的 A/B/C 分段；不要把 BGM 假作旁白再次叠加。

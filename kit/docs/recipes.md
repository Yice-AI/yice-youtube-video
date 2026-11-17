# 15 个配方

依据随包的 `_src/*.txt`、对应 `.js` 和 `rec-zoom.html`，以执行代码为准。示例是单幕的 `spec`；把它放到 beats 的 scene.spec，并按 media 一栏配素材。时序规则见 [beats-schema.md](beats-schema.md)。

共用约定：x/y/w/h 为 1920×1080 画布像素，rot 为角度，at 支持口播锚点。**props 数组项**为 `{m,x,y,w,z,rot,at}`，m 从 0 开始，图片高度自动；**label** 为 `{text,sub,at,side:"right",top,size}`。不是每个配方都支持 label 的全部字段，下文注明。各配方自动加入幕背景、章节页眉和时间信息，rec-zoom 全屏素材除外。不要把标题正文写成 HTML；这些配方继承旧版 innerHTML 组合，仅使用可信本地剧本。

## 1. chapter — 章节路标

不需要 media。字段：`no`、`title`、`sub` 字符串，`list:[{no,title}]`、`current`（从 0 开始的高亮索引）。动画时刻由配方固定；不支持自定义 title.at。

```json
{"no":"01","title":"克隆声音","sub":"先准备一段录音","list":[{"no":"01","title":"声音"},{"no":"02","title":"配图"}],"current":0}
```

## 2. checklist — 准备项和行动清单

不强制 media；`sides` 中每项的 m 要有对应图片。字段：`card:{x,y,w,rot}`、`tone:"sticky"`、`kicker`、`title`、`items:[{text,sub,at}]`、`sides`（共用 props）。代码读取 **sides**，旧 txt 的单数 side 不生效。

`checked:[0]` 只勾第一个条目（零起算）；`checked:[]` 全不勾；省略则沿用全部勾选。条目文字和下划线照常显示。

```json
{"title":"准备三样东西","items":[{"text":"一段自己的录音","sub":"安静环境录制","at":0.8},{"text":"一个项目文件夹","at":2.0}]}
```

## 3. desk — 多素材桌面摆放

素材按 items[].m 的编号准备。字段：`items` 各项 `{kind,m,text,sub,x,y,w,h,rot,at,z,round,tape,size,font}`；kind 可用 `prop`、`photo`、`screen`、`card`、`label`，前三类使用图片，后两类用文字；font 为 `song` 时用宋体。prop 用 w 和 round，photo/screen 用 w/h；card 尺寸由 CSS 决定，不读条目的 w/h。`keys:[{at,x,y,s,d,ease}]` 控制画布镜头，`title` 用共用 label。

```json
{"items":[{"kind":"prop","m":0,"x":900,"y":180,"w":700,"rot":-5,"at":0.2},{"kind":"card","text":"本地生成","sub":"素材留在电脑里","x":160,"y":300,"at":0.6}],"title":{"text":"一次说清需求","at":1}}
```

## 4. doc-zoom — 文档截图聚焦

m0 为截图；可用候选占位图，回退时显示文档骨架。字段：`page:{x,y,w,rot}`、`aspect`（高/宽）、`bar:false` 去掉浏览器栏、`url` 为栏中文字、`ph` 显式占位；`keys:[{at,x,y,z,d}]` 中 x/y 为截图百分比；`hls:[{x,y,w,h,at,under}]`、`circle:{x,y,w,h,at}` 也是截图百分比；`stamp:{text,x,y,size,at}` 的 x/y 同样按截图百分比；`title:{text,sub,side,top,at}`。

```json
{"page":{"x":220,"y":100,"w":1480,"rot":0},"aspect":0.56,"keys":[{"at":0,"x":50,"y":50,"z":1},{"at":1.2,"x":38,"y":28,"z":1.8,"d":1.1}],"hls":[{"x":18,"y":25,"w":43,"h":9,"at":1.8}]}
```

## 5. editor — 代码逐行出现

无需 media。字段：`win:{x,y,w,h}`、`file`、`lines:[string]`、`at`（开始显示行）、`hl:{line,at}`（从 0 开始的行号）、`title`（共用 label）。每行间隔按幕长与行数自动计算，上限 0.22 秒；高亮时镜头自动接近对应行。

```json
{"file":"episode.json","lines":["{","  \"id\": \"ep02\"","}"],"at":0.3,"hl":{"line":1,"at":1.2},"title":{"text":"配置新一期","at":0.6}}
```

## 6. ledger — 费用、清单表和输入输出

无需主素材；`sides` 可引用图片。字段：`card:{x,y,w,rot}`、`mode:"io"`（竖向输入输出）、`kicker`、`title`、`cols:[左列,右列]`、`rows:[{k,v,sub,at}]`、`total:{k,v,at}`、`stamp:{text,at}`、`stampY`、`sides`（props）。io 模式忽略列头并在行间显示箭头。

```json
{"kicker":"本期成本","title":"制作清单","cols":["项目","方式"],"rows":[{"k":"配音","v":"本地","at":0.6},{"k":"剪辑","v":"代码","at":1.5}],"stamp":{"text":"可复用","at":2.4}}
```

## 7. num-split — 两个数字或结论比较

无需主素材，extras 可用图片。`left`、`right` 各含 `{kicker,label,sub,at,size,text}`；给 text 显示原文，否则读 `{from,num,dec,pre,suf,unit}` 做计数。`rel:{text,at}` 是关系符；`bar:{a,b,max,unit,at}` 是刻度条（max>0）；`circle:{side:"right",at}` 圈对应大字；`note:{text,at}`、`extras`（props）。左右卡片布局固定。

```json
{"left":{"kicker":"以前","num":60,"unit":"分钟","label":"手工整理","at":0.4},"right":{"kicker":"现在","num":10,"unit":"分钟","label":"模板复用","at":1.4},"rel":{"text":"→","at":1},"bar":{"a":10,"b":60,"max":70,"unit":"分钟","at":2}}
```

## 8. photo-word — 实物道具配一个重点词

**m0 必需**，通常是透明道具。m1 可作夹在旁边的小照片；clip.text 存在时改为纸条。字段：`obj:{x,y,w,rot,at,photo,static}`（photo 使它带照片外框）、`word:{text,at,x,y,size,color,static}`、`notes:[{text,at,ox,oy,lx,ly}]`（标注原点/标签坐标）、`push:{at,s,x,y,d}`、`clip:{text,sub,x,y,w,rot,at}`、`extras`（props）、`texts:[{text,x,y,size,rot,color,at}]`。

独立红圈：`circle:{x:1000,y:400,w:480,h:180,at:"@重点",stroke:6,d:0.6}`，坐标为舞台像素，跟随相机；默认印章红，可用 color 覆盖，不要求 notes。

```json
{"obj":{"x":1000,"y":180,"w":750,"rot":-3,"at":0.1},"word":{"text":"声音","x":160,"y":340,"size":230,"at":"@声音"},"push":{"at":1.2,"s":1.04,"x":1100,"y":470,"d":1.6}}
```

## 9. prompt — 需求原文输入演示

不需要 media；是示意 UI。字段：`kicker`、`text`、`at`、`rate`（每秒字数，默认 14）、`marks:[{phrase,at}]`、`send:{at}`、`title`（共用 label）、`ph`（提示文字，默认“示意 · 待录屏替换”）。演示壳中的模型名来自既有配方，不读取真实聊天，也不支持用 ph 切换真实截图。

```json
{"kicker":"把要求说清楚","text":"请用这段录音生成旁白，保留自然停顿。","at":0.3,"rate":14,"marks":[{"phrase":"自然停顿","at":2.4}],"send":{"at":3}}
```

## 10. rec-zoom — 真实录屏跟随重点

**m0 必需**（录屏视频，也兼容截图），通过 media.start/rate 设置入点和倍速。`frame:"device"` 使用设备框，其他值全屏；`box:{x,y,w,h}` 只作用于设备框；`keys:[{at,x,y,z,d,ease}]` 中 x/y 为素材百分比；`dof:false` 关闭聚焦模糊；`hls:[{x,y,w,h,at,under}]`、`circle:{x,y,w,h,at}`、`stamp:{text,x,y,size,at}` 位置按素材百分比；`title:{text,sub,side,top,at}`（不读 size）；`tag:{text,side,at}`；`props` 为画面固定位置的共用道具数组。该配方仅有 HTML 源，不在 wrap.py 的 14 个条目中。

```json
{"frame":"full","keys":[{"at":0,"x":50,"y":50,"z":1},{"at":1,"x":59,"y":15,"z":2.1,"d":1.2}],"title":{"text":"用中文说需求","at":0.6},"tag":{"text":"真实操作","at":0.4}}
```

## 11. rope-map — 概念关系连线

不需要主素材；extras 可引用图片。`center:{text,sub,x,y,cw}`、`nodes:[{text,sub,x,y,at}]`、`extras`（props）。中心与节点是文字卡片，连线按位置自动生成；cw 只影响中心连线定位，卡片宽度自动。**代码不读取 m0 作为中心图片**，旧 txt 的图片描述不作为接口。

```json
{"center":{"text":"一期视频","sub":"制作流程","x":720,"y":380,"cw":480},"nodes":[{"text":"旁白","x":180,"y":180,"at":0.6},{"text":"配图","x":1360,"y":180,"at":1.2},{"text":"剪辑","x":1360,"y":720,"at":1.8}]}
```

## 12. single-line — 一句结论

不强制 media；有 m0 可显示旁边照片，clip.text 存在则显示纸条。字段：`text`、`at`、`x`、`y`、`size`、`sub:{text,at}`；`mark:"circle"` 圈、`"none"` 不标记，其他值为下划线；`markAt`、`markColor`；`clip:{text,sub,x,y,w,rot,at}`；`extras`（props）。

```json
{"text":"先把想法说清楚","at":0.3,"size":100,"mark":"circle","markAt":1.2,"sub":{"text":"再交给工具执行","at":1.8}}
```

## 13. step-ruler — 流程进度尺

无需 media。字段：`word:{text,at}`、`kicker`、`steps:[string]`、`active`（从 0 开始）、`at`、`done:[index]`、`ticks:[{i,at}]`（按时点勾选）、`readout`。步骤数量决定刻度布局。

```json
{"kicker":"这一期怎么做","word":{"text":"三步","at":0.2},"steps":["声音","配图","剪辑"],"active":1,"done":[0],"ticks":[{"i":1,"at":2}],"readout":"02 / 03"}
```

## 14. stock-shot — 素材全屏或印刷照片

**m0 必需**。`frame:"print"` 或主素材发生候选回退时以印刷照片方式显示，其余全屏；`title:{text,at,side}`、`sub:{text,at}`、`credit`；`kb:{from:{s,x,y},to:{s,x,y}}` 控制从头到尾的推拉。x/y 是画布像素。旧 txt 提到的 phLabel 未被 JS 使用。

```json
{"frame":"print","title":{"text":"本地制作","at":0.5},"sub":{"text":"素材留在自己的电脑","at":1.3},"credit":"来源：本人拍摄","kb":{"from":{"s":1,"x":960,"y":540},"to":{"s":1.08,"x":1000,"y":520}}}
```

## 15. strike-slips — 划去误解，留下结论

无需主素材，props 可用图片。字段：`lead:{text,at}`、`slips:[{text,at,strike}]`、`step`（纸条纵向间距，默认 230）、`keep:{text,sub,at}`、`short:{text,n,at,strike}`、`props`（共用道具）。strike 是画线时间字段，也支持口播锚点。

便签合并：`merge:{at:"@合并",x:820,y:600,d:0.6}` 配合 keep，已有 slips 移到同一位置并收起，留下 keep 的结论。keep.at 省略时跟随汇合结束；明确填写时按指定锚点。此扩展针对 slips，不改变 short 模式。

```json
{"lead":{"text":"不用从零开始","at":0.2},"slips":[{"text":"每期重搭工具","at":0.6,"strike":1.2},{"text":"手工对齐每句话","at":1.6,"strike":2.2}],"keep":{"text":"复用模板","sub":"把精力放在内容上","at":2.8}}
```

## 共用道具压字和盖印

各配方已有的 props/extras/sides 列表可选 `press` 和 `stamp`。例如：

```json
{"m":1,"x":1200,"y":180,"w":260,"at":0.2,"press":{"at":1.4,"x":1000,"y":400,"d":0.24,"target":".word"},"stamp":{"text":"完成","x":1040,"y":580,"size":56}}
```

press 的 x/y 是道具最终左上角，target 是本幕相机内的文字选择器，落下时文字短暂受压后恢复；省略 target 只移动道具。目标在本幕所有内容建好后解析，缺失会报错。stamp 复用现有印章组件，at 省略时跟随压字接触点，也可独立指定。动画均写入本幕时间线，可向前、向后定位。

## 维护配方

14 个配方由 `_src/名称.txt/.css/.js` 和 wrap.py 生成 HTML；rec-zoom 直接维护 HTML。复制版本的既有细节应保留，修改后只重新生成自己改动的配方并检查 diff，避免覆盖已有 HTML 手工修正。注册组件位于 compositions/components，与这 15 个叙事配方分别管理；原工程一条指向缺失文件的 freeze-frame-dressing 登记没有带入本包，8 个实际存在的组件已保留。

## 首批视觉词汇（A1–G2）

规格表逐项共17个名称，全部实现。新配方用 `recipe + props`；旧配方的 `spec` 接口保留。共用三舞台、三功能色与Yice三字体，不使用registry原始配色。媒体槽支持路径、`{src,start,rate,sourceType}` 或已有 `media` 的 `{m:编号}`，经原有视频预处理后进入动画。

下列中文例子也保存在模板 `vocab-examples.json`；示例数据只演示接口，成片数字必须换成实测。坐标采用1920×1080画布，`at`支持数字及口播锚点。来源与改编范围见 [原件说明](vocabulary-origins.md)。

### news-card

首批配方通用 `props.showTitle:false` 可关闭左上标题，来源仍保留；金句和轮换词本身没有左上标题。单期至少 40% 镜头无左上标题，同一版式骨架最多连续 3 镜。标题与来源在旧镜头转场前退场，新镜头随后进入。

shot为网页静帧或滚动片段；source/date必填。highlight为框数组{x,y,w,h,at}；zoom为局部框，固定1.6倍，带蓝墨边框与引线。两角胶带，截图内裁切。来源日期固定在画面右上，默认注明采集日期。

```json
{"recipe": "news-card", "props": {"shot": "@assets/page.png", "source": "Wikipedia", "date": "2026-11-17", "headline": "原文作证", "highlight": [{"x": 486, "y": 93, "w": 249, "h": 32}], "zoom": {"x": 440, "y": 70, "w": 370, "h": 230}}}
```

### social-post

头像、姓名和handle默认隐去；仅公开机构或官方账号显式publicAccount:true才显示。可传avatar/image媒体槽。metrics支持likes/reposts/comments，仅传有出处的数字；省略即不显示。

```json
{"recipe": "social-post", "props": {"name": "需要隐去的姓名", "handle": "@private", "text": "把一批图片压到每张500KB以内，压完打包下载。", "time": "需求原文", "metrics": {}}}
```

### chat-bubble

turns每项role为user/ai，text为原文，可用at控制逐条时间。typing:true先显示0.6秒三点。短镜头宜2条短句。

```json
{"recipe": "chat-bubble", "props": {"turns": [{"role": "user", "text": "把30张图片压缩后打包。", "at": 0}, {"role": "ai", "text": "每张控制在500KB以内。", "at": 0.9}], "typing": true}}
```

### device-stage

chrome支持browser/window/phone；url只是显示文本，可用已打码的名称。swap为第二媒体，swapAt控制横推时间。灰色三点，不使用系统彩色灯。

```json
{"recipe": "device-stage", "props": {"media": "@assets/screen.mp4", "chrome": "browser", "url": "本地图片工具", "swap": "@assets/second.mp4"}}
```

### laptop-3d

angle范围−12至12度；dolly为0–0.15的全镜头推近比例。屏幕内播放media，保持固定视角，不旋转绕圈。

```json
{"recipe": "laptop-3d", "props": {"media": "@assets/screen.mp4", "angle": -7, "dolly": 0.08}}
```

### filmed-screen

moire与handheld范围0–1，默认0.3；轻透视与确定性扫描线/手持运动，不靠模糊制造质感。

```json
{"recipe": "filmed-screen", "props": {"media": "@assets/screen.mp4", "moire": 0.3, "handheld": 0.3}}
```

### cursor-zoom

cursorLog支持数组或JSON文件路径；文件为数组或{points:[...]}。每点{t,x,y,click?}：镜头局部秒、1920×1080坐标。原日志需按实际裁切/缩放换算。平滑系数0.12，以60Hz固定采样保证随机seek一致；zoom范围1.4–2.2。

```json
{"recipe": "cursor-zoom", "props": {"media": "@assets/screen.mp4", "cursorLog": [{"t": 0, "x": 500, "y": 300}, {"t": 0.8, "x": 1100, "y": 600, "click": true}, {"t": 2, "x": 1400, "y": 700}], "zoom": 1.7}}
```

### terminal-run

lines每项{cmd:true,text}或{out:true,text}；speed是行速倍率。输出默认60ms/行，字体30px；终端随行数自适应，至少6行高。success:false隐藏成功章；红章盖在纸色小签上，炭色舞台也达到4.5:1对比度。不要把演示命令冒充实际执行记录。

```json
{"recipe": "terminal-run", "props": {"lines": [{"cmd": true, "text": "python compress.py"}, {"out": true, "text": "30张图片已处理"}, {"out": true, "text": "输出已打包"}], "speed": 1, "stage": "charcoal"}}
```

### code-diff

before/after为换行文本，lang为语言/参数标签；红色删除底18%、蓝墨新增底14%，行号等宽。

```json
{"recipe": "code-diff", "props": {"before": "上限 = 1000\n水印大小 = 48", "after": "上限 = 500\n水印大小 = 24", "lang": "参数对比"}}
```

### bar-compare

items为{label,value,unit}，最多6根；highlight是从0开始的索引；value非负，source可注明实测来源。柱宽140px，墨柱为85%墨色叠纸纤维；两根柱时自动以原始数值计算蓝墨测量线上的变化百分比。

```json
{"recipe": "bar-compare", "props": {"items": [{"label": "原始素材", "value": 132, "unit": "MB"}, {"label": "压缩后", "value": 14.8, "unit": "MB"}], "highlight": 1}}
```

### progress-ring

value/from为0–100百分比，label必填；蓝墨环与宋体160px中心数，完成时盖红章。

```json
{"recipe": "progress-ring", "props": {"value": 88.79, "label": "体积减少", "from": 0}}
```

### rank-race

frames至少2帧，每帧{t,items,label?}，t严格递增；允许榜单成员进出，同一帧label不可重复，items非负数。条宽按当前帧最大值缩放并从0生长，卡片高度随可见条数自适应。title/source必填，无来源或单帧拒绝构建；只有多次实测排名才用此配方，静态对比用bar-compare，不编造热度。

```json
{"recipe": "rank-race", "props": {"frames": [{"t": 0, "label": "第1次观察", "items": [{"label": "照片一", "value": 90, "unit": "%"}, {"label": "照片二", "value": 80, "unit": "%"}]}, {"t": 0.65, "label": "第2次观察", "items": [{"label": "照片三", "value": 95, "unit": "%"}, {"label": "照片一", "value": 90, "unit": "%"}]}, {"t": 1.2, "label": "第3次观察", "items": [{"label": "照片三", "value": 95, "unit": "%"}, {"label": "照片四", "value": 93, "unit": "%"}]}], "title": "样本逐步加入榜单", "source": "接口示例数据，成片须换实测"}}
```

### concept-hub

center为中心文字，nodes最多6个，可为字符串或{text}；order为从0开始的节点顺序。蓝墨细线逐个点亮，当前节点用荧光。

```json
{"recipe": "concept-hub", "props": {"center": "图片工具", "nodes": ["压缩", "水印", "打包", "本地处理"], "order": [0, 1, 2, 3]}}
```

### photo-path

images为媒体槽数组，2–60张；focus为从0开始的索引，focusAt可选。沿path-2波浪运动；聚焦图占画面宽45%，其余压暗40%。

```json
{"recipe": "photo-path", "props": {"images": ["@assets/photo-01.jpg", "@assets/photo-02.jpg", "@assets/photo-03.jpg"], "focus": 1}}
```

### hand-mark

kind支持arrow/circle/underline/box；target是画布框，label可选；color只支持stamp/blue-ink。media可选背景；笔画0.5秒，5px线宽，0.2强度微抖。

```json
{"recipe": "hand-mark", "props": {"kind": "circle", "target": {"x": 700, "y": 410, "w": 500, "h": 180}, "label": "看这里", "color": "blue-ink", "media": "@assets/page.png"}}
```

### word-swap

prefix固定前缀，words顺序替换；interval至少0.35秒，竖向换词0.35秒。宋体120px，变化词为荧光底。

```json
{"recipe": "word-swap", "props": {"prefix": "一句话，", "words": ["压图片", "加水印", "打包"], "interval": 0.8}}
```

### headline-slam

text最多10字，stage推荐charcoal；每章最多一次。逐字砸入，位移回弹2px。sub可放等宽小签。

```json
{"recipe": "headline-slam", "props": {"text": "工具自己做", "stage": "charcoal"}}
```

### 转场包与质感层

`enter`可用directional-wipe、cinematic-zoom、grid-pixelate-wipe、halftone-dissolve、flash-through-white、chromatic-aberration-wipe，统一0.5秒；最后一种每期最多一次，改为红章/蓝墨边缘分离，不保留RGB霓虹。

任何镜头都可加`layers`，不增加配方计数；纹理/扫光不冒充信息叠加层，通知卡才作为信息层统计。

```json
{"enter":"directional-wipe","layers":[{"kind":"grain-overlay","strength":0.06},{"kind":"light-sweep-pass","at":0.3},{"kind":"notification-stack","items":[{"text":"已下载","at":1.0},{"text":"已打包","at":1.4}]}]}
```

第二批真实素材配方见 [recipes-second-batch.md](recipes-second-batch.md)，人物库与双档规则见 [people.md](people.md)。

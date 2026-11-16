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

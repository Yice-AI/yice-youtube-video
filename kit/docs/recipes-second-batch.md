# 第二批真实素材配方

全部继承 frame.md 的纸张/炭黑舞台与字体。默认硬切；仅在表达关系时配置转场。

| 配方或参数 | 入口与默认行为 |
|---|---|
| stock-shot / laptop-3d `push` | `{from:1,to:1.17,duration:3}`，按手法表量化参数，duration 可设 6；线性推近 |
| action-montage | `clips:[{src,start,duration}]`，4–6 条真实视频，每条 0.5–0.9 秒，硬切 |
| news-card `focusRect` / `cutZoom` | 素材像素裁切 `{x,y,w,h}`；`cutZoom:[{at,scale,rect?}]` 跳切到关键词，阅读区域仍须满足 28px |
| quote-fragments | `text,keywords,image,keywordAt,photoAt`；整句 0.4–0.7 秒淡去，关键词留在后续照片上 |
| visual-contrast | `left,right,leftLabel,rightLabel`；默认主物件高 72%，另一物件 54%，可配置 |
| stock-shot / device-stage `overlays` | `{media?,text?,x,y,width:0.42,height:420,at}` 叠真实证据/评论卡；width 是画幅比例，height 是像素 |
| hand-mark `labelHeight` | 0.06–0.14 画高的大标注 |
| cutout-stack | `items,title,stagger`；每 0.15–0.25 秒飞入，最多 30 张，支持透明主体与整张照片剪报混用 |
| paper-break | `mode:zip|tear|stamp`；物件发生可见变化，`changeDuration` 为 0.8–1.2 秒 |
| brand-hero | `logo,line,background?`；官方 logo 高度 30–45%，一行判断或数字，logo 用 media-use 冻结官方原件 |
| sticker-text | `text,ink:highlight|stamp|blue,stroke:8..12,angle:-4..4`；Yice Sans Heavy 900，0.15 秒回弹 |
| reaction-cutout | `person` 或 `personRef` + 贴纸评论；见 people.md |

全局 `autoReframe` 根据前景时间轴的可见变化间隙安排小幅跳切；不把装饰层当作有效变化。可用 `reframe:false` 关闭，最终是否静止仍由渲染视频测量。每期 sticker-text 与带评论的 reaction-cutout 合计最多 4 次。

`collect-entity.sh --evidence evidence.json` 接受 App 排名、融资/股价、官方跑分：`[{"type":"app-ranking|finance|benchmark","url":"https://…","claim":"要证明什么","values":[{"label":"项目","value":77.3}]}]`。网页截图可引用为 news-card；数值须人工核实，bar-compare 用 `props.entity:{manifest,item}` 引入，不从截图猜数，不跨测试口径混用。拒绝访问的网页如实跳过。

两条新门：真实视频/照片/抠图/截图累计占比 ≥30%；画面变化率 ≥0.45 次/秒。变化测量统一为 24fps、256×144 灰度、像素亮度差严格 >32 且面积 ≥12%，候选峰在 ±0.25 秒内按强度抑制。真实占比依据实际可用素材、账本和配方主承载前景按时长分类；AI 图、logo 和纯文字不算真实照片，视觉复核仍需确认主体。比较报告同时列不含截图与含截图两种占比。

字体现用 Adobe Source Han Sans CN Heavy，官方文件 `https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/SubsetOTF/CN/SourceHanSansCN-Heavy.otf`，随现有 Source Han Sans 的 OFL 许可；映射为 `Yice Sans` weight 900。

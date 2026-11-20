# 七种制片工具的八个镜头

[完整镜头参数](../template/demos/tool-demos.example.json)对应 35.5 秒、1920×1080、30 fps 的无旁白示范。项目中的时间单位为秒，坐标按 1920×1080 填写。请把模板里的相对素材路径换成本期实际产物，并为每个场景填写对应的句号或时间段。

| 镜头 | 时间 | 素材和装配 |
| --- | --- | --- |
| D1 | 0–4.5 | 在访达实录中截取两次按大小排序的动作。用 `cursor-zoom` 放大排序列。把目录名遮罩放在录屏图层内，让它随推镜移动。 |
| D2 | 4.5–9 | 抓取 Python 官方 pathlib 文档，用 `news-card` 高亮页面标题，局部放大类图，保留来源与采集日期。 |
| D3 | 9–13.5 | 选两段 Pexels 摄影机实拍，从镜身和机位操作中截出五段 0.9 秒动作，用 `action-montage` 交替剪接。作者和许可见素材账本。 |
| D4 | 13.5–17.5 | 用 image2 生成两张暗调案板摄影图，选木纹、食材和负空间最清楚的一张，用 `footage-bigword` 叠“真凶”和“案板上只有两样菜”。 |
| D5 | 17.5–22 | 向 `blueprint-diagram` 填四个节点和三条有向边。节点依次说明判需求、造画面、装配和质检。 |
| D6 | 22–26 | 用 Modal LTX-2 生成卡尺滑过胶片的横版微距镜头，用 `cinematic-broll` 装配。97 帧按 24 fps 生成，取其中 4 秒。 |
| D7a | 26–30.5 | 从 `annotated-shots.json` 读取两组开头 60 秒的逐镜时长与素材类别。用 `shot-wall` 的色带绘制，数字来自实际标注。 |
| D7b | 30.5–35.5 | 从两期自有成片各截一个片段，放入 `split-compare` 的左右 16:9 视窗，依次聚焦左窗与右窗，再回到同屏倒数和双印章。 |

在技能仓库根目录执行以下命令。`DEMO` 指向本期证据工程，`FINDER` 指向真实访达录屏，`YICE_MODAL_GUARD_FILE` 指向已核实免费额度上限的本机记录。

```bash
ffmpeg -ss 4.8 -i "$FINDER" -t 6 -an -vf scale=1920:1080,fps=30 -c:v libx264 "$DEMO/assets/local/D1-finder.mp4"
bash kit/scripts/produce-asset.sh --project "$DEMO" --scene D2 --kind web-capture --id python-pathlib --duration 6 --url https://docs.python.org/3/library/pathlib.html
bash kit/scripts/produce-asset.sh --project "$DEMO" --scene D3 --kind stock-footage --source pexels --id optical-workbench --query 'filmmaker adjusts camera lens hands' --count 2 --stock-budget 4
node kit/scripts/find-media.mjs --download "$DEMO/assets/stock/optical-workbench/candidates.json" --select "$SELECTED_ID" --project "$DEMO" --scene D3 --max-mib 75
for take in A B; do
  bash kit/scripts/produce-asset.sh --project "$DEMO" --scene D4 --kind metaphor-image --id "board-$take" --output "assets/local/D4-$take.png" --reserve-image 0.20 --cost 0.20 --prompt 'Photorealistic walnut cutting board, a golden onion and red tomato under one tungsten spotlight, deep shadows, negative space on the left. No text.'
done
bash kit/scripts/produce-asset.sh --project "$DEMO" --scene D6 --kind motion-video --id film-caliper --duration 4 --width 1024 --height 576 --quality fast --output assets/local/D6-film.mp4 --prompt 'A brushed steel vernier caliper slides across film perforations on a dark editing bench. Warm tungsten light, macro tracking shot, shallow optical depth of field.'
```

图库下载后把返回的相对路径填入 D3。image2 的每张 0.20 美元是预算预留值，供应商账单以实际用量为准。D5、D7a 和 D7b 的完整节点、真实数据行、聚焦时间与印章参数见上方 JSON。复用 D7a 时，用本期标注的 duration_s 逐镜替换 d，将实拍视频、照片、抠像归为 real，屏幕截图归为 screen，其余归为 graphic。

```bash
cd "$DEMO"
npm run build
DO_NOT_TRACK=1 npm run render -- --fps 30 --output renders/tool-demos-reel.mp4
DO_NOT_TRACK=1 npm run check -- --rendered renders/tool-demos-reel.mp4
```

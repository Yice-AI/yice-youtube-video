"""本地系统抠图 + 可复现的剪报处理；账本复用素材入口。"""
import argparse
import hashlib
import json
import math
import random
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def validate_subject_mask(alpha):
    mask = alpha.point(lambda pixel: 255 if pixel > 24 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("抠图未产生有效透明背景，不能当作成功")
    left,top,right,bottom = bbox
    borders = sum((left==0,top==0,right==mask.width,bottom==mask.height))
    coverage = mask.histogram()[255] / ((right-left)*(bottom-top))
    if borders>=3 or (borders>=2 and coverage>.75):
        raise ValueError("抠图未分离出独立主体（触碰多条画幅边界或含大面积背景底板）")


def paper_cutout(image, angle=2.0, border=12, seed=0, *, allow_edge_bleed=False):
    if not math.isfinite(angle) or abs(angle) > 3:
        raise ValueError("剪报倾斜须在 −3° 到 +3° 之间")
    if not isinstance(border, int) or not 1 <= border <= 64:
        raise ValueError("白边须为 1–64 像素")
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] >= 250 or alpha.getbbox() is None:
        raise ValueError("抠图未产生有效透明背景，不能当作成功")
    if not allow_edge_bleed:
        validate_subject_mask(alpha)
    image = image.crop(alpha.getbbox())
    pad = border * 4
    canvas = Image.new("RGBA", (image.width + pad * 2, image.height + pad * 2))
    canvas.alpha_composite(image, (pad, pad))
    alpha = canvas.getchannel("A")
    silhouette = alpha.filter(ImageFilter.MaxFilter(border * 2 + 1))
    rng = random.Random(seed)
    # 纸纹只在白边中；保留主体颜色和细节。
    grain = Image.frombytes("L", canvas.size, bytes(rng.randrange(244, 256) for _ in range(canvas.width * canvas.height)))
    paper = Image.merge("RGBA", (grain, grain, grain, silhouette))
    paper.alpha_composite(canvas)
    paper = paper.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    shadow_alpha = paper.getchannel("A").filter(ImageFilter.GaussianBlur(border * 0.65)).point(lambda x: round(x * 0.24))
    shadow = Image.new("RGBA", paper.size, (20, 19, 17, 0))
    shadow.putalpha(shadow_alpha)
    result = Image.new("RGBA", (paper.width + border * 4, paper.height + border * 4))
    result.alpha_composite(shadow, (border * 2, border * 2 + border))
    result.alpha_composite(paper, (border * 2, border * 2))
    return result


def vision_extract(source, target):
    result = subprocess.run(["xcrun", "swift", str(Path(__file__).with_name("vision-cutout.swift")), str(source), str(target)], capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("本地抠图失败：" + result.stderr[-1800:])
    return json.loads(result.stdout.strip().splitlines()[-1])


def cutout(source, project, asset_id, provenance, *, scene="", angle=2.0, crop=None,
           allow_edge_bleed=False, backend=vision_extract):
    source, project = Path(source).resolve(), Path(project).resolve()
    if not asset_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in asset_id):
        raise ValueError("id 只支持字母、数字、短横线和下划线")
    for key in ["sourceUrl", "licenseUrl", "license"]:
        if not provenance.get(key):
            raise ValueError("素材来源缺少 " + key)
    if not math.isfinite(angle) or abs(angle) > 3:
        raise ValueError("剪报倾斜须在 −3° 到 +3° 之间")
    output = project / "assets/cutouts" / asset_id
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    if crop:
        x, y, w, h = crop
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > image.width or y + h > image.height:
            raise ValueError("裁切范围必须在原图内")
        image = image.crop((x, y, x + w, y + h))
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        prepared, raw = Path(tmp) / "input.png", Path(tmp) / "alpha.png"
        image.save(prepared)
        if image.getchannel("A").getextrema()[0] < 250:
            image.save(raw)
            info = {"backend": "existing-alpha", "instances": None}
        else:
            info = backend(prepared, raw)
        with Image.open(raw) as opened:
            transparent = opened.convert("RGBA")
        decorated = paper_cutout(transparent, angle=angle, seed=int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16),
                                 allow_edge_bleed=allow_edge_bleed)
        transparent.save(output / "transparent.png")
        decorated.save(output / "paper.png")
    files = [{"path": str((output / name).relative_to(project)), "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()} for name in ["transparent.png", "paper.png"]]
    entry = {**provenance, "id": asset_id, "kind": "cutout", "scene": scene, "capturedAt": datetime.now(timezone.utc).isoformat(), "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(), "sourcePath": str(source), "files": files, "path": files[1]["path"], "sha256": files[1]["sha256"], "processing": {**info, "crop": crop, "maxEdge": 1600, "angleDegrees": angle, "whiteBorderPx": 12, "paperGrain": "244–255, border only", "shadowOpacity": 0.24}, "modified": True, "attribution": provenance.get("attribution") or f"{provenance.get('creator') or '作者见来源页'} · {provenance['sourceUrl']} · {provenance['license']} · 已抠图、剪报处理"}
    entry["attribution"] = (provenance.get("attribution") or f"{provenance.get('creator') or '作者见来源页'} · {provenance['sourceUrl']} · {provenance['license']}") + " · 已抠图、剪报处理"
    entry.update(mime="image/png", type="image", width=decorated.width, height=decorated.height, bytes=(output / "paper.png").stat().st_size)
    # 与网页、开放素材共用原子账本写入，保留其余素材行。
    module = Path(__file__).with_name("capture-web.mjs").as_uri()
    subprocess.run(["node", "--input-type=module", "-e", "import fs from 'node:fs'; const {recordAsset}=await import(process.argv[1]);const d=JSON.parse(fs.readFileSync(0,'utf8'));recordAsset(d.project,d.entry);", module], input=json.dumps({"project": str(project), "entry": entry}), text=True, check=True)
    (output / "cutout.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--project", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--source-json", required=True, help="含 sourceUrl/licenseUrl/license/creator 的来源记录")
    parser.add_argument("--scene", default="")
    parser.add_argument("--angle", type=float, default=2.0)
    parser.add_argument("--crop", help="原图坐标 x,y,width,height")
    parser.add_argument("--allow-edge-bleed", action="store_true", help="主体有意出画时允许保留画幅边缘")
    args = parser.parse_args()
    crop = tuple(map(int, args.crop.split(","))) if args.crop else None
    if crop and len(crop) != 4:
        parser.error("crop 需要四个整数")
    result = cutout(args.input, args.project, args.id, json.loads(Path(args.source_json).read_text()),
                    scene=args.scene, angle=args.angle, crop=crop, allow_edge_bleed=args.allow_edge_bleed)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

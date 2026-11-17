import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

SPEC = importlib.util.spec_from_file_location("cutout", Path(__file__).parents[1] / "scripts/cutout.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
SOURCE = {"sourceUrl": "https://commons.wikimedia.org/wiki/File:Sample.png", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/", "license": "CC BY-SA 4.0", "creator": "Example"}


def alpha_image():
    image = Image.new("RGBA", (160, 120))
    ImageDraw.Draw(image).ellipse((40, 20, 120, 100), fill=(30, 70, 120, 255))
    return image


class CutoutTests(unittest.TestCase):
    def test_border_shadow_transparency_and_deterministic_grain(self):
        image = alpha_image()
        result = C.paper_cutout(image, angle=-3)
        self.assertEqual(result.mode, "RGBA")
        self.assertEqual(result.getchannel("A").getextrema(), (0, 255))
        self.assertGreater(result.width, 100)
        self.assertEqual(result.tobytes(), C.paper_cutout(image, angle=-3).tobytes())
        colors = result.getdata()
        self.assertTrue(any(r > 240 and g > 240 and b > 240 and a == 255 for r, g, b, a in colors))
        self.assertTrue(any(0 < a < 100 for r, g, b, a in colors))

    def test_bad_alpha_and_angles_fail(self):
        for image in [Image.new("RGBA", (10, 10)), Image.new("RGBA", (10, 10), (10, 20, 30, 255))]:
            with self.assertRaises(ValueError): C.paper_cutout(image)
        for angle in [3.01, -3.01, float("nan")]:
            with self.assertRaises(ValueError): C.paper_cutout(alpha_image(), angle=angle)

    def test_existing_alpha_preserved_and_shared_ledger_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);source = root / "input.png";alpha_image().save(source)
            (root / "asset-ledger.jsonl").write_text('{"id":"other","path":"keep.png"}\n')
            def forbidden(*args): raise AssertionError("已有透明度不能再次分割")
            row = C.cutout(source, root, "sample", SOURCE, backend=forbidden)
            self.assertEqual(row["processing"]["backend"], "existing-alpha")
            self.assertEqual(row["license"], "CC BY-SA 4.0")
            self.assertIn("已抠图", row["attribution"])
            self.assertEqual(Image.open(root / row["files"][0]["path"]).tobytes(), alpha_image().tobytes())
            C.cutout(source, root, "sample", SOURCE, backend=forbidden)
            rows = [json.loads(line) for line in (root / "asset-ledger.jsonl").read_text().splitlines()]
            self.assertEqual([r["id"] for r in rows], ["other", "sample"])
            self.assertEqual(rows[0]["path"], "keep.png")

    def test_backend_failure_is_not_recorded_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);source = root / "input.png";Image.new("RGB", (160, 120), "white").save(source)
            def opaque(src, dst): Image.new("RGBA", (160, 120), "white").save(dst);return {"backend": "failed-mask"}
            with self.assertRaises(ValueError): C.cutout(source, root, "bad", SOURCE, backend=opaque)
            self.assertFalse((root / "asset-ledger.jsonl").exists())
            self.assertFalse((root / "assets/cutouts/bad/paper.png").exists())

    def test_invalid_crop_and_source_fail_before_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);source = root / "input.png";alpha_image().save(source)
            for crop in [(-1, 0, 10, 10), (0, 0, 500, 10), (0, 0, 0, 10)]:
                with self.assertRaises(ValueError): C.cutout(source, root, "bad", SOURCE, crop=crop)
            with self.assertRaises(ValueError): C.cutout(source, root, "bad", {"sourceUrl": "x"})
            with self.assertRaises(ValueError): C.cutout(source, root, "../escape", SOURCE)


if __name__ == "__main__":
    unittest.main()

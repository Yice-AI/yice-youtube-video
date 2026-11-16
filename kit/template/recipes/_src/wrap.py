# wraps recipes/_src/<name>.{css,js,txt} into recipes/<name>.html (HF sub-composition templates)
import sys, pathlib
src = pathlib.Path(__file__).parent; out = src.parent
HEAD = 'var Y = YF, c = Y.ctx("__SID__", document.querySelector(\'[data-composition-id="__SID__"]\')), s = c.spec, tl = c.tl, W = 1920, H = 1080;\n'
for js in sorted(src.glob("*.js")):
    name = js.stem
    css = (src / f"{name}.css").read_text() if (src / f"{name}.css").exists() else ""
    doc = (src / f"{name}.txt").read_text() if (src / f"{name}.txt").exists() else name
    html = f"""<!doctype html>
<!--
{doc.strip()}
-->
<html><head><meta charset="UTF-8" /></head><body><template>
<style>
{css.strip()}
</style>
<div id="__SID__-root" data-composition-id="__SID__" data-width="1920" data-height="1080">
  <div id="__SID__-holder">__MEDIA__</div>
  <script type="application/json" id="__SID__-spec">__SPEC__</script>
</div>
<script>
(function () {{
{HEAD}{js.read_text().rstrip()}
  Y.finish(c);
}})();
</script>
</template></body></html>
"""
    (out / f"{name}.html").write_text(html)
    print("wrote", name)

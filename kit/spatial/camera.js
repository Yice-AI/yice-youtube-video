// HyperFrames 3d-camera-flight: one lens and one writer, translating in screen axes.
const world = q('.world');
const cam = {x:0, y:0, z:0, rx:0, ry:0};
function applyCamera() {
  world.style.transform = `translate3d(${cam.x}px,${cam.y}px,${cam.z}px) rotateX(${cam.rx}deg) rotateY(${cam.ry}deg)`;
}
applyCamera();
tl.to(q('.bloom'), {opacity:.56,scale:1.12,duration:dur*.53,ease:'sine.inOut'},0);
tl.to(q('.bloom'), {opacity:.26,scale:1.03,duration:dur*.47,ease:'sine.inOut'},dur*.53);

tl.fromTo(q('.energy-thread'),{strokeDashoffset:1},{strokeDashoffset:-.7,duration:dur,ease:'sine.inOut'},0);

// Measure the final projected panel in stage coordinates before adding the camera push.
function zoomToFrame(frame, surroundings) {
  const at = data.exit_zoom_at;
  tl.seek(dur, false);
  const box = frame.getBoundingClientRect();
  const canvas = root.getBoundingClientRect();
  tl.seek(0, false);
  if (!box.width || !box.height) return;
  const scale = Math.min(canvas.width / box.width, canvas.height / box.height);
  const x = root.clientWidth * (.5 - scale * (box.left + box.width / 2 - canvas.left) / canvas.width);
  const y = root.clientHeight * (.5 - scale * (box.top + box.height / 2 - canvas.top) / canvas.height);
  tl.fromTo(frame, {outline:'4px solid var(--accent)'}, {outline:'0px solid transparent', duration:.16, immediateRender:false}, at);
  tl.to([frame, ...frame.querySelectorAll('img,video')], {borderRadius:0, duration:.2}, at);
  tl.to(surroundings.filter(Boolean), {opacity:0, duration:.22}, at);
  tl.to(q('.stage'), {transformOrigin:'0 0', x, y, scale, duration:dur-at, ease:'power3.inOut'}, at);
}

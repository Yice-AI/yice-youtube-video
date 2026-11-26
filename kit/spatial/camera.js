// HyperFrames 3d-camera-flight: one lens and one writer, translating in screen axes.
const world = q('.world');
const cam = {x:0, y:0, z:0, rx:0, ry:0};
function applyCamera() {
  world.style.transform = `translate3d(${cam.x}px,${cam.y}px,${cam.z}px) rotateX(${cam.rx}deg) rotateY(${cam.ry}deg)`;
}
applyCamera();
tl.to(q('.bloom'), {opacity:.56,scale:1.12,duration:dur*.53,ease:'sine.inOut'},0);
tl.to(q('.bloom'), {opacity:.26,scale:1.03,duration:dur*.47,ease:'sine.inOut'},dur*.53);

// PointSnap 3D — hai cảnh Three.js: point cloud LiDAR ở hero và mô hình VF8 xoay 360°.
// Toạ độ sinh ra theo hệ LiDAR (x tiến, y trái, z lên) rồi đổi sang hệ Three.js (x, z, -y).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const P = (x, y, z) => [x, z, -y];

function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

// Điểm tròn mềm thay cho ô vuông mặc định.
function dotTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.45, 'rgba(255,255,255,.9)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const DOT = dotTexture();

class Cloud {
  constructor() { this.pos = []; this.col = []; }
  add(x, y, z, hex) { const p = P(x, y, z); this.pos.push(...p); const c = new THREE.Color(hex); this.col.push(c.r, c.g, c.b); }
  build(size, opacity = 1) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
    const m = new THREE.PointsMaterial({ size, map: DOT, vertexColors: true, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true, alphaTest: .02 });
    return new THREE.Points(g, m);
  }
}

function boxEdges(L, W, H, color, opacity = 1) {
  const geo = new THREE.EdgesGeometry(new THREE.BoxGeometry(L, H, W));
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  const l = new THREE.LineSegments(geo, mat); return l;
}

function makeRenderer(canvas) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  r.setPixelRatio(Math.min(devicePixelRatio, 2)); r.setClearColor(0x000000, 0);
  return r;
}

// Chỉ vẽ khi cảnh nằm trong màn hình để đỡ tốn pin.
function runWhenVisible(el, frame) {
  let on = false, raf = 0; const clock = new THREE.Clock();
  const loop = () => { raf = on ? requestAnimationFrame(loop) : 0; frame(clock.getDelta(), clock.elapsedTime); };
  new IntersectionObserver((en) => { on = en[0].isIntersecting; if (on && !raf) { clock.getDelta(); loop(); } }, { threshold: .01 }).observe(el);
}

function fit(renderer, camera, el) {
  const resize = () => { const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); };
  new ResizeObserver(resize).observe(el); resize();
}

// =====================================================================
// HERO — cảnh đường phố LiDAR
// =====================================================================
function heroScene() {
  const el = document.getElementById('lidarScene'); const canvas = el.querySelector('canvas');
  const renderer = makeRenderer(canvas); const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, .1, 400);
  camera.position.set(...P(2.5, -12, 5.2));
  const controls = new OrbitControls(camera, canvas);
  controls.target.set(...P(0.5, 9, 0.6)); controls.enableDamping = true; controls.dampingFactor = .06;
  controls.enableZoom = false; controls.enablePan = false; controls.autoRotate = !reduceMotion; controls.autoRotateSpeed = .55;
  controls.minPolarAngle = .55; controls.maxPolarAngle = 1.32; controls.update();
  fit(renderer, camera, el);

  const rnd = rng(11); const cl = new Cloud(); const obj = new Cloud();
  const ego = [0, -4];
  // mặt đường: các vòng quét LiDAR
  for (let k = 0; k < 24; k++) { const R = 2.4 * Math.pow(1.16, k); const nA = 520;
    for (let i = 0; i < nA; i++) { const a = i / nA * Math.PI * 2; const x = ego[0] + R * Math.cos(a), y = ego[1] + R * Math.sin(a);
      if (Math.abs(x) > 9.5 && rnd() < .5) continue; if (Math.hypot(x, y - 10) > 46) continue;
      cl.add(x, y, (rnd() - .5) * .05 + (Math.abs(x) > 7.5 ? .15 : 0), R < 12 ? '#7DB4FF' : R < 24 ? '#4C9AFF' : '#3D7BD9'); } }
  for (const sx of [-7.5, 7.5]) for (let y = -30; y < 45; y += .14) cl.add(sx + (rnd() - .5) * .05, y, .1 + rnd() * .06, '#5E7FA8');
  const facade = (x0, y0, y1, h) => { for (let i = 0; i < (y1 - y0) * h * 8; i++) { const y = y0 + rnd() * (y1 - y0), z = rnd() * h; const wy = (y - y0) % 3.2, wz = z % 2.8; if (wy > 1.2 && wy < 2.6 && wz > 1 && wz < 2.2 && rnd() < .85) continue; cl.add(x0 + (rnd() - .5) * .08, y, z, '#5E7FA8'); } };
  facade(-11, 6, 22, 7); facade(-11.5, 24, 40, 9); facade(11, 9, 26, 8); facade(11.5, 28, 44, 6); facade(-11, -26, -6, 6); facade(11, -24, 4, 7);
  for (let i = 0; i < 2600; i++) cl.add((rnd() - .5) * 24, 46 + (rnd() - .5) * .2, rnd() * 5, '#4A6A95');
  const tree = (x, y, rr) => { for (let i = 0; i < 380; i++) { const a = rnd() * Math.PI * 2, b = Math.acos(2 * rnd() - 1), k = .75 + rnd() * .25; cl.add(x + Math.sin(b) * Math.cos(a) * rr * k, y + Math.sin(b) * Math.sin(a) * rr * k, 3 + Math.cos(b) * rr * k, '#3FA57A'); } for (let z = 0; z < 2.4; z += .06) cl.add(x, y, z, '#5E7FA8'); };
  [[-8.6, 3, 1.4], [-8.6, 14, 1.6], [8.8, 6, 1.5], [8.8, 18, 1.3], [-8.8, 30, 1.7], [9, 34, 1.6], [-8.7, -12, 1.5], [8.9, -16, 1.4]].forEach(t => tree(...t));
  const OBJS = [
    { c: [-3.3, 6], L: 4.6, W: 1.9, H: 1.6, yaw: .06, kind: 'car' },
    { c: [3.4, 16], L: 4.4, W: 1.85, H: 1.5, yaw: -.04, kind: 'car' },
    { c: [-3.0, 27], L: 8, W: 2.4, H: 3.2, yaw: 0, kind: 'truck' },
    { c: [5.6, 4.2], L: .6, W: .6, H: 1.75, yaw: 0, kind: 'ped' },
    { c: [.4, 10.5], L: 1.8, W: .6, H: 1.65, yaw: 1.45, kind: 'cyc', err: true },
  ];
  for (const o of OBJS) {
    const N = o.kind === 'truck' ? 1400 : o.kind === 'car' ? 1100 : 320; const hl = o.L / 2, hw = o.W / 2;
    for (let i = 0; i < N; i++) { let lx, ly, lz; const f = rnd();
      if (o.kind === 'car') {
        if (f < .3) { lx = (rnd() - .5) * o.L; ly = -hw * (rnd() < .5 ? 1 : -1); lz = .2 + rnd() * .8; }
        else if (f < .5) { lx = -hl * .98 * (rnd() < .5 ? 1 : -1); ly = (rnd() - .5) * o.W; lz = .25 + rnd() * .7; }
        else if (f < .75) { lx = (rnd() - .5) * o.L * .95; ly = (rnd() - .5) * o.W * .95; lz = Math.abs(lx + .2) < o.L * .24 ? 1.55 : 1.0; }
        else { lx = -.2 + (rnd() - .5) * o.L * .48; ly = -hw * .82 * (rnd() < .5 ? 1 : -1); lz = 1 + rnd() * .55; }
      } else if (o.kind === 'truck') { if (f < .5) { lx = (rnd() - .5) * o.L; ly = hw * (rnd() < .5 ? 1 : -1); lz = .4 + rnd() * (o.H - .4); } else if (f < .75) { lx = -hl * (rnd() < .5 ? 1 : -1); ly = (rnd() - .5) * o.W; lz = .4 + rnd() * (o.H - .4); } else { lx = (rnd() - .5) * o.L; ly = (rnd() - .5) * o.W; lz = o.H; } }
      else if (o.kind === 'ped') { const a = rnd() * Math.PI * 2; lz = rnd() * o.H; const w = lz > 1.5 ? .11 : lz > .85 ? .21 : .13; lx = Math.cos(a) * w + (lz < .85 ? (rnd() < .5 ? -.1 : .1) : 0); ly = Math.sin(a) * w; }
      else { if (rnd() < .55) { const side = rnd() < .5 ? -.58 : .58, a = rnd() * Math.PI * 2; lx = side + Math.cos(a) * .34; lz = .34 + Math.sin(a) * .34; ly = (rnd() - .5) * .05; } else { lz = .6 + rnd() * 1.05; lx = (rnd() - .5) * .5 + (lz > 1.2 ? .1 : 0); ly = (rnd() - .5) * .3; } }
      const cx = Math.cos(o.yaw), sx = Math.sin(o.yaw);
      obj.add(o.c[0] + lx * cx - ly * sx, o.c[1] + lx * sx + ly * cx, lz, lz > 1.1 ? '#FFFFFF' : '#BFE0FF'); }
  }
  scene.add(cl.build(.12, .9)); scene.add(obj.build(.1, 1));

  // box 3D
  let errBox = null;
  for (const o of OBJS) {
    const b = boxEdges(o.L + .24, o.W + .24, o.H + .08, o.err ? 0xF87171 : 0x4CC38A);
    b.position.set(...P(o.c[0], o.c[1], (o.H + .08) / 2 + (o.err ? .75 : 0))); b.rotation.y = o.yaw; scene.add(b);
    if (o.err) { errBox = b; errBox.userData = { lift: .75, target: .75, h: o.H + .08, c: o.c, L: o.L, W: o.W }; }
  }
  // vòng quét LiDAR lan ra
  const sweep = new THREE.Mesh(new THREE.RingGeometry(.97, 1, 160), new THREE.MeshBasicMaterial({ color: 0x7DB4FF, transparent: true, opacity: .9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
  sweep.rotation.x = -Math.PI / 2; sweep.position.set(...P(ego[0], ego[1], .03)); scene.add(sweep);
  // cảm biến trên xe ego
  const sensor = new THREE.Mesh(new THREE.SphereGeometry(.18, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  sensor.position.set(...P(ego[0], ego[1], 1.9)); scene.add(sensor);

  document.addEventListener('pointsnap:fix', (e) => { errBox.userData.target = e.detail.fixed ? 0 : .75; });

  const tag = document.getElementById('errTag'); const v = new THREE.Vector3(); const red = new THREE.Color(0xF87171), green = new THREE.Color(0x4CC38A);
  runWhenVisible(el, (dt, t) => {
    controls.update();
    const s = 1 + ((t * 9) % 42); sweep.scale.setScalar(s); sweep.material.opacity = Math.max(0, .9 - s / 46);
    const u = errBox.userData; u.lift += (u.target - u.lift) * Math.min(1, dt * 3);
    errBox.position.y = u.h / 2 + u.lift; const k = u.lift / .75;
    errBox.material.color.copy(green).lerp(red, k); errBox.material.opacity = k > .05 ? .65 + .35 * Math.abs(Math.sin(t * 3)) : 1;
    renderer.render(scene, camera);
    // đặt nhãn HTML theo góc box
    v.set(...P(u.c[0] + u.W, u.c[1], u.h + u.lift + .3)).project(camera);
    const x = (v.x + 1) / 2 * el.clientWidth, y = (1 - v.y) / 2 * el.clientHeight;
    tag.style.transform = `translate(${Math.min(el.clientWidth - 190, x + 14).toFixed(0)}px, ${(y - 30).toFixed(0)}px)`;
    tag.style.opacity = v.z < 1 ? '1' : '0';
  });
}

// =====================================================================
// VF8 — point cloud xoay 360° trên bàn xoay
// =====================================================================
function vf8Scene() {
  const el = document.getElementById('vf8Scene'); const canvas = el.querySelector('canvas');
  const renderer = makeRenderer(canvas); const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, .1, 100);
  camera.position.set(...P(6.5, -6.9, 3.1)); camera.lookAt(...P(0, 0, .25));
  fit(renderer, camera, el);

  const L = 4.75, HL = L / 2, Wd = 1.934, Hh = 1.667, AXF = 1.40, AXR = -1.55, WR = .38;
  const roof = x => { if (x > 2.2) return .80 + (2.375 - x) * .4; if (x > 1.25) return .87 + (2.2 - x) / .95 * .15; if (x > .3) return 1.02 + (1.25 - x) / .95 * .62; if (x > -1.05) return 1.64 + Math.sin((x - .3) / -1.35 * Math.PI) * .025; if (x > -2.0) return 1.64 - Math.pow((-1.05 - x) / .95, 1.6) * .33; return 1.31 - (-2.0 - x) / .375 * .22; };
  const bottom = x => (Math.abs(x) > 2.0 ? .32 : .22);
  const halfW = (x, z) => { let w = Wd / 2; if (z > 1.0) w -= (z - 1.0) * .36; const e = Math.abs(x) - 1.85; if (e > 0) w *= Math.sqrt(Math.max(.2, 1 - (e / .55) ** 2 * .55)); if (z < .4) w -= (.4 - z) * .15; return w; };
  const inArch = (x, z) => [AXF, AXR].some(ax => Math.hypot(x - ax, z - WR) < WR + .07);
  const rnd = rng(21);
  const body = new Cloud(), lights = new Cloud(), refl = new Cloud();
  const C = { body: '#9CC7FF', clad: '#4A6A95', glass: '#3D7BD9', line: '#FFFFFF', tire: '#5E7FA8', rim: '#BFE0FF' };
  const put = (x, y, z, k) => { body.add(x, y, z, C[k]); if (rnd() < .35) refl.add(x, y, -z, C[k]); };
  for (let i = 0; i < 9000; i++) { const s = rnd() < .5 ? -1 : 1, x = (rnd() - .5) * L * .98, top = roof(x) - .02, z = bottom(x) + rnd() * (top - bottom(x));
    if (inArch(x, z)) continue; const glass = z > 1.04 && z < top - .05 && x < 1.15 && x > -1.95;
    const clad = z < .42 || [AXF, AXR].some(ax => Math.hypot(x - ax, z - WR) < WR + .16);
    put(x, s * halfW(x, z), z, glass ? 'glass' : Math.abs(z - .96) < .015 ? 'line' : clad ? 'clad' : 'body'); }
  for (let i = 0; i < 6000; i++) { const x = (rnd() - .5) * L * .97, z = roof(x), y = (rnd() - .5) * 2 * halfW(x, z) * .97;
    const glass = (x > .3 && x < 1.22 && Math.abs(y) < halfW(x, z) - .08) || (x < -1.3 && x > -2.0 && Math.abs(y) < halfW(x, z) - .1); put(x, y, z, glass ? 'glass' : 'body'); }
  for (let i = 0; i < 1800; i++) { const z = .3 + rnd() * .52, y = (rnd() - .5) * 2 * halfW(HL - .05, z) * .95; put(HL - .02 - Math.abs(y) * .12, y, z, z < .45 ? 'clad' : 'body'); }
  for (let i = 0; i < 1600; i++) { const z = .32 + rnd() * .85, y = (rnd() - .5) * 2 * halfW(-HL + .05, z) * .95; put(-HL + .02 + Math.abs(y) * .1, y, z, z < .45 ? 'clad' : 'body'); }
  for (const ax of [AXF, AXR]) for (const s of [-1, 1]) { const yy = s * (Wd / 2 - .04);
    for (let i = 0; i < 500; i++) { const a = rnd() * Math.PI * 2, rr = WR - .06 + rnd() * .06; put(ax + Math.cos(a) * rr, yy, WR + Math.sin(a) * rr, 'tire'); }
    for (let sp = 0; sp < 5; sp++) for (let i = 0; i < 50; i++) { const a = sp / 5 * Math.PI * 2 + (rnd() - .5) * .18, rr = .05 + rnd() * .25; put(ax + Math.cos(a) * rr, yy + s * .01, WR + Math.sin(a) * rr, 'rim'); } }
  for (const s of [-1, 1]) for (let i = 0; i < 140; i++) { const x = -1.6 + rnd() * 2.0; put(x, s * .6, roof(x) + .04, 'line'); }
  // đèn chữ V, đèn pha, đèn hậu
  for (let i = 0; i < 900; i++) { const y = (rnd() - .5) * 1.82, ay = Math.abs(y); const z = ay < .2 ? .80 + ay * .5 : .90 + (ay - .2) * .02; lights.add(HL - .03 - ay * .12 - (ay > .8 ? (ay - .8) * .8 : 0), y, z, '#FFFFFF'); }
  for (const s of [-1, 1]) for (let i = 0; i < 120; i++) lights.add(HL - .12, s * (.6 + rnd() * .18), .55 + rnd() * .12, '#7DE3FF');
  for (let i = 0; i < 600; i++) { const y = (rnd() - .5) * 1.75; lights.add(-HL + .04 + Math.abs(y) * .1, y, 1.0 + (rnd() - .5) * .02, '#F87171'); }

  const car = new THREE.Group(); scene.add(car);
  car.add(body.build(.032, .95)); car.add(lights.build(.05, 1));
  const r = refl.build(.03, .16); car.add(r);
  const box = boxEdges(L + .16, Wd + .16, Hh + .04, 0x4CC38A, .95); box.position.y = (Hh + .04) / 2; car.add(box);
  const sensor = new THREE.Mesh(new THREE.SphereGeometry(.06, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffffff })); sensor.position.set(...P(-.1, 0, roof(-.1) + .08)); car.add(sensor);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: DOT, color: 0x4C9AFF, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); halo.scale.setScalar(.5); halo.position.copy(sensor.position); car.add(halo);

  // sàn bàn xoay: vòng tròn thật nằm trên mặt đất, tâm dưới gầm xe
  const circle = (R, color, opacity, dashed) => { const pts = []; for (let i = 0; i <= 180; i++) { const a = i / 180 * Math.PI * 2; pts.push(new THREE.Vector3(R * Math.cos(a), .002, R * Math.sin(a))); }
    const g = new THREE.BufferGeometry().setFromPoints(pts); const m = dashed ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: .12, gapSize: .18 }) : new THREE.LineBasicMaterial({ color, transparent: true, opacity });
    const l = new THREE.Line(g, m); if (dashed) l.computeLineDistances(); return l; };
  const floor = new THREE.Group(); scene.add(floor);
  floor.add(circle(2.75, 0x7DB4FF, .95)); floor.add(circle(2.77, 0x7DB4FF, .6)); floor.add(circle(3.10, 0x4C9AFF, .4)); floor.add(circle(3.35, 0x4C9AFF, .35, true));
  const ticks = []; for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; ticks.push(new THREE.Vector3(2.75 * Math.cos(a), .002, 2.75 * Math.sin(a)), new THREE.Vector3(2.95 * Math.cos(a), .002, 2.95 * Math.sin(a))); }
  floor.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(ticks), new THREE.LineBasicMaterial({ color: 0x7DB4FF, transparent: true, opacity: .8 })));
  const discTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d'); const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128); gr.addColorStop(0, 'rgba(76,154,255,.55)'); gr.addColorStop(.7, 'rgba(76,154,255,.18)'); gr.addColorStop(1, 'rgba(76,154,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c); })();
  const disc = new THREE.Mesh(new THREE.PlaneGeometry(6.4, 6.4), new THREE.MeshBasicMaterial({ map: discTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })); disc.rotation.x = -Math.PI / 2; floor.add(disc);
  const shadowTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(2,8,20,.7)'); gr.addColorStop(1, 'rgba(2,8,20,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c); })();
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 2.4), new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false })); shadow.rotation.x = -Math.PI / 2; shadow.position.y = .004; car.add(shadow);
  // vạch tốc độ nền
  const lines = []; for (let i = 0; i < 18; i++) { const z = -6 - rnd() * 8, y = .5 + rnd() * 3.5, x = -8 + rnd() * 10; lines.push(new THREE.Vector3(x, y, z), new THREE.Vector3(x + 1.5 + rnd() * 3, y, z)); }
  const speed = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(lines), new THREE.LineBasicMaterial({ color: 0x4C9AFF, transparent: true, opacity: .2 })); scene.add(speed);

  // kéo để xoay (có quán tính), không kéo thì tự xoay
  let vel = reduceMotion ? 0 : .35, dragging = false, lastX = 0;
  el.addEventListener('pointerdown', (e) => { dragging = true; lastX = e.clientX; el.setPointerCapture(e.pointerId); });
  el.addEventListener('pointermove', (e) => { if (!dragging) return; const dx = e.clientX - lastX; lastX = e.clientX; car.rotation.y += dx * .01; vel = dx * .6; });
  const up = () => { dragging = false; }; el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);

  runWhenVisible(el, (dt, t) => {
    if (!dragging) { vel += ((reduceMotion ? 0 : .35) - vel) * Math.min(1, dt * 1.5); car.rotation.y += vel * dt; }
    halo.material.opacity = .6 + .4 * Math.sin(t * 4);
    speed.position.x = ((t * 3) % 6) - 3;
    renderer.render(scene, camera);
  });
}

export function init() { heroScene(); vf8Scene(); }

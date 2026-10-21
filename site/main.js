// Ilios Froyo: the pour.
// Built on the shop's real station: a three-handle twist machine set into a limewash niche.
// Pick a handle (Sweet Harbor Coffee, twist, Organic Vanilla Bean), pull it, and the cup fills.
// One live three.js scene, scrubbed by scroll:
//   pull the handle -> a ribbon of froyo leaves the star spout -> the camera
//   follows it down -> the cup circles under the spout while the swirl builds
//   -> the tail breaks off, the tip curls, the handle springs back -> settle.
// The froyo is simulated live when the page loads (pour-sim.js): a yield-stress rope fed out of the star spout
// falls a few centimetres, lands, stops dead and slumps into coils that stack and fuse while the server circles the
// cup; then the valve closes, the cup drops away and the tail folds over into the tip. It is recorded at 240 Hz and
// drawn as a ridged rope for any time (pour.js), so scrolling scrubs the physics smoothly, forwards or back.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildCup, cupMaterials, CUP } from './cup.js';
import { simulatePour } from './pour-sim.js';
import { FroyoRope } from './pour.js';
import { FLAVORS, makeFroyoMaterial, setFlavorUniforms } from './froyo.js';

const $ = (s, r = document) => r.querySelector(s);
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeInOut = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const RM = matchMedia('(prefers-reduced-motion: reduce)');

const root = document.documentElement;
const stage = $('#stage');
const canvas = $('#gl');
const hero = $('.hero');
const ring = $('#ring');
const knobcue = $('#knobcue');
const railbar = $('#railbar');

// ------------------------------------------------------------------ timeline
// Every beat lives in hero progress p (0..1). Tuned for a 1000vh hero.
const TL = {
  pull: [0.045, 0.14],      // handle travels down
  emerge: [0.18, 0.30],     // the cup is up at the spout and the paste starts to flow
  pour: [0.30, 0.80],       // swirl builds, cup circles under the spout
  release: [0.80, 0.86],    // handle back up, tail breaks off
  settle: [0.86, 0.97],     // camera eases out to the product shot
};

// ------------------------------------------------------------------ renderer
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
} catch (e) {
  fail(e);
}
const isSmall = () => innerWidth < 820;
const dpr = () => Math.min(devicePixelRatio || 1, isSmall() ? 1.6 : 1.85);
if (renderer) {
  renderer.setPixelRatio(dpr());
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
}

function fail(err) {
  console.warn('3D unavailable, showing the still.', err);
  root.classList.add('no-gl');
  barFallback();
  $('#poster').style.backgroundImage = "url('assets/img/machine.jpg')";
  if (renderer) updateBands(1, true); // a failed context is handled at the end of setup, once the bands exist
}

const scene = new THREE.Scene();
const PLASTER = new THREE.Color('#cfc5b5');
scene.background = PLASTER.clone();
scene.fog = new THREE.Fog(PLASTER, 6.5, 16.0);

const camera = new THREE.PerspectiveCamera(26, 1, 0.01, 30);

if (renderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.5;
}

// light: the shop's warm ceiling cans, one over the niche and one over the wall sun,
// a soft bounce off the room, and a glow at the top of the niche
const can = new THREE.SpotLight('#ffe8cc', 9, 4.5, 0.62, 0.85, 1.4);
can.position.set(0.05, 1.85, 1.05);
can.target.position.set(0, 0.35, 0.15);
can.castShadow = true;
can.shadow.mapSize.set(2048, 2048);
can.shadow.bias = -0.0002;
can.shadow.normalBias = 0.01;
can.shadow.radius = 6;
can.shadow.camera.near = 0.6;
can.shadow.camera.far = 4;
scene.add(can, can.target);
const can2 = new THREE.SpotLight('#ffe8cc', 5, 4, 0.5, 0.9, 1.4);
can2.position.set(0.9, 1.9, 1.0);
can2.target.position.set(0.86, 1.0, 0.3);
scene.add(can2, can2.target);
scene.add(new THREE.HemisphereLight('#fff6ea', '#bdb2a2', 0.85));
const fillL = new THREE.DirectionalLight('#f6efe4', 0.7);
fillL.position.set(-1.2, 0.9, 2.2);
scene.add(fillL);
const nicheGlow = new THREE.PointLight('#fff1dc', 0.35, 1.2, 1.6);
nicheGlow.position.set(0, 0.97, 0.05);
scene.add(nicheGlow);

// ------------------------------------------------------------------ the froyo
// The shop's six flavours on three machines (docs/ILIOS-FIELD-NOTES.md, froyo.js): each machine pours its left flavour, a
// twist of the two, and its right flavour. The station on the page is one machine; picking a flavour puts that machine's
// sign on it and pulls the matching handle (0 left, 1 twist, 2 right).
const MACHINES = {
  tart: [['ORGANIC', 'ORIGINAL TART'], ['ORGANIC', 'ORIGINAL TART']],
  raspberry: [['', 'RASPBERRY'], ['ORGANIC', 'VANILLA BEAN']],
  coffee: [['SWEET', 'HARBOR COFFEE'], ['ORGANIC', 'VANILLA BEAN']],
};

// ------------------------------------------------------------------ flavour choice
let fl = 1;             // which flavour (FLAVORS)
let sel = 1;            // which handle on the machine: 0 left, 1 twist, 2 right
const chips = [...document.querySelectorAll('[data-flavor]')];
const flavorNames = [...document.querySelectorAll('[data-flavor-name]')];
function setFlavor(i, fromUser) {
  if (scrub && shown > TL.emerge[0] && fromUser) return;   // the cup is already under a spout
  fl = i;
  const f = FLAVORS[i];
  sel = f.handle;
  setFlavorUniforms(f);
  const chip = f.chip ?? i;
  chips.forEach(c => c.setAttribute('aria-pressed', String(+c.dataset.flavor === chip)));
  flavorNames.forEach(n => { n.textContent = f.name; });
  setSign(f.machine);
  const bf = document.getElementById('barflavor');
  if (bf) bf.textContent = f.name;
  wake();
}
chips.forEach(c => c.addEventListener('click', () => setFlavor(+c.dataset.flavor, true)));
// a handle grabbed on the machine on screen: that machine's flavour for it
const flavorFor = handle => FLAVORS.findIndex(f => f.machine === FLAVORS[fl].machine && f.handle === handle);

// the machine's header sign, redrawn for each machine on top of the model's own sign texture
let signMesh = null, signBase = null;
const signTex = {};
function setSign(machine) {
  if (!signMesh || !signBase) return;
  if (!signTex[machine]) {
    const img = signBase.image, W = img.width, H = img.height;
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const x = c.getContext('2d');
    x.drawImage(img, 0, 0);
    if (machine !== 'coffee') {
      const [L, R] = MACHINES[machine];
      x.fillStyle = 'rgb(244,242,237)';
      x.fillRect(W * 0.01, H * 0.2, W * 0.34, H * 0.58);
      x.fillRect(W * 0.65, H * 0.2, W * 0.34, H * 0.58);
      x.fillStyle = 'rgb(128,98,58)';
      x.textAlign = 'center';
      x.font = `500 ${Math.round(H * 0.105)}px "Manrope", ui-sans-serif, sans-serif`;
      if ('letterSpacing' in x) x.letterSpacing = Math.round(H * 0.014) + 'px';
      for (const [[l1, l2], cx] of [[L, W * 0.18], [R, W * 0.82]]) {
        if (l1) { x.fillText(l1, cx, H * 0.46); x.fillText(l2, cx, H * 0.64); }
        else x.fillText(l2, cx, H * 0.56);
      }
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.flipY = signBase.flipY;
    t.anisotropy = 8;
    signTex[machine] = t;
  }
  signMesh.material.map = signTex[machine];
  wake();
}

// ------------------------------------------------------------------ load
const manager = new THREE.LoadingManager();
manager.onProgress = (_u, done, total) => {
  ring.style.strokeDashoffset = String(Math.round(126 * (1 - done / Math.max(total, 1))));
};
const loader = new GLTFLoader(manager).setMeshoptDecoder(MeshoptDecoder);
const load = url => new Promise((res, rej) => loader.load(url, res, undefined, rej));

let machine, room, handles = [], balls = [], cup, path, pour, rec, froyoMat, cupMats;
let nozzles = [], cupBases = [];
const knobWorld = new THREE.Vector3();

Promise.all([
  load('assets/models/ilios-softserve-machine.glb'),
  load('assets/models/ilios-froyo-cup.glb'),
  load('assets/models/ilios-room.glb'),
  fetch('assets/pour-path.json').then(r => r.json()),
]).then(([gm, gc, gr, pj]) => {
  if (!renderer) return;
  machine = gm.scene;
  room = gr.scene;
  removeHiddenTwins(room);
  room.traverse(o => {
    if (!o.isMesh) return;
    o.receiveShadow = true;
    o.castShadow = !o.material.transparent;
    if (o.material.transparent) { o.material.depthWrite = false; o.material.polygonOffset = true; o.material.polygonOffsetFactor = -2; }
    if (o.material.map) o.material.map.anisotropy = 8;
  });
  path = pj;
  // the real cup's size (cup.js), in the model's paper and foil
  cupMats = cupMaterials(gc.scene);
  cup = buildCup(cupMats);
  machine.traverse(o => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      if (o.material.transparent) { o.material.depthWrite = false; o.castShadow = false; }
      if (o.material.map) o.material.map.anisotropy = 8;
    }
  });
  handles = path.handles.map(n => machine.getObjectByName(n));
  signMesh = machine.getObjectByName('SignFace');
  if (signMesh && signMesh.material.map) { signMesh.material = signMesh.material.clone(); signBase = signMesh.material.map; }
  document.fonts && document.fonts.ready.then(() => { for (const k in signTex) delete signTex[k]; setSign(FLAVORS[fl].machine); });
  balls = path.handles.map(n => machine.getObjectByName(n + 'Ball'));
  [cupMats.print, cupMats.inside, cupMats.foil].forEach(m => { if (m.map) m.map.anisotropy = 8; });
  // the machine model's cup stack is the old squat cup: swap in a stack of the real ones
  machine.traverse(o => { if (/^Stack(Cup|CupSeam|Emblem)\d/.test(o.name)) o.visible = false; });
  const stack = new THREE.Group();
  for (let i = 0; i < 6; i++) {
    const c = buildCup(cupMats);
    c.position.set(0, i * 0.0105, 0);
    c.rotation.y = 0.35 + i * 0.07;
    c.traverse(o => { if (o.isMesh) o.castShadow = i === 5 || o.name === 'Cup'; });
    stack.add(c);
  }
  stack.position.set(-0.262, path.cupBasesMachine[0][1], 0.214);
  machine.add(stack);

  nozzles = path.nozzlesMachine.map(a => new THREE.Vector3().fromArray(a));
  cupBases = path.cupBasesMachine.map(a => new THREE.Vector3().fromArray(a));
  cup.position.copy(cupBases[1]);
  scene.add(room, machine, cup);

  const pmat = makeFroyoMaterial();
  froyoMat = pmat;
  rec = simulatePour();
  pour = new FroyoRope(rec, pmat);
  cup.add(pour.mesh);                 // the simulation is in the cup's own frame

  setupToppings();
  root.classList.add('ready');
  resize();
  applyMode();
  wake();
}).catch(fail);

// The room model is built from slabs, and where the wall slab meets the niche its end faces lie in exactly the same
// planes as the niche's side walls, its ceiling and its sill (the 6 cm of wall thickness at the front of the opening).
// Two coplanar faces flicker against each other as the camera moves, which showed as a crawling band on the left
// wall once the cup was full. Those end faces are buried, so drop them: anything facing into the opening that sits
// in the front 6 cm of the wall, on the opening's sides (x = +-0.37), top (y = 1.02) or sill (y = 0).
function removeHiddenTwins(root) {
  const NW = 0.37, NH = 1.02, Z0 = 0.2385, Z1 = 0.3015, TOL = 0.0025;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3(), m = new THREE.Vector3();
  root.updateMatrixWorld(true);
  root.traverse(o => {
    if (!o.isMesh || !o.geometry.index) return;
    const g = o.geometry, P = g.attributes.position, I = g.index.array, keep = [];
    let dropped = 0;
    for (let i = 0; i < I.length; i += 3) {
      a.fromBufferAttribute(P, I[i]).applyMatrix4(o.matrixWorld);
      b.fromBufferAttribute(P, I[i + 1]).applyMatrix4(o.matrixWorld);
      c.fromBufferAttribute(P, I[i + 2]).applyMatrix4(o.matrixWorld);
      n.subVectors(b, a).cross(m.subVectors(c, a)).normalize();
      const zmin = Math.min(a.z, b.z, c.z), zmax = Math.max(a.z, b.z, c.z);
      const inFront = zmin > Z0 && zmax < Z1;
      const side = (Math.abs(a.x + NW) < TOL && Math.abs(b.x + NW) < TOL && Math.abs(c.x + NW) < TOL && n.x > 0.9) ||
        (Math.abs(a.x - NW) < TOL && Math.abs(b.x - NW) < TOL && Math.abs(c.x - NW) < TOL && n.x < -0.9);
      const top = Math.abs(a.y - NH) < TOL && Math.abs(b.y - NH) < TOL && Math.abs(c.y - NH) < TOL && n.y < -0.9;
      const sill = Math.abs(a.y) < TOL && Math.abs(b.y) < TOL && Math.abs(c.y) < TOL && n.y > 0.9 && Math.max(Math.abs(a.x), Math.abs(b.x), Math.abs(c.x)) < NW + TOL;
      if (inFront && (side || top || sill)) { dropped++; continue; }
      keep.push(I[i], I[i + 1], I[i + 2]);
    }
    if (dropped) g.setIndex(keep);
    o.userData.droppedTwins = dropped;
  });
}

// ------------------------------------------------------------------ camera choreography
// Keys are [p, camera position, look target] in machine space (metres, Y up, front = +Z).
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const Z0 = 0.272;   // the spouts' line
const NZY = 0.362;  // spout exit height
const CAM_KEYS = [
  [0.000, V(0.16, 0.64, 3.55), V(0.05, 0.56, 0.20)],
  [0.045, V(0.13, 0.60, 2.55), V(0.00, 0.52, 0.22)],
  [0.120, V(0.20, 0.50, 1.35), V(0.00, 0.40, Z0)],
  [0.180, V(0.20, 0.42, Z0 + 0.66), V(0.00, 0.335, Z0)],
];
// the pour: the cup is held up under the spout, so the camera stays with the falling rope and the pile, looking down
// into the cup while it fills, then circling round and down as the swirl rises over the rim
for (let i = 0; i <= 6; i++) {
  const t = i / 6;
  const p = 0.22 + t * 0.52;
  const ang = THREE.MathUtils.degToRad(18 - 56 * t);
  const rad = 0.40 - 0.06 * Math.sin(t * Math.PI);
  const y = 0.50 - 0.13 * smooth(0.35, 0.95, t);
  CAM_KEYS.push([p, V(Math.sin(ang) * rad, y, Z0 + Math.cos(ang) * rad), V(0, 0.325, Z0)]);
}
CAM_KEYS.push([0.84, V(0.14, 0.22, Z0 + 0.58), V(0.0, 0.12, Z0)]);
CAM_KEYS.push([0.97, V(0.42, 0.20, Z0 + 0.80), V(-0.10, 0.12, Z0 + 0.04)]);
CAM_KEYS.push([1.00, V(0.425, 0.199, Z0 + 0.81), V(-0.102, 0.12, Z0 + 0.04)]);

const camPosCurve = new THREE.CatmullRomCurve3(CAM_KEYS.map(k => k[1]), false, 'centripetal');
const camTgtCurve = new THREE.CatmullRomCurve3(CAM_KEYS.map(k => k[2]), false, 'centripetal');
function camAt(p, pos, tgt) {
  let i = 0;
  while (i < CAM_KEYS.length - 2 && p > CAM_KEYS[i + 1][0]) i++;
  const [pa] = CAM_KEYS[i], [pb] = CAM_KEYS[i + 1];
  const local = clamp((p - pa) / (pb - pa));
  const u = (i + local) / (CAM_KEYS.length - 1);
  camPosCurve.getPoint(u, pos);
  camTgtCurve.getPoint(u, tgt);
}

// portrait screens: back the camera away along its own line so the subject still fits
// and re-centre: on narrow screens the copy sits above the subject, so the subject
// moves to the horizontal centre and into the lower part of the frame
function fitPortrait(pos, tgt, p) {
  const a = camera.aspect;
  if (a >= 1.2) return;
  const w = clamp((1.2 - a) / 0.6);
  const dist = pos.distanceTo(tgt);
  tgt.x *= 1 - 0.85 * w;
  pos.x -= 0.0;
  // copy on top -> subject low; on the settle beat the card sits at the bottom -> subject high
  const settle = smooth(0.86, 0.95, p);
  tgt.y += dist * (0.13 - 0.25 * settle) * w;
  const k = Math.pow(1.2 / a, 0.62);
  pos.sub(tgt).multiplyScalar(k).add(tgt);
}

// ------------------------------------------------------------------ the scene at progress p
const camPos = new THREE.Vector3(), camTgt = new THREE.Vector3();

// scroll p -> pour time
const POUR_P = [0.18, 0.84];
const _held = new THREE.Vector3(), _tray = new THREE.Vector3(), _h0 = new THREE.Vector3(), _hand = [0, 0, 0];
const pourT = p => clamp((p - POUR_P[0]) / (POUR_P[1] - POUR_P[0])) * rec.duration;
const pOfT = t => POUR_P[0] + t / rec.duration * (POUR_P[1] - POUR_P[0]);
let camY = -1;

// The simulated hand keeps the spout's star tip above the rim the whole time (the cap never enters the cup), so the
// cup can follow it exactly.
function pose(p) {
  if (!machine) return;
  const t = pourT(p);
  const N = nozzles[sel];

  // the handle: pulled for the whole pour, released when the valve closes
  const pRel = pOfT(rec.valveCloseT);
  const pull = easeInOut(smooth(TL.pull[0], TL.pull[1], p)) * (1 - easeInOut(smooth(pRel, pRel + 0.03, p)));
  handles.forEach((h, i) => { h.rotation.x = i === sel ? pull * path.handlePullRadians : 0; });

  // the cup: waits on the tray, slides under the chosen spout, is lifted up to it, held there while the server
  // circles it (the simulation's hand), then, once the tail has broken off, lowered back to the tray
  const slide = easeInOut(smooth(0.03, 0.10, p));
  _tray.copy(cupBases[1]).lerp(cupBases[sel], slide);
  pour.handAt(0, _hand);
  _h0.set(N.x - _hand[0], N.y - _hand[1], N.z - _hand[2]);          // held position at the start of the pour
  if (p < POUR_P[0]) {
    cup.position.copy(_tray).lerp(_h0, easeInOut(smooth(0.10, POUR_P[0], p)));
  } else {
    const tr = rec.releaseT + 0.12;
    pour.handAt(Math.min(t, tr), _hand);
    _held.set(N.x - _hand[0], N.y - _hand[1], N.z - _hand[2]);
    cup.position.copy(_held).lerp(_tray, easeInOut(smooth(rec.releaseT, rec.duration, t)));
  }

  pour.setTime(p < POUR_P[0] ? 0 : t);
  pour.mesh.visible = p >= POUR_P[0] - 1e-6 && pour.visible > 1;

  // camera
  camAt(p, camPos, camTgt);
  const sx = nozzles[sel].x * smooth(0.05, 0.14, p);
  camPos.x += sx;
  camTgt.x += sx;
  // during the pour, keep the falling rope and the pile in frame: aim between the spout and the top of the pile
  {
    const top = cup.position.y + Math.max(0.03, rec.frames[Math.min(rec.frames.length - 1, Math.floor(t / rec.params.rec))].top);
    // while pouring: between the spout and the top of the pile; once the valve closes: on the cup and its swirl
    const pour = (N.y + top) / 2 - 0.004, done = cup.position.y + 0.075;
    camY = pour + (done - pour) * smooth(rec.valveCloseT, rec.releaseT + 0.5, t);
    const w = smooth(0.17, 0.24, p) * (1 - smooth(0.79, 0.86, p));
    camTgt.y += (camY - camTgt.y) * w;
    camPos.y += (camY - 0.325) * w;
  }
  if (window.__ilios && window.__ilios.free) return;   // test hook: a camera set from outside stays put
  fitPortrait(camPos, camTgt, p);
  camera.position.copy(camPos);
  camera.lookAt(camTgt);
  const close = smooth(0.12, 0.2, p) * (1 - smooth(0.80, 0.95, p));
  camera.fov = THREE.MathUtils.lerp(26, 30, close) * (camera.aspect < 1 ? 1.12 : 1);
  camera.updateProjectionMatrix();
}

// ------------------------------------------------------------------ captions
const bands = [...document.querySelectorAll('.band')].map(el => {
  const [a, b] = el.dataset.band.split(',').map(Number);
  return { el, a, b, op: -1, k: -1, first: el.classList.contains('first'), last: el.classList.contains('final') };
});
// split headlines into words with seeded stagger thresholds
function rng(seed) { let s = seed >>> 0; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; }
document.querySelectorAll('[data-split]').forEach((h, n) => {
  const text = h.textContent.trim();
  const r = rng(11 + n);
  const words = text.split(/\s+/);
  h.textContent = '';
  const sr = document.createElement('span');
  sr.className = 'vh';
  sr.textContent = text;
  const vis = document.createElement('span');
  vis.setAttribute('aria-hidden', 'true');
  words.forEach((w, i) => {
    const s = document.createElement('span');
    s.className = 'w';
    s.style.setProperty('--th', (i / words.length * 0.42 + r() * 0.05).toFixed(3));
    s.textContent = w;
    vis.appendChild(s);
    if (i < words.length - 1) vis.appendChild(document.createTextNode(' '));
  });
  h.append(sr, vis);
});

let loadK = 0;
function updateBands(p, force) {
  for (const B of bands) {
    const f = Math.min(0.02, (B.b - B.a) / 3);
    let op = (B.first ? 1 : smooth(B.a, B.a + f, p)) * (B.last ? 1 : 1 - smooth(B.b - f, B.b, p));
    if (B.last && p < B.a) op = 0;
    let k = clamp((p - B.a) / Math.min(0.03, (B.b - B.a) * 0.35));
    if (B.first) k = Math.max(k, loadK);
    if (force && B.last) { op = 1; k = 1; }
    if (Math.abs(op - B.op) > 0.004) { B.op = op; B.el.style.opacity = op.toFixed(3); B.el.style.visibility = op < 0.01 ? 'hidden' : 'visible'; }
    if (Math.abs(k - B.k) > 0.008) { B.k = k; B.el.style.setProperty('--k', k.toFixed(3)); }
  }
}

// ------------------------------------------------------------------ scroll drive (lerped, rests when converged)
let target = 0, shown = 0, raf = null, last = 0, heroOn = true, scrub = false, dirty = true;
const heroProgress = () => {
  const r = hero.getBoundingClientRect();
  return clamp(-r.top / Math.max(1, r.height - innerHeight));
};
function tick(now) {
  const dt = Math.min(100, now - (last || now));
  last = now;
  const k = 0.11;
  shown += (target - shown) * (1 - Math.pow(1 - k, dt / 16.667));
  let more = Math.abs(target - shown) > 0.00004;
  if (!more) shown = target;
  if (loadK < 1) { loadK = Math.min(1, loadK + dt / 1400); more = true; }
  frame(shown);
  if (more || dirty) { dirty = false; raf = requestAnimationFrame(tick); } else { raf = null; last = 0; }
}
function frame(p) {
  updateBands(p);
  if (p > 0.72 && window.__startToppings) window.__startToppings();   // get the bar ready while the cup is finishing
  if (railbar) railbar.style.setProperty('--p', p.toFixed(3));
  if (!machine) return;
  pose(p);
  renderer.render(scene, camera);
  placeKnobCue(p);
}
function wake() {
  dirty = true;
  if (raf === null && heroOn) raf = requestAnimationFrame(tick);
}
function onScroll() {
  if (!scrub) return;
  target = heroProgress();
  wake();
}

// gold ring that sits on the knob until the handle is pulled
let cueOp = -1;
function placeKnobCue(p) {
  const knobMesh = balls[sel];
  if (!knobMesh) return;
  const op = 1 - smooth(0.01, 0.05, p);
  if (Math.abs(op - cueOp) > 0.01) {
    cueOp = op;
    knobcue.style.opacity = (op * (root.classList.contains('ready') ? 1 : 0)).toFixed(2);
    knobcue.style.visibility = op < 0.02 ? 'hidden' : 'visible';
  }
  if (op <= 0) return;
  knobMesh.getWorldPosition(knobWorld).project(camera);
  const x = (knobWorld.x * 0.5 + 0.5) * stage.clientWidth;
  const y = (-knobWorld.y * 0.5 + 0.5) * stage.clientHeight;
  knobcue.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
}

// ------------------------------------------------------------------ grab the handle
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
let drag = null;
function hitHandle(e) {
  if (!handles.length) return -1;
  const r = canvas.getBoundingClientRect();
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  for (let i = 0; i < handles.length; i++) if (ray.intersectObject(handles[i], true).length) return i;
  // generous target: anywhere within ~40px of a ball counts
  let best = -1, bd = 40;
  balls.forEach((b, i) => {
    b.getWorldPosition(knobWorld).project(camera);
    const kx = (knobWorld.x * 0.5 + 0.5) * r.width + r.left, ky = (-knobWorld.y * 0.5 + 0.5) * r.height + r.top;
    const d = Math.hypot(e.clientX - kx, e.clientY - ky);
    if (d < bd) { bd = d; best = i; }
  });
  return best;
}
const pullPx = () => Math.max(140, innerHeight * 0.28);   // drag distance for a full pull
const pullScroll = () => (hero.offsetHeight - innerHeight) * (TL.pull[1] + 0.01);
canvas.addEventListener('pointerdown', e => {
  if (!scrub || shown > TL.pull[1] + 0.02) return;
  const hi = hitHandle(e);
  if (hi < 0) return;
  if (shown < TL.emerge[0]) setFlavor(flavorFor(hi), true);
  drag = { y: e.clientY, start: scrollY, id: e.pointerId };
  canvas.setPointerCapture(e.pointerId);
  root.classList.add('grabbing');
  e.preventDefault();
});
canvas.addEventListener('pointermove', e => {
  if (drag) {
    const dy = Math.max(0, e.clientY - drag.y);
    const goal = drag.start + dy / pullPx() * (pullScroll() - drag.start + hero.offsetTop);
    scrollTo(0, Math.min(goal, hero.offsetTop + pullScroll()));
    return;
  }
  if (e.pointerType === 'mouse' && scrub && shown < TL.pull[1]) {
    const over = hitHandle(e) >= 0;
    root.classList.toggle('grab', over);
  }
}, { passive: true });
const endDrag = e => {
  if (!drag) return;
  // a decisive pull (past ~45%) finishes itself; otherwise the handle eases back up
  const done = (scrollY - hero.offsetTop) / pullScroll() > 0.45;
  scrollTo({ top: done ? hero.offsetTop + pullScroll() * 1.25 : drag.start, behavior: 'smooth' });
  drag = null;
  root.classList.remove('grabbing', 'grab');
  try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* already released */ }
};
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);

// ------------------------------------------------------------------ sizing, modes
function resize() {
  if (!renderer) return;
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setPixelRatio(dpr());
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  wake();
}
addEventListener('resize', resize);

function applyMode() {
  if (RM.matches) {
    // one still, finished frame; no scrub
    scrub = false;
    removeEventListener('scroll', onScroll);
    target = shown = 1;
    loadK = 1;
    updateBands(1, true);
    if (machine) { pose(1); renderer.render(scene, camera); }
  } else {
    scrub = true;
    addEventListener('scroll', onScroll, { passive: true });
    bands.forEach(b => { b.op = -1; b.k = -1; });
    target = heroProgress();
    shown = target;
    wake();
  }
}
RM.addEventListener('change', applyMode);
if (!renderer) updateBands(1, true); else applyMode();

const nav = $('.nav');
new IntersectionObserver(([e]) => {
  heroOn = e.isIntersecting;
  nav.classList.toggle('solid', !heroOn);
  if (heroOn) wake();
}).observe(hero);

document.addEventListener('visibilitychange', () => document.body.classList.toggle('paused', document.hidden));

// test hook: jump straight to a progress value (used by the screenshot harness)
window.__ilios = { scene, camera, THREE, render: () => renderer.render(scene, camera), setP(p) { target = shown = p; loadK = 1; frame(p); }, cam: () => ({ tgt: camTgt.toArray(), dir: camera.getWorldDirection(new THREE.Vector3()).toArray(), pos: camera.position.toArray(), fov: camera.fov, near: camera.near, cup: cup && cup.position.toArray() }), setFlavor };

// section entrances
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  e.target.classList.add('in');
  setTimeout(() => e.target.classList.add('settled'), 1400);
  io.unobserve(e.target);
}), { threshold: 0.18 });
document.querySelectorAll('.io').forEach(s => io.observe(s));

// ------------------------------------------------------------------ the topping bar
// Lazy: nothing for it (topping models, the bar's own scene) loads until the section is near the viewport. It uses the
// swirl you just poured (same simulation, same flavour material) and the same cup.
function setupToppings() {
  const section = $('#bar'), el = $('#barcanvas');
  if (!section || !el) return;
  const intro = $('#barintro'), line = [...document.querySelectorAll('#barline li')], end = $('#barend');
  const list = $('#barlist'), tip = $('#bartip'), stageEl = $('#barstage'), keys = $('#barkeys');
  let bar = null, started = false;
  const progress = () => { const r = section.getBoundingClientRect(); return clamp(-r.top / Math.max(1, r.height - innerHeight)); };
  // phones: you walk the bar by swiping sideways, not by scrolling down (the section is one screen tall)
  const SW = matchMedia('(pointer: coarse), (max-width: 820px)');
  const ui = {
    onSwipe() { stageEl.classList.add('swiped'); },
    onProgress(p, zone) {
      intro.classList.toggle('away', p > (SW.matches ? 0.008 : 0.035));
      line.forEach(li => li.classList.toggle('on', li.dataset.zone === zone));
      end.classList.toggle('on', zone === 'pay');
    },
    onChange(defs) {
      list.innerHTML = defs.length ? defs.map(d => `<li>${d.label}</li>`).join('') : '<li class="empty">Just the froyo so far</li>';
      list.scrollTop = list.scrollHeight;
      $('#barundo').disabled = $('#barclear').disabled = !defs.length;
    },
    onHover(def, e) {
      if (!def) { tip.classList.remove('on'); return; }
      const r = stageEl.getBoundingClientRect();
      tip.innerHTML = `${def.label}<small>${def.note ? def.note + ' · ' : ''}${def.zone === 'warm' ? 'Served warm' : 'Tap to add'}</small>`;
      tip.style.left = (e.clientX - r.left) + 'px';
      tip.style.top = (e.clientY - r.top) + 'px';
      tip.classList.add('on');
    },
  };
  root.classList.toggle('bar-swipe', SW.matches);
  const start = async () => {
    if (started || !rec) return;
    started = true;
    try {
      // the modelled pieces (source/toppings) and their settled heaps; the older procedural pieces fill in what is not modelled yet
      const [tm, heaps, mod] = await Promise.all([
        load('assets/models/toppings-v2.glb').catch(() => null),
        fetch('assets/bar-heaps.json').then(r => (r.ok ? r.json() : {})).catch(() => ({})),
        import('./bar.js'),
      ]);
      const tg = tm ? null : await load('assets/models/toppings.glb');     // the older, simpler pieces, only if the modelled ones did not load
      bar = await mod.initBar({ canvas: el, froyoRec: rec, froyoMaterial: froyoMat, cupMats, toppingsScene: tg && tg.scene, modelledScene: tm && tm.scene, heaps: tm ? heaps : {}, roomScene: room, dpr, reduced: RM.matches, ui });
      root.classList.add('bar-on');
      // keyboard: every topping is a button too
      keys.innerHTML = mod.BAR.map(d => `<li><button type="button" data-key="${d.key}">Add ${d.label}</button></li>`).join('');
      keys.addEventListener('click', e => { const b = e.target.closest('button'); if (b) bar.add(b.dataset.key); });
      $('#barundo').addEventListener('click', () => bar.undo());
      $('#barclear').addEventListener('click', () => bar.clear());
      const onScroll = () => { if (!SW.matches) bar.setProgress(progress()); };
      addEventListener('scroll', onScroll, { passive: true });
      const mode = () => { root.classList.toggle('bar-swipe', SW.matches); bar.setSwipe(SW.matches); if (!SW.matches) onScroll(); };
      SW.addEventListener('change', mode);
      mode();
      // the stations in the strip are buttons too
      line.forEach(li => li.addEventListener('click', () => bar.goTo(li.dataset.zone)));
      window.__bar = bar;
    } catch (e) {
      console.warn('Topping bar unavailable', e);
      barFallback();
    }
  };
  new IntersectionObserver(([e]) => { if (e.isIntersecting) start(); }, { rootMargin: '1200px 0px' }).observe(section);
  window.__startToppings = start;
}

// without WebGL: the bar as a plain list, in the shop's order
function barFallback() {
  root.classList.add('bar-off');
  import('./bar-list.js').then(m => { $('#barlistall').innerHTML = m.listHTML(); }).catch(() => {});
}

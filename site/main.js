// Ilios Froyo: the pour.
// Built on the shop's real station: a three-handle twist machine set into a limewash niche.
// Pick a handle (Sweet Harbor Coffee, twist, Organic Vanilla Bean), pull it, and the cup fills.
// One live three.js scene, scrubbed by scroll:
//   pull the handle -> a ribbon of froyo leaves the star spout -> the camera
//   follows it down -> the cup circles under the spout while the swirl builds
//   -> the tail breaks off, the tip curls, the handle springs back -> settle.
// The swirl is a single extruded rope (from Blender) with a `_reveal` 0..1
// attribute along its length; a shader discards everything past the pour
// front. The falling stream is rebuilt on the CPU each frame.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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
  emerge: [0.15, 0.30],     // ribbon leaves the spout and falls to the cup
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
  $('#poster').style.backgroundImage = "url('assets/img/machine.jpg')";
  updateBands(1, true);
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

// ------------------------------------------------------------------ the swirl reveal shader
const uReveal = { value: 0 };
const uFillY = { value: 0 };
// flavours, in handle order (left, centre, right), as on the shop's machine sign
const FLAVORS = [
  { name: 'Sweet Harbor Coffee', a: '#b98a5c', b: '#b98a5c', twist: 0, speckA: 0, speckB: 0 },
  { name: 'Twist', a: '#b98a5c', b: '#f2e8cf', twist: 1, speckA: 0, speckB: 0.8 },
  { name: 'Organic Vanilla Bean', a: '#f2e8cf', b: '#f2e8cf', twist: 0, speckA: 1, speckB: 1 },
];
const U = {
  uColA: { value: new THREE.Color(FLAVORS[1].a) }, uColB: { value: new THREE.Color(FLAVORS[1].b) },
  uTwist: { value: 1 }, uSpeckA: { value: 0 }, uSpeckB: { value: 0.8 },
};
const FLAVOR_GLSL = `
  {
    float phi = vFlavUv.y / 1.3980 * 6.2831853;
    float along = vFlavUv.x * 0.04;
    float band = fract((phi + along * 9.0) / 6.2831853 * 3.0);
    float m = uTwist * smoothstep(0.02, 0.10, band) * (1.0 - smoothstep(0.48, 0.56, band));
    vec3 fc = mix(uColA, uColB, m);
    vec2 cell = floor(vFlavUv * vec2(240.0, 100.0));
    float h = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
    float sp = mix(uSpeckA, uSpeckB, m) * step(0.986, h);
    fc = mix(fc, vec3(0.05, 0.036, 0.028), sp * 0.9);
    diffuseColor.rgb = fc;
  }`;
function froyoPatch(mat, mode) {
  mat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U, { uReveal, uFillY });
    let vs = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vFlavUv;' +
      (mode === 'reveal' ? '\nattribute float _reveal;\nvarying float vReveal;' : '') +
      (mode === 'fill' ? '\nvarying float vWorldY;' : ''));
    vs = vs.replace('#include <begin_vertex>', '#include <begin_vertex>\nvFlavUv = uv;' +
      (mode === 'reveal' ? '\nvReveal = _reveal;' : '') +
      (mode === 'fill' ? '\nvWorldY = (modelMatrix * vec4(transformed, 1.0)).y;' : ''));
    let fs = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec2 vFlavUv;\n' +
      'uniform vec3 uColA; uniform vec3 uColB; uniform float uTwist; uniform float uSpeckA; uniform float uSpeckB;' +
      (mode === 'reveal' ? '\nuniform float uReveal;\nvarying float vReveal;' : '') +
      (mode === 'fill' ? '\nuniform float uFillY;\nvarying float vWorldY;' : ''));
    if (mode === 'reveal') fs = fs.replace('void main() {', 'void main() {\n  if (vReveal > uReveal) discard;');
    if (mode === 'fill') fs = fs.replace('void main() {', 'void main() {\n  if (vWorldY > uFillY) discard;');
    fs = fs.replace('#include <color_fragment>', '#include <color_fragment>' + FLAVOR_GLSL);
    sh.vertexShader = vs;
    sh.fragmentShader = fs;
  };
  mat.customProgramCacheKey = () => 'froyo-' + mode;
}
// the swirl's shadow must follow the pour too
function revealDepthPatch(mat) {
  mat.onBeforeCompile = sh => {
    sh.uniforms.uReveal = uReveal;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float _reveal;\nvarying float vReveal;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvReveal = _reveal;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uReveal;\nvarying float vReveal;')
      .replace('void main() {', 'void main() {\n  if (vReveal > uReveal) discard;');
  };
  mat.customProgramCacheKey = () => 'reveal-depth';
}

// ------------------------------------------------------------------ flavour choice
let sel = 1;            // 0 left (coffee), 1 centre (twist), 2 right (vanilla bean)
const chips = [...document.querySelectorAll('[data-flavor]')];
const flavorNames = [...document.querySelectorAll('[data-flavor-name]')];
function setFlavor(i, fromUser) {
  if (scrub && shown > TL.emerge[0] && fromUser) return;   // the cup is already under a spout
  sel = i;
  const f = FLAVORS[i];
  U.uColA.value.set(f.a);
  U.uColB.value.set(f.b);
  U.uTwist.value = f.twist;
  U.uSpeckA.value = f.speckA;
  U.uSpeckB.value = f.speckB;
  chips.forEach(c => c.setAttribute('aria-pressed', String(+c.dataset.flavor === i)));
  flavorNames.forEach(n => { n.textContent = f.name; });
  wake();
}
chips.forEach(c => c.addEventListener('click', () => setFlavor(+c.dataset.flavor, true)));

// ------------------------------------------------------------------ load
const manager = new THREE.LoadingManager();
manager.onProgress = (_u, done, total) => {
  ring.style.strokeDashoffset = String(Math.round(126 * (1 - done / Math.max(total, 1))));
};
const loader = new GLTFLoader(manager).setMeshoptDecoder(MeshoptDecoder);
const load = url => new Promise((res, rej) => loader.load(url, res, undefined, rej));

let machine, room, handles = [], balls = [], cup, swirl, core, path, stream, froyoMat;
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
  room.traverse(o => {
    if (!o.isMesh) return;
    o.receiveShadow = true;
    o.castShadow = !o.material.transparent;
    if (o.material.transparent) { o.material.depthWrite = false; o.material.polygonOffset = true; o.material.polygonOffsetFactor = -2; }
    if (o.material.map) o.material.map.anisotropy = 8;
  });
  cup = gc.scene;
  path = pj;
  machine.traverse(o => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      if (o.material.transparent) { o.material.depthWrite = false; o.castShadow = false; }
      if (o.material.map) o.material.map.anisotropy = 8;
    }
  });
  handles = path.handles.map(n => machine.getObjectByName(n));
  balls = path.handles.map(n => machine.getObjectByName(n + 'Ball'));
  cup.traverse(o => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    if (o.material.transparent) {
      o.material.depthWrite = false;
      o.material.polygonOffset = true;
      o.material.polygonOffsetFactor = -2;
      o.castShadow = false;
    }
    if (o.material.map) o.material.map.anisotropy = 8;
  });
  swirl = cup.getObjectByName('Swirl');
  core = cup.getObjectByName('SwirlCore');
  // the fill inside the cup is clipped by a rising level instead of scaled
  // (squashing a flared shape would push its wide top through the narrower wall below)
  froyoMat = swirl.material;
  core.material = froyoMat.clone();
  core.material.side = THREE.DoubleSide;
  core.castShadow = false;
  froyoPatch(core.material, 'fill');
  swirl.material = froyoMat.clone();
  froyoPatch(swirl.material, 'reveal');
  const depth = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  revealDepthPatch(depth);
  swirl.customDepthMaterial = depth;

  nozzles = path.nozzlesMachine.map(a => new THREE.Vector3().fromArray(a));
  cupBases = path.cupBasesMachine.map(a => new THREE.Vector3().fromArray(a));
  cup.position.copy(cupBases[1]);
  scene.add(room, machine, cup);

  const smat = froyoMat.clone();
  froyoPatch(smat, 'plain');
  stream = makeStream(smat);
  scene.add(stream.mesh);

  initSpin(gc);
  root.classList.add('ready');
  resize();
  applyMode();
  wake();
}).catch(fail);

// ------------------------------------------------------------------ swirl path helpers
const _a = new THREE.Vector3(), _b = new THREE.Vector3();
function pathAt(s, out = new THREE.Vector3()) {
  const P = path.path;
  if (s <= P[0].s) return out.fromArray(P[0].p);
  if (s >= P[P.length - 1].s) return out.fromArray(P[P.length - 1].p);
  let lo = 0, hi = P.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (P[m].s < s) lo = m; else hi = m; }
  const t = (s - P[lo].s) / (P[hi].s - P[lo].s);
  return out.fromArray(P[lo].p).lerp(_a.fromArray(P[hi].p), t);
}
function tangentAt(s, out = new THREE.Vector3()) {
  pathAt(Math.min(1, s + 0.003), out);
  pathAt(Math.max(0, s - 0.003), _b);
  return out.sub(_b).normalize();
}

// ------------------------------------------------------------------ the falling stream
// A ridged rope, rebuilt each frame along a cubic bezier from the spout to the pour front.
function makeStream(mat) {
  const NS = 110, MS = 40;
  const A0 = 0.0089;
  const verts = (NS + 1) * (MS + 1) + 2;
  const pos = new Float32Array(verts * 3);
  const uv = new Float32Array(verts * 2);
  const idx = [];
  for (let i = 0; i < NS; i++) for (let j = 0; j < MS; j++) {
    const a = i * (MS + 1) + j, b = a + MS + 1;
    idx.push(a, b, a + 1, a + 1, b, b + 1);
  }
  const top = (NS + 1) * (MS + 1), bot = top + 1;
  for (let j = 0; j < MS; j++) {
    idx.push(top, j + 1, j);
    const r = NS * (MS + 1);
    idx.push(r + j, r + j + 1, bot);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2).setUsage(THREE.DynamicDrawUsage));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.frustumCulled = false;
  mesh.visible = false;

  const P = [], T = [], N = [], B = [], L = [];
  for (let i = 0; i <= NS; i++) { P.push(new THREE.Vector3()); T.push(new THREE.Vector3()); N.push(new THREE.Vector3()); B.push(new THREE.Vector3()); L.push(0); }
  const p0 = new THREE.Vector3(), p1 = new THREE.Vector3(), p2 = new THREE.Vector3(), p3 = new THREE.Vector3();
  const tmp = new THREE.Vector3(), v1 = new THREE.Vector3(), rL = new THREE.Vector3(), tL = new THREE.Vector3(), v2 = new THREE.Vector3();

  function bez(t, out) {
    const u = 1 - t;
    return out.set(0, 0, 0)
      .addScaledVector(p0, u * u * u).addScaledVector(p1, 3 * u * u * t)
      .addScaledVector(p2, 3 * u * t * t).addScaledVector(p3, t * t * t);
  }

  // a, b: bezier control points set by the caller; capTop/capBot: rounded ends; flow: material moved (m)
  function update({ from, to, toDir, capTop, capBot, flow }) {
    const len = from.distanceTo(to);
    p0.copy(from);
    p3.copy(to);
    p1.copy(from).y -= len * 0.42;
    if (toDir) {
      // land and bend into the laid rope
      p2.copy(to).addScaledVector(toDir, -0.006);
      p2.y += Math.min(0.022, len * 0.45);
    } else {
      p2.copy(to);
      p2.y += len * 0.2;
    }
    for (let i = 0; i <= NS; i++) bez(i / NS, P[i]);
    let acc = 0;
    for (let i = 0; i <= NS; i++) {
      if (i) acc += P[i].distanceTo(P[i - 1]);
      L[i] = acc;
      tmp.copy(P[Math.min(NS, i + 1)]).sub(P[Math.max(0, i - 1)]);
      T[i].copy(tmp.lengthSq() > 1e-14 ? tmp.normalize() : T[Math.max(0, i - 1)].lengthSq() ? T[Math.max(0, i - 1)] : tmp.set(0, -1, 0));
    }
    // rotation-minimising frames (double reflection)
    N[0].set(1, 0, 0).addScaledVector(T[0], -T[0].x).normalize();
    for (let i = 0; i < NS; i++) {
      v1.copy(P[i + 1]).sub(P[i]);
      const c1 = v1.dot(v1) || 1e-12;
      rL.copy(N[i]).addScaledVector(v1, -2 / c1 * v1.dot(N[i]));
      tL.copy(T[i]).addScaledVector(v1, -2 / c1 * v1.dot(T[i]));
      v2.copy(T[i + 1]).sub(tL);
      const c2 = v2.dot(v2);
      N[i + 1].copy(c2 > 1e-12 ? rL.addScaledVector(v2, -2 / c2 * v2.dot(rL)) : rL).normalize();
    }
    for (let i = 0; i <= NS; i++) B[i].crossVectors(T[i], N[i]);
    const total = acc;
    const circ = 2 * Math.PI * A0;
    let k = 0, q = 0;
    for (let i = 0; i <= NS; i++) {
      let r = A0;
      const dTop = L[i], dBot = total - L[i];
      if (capTop) r *= Math.sqrt(clamp(1 - Math.pow(clamp(1 - dTop / (A0 * 1.4)), 2)));
      if (capBot) r *= Math.sqrt(clamp(1 - Math.pow(clamp(1 - dBot / (A0 * 1.1)), 2)));
      // slight neck-down as it stretches under gravity, fattening again where it lands
      r *= 1 - 0.07 * smooth(0.0, 0.08, dTop) * (1 - smooth(0.0, 0.03, dBot));
      const tw = (dTop - flow) * 9.0;
      for (let j = 0; j <= MS; j++) {
        const phi = j / MS * Math.PI * 2;
        const ridge = 1 + 0.065 * Math.cos(6 * (phi + tw)) - 0.015 * Math.cos(12 * (phi + tw));
        const c = Math.cos(phi) * r * ridge, s = Math.sin(phi) * r * ridge;
        pos[k++] = P[i].x + N[i].x * c + B[i].x * s;
        pos[k++] = P[i].y + N[i].y * c + B[i].y * s;
        pos[k++] = P[i].z + N[i].z * c + B[i].z * s;
        uv[q++] = (dTop - flow) / 0.04;
        uv[q++] = j / MS * circ / 0.04;
      }
    }
    // end caps
    tmp.copy(P[0]);
    pos[k++] = tmp.x; pos[k++] = tmp.y; pos[k++] = tmp.z;
    tmp.copy(P[NS]);
    pos[k++] = tmp.x; pos[k++] = tmp.y; pos[k++] = tmp.z;
    geo.attributes.position.needsUpdate = true;
    geo.attributes.uv.needsUpdate = true;
    geo.computeVertexNormals();
    // weld the uv seam normals
    const nrm = geo.attributes.normal.array;
    for (let i = 0; i <= NS; i++) {
      const a = (i * (MS + 1)) * 3, b = (i * (MS + 1) + MS) * 3;
      for (let c = 0; c < 3; c++) { const m = (nrm[a + c] + nrm[b + c]) / 2; nrm[a + c] = nrm[b + c] = m; }
    }
    geo.attributes.normal.needsUpdate = true;
  }
  return { mesh, update, A0 };
}

// ------------------------------------------------------------------ camera choreography
// Keys are [p, camera position, look target] in machine space (metres, Y up, front = +Z).
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const CAM_KEYS = [
  [0.000, V(0.16, 0.64, 3.55), V(0.05, 0.56, 0.20)],
  [0.045, V(0.13, 0.60, 2.55), V(0.00, 0.52, 0.20)],
  [0.140, V(0.21, 0.56, 1.12), V(0.00, 0.49, 0.24)],
  [0.210, V(0.13, 0.40, 0.66), V(0.00, 0.355, 0.21)],
  [0.265, V(0.14, 0.27, 0.68), V(0.00, 0.23, 0.21)],
  [0.315, V(0.12, 0.245, 0.68), V(0.00, 0.12, 0.21)],
];
// during the pour the camera orbits the spout axis and rises with the swirl
for (let i = 0; i <= 6; i++) {
  const t = i / 6;
  const p = 0.36 + t * 0.44;
  const ang = THREE.MathUtils.degToRad(16 - 58 * t);
  const rad = 0.345 - 0.045 * Math.sin(t * Math.PI);
  const y = 0.215 + 0.085 * t;
  CAM_KEYS.push([p, V(Math.sin(ang) * rad, y, 0.212 + Math.cos(ang) * rad), V(0, 0.112 + 0.062 * t, 0.212)]);
}
CAM_KEYS.push([0.865, V(0.02, 0.29, 0.80), V(-0.02, 0.17, 0.24)]);
CAM_KEYS.push([0.970, V(0.42, 0.31, 1.02), V(-0.10, 0.175, 0.28)]);
CAM_KEYS.push([1.000, V(0.425, 0.312, 1.03), V(-0.102, 0.175, 0.28)]);

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
const D = new THREE.Vector3(), Dt = new THREE.Vector3(), Dw = new THREE.Vector3();
const tipW = new THREE.Vector3(), from = new THREE.Vector3(), _cb = new THREE.Vector3();

function pose(p) {
  if (!machine) return;
  // handle: pulled, held through the pour, released
  const pull = easeInOut(smooth(TL.pull[0], TL.pull[1], p)) * (1 - easeInOut(smooth(TL.release[0], TL.release[0] + 0.035, p)));
  handles.forEach((h, i) => { h.rotation.x = i === sel ? pull * path.handlePullRadians : 0; });
  const nozzle = nozzles[sel];
  // the empty cup waits under the twist spout, then slides under the chosen one
  const slide = easeInOut(smooth(0.03, 0.12, p));
  const cupBase = _cb.copy(cupBases[1]).lerp(cupBases[sel], slide);

  // pour front along the swirl (0..1)
  const pr = clamp((p - TL.pour[0]) / (TL.pour[1] - TL.pour[0]));
  const reveal = pr <= 0 ? 0 : 0.002 + 0.998 * pr;
  uReveal.value = p >= TL.pour[1] ? 1.01 : reveal;

  // the cup circles under the spout so the pour front is always straight below it
  pathAt(Math.min(reveal, 0.999), D);
  tangentAt(Math.min(reveal, 0.999), Dt);
  const follow = 1 - smooth(TL.release[0] + 0.01, TL.settle[0] + 0.05, p);
  cup.position.set(cupBase.x - D.x * follow, cupBase.y, cupBase.z - D.z * follow);
  // the hidden fill rises with the coils inside the cup
  const fill = clamp(reveal / path.insideRevealEnd);
  uFillY.value = cup.position.y + 0.0068 + fill * 0.0505;
  core.visible = fill > 0.002;
  swirl.visible = reveal > 0;

  // stream
  const emerge = smooth(TL.emerge[0], TL.emerge[1], p);
  Dw.copy(D).add(cup.position);
  const flow = (emerge * 0.22 + pr * path.swirlLength);
  if (p < TL.emerge[0] || p > TL.release[1]) {
    stream.mesh.visible = false;
  } else if (p < TL.pour[0]) {
    // falling: gravity accelerates the front (t^2), rounded nub at the bottom
    const fall = Math.pow(emerge, 1.6);
    from.copy(nozzle);
    tipW.copy(nozzle);
    tipW.y = THREE.MathUtils.lerp(nozzle.y - 0.003, Dw.y + 0.004, fall);
    stream.mesh.visible = true;
    stream.update({ from, to: tipW, toDir: null, capTop: false, capBot: true, flow });
  } else if (p < TL.pour[1]) {
    from.copy(nozzle);
    stream.mesh.visible = true;
    stream.update({ from, to: Dw, toDir: Dt, capTop: false, capBot: false, flow });
  } else {
    // released: the tail leaves the spout and drops onto the tip
    const t = easeInOut(clamp((p - TL.release[0]) / (TL.release[1] - TL.release[0])));
    pathAt(0.999, D);
    tangentAt(0.999, Dt);
    Dw.copy(D).add(cup.position);
    from.copy(nozzle);
    from.y = THREE.MathUtils.lerp(nozzle.y, Dw.y + 0.006, t);
    stream.mesh.visible = from.y - Dw.y > 0.003;
    if (stream.mesh.visible) stream.update({ from, to: Dw, toDir: Dt, capTop: true, capBot: false, flow: flow + t * 0.1 });
  }

  // camera
  camAt(p, camPos, camTgt);
  // once a flavour is chosen the whole close-up follows its spout
  const sx = nozzles[sel].x * smooth(0.05, 0.14, p);
  camPos.x += sx;
  camTgt.x += sx;
  fitPortrait(camPos, camTgt, p);
  camera.position.copy(camPos);
  camera.lookAt(camTgt);
  // narrow the lens a touch for the close moments
  const close = smooth(0.12, 0.24, p) * (1 - smooth(0.82, 0.95, p));
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
  if (shown < TL.emerge[0]) setFlavor(hi, true);
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
window.__ilios = { scene, render: () => renderer.render(scene, camera), setP(p) { target = shown = p; loadK = 1; frame(p); }, cam: () => ({ tgt: camTgt.toArray(), dir: camera.getWorldDirection(new THREE.Vector3()).toArray(), pos: camera.position.toArray(), fov: camera.fov, near: camera.near, stream: stream && stream.mesh.visible, cup: cup && cup.position.toArray() }), setFlavor };

// section entrances
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  e.target.classList.add('in');
  setTimeout(() => e.target.classList.add('settled'), 1400);
  io.unobserve(e.target);
}), { threshold: 0.18 });
document.querySelectorAll('.io').forEach(s => io.observe(s));

// ------------------------------------------------------------------ the spin viewer (same cup model)
function initSpin(gltf) {
  const el = $('#spin');
  if (!el || !renderer) return;
  let r2;
  try { r2 = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true }); } catch (e) { return; }
  r2.setPixelRatio(dpr());
  r2.outputColorSpace = THREE.SRGBColorSpace;
  r2.toneMapping = THREE.AgXToneMapping;
  r2.toneMappingExposure = 1.15;
  r2.shadowMap.enabled = true;
  r2.shadowMap.type = THREE.PCFSoftShadowMap;
  const s2 = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(r2);
  s2.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  s2.environmentIntensity = 0.7;
  const c2 = new THREE.PerspectiveCamera(24, 1, 0.01, 10);
  c2.position.set(0.16, 0.2, 0.42);
  const model = gltf.scene.clone(true);
  model.position.set(0, 0, 0);
  // the hero scene patches the froyo materials (pour reveal, fill clip); the viewer shows the finished cup
  const plain = froyoMat.clone();
  froyoPatch(plain, 'plain');
  model.traverse(o => {
    if (!o.isMesh) return;
    o.castShadow = !o.material.transparent;
    o.receiveShadow = true;
    if (o.name === 'Swirl' || o.name === 'SwirlCore') { o.material = plain; o.customDepthMaterial = undefined; o.visible = true; }
  });
  s2.add(model);
  const k2 = new THREE.DirectionalLight('#fff0db', 2.2);
  k2.position.set(-0.5, 0.8, 0.6);
  k2.castShadow = true;
  k2.shadow.mapSize.set(1024, 1024);
  Object.assign(k2.shadow.camera, { left: -0.2, right: 0.2, top: 0.25, bottom: -0.1, near: 0.1, far: 2 });
  k2.shadow.bias = -0.0004;
  k2.shadow.radius = 6;
  s2.add(k2, new THREE.HemisphereLight('#fff7ec', '#a59b8e', 0.6));
  const floor = new THREE.Mesh(new THREE.CircleGeometry(0.4, 64), new THREE.ShadowMaterial({ opacity: 0.22 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  s2.add(floor);
  const ctl = new OrbitControls(c2, el);
  ctl.target.set(0, 0.068, 0);
  ctl.enableDamping = true;
  ctl.enablePan = false;
  ctl.enableZoom = false;
  ctl.minPolarAngle = 0.35;
  ctl.maxPolarAngle = 1.5;
  ctl.autoRotate = !RM.matches;
  ctl.autoRotateSpeed = 1.1;
  let visible = false, raf2 = null;
  const size = () => {
    const w = el.clientWidth, h = el.clientHeight;
    r2.setSize(w, h, false);
    c2.aspect = w / h;
    c2.updateProjectionMatrix();
  };
  const loop = () => {
    ctl.update();
    r2.render(s2, c2);
    raf2 = visible && !document.hidden ? requestAnimationFrame(loop) : null;
  };
  new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && raf2 === null) { size(); raf2 = requestAnimationFrame(loop); }
  }).observe(el);
  addEventListener('resize', size);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && visible && raf2 === null) raf2 = requestAnimationFrame(loop); });
  size();
}

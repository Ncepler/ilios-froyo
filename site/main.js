// Ilios Froyo: the pour.
// Built on the shop's real station: a three-handle twist machine set into a limewash niche.
// Pick a handle (Sweet Harbor Coffee, twist, Organic Vanilla Bean), pull it, and the cup fills.
// One live three.js scene, scrubbed by scroll:
//   pull the handle -> a ribbon of froyo leaves the star spout -> the camera
//   follows it down -> the cup circles under the spout while the swirl builds
//   -> the tail breaks off, the tip curls, the handle springs back -> settle.
// The froyo is a viscous-rope simulation (source/sim.py): extruded from the spout, stretched thin by
// gravity on the way down, coiling and piling in the cup as the server circles it, setting where it
// lands. The page replays the baked simulation frame by frame and skins it as froyo.

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
const loadBin = url => fetch(url).then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.arrayBuffer(); });

let machine, room, handles = [], balls = [], cup, swirl, path, rope, sim, froyoMat;
let nozzles = [], cupBases = [];
const knobWorld = new THREE.Vector3();

Promise.all([
  load('assets/models/ilios-softserve-machine.glb'),
  load('assets/models/ilios-froyo-cup.glb'),
  load('assets/models/ilios-room.glb'),
  fetch('assets/pour-path.json').then(r => r.json()),
  fetch('assets/pour-sim.json').then(r => r.json()),
  loadBin('assets/pour-sim.bin'),
]).then(([gm, gc, gr, pj, sj, sb]) => {
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
  // the finished swirl in the cup model is for the spin viewer; the hero pours a live rope instead
  swirl = cup.getObjectByName('Swirl');
  froyoMat = swirl.material;
  swirl.visible = false;
  sim = prepSim(sj, sb);

  nozzles = path.nozzlesMachine.map(a => new THREE.Vector3().fromArray(a));
  cupBases = path.cupBasesMachine.map(a => new THREE.Vector3().fromArray(a));
  cup.position.copy(cupBases[1]);
  scene.add(room, machine, cup);

  const rmat = froyoMat.clone();
  froyoPatch(rmat, 'plain');
  rope = makeRope(rmat, sim);
  cup.add(rope.mesh);                 // the simulation is in the cup's own frame

  initSpin(gc);
  root.classList.add('ready');
  resize();
  applyMode();
  wake();
}).catch(fail);

// ------------------------------------------------------------------ the pour (a simulated rope, played back)
// sim.py runs a viscous-rope simulation: extrusion from the spout, gravity stretching and thinning the
// falling column, bending, collisions with the cup and with itself, and yield stress (it sets where it
// lands). It saves every particle's path until it sets. Here we replay any frame and skin it as froyo.
function prepSim(meta, buf) {
  const raw = new Int16Array(buf);
  const pos = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i++) pos[i] = raw[i] / meta.scale;
  return { ...meta, pos, detach: Math.round((meta.emitEnd + 0.08) * meta.fps) };
}
function particleAt(S, i, f, out) {
  const k = Math.max(0, Math.min(Math.min(f, S.settle[i]) - S.emit[i], S.length[i] - 1));
  const o = (S.offset[i] + k) * 3;
  out[0] = S.pos[o]; out[1] = S.pos[o + 1]; out[2] = S.pos[o + 2];
}

function makeRope(mat, S) {
  const SUB = 3, M = 40;
  const A = S.radius, Dsp = S.spacing;
  const maxRings = (S.count - 1) * SUB + 1;
  const vcount = maxRings * (M + 1);
  const pos = new Float32Array(vcount * 3), nrm = new Float32Array(vcount * 3), uv = new Float32Array(vcount * 2);
  const idx = new Uint32Array((maxRings - 1) * M * 6);
  let q = 0;
  for (let i = 0; i < maxRings - 1; i++) for (let j = 0; j < M; j++) {
    const a = i * (M + 1) + j, b = a + M + 1;
    idx[q++] = a; idx[q++] = b; idx[q++] = a + 1; idx[q++] = a + 1; idx[q++] = b; idx[q++] = b + 1;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('normal', new THREE.BufferAttribute(nrm, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2).setUsage(THREE.DynamicDrawUsage));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.setDrawRange(0, 0);
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.frustumCulled = false;

  const P = new Float32Array(S.count * 3), P1 = new Float32Array(3), P2 = new Float32Array(3);
  const LL = new Float32Array(S.count), LS = new Float32Array(S.count);
  const C = new Float32Array(maxRings * 3), T = new Float32Array(maxRings * 3), Rr = new Float32Array(maxRings), Sm = new Float32Array(maxRings);
  const N = new Float32Array(3), B = new Float32Array(3);
  const circ = 2 * Math.PI * A;
  const cosT = new Float32Array(M + 1), sinT = new Float32Array(M + 1);
  for (let j = 0; j <= M; j++) { cosT[j] = Math.cos(j / M * Math.PI * 2); sinT[j] = Math.sin(j / M * Math.PI * 2); }

  function update(fr) {
    const f0 = Math.floor(fr), t = fr - f0;
    let n = 0;
    while (n < S.count && S.emit[n] <= f0) n++;
    if (n < 2) { geo.setDrawRange(0, 0); mesh.visible = false; return; }
    mesh.visible = true;
    for (let i = 0; i < n; i++) {
      particleAt(S, i, f0, P1);
      particleAt(S, i, f0 + 1, P2);
      P[i * 3] = P1[0] + (P2[0] - P1[0]) * t;
      P[i * 3 + 1] = P1[1] + (P2[1] - P1[1]) * t;
      P[i * 3 + 2] = P1[2] + (P2[2] - P1[2]) * t;
    }
    // link lengths, smoothed over a few links (the sim's spacing jitters slightly link to link)
    for (let i = 0; i < n - 1; i++) {
      LL[i] = Math.hypot(P[i * 3 + 3] - P[i * 3], P[i * 3 + 4] - P[i * 3 + 1], P[i * 3 + 5] - P[i * 3 + 2]);
    }
    for (let i = 0; i < n - 1; i++) {
      let s = 0, c = 0;
      for (let k = Math.max(0, i - 4); k <= Math.min(n - 2, i + 4); k++) { s += LL[k]; c++; }
      LS[i] = s / c;
    }
    // Catmull-Rom through the particles, SUB samples per link
    let r = 0;
    for (let i = 0; i < n - 1; i++) {
      const i0 = Math.max(0, i - 1) * 3, i1 = i * 3, i2 = (i + 1) * 3, i3 = Math.min(n - 1, i + 2) * 3;
      // volume conservation: a stretched stretch of rope is thinner, a squashed one fatter
      const ra = A * Math.min(1.2, Math.max(0.6, Math.sqrt(Dsp / Math.max(LS[i], 1e-5))));
      const rb = A * Math.min(1.2, Math.max(0.6, Math.sqrt(Dsp / Math.max(LS[Math.min(n - 2, i + 1)], 1e-5))));
      for (let s = 0; s < SUB; s++) {
        const u = s / SUB, u2 = u * u, u3 = u2 * u;
        for (let c = 0; c < 3; c++) {
          const p0 = P[i0 + c], p1 = P[i1 + c], p2 = P[i2 + c], p3 = P[i3 + c];
          C[r * 3 + c] = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3);
        }
        Rr[r] = ra + (rb - ra) * u;
        Sm[r] = (i + u) * Dsp;
        r++;
      }
    }
    C[r * 3] = P[(n - 1) * 3]; C[r * 3 + 1] = P[(n - 1) * 3 + 1]; C[r * 3 + 2] = P[(n - 1) * 3 + 2];
    Rr[r] = Rr[r - 1]; Sm[r] = (n - 1) * Dsp; r++;
    const rings = r;
    // smooth the radius a touch and taper the tail once it has broken off the spout
    const tailFree = f0 >= S.detach && n === S.count;
    for (let k = 0; k < rings; k++) {
      const fromEnd = (rings - 1 - k) / SUB * Dsp;
      if (tailFree && fromEnd < 0.012) Rr[k] *= Math.sqrt(Math.max(0, 1 - Math.pow(1 - fromEnd / 0.012, 2.4))) * 0.9 + 0.05;
      if (k === 0) Rr[k] *= 0.6;
    }
    for (let k = 0; k < rings; k++) {
      const a = Math.max(0, k - 1) * 3, b = Math.min(rings - 1, k + 1) * 3;
      let tx = C[b] - C[a], ty = C[b + 1] - C[a + 1], tz = C[b + 2] - C[a + 2];
      const l = Math.hypot(tx, ty, tz) || 1;
      T[k * 3] = tx / l; T[k * 3 + 1] = ty / l; T[k * 3 + 2] = tz / l;
    }
    // rotation-minimising frame, started from the cup's X axis
    N[0] = 1; N[1] = 0; N[2] = 0;
    { const d = N[0] * T[0] + N[1] * T[1] + N[2] * T[2]; N[0] -= d * T[0]; N[1] -= d * T[1]; N[2] -= d * T[2];
      const l = Math.hypot(N[0], N[1], N[2]) || 1; N[0] /= l; N[1] /= l; N[2] /= l; }
    let v = 0, w = 0;
    for (let k = 0; k < rings; k++) {
      if (k > 0) {
        // project the previous normal onto the plane of this tangent (cheap, stable at this spacing)
        const d = N[0] * T[k * 3] + N[1] * T[k * 3 + 1] + N[2] * T[k * 3 + 2];
        N[0] -= d * T[k * 3]; N[1] -= d * T[k * 3 + 1]; N[2] -= d * T[k * 3 + 2];
        const l = Math.hypot(N[0], N[1], N[2]) || 1; N[0] /= l; N[1] /= l; N[2] /= l;
      }
      const tx = T[k * 3], ty = T[k * 3 + 1], tz = T[k * 3 + 2];
      B[0] = ty * N[2] - tz * N[1]; B[1] = tz * N[0] - tx * N[2]; B[2] = tx * N[1] - ty * N[0];
      // lying coils sag flat under their own weight
      const flat = 1 - Math.abs(ty);
      const sq = 1 - 0.2 * Math.max(0, Math.min(1, (flat - 0.55) / 0.4));
      const tw = Sm[k] * 9.0;
      const rk = Rr[k];
      for (let j = 0; j <= M; j++) {
        const ct = cosT[j], st = sinT[j];
        let ox = ct * N[0] + st * B[0], oy = ct * N[1] + st * B[1], oz = ct * N[2] + st * B[2];
        // star-nozzle ridges, carried by the material as it moves
        const ps = (j / M) * Math.PI * 2 + tw;
        const ridge = 0.032 * Math.cos(6 * ps);
        const dRidge = -0.192 * Math.sin(6 * ps);
        const R = rk * (1 + ridge);
        // squash along world up
        const oyS = oy * sq;
        pos[v] = C[k * 3] + ox * R; pos[v + 1] = C[k * 3 + 1] + oyS * R; pos[v + 2] = C[k * 3 + 2] + oz * R;
        // normal: radial minus the ridge slope along the circumference
        const px = -st * N[0] + ct * B[0], py = -st * N[1] + ct * B[1], pz = -st * N[2] + ct * B[2];
        let nx = ox - px * dRidge, ny = (oy - py * dRidge) / sq, nz = oz - pz * dRidge;
        const nl = Math.hypot(nx, ny, nz) || 1;
        nrm[v] = nx / nl; nrm[v + 1] = ny / nl; nrm[v + 2] = nz / nl;
        uv[w] = Sm[k] / 0.04; uv[w + 1] = (j / M) * circ / 0.04;
        v += 3; w += 2;
      }
    }
    geo.setDrawRange(0, (rings - 1) * M * 6);
    geo.attributes.position.needsUpdate = true;
    geo.attributes.normal.needsUpdate = true;
    geo.attributes.uv.needsUpdate = true;
    geo.attributes.position.updateRange = undefined;
  }
  return { mesh, update };
}

// ------------------------------------------------------------------ camera choreography
// Keys are [p, camera position, look target] in machine space (metres, Y up, front = +Z).
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const Z0 = 0.272;   // spout line (the cup circles under it)
const CAM_KEYS = [
  [0.000, V(0.16, 0.64, 3.55), V(0.05, 0.56, 0.20)],
  [0.045, V(0.13, 0.60, 2.55), V(0.00, 0.52, 0.22)],
  [0.140, V(0.22, 0.56, 1.18), V(0.00, 0.49, Z0)],
  [0.200, V(0.14, 0.41, Z0 + 0.45), V(0.00, 0.355, Z0)],
  [0.250, V(0.15, 0.29, Z0 + 0.46), V(0.00, 0.24, Z0)],
  [0.300, V(0.13, 0.25, Z0 + 0.45), V(0.00, 0.13, Z0)],
];
// during the pour the camera orbits the spout axis and rises with the pile
for (let i = 0; i <= 6; i++) {
  const t = i / 6;
  const p = 0.34 + t * 0.44;
  const ang = THREE.MathUtils.degToRad(16 - 58 * t);
  const rad = 0.36 - 0.04 * Math.sin(t * Math.PI);
  const y = 0.23 + 0.07 * t;
  CAM_KEYS.push([p, V(Math.sin(ang) * rad, y, Z0 + Math.cos(ang) * rad), V(0, 0.11 + 0.05 * t, Z0)]);
}
CAM_KEYS.push([0.865, V(0.02, 0.28, Z0 + 0.58), V(-0.02, 0.16, Z0 + 0.02)]);
CAM_KEYS.push([0.970, V(0.42, 0.30, Z0 + 0.80), V(-0.10, 0.165, Z0 + 0.06)]);
CAM_KEYS.push([1.000, V(0.425, 0.302, Z0 + 0.81), V(-0.102, 0.165, Z0 + 0.06)]);

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
const _cb = new THREE.Vector3();

// scroll p -> simulation frame
const SIM_P = [0.15, 0.86];
const simFrameAt = p => clamp((p - SIM_P[0]) / (SIM_P[1] - SIM_P[0])) * (sim.frames - 1);

function pose(p) {
  if (!machine) return;
  const fr = simFrameAt(p);
  // the valve closes when the sim stops extruding; the handle springs back with it
  const pRel = SIM_P[0] + (sim.emitEnd * sim.fps / (sim.frames - 1)) * (SIM_P[1] - SIM_P[0]);
  const pull = easeInOut(smooth(TL.pull[0], TL.pull[1], p)) * (1 - easeInOut(smooth(pRel, pRel + 0.03, p)));
  handles.forEach((h, i) => { h.rotation.x = i === sel ? pull * path.handlePullRadians : 0; });

  // the empty cup waits under the twist spout, slides under the chosen one, then the server
  // circles it exactly as the simulation's hand did
  const slide = easeInOut(smooth(0.03, 0.12, p));
  const base = _cb.copy(cupBases[1]).lerp(cupBases[sel], slide);
  const f0 = Math.min(sim.frames - 1, Math.floor(fr)), f1 = Math.min(sim.frames - 1, f0 + 1), ft = fr - f0;
  const co = sim.cupOffset;
  const live = p > SIM_P[0] ? 1 : 0;
  cup.position.set(
    base.x + live * (co[f0][0] + (co[f1][0] - co[f0][0]) * ft),
    base.y,
    base.z + live * (co[f0][1] + (co[f1][1] - co[f0][1]) * ft));

  if (p > SIM_P[0]) rope.update(fr); else rope.mesh.visible = false;

  // camera
  camAt(p, camPos, camTgt);
  // once a flavour is chosen the whole close-up follows its spout
  const sx = nozzles[sel].x * smooth(0.05, 0.14, p);
  camPos.x += sx;
  camTgt.x += sx;
  fitPortrait(camPos, camTgt, p);
  camera.position.copy(camPos);
  camera.lookAt(camTgt);
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
window.__ilios = { scene, render: () => renderer.render(scene, camera), setP(p) { target = shown = p; loadK = 1; frame(p); }, cam: () => ({ tgt: camTgt.toArray(), dir: camera.getWorldDirection(new THREE.Vector3()).toArray(), pos: camera.position.toArray(), fov: camera.fov, near: camera.near, cup: cup && cup.position.toArray() }), setFlavor };

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

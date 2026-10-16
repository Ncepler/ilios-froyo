// The topping bar: a live physics scene on the finished cup.
//
// The froyo is the same baked pour you watched (its last frame, as a collision mesh); every topping is a real rigid
// body (a convex hull of the modelled piece, with weight, friction and damping) dropped over the swirl in slow
// motion, so it lands, tumbles, wedges between the coils and comes to rest. Sauces (honey, Nutella, pistachio cream,
// Biscoff, icing) are laid as a thread over whatever is under them: the thread is ray-cast down onto the froyo and
// the toppings, bridges the gaps between pieces like a real drizzle, and is drawn on over the first second.

import * as THREE from 'three';
import RAPIER from 'rapier';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const MM = 0.001;
const H_RIM = 0.062, RB = 0.034, RT = 0.0455, TWALL = 0.00056, ZB = 0.0068;
const SLOPE = (RT - RB) / (H_RIM - 0.0016 - 0.0015);
const rIn = y => RB + (Math.max(y, 0.0015) - 0.0015) * SLOPE - TWALL;

// what the bar offers, in the order of the shop's signs. `pieces`: model variants and how many per serving.
export const BAR = [
  { key: 'honey', label: 'Honey', group: 'Drizzles', sauce: 'honey', tint: '#e0911a' },
  { key: 'nutella', label: 'Nutella', group: 'Drizzles', sauce: 'nutella', tint: '#3a1d10' },
  { key: 'pistachio', label: 'Pistachio kataifi', group: 'Signature', sauce: 'pistachio', tint: '#9aa356', pieces: [['kataifi', 11, 1.0], ['pistachio', 30, 1.0]], radius: 0.026 },
  { key: 'biscoff', label: 'Biscoff crunch', group: 'Signature', sauce: 'biscoff', tint: '#a8672b', pieces: [['biscoff', 30, 1.0]], radius: 0.026 },
  { key: 'cinnamon', label: 'Cinnamon rolls', group: 'Signature', sauce: 'icing', tint: '#d89a52', pieces: [['cinnamon', 6, 1.0]], radius: 0.022 },
  { key: 'strawberry', label: 'Strawberry', group: 'Fruit', tint: '#c4121f', pieces: [['strawberry', 30, 1.0]], radius: 0.026 },
  { key: 'mango', label: 'Mango', group: 'Fruit', tint: '#f2a50a', pieces: [['mango', 30, 1.0]], radius: 0.026 },
  { key: 'dates', label: 'Dates', group: 'Fruit', tint: '#3e1d0e', pieces: [['date', 11, 1.0]], radius: 0.024 },
  { key: 'figs', label: 'Figs', group: 'Fruit', tint: '#4d2a4a', pieces: [['fig', 6, 1.0]], radius: 0.022 },
  { key: 'granola', label: 'Granola', group: 'Crunch', tint: '#9b6532', pieces: [['granola', 36, 1.0]], radius: 0.028 },
  { key: 'chips', label: 'Chocolate chips', group: 'Crunch', tint: '#24120b', pieces: [['chip', 52, 1.0]], radius: 0.028 },
  { key: 'brownies', label: 'Brownies', group: 'Crunch', tint: '#4a2815', pieces: [['brownie', 11, 1.0]], radius: 0.024 },
  { key: 'rainbow', label: 'Rainbow cookies', group: 'Crunch', tint: '#5da345', pieces: [['rainbow', 6, 1.0]], radius: 0.022 },
  { key: 'sprinkles', label: 'Sprinkles', group: 'Crunch', tint: '#e0474f', pieces: [['nonpareil', 460, 1.0]], radius: 0.03 },
];

// the shop's sprinkles are nonpareils in a pastel mix
const NONPAREIL = ['#f7f3ea', '#f4a6b8', '#f7d44a', '#7fc4e8', '#9ad07a', '#f08a3c', '#c79be0', '#e5463f'].map(h => new THREE.Color(h));

const SAUCE = {
  honey: { color: '#cf7d06', emissive: '#7a3a00', rough: 0.05, coat: 1, alpha: 0.96, r: 0.95 * MM, lines: 4, ang: 0.5 },
  nutella: { color: '#321811', emissive: '#000000', rough: 0.2, coat: 0.8, r: 1.45 * MM, lines: 3, ang: 1.45 },
  pistachio: { color: '#96a64f', emissive: '#10140a', rough: 0.32, coat: 0.4, r: 1.5 * MM, lines: 3, ang: 2.4 },
  biscoff: { color: '#a8631f', emissive: '#2a1204', rough: 0.22, coat: 0.7, r: 1.35 * MM, lines: 4, ang: 0.95 },
  icing: { color: '#f6f0e2', emissive: '#000000', rough: 0.3, coat: 0.5, r: 1.5 * MM, lines: 3, ang: 1.9 },
};

// the toppings share one material: the model's vertex colour is the albedo and its alpha the roughness
function toppingMaterial() {
  const m = new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 1, metalness: 0, vertexColors: true, sheen: 0, specularIntensity: 0.6 });
  m.onBeforeCompile = sh => {
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <color_fragment>', '#include <color_fragment>\n#ifdef USE_COLOR_ALPHA\n  float vRough = vColor.a;\n  diffuseColor.a = 1.0;\n  { float l = dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722)); diffuseColor.rgb = max(vec3(0.0), mix(vec3(l), diffuseColor.rgb, 1.32)) * 0.96; }\n#else\n  float vRough = 0.6;\n#endif')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\n  roughnessFactor = clamp(vRough, 0.04, 1.0);');
  };
  m.customProgramCacheKey = () => 'topping';
  return m;
}

export async function initToppings(o) {
  const { canvas, cup, toppings, froyo, froyoMaterial, dpr, reduced, chipsEl } = o;
  await RAPIER.init();

  // ------------------------------------------------------------------ viewer
  const r2 = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: false });
  r2.setPixelRatio(dpr());
  r2.outputColorSpace = THREE.SRGBColorSpace;
  r2.toneMapping = THREE.AgXToneMapping;
  r2.toneMappingExposure = 1.22;
  r2.shadowMap.enabled = true;
  r2.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(r2).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.5;
  const camera = new THREE.PerspectiveCamera(24, 1, 0.01, 10);
  camera.position.set(0.12, 0.2, 0.34);

  const model = cup.clone(true);
  model.traverse(ob => {
    if (!ob.isMesh) return;
    if (ob.name === 'Swirl' || ob.name === 'SwirlCore') { ob.visible = false; return; }
    ob.castShadow = !ob.material.transparent;
    ob.receiveShadow = true;
  });
  scene.add(model);
  froyo.mesh.visible = true;
  const swirl = new THREE.Group();
  swirl.add(froyo.mesh);
  scene.add(swirl);

  const key = new THREE.DirectionalLight('#ffe9cc', 2.9);
  key.position.set(-0.4, 0.7, 0.5);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -0.1, right: 0.1, top: 0.2, bottom: -0.05, near: 0.1, far: 2 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 0.0006;
  key.shadow.radius = 4;
  const rim = new THREE.DirectionalLight('#ffe9d0', 0.9);
  rim.position.set(0.5, 0.4, -0.5);
  scene.add(key, rim, new THREE.HemisphereLight('#fff7ec', '#a59b8e', 0.6));
  const floor = new THREE.Mesh(new THREE.CircleGeometry(0.4, 64), new THREE.ShadowMaterial({ opacity: 0.22 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const ctl = new OrbitControls(camera, canvas);
  ctl.target.set(0, 0.075, 0);
  ctl.enableDamping = true;
  ctl.enablePan = false;
  ctl.enableZoom = false;
  ctl.minPolarAngle = 0.25;
  ctl.maxPolarAngle = 1.5;
  ctl.autoRotate = !reduced;
  ctl.autoRotateSpeed = 0.9;
  ctl.addEventListener('start', () => { ctl.autoRotate = false; });

  // ------------------------------------------------------------------ physics
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = 1 / 360;

  // the froyo, exactly as meshed
  let froyoCol = null;
  const events = new RAPIER.EventQueue(true);
  const byHandle = new Map();
  {
    const nv = froyo.geometry.drawRange.count;
    const verts = froyo.pos.slice(0, nv * 3);
    const idx = new Uint32Array(nv);
    for (let i = 0; i < nv; i++) idx[i] = i;
    const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
    let cd;
    try { cd = RAPIER.ColliderDesc.trimesh(verts, idx, RAPIER.TriMeshFlags.FIX_INTERNAL_EDGES | RAPIER.TriMeshFlags.DELETE_DEGENERATE_TRIANGLES); }
    catch (e) { cd = RAPIER.ColliderDesc.trimesh(verts, idx); }
    // soft serve is cold and tacky: things set into it rather than slide off
    cd.setFriction(3.0).setFrictionCombineRule(RAPIER.CoefficientCombineRule.Max).setRestitution(0);
    froyoCol = world.createCollider(cd, body);
  }
  // the cup's inside and an invisible chimney above it, so nothing escapes while it settles
  {
    const seg = 40, prof = [[0, ZB], [rIn(ZB), ZB]];
    for (let y = ZB; y < H_RIM; y += 0.006) prof.push([rIn(y), y]);
    prof.push([rIn(H_RIM), H_RIM], [RT - TWALL, H_RIM + 0.0001], [RT - TWALL, 0.34]);
    const vs = [], is = [];
    for (let k = 0; k < prof.length; k++) for (let s = 0; s < seg; s++) {
      const a = s / seg * Math.PI * 2;
      vs.push(Math.cos(a) * prof[k][0], prof[k][1], Math.sin(a) * prof[k][0]);
    }
    for (let k = 0; k < prof.length - 1; k++) for (let s = 0; s < seg; s++) {
      const a = k * seg + s, b = k * seg + (s + 1) % seg, c = (k + 1) * seg + s, d = (k + 1) * seg + (s + 1) % seg;
      is.push(a, c, b, b, c, d);
    }
    const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
    world.createCollider(RAPIER.ColliderDesc.trimesh(new Float32Array(vs), new Uint32Array(is)).setFriction(0.8).setRestitution(0), body);
  }

  // ------------------------------------------------------------------ the pieces
  const tmat = toppingMaterial();
  const variants = {};            // 'strawberry' -> [{geo, hull}]
  toppings.updateWorldMatrix(true, true);
  toppings.traverse(ob => {
    if (!ob.isMesh) return;
    const m = /^(.*)_(\d+)$/.exec(ob.name);
    if (!m) return;
    const g = ob.geometry.clone();
    g.applyMatrix4(ob.matrixWorld);
    g.computeBoundingSphere();
    const p = g.attributes.position;
    const step = Math.max(1, Math.floor(p.count / 160));
    const pts = [];
    for (let i = 0; i < p.count; i += step) pts.push(p.getX(i), p.getY(i), p.getZ(i));
    (variants[m[1]] = variants[m[1]] || []).push({ geo: g, hull: new Float32Array(pts), r: g.boundingSphere.radius });
  });

  const piecesRoot = new THREE.Group();
  scene.add(piecesRoot);
  const live = {};                // key -> { items: [], meshes: [], leaving }
  const dummy = new THREE.Object3D();
  const rand = (a, b) => a + Math.random() * (b - a);

  function buildServing(def) {
    const grp = { def, items: [], meshes: new Map(), leaving: false, t: 0 };
    for (const [vname, n] of def.pieces) {
      const vs = variants[vname];
      if (!vs) continue;
      vs.forEach((v, vi) => {
        const mesh = new THREE.InstancedMesh(v.geo, tmat, n);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.frustumCulled = false;
        mesh.count = 0;
        piecesRoot.add(mesh);
        grp.meshes.set(vname + vi, { mesh, used: 0 });
      });
      for (let i = 0; i < n; i++) {
        const vi = Math.floor(Math.random() * vs.length);
        const v = vs[vi];
        const R = (vname === 'nonpareil' ? 0.022 : def.radius) * Math.pow(Math.random(), 0.8), a = rand(0, Math.PI * 2);
        const y = vname === 'nonpareil' ? rand(0.12, 0.2) : rand(0.125, 0.125 + 0.0025 * Math.sqrt(n) * 7 + 0.03);
        const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(rand(0, 6.28), rand(0, 6.28), rand(0, 6.28)));
        const bd = RAPIER.RigidBodyDesc.dynamic()
          .setTranslation(Math.cos(a) * R, y, Math.sin(a) * R)
          .setRotation({ x: q.x, y: q.y, z: q.z, w: q.w })
          .setLinvel(rand(-0.03, 0.03), rand(-0.35, -0.1), rand(-0.03, 0.03))
          .setAngvel({ x: rand(-6, 6), y: rand(-6, 6), z: rand(-6, 6) })
          .setLinearDamping(vname === 'nonpareil' ? 4.0 : 1.5)
          .setAngularDamping(vname === 'nonpareil' ? 6 : 2.2)
          .setCcdEnabled(true).setSoftCcdPrediction(0.004);
        const body = world.createRigidBody(bd);
        let cd = vname === 'nonpareil' ? RAPIER.ColliderDesc.ball(1.15 * MM) : RAPIER.ColliderDesc.convexHull(v.hull);
        if (!cd) cd = RAPIER.ColliderDesc.ball(v.r * 0.8);
        cd.setDensity(vname === 'kataifi' ? 120 : 1000).setFriction(1.0).setRestitution(0.03).setActiveEvents(RAPIER.ActiveEvents.COLLISION_EVENTS);
        const col = world.createCollider(cd, body);
        const slot = grp.meshes.get(vname + vi);
        const item = { body, col, slot, idx: slot.used++, s: 0, color: vname === 'nonpareil' ? NONPAREIL[(Math.random() * NONPAREIL.length) | 0] : null, born: -rand(0, 0.25) };
        byHandle.set(col.handle, item);
        grp.items.push(item);
      }
    }
    grp.meshes.forEach(({ mesh }, k) => {
      if (grp.items.some(it => it.color)) {
        mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(mesh.instanceMatrix.count * 3), 3);
      }
    });
    return grp;
  }

  // ------------------------------------------------------------------ sauces
  const sauceGroup = new THREE.Group();
  scene.add(sauceGroup);
  let sauces = [];                // { mesh, total, t }
  const matCache = {};
  function sauceMat(k) {
    if (matCache[k]) return matCache[k];
    const s = SAUCE[k];
    return (matCache[k] = new THREE.MeshPhysicalMaterial({
      color: s.color, emissive: s.emissive, emissiveIntensity: 1, roughness: s.rough, metalness: 0,
      clearcoat: s.coat, clearcoatRoughness: 0.08, sheen: 0, ior: 1.45, side: THREE.DoubleSide,
      transparent: !!s.alpha, opacity: s.alpha || 1, specularIntensity: 1,
    }));
  }

  const RAYDIR = { x: 0, y: -1, z: 0 };
  function surfaceAt(x, z) {
    const hit = world.castRayAndGetNormal(new RAPIER.Ray({ x, y: 0.3, z }, RAYDIR), 0.3, true);
    if (!hit) return null;
    return { y: 0.3 - hit.timeOfImpact, n: new THREE.Vector3(hit.normal.x, hit.normal.y, hit.normal.z) };
  }

  // a drizzle: a few strokes laid across the swirl, joined by turns at the edge, as a server swings the bottle
  function pathFor(kind, idx) {
    const s = SAUCE[kind];
    const th = s.ang + idx * 0.55;
    const dir = new THREE.Vector3(Math.cos(th), 0, Math.sin(th)), nrm = new THREE.Vector3(-dir.z, 0, dir.x);
    const R = 0.030, sp = 0.0082, n = s.lines;
    const ctl = [];
    for (let L = 0; L < n; L++) {
      const off = (L - (n - 1) / 2) * sp + Math.sin(L * 2.1 + idx) * 0.0012;
      const half = Math.sqrt(Math.max(1e-6, R * R - off * off));
      const sg = L % 2 ? -1 : 1;
      const bow = (L % 2 ? 1 : -1) * 0.0032 + Math.sin(idx * 1.3 + L) * 0.0012;
      const a = nrm.clone().multiplyScalar(off).addScaledVector(dir, -half * sg);
      const b = nrm.clone().multiplyScalar(off).addScaledVector(dir, half * sg);
      ctl.push(a.clone().addScaledVector(dir, 0.0), a.clone().lerp(b, 0.5).addScaledVector(nrm, bow), b);
      if (L < n - 1) ctl.push(b.clone().addScaledVector(dir, sg * 0.0042).addScaledVector(nrm, sp * 0.5));
    }
    const curve = new THREE.CatmullRomCurve3(ctl, false, 'centripetal');
    const len = curve.getLength();
    return curve.getSpacedPoints(Math.max(8, Math.round(len / 0.00075)));
  }

  function buildSauce(kind, idx) {
    const s = SAUCE[kind];
    const P = pathFor(kind, idx);
    const hits = P.map(p => surfaceAt(p.x, p.z));
    const ys = hits.map(h => (h ? h.y : 0.065));
    // the thread bridges only the smallest gaps: a light smoothing of the surface under it
    for (let pass = 0; pass < 2; pass++) for (let i = 1; i < ys.length - 1; i++) ys[i] = Math.max(ys[i], (ys[i - 1] + ys[i] * 2 + ys[i + 1]) / 4);
    const pos = P.map((p, i) => {
      const nrm = hits[i] ? hits[i].n : new THREE.Vector3(0, 1, 0);
      return new THREE.Vector3(p.x, ys[i], p.z).addScaledVector(nrm, s.r * 0.55);
    });
    // tube
    const SEG = 10, N = pos.length;
    const vs = new Float32Array(N * SEG * 3), ns = new Float32Array(N * SEG * 3), ix = [];
    let nPrev = new THREE.Vector3(0, 1, 0);
    for (let i = 0; i < N; i++) {
      const t = pos[Math.min(N - 1, i + 1)].clone().sub(pos[Math.max(0, i - 1)]).normalize();
      let a = nPrev.clone().sub(t.clone().multiplyScalar(nPrev.dot(t)));
      if (a.lengthSq() < 1e-8) a = new THREE.Vector3(1, 0, 0).cross(t);
      a.normalize();
      const b = t.clone().cross(a);
      nPrev = a;
      const edge = Math.min(i, N - 1 - i) * 0.00075;
      const taper = Math.min(1, Math.sqrt(Math.max(0, edge / (s.r * 1.8)) + 0.03));
      const slope = i > 1 && i < N - 2 ? Math.max(0, (ys[i - 2] - ys[i + 2]) / 0.003) : 0;
      // a thread thins where it runs and swells where it slows and pools
      const r = s.r * taper * (1 + 0.3 * Math.min(1, Math.abs(slope)) + 0.14 * Math.sin(i * 0.31 + idx * 2) + (i > N - 14 ? 0.35 * (1 - (N - 1 - i) / 14) : 0));
      for (let k = 0; k < SEG; k++) {
        const w = k / SEG * Math.PI * 2, c = Math.cos(w), sn = Math.sin(w);
        const nx = a.x * c + b.x * sn, ny = a.y * c + b.y * sn, nz = a.z * c + b.z * sn;
        const o = (i * SEG + k) * 3;
        vs[o] = pos[i].x + nx * r; vs[o + 1] = pos[i].y + ny * r * 0.8; vs[o + 2] = pos[i].z + nz * r;
        ns[o] = nx; ns[o + 1] = ny; ns[o + 2] = nz;
      }
      if (i < N - 1) for (let k = 0; k < SEG; k++) {
        const A = i * SEG + k, B = i * SEG + (k + 1) % SEG, C = (i + 1) * SEG + k, D = (i + 1) * SEG + (k + 1) % SEG;
        ix.push(A, B, C, B, D, C);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(vs, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(ns, 3));
    g.setIndex(ix);
    g.setDrawRange(0, 0);
    const mesh = new THREE.Mesh(g, sauceMat(kind));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    mesh.renderOrder = 2;
    sauceGroup.add(mesh);
    return { mesh, total: ix.length, t: reduced ? 1 : 0, kind };
  }

  function rebuildSauces(animate = true) {
    sauces.forEach(s => { sauceGroup.remove(s.mesh); s.mesh.geometry.dispose(); });
    sauces = [];
    let idx = 0;
    for (const def of BAR) {
      const g = live[def.key];
      if (def.sauce && g && !g.leaving) sauces.push(buildSauce(def.sauce, idx++));
    }
    if (!animate) sauces.forEach(s => { s.t = 1; s.mesh.geometry.setDrawRange(0, s.total); });
  }

  // ------------------------------------------------------------------ state, loop
  let settledFor = 0, dirty = false, acc = 0, last = 0, raf = null, visible = false, active = true;
  const TIMESCALE = reduced ? 1.0 : 0.5;

  function setChip(key, on) {
    chipsEl && chipsEl.querySelectorAll(`[data-top="${key}"]`).forEach(c => c.setAttribute('aria-pressed', String(on)));
  }
  function count() {
    const n = Object.values(live).filter(g => !g.leaving).length;
    const el = document.getElementById('topcount');
    if (el) el.textContent = n ? `${n} topping${n > 1 ? 's' : ''} on` : 'Plain, the way it pours';
  }

  function add(key) {
    const def = BAR.find(b => b.key === key);
    if (!def || (live[key] && !live[key].leaving)) return;
    if (live[key]) removeNow(key);
    live[key] = def.pieces ? buildServing(def) : { def, items: [], meshes: new Map(), leaving: false, t: 0 };
    settledFor = 0;
    dirty = true;
    setChip(key, true);
    count();
    wake();
  }
  function removeNow(key) {
    const g = live[key];
    if (!g) return;
    g.items.forEach(it => { byHandle.delete(it.col.handle); world.removeRigidBody(it.body); });
    g.meshes.forEach(({ mesh }) => { piecesRoot.remove(mesh); mesh.dispose(); });
    delete live[key];
  }
  function remove(key) {
    const g = live[key];
    if (!g || g.leaving) return;
    g.leaving = true;
    g.t = 0;
    setChip(key, false);
    dirty = true;
    settledFor = 0.2;
    count();
    wake();
  }
  function toggle(key) { live[key] && !live[key].leaving ? remove(key) : add(key); }
  function clear() { Object.keys(live).forEach(remove); }
  function surprise() {
    clear();
    const keys = BAR.map(b => b.key).sort(() => Math.random() - 0.5).slice(0, 3);
    setTimeout(() => keys.forEach(add), 380);
  }

  const q = new THREE.Quaternion(), pv = new THREE.Vector3(), sc = new THREE.Vector3(), tmpM = new THREE.Matrix4(), col = new THREE.Color();
  function writeInstances(dt) {
    let anyAwake = false;
    for (const key of Object.keys(live)) {
      const g = live[key];
      g.t += dt;
      if (g.leaving) {
        const k = Math.max(0, 1 - g.t / 0.35);
        if (k <= 0) { removeNow(key); continue; }
        g.items.forEach(it => { it.s = k; });
      }
      const counts = new Map();
      for (const it of g.items) {
        if (!g.leaving) it.s = Math.min(1, Math.max(0, (g.t + it.born) / 0.06 + 0.001));
        const tr = it.body.translation(), ro = it.body.rotation();
        if (!it.body.isSleeping()) anyAwake = true;
        pv.set(tr.x, tr.y, tr.z);
        q.set(ro.x, ro.y, ro.z, ro.w);
        sc.setScalar(it.s);
        tmpM.compose(pv, q, sc);
        it.slot.mesh.setMatrixAt(it.idx, tmpM);
        if (it.color) it.slot.mesh.setColorAt(it.idx, it.color);
      }
      g.meshes.forEach(({ mesh, used }) => {
        mesh.count = used;
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      });
    }
    return anyAwake;
  }

  // soft serve is cold and slightly wet: whatever lands on it sticks where it touched
  function stepWorld() {
    world.step(events);
    events.drainCollisionEvents((a, b, started) => {
      if (!started) return;
      const other = a === froyoCol.handle ? b : b === froyoCol.handle ? a : null;
      if (other === null) return;
      const it = byHandle.get(other);
      if (it && !it.stuck) { it.stuck = true; it.body.setLinearDamping(14); it.body.setAngularDamping(14); }
    });
  }

  function frame(now) {
    raf = null;
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    let busy = false;
    const live_n = Object.keys(live).length;
    if (live_n) {
      acc += dt * TIMESCALE;
      let steps = 0;
      while (acc >= world.timestep && steps < 12) { stepWorld(); acc -= world.timestep; steps++; }
      if (steps === 12) acc = 0;
      const awake = writeInstances(dt);
      busy = awake || Object.values(live).some(g => g.leaving || g.t < 0.6);
      if (!awake) settledFor += dt; else settledFor = 0;
      if (dirty && settledFor > 0.35) { dirty = false; rebuildSauces(); }
    }
    for (const s of sauces) {
      if (s.t < 1) {
        s.t = Math.min(1, s.t + dt / 1.4);
        const e = 1 - Math.pow(1 - s.t, 2);
        s.mesh.geometry.setDrawRange(0, Math.floor(s.total * e / 6) * 6);
        busy = true;
      }
    }
    if (dirty) busy = true;
    ctl.update();
    r2.render(scene, camera);
    if (visible && !document.hidden && (busy || ctl.autoRotate || userMoving)) raf = requestAnimationFrame(frame);
  }
  let userMoving = false;
  ctl.addEventListener('start', () => { userMoving = true; wake(); });
  ctl.addEventListener('end', () => { setTimeout(() => { userMoving = false; }, 900); });
  function wake() { if (visible && raf === null) { last = performance.now(); raf = requestAnimationFrame(frame); } }

  const size = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    r2.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w / h < 0.85 ? 30 : 24;
    camera.updateProjectionMatrix();
  };
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) { size(); wake(); } }).observe(canvas);
  addEventListener('resize', () => { size(); wake(); });
  document.addEventListener('visibilitychange', () => wake());
  size();

  // ------------------------------------------------------------------ chips with a render of each topping
  function thumb(def) {
    const g = new THREE.Scene();
    g.environment = scene.environment;
    g.environmentIntensity = 0.9;
    const L = new THREE.DirectionalLight('#fff0db', 2.4);
    L.position.set(-0.3, 0.8, 0.5);
    g.add(L, new THREE.HemisphereLight('#fff7ec', '#a59b8e', 0.8));
    const c = new THREE.PerspectiveCamera(22, 1, 0.005, 1);
    const grp = new THREE.Group();
    g.add(grp);
    let bound = 0.012;
    if (def.pieces) {
      const [vn] = def.pieces[0];
      const vs = variants[vn] || [];
      const spots = vn === 'nonpareil' ? 26 : vn === 'kataifi' || vn === 'pistachio' || vn === 'biscoff' ? 3 : 2;
      for (let i = 0; i < spots; i++) {
        const v = vs[i % vs.length];
        if (!v) continue;
        const m = new THREE.Mesh(v.geo, tmat);
        const a = i / spots * 6.28 + 0.4, r = vn === 'nonpareil' ? 0.0055 * Math.sqrt((i + 1) / spots) * 1.6 : 0.0052 * (spots > 1);
        m.position.set(Math.cos(a) * r, 0, Math.sin(a) * r);
        m.rotation.set(0.5 + i, i * 2.1, 0.2);
        if (vn === 'nonpareil') {
          const mm = new THREE.MeshPhysicalMaterial({ color: NONPAREIL[i % NONPAREIL.length], roughness: 0.35 });
          m.material = mm;
          m.scale.setScalar(1.7);
        }
        grp.add(m);
      }
      bound = vn === 'nonpareil' ? 0.011 : vn === 'kataifi' ? 0.016 : vn === 'cinnamon' ? 0.016 : vn === 'fig' ? 0.017 : vn === 'rainbow' ? 0.014 : 0.0125;
    }
    if (def.sauce) {
      const s = SAUCE[def.sauce];
      const curve = new THREE.CatmullRomCurve3([[-0.011, 0.0, 0.004], [-0.004, 0.003, -0.005], [0.004, 0.0, 0.005], [0.011, 0.003, -0.004]].map(p => new THREE.Vector3(...p)));
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, def.pieces ? 0.0011 : 0.0017, 10, false), sauceMat(def.sauce));
      tube.position.y = def.pieces ? 0.0075 : 0.0;
      if (!def.pieces) { tube.scale.setScalar(1.15); bound = 0.0125; }
      grp.add(tube);
      const bowl = null;
    }
    c.position.set(0.0, bound * 3.4, bound * 3.1);
    c.lookAt(0, 0.001, 0);
    const prevSize = r2.getSize(new THREE.Vector2());
    const prevPR = r2.getPixelRatio();
    r2.setPixelRatio(1);
    r2.setSize(128, 128, false);
    r2.setClearAlpha(0);
    r2.render(g, c);
    const url = canvas.toDataURL('image/png');
    r2.setPixelRatio(prevPR);
    r2.setSize(prevSize.x / prevPR, prevSize.y / prevPR, false);
    size();
    return url;
  }

  if (chipsEl) {
    const groups = [...new Set(BAR.map(b => b.group))];
    chipsEl.innerHTML = '';
    for (const gname of groups) {
      const wrap = document.createElement('div');
      wrap.className = 'tgrp';
      wrap.innerHTML = `<h3>${gname}</h3><div class="tchips"></div>`;
      const box = wrap.querySelector('.tchips');
      for (const def of BAR.filter(b => b.group === gname)) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'tchip';
        b.dataset.top = def.key;
        b.setAttribute('aria-pressed', 'false');
        let url = '';
        try { url = thumb(def); } catch (e) { /* the chip still works without its picture */ }
        b.innerHTML = `<i class="ti" style="background-image:url(${url});--tint:${def.tint}"></i><span>${def.label}</span>`;
        b.addEventListener('click', () => toggle(def.key));
        box.appendChild(b);
      }
      chipsEl.appendChild(wrap);
    }
  }
  document.getElementById('topclear')?.addEventListener('click', clear);
  document.getElementById('topsurprise')?.addEventListener('click', surprise);
  count();

  window.__toppings = { add, remove, toggle, clear, camera, ctl, scene, world, render: () => r2.render(scene, camera), live, get settled() { return settledFor; }, step(n) { for (let i = 0; i < n; i++) stepWorld(); writeInstances(0.01); }, rebuildSauces, variants };
  return { add, remove, toggle, clear };
}

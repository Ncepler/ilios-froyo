// Topping pieces for the bar, built in code: every piece is a small mesh with its albedo in the vertex colour and
// its roughness in the vertex alpha (the same convention as toppings.glb, which supplies the pieces modelled in
// Blender: strawberry, mango, dates, figs, granola, chocolate chips, brownies, rainbow cookies, cinnamon-roll bites,
// kataifi, pistachio, Biscoff and nonpareils). Sizes are real, in metres.

import * as THREE from 'three';

// ------------------------------------------------------------------ noise
function hash(x, y, z) {
  let h = (x * 374761393 + y * 668265263 + z * 1274126177) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
export function noise3(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const l = (a, b, t) => a + (b - a) * t;
  const c = (i, j, k) => hash(xi + i, yi + j, zi + k);
  return l(l(l(c(0, 0, 0), c(1, 0, 0), u), l(c(0, 1, 0), c(1, 1, 0), u), v),
    l(l(c(0, 0, 1), c(1, 0, 1), u), l(c(0, 1, 1), c(1, 1, 1), u), v), w) * 2 - 1;
}
export function fbm(x, y, z, oct = 3) {
  let s = 0, a = 0.5, f = 1;
  for (let i = 0; i < oct; i++) { s += a * noise3(x * f, y * f, z * f); a *= 0.5; f *= 2.03; }
  return s;
}
export function rng(seed) { let s = seed >>> 0 || 1; return () => (s = Math.imul(s ^ (s >>> 15), 2246822519) + 0x9e3779b9 >>> 0, (s >>> 8) / 16777216); }

const C = h => new THREE.Color(h);

// colour every vertex with fn(position, normal) -> [colour, roughness] (THREE.Color is already linear)
function paint(g, fn) {
  g.computeVertexNormals();
  const p = g.attributes.position, n = g.attributes.normal, col = new Float32Array(p.count * 4);
  const tmp = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const [c, r] = fn(p.getX(i), p.getY(i), p.getZ(i), n.getX(i), n.getY(i), n.getZ(i));
    tmp.copy(c);
    col[i * 4] = tmp.r; col[i * 4 + 1] = tmp.g; col[i * 4 + 2] = tmp.b; col[i * 4 + 3] = r;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 4));
  return g;
}
// push vertices along their normal by fn(p) (on an indexed copy so the surface stays closed)
function displace(g, fn) {
  const p = g.attributes.position;
  g.computeVertexNormals();
  const n = g.attributes.normal;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), d = fn(x, y, z);
    p.setXYZ(i, x + n.getX(i) * d, y + n.getY(i) * d, z + n.getZ(i) * d);
  }
  return g;
}
function merged(g) {
  // drop the uv/normal attributes so coincident vertices of primitive geometries weld, then re-index
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', g.attributes.position.clone());
  if (g.index) out.setIndex(g.index.clone());
  return weld(out);
}
export function weld(g, tol = 1e-6) {
  const p = g.attributes.position, map = new Map(), remap = new Uint32Array(p.count), pos = [];
  let n = 0;
  for (let i = 0; i < p.count; i++) {
    const k = `${Math.round(p.getX(i) / tol)},${Math.round(p.getY(i) / tol)},${Math.round(p.getZ(i) / tol)}`;
    let j = map.get(k);
    if (j === undefined) { j = n++; map.set(k, j); pos.push(p.getX(i), p.getY(i), p.getZ(i)); }
    remap[i] = j;
  }
  const idx = g.index ? Array.from(g.index.array, i => remap[i]) : Array.from(remap);
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setIndex(idx);
  return out;
}
const mix = (a, b, t) => a.clone().lerp(b, Math.min(1, Math.max(0, t)));

// ------------------------------------------------------------------ the pieces
// each returns { geo, r (bounding radius), flat: true if it lies flat (thin axis = local y) }

export function blueberry(seed) {
  const R = rng(seed), r = 0.0052 + R() * 0.0012;
  let g = merged(new THREE.SphereGeometry(r, 18, 12));
  g.scale(1, 0.86, 1);
  g = displace(g, (x, y, z) => r * 0.03 * fbm(x * 900, y * 900, z * 900));
  const blue = C('#2b3150'), bloom = C('#6a7393'), crown = C('#1b1a22');
  return { geo: paint(g, (x, y, z) => {
    const top = y / r, b = fbm(x * 700 + seed, y * 700, z * 700);
    let c = mix(blue, bloom, 0.45 + 0.4 * b);
    if (top > 0.72 && Math.hypot(x, z) < r * 0.36) c = mix(c, crown, 0.85);
    return [c, 0.55 + 0.15 * b];
  }), r };
}

export function kiwi(seed) {
  const R = rng(seed), s = 0.0085 + R() * 0.002;
  let g = merged(new THREE.BoxGeometry(s, s * (0.75 + R() * 0.3), s * (0.85 + R() * 0.3), 4, 4, 4));
  g = displace(g, (x, y, z) => s * 0.05 * fbm(x * 500 + seed, y * 500, z * 500));
  const flesh = C('#7fb22a'), pale = C('#d7e3a2'), seedc = C('#1c1610');
  const cx = (R() - 0.5) * s, cz = (R() - 0.5) * s;
  return { geo: paint(g, (x, y, z) => {
    // the pale core and a ring of black seeds around it, as if the dice were cut from a slice
    const d = Math.hypot(x - cx, z - cz) / s;
    let c = mix(pale, flesh, (d - 0.15) * 3);
    const ang = Math.atan2(z - cz, x - cx);
    if (d > 0.28 && d < 0.42 && Math.sin(ang * 14) > 0.75 && hash(Math.round(ang * 9), seed, 1) > 0.3) c = seedc;
    return [c, 0.28];
  }), r: s * 0.8 };
}

export function grape(seed) {
  const R = rng(seed), r = 0.0075 + R() * 0.0015;
  let g = merged(new THREE.SphereGeometry(r, 18, 12));
  g.scale(1, 1.18, 1);
  g = displace(g, (x, y, z) => r * 0.02 * fbm(x * 600, y * 600 + seed, z * 600));
  const skin = C('#a9c45a'), hi = C('#d4df8c');
  return { geo: paint(g, (x, y, z) => [mix(skin, hi, 0.5 + 0.5 * fbm(x * 400, y * 200 + seed, z * 400)), 0.22]), r: r * 1.18 };
}

export function honeydew(seed) {
  const R = rng(seed), r = 0.0085 + R() * 0.0015;
  let g = merged(new THREE.SphereGeometry(r, 18, 12));
  g = displace(g, (x, y, z) => r * 0.025 * fbm(x * 500 + seed, y * 500, z * 500));
  const a = C('#cfe2a1'), b = C('#e9f0c3');
  return { geo: paint(g, (x, y, z) => [mix(a, b, 0.5 + 0.6 * fbm(x * 900, y * 900, z * 900 + seed)), 0.3]), r };
}

export function pineapple(seed) {
  const R = rng(seed), s = 0.0095 + R() * 0.002;
  let g = merged(new THREE.BoxGeometry(s, s * 0.8, s * 0.9, 4, 4, 4));
  g = displace(g, (x, y, z) => s * 0.05 * fbm(x * 300 + seed, y * 1400, z * 300));
  const a = C('#f2c632'), b = C('#f8e27a');
  return { geo: paint(g, (x, y, z) => [mix(a, b, 0.5 + 0.7 * noise3(x * 2600, y * 300, z * 300 + seed)), 0.32]), r: s * 0.75 };
}

export function coconut(seed) {
  // a thin curled shred
  const R = rng(seed), L = 0.006 + R() * 0.006, w = 0.0011 + R() * 0.0006, k = (R() - 0.5) * 300;
  const pts = [];
  for (let i = 0; i <= 8; i++) { const t = i / 8 - 0.5; pts.push(new THREE.Vector3(t * L, k * (t * L) * (t * L), Math.sin(t * 5 + seed) * 0.0008)); }
  let g = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 10, w, 4, false);
  g.scale(1, 0.35, 1);
  const a = C('#f7f3ea'), b = C('#e7e0d0');
  return { geo: paint(merged(g), (x, y, z) => [mix(a, b, 0.5 + noise3(x * 2000, z * 2000, seed)), 0.7]), r: L * 0.55, flat: true };
}

const GUMMY = ['#e8402f', '#f59a1c', '#f6d72c', '#5fbf3c', '#ef5e8f', '#ffffff'].map(C);
export function gummyBear(seed) {
  const R = rng(seed), s = 0.0105;
  const parts = [];
  const add = (geo, x, y, z) => { geo.translate(x, y, z); parts.push(geo); };
  add(new THREE.SphereGeometry(0.42, 12, 10).scale(1, 1.15, 0.8), 0, 0, 0);          // body
  add(new THREE.SphereGeometry(0.32, 12, 10).scale(1, 0.95, 0.85), 0, 0.62, 0);       // head
  add(new THREE.SphereGeometry(0.11, 8, 6), -0.22, 0.86, 0); add(new THREE.SphereGeometry(0.11, 8, 6), 0.22, 0.86, 0); // ears
  add(new THREE.SphereGeometry(0.15, 8, 6), -0.36, 0.2, 0.05); add(new THREE.SphereGeometry(0.15, 8, 6), 0.36, 0.2, 0.05); // arms
  add(new THREE.SphereGeometry(0.18, 8, 6), -0.22, -0.42, 0.04); add(new THREE.SphereGeometry(0.18, 8, 6), 0.22, -0.42, 0.04); // legs
  const g = mergeAll(parts);
  g.scale(s, s, s);
  const col = GUMMY[Math.floor(R() * GUMMY.length)];
  const clear = col.equals(GUMMY[5]) ? C('#f2efe6') : col;
  return { geo: paint(g, () => [clear, 0.18]), r: s * 0.75, jelly: true, flat: true };
}

const MM = ['#d6261f', '#f6c21b', '#2d7a3c', '#2457a6', '#f07d14', '#5a3420'].map(C);
export function mm(seed) {
  const R = rng(seed);
  let g = merged(new THREE.SphereGeometry(0.0068, 16, 10));
  g.scale(1, 0.55, 1);
  const c = MM[Math.floor(R() * MM.length)];
  return { geo: paint(g, () => [c, 0.16]), r: 0.0068, flat: true };
}

export function jimmy(seed, colors) {
  const R = rng(seed), L = 0.0048 + R() * 0.0018;
  const g = merged(new THREE.CapsuleGeometry(0.00055, L, 2, 6));
  g.rotateZ(Math.PI / 2);
  const c = colors[Math.floor(R() * colors.length)];
  return { geo: paint(g, () => [c, 0.35]), r: L * 0.55, flat: true };
}
export const RAINBOW_JIMMIES = ['#f05a7e', '#f7d046', '#5bb5e8', '#7cc75a', '#f39538', '#b48ad9', '#ffffff'].map(C);
export const CHOC_JIMMIES = ['#3b2216', '#45291b', '#352015'].map(C);

export function krispie(seed) {
  const R = rng(seed), s = 0.011 + R() * 0.003;
  let g = merged(new THREE.BoxGeometry(s, s * 0.8, s * 0.95, 6, 5, 6));
  g = displace(g, (x, y, z) => s * (0.05 * fbm(x * 260 + seed, y * 260, z * 260) + 0.03 * (Math.abs(noise3(x * 1500, y * 1500, z * 1500 + seed)) - 0.3)));
  const a = C('#e6c98d'), b = C('#c99b55'), w = C('#f3e7cb');
  return { geo: paint(g, (x, y, z) => {
    const v = noise3(x * 1800 + seed, y * 1800, z * 1800);
    return [v > 0.45 ? w : mix(a, b, 0.5 + 0.8 * v), 0.6];
  }), r: s * 0.75 };
}

export function oreo(seed) {
  const R = rng(seed), s = 0.006 + R() * 0.006;
  let g = merged(new THREE.IcosahedronGeometry(s * 0.6, 1));
  g.scale(1, 0.38, 0.8 + R() * 0.3);
  g = displace(g, (x, y, z) => s * 0.12 * fbm(x * 400 + seed, y * 400, z * 400));
  const dark = C('#1d1514'), cream = C('#efe9de');
  const creamy = R() < 0.35;
  return { geo: paint(g, (x, y, z) => [creamy && y > s * 0.06 && noise3(x * 900, z * 900, seed) > -0.1 ? cream : mix(dark, C('#2c2220'), 0.5 + noise3(x * 1200, y * 1200, z * 1200)), 0.75]), r: s * 0.6, flat: true };
}

export function miniCookie(seed) {
  const R = rng(seed), r = 0.0095 + R() * 0.0015;
  let g = merged(new THREE.CylinderGeometry(r, r * 0.96, r * 0.42, 20, 2));
  g = displace(g, (x, y, z) => r * 0.07 * fbm(x * 320 + seed, y * 320, z * 320));
  const a = C('#c88a45'), b = C('#a5682e'), chip = C('#2a170e');
  return { geo: paint(g, (x, y, z) => {
    const v = noise3(x * 900 + seed, y * 900, z * 900);
    return [v > 0.5 ? chip : mix(a, b, 0.5 + v), 0.7];
  }), r, flat: true };
}

export function cookieDough(seed) {
  const R = rng(seed), r = 0.0105 + R() * 0.002;
  let g = merged(new THREE.IcosahedronGeometry(r, 3));
  g.scale(1, 0.78, 1);
  g = displace(g, (x, y, z) => r * 0.14 * fbm(x * 260 + seed, y * 260, z * 260));
  const a = C('#e0c08c'), b = C('#c9a066'), chip = C('#2b180f');
  return { geo: paint(g, (x, y, z) => {
    const v = noise3(x * 700 + seed, y * 700, z * 700);
    return [v > 0.48 ? chip : mix(a, b, 0.5 + 0.6 * fbm(x * 500, y * 500, z * 500)), 0.82];
  }), r };
}

const SOUR = [['#e8352c', '#f7d23a'], ['#5bbf3a', '#f6f1e6'], ['#f39a1d', '#e8352c'], ['#3f7fd6', '#f6f1e6']].map(p => p.map(C));
export function sourStrip(seed) {
  const R = rng(seed), L = 0.026 + R() * 0.012, W = 0.007, T = 0.0022, bend = (R() - 0.5) * 2.2;
  const g0 = new THREE.BoxGeometry(L, T, W, 14, 1, 2);
  const p = g0.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), u = x / L;
    p.setY(i, p.getY(i) + Math.sin(u * Math.PI) * 0.0012 + Math.sin(u * 6 + seed) * 0.0008);
    p.setZ(i, p.getZ(i) + bend * u * u * 0.012);
  }
  const g = merged(g0);
  const pair = SOUR[Math.floor(R() * SOUR.length)];
  return { geo: paint(g, (x, y, z) => {
    const sugar = hash(Math.round(x * 3000), Math.round(z * 3000), Math.round(y * 3000)) > 0.86;
    return [sugar ? C('#fbf6ea') : z > 0 ? pair[0] : pair[1], 0.85];
  }), r: L * 0.5, flat: true };
}

export function gummyWorm(seed) {
  const R = rng(seed), L = 0.034 + R() * 0.01;
  const pts = [];
  for (let i = 0; i <= 12; i++) { const t = i / 12; pts.push(new THREE.Vector3((t - 0.5) * L, Math.sin(t * 3.1 + seed) * 0.003, Math.sin(t * 6 + seed * 2) * 0.006)); }
  const g = merged(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 24, 0.0034, 8, false));
  const pairs = [['#e8402f', '#f6d72c'], ['#5fbf3c', '#f59a1c'], ['#ef5e8f', '#3f7fd6']].map(p => p.map(C));
  const pair = pairs[Math.floor(R() * pairs.length)];
  return { geo: paint(g, x => [x / L + 0.5 < 0.5 ? pair[0] : pair[1], 0.2]), r: L * 0.5, jelly: true, flat: true };
}

export function chocChunk(seed) {
  const R = rng(seed), s = 0.012 + R() * 0.004;
  let g = merged(new THREE.BoxGeometry(s, s * 0.42, s * 0.75, 3, 2, 3));
  g = displace(g, (x, y, z) => s * 0.035 * fbm(x * 300 + seed, y * 300, z * 300));
  const milk = C('#5a3423'), white = C('#efe6d4');
  return { geo: paint(g, (x, y, z) => [y < -s * 0.05 ? white : milk, 0.32]), r: s * 0.6, flat: true };
}

export function saltFlake(seed) {
  const R = rng(seed), s = 0.0018 + R() * 0.0016;
  const g = merged(new THREE.OctahedronGeometry(s, 0));
  g.scale(1, 0.25, 0.8);
  return { geo: paint(g, () => [C('#fbfbf8'), 0.15]), r: s, flat: true };
}

// mini cinnamon roll, the pan's: a spiral of dough and cinnamon, soft from the icing it soaks in
export function miniRoll(seed) {
  const R = rng(seed), r = 0.012 + R() * 0.002, H = 0.0085;
  let g = merged(new THREE.CylinderGeometry(r, r * 0.98, H, 40, 3));
  g = displace(g, (x, y, z) => r * 0.05 * fbm(x * 240 + seed, y * 240, z * 240));
  const dough = C('#d9a463'), cinn = C('#7a3e1c'), icing = C('#f4eee1');
  return { geo: paint(g, (x, y, z) => {
    const d = Math.hypot(x, z) / r, a = Math.atan2(z, x);
    const spiral = Math.sin((d * 4.2 - a / (2 * Math.PI)) * 2 * Math.PI);
    let c = spiral > 0.55 ? cinn : dough;
    if (y > H * 0.3 && noise3(x * 500, z * 500, seed) > -0.25) c = mix(c, icing, 0.85);
    return [c, y > H * 0.3 ? 0.35 : 0.75];
  }), r, flat: true };
}

function mergeAll(geos) {
  let n = 0;
  geos.forEach(g => { n += g.attributes.position.count; });
  const pos = new Float32Array(n * 3), idx = [];
  let o = 0;
  for (const g0 of geos) {
    const g = g0, p = g.attributes.position;
    for (let i = 0; i < p.count; i++) { pos[(o + i) * 3] = p.getX(i); pos[(o + i) * 3 + 1] = p.getY(i); pos[(o + i) * 3 + 2] = p.getZ(i); }
    if (g.index) for (const i of g.index.array) idx.push(i + o); else for (let i = 0; i < p.count; i++) idx.push(i + o);
    o += p.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setIndex(idx);
  return out;
}

// the shared material: vertex colour is the albedo, its alpha the roughness; jelly pieces get a bit of sheen
export function pieceMaterial({ jelly = false } = {}) {
  const m = new THREE.MeshPhysicalMaterial({
    color: '#ffffff', roughness: 1, metalness: 0, vertexColors: true, specularIntensity: 0.6,
    clearcoat: jelly ? 0.6 : 0, clearcoatRoughness: 0.2, sheen: jelly ? 0.4 : 0,
  });
  m.onBeforeCompile = sh => {
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <color_fragment>', '#include <color_fragment>\n#ifdef USE_COLOR_ALPHA\n  float vRough = vColor.a;\n  diffuseColor.a = 1.0;\n#else\n  float vRough = 0.6;\n#endif')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\n  roughnessFactor = clamp(vRough, 0.04, 1.0);');
  };
  m.customProgramCacheKey = () => 'piece' + (jelly ? 'J' : '');
  return m;
}

// pieces modelled in Blender (toppings.glb): name -> [{ geo, r }]
export function glbPieces(gltfScene) {
  const out = {};
  gltfScene.updateWorldMatrix(true, true);
  gltfScene.traverse(ob => {
    if (!ob.isMesh) return;
    const m = /^(.*)_(\d+)$/.exec(ob.name);
    if (!m) return;
    const g = ob.geometry.clone();
    g.applyMatrix4(ob.matrixWorld);
    g.computeBoundingBox();
    const c = g.boundingBox.getCenter(new THREE.Vector3());
    g.translate(-c.x, -c.y, -c.z);
    g.computeBoundingSphere();
    (out[m[1]] = out[m[1]] || []).push({ geo: g, r: g.boundingSphere.radius });
  });
  return out;
}

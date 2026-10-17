// Draws the simulated pour (pour-sim.js) as soft serve: a star-ridged rope that is round while it falls and slumps
// into a wider, flatter coil once it has landed, fusing into the coil below. Rebuilt for any time t, so scrolling
// scrubs the pour smoothly in both directions (nothing is a pre-baked frame).

import * as THREE from 'three';
import { nodesAt, handAt } from './pour-sim.js';

const RING = 48;            // vertices around the rope
const SUB = 2;              // rings per node spacing (smooth bends)
const RIDGES = 8;           // the star tip's points
const SETTLE = 0.2;         // seconds a landed coil takes to slump into its laid shape
const TWIST_RATE = 2 * Math.PI / 0.085;   // a twist's two flavours wind once every 8.5 cm of rope

const _v = new THREE.Vector3();
// forward rotation-minimising frames (double reflection, Wang et al. 2008) over interleaved positions P, from node lo.
// With `fixed`: nodes landed by time t take the fixed frame, moving ones are carried on from the node before.
function rmfForward(P, n, out, lo, fixed, frozenT, t) {
  const tan = (i, o) => {
    const a = Math.max(0, i - 1) * 3, b = Math.min(n - 1, i + 1) * 3;
    const tx = P[b] - P[a], ty = P[b + 1] - P[a + 1], tz = P[b + 2] - P[a + 2], l = Math.hypot(tx, ty, tz) || 1;
    o[0] = tx / l; o[1] = ty / l; o[2] = tz / l;
  };
  const Ti = [0, 0, 0], Tj = [0, 0, 0];
  let start = lo;
  if (!fixed || lo === 0) {
    tan(0, Ti);
    let nx = 0, ny = 1, nz = 0;
    if (Math.abs(Ti[1]) > 0.9) { nx = 1; ny = 0; }
    const d = nx * Ti[0] + ny * Ti[1] + nz * Ti[2];
    nx -= d * Ti[0]; ny -= d * Ti[1]; nz -= d * Ti[2];
    const l = Math.hypot(nx, ny, nz);
    if (fixed && frozenT[0] <= t) { out[0] = fixed[0]; out[1] = fixed[1]; out[2] = fixed[2]; }
    else { out[0] = nx / l; out[1] = ny / l; out[2] = nz / l; }
    start = 1;
  } else {
    const o = (lo - 1) * 3;
    out[o] = fixed[o]; out[o + 1] = fixed[o + 1]; out[o + 2] = fixed[o + 2];
  }
  for (let i = start; i < n; i++) {
    const o = i * 3, q = o - 3;
    if (fixed && frozenT[i] <= t) { out[o] = fixed[o]; out[o + 1] = fixed[o + 1]; out[o + 2] = fixed[o + 2]; continue; }
    tan(i - 1, Ti); tan(i, Tj);
    const v1x = P[o] - P[q], v1y = P[o + 1] - P[q + 1], v1z = P[o + 2] - P[q + 2];
    const c1 = v1x * v1x + v1y * v1y + v1z * v1z;
    const Nx = out[q], Ny = out[q + 1], Nz = out[q + 2];
    if (c1 < 1e-14) { out[o] = Nx; out[o + 1] = Ny; out[o + 2] = Nz; continue; }
    let k = 2 / c1 * (v1x * Nx + v1y * Ny + v1z * Nz);
    const rx = Nx - k * v1x, ry = Ny - k * v1y, rz = Nz - k * v1z;
    k = 2 / c1 * (v1x * Ti[0] + v1y * Ti[1] + v1z * Ti[2]);
    const tlx = Ti[0] - k * v1x, tly = Ti[1] - k * v1y, tlz = Ti[2] - k * v1z;
    const v2x = Tj[0] - tlx, v2y = Tj[1] - tly, v2z = Tj[2] - tlz;
    const c2 = v2x * v2x + v2y * v2y + v2z * v2z;
    let qx = rx, qy = ry, qz = rz;
    if (c2 > 1e-14) { k = 2 / c2 * (v2x * rx + v2y * ry + v2z * rz); qx -= k * v2x; qy -= k * v2y; qz -= k * v2z; }
    const l = Math.hypot(qx, qy, qz) || 1;
    out[o] = qx / l; out[o + 1] = qy / l; out[o + 2] = qz / l;
  }
}

function makeTables() {
  const T = { c: [], s: [], cR: [], sR: [], c2R: [], s2R: [] };
  for (let k = 0; k < RING; k++) {
    const ph = k / RING * Math.PI * 2;
    T.c.push(Math.cos(ph)); T.s.push(Math.sin(ph));
    T.cR.push(Math.cos(RIDGES * ph)); T.sR.push(Math.sin(RIDGES * ph));
    T.c2R.push(Math.cos(2 * RIDGES * ph)); T.s2R.push(Math.sin(2 * RIDGES * ph));
  }
  return T;
}

export class FroyoRope {
  constructor(rec, material) {
    this.rec = rec;
    const n = rec.count;
    this.n = n;
    this.P = new Float32Array(n * 3);
    this.Nf = new Float32Array(n * 3);
    // per-node values for the current time
    this.rN = new Float32Array(n); this.sN = new Float32Array(n); this.fN = new Uint8Array(n);
    // samples: SUB rings per node spacing
    const ms = (n - 1) * SUB + 1;
    this.ms = ms;
    this.Q = new Float32Array(ms * 3);
    const nv = ms * RING + 1;
    this.pos = new Float32Array(nv * 3);
    this.nor = new Float32Array(nv * 3);
    this.mm = new Float32Array(nv);
    const idx = new Uint32Array(RING * 3 + (ms - 1) * RING * 6);
    let o = 0;
    const C = ms * RING;                    // start-cap centre
    for (let k = 0; k < RING; k++) { idx[o++] = C; idx[o++] = (k + 1) % RING; idx[o++] = k; }
    for (let i = 0; i < ms - 1; i++) for (let k = 0; k < RING; k++) {
      const a = i * RING + k, b = i * RING + (k + 1) % RING, c = a + RING, d = b + RING;
      idx[o++] = a; idx[o++] = b; idx[o++] = c;
      idx[o++] = b; idx[o++] = d; idx[o++] = c;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nor, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('m', new THREE.BufferAttribute(this.mm, 1).setUsage(THREE.DynamicDrawUsage));
    g.setIndex(new THREE.BufferAttribute(idx, 1));
    g.setDrawRange(0, 0);
    this.geometry = g;
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.name = 'Froyo';
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = true;
    this.t = -1;
    this.hand = [0, 0, 0];
    // frames along the finished rope (forward rotation-minimising), so neighbouring sections never twist apart
    this.FF = new Float32Array(n * 3);
    rmfForward(rec.final, n, this.FF, 0, null);
  }

  // the nozzle, in the cup's frame, at time t
  handAt(t, out = this.hand) { return handAt(this.rec, t, out); }

  setTime(t) {
    t = Math.max(0, Math.min(this.rec.duration, t));
    if (t === this.t) return;
    this.t = t;
    const rec = this.rec, { FX, FY, DS } = rec.params;
    const P = this.P, Nf = this.Nf;
    const n = nodesAt(rec, t, P);
    this.visible = n;
    if (n < 2) { this.geometry.setDrawRange(0, 0); this.mesh.visible = false; return; }
    this.mesh.visible = true;
    const rad = rec.rad, frozenT = rec.frozenT, FF = this.FF;
    const released = rec.releaseT >= 0 && t >= rec.releaseT;
    // where each node's ridges point: landed rope uses the frames of the finished rope; rope still moving carries
    // the frame on from the node before it
    let lo = 0;
    while (lo < n && frozenT[lo] <= t) lo++;
    if (lo < n) rmfForward(P, n, Nf, lo, FF, frozenT, t);
    const rN = this.rN, sN = this.sN, fN = this.fN;
    const settled = i => i < 0 || i >= n || frozenT[i] + SETTLE <= t;
    for (let i = 0; i < n; i++) {
      const o = i * 3;
      const fr = frozenT[i] <= t;
      if (!fr) { Nf[o] = Nf[o]; } else { Nf[o] = FF[o]; Nf[o + 1] = FF[o + 1]; Nf[o + 2] = FF[o + 2]; }
      // where the rope is stretched (the cup dropping away at the end) it necks: same volume, thinner
      const la = i > 0 ? Math.hypot(P[o] - P[o - 3], P[o + 1] - P[o - 2], P[o + 2] - P[o - 1]) : DS;
      const lb = i < n - 1 ? Math.hypot(P[o + 3] - P[o], P[o + 4] - P[o + 1], P[o + 5] - P[o + 2]) : DS;
      let r = rad[i] * Math.min(1, Math.max(0.3, Math.sqrt(DS * 2 / (la + lb + 1e-9))));
      // a rounded start, and after the break a tail that necks down to a soft point
      if (i < 4) r *= 0.62 + 0.38 * Math.sin(Math.min(1, i / 3) * Math.PI / 2);
      if (released) {
        const e = (n - 1 - i) / 9;
        if (e < 1) r *= Math.sqrt(Math.max(0, e)) * 0.92 + 0.02;
      }
      rN[i] = r;
      const sf = fr ? Math.min(1, (t - frozenT[i]) / SETTLE) : 0;
      sN[i] = sf * sf * (3 - 2 * sf);
      // a coil that has landed and slumped, among landed neighbours, never changes again
      fN[i] = settled(i) && settled(i - 1) && settled(i + 1) && settled(i - 2) && settled(i + 2) && i > 4 && i < n - 3 &&
        (!released || n - 1 - i > 11) ? 1 : 0;
    }
    // samples along the rope (Catmull-Rom between nodes)
    const ms = (n - 1) * SUB + 1, Q = this.Q, h = DS / SUB;
    for (let j = 0; j < ms; j++) {
      const a = Math.floor(j / SUB), f = (j - a * SUB) / SUB, o = j * 3;
      if (f === 0) { Q[o] = P[a * 3]; Q[o + 1] = P[a * 3 + 1]; Q[o + 2] = P[a * 3 + 2]; continue; }
      const i0 = Math.max(0, a - 1) * 3, i1 = a * 3, i2 = Math.min(n - 1, a + 1) * 3, i3 = Math.min(n - 1, a + 2) * 3;
      const f2 = f * f, f3 = f2 * f;
      const w0 = -0.5 * f3 + f2 - 0.5 * f, w1 = 1.5 * f3 - 2.5 * f2 + 1, w2 = -1.5 * f3 + 2 * f2 + 0.5 * f, w3 = 0.5 * f3 - 0.5 * f2;
      for (let c = 0; c < 3; c++) Q[o + c] = w0 * P[i0 + c] + w1 * P[i1 + c] + w2 * P[i2 + c] + w3 * P[i3 + c];
    }
    const cache = this.cache || (this.cache = new Int8Array(this.ms));
    const pos = this.pos, nor = this.nor, mm = this.mm;
    const TB = this.tables || (this.tables = makeTables());
    let written = 0, first = ms;
    for (let j = 0; j < ms; j++) {
      const a = Math.floor(j / SUB), f = (j - a * SUB) / SUB, b = Math.min(n - 1, a + 1), o = j * 3;
      const final = fN[a] && fN[b];
      if (final && cache[j] === 1) continue;
      cache[j] = final ? 1 : 0;
      written++;
      if (j < first) first = j;
      // tangent
      const ja = Math.max(0, j - 1) * 3, jb = Math.min(ms - 1, j + 1) * 3;
      let tx = Q[jb] - Q[ja], ty = Q[jb + 1] - Q[ja + 1], tz = Q[jb + 2] - Q[ja + 2];
      const tl = Math.hypot(tx, ty, tz) || 1; tx /= tl; ty /= tl; tz /= tl;
      // frame, radius and slump, between the two nodes
      let Nx = Nf[a * 3] * (1 - f) + Nf[b * 3] * f, Ny = Nf[a * 3 + 1] * (1 - f) + Nf[b * 3 + 1] * f, Nz = Nf[a * 3 + 2] * (1 - f) + Nf[b * 3 + 2] * f;
      { const d = Nx * tx + Ny * ty + Nz * tz; Nx -= d * tx; Ny -= d * ty; Nz -= d * tz; const l = Math.hypot(Nx, Ny, Nz) || 1; Nx /= l; Ny /= l; Nz /= l; }
      const Bx = ty * Nz - tz * Ny, By = tz * Nx - tx * Nz, Bz = tx * Ny - ty * Nx;
      const r = rN[a] * (1 - f) + rN[b] * f, ss = sN[a] * (1 - f) + sN[b] * f;
      // landed coils slump: wider and lower, flattened along the vertical
      const flat = ss * (0.35 + 0.65 * (1 - Math.abs(ty)));
      const ax = 1 + (FX - 1) * flat, ay = 1 + (FY - 1) * flat;
      let Ux = -ty * tx, Uy = 1 - ty * ty, Uz = -ty * tz;
      let ul = Math.hypot(Ux, Uy, Uz);
      if (ul < 0.25) { Ux = Nx; Uy = Ny; Uz = Nz; ul = 1; }
      Ux /= ul; Uy /= ul; Uz /= ul;
      const Sx = Uy * tz - Uz * ty, Sy = Uz * tx - Ux * tz, Sz = Ux * ty - Uy * tx;
      const nS = Nx * Sx + Ny * Sy + Nz * Sz, nU = Nx * Ux + Ny * Uy + Nz * Uz;
      const bS = Bx * Sx + By * Sy + Bz * Sz, bU = Bx * Ux + By * Uy + Bz * Uz;
      const A = 0.08 * (1 - 0.25 * ss), A2 = 0.018;
      const s = j * h, tw = s * 3.0 * RIDGES, tws = s * TWIST_RATE;
      const cw = Math.cos(tw), sw = Math.sin(tw), c2w = Math.cos(2 * tw), s2w = Math.sin(2 * tw);
      const cm0 = Math.cos(tws), sm0 = Math.sin(tws);
      const px = Q[o], py = Q[o + 1], pz = Q[o + 2];
      // in a bend tighter than the rope is thick, the inside of the bend is squashed instead of folding over
      let kx = 0, ky = 0, kz = 0, kmax = Infinity;
      if (j > 0 && j < ms - 1) {
        kx = (Q[o + 3] - 2 * px + Q[o - 3]) / (h * h); ky = (Q[o + 4] - 2 * py + Q[o - 2]) / (h * h); kz = (Q[o + 5] - 2 * pz + Q[o - 1]) / (h * h);
        const kl = Math.hypot(kx, ky, kz);
        if (kl > 1e-6) { kx /= kl; ky /= kl; kz /= kl; kmax = 0.82 / kl; }
      }
      const base = j * RING;
      for (let k = 0; k < RING; k++) {
        const c = TB.c[k], sn = TB.s[k];
        // cos(R(ph + tw)) and cos(2R(ph + tw)) from the tables
        const cr = TB.cR[k] * cw - TB.sR[k] * sw, sr = TB.sR[k] * cw + TB.cR[k] * sw;
        const c2r = TB.c2R[k] * c2w - TB.s2R[k] * s2w, s2r = TB.s2R[k] * c2w + TB.c2R[k] * s2w;
        const fr = 1 + A * cr - A2 * c2r, fp = -A * RIDGES * sr + 2 * A2 * RIDGES * s2r;
        const os = c * nS + sn * bS, ou = c * nU + sn * bU;
        const dos = -sn * nS + c * bS, dou = -sn * nU + c * bU;
        const qs = os * fr * ax * r, qu = ou * fr * ay * r;
        const v = (base + k) * 3;
        let ox = qs * Sx + qu * Ux, oy = qs * Sy + qu * Uy, oz = qs * Sz + qu * Uz;
        const ik = ox * kx + oy * ky + oz * kz, k0 = kmax * 0.55;
        if (ik > k0) { const cut = ik - (k0 + (kmax - k0) * Math.tanh((ik - k0) / (kmax - k0))); ox -= kx * cut; oy -= ky * cut; oz -= kz * cut; }
        pos[v] = px + ox;
        pos[v + 1] = py + oy;
        pos[v + 2] = pz + oz;
        // outward normal of the cross-section curve
        const ds = (dos * fr + os * fp) * ax, du = (dou * fr + ou * fp) * ay;
        let ns = du, nu = -ds;
        if (ns * os + nu * ou < 0) { ns = -ns; nu = -nu; }
        const wx = ns * Sx + nu * Ux, wy = ns * Sy + nu * Uy, wz = ns * Sz + nu * Uz;
        const wl = Math.hypot(wx, wy, wz) || 1;
        nor[v] = wx / wl; nor[v + 1] = wy / wl; nor[v + 2] = wz / wl;
        // twist: the two flavours side by side, winding slowly along the rope
        const cm = c * cm0 - sn * sm0;
        mm[base + k] = cm > 0.22 ? 1 : cm < -0.22 ? 0 : 0.5 + cm / 0.44;
      }
    }
    this.written = written;
    // start cap
    {
      const c = this.ms * RING * 3;
      const tx = Q[3] - Q[0], ty = Q[4] - Q[1], tz = Q[5] - Q[2], l = Math.hypot(tx, ty, tz) || 1;
      pos[c] = Q[0] - tx / l * rad[0] * 0.3; pos[c + 1] = Q[1] - ty / l * rad[0] * 0.3; pos[c + 2] = Q[2] - tz / l * rad[0] * 0.3;
      nor[c] = -tx / l; nor[c + 1] = -ty / l; nor[c + 2] = -tz / l;
      mm[this.ms * RING] = 0.5;
    }
    const g = this.geometry;
    g.setDrawRange(0, RING * 3 + (ms - 1) * RING * 6);
    // upload only what changed (the rope still moving sits at the end), plus the cap
    for (const [name, size] of [['position', 3], ['normal', 3], ['m', 1]]) {
      const at = g.attributes[name];
      at.clearUpdateRanges();
      if (first < ms) at.addUpdateRange(first * RING * size, (ms - first) * RING * size);
      at.addUpdateRange(this.ms * RING * size, size);
      at.needsUpdate = true;
    }
    // the ring-index winding may face either way depending on frame handedness: keep the visible side outward
    if (this._wind === undefined) this._wind = this._checkWinding(n);
  }

  _checkWinding(n) {
    // compare one face's geometric normal against its vertex normal; flip the index order if they disagree
    const i = Math.min((n - 1) * SUB - 1, 4), k = 3;
    const a = i * RING + k, b = i * RING + (k + 1) % RING, c = a + RING;
    const p = this.pos, A = new THREE.Vector3(p[a * 3], p[a * 3 + 1], p[a * 3 + 2]);
    const B = new THREE.Vector3(p[b * 3], p[b * 3 + 1], p[b * 3 + 2]), C = new THREE.Vector3(p[c * 3], p[c * 3 + 1], p[c * 3 + 2]);
    const fn = B.sub(A).cross(C.sub(A));
    const vn = _v.set(this.nor[a * 3], this.nor[a * 3 + 1], this.nor[a * 3 + 2]);
    if (fn.dot(vn) < 0) {
      const ix = this.geometry.index.array;
      for (let j = 0; j < ix.length; j += 3) { const s = ix[j + 1]; ix[j + 1] = ix[j + 2]; ix[j + 2] = s; }
      this.geometry.index.needsUpdate = true;
      return -1;
    }
    return 1;
  }

  // the froyo's surface height above (x, z) in the cup's frame, from the laid coils (for toppings to land on)
  heightAt(x, z) {
    const rec = this.rec, { FX, FY } = rec.params, F = rec.final, R = rec.rad;
    let h = -Infinity;
    for (let i = 0; i < rec.count; i++) {
      const dx = x - F[i * 3], dz = z - F[i * 3 + 2], w = FX * R[i];
      const d2 = (dx * dx + dz * dz) / (w * w);
      if (d2 < 1) h = Math.max(h, F[i * 3 + 1] + FY * R[i] * Math.sqrt(1 - d2));
    }
    return h;
  }
}

// Draws the simulated pour (pour-sim.js) as soft serve: a star-ridged rope that is round while it falls and slumps
// into a wider, flatter coil once it has landed, fusing into the coil below. Rebuilt for any time t, so scrolling
// scrubs the pour smoothly in both directions (nothing is a pre-baked frame).
//
// The simulation's nodes sit 2 mm apart and jitter a little where coils press on each other. Drawn as they are, that
// jitter reads as hairpin bends and folds the surface over itself (the crumpled tip), so the centre line and the
// radius are smoothed first (Taubin, which does not shrink the coils), and the surface is bent only as far as the
// smoothed curve really bends. The cross-section is the nozzle's star: rounded lobes with narrow grooves between
// them. Each ring also carries how much the other coils and the paper shut it in, for the shader's occlusion.

import * as THREE from 'three';
import { nodesAt, handAt } from './pour-sim.js';
import { CUP, rIn } from './cup-dims.js';

const RING = 64;            // vertices around the rope (8 per lobe)
const SUB = 2;              // rings per node spacing (smooth bends)
const LOBES = 8;            // the star tip's points
const SETTLE = 0.2;         // seconds a landed coil takes to slump into its laid shape
const EPS = 0.14;           // how sharp the grooves are (smaller is sharper)
const ABN = Math.sqrt(1 + EPS * EPS) - EPS;
const SMOOTH_PASSES = 3;    // Taubin pairs; each pass reaches one node along the rope
const AO_SKIP = 13;         // nodes along the rope that count as the same tube, not as a neighbour
const AO_R = 0.045;         // how far away a coil still shuts a vertex in

// mean of the (smoothed) crest profile, so the lobes ride on the rope's own radius
const MU = (() => { let s = 0; for (let i = 0; i < 720; i++) s += (Math.sqrt(Math.sin(i / 720 * Math.PI) ** 2 + EPS * EPS) - EPS) / ABN; return s / 720; })();

// twist: the two halves of a twist spiral round the rope slowly, riding on the star's own pattern
export const TWIST = { rate: 28 };
const twistAngle = s => TWIST.rate * s + 0.55 * Math.sin(23 * s + 1.3);

const _v = new THREE.Vector3();

// Taubin smoothing of an interleaved polyline, ends fixed
function smoothPath(src, n, out, tmp) {
  out.set(src.subarray(0, n * 3));
  for (let p = 0; p < SMOOTH_PASSES; p++) for (const f of [0.5, -0.53]) {
    for (let i = 1; i < n - 1; i++) {
      const o = i * 3;
      tmp[o] = f * (0.5 * (out[o - 3] + out[o + 3]) - out[o]);
      tmp[o + 1] = f * (0.5 * (out[o - 2] + out[o + 4]) - out[o + 1]);
      tmp[o + 2] = f * (0.5 * (out[o - 1] + out[o + 5]) - out[o + 2]);
    }
    for (let i = 1; i < n - 1; i++) { const o = i * 3; out[o] += tmp[o]; out[o + 1] += tmp[o + 1]; out[o + 2] += tmp[o + 2]; }
  }
}

// Soft serve is a paste, not wire: it does not fold tighter than its own thickness. Where the smoothed line still
// curves more sharply than the rope is thick (a kink where it pressed against the paper or a neighbour), relax those
// nodes toward the chord until the bend is at least about one rope radius, so the surface rounds the corner instead of
// folding over itself. Menger curvature over a 2-node stencil; Gauss-Seidel, a few passes.
function limitBends(P, n, rad, fx) {
  for (let it = 0; it < 16; it++) {
    let moved = 0;
    for (let i = 2; i < n - 2; i++) {
      const o = i * 3, a = o - 6, c = o + 6;
      const abx = P[o] - P[a], aby = P[o + 1] - P[a + 1], abz = P[o + 2] - P[a + 2];
      const bcx = P[c] - P[o], bcy = P[c + 1] - P[o + 1], bcz = P[c + 2] - P[o + 2];
      const acx = P[c] - P[a], acy = P[c + 1] - P[a + 1], acz = P[c + 2] - P[a + 2];
      const cx = aby * acz - abz * acy, cy = abz * acx - abx * acz, cz = abx * acy - aby * acx;
      const ab = Math.hypot(abx, aby, abz), bc = Math.hypot(bcx, bcy, bcz), ac = Math.hypot(acx, acy, acz);
      if (ab * bc * ac < 1e-12) continue;
      const kr = 2 * Math.hypot(cx, cy, cz) / (ab * bc * ac) * rad[i] * fx;
      if (kr <= 0.68) continue;
      const w = Math.min(0.6, (kr - 0.68) * 0.9);
      // toward the chord, through the near neighbours too (a 2-node stencil alone lets odd and even nodes drift apart)
      for (let q = 0; q < 3; q++) {
        const m = 0.25 * (P[a + q] + P[c + q]) + 0.25 * (P[o - 3 + q] + P[o + 3 + q]);
        P[o + q] += w * (m - P[o + q]);
      }
      moved++;
    }
    if (!moved) break;
  }
}

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
  const T = { c: [], s: [], c4: [], s4: [] };
  for (let k = 0; k < RING; k++) {
    const ph = k / RING * Math.PI * 2;
    T.c.push(Math.cos(ph)); T.s.push(Math.sin(ph));
    T.c4.push(Math.cos(LOBES / 2 * ph)); T.s4.push(Math.sin(LOBES / 2 * ph));
  }
  return T;
}

export class FroyoRope {
  constructor(rec, material) {
    this.rec = rec;
    const n = rec.count;
    this.n = n;
    this.P = new Float32Array(n * 3);      // the simulation's nodes at the current time
    this.Ps = new Float32Array(n * 3);     // ... smoothed, what is drawn
    this.tmp = new Float32Array(n * 3);
    this.Nf = new Float32Array(n * 3);
    // per-node values for the current time
    this.rN = new Float32Array(n); this.rT = new Float32Array(n); this.sN = new Float32Array(n); this.fN = new Uint8Array(n);
    // samples: SUB rings per node spacing
    const ms = (n - 1) * SUB + 1;
    this.ms = ms;
    this.Q = new Float32Array(ms * 3);
    this.K = new Float32Array(ms * 3);     // curvature vector of the smoothed centre line at each sample
    const nv = ms * RING + 1;
    this.pos = new Float32Array(nv * 3);
    this.nor = new Float32Array(nv * 3);
    this.mm = new Float32Array(nv);
    this.oc = new Float32Array(nv * 3);    // how much, and from where, the other coils shut the vertex in
    this.rg = new Float32Array(nv);        // 1 on a lobe's crest, 0 in a groove
    this.ocRing = new Float32Array(ms * 3);
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
    const dyn = (arr, size) => new THREE.BufferAttribute(arr, size).setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('position', dyn(this.pos, 3));
    g.setAttribute('normal', dyn(this.nor, 3));
    g.setAttribute('m', dyn(this.mm, 1));
    g.setAttribute('oc', dyn(this.oc, 3));
    g.setAttribute('rg', dyn(this.rg, 1));
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
    const fs = new Float32Array(n * 3);
    smoothPath(rec.final, n, fs, this.tmp);
    limitBends(fs, n, rec.rad, rec.params.FX);
    rmfForward(fs, n, this.FF, 0, null);
    this.grid = new Map();
  }

  get vertCount() { return this.ms * RING + 1; }   // vertices of the rope's surface (and the start cap)

  // the nozzle, in the cup's frame, at time t
  handAt(t, out = this.hand) { return handAt(this.rec, t, out); }

  setTime(t) {
    t = Math.max(0, Math.min(this.rec.duration, t));
    if (t === this.t) return;
    this.t = t;
    const rec = this.rec, { FX, FY, DS } = rec.params;
    const P = this.P, Ps = this.Ps, Nf = this.Nf;
    const n = nodesAt(rec, t, P);
    this.visible = n;
    if (n < 2) { this.geometry.setDrawRange(0, 0); this.mesh.visible = false; return; }
    this.mesh.visible = true;
    smoothPath(P, n, Ps, this.tmp);
    const rad = rec.rad, frozenT = rec.frozenT, FF = this.FF;
    const released = rec.releaseT >= 0 && t >= rec.releaseT;
    const rN = this.rN, sN = this.sN, fN = this.fN, rT = this.rT;
    const settled = i => i < 0 || i >= n || frozenT[i] + SETTLE <= t;
    for (let i = 0; i < n; i++) {
      const o = i * 3;
      const fr = frozenT[i] <= t;
      if (fr) { Nf[o] = FF[o]; Nf[o + 1] = FF[o + 1]; Nf[o + 2] = FF[o + 2]; }
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
      rT[i] = r;
      const sf = fr ? Math.min(1, (t - frozenT[i]) / SETTLE) : 0;
      sN[i] = sf * sf * (3 - 2 * sf);
    }
    // the radius is smoothed along the rope too (the stretch above is noisy node to node)
    for (let p = 0; p < 2; p++) {
      let a = rT[0];
      for (let i = 1; i < n - 1; i++) { const c = rT[i]; rT[i] = 0.25 * a + 0.5 * c + 0.25 * rT[i + 1]; a = c; }
    }
    for (let i = 0; i < n; i++) rN[i] = rT[i];
    // after the break the tail end is free: smooth the last stretch with the end loose, so the point is not a kink
    if (released) for (let p = 0; p < 6; p++) {
      for (let i = Math.max(1, n - 14); i < n; i++) {
        const o = i * 3, b = i < n - 1 ? o + 3 : o;
        for (let q = 0; q < 3; q++) Ps[o + q] = 0.5 * Ps[o + q] + 0.25 * (Ps[o - 3 + q] + Ps[b + q]);
      }
    }
    limitBends(Ps, n, rN, FX);
    // where each node's ridges point: landed rope uses the frames of the finished rope; rope still moving carries
    // the frame on from the node before it
    let lo = 0;
    while (lo < n && frozenT[lo] <= t) lo++;
    if (lo < n) rmfForward(Ps, n, Nf, lo, FF, frozenT, t);
    for (let i = 0; i < lo; i++) { const o = i * 3; Nf[o] = FF[o]; Nf[o + 1] = FF[o + 1]; Nf[o + 2] = FF[o + 2]; }
    // a coil that has landed and slumped, among landed neighbours, never changes again (smoothing and bend limiting
    // reach a good way along the rope)
    const far = 16;
    for (let i = 0; i < n; i++) {
      let ok = i > 4 && i < n - 3 - far && (!released || n - 1 - i > 11 + far);
      for (let d = -far; ok && d <= far; d++) if (!settled(i + d)) ok = false;
      fN[i] = ok ? 1 : 0;
    }
    // samples along the rope (Catmull-Rom between smoothed nodes)
    const ms = (n - 1) * SUB + 1, Q = this.Q, K = this.K, h = DS / SUB;
    for (let j = 0; j < ms; j++) {
      const a = Math.floor(j / SUB), f = (j - a * SUB) / SUB, o = j * 3;
      if (f === 0) { Q[o] = Ps[a * 3]; Q[o + 1] = Ps[a * 3 + 1]; Q[o + 2] = Ps[a * 3 + 2]; continue; }
      const i0 = Math.max(0, a - 1) * 3, i1 = a * 3, i2 = Math.min(n - 1, a + 1) * 3, i3 = Math.min(n - 1, a + 2) * 3;
      const f2 = f * f, f3 = f2 * f;
      const w0 = -0.5 * f3 + f2 - 0.5 * f, w1 = 1.5 * f3 - 2.5 * f2 + 1, w2 = -1.5 * f3 + 2 * f2 + 0.5 * f, w3 = 0.5 * f3 - 0.5 * f2;
      for (let c = 0; c < 3; c++) Q[o + c] = w0 * Ps[i0 + c] + w1 * Ps[i1 + c] + w2 * Ps[i2 + c] + w3 * Ps[i3 + c];
    }
    // curvature of the smoothed line, over a stencil of 3 samples each side (a stable second difference)
    const W = 3, hh = 1 / (W * W * h * h);
    for (let j = 0; j < ms; j++) {
      const o = j * 3;
      if (j < W || j >= ms - W) { K[o] = K[o + 1] = K[o + 2] = 0; continue; }
      K[o] = (Q[o + 3 * W] - 2 * Q[o] + Q[o - 3 * W]) * hh;
      K[o + 1] = (Q[o + 3 * W + 1] - 2 * Q[o + 1] + Q[o - 3 * W + 1]) * hh;
      K[o + 2] = (Q[o + 3 * W + 2] - 2 * Q[o + 2] + Q[o - 3 * W + 2]) * hh;
    }
    this._occlusion(n, ms, t);

    const cache = this.cache || (this.cache = new Int8Array(this.ms));
    const pos = this.pos, nor = this.nor, mm = this.mm, rg = this.rg, oc = this.oc, ocRing = this.ocRing;
    const TB = this.tables || (this.tables = makeTables());
    let written = 0, first = ms;
    for (let j = 0; j < ms; j++) {
      const a = Math.floor(j / SUB), f = (j - a * SUB) / SUB, b = Math.min(n - 1, a + 1), o = j * 3;
      const base = j * RING;
      // how much the other coils shut this ring in (cheap, and it changes as later coils land)
      for (let k = 0; k < RING; k++) { const v = (base + k) * 3; oc[v] = ocRing[o]; oc[v + 1] = ocRing[o + 1]; oc[v + 2] = ocRing[o + 2]; }
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
      // (a rope going straight up or down stays round, so the flattening axes never matter where they are undefined)
      const vert = Math.min(1, Math.max(0, (Math.abs(ty) - 0.7) / 0.25)), iso = vert * vert * (3 - 2 * vert);
      const flat = ss * (0.35 + 0.65 * (1 - Math.abs(ty))) * (1 - iso);
      const ax = 1 + (FX - 1) * flat, ay = 1 + (FY - 1) * flat;
      let Ux = -ty * tx, Uy = 1 - ty * ty, Uz = -ty * tz;
      let ul = Math.hypot(Ux, Uy, Uz);
      if (ul < 0.25) { Ux = Nx; Uy = Ny; Uz = Nz; ul = 1; }
      Ux /= ul; Uy /= ul; Uz /= ul;
      const Sx = Uy * tz - Uz * ty, Sy = Uz * tx - Ux * tz, Sz = Ux * ty - Uy * tx;
      const nS = Nx * Sx + Ny * Sy + Nz * Sz, nU = Nx * Ux + Ny * Uy + Nz * Uz;
      const bS = Bx * Sx + By * Sy + Bz * Sz, bU = Bx * Ux + By * Uy + Bz * Uz;
      // the star's lobes fade out as the rope thins to the point of the tip (nothing for a ridge to be on)
      const thin = Math.min(1, Math.max(0, (r - 0.0022) / 0.0042));
      const A = 0.15 * (1 - 0.2 * ss) * thin * thin * (3 - 2 * thin);
      const s = j * h, rw = 12 * s, cw = Math.cos(rw), sw = Math.sin(rw);
      const tws = twistAngle(s), cm0 = Math.cos(tws), sm0 = Math.sin(tws);
      const px = Q[o], py = Q[o + 1], pz = Q[o + 2];
      // in a bend tighter than the rope is thick, the inside of the bend is squashed instead of folding over
      let kx = K[o], ky = K[o + 1], kz = K[o + 2], kmax = Infinity;
      const kl = Math.hypot(kx, ky, kz);
      if (kl > 1e-6) { kx /= kl; ky /= kl; kz /= kl; kmax = 0.9 / kl; }
      for (let k = 0; k < RING; k++) {
        const c = TB.c[k], sn = TB.s[k];
        // the star: |sin(4 (phi + 3 s))| with its V rounded off, so lobes are round and the grooves between them narrow
        const sx = TB.s4[k] * cw + TB.c4[k] * sw, cx = TB.c4[k] * cw - TB.s4[k] * sw;
        const ab = Math.sqrt(sx * sx + EPS * EPS);
        const crest = (ab - EPS) / ABN;
        const fr = 1 + A * (crest - MU), fp = A * (LOBES / 2) * sx * cx / ab / ABN;
        const os = c * nS + sn * bS, ou = c * nU + sn * bU;
        const dos = -sn * nS + c * bS, dou = -sn * nU + c * bU;
        const qs = os * fr * ax * r, qu = ou * fr * ay * r;
        const vi = base + k, v = vi * 3;
        let ox = qs * Sx + qu * Ux, oy = qs * Sy + qu * Uy, oz = qs * Sz + qu * Uz;
        const ik = ox * kx + oy * ky + oz * kz, k0 = kmax * 0.6;
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
        rg[vi] = crest;
        // twist: the two flavours side by side, winding slowly along the rope
        const cm = c * cm0 - sn * sm0;
        mm[vi] = Math.min(1, Math.max(0, 0.5 + 0.9 * cm));
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
      rg[this.ms * RING] = 1;
    }
    const g = this.geometry;
    g.setDrawRange(0, RING * 3 + (ms - 1) * RING * 6);
    // upload only what changed (the rope still moving sits at the end), plus the cap; the occlusion changes anywhere
    for (const [name, size] of [['position', 3], ['normal', 3], ['m', 1], ['rg', 1]]) {
      const at = g.attributes[name];
      at.clearUpdateRanges();
      if (first < ms) at.addUpdateRange(first * RING * size, (ms - first) * RING * size);
      at.addUpdateRange(this.ms * RING * size, size);
      at.needsUpdate = true;
    }
    g.attributes.oc.clearUpdateRanges();
    g.attributes.oc.addUpdateRange(0, ms * RING * 3);
    g.attributes.oc.needsUpdate = true;
    // the ring-index winding may face either way depending on frame handedness: keep the visible side outward
    if (this._wind === undefined) this._wind = this._checkWinding(n);
  }

  // Occlusion per ring: the landed coils (and the paper) around it, as one vector whose direction points at them and
  // whose length is how much of the sky they cover (spheres of the rope's radius: (r / d)^2, summed, the way a cheap
  // analytic occluder works). The vertex shader dots it with the vertex normal.
  _occlusion(n, ms, t) {
    const Ps = this.Ps, rec = this.rec, rad = this.rN, frozenT = rec.frozenT, { FX, FY } = rec.params;  // eslint-disable-line
    const CELL = 0.03, grid = this.grid, key = (i, j, k) => ((i + 256) * 512 + (j + 256)) * 512 + (k + 256);
    grid.clear();
    for (let i = 0; i < n; i++) {
      if (frozenT[i] > t) continue;
      const kk = key(Math.floor(Ps[i * 3] / CELL), Math.floor(Ps[i * 3 + 1] / CELL), Math.floor(Ps[i * 3 + 2] / CELL));
      let a = grid.get(kk); if (!a) grid.set(kk, a = []); a.push(i);
    }
    const Q = this.Q, out = this.ocRing, rN = this.rN;
    for (let j = 0; j < ms; j++) {
      const o = j * 3, cx = Q[o], cy = Q[o + 1], cz = Q[o + 2], a = j / SUB, rj = rN[Math.min(n - 1, Math.round(a))];
      let ox = 0, oy = 0, oz = 0;
      const ci = Math.floor(cx / CELL), cj = Math.floor(cy / CELL), ck = Math.floor(cz / CELL);
      for (let gi = ci - 1; gi <= ci + 1; gi++) for (let gj = cj - 1; gj <= cj + 1; gj++) for (let gk = ck - 1; gk <= ck + 1; gk++) {
        const L = grid.get(key(gi, gj, gk)); if (!L) continue;
        for (let m = 0; m < L.length; m++) {
          const i = L[m];
          if (Math.abs(i - a) < AO_SKIP) continue;
          const dx = Ps[i * 3] - cx, dy = Ps[i * 3 + 1] - cy, dz = Ps[i * 3 + 2] - cz;
          const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
          if (d > AO_R || d < 1e-6) continue;
          const rq = rad[i], w = Math.min(1, (rq / Math.max(d - rj, 0.7 * rq)) ** 2) * 0.62;
          ox += dx / d * w; oy += dy / d * w; oz += dz / d * w;
        }
      }
      // the paper: the cup wall shuts in whatever lies against it
      if (cy < CUP.H) {
        const rho = Math.hypot(cx, cz);
        if (rho > 1e-4) {
          const gap = rIn(cy) - rho - rj * FX;
          const w = 0.7 * Math.max(0, 1 - gap / (1.3 * rj));
          ox += cx / rho * w; oz += cz / rho * w;
        }
        const gapF = cy - CUP.ZB - rj * FY;
        oy -= 0.7 * Math.max(0, 1 - gapF / (1.3 * rj));
      }
      const l = Math.hypot(ox, oy, oz);
      if (l > 1.15) { const s = 1.15 / l; ox *= s; oy *= s; oz *= s; }
      out[o] = ox; out[o + 1] = oy; out[o + 2] = oz;
    }
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

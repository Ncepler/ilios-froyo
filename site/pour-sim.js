// The pour: soft serve leaving the star spout and landing in the cup, simulated.
//
// Soft serve is a foam (about 50% air) that behaves as a yield-stress paste: below its yield stress it is a soft
// solid, above it, it flows. Out of the spout that makes it a rope that keeps its thickness (it does not neck or
// drip like a liquid), bends under its own weight over a few centimetres, falls, and where it lands it stops dead
// and stays (once the load drops under the yield stress there is no flow left), slumping a little into a flatter,
// wider coil that fuses with the coil it sits on. The server circles the cup under the spout so the rope is laid in
// rings, keeps the spout a couple of centimetres above the pile, builds the swirl over the rim, then closes the
// valve and drops the cup away, which necks the rope and leaves the curled tip.
//
// The model: a chain of nodes (position-based dynamics, Mueller et al. 2007) fed out of the nozzle at the extrusion
// speed. Inextensible links (the yield stress keeps the rope from thinning), a bending stiffness, gravity and air
// drag; sticky contact against the paper and against froyo already laid (cold soft serve is tacky); and a node that
// lands and comes to rest freezes for good, in order along the rope. Laid coils are flattened ellipses (wider than
// tall at the same area) and their contact distance is measured in that shape, so new coils sit on and press into
// old ones. The server's hand is a feedback controller over the pile's own height map, like a real server watching
// the cup. Runs once on page load (well under a second) and is recorded at 240 Hz, so scrolling scrubs it smoothly
// in both directions. No three.js in here so it can run headless (source/validate_pour.mjs).

import { CUP, rIn, RIM_IN } from './cup-dims.js';

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export const POUR = {
  R0: 0.0086,     // rope radius out of the star tip (20 mm star, the rope is a hair thinner)
  DS: 0.0021,     // node spacing along the rope
  VE: 0.17,       // extrusion speed, m/s (a 16 oz cup in about 8 s, as in the shop's videos)
  FX: 1.16,       // a laid coil is 16% wider ...
  FY: 0.84,       // ... and 16% lower than the round rope (area kept within 3%)
  FUSE: 0.93,     // coils press 7% into each other
  KB: 0.10,       // bending stiffness (per constraint pass)
  MU: 0.72,       // contact friction (tacky)
  DRAG: 0.6,      // air drag, 1/s
  CLEAR: 0.024,   // the server keeps the spout this far over the pile while filling ...
  CLEAR_SW: 0.019,// ... and this far while building the swirl
  LIFT_MIN: CUP.H + 0.006,  // the spout's cap never goes inside the cup
  SWIRL_TURNS: 3.2,
  RHO_END: 0.0050,  // the last turn of the swirl, before the server pulls up into the tip
  PEAK_T: 0.2,      // seconds spent lifting with the valve part open (draws up the peak)
  PEAK_RISE: 0.105, // m/s, about the speed the rope comes out at that flow, so the peak stands rather than buckles
  dt: 1 / 600,
  iters: 6,
  rec: 1 / 240,
};

export function simulatePour(opt = {}) {
  const P = { ...POUR, ...opt };
  const { R0, DS, VE, FX, FY, FUSE, KB, MU, DRAG, dt, iters } = P;
  const MAX = 1400;
  const x = new Float64Array(MAX), y = new Float64Array(MAX), z = new Float64Array(MAX);
  const px = new Float64Array(MAX), py = new Float64Array(MAX), pz = new Float64Array(MAX);
  const vx = new Float64Array(MAX), vy = new Float64Array(MAX), vz = new Float64Array(MAX);
  const rad = new Float64Array(MAX), emitT = new Float64Array(MAX), frozenT = new Float64Array(MAX).fill(Infinity);
  const cont = new Uint8Array(MAX), contT = new Float64Array(MAX), fz = new Uint8Array(MAX), still = new Float64Array(MAX);
  // each node's material frame (where its star ridges point), set where it lands and carried for good
  const frN = new Float32Array(MAX * 3), tmpN = new Float64Array(MAX * 3), PP = new Float64Array(MAX * 3);
  const packP = () => { for (let i = Math.max(0, ff - 1); i < n; i++) { PP[i * 3] = x[i]; PP[i * 3 + 1] = y[i]; PP[i * 3 + 2] = z[i]; } };
  let n = 0, ff = 0, pinned = true;

  // frozen nodes in a hash grid (12 mm cells)
  const CELL = 0.012, grid = new Map();
  const SKIP = Math.ceil(2.4 * FX * R0 / DS);
  const key = (i, j, k) => ((i + 512) * 1024 + (j + 512)) * 1024 + (k + 512);
  const addFrozen = i => {
    const kk = key(Math.floor(x[i] / CELL), Math.floor(y[i] / CELL), Math.floor(z[i] / CELL));
    let a = grid.get(kk); if (!a) grid.set(kk, a = []); a.push(i);
  };
  // the pile's height map (2 mm cells), for the server's eye and for a quick "nothing below" test
  const HG = 2e-3, HN = 64, HO = -HN * HG / 2, hmap = new Float32Array(HN * HN).fill(CUP.ZB);
  const hAt = (qx, qz) => {
    const i = Math.min(HN - 1, Math.max(0, Math.floor((qx - HO) / HG))), k = Math.min(HN - 1, Math.max(0, Math.floor((qz - HO) / HG)));
    return hmap[k * HN + i];
  };
  const hUnder = (qx, qz, rr) => {           // highest point within rr of (qx, qz)
    let m = CUP.ZB;
    const n0 = Math.ceil(rr / HG);
    const ci = Math.floor((qx - HO) / HG), ck = Math.floor((qz - HO) / HG);
    for (let k = ck - n0; k <= ck + n0; k++) for (let i = ci - n0; i <= ci + n0; i++) {
      if (i < 0 || k < 0 || i >= HN || k >= HN) continue;
      const dx = HO + (i + 0.5) * HG - qx, dz = HO + (k + 0.5) * HG - qz;
      if (dx * dx + dz * dz > rr * rr) continue;
      m = Math.max(m, hmap[k * HN + i]);
    }
    return m;
  };
  const splat = i => {
    const w = FX * rad[i] * 1.05, top = y[i] + FY * rad[i];
    const n0 = Math.ceil(w / HG), ci = Math.floor((x[i] - HO) / HG), ck = Math.floor((z[i] - HO) / HG);
    for (let k = ck - n0; k <= ck + n0; k++) for (let ii = ci - n0; ii <= ci + n0; ii++) {
      if (ii < 0 || k < 0 || ii >= HN || k >= HN) continue;
      const dx = HO + (ii + 0.5) * HG - x[i], dz = HO + (k + 0.5) * HG - z[i], d2 = (dx * dx + dz * dz) / (w * w);
      if (d2 >= 1) continue;
      const h = y[i] + FY * rad[i] * Math.sqrt(1 - d2);
      if (h > hmap[k * HN + ii]) hmap[k * HN + ii] = h;
    }
    void top;
  };
  const meanFill = () => {
    let s = 0, c = 0;
    const rr = RIM_IN * 0.8;
    for (let k = 0; k < HN; k++) for (let i = 0; i < HN; i++) {
      const dx = HO + (i + 0.5) * HG, dz = HO + (k + 0.5) * HG;
      if (dx * dx + dz * dz > rr * rr) continue;
      s += hmap[k * HN + i]; c++;
    }
    return s / c;
  };

  // ------------------------------------------------------------------ the server's hand (nozzle in the cup's frame)
  const N = [0, P.LIFT_MIN + 0.002, 0], Nv = [0, 0, 0];
  let mode = 'fill', phi = -0.6, psi = 0, tMode = 0, q = 0, E = 0, swirlPhi0 = 0, swirlR0 = 0, swirlY0 = 0, released = false;
  let valveCloseT = -1, releaseT = -1, swirlT = -1, closeY0 = 0, lift = 0;
  const tri = u => { const f = u - Math.floor(u); return f < 0.5 ? 1 - 2 * f : 2 * f - 1; };   // 1 -> 0 -> 1

  function hand(t) {
    const nx0 = N[0], ny0 = N[1], nz0 = N[2];
    let rho, ny;
    const fillTop = meanFill();
    const lay = VE * q;                              // the cup is moved as fast as the rope comes out
    if (mode === 'fill') {
      q = smooth(0.0, 0.14, t);
      const wallR = rIn(Math.min(CUP.H - 0.004, fillTop + R0)) - FX * R0 * 1.04;
      // spiral in from the wall to the middle and back out, one layer each way
      rho = wallR * (0.24 + 0.76 * tri(psi / (Math.PI * 2 * 3.0)));
      const step = lay * dt / Math.max(rho, 0.009);
      phi += step; psi += step;
      const under = hUnder(nx0, nz0, FX * R0 * 1.2);
      ny = Math.max(P.LIFT_MIN, under + P.CLEAR);
      if (fillTop > CUP.H - 0.0075 && t > 1.0) { mode = 'swirl'; tMode = t; swirlPhi0 = phi; swirlT = t; swirlR0 = Math.hypot(nx0, nz0); swirlY0 = ny0; }
    } else if (mode === 'swirl') {
      q = 1;
      const u = (phi - swirlPhi0) / (Math.PI * 2 * P.SWIRL_TURNS);
      const ring = RIM_IN - FX * R0 * 0.9;
      // ease out to the rim for the first ring, then wind in to the peak
      const ue = Math.pow(Math.min(1, u), 1.1);
      rho = (swirlR0 + (ring - swirlR0) * smooth(0, 0.18, u)) * (1 - ue) + P.RHO_END * ue;
      phi += lay * dt / Math.max(rho, 0.008);
      const under = hUnder(nx0, nz0, FX * R0 * 1.1);
      ny = Math.max(swirlY0 * (1 - smooth(0, 0.1, u)), under + P.CLEAR_SW);
      if (u >= 1) { mode = 'close'; tMode = t; valveCloseT = t; closeY0 = ny0; lift = 0; }
    } else {
      // close the valve and drop the cup away: the rope necks and breaks, the tail folds over into the tip
      const a = t - tMode;
      // first the server lifts slowly with the valve still part open, drawing up the peak; then closes and pulls away
      const A1 = P.PEAK_T;
      q = a < A1 ? 1 - 0.3 * smooth(0, 0.08, a) : 0.7 * (1 - smooth(A1, A1 + 0.1, a));
      rho = Math.hypot(nx0, nz0) * (1 - Math.min(1, dt * 10));
      phi += 2 * Math.PI * 0.35 * dt;
      lift += (a < A1 ? P.PEAK_RISE : P.PEAK_RISE + 0.45 * smooth(A1, A1 + 0.12, a)) * dt;
      ny = closeY0 + lift;
      if (!released && a > A1 + 0.06) { released = true; pinned = false; releaseT = t; }
    }
    // a hand is smooth: low-pass the target
    const tx = rho * Math.cos(phi), tz = rho * Math.sin(phi);
    const k = 1 - Math.exp(-dt * 38);
    N[0] += (tx - N[0]) * k; N[2] += (tz - N[2]) * k;
    N[1] = mode === 'close' ? ny : N[1] + (ny - N[1]) * (1 - Math.exp(-dt * 14));
    Nv[0] = (N[0] - nx0) / dt; Nv[1] = (N[1] - ny0) / dt; Nv[2] = (N[2] - nz0) / dt;
  }

  // ------------------------------------------------------------------ constraints
  const inv = i => (fz[i] || (pinned && i === n - 1)) ? 0 : 1;
  function links() {
    for (let i = Math.max(ff - 1, 0); i < n - 1; i++) {
      const a = i, b = i + 1, wa = inv(a), wb = inv(b), w = wa + wb;
      if (w === 0) continue;
      const dx = x[b] - x[a], dy = y[b] - y[a], dz = z[b] - z[a], d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-9;
      const c = (d - DS) / d / w;
      x[a] += dx * c * wa; y[a] += dy * c * wa; z[a] += dz * c * wa;
      x[b] -= dx * c * wb; y[b] -= dy * c * wb; z[b] -= dz * c * wb;
    }
  }
  function bend() {
    for (let i = Math.max(ff, 1); i < n - 1; i++) {
      const wi = inv(i); if (!wi) continue;
      const a = i - 1, b = i + 1, wa = inv(a) * 0.5, wb = inv(b) * 0.5;
      const mx = (x[a] + x[b]) * 0.5, my = (y[a] + y[b]) * 0.5, mz = (z[a] + z[b]) * 0.5;
      const ex = x[i] - mx, ey = y[i] - my, ez = z[i] - mz;
      const w = wi + 0.25 * (wa + wb) * 2, k = KB / w;
      x[i] -= ex * k * wi; y[i] -= ey * k * wi; z[i] -= ez * k * wi;
      x[a] += ex * k * wa; y[a] += ey * k * wa; z[a] += ez * k * wa;
      x[b] += ex * k * wb; y[b] += ey * k * wb; z[b] += ez * k * wb;
    }
    // the rope leaves the spout straight down (it comes out at speed): hold the first centimetre vertical
    if (pinned && n > 2) {
      const e = Math.max(0, E - (n - 1) * DS);
      for (let j = 1; j <= 4 && n - 1 - j >= ff; j++) {
        const i = n - 1 - j, s = [0.7, 0.45, 0.22, 0.1][j - 1];
        x[i] += (N[0] - x[i]) * s; z[i] += (N[2] - z[i]) * s;
        const ty = N[1] - e - j * DS; y[i] += (ty - y[i]) * s;
      }
    }
  }
  function collide(i) {
    if (!inv(i)) return;
    const ri = rad[i];
    // nothing near: skip the search
    if (y[i] - FY * ri > hAt(x[i], z[i]) + 0.03) return;
    let hit = false;
    // paper: floor and wall (froyo presses flat against it)
    const fl = CUP.ZB + FY * ri * 0.98;
    if (y[i] < fl) { y[i] = fl; hit = true; }
    if (y[i] < CUP.H - 0.0015) {
      const r = Math.hypot(x[i], z[i]), lim = rIn(y[i]) - FX * ri * 0.97;
      if (r > lim) { x[i] *= lim / r; z[i] *= lim / r; hit = true; }
    }
    // froyo already laid
    const ci = Math.floor(x[i] / CELL), cj = Math.floor(y[i] / CELL), ck = Math.floor(z[i] / CELL);
    for (let a = ci - 1; a <= ci + 1; a++) for (let b = cj - 2; b <= cj + 1; b++) for (let c = ck - 1; c <= ck + 1; c++) {
      const L = grid.get(key(a, b, c)); if (!L) continue;
      for (let m = 0; m < L.length; m++) {
        const j = L[m];
        if (j > i - SKIP) continue;          // its own neighbours along the rope are not a collision
        const sx = (x[i] - x[j]) / FX, sy = (y[i] - y[j]) / FY, sz = (z[i] - z[j]) / FX;
        const d = Math.sqrt(sx * sx + sy * sy + sz * sz), tgt = (ri + rad[j]) * FUSE;
        if (d >= tgt || d < 1e-9) continue;
        const pu = (tgt - d) / d;
        x[i] += sx * pu * FX; y[i] += sy * pu * FY; z[i] += sz * pu * FX;
        hit = true;
      }
    }
    if (hit) {
      // tacky: most of this step's sliding is cancelled
      x[i] = px[i] + (x[i] - px[i]) * (1 - MU) + 0 * MU;
      z[i] = pz[i] + (z[i] - pz[i]) * (1 - MU);
      if (y[i] < py[i]) y[i] = Math.max(y[i], py[i] - (py[i] - y[i]) * (1 - MU));
      cont[i] = 1;
    }
  }

  // ------------------------------------------------------------------ record
  const frames = [];
  let nextRec = 0;
  function record(t) {
    // only what is still moving is stored (sorted node indices + positions); frozen nodes are in `final`
    let cnt = 0;
    for (let i = ff; i < n; i++) if (!fz[i]) cnt++;
    const ids = new Uint16Array(cnt), pos = new Float32Array(cnt * 3);
    for (let i = ff, o = 0; i < n; i++) {
      if (fz[i]) continue;
      ids[o] = i; pos[o * 3] = x[i]; pos[o * 3 + 1] = y[i]; pos[o * 3 + 2] = z[i]; o++;
    }
    frames.push({ t, n, ff, E, q, N: [N[0], N[1], N[2]], top: pileTop(), ids, pos });
  }
  function pileTop() { let m = CUP.ZB; for (let i = 0; i < hmap.length; i++) if (hmap[i] > m) m = hmap[i]; return m; }

  // ------------------------------------------------------------------ run
  let t = 0, settleUntil = Infinity;
  const TMAX = 16;
  while (t < TMAX) {
    hand(t);
    // feed: the newest node rides out of the spout; a new one starts at the spout every DS of rope
    if (!released) {
      E += VE * q * dt;
      while (E >= n * DS && n < MAX) {
        const i = n++;
        rad[i] = R0 * Math.sqrt(Math.max(q, 0.08));   // less flow, thinner rope (same speed)
        emitT[i] = t;
        x[i] = px[i] = N[0]; y[i] = py[i] = N[1]; z[i] = pz[i] = N[2];
        vx[i] = Nv[0]; vy[i] = Nv[1] - VE * q; vz[i] = Nv[2];
      }
    }
    // predict
    const damp = Math.exp(-DRAG * dt);
    for (let i = ff; i < n; i++) {
      px[i] = x[i]; py[i] = y[i]; pz[i] = z[i];
      cont[i] = 0;
      if (!inv(i)) continue;
      vx[i] *= damp; vy[i] = vy[i] * damp - 9.81 * dt; vz[i] *= damp;
      x[i] += vx[i] * dt; y[i] += vy[i] * dt; z[i] += vz[i] * dt;
    }
    if (pinned && n) {
      const h = n - 1, e = Math.max(0, E - h * DS);
      x[h] = N[0]; y[h] = N[1] - e; z[h] = N[2];
    }
    for (let it = 0; it < iters; it++) {
      links();
      bend();
      if (it >= iters - 2) for (let i = ff; i < n; i++) collide(i);
    }
    links();
    for (let i = ff; i < n; i++) {
      if (!inv(i)) { vx[i] = vy[i] = vz[i] = 0; continue; }
      vx[i] = (x[i] - px[i]) / dt; vy[i] = (y[i] - py[i]) / dt; vz[i] = (z[i] - pz[i]) / dt;
      contT[i] = cont[i] ? contT[i] + dt : 0;
    }
    // freeze whatever has landed and stopped (or hangs still, held up by the rope on either side)
    let framed = false;
    for (let i = ff; i < n - (pinned ? 1 : 0); i++) {
      if (fz[i]) continue;
      const sp = Math.hypot(vx[i], vy[i], vz[i]);
      still[i] = sp < 0.02 ? still[i] + dt : 0;
      if ((cont[i] && (sp < 0.03 || contT[i] > 0.05)) || (still[i] > 0.15 && t - emitT[i] > 0.4) || t > settleUntil) {
        if (!framed) { packP(); ropeFrames(n, PP, ff, tmpN); framed = true; }
        frN[i * 3] = tmpN[i * 3]; frN[i * 3 + 1] = tmpN[i * 3 + 1]; frN[i * 3 + 2] = tmpN[i * 3 + 2];
        fz[i] = 1; frozenT[i] = t; vx[i] = vy[i] = vz[i] = 0;
        addFrozen(i); splat(i);
      }
    }
    while (ff < n && fz[ff]) ff++;
    if (released && settleUntil === Infinity) settleUntil = t + 1.4;
    if (t >= nextRec) { record(t); nextRec += P.rec; }
    if (ff >= n && released) { record(t); break; }
    t += dt;
  }
  packP(); ropeFrames(n, PP, ff, tmpN);
  for (let i = ff; i < n; i++) {
    if (fz[i]) continue;
    frozenT[i] = t; frN[i * 3] = tmpN[i * 3]; frN[i * 3 + 1] = tmpN[i * 3 + 1]; frN[i * 3 + 2] = tmpN[i * 3 + 2];
  }
  ff = n;
  record(t + P.rec);

  // final: the laid rope, in order
  const final = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { final[i * 3] = x[i]; final[i * 3 + 1] = y[i]; final[i * 3 + 2] = z[i]; }
  return {
    params: P, count: n, duration: frames[frames.length - 1].t,
    emitT: emitT.slice(0, n), frozenT: frozenT.slice(0, n), rad: Float32Array.from(rad.slice(0, n)), final,
    frameN: frN.slice(0, n * 3),
    frames, valveCloseT, releaseT, swirlT, heightMap: { cell: HG, n: HN, origin: HO, h: hmap },
  };
}

// Rotation-minimising frames walked back from the spout end (the star's orientation is fixed by the spout, which
// does not turn), written for nodes lo..n-1 into out. Also used by the renderer for the rope still in the air.
export function ropeFrames(n, P, lo, out) {
  if (n < 2) return;
  const tan = (i, o) => {
    const a = Math.max(0, i - 1) * 3, b = Math.min(n - 1, i + 1) * 3;
    const tx = P[b] - P[a], ty = P[b + 1] - P[a + 1], tz = P[b + 2] - P[a + 2];
    const l = Math.hypot(tx, ty, tz) || 1;
    o[0] = tx / l; o[1] = ty / l; o[2] = tz / l;
  };
  const Ti = [0, 0, 0], Tj = [0, 0, 0];
  const h = n - 1;
  tan(h, Ti);
  let nx = 1, ny = 0, nz = 0;
  let d = Ti[0];
  if (Math.abs(d) > 0.95) { nx = 0; nz = 1; d = Ti[2]; }
  nx -= d * Ti[0]; ny -= d * Ti[1]; nz -= d * Ti[2];
  let l = Math.hypot(nx, ny, nz);
  out[h * 3] = nx / l; out[h * 3 + 1] = ny / l; out[h * 3 + 2] = nz / l;
  for (let i = h - 1; i >= lo; i--) {
    const p = i + 1, oi = i * 3, op = p * 3;
    tan(i, Tj); tan(p, Ti);
    const v1x = P[oi] - P[op], v1y = P[oi + 1] - P[op + 1], v1z = P[oi + 2] - P[op + 2];
    const c1 = v1x * v1x + v1y * v1y + v1z * v1z;
    const Nx = out[op], Ny = out[op + 1], Nz = out[op + 2];
    if (c1 < 1e-14) { out[oi] = Nx; out[oi + 1] = Ny; out[oi + 2] = Nz; continue; }
    let k = 2 / c1 * (v1x * Nx + v1y * Ny + v1z * Nz);
    const rx = Nx - k * v1x, ry = Ny - k * v1y, rz = Nz - k * v1z;
    k = 2 / c1 * (v1x * Ti[0] + v1y * Ti[1] + v1z * Ti[2]);
    const tlx = Ti[0] - k * v1x, tly = Ti[1] - k * v1y, tlz = Ti[2] - k * v1z;
    const v2x = Tj[0] - tlx, v2y = Tj[1] - tly, v2z = Tj[2] - tlz;
    const c2 = v2x * v2x + v2y * v2y + v2z * v2z;
    let qx = rx, qy = ry, qz = rz;
    if (c2 > 1e-14) { k = 2 / c2 * (v2x * rx + v2y * ry + v2z * rz); qx -= k * v2x; qy -= k * v2y; qz -= k * v2z; }
    l = Math.hypot(qx, qy, qz) || 1;
    out[oi] = qx / l; out[oi + 1] = qy / l; out[oi + 2] = qz / l;
  }
}

// ------------------------------------------------------------------ queries on a recorded pour

// frame index at time t (frames are evenly spaced except the last)
export function frameAt(rec, t) {
  const F = rec.frames, dtr = rec.params.rec;
  let k = Math.floor(t / dtr);
  k = Math.max(0, Math.min(F.length - 2, k));
  while (k > 0 && F[k].t > t) k--;
  while (k < F.length - 2 && F[k + 1].t <= t) k++;
  const a = F[k], b = F[k + 1];
  const w = b.t > a.t ? Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t))) : 0;
  return { a, b, w, k };
}

// nozzle (in the cup's frame) and flow at time t
export function handAt(rec, t, out) {
  const { a, b, w } = frameAt(rec, t);
  out[0] = a.N[0] + (b.N[0] - a.N[0]) * w;
  out[1] = a.N[1] + (b.N[1] - a.N[1]) * w;
  out[2] = a.N[2] + (b.N[2] - a.N[2]) * w;
  return out;
}

// positions of every node out of the spout at time t, written into out (Float32Array, n*3); returns the count
function find(ids, i) {
  let lo = 0, hi = ids.length - 1;
  while (lo <= hi) { const m = (lo + hi) >> 1, v = ids[m]; if (v === i) return m; if (v < i) lo = m + 1; else hi = m - 1; }
  return -1;
}
export function nodesAt(rec, t, out) {
  const { a, b, w } = frameAt(rec, t);
  const { frozenT, final, emitT } = rec;
  let n = a.n;
  while (n < b.n && emitT[n] <= t) n++;     // nodes born between the two frames appear when they are born
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    if (frozenT[i] <= t) { out[o] = final[o]; out[o + 1] = final[o + 1]; out[o + 2] = final[o + 2]; continue; }
    const ja = find(a.ids, i), jb = find(b.ids, i);
    let ax, ay, az, bx, by, bz;
    if (jb >= 0) { bx = b.pos[jb * 3]; by = b.pos[jb * 3 + 1]; bz = b.pos[jb * 3 + 2]; }
    else { bx = final[o]; by = final[o + 1]; bz = final[o + 2]; }      // frozen by the next frame
    if (ja >= 0) { ax = a.pos[ja * 3]; ay = a.pos[ja * 3 + 1]; az = a.pos[ja * 3 + 2]; }
    else { ax = bx; ay = by; az = bz; }                                  // born after the previous frame
    out[o] = ax + (bx - ax) * w; out[o + 1] = ay + (by - ay) * w; out[o + 2] = az + (bz - az) * w;
  }
  return n;
}

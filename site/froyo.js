// Plays back a baked froyo pour (source/mpm.py -> source/bake_web.py).
//
// The pour is a yield-stress paste simulated with the material point method. Each frame was baked into two
// voxel fields (fill fraction and flavour). Here a frame is decoded (keyframes plus deltas, raw deflate) and
// meshed with marching cubes, so scrubbing the page scrubs a real simulation, forwards or backwards.

import * as THREE from 'three';
import { inflateSync } from 'fflate';
import { edgeTable, triTable } from 'three/addons/objects/MarchingCubes.js';

// the 12 cube edges as corner pairs, and the 8 corners (Paul Bourke's numbering, as three's tables use)
const EDGE = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
const CORNER = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]];

export class FroyoPour {
  constructor(meta, buffer, material, maxTris = 60000) {
    this.meta = meta;
    this.buf = new Uint8Array(buffer);
    const [NX, NY, NZ] = meta.shape;
    this.NX = NX; this.NY = NY; this.NZ = NZ;
    this.D = new Uint8Array(NX * NY * NZ);
    this.T = new Uint8Array(NX * NY * NZ);
    this.cur = -1;
    this.frames = meta.frames;
    const maxV = maxTris * 3;
    this.pos = new Float32Array(maxV * 3);
    this.nor = new Float32Array(maxV * 3);
    this.mm = new Float32Array(maxV);
    this.maxV = maxV;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nor, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('m', new THREE.BufferAttribute(this.mm, 1).setUsage(THREE.DynamicDrawUsage));
    g.setDrawRange(0, 0);
    this.geometry = g;
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = true;
    this.tmp = { p: new Float32Array(36), n: new Float32Array(36), m: new Float32Array(12) };
  }

  _chunk(c) { return inflateSync(this.buf.subarray(c[0], c[0] + c[1])); }

  decode(f) {
    const K = this.meta.key, idx = this.meta.index;
    f = Math.max(0, Math.min(this.frames - 1, f | 0));
    if (f === this.cur) return f;
    const kf = Math.floor(f / K) * K;
    let start;
    if (this.cur >= kf && this.cur < f) start = this.cur + 1;
    else {
      this.D.set(this._chunk(idx[kf].d));
      this.T.set(this._chunk(idx[kf].t));
      start = kf + 1;
    }
    for (let i = start; i <= f; i++) {
      const dd = this._chunk(idx[i].d), dt = this._chunk(idx[i].t);
      const D = this.D, T = this.T;
      for (let j = 0, n = D.length; j < n; j++) { D[j] += dd[j]; T[j] += dt[j]; }   // uint8 wraps
    }
    this.cur = f;
    return f;
  }

  // marching cubes over the whole box; the pile is small so most cells reject on the first corner test
  build() {
    const { NX, NY, NZ, D, T, pos, nor, mm } = this;
    const iso = this.meta.iso, vs = this.meta.vs;
    const [ox, oy, oz] = this.meta.org;
    const sx = 1, sy = NX, sz = NX * NY;
    const off = [0, sx, sx + sy, sy, sz, sz + sx, sz + sx + sy, sz + sy];
    const ep = new Float32Array(36), en = new Float32Array(36), em = new Float32Array(12);
    let nv = 0;
    const grad = (i, j, k, out, o) => {
      const q = k * sz + j * sy + i;
      const ix0 = i > 0 ? q - sx : q, ix1 = i < NX - 1 ? q + sx : q;
      const iy0 = j > 0 ? q - sy : q, iy1 = j < NY - 1 ? q + sy : q;
      const iz0 = k > 0 ? q - sz : q, iz1 = k < NZ - 1 ? q + sz : q;
      out[o] = D[ix0] - D[ix1]; out[o + 1] = D[iy0] - D[iy1]; out[o + 2] = D[iz0] - D[iz1];   // points outward
    };
    const g0 = new Float32Array(3), g1 = new Float32Array(3);
    // the cup, so the froyo surface can be pressed onto the paper (no gaps, nothing pokes through the wall)
    const H_RIM = 0.062, RB = 0.034, SLOPE = (0.0455 - 0.034) / (0.062 - 0.0016 - 0.0015), TWALL = 0.00056 * Math.sqrt(1 + SLOPE * SLOPE), ZB = 0.0068;
    for (let k = 0; k < NZ - 1; k++) {
      for (let j = 0; j < NY - 1; j++) {
        let q = k * sz + j * sy;
        for (let i = 0; i < NX - 1; i++, q++) {
          const v0 = D[q];
          const v1 = D[q + off[1]], v2 = D[q + off[2]], v3 = D[q + off[3]];
          const v4 = D[q + off[4]], v5 = D[q + off[5]], v6 = D[q + off[6]], v7 = D[q + off[7]];
          let ci = 0;
          if (v0 < iso) ci |= 1; if (v1 < iso) ci |= 2; if (v2 < iso) ci |= 4; if (v3 < iso) ci |= 8;
          if (v4 < iso) ci |= 16; if (v5 < iso) ci |= 32; if (v6 < iso) ci |= 64; if (v7 < iso) ci |= 128;
          const bits = edgeTable[ci];
          if (bits === 0) continue;
          for (let e = 0; e < 12; e++) {
            if (!(bits & (1 << e))) continue;
            const a = EDGE[e][0], b = EDGE[e][1];
            const ca = CORNER[a], cb = CORNER[b];
            const va = D[q + off[a]], vb = D[q + off[b]];
            const t = vb === va ? 0.5 : (iso - va) / (vb - va);
            ep[e * 3] = ox + (i + ca[0] + (cb[0] - ca[0]) * t + 0.5) * vs;
            ep[e * 3 + 1] = oy + (j + ca[1] + (cb[1] - ca[1]) * t + 0.5) * vs;
            ep[e * 3 + 2] = oz + (k + ca[2] + (cb[2] - ca[2]) * t + 0.5) * vs;
            {
              const px = ep[e * 3], py = ep[e * 3 + 1];
              if (py < H_RIM) {
                const r = Math.hypot(px, ep[e * 3 + 2]);
                const rin = RB + (Math.max(py, 0.0015) - 0.0015) * SLOPE - TWALL - 0.00025;
                if (r > rin) { const sc = rin / r; ep[e * 3] = px * sc; ep[e * 3 + 2] *= sc; }
                if (py < ZB + 0.0002) ep[e * 3 + 1] = ZB + 0.0002;
              }
            }
            grad(i + ca[0], j + ca[1], k + ca[2], g0, 0);
            grad(i + cb[0], j + cb[1], k + cb[2], g1, 0);
            const nx = g0[0] + (g1[0] - g0[0]) * t, ny = g0[1] + (g1[1] - g0[1]) * t, nz = g0[2] + (g1[2] - g0[2]) * t;
            const l = Math.hypot(nx, ny, nz) || 1;
            en[e * 3] = nx / l; en[e * 3 + 1] = ny / l; en[e * 3 + 2] = nz / l;
            const ta = T[q + off[a]], tb = T[q + off[b]];
            em[e] = (ta + (tb - ta) * t) / 255;
          }
          const base = ci * 16;
          for (let n = 0; triTable[base + n] !== -1 && n < 15; n += 3) {
            if (nv + 3 > this.maxV) { this.geometry.setDrawRange(0, nv); return nv; }
            for (let v = 0; v < 3; v++) {
              const e = triTable[base + n + v];
              pos[nv * 3] = ep[e * 3]; pos[nv * 3 + 1] = ep[e * 3 + 1]; pos[nv * 3 + 2] = ep[e * 3 + 2];
              nor[nv * 3] = en[e * 3]; nor[nv * 3 + 1] = en[e * 3 + 1]; nor[nv * 3 + 2] = en[e * 3 + 2];
              mm[nv] = em[e];
              nv++;
            }
          }
        }
      }
    }
    return nv;
  }

  setFrame(f) {
    const fr = this.decode(f);
    if (fr === this.built) return;
    const nv = this.build();
    this.built = fr;
    const g = this.geometry;
    g.setDrawRange(0, nv);
    g.attributes.position.needsUpdate = true;
    g.attributes.normal.needsUpdate = true;
    g.attributes.m.needsUpdate = true;
    this.mesh.visible = nv > 0;
  }
}

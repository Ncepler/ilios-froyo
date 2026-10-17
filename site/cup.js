// The Ilios cup, built in code at the size of the real one.
//
// The shop pours into white paper food cups: gently tapered, a rolled rim, nearly as tall as they are wide, with a
// printed cream square on the side carrying the gold sun face and ILIOS FROYO. Measured against hands, spouts and
// the drip-tray drains in the shop's videos: 9.6 cm across the rim, 7.4 cm across the base, 8.4 cm tall (a 16 oz
// food cup). The paper, PE lining and gold-foil materials are reused from the cup model (ilios-froyo-cup.glb).
//
// Cup-local frame: metres, Y up, origin at the centre of the cup's foot, the printed side facing +Z.

import * as THREE from 'three';
import { CUP, SLOPE, rOut, rIn, RIM_IN } from './cup-dims.js';

export { CUP, SLOPE, rOut, rIn, RIM_IN };
const { H, RT, RB, ZB, ZU, BEAD } = CUP;

// ------------------------------------------------------------------ profile helpers (r, y) pairs
function arc(cx, cy, r, a0, a1, n) {
  const out = [];
  for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  return out;
}
function fillet(pts, rad, n) {
  // round each interior corner of a polyline
  const out = [pts[0]];
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i], a = pts[i - 1], b = pts[i + 1];
    const da = [a[0] - p[0], a[1] - p[1]], db = [b[0] - p[0], b[1] - p[1]];
    const la = Math.hypot(...da), lb = Math.hypot(...db);
    const ua = [da[0] / la, da[1] / la], ub = [db[0] / lb, db[1] / lb];
    const ang = Math.acos(Math.max(-1, Math.min(1, ua[0] * ub[0] + ua[1] * ub[1])));
    const d = Math.min(rad / Math.tan(ang / 2), la * 0.45, lb * 0.45);
    const p0 = [p[0] + ua[0] * d, p[1] + ua[1] * d], p1 = [p[0] + ub[0] * d, p[1] + ub[1] * d];
    for (let k = 0; k <= n; k++) {
      const t = k / n, s = 1 - t;
      // quadratic bezier through the corner: close enough to a circular fillet at these sizes
      out.push([s * s * p0[0] + 2 * s * t * p[0] + t * t * p1[0], s * s * p0[1] + 2 * s * t * p[1] + t * t * p1[1]]);
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}
function densify(pts, step) {
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / step));
    for (let k = 1; k <= n; k++) out.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]);
  }
  return out;
}

// the cup's cross-section, from the centre of the inside floor, up the inner wall, over the rolled bead, down the
// outside, round the rolled foot and back in under the base. Returns the points and where the inside run ends.
function profile() {
  const inTop = [rIn(H - 0.0019), H - 0.0019], outTop = [rOut(H - 0.0019), H - 0.0019];
  const inside = densify(fillet([[0, ZB], [rIn(ZB), ZB], inTop], 0.0024, 10), 0.004);
  const bead = arc(RT + 0.0003, H - BEAD * 0.55, BEAD, 205 * Math.PI / 180, -160 * Math.PI / 180, 40).slice(1);
  const outside = densify([outTop, [rOut(0.0016), 0.0016]], 0.005).slice(1);
  const foot = arc(RB - 0.00075, 0.0010, 0.00075, 0, -Math.PI, 14).slice(1);
  const under = fillet([[RB - 0.0015, 0.0010], [RB - 0.0015, ZU], [0, ZU]], 0.0006, 6).slice(1);
  const pts = [...inside, ...bead, outTop, ...outside, ...foot, ...under].map(([r, y]) => [Math.max(0, r), y]);
  return { pts, nInside: inside.length };
}

// revolve with smooth normals from the profile tangent, uv = (turns x 6, arclength x 20) like the model's paper
function revolve(pts, segs, splitAt) {
  const n = pts.length;
  const pos = [], nor = [], uv = [], idxIn = [], idxOut = [];
  const s = [0];
  for (let i = 1; i < n; i++) s.push(s[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const n2 = pts.map((p, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    const tr = b[0] - a[0], ty = b[1] - a[1], l = Math.hypot(tr, ty) || 1;
    // the profile walks the paper as one loop (inside up, over the bead, outside down, under), so its left-hand
    // normal is always the visible side: into the cup on the inside, outward on the outside
    return [-ty / l, tr / l];
  });
  for (let j = 0; j <= segs; j++) {
    const th = j / segs * Math.PI * 2, c = Math.cos(th), sn = Math.sin(th);
    for (let i = 0; i < n; i++) {
      const [r, y] = pts[i];
      pos.push(r * sn, y, r * c);
      const [nr, ny] = n2[i];
      nor.push(nr * sn, ny, nr * c);
      uv.push(j / segs * 6, s[i] * 20);
    }
  }
  for (let j = 0; j < segs; j++) for (let i = 0; i < n - 1; i++) {
    const a = j * n + i, b = (j + 1) * n + i;
    (i < splitAt - 1 ? idxIn : idxOut).push(a, a + 1, b, b, a + 1, b + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex([...idxOut, ...idxIn]);
  g.addGroup(0, idxOut.length, 0);
  g.addGroup(idxOut.length, idxIn.length, 1);
  return g;
}

// a square patch conformed to the conical wall, centred on the front (+Z)
function wallPatch(D, yc, lift, flipV = false, nu = 48, nv = 48) {
  const pos = [], nor = [], uv = [], idx = [];
  const cs = Math.sqrt(1 + SLOPE * SLOPE);
  for (let iv = 0; iv <= nv; iv++) {
    const v = iv / nv, y = yc + (v - 0.5) * D / cs, r = rOut(y) + lift;
    for (let iu = 0; iu <= nu; iu++) {
      const u = iu / nu, th = (u - 0.5) * D / r;
      pos.push(r * Math.sin(th), y, r * Math.cos(th));
      nor.push(Math.sin(th) / cs, -SLOPE / cs, Math.cos(th) / cs);
      uv.push(u, flipV ? 1 - v : v);
    }
  }
  for (let iv = 0; iv < nv; iv++) for (let iu = 0; iu < nu; iu++) {
    const a = iv * (nu + 1) + iu;
    idx.push(a, a + 1, a + nu + 2, a, a + nu + 2, a + nu + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

// the printed cream square behind the foil sun (soft-cornered, a hair of ink texture)
function labelTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const x = c.getContext('2d');
  x.clearRect(0, 0, 256, 256);
  const r = 10, m = 6;
  x.fillStyle = '#efe5cf';
  x.beginPath();
  x.moveTo(m + r, m); x.arcTo(256 - m, m, 256 - m, 256 - m, r); x.arcTo(256 - m, 256 - m, m, 256 - m, r);
  x.arcTo(m, 256 - m, m, m, r); x.arcTo(m, m, 256 - m, m, r); x.closePath(); x.fill();
  const d = x.getImageData(0, 0, 256, 256);
  for (let i = 0; i < d.data.length; i += 4) {
    const n = (Math.random() - 0.5) * 7;
    d.data[i] += n; d.data[i + 1] += n; d.data[i + 2] += n;
  }
  x.putImageData(d, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// pull the paper and foil materials out of the loaded cup model
export function cupMaterials(gltfScene) {
  const mats = {};
  gltfScene.traverse(o => {
    if (!o.isMesh) return;
    (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { mats[m.name] = m; });
  });
  const print = mats['Ilios Paper (print side)'] || new THREE.MeshStandardMaterial({ color: '#f4f1ea', roughness: 0.7 });
  const inside = mats['Ilios Paper (PE-coated inside)'] || new THREE.MeshStandardMaterial({ color: '#f6f3ee', roughness: 0.38 });
  const foil = mats['Ilios Gold Foil'] || new THREE.MeshStandardMaterial({ color: '#b48a44', metalness: 1, roughness: 0.3 });
  return { print, inside, foil };
}

// build the cup: returns a Group with Cup, CupLabel and Emblem meshes
export function buildCup(mats) {
  const { pts, nInside } = profile();
  const grp = new THREE.Group();
  grp.name = 'IliosCup';
  const body = new THREE.Mesh(revolve(pts, 160, nInside), [mats.print, mats.inside]);
  body.name = 'Cup';
  grp.add(body);
  // printed label square, then the foil emblem over it
  const D = 0.050, yc = 0.0455;
  const labelMat = new THREE.MeshStandardMaterial({
    map: labelTexture(), transparent: true, roughness: 0.62, metalness: 0,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1, depthWrite: false,
  });
  const label = new THREE.Mesh(wallPatch(D * 0.98, yc, 0.00004), labelMat);
  label.name = 'CupLabel';
  label.renderOrder = 1;
  grp.add(label);
  const foil = mats.foil.clone();
  foil.transparent = true;
  foil.depthWrite = false;
  foil.polygonOffset = true;
  foil.polygonOffsetFactor = -2;
  foil.polygonOffsetUnits = -2;
  // glTF textures are not flipped: v runs top-down
  const emblem = new THREE.Mesh(wallPatch(D * 0.9, yc + 0.0006, 0.00008, true), foil);
  emblem.name = 'Emblem';
  emblem.renderOrder = 2;
  grp.add(emblem);
  grp.traverse(o => { if (o.isMesh) { o.castShadow = o === body; o.receiveShadow = true; } });
  return grp;
}

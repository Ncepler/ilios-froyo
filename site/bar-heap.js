// The heaps of toppings in their bowls: the bowls themselves, and the settled piles (source/toppings/heap.py simulates each
// pile with rigid body physics in the bowl's own profile; here they are drawn as instanced pieces).

import * as THREE from 'three';

export function bowlGeometry(type) {
  if (type === 'tray') {
    const g = new THREE.BoxGeometry(0.2, 0.035, 0.14, 4, 1, 4);
    g.translate(0, 0.0175, 0);
    return g;
  }
  const hob = type === 'hobnail', R = hob ? 0.095 : 0.102, H = hob ? 0.085 : 0.07, base = hob ? 0.055 : 0.06;
  const prof = [];
  const N = 22;
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    prof.push(new THREE.Vector2(base + (R - base) * Math.sin(t * Math.PI / 2) ** (hob ? 0.8 : 1.2), t * H));
  }
  for (let i = N; i >= 0; i--) {
    const t = i / N;
    prof.push(new THREE.Vector2(Math.max(0, base + (R - base) * Math.sin(t * Math.PI / 2) ** (hob ? 0.8 : 1.2) - 0.006), t * H + 0.006 * (1 - t) + (i === 0 ? 0.006 : 0)));
  }
  const g = new THREE.LatheGeometry(prof, 72);
  const p = g.attributes.position, seed = Math.random() * 10;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), a = Math.atan2(z, x), r = Math.hypot(x, z), t = y / H;
    let dr = 0, dy = 0;
    if (!hob) {
      // the organic bowls: a soft, uneven, wavy rim
      dr = r * 0.06 * Math.sin(a * 3 + seed) * t * t;
      dy = 0.007 * Math.sin(a * 5 + seed * 2) * t * t;
    } else if (r > base - 0.001 && t > 0.1 && t < 0.92) {
      // hobnail: rows of little beads on the outside
      const rowT = t * 9, row = Math.round(rowT);
      const col = a * 13 / Math.PI + (row % 2) * 0.5;
      const d = Math.hypot(rowT - row, (col - Math.round(col)) * 0.9);
      if (r > (base + (R - base) * Math.sin(t * Math.PI / 2) ** 0.8) - 0.003) dr = Math.max(0, 0.0028 * (1 - d * d * 4));
    }
    p.setXYZ(i, x * (1 + dr / r), y + dy, z * (1 + dr / r));
  }
  g.computeVertexNormals();
  return g;
}


const hash = (i, j) => { let h = Math.imul(i * 374761393 + j * 668265263, 1274126177); h ^= h >>> 15; return ((h >>> 0) % 10000) / 10000; };

// data.instances: [variant, x, y, z, qx, qy, qz, qw, ao] in the bowl's frame; variants: [{ geo, cls }]
export function buildHeap(data, variants, matFor) {
  const grp = new THREE.Group();
  const per = variants.map(() => []);
  for (const row of data.instances) if (per[row[0]]) per[row[0]].push(row);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1), col = new THREE.Color();
  variants.forEach((v, vi) => {
    const rows = per[vi];
    if (!rows.length) return;
    const im = new THREE.InstancedMesh(v.geo, matFor(v), rows.length);
    rows.forEach((r, i) => {
      p.set(r[1], r[2], r[3]); q.set(r[4], r[5], r[6], r[7]);
      im.setMatrixAt(i, m4.compose(p, q, one));
      // each piece is a touch different (ripeness, how the light caught it), darker where the others shut it in
      const k = r[8] * (0.9 + 0.2 * hash(i, vi));
      im.setColorAt(i, col.setRGB(k, k * (0.97 + 0.06 * hash(vi, i)), k * (0.95 + 0.1 * hash(i + 7, vi))));
    });
    im.castShadow = true; im.receiveShadow = true;
    im.computeBoundingSphere();
    grp.add(im);
  });
  grp.userData.top = data.top;
  return grp;
}

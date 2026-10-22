// Top it off: the Ilios topping bar, live.
//
// The bar is laid out the way it is in the shop (docs/ILIOS-FIELD-NOTES.md): one long quartz counter behind a low
// glass guard, the bowls in two staggered rows in the order you meet them after the machines (fresh fruit and the
// raspberry sauce, then candy and crunch), then the warm station (pistachio kataifi, Nutella, Biscoff and the
// cinnamon rolls in their icing, in white skillets on a warming plate, with the honey jar and the olive oil in
// front), then the register under the gold sun. Your cup sits on the counter in front of the glass; scrolling slides
// it down the line. Click any bowl where it sits: its own utensil (wooden spoon, tongs, the scoop, the soup spoon,
// the ladle, the disher, the jar) lifts a serving out, carries it over and tips it in. Pieces fall onto the froyo's
// real surface (the simulated swirl) and stay where they land; a sauce is laid along the path of the spoon and runs
// down where the swirl is steep. Everything goes on in the order you click it, on top of what is already there.
// Nothing is re-done.

import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { buildCup, CUP, RIM_IN, rIn } from './cup.js';
import { FroyoRope } from './pour.js';
import * as PC from './bar-pieces.js';
import { bowlGeometry, buildHeap } from './bar-heap.js';
import { Post } from './post.js';

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOut = t => 1 - Math.pow(1 - t, 3);
const lerp = (a, b, t) => a + (b - a) * t;
const isTouch = () => matchMedia('(pointer: coarse)').matches;

// ------------------------------------------------------------------ the bar, in line order
// kind: pieces | sauce | dollop | rolls | oil.  tool: spoon | tongs | scoop | soup | ladle | disher | metal | jar | jug
export const BAR = [
  // fresh fruit and sauce
  { key: 'strawberry', label: 'Strawberries', zone: 'fruit', bowl: 'hobnail', tool: 'spoon', glb: 'strawberry', n: 12, heap: '#c4222b' },
  { key: 'mango', label: 'Golden Mango', zone: 'fruit', tool: 'spoon', glb: 'mango', n: 11, heap: '#f0a414' },
  { key: 'granola', label: 'Granola', note: 'Nut free, gluten free', zone: 'fruit', tool: 'spoon', glb: 'granola', n: 22, heap: '#9b6532' },
  { key: 'dates', label: 'Dates', zone: 'fruit', tool: 'tongs', glb: 'date', n: 5, heap: '#40200f' },
  { key: 'figs', label: 'Fresh Figs', zone: 'fruit', tool: 'tongs', glb: 'fig', n: 3, heap: '#5b2c43' },
  { key: 'raspberry', label: 'Raspberry Sauce', zone: 'fruit', bowl: 'tray', tool: 'ladle', kind: 'sauce', sauce: 'raspberry' },
  { key: 'kiwi', label: 'Kiwi', zone: 'fruit', tool: 'tongs', make: PC.kiwi, n: 9, heap: '#7fb22a' },
  { key: 'blueberries', label: 'Blueberries', zone: 'fruit', tool: 'spoon', make: PC.blueberry, n: 13, heap: '#2b3150' },
  { key: 'grapes', label: 'Green Grapes', zone: 'fruit', tool: 'tongs', make: PC.grape, n: 7, heap: '#a9c45a' },
  { key: 'honeydew', label: 'Honeydew', zone: 'fruit', tool: 'spoon', make: PC.honeydew, n: 7, heap: '#cfe2a1' },
  { key: 'coconut', label: 'Coconut', zone: 'fruit', bowl: 'hobnail', tool: 'spoon', make: PC.coconut, n: 70, heap: '#f4efe4', baseTone: 0.93, fine: true },
  { key: 'pineapple', label: 'Pineapple', zone: 'fruit', tool: 'tongs', make: PC.pineapple, n: 8, heap: '#f2c632' },
  // candy and crunch
  { key: 'gummies', label: 'Gummy Bears', zone: 'candy', tool: 'tongs', make: PC.gummyBear, n: 9, heap: '#ef7a2a', chalk: true },
  { key: 'mms', label: "M&M's", zone: 'candy', tool: 'scoop', make: PC.mm, n: 18, heap: '#d6261f', chalk: true },
  { key: 'sprinkles', label: 'Rainbow Sprinkles', zone: 'candy', tool: 'spoon', glb: 'nonpareil', model: 'nonpareil', tint: PC.RAINBOW_JIMMIES, jimmies: PC.RAINBOW_JIMMIES, n: 260, heap: '#e9a0a8', fine: true, chalk: true },
  { key: 'brownies', label: 'Brownie Bites', zone: 'candy', tool: 'tongs', glb: 'brownie', n: 6, heap: '#4a2815', chalk: true },
  { key: 'rainbow', label: 'Rainbow Cookies', zone: 'candy', tool: 'tongs', glb: 'rainbow', n: 4, heap: '#4a2d20', chalk: true },
  { key: 'chips', label: 'Chocolate Chips', zone: 'candy', tool: 'spoon', glb: 'chip', n: 34, heap: '#24120b', chalk: true },
  { key: 'jimmies', label: 'Chocolate Sprinkles', zone: 'candy', tool: 'soup', make: s => PC.jimmy(s, PC.CHOC_JIMMIES), model: 'jimmy', tint: PC.CHOC_JIMMIES, n: 160, heap: '#3b2216', fine: true, chalk: true },
  { key: 'krispies', label: 'Rice Krispies Treats', zone: 'candy', tool: 'tongs', make: PC.krispie, n: 5, heap: '#e1c189', chalk: true },
  { key: 'oreo', label: 'Oreo Crumble', zone: 'candy', tool: 'tongs', make: PC.oreo, n: 14, heap: '#1d1514', chalk: true },
  { key: 'cookies', label: 'Mini Cookies', zone: 'candy', tool: 'tongs', make: PC.miniCookie, n: 5, heap: '#c08440', chalk: true },
  { key: 'biscoffbits', label: 'Biscoff Cookies', zone: 'candy', tool: 'tongs', glb: 'biscoff', n: 9, heap: '#a8672b', chalk: true },
  { key: 'dough', label: 'Cookie Dough', zone: 'candy', bowl: 'hobnail', tool: 'disher', make: PC.cookieDough, n: 3, heap: '#d9b984', chalk: true },
  { key: 'sour', label: 'Sour Strips', zone: 'candy', tool: 'tongs', make: PC.sourStrip, n: 4, heap: '#e8352c', chalk: true },
  { key: 'worms', label: 'Gummy Worms', zone: 'candy', tool: 'tongs', make: PC.gummyWorm, n: 3, heap: '#5fbf3c', chalk: true },
  { key: 'chunks', label: 'Chocolate Chunks', zone: 'candy', tool: 'tongs', make: PC.chocChunk, n: 5, heap: '#5a3423', chalk: true },
  // the warm station (served by the staff from behind the glass)
  { key: 'pistachio', label: 'Pistachio Kataifi', zone: 'warm', bowl: 'skillet', tool: 'disher', kind: 'dollop', heap: '#9a9a52', sign: 'PISTACHIO' },
  { key: 'nutella', label: 'Nutella', zone: 'warm', bowl: 'skillet', tool: 'metal', kind: 'sauce', sauce: 'nutella', sign: 'NUTELLA' },
  { key: 'biscoff', label: 'Biscoff Cookie Butter', zone: 'warm', bowl: 'skillet', tool: 'metal', kind: 'sauce', sauce: 'biscoff', sign: 'BISCOFF' },
  { key: 'cinnamon', label: 'Cinnamon Roll', zone: 'warm', bowl: 'skillet', tool: 'metal', kind: 'rolls', sauce: 'icing', sign: 'CINNAMON ROLL' },
  { key: 'honey', label: 'Honey', zone: 'warm', bowl: 'jar', tool: 'jar', kind: 'sauce', sauce: 'honey', sign: 'HONEY' },
  { key: 'oil', label: 'Olive Oil + Sea Salt', zone: 'warm', bowl: 'jug', tool: 'jug', kind: 'oil', sauce: 'oil' },
];
BAR.forEach(b => { b.kind = b.kind || 'pieces'; b.bowl = b.bowl || (b.zone === 'warm' ? 'skillet' : 'organic'); });

const SAUCE = {
  raspberry: { color: '#a3101f', rough: 0.12, coat: 0.9, r: 0.0016, opacity: 1, sheen: 0 },
  nutella: { color: '#3a1d10', rough: 0.22, coat: 0.8, r: 0.0024, opacity: 1 },
  biscoff: { color: '#a5621f', rough: 0.2, coat: 0.8, r: 0.0023, opacity: 1 },
  icing: { color: '#f6f0e2', rough: 0.3, coat: 0.5, r: 0.0026, opacity: 1 },
  honey: { color: '#c47c08', rough: 0.05, coat: 1, r: 0.0014, opacity: 0.86, emissive: '#5a2f00' },
  oil: { color: '#b9a531', rough: 0.03, coat: 1, r: 0.0012, opacity: 0.7, emissive: '#2a2600' },
};

// layout (metres): counter top at y = 0, the line runs along +x, you stand at +z
const COL = 0.25, Z_FRONT = 0.065, Z_BACK = -0.175, Z_CUP = 0.285, Z_GLASS = 0.205;
const SELF = BAR.filter(b => b.zone !== 'warm');
const WARM = BAR.filter(b => b.zone === 'warm');

export async function initBar(o) {
  const { canvas, froyoRec, froyoMaterial, cupMats, toppingsScene, modelledScene, roomScene, dpr, reduced, ui, heaps = {} } = o;

  // ------------------------------------------------------------------ renderer and room
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(dpr());
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  // food has to keep its own colours: the neutral tone mapper does not shift hue or wash out saturated albedo
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 0.88;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  const WALL = new THREE.Color('#d8cfc0');
  scene.background = WALL.clone();
  scene.fog = new THREE.Fog(WALL, 4.2, 9);
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.26;
  const camera = new THREE.PerspectiveCamera(30, 1, 0.03, 8);

  // light: the shop's warm downlights from above and in front, a soft sky, and a cool rim from behind the line that picks
  // out the edges of the glossy and translucent pieces. Less flat ambient than before: shadows keep their depth.
  scene.add(new THREE.HemisphereLight('#fff4e6', '#8f8272', 0.26));
  const key = new THREE.DirectionalLight('#ffe2bd', 3.3);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -0.85, right: 0.85, top: 0.6, bottom: -0.6, near: 0.2, far: 4 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 0.0015;
  key.shadow.radius = 3.5;
  scene.add(key, key.target);
  const fill = new THREE.DirectionalLight('#eef0ff', 0.32);
  fill.position.set(1.5, 1.0, 2.5);
  scene.add(fill);
  const rim = new THREE.DirectionalLight('#dfe8ff', 0.9);
  rim.position.set(0.8, 0.9, -1.6);
  scene.add(rim);

  // ambient occlusion and the tone mapping; the quality drops by itself if the device cannot keep up
  const post = new Post(renderer, scene, camera, { quality: isTouch() ? 1 : 2 });
  let ema = 16, slow = 0;

  // ------------------------------------------------------------------ materials
  // (built in small slices that give the page back between them: this runs while you are still scrolling the pour)
  const mats = await makeMaterials(roomScene);
  const pieceMat = PC.pieceMaterial(), jellyMat = PC.pieceMaterial({ jelly: true });
  const matFor = v => v.cls ? PC.toppingMaterial(v.cls) : v.jelly ? jellyMat : pieceMat;

  // ------------------------------------------------------------------ layout
  const items = [];
  SELF.forEach((b, i) => {
    const col = Math.floor(i / 2), back = i % 2 === 1;
    items.push({ def: b, x: col * COL + (back ? COL / 2 : 0), z: back ? Z_BACK : Z_FRONT, back });
  });
  const selfEnd = items[items.length - 1].x + COL * 0.9;
  const W0 = selfEnd + 0.35;                 // warm station starts here
  const skillets = WARM.filter(b => b.bowl === 'skillet');
  skillets.forEach((b, i) => items.push({ def: b, x: W0 + i * 0.27, z: -0.12, back: true, staff: true }));
  const afterPans = W0 + (skillets.length - 1) * 0.27;
  items.push({ def: WARM.find(b => b.key === 'honey'), x: afterPans + 0.36, z: 0.09, back: false });
  items.push({ def: WARM.find(b => b.key === 'oil'), x: afterPans + 0.6, z: 0.07, back: false });
  const X_REG = afterPans + 1.25;            // the register
  const X0 = -0.05, X1 = X_REG - 0.05;       // where the cup travels
  const LEN = X_REG + 0.9;

  // ------------------------------------------------------------------ the counter, glass, back wall
  buildRoom(scene, mats, LEN, W0, afterPans, X_REG, roomScene);

  // ------------------------------------------------------------------ bowls, heaps, labels, utensils
  const glb = toppingsScene ? PC.glbPieces(toppingsScene) : {};        // the older procedural-era pieces: only a fallback now
  const modelled = modelledScene ? PC.modelledPieces(modelledScene) : {};
  const kataifi = modelled.kataifi || glb.kataifi || [];
  const pickables = [];
  let built = 0;
  for (const it of items) {
    if (++built % 3 === 0) await idle();
    it.variants = variantsFor(it.def, glb, modelled);
    it.rods = it.def.jimmies && modelled.jimmy ? modelled.jimmy.map(v => ({ ...v, tint: it.def.jimmies })) : null;
    const hd = heaps[it.def.key];
    if (hd && it.rods && it.variants.length + it.rods.length === hd.variants) it.variants = it.variants.concat(it.rods);      // rainbow sprinkles: nonpareils and jimmies in one pile
    it.heapData = hd && it.variants.length === hd.variants ? hd : null;
    it.group = new THREE.Group();
    it.group.position.set(it.x, 0, it.z);
    scene.add(it.group);
    it.matFor = matFor;
    buildStation(it, mats, pieceMat, jellyMat);
    it.group.traverse(m => { if (m.isMesh) { m.userData.item = it; pickables.push(m); } });
    it.label = buildLabel(it, mats);
    if (it.label) { scene.add(it.label); it.label.traverse(m => { if (m.isMesh) { m.userData.item = it; pickables.push(m); } }); }
    it.tool = buildTool(it.def.tool, it, mats);
    scene.add(it.tool.root);
    if (it.def.tool === 'jar' || it.def.tool === 'jug') it.tool.root.traverse(m => { if (m.isMesh) pickables.push(m); });
    it.busy = false;
  }

  // ------------------------------------------------------------------ the cup, with the swirl you poured
  const cup = buildCup(cupMats);
  cup.position.set(X0, 0, Z_CUP);
  cup.rotation.y = -0.35;
  scene.add(cup);
  const froyo = new FroyoRope(froyoRec, froyoMaterial);
  froyo.setTime(froyoRec.duration);
  cup.add(froyo.mesh);
  const layer = new THREE.Group();          // everything you add, in the cup's frame
  cup.add(layer);
  const surf = new Surface(froyoRec);
  const froyoPos0 = froyo.pos.slice(), froyoNor0 = froyo.nor.slice();
  const nFroyoV = froyo.vertCount;
  surf.fromMesh(froyo.pos, nFroyoV);
  surf.f = surf.base.slice();
  const squashes = [];                       // pistachio scoops pressing the soft tip down: [x, z, r, yTop]
  function applySquashes() {
    froyo.pos.set(froyoPos0); froyo.nor.set(froyoNor0);
    const P = froyo.pos;
    for (const [x0, z0, R, y0] of squashes) {
      for (let v = 0; v < nFroyoV; v++) {
        const dx = P[v * 3] - x0, dz = P[v * 3 + 2] - z0, d = Math.hypot(dx, dz);
        if (d > R) continue;
        // the scoop's underside: a shallow bowl; soft serve above it is pressed down under it and bulges out a bit
        const yb = y0 - 0.010 * (d / R) ** 2, y = P[v * 3 + 1];
        if (y <= yb) continue;
        // full press under the middle of the scoop, easing to none at its rim (a hard edge there cut the coils into a zigzag)
        const t = d / R, u = t <= 0.5 ? 0 : (t - 0.5) / 0.5, w = 1 - u * u * (3 - 2 * u);
        const over = y - yb;
        P[v * 3 + 1] = y - over * 0.92 * w;
        const sp = 1 + Math.min(0.25, over * 8) * w * (1 - 0.5 * t);
        P[v * 3] = x0 + dx * sp; P[v * 3 + 2] = z0 + dz * sp;
      }
    }
    const g = froyo.geometry;
    g.attributes.position.clearUpdateRanges(); g.attributes.position.needsUpdate = true;
    g.attributes.normal.clearUpdateRanges();
    if (squashes.length) g.computeVertexNormals(); else g.attributes.normal.needsUpdate = true;
    surf.fromMesh(froyo.pos, nFroyoV);
    surf.f = surf.base.slice();
  }

  // ------------------------------------------------------------------ state
  const added = [];                         // [{ item, objects: [] }] in the order added
  const queue = [];
  const flying = [];                        // pieces in the air (cup frame)
  const sauces = [];                        // drizzles being laid
  let active = [];                          // running utensil actions
  let version = 0, shownVersion = -1;

  // ------------------------------------------------------------------ scroll
  let target = 0, shown = 0, dbgCam = null;
  const camPos = new THREE.Vector3(), camTgt = new THREE.Vector3();
  function place(p) {
    const x = lerp(X0, X1, p);
    cup.position.x = x;
    const a = camera.aspect, portrait = a < 1;
    // close behind your cup, looking down over it at the bar; on a phone, further back and higher
    // at the register, step back and lift the eye: your cup, the tablet and the gold sun on the wall
    const reg = smooth(0.88, 1, p);
    const back = lerp(portrait ? 0.6 + (1 - a) * 0.3 : 0.54, portrait ? 1.7 : 1.15, reg);
    camPos.set(x + (portrait ? 0 : 0.025) + (portrait ? -0.08 : 0.02) * reg, lerp(portrait ? 0.46 : 0.37, portrait ? 0.42 : 0.36, reg), Z_CUP + back);
    camTgt.set(x + (portrait ? -0.08 : 0.06) * reg, lerp(portrait ? 0.075 : 0.065, portrait ? 0.32 : 0.2, reg), lerp(Z_CUP - 0.3, -0.45, reg));
    if (dbgCam) { camPos.copy(dbgCam[0]); camTgt.copy(dbgCam[1]); }
    camera.position.copy(camPos);
    camera.lookAt(camTgt);
    key.position.set(x - 0.6, 1.6, 1.2);
    key.target.position.set(x, 0, -0.1);
    // which part of the line you are at
    ui.onProgress && ui.onProgress(p, x < selfEnd - COL * 0.2 ? (x < items.find(i => i.def.zone === 'candy').x - 0.1 ? 'fruit' : 'candy') : x < X_REG - 0.45 ? 'warm' : 'pay');
  }

  // ------------------------------------------------------------------ actions
  function add(item) {
    if (!item) return;
    queue.push(item);
    ui.onAdd && ui.onAdd(item.def, added.length + queue.length);
    pump();
    wake();
  }
  function pump() {
    // one serving at a time, in order; the next starts once the last one is on its way down into the cup
    if (!queue.length) return;
    if (active.some(a => !a.released)) return;
    const item = queue[0];
    if (item.busy) return;
    queue.shift();
    item.busy = true;
    const entry = { item, objects: [] };
    added.push(entry);
    version++;
    active.push(makeAction(item, entry));
  }

  function makeAction(item, entry) {
    const def = item.def, tool = item.tool;
    const a = { item, entry, t: 0, released: false, done: false, dropped: false };
    const speed = reduced ? 2.2 : 1;
    const rest = tool.rest;
    const sauceLike = def.kind === 'sauce' || def.kind === 'oil' || def.kind === 'rolls';
    const T = { dip: tool.dig ? 0.32 : 0.12, lift: 0.24, go: 0.62, pour: sauceLike ? (def.kind === 'rolls' ? 1.35 : 1.15) : def.kind === 'dollop' ? 0.5 : 0.42, back: 0.6 };
    const t1 = T.dip, t2 = t1 + T.lift, t3 = t2 + T.go, t4 = t3 + T.pour, t5 = t4 + T.back;
    a.portion = makePortion(item, entry);
    if (a.portion) tool.scoop.add(a.portion.obj);
    const S0 = tool.restScoop.clone();                         // the working end, at rest in its bowl
    const S1 = S0.clone().add(new THREE.Vector3(0, 0.09, 0.06));  // lifted out
    const over = new THREE.Vector3(), S = new THREE.Vector3(), C = new THREE.Vector3(), Pz = new THREE.Vector3();
    a.step = (dt) => {
      a.t += dt * speed;
      const t = a.t;
      // over the cup (the cup can slide along while this runs)
      const top = surf.top + 0.05;
      cup.localToWorld(over.set(0, top, 0));
      if (t < t1) {
        // dig in: down into the heap, tipping the scoop
        const u = ease(t / t1);
        S.copy(S0); S.y -= tool.dig * Math.sin(u * Math.PI) + 0.003 * u;
        tool.place(S, rest.q, u * 0.35, 0, 0);
        if (a.portion) a.portion.obj.scale.setScalar(Math.max(0.001, u));
      } else if (t < t2) {
        const u = ease((t - t1) / T.lift);
        tool.place(S.copy(S0).lerp(S1, u), rest.q, 0.35 * (1 - u), u, 0);
        if (a.portion) a.portion.obj.scale.setScalar(1);
      } else if (t < t3) {
        // over the glass to the cup
        const u = ease((t - t2) / T.go);
        C.copy(S1).lerp(over, 0.5); C.y = Math.max(S1.y, over.y) + 0.035;
        tool.place(bez(S1, C, over, u, S), rest.q, 0, 1, 0);
      } else if (t < t4) {
        const u = (t - t3) / T.pour;
        if (!sauceLike) {
          tool.place(over, rest.q, 0, 1, ease(Math.min(1, u * 1.6)));
          if (!a.dropped && u > 0.22) { a.dropped = true; a.released = true; release(a); }
        } else {
          // the rolls go on first, then the stream: the tool sweeps back and forth over the swirl
          const rolls = def.kind === 'rolls';
          if (rolls && !a.dropped) {
            tool.place(over, rest.q, 0, 1, ease(Math.min(1, u * 5)));
            if (u > 0.12) { a.dropped = true; release(a); }
          } else {
            const v = rolls ? clamp((u - 0.22) / 0.78) : u;
            const k = drizzlePath(def.sauce === 'icing' ? 'cinnamon' : def.key, v, Pz);
            cup.localToWorld(S.set(k.x, top - 0.012, k.z));
            tool.place(S, rest.q, 0, 1, tool.pourTip);
            if (!a.sauce) { a.sauce = startSauce(def, entry); a.released = true; }
            a.sauce.feed(tool.tipWorld(_tip), v);
          }
        }
      } else if (t < t5) {
        if (a.sauce && !a.sauce.ended) a.sauce.end();
        const u = ease((t - t4) / T.back);
        C.copy(over).lerp(S0, 0.5); C.y = Math.max(over.y, S0.y) + 0.08;
        tool.place(bez(over, C, S0, u, S), rest.q, 0, 1 - u, (1 - u) * (sauceLike ? tool.pourTip : 1));
      } else {
        tool.place(S0, rest.q, 0, 0, 0);
        a.done = true;
        item.busy = false;
        version++;
      }
      return !a.done;
    };
    return a;
  }

  // the serving that rides in the tool, then falls: instanced pieces (one draw per shape, however many sprinkles)
  const _mt = new THREE.Matrix4(), _p = new THREE.Vector3(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _tip = new THREE.Vector3();
  function makePortion(item, entry) {
    const def = item.def;
    if (def.kind === 'sauce' || def.kind === 'oil') return null;
    const obj = new THREE.Group();
    const bodies = [];
    if (def.kind === 'dollop') {
      const d = makeDollop();
      d.mesh.position.set(0, 0.006, 0);
      obj.add(d.mesh);
      bodies.push({ kind: 'dollop', mesh: d.mesh, dollop: d, r: 0.012, p: new THREE.Vector3(), q: new THREE.Quaternion() });
    } else {
      const n = def.kind === 'rolls' ? 2 : def.n;
      let vs = def.kind === 'rolls' ? (item.variants.length ? item.variants.slice(0, 2) : [PC.miniRoll(3), PC.miniRoll(7)]) : item.variants.slice();
      if (def.jimmies) vs = vs.concat(item.rods || [1, 2, 3].map(k => PC.jimmy(k, def.jimmies)));
      const R = PC.rng(1000 + added.length * 31);
      const per = vs.map(() => 0);
      const which = [];
      for (let i = 0; i < n; i++) { const vi = i % vs.length; which.push(vi); per[vi]++; }
      const ims = vs.map((v, vi) => {
        const im = new THREE.InstancedMesh(v.geo, matFor(v), Math.max(1, per[vi]));
        im.count = per[vi];
        im.castShadow = !def.fine; im.receiveShadow = true; im.frustumCulled = false;
        obj.add(im);
        return im;
      });
      const used = vs.map(() => 0), rr = item.tool.cap;
      for (let i = 0; i < n; i++) {
        const vi = which[i], v = vs[vi], im = ims[vi], idx = used[vi]++;
        const a = R() * Math.PI * 2, d = Math.sqrt(R()) * rr;
        const b = { kind: 'piece', im, idx, v, r: v.r, flat: !!v.flat || def.kind === 'rolls', p: new THREE.Vector3(Math.cos(a) * d, (R() * 0.6 + 0.2) * rr * 0.7, Math.sin(a) * d * 0.8), q: new THREE.Quaternion().setFromEuler(new THREE.Euler(R() * 6.3, R() * 6.3, R() * 6.3)) };
        if (def.kind === 'rolls') b.q.identity();
        im.setMatrixAt(idx, _mt.compose(b.p, b.q, _s.set(1, 1, 1)));
        if (v.tint) im.setColorAt(idx, v.tint[(R() * v.tint.length) | 0]);
        bodies.push(b);
      }
      ims.forEach(im => { im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; entry.objects.push(im); });
    }
    obj.scale.setScalar(0.001);
    return { obj, bodies };
  }

  // let go of the serving: every piece becomes a falling body in the cup's frame
  function release(a) {
    const portion = a.portion;
    if (!portion) return;
    a.portion = null;
    cup.updateMatrixWorld(true);
    portion.obj.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(cup.matrixWorld).invert();
    const R = PC.rng(77 + added.length * 13);
    const def = a.item.def, moved = new Set();
    for (const b of portion.bodies) {
      if (b.kind === 'dollop') {
        _mt.multiplyMatrices(inv, b.mesh.matrixWorld).decompose(_p, _q, _s);
        b.mesh.removeFromParent();
        b.mesh.position.copy(_p); b.mesh.quaternion.copy(_q); b.mesh.scale.set(1, 1, 1);
        layer.add(b.mesh);
        a.entry.objects.push(b.mesh);
        b.p.copy(_p); b.q.copy(_q);
      } else {
        // instance matrix (scoop space) -> cup space
        const M = new THREE.Matrix4().multiplyMatrices(inv, b.im.matrixWorld);
        _mt.compose(b.p, b.q, _s.set(1, 1, 1)).premultiply(M).decompose(b.p, b.q, _s);
        moved.add(b.im);
      }
      // each piece is thrown (by the tip of the spoon) toward its own spot on the swirl: a spoonful scatters over
      // the whole top, a couple of pieces from the tongs land closer together
      const fine = def.fine;
      const spread = def.kind === 'rolls' ? 0.014 : b.kind === 'dollop' ? 0.004 : fine ? 0.034 : def.n <= 6 ? 0.026 : 0.032;
      const ang = R() * Math.PI * 2, d = Math.sqrt(R()) * spread;
      const tx = Math.cos(ang) * d, tz = Math.sin(ang) * d;
      const fall = Math.sqrt(2 * Math.max(0.01, b.p.y - surf.height(tx, tz)) / 9.81);
      b.vx = (tx - b.p.x) / fall; b.vz = (tz - b.p.z) / fall; b.vy = 0;
      b.spin = new THREE.Vector3(R() - 0.5, R() - 0.5, R() - 0.5).multiplyScalar(def.kind === 'rolls' ? 0 : 9);
      b.sink = def.kind === 'rolls' ? 0.62 : b.kind === 'dollop' ? 0 : def.fine ? 0.25 : 0.42;
      b.delay = R() * (fine ? 0.18 : 0.08);
      b.entry = a.entry;
      flying.push(b);
    }
    for (const im of moved) {
      im.removeFromParent();
      im.position.set(0, 0, 0); im.quaternion.identity(); im.scale.set(1, 1, 1);
      layer.add(im);
    }
    for (const b of portion.bodies) if (b.im) b.im.setMatrixAt(b.idx, _mt.compose(b.p, b.q, _s.set(1, 1, 1)));
    for (const im of moved) im.instanceMatrix.needsUpdate = true;
  }

  // ------------------------------------------------------------------ falling and landing (cup frame)
  const _n = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0), _yaw = new THREE.Quaternion(), _e = new THREE.Euler();
  function stepFlying(dt) {
    const dirty = new Set();
    for (let i = flying.length - 1; i >= 0; i--) {
      const f = flying[i];
      if (f.delay > 0) { f.delay -= dt; continue; }
      f.vy -= 9.81 * dt;
      f.p.x += f.vx * dt; f.p.z += f.vz * dt; f.p.y += f.vy * dt;
      {
        // nothing gets past the rim: whatever reaches it drops inside
        const rr = Math.hypot(f.p.x, f.p.z), lim = RIM_IN * 0.9;
        if (rr > lim) { f.p.x *= lim / rr; f.p.z *= lim / rr; const vr = (f.vx * f.p.x + f.vz * f.p.z) / lim; if (vr > 0) { f.vx -= vr * f.p.x / lim; f.vz -= vr * f.p.z / lim; } }
      }
      f.vx *= Math.pow(0.6, dt); f.vz *= Math.pow(0.6, dt);
      if (f.spin.lengthSq()) { _e.set(f.spin.x * dt, f.spin.y * dt, f.spin.z * dt); f.q.multiply(_q.setFromEuler(_e)); }
      const r = f.r;
      let h = surf.height(f.p.x, f.p.z);
      let landed = false;
      if (f.p.y - r * (1 - f.sink) * 0.9 <= h) {
        landed = true;
        // soft serve is cold and tacky, so a piece stays about where it touched; on a steep flank it slides down to
        // the next ledge of the swirl first
        let x = f.p.x, z = f.p.z;
        if (f.kind !== 'dollop' && surf.height(x, z) - surf.froyo(x, z) > r * 0.7) {
          // it hit another piece: it tumbles off to a free spot next to it
          const a0 = Math.random() * Math.PI * 2;
          search: for (const ring of [1.3, 2.1, 2.9, 3.8]) for (let j = 0; j < 9; j++) {
            const a = a0 + j / 9 * Math.PI * 2, qx = x + Math.cos(a) * r * ring, qz = z + Math.sin(a) * r * ring;
            if (Math.hypot(qx, qz) > RIM_IN * 0.86) continue;
            if (surf.height(qx, qz) - surf.froyo(qx, qz) < r * 0.45) { x = qx; z = qz; break search; }
          }
        }
        const ledge = f.roll ? 0.86 : f.flat ? 0.74 : 0.68;
        for (let k = 0; k < 26; k++) {
          surf.normal(x, z, _n);
          if (_n.y > ledge) break;
          const g = Math.hypot(_n.x, _n.z) || 1;
          x += _n.x / g * 0.0011; z += _n.z / g * 0.0011;
          const rr = Math.hypot(x, z);
          if (rr > RIM_IN * 0.88) { x *= RIM_IN * 0.88 / rr; z *= RIM_IN * 0.88 / rr; break; }
        }
        h = surf.height(x, z);
        {
          const lim = rIn(Math.min(CUP.H, h)) - r * 0.9, rr = Math.hypot(x, z);
          if (h < CUP.H && rr > lim) { x *= lim / rr; z *= lim / rr; h = surf.height(x, z); }
        }
        surf.normal(x, z, _n);
        if (f.kind === 'dollop') {
          // the scoop is heavy and the froyo is soft: the tip under it is pressed down to about 1.6 cm below its top
          squashes.push([0.35 * x, 0.35 * z, 0.03, h - 0.02]);
          f.entry.squash = squashes[squashes.length - 1];
          applySquashes();
          rebuildSurface();
          h = surf.height(x, z);
          f.dollop.land(x, h, z, surf);
          surf.splat(x, z, 0.024, h + 0.014);
          f.entry.marks = (f.entry.marks || []).concat([[x, z, 0.024, h + 0.014]]);
        } else {
          f.p.set(x, h + r * (1 - f.sink), z);
          if (f.flat) {
            // lie on the froyo: thin axis between the surface normal and straight up (it settles into the soft
            // surface rather than clinging to a slope), any heading, a little rock
            _n.lerp(_up, f.roll ? 0.75 : 0.4).normalize();
            _q.setFromUnitVectors(_up, _n);
            _yaw.setFromAxisAngle(_up, Math.random() * Math.PI * 2);
            f.q.copy(_q).multiply(_yaw).multiply(_q.setFromEuler(_e.set((Math.random() - 0.5) * 0.3, 0, (Math.random() - 0.5) * 0.3)));
          }
          const top = h + r * (0.8 - f.sink * 0.6);
          surf.splat(x, z, r * 0.85, top);
          (f.entry.marks = f.entry.marks || []).push([x, z, r * 0.85, top]);
        }
        flying.splice(i, 1);
      }
      if (f.im) { f.im.setMatrixAt(f.idx, _mt.compose(f.p, f.q, _s.set(1, 1, 1))); dirty.add(f.im); }
      else if (f.kind !== 'dollop' || !landed) { f.mesh.position.copy(f.p); f.mesh.quaternion.copy(f.q); }
    }
    for (const im of dirty) im.instanceMatrix.needsUpdate = true;
  }

  // ------------------------------------------------------------------ sauces: laid along the tool's path
  const sauceMats = {};
  function sauceMat(k) {
    if (sauceMats[k]) return sauceMats[k];
    const s = SAUCE[k];
    return (sauceMats[k] = new THREE.MeshPhysicalMaterial({
      color: s.color, roughness: s.rough, metalness: 0, clearcoat: s.coat, clearcoatRoughness: 0.08,
      emissive: s.emissive || '#000000', emissiveIntensity: 1, transparent: s.opacity < 1, opacity: s.opacity,
      specularIntensity: 1, ior: 1.45, depthWrite: s.opacity >= 1,
    }));
  }
  function startSauce(def, entry) {
    const s = SAUCE[def.sauce];
    const line = new SauceLine(s.r, sauceMat(def.sauce), surf, cup);
    layer.add(line.mesh, line.stream);
    entry.objects.push(line.mesh, line.stream);
    (entry.lines = entry.lines || []).push(line);
    const sauce = {
      ended: false,
      feed(tipWorld, u) {
        // stream from the tip straight down onto whatever is under it, laid where it lands
        cup.worldToLocal(_p.copy(tipWorld));
        const h = surf.height(_p.x, _p.z);
        if (Number.isFinite(h) && u > 0.04 && u < 0.97) line.push(_p.x, h, _p.z);
        line.streamFrom(_p, h, u > 0.02 && u < 0.97);
        this.lastTip = _p.clone();
      },
      end() {
        this.ended = true;
        line.streamFrom(_p, 0, false);
        line.flush();
        line.onSettled = () => { rebuildSurface(); line.makeDrips(def.sauce === 'honey' || def.sauce === 'oil' ? 1.5 : 1); };
        line.finish();
        sauces.push(line);
        if (def.kind === 'oil') sprinkleSalt(entry);
      },
    };
    return sauce;
  }
  function sprinkleSalt(entry) {
    const R = PC.rng(91 + added.length);
    const vsalt = modelled.salt && modelled.salt.length ? modelled.salt : [PC.saltFlake(3)], n = 26;
    const cnt = vsalt.map(() => 0);
    for (let i = 0; i < n; i++) cnt[i % vsalt.length]++;
    const ims = vsalt.map((v, vi) => {
      const im = new THREE.InstancedMesh(v.geo, v.cls ? PC.toppingMaterial(v.cls) : pieceMat, cnt[vi]);
      im.frustumCulled = false;
      layer.add(im);
      entry.objects.push(im);
      return im;
    });
    const used = vsalt.map(() => 0);
    for (let i = 0; i < n; i++) {
      const vi = i % vsalt.length, v = vsalt[vi], im = ims[vi], idx = used[vi]++;
      const a = R() * Math.PI * 2, d = Math.sqrt(R()) * 0.024;
      const b = { kind: 'piece', im, idx, v, r: v.r, flat: true, p: new THREE.Vector3(Math.cos(a) * d, surf.top + 0.05 + R() * 0.03, Math.sin(a) * d), q: new THREE.Quaternion(), vx: 0, vz: 0, vy: 0, spin: new THREE.Vector3(), sink: 0.1, delay: 0.25 + R() * 0.45, entry };
      im.setMatrixAt(idx, _mt.compose(b.p, b.q, _s.set(1, 1, 1)));
      flying.push(b);
    }
    ims.forEach(im => { im.instanceMatrix.needsUpdate = true; });
  }

  // the pistachio kataifi: a heavy dollop from the disher that slumps and drapes over the swirl
  function makeDollop() {
    const geo = PC.weld(new THREE.IcosahedronGeometry(0.0165, 5));
    const base = geo.attributes.position.array.slice();
    const nv = base.length / 3;
    const col = new Float32Array(nv * 4);
    const green = new THREE.Color('#8f9248'), dark = new THREE.Color('#6e6a33'), gold = new THREE.Color('#c99a4e');
    const tmp = new THREE.Color();
    for (let i = 0; i < nv; i++) {
      const x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
      // pistachio cream with shredded kataifi folded through: stringy streaks of toasted pastry
      const strand = Math.abs(PC.noise3(x * 900, y * 180, z * 900));
      const n = PC.fbm(x * 600, y * 600, z * 600);
      tmp.copy(green).lerp(dark, 0.5 + 0.6 * n);
      if (strand < 0.09) tmp.lerp(gold, 0.75);
      col[i * 4] = tmp.r; col[i * 4 + 1] = tmp.g; col[i * 4 + 2] = tmp.b; col[i * 4 + 3] = 0.55;
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 4));
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, pieceMat);
    mesh.castShadow = true;
    const R0 = 0.0165;
    if (kataifi.length) {
      // golden shreds of toasted kataifi on top
      const R = PC.rng(dollops.length * 7 + 5);
      for (let i = 0; i < 7; i++) {
        const v = kataifi[i % kataifi.length];
        const sh = new THREE.Mesh(v.geo, v.cls ? PC.toppingMaterial(v.cls) : pieceMat);
        const a = R() * Math.PI * 2, d = R() * 0.6;
        sh.userData.dir = [Math.cos(a) * d, Math.sin(a) * d];
        sh.scale.setScalar(0.55 + R() * 0.25);
        sh.rotation.set(R() * 6, R() * 6, R() * 6);
        sh.castShadow = true;
        sh.position.set(Math.cos(a) * d * R0, R0 * 1.8, Math.sin(a) * d * R0);
        mesh.add(sh);
      }
    }
    const d = {
      mesh, t: -1,
      land(x, h, z, S) {
        // the blob comes to rest here and slumps: it spreads, and its underside settles onto the froyo under it, so
        // it drapes over the top of the swirl like the real filling does
        this.t = 0; this.x = x; this.z = z; this.h = h;
        mesh.position.set(x, h, z);
        mesh.quaternion.identity();
        this.under = new Float32Array(nv);
        for (let i = 0; i < nv; i++) this.under[i] = S.height(x + base[i * 3] * 1.32, z + base[i * 3 + 2] * 1.32) - h;
      },
      step(dt) {
        if (this.t < 0 || this.t >= 1) return false;
        this.t = Math.min(1, this.t + dt / 0.5);
        const k = easeOut(this.t), p = geo.attributes.position.array;
        // thick paste: it slumps into a soft, wide scoop sitting on the top of the swirl, settling a few millimetres
        // into the soft froyo; where the froyo is higher than the scoop's underside the scoop rides up over it
        // its underside sags onto the froyo (up to ~1.5 cm down over the shoulders), and it keeps its thickness on top
        for (let i = 0; i < nv; i++) {
          const bx = base[i * 3], by = base[i * 3 + 1], bz = base[i * 3 + 2];
          const wob = 1 + 0.12 * PC.fbm(bx * 260, by * 260, bz * 260);
          const ax = bx * wob, az = bz * wob, ay = by * wob + R0;
          const sx = bx * 1.32 * wob, sz = bz * 1.32 * wob;
          const rho = Math.min(1, Math.hypot(bx, bz) / R0);
          const bot = Math.max(this.under[i] + 0.0005, -0.004 - 0.009 * rho * rho);
          const thick = R0 * 1.25 * Math.pow(Math.max(0, 1 - rho * rho), 0.55) * wob;
          const sy = by < 0 ? bot + thick * 0.12 * (1 + by / R0) : bot + thick * Math.pow(Math.max(0, by / R0), 0.5) * 0.88 + thick * 0.12;
          p[i * 3] = ax + (sx - ax) * k; p[i * 3 + 1] = ay + (sy - ay) * k; p[i * 3 + 2] = az + (sz - az) * k;
        }
        geo.attributes.position.needsUpdate = true;
        geo.computeVertexNormals();
        // the shreds ride on the top of the scoop
        for (const sh of mesh.children) {
          const [u, w] = sh.userData.dir, rho = Math.hypot(u, w), cap = Math.sqrt(Math.max(0, 1 - rho * rho));
          const bot = Math.max(this.under[0] + 0.0005, -0.004 - 0.009 * rho * rho);
          sh.position.set(u * R0 * 1.32 * k + u * R0 * (1 - k), (bot + R0 * 1.25 * cap) * k + (1 - k) * R0 * (1 + cap), w * R0 * 1.32 * k + w * R0 * (1 - k));
        }
        return true;
      },
    };
    dollops.push(d);
    return d;
  }
  const dollops = [];

  // ------------------------------------------------------------------ undo / clear
  function undo() {
    if (active.length || flying.length) return;
    const e = added.pop();
    if (!e) return;
    e.objects.forEach(m => { m.removeFromParent(); });
    version++;
    rebuildSurface();
    ui.onChange && ui.onChange(added.map(a => a.item.def));
    wake();
  }
  function clear() {
    if (active.length || flying.length) { queue.length = 0; return; }
    while (added.length) added.pop().objects.forEach(m => m.removeFromParent());
    queue.length = 0;
    version++;
    rebuildSurface();
    ui.onChange && ui.onChange([]);
    wake();
  }
  function rebuildSurface() {
    // the height map is the froyo plus whatever is still on it
    const keep = new Set(added.map(e => e.squash).filter(Boolean));
    if (squashes.some(q => !keep.has(q))) { for (let i = squashes.length - 1; i >= 0; i--) if (!keep.has(squashes[i])) squashes.splice(i, 1); applySquashes(); }
    surf.reset();
    for (const e of added) {
      for (const m of e.marks || []) surf.splat(m[0], m[1], m[2], m[3]);
      for (const l of e.lines || []) l.reSplat();
    }
  }

  // ------------------------------------------------------------------ picking
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let hover = null;
  function pick(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false)[0];
    return hit ? hit.object.userData.item : null;
  }
  function setHover(it, e) {
    if (it !== hover) {
      if (hover) highlight(hover, false);
      hover = it;
      if (hover) highlight(hover, true);
      canvas.style.cursor = hover ? 'pointer' : '';
      wake();
    }
    ui.onHover && ui.onHover(hover ? hover.def : null, e);
  }
  function highlight(it, on) {
    it.group.traverse(m => { if (m.isMesh && m.material && m.material.emissive && m.userData.glow !== undefined) m.material.emissiveIntensity = on ? 0.18 : 0; });
    if (it.label) it.label.position.y = it.label.userData.y + (on ? 0.004 : 0);
  }
  canvas.addEventListener('pointermove', e => { if (e.pointerType === 'mouse' && !drag.on) setHover(pick(e), e); }, { passive: true });
  canvas.addEventListener('pointerleave', () => setHover(null));

  // ------------------------------------------------------------------ swipe (phones): the cup follows your finger
  // On touch screens the bar is one screen tall and you move along it by dragging sideways (the way you would walk the
  // line): the world under your finger moves with it, and a flick coasts. Vertical drags are left to the page
  // (touch-action: pan-y on the canvas), so scrolling past the bar still works.
  let swipe = false, swiped = false, down = null;
  const drag = { id: -1, x: 0, p: 0, lx: 0, lt: 0, v: 0, on: false };
  let coast = 0, glide = null;                  // inertia (progress per second); an eased jump to a station
  const GAIN = 1.25;                            // a little faster than 1:1: the line is long
  const _w0 = new THREE.Vector3(), _w1 = new THREE.Vector3();
  function pxPerP() {
    // CSS pixels the counter moves across the screen for one unit of progress, measured at the cup
    cup.updateMatrixWorld(true);
    cup.getWorldPosition(_w0); _w1.copy(_w0); _w1.x += 0.1;
    _w0.project(camera); _w1.project(camera);
    return Math.max(1, Math.abs(_w1.x - _w0.x) * 0.5 * canvas.clientWidth / 0.1 * (X1 - X0));
  }
  function endDrag(e) {
    if (e.pointerId !== drag.id) return;
    const was = drag.on;
    drag.id = -1; drag.on = false;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* already released */ }
    coast = was && e.timeStamp - drag.lt < 90 ? clamp(drag.v, -2.4, 2.4) : 0;
    wake();
  }
  canvas.addEventListener('pointerdown', e => {
    down = { x: e.clientX, y: e.clientY, t: performance.now() };
    if (!swipe || !e.isPrimary) return;
    drag.id = e.pointerId; drag.x = e.clientX; drag.p = target; drag.lx = e.clientX; drag.lt = e.timeStamp; drag.v = 0;
    drag.on = false; coast = 0; glide = null;
    try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* touch pointers are captured implicitly */ }
  });
  canvas.addEventListener('pointermove', e => {
    if (!swipe || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x;
    if (!drag.on) {
      if (Math.abs(dx) < 7) return;               // not yet a drag: could still be a tap
      drag.on = true; drag.x = e.clientX; drag.p = target; drag.lx = e.clientX; drag.lt = e.timeStamp;
      if (!swiped) { swiped = true; ui.onSwipe && ui.onSwipe(); }
      setHover(null);
      return;
    }
    const now = e.timeStamp, dp = -(e.clientX - drag.lx) * GAIN / pxPerP();
    const dtm = Math.max(1, now - drag.lt);
    drag.v = 0.7 * drag.v + 0.3 * (dp / dtm * 1000);
    drag.lx = e.clientX; drag.lt = now;
    target = shown = clamp(drag.p - (e.clientX - drag.x) * GAIN / pxPerP());
    wake();
  }, { passive: true });
  canvas.addEventListener('pointerup', endDrag);
  canvas.addEventListener('pointercancel', endDrag);
  // a sideways trackpad or wheel gesture moves along the bar too
  canvas.addEventListener('wheel', e => {
    if (!swipe || Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return;
    e.preventDefault();
    target = shown = clamp(target + e.deltaX * GAIN / pxPerP());
    glide = null; coast = 0; wake();
  }, { passive: false });

  canvas.addEventListener('pointerup', e => {
    if (!down) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (moved > 10 || drag.on) return;   // a drag or a scroll, not a tap
    const it = pick(e);
    if (it) add(it);
  });

  // ------------------------------------------------------------------ loop
  let raf = null, last = 0, visible = false;
  function frame(now) {
    raf = null;
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    const k = 1 - Math.pow(1 - 0.12, dt * 60);
    if (swipe) {
      // direct: the cup is where your finger left it; a flick coasts and a station chip glides
      if (glide) {
        glide.t = Math.min(1, glide.t + dt / glide.d);
        target = shown = lerp(glide.from, glide.to, ease(glide.t));
        if (glide.t >= 1) glide = null;
      } else if (!drag.on && Math.abs(coast) > 0.004) {
        target = clamp(target + coast * dt);
        if (target <= 0 || target >= 1) coast = 0;
        coast *= Math.exp(-dt / 0.42);
        shown = target;
      } else if (!drag.on) { coast = 0; shown = target; }
    } else {
      shown += (target - shown) * k;
      if (Math.abs(target - shown) < 0.00005) shown = target;
    }
    place(shown);
    active = active.filter(a => a.step(dt));
    pump();
    stepFlying(dt);
    for (const d of dollops) d.step(dt);
    for (const s of sauces) s.step(dt);
    let moving = Math.abs(target - shown) > 0.00005 || drag.on || glide || Math.abs(coast) > 0.004 || active.length || flying.length || queue.length || dollops.some(d => d.t >= 0 && d.t < 1) || sauces.some(s => s.busy);
    post.render();
    // frame governor: a device that cannot hold ~35 fps while the bar moves gives up the occlusion, then the soft shadows
    if (moving && dt < 0.09) {
      ema += (dt * 1000 - ema) * 0.08;
      if (ema > 29 && post.quality > 0 && ++slow > 45) { post.setQuality(post.quality - 1); post.setSize(canvas.clientWidth, canvas.clientHeight); slow = 0; ema = 16; }
    }
    if (moving && visible) raf = requestAnimationFrame(frame);
    if (version !== shownVersion) { shownVersion = version; ui.onChange && ui.onChange(added.map(a => a.item.def)); }
  }
  let paused = false;
  function wake() { if (raf === null && visible && !paused) { last = performance.now(); raf = requestAnimationFrame(frame); } }
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(dpr());
    renderer.setSize(w, h, false);
    post.setSize(w, h);
    camera.aspect = w / h;
    camera.fov = w / h < 1 ? 46 : 33;
    camera.updateProjectionMatrix();
    wake();
  }
  addEventListener('resize', resize);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) { resize(); wake(); } }).observe(canvas);
  resize();
  place(0);
  // compile every shader off the main thread where the browser can, before the bar is first seen
  try { await renderer.compileAsync(scene, camera); } catch (e) { /* older three/browsers: compiles on first draw */ }

  const api = {
    setProgress(p) { if (swipe) return; target = clamp(p); wake(); },
    // swipe mode: horizontal drags move along the bar instead of the page's scroll
    setSwipe(on) { swipe = !!on; coast = 0; glide = null; drag.id = -1; drag.on = false; if (swipe) shown = target; wake(); },
    // glide to the start of a station of the line ('fruit' | 'candy' | 'warm' | 'pay')
    goTo(zone) {
      const cx = items.find(i => i.def.zone === 'candy').x - 0.1 + 0.02;
      const x = zone === 'fruit' ? X0 : zone === 'candy' ? cx : zone === 'warm' ? selfEnd - COL * 0.2 + 0.02 : X_REG - 0.45 + 0.02;
      const to = clamp((x - X0) / (X1 - X0));
      if (swipe) { glide = { from: shown, to, t: 0, d: 0.9 }; coast = 0; } else target = to;
      wake();
    },
    add(key) { add(items.find(i => i.def.key === key)); },
    undo, clear,
    get items() { return items; },
    scene, camera, post, renderer, render: () => post.render(),
    jump(p) { target = shown = clamp(p); place(shown); post.render(); },
    get progress() { return shown; },
    get busy() { return active.length + flying.length + queue.length; },
    step(n = 1, dt = 1 / 60) { for (let i = 0; i < n; i++) { active = active.filter(a => a.step(dt)); pump(); stepFlying(dt); dollops.forEach(d => d.step(dt)); sauces.forEach(s => s.step(dt)); } place(shown); if (version !== shownVersion) { shownVersion = version; ui.onChange && ui.onChange(added.map(a => a.item.def)); } },
    get added() { return added.map(a => a.item.def.key); },
    get surf() { return surf; },
    debugCam(p, t) { dbgCam = p ? [new THREE.Vector3(...p), new THREE.Vector3(...t)] : null; place(shown); },
    pause(on) { paused = on; if (on && raf !== null) { cancelAnimationFrame(raf); raf = null; } else wake(); },
    xOf(key) { const it = items.find(i => i.def.key === key); return it ? (it.x - X0) / (X1 - X0) : 0; },
  };
  return api;
}

// ======================================================================================================== helpers

const _b0 = new THREE.Vector3(), _b1 = new THREE.Vector3();
function bez(a, c, b, t, out) {
  _b0.copy(a).lerp(c, t); _b1.copy(c).lerp(b, t);
  return out.copy(_b0).lerp(_b1, t);
}

// the path a server's hand takes laying a sauce over the swirl (cup frame), u: 0..1
function drizzlePath(kind, u, out) {
  if (kind === 'cinnamon' || kind === 'pistachio') {
    // a pour over the middle with a small circle
    const a = u * Math.PI * 2 * 1.2;
    out.x = Math.cos(a) * 0.009; out.z = Math.sin(a) * 0.009;
    return out;
  }
  const ang = { raspberry: 0.4, nutella: 1.2, biscoff: 2.0, honey: 2.7, oil: 0.9 }[kind] || 0;
  if (kind === 'nutella' || kind === 'biscoff' || kind === 'raspberry') {
    // from a spoon: a ribbon wound round the swirl, from its shoulders in toward the top
    const turns = kind === 'raspberry' ? 1.8 : 1.6;
    const a = ang + u * Math.PI * 2 * turns, r = 0.024 * (1 - 0.75 * u) + 0.002;
    out.x = Math.cos(a) * r; out.z = Math.sin(a) * r;
    return out;
  }
  // from the honey jar or the oil jug: a thin stream swung back and forth in soft S-curves as it travels across
  const along = (u - 0.5) * 0.05, swing = Math.sin(u * Math.PI * 5) * 0.022 * Math.sqrt(Math.max(0, 1 - (along / 0.03) ** 2));
  out.x = swing * Math.cos(ang) - along * Math.sin(ang);
  out.z = swing * Math.sin(ang) + along * Math.cos(ang);
  return out;
}

// ------------------------------------------------------------------ the froyo's surface, as a height map (cup frame)
class Surface {
  constructor(rec) {
    this.rec = rec;
    this.N = 96; this.S = 0.0012; this.O = -this.N * this.S / 2;
    this.h = new Float32Array(this.N * this.N);
    this.reset();
    this.f = this.h.slice();            // the froyo alone, without anything on it
  }
  setBase(h) { this.base = h; this.f = h.slice(); }
  froyo(x, z) { const h = this.h; this.h = this.f; const v = this.height(x, z); this.h = h; return v; }
  // the froyo's own surface, from its mesh (every ridge), as the base everything lands on
  fromMesh(pos, count) {
    const { N, S, O } = this, h = new Float32Array(N * N).fill(-1);
    for (let v = 0; v < count; v++) {
      const x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2];
      const i = Math.floor((x - O) / S), k = Math.floor((z - O) / S);
      if (i < 0 || k < 0 || i >= N || k >= N) continue;
      if (y > h[k * N + i]) h[k * N + i] = y;
    }
    // close pinholes between vertices
    for (let pass = 0; pass < 2; pass++) {
      const g = h.slice();
      for (let k = 1; k < N - 1; k++) for (let i = 1; i < N - 1; i++) {
        const c = k * N + i;
        const m = Math.max(g[c - 1], g[c + 1], g[c - N], g[c + N]);
        if (g[c] < m - 0.0012) h[c] = m - 0.0006;
      }
    }
    // the froyo fills the cup out to the paper: any cell inside the rim the mesh did not reach takes its neighbours'
    // height, so nothing can fall down a crack between the swirl and the cup wall
    for (let pass = 0; pass < 24; pass++) {
      let filled = 0;
      const g = h.slice();
      for (let k = 1; k < N - 1; k++) for (let i = 1; i < N - 1; i++) {
        const c = k * N + i;
        if (g[c] >= 0) continue;
        const x = O + (i + 0.5) * S, z = O + (k + 0.5) * S;
        if (x * x + z * z > RIM_IN * RIM_IN) continue;
        const m = Math.max(g[c - 1], g[c + 1], g[c - N], g[c + N]);
        if (m >= 0) { h[c] = m - 0.0004; filled++; }
      }
      if (!filled) break;
    }
    this.base = h;
    this.reset();
  }
  reset() {
    const { FX, FY } = this.rec.params, F = this.rec.final, R = this.rec.rad, h = this.h;
    if (this.base) h.set(this.base);
    else {
      h.fill(-1);
      for (let i = 0; i < this.rec.count; i++) {
        const x = F[i * 3], y = F[i * 3 + 1], z = F[i * 3 + 2];
        this.splat(x, z, FX * R[i], y, FY * R[i]);
      }
    }
    this.top = 0;
    for (let i = 0; i < h.length; i++) if (h[i] > this.top) this.top = h[i];
  }
  // a dome of radius r around (x, z) whose top is at y (+ hgt for an ellipse cap)
  splat(x, z, r, y, hgt = 0) {
    const { N, S, O, h } = this;
    const n0 = Math.ceil(r / S) + 1, ci = Math.floor((x - O) / S), ck = Math.floor((z - O) / S);
    for (let k = ck - n0; k <= ck + n0; k++) for (let i = ci - n0; i <= ci + n0; i++) {
      if (i < 0 || k < 0 || i >= N || k >= N) continue;
      const dx = O + (i + 0.5) * S - x, dz = O + (k + 0.5) * S - z, d2 = (dx * dx + dz * dz) / (r * r);
      if (d2 >= 1) continue;
      const v = y + hgt * Math.sqrt(1 - d2) - (hgt ? 0 : r * 0.35 * d2);
      if (v > h[k * N + i]) h[k * N + i] = v;
    }
    if (y + hgt > this.top) this.top = y + hgt;
  }
  height(x, z) {
    const { N, S, O, h } = this;
    const fx = clamp((x - O) / S - 0.5, 0, N - 1.001), fz = clamp((z - O) / S - 0.5, 0, N - 1.001);
    const i = fx | 0, k = fz | 0, u = fx - i, v = fz - k;
    const a = h[k * N + i], b = h[k * N + i + 1], c = h[(k + 1) * N + i], d = h[(k + 1) * N + i + 1];
    const m = Math.max(a, b, c, d);
    if (m < 0) return CUP.ZB;
    const f = q => (q < 0 ? m - 0.004 : q);
    return lerp(lerp(f(a), f(b), u), lerp(f(c), f(d), u), v);
  }
  normal(x, z, out) {
    const e = this.S * 1.5;
    const dx = (this.height(x + e, z) - this.height(x - e, z)) / (2 * e), dz = (this.height(x, z + e) - this.height(x, z - e)) / (2 * e);
    return out.set(-dx, 1, -dz).normalize();
  }
}

// ------------------------------------------------------------------ a sauce line: laid on the surface as the tool moves
class SauceLine {
  constructor(r, mat, surf, cup) {
    this.r = r; this.surf = surf; this.cup = cup;
    this.pts = [];
    this.SEG = 10; this.MAX = 900;
    const nv = this.MAX * this.SEG;
    this.pos = new Float32Array(nv * 3); this.nor = new Float32Array(nv * 3);
    const idx = new Uint32Array((this.MAX - 1) * this.SEG * 6);
    let o = 0;
    for (let i = 0; i < this.MAX - 1; i++) for (let k = 0; k < this.SEG; k++) {
      const a = i * this.SEG + k, b = i * this.SEG + (k + 1) % this.SEG;
      idx[o++] = a; idx[o++] = a + this.SEG; idx[o++] = b; idx[o++] = b; idx[o++] = a + this.SEG; idx[o++] = b + this.SEG;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nor, 3).setUsage(THREE.DynamicDrawUsage));
    g.setIndex(new THREE.BufferAttribute(idx, 1));
    g.setDrawRange(0, 0);
    this.mesh = new THREE.Mesh(g, mat);
    this.mesh.castShadow = true; this.mesh.receiveShadow = true; this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 2;
    this.mesh.userData.sauceLine = this;
    // the falling stream from the tool's tip
    const sg = new THREE.CylinderGeometry(r * 0.55, r * 0.7, 1, 8, 1, true);
    sg.translate(0, -0.5, 0);
    this.stream = new THREE.Mesh(sg, mat);
    this.stream.visible = false;
    this.stream.frustumCulled = false;
    this.busy = false;
    this.drips = [];
  }
  push(x, h, z) {
    const last = this.pts[this.pts.length - 1];
    if (last && Math.hypot(x - last.x, z - last.z) < 0.0011) return;
    if (this.pts.length >= this.MAX - 2) return;
    // the thread lands on top of whatever is there, and stays on top of it from then on
    // a thread of sauce has some body: off the edge of a coil it bridges and drapes down gradually, it never drops
    // straight down
    let y = h + this.r * 0.45;
    if (last) y = Math.max(y, last.y - 0.7 * Math.hypot(x - last.x, z - last.z));
    const p = { x, z, y, floor: h + this.r * 0.45 };    // floor: the surface under it when it was laid
    this.pts.push(p);
    // what is laid becomes part of the surface, but only a few millimetres behind the stream so the thread does not
    // climb onto itself
    const back = this.pts.length - 9;
    if (back >= 0) { const q = this.pts[back]; this.surf.splat(q.x, q.z, this.r * 1.2, q.y + this.r * 0.45); this.splatted = back + 1; }
    this.relax(2, Math.max(1, this.pts.length - 30));
    this.rebuild(Math.max(0, this.pts.length - 32));
  }
  flush() {
    for (let i = this.splatted || 0; i < this.pts.length; i++) { const q = this.pts[i]; this.surf.splat(q.x, q.z, this.r * 1.2, q.y + this.r * 0.45); }
    this.splatted = this.pts.length;
  }
  streamFrom(tip, h, on) {
    this.stream.visible = on && tip.y > h;
    if (!this.stream.visible) return;
    this.stream.position.copy(tip);
    this.stream.scale.set(1, Math.max(0.001, tip.y - h), 1);
  }
  // after the pour: where the swirl is steep, the sauce keeps running down a little (drips)
  // a laid thread is not stiff: where it bridged a gap it sags down onto whatever is under it
  relax(passes, from = 0) {
    const P = this.pts, n = P.length;
    for (let it = 0; it < passes; it++) for (let i = Math.max(1, from); i < n - 1; i++) {
      const want = 0.5 * (P[i - 1].y + P[i + 1].y) - 0.0004;
      P[i].y = Math.max(P[i].floor, Math.min(P[i].y, want));
    }
  }
  finish() { this.settle = 1; this.busy = true; }
  makeDrips(runny) {
    const n = new THREE.Vector3();
    const R = PC.rng(this.pts.length * 7 + 3);
    for (let i = 3; i < this.pts.length - 3; i += 5) {
      const p = this.pts[i];
      this.surf.normal(p.x, p.z, n);
      const slope = Math.hypot(n.x, n.z) / n.y;
      if (slope < 0.7 || slope > 2.4 || R() > 0.5 * runny) continue;
      const len = (0.006 + R() * 0.012) * runny * Math.min(1.6, slope);
      this.drips.push(new Drip(this, p, len));
    }
    this.busy = this.drips.length > 0;
  }
  step(dt) {
    if (!this.busy) return;
    let any = false;
    if (this.settle > 0) {
      // sag over half a second, then become part of the surface for whatever comes next
      this.relax(4);
      this.rebuild(0);
      this.settle -= dt / 0.5;
      any = true;
      if (this.settle <= 0 && this.onSettled) { const f = this.onSettled; this.onSettled = null; f(); }
    }
    for (const d of this.drips) any = d.step(dt) || any;
    this.busy = any;
  }
  reSplat() { for (const p of this.pts) this.surf.splat(p.x, p.z, this.r * 1.2, p.y + this.r * 0.45); }
  rebuild(from) {
    const P = this.pts, n = P.length, SEG = this.SEG, r = this.r;
    if (n < 2) return;
    const T = new THREE.Vector3(), U = new THREE.Vector3(), S = new THREE.Vector3(), N = new THREE.Vector3();
    for (let i = Math.max(0, from - 1); i < n; i++) {
      const a = P[Math.max(0, i - 1)], b = P[Math.min(n - 1, i + 1)];
      T.set(b.x - a.x, b.y - a.y, b.z - a.z).normalize();
      this.surf.normal(P[i].x, P[i].z, N);
      S.crossVectors(T, N).normalize();
      U.crossVectors(S, T).normalize();
      // flattened thread: wide on the surface, low; thin at its two ends
      const end = Math.min(i, n - 1 - i);
      const taper = Math.min(1, 0.35 + end * 0.22);
      const rw = r * 1.25 * taper, rh = r * 0.6 * taper;
      for (let k = 0; k < SEG; k++) {
        const ph = k / SEG * Math.PI * 2, c = Math.cos(ph), s = Math.sin(ph);
        const o = (i * SEG + k) * 3;
        this.pos[o] = P[i].x + S.x * c * rw + U.x * s * rh;
        this.pos[o + 1] = P[i].y + S.y * c * rw + U.y * s * rh;
        this.pos[o + 2] = P[i].z + S.z * c * rw + U.z * s * rh;
        const nx = S.x * c / rw + U.x * s / rh, ny = S.y * c / rw + U.y * s / rh, nz = S.z * c / rw + U.z * s / rh;
        const l = Math.hypot(nx, ny, nz) || 1;
        this.nor[o] = nx / l; this.nor[o + 1] = ny / l; this.nor[o + 2] = nz / l;
      }
    }
    const g = this.mesh.geometry;
    g.setDrawRange(0, (n - 1) * SEG * 6);
    g.attributes.position.needsUpdate = true;
    g.attributes.normal.needsUpdate = true;
  }
}

// a drip: a short tapered run of sauce growing down the slope from a point on the line
class Drip {
  constructor(line, p, len) {
    this.line = line; this.len = len; this.t = 0;
    const pts = [new THREE.Vector3(p.x, p.y, p.z)];
    const n = new THREE.Vector3();
    let x = p.x, z = p.z;
    let y = p.y;
    for (let s = 0; s < len; s += 0.0012) {
      line.surf.normal(x, z, n);
      const g = Math.hypot(n.x, n.z) || 1;
      const nx = x + n.x / g * 0.0012, nz = z + n.z / g * 0.0012;
      const ny = line.surf.height(nx, nz) + line.r * 0.35;
      if (y - ny > 0.0028) break;          // the edge of a coil: the run stops there, as a bead
      x = nx; z = nz; y = ny;
      pts.push(new THREE.Vector3(x, y, z));
    }
    if (pts.length < 2) pts.push(pts[0].clone().add(new THREE.Vector3(0, -0.0003, 0)));
    this.curve = new THREE.CatmullRomCurve3(pts);
    this.mesh = new THREE.Mesh(new THREE.BufferGeometry(), line.mesh.material);
    this.mesh.castShadow = true;
    line.mesh.add(this.mesh);
  }
  step(dt) {
    if (this.t >= 1) return false;
    this.t = Math.min(1, this.t + dt / 0.9);
    const k = easeOut(this.t);
    const L = Math.max(2, Math.round(12 * k) + 2);
    const pts = this.curve.getPoints(L).slice(0, Math.max(2, Math.round(L * k) + 1));
    const r = this.line.r;
    const c = new THREE.CatmullRomCurve3(pts.length > 1 ? pts : [pts[0], pts[0].clone().add(new THREE.Vector3(0, -1e-4, 0))]);
    const g = new THREE.TubeGeometry(c, Math.max(2, pts.length * 2), r * 0.8, 8, false);
    // taper to a bead at the end of the run
    const p = g.attributes.position, segs = Math.max(2, pts.length * 2);
    for (let i = 0; i < p.count; i++) {
      const ring = Math.floor(i / 9), u = ring / segs;
      const ctr = c.getPoint(Math.min(1, u));
      const s = (0.55 + 0.6 * Math.sin(u * Math.PI * 0.9)) * (u > 0.9 ? 1.25 : 1);
      p.setXYZ(i, ctr.x + (p.getX(i) - ctr.x) * s, ctr.y + (p.getY(i) - ctr.y) * s * 0.7, ctr.z + (p.getZ(i) - ctr.z) * s);
    }
    g.computeVertexNormals();
    this.mesh.geometry.dispose();
    this.mesh.geometry = g;
    return this.t < 1;
  }
}

// ------------------------------------------------------------------ materials for the room
const idle = () => new Promise(r => (window.requestIdleCallback ? requestIdleCallback(() => r(), { timeout: 60 }) : setTimeout(r, 0)));

async function makeMaterials(roomScene) {
  const M = {};
  // quartz: white-grey with soft grey veins, drawn once
  const q = document.createElement('canvas');
  q.width = 1024; q.height = 512;
  const x = q.getContext('2d');
  x.fillStyle = '#e6e3de'; x.fillRect(0, 0, 1024, 512);
  const img = x.getImageData(0, 0, 1024, 512);
  for (let j = 0; j < 512; j++) {
    if (j % 48 === 0) await idle();
    for (let i = 0; i < 1024; i++) {
    const n = PC.fbm(i / 180, j / 90, 0.5, 4), v = Math.abs(PC.fbm(i / 260 + n * 1.4, j / 140, 2.1, 4));
    const vein = Math.max(0, 1 - v * 14) * 0.4 + Math.max(0, 1 - v * 40) * 0.3;
    const o = (j * 1024 + i) * 4, g = 228 + n * 7 - vein * 26, sp = (PC.noise3(i * 0.9, j * 0.9, 7) > 0.84 ? -7 : 0);
    img.data[o] = g + 2 + sp; img.data[o + 1] = g + sp; img.data[o + 2] = g - 4 + sp; img.data[o + 3] = 255;
    }
  }
  x.putImageData(img, 0, 0);
  const qt = new THREE.CanvasTexture(q);
  qt.colorSpace = THREE.SRGBColorSpace; qt.wrapS = qt.wrapT = THREE.RepeatWrapping; qt.anisotropy = 8;
  M.quartz = new THREE.MeshPhysicalMaterial({ map: qt, roughness: 0.32, clearcoat: 0.35, clearcoatRoughness: 0.25 });
  M.quartzSide = new THREE.MeshPhysicalMaterial({ map: qt, roughness: 0.4, color: '#efece6' });
  M.ceramic = new THREE.MeshPhysicalMaterial({ color: '#f5f3ef', roughness: 0.24, clearcoat: 0.6, clearcoatRoughness: 0.15, emissive: '#fff3d6', emissiveIntensity: 0 });
  M.ceramic.userData.glowable = true;
  M.pan = new THREE.MeshPhysicalMaterial({ color: '#efece6', roughness: 0.42, clearcoat: 0.3, emissive: '#fff3d6', emissiveIntensity: 0 });
  M.wood = new THREE.MeshStandardMaterial({ color: '#c99a62', roughness: 0.62 });
  M.woodDark = new THREE.MeshStandardMaterial({ color: '#a8743f', roughness: 0.55 });
  M.oak = new THREE.MeshStandardMaterial({ color: '#a88a68', roughness: 0.66 });
  M.steel = new THREE.MeshStandardMaterial({ color: '#d9d9d6', roughness: 0.22, metalness: 1 });
  M.blackPlastic = new THREE.MeshStandardMaterial({ color: '#141414', roughness: 0.4 });
  M.clear = new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 0.08, transparent: true, opacity: 0.35, depthWrite: false });
  // clear glass has no body colour: all it does is reflect a few percent of the room. It used to be lit like a pale surface at
  // 7% alpha (HDR bright, clamped on the canvas but not in the post pass's float buffer), which veiled every bowl behind it.
  // Black plus additive blending leaves only the reflection and neither dims nor fogs what is behind.
  M.glass = new THREE.MeshPhysicalMaterial({ color: '#000000', roughness: 0.06, metalness: 0, transparent: true, blending: THREE.AdditiveBlending, opacity: 1, specularIntensity: 1, depthWrite: false, side: THREE.FrontSide });
  M.glassEdge = new THREE.MeshStandardMaterial({ color: '#9fcfc6', roughness: 0.15, transparent: true, opacity: 0.26, depthWrite: false });
  M.travertine = new THREE.MeshStandardMaterial({ color: '#d9cbb3', roughness: 0.8 });
  M.white = new THREE.MeshStandardMaterial({ color: '#f7f6f2', roughness: 0.5 });
  M.induction = new THREE.MeshPhysicalMaterial({ color: '#f1efe9', roughness: 0.3, clearcoat: 0.6 });
  M.globe = new THREE.MeshStandardMaterial({ color: '#fff4dc', emissive: '#ffe2b0', emissiveIntensity: 1.6, roughness: 0.4 });
  M.brass = new THREE.MeshStandardMaterial({ color: '#b8904c', roughness: 0.3, metalness: 1 });
  M.screen = new THREE.MeshStandardMaterial({ color: '#0d0e10', roughness: 0.2, emissive: '#1d2430', emissiveIntensity: 0.6 });
  // limewash from the room model
  let lime = null;
  roomScene && roomScene.traverse(o => { if (o.isMesh && /Limewash/.test(o.material.name)) lime = o.material; });
  M.limewash = lime ? lime.clone() : new THREE.MeshStandardMaterial({ color: '#d8cfc0', roughness: 0.95 });
  if (M.limewash.map) { M.limewash.map = M.limewash.map.clone(); M.limewash.map.wrapS = M.limewash.map.wrapT = THREE.RepeatWrapping; M.limewash.map.repeat.set(3, 1.2); M.limewash.map.needsUpdate = true; }
  return M;
}

// ------------------------------------------------------------------ counter, glass, back wall, register
function buildRoom(scene, M, LEN, W0, afterPans, X_REG, roomScene) {
  const box = (w, h, d, mat, x, y, z, shadow = true) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z); m.receiveShadow = true; m.castShadow = shadow;
    scene.add(m); return m;
  };
  const X = -0.9, L = LEN + 1.2, CX = X + L / 2;
  // counter: quartz slab with a soft front nose, a stone apron below
  const top = box(L, 0.03, 0.78, M.quartz, CX, -0.015, -0.03);
  top.material.map.repeat.set(L / 1.6, 0.6);
  box(L, 0.9, 0.04, M.quartzSide, CX, -0.48, 0.34);
  // glass guard: low front pane on the customer edge, a high shelf pane over the front row
  box(L, 0.16, 0.008, M.glass, CX, 0.08, Z_GLASS, false);
  box(L, 0.004, 0.009, M.glassEdge, CX, 0.161, Z_GLASS, false);
  box(L, 0.008, 0.36, M.glass, CX, 0.52, Z_GLASS - 0.25, false);

  // staff side: back counter on light oak cabinets, a shelf of white Greek vases, brass globe sconces
  box(L, 0.86, 0.6, M.oak, CX, -0.43, -0.98);
  box(L, 0.03, 0.62, M.quartz, CX, 0.0, -0.98);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(L, 1.2), new THREE.MeshStandardMaterial({ color: '#8c8478', roughness: 0.9 }));
  floor.rotation.x = -Math.PI / 2; floor.position.set(CX, -0.9, -0.55); scene.add(floor);
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(L, 3.2), M.limewash);
  wall.position.set(CX, 0.6, -1.29); wall.receiveShadow = true; scene.add(wall);
  box(L, 0.025, 0.2, M.white, CX, 0.52, -1.18);
  const R = PC.rng(5);
  for (let x = X + 0.2; x < X + L; x += 0.32 + R() * 0.2) {
    const h = 0.12 + R() * 0.14, w = 0.04 + R() * 0.035;
    const prof = [];
    for (let i = 0; i <= 12; i++) {
      const t = i / 12;
      prof.push(new THREE.Vector2(w * (0.55 + 0.6 * Math.sin(Math.min(1, t * 1.15) * Math.PI) * (t < 0.85 ? 1 : 0.6)) + (t > 0.9 ? w * 0.15 : 0), t * h));
    }
    const vase = new THREE.Mesh(new THREE.LatheGeometry(prof, 28), M.ceramic);
    vase.position.set(x, 0.533, -1.17 + (R() - 0.5) * 0.05); vase.castShadow = true; scene.add(vase);
  }
  for (let x = X + 0.6; x < X + L; x += 1.4) {
    const g = new THREE.Mesh(new THREE.SphereGeometry(0.045, 24, 16), M.globe);
    g.position.set(x, 0.86, -1.2); scene.add(g);
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.09, 8), M.brass);
    arm.rotation.x = Math.PI / 2; arm.position.set(x, 0.86, -1.245); scene.add(arm);
  }
  // the warm station: a white warming plate behind the glass
  const plate = box(afterPans - W0 + 0.36, 0.02, 0.3, M.induction, (W0 + afterPans) / 2, 0.01, -0.12);
  plate.castShadow = false;
  // the register: a pale stone counter block, a tablet showing the sun, and the scale your cup goes on
  const reg = box(0.62, 0.11, 0.42, M.travertine, X_REG - 0.12, 0.055, -0.16);
  reg.material = reg.material.clone(); reg.material.color.set('#e4dccd');
  const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.026, 0.08, 16), M.steel);
  stand.position.set(X_REG - 0.24, 0.15, -0.26); stand.castShadow = true; scene.add(stand);
  const tab = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.14, 0.01), M.blackPlastic);
  tab.position.set(X_REG - 0.24, 0.24, -0.26); tab.rotation.set(-0.32, 0.25, 0); tab.castShadow = true; scene.add(tab);
  {
    const c = document.createElement('canvas'); c.width = 400; c.height = 280;
    const x = c.getContext('2d');
    const g = x.createLinearGradient(0, 0, 0, 280); g.addColorStop(0, '#1b1a18'); g.addColorStop(1, '#0f0e0d');
    x.fillStyle = g; x.fillRect(0, 0, 400, 280);
    x.fillStyle = '#c99a4e'; x.textAlign = 'center';
    x.beginPath(); x.arc(200, 110, 34, 0, 7); x.fill();
    for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; x.beginPath(); x.moveTo(200 + Math.cos(a) * 40, 110 + Math.sin(a) * 40); x.lineTo(200 + Math.cos(a + 0.12) * 58, 110 + Math.sin(a + 0.12) * 58); x.lineTo(200 + Math.cos(a - 0.12) * 40, 110 + Math.sin(a - 0.12) * 40); x.fill(); }
    x.font = '400 34px "Italiana", Georgia, serif'; x.fillText('ILIOS', 200, 212);
    x.font = '400 14px "DM Mono", monospace'; x.fillStyle = '#8f877c'; x.fillText('PLACE CUP ON SCALE', 200, 246);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.184, 0.126), new THREE.MeshBasicMaterial({ map: t }));
    scr.position.set(0, 0, 0.0052); tab.add(scr);
  }
  const scale = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.018, 0.2), M.steel);
  scale.position.set(X_REG + 0.02, 0.119, -0.12); scale.castShadow = scale.receiveShadow = true; scene.add(scale);
  if (roomScene) {
    const sun = roomScene.getObjectByName('WallSun');
    const t1 = roomScene.getObjectByName('WallFROYO');
    const t0 = roomScene.getObjectByName('WallILIOS');
    const grp = new THREE.Group();
    for (const s of [sun, t0, t1]) if (s) { const c = s.clone(); grp.add(c); }
    // the room puts them at x 0.86, y ~1.08, z 0.3: bring them to the wall behind the register
    grp.position.set(X_REG - 0.1 - 0.86, -0.36, -1.285 - 0.3 + 0.012);
    scene.add(grp);
  }
}

// ------------------------------------------------------------------ one station: bowl, heap, label
function variantsFor(def, glb, modelled) {
  // modelled pieces (source/toppings); sprinkles are modelled white and tinted per instance from the def's palette
  const m = modelled[def.model || def.key];
  if (m) return m.map(v => ({ ...v, tint: def.tint || null }));
  if (def.glb && glb[def.glb]) return glb[def.glb].map(v => ({ ...v, flat: ['rainbow', 'biscoff', 'nonpareil'].includes(def.glb) }));
  if (def.make) return [1, 2, 3, 4].map(s => def.make(s * 17 + def.key.length));
  return [];
}

function buildStation(it, M, pieceMat, jellyMat) {
  const def = it.def, G = it.group, R = PC.rng(def.key.length * 977 + Math.round(it.x * 100));
  if (def.bowl === 'skillet') {
    // white ceramic non-stick skillet with a blond wood handle
    const prof = [new THREE.Vector2(0, 0), new THREE.Vector2(0.085, 0), new THREE.Vector2(0.1, 0.045), new THREE.Vector2(0.104, 0.047), new THREE.Vector2(0.097, 0.047), new THREE.Vector2(0.081, 0.006), new THREE.Vector2(0, 0.006)];
    const pan = new THREE.Mesh(new THREE.LatheGeometry(prof, 64), M.pan.clone());
    pan.position.y = 0.02; pan.castShadow = pan.receiveShadow = true; pan.userData.glow = 1;
    G.add(pan);
    const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.016, 0.17, 16), M.wood);
    handle.rotation.x = Math.PI / 2 - 0.12; handle.position.set(0, 0.07, -0.18); handle.castShadow = true;
    G.add(handle);
    G.add(contents(def, 0.09, 0.033, M, pieceMat, jellyMat, it));
    return;
  }
  if (def.bowl === 'jar') {
    // the honey drizzler: a glass jar of honey with a steel top, on the customer side of the glass
    const jar = new THREE.Mesh(new THREE.CylinderGeometry(0.038, 0.04, 0.12, 32), M.clear.clone());
    jar.position.y = 0.06; jar.userData.glow = 1; G.add(jar);
    const honey = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.037, 0.085, 32), new THREE.MeshPhysicalMaterial({ color: '#c47c08', roughness: 0.1, transparent: true, opacity: 0.85, emissive: '#4a2600' }));
    honey.position.y = -0.015; jar.add(honey);
    it.toolAnchor = jar;
    return;
  }
  if (def.bowl === 'jug') {
    // olive oil in a painted ceramic jug, and the flaky salt in a little dish
    const dish = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.032, 0.022, 32), M.ceramic.clone());
    dish.position.set(0.09, 0.011, 0.03); dish.userData.glow = 1; G.add(dish);
    const salt = new THREE.Mesh(new THREE.CylinderGeometry(0.034, 0.034, 0.004, 32), new THREE.MeshStandardMaterial({ color: '#fbfaf6', roughness: 0.4 }));
    salt.position.set(0.09, 0.02, 0.03); G.add(salt);
    return;
  }
  if (def.bowl === 'tray') { buildSauceTray(it, G, M); return; }
  const bowl = new THREE.Mesh(bowlGeometry(def.bowl, it.heapData && it.heapData.seed), M.ceramic.clone());
  bowl.castShadow = bowl.receiveShadow = true;
  bowl.userData.glow = 1;
  bowl.rotation.y = it.heapData && it.heapData.seed !== undefined ? 0 : R() * Math.PI * 2;      // (a heap was settled against the bowl as modelled: not turned)
  G.add(bowl);
  const hob = def.bowl === 'hobnail';
  G.add(contents(def, hob ? 0.085 : 0.092, hob ? 0.088 : 0.074, M, pieceMat, jellyMat, it));
}

// the raspberry sauce: a rounded white dish on a wooden board, filled nearly to the lip with glossy sauce
function roundedRect(w, d, r, path = new THREE.Shape()) {
  const x = -w / 2, y = -d / 2;
  path.moveTo(x + r, y); path.lineTo(x + w - r, y); path.quadraticCurveTo(x + w, y, x + w, y + r);
  path.lineTo(x + w, y + d - r); path.quadraticCurveTo(x + w, y + d, x + w - r, y + d);
  path.lineTo(x + r, y + d); path.quadraticCurveTo(x, y + d, x, y + d - r);
  path.lineTo(x, y + r); path.quadraticCurveTo(x, y, x + r, y);
  return path;
}
let sauceMapTex = null;
function sauceMap(color) {
  if (sauceMapTex) return sauceMapTex;
  // pulp and seeds: marbled streaks of lighter and darker sauce, and the little pale seeds
  const c = document.createElement('canvas'); c.width = 512; c.height = 352;
  const x = c.getContext('2d');
  x.fillStyle = color; x.fillRect(0, 0, 512, 352);
  const rnd = PC.rng(4711);
  for (let i = 0; i < 90; i++) {
    const cx = rnd() * 512, cy = rnd() * 352, rx = 30 + rnd() * 90, ry = 4 + rnd() * 14, a = rnd() * Math.PI;
    x.fillStyle = rnd() < 0.5 ? 'rgba(255,90,110,0.10)' : 'rgba(40,0,10,0.16)';
    x.beginPath(); x.ellipse(cx, cy, rx, ry, a, 0, 7); x.fill();
  }
  for (let i = 0; i < 520; i++) {
    x.fillStyle = `rgba(${215 + rnd() * 30 | 0},${150 + rnd() * 60 | 0},${120 + rnd() * 50 | 0},${0.35 + rnd() * 0.4})`;
    x.beginPath(); x.ellipse(rnd() * 512, rnd() * 352, 1.2 + rnd() * 0.8, 0.8 + rnd() * 0.6, rnd() * 3, 0, 7); x.fill();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return (sauceMapTex = t);
}
function buildSauceTray(it, G, M) {
  const s = SAUCE[it.def.sauce];
  const board = new THREE.Mesh(new THREE.BoxGeometry(0.222, 0.012, 0.162), M.woodDark);
  board.position.y = 0.006; board.castShadow = board.receiveShadow = true;
  const outer = roundedRect(0.2, 0.14, 0.02);
  outer.holes.push(roundedRect(0.18, 0.12, 0.013, new THREE.Path()));
  const bev = { bevelEnabled: true, bevelSize: 0.0016, bevelThickness: 0.0016, bevelSegments: 3, curveSegments: 12 };
  const wall = new THREE.ExtrudeGeometry(outer, { ...bev, depth: 0.03 }).rotateX(-Math.PI / 2);
  const bottom = new THREE.ExtrudeGeometry(roundedRect(0.2, 0.14, 0.02), { ...bev, depth: 0.004 }).rotateX(-Math.PI / 2);
  const dish = new THREE.Mesh(wall, M.ceramic.clone());
  const dishBottom = new THREE.Mesh(bottom, dish.material);
  dish.position.y = dishBottom.position.y = 0.012;
  dish.castShadow = dish.receiveShadow = dishBottom.castShadow = dishBottom.receiveShadow = true;
  dish.userData.glow = 1; dishBottom.userData.glow = 1;
  // the sauce: its edge rolls up the dish's wall (a meniscus), its top carries the pulp
  const pool = roundedRect(0.178, 0.118, 0.012);
  const poolGeo = new THREE.ExtrudeGeometry(pool, { depth: 0.0006, bevelEnabled: true, bevelSize: 0.0025, bevelThickness: 0.0022, bevelSegments: 4, curveSegments: 12 }).rotateX(-Math.PI / 2);
  const uv = poolGeo.attributes.uv, pos = poolGeo.attributes.position;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (pos.getX(i) + 0.09) / 0.18, (pos.getZ(i) + 0.06) / 0.12);
  const sauce = new THREE.Mesh(poolGeo, new THREE.MeshPhysicalMaterial({ color: '#ffffff', map: sauceMap(s.color), roughness: 0.1, clearcoat: 1, clearcoatRoughness: 0.04, emissive: '#2a0208' }));
  sauce.position.y = 0.0357; sauce.receiveShadow = true;
  G.add(board, dish, dishBottom, sauce);
  it.heapTop = 0.045;
}

// the dome under a heap of sprinkles: a dark floor flecked with the palette, so the gaps between the pieces are not one flat colour
const confettiTex = {};
function confettiMap(palette, tone) {
  const k = palette.length + ':' + tone;
  if (confettiTex[k]) return confettiTex[k];
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d');
  x.fillStyle = `rgb(${tone * 255 * 0.5 | 0},${tone * 255 * 0.42 | 0},${tone * 255 * 0.42 | 0})`; x.fillRect(0, 0, 256, 256);
  const rnd = PC.rng(99);
  for (let i = 0; i < 900; i++) {
    const col = palette[(rnd() * palette.length) | 0];
    x.fillStyle = `rgb(${col.r * 255 * 0.55 | 0},${col.g * 255 * 0.55 | 0},${col.b * 255 * 0.55 | 0})`;
    x.save(); x.translate(rnd() * 256, rnd() * 256); x.rotate(rnd() * 3.14); x.fillRect(-4, -1, 8, 2.2); x.restore();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 1.5);
  return (confettiTex[k] = t);
}

// what is in a bowl or a pan
function contents(def, R, H, M, pieceMat, jellyMat, it) {
  const grp = new THREE.Group();
  if (def.kind === 'sauce' || def.kind === 'oil' || def.kind === 'dollop' || def.kind === 'rolls') {
    const s = SAUCE[def.sauce] || { color: def.heap, rough: 0.5, coat: 0.2 };
    const isTray = def.bowl === 'tray';
    const geo = isTray ? new THREE.BoxGeometry(0.19, 0.004, 0.13) : new THREE.CircleGeometry(R * 0.95, 48).rotateX(-Math.PI / 2);
    let mat;
    if (def.kind === 'dollop') {
      // pistachio kataifi sits in the pan as a thick, textured filling
      const g = new THREE.CircleGeometry(R * 0.94, 64, 0, Math.PI * 2);
      g.rotateX(-Math.PI / 2);
      const seg = new THREE.PlaneGeometry(R * 1.9, R * 1.9, 70, 70).rotateX(-Math.PI / 2);
      const p = seg.attributes.position, col = new Float32Array(p.count * 4);
      const green = new THREE.Color('#8f9248'), dark = new THREE.Color('#6c6831'), gold = new THREE.Color('#c99a4e'), tmp = new THREE.Color();
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i), z = p.getZ(i), r = Math.hypot(x, z);
        const n = PC.fbm(x * 90, z * 90, 1.3, 4), strand = Math.abs(PC.noise3(x * 420, z * 70, 2));
        const y = r < R * 0.93 ? 0.004 * n + 0.003 * Math.max(0, 0.12 - strand) * 8 : -0.01;
        p.setY(i, y);
        tmp.copy(green).lerp(dark, 0.5 + 0.7 * n);
        if (strand < 0.08) tmp.lerp(gold, 0.7);
        col[i * 4] = tmp.r; col[i * 4 + 1] = tmp.g; col[i * 4 + 2] = tmp.b; col[i * 4 + 3] = 0.6;
      }
      seg.setAttribute('color', new THREE.BufferAttribute(col, 4));
      seg.computeVertexNormals();
      const m = new THREE.Mesh(seg, pieceMat);
      m.position.y = H - 0.004;
      m.receiveShadow = true;
      grp.add(m);
      return grp;
    }
    mat = new THREE.MeshPhysicalMaterial({ color: s.color, roughness: s.rough + 0.05, clearcoat: s.coat, clearcoatRoughness: 0.1, emissive: s.emissive || '#000000' });
    const m = new THREE.Mesh(geo, mat);
    m.position.y = isTray ? 0.03 : H;
    m.receiveShadow = true;
    grp.add(m);
    if (def.kind === 'rolls') {
      // the little cinnamon rolls soaking in the icing
      const ring = [[0.064, 9, 0.3], [0.03, 4, 0.9]];          // rolls packed in two rings: [radius, count, start angle]
      let ri = 0;
      for (const [rad, cnt, a0] of ring) for (let k = 0; k < cnt; k++, ri++) {
        const v = it.variants.length ? it.variants[ri % it.variants.length] : PC.miniRoll(ri * 3 + 1);
        const r = new THREE.Mesh(v.geo, v.cls ? it.matFor(v) : pieceMat);
        const a = a0 + k / cnt * Math.PI * 2 + (Math.random() - 0.5) * 0.12, d = rad + (Math.random() - 0.5) * 0.006;
        r.position.set(Math.cos(a) * d, H - 0.001, Math.sin(a) * d);
        r.rotation.set((Math.random() - 0.5) * 0.3, Math.random() * 6, (Math.random() - 0.5) * 0.3);
        r.castShadow = true;
        grp.add(r);
      }
    }
    return grp;
  }
  // a heap of pieces: a mound filled in the topping's own colour, and the pieces themselves over it
  const vs = it.variants;
  if (!vs.length) return grp;
  if (it.heapData) {
    // settled by physics (bar-heap.js): the pieces rest on a dark, dome-shaped fill whose gaps stay in shadow
    const d = it.heapData;
    const baseMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(def.heap).multiplyScalar(def.baseTone || 0.42), roughness: 0.9 });   // (darker than the pieces: the gaps between them are in shadow)
    // the base is the pile's own body under the shell of pieces, so nothing seems to float: it meets the bowl's wall all the way
    // round (organic bowls have a wavy rim: the lathe is scaled with the same wave as the bowl) and drops down along the wall
    const hobBowl = def.bowl === 'hobnail', bR = hobBowl ? 0.095 : 0.102, bH = hobBowl ? 0.085 : 0.07, bB = hobBowl ? 0.055 : 0.06, bP = hobBowl ? 0.8 : 1.2;
    const wobble = !hobBowl && d.seed !== undefined;
    const wallIn = y => (wobble || hobBowl ? 1 : 0.94) * (bB + (bR - bB) * Math.sin(Math.min(1, Math.max(0, y / bH)) * Math.PI / 2) ** bP - 0.006) - 0.0012;
    // a height map over angle and radius: the low end of the pieces in each cell (so the base is right under them everywhere), holes
    // filled from their neighbours, cut where it meets the (wavy) wall, then down along the wall
    const nb = 18, ns = 48, bw = bR / nb, TAU = Math.PI * 2;
    const cellY = Array.from({ length: nb * ns }, () => []);
    for (const r of d.instances) {
      const b = Math.floor(Math.hypot(r[1], r[3]) / bw);
      if (b < nb) cellY[b * ns + (Math.floor((Math.atan2(r[3], r[1]) + Math.PI) / TAU * ns) % ns)].push(r[2]);
    }
    const off = d.dome ? 0.0012 : 0.004, cap = d.top - 0.006;
    let lev = cellY.map(a => { if (a.length < 3) return NaN; a.sort((x, y) => x - y); return Math.min(cap, a[Math.floor(a.length * 0.12)] - off); });
    for (let pass = 0; pass < 40 && lev.some(isNaN); pass++) {
      lev = lev.map((v, k) => {
        if (!isNaN(v)) return v;
        const b = Math.floor(k / ns), j = k % ns; let sum = 0, n = 0;
        for (const [db, dj] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
          const bb = b + db; if (bb < 0 || bb >= nb) continue;
          const u = lev[bb * ns + (j + dj + ns) % ns]; if (!isNaN(u)) { sum += u; n++; }
        }
        return n ? sum / n : NaN;
      });
    }
    lev = lev.map(v => isNaN(v) ? d.ye : v);
    const sm = lev.map((v, k) => {         // a light smoothing that never lifts the base into the pieces
      const b = Math.floor(k / ns), j = k % ns; let sum = 0, n = 0;
      for (let db = -1; db <= 1; db++) for (let dj = -1; dj <= 1; dj++) { const bb = b + db; if (bb < 0 || bb >= nb) continue; sum += lev[bb * ns + (j + dj + ns) % ns]; n++; }
      return Math.min(v, sum / n);
    });
    const wob = (th, y) => wobble ? 1 + 0.06 * Math.sin(th * 3 + d.seed) * (y / bH) ** 2 : 1;
    const rows = nb + 1 + 5;               // ring 0 is the centre, rings 1..nb the heap, then five steps down the wall
    const posA = new Float32Array(rows * ns * 3), uvA = new Float32Array(rows * ns * 2), idx = [];
    for (let j = 0; j < ns; j++) {
      const th = (j + 0.5) / ns * TAU - Math.PI, c = Math.cos(th), sn = Math.sin(th);
      let cut = false, ry = 0, rr = 0;
      for (let i = 0; i < rows; i++) {
        let r, y;
        if (i <= nb) {
          y = sm[Math.max(0, i - 1) * ns + j];
          r = i * bw;
          const w = wallIn(y) * wob(th, y);
          if (cut || r >= w) { r = w; cut = true; if (!ry) { ry = y; } y = ry; }
          rr = r;
        } else {
          y = ry || sm[(nb - 1) * ns + j];
          if (!ry) { ry = y; rr = wallIn(y) * wob(th, y); }
          y = ry - 0.004 - (i - nb - 1) * 0.0065;
          r = Math.min(rr, wallIn(y) * wob(th, y));
        }
        const o = (i * ns + j);
        posA[o * 3] = r * c; posA[o * 3 + 1] = y; posA[o * 3 + 2] = r * sn;
        uvA[o * 2] = (r * c / bR) * 0.5 + 0.5; uvA[o * 2 + 1] = (r * sn / bR) * 0.5 + 0.5;
      }
    }
    for (let i = 0; i < rows - 1; i++) for (let j = 0; j < ns; j++) {
      const a0 = i * ns + j, a1 = i * ns + (j + 1) % ns, b0 = (i + 1) * ns + j, b1 = (i + 1) * ns + (j + 1) % ns;
      idx.push(a0, a1, b0, a1, b1, b0);
    }
    const baseGeo = new THREE.BufferGeometry();
    baseGeo.setAttribute('position', new THREE.BufferAttribute(posA, 3));
    baseGeo.setAttribute('uv', new THREE.BufferAttribute(uvA, 2));
    baseGeo.setIndex(idx);
    baseGeo.computeVertexNormals();
    baseMat.side = THREE.DoubleSide;
    const base = new THREE.Mesh(baseGeo, baseMat);
    if (d.dome && def.tint) { baseMat.color.set('#ffffff'); baseMat.map = confettiMap(def.tint, def.baseTone || 0.42); }
    base.receiveShadow = true;
    grp.add(base, buildHeap(d, vs, it.matFor));
    it.heapTop = d.top;
    return grp;
  }
  const heapCol = new THREE.Color(def.heap);
  const mound = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 14, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: heapCol, roughness: 0.8 }));
  const MH = H * 0.42;
  mound.scale.set(R * 0.9, MH, R * 0.9);
  mound.position.y = H * 0.62;
  grp.add(mound);
  const rr = vs.reduce((s, v) => s + v.r, 0) / vs.length;
  const area = Math.PI * (R * 0.9) ** 2 * 1.25;
  const count = Math.min(def.fine ? 900 : 260, Math.round(area / (Math.PI * rr * rr * (def.fine ? 0.9 : 1.3))));
  const per = Math.ceil(count / vs.length);
  const rnd = PC.rng(def.key.length * 131 + 7);
  const dummy = new THREE.Object3D();
  const jelly = vs[0].jelly;
  vs.forEach((v, vi) => {
    const im = new THREE.InstancedMesh(v.geo, v.cls ? it.matFor(v) : jelly ? jellyMat : pieceMat, per);
    im.castShadow = !def.fine; im.receiveShadow = true;
    for (let i = 0; i < per; i++) {
      const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()) * R * 0.86;
      const y = H * 0.62 + MH * Math.sqrt(Math.max(0, 1 - (d / (R * 0.9)) ** 2)) + v.r * (0.1 + 0.3 * rnd());
      dummy.position.set(Math.cos(a) * d, y, Math.sin(a) * d);
      dummy.rotation.set(rnd() * 6.3, rnd() * 6.3, rnd() * 6.3);
      if (v.flat) dummy.rotation.set((rnd() - 0.5) * 0.8, rnd() * 6.3, (rnd() - 0.5) * 0.8);
      dummy.updateMatrix();
      im.setMatrixAt(i, dummy.matrix);
      if (v.tint) im.setColorAt(i, v.tint[(rnd() * v.tint.length) | 0]);
    }
    grp.add(im);
  });
  if (def.jimmies) {
    // rainbow sprinkles are nonpareils and jimmies together
    const js = it.rods || [1, 2, 3].map(s => PC.jimmy(s, def.jimmies));
    js.forEach(v => {
      const n = 160, im = new THREE.InstancedMesh(v.geo, v.cls ? it.matFor(v) : pieceMat, n);
      for (let i = 0; i < n; i++) {
        const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()) * R * 0.86;
        dummy.position.set(Math.cos(a) * d, H * 0.62 + MH * Math.sqrt(Math.max(0, 1 - (d / (R * 0.9)) ** 2)) + 0.0008, Math.sin(a) * d);
        dummy.rotation.set((rnd() - 0.5) * 0.6, rnd() * 6.3, (rnd() - 0.5) * 0.6);
        dummy.updateMatrix();
        im.setMatrixAt(i, dummy.matrix);
        if (v.tint) im.setColorAt(i, v.tint[(rnd() * v.tint.length) | 0]);
      }
      grp.add(im);
    });
  }
  it.heapTop = H * 0.62 + MH;
  return grp;
}

// ------------------------------------------------------------------ labels: white cards in travertine blocks (fruit),
// little chalkboard flags (candy), brown lettering on the glass (warm station)
function buildLabel(it, M) {
  const def = it.def;
  if (def.bowl === 'skillet' || def.key === 'honey') {
    const c = document.createElement('canvas');
    c.width = 512; c.height = 96;
    const x = c.getContext('2d');
    x.fillStyle = '#5b3a24';
    x.font = '700 64px "Manrope", ui-sans-serif, sans-serif';
    x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(def.sign || def.label.toUpperCase(), 256, 52);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(0.15, 0.028), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false }));
    m.position.set(it.x, 0.11, Z_GLASS + 0.006);
    m.userData.y = 0.11;
    return m;
  }
  if (def.key === 'oil') return null;
  const grp = new THREE.Group();
  const chalk = def.chalk;
  const c = document.createElement('canvas');
  c.width = 512; c.height = chalk ? 200 : 300;
  const x = c.getContext('2d');
  if (chalk) {
    x.fillStyle = '#1e1e1c'; x.fillRect(0, 0, 512, 200);
    x.strokeStyle = '#6b5135'; x.lineWidth = 14; x.strokeRect(7, 7, 498, 186);
    x.fillStyle = '#f2efe7';
    fitText(x, def.label, 256, 104, 460, 64, '400 {s}px "Italiana", Georgia, serif');
  } else {
    x.fillStyle = '#fbfaf7'; x.fillRect(0, 0, 512, 300);
    x.fillStyle = '#3d362e';
    fitText(x, def.label.toUpperCase(), 256, def.note ? 120 : 150, 440, 52, '500 {s}px "DM Mono", ui-monospace, monospace', 4);
    if (def.note) { x.fillStyle = '#7a6f62'; fitText(x, def.note.toUpperCase(), 256, 196, 440, 28, '400 {s}px "DM Mono", ui-monospace, monospace', 2); }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  const w = chalk ? 0.072 : 0.07, h = chalk ? 0.028 : 0.041;
  const card = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshStandardMaterial({ map: t, roughness: 0.7 }));
  card.castShadow = true;
  const zOff = it.back ? 0.115 : 0.118;
  if (chalk) {
    // on a pick stuck into the heap
    const pick = new THREE.Mesh(new THREE.CylinderGeometry(0.0015, 0.0015, 0.09, 6), M.woodDark);
    pick.position.set(0, -0.045, 0);
    card.add(pick);
    card.position.set(it.x + 0.03, (it.heapTop || 0.07) + 0.05, it.z + 0.04);
    card.rotation.x = -0.12;
    grp.add(card);
    grp.userData.y = 0;
    return grp;
  }
  const block = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.022, 0.026), M.travertine);
  block.position.set(it.x, 0.011, it.z + zOff);
  block.castShadow = true;
  card.position.set(it.x, 0.022 + h / 2 - 0.004, it.z + zOff);
  card.rotation.x = -0.18;
  grp.add(block, card);
  grp.userData.y = 0;
  return grp;
}
function fitText(x, s, cx, cy, maxW, size, font, spacing = 0) {
  let sz = size;
  do { x.font = font.replace('{s}', sz); sz -= 2; } while (x.measureText(s).width + spacing * s.length > maxW && sz > 12);
  x.textAlign = 'center'; x.textBaseline = 'middle';
  if ('letterSpacing' in x) x.letterSpacing = spacing + 'px';
  x.fillText(s, cx, cy);
}

// ------------------------------------------------------------------ utensils
// each tool: root (in the scene), scoop (where a serving rides), rest pose, how deep it digs, an offset that puts its
// working end over the cup, and set(pos, q, dig, lift, tip) to pose it
function buildTool(type, it, M) {
  const root = new THREE.Group(), body = new THREE.Group(), scoop = new THREE.Group();
  root.add(body);
  let cap = 0.012, dig = 0.012, tipAxis = new THREE.Vector3(0, 0, 1), tipAngle = 1.9;
  const mesh = (g, m) => { const o = new THREE.Mesh(g, m); o.castShadow = true; return o; };
  // tools are built pointing along -z (working end) with the handle running back toward +z (to you) and up
  if (type === 'spoon' || type === 'ladle' || type === 'metal' || type === 'soup') {
    const mat = type === 'metal' ? M.steel : type === 'soup' ? M.ceramic : M.wood;
    const len = type === 'soup' ? 0.13 : type === 'ladle' ? 0.2 : 0.24, bw = type === 'soup' ? 0.022 : type === 'ladle' ? 0.024 : 0.019;
    const handle = mesh(new THREE.CylinderGeometry(type === 'soup' ? 0.006 : 0.0045, type === 'soup' ? 0.008 : 0.0055, len, 10), mat);
    handle.rotation.x = Math.PI / 2; handle.position.z = len / 2 + bw * 0.6;
    const bowl = mesh(new THREE.SphereGeometry(1, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), mat);
    bowl.scale.set(bw, bw * 0.55, bw * (type === 'soup' ? 1.5 : 1.3));
    body.add(handle, bowl);
    scoop.position.set(0, 0.002, 0);
    body.add(scoop);
    cap = bw * 0.75; dig = 0.022;
  } else if (type === 'tongs') {
    for (const s of [-1, 1]) {
      const arm = mesh(new THREE.BoxGeometry(0.004, 0.0025, 0.2), M.steel);
      arm.position.set(s * 0.008, 0, 0.1); arm.rotation.y = s * -0.03;
      const pad = mesh(new THREE.BoxGeometry(0.006, 0.012, 0.03), M.steel);
      pad.position.set(s * 0.011, -0.004, 0.012);
      body.add(arm, pad);
    }
    body.add(scoop);
    cap = 0.011; dig = 0.018; tipAngle = 0.9;
  } else if (type === 'scoop') {
    const sc = mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.06, 20, 1, true, 0, Math.PI), M.clear);
    sc.rotation.set(Math.PI / 2, 0, Math.PI / 2); sc.position.z = 0.0;
    const h = mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.09, 10), M.clear);
    h.rotation.x = Math.PI / 2; h.position.z = 0.07;
    body.add(sc, h, scoop);
    cap = 0.016; dig = 0.02;
  } else if (type === 'disher') {
    const cupM = mesh(new THREE.SphereGeometry(0.021, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), M.steel);
    const h = mesh(new THREE.CylinderGeometry(0.007, 0.007, 0.11, 12), M.blackPlastic);
    h.rotation.x = Math.PI / 2; h.position.z = 0.075;
    body.add(cupM, h, scoop);
    scoop.position.y = 0.004;
    cap = 0.012; dig = 0.02; tipAngle = 2.6;
  } else if (type === 'jar') {
    // the honey drizzler is lifted and tipped itself
    const top = mesh(new THREE.CylinderGeometry(0.022, 0.03, 0.03, 24), M.steel);
    top.position.y = 0.135;
    const spout = mesh(new THREE.CylinderGeometry(0.003, 0.005, 0.02, 10), M.steel);
    spout.position.y = 0.158;
    body.add(top, spout);
    scoop.position.y = 0.168;
    body.add(scoop);
    tipAxis = new THREE.Vector3(1, 0, 0); tipAngle = 2.1;
  } else if (type === 'jug') {
    const prof = [];
    for (let i = 0; i <= 14; i++) { const t = i / 14; prof.push(new THREE.Vector2(0.03 + 0.022 * Math.sin(Math.min(1, t * 1.1) * Math.PI) - (t > 0.8 ? 0.012 * (t - 0.8) * 5 : 0), t * 0.14)); }
    const c = document.createElement('canvas'); c.width = 256; c.height = 128;
    const x = c.getContext('2d'); x.fillStyle = '#f4f0e6'; x.fillRect(0, 0, 256, 128);
    x.strokeStyle = '#2f5d8a'; x.lineWidth = 5;
    for (let i = 0; i < 8; i++) { x.beginPath(); x.arc(i * 32 + 16, 64, 11, 0, Math.PI * 2); x.stroke(); }
    x.fillStyle = '#5f8a3c'; for (let i = 0; i < 16; i++) { x.beginPath(); x.ellipse(i * 16 + 8, 26, 3, 7, 0.6, 0, 7); x.fill(); x.beginPath(); x.ellipse(i * 16 + 8, 102, 3, 7, -0.6, 0, 7); x.fill(); }
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    const jug = mesh(new THREE.LatheGeometry(prof, 32), new THREE.MeshPhysicalMaterial({ map: tex, roughness: 0.3, clearcoat: 0.6 }));
    const spout = mesh(new THREE.ConeGeometry(0.01, 0.03, 12, 1, true), M.ceramic);
    spout.rotation.z = Math.PI / 2 + 0.4; spout.position.set(0.035, 0.135, 0);
    body.add(jug, spout);
    scoop.position.set(0.05, 0.142, 0);
    body.add(scoop);
    tipAxis = new THREE.Vector3(0, 0, 1); tipAngle = -1.4;
  }

  // rest pose
  const rest = { pos: new THREE.Vector3(), q: new THREE.Quaternion() };
  const def = it.def;
  if (type === 'jar' || type === 'jug') {
    rest.pos.set(it.x, 0, it.z);
  } else if (def.bowl === 'skillet') {
    rest.pos.set(it.x + 0.02, 0.06, it.z - 0.01);
    rest.q.setFromEuler(new THREE.Euler(-0.55, 0.3, 0));
  } else {
    const top = it.heapTop || 0.06;
    rest.pos.set(it.x + 0.012, top - 0.004, it.z + 0.01);
    rest.q.setFromEuler(new THREE.Euler(-0.5, (it.back ? -0.2 : 0.25), 0));
  }
  const pourTip = type === 'jar' || type === 'jug' ? 1 : 0.62;
  const qTip = new THREE.Quaternion(), qLevel = new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.2, 0, 0)), X = new THREE.Vector3(1, 0, 0), off = new THREE.Vector3();
  const tool = {
    root, scoop, rest, cap, dig: type === 'jar' || type === 'jug' ? 0 : dig, pourTip, restScoop: new THREE.Vector3(),
    // orient the tool, then put it where its working end lands on `target` (world)
    place(target, q, digTilt = 0, lift = 0, tip = 0) {
      root.quaternion.copy(q);
      // as it comes out of the bowl the tool levels off; the jar and the jug stay upright until they pour
      if (type !== 'jar' && type !== 'jug') root.quaternion.slerp(qLevel, lift);
      body.quaternion.setFromAxisAngle(X, -digTilt);
      if (tip) body.quaternion.multiply(qTip.setFromAxisAngle(tipAxis, tipAngle * tip));
      root.position.set(0, 0, 0);
      root.updateMatrixWorld(true);
      scoop.getWorldPosition(off);
      root.position.copy(target).sub(off);
      root.updateMatrixWorld(true);
    },
    tipWorld(out) { scoop.updateMatrixWorld(true); return scoop.getWorldPosition(out); },
  };
  // where the working end sits at rest
  root.quaternion.copy(rest.q); body.quaternion.identity(); root.position.copy(rest.pos); root.updateMatrixWorld(true);
  scoop.getWorldPosition(tool.restScoop);
  if (type === 'jar' || type === 'jug') {
    // these sit by the bowls and are the thing that moves; the pick target is the jar itself
    const shell = it.toolAnchor;
    if (shell) { shell.removeFromParent(); body.add(shell); }
    root.traverse(m => { if (m.isMesh) m.userData.item = it; });
  }
  tool.place(tool.restScoop, rest.q);
  return tool;
}

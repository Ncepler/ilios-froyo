// The froyo's look: its six flavours and the soft-serve material, shared by the hero pour, the topping bar and the lab.
//
// Soft serve is a foam of ice crystals, fat and air: matte and creamy, with a faint velvety sheen, soft shadows that
// glow a little warmer at the terminator (light scatters through it), tiny pores where air bubbles broke the
// surface, and narrow dark valleys between coils. The material is a MeshPhysicalMaterial patched with:
//   - the twist's two flavours (a soft, noisy boundary that follows the ridges), vanilla-bean specks
//   - ambient occlusion from the geometry (pour.js writes an occluder direction per vertex; the ridge grooves darken)
//   - wrapped diffuse lighting with a warm scattered fringe (cheap subsurface)
//   - a fine pore / grain normal

import * as THREE from 'three';
import { NOISE_GLSL, installWrap } from './shade.js';

// The shop's six flavours on three machines (docs/ILIOS-FIELD-NOTES.md): each machine pours its left flavour, a twist of
// the two, and its right flavour.
export const C_COFFEE = '#a88563', C_VANILLA = '#f3e8c9', C_RASP = '#d98598', C_TART = '#f7f5ef';
export const FLAVORS = [
  { name: 'Sweet Harbor Coffee', machine: 'coffee', handle: 0, a: C_COFFEE, b: C_COFFEE, twist: 0, speckA: 0, speckB: 0 },
  { name: 'Coffee + Vanilla Bean twist', machine: 'coffee', handle: 1, a: C_COFFEE, b: C_VANILLA, twist: 1, speckA: 0, speckB: 0.8 },
  { name: 'Organic Vanilla Bean', machine: 'coffee', handle: 2, a: C_VANILLA, b: C_VANILLA, twist: 0, speckA: 1, speckB: 1 },
  { name: 'Raspberry', machine: 'raspberry', handle: 0, a: C_RASP, b: C_RASP, twist: 0, speckA: 0, speckB: 0 },
  { name: 'Raspberry + Vanilla Bean twist', machine: 'raspberry', handle: 1, a: C_RASP, b: C_VANILLA, twist: 1, speckA: 0, speckB: 0.8 },
  { name: 'Organic Original Tart', machine: 'tart', handle: 0, a: C_TART, b: C_TART, twist: 0, speckA: 0, speckB: 0 },
  { name: 'Organic Vanilla Bean', machine: 'raspberry', handle: 2, a: C_VANILLA, b: C_VANILLA, twist: 0, speckA: 1, speckB: 1, chip: 2 },
  { name: 'Organic Original Tart', machine: 'tart', handle: 1, a: C_TART, b: C_TART, twist: 0, speckA: 0, speckB: 0, chip: 5 },
  { name: 'Organic Original Tart', machine: 'tart', handle: 2, a: C_TART, b: C_TART, twist: 0, speckA: 0, speckB: 0, chip: 5 },
];

export const U = {
  uColA: { value: new THREE.Color(FLAVORS[1].a) }, uColB: { value: new THREE.Color(FLAVORS[1].b) },
  uTwist: { value: 1 }, uSpeckA: { value: 0 }, uSpeckB: { value: 0.8 },
};
export function setFlavorUniforms(f) {
  U.uColA.value.set(f.a);
  U.uColB.value.set(f.b);
  U.uTwist.value = f.twist;
  U.uSpeckA.value = f.speckA;
  U.uSpeckB.value = f.speckB;
}

const HASH = 'fract(sin(dot(c, vec3(12.9898, 78.233, 37.719))) * 43758.5453)';

const COMMON_GLSL = `
  varying float vM;
  varying vec3 vLocal;
  varying float vAO;
` + NOISE_GLSL;

const FLAVOR_GLSL = `
  {
    // the boundary between the two halves of a twist: a soft edge, pushed about by slow noise so it is never a ruled line
    float wob = (vnoise(vLocal * 110.0) - 0.5) * 0.34 + (vnoise(vLocal * 420.0) - 0.5) * 0.12;
    float mm = uTwist * smoothstep(0.40, 0.60, vM + wob);
    vec3 fc = mix(uColA, uColB, mm);
    // a little streaking where the two flavours were folded together
    float streak = 1.0 - 4.0 * mm * (1.0 - mm) * (0.5 + 0.5 * vnoise(vLocal * vec3(180.0, 60.0, 180.0)));
    fc = mix(fc, mix(uColA, uColB, 0.5), (1.0 - streak) * 0.35 * uTwist);
    // tiny pores and grain make the colour very slightly uneven
    fc *= 0.965 + 0.07 * vnoise(vLocal * 700.0);
    vec3 c = floor(vLocal * 520.0);
    float h = ${HASH};
    float sp = mix(uSpeckA, uSpeckB, mm) * step(0.9965, h);
    fc = mix(fc, vec3(0.05, 0.036, 0.028), sp * 0.9);
    diffuseColor.rgb = fc;
    g_wrap = 0.45; g_tint = vec3(1.0, 0.86, 0.72);
  }`;

// aerated: a fine, even grain, plus the odd tiny pit where a bubble broke the surface (object-space noise, no seams)
const BUMP_GLSL = `
  {
    vec3 q = vLocal * 900.0;
    vec3 g = vec3(vnoise(q) - 0.5, vnoise(q + 17.0) - 0.5, vnoise(q + 41.0) - 0.5);
    vec3 q2 = vLocal * 2600.0;
    vec3 g2 = vec3(vnoise(q2 + 5.0) - 0.5, vnoise(q2 + 23.0) - 0.5, vnoise(q2 + 61.0) - 0.5);
    normal = normalize(normal + 0.075 * g + 0.045 * g2);
  }`;

function patch(mat) {
  mat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float m;\nattribute vec3 oc;\nattribute float rg;\nvarying float vM;\nvarying vec3 vLocal;\nvarying float vAO;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vM = m; vLocal = position;
        // geometric occlusion: coils beside and above this vertex, in the direction oc (its length is how much), and the
        // ridge grooves (rg = 1 on a crest, 0 in a groove)
        vAO = (1.0 - 0.8 * clamp(dot(normalize(normal), oc), 0.0, 1.0)) * (0.62 + 0.38 * rg);`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\n' + COMMON_GLSL +
        'uniform vec3 uColA; uniform vec3 uColB; uniform float uTwist; uniform float uSpeckA; uniform float uSpeckB;')
      .replace('#include <color_fragment>', '#include <color_fragment>' + FLAVOR_GLSL)
      .replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\n' + BUMP_GLSL)
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
        reflectedLight.indirectDiffuse *= vAO;
        reflectedLight.indirectSpecular *= vAO;
        reflectedLight.directDiffuse *= mix(1.0, vAO, 0.7);
        reflectedLight.directSpecular *= vAO;`);
  };
  mat.customProgramCacheKey = () => 'froyo2';
}

export function makeFroyoMaterial() {
  installWrap();
  const m = new THREE.MeshPhysicalMaterial({
    color: '#f4ecd6', roughness: 0.6, metalness: 0, side: THREE.DoubleSide,
    sheen: 0.7, sheenRoughness: 0.55, sheenColor: new THREE.Color('#fff0d0'),
    clearcoat: 0.06, clearcoatRoughness: 0.6,
  });
  m.defines = { WRAPLIGHT: '' };
  patch(m);
  return m;
}

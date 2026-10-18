// Shared shader pieces for the soft, translucent things on the page (the froyo, fruit, gummies).

import * as THREE from 'three';

// 3D value noise and a hash, for the materials' pores, grain and streaks
export const NOISE_GLSL = `
  float h31(vec3 c) { return fract(sin(dot(c, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
  float vnoise(vec3 p) {
    vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(h31(i), h31(i + vec3(1,0,0)), f.x), mix(h31(i + vec3(0,1,0)), h31(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(h31(i + vec3(0,0,1)), h31(i + vec3(1,0,1)), f.x), mix(h31(i + vec3(0,1,1)), h31(i + vec3(1,1,1)), f.x), f.y), f.z);
  }
`;

// Wrapped diffuse light with a tinted fringe: light that scatters inside a soft, translucent material reaches past the
// terminator and comes out coloured by the material. g_wrap (0 = ordinary Lambert) and g_tint are set per fragment,
// before the lights run. three's physical light function is a shader chunk: add a copy with the diffuse term changed,
// used only by materials that define WRAPLIGHT (once, before the first compile).
let wrapped = false;
export function installWrap() {
  if (wrapped) return;
  wrapped = true;
  const k = THREE.ShaderChunk.lights_physical_pars_fragment;
  const from = '\tvec3 irradiance = dotNL * directLight.color;';
  const diff = 'reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );';
  const def = '#define RE_Direct\t\t\t\tRE_Direct_Physical';
  const a = k.indexOf('void RE_Direct_Physical'), b = k.indexOf('void RE_IndirectDiffuse_Physical');
  const fn = k.slice(a, b);
  if (a < 0 || !fn.includes(from) || !fn.includes(diff) || !k.includes(def)) { console.warn('shade: three light chunk changed, no wrapped light'); return; }
  const wrapFn = fn.replace('void RE_Direct_Physical', 'void RE_Direct_Wrap')
    .replace(from, `\tvec3 irradiance = dotNL * directLight.color;
\tfloat wrapNL = saturate((dot(geometryNormal, directLight.direction) + g_wrap) / (1.0 + g_wrap));
\tvec3 irradianceD = mix(dotNL * directLight.color, wrapNL * wrapNL * directLight.color * mix(g_tint, vec3(1.0), smoothstep(0.0, 0.55, dotNL)), step(0.001, g_wrap));`)
    .replace(diff, 'reflectedLight.directDiffuse += irradianceD * BRDF_Lambert( material.diffuseColor );');
  THREE.ShaderChunk.lights_physical_pars_fragment = (k.slice(0, b) + '\n#ifdef WRAPLIGHT\nfloat g_wrap = 0.0;\nvec3 g_tint = vec3(1.0);\n' + wrapFn + '#endif\n' + k.slice(b))
    .replace(def, '#ifdef WRAPLIGHT\n#define RE_Direct\t\t\t\tRE_Direct_Wrap\n#else\n' + def + '\n#endif');
}

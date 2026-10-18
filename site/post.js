// The bar's finishing: ambient occlusion (contact shadows in every crease: between pieces, under bowls, where the cup
// meets the counter), then tone mapping. Cheap fallbacks: no AO on weak devices (it is decided by measuring frames).
//
//   const post = new Post(renderer, scene, camera, { dpr, quality })
//   post.setSize(w, h); post.render();            // instead of renderer.render
//   post.setQuality(0 | 1 | 2)                    // 0 = plain render, 1 = half-resolution AO, 2 = full

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// GTAOPass draws the whole scene with a normal material to find the creases; glass and other see-through things must not
// count there (a pane of glass in front of the bowls would shade them all)
class AOPass extends GTAOPass {
  overrideVisibility() {
    super.overrideVisibility();
    this.scene.traverse(o => {
      if (!o.isMesh || !o.material) return;
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      if (ms.every(m => m.transparent || (m.userData && m.userData.noAO))) o.visible = false;
    });
  }
}

export class Post {
  constructor(renderer, scene, camera, { quality = 2 } = {}) {
    this.renderer = renderer; this.scene = scene; this.camera = camera;
    this.quality = quality;
    this.w = 2; this.h = 2;
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const rt = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(renderer, rt);
    this.composer.addPass(new RenderPass(scene, camera));
    this.ao = new AOPass(scene, camera, size.x, size.y);
    this.ao.updateGtaoMaterial({ radius: 0.05, distanceExponent: 1.3, thickness: 1.2, scale: 1.15, samples: 12, distanceFallOff: 1.0, screenSpaceRadius: false });
    this.ao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 12 });
    this.ao.blendIntensity = 0.9;
    this.composer.addPass(this.ao);
    this.composer.addPass(new OutputPass());
    this.setQuality(quality);
  }

  setQuality(q) {
    this.quality = q;
    this.ao.enabled = q > 0;
    this.composer.passes.forEach(p => { if (p.isRenderPass || p.constructor.name === 'OutputPass') p.enabled = true; });
  }

  // w, h in CSS pixels; the pixel ratio comes from the renderer
  setSize(w, h) {
    this.w = w; this.h = h;
    this.composer.setPixelRatio(this.renderer.getPixelRatio());
    this.composer.setSize(w, h);
    // half-resolution occlusion on the middle setting (it is soft anyway)
    if (this.quality === 1) { const pr = this.renderer.getPixelRatio(); this.ao.setSize(Math.max(2, Math.round(w * pr / 2)), Math.max(2, Math.round(h * pr / 2))); }
  }

  render() {
    if (this.quality > 0) this.composer.render();
    else this.renderer.render(this.scene, this.camera);
  }
}

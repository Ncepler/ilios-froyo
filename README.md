# Ilios Froyo: 3D cup, soft-serve machine, and "the pour" hero

A client concept for **Ilios Froyo** (organic Greek frozen yogurt, 1355 Old Northern Blvd, Roslyn NY).
Everything here is generated from code: the models, the textures, the gold sun emblem, and the renders.
No stock images, no AI images.

This folder is self-contained and is **not part of the Vilas Next.js site build**: nothing in `app/`
imports it, and tsconfig and ESLint don't touch it. Once the client site has its own repo, move it there.

## What's in here

```
models/
  ilios-froyo-cup.glb            1.3 MB  cup + gold-foil emblem + seam + soft-serve swirl (meshopt + WebP)
  ilios-softserve-machine.glb    0.7 MB  the shop's wall-set twist machine: header sign, 3 animated handles,
                                         black door, 3 spouts, drip tray with oval drains, cup stack (meshopt + WebP)
  ilios-room.glb                 0.2 MB  limewash wall with the niche and plaster frame, travertine ledge,
                                         gold wall sun with 3D ILIOS / FROYO letters
  draco/                                 the same three, Draco-compressed (0.8 / 0.6 / 0.2 MB)
site/                                    the scroll-driven hero site (plain HTML + JS, no build step)
renders/                                 photoreal Cycles renders (product shots, macro, machine)
source/
  mpm.py                                 the pour: a yield-stress paste (MLS-MPM) simulation (see below)
  validate.py / bake_web.py / analyze.py  physics checks, web bake, surface extraction
  toppings.py                            Blender: the topping pieces (vertex-painted, one material) -> toppings.glb
  clearance.py                           proves the cup never touches the dispenser, tray or room
  tex.py                                 procedural textures: sun emblem, paper, brushed steel, marble, froyo micro-surface
  build.py                               Blender script: builds the cup, swirl, machine, materials; exports GLB + pour path
  render.py                              Cycles product renders
```

## Using the models on a website

The GLBs are standard glTF 2.0 with PBR materials (metal/roughness, clearcoat, sheen, normal maps).
They drop straight into three.js, `<model-viewer>`, Babylon, Spline, Framer, and Webflow (via model-viewer).

Quickest embed (Google's `<model-viewer>`, supports both meshopt and Draco):

```html
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<model-viewer src="ilios-froyo-cup.glb" camera-controls auto-rotate shadow-intensity="1"
  environment-image="neutral" exposure="1.1" alt="Ilios froyo cup" style="width:100%;height:520px"></model-viewer>
```

three.js:

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load('ilios-froyo-cup.glb', g => scene.add(g.scene));
```

Scale is real-world metres, Y up, front of the cup facing +Z. The cup is 6.2 cm tall and 9.1 cm across the rim.

### Node names you can drive

| File | Node | What it is |
|---|---|---|
| cup | `Cup` | paper bowl: rolled rim, recessed base, rolled bottom skirt |
| cup | `Emblem` | gold-foil sun face + ILIOS / FROYO wordmark (alpha decal) |
| cup | `CupSeam` | the glued side seam at the back |
| cup | `Swirl` | the soft-serve rope. Carries a `_reveal` vertex attribute, 0 at the start of the pour and 1 at the tip |
| cup | `SwirlCore` | hidden fill inside the cup, seen between the coils |
| machine | `HandleL` / `HandleC` / `HandleR` | draw handle pivots (left flavor, twist, right flavor). Rotate on X from 0 to 0.96 rad to pull. `HandleC` is also baked as the `PullHandle` clip |
| machine | `Spout0..2` / `SpoutStar0..2` | the three spouts; exit points are in `site/assets/pour-path.json` (`nozzlesMachine`) |
| machine | `SignFace` | the header sign: Sweet Harbor Coffee, sun + ILIOS FROYO, Organic Vanilla Bean (texture from `tex.py`, easy to re-letter) |

`site/assets/pour-path.json` holds the swirl's centreline (cup-local, with the matching `_reveal` value per point),
the nozzle position, and where the cup sits on the drip tray. The site uses it to keep the falling stream locked to
the pour front.

## The hero site (`site/`)

Screen one is the shop's station: the three-handle machine in its limewash niche, with the gold sun on the wall.
You pick a flavor (Sweet Harbor Coffee, Twist, or Organic Vanilla Bean, from the real machine sign), then pull,
either by dragging a handle or by scrolling. A ribbon of froyo leaves
the star spout, the camera follows it down, and the cup circles under the spout while the swirl builds coil by coil,
the same way it's done at a real counter. Then the tail breaks off, the tip curls, the handle springs back, and the
page settles on the finished cup with directions.

- Everything is rendered live in WebGL (three.js r169, vendored in `site/vendor/three`, MIT). There is no video file.
- The flavor is a shader on the froyo: one color, or two-tone stripes that follow the ridges for the twist, with
  tiny dark specks for vanilla bean. The same choice carries into the spin viewer below.
- The froyo is a simulated paste, baked. Soft serve is a foam (about 40-60% overrun, ~700 kg/m3) that behaves as a
  shear-thinning yield-stress solid: it holds its shape until stress passes a yield value, then flows. `source/mpm.py`
  simulates it with the material point method (Hencky-strain elasticity, von Mises yield with viscous regularization,
  after Yue et al. 2015 "Continuum Foam" and the PAC-NeRF return map), 4 mm grid, ~31k particles. A server's-hand
  model runs it: it spirals out and in to fill the cup in layers, turns a ring at the rim, spirals a dome inward,
  rides the nozzle up with the pile, shrinks the nozzle opening to close the valve and lifts away to pull the peak.
  Parameters: rho 700, tau_y 650 Pa, mu 8000, lambda 32000, eta 14 Pa s. **tau_y is tuned to give the cone height seen in
  the shop photos, not measured.** `source/validate.py` writes `physics_report.json`: it comes to rest (p99 speed
  1.5 mm/s), the stream keeps its thickness, nothing leaves the paper, the 11 cm pile is under the 16 cm
  self-supporting limit sqrt(3) tau_y/(rho g), and volume is conserved. Some air stays trapped between layers
  (void fraction ~0.28 inside the cup), as in real soft serve. Not modelled: the star-nozzle ridges.
  The site replays the baked frames (`pour.bin`, 4.7 MB: 1.5 mm voxel fields, flavour at half resolution, keyframe +
  deltas, deflate) and meshes each frame with marching cubes in the browser (wide-stencil normals, so the surface is
  smooth, with a fine bubble grain in the shader), so scrolling scrubs the simulation, forwards or back.
- **Nothing touches.** `source/clearance.py` rebuilds the cup's whole path (all three handles, 401 scroll positions) and
  tests it against every surface of the machine, tray and room, plus the froyo, with 1 mm of clearance. The nozzle is
  a 20 mm star tip and a 34 mm white cap 30 mm above it, sized so the simulated hand never carries either into the cup
  wall; the page also clamps the hand to the same limits (`nozzleCap()` in `site/main.js`). Result: no overlaps.
- The scroll position is eased (frame-rate independent lerp) and the render loop rests once it has caught up.
- Phones get the same 3D scene with portrait framing. Reduced motion gets the finished frame, with no scrubbing.
  If WebGL fails, the page shows a still render.
- Below the hero: the name story (Ilios = Greek for sun), **the topping bar** (below), the flavors on the machine
  signs, and visit/directions.
- **The topping bar** (`site/toppings.js`, `source/toppings.py`): the finished cup, live, with the 14 items from the
  shop's bar, built from the photos of it: pistachio kataifi (green cream, golden shreds, crushed pistachio), Biscoff
  crunch (caramel and cookie shards), cinnamon-roll bites with icing, honey, Nutella, diced strawberry and mango,
  chopped dates, fig quarters, oat granola clusters, dark chocolate chips, brownie cubes, New York rainbow-cookie
  slices and nonpareil sprinkles. Solid pieces are rigid bodies in a physics engine (Rapier, WASM): each is a convex
  hull of its modelled mesh with its own weight and friction, dropped over the swirl in slow motion onto the froyo's
  own collision mesh (the last frame of the pour), so they land, tumble and set into it (soft serve is cold and tacky:
  whatever touches it sticks). Sauces are a thread ray-cast onto whatever is under it, froyo and pieces alike, drawn on
  over a second. Any combination works; the physics is live, not baked, so it never plays the same way twice.

Preview locally (it has to be served; opening `index.html` from disk won't load the models):

```
cd ilios-3d/site && python3 -m http.server 8080
# open http://localhost:8080
```

## Regenerating everything

Needs Blender as a Python module (`pip install bpy==4.2.0 "numpy<2" pillow scipy` on Python 3.11),
plus `@gltf-transform/cli` for compression.

```
python source/tex.py   /tmp/tex
python source/build.py /tmp/tex /tmp/out
python source/render.py /tmp/tex /tmp/out cup_hero 128 1600     # also: cup_top, cup_macro, machine, machine_pull
npx gltf-transform optimize /tmp/out/ilios-froyo-cup.glb site/assets/models/ilios-froyo-cup.glb \
    --compress meshopt --texture-compress webp --texture-size 2048 --simplify false
```

Keep `--simplify false` (it would re-mesh the swirl) and, for the machine, `--flatten false --join false`
(they would merge away the three handle pivots).

The pour (about 10 min for 4 mm on 4 cores):
```
DX=0.004 MU=8000 LAM=32000 TAU_Y=650 D_RHO=0.011 CLOSE_T=0.24 PEAK_LIFT=0.034 PEAK_SIDE=0.026 python source/mpm.py /tmp/mpm
python source/validate.py /tmp/mpm
python source/analyze.py /tmp/mpm last --obj /tmp/mpm/last.obj --vs 0.0014
python source/bake_web.py /tmp/mpm site/assets
SWIRL_OBJ=/tmp/mpm/last.obj python source/build.py /tmp/tex /tmp/out   # then compress as above
```
Check the dispenser clearance, rebuild the toppings, and compress them:
```
python source/clearance.py /tmp/out/ilios-softserve-machine.glb /tmp/out/ilios-room.glb /tmp/out/pour-path.json /tmp/mpm 1
python source/toppings.py /tmp/top            # add `sheet` as a 2nd argument for a Cycles contact sheet
npx gltf-transform optimize /tmp/top/toppings.glb site/assets/models/toppings.glb --compress meshopt --simplify false --flatten false --join false
```
`source/sim.py` is the superseded elastic-rope version (it looked like a worm); kept for reference only.

Sources: US 4,452,823 (soft-serve overrun); Herschel-Bulkley ice-cream mixes (agris.fao.org 65dfb43f); Yue et al.
2015 Continuum Foam; PAC-NeRF (arXiv 2303.05512).

## Before this goes to the client

- **Copy:** flavors and toppings are taken from the shop's own signs (seen in a customer's photos, Sept 2026): Organic
  Vanilla Bean, Organic Original Tart, Sweet Harbor Coffee, Raspberry; pistachio kataifi, Biscoff crunch, honey,
  cinnamon rolls, Nutella, strawberry, mango, dates, figs, granola (NF/GF), chocolate chips, brownies, rainbow cookies,
  sprinkles. Flavors rotate, so confirm the current list. There are no hours on the page yet.
- **Emblem:** the sun face is a faithful redraw of the cup in the photo, not the client's vector file. If they can
  send the real logo (SVG/AI), swap it into `tex.py` (`sun_emblem`) and rebuild.
- **Machine:** modelled from photos of the shop's station (layout, sign, handles, tray, niche). Faceplate stickers are
  generic stand-ins; no third-party logos are reproduced.

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
  sim.py                                 the pour: a viscous-rope physics simulation (see below)
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
- The froyo is real physics, baked: `source/sim.py` simulates the soft serve as a viscous rope (position-based
  dynamics). It is extruded from the star spout at a steady rate; gravity draws the falling column out and it thins
  (radius follows volume conservation); it bends softly; it collides with the cup and with the rope already in it;
  pieces that land lying flat set almost at once while upright folds topple first (yield stress); and the server's
  hand circles the cup, filling it in flat layers and then stepping inward to build the dome, steering by watching
  where the rope touches down. When the valve closes the tail breaks off and falls onto the top. The site replays
  the baked frames as one live rope (`pour-sim.bin`, 0.4 MB) as you scroll, forward or back.
- The downloadable cup's `Swirl` is the simulation's final frame. It still carries a `_reveal` attribute (0 where the
  rope starts, 1 at the tip), so another site can animate a simple pour with a one-line shader discard.
- The scroll position is eased (frame-rate independent lerp) and the render loop rests once it has caught up.
- Phones get the same 3D scene with portrait framing. Reduced motion gets the finished frame, with no scrubbing.
  If WebGL fails, the page shows a still render.
- Below the hero: the name story (Ilios = Greek for sun), an interactive spin viewer of the same cup model,
  the flavors on the machine signs, the topping bar, and visit/directions.

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

The pour: `python source/sim.py /tmp/sim` (about 25 s on a laptop CPU), then pass `/tmp/sim` as the third
argument to `build.py` so the cup's swirl is the simulation's final frame, and copy `pour-sim.json` +
`pour-sim.bin` into `site/assets/`.

## Before this goes to the client

- **Copy:** flavors and toppings are taken from the shop's own signs (seen in a customer's photos, Sept 2026): Organic
  Vanilla Bean, Organic Original Tart, Sweet Harbor Coffee, Raspberry; pistachio kataifi, Biscoff crunch, honey,
  cinnamon rolls, Nutella, strawberry, mango, dates, figs, granola (NF/GF), chocolate chips, brownies, rainbow cookies,
  sprinkles. Flavors rotate, so confirm the current list. There are no hours on the page yet.
- **Emblem:** the sun face is a faithful redraw of the cup in the photo, not the client's vector file. If they can
  send the real logo (SVG/AI), swap it into `tex.py` (`sun_emblem`) and rebuild.
- **Machine:** modelled from photos of the shop's station (layout, sign, handles, tray, niche). Faceplate stickers are
  generic stand-ins; no third-party logos are reproduced.

# Ilios Froyo: the pour, the cup, and the topping bar

A client concept site for **Ilios Froyo** (organic Greek frozen yogurt, 1355 Old Northern Blvd, Roslyn NY).
Everything is generated from code: the models, the textures, the gold sun emblem, the froyo, the toppings and the
renders. No stock images, no AI images.

What the shop actually serves, how its room is laid out and the order of its topping bar are in
[`docs/ILIOS-FIELD-NOTES.md`](docs/ILIOS-FIELD-NOTES.md) (researched from the shop's and customers' TikToks and
local press, October 2026). The site follows those notes.

## What's in here

```
site/                       the website: plain HTML + ES modules, no build step (three.js r169 vendored)
  index.html                page, styles, copy
  main.js                   the hero: machine, room, flavor picker, scroll timeline, camera
  pour-sim.js               the pour, simulated in the browser (no three.js, also runs headless)
  pour.js                   draws the simulated rope as star-ridged soft serve, scrubbable both ways
  froyo.js / shade.js       the six flavours and the soft-serve material (wrapped light, pores, twist, bean specks)
  cup.js / cup-dims.js      the real-size Ilios cup, built in code
  bar.js                    "Top it off": the topping bar, live (scene, utensils, physics, sauces, swipe mode)
  bar-heap.js               the bowls and the settled heaps of pieces in them
  bar-pieces.js             topping materials, loader for the modelled pieces, procedural fallbacks
  post.js                   the bar's ambient-occlusion pass and tone mapping
  bar-list.js               plain-text bar list, used when WebGL is off
  2/                        option two: the whole site with no 3D (one HTML file + img/), see below
  assets/models/            machine, room, cup materials, topping-v2 pieces (glTF, meshopt)
  assets/bar-heaps.json     every bowl's settled pile (piece, position, rotation), from Blender's rigid-body physics
models/                     the same GLBs for use elsewhere (plus Draco versions)
renders/                    Cycles product renders
docs/ILIOS-FIELD-NOTES.md   flavors, toppings, store layout, directions, sources
source/
  toppings/                 the topping pieces: a signed-distance modelling kit, one module per family (see its README)
  build_toppings.py         builds the pieces into a packed GLB, and with --heaps settles every bowl in Blender
  dev/pieces.mjs            renders the pieces lab (site/_pieces.html) to a PNG, for judging pieces
  validate_pour.mjs         headless checks on the site's pour -> physics_report.json
  build.py / tex.py         Blender: cup, machine, room, materials, textures -> GLB
  toppings.py               the first, simpler topping pieces (toppings.glb, now only a fallback)
  render.py                 Cycles product renders
  clearance.py              dispenser clearance check (written against the earlier baked pour)
  mpm.py, validate.py, bake_web.py, analyze.py, sim.py
                            earlier pour pipelines (MLS-MPM bake, elastic rope), superseded; kept for reference
```

Preview locally (it has to be served; opening `index.html` from disk won't load the models):

```
cd site && python3 -m http.server 8080
# open http://localhost:8080
```

## Option two: `site/2/` (no 3D)

A second, complete version of the site to pitch side by side with the 3D one, served at `/2/`. No WebGL: a calm,
editorial page in the shop's own palette (limewash milk and oat, the gold sun, one olive branch), built to feel
like the room. Sections: announcement ticker, hero, flavors today, toppings today (filterable), the warm pistachio
kataifi, how it works, the story, the shop, visit (live open/closed in New York time, hours, map), FAQ, Instagram,
a monthly-flavor email form, footer.

- `site/2/index.html` holds the page, styles and script (no build step, no libraries).
- **Daily edits** are in the HTML: each flavor is one `<li class="flavor">`; add `class="soon"` to a topping that's
  not out today. The ticker and the hero's "Now pouring" chip are plain text next to them. Hours live in `HOURS`
  in the script and in the hours list.
- The flavor photos are the `renders/cup-hero.jpg` Cycles render with the froyo recoloured per flavor (the twists
  are two flavors banded along each coil); the skillet and the lounge are SVG illustrations in `site/2/img/`.
- **Before launch:** point the email form at the shop's mailing list (it only confirms on the page for now) and
  make `og:image` absolute.

### Halloween: `site/2/halloween/`

The same page after dark, served at `/2/halloween/`: every section, the toppings filter, the live open/closed
status and the email form carry over, in a plum-black room with a pumpkin glow. Kept deliberately light: the line
sun still turns behind the hero arch (in candlelight) under a full moon, the olive branch stays (moonlit), one bat
crosses now and then, the sun mark is a jack-o'-lantern sun, the kicker rules are candy corn, and the "on the
machines tonight" line counts the nights to Halloween. The flavors keep their real names except Ghost Tart; the
warm station is "the cauldron", and there's a costume question in the FAQ. Animation stops under reduced motion.

- `site/2/halloween/index.html` is a copy of `site/2/index.html` with its own tokens, copy and decorations; daily
  edits work the same way. It links back to `/2/` from the footer.
- The photos are night grades of `site/2/img/`, with small ghost faces on the white swirls:
  `python3 source/dev/halloween_img.py` rebuilds them into `site/2/halloween/img/`. `lounge.svg` (moon, cobweb,
  jack-o'-lanterns) and `cauldron.svg` (the skillet's kataifi in an iron pot, bubbling) are illustrations there.

## The hero: the pour

Screen one is the shop's station: the machine in its limewash niche with the gold sun on the wall. Pick one of the
six flavors on the machine signs (Sweet Harbor Coffee, Coffee + Vanilla Bean twist, Organic Vanilla Bean, Raspberry,
Raspberry + Vanilla Bean twist, Organic Original Tart). The header sign re-letters for the machine that pours it, and
the matching handle pulls. Then pull, either by dragging the handle or by scrolling. The rope of froyo leaves the
star spout, bends and falls, and lands in the cup, which circles under the spout so the coils are laid in rings,
fills the cup in layers, builds the swirl over the rim, then the valve closes, the cup drops away and the tail
breaks and curls into the tip. Scrolling back runs it backwards exactly.

**How it's simulated** (`site/pour-sim.js`, runs once on page load in about 0.4 s):

- Soft serve is a foam (about 50% air) that behaves as a yield-stress paste: under its yield stress it is a soft
  solid, over it, it flows. Out of the spout that makes it a rope that keeps its thickness (it doesn't neck or
  drip like a liquid), bends under its own weight over a few centimetres, and stops dead where it lands.
- The rope is a chain of nodes (position-based dynamics) fed out of the nozzle at the extrusion speed (0.17 m/s,
  a 16 oz cup in about 8 s, as in the shop's videos): inextensible links, bending stiffness, gravity and air drag,
  and sticky contact against the paper and the froyo already laid (cold soft serve is tacky). A node that lands
  and stops freezes for good.
- Laid coils are flattened ellipses (16% wider, 16% lower, area kept) and contact is measured in that shape, so new
  coils sit on and press 7% into old ones.
- The server's hand is a feedback controller over the pile's own height map, the way a server watches the cup:
  spiral in and out to fill in layers, keep the spout about 2 cm over the pile and its cap out of the cup, a ring
  at the rim, wind in for the swirl, lift slowly with the valve part open to draw the peak, then close and pull
  away.
- Recorded at 240 Hz, only the nodes still moving, so any scroll position is an exact state, forwards or back.

**How it's drawn** (`site/pour.js`, `site/froyo.js`): an 8-point star cross-section (the 20 mm star tip) swept
along the rope with rotation-minimising frames, round while it falls and slumping into the wider laid coil after it
lands. The laid coils are blended into each other (no crumpled facets where they overlap), the ridges fade out as
the rope thins at the break so the tip is a smooth curl, and the swirl runs 3.2 turns to a proper peak. The material
is soft serve rather than plastic: matte and creamy, with wrapped diffuse light that glows warm at the terminator
(a cheap stand-in for light scattering inside the foam), fine pores, narrow dark valleys between coils (ambient
occlusion written per vertex by the renderer), the twist's two flavors as soft-edged stripes that wind with the
ridges, and vanilla bean specks.

**Checks:** `node source/validate_pour.mjs physics_report.json` runs the same code and fails if the rope stretches
over 5%, any coil ends up outside the paper or under the floor, the spout's cap enters the cup, the pour doesn't
come to rest by itself, the swirl height is off, or scrubbing isn't exact. Current result: 652 nodes, 1.37 m of
rope, link stretch p99 3.4%, nothing outside the paper, cap never in the cup, peak 7.3 cm over the rim, pass.

**The cup** (`site/cup.js`): the shop's white paper food cup at its real size, measured against hands, spouts and the
drip-tray drains in the shop's videos: 9.6 cm across the rim, 7.4 cm across the base, 8.4 cm tall (16 oz), with the
rolled rim and the printed cream square carrying the gold sun and ILIOS FROYO. The paper and gold-foil materials
come from `ilios-froyo-cup.glb`.

## Top it off: the topping bar

`site/bar.js` loads as you near it. It is the shop's line (see the field notes): one long quartz counter behind a low
glass guard, the bowls in two staggered rows in the order you meet them after the machines, then the warm station,
then the register under the gold sun. Your cup sits on the counter in front of the glass, the way it does in the
shop, and scrolling slides it down the line. The strip at the top (Fruit, Candy & Crunch, Warm, Pay) shows where
you are.

- **33 toppings**, each clickable where it sits. Fresh fruit and sauce: strawberries, golden mango, granola (nut
  free, gluten free), dates, fresh figs, raspberry sauce, kiwi, blueberries, green grapes, honeydew, coconut,
  pineapple. Candy and crunch: gummy bears, M&M's, rainbow sprinkles, brownie bites, rainbow cookies, chocolate
  chips, chocolate sprinkles, Rice Krispies treats, Oreo crumble, mini cookies, Biscoff cookies, cookie dough,
  sour strips, gummy worms, chocolate chunks. Warm: pistachio kataifi (the thick filling in its skillet, served with
  a disher), Nutella, Biscoff cookie butter, cinnamon rolls (mini rolls in icing), honey, olive oil + sea salt.
- **Each one has its own utensil** (wooden spoon, tongs, scoop, soup spoon, ladle, disher, the honey jar, the oil
  jug). Click and it dips into the bowl, lifts a serving, carries it over the cup and tips it in.
- **In order.** Toppings go on in the order you click, on top of what's already there. Nothing is redone: a
  drizzle added last runs over the toppings already on.
- **The food is modelled, not decorated boxes** (`source/toppings/`, 29 families, 183 pieces). Each piece is a signed
  distance field meshed with marching cubes, so every vertex knows its depth below the original skin and is coloured
  by it: a strawberry is a whole seeded berry cut by planes (dice, wedges, halves, slices), with red flesh and a pale
  core on the cut faces; kiwi shows its core, rays and a ring of seeds; gummy bears are smooth unions of ellipsoids
  with glossy translucent jelly; M&M's carry the printed "m"; rainbow cookies have their seven layers; the cinnamon
  rolls have a spiral and pooled icing; kataifi and coconut are swept strands and ribbons. Every variant of a family
  is different (size, cut, ripeness). One shader per surface class (matte, wet fruit, candy shell, chocolate, jelly)
  adds gloss, a micro bump and light passing through thin or translucent parts.
- **Bowls are filled by physics.** Each bowl's pile is settled ahead of time and stored in `assets/bar-heaps.json` (about
  7,000 visible pieces across 24 bowls, 60 to 1,000 per bowl, 460 KB). Chunky pieces (strawberries, mango, kiwi, gummy
  bears, M&M's, brownies and so on, 18 bowls) are dropped into the bowl in Blender's rigid-body engine and left to rest
  on each other, leaning and overlapping. Bowls of tiny pieces (chips, Oreo crumble, coconut, granola, Biscoff shards)
  would take hours that way, so those are deposited onto a height field: each piece lands in the lowest of several
  random spots, in an orientation it could rest in (plates flat, ribbons along the surface). The page draws piles as
  instanced meshes using decimated copies of the pieces (they are 25 to 40 px on screen), which keeps the whole line
  near 3 million triangles a frame with the occlusion pass on. Servings and everything in the cup use the full meshes.
  The pieces ship as one 4.4 MB file, quantised and meshopt-compressed (`source/toppings/pack.py`; the same data as
  float32 is 17 MB).
- **Lighting:** one warm key light with a soft shadow, a cool rim from behind, a little sky and room reflection, and a
  screen-space ambient-occlusion pass (`site/post.js`) for the contact shadows in every crease. The glass guard is a
  reflection-only layer: clear glass has no body colour, and it used to veil the bowls behind it. Weak devices drop
  the AO, then the soft shadows, by themselves.
- **Physics in the cup:** pieces fall onto the froyo's real surface (a height map of the simulated swirl), slide off steep
  spots, never perch on another piece's tip, and stay inside the paper. Sauces are laid along the spoon's path,
  sag between high points under gravity and run down where the swirl is steep, with drips. The pistachio dollop
  presses the swirl's tip down and slumps over it. Undo and Start over rebuild the surface.
- No WebGL: the bar becomes a plain list of everything on it, by station.

## Everything else on the page

The name story (Ilios is Greek for sun), the flavors on the machine signs (including the rotating flavor), and the
visit card with the address, hours (Tuesday to Sunday, 5 to 10 pm), directions and Instagram.

- Rendered live in WebGL (three.js r169, vendored in `site/vendor/three`, MIT). No video files.
- Scroll is eased (frame-rate independent) and the render loop rests once it catches up.
- Phones get the same scenes with portrait framing. On a phone the topping bar is one screen tall and you move along
  it by swiping left and right (the counter follows your finger and coasts), the way you'd walk the line, instead of
  scrolling down to go right; the station strip jumps between sections. Reduced motion gets the finished frame with
  no scrubbing. If WebGL fails, the hero shows a still render and the bar shows its list.

## Using the models elsewhere

The GLBs in `models/` are glTF 2.0 with PBR materials (metal/roughness, clearcoat, sheen, normal maps) and drop into
three.js, `<model-viewer>`, Babylon, Spline, Framer and Webflow (via model-viewer). Scale is real-world metres, Y up,
front facing +Z.

```html
<script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
<model-viewer src="ilios-softserve-machine.glb" camera-controls shadow-intensity="1"
  environment-image="neutral" exposure="1.1" alt="Ilios soft-serve machine" style="width:100%;height:520px"></model-viewer>
```

| File | Node | What it is |
|---|---|---|
| machine | `HandleL` / `HandleC` / `HandleR` | draw handle pivots (left flavor, twist, right flavor). Rotate on X from 0 to 0.96 rad to pull |
| machine | `Spout0..2` / `SpoutStar0..2` | the three spouts; exit points are in `site/assets/pour-path.json` (`nozzlesMachine`) |
| machine | `SignFace` | the header sign (the site re-letters it per machine on a canvas) |
| cup | `Cup` / `Emblem` / `CupSeam` | the earlier, smaller cup model (6.2 cm tall). The site now builds the real-size cup in `site/cup.js` and only takes its materials |

## Regenerating the models

Needs Blender as a Python module (`pip install bpy==4.2.0 "numpy<2" pillow scipy` on Python 3.11), plus
`@gltf-transform/cli` for compression.

```
python source/tex.py   /tmp/tex
python source/build.py /tmp/tex /tmp/out
python source/render.py /tmp/tex /tmp/out cup_hero 128 1600     # also: cup_top, cup_macro, machine, machine_pull
npx gltf-transform optimize /tmp/out/ilios-softserve-machine.glb site/assets/models/ilios-softserve-machine.glb \
    --compress meshopt --texture-compress webp --texture-size 2048 --simplify false --flatten false --join false
```

The toppings (about 20 minutes on 4 cores; needs `scikit-image meshoptimizer` and `bpy` for the heaps, see
`source/toppings/README.md`):

```
python source/build_toppings.py /tmp/full --heaps --jobs 3
cp /tmp/full.glb site/assets/models/toppings-v2.glb && cp /tmp/full-heaps.json site/assets/bar-heaps.json
```

Keep `--flatten false --join false` for the machine (they would merge away the handle pivots). The pour needs no
regeneration: it is simulated by the page. To tune it, change `POUR` in `site/pour-sim.js` and rerun
`node source/validate_pour.mjs physics_report.json`.

## Before this goes to the client

- **Copy:** flavors, toppings, hours and owners are from the shop's own posts and signs and from local press (see
  the field notes). Flavors rotate (a banana rotation has been seen), so confirm the current list before launch.
- **Emblem:** the sun face is a faithful redraw of the cup, not the client's vector file. If they can send the real
  logo (SVG/AI), swap it into `tex.py` (`sun_emblem`) and rebuild.
- **Machine:** modelled from photos and videos of the shop's station. Faceplate stickers are generic stand-ins; no
  third-party logos are reproduced.

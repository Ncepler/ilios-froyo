# The topping pieces

Photoreal-as-we-can-get-it models of everything on the Ilios topping bar, built from code (numpy signed-distance fields,
marching cubes), written to `toppings-v2.glb`, and settled into their bowls by Blender's rigid-body physics
(`bar-heaps.json`). The page draws them as instanced meshes under one shader per surface class.

Why signed-distance fields: a piece of fruit is a whole fruit cut by planes. If the whole is a distance field, every
vertex of every piece knows its depth below the original skin, and that depth is what colours it (a strawberry:
seeded skin outside, red flesh, a pale core in the cut face). The same kit makes gummy bears (smooth unions of
ellipsoids), chocolate chunks, brownies, cookies, granola.

## Layout

```
lib.py       the kit: noise, SDF primitives, meshing, per-piece AO, GLB writer      (do not change; add helpers to your module)
fruit.py     fresh fruit            PIECES = { key: dict(fn=, n=, heap=) }
candy.py     candy
baked.py     baked / crunchy / warm
heap.py      rigid-body heaps (Blender)       heaps.py   picks how many pieces fill a bowl
../build_toppings.py                           builds everything / a subset
../dev/pieces.mjs                              renders the pieces lab to a PNG
```

`key` is the topping's key in `site/bar.js` (`BAR`): strawberry, mango, granola, dates, figs, kiwi, blueberries, grapes,
honeydew, coconut, pineapple, gummies, mms, sprinkles, brownies, rainbow, chips, jimmies, krispies, oreo, cookies,
biscoffbits, dough, sour, worms, chunks, cinnamon. A piece builder is `fn(i) -> piece(...)` for variant `i`; the
mesh is named `<key>_<i>`.

## Writing a piece

```python
def mango(i):
    rng = np.random.default_rng(2000 + i)
    f = lambda P: ...                       # P is (N, 3) metres, Y up; return the signed distance (negative inside)
    def paint(V, N, field):                 # V (n,3) positions, N (n,3) unit normals
        ...
        return rgb_linear (n,3), roughness (n,), translucency (n,), specular (n,)
    return piece('mango_%d' % i, f, lo, hi, voxel, paint, smooth=2, cls='wet')
```

- `lo, hi`: the box to mesh. `voxel`: marching-cubes cell, 0.55 to 0.9 mm for pieces of 6 to 20 mm. Triangle budget:
  large pieces <= 3500, small <= 1200, tiny (sprinkles) <= 250. Check the build's "tris each" line.
- Colours are **linear** (`lin('#c3111d')`). Use `mix`, `smoothstep`, `fbm`, `vnoise`, `worley` (cells: seeds, bubbles, chips).
- Paint with *position-derived* quantities (depth below the original surface, distance from the axis, noise), not
  random per-vertex values, so it looks like material, not noise.
- `cls`: `wet` (cut fruit: glossy, translucent), `candy` (hard glossy shell, glazed), `choc` (chocolate), `jelly`
  (gummies: very translucent), `matte` (baked, dry, crumbly). It picks the page's material (gloss, micro bump).
- translucency (`sss`, 0..1): how much light passes through and colours the shadow side. Cut fruit 0.5-0.8, gummies
  0.9-1, grapes 0.8, chocolate 0.05, baked goods 0.1-0.2, skins 0.2-0.3.
- `flat=True` for thin pieces that lie flat (cookies, slices, strips): the page lays them on the froyo that way.
- Sizes are real. A bar piece is 6 to 25 mm. Make **every variant different** (rng by `i`): size, shape, cut, colour.
  Real heaps are not uniform: mix kinds (wedges and cubes and slices), sizes, ripeness.

## Heaps

`heap=dict(bowl='organic'|'hobnail', over=0.012, phi=0.5)`: the bowl type the shop uses (hobnail for strawberries,
coconut and cookie dough; organic wavy bowl for the rest), how far the heap stands above the rim (m), and the packing
fraction (0.5 for chunky, 0.3 for strands/shreds/crumbs, 0.55 for spheres). `weights=[...]` favours some variants.
`heap=None` for tiny pieces (sprinkles, jimmies): the page scatters those.

## Workflow

```bash
VENV=/tmp/claude-0/-home-user-ilios-froyo/4e98f785-43c7-4414-a5d7-8a63e5d05cfb/scratchpad/venv/bin/python
cd /home/user/ilios-froyo
# 1. the pieces (seconds):
$VENV source/build_toppings.py site/assets/models/_dev-mine --only mango,pineapple
# 2. see them (the site must be served: cd site && python3 -m http.server 8080, already running)
node source/dev/pieces.mjs /tmp/x.png "src=assets/models/_dev-mine.glb&keys=mango&scale=4&wrap=0.5" "0,0.28,0.45|0,0.02,0|30" 1400 700    # big, to judge shape and colour
node source/dev/pieces.mjs /tmp/y.png "src=assets/models/_dev-mine.glb&keys=mango&scale=1" "0,0.17,0.30|0,0.0,0|30" 1400 400            # life size at the bar's distance
# 3. a heap (minutes; run it once the pieces look right):
$VENV source/build_toppings.py site/assets/models/_dev-mine --only mango --heaps
node source/dev/pieces.mjs /tmp/z.png "src=assets/models/_dev-mine.glb&keys=mango&heaps=assets/models/_dev-mine-heaps.json" "0,0.28,0.38|0,0.05,0|30"
```

View the PNGs with the Read tool. Judge honestly against a photograph of the real thing in your head: silhouette,
proportions, the way the colour changes across a surface, where it is glossy and where matte, what the cut face
looks like. Real food is irregular, has two or three kinds of surface, and its colour has *structure* (a pale core,
a darker rim, seeds, fibres, a crust). Flat, uniform, geometric = a fail. At the bar the camera is ~0.35 m away, so a
10 mm piece is 25-40 px: shape, colour structure, gloss and shading carry it; fine detail below ~0.4 mm does not.

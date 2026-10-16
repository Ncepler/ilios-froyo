"""Build the topping pieces (Blender as a module) -> toppings.glb, plus a Cycles contact sheet to check them.

    python toppings.py <out_dir> [sheet]

Every piece is one low-poly mesh in metres (Y up in the GLB), built from reference photos of the shop's topping
bar (strawberry/mango dice, chopped dates, fig quarters, granola clusters, dark chocolate chips, brownie cubes,
rainbow-cookie slices, nonpareils, a cookie-crumb, pistachio crumbs and kataifi shreds, cinnamon-roll bites).
Colour and roughness are painted per vertex: COLOR_0 = rgb (linear) and a = roughness, which the page's single
topping material reads (so one draw call per variant, and no textures to download).
The sauces (honey, Nutella, pistachio cream, Biscoff, icing) are not meshes here: the page lays them as drizzle
along the froyo and anything on it.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector, noise

MM = 0.001
OUT = sys.argv[1]
SHEET = len(sys.argv) > 2
os.makedirs(OUT, exist_ok=True)


def lin(h):
    """sRGB hex -> linear rgb"""
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def fbm(p, oct=3, seed=0.0):
    return noise.fractal(Vector(p) + Vector((seed, seed * 1.7, seed * 2.3)), 0.5, 2.0, oct)


def ridged(p, seed=0.0):
    return 1.0 - abs(noise.noise(Vector(p) + Vector((seed, seed * 1.3, seed * 0.7)))) * 2.0


scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

MAT = bpy.data.materials.new("topping")
MAT.use_nodes = True
objs = {}


def finish(name, bm, colorfn, smooth=True):
    """paint per-loop colours (rgb + roughness in a) and make the object"""
    layer = bm.loops.layers.float_color.get("Col") or bm.loops.layers.float_color.new("Col")
    bm.normal_update()
    for f in bm.faces:
        f.smooth = smooth
        for l in f.loops:
            r = colorfn(l.vert.co.copy(), l.vert.normal.copy(), f)
            l[layer] = (r[0][0], r[0][1], r[0][2], r[1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(MAT)
    scene.collection.objects.link(ob)
    if "Col" in me.color_attributes:
        me.color_attributes.active_color = me.color_attributes["Col"]
        me.color_attributes.render_color_index = me.color_attributes.find("Col")
    objs[name] = ob
    return ob


def blob(bm, radii, cuts=3, rounded=1.0):
    """unit cube -> rounded box with half-extents `radii` (rounded=1 sphere, 0 cube)"""
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        p = v.co.copy()
        s = p.normalized()
        # blend towards the sphere only near the corners so the faces stay flat
        k = rounded * (max(abs(p.x), abs(p.y), abs(p.z)) ** 0) * 0.0
        e = (abs(p.x) ** 4 + abs(p.y) ** 4 + abs(p.z) ** 4) ** 0.25
        q = p / max(e, 1e-6)                      # superellipsoid-ish: round corners, flat faces
        v.co = Vector((q.x * radii[0], q.y * radii[1], q.z * radii[2])) * 1.0
        v.co = Vector((p.x * radii[0], p.y * radii[1], p.z * radii[2])).lerp(v.co, rounded)
    return bm


def displace(bm, amp, freq, seed, aniso=(1, 1, 1), ridge=False, oct=3):
    bm.normal_update()
    for v in bm.verts:
        p = (v.co.x * freq * aniso[0], v.co.y * freq * aniso[1], v.co.z * freq * aniso[2])
        n = ridged(p, seed) * 0.5 if ridge else fbm(p, oct, seed)
        v.co += v.normal * (n * amp)


def new_bm():
    return bmesh.new()


# ------------------------------------------------------------------ strawberry (diced, ~7 mm)
def strawberry(i):
    rng = random.Random(100 + i)
    bm = new_bm()
    s = rng.uniform(3.0, 3.8) * MM
    blob(bm, (s * rng.uniform(.95, 1.15), s * rng.uniform(.8, 1.0), s * rng.uniform(.95, 1.15)), cuts=3, rounded=0.28)
    displace(bm, 0.28 * MM, 220, i * 3.1)
    skin_axis = rng.choice([0, 1, 2])
    red, deep, pink, seed = lin("#a8101c"), lin("#6a0711"), lin("#e8707a"), lin("#e7c35a")

    def col(co, n, f):
        a = [abs(n.x), abs(n.y), abs(n.z)]
        ax = a.index(max(a))
        c = mix(red, deep, 0.5 + 0.5 * fbm((co.x * 400, co.y * 400, co.z * 400), 2, i))
        # the cut faces show the pale core and fibres; one face of a dice may carry the skin and its seeds
        if ax == skin_axis and n[ax] > 0:
            h = abs(noise.noise(Vector((co.x, co.y, co.z)) * 900.0))
            return (mix(deep, seed, 1.0 if h > 0.43 else 0.0), 0.32)
        core = math.exp(-((co.x ** 2 + co.y ** 2 + co.z ** 2) / (2.6 * MM) ** 2))
        c = mix(c, pink, core * 0.8 + 0.1 * abs(fbm((co.x * 700, co.y * 90, co.z * 700), 2, 4 + i)))
        return (c, 0.28)
    return finish(f"strawberry_{i}", bm, col)


# ------------------------------------------------------------------ mango (diced, ~8 mm)
def mango(i):
    rng = random.Random(200 + i)
    bm = new_bm()
    s = rng.uniform(3.6, 4.4) * MM
    blob(bm, (s * rng.uniform(.9, 1.1), s * rng.uniform(.8, 1.05), s * rng.uniform(.9, 1.15)), cuts=3, rounded=0.2)
    displace(bm, 0.22 * MM, 160, i * 2.2)
    a, b = lin("#ef9500"), lin("#f6b414")

    def col(co, n, f):
        fib = 0.5 + 0.5 * noise.noise(Vector((co.x * 250, co.y * 40, co.z * 250)))
        edge = max(abs(co.x), abs(co.y), abs(co.z)) / (4.2 * MM)
        return (mix(mix(a, b, fib), lin("#f08f10"), 0.35 * max(0, edge - 0.7)), 0.22)
    return finish(f"mango_{i}", bm, col)


# ------------------------------------------------------------------ date, chopped (~11 mm)
def date(i):
    rng = random.Random(300 + i)
    bm = new_bm()
    blob(bm, (rng.uniform(5.0, 6.4) * MM, rng.uniform(2.8, 3.4) * MM, rng.uniform(2.8, 3.4) * MM), cuts=3, rounded=0.95)
    displace(bm, 0.7 * MM, 300, i * 1.9, aniso=(0.25, 1, 1), ridge=True)
    displace(bm, 0.25 * MM, 120, i * 5.0)
    dark, mid, flesh = lin("#190a06"), lin("#3e1d0e"), lin("#6e3a18")

    def col(co, n, f):
        t = 0.5 + 0.5 * fbm((co.x * 500, co.y * 500, co.z * 500), 2, i)
        c = mix(dark, mid, t * 0.8)
        if abs(co.x) > 5.4 * MM:                               # the chopped end: lighter, fibrous flesh
            c = mix(c, flesh, 0.6)
        return (c, 0.3 + 0.2 * t)
    return finish(f"date_{i}", bm, col)


# ------------------------------------------------------------------ fig quarter (~17 mm)
def fig(i):
    rng = random.Random(400 + i)
    bm = new_bm()
    blob(bm, (8.5 * MM, 7.0 * MM, 7.0 * MM), cuts=3, rounded=1.0)
    for v in bm.verts:                                         # pear taper
        t = (v.co.x / (8.5 * MM) + 1) / 2
        v.co.y *= 0.75 + 0.5 * (1 - t)
        v.co.z *= 0.75 + 0.5 * (1 - t)
    # cut the fruit into a quarter: keep y>=0 and z>=0
    for no in (Vector((0, -1, 0)), Vector((0, 0, -1))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        r = bmesh.ops.bisect_plane(bm, geom=geom, dist=0.0001, plane_co=Vector((0, 0, 0)), plane_no=no,
                                   clear_inner=False, clear_outer=True)
        edges = [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        bmesh.ops.contextual_create(bm, geom=edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    skin, skin2, rind, flesh, seedc = lin("#2c1431"), lin("#4d2a4a"), lin("#e8d9c7"), lin("#c2384a"), lin("#e9c986")

    def col(co, n, f):
        on_cut = abs(co.y) < 0.00004 or abs(co.z) < 0.00004
        if on_cut and all(abs(l.vert.co.y) < 0.00004 or abs(l.vert.co.z) < 0.00004 for l in f.loops):
            # the cut face: rind -> flesh -> pale centre with the seeds
            d = min(1.0, math.hypot(co.y, co.z) / (7 * MM) + (1 - ((co.x / (8.5 * MM)) ** 2)) * 0.0)
            c = mix(flesh, lin("#f0a0a8"), 0.6 * (1 - d) ** 1.5)
            c = mix(c, rind, max(0.0, (d - 0.86) / 0.14))
            h = abs(noise.noise(Vector((co.x, co.y, co.z)) * 1100.0))
            if h > 0.46 and d < 0.8:
                c = seedc
            return (c, 0.35)
        t = 0.5 + 0.5 * fbm((co.x * 300, co.y * 300, co.z * 300), 2, i)
        return (mix(skin, skin2, t), 0.38)
    return finish(f"fig_{i}", bm, col)


# ------------------------------------------------------------------ granola cluster (~9 mm), oats clumped with honey
def granola(i):
    rng = random.Random(500 + i)
    bm = new_bm()
    for k in range(rng.randint(3, 5)):
        b = new_bm()
        blob(b, (rng.uniform(2.3, 3.6) * MM, rng.uniform(0.9, 1.5) * MM, rng.uniform(1.8, 3.0) * MM), cuts=2, rounded=0.9)
        displace(b, 0.35 * MM, 260, rng.random() * 50, oct=2)
        ang = rng.uniform(0, math.tau)
        M = Matrix.Translation(Vector((rng.uniform(-3, 3) * MM, rng.uniform(-1.4, 1.6) * MM, rng.uniform(-3, 3) * MM))) @ \
            Matrix.Rotation(ang, 4, 'Y') @ Matrix.Rotation(rng.uniform(-.5, .5), 4, 'X')
        b.transform(M)
        me = bpy.data.meshes.new("tmp")
        b.to_mesh(me)
        b.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    toast, dark, oat = lin("#9b6532"), lin("#6c3f1c"), lin("#d1a867")

    def col(co, n, f):
        t = 0.5 + 0.5 * fbm((co.x * 350, co.y * 350, co.z * 350), 3, i)
        c = mix(dark, toast, t)
        flake = 0.5 + 0.5 * noise.noise(Vector((co.x * 600, co.y * 600, co.z * 600)))
        c = mix(c, oat, 0.55 * max(0.0, flake - 0.45) * 2)
        return (c, 0.82)
    return finish(f"granola_{i}", bm, col)


# ------------------------------------------------------------------ dark chocolate chip (~7 mm, flat base)
def chip(i):
    bm = new_bm()
    prof = [(0, 0), (3.5, 0), (3.65, .5), (3.25, 1.8), (2.3, 3.0), (1.1, 3.9), (0, 4.3)]
    ring = [bm.verts.new((r * MM, 0, z * MM)) for r, z in prof]
    es = [bm.edges.new((ring[k], ring[k + 1])) for k in range(len(ring) - 1)]
    bmesh.ops.spin(bm, geom=ring + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=math.tau, steps=18, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.00001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for v in bm.verts:
        v.co.x += (fbm((v.co.x * 400, v.co.y * 400, i), 2) * 0.12) * MM
    c0, c1 = lin("#24120b"), lin("#4b2a18")

    def col(co, n, f):
        return (mix(c0, c1, 0.5 + 0.5 * fbm((co.x * 600, co.y * 600, co.z * 600), 2, i)), 0.32)
    ob = finish(f"chip_{i}", bm, col)
    ob.data.transform(Matrix.Translation((0, 0, -2.15 * MM)))      # centre the chip on its own height
    return ob


# ------------------------------------------------------------------ brownie cube (~10 mm), fudgy and crumbly
def brownie(i):
    rng = random.Random(600 + i)
    bm = new_bm()
    s = rng.uniform(4.2, 5.4) * MM
    blob(bm, (s, s * rng.uniform(.75, .95), s * rng.uniform(.9, 1.1)), cuts=4, rounded=0.2)
    displace(bm, 0.45 * MM, 200, i * 1.3)
    displace(bm, 0.18 * MM, 520, i * 4.4, oct=2)
    d1, d2, crust = lin("#28150b"), lin("#4a2815"), lin("#6a3b1c")

    def col(co, n, f):
        t = 0.5 + 0.5 * fbm((co.x * 500, co.y * 500, co.z * 500), 3, i)
        c = mix(d1, d2, t)
        if n.z > 0.55:                                          # the baked top: a paler, crackled crust
            c = mix(c, crust, 0.55 * (0.5 + 0.5 * noise.noise(Vector((co.x, co.y, co.z)) * 900)))
        return (c, 0.62 if n.z > 0.55 else 0.85)
    return finish(f"brownie_{i}", bm, col)


# ------------------------------------------------------------------ New York rainbow cookie slice (~13 x 9 x 9 mm)
def rainbow(i):
    rng = random.Random(700 + i)
    bm = new_bm()
    W, D = 6.8 * MM, 4.6 * MM
    layers = [(0.55, "#1f0f09", .6), (1.5, "#5da345", .8), (0.45, "#b9361f", .5), (1.45, "#f4d57a", .8),
              (0.45, "#b9361f", .5), (1.5, "#e0474f", .8), (0.55, "#1f0f09", .6)]
    z0 = -sum(h for h, _, _ in layers) * MM / 2
    seq = []
    for h, hexc, rough in layers:
        b = new_bm()
        blob(b, (W + rng.uniform(-.2, .2) * MM, D + rng.uniform(-.15, .15) * MM, h * MM / 2), cuts=2, rounded=0.08)
        b.transform(Matrix.Translation((0, 0, z0 + h * MM / 2)))
        z0 += h * MM
        me = bpy.data.meshes.new("tmp")
        b.to_mesh(me)
        b.free()
        bm.from_mesh(me)
        seq.append((z0 - h * MM, z0, lin(hexc), rough))
        bpy.data.meshes.remove(me)
    skew = rng.uniform(-.25, .25)
    for v in bm.verts:
        v.co.x += v.co.z * skew
        v.co += Vector((fbm((v.co.x * 300, v.co.y * 300, v.co.z * 300), 2, i), fbm((v.co.y * 300, v.co.z * 300, v.co.x * 300), 2, i + 9), 0)) * 0.1 * MM
    choc = lin("#1f0f09")

    def col(co, n, f):
        # colour from the slab the face centre sits in; the long sides show the layers, the ends are chocolate-dipped
        c = f.calc_center_median()
        for z_a, z_b, rgb, rough in seq:
            if z_a - 1e-6 <= c.z <= z_b + 1e-6:
                if abs(n.x) > 0.7 and abs(co.x) > W * 0.96 and (rgb != choc):
                    return (mix(rgb, lin("#3a2014"), 0.0), rough)
                return (mix(rgb, [x * 0.8 for x in rgb], 0.5 + 0.5 * noise.noise(Vector(co) * 700) * 0.4), rough)
        return (choc, 0.6)
    return finish(f"rainbow_{i}", bm, col, smooth=False)


# ------------------------------------------------------------------ cinnamon roll bite (~15 mm, iced)
def cinnamon(i):
    rng = random.Random(800 + i)
    bm = new_bm()
    H = rng.uniform(7.5, 9.0) * MM
    pitch = 2.9 * MM
    turns = rng.uniform(2.0, 2.4)
    r_start = 1.2 * MM
    steps = 90

    def rad(a):
        return r_start + pitch * a / math.tau

    segs = []
    # alternating dough / cinnamon filling strips along the spiral, extruded to height H
    bands = [(0.0, 2.3 * MM, "dough"), (2.3 * MM, 2.9 * MM, "fill")]
    for (o0, o1, kind) in bands:
        prev = None
        for k in range(steps + 1):
            a = turns * math.tau * k / steps
            c, s = math.cos(a), math.sin(a)
            r0, r1 = rad(a) + o0, rad(a) + o1
            Ht = H if kind == "dough" else H * 0.78
            ring = [bm.verts.new((r0 * c, r0 * s, 0)), bm.verts.new((r1 * c, r1 * s, 0)),
                    bm.verts.new((r1 * c, r1 * s, Ht)), bm.verts.new((r0 * c, r0 * s, Ht))]
            if prev:
                for q in range(4):
                    try:
                        bm.faces.new((prev[q], prev[(q + 1) % 4], ring[(q + 1) % 4], ring[q]))
                    except ValueError:
                        pass
            else:
                try:
                    bm.faces.new(ring)
                except ValueError:
                    pass
            prev = ring
        try:
            bm.faces.new(prev[::-1])
        except ValueError:
            pass
        segs.append(kind)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if (e.verts[0].co - e.verts[1].co).length > 2.5 * MM and abs(e.verts[0].co.z - e.verts[1].co.z) > 1 * MM], cuts=2)
    # puffed, slightly lopsided dough
    for v in bm.verts:
        r = math.hypot(v.co.x, v.co.y)
        top = v.co.z / H
        v.co.z += (fbm((v.co.x * 220, v.co.y * 220, 0), 2, i) * 0.9 * MM) * top
        k = 1 + 0.08 * math.sin(math.pi * top) + 0.05 * fbm((v.co.x * 160, v.co.y * 160, v.co.z * 160), 2, i)
        v.co.x *= k
        v.co.y *= k
    # icing: a soft flat puddle on top
    ic = new_bm()
    blob(ic, (rng.uniform(3.2, 4.4) * MM, rng.uniform(2.4, 3.4) * MM, 1.3 * MM), cuts=3, rounded=0.95)
    for v in ic.verts:
        v.co.z = max(v.co.z, 0) * 1.0 + (0 if v.co.z > 0 else -0.0)
    displace(ic, 0.35 * MM, 160, i * 3)
    ic.transform(Matrix.Rotation(rng.uniform(0, 3), 4, 'Z') @ Matrix.Translation((rng.uniform(-2, 2) * MM, rng.uniform(-2, 2) * MM, H + 0.1 * MM)))
    me = bpy.data.meshes.new("ic")
    ic.to_mesh(me)
    ic.free()
    n_dough = len(bm.verts)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    icing_ids = set(range(n_dough, len(bm.verts)))
    dough_top, dough_side, dough_in, cin, white = lin("#b8732f"), lin("#d89a52"), lin("#e9c58b"), lin("#5a230f"), lin("#f7f1e4")
    vid = {v.index: v for v in bm.verts}

    def col(co, n, f):
        if all(l.vert.index in icing_ids for l in f.loops):
            return (mix(white, lin("#efe4cc"), 0.5 + 0.5 * fbm((co.x * 300, co.y * 300, 0), 2, i)), 0.22)
        r = math.hypot(co.x, co.y)
        ang = math.atan2(co.y, co.x) % math.tau
        # which band of the spiral is this? distance past the spiral's radius at the same angle
        base = rad(ang) if rad(ang) <= r else None
        best = 1e9
        for t in range(0, int(turns) + 2):
            best = min(best, abs(r - (rad(ang + t * math.tau) + 2.6 * MM)))
        is_fill = best < 0.35 * MM
        if n.z > 0.5:
            c = mix(dough_top, dough_side, 0.5 + 0.5 * fbm((co.x * 260, co.y * 260, 0), 2, i))
            if is_fill:
                c = cin
            return (c, 0.62)
        if is_fill:
            return (cin, 0.7)
        return (mix(dough_in, dough_side, 0.5 + 0.5 * co.z / H), 0.7)
    return finish(f"cinnamon_{i}", bm, col)


# ------------------------------------------------------------------ kataifi shreds (golden, crisp, ~14 mm nest)
def kataifi(i):
    rng = random.Random(900 + i)
    bm = new_bm()
    R = 0.28 * MM
    for k in range(30):
        # a wavy strand: a random walk that curls, as the baked vermicelli of phyllo does
        p = Vector((rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(-2.5, 2.5))) * MM
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-.6, .6))).normalized()
        pts = []
        for s in range(26):
            pts.append(p.copy())
            d = (d + Vector((rng.uniform(-.55, .55), rng.uniform(-.55, .55), rng.uniform(-.4, .4)))).normalized()
            p += d * 0.55 * MM
            # keep the nest compact
            p -= p * 0.04
        # sweep a small hexagon along the strand
        rings = []
        for s, q in enumerate(pts):
            t = (pts[min(s + 1, len(pts) - 1)] - pts[max(s - 1, 0)]).normalized()
            a = t.cross(Vector((0, 0, 1)))
            if a.length < 1e-3:
                a = t.cross(Vector((1, 0, 0)))
            a.normalize()
            b = t.cross(a)
            rings.append([bm.verts.new(q + (a * math.cos(w) + b * math.sin(w)) * R) for w in [m * math.tau / 5 for m in range(5)]])
        for s in range(len(rings) - 1):
            for m in range(5):
                bm.faces.new((rings[s][m], rings[s][(m + 1) % 5], rings[s + 1][(m + 1) % 5], rings[s + 1][m]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    a, b = lin("#e7b55a"), lin("#9b5f1a")

    def col(co, n, f):
        t = 0.5 + 0.5 * fbm((co.x * 500, co.y * 500, co.z * 500), 2, i)
        return (mix(b, a, t), 0.5)
    return finish(f"kataifi_{i}", bm, col)


# ------------------------------------------------------------------ pistachio crumb (~3.5 mm) and cookie crumb (~9 mm)
def pistachio(i):
    rng = random.Random(1000 + i)
    bm = new_bm()
    blob(bm, (rng.uniform(1.4, 2.0) * MM, rng.uniform(1.0, 1.4) * MM, rng.uniform(0.9, 1.3) * MM), cuts=1, rounded=0.5)
    for v in bm.verts:
        v.co += Vector((rng.uniform(-.3, .3), rng.uniform(-.3, .3), rng.uniform(-.3, .3))) * MM
    g, p, y = lin("#6c8a2a"), lin("#a7c256"), lin("#d9e195")

    def col(co, n, f):
        t = 0.5 + 0.5 * noise.noise(Vector(co) * 1200)
        return (mix(mix(g, p, t), y, 0.25 * (1 if n.z > 0.5 else 0)), 0.55)
    return finish(f"pistachio_{i}", bm, col, smooth=False)


def biscoff(i):
    rng = random.Random(1100 + i)
    bm = new_bm()
    w, d, h = rng.uniform(3.2, 5.0) * MM, rng.uniform(2.6, 4.2) * MM, rng.uniform(0.9, 1.4) * MM
    blob(bm, (w, d, h), cuts=2, rounded=0.15)
    for v in bm.verts:                                         # shards: snapped, angular outline
        v.co.x += rng.uniform(-.45, .45) * MM * (1 if abs(v.co.x) > w * .8 else 0.2)
        v.co.y += rng.uniform(-.45, .45) * MM * (1 if abs(v.co.y) > d * .8 else 0.2)
    displace(bm, 0.18 * MM, 380, i * 2.7, oct=2)
    top, edge, lite = lin("#a36528"), lin("#7a431a"), lin("#d9a05a")

    def col(co, n, f):
        t = 0.5 + 0.5 * fbm((co.x * 600, co.y * 600, co.z * 600), 3, i)
        c = mix(edge, top, t)
        if abs(n.z) < 0.6:
            c = mix(c, lite, 0.55)                              # the snapped edge shows the pale inside
        return (c, 0.8)
    return finish(f"biscoff_{i}", bm, col, smooth=False)


# ------------------------------------------------------------------ nonpareil (a ~2 mm ball; the page tints each one)
def nonpareil():
    bm = new_bm()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=1.0 * MM)
    return finish("nonpareil_0", bm, lambda co, n, f: ([1.0, 1.0, 1.0], 0.35))


BUILD = {strawberry: 3, mango: 3, date: 3, fig: 3, granola: 4, chip: 2, brownie: 3, rainbow: 3, cinnamon: 3,
         kataifi: 3, pistachio: 2, biscoff: 4}
for fn, n in BUILD.items():
    for i in range(n):
        fn(i)
nonpareil()

# lay them out on a grid for the contact sheet; the GLB keeps each piece at its own origin
names = sorted(objs)
if SHEET:
    cols = 8
    for k, nm in enumerate(names):
        objs[nm].location = ((k % cols) * 0.022, -(k // cols) * 0.022, 0)
else:
    pass

bpy.ops.object.select_all(action='SELECT')
if not SHEET:
    for ob in objs.values():
        ob.location = (0, 0, 0)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "toppings.glb"), export_format='GLB', export_apply=True,
                              export_vertex_color='ACTIVE', export_yup=True, export_texcoords=False,
                              export_normals=True, export_materials='EXPORT')
    print("exported", len(objs), "pieces ->", os.path.join(OUT, "toppings.glb"))
else:
    rows = (len(names) + cols - 1) // cols
    cx, cy = (cols - 1) * 0.011, -(rows - 1) * 0.011
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = cols * 0.0215
    tilt = math.radians(52)
    cam.location = (cx, cy - 0.3 * math.sin(tilt), 0.3 * math.cos(tilt))
    cam.rotation_euler = (tilt, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # a tilted key so the relief reads
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(35), math.radians(-25), 0)
    scene.collection.objects.link(sun)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.88, 0.84, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    scene.world = w
    # the principled material, reading the painted colour
    nt = MAT.node_tree
    pb = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vc.outputs["Color"], pb.inputs["Base Color"])
    nt.links.new(vc.outputs["Alpha"], pb.inputs["Roughness"])
    bg = bpy.data.objects.new("plane", bpy.data.meshes.new("plane"))
    scene.collection.objects.link(bg)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 40
    scene.cycles.device = 'CPU'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = int(1800 * rows / cols * 0.78) + 40
    scene.render.filepath = os.path.join(OUT, "sheet.png")
    bpy.ops.render.render(write_still=True)
    print("sheet", scene.render.filepath, names)

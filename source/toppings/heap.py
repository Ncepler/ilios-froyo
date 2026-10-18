"""Heaps of toppings, settled by Blender's rigid body physics (bpy), exported as instance transforms.

The bowl is the page's bowl (the same profile as bowlGeometry in site/bar.js); the pieces are the modelled pieces,
dropped in as convex bodies and left to settle, so what you see in a bowl is what a heap really looks like: pieces
resting on each other and the glass-smooth bowl, leaning, overlapping, with the flat ones lying flat.

    simulate(bowl_kind, variants, weights, fill, seed) -> dict(instances=[...], top=y)

Coordinates out are the page's (three.js: Y up), origin at the bowl's centre on the counter.
"""
import math

import bpy  # noqa: I001  (bmesh only exists once bpy has been imported)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

# Blender is Z up, three.js Y up: p_three = M p_blender
M = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float)
Minv = M.T

BOWLS = {
    # R (rim radius), H (height), base radius, profile exponent: the page's bowlGeometry
    'organic': dict(R=0.102, H=0.070, base=0.060, p=1.2),
    'hobnail': dict(R=0.095, H=0.085, base=0.055, p=0.8),
}


def bowl_inner(kind, n=22):
    b = BOWLS[kind]
    pts = []
    for i in range(n + 1):
        t = i / n
        r = b['base'] + (b['R'] - b['base']) * math.sin(t * math.pi / 2) ** b['p'] - 0.006
        y = t * b['H'] + 0.006 * (1 - t) + (0.006 if i == 0 else 0)
        pts.append((max(r, 0.0), max(y, pts[-1][1]) if pts else y))     # (the page's first inner point sits 6 mm high)
    return pts, b['H']


def wall_radius(kind, y):
    pts, _ = bowl_inner(kind)
    return float(np.interp(y, [p[1] for p in pts], [p[0] for p in pts]))


def _clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def _bowl_object(kind, y_c, y_e):
    """the bowl's inner wall with a domed fill inside it: the dome's centre is at y_c, where it meets the wall at y_e.
    Only the top layer of a heap is ever seen, so only that layer is simulated, resting on the dome."""
    pts, H = bowl_inner(kind)
    # radius of the wall at height y
    ys = np.array([p[1] for p in pts])
    rs = np.array([p[0] for p in pts])
    r_w = float(np.interp(y_e, ys, rs))
    prof = []
    nd = 14
    for i in range(nd + 1):
        u = i / nd
        prof.append((r_w * u, y_c + (y_e - y_c) * u ** 1.15))
    for (r, y) in pts:
        if y > y_e + 1e-6:
            prof.append((r, y))
    prof.append((pts[-1][0] + 0.004, pts[-1][1] + 0.10))       # a lip above the rim so nothing escapes while it settles
    bm = bmesh.new()
    seg = 56
    rings = [[bm.verts.new((r * math.cos(a), r * math.sin(a), y)) for a in [k * math.tau / seg for k in range(seg)]] for (r, y) in prof]
    for j in range(len(rings) - 1):
        for k in range(seg):
            bm.faces.new((rings[j][k], rings[j][(k + 1) % seg], rings[j + 1][(k + 1) % seg], rings[j + 1][k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('bowl')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('bowl', me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.rigidbody.object_add()
    ob.rigid_body.type = 'PASSIVE'
    ob.rigid_body.collision_shape = 'MESH'
    ob.rigid_body.friction = 1.0
    ob.rigid_body.collision_margin = 0.0003
    return ob


def hull_mesh(V, maxv=48):
    """the convex hull of a piece, thinned to about maxv points (a collision shape does not need 3000)"""
    from scipy.spatial import ConvexHull
    h = ConvexHull(V.astype(np.float64))
    pts = V[h.vertices].astype(np.float64)
    if len(pts) > maxv:
        keep = [int(np.argmax(np.linalg.norm(pts - pts.mean(0), axis=1)))]
        dmin = np.linalg.norm(pts - pts[keep[0]], axis=1)
        while len(keep) < maxv:
            k = int(np.argmax(dmin))
            keep.append(k)
            dmin = np.minimum(dmin, np.linalg.norm(pts - pts[k], axis=1))
        pts = pts[keep]
    h2 = ConvexHull(pts)
    return pts, h2.simplices


def _piece_object(name, V, F):
    """V in the page's frame (Y up), centred; the object lives in Blender's (Z up). Its mesh is the piece's hull."""
    V, F = hull_mesh(V)
    Vb = V @ Minv.T
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in Vb], [], [tuple(int(i) for i in f) for f in F])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def simulate(kind, variants, weights, n, y_c, y_e, seed=0, wave=48, frames=34):
    """Drop n pieces in waves of `wave`, each wave onto the settled ones before it (so none falls more than a few cm).
    variants: list of dict(V, F, r, vol); returns [(variant, pos(3), quat xyzw)] in three's frame."""
    rng = np.random.default_rng(seed)
    choice = rng.choice(len(variants), size=n, p=np.asarray(weights) / np.sum(weights))
    rads = np.array([variants[vi]['r'] for vi in choice])
    R_drop = BOWLS[kind]['R'] * 0.72
    state = []                                       # (variant, 4x4 matrix in Blender's frame) of the pieces so far
    sc = bpy.context.scene
    for w0 in range(0, n, wave):
        _clear()
        if sc.rigidbody_world is not None:
            bpy.ops.rigidbody.world_remove()
        bpy.ops.rigidbody.world_add()
        rw = sc.rigidbody_world
        rw.substeps_per_frame = 10
        rw.solver_iterations = 24
        sc.render.fps = 60
        sc.frame_start = 1
        sc.frame_end = frames
        _bowl_object(kind, y_c, y_e)
        base = [_piece_object(f'v{i}', v['V'], v['F']) for i, v in enumerate(variants)]
        objs = []
        placed = []
        for vi, m in state:
            ob = bpy.data.objects.new(f'p{len(objs)}', base[vi].data)
            sc.collection.objects.link(ob)
            ob.matrix_world = Matrix(m.tolist())
            objs.append((ob, vi))
            placed.append((m[:3, 3].copy(), variants[vi]['r']))
        zmax = max([c[2] + r for c, r in placed] or [y_c]) + 0.006
        new = range(w0, min(n, w0 + wave))
        vol = sum(4 / 3 * math.pi * rads[k] ** 3 for k in new)
        height = max(0.03, vol / (0.22 * math.pi * R_drop ** 2))
        for k in new:
            r_i = rads[k]
            vi = int(choice[k])
            for tries in range(500):
                if tries and tries % 120 == 0:
                    height *= 1.3
                a_ = rng.uniform(0, math.tau)
                d_ = math.sqrt(rng.uniform(0, 1)) * R_drop
                c = np.array([d_ * math.cos(a_), d_ * math.sin(a_), zmax + r_i + rng.uniform(0, height)])
                if all(np.linalg.norm(c - q) >= (r_i + rr) * 0.98 for q, rr in placed):
                    break
            placed.append((c, r_i))
            ob = bpy.data.objects.new(f'p{len(objs)}', base[vi].data)
            sc.collection.objects.link(ob)
            ob.location = tuple(c)
            ob.rotation_euler = tuple(rng.uniform(0, math.tau, 3))
            objs.append((ob, vi))
        for ob in base:
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.ops.object.select_all(action='DESELECT')
        n_old = len(state)
        for oi, (ob, vi) in enumerate(objs):
            bpy.context.view_layer.objects.active = ob
            ob.select_set(True)
            bpy.ops.rigidbody.object_add()
            rb = ob.rigid_body
            # what settled in earlier waves stays put (a passive body costs nothing to simulate)
            rb.type = 'PASSIVE' if oi < n_old else 'ACTIVE'
            rb.collision_shape = 'CONVEX_HULL'
            rb.mass = max(0.0003, variants[vi]['vol'] * 1050.0)
            rb.friction = 0.95
            rb.restitution = 0.02
            rb.linear_damping = 0.45
            rb.angular_damping = 0.6
            rb.collision_margin = 0.0002
            ob.select_set(False)
        for f in range(1, frames + 1):
            sc.frame_set(f)
        state = [(vi, np.array(ob.matrix_world)) for ob, vi in objs]
        print(f'  wave {w0 // wave + 1}: {len(state)} pieces', flush=True)
    out = []
    for vi, mw in state:
        Rb = mw[:3, :3] / np.cbrt(abs(np.linalg.det(mw[:3, :3])))
        out.append((int(vi), M @ mw[:3, 3], _quat(M @ Rb @ Minv)))
    return out


def _quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def finish(kind, instances, variants, y_c=None, y_e=None, top_cull=True):
    """work out each piece's occlusion, drop the ones that are buried, and measure the heap: its top, and how much of the
    bowl's surface the pieces cover (so the caller can add pieces until there are no bare patches)"""
    H = BOWLS[kind]['H']
    P = np.array([i[1] for i in instances])
    r = np.array([variants[i[0]]['r'] for i in instances])
    n = len(P)
    # rays up the hemisphere; a piece is a sphere of 0.85 r for the test
    rng = np.random.default_rng(3)
    dirs = rng.normal(size=(24, 3))
    dirs[:, 1] = np.abs(dirs[:, 1]) * 0.9 + 0.25
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    open_frac = np.zeros(n)
    for a in range(n):
        d = P - P[a]
        dist = np.linalg.norm(d, axis=1)
        near = (dist > 1e-6) & (dist < 6 * r.max()) & (np.arange(n) != a)
        if not near.any():
            open_frac[a] = 1
            continue
        dn = d[near]
        rn = 0.85 * r[near]
        t = dirs @ dn.T
        miss = np.sqrt(np.maximum(np.einsum('ij,ij->i', dn, dn)[None, :] - t * t, 0))
        hit = (t > 0) & (miss < rn[None, :])
        open_frac[a] = 1 - hit.any(1).mean()
    ao = 0.4 + 0.6 * np.clip(open_frac * 1.15, 0, 1)
    # the heap's height field: the highest piece top in each 6 mm cell within the bowl
    cell = 0.006
    Rw = wall_radius(kind, y_e if y_e is not None else H * 0.7)
    gx = np.arange(-Rw, Rw + cell, cell)
    tops = []
    cov_cells = 0
    cells = 0
    for cx in gx:
        for cz in gx:
            rr = math.hypot(cx, cz)
            if rr > Rw * 0.78:
                continue
            m = (np.abs(P[:, 0] - cx) < r * 0.9 + cell / 2) & (np.abs(P[:, 2] - cz) < r * 0.9 + cell / 2)
            top = float(np.max(P[m, 1] + r[m] * 0.6)) if m.any() else -1.0
            tops.append(top)
            cells += 1
            floor = (y_c + (y_e - y_c) * (rr / max(Rw, 1e-6)) ** 1.15) if y_c is not None else 0.0
            if top > floor + 0.0045:
                cov_cells += 1
    tops = np.array(tops)
    mean_top = float(np.mean(np.maximum(tops, 0)))
    cover = cov_cells / max(cells, 1)
    top = float(np.percentile(P[:, 1] + r * 0.6, 97))
    keep = open_frac > 0.0
    res = []
    for k, (vi, p, q) in enumerate(instances):
        if top_cull and not keep[k]:
            continue
        res.append([vi, *[round(float(x), 5) for x in p], *[round(float(x), 4) for x in q], round(float(ao[k]), 3)])
    return res, dict(top=top, mean_top=mean_top, cover=cover)

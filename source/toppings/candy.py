"""Candy: gummy bears, M&M's, chocolate chips and chunks, sour strips, gummy worms, sprinkles, flaky salt."""
import math

import numpy as np

from lib import (MM, fbm, face_normals, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_cyl, sd_ellipsoid,  # noqa: F401
                 sd_plane, sd_sphere, sdf_ao, smax, smin, smoothstep, vertex_normals, vnoise, worley)


# ------------------------------------------------------------------ helpers shared by the candies
def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def thickness(f, V, N, step=0.35 * MM, n=40):
    """how far one has to go inward from each surface point to get out of the solid again (a local thickness: it is
    what makes a gummy glow at its thin ears and fingers and go deep where it is fat)"""
    t = np.full(len(V), n * step)
    done = np.zeros(len(V), bool)
    for k in range(1, n):
        d = k * step
        out = (f(V - N * d) > 0) & ~done
        t[out] = d - 0.5 * step
        done |= out
    return t


def finish(name, V, F, N, rgb, rough, sss, spec, ao, cls, flat=False, jelly=False):
    """pack a hand-made mesh like lib.piece does: centred on its bounding box, wound to agree with its normals"""
    V = np.asarray(V, dtype=float)
    F = np.asarray(F, dtype=np.int64)
    lo_v, hi_v = V.min(0), V.max(0)
    Vc = V - (lo_v + hi_v) / 2
    fn = face_normals(V, F)
    fc = N[F].mean(1)
    if (np.einsum('ij,ij->i', fn, fc) < 0).mean() > 0.5:
        F = F[:, ::-1].copy()
    n = len(V)
    rough = np.broadcast_to(np.asarray(rough, dtype=float), (n,))
    sss = np.broadcast_to(np.asarray(sss, dtype=float), (n,))
    spec = np.broadcast_to(np.asarray(spec, dtype=float), (n,))
    ao = np.broadcast_to(np.asarray(ao, dtype=float), (n,))
    return dict(name=name, V=Vc.astype(np.float32), N=N.astype(np.float32), F=F.astype(np.uint32),
                COLOR_0=np.concatenate([rgb, rough[:, None]], 1).astype(np.float32),
                _DATA=np.stack([ao, sss, spec], 1).astype(np.float32),
                extras=dict(cls=cls, flat=bool(flat), jelly=bool(jelly), r=float(np.linalg.norm(Vc, axis=-1).max()),
                            size=[float(x) for x in (hi_v - lo_v)]))


# ------------------------------------------------------------------ gummy bears
BEAR_COLOURS = ['#d4141c', '#f27a10', '#f6d012', '#5ab52a', '#ef5d92', '#f2efe6', '#d4141c', '#5ab52a']


def gummy_bear(i):
    rng = np.random.default_rng(3000 + i)
    S = rng.uniform(0.92, 1.08)                    # 15 .. 19 mm tall
    hexc = BEAR_COLOURS[i % len(BEAR_COLOURS)]
    base = lin(hexc)
    clear = hexc == '#f2efe6'
    # pose: arm angles (0 hangs, 1.57 out sideways, 2.6 up), leg spread and kick, head turned and tipped
    arm_a = [rng.uniform(0.5, 1.5), rng.uniform(0.5, 1.5)]
    if i % 4 == 1:
        arm_a[1] = rng.uniform(2.1, 2.6)            # waving
    if i % 4 == 3:
        arm_a = [rng.uniform(1.8, 2.5), rng.uniform(1.8, 2.5)]   # both up
    arm_f = [rng.uniform(0.15, 0.7), rng.uniform(0.15, 0.7)]
    leg_a = [rng.uniform(0.12, 0.5), rng.uniform(0.12, 0.5)]
    leg_f = [rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9)]
    head_R = rot_matrix(rng.uniform(-0.12, 0.2), rng.uniform(-0.35, 0.35), rng.uniform(-0.2, 0.2))
    lean = rot_matrix(rng.uniform(-0.1, 0.1), 0, rng.uniform(-0.12, 0.12))
    belly = rng.uniform(0.9, 1.1)
    N0 = np.array([0, 2.7, 0.2])                    # the neck
    Ch = np.array([0, 5.4, 0.55])                   # the head's centre
    sx = np.array([-1, 1])

    def limb(side, sh, ang, fwd, L, r):
        d = unit([side * math.sin(ang), -math.cos(ang), fwd])
        return np.array(sh), np.array(sh) + d * L, r

    arms = [limb(s, (s * 3.3, 2.5, 0.0), arm_a[k], arm_f[k], 3.5, 1.3) for k, s in enumerate(sx)]
    legs = [limb(s, (s * 2.3, -3.2, 0.0), leg_a[k], leg_f[k], 2.9, 1.95) for k, s in enumerate(sx)]
    eyes_l = [np.array([s * 1.35, 0.75, 0.0]) for s in sx]
    for e in eyes_l:                                 # put the eyes on the head's surface (local frame)
        e[2] = 3.3 * math.sqrt(max(0.05, 1 - (e[0] / 3.7) ** 2 - (e[1] / 3.3) ** 2)) - 0.05
    nose_l = np.array([0.0, -0.45, 4.35])

    def to_world(q):
        return N0 + head_R @ ((Ch - N0) + q)

    def bear(P):
        P = (P / MM / S) @ lean                      # work in mm of the unit bear; lean tilts the whole thing
        body = smin(sd_ellipsoid(P, (0, -0.4, 0), (4.3, 4.8, 3.4)), sd_ellipsoid(P, (0, -2.3, 0.2), (4.5, 3.4, 3.6)), 2.2)
        body = smin(body, sd_ellipsoid(P, (0, -0.8, 2.3 * belly), (3.0, 3.6, 1.7)), 2.0)
        q = ((P - N0) @ head_R) - (Ch - N0)
        head = sd_ellipsoid(q, (0, 0, 0), (3.7, 3.3, 3.3))
        for s in sx:
            head = smin(head, sd_ellipsoid(q, (s * 2.75, 2.75, -0.3), (1.45, 1.45, 1.0)), 1.1)
        head = smin(head, sd_ellipsoid(q, (0, -0.95, 3.0), (1.95, 1.45, 1.45)), 0.9)
        d = smin(body, head, 1.8)
        for a, b, r in arms:
            d = smin(d, sd_capsule(P, a, b, r), 1.5)
            d = smin(d, sd_sphere(P, b, r * 1.12), 1.0)
        for a, b, r in legs:
            d = smin(d, sd_capsule(P, a, b, r), 1.5)
            d = smin(d, sd_ellipsoid(P, b + np.array([0, -0.45, 0.8]), (r * 1.0, 1.3, 2.1)), 1.2)
        d = smax(d, sd_plane(P, [0, 0, -1], 2.65), 1.4)         # the flat back of a starch-moulded bear
        d = d + 0.04 * fbm(P / 2.0, 2, i)                      # not machined
        return d * MM * S

    lo = np.array([-8.5, -9.5, -4.5]) * MM * S
    hi = np.array([8.5, 10.5, 7.2]) * MM * S
    deep = base * (0.93 if clear else {'#ef5d92': 0.9, '#f6d012': 0.86, '#f27a10': 0.8, '#5ab52a': 0.78}.get(hexc, 0.74))
    glow = np.minimum(mix(base, np.array([1.0, 0.85, 0.6]), 0.22) * (1.18 if not clear else 1.04), 1.0)

    def paint(V, N, field):
        t = thickness(field, V, N) / MM / S
        Pm = (V / MM / S) @ lean
        k = smoothstep(2.2, 7.5, t)
        col = mix(glow, deep, k)
        # the shade deepens a little towards the middle of the back, light pools in the thin ears and fingers
        # face: two eyes and the nose are small dark dimples, the mouth a short line under the snout
        face = np.zeros(len(V))
        for e in eyes_l:
            wp = to_world(e)
            face = np.maximum(face, smoothstep(0.8, 0.45, np.linalg.norm(Pm - wp, axis=1)))
        nw = to_world(nose_l)
        face = np.maximum(face, smoothstep(0.85, 0.4, np.linalg.norm((Pm - nw) * [1.0, 1.4, 1.0], axis=1)))
        mw = to_world(np.array([0, -1.85, 3.6]))
        mouth = smoothstep(0.32, 0.12, np.abs(np.linalg.norm((Pm - mw) * [0.7, 1.0, 1.0], axis=1) - 0.9)) * (Pm[:, 1] < mw[1] + 0.1) * (Pm[:, 2] > 1.5)
        face = np.maximum(face, mouth * 0.7)
        col = mix(col, deep * 0.32, face * 0.85)
        # tiny trapped bubbles and a faint sugar bloom
        f1, f2, cid = worley(Pm / 2.2, 11 + i)
        bub = smoothstep(0.1, 0.05, f1) * (cid > 0.8) * (t > 3.5)
        col = mix(col, glow * 1.25, bub * 0.6)
        rough = 0.1 + 0.025 * fbm(V / (3 * MM), 2, 5 + i) - 0.02 * face
        return col, rough, np.full(len(V), 0.96), np.ones(len(V))

    voxel = fit_voxel(bear, lo, hi, 0.72 * MM, 3350)
    return piece(f'gummies_{i}', bear, lo, hi, voxel, paint, smooth=2, cls='jelly', jelly=True, ao_strength=0.7)



# ------------------------------------------------------------------ shared: meshing helpers
def fit_voxel(f, lo, hi, v0, max_tris, grow=1.04, pad=2):
    """the finest voxel (from v0 up) at which the solid meshes to no more than max_tris triangles"""
    from lib import mesh_sdf
    v = v0
    for _ in range(40):
        _, F = mesh_sdf(f, lo, hi, v, pad)
        if len(F) <= max_tris:
            return v
        v *= grow
    return v


def sd_roundcone(P, a, b, r1, r2):
    """a capsule whose two ends have different radii (iq's exact round cone); P (n,3)"""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    w = pa * l2 - ba[None, :] * y[:, None]
    x2 = np.einsum('ij,ij->i', w, w)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


def project_to_surface(f, V, iters=2, eps=0.15 * MM):
    """slide vertices onto f = 0 along the field's gradient"""
    from lib import grad
    V = V.copy()
    for _ in range(iters):
        g = grad(f, V, eps)
        gn = np.einsum('ij,ij->i', g, g)
        V = V - (f(V) / np.maximum(gn, 1e-9))[:, None] * g
    return V


def refine_faces(V, F, mark, f=None):
    """one round of conforming midpoint subdivision of the faces whose centroid satisfies mark(c) -> bool (n,).
    Neighbours are split just enough to leave no cracks; new vertices are slid back onto the surface f = 0."""
    V = np.asarray(V, dtype=float)
    F = np.asarray(F, dtype=np.int64)
    nV = len(V)
    sel = mark(V[F].mean(1))
    ek = lambda a, b: (min(a, b), max(a, b))
    split = set()
    for fi in np.where(sel)[0]:
        a, b, c = F[fi]
        split.update([ek(a, b), ek(b, c), ek(c, a)])
    changed = True
    while changed:
        changed = False
        for a, b, c in F:
            es = [ek(a, b), ek(b, c), ek(c, a)]
            ns = sum(e in split for e in es)
            if ns == 2:
                split.update(es)
                changed = True
    mid = {}
    newV = []
    for e in sorted(split):
        mid[e] = nV + len(newV)
        newV.append((V[e[0]] + V[e[1]]) / 2)
    out = []
    for a, b, c in F:
        eab, ebc, eca = ek(a, b), ek(b, c), ek(c, a)
        sab, sbc, sca = eab in split, ebc in split, eca in split
        n = sab + sbc + sca
        if n == 0:
            out.append((a, b, c))
        elif n == 3:
            ab, bc, ca = mid[eab], mid[ebc], mid[eca]
            out += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        else:   # exactly one
            if sab:
                m = mid[eab]
                out += [(a, m, c), (m, b, c)]
            elif sbc:
                m = mid[ebc]
                out += [(b, m, a), (m, c, a)]
            else:
                m = mid[eca]
                out += [(c, m, b), (m, a, b)]
    V2 = np.vstack([V, np.array(newV)]) if newV else V
    if f is not None and newV:
        V2[nV:] = project_to_surface(f, V2[nV:], 2)
    return V2, np.array(out, dtype=np.int64)


def field_mesh(f, lo, hi, voxel, smooth=2):
    """marching cubes + Taubin smoothing, then back onto the surface"""
    from lib import mesh_sdf, smooth_mesh
    V, F = mesh_sdf(f, lo, hi, voxel)
    if smooth:
        V = smooth_mesh(V, F, smooth)
    return project_to_surface(f, V, 2, voxel * 0.3), F


def field_normals(f, V, F, eps):
    from lib import grad
    G = grad(f, V, eps)
    N = G / np.maximum(np.linalg.norm(G, axis=-1, keepdims=True), 1e-9)
    bad = np.linalg.norm(G, axis=-1) < 0.2
    if bad.any():
        N[bad] = vertex_normals(V, F)[bad]
    return N


# ------------------------------------------------------------------ M&M's
MM_COLOURS = ['#c8102e', '#f26a1b', '#fcd116', '#4fae31', '#1766c2', '#4f2a17', '#c8102e', '#1766c2']


def _m_glyph(u, v, w=0.62):
    """distance to a lowercase 'm' (a stroke centreline, mm): three stems and two arches"""
    segs = [((-1.95, -1.65), (-1.95, 1.7)), ((0, -1.65), (0, 0.8)), ((1.95, -1.65), (1.95, 0.8))]
    for cx in (-0.975, 0.975):
        th = np.linspace(math.pi, 0, 15)
        pts = np.stack([cx + 0.975 * np.cos(th), 0.8 + 0.9 * np.sin(th)], 1)
        segs += [(tuple(pts[k]), tuple(pts[k + 1])) for k in range(len(pts) - 1)]
    d = np.full(u.shape, 9.0)
    for (ax, ay), (bx, by) in segs:
        px, py = u - ax, v - ay
        bx_, by_ = bx - ax, by - ay
        h = np.clip((px * bx_ + py * by_) / (bx_ * bx_ + by_ * by_), 0, 1)
        d = np.minimum(d, np.hypot(px - h * bx_, py - h * by_))
    return d - w / 2


def mm_candy(i):
    rng = np.random.default_rng(4000 + i)
    hexc = MM_COLOURS[i % len(MM_COLOURS)]
    base = lin(hexc)
    R = rng.uniform(6.3, 6.75)                     # 12.6 .. 13.5 mm across
    h = rng.uniform(3.25, 3.7)                     # 6.5 .. 7.4 mm thick
    ell = rng.uniform(0.96, 1.03)
    rc = h - rng.uniform(0.9, 1.3)
    dome = rng.uniform(0.25, 0.55)
    dome2 = rng.uniform(0.05, 0.3)                 # the underside is flatter
    tilt = rng.uniform(-0.05, 0.05, 2)
    printed_up = True
    # a chip off the rim in two of them, showing the chocolate
    chip = None
    if i in (2, 6):
        ang = rng.uniform(0, math.tau)
        chip = np.array([math.cos(ang) * (R - 0.2), rng.uniform(-0.8, 0.8), math.sin(ang) * (R - 0.2)]), rng.uniform(0.85, 1.15)
    glyph_ang = rng.uniform(0, math.tau)
    glyph_off = rng.uniform(-0.35, 0.35, 2)
    ink = lin('#f6f3ea')
    choc = lin('#4a2918')

    def field_mm(P):
        Q = P / MM
        Q = Q @ rot_matrix(tilt[0], 0, tilt[1])
        rr = np.hypot(Q[:, 0] * ell, Q[:, 2])
        ay = np.abs(Q[:, 1]) - np.where(Q[:, 1] > 0, dome, dome2) * np.clip(1 - (rr / R) ** 2, 0, 1)
        qx, qy = rr - (R - rc), ay - (h - rc)
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rc
        if chip is not None:
            d = smax(d, -(np.linalg.norm(Q - chip[0], axis=1) - chip[1] * 1.5), 0.25)
        return d * MM

    lo, hi = np.array([-R - 0.5, -h - 1, -R - 0.5]) * MM, np.array([R + 0.5, h + 1, R + 0.5]) * MM
    voxel = 1.5 * MM
    V, F = field_mesh(field_mm, lo, hi, voxel, smooth=1)
    ca, sa = math.cos(glyph_ang), math.sin(glyph_ang)

    def glyph_xy(Q):
        gu0, gv0 = Q[:, 0] - glyph_off[0], -Q[:, 2] - glyph_off[1]
        return gu0 * ca + gv0 * sa, -gu0 * sa + gv0 * ca

    def near_print(reach):
        def mark(c):
            Qc = c / MM
            gu, gv = glyph_xy(Qc)
            return (Qc[:, 1] > h * 0.55) & (_m_glyph(gu, gv) < reach)
        return mark

    f_loc = lambda P: field_mm(P)
    for reach in (1.1, 0.62):
        V, F = refine_faces(V, F, near_print(reach), f_loc)
    N = field_normals(field_mm, V, F, 0.12 * MM)
    ao = sdf_ao(field_mm, V, N, 0.9 * MM, 0.8)
    Q = V / MM
    gu, gv = glyph_xy(Q)
    on_top = smoothstep(h * 0.45, h * 0.75, Q[:, 1])
    gd = _m_glyph(gu, gv)
    inkm = smoothstep(0.17, -0.12, gd) * on_top * (np.hypot(gu, gv) < 3.6)
    # shell: a flat, rich colour, hardly mottled; slightly lighter and glossier where the dome curves
    mott = 0.045 * fbm(Q / 2.6, 2, 21 + i) + 0.02 * fbm(Q / 0.9, 2, 31 + i)
    shell = np.clip(base * (1 + mott[:, None] * 3.0), 0, 1)
    col = mix(shell, ink, inkm)
    rough = 0.11 + 0.035 * fbm(Q / 1.3, 2, 41 + i) + 0.18 * inkm
    spec = 1.0 - 0.45 * inkm
    if chip is not None:
        cd = np.linalg.norm(Q - chip[0], axis=1) - chip[1] * 1.5
        cm = smoothstep(0.35, -0.05, cd)
        col = mix(col, choc * (1 + 0.2 * fbm(Q / 0.6, 2, 3))[:, None], cm)
        rough = np.where(cm > 0.5, 0.5, rough)
        spec = np.where(cm > 0.5, 0.45, spec)
    sss = np.full(len(V), 0.12)
    return finish(f'mms_{i}', V, F, N, col, rough, sss, spec, ao, 'candy', flat=True)


# ------------------------------------------------------------------ chocolate chips
def clip_plane(V, F, n, o, snap):
    """cut a star-shaped surface with the half-space n.p <= o by sliding the vertices beyond it onto the plane; faces
    that land flat on the plane and look away from it are dropped, so the cut face is covered exactly once.
    snap (bool per vertex) is set for vertices that now lie on a cut."""
    V = V.copy()
    n = unit(n)
    s = V @ n - o
    out = s > 0
    V[out] -= s[out, None] * n
    snap = snap | out
    fn = face_normals(V, F)
    area = np.linalg.norm(fn, axis=1)
    flat = out[F].all(1)
    keep = ~(flat & ((fn @ n) <= 1e-12 * np.maximum(area, 1e-30))) & (area > 1e-14)
    return V, F[keep], snap


def fill_holes(V, F):
    """close small boundary loops (left where a clip dropped faces) with a fan to the loop's centre"""
    d = {}
    for a, b, c in F:
        for u, v in ((a, b), (b, c), (c, a)):
            d[(u, v)] = d.get((u, v), 0) + 1
    nxt = {}
    for (u, v) in d:
        if (v, u) not in d:
            nxt[u] = v
    V = [tuple(x) for x in V]
    F = [tuple(f) for f in F]
    seen = set()
    for st in list(nxt):
        if st in seen:
            continue
        loop = [st]
        seen.add(st)
        k = nxt.get(st)
        while k is not None and k != st and k not in seen:
            loop.append(k)
            seen.add(k)
            k = nxt.get(k)
        if k != st or len(loop) < 3:
            continue
        c = np.mean([V[j] for j in loop], axis=0)
        V.append(tuple(c))
        ci = len(V) - 1
        for j in range(len(loop)):
            a, b = loop[j], loop[(j + 1) % len(loop)]
            F.append((b, a, ci))
    return np.array(V), np.array(F, dtype=np.int64)


def choc_chip(i):
    rng = np.random.default_rng(5000 + i)
    Rb = rng.uniform(3.95, 4.5)                    # 8 .. 9 mm wide
    H = rng.uniform(5.2, 5.9)                      # 5 .. 6 mm tall
    ellz = rng.uniform(0.9, 0.99)
    lean = rng.uniform(-1.4, 1.4, 2)
    kind = ['whole', 'whole', 'whole', 'split', 'broken'][i % 5]
    nseg = 16
    t_k = np.array([0.0, 0.05, 0.2, 0.38, 0.56, 0.7, 0.82, 0.93])
    rho = np.array([0.90, 0.99, 1.0, 0.84, 0.60, 0.40, 0.23, 0.10]) * (1 + rng.uniform(-0.04, 0.04, 8))
    rho[0] = rho[1] * 0.92
    ph = np.arange(nseg) * math.tau / nseg + rng.uniform(-0.05, 0.05)
    rings = len(t_k)
    V = []
    for j in range(rings):
        t = t_k[j]
        c = np.array([lean[0], 0, lean[1]]) * t ** 2.2
        r = Rb * rho[j]
        for k in range(nseg):
            wob = 1 + 0.045 * math.sin(2 * ph[k] + i) + 0.03 * math.sin(3 * ph[k] + 2 * i)
            V.append([c[0] + r * wob * math.cos(ph[k]), t * H, c[2] + r * wob * ellz * math.sin(ph[k])])
    apex = [lean[0] * 1.0 + 0.45 * math.cos(i), H, lean[1] * 1.0 + 0.45 * math.sin(i)]
    V.append(apex)
    V.append([0, 0, 0])                               # (the base centre)
    V = np.array(V)
    F = []
    for j in range(rings - 1):
        for k in range(nseg):
            a, b = j * nseg + k, j * nseg + (k + 1) % nseg
            c_, d = a + nseg, b + nseg
            F += [(a, c_, b), (b, c_, d)]
    last = (rings - 1) * nseg
    for k in range(nseg):
        F.append((last + k, last + nseg, last + (k + 1) % nseg))
    nb = last + nseg + 1
    for k in range(nseg):
        F.append((nb, k, (k + 1) % nseg))
    F = np.array(F, dtype=np.int64)
    # lumpy, as a depositor's drop is: low noise displacement of the whole thing
    V = V + 0.12 * np.stack([fbm(V / 2.0, 2, 200 + i), fbm(V / 2.0, 2, 210 + i) * 0.5, fbm(V / 2.0, 2, 220 + i)], 1)
    V[:nseg, 1] = np.maximum(V[:nseg, 1], 0.0)
    V[nb, 1] = 0.0
    snap = np.zeros(len(V), bool)
    if kind == 'split':
        n = unit([1, 0.12, rng.uniform(-0.25, 0.25)])
        V, F, snap = clip_plane(V, F, n, rng.uniform(-0.2, 0.3), snap)
        jag = np.abs(fbm(V / 0.9, 2, 230 + i)) * 0.55
        V[snap] -= jag[snap, None] * n
    elif kind == 'broken':
        n1 = unit([rng.uniform(0.25, 0.5), 0.9, rng.uniform(-0.3, 0.3)])
        V, F, snap = clip_plane(V, F, n1, H * rng.uniform(0.5, 0.62) * n1[1] + 0.2, snap)
        n2 = unit([0.9, 0.25, rng.uniform(-0.4, 0.4)])
        V, F, snap2 = clip_plane(V, F, n2, Rb * rng.uniform(0.35, 0.55), snap)
        snap = snap2
        jag = np.abs(fbm(V / 0.8, 2, 240 + i)) * 0.5
        V[snap] -= jag[snap, None] * 0.9 * np.where(V[snap, 1:2] > 0, 1, 1) * unit([0.3, 1, 0.2])
    nV0 = len(V)
    V, F = fill_holes(V, F)
    snap = np.concatenate([snap, np.ones(len(V) - nV0, bool)])
    V = V * MM
    # drop unused vertices
    used = np.unique(F)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used))
    V, F, snap = V[used], remap[F], snap[used]
    N = vertex_normals(V, F)
    Q = V / MM
    # the flat base keeps its own normal
    basev = (Q[:, 1] < 0.12)
    N[basev & (N[:, 1] < -0.2)] = [0, -1, 0]
    ao = np.clip(0.55 + 0.45 * smoothstep(0.0, 1.0, Q[:, 1]) + 0.2 * (N[:, 1] > -0.5), 0.5, 1.0)

    dark, mid, snapc = lin('#2a140b'), lin('#3b1f12'), lin('#5a3320')
    mott = fbm(Q / 2.2, 2, 80 + i)
    col = mix(dark, mid, smoothstep(-0.3, 0.8, mott) * 0.55)
    col = mix(col, lin('#3a2014'), smoothstep(2.0, 5.5, Q[:, 1]) * 0.3)
    sm = np.where(snap, 1.0, 0.0)
    col = mix(col, snapc * (1 + 0.25 * fbm(Q / 0.5, 2, 5))[:, None], sm)
    base_face = (N[:, 1] < -0.6).astype(float)
    col = mix(col, lin('#34190e'), base_face * 0.6)
    rough = 0.15 + 0.06 * fbm(Q / 1.3, 2, 90 + i) + 0.42 * sm + 0.25 * base_face
    spec = 1.0 - 0.5 * sm
    return finish(f'chips_{i}', V, F, N, col, rough, np.full(len(V), 0.06), spec, ao, 'choc')


# ------------------------------------------------------------------ chocolate chunks (milk chocolate bar pieces)
def choc_chunk(i):
    rng = np.random.default_rng(6000 + i)
    a = rng.uniform(11.0, 15.5) / 2                # half sides of the bar piece it was snapped from
    b = rng.uniform(8.5, 13.0) / 2
    hh = rng.uniform(4.0, 5.0) / 2                 # 4 .. 5 mm thick
    rot = rng.uniform(0, math.tau)
    n_snap = [1, 2, 2, 1, 3, 2][i % 6]
    sides = [(1, 0, a), (-1, 0, a), (0, 1, b), (0, -1, b)]
    order = rng.permutation(4)
    snap_ids = set(order[:n_snap].tolist())
    corner = i % 3 == 1                              # a corner snapped off diagonally
    cream = i in (0, 2, 4)
    cream_y = rng.uniform(-0.3, 0.3)
    cream_w = rng.uniform(0.5, 0.8)
    R2 = rot_matrix(0, rot, 0)
    sn = []
    for k, (nx, nz, off) in enumerate(sides):
        ang = rng.uniform(-0.22, 0.22) if k in snap_ids else 0.0
        c, s = math.cos(ang), math.sin(ang)
        n = np.array([nx * c - nz * s, 0, nx * s + nz * c])
        o = off - (rng.uniform(0.0, 0.8) if k in snap_ids else 0.0)
        sn.append((n, o, k in snap_ids, rng.uniform(0, 100)))
    if corner:
        cn = unit([1, 0, 1]) * np.array([1, 0, rng.choice([-1, 1])])
        co = (a + b) * 0.5 * rng.uniform(0.62, 0.8)
        sn.append((unit(cn), co, True, rng.uniform(0, 100)))
    tiltn = unit([rng.uniform(-0.05, 0.05), 1, rng.uniform(-0.05, 0.05)])

    def sides_field(Q):
        sm, ss = np.full(len(Q), -9.0), np.full(len(Q), -9.0)
        for n, o, snap, sd in sn:
            s = Q @ n - o
            if snap:
                # a snapped edge: uneven, in vertical ridges, with a little conchoidal curl
                jag = 0.55 * fbm(np.stack([Q[:, 0] / 1.7 + sd, Q[:, 1] / 2.6, Q[:, 2] / 1.7], 1), 3, int(sd)) \
                    + 0.18 * vnoise(Q / 0.55, int(sd))
                s = s + jag + 0.25 * (Q[:, 1] / hh) ** 2
                ss = np.maximum(ss, s)
            else:
                sm = np.maximum(sm, s)
        return sm, ss

    def field_cube(P):
        Q = (P / MM) @ R2
        sm, ss = sides_field(Q)
        yy = Q @ tiltn
        dy = np.abs(yy) - hh + np.where(yy > 0, 0.36 * smoothstep(0.9, 1.7, -sm), 0.0)     # the moulded panel: a shallow recess inside a frame
        out = np.full(len(Q), -9.0)
        for s, r in ((sm, 0.85), (ss, 0.2)):
            qx, qy = s + r, dy + r
            d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
            out = np.maximum(out, np.where(s > -8, d, -9.0))
        return out * MM

    ext = math.hypot(a, b) + 1.5
    lo, hi = np.array([-ext, -hh - 1, -ext]) * MM, np.array([ext, hh + 1, ext]) * MM
    voxel = fit_voxel(field_cube, lo, hi, 0.6 * MM, 3300)

    milk, snapc, creamc = lin('#5e3724'), lin('#7b4b31'), lin('#efe2c3')

    def paint(V, N, field):
        Q = (V / MM) @ R2
        sm, ss = sides_field(Q)
        dy = np.abs(Q @ tiltn) - hh
        snap = smoothstep(-0.12, 0.12, ss - np.maximum(sm, dy - 0.15)) * (ss > -8)
        top = smoothstep(0.3, 0.8, N[:, 1])
        bot = smoothstep(-0.3, -0.8, N[:, 1])
        base = milk * (1 + 0.14 * fbm(Q / 3.2, 2, 100 + i))[:, None]
        col = mix(base, base * 0.88, bot)
        # moulded rim: a slightly lighter, glossier bevel
        rim = smoothstep(0.9, 0.2, -(dy)) * (1 - snap) * (1 - top * 0.0)
        col = mix(col, base * 1.12, rim * 0.5)
        sc = snapc * (1 + 0.22 * fbm(Q / np.array([0.8, 2.5, 0.8]), 3, 110 + i))[:, None]
        col = mix(col, sc, snap)
        if cream:
            band = smoothstep(cream_w * 0.5 + 0.12, cream_w * 0.5 - 0.1, np.abs(Q[:, 1] - cream_y + 0.18 * fbm(Q / 1.3, 2, 120 + i)))
            col = mix(col, creamc * (1 + 0.05 * fbm(Q / 0.4, 2, 4))[:, None], band * snap)
        rough = 0.17 + 0.05 * fbm(Q / 1.6, 2, 130 + i) + 0.42 * snap + 0.12 * bot
        spec = 1.0 - 0.5 * snap
        sss = np.full(len(V), 0.06)
        return col, rough, sss, spec

    return piece(f'chunks_{i}', field_cube, lo, hi, voxel, paint, smooth=2, cls='choc', flat=True, ao_strength=0.8)



# ------------------------------------------------------------------ swept shapes (worms, belts, sprinkles)
def signed_volume(V, F):
    return float(np.einsum('ij,ij->i', V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)


def orient_outward(V, F):
    return F if signed_volume(V, F) > 0 else F[:, ::-1].copy()


def curve_from_heading(L, alpha, beta, n=600):
    """a space curve of length L (mm) from its heading functions alpha(s) (in the xz plane) and beta(s) (elevation).
    Returns arc length s (n,), points C (n,3), unit tangents T (n,3)"""
    s = np.linspace(0, L, n)
    a, b = alpha(s), beta(s)
    d = np.stack([np.cos(b) * np.cos(a), np.sin(b), np.cos(b) * np.sin(a)], 1)
    C = np.concatenate([[np.zeros(3)], np.cumsum((d[1:] + d[:-1]) / 2 * (s[1] - s[0]), axis=0)])
    C = C - C.mean(0)
    return s, C, d


def frame_along(T, twist=None):
    """width and thickness directions for a strip lying 'flat' (thickness near y) with an optional twist (rad per sample)"""
    up = np.array([0, 1.0, 0])
    W = np.cross(up, T)
    W /= np.linalg.norm(W, axis=1, keepdims=True)
    B = np.cross(T, W)
    if twist is not None:
        c, s_ = np.cos(twist)[:, None], np.sin(twist)[:, None]
        W, B = W * c + B * s_, B * c - W * s_
    return W, B


def sample_curve(s, C, T, sv):
    Cs = np.stack([np.interp(sv, s, C[:, k]) for k in range(3)], 1)
    Ts = np.stack([np.interp(sv, s, T[:, k]) for k in range(3)], 1)
    return Cs, Ts / np.linalg.norm(Ts, axis=1, keepdims=True)


def ring_faces(nu, nphi, base=0):
    F = []
    for j in range(nu - 1):
        for k in range(nphi):
            a = base + j * nphi + k
            b = base + j * nphi + (k + 1) % nphi
            F += [(a, a + nphi, b), (b, a + nphi, b + nphi)]
    return F


def hash_vec(Q, scale, seed):
    """a smooth random vector field at the given feature size (same units as Q)"""
    return np.stack([vnoise(Q / scale, seed), vnoise(Q / scale + 7.7, seed + 1), vnoise(Q / scale + 19.1, seed + 2)], 1)


# ------------------------------------------------------------------ gummy worms
WORM_STYLES = [('#5ab52a', '#f27a10', 'spiral'), ('#d4141c', '#f6d012', 'halves'), ('#ef5d92', '#2c82d8', 'bands'),
               ('#6bc02e', '#f6d012', 'spiral'), ('#f27a10', '#d4141c', 'halves')]


def gummy_worm(i):
    rng = np.random.default_rng(7000 + i)
    L = rng.uniform(38, 48)
    r0 = rng.uniform(3.5, 4.0)
    ca, cb, mode = WORM_STYLES[i % len(WORM_STYLES)]
    colA, colB = lin(ca), lin(cb)
    ph = rng.uniform(0, 6.28, 3)
    turn = [0.0, 2.1, 2.9, 0.6, -2.4][i % 5]                     # overall curl (rad over the length)
    wave = [0.95, 0.35, 0.3, 0.8, 0.3][i % 5]
    waves = [1.0, 1.5, 2.0, 1.5, 2.5][i % 5]
    alpha = lambda t: turn * (t / L) + wave * np.sin(2 * math.pi * waves * t / L + ph[0])
    beta = lambda t: 0.28 * np.sin(2 * math.pi * 1.2 * t / L + ph[1])
    s_d, C_d, T_d = curve_from_heading(L, alpha, beta)
    # ring stations: a rounded head and tail, uniform in between
    th = np.radians([14, 36, 58, 78])
    cap = r0 * (1 - np.cos(th))
    body = np.arange(r0, L - r0 + 1e-9, 0.82)
    sv = np.concatenate([[0.0], cap, body[1:-1], L - cap[::-1], [L]])
    rad_end = np.concatenate([[0.0], r0 * np.sin(th), np.full(len(body) - 2, r0), r0 * np.sin(th)[::-1], [0.0]])
    Cs, Ts = sample_curve(s_d, C_d, T_d, sv)
    tw = 0.25 * np.sin(2 * math.pi * sv / L * 1.3 + ph[2])
    W, B = frame_along(Ts, tw)
    period = rng.uniform(3.2, 3.9)
    groove = np.exp(-(((sv / period) % 1.0 - 0.5) / 0.13) ** 2)
    ridge = 1 - 0.042 * groove
    wob = 1 + 0.03 * np.sin(2 * math.pi * sv / 17 + ph[0])
    nphi = 16
    phi = np.arange(nphi) * math.tau / nphi
    nu = len(sv)
    rw = (rad_end * ridge * wob)[:, None]
    rb = rw * 0.9
    ring = Cs[:, None, :] + rw[..., None] * np.cos(phi)[None, :, None] * W[:, None, :] + rb[..., None] * np.sin(phi)[None, :, None] * B[:, None, :]
    # the end rings are single points (apex): merge them
    V = ring.reshape(-1, 3)
    F = ring_faces(nu, nphi)
    # (the first and last rings have radius 0: degenerate triangles are dropped)
    F = np.array(F, dtype=np.int64)
    ar = np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    F = F[ar > 1e-9]
    su = np.repeat(sv, nphi)
    pv = np.tile(phi, nu)
    gr = np.repeat(groove, nphi)
    V = V + 0.03 * hash_vec(V, 1.7, 300 + i)
    F = orient_outward(V, F)
    used = np.unique(F)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used))
    V, F, su, pv, gr = V[used], remap[F], su[used], pv[used], gr[used]
    N = vertex_normals(V, F)
    # colour
    if mode == 'spiral':
        lam = rng.uniform(16, 30)
        sel = np.sin(pv + math.tau * su / lam + ph[0])
        blend = smoothstep(-0.12, 0.12, sel)
    elif mode == 'halves':
        lam = rng.uniform(60, 120)
        sel = np.sin(pv + math.tau * su / lam + ph[1] + 1.2)
        blend = smoothstep(-0.07, 0.07, sel)
    else:
        per = rng.uniform(8, 11)
        sel = np.sin(math.tau * su / per + 0.35 * np.sin(pv) + ph[2])
        blend = smoothstep(-0.1, 0.1, sel)
    Q = V
    ends = smoothstep(r0 * 0.9, 0.0, np.minimum(su, L - su))
    col = mix(colA, colB, blend)
    col = mix(col * 0.78, np.minimum(col * 1.15 + 0.03, 1.0), np.clip(ends + 0.25, 0, 1))      # the thin tips glow
    col = col * (1 - 0.22 * gr[:, None])                                     # shade in the grooves
    col = col * (1 + 0.05 * fbm(Q / 3.0, 2, 17 + i))[:, None]
    rough = 0.1 + 0.03 * fbm(Q / 2.2, 2, 5 + i) + 0.05 * gr
    ao = 1 - 0.28 * gr
    return finish(f'worms_{i}', V * MM, F, N, col, rough, np.full(len(V), 0.97), np.ones(len(V)), ao, 'jelly', jelly=True)


# ------------------------------------------------------------------ sour belts
SOUR_STYLES = [('#d4141c', '#f6d012', 'width'), ('#4fae31', '#1d6fd0', 'length'), ('#f26a1b', '#c8102e', 'width'),
               ('#e0192a', '#f9d51a', 'length'), ('#4fae31', '#1d6fd0', 'width')]


def sour_belt(i):
    rng = np.random.default_rng(8000 + i)
    L = rng.uniform(30, 40)
    w = rng.uniform(6.0, 8.0)
    t = rng.uniform(1.8, 2.3)
    ca, cb, mode = SOUR_STYLES[i % 5]
    colA, colB = lin(ca), lin(cb)
    shape = ['S', 'U', 'S', 'U', 'S'][i % 5]
    ph = rng.uniform(0, 6.28, 4)
    if shape == 'S':
        k1, k2 = rng.uniform(0.9, 1.25), rng.uniform(0, 0.4)
        alpha = lambda x: k1 * np.sin(2 * math.pi * x / L + ph[0] * 0.2) + k2 * (x / L - 0.5)
    else:
        tot = rng.uniform(2.2, 3.0) * rng.choice([-1, 1])
        alpha = lambda x: tot * (x / L - 0.5) + 0.25 * np.sin(2 * math.pi * 1.5 * x / L + ph[0])
    beta = lambda x: 0.1 * np.sin(2 * math.pi * x / L * 1.0 + ph[1]) + 0.05 * np.sin(2 * math.pi * x / L * 2.3 + ph[2])
    s_d, C_d, T_d = curve_from_heading(L, alpha, beta)
    sv = np.linspace(0, L, int(L / 0.72) + 1)
    Cs, Ts = sample_curve(s_d, C_d, T_d, sv)
    tw = 0.2 * np.sin(2 * math.pi * sv / L * 0.9 + ph[3]) + 0.08 * np.sin(2 * math.pi * sv / L * 2.7 + ph[1])
    W, B = frame_along(Ts, tw)
    # the cross-section: a rounded rectangle, resampled evenly by arc length (so the wide faces get their share of vertices)
    a_h, b_h = 0.5, t / w * 0.5                                    # (unit width)
    rc = b_h * 0.8
    cs = []
    for (cx, cy, a0) in ((a_h - rc, b_h - rc, 0.0), (-(a_h - rc), b_h - rc, math.pi / 2), (-(a_h - rc), -(b_h - rc), math.pi),
                         (a_h - rc, -(b_h - rc), 1.5 * math.pi)):
        for th in np.linspace(a0, a0 + math.pi / 2, 7):
            cs.append((cx + rc * math.cos(th), cy + rc * math.sin(th)))
    cs = np.array(cs + [cs[0]])
    seg = np.linalg.norm(np.diff(cs, axis=0), axis=1)
    arc = np.concatenate([[0], np.cumsum(seg)])
    nphi = 30
    q = np.arange(nphi) * arc[-1] / nphi
    ex = np.interp(q, arc, cs[:, 0]) * 2                          # -1 .. 1 across the width
    ey = np.interp(q, arc, cs[:, 1]) * 2 * w / t                   # -1 .. 1 through the thickness
    phi = q
    nu = len(sv)
    wob = 1 + 0.025 * np.sin(2 * math.pi * sv / 9 + ph[2])
    ring = Cs[:, None, :] + (w / 2 * wob)[:, None, None] * ex[None, :, None] * W[:, None, :] + (t / 2) * ey[None, :, None] * B[:, None, :]
    V = ring.reshape(-1, 3)
    F = np.array(ring_faces(nu, nphi), dtype=np.int64)
    # flat square-cut ends: duplicate the end rings with a fan to the centre
    n0 = len(V)
    caps = [np.arange(nphi), (nu - 1) * nphi + np.arange(nphi)]
    extraV = []
    extraF = []
    for ci, rg in enumerate(caps):
        base = n0 + len(extraV)
        extraV += [V[k] for k in rg] + [V[rg].mean(0)]
        for k in range(nphi):
            a, b = base + k, base + (k + 1) % nphi
            extraF.append((base + nphi, a, b) if ci == 0 else (base + nphi, b, a))
    V = np.vstack([V, np.array(extraV)])
    F = np.vstack([F, np.array(extraF, dtype=np.int64)])
    F = orient_outward(V, F)
    su = np.concatenate([np.repeat(sv, nphi), np.zeros(nphi + 1), np.full(nphi + 1, L)])
    pv = np.concatenate([np.tile(phi, nu), phi, [0.0], phi, [0.0]])
    # width coordinate (which side of the belt) for the two-tone split: sign of the W component
    wv = np.concatenate([np.tile(ex, nu), ex, [0.0], ex, [0.0]])
    bv = np.concatenate([np.tile(ey, nu), ey, [0.0], ey, [0.0]])
    N = vertex_normals(V, F)
    # a finer, deliberately rough look: sugar crystals tilt the normal and break the silhouette
    Q = V
    jit = hash_vec(Q, 0.55, 40 + i) * 0.2 + hash_vec(Q, 0.3, 50 + i) * 0.16
    N = N + jit
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    # two-tone
    wob_split = 0.18 * fbm(Q / 2.0, 2, 3 + i)
    if mode == 'width':
        blend = smoothstep(-0.05, 0.05, wv + wob_split * 0.3)
    else:
        blend = smoothstep(-0.8, 0.8, su - L * (0.5 + 0.03 * np.sin(wv * 3 + i)) + 0.0) * 1.0
    base = mix(colA, colB, blend)
    # sugar: patchy cover; bare spots show the saturated, glossy gum
    f1, f2, cid = worley(Q / 0.46, 70 + i)
    patch = 0.62 + 0.3 * fbm(Q / 3.0, 2, 77 + i)
    crystal = smoothstep(0.62, 0.18, f1) * smoothstep(0.18, 0.48, cid + 0.25 * vnoise(Q / 0.5, 3))
    cover = np.clip(patch * (0.55 + 0.7 * crystal), 0, 1)
    sugar = lin('#fbf9f3')
    pale = mix(base, sugar, 0.3)
    col = mix(base * 0.92, pale, cover)
    col = mix(col, sugar, crystal * 0.5)
    rough = 0.55 - 0.3 * crystal - 0.15 * (1 - cover)
    spec = np.clip(0.55 + 0.7 * crystal + 0.4 * vnoise(Q / 0.25, 9), 0.3, 1.0)
    ao = 1 - 0.12 * np.clip(-bv, 0, 1)
    return finish(f'sour_{i}', V * MM, F, N, col, rough, np.full(len(V), 0.35), spec, ao, 'candy', flat=True)


# ------------------------------------------------------------------ sprinkles
def nonpareil_ball(i):
    rng = np.random.default_rng(9000 + i)
    # icosphere, one subdivision: 42 vertices, 80 faces
    t = (1 + 5 ** 0.5) / 2
    base = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                     [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], dtype=float)
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    f0 = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
          (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [v for v in base]
    cache = {}

    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k not in cache:
            m = (V[a] + V[b]) / 2
            V.append(m / np.linalg.norm(m))
            cache[k] = len(V) - 1
        return cache[k]
    F = []
    for a, b, c in f0:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
        F += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    V = np.array(V)
    F = np.array(F, dtype=np.int64)
    r = 1.0 * (1 + 0.07 * hash_vec(V * 1.3, 1.0, 11)[:, 0] + 0.03 * hash_vec(V * 2.3, 1.0, 14)[:, 1])
    V = V * r[:, None] * np.array([1.0, 0.93, 1.0])
    F = orient_outward(V, F)
    N = vertex_normals(V, F)
    return finish('nonpareil_0', V * MM, F, N, np.ones((len(V), 3)), np.full(len(V), 0.18), np.full(len(V), 0.35), np.ones(len(V)), np.ones(len(V)), 'candy')


def jimmy_rod(i):
    rng = np.random.default_rng(9100 + i)
    L = [5.0, 5.6, 6.0][i % 3] * rng.uniform(0.97, 1.03)      # 5 .. 6 mm
    r = 0.55 * rng.uniform(0.95, 1.05)                          # 1.1 mm across
    bend = [0.12, 0.3, -0.22][i % 3]                            # gentle curve (rad over the length)
    nseg = 8
    th = np.radians([32, 66])
    cap = r * (1 - np.cos(th))
    sv = np.concatenate([[0.0], cap, [L / 2], L - cap[::-1], [L]])
    rad = np.concatenate([[0.0], r * np.sin(th), [r], r * np.sin(th)[::-1], [0.0]])
    alpha = lambda x: bend * (x / L - 0.5)
    beta = lambda x: 0 * x
    s_d, C_d, T_d = curve_from_heading(L, alpha, beta, 200)
    Cs, Ts = sample_curve(s_d, C_d, T_d, sv)
    W, B = frame_along(Ts)
    phi = np.arange(nseg) * math.tau / nseg + 0.2 * i
    ring = Cs[:, None, :] + rad[:, None, None] * (np.cos(phi)[None, :, None] * W[:, None, :] + np.sin(phi)[None, :, None] * B[:, None, :])
    V = ring.reshape(-1, 3)
    F = np.array(ring_faces(len(sv), nseg), dtype=np.int64)
    ar = np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    F = F[ar > 1e-9]
    V = V + 0.02 * hash_vec(V, 0.6, 400 + i)
    F = orient_outward(V, F)
    used = np.unique(F)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used))
    V, F = V[used], remap[F]
    N = vertex_normals(V, F)
    return finish(f'jimmy_{i}', V * MM, F, N, np.ones((len(V), 3)), np.full(len(V), 0.2), np.full(len(V), 0.3), np.ones(len(V)), np.ones(len(V)), 'candy')


def salt_flake(i):
    """a hopper of salt: a thin four-sided shell, point down, open at the top (a pyramid with a hollow middle)"""
    rng = np.random.default_rng(9200 + i)
    a = [0.62, 0.78, 0.93, 1.1][i % 4] * rng.uniform(0.94, 1.06)     # (the flake is about 3.4 a wide): 2 .. 3.9 mm
    d = a * [0.8, 0.62, 0.9, 0.42][i % 4]                             # how deep the hollow goes
    tw = rng.uniform(0.1, 0.15)                                       # the wall
    ang = rng.uniform(0, math.tau)
    corners = []
    for k in range(4):
        th = ang + k * math.pi / 2 + rng.uniform(-0.18, 0.18)
        corners.append([a * rng.uniform(0.9, 1.22) * math.cos(th) * 1.41, 0, a * rng.uniform(0.9, 1.22) * math.sin(th) * 1.41])
    corners = np.array(corners)
    # ring of 8 points: corners and edge midpoints (the midpoints sag and wander a little: uneven edges)
    def ring_pts(scale, y):
        pts = []
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            pts.append(c0 * scale)
            m = (c0 + c1) / 2 * scale
            pts.append(m + np.array([0.0, 0.0, 0.0]))
        P = np.array(pts)
        P[:, 1] = y
        return P
    levels = [(1.0, 0.0), (0.66, -0.36 * d), (0.34, -0.7 * d)]
    apex_out = np.array([0.0, -d - tw * 1.35, 0.0])
    apex_in = np.array([0.0, -d + tw * 0.5, 0.0])
    # edge midpoint wander and a lower corner
    wander = rng.uniform(-0.12, 0.12, (3, 8, 3)) * a
    V = []
    idx_out = []
    idx_in = []
    for li, (sc, y) in enumerate(levels):
        po = ring_pts(sc * (1.0 + tw / a * 0.9), y - tw * 0.9) + wander[li] * (0.5 if li else 1.0) * np.array([1, 0.4, 1])
        pi_ = ring_pts(sc * (1.0 - tw / a * 0.5), y + (0.0 if li else 0.0)) + wander[li] * (0.5 if li else 1.0) * np.array([1, 0.4, 1])
        idx_out.append(list(range(len(V), len(V) + 8)))
        V += list(po)
        idx_in.append(list(range(len(V), len(V) + 8)))
        V += list(pi_)
    ao_i = len(V)
    V.append(apex_out)
    V.append(apex_in)
    V = np.array(V)
    F = []
    for li in range(2):
        for k in range(8):
            k2 = (k + 1) % 8
            F += [(idx_out[li][k], idx_out[li + 1][k], idx_out[li][k2]), (idx_out[li][k2], idx_out[li + 1][k], idx_out[li + 1][k2])]
            F += [(idx_in[li][k], idx_in[li][k2], idx_in[li + 1][k]), (idx_in[li][k2], idx_in[li + 1][k2], idx_in[li + 1][k])]
    for k in range(8):
        k2 = (k + 1) % 8
        F.append((idx_out[2][k], ao_i, idx_out[2][k2]))
        F.append((idx_in[2][k], idx_in[2][k2], ao_i + 1))
        F += [(idx_out[0][k], idx_out[0][k2], idx_in[0][k]), (idx_out[0][k2], idx_in[0][k2], idx_in[0][k])]   # the rim
    F = np.array(F, dtype=np.int64)
    F = orient_outward(V, F)
    # flat facets: every triangle its own vertices, so each one glints separately
    Vf = V[F].reshape(-1, 3)
    Ff = np.arange(len(Vf)).reshape(-1, 3)
    fnrm = face_normals(Vf, Ff)
    fnrm /= np.maximum(np.linalg.norm(fnrm, axis=1, keepdims=True), 1e-12)
    N = np.repeat(fnrm, 3, axis=0)
    depth = np.clip(-Vf[:, 1] / max(d, 1e-6), 0, 1)
    inside = np.repeat(fnrm[:, 1] > 0.1, 3)
    shade = np.repeat(rng.uniform(0.9, 1.0, len(F)), 3)
    col = np.outer(shade * (1 - 0.18 * depth * inside), [0.985, 0.985, 0.972])
    ao = 1 - 0.38 * depth * inside
    return finish(f'salt_{i}', Vf * MM, Ff, N, col, np.full(len(Vf), 0.22), np.full(len(Vf), 0.65), np.ones(len(Vf)), ao, 'candy')


# key (the bar's topping key) -> piece builder, how many variants, how its heap is laid (None: scattered by the page)
PIECES = {
    'gummies': dict(fn=gummy_bear, n=8, heap=dict(bowl='organic', over=0.012, phi=0.5, weights=[0.5, 1, 1, 0.5, 1, 1, 0.5, 0.5])),
    'mms': dict(fn=mm_candy, n=8, heap=dict(bowl='organic', over=0.012, phi=0.5, weights=[0.5, 1, 1, 1, 0.5, 1, 0.5, 0.5])),
    'chips': dict(fn=choc_chip, n=5, heap=dict(bowl='organic', over=0.012, phi=0.5, fast=True)),
    'chunks': dict(fn=choc_chunk, n=6, heap=dict(bowl='organic', over=0.012, phi=0.5)),
    'sour': dict(fn=sour_belt, n=5, heap=dict(bowl='organic', over=0.015, phi=0.3)),
    'worms': dict(fn=gummy_worm, n=5, heap=dict(bowl='organic', over=0.015, phi=0.3)),
    'nonpareil': dict(fn=nonpareil_ball, n=1, heap=None),
    'jimmy': dict(fn=jimmy_rod, n=3, heap=None),
    'salt': dict(fn=salt_flake, n=4, heap=None),
}

"""Baked and crunchy: granola, brownie bites, rainbow cookies, Rice Krispies treats, Oreo crumble, mini cookies, Biscoff, cookie dough, cinnamon rolls, coconut, kataifi."""
import math

import numpy as np  # noqa: F401
from scipy import ndimage
from skimage import measure

from lib import (MM, TAU, face_normals, fbm, grad, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_cyl, sd_ellipsoid, sd_plane, sd_sphere,  # noqa: F401
                 sdf_ao, smax, smin, smooth_mesh, smoothstep, vertex_normals, vnoise, worley)


# ------------------------------------------------------------------ helpers shared by the pieces in this file
def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def _frame(n, rng):
    """a rotation whose columns are (a, b, n): n the given normal, a random in-plane axis. q = (P - c) @ R gives local coords"""
    n = _unit(n)
    a = rng.normal(size=3)
    a = _unit(a - (a @ n) * n)
    return np.stack([a, np.cross(n, a), n], 1)


def _lerp(a, b, t):
    """scalar lerp (mix is for colours)"""
    t = np.clip(np.asarray(t, dtype=float), 0, 1)
    return a * (1 - t) + b * t


def _sminv(cols, k):
    """smooth union over the columns of an (n, m) array"""
    d = cols[:, 0]
    for j in range(1, cols.shape[1]):
        d = smin(d, cols[:, j], k)
    return d


def _bake(name, f, lo, hi, vox, paint, smooth=1, cls='matte', flat=False, ao_h=None, ao_strength=1.0):
    """lib.piece with a per-axis voxel (finer where a layer boundary has to stay crisp) and only the largest solid kept"""
    vox = np.broadcast_to(np.asarray(vox, dtype=float), (3,)).copy()
    lo = np.asarray(lo, dtype=float) - 2 * vox
    hi = np.asarray(hi, dtype=float) + 2 * vox
    n = np.ceil((hi - lo) / vox).astype(int) + 1
    ax = [lo[a] + np.arange(n[a]) * vox[a] for a in range(3)]
    G = np.stack(np.meshgrid(*ax, indexing='ij'), -1).reshape(-1, 3)
    vol = f(G).reshape(tuple(n))
    inside = vol < 0
    lab, k = ndimage.label(inside)
    if k > 1:
        sizes = ndimage.sum(inside, lab, np.arange(1, k + 1))
        keep = 1 + int(np.argmax(sizes))
        vol = np.where(inside & (lab != keep), np.abs(vol) + 1e-7, vol)
    V, F, _, _ = measure.marching_cubes(vol, 0.0, spacing=tuple(vox))
    V = V + lo
    if smooth:
        V = smooth_mesh(V, F, smooth)
    G3 = grad(f, V, float(vox.min()) * 0.5)
    N = G3 / np.maximum(np.linalg.norm(G3, axis=-1, keepdims=True), 1e-9)
    Nm = vertex_normals(V, F)
    bad = np.linalg.norm(G3, axis=-1) < 0.2
    N[bad] = Nm[bad]
    ao = sdf_ao(f, V, N, ao_h or float(vox.min()) * 1.6, ao_strength)
    rgb, rough, sss, spec = paint(V, N, f)
    lo_v, hi_v = V.min(0), V.max(0)
    Vc = V - (lo_v + hi_v) / 2
    fn = face_normals(V, F)
    if (np.einsum('ij,ij->i', fn, N[F].mean(1)) < 0).mean() > 0.5:
        F = F[:, ::-1].copy()
    return dict(name=name, V=Vc.astype(np.float32), N=N.astype(np.float32), F=F.astype(np.uint32),
                COLOR_0=np.concatenate([rgb, np.clip(rough, 0.04, 1.0)[:, None]], 1).astype(np.float32),
                _DATA=np.stack([ao, sss, spec], 1).astype(np.float32),
                extras=dict(cls=cls, flat=bool(flat), jelly=False, r=float(np.linalg.norm(Vc, axis=-1).max()),
                            size=[float(x) for x in (hi_v - lo_v)]))


# ------------------------------------------------------------------ granola
def granola(i):
    """a cluster of rolled-oat flakes (thin curled ovals, overlapping at angles) and a few seeds, bound and glazed with honey"""
    rng = np.random.default_rng(3100 + i)
    A = np.array([rng.uniform(3.3, 4.6), rng.uniform(2.7, 3.7), rng.uniform(2.4, 3.4)]) * MM
    if rng.random() < 0.4:
        A[0] *= 1.15
    nf = int(rng.integers(22, 30))
    C = np.zeros((nf, 3))
    Rm = np.zeros((nf, 3, 3))
    Rad = np.zeros((nf, 3))
    curl = np.zeros(nf)
    toast = np.zeros(nf)
    for j in range(nf):
        u = _unit(rng.normal(size=3))
        C[j] = u * A * rng.uniform(0.62, 1.0)
        n = _unit(u / A) * rng.uniform(0.2, 0.9) + rng.normal(size=3) * 0.75
        Rm[j] = _frame(n, rng)
        Rad[j] = np.array([rng.uniform(2.2, 3.1), rng.uniform(1.4, 2.0), rng.uniform(0.42, 0.56)]) * MM
        curl[j] = rng.uniform(-0.55, 0.55) * MM
        toast[j] = rng.random()
    # seeds: a pumpkin seed or two, a few sesame
    ns = int(rng.integers(4, 8))
    npump = int(rng.integers(0, 4)) if i % 4 else 2
    SC = np.zeros((ns, 3))
    SR = np.zeros((ns, 3, 3))
    SRad = np.zeros((ns, 3))
    SK = np.zeros(ns)
    for j in range(ns):
        u = _unit(rng.normal(size=3))
        pump = j < npump
        SC[j] = u * A * rng.uniform(0.92, 1.06)
        SR[j] = _frame(_unit(u / A) + rng.normal(size=3) * 0.25, rng)
        SRad[j] = np.array([1.9, 1.05, 0.5] if pump else [0.9, 0.55, 0.3]) * MM * rng.uniform(0.9, 1.1)
        SK[j] = 1.0 if pump else 0.0
    tone = rng.uniform(-0.3, 0.15)         # how toasted this cluster is overall

    def warp(P):
        s = 1.0 / (1.7 * MM)
        return P + 0.22 * MM * np.stack([vnoise(P * s, 11), vnoise(P * s + 5.3, 12), vnoise(P * s + 9.1, 13)], 1)

    def parts(P):
        Pw = warp(P)
        D = np.empty((len(P), nf))
        for j in range(nf):
            q = (Pw - C[j]) @ Rm[j]
            qz = q[:, 2] - curl[j] * (q[:, 0] / Rad[j, 0]) ** 2
            D[:, j] = sd_ellipsoid(np.stack([q[:, 0], q[:, 1], qz], 1), 0, Rad[j])
        S = np.empty((len(P), ns))
        for j in range(ns):
            S[:, j] = sd_ellipsoid((P - SC[j]) @ SR[j], 0, SRad[j])
        core = sd_ellipsoid(P, 0, A * 0.45) + 0.3 * MM * fbm(P / (2.4 * MM), 2, 5)
        return D, S, core

    def film(P):
        n = vnoise(P / (2.1 * MM), 31) + 0.55 * vnoise(P / (0.9 * MM), 32)
        return (0.0 + 0.07 * smoothstep(0.1, 0.7, n)) * MM

    def f(P):
        D, S, core = parts(P)
        pools = core
        for j in range(nf):
            pools = smin(pools, D[:, j], 0.5 * MM)
        for j in range(ns):
            pools = smin(pools, S[:, j], 0.6 * MM)
        return pools - film(P)

    pale, golden, toasted, deep = lin('#e4c581'), lin('#d3a05a'), lin('#a8702f'), lin('#8c5a24')
    honey, honey_d = lin('#a56a26'), lin('#7c4a18')
    pump_c, pump_rim, ses_c = lin('#5e7a2c'), lin('#8da04a'), lin('#e8d6a6')

    def paint(V, N, field):
        D, S, core = parts(V)
        dry = _sminv(np.concatenate([D, core[:, None]], 1), 0.4 * MM)
        j = np.argmin(D, 1)
        dmin = D[np.arange(len(V)), j]
        wf = smoothstep(0.30 * MM, 0.0, dmin)
        q = np.einsum('nj,njk->nk', warp(V) - C[j], Rm[j])
        r2 = np.sqrt((q[:, 0] / Rad[j, 0]) ** 2 + (q[:, 1] / Rad[j, 1]) ** 2)
        edge = smoothstep(0.55, 1.05, r2)
        streak = vnoise(np.stack([q[:, 0] / (3.5 * MM), q[:, 1] / (0.55 * MM), q[:, 2] / (2 * MM)], 1) + j[:, None] * 3.7, 41)
        t = np.clip(toast[j] * 0.8 + 0.3 * edge + tone + 0.12 * streak
                    + 0.25 * smoothstep(0.5, 1.2, np.linalg.norm(V / A, axis=1)), 0, 1)
        flake = mix(mix(pale, golden, smoothstep(0.0, 0.5, t)), toasted, smoothstep(0.45, 1.0, t))
        flake = flake * (1 + 0.07 * streak[:, None]) * (0.86 + 0.28 * ((j * 0.6180339) % 1.0))[:, None]
        # honey: thick wherever the surface stands off the dry flakes (crevices, menisci) and in patches
        th = np.maximum(dry, 0.0)
        glaze = np.clip(smoothstep(0.12 * MM, 0.35 * MM, th) + 0.9 * smoothstep(0.45, 0.8, vnoise(V / (1.8 * MM), 51)) * smoothstep(0.02 * MM, 0.12 * MM, th + 0.04 * MM), 0, 1)
        hc = mix(honey, honey_d, smoothstep(0.1 * MM, 0.5 * MM, th))
        col = mix(flake, hc, glaze * 0.9)
        col = mix(hc * 0.9, col, wf)                           # no flake near: just the binder
        # seeds
        sm = S.min(1)
        k = np.argmin(S, 1)
        ws = smoothstep(0.10 * MM, -0.08 * MM, sm)
        pump = SK[k] > 0.5
        sq = np.einsum('nj,njk->nk', V - SC[k], SR[k])
        sr = np.sqrt((sq[:, 0] / SRad[k, 0]) ** 2 + (sq[:, 1] / SRad[k, 1]) ** 2)
        sc = np.where(pump[:, None], mix(pump_c, pump_rim, smoothstep(0.55, 1.0, sr)), ses_c)
        col = mix(col, sc, ws)
        rough = 0.84 - 0.42 * smoothstep(0.25, 0.7, glaze) + 0.06 * streak
        rough = np.where(ws > 0.5, 0.5, rough)
        sss = np.full(len(V), 0.14)
        spec = 0.35 + 0.65 * glaze
        return col, rough, sss, spec

    lo, hi = -(A + 2.6 * MM), (A + 2.6 * MM)
    return _bake(f'granola_{i}', f, lo, hi, 0.62 * MM, paint, smooth=1, ao_strength=1.0)



# ------------------------------------------------------------------ brownie bites
def brownies(i):
    """a brownie bite cut from the pan: shiny crackled crust on top, dense fudgy crumb on the cut sides, crumbled edges"""
    rng = np.random.default_rng(3200 + i)
    half = np.array([rng.uniform(5.3, 6.7), rng.uniform(4.6, 5.9), rng.uniform(5.3, 6.7)]) * MM
    axes = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    nrm = np.array([_unit(a + 0.07 * rng.normal(size=3)) for a in axes])
    off = np.array([half[np.argmax(np.abs(a))] * rng.uniform(0.94, 1.02) for a in axes])
    dome = rng.uniform(0.35, 0.8) * MM
    # a few bites taken out of the edges and corners
    chips = []
    for _ in range(int(rng.integers(3, 6))):
        s_ = rng.choice([-1, 1], 3)
        c = s_ * half * rng.uniform(0.88, 1.0, 3)
        c[rng.integers(0, 3)] = rng.uniform(-0.7, 0.7) * half[0]
        chips.append((c, rng.uniform(0.9, 1.7) * MM))
    seed = int(rng.integers(0, 1000))

    def planes(P):
        D = P @ nrm.T - off                                  # (n,6) signed distance to each face plane
        rr = np.minimum(np.hypot(P[:, 0] / half[0], P[:, 2] / half[2]), 1.0)
        D[:, 2] -= dome * (1.0 - rr * rr)                    # the top domes a little
        return D

    def f(P):
        D = planes(P)
        d = D[:, 0]
        for k in range(1, 6):
            d = smax(d, D[:, k], 1.2 * MM)
        srt = np.sort(D, axis=1)
        edge = smoothstep(2.0 * MM, 0.2 * MM, -srt[:, -2])
        d = d + (0.16 * MM + 0.30 * MM * edge) * fbm(P / (1.25 * MM), 2, seed)
        for c, r in chips:
            d = smax(d, -(np.linalg.norm(P - c, axis=1) - r * (1 + 0.25 * vnoise(P / (0.8 * MM), seed + 5))), 0.35 * MM)
        return d

    crust_c, crust_d, crack_c = lin('#43220f'), lin('#2c1308'), lin('#8a6446')
    crumb_a, crumb_b, crumb_l, pore, fudge = lin('#2b150b'), lin('#4a2814'), lin('#62391d'), lin('#150803'), lin('#1f0e06')
    bottom_c = lin('#3b1f0f')

    def paint(V, N, field):
        D = planes(V)
        dt = -D[:, 2]
        srt = np.sort(D, axis=1)
        edge = smoothstep(2.0 * MM, 0.2 * MM, -srt[:, -2])
        up = smoothstep(0.45, 0.85, N[:, 1])
        crust = up * smoothstep(1.5 * MM, 0.5 * MM, dt)
        down = smoothstep(-0.5, -0.9, N[:, 1])
        # --- the crust: glossy, darker in patches, a network of paler cracks
        W = V + 0.45 * MM * np.stack([vnoise(V / (2.5 * MM), 61), vnoise(V / (2.5 * MM) + 3.1, 62), vnoise(V / (2.5 * MM) + 7.7, 63)], 1)
        f1, f2, cid = worley(W / (3.1 * MM), seed + 1)
        crack = smoothstep(0.24, 0.10, f2 - f1) * smoothstep(-0.5, 0.25, vnoise(W / (2.2 * MM), seed + 4))
        g1, g2, gid = worley(W / (1.5 * MM), seed + 9)
        fine = smoothstep(0.22, 0.06, g2 - g1) * 0.5
        patch = 0.5 + 0.5 * fbm(V / (3.0 * MM), 2, seed + 12)
        cr = mix(crust_c, crust_d, np.clip(patch * 0.6 + 0.5 * (cid - 0.5) + 0.2, 0, 1))
        cr = mix(cr, crack_c, np.clip(crack + fine * (1 - crack), 0, 1) * 0.85)
        cr = mix(cr, lin('#7a4a28'), smoothstep(0.78, 0.95, vnoise(V / (0.8 * MM), 64)) * 0.4)   # pale flecks
        # --- the cut crumb: dense, moist, dark, tiny crumbs and pores, glossy fudge patches
        c1, c2, cd = worley(V / (1.05 * MM), seed + 21)
        crumb_sp = smoothstep(0.34, 0.14, c1) * (cd > 0.55)
        pore_sp = smoothstep(0.26, 0.10, c1) * (cd < 0.2)
        base = mix(crumb_a, crumb_b, 0.5 + 0.5 * fbm(V / (1.6 * MM), 2, seed + 22))
        base = mix(base, crumb_l, crumb_sp * 0.8)
        base = mix(base, pore, pore_sp * 0.9)
        fg = smoothstep(0.18, 0.5, fbm(V / (3.3 * MM), 2, seed + 33))
        base = mix(base, fudge, fg * 0.9)
        base = mix(base, crumb_l, edge * 0.55 * (0.5 + 0.5 * vnoise(V / (0.9 * MM), 66)))   # crumbled edges are paler
        base = mix(base, bottom_c, down * 0.8)
        col = mix(base, cr, crust)
        rough = _lerp(0.84 - 0.38 * fg + 0.1 * edge, 0.22 + 0.36 * np.clip(crack + fine, 0, 1), crust)
        rough = np.where(down > 0.5, 0.88, rough)
        sss = np.full(len(V), 0.12)
        spec = _lerp(0.35 + 0.45 * fg, 0.8, crust) * (1 - 0.4 * down)
        return col, rough, sss, spec

    lo, hi = -(half + 1.8 * MM), (half + 1.8 * MM)
    return _bake(f'brownies_{i}', f, lo, hi, 0.8 * MM, paint, smooth=1, ao_strength=1.0)


# ------------------------------------------------------------------ rainbow cookie (tricolor), cut from the bar
def rainbow(i):
    """chocolate, green almond sponge, raspberry jam, yellow-cream sponge, jam, red-pink sponge, chocolate: layers lie along Y"""
    rng = np.random.default_rng(3300 + i)
    Lx, Lz, H = rng.uniform(13.0, 15.0) * MM, rng.uniform(8.6, 9.6) * MM, rng.uniform(8.6, 9.6) * MM
    hx, hz, hh = Lx / 2, Lz / 2, H / 2
    tc = rng.uniform(0.7, 1.0) * MM
    tj = rng.uniform(0.5, 0.7, 2) * MM
    sp = (H - 2 * tc - tj.sum())
    spl = rng.uniform(0.9, 1.1, 3)
    spl = spl / spl.sum() * sp
    th = [tc, spl[0], tj[0], spl[1], tj[1], spl[2], tc]
    bnd = -hh + np.cumsum(th)[:-1]                                        # the six boundaries, bottom to top
    green, yellow, redp = lin('#6aa84f'), lin('#f1d27a'), lin('#e05a62')
    jam_c, choc_c = lin('#a82a1a'), lin('#1f0f09')
    sponge = [green, yellow, redp]
    if rng.random() < 0.4:
        sponge = sponge[::-1]
    LC = [choc_c, sponge[0], jam_c, sponge[1], jam_c, sponge[2], choc_c]
    shx, shz = rng.uniform(-0.03, 0.03, 2)                                # the knife was not quite square
    chips = [(rng.choice([-1, 1], 3) * np.array([hx, hh, hz]) * rng.uniform(0.9, 1.0, 3), rng.uniform(0.8, 1.4) * MM)
             for _ in range(int(rng.integers(1, 4)))]
    seed = int(rng.integers(0, 1000))
    rr = 0.7 * MM

    def un(P):
        return np.stack([P[:, 0] - shx * P[:, 1], P[:, 1], P[:, 2] - shz * P[:, 1]], 1)

    def band(y, a, b, w=0.12 * MM):
        return smoothstep(a - w, a + w, y) - smoothstep(b - w, b + w, y)

    def f(P):
        Q = un(P)
        x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
        e = 0.14 * MM * (1 - smoothstep(bnd[0] - 0.1 * MM, bnd[0] + 0.1 * MM, y) + smoothstep(bnd[5] - 0.1 * MM, bnd[5] + 0.1 * MM, y))
        e = e + 0.10 * MM * (band(y, bnd[1], bnd[2]) + band(y, bnd[3], bnd[4]))
        qx = np.abs(x) - (hx + e) + rr
        qz = np.abs(z) - (hz + e) + rr
        out = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - rr
        d = smax(out, np.abs(y) - hh, 0.5 * MM)
        d = d + 0.08 * MM * fbm(Q / (2.0 * MM), 2, seed)
        for c, r in chips:
            d = smax(d, -(np.linalg.norm(Q - c, axis=1) - r), 0.25 * MM)
        return d

    def paint(V, N, field):
        Q = un(V)
        x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
        xz = np.stack([x / (3.5 * MM), z / (3.5 * MM)], 1)

        def wob(k):
            return 0.12 * MM * vnoise(np.concatenate([xz, np.full((len(x), 1), 3.1 * k)], 1), 70 + k)
        drip = vnoise(np.stack([x / (1.5 * MM), z / (1.5 * MM), np.full(len(x), 5.5)], 1), 80)
        dt = 0.8 * MM * smoothstep(0.05, 0.7, drip)
        db = 0.3 * MM * smoothstep(0.1, 0.8, drip)
        col = np.tile(LC[0], (len(x), 1))
        T = []
        for k in range(6):
            b = bnd[k] + wob(k) + (db if k == 0 else 0) - (dt if k == 5 else 0)
            t = smoothstep(b - 0.08 * MM, b + 0.08 * MM, y)
            T.append(t)
            col = mix(col, LC[k + 1], t)
        choc = (1 - T[0]) + T[5]
        jam = (T[1] - T[2]) + (T[3] - T[4])
        # sponge: fine crumb, pores
        s1, s2, sid = worley(V / (0.8 * MM), seed + 3)
        crumb = 1 + 0.07 * vnoise(V / (0.7 * MM), seed + 4) - 0.10 * smoothstep(0.2, 0.08, s1) * (sid > 0.5)
        col = col * np.where(choc[:, None] > 0.5, 1.0, crumb[:, None])
        # jam: darker seeds
        j1, j2, jid = worley(V / (0.6 * MM), seed + 5)
        col = mix(col, lin('#6a1a0d'), jam * smoothstep(0.2, 0.1, j1) * (jid > 0.6) * 0.6)
        # chocolate: blotchy bloom
        bloom = smoothstep(0.35, 0.8, fbm(V / (2.2 * MM), 2, seed + 6))
        col = mix(col, lin('#33190f'), choc * bloom * 0.6)
        rough = 0.9 - 0.62 * jam - 0.55 * choc + 0.2 * choc * bloom
        sss = 0.16 + 0.36 * jam - 0.11 * choc
        spec = 0.3 + 0.7 * np.clip(jam + choc * 0.9, 0, 1)
        return col, rough, sss, spec

    lo, hi = -np.array([hx + 0.6 * MM, hh, hz + 0.6 * MM]), np.array([hx + 0.6 * MM, hh, hz + 0.6 * MM])
    return _bake(f'rainbow_{i}', f, lo, hi, (1.0 * MM, 0.36 * MM, 1.0 * MM), paint, smooth=1, flat=True, ao_strength=0.9)


# ------------------------------------------------------------------ Rice Krispies treat
def krispies(i):
    """puffed rice kernels (bubbly capsules) glued with glossy white marshmallow, cut into a lumpy cube"""
    rng = np.random.default_rng(3400 + i)
    h = rng.uniform(7.0, 8.4, 3) * MM
    ext = h + 0.6 * MM
    want = int(rng.integers(32, 41))
    pts = []
    for _ in range(6000):
        c = rng.uniform(-ext, ext)
        if np.max(np.abs(c) / h) < 0.6:
            continue                                       # kernels sit in the outer shell; the middle is marshmallow
        if all(np.linalg.norm(c - q) > 2.3 * MM for q in pts):
            pts.append(c)
            if len(pts) >= want:
                break
    nk = len(pts)
    KC = np.array(pts)
    KA = np.array([_unit(rng.normal(size=3)) for _ in range(nk)])
    KL = rng.uniform(1.1, 1.7, nk) * MM
    KR = rng.uniform(1.4, 1.85, nk) * MM
    toast = rng.random(nk)
    # strands of marshmallow between near neighbours
    pairs = [(a, b) for a in range(nk) for b in range(a + 1, nk) if np.linalg.norm(KC[a] - KC[b]) < 4.6 * MM]
    rng.shuffle(pairs)
    strands = [(KC[a] + KA[a] * rng.uniform(-0.6, 0.6) * KL[a], KC[b] + KA[b] * rng.uniform(-0.6, 0.6) * KL[b], rng.uniform(0.4, 0.55) * MM)
               for a, b in pairs[:14]]
    seed = int(rng.integers(0, 1000))

    def kern(P):
        K = np.empty((len(P), nk))
        for j in range(nk):
            K[:, j] = sd_capsule(P, KC[j] - KA[j] * KL[j], KC[j] + KA[j] * KL[j], KR[j])
        return K

    def bub(P):
        w1, _, _ = worley(P / (1.5 * MM), seed + 2)
        return -0.28 * MM * (1 - smoothstep(0.0, 0.65, w1))

    def f(P):
        K = kern(P)
        M = K[:, 0] - 0.22 * MM
        for j in range(1, nk):
            M = smin(M, K[:, j] - 0.22 * MM, 1.2 * MM)
        for a, b, r in strands:
            M = smin(M, sd_capsule(P, a, b, r), 0.5 * MM)
        M = smin(M, sd_box(P, 0, h - 1.7 * MM, 1.7 * MM) + 0.45 * MM * fbm(P / (2.2 * MM), 2, seed + 4), 0.9 * MM)   # the marshmallow body
        M = M + bub(P)
        cube = sd_box(P, 0, h, 1.7 * MM) + 0.25 * MM * fbm(P / (3.5 * MM), 2, seed + 3)
        return smax(M, cube, 0.9 * MM)

    kern_pale, kern_toast, kern_in, marsh = lin('#e9cf98'), lin('#cc9f5a'), lin('#f1e3c0'), lin('#fbf1da')

    def paint(V, N, field):
        K = kern(V)
        Kd = _sminv(K, 0.4 * MM)
        j = np.argmin(K, 1)
        wk = smoothstep(0.55 * MM, 0.2 * MM, Kd)
        tj = np.clip(toast[j] * 0.9 + 0.25 * vnoise(V / (1.4 * MM), seed + 7), 0, 1)
        kc = mix(kern_pale, kern_toast, smoothstep(0.35, 1.0, tj))
        shell = smoothstep(-0.55 * MM, -0.15 * MM, Kd)                       # cut through a kernel: toasted shell ring, pale airy middle
        kc = mix(kern_in, kc, np.where(Kd < 0, shell, 1.0))
        w1, _, _ = worley(V / (1.5 * MM), seed + 2)
        kc = kc * (0.78 + 0.34 * smoothstep(0.0, 0.7, w1))[:, None]          # the bubbly relief: pits toasted darker
        coat = smoothstep(0.55, 0.85, vnoise(V / (2.2 * MM), seed + 8)) * 0.55  # thin marshmallow coat over parts of a kernel
        col = mix(kc, marsh * (0.96 + 0.04 * vnoise(V / (1.3 * MM), seed + 9))[:, None], np.clip(1 - wk + coat * wk, 0, 1))
        wm = np.clip(1 - wk + coat * wk, 0, 1)
        rough = _lerp(0.72, 0.46, wm)
        sss = _lerp(0.12, 0.6, wm)
        spec = _lerp(0.4, 0.6, wm)
        return col, rough, sss, spec

    lo, hi = -ext, ext
    return _bake(f'krispies_{i}', f, lo, hi, 1.09 * MM, paint, smooth=1, ao_strength=0.85)


# ------------------------------------------------------------------ Oreo crumble
_OREO = [  # size mm, thickness mm, sides, cream smear, flat, voxel mm
    (13.5, 2.5, 6, True, True, 0.78),
    (12.0, 2.3, 6, False, True, 0.74),
    (10.5, 2.6, 5, True, True, 0.70),
    (9.5, 2.4, 6, False, True, 0.66),
    (8.5, 3.0, 6, True, False, 0.58),
    (7.5, 3.2, 7, False, False, 0.54),
    (6.5, 3.0, 7, True, False, 0.50),
    (5.0, 2.8, 8, False, False, 0.42),
]


def oreo(i):
    """a chip of chocolate wafer, broken on every side, some with a smear of cream filling on one face"""
    size, thk, nside, creamy, flat, vox = _OREO[i % len(_OREO)]
    rng = np.random.default_rng(3500 + i)
    Rx = size / 2 * MM
    Rz = Rx * rng.uniform(0.55, 0.85)
    th = thk * MM * rng.uniform(0.92, 1.08)
    Ry = rot_matrix(0, rng.uniform(0, TAU), 0)
    ang = (np.arange(nside) + rng.uniform(-0.3, 0.3, nside)) * TAU / nside
    tiltmax = 0.3 if flat else 0.8
    PN = []
    PO = []
    for a in ang:
        sup = math.hypot(Rx * math.cos(a), Rz * math.sin(a)) * rng.uniform(0.8, 0.98)
        n = _unit([math.cos(a), rng.uniform(-tiltmax, tiltmax), math.sin(a)])
        PN.append(n)
        PO.append(sup)
    PN = np.array(PN)
    PO = np.array(PO)
    bend = rng.uniform(-0.45, 0.45) * MM if flat else 0.0
    seed = int(rng.integers(0, 1000))
    if creamy:
        ox, oz = rng.uniform(-0.25, 0.25) * Rx, rng.uniform(-0.25, 0.25) * Rz
        rx, rz = Rx * rng.uniform(0.55, 0.9), Rz * rng.uniform(0.6, 0.95)
        ct = rng.uniform(0.55, 0.95) * MM

    def wafer(P):
        Q = P @ Ry
        x, y, z = Q[:, 0], Q[:, 1] + bend * (x_ := Q[:, 0] / Rx) ** 2, Q[:, 2]
        Qb = np.stack([x, y, z], 1)
        D = Qb @ PN.T - PO
        d = D[:, 0]
        for k in range(1, len(PO)):
            d = smax(d, D[:, k], 0.5 * MM)
        d = smax(d, np.abs(y) - th / 2, 0.45 * MM)
        d = d + 0.26 * MM * fbm(P / (1.0 * MM), 2, seed) + 0.12 * MM * vnoise(P / (0.5 * MM), seed + 1)
        return d, Qb, D

    def cream(P):
        d0, Qb, D = wafer(P)
        x, y, z = Qb[:, 0], Qb[:, 1], Qb[:, 2]
        e = np.hypot((x - ox) / rx, (z - oz) / rz) + 0.14 * fbm(P / (2.4 * MM), 2, seed + 2)
        t = (0.2 * MM + ct) * smoothstep(1.0, 0.82, e) * (0.88 + 0.24 * (0.5 + 0.5 * vnoise(P / (1.8 * MM), seed + 3)))     # a smear: thickest in the middle, feathered out
        top = th / 2 + t
        c = smax(y - top, (th / 2 - 0.5 * MM) - y, 0.2 * MM)
        inner = D[:, 0]
        for k in range(1, len(PO)):
            inner = smax(inner, D[:, k], 0.3 * MM)
        return smax(c, inner + 0.1 * MM, 0.3 * MM)

    def f(P):
        d0 = wafer(P)[0]
        return smin(d0, cream(P), 0.35 * MM) if creamy else d0

    t0 = rng.uniform()
    dark = mix(lin('#1d1514'), lin('#2b1f1a'), t0)
    light = mix(lin('#2e221d'), lin('#3d2d26'), t0)
    fract = lin('#5b4638')
    cream_c, cream_e, flecks = lin('#efe8d8'), lin('#ddd2b8'), lin('#3a2c25')

    def paint(V, N, field):
        d0 = wafer(V)[0]
        orig = smoothstep(0.55, 0.9, np.abs(N[:, 1]))
        w1, _, wid = worley(V / (0.7 * MM), seed + 4)
        grain = smoothstep(0.3, 0.1, w1) * (wid > 0.55)
        col = mix(light, dark, orig)
        col = mix(col, fract, grain * (0.35 + 0.5 * (1 - orig)) + 0.35 * (1 - orig) * (0.5 + 0.5 * vnoise(V / (1.0 * MM), seed + 8)))
        col = col * (0.9 + 0.2 * (0.5 + 0.5 * vnoise(V / (1.2 * MM), seed + 5)))[:, None]
        rough = 0.92 - 0.2 * orig
        spec = 0.15 + 0.15 * orig
        sss = np.full(len(V), 0.08)
        if creamy:
            dc = cream(V)
            wc = smoothstep(0.0, 0.14 * MM, d0 - dc)
            f1, _, fid = worley(V / (0.55 * MM), seed + 6)
            cc = mix(cream_c, cream_e, smoothstep(0.0, 0.5, 0.5 + 0.5 * vnoise(V / (1.5 * MM), seed + 7)))
            cc = mix(cc, flecks, smoothstep(0.2, 0.1, f1) * (fid > 0.72) * 0.8)
            col = mix(col, cc, wc)
            rough = _lerp(rough, 0.5, wc)
            spec = _lerp(spec, 0.6, wc)
            sss = _lerp(sss, 0.3, wc)
        return col, rough, sss, spec

    ex = size * MM / 2 + 1.5 * MM
    lo, hi = np.array([-ex, -th / 2 - 2.2 * MM, -ex]), np.array([ex, th / 2 + 2.6 * MM, ex])
    return _bake(f'oreo_{i}', f, lo, hi, vox * MM, paint, smooth=1, flat=flat, ao_strength=0.9)


# ------------------------------------------------------------------ mini chocolate chip cookie
def cookies(i):
    """a mini chocolate-chip cookie: golden edge, paler cracked top, dark chunks poking out"""
    rng = np.random.default_rng(3600 + i)
    R = rng.uniform(9.5, 11.0) * MM
    ht = rng.uniform(5.4, 6.6) * MM / 2
    seed = int(rng.integers(0, 1000))
    nch = int(rng.integers(5, 9))
    chunks = []
    cpos = []
    for j in range(nch * 12):
        if len(chunks) >= nch:
            break
        u = rng.uniform(0.0, 0.8) if len(chunks) < nch - 1 else rng.uniform(0.82, 0.95)
        a = rng.uniform(0, TAU)
        c = np.array([u * R * math.cos(a), 0.0, u * R * math.sin(a)])
        if any(np.linalg.norm(c - q) < 4.4 * MM for q in cpos):
            continue
        cpos.append(c)
        half = np.array([rng.uniform(1.4, 2.1), rng.uniform(0.9, 1.3), rng.uniform(1.3, 1.9)]) * MM
        Rm = rot_matrix(rng.uniform(-0.25, 0.25), rng.uniform(0, TAU), rng.uniform(-0.25, 0.25))
        chunks.append((c, half, Rm, rng.uniform(0.0, 0.6) * MM))

    def outline(P):
        th = np.arctan2(P[:, 2], P[:, 0])
        q = np.stack([np.cos(th) * 1.5, np.sin(th) * 1.5, np.full(len(th), 0.37)], 1)
        return R * (1 + 0.05 * vnoise(q, seed) + 0.02 * vnoise(q * 2.3 + 4, seed + 1))

    def tops(P):
        r = np.hypot(P[:, 0], P[:, 2])
        u = np.minimum(r / R, 1.2)
        return ht * (0.62 + 0.38 * (1 - u * u)), -ht * (0.9 - 0.25 * (1 - u * u)), u

    def crack(P):
        W = P + 0.7 * MM * np.stack([vnoise(P / (3 * MM), seed + 2), vnoise(P / (3 * MM) + 3, seed + 3), vnoise(P / (3 * MM) + 6, seed + 4)], 1)
        f1, f2, _ = worley(W / (6.2 * MM), seed + 5)
        return smoothstep(0.22, 0.05, f2 - f1)

    def dough(P):
        yt, yb, u = tops(P)
        cr = crack(P) * smoothstep(1.0, 0.45, u)
        d_side = np.hypot(P[:, 0], P[:, 2]) - outline(P) + 0.4 * MM * fbm(P / (1.5 * MM), 2, seed + 6)
        d_top = P[:, 1] - yt + 0.45 * MM * cr - 0.55 * MM * fbm(P / (3.0 * MM), 2, seed + 7)
        d_bot = yb - P[:, 1] + 0.12 * MM * fbm(P / (2 * MM), 2, seed + 8)
        return smax(smax(d_side, d_top, 1.8 * MM), d_bot, 1.2 * MM)

    def choc(P):
        d = np.full(len(P), 1e3)
        for c, half, Rm, dy in chunks:
            r = math.hypot(c[0], c[2])
            yt = ht * (0.62 + 0.38 * (1 - min(r / R, 1.2) ** 2))
            cc = np.array([c[0], yt - dy - 0.1 * MM, c[2]])
            d = smin(d, sd_box((P - cc) @ Rm, 0, half, 0.45 * MM) + 0.08 * MM * vnoise(P / (0.7 * MM), seed + 9), 0.2 * MM)
        return d

    def f(P):
        return smin(dough(P), choc(P), 0.45 * MM)

    c_edge, c_mid, c_dark, c_crack, c_bot = lin('#c78a45'), lin('#e8bf7f'), lin('#a8672d'), lin('#f1d8a2'), lin('#a56a30')
    choc_c, choc_b, smear = lin('#2a150c'), lin('#4c2c1a'), lin('#6b3f1e')

    def paint(V, N, field):
        yt, yb, u = tops(V)
        dd, dc = dough(V), choc(V)
        up = smoothstep(0.35, 0.8, N[:, 1])
        down = smoothstep(-0.4, -0.85, N[:, 1])
        mott = fbm(V / (2.2 * MM), 2, seed + 10)
        e = smoothstep(0.55, 0.96, u + 0.07 * mott)
        top = mix(c_mid, c_edge, e)
        cr = crack(V) * smoothstep(1.0, 0.45, u)
        top = mix(top, c_crack, cr * 0.8)
        lump = vnoise(V / (1.2 * MM), seed + 11)
        top = mix(top, lin('#b9792f'), smoothstep(0.25, 0.7, fbm(V / (2.6 * MM), 2, seed + 14)) * 0.55)   # browned patches
        top = top * (1 + 0.07 * mott + 0.05 * lump)[:, None]
        side = mix(c_edge, c_dark, smoothstep(0.2 * ht, -0.7 * ht, V[:, 1])) * (1 + 0.08 * mott)[:, None]
        col = mix(side, top, up)
        col = mix(col, c_bot, down * 0.9)
        # sugar-bright speckle on top
        f1, _, fid = worley(V / (0.8 * MM), seed + 12)
        col = mix(col, lin('#f5dfae'), smoothstep(0.18, 0.08, f1) * (fid > 0.7) * up * 0.5)
        col = mix(col, smear, smoothstep(0.8 * MM, 0.0, dc) * 0.55)          # melted chocolate smears the dough around a chunk
        wch = smoothstep(0.12 * MM, -0.10 * MM, dc - dd)
        cc = mix(choc_c, choc_b, smoothstep(0.3, 0.8, vnoise(V / (1.1 * MM), seed + 13)) * 0.7)
        col = mix(col, cc, wch)
        rough = _lerp(0.9 - 0.05 * up, 0.30, wch)
        spec = _lerp(0.3, 1.0, wch)
        sss = _lerp(0.14, 0.05, wch)
        return col, rough, sss, spec

    lo, hi = np.array([-R - 1.2 * MM, -ht - 1.5 * MM, -R - 1.2 * MM]), np.array([R + 1.2 * MM, ht + 2.0 * MM, R + 1.2 * MM])
    return _bake(f'cookies_{i}', f, lo, hi, 0.9 * MM, paint, smooth=1, flat=True, ao_strength=1.0)


PIECES = {
    'granola': dict(fn=granola, n=8, heap=dict(bowl='organic', over=0.012, phi=0.45, fast=True)),      # (the rigid-body run takes 20 minutes)
    'brownies': dict(fn=brownies, n=6, heap=dict(bowl='organic', over=0.012, phi=0.5)),
    'rainbow': dict(fn=rainbow, n=5, heap=dict(bowl='organic', over=0.012, phi=0.5)),
    'krispies': dict(fn=krispies, n=6, heap=dict(bowl='organic', over=0.012, phi=0.5)),
    'oreo': dict(fn=oreo, n=8, heap=dict(bowl='organic', over=0.012, phi=0.4, fast=True)),
    'cookies': dict(fn=cookies, n=5, heap=dict(bowl='organic', over=0.012, phi=0.5)),
}

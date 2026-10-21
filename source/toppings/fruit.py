"""Fresh fruit: strawberries, mango, pineapple, honeydew, kiwi, blueberries, grapes, dates, figs."""
import math

import numpy as np

from lib import (MM, fbm, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_cyl, sd_ellipsoid, sd_plane, sd_sphere,
                 smax, smin, smoothstep, vnoise, worley)
from lib import mesh_sdf


# ------------------------------------------------------------------ strawberry
def _berry(P, R, H, seed):
    """a whole strawberry: tip at the origin, calyx end up the y axis"""
    e1 = sd_ellipsoid(P, (0, 0.60 * H, 0), (R, 0.42 * H, R))
    e2 = sd_ellipsoid(P, (0, 0.26 * H, 0), (0.62 * R, 0.30 * H, 0.62 * R))
    d = smin(e1, e2, 4.5 * MM)
    d = smax(d, -sd_sphere(P, (0, H * 1.10, 0), R * 0.45), 1.5 * MM)      # the well the calyx sits in
    return d + 0.45 * MM * fbm(P / (7 * MM), 2, seed)


def strawberry(i, kind=None):
    rng = np.random.default_rng(1000 + i)
    kinds = ['chunk', 'chunk', 'quarter', 'chunk', 'slice', 'quarter', 'chunk', 'half']
    kind = kind or kinds[i % len(kinds)]
    R = rng.uniform(10.5, 12.5) * MM
    H = rng.uniform(24, 29) * MM
    berry = lambda P: _berry(P, R, H, i)

    def unit(v):
        v = np.asarray(v, dtype=float)
        return v / np.linalg.norm(v)

    if kind == 'chunk':
        # a dice cut from a berry; its box reaches the skin about half the time
        for _ in range(60):
            u = unit(rng.normal(size=3) * [1, 0.55, 1])
            c0 = np.array([0, 0.52 * H, 0])
            t = np.linspace(0, 1, 200)[:, None] * 22 * MM
            ray = c0 + u * t
            inside = berry(ray) < 0
            if inside.any():
                s = t[np.where(inside)[0][-1], 0]
                break
        depth = rng.uniform(2.4, 5.2) * MM if rng.random() < 0.62 else rng.uniform(5.5, 8.0) * MM
        ctr = c0 + u * (s - depth)
        half = rng.uniform(3.6, 5.0, 3) * MM
        Rm = rot_matrix(*rng.uniform(0, 6.28, 3))
        cut = lambda P: sd_box((P - ctr) @ Rm, 0, half, 0.45 * MM)
        lo, hi = ctr - np.max(half) * 1.8, ctr + np.max(half) * 1.8
        f = lambda P: smax(berry(P), cut(P), 0.5 * MM)
        voxel = 0.62 * MM
    elif kind == 'quarter':
        n1 = unit([-1, 0, rng.uniform(-0.22, 0.22)])
        n2 = unit([rng.uniform(-0.22, 0.22), 0, -1])
        top = H * rng.uniform(0.80, 1.05)
        o = rng.uniform(-0.9, 0.9, 2) * MM
        f = lambda P: smax(smax(berry(P), sd_plane(P, n1, o[0]), 0.5 * MM), smax(sd_plane(P, n2, o[1]), sd_plane(P, [0, 1, 0], top), 0.5 * MM), 0.5 * MM)
        lo, hi = np.array([-1, 0, -1]) * MM, np.array([R + MM, H * 1.05, R + MM])
        voxel = 0.8 * MM
    elif kind == 'half':
        n1 = unit([-1, 0, rng.uniform(-0.15, 0.15)])
        top = H * rng.uniform(0.82, 1.05)
        f = lambda P: smax(smax(berry(P), sd_plane(P, n1, rng.uniform(-0.5, 0.5) * MM), 0.5 * MM), sd_plane(P, [0, 1, 0], top), 0.5 * MM)
        lo, hi = np.array([-1, 0, -R - MM]) * MM * 1, np.array([R + MM, H * 1.05, R + MM])
        voxel = 0.85 * MM
    else:   # slice: a coin cut across the berry, a vertical cut makes it a half-moon
        y0 = H * rng.uniform(0.32, 0.62)
        th = rng.uniform(3.2, 4.4) * MM
        tilt = unit([rng.uniform(-0.12, 0.12), 1, rng.uniform(-0.12, 0.12)])
        half_moon = rng.random() < 0.5
        c = np.array([0, y0, 0])
        def f(P):
            d = smax(berry(P), np.abs((P - c) @ tilt) - th / 2, 0.45 * MM)
            return smax(d, sd_plane(P, [-1, 0, 0.1], 0.0), 0.5 * MM) if half_moon else d
        lo, hi = np.array([-R - MM, y0 - th - 2 * MM, -R - MM]), np.array([R + MM, y0 + th + 2 * MM, R + MM])
        voxel = 0.8 * MM

    red_deep, red, pink, core, seedc, dark = lin('#8d0b17'), lin('#c3111d'), lin('#ef7f88'), lin('#f7e4d9'), lin('#e9c260'), lin('#6e0912')

    def paint(V, N, field):
        d = -berry(V)                                   # depth below the skin
        skin = d < 0.5 * MM
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        rr = np.hypot(x, z)
        rn = rr / np.maximum(rr + np.maximum(d, 0), 1e-6)    # 0 on the axis, 1 at the skin
        ang = np.arctan2(z, x)
        fib = vnoise(np.stack([np.cos(ang) * 4.5, np.sin(ang) * 4.5, y / (4.5 * MM)], 1), 3)
        # flesh: pale core, pink, then the deep red outer layer; white fibres run out from the core
        flesh = mix(core, pink, smoothstep(0.08, 0.42, rn + 0.06 * fib))
        flesh = mix(flesh, red, smoothstep(0.42, 0.86, rn + 0.05 * fib))
        flesh = mix(flesh, red_deep, smoothstep(2.2 * MM, 0.5 * MM, d) * 0.7)
        flesh = mix(flesh, core, np.clip(fib * 0.35, 0, 1) * smoothstep(0.78, 0.3, rn) * 0.7)
        # skin: glossy red with the yellow seeds (achenes) each in a small dimple
        f1, f2, cid = worley(V / (2.25 * MM), 5)
        seed = smoothstep(0.2, 0.12, f1)
        ring = smoothstep(0.42, 0.18, f1)
        sk = mix(red, red_deep, 0.35 + 0.35 * fbm(V / (5 * MM), 2, 9))
        sk = mix(sk, dark, ring * 0.55)
        sk = mix(sk, seedc, seed)
        col = mix(flesh, sk, smoothstep(0.7 * MM, 0.15 * MM, d))
        rough = np.where(skin, 0.34 - 0.08 * seed, 0.15 + 0.06 * fbm(V / (2 * MM), 2, 4))
        sss = np.where(skin, 0.3, 0.7)
        return col, rough, sss, np.ones(len(V))

    return piece(f'strawberry_{i}', f, lo, hi, voxel, paint, smooth=2, cls='wet', ao_strength=0.9)


# ------------------------------------------------------------------ shared helpers for the cut fruit below
def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def _basis(a):
    """a unit vector and two unit vectors perpendicular to it"""
    a = _unit(a)
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    u = _unit(np.cross(a, t))
    return a, u, np.cross(a, u)


def _aniso(P, axis, across, along, seed, octaves=2):
    """noise in [-1, 1] stretched along `axis`: fibres. `across` / `along`: feature sizes (m) across and along the axis"""
    a, u, v = _basis(axis)
    q = np.stack([(P @ u) / across, (P @ v) / across, (P @ a) / along], -1)
    return fbm(q, octaves, seed)


def _convex(f, V, h):
    """Laplacian of the field: large and positive on convex edges and corners (where a thin piece lets light through)"""
    lap = -6.0 * f(V)
    for k in range(3):
        e = np.zeros(3)
        e[k] = h
        lap = lap + f(V + e) + f(V - e)
    return lap / (h * h)


def _mk(name, f, lo, hi, voxel, paint, budget=3400, **kw):
    """lib.piece, with the marching-cubes cell coarsened just enough to stay within the triangle budget"""
    for _ in range(3):
        n = len(mesh_sdf(f, lo, hi, voxel)[1])
        if n <= budget:
            break
        voxel *= math.sqrt(n / budget) * 1.01
    return piece(name, f, lo, hi, voxel, paint, **kw)


def _poly(P, ns, ds, k):
    """a convex solid from half-spaces n.p < d, edges rounded by the smooth max k"""
    d = None
    for n, o in zip(ns, ds):
        s = P @ n - o
        d = s if d is None else smax(d, s, k)
    return d


def _cut_block(rng, half, tilt=0.07, n_cham=3, cham=(0.9, 2.2), taper=0.0):
    """the half-spaces of a hand-cut dice: six faces tilted a few degrees off square, a few corner / edge chamfers.
    taper turns the two x faces towards each other going down z (a wedge cut from a ring)."""
    half = np.asarray(half, dtype=float)
    ns, ds = [], []
    for ax in range(3):
        for sg in (-1, 1):
            n = np.zeros(3)
            n[ax] = sg
            d0 = half[ax]
            if taper and ax == 0:
                n = np.array([sg * math.cos(taper), 0, -math.sin(taper)])
                d0 = half[0] * math.cos(taper)
            n = _unit(n + rng.normal(0, tilt, 3))
            ns.append(n)
            ds.append(d0 * rng.uniform(0.94, 1.06))
    for _ in range(n_cham):
        if rng.random() < 0.5:
            mask = np.ones(3)
        else:
            mask = np.ones(3)
            mask[rng.integers(0, 3)] = 0
        s = rng.choice([-1.0, 1.0], 3) * mask
        n = _unit(s)
        corner = (half * np.abs(s)).sum() / np.linalg.norm(s)
        ns.append(n)
        ds.append(corner - rng.uniform(*cham) * MM)
    return ns, ds


# ------------------------------------------------------------------ mango
def mango(i):
    """a hand-cut dice of golden (Ataulfo) mango: near-planar faces, rounded edges, a few chamfers, fibres in one direction"""
    rng = np.random.default_rng(2000 + i)
    L = rng.uniform(9.4, 12.6) * MM
    half = L / 2 * np.array([1.0, rng.uniform(0.70, 0.96), rng.uniform(0.64, 0.92)])
    ns, ds = _cut_block(rng, half, tilt=rng.uniform(0.05, 0.12), n_cham=int(rng.integers(2, 5)), cham=(0.9, 2.4))
    k = rng.uniform(0.6, 0.9) * MM
    wob = rng.uniform(0.1, 0.18) * MM
    fa = _unit(rng.normal(size=3) * [1, 1, 1])              # the fibre direction
    g = _unit(rng.normal(size=3))                           # ripeness gradient (towards the skin = deeper orange)
    ripe = [0.25, -0.2, 0.0, 0.3, -0.35, 0.1, -0.1, 0.4][i % 8]
    f = lambda P: _poly(P, ns, ds, k) + wob * fbm(P / (5 * MM), 2, 20 + i)
    deep, light, pale, dark = lin('#f0a000'), lin('#f8c424'), lin('#fdd958'), lin('#e48a00')
    ext = half.max() * 1.45 + 2 * MM

    def paint(V, N, field):
        fib = _aniso(V, fa, 1.25 * MM, 6 * MM, 40 + i, 2)
        fib2 = _aniso(V, fa, 2.2 * MM, 12 * MM, 70 + i)
        along = (V @ g) / L
        edge = smoothstep(120, 700, _convex(field, V, 0.6 * MM))
        t = 0.5 + 0.55 * fib2 + 0.38 * fib + 0.6 * along + ripe
        col = mix(deep, light, smoothstep(0.1, 0.95, t))
        col = mix(col, pale, smoothstep(0.15, 0.6, fib) * 0.75)           # pale fibre strands
        col = mix(col, dark, smoothstep(-0.15, -0.55, fib) * 0.65)        # deeper orange between them
        col = mix(col, light, edge * 0.5)                                 # thin edges glow
        rough = 0.15 + 0.05 * fib2 + 0.03 * (1 - edge) + 0.08 * smoothstep(0.2, 0.8, fib)
        sss = 0.55 + 0.3 * edge
        spec = 0.85 + 0.15 * edge
        return col, rough, sss, spec

    return _mk(f'mango_{i}', f, np.full(3, -ext), np.full(3, ext), 0.62 * MM, paint, smooth=1, cls='wet', ao_strength=0.8)


# ------------------------------------------------------------------ pineapple
def pineapple(i):
    """a chunk of pineapple: cuboids and wedges cut from a ring (a domed outer face), fibres along y, some with the pale
    woody core along one face"""
    rng = np.random.default_rng(3000 + i)
    kinds = ['cube', 'wedge', 'core', 'wedge', 'cube', 'wedge', 'core', 'tri']
    kind = kinds[i % len(kinds)]
    L = rng.uniform(11, 15) * MM
    half = L / 2 * np.array([rng.uniform(0.82, 1.0), 1.0, rng.uniform(0.62, 0.92)])
    taper = {'wedge': rng.uniform(0.18, 0.3), 'core': rng.uniform(0.08, 0.2)}.get(kind, rng.uniform(0, 0.05))
    n_cham = {'tri': 2, 'cube': 3}.get(kind, 2)
    ns, ds = _cut_block(rng, half, tilt=rng.uniform(0.04, 0.1), n_cham=n_cham, cham=(1.2, 3.0) if kind == 'tri' else (0.9, 2.4), taper=taper)
    k = rng.uniform(0.6, 0.9) * MM
    fa = _unit([rng.uniform(-0.12, 0.12), 1, rng.uniform(-0.12, 0.12)])
    core = kind == 'core'
    domed = kind in ('wedge', 'core', 'tri')
    zf = half[2]
    cw = rng.uniform(2.6, 4.2) * MM

    def f(P):
        d = _poly(P, ns, ds, k) + 0.065 * MM * _aniso(P, fa, 0.9 * MM, 7 * MM, 90 + i, 2) + 0.1 * MM * fbm(P / (6 * MM), 2, 100 + i)
        if domed:
            d = d - 0.9 * MM * np.clip(1 - (P[:, 0] / half[0]) ** 2, 0, 1) * smoothstep(zf - 3 * MM, zf, P[:, 2])
        return d

    light, mid, pale, dark = lin('#f9ec96'), lin('#f4dc5c'), lin('#fdf6c6'), lin('#ebc940')
    corec, coredk = lin('#f7efc2'), lin('#e8d890')
    ext = half.max() * 1.45 + 2 * MM

    def paint(V, N, field):
        fib = _aniso(V, fa, 1.0 * MM, 7 * MM, 120 + i, 2)
        fib2 = _aniso(V, fa, 2.6 * MM, 12 * MM, 150 + i)
        edge = smoothstep(120, 700, _convex(field, V, 0.6 * MM))
        t = 0.5 + 0.5 * fib + 0.45 * fib2
        col = mix(mid, light, smoothstep(0.15, 0.95, t))
        col = mix(col, pale, smoothstep(0.3, 0.8, fib) * 0.55)
        col = mix(col, dark, smoothstep(-0.2, -0.75, fib) * 0.45)
        rough = 0.25 + 0.1 * fib + 0.05 * (1 - edge)
        if core:
            cz = smoothstep(-zf + cw + 0.9 * MM, -zf + cw - 1.1 * MM, V[:, 2] + 0.9 * MM * fbm(V / (4 * MM), 2, 5 + i))
            wood = 0.5 + 0.5 * _aniso(V, fa, 0.9 * MM, 5 * MM, 170 + i, 2)
            cc = mix(corec, coredk, 0.6 * smoothstep(0.3, 0.8, wood))
            col = mix(col, cc, cz)
            rough = rough + 0.14 * cz
        col = mix(col, light, edge * 0.35)
        sss = 0.5 + 0.3 * edge
        return col, rough, sss, 0.8 + 0.2 * edge

    return _mk(f'pineapple_{i}', f, np.full(3, -ext), np.full(3, ext), 0.62 * MM, paint, smooth=1, cls='wet', ao_strength=0.8)


# ------------------------------------------------------------------ honeydew
def honeydew(i):
    """a scooped melon ball: a slightly oblate sphere with the flat spot and the ridge ring a baller leaves; a few halves"""
    rng = np.random.default_rng(4000 + i)
    half_ball = i in (2, 5)
    R = rng.uniform(8.5, 10.6) * MM
    rad = R * np.array([rng.uniform(0.96, 1.04), rng.uniform(0.9, 0.98), rng.uniform(0.96, 1.04)])
    s = _unit(rng.normal(size=3))                         # the flat spot where the scoop closed
    sd = rng.uniform(0.86, 0.92) * R
    ring = rng.uniform(0.75, 0.95)
    g = _unit(rng.normal(size=3))                         # towards the rind: greener
    cut_n = _unit(rng.normal(size=3))
    cut_d = rng.uniform(-0.1, 0.12) * R

    def f(P):
        d = sd_ellipsoid(P, 0, rad)
        u = P / np.maximum(np.linalg.norm(P, axis=-1, keepdims=True), 1e-9)
        ang = np.arccos(np.clip(u @ s, -1, 1))
        d = d - 0.2 * MM * np.exp(-((ang - ring) / 0.13) ** 2) * smoothstep(0.2, 0.6, ang)        # the baller's lip
        d = d - 0.14 * MM * np.exp(-((ang - 2.0) / 0.12) ** 2)
        d = d + 0.16 * MM * fbm(P / (4.5 * MM), 2, 200 + i)
        d = smax(d, P @ s - sd, 1.8 * MM)
        if half_ball:
            d = smax(d, P @ cut_n - cut_d, 1.0 * MM)
        return d + 0.07 * MM * vnoise(P / (0.9 * MM), 240 + i)

    green, cream, deep = lin('#d3e5a4'), lin('#eef4cd'), lin('#bfda86')
    ext = R * 1.15

    def paint(V, N, field):
        r = np.linalg.norm(V, axis=-1)
        t = (V @ g) / R * 0.5 + 0.5 + 0.3 * fbm(V / (5.5 * MM), 2, 210 + i)
        col = mix(cream, green, smoothstep(0.3, 0.9, t))
        col = mix(col, deep, smoothstep(0.4, 1.1, t) * 0.55 * smoothstep(0.5, 1.0, r / R))
        # faint radial fibres in the cut faces and a paler flat spot
        fib = _aniso(V, g, 1.6 * MM, 6 * MM, 220 + i)
        col = mix(col, cream, np.clip(0.5 * fib, 0, 0.4))
        ang = np.arccos(np.clip((V / np.maximum(r, 1e-9)[:, None]) @ s, -1, 1))
        col = mix(col, cream, 0.35 * smoothstep(0.55, 0.15, ang))
        rough = 0.10 + 0.04 * fbm(V / (3 * MM), 2, 230 + i)
        cutf = smoothstep(0.9 * MM, 0.2 * MM, np.abs(V @ cut_n - cut_d)) if half_ball else 0.0
        col = mix(col, mix(lin('#f1f6d6'), lin('#dcebb0'), smoothstep(0.2, 0.9, 0.5 + 0.5 * fib)), cutf * 0.85)
        rough = rough + 0.08 * cutf
        sss = (0.78 - 0.3 * cutf) * np.ones(len(V))
        return col, rough, sss, np.ones(len(V))

    return _mk(f'honeydew_{i}', f, np.full(3, -ext), np.full(3, ext), 0.7 * MM, paint, smooth=2, cls='wet', ao_strength=0.6)


# ------------------------------------------------------------------ kiwi
def _kiwi_color(Q, Rk, seed, ex=1.0, ez=0.88):
    """the cross-section of a peeled kiwi at points Q (kiwi frame: axis y, long axis of the oval x; Rk = radius):
    a white core, a halo of pale lime, pale rays out to the deep emerald outer flesh, and a ring of black seeds
    returns albedo, seed mask, core mask"""
    x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
    xe, ze = x / ex, z / ez
    rho = np.hypot(xe, ze)
    th = np.arctan2(ze, xe)
    rn = rho / Rk
    wob = fbm(np.stack([np.cos(th) * 1.5, np.sin(th) * 1.5, y / (5 * MM)], 1), 2, seed)
    outer, outer2, inner, pale, corec = lin('#79b72b'), lin('#8cc233'), lin('#a8cf4a'), lin('#d6e98f'), lin('#eef0c6')
    col = mix(outer, outer2, 0.5 + 0.5 * wob)
    col = mix(col, inner, smoothstep(0.9, 0.3, rn + 0.07 * wob))
    nr = int(max(14, round(2 * math.pi * Rk * 0.55 / (1.9 * MM))))
    ray = 0.5 + 0.5 * np.cos(th * nr + 2.4 * wob + 3.0 * vnoise(np.stack([th * 2, y / (6 * MM), np.zeros_like(y)], 1), seed + 5))
    ray = smoothstep(0.6, 0.95, ray) * smoothstep(0.1, 0.28, rn) * smoothstep(1.0, 0.5, rn)
    col = mix(col, pale, ray * 0.7)
    ce = np.hypot(xe / (0.27 * Rk), ze / (0.15 * Rk))
    col = mix(col, lin('#c4e07a'), smoothstep(2.6, 1.2, ce) * 0.5)
    core = smoothstep(1.3, 0.8, ce + 0.18 * wob)
    col = mix(col, corec, core)
    # seeds: two staggered rows round the core
    perim = 2 * math.pi * math.sqrt((0.56 * Rk) ** 2 + (0.3 * Rk) ** 2) / math.sqrt(2) * 1.0
    ns = int(max(10, round(perim / (1.5 * MM))))
    ph = np.arctan2(ze / (0.15 * Rk), xe / (0.27 * Rk))
    a = (ph / (2 * math.pi) + 1.0) * ns
    ia = np.floor(a)
    ys = 1.5 * MM
    odd = (ia % 2)
    yi = np.floor(y / ys + 0.5 * odd)
    ycen = (yi + 0.5 - 0.5 * odd) * ys
    phc = (ia + 0.5) * 2 * math.pi / ns
    cs = 2.05 + 0.2 * vnoise(np.stack([ia, yi, np.zeros_like(ia)], 1) * 3.7, seed + 9)
    xc, zc = 0.27 * Rk * cs * np.cos(phc), 0.15 * Rk * cs * np.sin(phc)
    rh = np.stack([xc, zc], -1)
    rl = np.maximum(np.linalg.norm(rh, axis=-1), 1e-9)
    rh = rh / rl[:, None]
    dx, dz = xe - xc, ze - zc
    dr = dx * rh[:, 0] + dz * rh[:, 1]
    dt = -dx * rh[:, 1] + dz * rh[:, 0]
    dy = y - ycen
    sr = float(np.clip(0.14 * Rk, 0.75 * MM, 1.25 * MM))
    q = (dr / sr) ** 2 + (dt / (0.6 * sr)) ** 2 + (dy / (1.05 * sr)) ** 2
    seeds = smoothstep(1.7, 0.3, q)
    col = mix(col, lin('#1a170b'), seeds * 0.95)
    return col, seeds, core


def kiwi(i):
    """peeled kiwi: dice cut from the flesh at different distances from the core, and thin slices (round and half-round)
    cut across the fruit, so every cut face shows the core, the pale rays and the ring of seeds"""
    rng = np.random.default_rng(5000 + i)
    kinds = ['dice', 'slice', 'dice', 'half', 'dice', 'slice', 'dice', 'half']
    kind = kinds[i % 8]
    flat = kind != 'dice'
    if kind == 'dice':
        Rk = rng.uniform(13, 17) * MM
        L = rng.uniform(9.2, 12.0) * MM
        half = L / 2 * np.array([1.0, rng.uniform(0.78, 0.95), rng.uniform(0.7, 0.9)])
        ns, ds = _cut_block(rng, half, tilt=rng.uniform(0.05, 0.1), n_cham=int(rng.integers(1, 4)), cham=(0.8, 1.9))
        k = rng.uniform(0.5, 0.7) * MM
        f = lambda P: _poly(P, ns, ds, k) + 0.1 * MM * fbm(P / (5 * MM), 2, 400 + i)
        ro = [0.2, 0.2, 0.42, 0.3, 0.62, 0.5, 0.3, 0.7][i % 8] * Rk
        ang = rng.uniform(0, 6.28)
        off = np.array([ro * math.cos(ang), rng.uniform(-3, 3) * MM, ro * math.sin(ang)])
        Rm = rot_matrix(rng.uniform(-0.5, 0.5), rng.uniform(0, 6.28), rng.uniform(-0.5, 0.5))
        ext = half.max() * 1.45 + 2 * MM
        lo, hi = np.full(3, -ext), np.full(3, ext)
        eaxes = (1.0, 0.88)
    else:
        Rk = rng.uniform(5.5, 6.1) * MM
        th = rng.uniform(4.0, 5.0) * MM
        ex, ez = rng.uniform(0.98, 1.06), rng.uniform(0.84, 0.9)
        tilt = _unit([rng.uniform(-0.06, 0.06), 1, rng.uniform(-0.06, 0.06)])
        cutn = _unit([math.cos(a0 := rng.choice([0.0, 1.5708]) + rng.uniform(-0.15, 0.15)), 0, math.sin(a0)])
        cuto = rng.uniform(-0.2, 0.5) * MM

        def f(P):
            sd2 = (np.hypot(P[:, 0] / (Rk * ex), P[:, 2] / (Rk * ez)) - 1.0) * Rk * ez * 0.95
            d = smax(sd2, np.abs(P @ tilt) - th / 2, 0.8 * MM)
            d = d + 0.1 * MM * fbm(P / (4 * MM), 2, 410 + i)
            if kind == 'half':
                d = smax(d, P @ cutn - cuto, 0.5 * MM)
            return d
        off = np.array([0.0, 0.0, 0.0]) + rng.uniform(-0.3, 0.3, 3) * MM
        Rm = np.eye(3)
        ext = Rk * 1.25
        lo, hi = np.array([-ext, -th, -ext]), np.array([ext, th, ext])
        eaxes = (ex, ez)

    def paint(V, N, field):
        Q = V @ Rm + off
        col, seeds, core = _kiwi_color(Q, Rk, 430 + i, *eaxes)
        edge = smoothstep(120, 700, _convex(field, V, 0.5 * MM))
        col = mix(col, lin('#a9d24c'), edge * 0.3)
        rough = 0.10 + 0.05 * fbm(V / (2.5 * MM), 2, 440 + i) + 0.12 * core - 0.03 * seeds
        sss = 0.7 - 0.5 * seeds + 0.2 * edge
        return col, rough, np.clip(sss, 0.05, 1), np.ones(len(V))

    return _mk(f'kiwi_{i}', f, lo, hi, 0.5 * MM, paint, smooth=0 if kind == 'dice' else 1, cls='wet', flat=flat, ao_strength=0.8)


# ------------------------------------------------------------------ blueberries
def _star(P, c, th0, n=5):
    """signed distance (roughly) to an n-pointed star in the xz plane, tips at radius c, valleys at 0.5 c"""
    th = np.arctan2(P[:, 2], P[:, 0]) - th0
    fr = th / (2 * math.pi) * n
    fr = fr - np.floor(fr)
    tri = np.abs(2 * fr - 1)                              # 0 at a tip, 1 in a valley
    r = c * (0.5 + 0.5 * (1 - tri ** 0.8))
    return (np.hypot(P[:, 0], P[:, 2]) - r) * 0.7


def blueberry(i):
    """a blueberry: a slightly flattened ball, a crown (a bowl with five dry calyx lobes) on top, the stem scar underneath,
    patchy white-blue bloom over deep blue skin; a few dented or wrinkled"""
    rng = np.random.default_rng(6000 + i)
    R = rng.uniform(5.5, 7.4) * MM
    sx, sz = rng.uniform(0.95, 1.05), rng.uniform(0.94, 1.04)
    b = R * rng.uniform(0.82, 0.92)
    wrinkled = i in (3, 6)
    dented = i in (5, 6)
    c = rng.uniform(0.36, 0.42) * R                   # crown radius (tip of a lobe)
    cs = 1.5 * c
    bowl_c = np.array([0, b + cs - rng.uniform(0.9, 1.2) * MM, 0])
    th0 = rng.uniform(0, 6.28)
    cover = [0.62, 0.5, 0.72, 0.3, 0.58, 0.66, 0.25, 0.78][i % 8]
    dent_c = None
    if dented:
        dd = _unit([rng.normal(), rng.uniform(-0.6, 0.3), rng.normal()])
        dent_r = rng.uniform(3.2, 4.2) * MM
        dent_c = dd * (R + dent_r - rng.uniform(0.9, 1.5) * MM)
    tooth_a = [th0 + k * 2 * math.pi / 5 for k in range(5)]

    def f(P):
        d = sd_ellipsoid(P, 0, (R * sx, b, R * sz))
        d = d + 0.25 * MM * fbm(P / (7 * MM), 2, 500 + i)
        if wrinkled:
            n = _aniso(P, [0, 1, 0], 2.2 * MM, 7 * MM, 510 + i, 1)
            d = d + 0.32 * MM * smoothstep(0.4, 0.0, np.abs(n)) + 0.2 * MM * fbm(P / (3.5 * MM), 1, 520 + i)
        if dented:
            d = smax(d, -sd_sphere(P, dent_c, dent_r), 1.6 * MM)
        d2 = _star(P, c, th0)
        cav = smax(sd_sphere(P, bowl_c, cs), d2, 0.25 * MM)                    # the crown: a five-pointed star sunk into the top
        d = smax(d, -cav, 0.3 * MM)
        d = d - 0.28 * MM * np.exp(-((d2 - 0.35 * MM) / (0.45 * MM)) ** 2) * smoothstep(b - 1.5 * MM, b - 0.3 * MM, P[:, 1])   # its raised lip
        d = smax(d, -sd_sphere(P, (0, -b - 0.25 * MM, 0), 1.0 * MM), 0.45 * MM)     # the stem scar
        return d

    deep, deep2, bloom, bloom2 = lin('#27315a'), lin('#2e2a5c'), lin('#7c88b0'), lin('#98a3c6')
    dry, dry2 = lin('#1c1626'), lin('#3a3244')
    ext = R * 1.2
    lo, hi = np.array([-ext, -b - MM, -ext]), np.array([ext, b + 2.2 * MM, ext])

    def paint(V, N, field):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        rho = np.hypot(x, z)
        n1 = fbm(V / (4.5 * MM), 3, 530 + i)
        n2 = fbm(V / (1.0 * MM), 2, 540 + i)
        dcrown = np.linalg.norm(V - bowl_c, axis=-1)
        incrown = smoothstep(0.3 * MM, -0.35 * MM, _star(V, c, th0)) * smoothstep(b - 2.2 * MM, b - 0.9 * MM, y)
        halo = smoothstep(c * 2.4, c * 1.0, np.hypot(x, z)) * smoothstep(b * 0.2, b * 0.8, y) * (1 - incrown)   # bloom piles up round the crown
        scar = smoothstep(1.7 * MM, 0.9 * MM, rho) * smoothstep(-b + 2.2 * MM, -b + 0.8 * MM, y)
        pole = smoothstep(b * 0.5, b * 0.95, np.abs(y))
        bl = smoothstep(-0.25, 0.45, 0.55 * n1 + (cover - 0.45) * 1.6 + 0.3 * n2 + 0.35 * halo + 0.2 * pole)
        base = mix(deep, deep2, 0.5 + 0.5 * fbm(V / (4 * MM), 2, 550 + i))
        col = mix(base, mix(bloom, bloom2, smoothstep(0.2, 0.9, n2 + 0.3)), bl * 0.9)
        drycol = mix(mix(dry2, dry, smoothstep(b - 0.2 * MM, b - 1.1 * MM, y)), lin('#6a5a58'), 0.3 * fbm(V / (0.8 * MM), 2, 560 + i) + 0.22 + 0.4 * smoothstep(0.9 * MM, 0.0, np.abs(_star(V, c, th0) + 0.3 * MM)))
        col = mix(col, drycol, incrown * 0.92)
        col = mix(col, lin('#7a6650'), scar * 0.9)
        rough = np.where(bl > 0.5, 0.58, 0.16) * (1 - 0) + 0.0
        rough = 0.16 + 0.46 * smoothstep(0.15, 0.85, bl) + 0.05 * n2
        rough = np.clip(rough * (1 - incrown) + 0.85 * incrown, 0.05, 1)
        sss = 0.22 * (1 - incrown) + 0.05 * incrown
        spec = (1.0 - 0.7 * smoothstep(0.2, 0.9, bl)) * (1 - 0.8 * incrown)
        return col, rough, sss, spec

    return _mk(f'blueberries_{i}', f, lo, hi, 0.55 * MM, paint, smooth=2, cls='matte', ao_strength=1.0)


# ------------------------------------------------------------------ grapes
def grape(i):
    """a green seedless grape: an egg-shaped, translucent berry with a stem-scar nub at one pole; a few cut lengthwise"""
    rng = np.random.default_rng(7000 + i)
    half_kind = i in (3, 6)
    a = rng.uniform(8.2, 11.0) * MM
    b = a * rng.uniform(0.72, 0.86)
    egg = rng.uniform(0.04, 0.1)
    bz = b * rng.uniform(0.96, 1.04)
    cut_n = _unit([1, rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)])
    cut_d = rng.uniform(-0.4, 0.5) * MM

    def body(P):
        q = P.copy()
        s = 1 + egg * np.clip(P[:, 1] / a, -1, 1)
        q[:, 0] = q[:, 0] / s
        q[:, 2] = q[:, 2] / s
        return sd_ellipsoid(q, 0, (b, a, bz)) * 0.95

    def f(P):
        d = body(P) + 0.14 * MM * fbm(P / (6 * MM), 2, 600 + i)
        nub = sd_capsule(P, (0, a - 1.0 * MM, 0), (0, a + 0.55 * MM, 0), 1.05 * MM)
        d = smin(d, nub, 1.2 * MM)
        if half_kind:
            d = smax(d, P @ cut_n - cut_d, 0.5 * MM)
        return d

    g1, g2, gc = lin('#bddb66'), lin('#dfeb96'), lin('#dfeaa8')
    flesh, flesh2, rim = lin('#f0f7d0'), lin('#dcec9c'), lin('#a8c850')
    ext = a * 1.1
    lo, hi = np.array([-ext, -a - 2 * MM, -ext]), np.array([ext, a + 3 * MM, ext])

    def paint(V, N, field):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        t = 0.5 + 0.5 * fbm(V / (6 * MM), 2, 610 + i) + 0.2 * (y / a)
        col = mix(g1, g2, smoothstep(0.2, 0.9, t))
        # faint pale veins running pole to pole
        th = np.arctan2(z, x)
        vein = vnoise(np.stack([np.cos(th) * 3.0, np.sin(th) * 3.0, y / (7 * MM)], 1), 620 + i)
        col = mix(col, g2, smoothstep(0.2, 0.8, vein) * 0.35)
        bl = smoothstep(0.1, 0.6, fbm(V / (2.4 * MM), 3, 630 + i) + 0.1)
        col = mix(col, lin('#e6eed0'), bl * 0.35)
        rho = np.hypot(x, z)
        top = smoothstep(a - 2.6 * MM, a - 0.4 * MM, y)
        nubm = top * smoothstep(1.6 * MM, 0.9 * MM, rho)
        col = mix(col, lin('#7b7a38'), nubm * 0.85)
        ring = top * smoothstep(3.0 * MM, 1.6 * MM, rho) * (1 - nubm)
        col = mix(col, lin('#a9bf58'), ring * 0.5)
        bot = smoothstep(-a + 1.8 * MM, -a + 0.3 * MM, y) * smoothstep(1.2 * MM, 0.3 * MM, rho)
        col = mix(col, lin('#7e7a3a'), bot * 0.7)
        rough = 0.12 + 0.28 * bl * 0.6 + 0.2 * nubm
        sss = 0.86 * np.ones(len(V))
        spec = 1.0 - 0.3 * bl
        if half_kind:
            cf = smoothstep(0.55 * MM, 0.1 * MM, np.abs(V @ cut_n - cut_d))
            # on the cut face: the pale axis, a thin darker rim, translucent green flesh
            r2 = np.hypot(z, 0)  # across the face
            dsk = -body(V)
            cc = mix(flesh2, flesh, smoothstep(5.5 * MM, 0.5 * MM, np.hypot(z, y * 0.0 + 0.0)))
            axis = smoothstep(2.0 * MM, 0.4 * MM, np.abs(z)) * smoothstep(a * 0.95, a * 0.2, np.abs(y))
            cc = mix(cc, lin('#f1f6d4'), axis * 0.8)
            ray = 0.5 + 0.5 * np.cos(np.arctan2(y, z + 1e-6) * 7 + 2 * fbm(V / (3 * MM), 2, 640))
            cc = mix(cc, flesh, smoothstep(0.6, 0.95, ray) * 0.4)
            cc = mix(cc, rim, smoothstep(1.3 * MM, 0.2 * MM, dsk) * 0.8)
            col = mix(col, cc, cf)
            rough = rough + 0.08 * cf
            sss = sss * (1 - 0.5 * cf)
        return col, rough, sss, spec

    return _mk(f'grapes_{i}', f, lo, hi, 0.7 * MM, paint, smooth=2, cls='jelly', ao_strength=0.6)


# ------------------------------------------------------------------ dates
def date(i):
    """a Medjool date chopped up: crosswise rounds (halved, quartered), lengthwise strips and hand-cut chunks, with the
    wrinkled sticky dark skin, the caramel fibrous cut faces and the channel the stone left"""
    rng = np.random.default_rng(8000 + i)
    kinds = ['half', 'quarter', 'chunk', 'end', 'strip', 'half', 'chunk', 'quarter']
    kind = kinds[i % 8]
    a, b, c = rng.uniform(15.5, 17.5) * MM, rng.uniform(8.6, 9.8) * MM, rng.uniform(7.8, 9.0) * MM
    bend = rng.uniform(-0.12, 0.12) * a
    taper = rng.uniform(-0.12, 0.12)
    amp = rng.uniform(0.55, 0.8) * MM
    roll = rng.uniform(0, 6.28)

    def whole(P):
        q = P.copy()
        q[:, 1] = q[:, 1] - bend * (P[:, 0] / a) ** 2
        s = 1 + taper * np.clip(P[:, 0] / a, -1, 1)
        q[:, 1] = q[:, 1] / s
        q[:, 2] = q[:, 2] / s
        return sd_ellipsoid(q, 0, (a, b, c)) * 0.92

    def skin_field(P):
        n = _aniso(P, [1, 0, 0], 2.3 * MM, 6.5 * MM, 700 + i, 2)
        n2 = _aniso(P, [0.15, 0.3, 1], 4 * MM, 3 * MM, 710 + i, 2)
        gr = smoothstep(0.26, 0.0, np.abs(n)) * 0.75 + smoothstep(0.22, 0.0, np.abs(n2)) * 0.4
        return whole(P) + amp * gr + 0.4 * MM * fbm(P / (7 * MM), 2, 720 + i), gr

    def pit(P):
        q = P - np.array([0, 0.3 * MM + bend * 0.0, 0])
        q[:, 1] = q[:, 1] - bend * (P[:, 0] / a) ** 2
        return sd_ellipsoid(q, 0, (a * 0.85, 3.2 * MM, 2.8 * MM))

    c0 = rng.uniform(-3.5, 3.5) * MM                            # where the crosswise cut falls
    th = rng.uniform(9.5, 12.5) * MM                            # thickness of a round
    tx = _unit([1.0, rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06)])
    roll_n = np.array([0, math.cos(roll), math.sin(roll)])
    roll_m = np.array([0, -math.sin(roll), math.cos(roll)])
    off0, off1 = rng.uniform(-1.6, 1.6, 2) * MM
    if kind == 'end':
        c0 = a - 11.5 * MM
    pits_on = kind != 'chunk' or rng.random() < 0.4

    if kind == 'chunk':
        L = rng.uniform(10, 14) * MM
        half = L / 2 * np.array([rng.uniform(0.85, 1.0), 1.0, rng.uniform(0.7, 0.95)])
        ns, ds = _cut_block(rng, half, tilt=0.07, n_cham=2, cham=(1.0, 2.2))
        Rm = rot_matrix(*rng.uniform(0, 6.28, 3))
        ctr = np.array([rng.uniform(-4, 4) * MM, rng.uniform(-1, 1) * MM, rng.uniform(-1.5, 1.5) * MM])
        cutf = lambda P: _poly((P - ctr) @ Rm, ns, ds, 0.7 * MM)
    else:
        def cutf(P):
            x = P @ tx
            if kind == 'end':                       # the tip of the date, halved
                d = smax(c0 - x, P @ roll_n - off0, 0.5 * MM)
            elif kind == 'strip':                   # a lengthwise quarter, 15 mm long
                d = smax(x - (c0 + 7.5 * MM), -x + (c0 - 7.5 * MM), 0.5 * MM)
                d = smax(smax(d, P @ roll_n - off0, 0.5 * MM), P @ roll_m - off1, 0.5 * MM)
            else:                                   # a crosswise round, halved or quartered
                d = smax(x - (c0 + th / 2), -x + (c0 - th / 2), 0.5 * MM)
                d = smax(d, P @ roll_n - off0, 0.5 * MM)
                if kind == 'quarter':
                    d = smax(d, P @ roll_m - off1, 0.5 * MM)
            return d

    def f(P):
        d, _ = skin_field(P)
        d = smax(d, cutf(P), 0.5 * MM)
        if pits_on:
            d = smax(d, -pit(P), 0.45 * MM)
        return d

    skin_d, skin_l, skin_b = lin('#2a1409'), lin('#5e3316'), lin('#6c4424')
    cara, cara_d, cara_l = lin('#835023'), lin('#52290f'), lin('#b07a3c')
    ext_hi = np.array([a + 2 * MM, b + abs(bend) + 2 * MM, c + 2 * MM])
    lo, hi = -ext_hi, ext_hi

    def paint(V, N, field):
        sd, gr = skin_field(V)
        depth = -sd                                           # below the (wrinkled) skin
        fib = _aniso(V, [1, 0.05, 0.03], 1.3 * MM, 6 * MM, 730 + i, 2)
        fib2 = _aniso(V, [1, 0.05, 0.03], 2.4 * MM, 9 * MM, 740 + i)
        skin = smoothstep(0.55 * MM, 0.1 * MM, depth)
        crest = np.clip(1 - gr, 0, 1) * smoothstep(0.1, 0.6, fbm(V / (2.2 * MM), 2, 750 + i) + 0.55)
        sk = mix(skin_d, skin_l, crest * 0.9)
        sugar = smoothstep(0.35, 0.65, fbm(V / (4 * MM), 3, 760 + i)) * 0.55
        sk = mix(sk, skin_b, sugar * crest)
        flesh = mix(cara_d, cara, smoothstep(0.0, 2.4 * MM, depth))
        flesh = mix(flesh, cara_l, smoothstep(0.1, 0.7, 0.55 * fib + 0.45 * fib2) * 0.85)
        flesh = mix(flesh, cara_d, smoothstep(-0.1, -0.6, fib) * 0.7)
        if pits_on:
            pd = pit(V)
            lum = smoothstep(0.6 * MM, 0.0, pd) * (1 - skin)
            flesh = mix(flesh, lin('#5a2e16'), lum * 0.75)
        else:
            lum = 0.0
        col = mix(flesh, sk, skin)
        rough = np.where(skin > 0.5, 0.36 + 0.25 * sugar * crest + 0.08 * (1 - crest), 0.22 + 0.1 * fib2)
        rough = rough + 0.25 * lum
        sss = np.where(skin > 0.5, 0.08, 0.15)
        return col, rough, sss, np.where(skin > 0.5, 0.85, 1.0)

    return _mk(f'dates_{i}', f, lo, hi, 0.7 * MM, paint, smooth=2, cls='wet', ao_strength=0.8)


# ------------------------------------------------------------------ figs
def _fig(P, R, H, seed):
    """a whole black mission fig, calyx (stem) end up the y axis, base at the origin"""
    bulb = sd_ellipsoid(P, (0, 0.40 * H, 0), (R, 0.40 * H, R))
    neck = sd_ellipsoid(P, (0, 0.76 * H, 0), (0.68 * R, 0.25 * H, 0.68 * R))
    d = smin(bulb, neck, 0.55 * R)
    d = smax(d, P[:, 1] - 0.97 * H, 1.5 * MM)
    stem = sd_capsule(P, (0, 0.95 * H, 0), (0, 1.03 * H, 0), 1.6 * MM)
    d = smin(d, stem, 1.0 * MM)
    d = smax(d, -sd_sphere(P, (0, -0.3 * MM, 0), 1.2 * MM), 0.7 * MM)
    return d * 0.95 + 0.3 * MM * fbm(P / (7 * MM), 2, seed)


def fig(i):
    """a fresh black mission fig, quartered: purple-black bloomy skin, a thin pale rind, pink-red flesh round a darker
    magenta centre, full of tiny golden seeds"""
    rng = np.random.default_rng(9000 + i)
    kinds = ['quarter', 'quarter', 'low', 'quarter', 'high', 'low', 'quarter', 'eighth']
    kind = kinds[i % 8]
    R = rng.uniform(10.8, 12.4) * MM
    H = rng.uniform(22, 26) * MM
    whole = lambda P: _fig(P, R, H, 800 + i)
    ca = rng.uniform(-0.2, 0.2)
    n1 = _unit([-math.cos(ca), 0, -math.sin(ca)])
    n2 = _unit([-math.sin(ca) * 1.0, 0, math.cos(ca)]) * -1
    n1, n2 = _unit([-1, 0, rng.uniform(-0.15, 0.15)]), _unit([rng.uniform(-0.15, 0.15), 0, -1])
    o1, o2 = rng.uniform(-0.6, 0.6, 2) * MM
    ylo = {'low': 0.0, 'high': H * rng.uniform(0.38, 0.48)}.get(kind, 0.0)
    yhi = {'low': H * rng.uniform(0.6, 0.7), 'high': H * 1.05}.get(kind, H * rng.uniform(0.9, 1.05))
    n3 = _unit([1, 0, 0.55 * rng.choice([-1, 1]) + rng.uniform(-0.15, 0.15)])
    o3 = rng.uniform(1.5, 2.5) * MM

    def f(P):
        d = smax(whole(P), smax(P @ n1 - o1, P @ n2 - o2, 0.5 * MM), 0.4 * MM)
        if kind == 'eighth':
            d = smax(d, P @ n3 - o3 - 0.3 * R, 0.5 * MM)
        if ylo > 0:
            d = smax(d, -(P[:, 1] - ylo), 0.5 * MM)
        d = smax(d, P[:, 1] - yhi, 0.5 * MM)
        return d

    skin_a, skin_b, bloomc = lin('#2b1230'), lin('#4a2548'), lin('#9a8fb0')
    rind, pink, red, mag, seedc, deepm = lin('#eadfcb'), lin('#e5667a'), lin('#c93a4d'), lin('#8d1f55'), lin('#e8c878'), lin('#6a1744')
    lo, hi = np.array([-MM, ylo - 2 * MM if ylo else -2 * MM, -MM]), np.array([R + 2 * MM, yhi + 3 * MM, R + 2 * MM])
    lo[0] = lo[2] = -R * 0.4 if kind == 'eighth' else -1.5 * MM
    lo[0] = lo[2] = -1.5 * MM
    vox = 0.7 * MM

    def paint(V, N, field):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        d = -whole(V)
        rr = np.hypot(x, z)
        rn = rr / np.maximum(rr + np.maximum(d, 0), 1e-6)
        ang = np.arctan2(z, x)
        fib = vnoise(np.stack([np.cos(ang) * 5.0, np.sin(ang) * 5.0, y / (5 * MM)], 1), 3)
        skin = smoothstep(0.95 * MM, 0.05 * MM, d)
        # flesh from the pale rind in, through pink and red, to the dark magenta centre
        fl = mix(mag, red, smoothstep(0.2, 0.62, rn + 0.1 * fib))
        fl = mix(fl, pink, smoothstep(0.68, 0.95, rn + 0.06 * fib) * 0.9)
        fl = mix(fl, deepm, smoothstep(0.34, 0.0, rn) * 0.7)
        fl = mix(fl, rind, smoothstep(2.0 * MM, 0.9 * MM, d))
        fl = mix(fl, pink, np.clip(fib * 0.6, 0, 1) * smoothstep(0.9, 0.25, rn) * 0.6)
        f1, f2, cid = worley(V / (1.3 * MM), 17 + i)
        seeds = smoothstep(0.4, 0.14, f1) * smoothstep(1.8 * MM, 2.8 * MM, d) * smoothstep(0.02, 0.1, rn)
        fl = mix(fl, seedc, seeds * 0.85)
        # skin: purple-black, ribbed lighter lines, patches of pale bloom
        bl = smoothstep(0.0, 0.5, fbm(V / (2.6 * MM), 3, 820 + i) + 0.2)
        rib = vnoise(np.stack([np.cos(ang) * 3.2, np.sin(ang) * 3.2, y / (9 * MM)], 1), 830 + i)
        sk = mix(skin_a, skin_b, 0.5 + 0.5 * fbm(V / (4 * MM), 2, 840 + i) + 0.25 * rib)
        sk = mix(sk, bloomc, bl * 0.55)
        sk = mix(sk, lin('#6e6a3a'), smoothstep(H * 0.92, H * 1.0, y) * 0.8)
        col = mix(fl, sk, skin)
        rough = np.where(skin > 0.5, 0.4 + 0.25 * bl, 0.13 + 0.06 * fib)
        rough = rough + 0.0
        sss = np.where(skin > 0.5, 0.2, 0.7)
        spec = np.where(skin > 0.5, 1.0 - 0.4 * bl, 1.0)
        return col, rough, sss, spec

    return _mk(f'figs_{i}', f, lo, hi, vox, paint, budget=3400, smooth=2, cls='wet', ao_strength=0.9)


# key (the bar's topping key) -> piece builder, how many variants, how its heap is laid (None: scattered by the page)
PIECES = {
    'strawberry': dict(fn=strawberry, n=8, heap=dict(bowl='hobnail', over=0.014, phi=0.50)),
    'mango': dict(fn=mango, n=8, heap=dict(bowl='organic', over=0.012, phi=0.50)),
    'pineapple': dict(fn=pineapple, n=8, heap=dict(bowl='organic', over=0.012, phi=0.50)),
    'honeydew': dict(fn=honeydew, n=7, heap=dict(bowl='organic', over=0.012, phi=0.57)),
    'kiwi': dict(fn=kiwi, n=8, heap=dict(bowl='organic', over=0.012, phi=0.50)),
    'blueberries': dict(fn=blueberry, n=8, heap=dict(bowl='organic', over=0.012, phi=0.58)),
    'grapes': dict(fn=grape, n=8, heap=dict(bowl='organic', over=0.012, phi=0.57)),
    'dates': dict(fn=date, n=8, heap=dict(bowl='organic', over=0.012, phi=0.50)),
    'figs': dict(fn=fig, n=8, heap=dict(bowl='organic', over=0.012, phi=0.50)),
}

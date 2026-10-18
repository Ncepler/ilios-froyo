"""Fresh fruit: strawberries, mango, pineapple, honeydew, kiwi, blueberries, grapes, dates, figs."""
import math

import numpy as np

from lib import (MM, fbm, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_ellipsoid, sd_plane, sd_sphere, smax,
                 smin, smoothstep, vnoise, worley)


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


# key (the bar's topping key) -> piece builder, how many variants, how its heap is laid (None: scattered by the page)
PIECES = {
    'strawberry': dict(fn=strawberry, n=8, heap=dict(bowl='hobnail', over=0.014, phi=0.50)),
}

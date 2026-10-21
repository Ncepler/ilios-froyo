"""The bowls' insides, as numbers: the page's bowlGeometry (site/bar-heap.js) without three.js. Used by fill.py (and heap.py's
Blender runs have their own copy of the profile). Y up, origin at the bowl's centre on the counter."""
import math

import numpy as np

BOWLS = {
    # R (rim radius), H (height), base radius, profile exponent: the page's bowlGeometry
    'organic': dict(R=0.102, H=0.070, base=0.060, p=1.2, wobble=0.06),
    'hobnail': dict(R=0.095, H=0.085, base=0.055, p=0.8, wobble=0.0),
}


def inner_profile(kind, n=22):
    """(radius, height) of the bowl's inside, from the floor to the rim (bowlGeometry's inner wall, 6 mm in from the outer)"""
    b = BOWLS[kind]
    r, y = [], []
    for i in range(n + 1):
        t = i / n
        r.append(max(b['base'] + (b['R'] - b['base']) * math.sin(t * math.pi / 2) ** b['p'] - 0.006, 0.0))
        y.append(t * b['H'] + 0.006 * (1 - t) + (0.006 if i == 0 else 0))
    for i in range(1, len(y)):
        y[i] = max(y[i], y[i - 1])
    return np.array(r), np.array(y)


def wall_radius(kind, y, a=None, seed=0.0):
    """radius of the wall at height y (above the rim: the rim's) and angle a; a=None leaves the wavy rim out.
    The organic bowls are drawn with a rim that swells in and out: radius * (1 + 0.06 sin(3a + seed) t^2), t = y / H."""
    b = BOWLS[kind]
    r, ys = inner_profile(kind)
    y = np.asarray(y, dtype=float)
    base = np.interp(y, ys, r)
    if a is None or not b['wobble']:
        return base if base.ndim else float(base)
    t = np.clip(y / b['H'], 0, 1)
    out = base * (1 + b['wobble'] * np.sin(3 * np.asarray(a) + seed) * t * t)
    return out if out.ndim else float(out)


def floor_height(kind, rr):
    """the bowl's inside surface as a height over radius rr (flat in the middle)"""
    r, ys = inner_profile(kind)
    return np.interp(rr, r, ys)


def target_at(T, cx, cz, cells):
    ix, iz = cells(np.array([cx]), np.array([cz]))
    return float(T[ix[0], iz[0]])

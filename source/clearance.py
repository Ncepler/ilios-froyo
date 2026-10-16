"""Does the cup (and the froyo in it) ever touch the dispenser, tray or room while the page plays?

    python clearance.py <machine.glb> <room.glb> <pour-path.json> <mpm_dir> [clear_mm]

The cup's position at each scroll progress is rebuilt exactly as main.js pose() does (slide under the spout, rise to it,
follow the simulated hand, lower to the tray), for each of the three handles.
Surface points are sampled on every dispenser/room mesh; the cup is its true outer envelope (solid of
revolution, rim bead included) plus the simulated froyo (particle cloud padded by half a particle).
Reports the worst intrusion per part. Contact with the tray at the very start/end (cup standing on it) is allowed.
"""
import json
import math
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

import analyze

machine_p, room_p, pp_path, mpm_d = sys.argv[1:5]
CLEAR = float(sys.argv[5]) / 1000 if len(sys.argv) > 5 else 0.002

def surface_points(path, n_per_m2=2.0e6, cap=60000):
    sc = trimesh.load(path, force="scene")
    pts, names = [], []
    for node in sc.graph.nodes_geometry:
        T, gname = sc.graph[node]
        g = sc.geometry[gname].copy()
        g.apply_transform(T)
        if g.area < 1e-9:
            continue
        n = int(min(cap, max(60, g.area * n_per_m2)))
        p, _ = trimesh.sample.sample_surface(g, n)
        pts.append(p)
        names += [node] * len(p)
    return np.vstack(pts), np.array(names)

P_m, N_m = surface_points(machine_p)
P_r, N_r = surface_points(room_p, n_per_m2=2.0e5, cap=20000)
P = np.vstack([P_m, P_r])
N = np.concatenate([N_m, N_r])
# the stack of spare cups and the sample cups are props away from the path
skip = np.array([n.startswith(("Cup", "Emblem", "SampleCup")) for n in N])
P, N = P[~skip], N[~skip]
print("surface points", len(P))

H_RIM, RB, RT = 0.062, 0.034, 0.0455
SLOPE = (RT - RB) / (H_RIM - 0.0016 - 0.0015)
meta, fr, tag = analyze.load(mpm_d)
sp = meta["spacing"]
pp = json.load(open(pp_path))
meta_hand = np.array(meta["hand"], float)
F = meta["frames"]
rel = meta.get("release_frame") or F - 1


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ease(t):
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


R_S, R_C, CAP_H, CL = 0.0103, 0.0168, 0.030, 0.0013      # same constants as site/main.js nozzleCap()


def r_in_c(y):
    return RB + (max(y, 0.0015) - 0.0015) * SLOPE - 0.00056


def clamp_hand(h):
    """keep the star tip and the white cap off the cup wall (a few frames of the simulated hand ask for a millimetre too much)"""
    hx, ny, hz = h[0], h[1], h[2]
    if ny < 0.0685:
        cap = r_in_c(min(ny, H_RIM)) - R_S - CL
        if ny + CAP_H < H_RIM:
            cap = min(cap, r_in_c(ny + CAP_H) - R_C - CL)
        cap = max(0.01, cap)
        r = math.hypot(hx, hz)
        u = min(1.0, max(0.0, (ny - 0.0645) / 0.004))
        u = u * u * (3 - 2 * u)
        lim = cap + (r - cap) * u
        if r > lim:
            hx, hz = hx * lim / r, hz * lim / r
    return np.array([hx, ny, hz])


def cup_pos(p, sel):
    N = np.array(pp["nozzlesMachine"][sel])
    bases = [np.array(b) for b in pp["cupBasesMachine"]]
    tray = bases[1] + (bases[sel] - bases[1]) * ease(smooth(0.03, 0.10, p))
    h0 = meta_hand[0]
    held0 = N - clamp_hand(h0)
    if p < 0.18:
        return tray + (held0 - tray) * ease(smooth(0.10, 0.18, p))
    fr = min(1.0, (p - 0.18) / 0.66) * (F - 1)
    f0 = int(fr); f1 = min(F - 1, f0 + 1); ft = fr - f0
    h = meta_hand[f0] + (meta_hand[f1] - meta_hand[f0]) * ft
    held = N - clamp_hand(h)
    lower = ease(smooth(rel, F - 1, fr))
    pos = held + (tray - held) * lower
    pos[1] = max(pos[1], tray[1])
    return pos


path = {str(sel): [[p, *cup_pos(p, sel)] for p in np.linspace(0, 1, 401)] for sel in range(3)}

def r_out(y):  # outside radius of the cup wall (+ rolled rim bead near the top)
    r = RB + np.clip(y - 0.0015, 0, None) * SLOPE + 0.00056
    return r + 0.0016 * (y > H_RIM - 0.004)

worst = {}
fail_p = {}
for sel, rows in path.items():
    for row in rows:
        p, cx, cy, cz = row
        d = P - np.array([cx, cy, cz])
        y = d[:, 1]
        r = np.hypot(d[:, 0], d[:, 2])
        ri = RB + np.clip(y - 0.0015, 0, None) * SLOPE - 0.00056
        shell = (y > 0.0008) & (y < H_RIM + 0.002) & (r < r_out(y) + CLEAR) & (r > ri - CLEAR)
        base = (y > 0.0008) & (y < 0.0068 + CLEAR) & (r < RB + 0.0006)     # the cup's solid foot
        inside = shell | base
        # the cup base ring/foot is solid below y=0.007
        # froyo
        f = 0 if p < 0.18 else int(round(min(1, (p - 0.18) / 0.66) * (meta["frames"] - 1)))
        A, n = analyze.particles(fr, f, meta)
        hit_f = np.zeros(len(P), bool)
        if n:
            tree = cKDTree(A[:n])
            dist, _ = tree.query(d, distance_upper_bound=sp * 0.55 + CLEAR)
            hit_f = np.isfinite(dist)
        bad = inside | hit_f
        # the nozzle is allowed to deliver froyo: the star tip opening touches the stream by design
        tip = (np.abs(P[:, 0] - (-0.1 + 0.1 * int(sel))) < 0.016) & (P[:, 1] > 0.355) & (P[:, 1] < 0.395)
        bad &= ~(hit_f & tip & ~inside)
        # standing on the tray at rest is fine
        bad &= ~((y < 0.0009) & ~hit_f)                              # resting on the tray is contact, not overlap
        if bad.any():
            for nm in set(N[bad]):
                k = bad & (N == nm)
                depth = float(np.max(np.where(k & inside, np.minimum(r_out(y) + CLEAR - r, r - (ri - CLEAR)), 0)) * 1000)
                key = (sel, nm)
                worst[key] = max(worst.get(key, 0), depth)
                fail_p.setdefault(key, []).append(round(p, 3))
print("violations:" if worst else "NO OVERLAPS across", len(path), "flavour paths")
for k, v in sorted(worst.items(), key=lambda kv: -kv[1]):
    ps = fail_p[k]
    print(f"  handle {k[0]} {k[1]:<14} max intrusion {v:5.1f} mm   p={ps[0]}..{ps[-1]} ({len(ps)} samples)")

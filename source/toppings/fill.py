"""Full bowls: fill a bowl with pieces from its floor up to a mound over the rim, then keep only the ones you can see.

heap.py settled a thin layer of pieces on a dome-shaped fill, which read as "a bit of stuff on one solid colour". This
module builds the whole pile instead, by height-field deposition (numpy only, no Blender):

  * the target is a mound: the bowl's wall up to the rim, then a dome standing `over` metres above the rim at the centre;
  * pieces are dropped one at a time, each in the spot (of several random ones) where the pile is furthest below the
    target, in an orientation it could rest in (plates lie flat-ish, rods and ribbons along the surface, the rest tumble);
    it comes to rest on the highest thing under it (a high percentile of the surface under its own vertices, so it sinks
    a little into gaps), and may not poke through the bowl's wall (which is wavy, see wall_radius);
  * it stops when the pile has reached the target everywhere;
  * only the shell is kept: pieces whose top is within `depth` of the final surface, with the occlusion of every piece
    worked out against the whole pile, buried ones included.  What is below the shell is the page's dark dome.

    make_heap(key, pieces, spec, weights) -> the dict bar-heaps.json stores for the bowl (see bar-heap.js)
"""
import math

import numpy as np

import heap_geom as G


def _hash_seed(key):
    h = 0
    for ch in key:
        h = (h * 131 + ord(ch)) & 0xFFFFFF
    return 0.6 + (h % 560) / 100.0           # the wavy rim's phase: fixed per bowl, so the page can draw the very same bowl


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


def _orientation(V, rng, tilt_k):
    """a random rotation (piece-local -> world, Y up) the piece could rest in"""
    from scipy.spatial.transform import Rotation as Rot
    Vc = V - V.mean(0)
    w, E = np.linalg.eigh(np.cov(Vc.T))
    s = np.sqrt(np.maximum(w, 1e-18))
    if s[0] / s[2] < 0.38 and s[0] / s[1] < 0.7:           # a plate: thin axis up (or down)
        up = E[:, 0] * rng.choice([-1.0, 1.0])
        base = Rot.align_vectors([[0, 1, 0]], [up])[0].as_matrix()
        tilt = 0.20 * tilt_k
    elif s[1] / s[2] < 0.5:                                # a rod or ribbon: long axis near-horizontal
        a = Rot.align_vectors([[1, 0, 0]], [E[:, 2] * rng.choice([-1.0, 1.0])])[0]
        base = Rot.from_rotvec([rng.uniform(0, math.tau), 0, 0]).as_matrix() @ a.as_matrix()
        tilt = 0.40 * tilt_k
    else:
        return Rot.random(random_state=int(rng.integers(1 << 30))).as_matrix()
    yaw = Rot.from_rotvec([0, rng.uniform(0, math.tau), 0]).as_matrix()
    tl = Rot.from_rotvec([rng.normal(0, tilt), 0, rng.normal(0, tilt)]).as_matrix()
    return yaw @ tl @ base


def make_heap(key, pieces, spec, weights=None, log=print):
    """spec: bowl, over (mound height above the rim, m), tilt (1: how much pieces lean), depth (shell thickness, in mean piece
    radii), max_n, tries, pct (how deep a piece sinks into the gaps: percentile of the surface under it), ao_lo, edge (the
    mound's height at the wall, in m above the rim: negative = below it), solid (m below the target down to which the pile is
    taken as already there: for tiny pieces, where dropping a whole bowl's worth would be 100k of them), tint (the page colours each
    instance from the topping's palette)"""
    kind = spec['bowl']
    seed = _hash_seed(key)
    H = G.BOWLS[kind]['H']
    vs = []
    rng = np.random.default_rng(11 + len(key))
    for p in pieces:
        V = p['V'].astype(float)
        # a sample of the vertices stands for the piece when it lands: all the extremes (the hull), and a spread of the rest
        from scipy.spatial import ConvexHull
        hv = V[ConvexHull(V).vertices]
        k = min(len(V), spec.get('samples', 260))
        samp = np.concatenate([hv, V[rng.choice(len(V), k, replace=False)]])
        vs.append(dict(V=V, S=samp, r=float(p['extras']['r'])))
    w = np.asarray(weights if weights is not None else [1] * len(vs), float)
    pr = w / w.sum()
    rbar = float(np.average([v['r'] for v in vs], weights=w))
    cell = spec.get('cell') or max(0.0008, min(0.002, rbar / 4.5))
    over = spec['over']
    edge = spec.get('edge', 0.0)
    Rr = G.wall_radius(kind, H, 0.0, seed)             # (the rim's radius, without the wobble)
    half = Rr * 1.12 + 0.004
    nc = int(2 * half / cell) + 1
    ctr = (nc - 1) / 2
    gx = (np.arange(nc) - ctr) * cell
    X, Z = np.meshgrid(gx, gx, indexing='ij')
    rr = np.hypot(X, Z)
    # the floor: the bowl's inside, wavy and all (wall_floor), flat in the middle
    Hf = G.floor_height(kind, rr)
    # the target: up the wall to the rim, then a dome standing `over` above it at the middle
    u = np.clip(rr / Rr, 0, 1)
    shape = spec.get('shape', 1.0)
    T = H + edge + over * (1 - u ** 2) ** shape
    if spec.get('bumps'):                              # a loose pile is lumpy, not a smooth cap: a few long waves over the mound, none at the rim
        amp, wl = spec['bumps']
        br = np.random.default_rng(int(seed * 100))
        wave = np.zeros_like(T)
        for k in range(1, 5):
            th, ph = br.uniform(0, math.tau, 2)
            wave += np.sin(math.tau * (X * math.cos(th) + Z * math.sin(th)) / (wl / k) + ph) / k
        T = T + amp * wave / 1.4 * np.clip(1.2 - u ** 3, 0, 1) * (u < 1)
    if spec.get('scoop'):                              # where the spoon has been
        sx, sz, sr, sd = spec['scoop']
        T = T - sd * np.exp(-((X - sx) ** 2 + (Z - sz) ** 2) / sr ** 2) * np.clip(1.2 - u ** 3, 0, 1)
    if spec.get('solid'):                              # tiny pieces: everything deeper than this below the target is taken as already filled
        Hf = np.maximum(Hf, T - spec['solid'])
    inner = rr < G.wall_radius(kind, H, np.arctan2(Z, X), seed) - 0.0035          # (every cell inside the wavy wall: the pile must reach it all the way round)
    tol = spec.get('tol', 0.55) * rbar
    tries = spec.get('tries', 10)
    pct = spec.get('pct', 90)
    max_n = spec.get('max_n', 4000)
    tilt_k = spec.get('tilt', 1.0)

    def cells(x, z):
        return (np.clip(np.rint(x / cell + ctr).astype(int), 0, nc - 1), np.clip(np.rint(z / cell + ctr).astype(int), 0, nc - 1))

    out = []
    n_try_fail = 0
    while len(out) < max_n:
        vi = int(rng.choice(len(vs), p=pr))
        v = vs[vi]
        # (the deficit picks the spot: where the pile is furthest below the target)
        best = None
        for _ in range(tries):
            R = _orientation(v['V'], rng, tilt_k)
            Vw = v['S'] @ R.T
            reach = float(np.hypot(Vw[:, 0], Vw[:, 2]).max())
            # aim at the deficit: a random spot, weighted to the lowest of a few
            a = rng.uniform(0, math.tau)
            d = math.sqrt(rng.uniform(0, 1)) * Rr * 0.98
            cx, cz = d * math.cos(a), d * math.sin(a)
            ok = False
            for _ in range(3):
                ix, iz = cells(cx + Vw[:, 0], cz + Vw[:, 2])
                yc = float(np.percentile(Hf[ix, iz] - Vw[:, 1], pct))
                yv = yc + Vw[:, 1]
                px, pz = cx + Vw[:, 0], cz + Vw[:, 2]
                over_w = np.hypot(px, pz) - G.wall_radius(kind, yv, np.arctan2(pz, px), seed) + 0.0004
                m = float(over_w.max())
                if m <= 0:
                    ok = True
                    break
                dd = math.hypot(cx, cz)
                if dd < 1e-6:
                    break
                f = max(0.0, 1 - (m + 0.0004) / dd)
                cx, cz = cx * f, cz * f
            if not ok:
                continue
            deficit = G.target_at(T, cx, cz, cells) - (yc + 0.7 * float(Vw[:, 1].max()))     # (how far its top would end up below the target)
            sc = -deficit + rng.normal(0, 0.25 * rbar)
            if best is None or sc < best[0]:
                best = (sc, yc, cx, cz, R, Vw, deficit)
        if best is None:
            n_try_fail += 1
            if n_try_fail > 400:
                break
            continue
        sc, yc, cx, cz, R, Vw, deficit = best
        if deficit < -0.3 * rbar:                       # the best spot is already above the target: full
            n_try_fail += 1
            if n_try_fail > 150:
                break
            continue
        n_try_fail = 0
        ix, iz = cells(cx + Vw[:, 0], cz + Vw[:, 2])
        np.maximum.at(Hf, (ix, iz), yc + Vw[:, 1])
        out.append((vi, np.array([cx, yc, cz]), R))
        if len(out) % 30 == 0:
            lack = (T - Hf)[inner]
            if np.percentile(lack, 96) <= tol and lack.mean() <= 0.35 * tol:
                break
    n_all = len(out)
    if spec.get('debug'):
        for lo in np.arange(0, 0.1, 0.02):
            m = (rr >= lo) & (rr < lo + 0.02)
            print('   r %.2f-%.2f  surface %.1f  target %.1f  floor %.1f' % (lo, lo + 0.02, Hf[m].mean() * 1000, T[m].mean() * 1000, G.floor_height(kind, rr[m]).mean() * 1000), 'fails', n_try_fail)
    # ---- the shell: which pieces can be seen
    P = np.array([o[1] for o in out])
    rad = np.array([vs[o[0]]['r'] for o in out])
    topy = np.array([P[i, 1] + float((vs[o[0]]['S'] @ o[2].T)[:, 1].max()) for i, o in enumerate(out)])
    surf = np.empty(n_all)
    for i, o in enumerate(out):
        Vw = vs[o[0]]['S'] @ o[2].T
        ix, iz = cells(P[i, 0] + Vw[:, 0], P[i, 2] + Vw[:, 2])
        surf[i] = Hf[ix, iz].max()
    D = spec.get('depth', 1.7) * rbar
    depth = surf - topy
    keep = depth <= D
    # ---- occlusion, against everything (rays up the hemisphere; a neighbour is a sphere of 0.85 r)
    rg = np.random.default_rng(3)
    dirs = rg.normal(size=(24, 3))
    dirs[:, 1] = np.abs(dirs[:, 1]) * 0.9 + 0.25
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    rmax = float(rad.max())
    open_frac = np.zeros(n_all)
    kidx = np.flatnonzero(keep)
    for a in kidx:
        d = P - P[a]
        dist = np.linalg.norm(d, axis=1)
        near = (dist > 1e-6) & (dist < 6 * rmax)
        near[a] = False
        if not near.any():
            open_frac[a] = 1
            continue
        dn = d[near]
        rn = 0.85 * rad[near]
        t = dirs @ dn.T
        miss = np.sqrt(np.maximum(np.einsum('ij,ij->i', dn, dn)[None, :] - t * t, 0))
        hit = (t > 0) & (miss < rn[None, :])
        open_frac[a] = 1 - hit.any(1).mean()
    ao_lo = spec.get('ao_lo', 0.42)
    ao = ao_lo + (1 - ao_lo) * np.clip(open_frac * 1.15, 0, 1)
    ao *= 1 - 0.22 * np.clip(depth / max(D, 1e-9), 0, 1)           # a little darker the deeper it sits
    res = []
    for i in kidx:
        o = out[i]
        q = _quat(o[2])
        if q[3] < 0:
            q = -q
        row = [int(o[0]), *[round(float(x), 4) for x in o[1]], *[round(float(x), 3) for x in q], round(float(ao[i]), 2)]
        res.append(row)
    top_c = float(np.percentile(topy[kidx], 97))
    # the dark dome under the shell: the pile's own surface, lowered past the shell (the page draws it as a lathe)
    dome_gap = spec.get('dome_gap', 0.5) * rbar
    Rin = Rr * (1 - G.BOWLS[kind]['wobble']) - 0.004
    edges = np.linspace(0, Rin, 12)
    dome = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (rr >= a) & (rr < b)
        dome.append([round(float((a + b) / 2), 4), round(float(np.percentile(Hf[m], 12)) - D - dome_gap, 4)])
    y_c, y_e = dome[0][1], dome[-1][1]
    rw = G.wall_radius(kind, max(y_e, 0.01), None, seed)
    lack = (T - Hf)[inner]
    log(f"  {key}: dropped {n_all}, kept {len(res)}, top={top_c * 1000:.0f} mm (target {(H + over) * 1000:.0f}), shell {D * 1000:.0f} mm, "
        f"deficit p96={np.percentile(lack, 96) * 1000:.1f} mm")
    return dict(instances=res, top=round(top_c, 5), n=n_all, bowl=kind, variants=len(vs), yc=round(y_c, 5), ye=round(y_e, 5),
                rw=round(rw, 5), seed=round(seed, 3), dome=dome, cover=1.0)

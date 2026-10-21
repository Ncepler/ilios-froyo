"""Fill a bowl with a topping: pick the number of pieces that heaps to the right height, settle them (heap.py)."""
import math

import numpy as np



def cavity_volume(kind, y_top):
    import heap
    pts, H = heap.bowl_inner(kind)
    v = 0.0
    for (r0, y0), (r1, y1) in zip(pts[:-1], pts[1:]):
        if y0 >= y_top:
            break
        y1c = min(y1, y_top)
        f = (y1c - y0) / max(y1 - y0, 1e-9)
        r1c = r0 + (r1 - r0) * f
        v += math.pi * (r0 * r0 + r0 * r1c + r1c * r1c) / 3 * (y1c - y0)
    return v


def piece_volume(p):
    V, F = p['V'].astype(float), p['F'].astype(int)
    return abs(np.einsum('ij,ij->i', V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum()) / 6


def make_heap(key, pieces, spec):
    """spec: bowl, over (heap top above the rim, m), phi (packing of the pieces), edge (heap level at the wall / H),
    fast (tiny pieces: skip the rigid-body simulation, which grows with the square of the piece count)"""
    if not spec.get('rigid'):                          # the default: the whole bowl, filled by height-field deposition (fill.py)
        import fill
        return fill.make_heap(key, pieces, spec, spec.get('weights'))
    import heap                                        # the older thin-layer runs (Blender rigid bodies, needs bpy)
    kind = spec['bowl']
    H = heap.BOWLS[kind]['H']
    vs = [dict(V=p['V'].astype(float), F=p['F'].astype(int), r=float(p['extras']['r']), vol=piece_volume(p)) for p in pieces]
    w = spec.get('weights') or [1] * len(vs)
    vmean = float(np.average([v['vol'] for v in vs], weights=w))
    rmean = float(np.average([v['r'] for v in vs], weights=w))
    R = heap.BOWLS[kind]['R']
    top = H + spec['over']
    T = spec.get('layer') or max(0.016, 2.3 * rmean)  # thickness of the simulated layer (the dome under it is the rest of the fill)
    y_e_top = H * spec.get('edge', 0.78)
    y_c, y_e = top - T, y_e_top - T
    n = int(math.pi * (0.8 * R) ** 2 * T * spec['phi'] / vmean)
    if spec.get('fast'):                               # tiny pieces: height-field deposition, not rigid bodies (heap.simulate_fast)
        inst = heap.simulate_fast(kind, vs, w, top, y_c, y_e, seed=7, max_n=spec.get('max_n', 4500), tries=spec.get('tries', 8), min_n=spec.get('min_n', 0))
        res, st = heap.finish(kind, inst, vs, y_c, y_e, ao_lo=spec.get('ao_lo', 0.4))
        print(f"  {key}: fast, {len(inst)} dropped, {len(res)} kept, top={st['top'] * 1000:.0f} mm (want {top * 1000:.0f}) cover={st['cover']:.2f}", flush=True)
        return dict(instances=res, top=st['top'], n=len(inst), bowl=kind, variants=len(vs), yc=round(y_c, 5), ye=round(y_e, 5),
                    rw=round(heap.wall_radius(kind, y_e), 5), cover=round(st['cover'], 3))
    best = None
    for it in range(4):
        inst = heap.simulate(kind, vs, w, n, y_c, y_e, seed=7 + it)
        res, st = heap.finish(kind, inst, vs, y_c, y_e, ao_lo=spec.get('ao_lo', 0.4))
        best = dict(instances=res, top=st['top'], n=n, bowl=kind, variants=len(vs), yc=round(y_c, 5), ye=round(y_e, 5),
                    rw=round(heap.wall_radius(kind, y_e), 5), cover=round(st['cover'], 3))
        print(f"  {key}: n={n} top={st['top'] * 1000:.0f} mm (want {top * 1000:.0f}) cover={st['cover']:.2f}", flush=True)
        # dense (no bare patches) and about the right height
        if st['cover'] >= 0.93 and abs(top - st['top']) < 0.005:
            break
        grow = (0.94 - st['cover']) * 1.1 if st['cover'] < 0.93 else 0.0
        grow += (top - st['top']) / T * 0.4
        n = max(20, int(n * (1 + max(-0.3, min(0.6, grow)))))
    return best

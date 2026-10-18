"""Build the topping pieces (numpy signed-distance models, marching cubes) -> a GLB the page loads, and their heaps.

    python source/build_toppings.py <out prefix> [--only key,key] [--heaps] [--jobs N]

writes <prefix>.glb (the pieces) and, with --heaps, <prefix>-heaps.json (each bowl's settled pile, simulated with
Blender's rigid body physics; run with a Python that has bpy). Pieces are modelled in source/toppings/{fruit,candy,
baked}.py, each exporting PIECES; see lib.py for the kit and the per-vertex data convention
(COLOR_0 = albedo + roughness, _DATA = self occlusion, translucency, specular).
"""
import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'toppings'))
import lib  # noqa: E402


def registry():
    import baked
    import baked2
    import candy
    import fruit
    reg = {}
    for m in (fruit, candy, baked, baked2):
        reg.update(m.PIECES)
    return reg


def build_pieces(key):
    reg = registry()
    spec = reg[key]
    return [spec['fn'](i) for i in range(spec['n'])]


def _heap_job(key):
    import heaps
    t = time.time()
    spec = registry()[key]['heap']
    pcs = build_pieces(key)
    h = heaps.make_heap(key, pcs, spec)
    return key, h, time.time() - t


if __name__ == '__main__':
    out = sys.argv[1]
    only = None
    if '--only' in sys.argv:
        only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 1
    reg = registry()
    keys = [k for k in reg if not only or k in only]
    pieces = []
    for key in keys:
        t = time.time()
        pcs = build_pieces(key)
        pieces += pcs
        print(f"{key}: {len(pcs)} variants, {sum(len(p['F']) for p in pcs) // len(pcs)} tris each, {time.time() - t:.1f}s", flush=True)
    glb = out + '.glb'
    size = lib.write_glb(glb, pieces)
    print('wrote', glb, f'{size / 1e6:.2f} MB, {len(pieces)} pieces', flush=True)
    if '--heaps' in sys.argv:
        todo = [k for k in keys if reg[k]['heap']]
        data = {}
        if jobs > 1:
            with mp.get_context('spawn').Pool(jobs) as pool:
                for key, h, dt in pool.imap_unordered(_heap_job, todo):
                    data[key] = h
                    print(f"heap {key}: {len(h['instances'])} pieces, top {h['top'] * 1000:.0f} mm, {dt:.0f}s", flush=True)
        else:
            for key in todo:
                key, h, dt = _heap_job(key)
                data[key] = h
                print(f"heap {key}: {len(h['instances'])} pieces, top {h['top'] * 1000:.0f} mm, {dt:.0f}s", flush=True)
        hp = out + '-heaps.json'
        with open(hp, 'w') as fh:
            json.dump(data, fh, separators=(',', ':'))
        print('wrote', hp, os.path.getsize(hp) // 1024, 'KB', flush=True)

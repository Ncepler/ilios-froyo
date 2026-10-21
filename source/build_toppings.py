"""Build the topping pieces (numpy signed-distance models, marching cubes) -> a GLB the page loads, and their heaps.

    python source/build_toppings.py <out prefix> [--only key,key] [--heaps] [--jobs N] [--plain]

writes <prefix>.glb (the pieces: quantised and meshopt-compressed, see pack.py; --plain for float32) and, with --heaps, <prefix>-heaps.json (each bowl's settled pile, simulated with
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
import pack  # noqa: E402


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
    size = lib.write_glb(glb, pieces) if '--plain' in sys.argv else pack.write_glb_meshopt(glb, pieces)
    print('wrote', glb, f'{os.path.getsize(glb) / 1e6:.2f} MB, {len(pieces)} pieces', '(plain float32)' if '--plain' in sys.argv else '(quantised + meshopt)', flush=True)
    if '--heaps' in sys.argv:
        # each finished heap is saved at once (<prefix>-heaps/<key>.json) and reused on the next run (--redo to recompute), so a
        # long run that is interrupted loses nothing; the slowest bowls start first
        cache = out + '-heaps'
        os.makedirs(cache, exist_ok=True)
        data, todo = {}, []
        for k in [k for k in keys if reg[k]['heap']]:
            f = os.path.join(cache, k + '.json')
            if os.path.exists(f) and '--redo' not in sys.argv:
                data[k] = json.load(open(f))
                print(f"heap {k}: cached ({len(data[k]['instances'])} pieces)", flush=True)
            else:
                todo.append(k)
        todo.sort(key=lambda k: (2 if reg[k]['heap'].get('fast') else 1 if k != 'granola' else 0))

        def done(key, h, dt):
            data[key] = h
            with open(os.path.join(cache, key + '.json'), 'w') as fh:
                json.dump(h, fh, separators=(',', ':'))
            print(f"heap {key}: {len(h['instances'])} pieces, top {h['top'] * 1000:.0f} mm, {dt:.0f}s", flush=True)
        if jobs > 1 and len(todo) > 1:
            with mp.get_context('spawn').Pool(jobs) as pool:
                for key, h, dt in pool.imap_unordered(_heap_job, todo):
                    done(key, h, dt)
        else:
            for key in todo:
                done(*_heap_job(key))
        hp = out + '-heaps.json'
        with open(hp, 'w') as fh:
            json.dump({k: data[k] for k in keys if k in data}, fh, separators=(',', ':'))
        print('wrote', hp, os.path.getsize(hp) // 1024, 'KB', flush=True)

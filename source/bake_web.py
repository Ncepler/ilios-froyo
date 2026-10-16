"""Bake a froyo pour (mpm.py output) into a compact file the website can play back.

    python bake_web.py <mpm_dir> <out_dir> [--vs 0.0025]

Each frame becomes two uint8 voxel fields over the cup's frame: fill fraction (iso 0.5 -> 64) and flavour
(which half of the nozzle the paste came from, for a twist). Frames are stored as one keyframe every KEY
frames and deltas in between (almost the whole pile is static), each raw-deflated, so the page can decode any
frame synchronously and run marching cubes on it.  Files: pour.bin (chunks) + pour.json (index and the
hand/cup path).
"""
import argparse
import json
import math
import os
import zlib

import numpy as np

import analyze

KEY = 8


def deflate(b):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(b) + c.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mpm")
    ap.add_argument("out")
    ap.add_argument("--vs", type=float, default=0.0025)
    ap.add_argument("--size", type=float, nargs=3, default=(0.15, 0.20, 0.15))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    meta, fr, tag = analyze.load(a.mpm)
    org = (-a.size[0] / 2, 0.0, -a.size[2] / 2)
    shape = tuple(int(math.ceil(s / a.vs)) for s in a.size)       # (NX, NY, NZ)
    print("voxels", shape, "frames", meta["frames"])
    chunks, index = [], []
    prev_d = prev_t = None
    total = 0
    for f in range(meta["frames"]):
        P, n = analyze.particles(fr, f, meta)
        dens, tg, o = analyze.field(P, tag, meta, a.vs, org=org, size=a.size)
        q = np.clip(dens * 128.0, 0, 255).astype(np.uint8)
        m = np.where(dens > 0.05, np.clip(tg / np.maximum(dens, 1e-3), 0, 1), 0.0)
        mq = (m * 255).astype(np.uint8)
        # store as (z, y, x) so x runs fastest in memory
        qd = np.ascontiguousarray(q.transpose(2, 1, 0)).ravel()
        qt = np.ascontiguousarray(mq.transpose(2, 1, 0)).ravel()
        key = f % KEY == 0
        if key:
            bd, bt = qd.tobytes(), qt.tobytes()
        else:
            bd = ((qd.astype(np.int16) - prev_d.astype(np.int16)) & 255).astype(np.uint8).tobytes()
            bt = ((qt.astype(np.int16) - prev_t.astype(np.int16)) & 255).astype(np.uint8).tobytes()
        cd, ct = deflate(bd), deflate(bt)
        index.append({"key": bool(key), "d": [total, len(cd)], "t": [total + len(cd), len(ct)]})
        chunks.append(cd)
        chunks.append(ct)
        total += len(cd) + len(ct)
        prev_d, prev_t = qd, qt
        if f % 20 == 0:
            print(f"frame {f}: {len(cd)/1024:.1f} KB density, {len(ct)/1024:.1f} KB flavour", flush=True)
    with open(os.path.join(a.out, "pour.bin"), "wb") as fh:
        for c in chunks:
            fh.write(c)
    hand = meta["hand"]
    out = {
        "fps": meta["fps"], "frames": meta["frames"], "key": KEY,
        "vs": a.vs, "shape": list(shape), "org": list(org), "iso": 64,
        "hand": [[round(h[0], 5), round(h[1], 5), round(h[2], 5), round(h[3], 4)] for h in hand],
        "valveClose": meta.get("valve_close_frame"), "release": meta.get("release_frame"),
        "index": index,
    }
    with open(os.path.join(a.out, "pour.json"), "w") as fh:
        json.dump(out, fh)
    print(f"pour.bin {total/1e6:.2f} MB for {meta['frames']} frames")


if __name__ == "__main__":
    main()

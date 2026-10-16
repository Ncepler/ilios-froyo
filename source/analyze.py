"""Turn MPM particles into a surface and measure it.

    python analyze.py <mpm_dir> <frame|last> [--obj out.obj] [--vs 0.0015]

Prints the numbers that matter for judging a swirl against the shop's cups:
height of the peak above the rim, width of the swirl at the rim, volume, and whether anything has
crossed the cup wall or floor. Optionally writes a smooth-shaded OBJ for rendering.
"""
import argparse
import json
import math
import os

import numpy as np
from scipy import ndimage
from skimage import measure

H_RIM, RB, RT, TW, ZB = 0.0620, 0.0340, 0.0455, 0.00055, 0.0068
SLOPE = (RT - RB) / (H_RIM - 0.0016 - 0.0015)
TWALL = TW * math.sqrt(1 + SLOPE * SLOPE)


def r_in(y):
    return RB + (y - 0.0015) * SLOPE - TWALL


def load(d):
    meta = json.load(open(os.path.join(d, "meta.json")))
    fr = np.load(os.path.join(d, "frames.npy"), mmap_mode="r")
    tag = np.load(os.path.join(d, "tag.npy"))
    return meta, fr, tag


def particles(fr, f, meta):
    n = meta["counts"][f]
    P = np.asarray(fr[f][:n], np.float32)
    return P, n


def splat(P, w, org, shape, vs):
    """Cloud-in-cell splat of weights w at P into a grid of voxel size vs."""
    g = (P - org) / vs - 0.5
    i0 = np.floor(g).astype(int)
    f = g - i0
    out = np.zeros(shape, np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                ix, iy, iz = i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz
                wt = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2]) * w
                ok = (ix >= 0) & (iy >= 0) & (iz >= 0) & (ix < shape[0]) & (iy < shape[1]) & (iz < shape[2])
                np.add.at(out, (ix[ok], iy[ok], iz[ok]), wt[ok])
    return out


def field(P, tag, meta, vs, org=(-0.075, 0.0, -0.075), size=(0.15, 0.22, 0.15), blur=1.0):
    shape = tuple(int(math.ceil(s / vs)) for s in size)
    sp = meta["spacing"]
    w = np.full(len(P), (sp ** 3) / (vs ** 3), np.float32)
    org = np.array(org, np.float32)
    dens = splat(P, w, org, shape, vs)
    tg = splat(P, w * tag[:len(P)].astype(np.float32), org, shape, vs)
    # the splat is a point cloud at roughly 2 particles per voxel: smooth it into a continuous fill fraction
    s = blur * sp / vs * 0.62          # about 0.6 particle spacings: continuous, but coil grooves survive
    dens = ndimage.gaussian_filter(dens, s)
    tg = ndimage.gaussian_filter(tg, s)
    dens, tg = clip_to_cup(dens, tg, org, vs)
    return dens, tg, org


def clip_to_cup(dens, tg, org, vs):
    """Froyo is pressed against the paper: boost the fill next to the wall and floor so the surface lands on
    them (no gap), and cut everything beyond so the mesh never pokes through the cup."""
    sh = dens.shape
    xs = org[0] + (np.arange(sh[0]) + 0.5) * vs
    ys = org[1] + (np.arange(sh[1]) + 0.5) * vs
    zs = org[2] + (np.arange(sh[2]) + 0.5) * vs
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    r = np.hypot(X, Z)
    rin = RB + (np.clip(Y, 0.0015, H_RIM) - 0.0015) * SLOPE - TWALL
    dw = rin - r                                     # > 0 inside the cup
    band = 0.0050
    inside_h = Y < H_RIM
    gain = np.where(inside_h & (dw > 0), 1.0 + 1.1 * np.clip(1 - dw / band, 0, 1), 1.0)
    df = Y - ZB
    gain = np.where((df > 0) & (r < rin), gain * (1.0 + 1.1 * np.clip(1 - df / band, 0, 1)), gain)
    dens = dens * gain
    tg = tg * gain
    cut = (inside_h & (dw < -0.0003)) | (Y < ZB - 0.0003)
    dens[cut] = 0
    tg[cut] = 0
    return dens, tg


def mesh_from(dens, tg, org, vs, level=0.5):
    d = np.pad(dens, 1)
    verts, faces, normals, _ = measure.marching_cubes(d, level=level, spacing=(vs, vs, vs))
    verts = verts - vs + org
    # tag at the vertices (nearest voxel of the colour field, normalised by density)
    idx = np.clip(((verts - org) / vs).astype(int), 0, np.array(dens.shape) - 1)
    dd = np.maximum(dens[idx[:, 0], idx[:, 1], idx[:, 2]], 1e-3)
    m = np.clip(tg[idx[:, 0], idx[:, 1], idx[:, 2]] / dd, 0, 1)
    return verts, faces, normals, m


def stats(P, meta):
    sp = meta["spacing"]
    y = P[:, 1]
    r = np.hypot(P[:, 0], P[:, 2])
    top = float(y.max())
    below = y < H_RIM
    wall = np.array([r_in(max(yy, 0.0015)) for yy in y[below]])
    pen = (r[below] - wall)
    out = {
        "particles": int(len(P)),
        "volume_mL": round(len(P) * sp ** 3 * 1e6, 1),
        "peak_above_rim_mm": round((top - H_RIM) * 1000, 1),
        "peak_xz_mm": [round(float(P[y.argmax(), 0]) * 1000, 1), round(float(P[y.argmax(), 2]) * 1000, 1)],
        "rim_overhang_mm": round(float(max(0, r[(y > H_RIM - 0.004) & (y < H_RIM + 0.012)].max() - r_in(H_RIM))) * 1000, 1)
        if ((y > H_RIM - 0.004) & (y < H_RIM + 0.012)).any() else 0.0,
        "max_wall_penetration_mm": round(float(max(0, pen.max())) * 1000, 2) if below.any() else 0.0,
        "min_y_above_floor_mm": round(float(y.min() - ZB) * 1000, 2),
    }
    # swirl width as seen from the front at three heights above the rim
    for h in (0.01, 0.02, 0.03, 0.04, 0.05):
        sel = (y > H_RIM + h - 0.004) & (y < H_RIM + h + 0.004)
        if sel.any():
            out[f"width_at_{int(h*1000)}mm"] = round(float(P[sel, 0].max() - P[sel, 0].min()) * 1000, 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("frame", nargs="?", default="last")
    ap.add_argument("--obj")
    ap.add_argument("--vs", type=float, default=0.0015)
    a = ap.parse_args()
    meta, fr, tag = load(a.dir)
    f = meta["frames"] - 1 if a.frame == "last" else int(a.frame)
    P, n = particles(fr, f, meta)
    s = stats(P, meta)
    print(json.dumps(s, indent=1))
    if a.obj:
        dens, tg, org = field(P, tag, meta, a.vs)
        v, fc, nr, m = mesh_from(dens, tg, org, a.vs)
        import trimesh
        tm = trimesh.Trimesh(vertices=v, faces=fc, process=True)
        trimesh.smoothing.filter_taubin(tm, lamb=0.5, nu=-0.53, iterations=4)
        tm.fix_normals()
        if tm.volume < 0:
            tm.invert()
        v, fc = np.asarray(tm.vertices).copy(), np.asarray(tm.faces)
        # press onto the paper: nothing may cross the wall or floor
        r = np.hypot(v[:, 0], v[:, 2])
        rin = RB + (np.clip(v[:, 1], 0.0015, H_RIM) - 0.0015) * SLOPE - TWALL - 0.00025
        sc = np.where((v[:, 1] < H_RIM) & (r > rin), rin / np.maximum(r, 1e-9), 1.0)
        v[:, 0] *= sc
        v[:, 2] *= sc
        v[:, 1] = np.where(v[:, 1] < ZB + 0.0002, ZB + 0.0002, v[:, 1])
        with open(a.obj, "w") as fh:
            for p in v:
                fh.write("v %.5f %.5f %.5f\n" % tuple(p))
            for t in fc + 1:
                fh.write("f %d %d %d\n" % (t[0], t[1], t[2]))
        print("wrote", a.obj, len(v), "verts")

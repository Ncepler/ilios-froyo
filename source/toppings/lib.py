"""A small modelling kit for the topping pieces: signed-distance solids, meshed with marching cubes.

Why SDFs: a piece of fruit is a whole fruit cut by planes. If the whole is a distance field, a piece is the field
intersected with half-spaces, and every vertex knows how deep it sits below the original skin: that depth is what
colours a strawberry (seeded skin on the outside, red flesh, a pale core in the cut face) or a mango. The same toolkit
makes gummy bears (smooth unions of ellipsoids), chocolate chunks, brownies, cookies, grains of granola.

Everything is in metres, Y up. A piece is a dict (see `piece`) with positions, normals, faces and two per-vertex
attributes that the page's single topping shader reads:
    COLOR_0 = (albedo rgb, linear; roughness)
    _DATA   = (ambient occlusion of the piece on itself, translucency, specular strength)
"""
import json
import math
import struct

import numpy as np
from skimage import measure

MM = 0.001
TAU = math.tau


# ------------------------------------------------------------------ colour
def lin(h):
    """sRGB hex -> linear rgb"""
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def mix(a, b, t):
    """lerp between colours; t scalar or (n,) / (n,1)"""
    t = np.clip(np.asarray(t, dtype=float), 0, 1)
    if t.ndim == 1:
        t = t[:, None]
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ noise (vectorised, deterministic)
def _hash3(ix, iy, iz, seed):
    h = (ix.astype(np.uint32) * np.uint32(374761393) + iy.astype(np.uint32) * np.uint32(668265263)
         + iz.astype(np.uint32) * np.uint32(2147483629) + np.uint32((seed * 1442695041 + 12345) % (2 ** 32)))
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h = h ^ (h >> np.uint32(16))
    return h.astype(np.float64) / 4294967296.0


def vnoise(P, seed=0):
    """value noise in [-1, 1]; P is (..., 3)"""
    P = np.asarray(P, dtype=float)
    i = np.floor(P)
    f = P - i
    u = f * f * f * (f * (f * 6 - 15) + 10)
    ix, iy, iz = i[..., 0], i[..., 1], i[..., 2]

    def c(dx, dy, dz):
        return _hash3(ix + dx, iy + dy, iz + dz, seed)

    x00 = c(0, 0, 0) * (1 - u[..., 0]) + c(1, 0, 0) * u[..., 0]
    x10 = c(0, 1, 0) * (1 - u[..., 0]) + c(1, 1, 0) * u[..., 0]
    x01 = c(0, 0, 1) * (1 - u[..., 0]) + c(1, 0, 1) * u[..., 0]
    x11 = c(0, 1, 1) * (1 - u[..., 0]) + c(1, 1, 1) * u[..., 0]
    y0 = x00 * (1 - u[..., 1]) + x10 * u[..., 1]
    y1 = x01 * (1 - u[..., 1]) + x11 * u[..., 1]
    return (y0 * (1 - u[..., 2]) + y1 * u[..., 2]) * 2 - 1


def fbm(P, octaves=3, seed=0, lac=2.03, gain=0.5):
    P = np.asarray(P, dtype=float)
    s = 0.0
    a = 0.5
    f = 1.0
    for o in range(octaves):
        s = s + a * vnoise(P * f + o * 17.3, seed + o)
        a *= gain
        f *= lac
    return s


def worley(P, seed=0, jitter=0.9):
    """cellular noise: distance to the nearest and second nearest feature point (cell size 1), nearest cell hash"""
    P = np.asarray(P, dtype=float)
    i = np.floor(P)
    f1 = np.full(P.shape[:-1], 9.0)
    f2 = np.full(P.shape[:-1], 9.0)
    cid = np.zeros(P.shape[:-1])
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                ci = i + np.array([dx, dy, dz])
                jx = _hash3(ci[..., 0], ci[..., 1], ci[..., 2], seed + 1)
                jy = _hash3(ci[..., 0], ci[..., 1], ci[..., 2], seed + 2)
                jz = _hash3(ci[..., 0], ci[..., 1], ci[..., 2], seed + 3)
                pt = ci + 0.5 + (np.stack([jx, jy, jz], -1) - 0.5) * jitter
                d = np.linalg.norm(P - pt, axis=-1)
                closer = d < f1
                f2 = np.where(closer, f1, np.minimum(f2, d))
                cid = np.where(closer, _hash3(ci[..., 0], ci[..., 1], ci[..., 2], seed + 4), cid)
                f1 = np.where(closer, d, f1)
    return f1, f2, cid


# ------------------------------------------------------------------ signed distance fields (negative inside)
def _n(P):
    return np.linalg.norm(P, axis=-1)


def sd_sphere(P, c, r):
    return _n(P - c) - r


def sd_ellipsoid(P, c, rad):
    p = (P - c)
    rad = np.asarray(rad, dtype=float)
    k0 = _n(p / rad)
    k1 = _n(p / (rad * rad))
    return np.where(k1 > 1e-12, k0 * (k0 - 1) / np.maximum(k1, 1e-12), -np.min(rad))


def sd_box(P, c, half, rnd=0.0):
    q = np.abs(P - c) - (np.asarray(half) - rnd)
    return _n(np.maximum(q, 0)) + np.minimum(np.max(q, axis=-1), 0) - rnd


def sd_capsule(P, a, b, r):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    pa = P - a
    ba = b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return _n(pa - h[..., None] * ba) - r


def sd_cyl(P, c, h, r):
    """cylinder along y, half height h, radius r"""
    p = P - c
    d = np.stack([np.hypot(p[..., 0], p[..., 2]) - r, np.abs(p[..., 1]) - h], -1)
    return np.minimum(np.maximum(d[..., 0], d[..., 1]), 0) + _n(np.maximum(d, 0))


def sd_plane(P, n, d=0.0):
    """half-space: inside is n.p < d"""
    n = np.asarray(n, dtype=float)
    n = n / np.linalg.norm(n)
    return P @ n - d


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def rot_matrix(ex, ey, ez):
    cx, sx, cy, sy, cz, sz = math.cos(ex), math.sin(ex), math.cos(ey), math.sin(ey), math.cos(ez), math.sin(ez)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def xf(P, R=None, t=(0, 0, 0)):
    """evaluate a shape that is rotated by R and moved by t: pass P through the inverse"""
    p = P - np.asarray(t)
    return p if R is None else p @ R  # (R^T p) for row vectors


# ------------------------------------------------------------------ meshing
def mesh_sdf(f, lo, hi, voxel, pad=2):
    """marching cubes of f<0 over the box lo..hi. Returns welded vertices (n,3) and faces (m,3)"""
    lo = np.asarray(lo, dtype=float) - pad * voxel
    hi = np.asarray(hi, dtype=float) + pad * voxel
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    ax = [lo[i] + np.arange(n[i]) * voxel for i in range(3)]
    G = np.stack(np.meshgrid(*ax, indexing='ij'), -1)
    vol = f(G.reshape(-1, 3)).reshape(tuple(n))
    V, F, _, _ = measure.marching_cubes(vol, 0.0, spacing=(voxel, voxel, voxel))
    V = V + lo
    return V.astype(np.float64), F.astype(np.int64)


def grad(f, V, eps):
    g = np.stack([f(V + np.array([eps, 0, 0])) - f(V - np.array([eps, 0, 0])),
                  f(V + np.array([0, eps, 0])) - f(V - np.array([0, eps, 0])),
                  f(V + np.array([0, 0, eps])) - f(V - np.array([0, 0, eps]))], -1)
    return g / (2 * eps)


def smooth_mesh(V, F, iters=2, lam=0.5, mu=-0.53):
    """Taubin smoothing (does not shrink the piece)"""
    n = len(V)
    I = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    J = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    deg = np.bincount(I, minlength=n).astype(float)
    V = V.copy()
    for _ in range(iters):
        for k in (lam, mu):
            S = np.zeros_like(V)
            np.add.at(S, I, V[J])
            L = S / np.maximum(deg, 1)[:, None] - V
            V += k * L
    return V


def face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n


def vertex_normals(V, F):
    fn = face_normals(V, F)
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)


def sdf_ao(f, V, N, h, strength=1.0):
    """ambient occlusion of a solid on itself, from its own distance field: 1 in the open, down to ~0.45 in a crease"""
    occ = np.zeros(len(V))
    w = 1.0
    for i in range(1, 6):
        d = i * h
        occ += w * np.maximum(0.0, d - f(V + N * d))
        w *= 0.62
    return np.clip(1.0 - strength * 1.35 * occ / h, 0.3, 1.0)


# ------------------------------------------------------------------ pieces
def piece(name, f, lo, hi, voxel, paint, smooth=2, cls='matte', flat=False, ao_h=None, ao_strength=1.0, jelly=False):
    """mesh the solid f, then paint it.

    paint(V, N, ctx) -> (rgb (n,3) linear, rough (n,), sss (n,), spec (n,)); ctx has the field f for depth queries.
    The mesh is centred on its own bounding box (the page places pieces by their centre)."""
    V, F = mesh_sdf(f, lo, hi, voxel)
    if smooth:
        V = smooth_mesh(V, F, smooth)
    # normals from the field (smooth, no marching-cube facets); fall back to the mesh's where the gradient is flat
    G = grad(f, V, voxel * 0.5)
    N = G / np.maximum(np.linalg.norm(G, axis=-1, keepdims=True), 1e-9)
    Nm = vertex_normals(V, F)
    bad = np.linalg.norm(G, axis=-1) < 0.2
    N[bad] = Nm[bad]
    ao = sdf_ao(f, V, N, ao_h or voxel * 1.6, ao_strength)
    rgb, rough, sss, spec = paint(V, N, f)
    c = (lo + hi) / 2 if False else None
    lo_v, hi_v = V.min(0), V.max(0)
    ctr = (lo_v + hi_v) / 2
    Vc = V - ctr
    # winding: make the face normals agree with the field's outward normals
    fn = face_normals(V, F)
    fc = N[F].mean(1)
    if (np.einsum('ij,ij->i', fn, fc) < 0).mean() > 0.5:
        F = F[:, ::-1].copy()
    return dict(name=name, V=Vc.astype(np.float32), N=N.astype(np.float32), F=F.astype(np.uint32),
                COLOR_0=np.concatenate([rgb, rough[:, None]], 1).astype(np.float32),
                _DATA=np.stack([ao, sss, spec], 1).astype(np.float32),
                extras=dict(cls=cls, flat=bool(flat), jelly=bool(jelly), r=float(np.linalg.norm(Vc, axis=-1).max()),
                            size=[float(x) for x in (hi_v - lo_v)]))


# ------------------------------------------------------------------ GLB writer
def write_glb(path, pieces):
    bin_parts = []
    views, accessors, meshes, nodes = [], [], [], []
    off = 0

    def add(arr, target):
        nonlocal off
        data = arr.tobytes()
        pad = (-len(data)) % 4
        views.append(dict(buffer=0, byteOffset=off, byteLength=len(data), target=target))
        bin_parts.append(data + b'\0' * pad)
        off += len(data) + pad
        return len(views) - 1

    def acc(view, ctype, count, typ, mn=None, mx=None):
        a = dict(bufferView=view, componentType=ctype, count=count, type=typ)
        if mn is not None:
            a['min'], a['max'] = mn, mx
        accessors.append(a)
        return len(accessors) - 1

    for p in pieces:
        V, N, F = p['V'], p['N'], p['F']
        at = {}
        at['POSITION'] = acc(add(V, 34962), 5126, len(V), 'VEC3', [float(x) for x in V.min(0)], [float(x) for x in V.max(0)])
        at['NORMAL'] = acc(add(N, 34962), 5126, len(N), 'VEC3')
        at['COLOR_0'] = acc(add(p['COLOR_0'], 34962), 5126, len(V), 'VEC4')
        at['_DATA'] = acc(add(p['_DATA'], 34962), 5126, len(V), 'VEC3')
        ix = acc(add(F.reshape(-1), 34963), 5125, F.size, 'SCALAR')
        meshes.append(dict(name=p['name'], primitives=[dict(attributes=at, indices=ix, mode=4)]))
        nodes.append(dict(name=p['name'], mesh=len(meshes) - 1, extras=p['extras']))
    gltf = dict(asset=dict(version='2.0', generator='ilios topping kit'), scene=0, scenes=[dict(nodes=list(range(len(nodes))))],
                nodes=nodes, meshes=meshes, accessors=accessors, bufferViews=views, buffers=[dict(byteLength=off)])
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    blob = b''.join(bin_parts)
    with open(path, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        fh.write(struct.pack('<II', len(blob), 0x004E4942) + blob)
    return len(blob)


def read_glb_stats(path):
    d = open(path, 'rb').read()
    jl = struct.unpack('<I', d[12:16])[0]
    j = json.loads(d[20:20 + jl])
    return len(j['meshes']), sum(a['count'] for a in j['accessors'] if a['type'] == 'VEC3') // 2

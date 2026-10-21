"""Write the topping pieces as a compact GLB: quantised vertex data, meshopt-compressed (EXT_meshopt_compression).

lib.write_glb stores every attribute as float32 and the indices as uint32 (about 76 bytes per vertex: 17 MB for the whole
bar). The page already ships three's GLTFLoader and the meshopt decoder, so this writer quantises each piece instead:

    POSITION  int16 normalised, with the piece's centre and half-size as the node's translation and scale
              (KHR_mesh_quantization; a 25 mm piece is resolved to 0.8 micrometres)
    NORMAL    int8 normalised
    COLOR_0   uint8 normalised: sqrt(albedo) in rgb (so dark albedos keep their precision), roughness in alpha
    _DATA     uint8 normalised (own occlusion, translucency, specular), padded to 4 bytes
    indices   uint16, vertex-cache ordered

and meshopt-codes each buffer view. Pieces of more than ~600 triangles also get a `<name>_lod` node: the same vertex buffers,
a decimated index list (meshopt simplify, ~28%). Settled bowl heaps show pieces as 25-40 px blobs, so they draw the lod
and the scene stays at a few million triangles; servings and the cup keep the full mesh. The page turns it all back into
plain float arrays (bar-pieces.js, modelledPieces).
Needs `pip install meshoptimizer`.
"""
import json
import struct

import numpy as np
import meshoptimizer as mo

EXT = 'EXT_meshopt_compression'
LOD_MIN = 600          # triangles below which a piece has no lod
LOD_RATIO = 0.28       # of the full index count
LOD_ERROR = 0.03       # relative to the piece's extent


def _q(a, lo, hi, dtype):
    return np.clip(np.rint(a), lo, hi).astype(dtype)


def write_glb_meshopt(path, pieces):
    comp = []           # compressed chunks of the GLB binary
    views, accessors, meshes, nodes = [], [], [], []
    state = dict(off=0, raw=0)

    def add(arr, count, stride, mode, target):
        """arr: contiguous array whose rows are `stride` bytes; returns the buffer view index"""
        raw = np.ascontiguousarray(arr)
        if mode == 'ATTRIBUTES':
            data = mo.encode_vertex_buffer(raw.view(np.uint8).reshape(count, stride), count, stride)
        else:
            data = mo.encode_index_buffer(raw.reshape(-1), raw.size, int(raw.max()) + 1)
        data = bytes(data)
        pad = (-len(data)) % 4
        raw_len = count * stride
        view = dict(buffer=1, byteOffset=state['raw'], byteLength=raw_len, target=target,
                    extensions={EXT: dict(buffer=0, byteOffset=state['off'], byteLength=len(data), byteStride=stride,
                                          count=count, mode=mode, filter='NONE')})
        if mode == 'ATTRIBUTES':
            view['byteStride'] = stride
        views.append(view)
        comp.append(data + b'\0' * pad)
        state['off'] += len(data) + pad
        state['raw'] += raw_len + ((-raw_len) % 4)
        return len(views) - 1

    def acc(view, ctype, count, typ, normalized=False, mn=None, mx=None):
        a = dict(bufferView=view, componentType=ctype, count=count, type=typ)
        if normalized:
            a['normalized'] = True
        if mn is not None:
            a['min'], a['max'] = mn, mx
        accessors.append(a)
        return len(accessors) - 1

    for p in pieces:
        V = p['V'].astype(np.float64)
        n = len(V)
        lo, hi = V.min(0), V.max(0)
        c = (lo + hi) / 2
        h = max(float((hi - lo).max()) / 2, 1e-6)
        pos = np.zeros((n, 4), np.int16)
        pos[:, :3] = _q((V - c) / h * 32767, -32767, 32767, np.int16)
        nor = np.zeros((n, 4), np.int8)
        nor[:, :3] = _q(p['N'] * 127, -127, 127, np.int8)
        col = np.zeros((n, 4), np.uint8)
        col[:, :3] = _q(np.sqrt(np.clip(p['COLOR_0'][:, :3], 0, 1)) * 255, 0, 255, np.uint8)
        col[:, 3] = _q(np.clip(p['COLOR_0'][:, 3], 0, 1) * 255, 0, 255, np.uint8)
        dat = np.zeros((n, 4), np.uint8)
        dat[:, :3] = _q(np.clip(p['_DATA'], 0, 1) * 255, 0, 255, np.uint8)
        F = p['F'].astype(np.uint32).reshape(-1)
        Fo = np.zeros_like(F)
        mo.optimize_vertex_cache(Fo, F, F.size, n)
        Fo = Fo.astype(np.uint16)
        at = {}
        at['POSITION'] = acc(add(pos, n, 8, 'ATTRIBUTES', 34962), 5122, n, 'VEC3', True,
                             [int(v) for v in pos[:, :3].min(0)], [int(v) for v in pos[:, :3].max(0)])
        at['NORMAL'] = acc(add(nor, n, 4, 'ATTRIBUTES', 34962), 5120, n, 'VEC3', True)
        at['COLOR_0'] = acc(add(col, n, 4, 'ATTRIBUTES', 34962), 5121, n, 'VEC4', True)
        at['_DATA'] = acc(add(dat, n, 4, 'ATTRIBUTES', 34962), 5121, n, 'VEC3', True)
        ix = acc(add(Fo, Fo.size, 2, 'TRIANGLES', 34963), 5123, Fo.size, 'SCALAR')
        meshes.append(dict(name=p['name'], primitives=[dict(attributes=at, indices=ix, mode=4)]))
        nodes.append(dict(name=p['name'], mesh=len(meshes) - 1, translation=[float(x) for x in c], scale=[h, h, h],
                          extras=p['extras']))
        if Fo.size >= LOD_MIN * 3:
            lo_idx = np.zeros(Fo.size, np.uint32)
            keep = mo.simplify(lo_idx, F, V.astype(np.float32), F.size, n, 12, max(150, int(Fo.size * LOD_RATIO)) // 3 * 3, LOD_ERROR, 0)
            Fl = np.zeros(keep, np.uint32)
            mo.optimize_vertex_cache(Fl, lo_idx[:keep].copy(), keep, n)
            ixl = acc(add(Fl.astype(np.uint16), keep, 2, 'TRIANGLES', 34963), 5123, keep, 'SCALAR')
            meshes.append(dict(name=p['name'] + '_lod', primitives=[dict(attributes=at, indices=ixl, mode=4)]))
            nodes.append(dict(name=p['name'] + '_lod', mesh=len(meshes) - 1, translation=[float(x) for x in c], scale=[h, h, h]))
    gltf = dict(asset=dict(version='2.0', generator='ilios topping kit (meshopt)'), scene=0,
                scenes=[dict(nodes=list(range(len(nodes))))], nodes=nodes, meshes=meshes, accessors=accessors,
                bufferViews=views,
                buffers=[dict(byteLength=state['off']), dict(byteLength=state['raw'], extensions={EXT: dict(fallback=True)})],
                extensionsUsed=[EXT, 'KHR_mesh_quantization'], extensionsRequired=[EXT, 'KHR_mesh_quantization'])
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    blob = b''.join(comp)
    with open(path, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        fh.write(struct.pack('<II', len(blob), 0x004E4942) + blob)
    return len(blob) + len(js)

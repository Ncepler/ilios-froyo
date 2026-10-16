"""Build the Ilios froyo cup, the soft-serve swirl and the soft-serve machine.

Run with Blender-as-a-module (bpy 4.2):
    python build.py <tex_dir> <out_dir>

Writes:
    <out_dir>/ilios.blend                 the working scene (for Cycles renders)
    <out_dir>/ilios-froyo-cup.glb         cup + emblem + seam + swirl + core
    <out_dir>/ilios-softserve-machine.glb machine with an animated pull handle
    <out_dir>/pour-path.json              swirl centreline + nozzle, glTF space

Units are metres. Blender is Z-up, the front of everything faces -Y.
glTF is Y-up: (x, y, z)_blender -> (x, z, -y)_gltf.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

TEX = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "tex")
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else "out")
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(3)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"


# =====================================================================
# materials
# =====================================================================
def img(name, non_color=False):
    im = bpy.data.images.load(os.path.join(TEX, name), check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def make_mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, base_tex=None, orm=None,
             normal=None, normal_strength=1.0, uv=None, alpha_from_base=False, coat=0.0,
             coat_rough=0.1, sheen=0.0, sheen_rough=0.5, sss=0.0, sss_radius=(1, 1, 1),
             emission=None, emission_strength=0.0, ior=1.5, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Specular IOR Level"].default_value = spec
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = coat_rough
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = sheen_rough
    if sss > 0:
        bsdf.inputs["Subsurface Weight"].default_value = sss
        bsdf.inputs["Subsurface Radius"].default_value = sss_radius
        bsdf.inputs["Subsurface Scale"].default_value = 0.004
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = emission_strength

    uvnode = None
    if uv:
        uvnode = nt.nodes.new("ShaderNodeUVMap")
        uvnode.uv_map = uv

    def tex_node(image):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = image
        t.interpolation = "Linear"
        if uvnode:
            nt.links.new(uvnode.outputs[0], t.inputs[0])
        return t

    if base_tex:
        t = tex_node(img(base_tex))
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if alpha_from_base:
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            m.blend_method = "BLEND"
            m.use_backface_culling = True
    if orm:
        t = tex_node(img(orm, True))
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        if metal > 0:
            nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    if normal:
        t = tex_node(img(normal, True))
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal_strength
        if uv:
            nm.uv_map = uv
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return m


def lin(hexs):
    """sRGB hex -> linear tuple (Principled base colour is linear)."""
    hexs = hexs.lstrip("#")
    c = [int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


M = {}
M["paper"] = make_mat("Ilios Paper (print side)", lin("#ece2cb"), 0.62, base_tex="paper_color.png",
                      orm="paper_orm.png", normal="paper_normal.png", normal_strength=0.35,
                      sheen=0.25, sheen_rough=0.6, spec=0.35)
M["paper_in"] = make_mat("Ilios Paper (PE-coated inside)", lin("#f4eddc"), 0.38, base_tex="paper_color.png",
                         normal="paper_normal.png", normal_strength=0.18, spec=0.5)
M["foil"] = make_mat("Ilios Gold Foil", lin("#b58c45"), 0.32, metal=1.0, base_tex="emblem_color.png",
                     orm="emblem_orm.png", normal="emblem_normal.png", normal_strength=0.6,
                     uv="Decal", alpha_from_base=True)
M["froyo"] = make_mat("Organic Greek Froyo", lin("#f2ead2"), 0.42, coat=0.18, coat_rough=0.30,
                      sheen=0.35, sheen_rough=0.35, sss=0.35, sss_radius=(1.0, 0.85, 0.6), spec=0.45)
M["body"] = make_mat("Machine Powder-Coat Cream", lin("#e7dfcc"), 0.48, normal="powder_normal.png",
                     normal_strength=0.12, coat=0.12, coat_rough=0.35)
M["steel"] = make_mat("Brushed Stainless", lin("#c9c8c4"), 0.3, metal=1.0, orm="brushed_orm.png",
                      normal="brushed_normal.png", normal_strength=0.25)
M["chrome"] = make_mat("Polished Chrome", lin("#e3e3e1"), 0.07, metal=1.0)
M["gold"] = make_mat("Brushed Gold", lin("#d2a24f"), 0.24, metal=1.0)
M["knob"] = make_mat("Cream Enamel", lin("#efe7d5"), 0.22, coat=0.8, coat_rough=0.06)
M["black"] = make_mat("Black Acetal", lin("#141312"), 0.38, spec=0.5)
M["rubber"] = make_mat("Rubber", lin("#0e0e0e"), 0.85)
M["glass"] = make_mat("Panel Glass", lin("#0b0b0c"), 0.04, coat=1.0, coat_rough=0.02)
M["vent"] = make_mat("Vent Shadow", lin("#2a2723"), 0.9)
M["led_w"] = make_mat("LED Warm", lin("#ffd9a0"), 0.3, emission=lin("#ffcf8a"), emission_strength=6.0)
M["led_g"] = make_mat("LED Green", lin("#9bffb5"), 0.3, emission=lin("#7dffa0"), emission_strength=4.0)
M["badge"] = make_mat("Machine Badge Foil", lin("#c9a14e"), 0.28, metal=1.0, base_tex="badge_color.png",
                      orm="badge_orm.png", normal="badge_normal.png", normal_strength=0.6,
                      uv="Decal", alpha_from_base=True)
M["badge_plate"] = make_mat("Badge Plate", lin("#1d1a17"), 0.35, coat=0.6, coat_rough=0.1)
M["froyo_nozzle"] = M["froyo"]


# =====================================================================
# mesh helpers
# =====================================================================
def mesh_obj(name, verts, faces, mats, face_mat=None, uvs=None, smooth=True, attrs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    for m in mats:
        me.materials.append(m)
    if face_mat is not None:
        me.polygons.foreach_set("material_index", np.asarray(face_mat, np.int32))
    if uvs:
        for uvname, loop_uv in uvs.items():
            layer = me.uv_layers.new(name=uvname)
            layer.data.foreach_set("uv", np.asarray(loop_uv, np.float32).ravel())
    if attrs:
        for an, arr in attrs.items():
            a = me.attributes.new(an, "FLOAT", "POINT")
            a.data.foreach_set("value", np.asarray(arr, np.float32))
    me.polygons.foreach_set("use_smooth", np.full(len(me.polygons), smooth))
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def loop_uvs_from_face_corners(faces, corner_uv):
    """corner_uv(face_index, corner_index, vertex_index) -> (u, v)."""
    out = []
    for fi, f in enumerate(faces):
        for ci, vi in enumerate(f):
            out.append(corner_uv(fi, ci, vi))
    return out


def revolve(name, prof, segs, mats, mat_of_seg=None, uv_scale=(6, 20.0), theta0=math.pi / 2, smooth=True):
    """Surface of revolution of a (r, z) polyline around Z.

    Columns wrap (no duplicated seam vertices, so normals stay smooth); UVs are
    per face-corner: u = turns * uv_scale[0] (integer -> seamless), v = arclength * uv_scale[1].
    """
    prof = np.asarray(prof, np.float64)
    n = len(prof)
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    verts = []
    for j in range(segs):
        th = theta0 + 2 * math.pi * j / segs
        c, s = math.cos(th), math.sin(th)
        for r, z in prof:
            verts.append((r * c, r * s, z))
    faces, fmat, fcol = [], [], []
    for j in range(segs):
        j2 = (j + 1) % segs
        for i in range(n - 1):
            a, b = j * n + i, j * n + i + 1
            c_, d = j2 * n + i + 1, j2 * n + i
            faces.append((a, d, c_, b))
            fmat.append(mat_of_seg(i) if mat_of_seg else 0)
            fcol.append(j)

    def cuv(fi, ci, vi):
        j = fcol[fi]
        col = vi // n
        i = vi % n
        jj = col if col >= j else segs  # wrapped column -> u = 1 turn
        return (jj / segs * uv_scale[0], arc[i] * uv_scale[1])

    uv = loop_uvs_from_face_corners(faces, cuv)
    return mesh_obj(name, verts, faces, mats, fmat, {"UVMap": uv}, smooth)


def arc_pts(cx, cz, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cz + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def fillet(points, radius, n=8):
    """Round every interior corner of a 2D polyline with a circular fillet."""
    pts = [np.array(p, float) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        d0 = (p0 - p1) / np.linalg.norm(p0 - p1)
        d2 = (p2 - p1) / np.linalg.norm(p2 - p1)
        ang = math.acos(max(-1, min(1, float(d0 @ d2))))
        if ang > math.pi - 1e-3:
            out.append(p1)
            continue
        rr = radius if np.isscalar(radius) else radius[i]
        t = rr / math.tan(ang / 2)
        t = min(t, 0.45 * np.linalg.norm(p0 - p1), 0.45 * np.linalg.norm(p2 - p1))
        a, b = p1 + d0 * t, p1 + d2 * t
        for k in range(n + 1):
            u = k / n
            # quadratic bezier is visually identical to an arc at this size
            out.append((1 - u) ** 2 * a + 2 * (1 - u) * u * p1 + u ** 2 * b)
    out.append(pts[-1])
    return [tuple(p) for p in out]


def densify(points, step):
    out = [points[0]]
    for p, q in zip(points[:-1], points[1:]):
        p, q = np.array(p), np.array(q)
        L = np.linalg.norm(q - p)
        k = max(1, int(math.ceil(L / step)))
        for i in range(1, k + 1):
            out.append(tuple(p + (q - p) * i / k))
    return out


def apply_mods(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def select_only(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def box_uv(ob, size=0.25):
    """Cube-project UVs (for the tiling steel / powder textures)."""
    select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=size)
    bpy.ops.object.mode_set(mode="OBJECT")


def rbox(name, dims, loc, bevel, mat, segs=6, uv=0.25):
    """Rounded box with hardened bevel normals."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width = bevel
    md.segments = segs
    md.limit_method = "NONE"
    md.harden_normals = True
    apply_mods(ob)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    box_uv(ob, uv)
    return ob


def cyl(name, r, depth, loc, mat, rot=(0, 0, 0), verts=48, bevel=0.0, segs=3):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if bevel > 0:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = segs
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(40)
        md.harden_normals = True
        apply_mods(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    ob.data.materials.append(mat)
    box_uv(ob, 0.2)
    return ob


def lathe(name, prof, mat, loc=(0, 0, 0), segs=64, rot=(0, 0, 0), smooth=True):
    ob = revolve(name, prof, segs, [mat], uv_scale=(1, 10))
    ob.location = loc
    ob.rotation_euler = rot
    if not smooth:
        select_only(ob)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    return ob


def parent(child, par, keep=True):
    child.parent = par
    if keep:
        child.matrix_parent_inverse = par.matrix_world.inverted()


# =====================================================================
# THE CUP  (squat 16oz-style paper bowl, matching the reference photo)
# =====================================================================
H = 0.0620          # overall height
RT = 0.0455         # outer radius at the top of the wall (under the bead)
RB = 0.0340         # outer radius at the bottom of the wall
T = 0.00055         # paper thickness
ZB = 0.0068         # top of the recessed base (inside floor)
ZU = 0.0060         # underside of the base disc
BEAD = 0.00135      # rolled rim bead radius

slope = (RT - RB) / (H - 0.0016 - 0.0015)


def r_out(z):
    return RB + (z - 0.0015) * slope


def r_in(z):
    return r_out(z) - T * math.sqrt(1 + slope * slope)


cx, cz = RT + 0.0003, H - BEAD * 0.55
inner_top = (r_in(H - 0.0019), H - 0.0019)
outer_top = (r_out(H - 0.0019), H - 0.0019)
prof = []
prof += fillet([(0.0, ZB), (r_in(ZB), ZB), inner_top], 0.0022, 10)
# rolled bead: from the inner wall, up and over, curling down the outside
prof += arc_pts(cx, cz, BEAD, math.radians(205), math.radians(-160), 40)[1:]
prof += [outer_top]
# outer wall, then the rolled bottom skirt curling inward, then the base underside
bottom = [outer_top, (r_out(0.0016), 0.0016)]
prof += densify(bottom, 0.006)[1:]
bcx, bcz, br = RB - 0.00075, 0.0010, 0.00075
prof += arc_pts(bcx, bcz, br, math.radians(0), math.radians(-180), 14)[1:]
prof += fillet([(RB - 0.0015, 0.0010), (RB - 0.0015, ZU), (0.0, ZU)], 0.0006, 6)[1:]
prof = [(max(0.0, r), z) for r, z in prof]
# densify long straight runs a little for clean interpolation in close-ups
prof = densify(prof, 0.004)

n_inner = len(fillet([(0.0, ZB), (r_in(ZB), ZB), inner_top], 0.0022, 10))


def cup_mat_of_seg(i):
    # profile segments before the rim bead are the PE-coated inside
    return 1 if i < n_inner_dense else 0


# count how many dense profile points belong to the inside run
_inside = densify(fillet([(0.0, ZB), (r_in(ZB), ZB), inner_top], 0.0022, 10), 0.004)
n_inner_dense = len(_inside) - 1

cup = revolve("Cup", prof, 192, [M["paper"], M["paper_in"]], cup_mat_of_seg, uv_scale=(6, 20.0))


# --- side seam: the overlapped, glued paper edge at the back (theta = +90deg)
def seam_strip():
    w = 0.0058
    zs = np.linspace(0.0026, H - 0.0011, 64)
    across = [(-w / 2, 0.0), (-w / 2 + 0.0012, 0.00022), (w / 2 - 0.0002, 0.00026), (w / 2, 0.00004)]
    verts, faces = [], []
    for z in zs:
        r = r_out(z)
        fade = min(1.0, (z - 0.0026) / 0.003, (H - 0.0011 - z) / 0.0035)
        for off, h in across:
            h *= max(0.0, fade)
            th = math.pi / 2 + off / r
            rr = r + h + 0.00002
            verts.append((rr * math.cos(th), rr * math.sin(th), z))
    k = len(across)
    for i in range(len(zs) - 1):
        for j in range(k - 1):
            a = i * k + j
            faces.append((a, a + 1, a + 1 + k, a + k))
    uv = loop_uvs_from_face_corners(
        faces, lambda fi, ci, vi: ((vi % k) / (k - 1) * 0.1, verts[vi][2] * 20))
    ob = mesh_obj("CupSeam", verts, faces, [M["paper"]], uvs={"UVMap": uv})
    select_only(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    return ob


seam = seam_strip()


# --- the gold-foil sun decal, conformed to the conical wall at the front
def emblem_decal():
    D = 0.0440                    # decal square edge, metres on the paper
    s_c = 0.031                   # decal centre, height above the cup floor line
    thc = -math.pi / 2            # front
    nu, nv = 72, 72
    verts, uvs = [], []
    for iv in range(nv + 1):
        v = iv / nv
        z = s_c + (v - 0.5) * D / math.sqrt(1 + slope * slope)
        r = r_out(z) + 0.00006
        for iu in range(nu + 1):
            u = iu / nu
            th = thc + (u - 0.5) * D / r
            verts.append((r * math.cos(th), r * math.sin(th), z))
            uvs.append((u, v))
    faces = []
    for iv in range(nv):
        for iu in range(nu):
            a = iv * (nu + 1) + iu
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    loop_uv = loop_uvs_from_face_corners(faces, lambda fi, ci, vi: uvs[vi])
    return mesh_obj("Emblem", verts, faces, [M["foil"]], uvs={"Decal": loop_uv})


emblem = emblem_decal()

# =====================================================================
# THE SWIRL  (one continuous extruded rope; a `_reveal` 0..1 attribute
# runs along it so the website can "pour" it in a shader)
# =====================================================================
A0 = 0.0089                   # rope radius as it leaves the star nozzle


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def build_centerline():
    pitch_in = 1.40 * A0
    pitch_up = 1.40 * A0
    z0 = ZB + 0.80 * A0
    T1 = (H - 0.0030 - z0) / pitch_in            # turns until the rim
    T2 = 2.75                                     # mound turns above the rim
    th_end = math.radians(150)                    # helix ends back-left
    total = T1 + T2
    th0 = th_end - 2 * math.pi * total
    Ts = np.arange(0, total, 1 / 540)
    pts, rad = [], []
    for Tn in Ts:
        th = th0 + 2 * math.pi * Tn
        if Tn < T1:
            z = z0 + pitch_in * Tn
            wall = r_in(z) - 1.12 * A0
            rho = 0.0015 + (wall - 0.0015) * smoothstep(0, 0.85, Tn)
            a = A0
        else:
            u = (Tn - T1) / T2
            AU = A0 * 1.16 * (1 - 0.20 * u)
            z = z0 + pitch_in * T1 + 1.42 * A0 * 1.16 * (Tn - T1) * (1 - 0.12 * u)
            rho0 = r_in(H) - 0.92 * A0
            # conical dome: broad shoulders that pull in steadily to the peak
            rho = rho0 * (1 - u ** 1.15) + 0.0052 * u ** 1.15
            a = A0 + (AU - A0) * smoothstep(0.06, 0.22, u)
        pts.append((rho * math.cos(th), rho * math.sin(th), z))
        rad.append(a)
    pts = np.array(pts)
    rad = np.array(rad)
    # the tip: rises up through the centre and curls over to the front-right,
    # like the reference photo's flame-shaped peak
    pe = pts[-1]
    te = pts[-1] - pts[-6]
    te /= np.linalg.norm(te)
    zt = pe[2]
    tip = np.array([
        pe + te * 0.0060 + np.array([0, 0, 0.0035]),
        (0.0010, 0.0004, zt + 0.0125),
        (0.0035, -0.0012, zt + 0.0250),
        (0.0110, -0.0032, zt + 0.0345),
        (0.0205, -0.0046, zt + 0.0368),
        (0.0280, -0.0052, zt + 0.0318),
    ])
    a_end = rad[-1]
    trad = a_end * np.array([1.04, 1.0, 0.88, 0.68, 0.43, 0.12])
    pts = np.vstack([pts, tip])
    rad = np.concatenate([rad, trad])
    return pts, rad, T1


def resample(pts, rad, step):
    # Catmull-Rom by chord length, then even arclength sampling
    from scipy.interpolate import make_interp_spline
    d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    keep = np.concatenate([[True], d > 1e-7])
    pts, rad = pts[keep], rad[keep]
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    sp = make_interp_spline(s, pts, k=3)
    sr = make_interp_spline(s, rad, k=1)
    fine = np.linspace(0, s[-1], int(s[-1] / (step / 8)))
    fp = sp(fine)
    fs = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(fp, axis=0), axis=1))])
    L = fs[-1]
    S = np.linspace(0, L, int(L / step) + 1)
    P = np.stack([np.interp(S, fs, fp[:, k]) for k in range(3)], -1)
    R = np.interp(np.interp(S, fs, fine), s, sr(s))
    return P, R, S, L


def smooth_noise(n, scale, seed):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n + 64)
    from scipy.ndimage import gaussian_filter1d
    out = gaussian_filter1d(w, scale)[32:32 + n]
    return out / (np.abs(out).max() + 1e-9)


def rmf(P):
    """Rotation-minimising frames (double reflection, Wang et al. 2008)."""
    Tn = np.gradient(P, axis=0)
    Tn /= np.linalg.norm(Tn, axis=1)[:, None]
    n = len(P)
    N = np.zeros_like(P)
    up = np.array([0, 0, 1.0])
    n0 = np.cross(Tn[0], up)
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(Tn[0], [1, 0, 0])
    N[0] = n0 / np.linalg.norm(n0)
    for i in range(n - 1):
        v1 = P[i + 1] - P[i]
        c1 = v1 @ v1
        rL = N[i] - (2 / c1) * (v1 @ N[i]) * v1
        tL = Tn[i] - (2 / c1) * (v1 @ Tn[i]) * v1
        v2 = Tn[i + 1] - tL
        c2 = v2 @ v2
        N[i + 1] = rL - (2 / c2) * (v2 @ rL) * v2 if c2 > 1e-12 else rL
        N[i + 1] /= np.linalg.norm(N[i + 1])
    B = np.cross(Tn, N)
    return Tn, N, B


SIM = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None


def sim_centerline():
    """The rope exactly where the pour simulation (sim.py) left it, in Blender axes,
    with its radius from volume conservation (stretched -> thinner, squashed -> fatter)."""
    meta = json.load(open(os.path.join(SIM, "pour-sim.json")))
    F = np.load(os.path.join(SIM, "pour-final.npy"))
    pts = np.stack([F[:, 0], -F[:, 2], F[:, 1]], -1)          # glTF (x, y-up, z-front) -> Blender
    rest = np.array(meta["rest"])
    rr = meta["radius"] * np.sqrt(meta["spacing"] / rest)
    rad = np.empty(len(pts))
    rad[0], rad[-1] = rr[0], rr[-1]
    rad[1:-1] = 0.5 * (rr[:-1] + rr[1:])
    return pts, np.clip(rad, 0.62 * A0, 1.2 * A0)


def build_swirl():
    pts, rad = sim_centerline() if SIM else build_centerline()[:2]
    step = 0.0011
    P, R, S, L = resample(pts, rad, step)
    n = len(P)
    # taper the very end (where the tail broke off at the spout) into a soft point
    tail = 0.012
    u = np.clip((S - (L - tail)) / tail, 0, 1)
    R *= np.sqrt(np.clip(1 - u ** 2.4, 0, 1)) * (1 - 0.15 * u) + 1e-5
    Tn, N, B = rmf(P)
    m = 48
    phis = np.arange(m) * 2 * math.pi / m
    upz = np.array([0, 0, 1.0])
    verts = []
    for i in range(n):
        Ui = upz - (upz @ Tn[i]) * Tn[i]
        un = np.linalg.norm(Ui)
        horiz = 1 - abs(Tn[i][2])
        squash = 1 - 0.20 * smoothstep(0.55, 0.95, horiz) * (1 - u[i])
        Ui = Ui / un if un > 1e-6 else N[i]
        twist = S[i] * 9.0
        for phi in phis:
            ridge = 0.065 * math.cos(6 * (phi + twist)) - 0.015 * math.cos(12 * (phi + twist))
            ridge *= 1 - 0.7 * u[i]
            o = math.cos(phi) * N[i] + math.sin(phi) * B[i]
            ou = (o @ Ui) * Ui
            o = (o - ou) * (1 + 0.06 * (1 - squash) * 2) + ou * squash
            verts.append(P[i] + o * R[i] * (1 + ridge))
    # froyo presses flat against the paper: nothing below the rim may cross the inner wall
    V = np.array(verts)
    rr = np.hypot(V[:, 0], V[:, 1])
    lim = np.array([r_in(z) for z in V[:, 2]]) - 0.0003
    below = V[:, 2] < H - 0.0006
    over = below & (rr > lim)
    # soft clamp: compress the overshoot into a thin band so the flattening has no hard crease
    excess = rr - (lim - 0.0012)
    soft = np.where(excess > 0, (lim - 0.0012) + 0.0012 * np.tanh(excess / 0.0012), rr)
    k = np.where(below & (excess > 0), soft / np.maximum(rr, 1e-9), 1.0)
    V[:, 0] *= k
    V[:, 1] *= k
    verts = [tuple(v) for v in V]
    print("flattened against the wall:", int(over.sum()), "verts")
    start_c = len(verts)
    verts.append(P[0] - Tn[0] * R[0] * 0.6)
    end_c = len(verts)
    verts.append(P[-1] + Tn[-1] * 0.0004)
    faces, fcol = [], []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
            fcol.append(j)
    for j in range(m):
        j2 = (j + 1) % m
        faces.append((start_c, j2, j))
        fcol.append(j)
        faces.append(((n - 1) * m + j, (n - 1) * m + j2, end_c))
        fcol.append(j)
    reveal = np.concatenate([np.repeat(S / L, m), [0.0, 1.0]])
    circ = 2 * math.pi * A0

    def cuv(fi, ci, vi):
        if vi >= start_c:
            ring, j = (0 if vi == start_c else n - 1), fcol[fi]
        else:
            ring, j = vi // m, vi % m
            if j < fcol[fi]:
                j = m  # wrapped corner
        return (S[ring] / 0.04, j / m * circ / 0.04)

    uv = loop_uvs_from_face_corners(faces, cuv)
    ob = mesh_obj("Swirl", verts, faces, [M["froyo"]], uvs={"UVMap": uv}, attrs={"_reveal": reveal})
    return ob, P, R, S, L


SWIRL_OBJ = os.environ.get("SWIRL_OBJ")


def import_swirl(path):
    """The finished swirl: the last frame of the froyo simulation (mpm.py), meshed by analyze.py."""
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    ob = [o for o in bpy.data.objects if o not in before][0]
    ob.name = "Swirl"
    ob.data.materials.clear()
    ob.data.materials.append(M["froyo"])
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_smooth()
    return ob


if SWIRL_OBJ:
    swirl = import_swirl(SWIRL_OBJ)
    SP = np.zeros((2, 3))
    SL = 1.0
else:
    swirl, SP, SR, SS, SL = build_swirl()


# the hidden fill inside the cup that rises as it's poured (seen between coils from above)
def swirl_core():
    zt = H - 0.0085
    prof = [(0.0, 0.0), (r_in(ZB + 0.001) - 0.0016, 0.0)]
    for z in np.linspace(ZB + 0.002, zt, 10):
        prof.append((r_in(z) - 0.0022, z - ZB))
    prof += [(r_in(zt) * 0.6, zt - ZB + 0.0025), (0.0, zt - ZB + 0.0032)]
    ob = revolve("SwirlCore", prof, 64, [M["froyo"]], uv_scale=(3, 25))
    ob.location = (0, 0, ZB)
    return ob


# (the simulated rope fills the cup solid, so no hidden core is needed any more)

# group the product under one root so it imports as a single model
cup_root = bpy.data.objects.new("IliosFroyoCup", None)
scene.collection.objects.link(cup_root)
for o in (cup, seam, emblem, swirl):
    o.parent = cup_root

# =====================================================================
# THE STATION  (the shop's wall-set, three-handle twist machine + the room around it)
# Modelled on the real Ilios counter: the machine sits in a limewash niche with a plaster
# frame; a white header sign reads "Sweet Harbor Coffee | sun + ILIOS FROYO | Organic Vanilla
# Bean"; brushed faceplate, black door, three black ball draw handles (left flavor, twist,
# right flavor), a black drip tray with three oval drains, paper cups stacked on the tray.
# =====================================================================
M["blackgloss"] = make_mat("Black Door Plastic", lin("#111112"), 0.2, coat=0.5, coat_rough=0.12)
M["ball"] = make_mat("Black Handle Ball", lin("#0b0b0c"), 0.34, coat=0.25, coat_rough=0.2, spec=0.4)
M["blackmatte"] = make_mat("Black Tray", lin("#121212"), 0.55)
M["whiteplastic"] = make_mat("Spout Plastic", lin("#ecebe6"), 0.32, coat=0.3, coat_rough=0.2)
M["sign"] = make_mat("Header Sign", lin("#ffffff"), 0.42, base_tex="sign_color.png", spec=0.3)
M["red"] = make_mat("Red Indicator", lin("#c42a22"), 0.3, emission=lin("#ff3a2a"), emission_strength=3.0)
M["caution"] = make_mat("Caution Label", lin("#ffffff"), 0.45, base_tex="sticker_caution.png")
M["service"] = make_mat("Service Label", lin("#ffffff"), 0.45, base_tex="sticker_service.png")
M["labels"] = make_mat("Switch Labels", lin("#ffffff"), 0.4, base_tex="switch_labels.png")
M["limewash"] = make_mat("Limewash Plaster", lin("#ffffff"), 0.93, base_tex="limewash_color.jpg",
                         normal="limewash_normal.png", normal_strength=0.4, spec=0.25)
M["travertine"] = make_mat("Travertine", lin("#ffffff"), 0.38, base_tex="travertine_color.jpg",
                           normal="travertine_normal.png", normal_strength=0.5, coat=0.15, coat_rough=0.3)
M["wallgold"] = make_mat("Wall Sun Gold", lin("#c39a4e"), 0.3, metal=1.0, base_tex="badge_color.png",
                         orm="badge_orm.png", normal="badge_normal.png", normal_strength=1.0,
                         uv="Decal", alpha_from_base=True)

WALL_Y = -0.300            # front face of the shop wall
NW, NH = 0.370, 1.020      # niche half-width, height (sill at z = 0)
FACE_Y = -0.160            # brushed faceplate front
SPOUT_X = (-0.100, 0.0, 0.100)
SPOUT_Y = -0.272
NOZ_Z = 0.362
NOZZLES = [Vector((x, SPOUT_Y, NOZ_Z)) for x in SPOUT_X]
NOZ = NOZZLES[1]
TRAY_TOP = 0.0645
PULL = math.radians(55)

mach_root = bpy.data.objects.new("IliosSoftServeMachine", None)
scene.collection.objects.link(mach_root)
room_root = bpy.data.objects.new("IliosRoom", None)
scene.collection.objects.link(room_root)
parts, room = [], []


def add(o):
    parts.append(o)
    return o


def addr(o):
    room.append(o)
    return o


def decal(name, w, h, center, mat, uvname="UVMap", y_out=-1):
    """Flat quad facing -Y (the room's front) with a 0..1 UV."""
    cx, cy, cz = center
    verts = [(cx - w / 2, cy, cz - h / 2), (cx + w / 2, cy, cz - h / 2), (cx + w / 2, cy, cz + h / 2),
             (cx - w / 2, cy, cz + h / 2)]
    faces = [(0, 1, 2, 3)]
    uvs = {uvname: [(0, 0), (1, 0), (1, 1), (0, 1)]}
    return mesh_obj(name, verts, faces, [mat], uvs=uvs, smooth=False)


# ---- faceplate, sign, details
add(rbox("Faceplate", (2 * NW - 0.012, 0.030, 0.790), (0, FACE_Y + 0.015, 0.070 + 0.395), 0.004, M["steel"], segs=3, uv=0.22))
add(rbox("PanelSeam", (2 * NW - 0.03, 0.002, 0.003), (0, FACE_Y - 0.0005, 0.352), 0.0008, M["blackmatte"], segs=1))
add(rbox("SignPanel", (2 * NW - 0.024, 0.016, 0.142), (0, FACE_Y - 0.010, 0.918), 0.004, M["whiteplastic"], segs=3))
add(decal("SignFace", 2 * NW - 0.034, 0.134, (0, FACE_Y - 0.0185, 0.918), M["sign"]))
add(decal("SwitchLabels", 0.50, 0.032, (0, FACE_Y - 0.0006, 0.818), M["labels"]))
for k in range(8):
    x = -0.21 + k * 0.06
    add(cyl(f"ToggleBase{k}", 0.0055, 0.006, (x, FACE_Y - 0.003, 0.795), M["chrome"], rot=(math.pi / 2, 0, 0), verts=20))
    lever = add(cyl(f"Toggle{k}", 0.0016, 0.016, (x, FACE_Y - 0.010, 0.799), M["chrome"], rot=(math.radians(60), 0, 0), verts=10))
for sx in (-1, 1):
    add(rbox(f"RedLight{sx}", (0.012, 0.006, 0.032), (sx * 0.272, FACE_Y - 0.002, 0.640), 0.002, M["red"], segs=2))
add(decal("CautionLabel", 0.072, 0.042, (-0.090, FACE_Y - 0.0008, 0.640), M["caution"]))
add(decal("ServiceLabel", 0.086, 0.050, (0.215, FACE_Y - 0.0008, 0.452), M["service"]))
add(rbox("DataPlate", (0.040, 0.004, 0.060), (-0.282, FACE_Y - 0.002, 0.430), 0.002, M["chrome"], segs=2))
for sx in (-1, 1):
    for sz in (-1, 1):
        add(cyl(f"PanelScrew{sx}{sz}", 0.0035, 0.003, (sx * 0.322, FACE_Y - 0.001, 0.465 + sz * 0.37), M["chrome"],
                rot=(math.pi / 2, 0, 0), verts=16))

# ---- the freezer door (black) with spouts and star knobs
add(rbox("Door", (0.340, 0.128, 0.150), (0, FACE_Y - 0.064, 0.498), 0.024, M["blackgloss"], segs=8))
add(rbox("DoorCap", (0.300, 0.100, 0.020), (0, FACE_Y - 0.058, 0.582), 0.008, M["blackgloss"], segs=4))
add(rbox("DoorParting", (0.344, 0.129, 0.003), (0, FACE_Y - 0.064, 0.452), 0.001, M["blackmatte"], segs=1))
add(rbox("DoorGasket", (0.352, 0.006, 0.166), (0, FACE_Y - 0.002, 0.498), 0.003, M["blackmatte"], segs=2))
add(rbox("DoorBridge", (0.300, 0.020, 0.024), (0, SPOUT_Y + 0.004, 0.400), 0.006, M["blackgloss"], segs=3))
for i, x in enumerate(SPOUT_X):
    add(lathe(f"Spout{i}", [(0.0, 0.040), (0.020, 0.040), (0.0205, 0.030), (0.0185, 0.026), (0.0180, 0.008),
                            (0.0170, 0.002), (0.0160, 0.0), (0.0, 0.0)], M["whiteplastic"],
              loc=(x, SPOUT_Y, NOZ_Z), segs=64))

    def mouth(x=x, i=i):
        m = 72
        verts, faces = [], []
        for ring, (rr, z) in enumerate([(0.0150, 0.0004), (0.0110, 0.0), (0.0110, 0.028)]):
            for j in range(m):
                phi = j / m * 2 * math.pi
                k = 1 + 0.16 * math.cos(6 * phi) if ring > 0 else 1
                verts.append((x + rr * k * math.cos(phi), SPOUT_Y + rr * k * math.sin(phi), NOZ_Z + z - 0.0004))
        for r in range(2):
            for j in range(m):
                j2 = (j + 1) % m
                faces.append((r * m + j, r * m + j2, (r + 1) * m + j2, (r + 1) * m + j))
        return mesh_obj(f"SpoutStar{i}", verts, faces, [M["blackmatte"]])
    add(mouth())
for sx in (-1, 1):
    x = sx * 0.050
    add(cyl(f"StarKnobHub{sx}", 0.010, 0.020, (x, FACE_Y - 0.135, 0.418), M["blackgloss"], rot=(math.pi / 2, 0, 0),
            verts=24, bevel=0.002))
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        add(cyl(f"StarKnobLobe{sx}{k}", 0.0065, 0.018, (x + 0.011 * math.cos(a), FACE_Y - 0.135, 0.418 + 0.011 * math.sin(a)),
                M["blackgloss"], rot=(math.pi / 2, 0, 0), verts=16, bevel=0.002))

# ---- three draw handles: left flavor, twist, right flavor
HANDLE_NAMES = ("HandleL", "HandleC", "HandleR")
PIVS = [Vector((x, FACE_Y - 0.126, 0.590)) for x in SPOUT_X]
handles = []
for name, PIV in zip(HANDLE_NAMES, PIVS):
    h = bpy.data.objects.new(name, None)
    scene.collection.objects.link(h)
    h.location = PIV
    hp = []
    adir = Vector((0, -1, 0.30)).normalized()
    alen = 0.118
    arm = cyl(f"{name}Arm", 0.0055, alen, PIV + adir * (alen / 2), M["chrome"], verts=24)
    arm.rotation_euler = adir.to_track_quat("Z", "Y").to_euler()
    hp.append(arm)
    hp.append(cyl(f"{name}Hub", 0.0095, 0.022, PIV, M["chrome"], rot=(0, math.pi / 2, 0), verts=32, bevel=0.002))
    ball = bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.026,
                                                location=PIV + adir * (alen + 0.020))
    ball = bpy.context.active_object
    ball.name = f"{name}Ball"
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(M["ball"])
    hp.append(ball)
    col = cyl(f"{name}Collar", 0.0085, 0.010, PIV + adir * (alen - 0.004), M["chrome"], verts=24)
    col.rotation_euler = adir.to_track_quat("Z", "Y").to_euler()
    hp.append(col)
    bpy.context.view_layer.update()
    for p in hp:
        parent(p, h)
    handles.append(h)
    # the wire hanger that runs up the faceplate from each handle
    top = Vector((PIV.x, FACE_Y - 0.006, 0.790))
    bot = PIV + Vector((0, 0.012, 0.016))
    mid = (top + bot) / 2
    wire = add(cyl(f"{name}Hanger", 0.0022, (top - bot).length, mid, M["chrome"], verts=12))
    wire.rotation_euler = (top - bot).normalized().to_track_quat("Z", "Y").to_euler()
    add(cyl(f"{name}Clip", 0.0045, 0.010, top, M["chrome"], rot=(math.pi / 2, 0, 0), verts=16))

# ---- drip tray: black tray, brushed top with three oval drains, back rail
add(rbox("DripTray", (2 * NW - 0.040, 0.245, 0.060), (0, FACE_Y - 0.1225, 0.030), 0.006, M["blackmatte"], segs=3))
add(rbox("TrayTop", (2 * NW - 0.070, 0.225, 0.005), (0, FACE_Y - 0.1225, TRAY_TOP - 0.0025), 0.0015, M["steel"], segs=2))
for i, x in enumerate(SPOUT_X):
    o = add(cyl(f"Drain{i}", 1.0, 0.002, (x, SPOUT_Y - 0.004, TRAY_TOP + 0.0002), M["blackmatte"], verts=48))
    o.scale = (0.036, 0.019, 1)
add(cyl("BackRail", 0.0055, 2 * NW - 0.08, (0, FACE_Y - 0.010, 0.082), M["steel"], rot=(0, math.pi / 2, 0), verts=24))

# ---- paper cups stacked on the tray, and a few sample cups
for i in range(6):
    for src in (cup, seam, emblem):
        o = bpy.data.objects.new(f"Stack{src.name}{i}", src.data)
        scene.collection.objects.link(o)
        o.location = (-0.262, FACE_Y - 0.062, TRAY_TOP + 0.0004 + i * 0.0105)
        o.rotation_euler = (0, 0, math.radians(-30 + i * 7))
        add(o)
M["sample"] = make_mat("Sample Cup", lin("#f1eee7"), 0.45, spec=0.35)
for i in range(4):
    add(lathe(f"SampleCup{i}", [(0.0, 0.0), (0.0145, 0.0), (0.0185, 0.028), (0.0190, 0.0285), (0.0182, 0.0285),
                                (0.0140, 0.0006), (0.0, 0.0006)], M["sample"],
              loc=(0.262, FACE_Y - 0.040, TRAY_TOP + i * 0.0045), segs=48))

# ---- the room: limewash wall with the niche, plaster frame, travertine ledge, gold sun + letters
def slab_box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0, uv=1.0):
    o = rbox(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
             max(bevel, 0.0002), mat, segs=3 if bevel else 1, uv=uv)
    return o


T_W = 0.06
addr(slab_box("WallL", -2.6, -NW - 0.0, WALL_Y, WALL_Y + T_W, -0.95, 2.6, M["limewash"], uv=1.0))
addr(slab_box("WallR", NW, 2.6, WALL_Y, WALL_Y + T_W, -0.95, 2.6, M["limewash"], uv=1.0))
addr(slab_box("WallTop", -NW, NW, WALL_Y, WALL_Y + T_W, NH, 2.6, M["limewash"], uv=1.0))
addr(slab_box("WallBelow", -NW, NW, WALL_Y, WALL_Y + T_W, -0.95, 0.0, M["limewash"], uv=1.0))
# niche reveals and back
addr(slab_box("RevealL", -NW - 0.02, -NW, WALL_Y, 0.10, 0.0, NH, M["limewash"], uv=1.0))
addr(slab_box("RevealR", NW, NW + 0.02, WALL_Y, 0.10, 0.0, NH, M["limewash"], uv=1.0))
addr(slab_box("RevealTop", -NW, NW, WALL_Y, 0.10, NH, NH + 0.02, M["limewash"], uv=1.0))
addr(slab_box("NicheBack", -NW, NW, 0.08, 0.10, 0.0, NH, M["limewash"], uv=1.0))
# raised plaster frame around the opening
FR, FD = 0.072, 0.034
addr(slab_box("FrameL", -NW - FR, -NW, WALL_Y - FD, WALL_Y, 0.0, NH + FR, M["limewash"], bevel=0.008, uv=1.0))
addr(slab_box("FrameR", NW, NW + FR, WALL_Y - FD, WALL_Y, 0.0, NH + FR, M["limewash"], bevel=0.008, uv=1.0))
addr(slab_box("FrameTop", -NW, NW, WALL_Y - FD, WALL_Y, NH, NH + FR, M["limewash"], bevel=0.008, uv=1.0))
# travertine sill inside the niche and a ledge running along the wall
addr(slab_box("NicheSill", -NW, NW, WALL_Y, 0.08, -0.03, 0.0, M["travertine"], uv=0.8))
addr(slab_box("Ledge", -1.9, 1.9, WALL_Y - 0.240, WALL_Y, -0.045, 0.0, M["travertine"], bevel=0.004, uv=0.8))
addr(slab_box("LedgeApron", -1.9, 1.9, WALL_Y - 0.236, WALL_Y, -0.95, -0.045, M["limewash"], uv=1.0))

# the gold sun relief on the wall, beside the niche, with ILIOS / FROYO in gold letters
SUN_C = Vector((0.86, WALL_Y - 0.010, 1.08))
sun_plate = addr(cyl("WallSunDisc", 0.086, 0.008, SUN_C + Vector((0, 0.006, 0.0)), M["gold"],
                     rot=(math.pi / 2, 0, 0), verts=96, bevel=0.003))
sun = decal("WallSun", 0.46, 0.46, (SUN_C.x, WALL_Y - 0.0122, SUN_C.z), M["wallgold"], uvname="Decal")
addr(sun)


def gold_text(name, body, size, loc, font="Italiana-Regular.ttf", extrude=0.004, spacing=1.25):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    path = None
    for d in ("/mnt/skills/examples/canvas-design/canvas-fonts",):
        p = os.path.join(d, font)
        if os.path.exists(p):
            path = p
    if path:
        cu.font = bpy.data.fonts.load(path)
    cu.size = size
    cu.extrude = extrude
    cu.space_character = spacing
    cu.align_x = "CENTER"
    cu.align_y = "BOTTOM"
    o = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi / 2, 0, 0)
    select_only(o)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.active_object
    o.data.materials.clear()
    o.data.materials.append(M["gold"])
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    box_uv(o, 0.2)
    return o


addr(gold_text("WallILIOS", "ILIOS", 0.085, (SUN_C.x - 0.020, WALL_Y - 0.004, SUN_C.z - 0.330)))
addr(gold_text("WallFROYO", "FROYO", 0.046, (SUN_C.x + 0.050, WALL_Y - 0.004, SUN_C.z - 0.385)))

bpy.context.view_layer.update()
for p in parts:
    parent(p, mach_root)
for h in handles:
    parent(h, mach_root)
for p in room:
    parent(p, room_root)

# handle animation (twist handle) for the glTF clip
handle = handles[1]
handle.rotation_mode = "XYZ"
handle.rotation_euler = (0, 0, 0)
handle.keyframe_insert("rotation_euler", frame=1)
handle.rotation_euler = (PULL, 0, 0)
handle.keyframe_insert("rotation_euler", frame=24)
handle.rotation_euler = (0, 0, 0)
act = handle.animation_data.action
act.name = "PullHandle"
scene.frame_start, scene.frame_end = 1, 24
scene.render.fps = 24
scene.frame_set(1)
PIV = PIVS[1]

# place the cup under the twist spout on the drip tray, for renders and for the json
cup_root.location = (NOZ.x, NOZ.y, TRAY_TOP + 0.0004)


# =====================================================================
# export
# =====================================================================
def to_gltf(v):
    return [round(float(v[0]), 6), round(float(v[2]), 6), round(float(-v[1]), 6)]


meta = {
    "units": "metres, glTF Y-up",
    "note": "Machine layout for the pour. The froyo itself is the baked simulation (pour.json / pour.bin).",
    "cupLocalToMachine": to_gltf(cup_root.location),
    "nozzleMachine": to_gltf(NOZ),
    "handlePivotMachine": to_gltf(PIV),
    "handlePullRadians": PULL,
    "handles": ["HandleL", "HandleC", "HandleR"],
    "nozzlesMachine": [to_gltf(n) for n in NOZZLES],
    "cupBasesMachine": [to_gltf((n.x, n.y, TRAY_TOP + 0.0004)) for n in NOZZLES],
    "handleAxis": "x",
    "cupHeight": H,
    "rimRadius": RT,
}
with open(os.path.join(OUT, "pour-path.json"), "w") as f:
    json.dump(meta, f)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "ilios.blend"))


def export(root, path, anim=False):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    stack = [root]
    while stack:
        o = stack.pop()
        o.select_set(True)
        stack.extend(o.children)
    loc = root.location.copy()
    root.location = (0, 0, 0)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_attributes=True,
        export_animations=anim,
        export_animation_mode="ACTIONS",
        export_force_sampling=False,
        export_yup=True,
        export_image_format="AUTO",
        export_extras=False,
    )
    root.location = loc


export(cup_root, os.path.join(OUT, "ilios-froyo-cup.glb"))
export(mach_root, os.path.join(OUT, "ilios-softserve-machine.glb"), anim=True)
export(room_root, os.path.join(OUT, "ilios-room.glb"))

print("swirl verts %d" % len(swirl.data.vertices))
print("cup verts", len(cup.data.vertices))
print("done ->", OUT)

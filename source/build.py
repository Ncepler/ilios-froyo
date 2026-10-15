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
M["froyo"] = make_mat("Organic Greek Froyo", lin("#f2ead2"), 0.38, orm="froyo_orm.png",
                      normal="froyo_normal.png", normal_strength=0.45, coat=0.18, coat_rough=0.32,
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


def build_swirl():
    pts, rad, T1 = build_centerline()
    step = 0.0011
    P, R, S, L = resample(pts, rad, step)
    n = len(P)
    # organic wobble of the centreline and thickness
    P[:, 0] += 0.00035 * smooth_noise(n, 18, 1)
    P[:, 1] += 0.00035 * smooth_noise(n, 18, 2)
    P[:, 2] += 0.00025 * smooth_noise(n, 22, 3)
    R *= 1 + 0.035 * smooth_noise(n, 14, 4)
    # taper the very end into a soft rounded point
    tail = 0.016
    u = np.clip((S - (L - tail)) / tail, 0, 1)
    R *= np.sqrt(np.clip(1 - u ** 2.4, 0, 1)) * (1 - 0.15 * u) + 1e-5
    # and swell the start so it reads as a blob landing in the cup
    R *= 1 + 0.15 * (1 - smoothstep(0, 0.05, S))
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


core = swirl_core()

# group the product under one root so it imports as a single model
cup_root = bpy.data.objects.new("IliosFroyoCup", None)
scene.collection.objects.link(cup_root)
for o in (cup, seam, emblem, swirl, core):
    o.parent = cup_root

# =====================================================================
# THE MACHINE  (countertop single-head soft-serve freezer, Ilios edition)
# =====================================================================
FRONT = -0.200            # front face of the body
NOZ = Vector((0.0, -0.290, 0.335))   # star-spout exit point
TRAY_TOP = 0.062

mach_root = bpy.data.objects.new("IliosSoftServeMachine", None)
scene.collection.objects.link(mach_root)
parts = []


def add(o):
    parts.append(o)
    return o


# body shell + plinth
add(rbox("Body", (0.420, 0.600, 0.720), (0, FRONT + 0.300, 0.040 + 0.360), 0.028, M["body"]))
add(rbox("BodyPlinth", (0.430, 0.610, 0.022), (0, FRONT + 0.300, 0.034), 0.006, M["steel"]))
# top deck + hopper lid with a cream knob
add(rbox("TopDeck", (0.400, 0.560, 0.012), (0, FRONT + 0.300, 0.766), 0.005, M["steel"]))
add(lathe("HopperLid", [(0, 0.020), (0.095, 0.020), (0.105, 0.016), (0.110, 0.006), (0.112, 0.0)],
          M["steel"], loc=(0, FRONT + 0.36, 0.772), segs=96))
add(lathe("HopperKnob", [(0, 0), (0.016, 0), (0.017, 0.006), (0.010, 0.016), (0.012, 0.024),
                         (0.008, 0.030), (0, 0.031)], M["knob"], loc=(0, FRONT + 0.36, 0.792)))
# feet
for sx in (-1, 1):
    for sy in (0, 1):
        y = FRONT + 0.045 + sy * 0.51
        add(cyl(f"Foot{sx}{sy}", 0.017, 0.020, (sx * 0.175, y, 0.014), M["chrome"], bevel=0.003))
        add(cyl(f"FootPad{sx}{sy}", 0.019, 0.006, (sx * 0.175, y, 0.003), M["rubber"], bevel=0.002))
# side vents: recessed slots on both sides
for sx in (-1, 1):
    for k in range(16):
        add(rbox(f"Vent{sx}_{k}", (0.006, 0.300, 0.0075),
                 (sx * 0.2085, FRONT + 0.36, 0.090 + k * 0.016), 0.0035, M["vent"], segs=3))
# freezer door (brushed steel) with four black star knobs
add(rbox("FreezerDoor", (0.300, 0.026, 0.240), (0, FRONT - 0.011, 0.480), 0.010, M["steel"]))
add(rbox("DoorGasket", (0.312, 0.008, 0.252), (0, FRONT - 0.002, 0.480), 0.004, M["black"]))
for sx in (-1, 1):
    for sz in (-1, 1):
        k = add(lathe(f"DoorKnob{sx}{sz}", [(0, 0), (0.016, 0), (0.017, 0.004), (0.015, 0.014),
                                            (0.012, 0.018), (0, 0.019)], M["black"],
                      loc=(sx * 0.128, FRONT - 0.024, 0.480 + sz * 0.098), rot=(math.pi / 2, 0, 0), segs=12,
                      smooth=False))
        add(cyl(f"DoorStud{sx}{sz}", 0.005, 0.012, (sx * 0.128, FRONT - 0.045, 0.480 + sz * 0.098),
                M["chrome"], rot=(math.pi / 2, 0, 0), verts=24))
# dispensing head
add(rbox("Head", (0.130, 0.105, 0.095), (0, FRONT - 0.070, 0.405), 0.022, M["steel"], segs=8))
add(rbox("HeadTrim", (0.134, 0.006, 0.099), (0, FRONT - 0.121, 0.405), 0.003, M["chrome"], segs=4))
add(rbox("HeadCollar", (0.150, 0.016, 0.115), (0, FRONT - 0.030, 0.405), 0.008, M["steel"]))
add(cyl("PrimePlug", 0.010, 0.014, (0.032, FRONT - 0.075, 0.457), M["black"], bevel=0.002))
# spout: a turned chrome nozzle with a six-point star mouth
spout = add(lathe("Spout", [(0.0, 0.040), (0.026, 0.040), (0.027, 0.036), (0.022, 0.030),
                            (0.0195, 0.016), (0.0185, 0.004), (0.0175, 0.0), (0.0, 0.0)],
                  M["chrome"], loc=(NOZ.x, NOZ.y, NOZ.z), segs=96))
star = []
for k in range(13):
    a = k / 12 * 2 * math.pi
    star.append(a)


def star_mouth():
    m = 96
    verts, faces = [], []
    for ring, (rr, z) in enumerate([(0.0168, 0.0005), (0.0128, 0.0), (0.0128, 0.030)]):
        for j in range(m):
            phi = j / m * 2 * math.pi
            k = 1 + 0.16 * math.cos(6 * phi) if ring > 0 else 1
            verts.append((NOZ.x + rr * k * math.cos(phi), NOZ.y + rr * k * math.sin(phi), NOZ.z + z - 0.0004))
    for r in range(2):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((r * m + j, r * m + j2, (r + 1) * m + j2, (r + 1) * m + j))
    ob = mesh_obj("SpoutStar", verts, faces, [M["black"]])
    return ob


add(star_mouth())

# ---- draw handle (animated). Pivot sits on a clevis on top of the head.
PIV = Vector((0.0, FRONT - 0.112, 0.468))
handle = bpy.data.objects.new("Handle", None)
scene.collection.objects.link(handle)
handle.location = PIV
for sx in (-1, 1):
    add(rbox(f"Clevis{sx}", (0.007, 0.040, 0.034), (sx * 0.016, PIV.y + 0.012, PIV.z - 0.010), 0.003,
             M["chrome"], segs=4))
add(cyl("PivotPin", 0.0045, 0.046, PIV, M["gold"], rot=(0, math.pi / 2, 0), verts=32, bevel=0.0015))
hparts = []
arm_dir = Vector((0, -1, 0.58)).normalized()
arm_len = 0.165
mid = PIV + arm_dir * (arm_len / 2)
arm = cyl("HandleArm", 0.0072, arm_len, mid, M["chrome"], verts=32)
arm.rotation_euler = arm_dir.to_track_quat("Z", "Y").to_euler()
hparts.append(arm)
hparts.append(cyl("HandleHub", 0.012, 0.024, PIV, M["chrome"], rot=(0, math.pi / 2, 0), verts=40, bevel=0.003))
tip = PIV + arm_dir * arm_len
knob = lathe("HandleKnob", [(0, -0.027), (0.012, -0.0265), (0.020, -0.021), (0.0240, -0.011),
                            (0.0250, 0.0), (0.0240, 0.011), (0.020, 0.020), (0.014, 0.0255), (0, 0.0262)],
             M["knob"], loc=tip + arm_dir * 0.019, segs=64)
cap = lathe("HandleCap", [(0, 0.0), (0.0115, 0.0), (0.0118, 0.0012), (0.0100, 0.0022), (0, 0.0026)],
            M["gold"], loc=tip + arm_dir * (0.019 + 0.0246), segs=48)
cap.rotation_euler = arm_dir.to_track_quat("Z", "Y").to_euler()
hparts.append(cap)
knob.rotation_euler = arm_dir.to_track_quat("Z", "Y").to_euler()
hparts.append(knob)
ring = lathe("HandleRing", [(0.0076, 0.0), (0.0118, 0.0), (0.0124, 0.0028), (0.0118, 0.0056), (0.0076, 0.0056)],
             M["gold"], loc=tip - arm_dir * 0.006, segs=48)
ring.rotation_euler = arm_dir.to_track_quat("Z", "Y").to_euler()
hparts.append(ring)
# the plunger link: a short rod from the hub into the head (slides when pulled)
link = cyl("PlungerLink", 0.0045, 0.040, PIV + Vector((0, 0.010, -0.022)), M["chrome"], verts=24)
hparts.append(link)
bpy.context.view_layer.update()
for p in hparts:
    parent(p, handle)

# ---- drip tray with a perforated grate
add(rbox("DripTray", (0.200, 0.190, 0.034), (0, FRONT - 0.090, 0.045), 0.008, M["steel"]))
add(rbox("TrayLip", (0.204, 0.194, 0.006), (0, FRONT - 0.090, TRAY_TOP - 0.003), 0.003, M["chrome"]))
for k in range(11):
    add(rbox(f"GrateBar{k}", (0.182, 0.006, 0.004), (0, FRONT - 0.172 + k * 0.0165, TRAY_TOP + 0.0005),
             0.0018, M["chrome"], segs=2))
add(rbox("TrayBracket", (0.120, 0.030, 0.050), (0, FRONT - 0.012, 0.055), 0.006, M["steel"]))

# ---- control panel: black glass, warm status LEDs, steel buttons
add(rbox("Panel", (0.300, 0.012, 0.085), (0, FRONT - 0.004, 0.672), 0.010, M["glass"]))
for k, mat in enumerate((M["led_w"], M["led_w"], M["led_g"])):
    add(cyl(f"Led{k}", 0.0032, 0.004, (-0.112 + k * 0.020, FRONT - 0.0105, 0.690), mat,
            rot=(math.pi / 2, 0, 0), verts=20))
for k in range(3):
    add(cyl(f"Button{k}", 0.0105, 0.006, (0.040 + k * 0.034, FRONT - 0.0115, 0.668), M["steel"],
            rot=(math.pi / 2, 0, 0), verts=40, bevel=0.002))
    add(cyl(f"ButtonBezel{k}", 0.0135, 0.002, (0.040 + k * 0.034, FRONT - 0.0102, 0.668), M["chrome"],
            rot=(math.pi / 2, 0, 0), verts=40))
# temperature readout: a thin warm emissive bar behind the glass
add(rbox("Readout", (0.060, 0.002, 0.016), (-0.070, FRONT - 0.0103, 0.662), 0.002, M["led_w"], segs=2))


# ---- the brand badge: a round dark plate with the gold sun
def badge_decal(side):
    """Round dark plate with the gold sun, on a side panel (side = -1 left, +1 right)."""
    r = 0.040
    x = side * (0.210 + 0.0005)
    loc = Vector((x, FRONT + 0.135, 0.560))
    plate = cyl(f"BadgePlate{side}", r + 0.006, 0.004, loc, M["badge_plate"], rot=(0, math.pi / 2, 0), verts=96,
                bevel=0.0015)
    plate.location.x = x + side * 0.0015
    nu = 32
    verts, uvs, faces = [], [], []
    for iv in range(nu + 1):
        for iu in range(nu + 1):
            u, v = iu / nu, iv / nu
            # u runs toward the machine front when seen from that side
            yy = loc.y + (0.5 - u) * 2 * r * side
            verts.append((x + side * 0.0040, yy, loc.z + (v - 0.5) * 2 * r))
            uvs.append((u, v))
    for iv in range(nu):
        for iu in range(nu):
            a = iv * (nu + 1) + iu
            f = (a, a + 1, a + nu + 2, a + nu + 1)
            faces.append(f if side > 0 else f[::-1])
    luv = loop_uvs_from_face_corners(faces, lambda fi, ci, vi: uvs[vi])
    dec = mesh_obj(f"BadgeSun{side}", verts, faces, [M["badge"]], uvs={"Decal": luv})
    return plate, dec


for sd in (-1, 1):
    for o in badge_decal(sd):
        add(o)

# a slim gold pinstripe under the control panel: the only accent on the front
add(rbox("Pinstripe", (0.300, 0.003, 0.003), (0, FRONT - 0.0012, 0.622), 0.001, M["gold"], segs=2))

bpy.context.view_layer.update()
for p in parts:
    parent(p, mach_root)
parent(handle, mach_root)

# handle animation: rest -> pulled (frames 1..24) for the glTF clip
handle.rotation_mode = "XYZ"
handle.rotation_euler = (0, 0, 0)
handle.keyframe_insert("rotation_euler", frame=1)
handle.rotation_euler = (math.radians(62), 0, 0)
handle.keyframe_insert("rotation_euler", frame=24)
handle.rotation_euler = (0, 0, 0)
act = handle.animation_data.action
act.name = "PullHandle"
for fc in act.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
scene.frame_start, scene.frame_end = 1, 24
scene.render.fps = 24
scene.frame_set(1)

# place the cup under the spout on the drip tray, for renders and for the json
cup_root.location = (NOZ.x, NOZ.y, TRAY_TOP + 0.0015)


# =====================================================================
# export
# =====================================================================
def to_gltf(v):
    return [round(float(v[0]), 6), round(float(v[2]), 6), round(float(-v[1]), 6)]


path_out = []
stride = 3
for i in range(0, len(SP), stride):
    path_out.append({"p": to_gltf(SP[i]), "r": round(float(SR[i]), 6), "s": round(float(SS[i] / SL), 6)})
meta = {
    "units": "metres, glTF Y-up",
    "note": "Swirl centreline in the cup's local space. s = the _reveal value at that point.",
    "cupLocalToMachine": to_gltf(cup_root.location),
    "nozzleMachine": to_gltf(NOZ),
    "handlePivotMachine": to_gltf(PIV),
    "handlePullRadians": math.radians(62),
    "handleAxis": "x",
    "swirlLength": round(float(SL), 5),
    "cupHeight": H,
    "rimRadius": RT,
    "insideRevealEnd": None,
    "path": path_out,
}
# reveal value at which the rope rises above the rim (used for the camera)
above = np.where(SP[:, 2] > H)[0]
meta["insideRevealEnd"] = round(float(SS[above[0]] / SL), 5) if len(above) else 0.6
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

print("swirl length %.3f m, verts %d" % (SL, len(swirl.data.vertices)))
print("cup verts", len(cup.data.vertices))
print("done ->", OUT)

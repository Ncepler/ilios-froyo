"""Photoreal Cycles renders of the Ilios cup and machine.

    python render.py <tex_dir> <out_dir> <shot> [samples] [width]

shots: cup_hero, cup_top, cup_macro, machine, machine_pull
"""
import math
import os
import sys

import bpy
from mathutils import Vector

TEX = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
SHOT = sys.argv[3]
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 192
WIDTH = int(sys.argv[5]) if len(sys.argv) > 5 else 1600

bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "ilios.blend"))
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 10
sc.cycles.transparent_max_bounces = 8
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.film_transparent = False
sc.render.image_settings.file_format = "PNG"


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


# ---- world: soft warm ambience
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (*lin("#bdb3a6"), 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.12


# ---- plaster wall (the reference photo's warm greige limewash)
def plaster_mat():
    m = bpy.data.materials.new("Plaster")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.92
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 3.0
    n1.inputs["Detail"].default_value = 8
    n1.inputs["Roughness"].default_value = 0.62
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*lin("#9d958b"), 1)
    ramp.color_ramp.elements[1].color = (*lin("#b9b1a6"), 1)
    nt.links.new(n1.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 140
    n2.inputs["Detail"].default_value = 4
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(n2.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


def marble_mat():
    m = bpy.data.materials.new("Marble")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(os.path.join(TEX, "marble_color.jpg"))
    nt.links.new(t.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.22
    b.inputs["Subsurface Weight"].default_value = 0.15
    b.inputs["Subsurface Scale"].default_value = 0.01
    b.inputs["Coat Weight"].default_value = 0.3
    b.inputs["Coat Roughness"].default_value = 0.08
    return m


def plane(name, size, loc, rot, mat):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (*size, 1)
    o.data.materials.append(mat)
    return o


def slab(name, dims, loc, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    md = o.modifiers.new("b", "BEVEL")
    md.width = 0.002
    md.segments = 3
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1.2)
    bpy.ops.object.mode_set(mode="OBJECT")
    return o


def area(name, loc, target, size, power, color="#fff1df", shape="RECTANGLE", size_y=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = power
    d.size = size
    d.shape = shape
    if size_y:
        d.size_y = size_y
    d.color = lin(color)
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def camera(loc, target, lens, fstop=None, focus=None):
    c = bpy.data.cameras.new("Cam")
    c.lens = lens
    c.clip_start = 0.005
    if fstop:
        c.dof.use_dof = True
        c.dof.aperture_fstop = fstop
        c.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length
    o = bpy.data.objects.new("Cam", c)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = o
    return o


def card(loc, size, strength):
    """Large soft white bounce card, invisible to camera, so metals have something to reflect."""
    m = bpy.data.materials.new("Card")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o_ = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*lin("#fff6ea"), 1)
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], o_.inputs[0])
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.active_object
    o.scale = (size, size, 1)
    o.rotation_euler = (Vector((0, 0, 0.3)) - Vector(loc)).to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(m)
    o.visible_camera = False
    return o


cup = bpy.data.objects["IliosFroyoCup"]


def froyo_plain():
    """Procedural soft-serve: warm white, slightly translucent, satin sheen, fine aeration bump."""
    m = bpy.data.materials.new("Froyo (sim)")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    col = os.environ.get("FROYO_COLOR", "#f2ead2")
    b.inputs["Base Color"].default_value = (*lin(col), 1)
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.30
    b.inputs["Sheen Weight"].default_value = 0.35
    b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Subsurface Weight"].default_value = 0.35
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.85, 0.6)
    b.inputs["Subsurface Scale"].default_value = 0.004
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 900
    n1.inputs["Detail"].default_value = 3
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(n1.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


if os.environ.get("SWIRL_OBJ"):
    for o in list(bpy.data.objects):
        if o.name in ("Swirl", "SwirlCore"):
            bpy.data.objects.remove(o, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.environ["SWIRL_OBJ"], forward_axis="NEGATIVE_Z", up_axis="Y")
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.name = "Swirl"
        o.parent = cup
        o.data.materials.clear()
        o.data.materials.append(froyo_plain())
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.shade_smooth()
mach = bpy.data.objects["IliosSoftServeMachine"]
handle = bpy.data.objects["HandleC"]
room = bpy.data.objects.get("IliosRoom")
plaster = plaster_mat()
marble = marble_mat()

if SHOT.startswith("cup"):
    # cup alone on a marble block against the plaster wall
    for o in mach.children_recursive + [mach] + ((room.children_recursive + [room]) if room else []):
        o.hide_render = True
    cup.location = (0, 0, 0.040)
    slab("Plinth", (0.22, 0.16, 0.040), (0, 0.0, 0.020), marble)
    plane("Wall", (3, 2), (0, 0.32, 0.6), (math.pi / 2, 0, 0), plaster)
    plane("Floor", (3, 3), (0, 0, -0.0005), (0, 0, 0), plaster)
    area("Key", (-0.55, -0.45, 0.55), (0, 0, 0.08), 0.9, 22, "#fff0dc")
    area("Fill", (0.6, -0.5, 0.15), (0, 0, 0.08), 1.2, 5, "#f3f0ea")
    area("Rim", (0.25, 0.45, 0.45), (0, 0, 0.12), 0.4, 7, "#ffe7c4")
    area("Top", (0, -0.05, 0.9), (0, 0, 0.1), 0.6, 5, "#fffaf2")
    if SHOT == "cup_hero":
        sc.render.resolution_x, sc.render.resolution_y = WIDTH, int(WIDTH * 1.25)
        camera((0.0, -0.62, 0.20), (0, 0, 0.105), 85, 4.0)
    elif SHOT == "cup_top":
        sc.render.resolution_x, sc.render.resolution_y = WIDTH, int(WIDTH * 1.0)
        camera((0.22, -0.36, 0.38), (0, 0, 0.115), 85, 5.6)
        card((-0.6, -0.6, 0.4), 0.6, 0.6)
    elif SHOT == "cup_macro":
        sc.render.resolution_x, sc.render.resolution_y = WIDTH, int(WIDTH * 0.625)
        camera((-0.06, -0.17, 0.085), (0, -0.043, 0.074), 100, 6.3)
else:
    # the wall-set station in its limewash niche, lit like the shop's ceiling cans
    area("Can1", (0.0, -0.75, 1.75), (0, -0.2, 0.45), 0.35, 55, "#ffe9cc", shape="DISK")
    area("Can2", (0.95, -0.75, 1.75), (0.86, -0.3, 1.0), 0.35, 38, "#ffe9cc", shape="DISK")
    area("Fill", (-1.2, -2.2, 0.9), (0, -0.2, 0.5), 2.4, 38, "#f6efe4")
    area("NicheGlow", (0.0, -0.24, 0.99), (0, -0.24, 0.0), 0.5, 4, "#fff2df", size_y=0.12)
    card((-1.4, -1.8, 0.9), 1.6, 0.6)
    card((1.2, -1.6, 1.0), 1.4, 0.4)
    if SHOT == "machine_pull":
        handle.rotation_euler = (math.radians(55), 0, 0)
    if SHOT == "station_wide":
        sc.render.resolution_x, sc.render.resolution_y = WIDTH, int(WIDTH * 0.625)
        camera((0.55, -2.75, 0.80), (0.32, -0.3, 0.62), 35, 8.0)
    else:
        sc.render.resolution_x, sc.render.resolution_y = WIDTH, int(WIDTH * 1.25)
        camera((0.36, -1.55, 0.70), (0.02, -0.2, 0.49), 45, 5.6)

sc.render.filepath = os.path.join(OUT, f"render_{SHOT}.png")
bpy.ops.render.render(write_still=True)
print("wrote", sc.render.filepath)

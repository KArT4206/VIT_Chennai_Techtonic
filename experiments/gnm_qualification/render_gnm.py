"""Verification renders of gnm_head_test.blend (Cycles, Metal GPU when available, 1024x1024).

    blender -b gnm_head_test.blend --python render_gnm.py -- renders/

Outputs (geometry/UV verification only, not photorealism):
    clay_front.png, clay_three_quarter.png       neutral clay head
    uv_checker_front.png                         UDIM checker on the full head (1001, 1003, 1005 visible)
    uv_checker_no_skin.png                       skin hidden: corneas 1003/1005, teeth 1006, tongue 1007
    uv_checker_eye_interiors.png                 skin + corneas hidden: sclera/iris/pupil 1002/1004
    clay_eyes_rotated.png                        eye bones rotated through the armature (rig test)
"""

import math
import os
import sys

import bpy
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
device = "CPU"
try:
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    gpus = [d for d in prefs.devices if d.type == "METAL"]
    for d in prefs.devices:
        d.use = d.type == "METAL"
    if gpus:
        scene.cycles.device = "GPU"
        device = "METAL"
except TypeError:
    pass
print("RENDER_DEVICE", device)
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"

ob = bpy.data.objects["GNM_Head"]
rig = bpy.data.objects["GNM_Rig"]
mw = ob.matrix_world
eyeL = mw @ rig.data.bones["left_eye"].head_local
eyeR = mw @ rig.data.bones["right_eye"].head_local
mid = (eyeL + eyeR) / 2
print("EYE_MIDPOINT_BLENDER", tuple(round(c, 4) for c in mid))

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.18, 0.2, 0.22, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def light(name, loc, power, size=0.25):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size = power, size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = (mid - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lo)


# Energies measured: 60/22/25 W saturated the clay to white at ~0.6 m; these keep it in range.
light("Key", mid + Vector((0.35, -0.45, 0.25)), 9)
light("Fill", mid + Vector((-0.4, -0.4, 0.05)), 3.5)
light("Rim", mid + Vector((0.0, 0.45, 0.3)), 4)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(pos, target, lens):
    cam.location = pos
    cam.rotation_euler = (target - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens


clay = bpy.data.materials.new("Clay")
clay.use_nodes = True
b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
b.inputs["Base Color"].default_value = (0.62, 0.6, 0.58, 1)
b.inputs["Roughness"].default_value = 0.55
vl = bpy.context.view_layer

head_centre = mid + Vector((0, 0.06, -0.06))


def render(name):
    scene.render.filepath = os.path.join(out, name)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)


def mask(group, invert):
    for m in [m for m in ob.modifiers if m.type == "MASK"]:
        ob.modifiers.remove(m)
    for g in group:
        m = ob.modifiers.new(f"hide_{g}", "MASK")
        m.vertex_group = f"gnm_{g}"
        m.invert_vertex_group = invert


# --- clay
vl.material_override = clay
aim(mid + Vector((0, -0.62, 0.0)), head_centre, 50)
render("clay_front.png")
aim(mid + Vector((0.38, -0.48, 0.06)), head_centre, 50)
render("clay_three_quarter.png")
# eye rig test: close-up, eyes rotated 20 deg to the subject's left and 10 deg up via the armature
pb = {s: rig.pose.bones[f"{s}_eye"] for s in ("left", "right")}
for p in pb.values():
    p.rotation_mode = "XYZ"
    p.rotation_euler = (math.radians(-10), math.radians(20), 0.0)
bpy.context.view_layer.update()
aim(mid + Vector((0, -0.40, 0.0)), mid, 85)
render("clay_eyes_rotated.png")
for p in pb.values():
    p.rotation_euler = (0, 0, 0)

# --- UDIM checker
vl.material_override = None
aim(mid + Vector((0.25, -0.55, 0.05)), head_centre, 50)
render("uv_checker_front.png")
mask(["skin"], True)                                   # hide skin -> corneas, teeth, tongue visible
aim(mid + Vector((0.12, -0.30, -0.02)), mid + Vector((0, 0.02, -0.04)), 45)
render("uv_checker_no_skin.png")
mask(["skin", "eye_exteriors"], True)                  # also hide corneas -> sclera/iris/pupil
aim(mid + Vector((0.0, -0.30, 0.0)), mid, 60)
render("uv_checker_eye_interiors.png")
mask(["skin", "upper_teeth_and_gums", "lower_teeth_and_gums"], True)   # tongue 1007 + eyes
aim(mid + Vector((0.10, -0.30, -0.04)), mid + Vector((0, 0.03, -0.07)), 45)
render("uv_checker_tongue.png")

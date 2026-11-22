"""PRIVATE QA renders of a web GLB: eye close-ups at given shape-key weights. Output stays in qa_private."""
import sys, math, os, json
import bpy
from mathutils import Vector
glb, out, spec = sys.argv[sys.argv.index("--") + 1:][:3]
shots = json.loads(spec)  # [{"name":..., "w":{key:val}, "view":"front"|"34"|"close"|"face34"|"face"}]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.25
for m in bpy.data.materials:
    if m.name.startswith("Cornea") and m.use_nodes:
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); p.inputs["Alpha"].default_value = 0.0
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys]
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
le = rig.matrix_world @ rig.data.bones["left_eye"].head_local; re_ = rig.matrix_world @ rig.data.bones["right_eye"].head_local
mid = (le + re_) / 2
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); L.data.energy = e; L.data.size = 0.5
    L.location = mid + Vector(loc); sc.collection.objects.link(L); L.rotation_euler = (mid - L.location).to_track_quat("-Z", "Y").to_euler()
VIEWS = {  # (camera offset from target, target offset, lens, resx, resy)
    "front": (Vector((0, -0.36, 0)), Vector((0, 0, 0)), 85, 1400, 600),
    "34": (Vector((0.22, -0.28, 0.0)), Vector((0, 0, 0)), 85, 1400, 600),
    "close": (Vector((0.0, -0.12, 0.0)), Vector((0.03, 0, 0)), 85, 1200, 700),
    "close34": (Vector((0.07, -0.10, 0.0)), Vector((0.03, 0, 0)), 85, 1200, 700),
    "face": (Vector((0, -0.75, 0)), Vector((0, 0, -0.03)), 85, 900, 1000),
    "eyeL_front": (Vector((0.0, -0.13, 0.0)), Vector((0.03, 0, 0.001)), 85, 900, 560),
    "eyeL_34": (Vector((0.08, -0.105, 0.0)), Vector((0.03, 0, 0.001)), 85, 900, 560),
    "eyeL_high": (Vector((0.0, -0.12, 0.05)), Vector((0.03, 0, 0.001)), 85, 900, 560),
    "eyeR_front": (Vector((0.0, -0.13, 0.0)), Vector((-0.03, 0, 0.001)), 85, 900, 560),
    "eyeR_34": (Vector((-0.08, -0.105, 0.0)), Vector((-0.03, 0, 0.001)), 85, 900, 560),
    "eyeR_high": (Vector((0.0, -0.12, 0.05)), Vector((-0.03, 0, 0.001)), 85, 900, 560),
    "mouth_front": (Vector((0.0, -0.20, 0.0)), Vector((0.0, 0, -0.068)), 85, 1000, 640),
    "mouth_34": (Vector((0.13, -0.16, 0.0)), Vector((0.0, 0, -0.068)), 85, 1000, 640),
    "mouth_close": (Vector((0.0, -0.16, 0.0)), Vector((0.0, 0, -0.068)), 85, 1000, 640),
    "cornerL_front": (Vector((0.0, -0.11, 0.0)), Vector((0.022, 0, -0.066)), 85, 1000, 700),
    "cornerL_34": (Vector((0.075, -0.085, 0.0)), Vector((0.022, 0, -0.066)), 85, 1000, 700),
    "cornerL_side": (Vector((0.11, -0.035, 0.0)), Vector((0.022, 0, -0.066)), 85, 1000, 700),
    "cornerL_front_c": (Vector((0.0, -0.11, 0.0)), Vector((0.022, -0.022, -0.065)), 85, 1000, 700),
    "cornerL_34_c": (Vector((0.075, -0.085, 0.0)), Vector((0.022, -0.022, -0.065)), 85, 1000, 700),
    "cornerL_side_c": (Vector((0.11, -0.035, 0.0)), Vector((0.022, -0.022, -0.065)), 85, 1000, 700),
    "cornerR_front": (Vector((0.0, -0.11, 0.0)), Vector((-0.022, 0, -0.066)), 85, 1000, 700),
    "cornerR_34": (Vector((-0.075, -0.085, 0.0)), Vector((-0.022, 0, -0.066)), 85, 1000, 700),
    "cornerR_side": (Vector((-0.11, -0.035, 0.0)), Vector((-0.022, 0, -0.066)), 85, 1000, 700),
    "mouth_macro": (Vector((0.0, -0.13, 0.0)), Vector((0.0, 0, -0.068)), 85, 1000, 640),
    "lower_face": (Vector((0.0, -0.40, 0.0)), Vector((0.0, 0, -0.055)), 85, 900, 900),
    "eyeL_front_wide": (Vector((0.0, -0.15, 0.0)), Vector((0.03, 0, 0.001)), 70, 900, 560),
    "eyeR_front_wide": (Vector((0.0, -0.15, 0.0)), Vector((-0.03, 0, 0.001)), 70, 900, 560),
    "eyes_both": (Vector((0.0, -0.2, 0.0)), Vector((0.0, 0, 0.0)), 85, 1300, 520),
    "face34": (Vector((0.45, -0.6, 0)), Vector((0, 0, -0.03)), 85, 900, 1000),
}
for s in shots:
    for o in meshes:
        for k in o.data.shape_keys.key_blocks[1:]:
            k.value = s["w"].get(k.name, 0.0)
    off, toff, lens, rx, ry = VIEWS[s["view"]]
    tgt = mid + toff; cam.location = tgt + off; cam.data.lens = lens; cam.data.clip_start = 0.002
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = os.path.join(out, s["name"] + ".png"); bpy.ops.render.render(write_still=True)
print("RENDERED", len(shots))

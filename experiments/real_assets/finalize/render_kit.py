"""Render marked screenshots from the kit cameras (rest pose, and jaw 50 % to show the defect unfold). Read-only."""
import sys, os, math, bpy
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]; os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name == "GNM_Head")
tgt = bpy.data.objects["CAM_front"].location
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); L.data.energy = e; L.data.size = 0.5
    L.location = tgt + Vector(loc) * 0.6; sc.collection.objects.link(L); L.rotation_euler = (tgt - L.location).to_track_quat("-Z", "Y").to_euler()
for m in bpy.data.materials:
    if m.name.startswith("Cornea") and m.use_nodes:
        next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Alpha"].default_value = 0.0
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
def vis(names, on):
    for c in bpy.data.collections:
        if c.name in names: c.hide_render = not on
shots = [("A_overview_front", "CAM_front", "all", 0.0), ("B_threequarter_L", "CAM_threequarter_L", "all", 0.0), ("C_threequarter_R", "CAM_threequarter_R", "all", 0.0),
         ("D_side_L", "CAM_side_L", "all", 0.0), ("E_corner_L_macro_defect_patch", "CAM_corner_L_macro", "defect", 0.0), ("F_corner_R_macro_defect_patch", "CAM_corner_R_macro", "defect", 0.0),
         ("G_corner_L_macro_jaw50_unmarked", "CAM_corner_L_macro", "none", 0.5), ("H_corner_R_macro_jaw50_unmarked", "CAM_corner_R_macro", "none", 0.5),
         ("I_front_jaw50_unmarked", "CAM_front", "none", 0.5), ("J_corner_L_macro_rest_unmarked", "CAM_corner_L_macro", "none", 0.0)]
ALL = [c.name for c in bpy.data.collections if c.name[:2] in ("02", "03", "04", "05", "06", "07", "08")]
for name, cam, mode, jaw in shots:
    vis(ALL, False)
    if mode == "all": vis(ALL, True)
    if mode == "defect": vis([n for n in ALL if n[:2] in ("02", "03", "07", "08")], True)
    for c in bpy.data.collections:
        if c.name.startswith("08"):
            for o in c.objects:
                if o.type == "FONT": o.hide_render = mode == "none" or "macro" in cam
    head.data.shape_keys.key_blocks["jaw_open"].value = jaw
    for o in bpy.data.objects:   # interior + strand meshes follow the same jaw value
        if o.type == "MESH" and o.data.shape_keys and "jaw_open" in o.data.shape_keys.key_blocks: o.data.shape_keys.key_blocks["jaw_open"].value = jaw
    sc.camera = bpy.data.objects[cam]; sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)
print("KIT_RENDERS", len(shots))

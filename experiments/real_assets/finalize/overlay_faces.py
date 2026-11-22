"""PRIVATE QA: coloured face-set overlay on the (deformed) head, rendered from the left-corner cameras.

    blender -b <file.blend> --python overlay_faces.py -- <sets.json> <object> <out_dir> <prefix> <jaws e.g. 0,0.5,1> [views front,34,side]

sets.json: {"label": {"rgb": [r,g,b], "faces": [...]} , ...}   (face indices of <object>; later sets draw on top)
Optional "points": {"label": {"rgb": [...], "verts": [...]}} draws small spheres on vertices.
"""
import json, os, sys
import bpy, bmesh
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
S = json.load(open(a[0])); obn, out, prefix = a[1], a[2], a[3]; jaws = [float(x) for x in a[4].split(",")]
views = a[5].split(",") if len(a) > 5 else ["front", "34", "side"]
os.makedirs(out, exist_ok=True)
ob = bpy.data.objects[obn]
for o in bpy.data.objects:
    if o.type in ("MESH", "FONT", "CURVE") and o.name not in (obn, "OralCavity", "Brows_web", "Lashes_web") and o.name not in __import__("os").environ.get("KEEP_OBJS", "").split(","): o.hide_render = True
for c in bpy.data.collections:
    if c.name.startswith("08"): c.hide_render = True
def emis(n, rgb):
    m = bpy.data.materials.new(n); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = 1.4
    nt.links.new(e.outputs[0], o.inputs[0]); return m
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
import os as _os
tgt = mid + Vector((0.022, float(_os.environ.get("TGT_Y", "0")), -0.066))
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); L.data.energy = e; L.data.size = 0.5; L.location = mid + Vector(loc)
    sc.collection.objects.link(L); L.rotation_euler = (mid - L.location).to_track_quat("-Z", "Y").to_euler()
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 85; cam.data.clip_start = 0.002
sc.render.resolution_x, sc.render.resolution_y = 1000, 700
OFF = {"front": Vector((0.0, -0.11, 0.0)), "34": Vector((0.075, -0.085, 0.0)), "side": Vector((0.11, -0.035, 0.0)), "inside": Vector((0.0, -0.06, -0.012))}
for jaw in jaws:
    for o in [x for x in bpy.data.objects if x.name.startswith("HL_")]: bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data.shape_keys and "jaw_open" in o.data.shape_keys.key_blocks: o.data.shape_keys.key_blocks["jaw_open"].value = jaw
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    em = ob.evaluated_get(dg).to_mesh(); P = [v.co.copy() for v in em.vertices]; F = [list(p.vertices) for p in em.polygons]
    for i, (lab, d) in enumerate(S.get("sets", S).items()):
        if lab == "points": continue
        if "vgroup" in d:
            gi = ob.vertex_groups[d["vgroup"]].index
            ing = {v.index for v in ob.data.vertices if any(g.group == gi for g in v.groups)}
            d["faces"] = [p.index for p in ob.data.polygons if (all if d.get("all", True) else any)(v in ing for v in p.vertices)]
        bm = bmesh.new(); vm = {}
        for f in d["faces"]:
            if f >= len(F): continue
            for v in F[f]:
                if v not in vm: vm[v] = bm.verts.new(P[v])
            try: bm.faces.new([vm[v] for v in F[f]])
            except ValueError: pass
        bm.normal_update(); mat = emis(lab, d["rgb"])
        for sgn in (1, -1):                      # both sides, so faces seen from the back are marked too
            b2 = bm.copy(); b2.normal_update()
            for v in b2.verts: v.co += v.normal * sgn * (0.00008 + 0.00003 * i)
            m2 = bpy.data.meshes.new("HL_" + lab); b2.to_mesh(m2); b2.free(); o2 = bpy.data.objects.new("HL_" + lab, m2); o2.matrix_world = ob.matrix_world.copy()
            sc.collection.objects.link(o2); m2.materials.append(mat)
        bm.free()
    for lab, d in S.get("points", {}).items():
        mm = emis("p_" + lab, d["rgb"])
        for v in d["verts"]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.00022, segments=8, ring_count=6, location=ob.matrix_world @ P[v])
            s = bpy.context.active_object; s.name = "HL_pt"; s.data.materials.append(mm)
    ob.evaluated_get(dg).to_mesh_clear()
    for vn in views:
        cam.location = tgt + OFF[vn]; cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(out, f"{prefix}_jaw{int(jaw * 100):03d}_{vn}.png"); bpy.ops.render.render(write_still=True)
print("OVERLAY_DONE")

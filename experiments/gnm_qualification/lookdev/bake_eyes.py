"""Bake two distinct irises and a subtler sclera onto GNM's eye-interior tiles (1002, 1004) at 2048^2.

    blender -b --factory-startup ../gnm_head_test.blend --python bake_eyes.py -- ../build/fit.npz ../../../scene.blend textures/

Source: the production procedural eye (tools/eye_model.py, this project, MIT): radial fibres, crypts,
collarette, pupillary ruff, limbal ring. iris_material() takes a seed that changes fibre and crypt
structure while the colour zones stay the same, so the two eyes belong to one identity but are not
copies (left seed 11, right seed 23; the production scene uses one material for both).
Sclera: vein factor reduced from 0.8 to 0.3 ("very subtle vascular detail"); the ambient-occlusion
lid shadow is removed (it belongs to lighting, not to the eyeball's colour).
Method as in Phase 2B: MakeHuman eye parts placed on each GNM eyeball (centre, gaze axis, radius),
DIFFUSE colour selected-to-active bake, plus a tangent-space NORMAL bake of the iris relief.
scene.blend is only read.
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index("--") + 1:]
fit = np.load(a[0]); prod = a[1]; out = os.path.abspath(a[2])
os.makedirs(out, exist_ok=True)
ROOT = os.path.abspath(os.path.join(os.path.dirname(prod)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import eye_model  # noqa: E402

sc = bpy.context.scene
sc.render.engine = "CYCLES"
p = bpy.context.preferences.addons["cycles"].preferences
try:
    p.compute_device_type = "METAL"; p.get_devices()
    for d in p.devices:
        d.use = d.type == "METAL"
    sc.cycles.device = "GPU"
except TypeError:
    pass
sc.cycles.samples = 16
RX = Matrix.Rotation(math.radians(90), 4, "X")
gnm = bpy.data.objects["GNM_Head"]
Vfit = fit["vertices"].astype(np.float32)

with bpy.data.libraries.load(prod, link=False) as (src, dst):
    dst.objects = ["Human.rig"] + [f"Eye{s}.{p}" for s in "LR" for p in ("Sclera", "Iris", "PupilDark")]
for o in dst.objects:
    sc.collection.objects.link(o)
mh_rig = bpy.data.objects["Human.rig"]
for pb in mh_rig.pose.bones:
    pb.location = (0, 0, 0); pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()

# two seeded irises, one identity (same colour zones)
for letter, seed in (("L", 11.0), ("R", 23.0)):
    iris = bpy.data.objects[f"Eye{letter}.Iris"]
    d = dict(iris["eye_dims"])
    m = eye_model.iris_material(d, seed=seed)
    m.name = f"Iris_seed{int(seed)}"
    iris.data.materials.clear(); iris.data.materials.append(m)
    print("IRIS", letter, "seed", seed)
# subtler sclera, no AO
for mat in {s.material for o in bpy.data.objects if o.name.endswith("Sclera") for s in o.material_slots}:
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "MATH" and n.operation == "MULTIPLY" and abs(n.inputs[1].default_value - 0.8) < 1e-6:
            n.inputs[1].default_value = 0.3
            print("VEINS 0.8 -> 0.3 in", mat.name)
    for ao in [n for n in nt.nodes if n.type == "AMBIENT_OCCLUSION"]:
        for link in list(ao.outputs["AO"].links):
            s = link.to_socket; nt.links.remove(link); s.default_value = 1.0
        print("AO removed in", mat.name)


def bake_copy(name, keep_index, u_shift):
    me = gnm.data.copy(); me.name = name
    if me.shape_keys:
        pass
    me.vertices.foreach_set("co", Vfit.reshape(-1))
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != keep_index], context="FACES")
    uv = bm.loops.layers.uv["UDIM"]
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = (l[uv].uv.x - u_shift, l[uv].uv.y)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.uv_layers.active = me.uv_layers["UDIM"]
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); ob.matrix_world = RX.copy()
    me.materials.clear()
    return ob


def target(ob, img):
    m = bpy.data.materials.new(ob.name + "_t"); m.use_nodes = True
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img; m.node_tree.nodes.active = t
    ob.data.materials.clear(); ob.data.materials.append(m)


def bake(tgt, srcs, img, kind, path):
    bpy.ops.object.select_all(action="DESELECT")
    for s in srcs:
        s.select_set(True)
    tgt.select_set(True); bpy.context.view_layer.objects.active = tgt
    kw = dict(type=kind, use_selected_to_active=True, cage_extrusion=0.003, max_ray_distance=0.006, margin=16)
    if kind == "DIFFUSE":
        kw["pass_filter"] = {"COLOR"}
    else:
        kw["normal_space"] = "TANGENT"
    bpy.ops.object.bake(**kw)
    img.filepath_raw = path; img.file_format = "PNG"; img.save()
    print("BAKED", path)


names = ["neck", "head", "left_eye", "right_eye"]
for side, L, idx, shift, tile in (("left", "L", 1, 1.0, 1002), ("right", "R", 3, 3.0, 1004)):
    parts = [bpy.data.objects[f"Eye{L}.{p}"] for p in ("Sclera", "Iris", "PupilDark")]
    iris = parts[1]
    mh_c = mh_rig.matrix_world @ mh_rig.data.bones[f"eye.{L}"].head_local
    mh_p = iris.matrix_world @ Vector(iris["pupil_local"])
    r_mh = max((parts[0].matrix_world @ v.co - mh_c).length for v in parts[0].data.vertices)
    gc = RX @ Vector(fit["joints"][names.index(f"{side}_eye")].tolist())
    gz = (RX.to_3x3() @ Vector((0.0012, -0.0055, 1.0))).normalized()
    q = (mh_p - mh_c).normalized().rotation_difference(gz)
    A = Matrix.Translation(gc) @ q.to_matrix().to_4x4() @ Matrix.Scale(0.0145 / r_mh, 4) @ Matrix.Translation(-mh_c)
    for o in parts:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = A @ mw
    bpy.context.view_layer.update()
    t = bake_copy(f"eye_{side}", idx, shift)
    col = bpy.data.images.new(f"col_{tile}", 2048, 2048); col.colorspace_settings.name = "sRGB"
    target(t, col); bake(t, parts, col, "DIFFUSE", os.path.join(out, f"eye_albedo.{tile}.png"))
    nrm = bpy.data.images.new(f"nrm_{tile}", 2048, 2048); nrm.colorspace_settings.name = "Non-Color"
    nrm.generated_color = (0.5, 0.5, 1.0, 1.0)
    target(t, nrm); bake(t, parts, nrm, "NORMAL", os.path.join(out, f"eye_normal.{tile}.png"))
    for o in parts:
        o.hide_render = True

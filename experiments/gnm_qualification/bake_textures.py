"""Geometry-aware bake of verified-licence textures onto GNM's own UDIM layout.

    blender -b --factory-startup gnm_head_test.blend --python bake_textures.py -- build/fit.npz build/cc0/young_lightskinned_male_diffuse.png ../../scene.blend textures/

Sources (read only; scene.blend is never saved):
- skin: MakeHuman young_lightskinned_male_diffuse.png, CC0 1.0 (asset header + upstream
  makehumancommunity/makehuman LICENSE.ASSETS.md), on the production MakeHuman head mesh (its UVMap);
- eyes: the production procedural sclera/iris/pupil shaders (tools/eye_model.py, this project, MIT).
Targets: a copy of GNM with the FITTED identity (fit_identity.py), so the two surfaces coincide
(face median 0.64 mm). Faces and UVs are GNM's; each tile is baked from a copy holding only that
tile's faces with u shifted into 0-1, so tiles cannot overwrite each other.

Bake: Cycles, DIFFUSE colour only (no lighting), selected-to-active rays, 16 px margin. Output:
gnm_skin_cc0.1001.png (2048) and gnm_eye_interior.1002.png / .1004.png (1024), sRGB.
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index("--") + 1:]
fit = np.load(a[0])
skin_png, prod_blend, out_dir = a[1], a[2], a[3]
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
p = bpy.context.preferences.addons["cycles"].preferences
try:
    p.compute_device_type = "METAL"; p.get_devices()
    for d in p.devices:
        d.use = d.type == "METAL"
    scene.cycles.device = "GPU"
except TypeError:
    pass
scene.cycles.samples = 16
RX = Matrix.Rotation(math.radians(90), 4, "X")            # GNM (Y up) -> Blender (Z up)
C = RX.inverted()                                          # Blender world -> GNM frame (x, z, -y)
G = Matrix(fit["mh_R"].tolist()).to_4x4()
G.translation = Vector(fit["mh_t"].tolist())               # MakeHuman (GNM frame) -> fitted GNM frame
MH_TO_GNM_WORLD = RX @ G @ C                               # MakeHuman Blender world -> GNM object world

gnm = bpy.data.objects["GNM_Head"]
Vfit = fit["vertices"].astype(np.float32)


def bake_copy(name, keep_material_index, u_shift):
    me = gnm.data.copy()
    me.name = name
    me.vertices.foreach_set("co", Vfit.reshape(-1))
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != keep_material_index], context="FACES")
    uv = bm.loops.layers.uv["UDIM"]
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = (l[uv].uv.x - u_shift, l[uv].uv.y)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))   # smooth normals for the bake rays
    me.uv_layers.active = me.uv_layers["UDIM"]
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.matrix_world = RX.copy()
    me.materials.clear()
    return ob


def target_material(ob, img):
    mat = bpy.data.materials.new(f"{ob.name}_bake")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    ob.data.materials.append(mat)


def new_image(name, size, rgb):
    img = bpy.data.images.new(name, size, size, alpha=False)
    img.colorspace_settings.name = "sRGB"
    img.generated_color = (*rgb, 1.0)
    return img


def fill_unbaked(img):
    """Texels no ray reached stay pure black: fill each from its nearest baked neighbours in UV space
    (iterative 3x3 dilation), so occluded areas (behind the ears, under the jaw) carry nearby skin."""
    w, h = img.size
    px = np.asarray(img.pixels[:], np.float32).reshape(h, w, 4)
    valid = px[..., :3].max(-1) > 1e-4
    print("UNBAKED_FRACTION", round(1 - float(valid.mean()), 4))
    rgb = px[..., :3].copy()
    for _ in range(64):
        if valid.all():
            break
        acc = np.zeros_like(rgb); cnt = np.zeros(valid.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                v = np.roll(np.roll(valid, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * v[..., None]; cnt += v
        grow = (~valid) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        valid = valid | grow
    px[..., :3] = rgb
    img.pixels[:] = px.reshape(-1)


def bake(target, sources, img, extrusion, distance, path):
    bpy.ops.object.select_all(action="DESELECT")
    for s in sources:
        s.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True,
                        cage_extrusion=extrusion, max_ray_distance=distance, margin=16, target="IMAGE_TEXTURES")
    fill_unbaked(img)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", path)


# --- append production MakeHuman head and eyes (read only)
with bpy.data.libraries.load(prod_blend, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in ("Human", "Human.rig") or
                   any(n == f"Eye{s}.{p}" for s in "LR" for p in ("Sclera", "Iris", "PupilDark"))]
for o in dst.objects:
    scene.collection.objects.link(o)
mh_rig = bpy.data.objects["Human.rig"]
for pb in mh_rig.pose.bones:                      # rest pose, as used for the fit
    pb.location = (0, 0, 0); pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()
human = bpy.data.objects["Human"]

# skin source material: CC0 diffuse on the MakeHuman UVMap
skin_src = bpy.data.images.load(os.path.abspath(skin_png))
skin_src.colorspace_settings.name = "sRGB"
m = bpy.data.materials.new("MH_CC0_skin_source")
m.use_nodes = True
bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
tx = m.node_tree.nodes.new("ShaderNodeTexImage"); tx.image = skin_src
uvn = m.node_tree.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
m.node_tree.links.new(uvn.outputs["UV"], tx.inputs["Vector"])
m.node_tree.links.new(tx.outputs["Color"], bsdf.inputs["Base Color"])
human.data.materials.clear(); human.data.materials.append(m)

# move MakeHuman (and its rig, which carries the eyes) into the fitted GNM frame
mh_rig.matrix_world = MH_TO_GNM_WORLD @ mh_rig.matrix_world
bpy.context.view_layer.update()

# --- skin (tile 1001)
skin_t = bake_copy("bake_skin", 0, 0.0)
mean = np.asarray(skin_src.pixels[:]).reshape(-1, 4)[::97, :3].mean(0)
img = new_image("gnm_skin_cc0", 2048, tuple(mean))
target_material(skin_t, img)
bake(skin_t, [human], img, 0.012, 0.03, os.path.abspath(os.path.join(out_dir, "gnm_skin_cc0.1001.png")))

# --- eyes: MakeHuman eye parts moved onto each GNM eyeball (centre, gaze axis, radius)
# The production sclera shader multiplies its colour by an ambient-occlusion "lid shadow"
# (tools/eye_model.py). That is a lighting effect of the MakeHuman lids, not eye colour: baked into
# the eyeball it would rotate with the eye and darken the wrong places (first bake showed dark bands).
# Neutralise it in this appended copy only (the production file is never saved).
for mat in {s.material for o in bpy.data.objects if o.name.startswith("Eye") for s in o.material_slots if s.material}:
    nt = mat.node_tree
    for ao in [n for n in nt.nodes if n.type == "AMBIENT_OCCLUSION"]:
        for link in list(ao.outputs["AO"].links):
            sock = link.to_socket
            nt.links.remove(link)
            sock.default_value = 1.0
        print("NEUTRALISED_AO", mat.name)
gnm_rig = bpy.data.objects["GNM_Rig"]
Jfit = fit["joints"]
names = ["neck", "head", "left_eye", "right_eye"]
for side, letter, mat_index, shift in (("left", "L", 1, 1.0), ("right", "R", 3, 3.0)):
    parts = [bpy.data.objects[f"Eye{letter}.{p}"] for p in ("Sclera", "Iris", "PupilDark")]
    iris = parts[1]
    mh_c = mh_rig.matrix_world @ mh_rig.data.bones[f"eye.{letter}"].head_local
    mh_pupil = iris.matrix_world @ Vector(iris["pupil_local"])
    sc = parts[0]
    r_mh = max((sc.matrix_world @ v.co - mh_c).length for v in sc.data.vertices)
    gc = RX @ Vector(Jfit[names.index(f"{side}_eye")].tolist())
    gaze_g = (RX.to_3x3() @ Vector((0.0012, -0.0055, 1.0))).normalized()      # GNM rest gaze (+Z), measured
    q = (mh_pupil - mh_c).normalized().rotation_difference(gaze_g)
    s = 0.0145 / r_mh
    A = Matrix.Translation(gc) @ q.to_matrix().to_4x4() @ Matrix.Scale(s, 4) @ Matrix.Translation(-mh_c)
    for o in parts:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = A @ mw
    print(f"EYE {side}: MakeHuman sclera r {r_mh*1000:.2f} mm -> 14.5 mm (scale {s:.3f})")
    bpy.context.view_layer.update()
    t = bake_copy(f"bake_eye_{side}", mat_index, shift)
    img = new_image(f"gnm_eye_{side}", 1024, (0.8, 0.78, 0.74))
    target_material(t, img)
    tile = 1002 if side == "left" else 1004
    bake(t, parts, img, 0.003, 0.006, os.path.abspath(os.path.join(out_dir, f"gnm_eye_interior.{tile}.png")))

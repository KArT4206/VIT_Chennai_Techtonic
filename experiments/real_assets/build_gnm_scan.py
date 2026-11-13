"""GNM Head v3 carrying the 3D Scan Store head's real shape and appearance, built inside a copy of the
vendor scene (same cameras, HDRI and light as the original-scan renders).

    blender -b --factory-startup --disable-autoexec build/scan_original.blend --python build_gnm_scan.py -- \
        <gnm_expression_test.blend> <gnm_keys.npz> <scan_gnm_fit.npz> <extracted dir> <out.blend> <keys_out.npz>

GNM_Head keeps GNM's 17,821 vertices, face order, UDIM UVs, 7 regions, rig and shape keys. Changes:
  * Basis shape: tile-1001 skin vertices = the scan's own positions (same topology, verified);
    teeth/tongue = GNM identity fitted to the scan; each eye (interior + cornea shell) = GNM's eye,
    translated to the scan eyeball's sphere centre and scaled to its radius (15.3 mm vs 14.5 mm).
  * Every GNM control shape key keeps its GNM offset (key = new basis + original offset).
  * Eye bones moved to the scan eye centres (rig in GNM frame, metres).
  * Tile 1001 material = the vendor's original skin material (original 8K maps); the UVs are identical.
  * Eye interiors: the scan's photographic eyeball colour baked onto GNM's 1002/1004 UVs from the scan
    eyeball placed concentric, its corneal axis turned onto GNM's +Z gaze axis.
  * Vendor Brows / Lashes / Eye Wet meshes (original materials) bound to GNM_Head by Surface Deform.
Vendor head, eyeballs, lenses, teeth and tongue are hidden (kept in the file for comparison renders).
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index("--") + 1:]
gnm_blend, keys_npz, fit_npz, X, out_blend, keys_out = a
fit = np.load(fit_npz); K = np.load(keys_npz)
sc = bpy.context.scene
p = bpy.context.preferences.addons["cycles"].preferences
p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"

with bpy.data.libraries.load(os.path.abspath(gnm_blend), link=False) as (src, dst):
    dst.objects = ["GNM_Head", "GNM_Rig"]
gh, rig = dst.objects
for o in (gh, rig):
    sc.collection.objects.link(o)
for idb in (rig, gh.data.shape_keys):
    if idb.animation_data:
        idb.animation_data.action = None
bpy.context.view_layer.update()
vendor_head = bpy.data.objects["Head"]
# GNM frame (metres, Y up) -> vendor world (cm, Z up): vendor objects carry x100 scale and the Y-up -> Z-up turn
V2W = vendor_head.matrix_world.copy()
rig.matrix_world = V2W.copy(); gh.matrix_world = V2W.copy()   # head is parented to the rig; set both
bpy.context.view_layer.update()
print("TRANSFORM vendor Head world matrix (applied to GNM):", [list(map(lambda x: round(x, 3), r)) for r in V2W])

me = gh.data; key = me.shape_keys
nv = len(me.vertices)
old_basis = np.empty(nv * 3, np.float32); key.key_blocks["Basis"].data.foreach_get("co", old_basis); old_basis = old_basis.reshape(-1, 3)
new_basis = fit["vertices_fit"].astype(np.float32).copy()            # GNM identity fitted to the scan
new_basis[fit["skin_vertex_ids"]] = fit["scan_skin"].astype(np.float32)   # tile 1001: the scan itself
gi = {g.name: g.index for g in gh.vertex_groups}
memb = [set(g.group for g in v.groups) for v in me.vertices]


def sphere(P):
    A = np.c_[2 * P, np.ones(len(P))]; c = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0]
    return c[:3], float(np.sqrt(c[3] + c[:3] @ c[:3]))


def obj_vertices(p):
    return np.array([[float(x) for x in l.split()[1:4]] for l in open(p, errors="ignore") if l.startswith("v ")])


eye_info = {}
for side, name in (("left", "Left"), ("right", "Right")):
    ball = obj_vertices(f"{X}/OBJ/Realtime Eyeball {name}.obj"); lens = obj_vertices(f"{X}/OBJ/Lens {name}.obj")
    c_s, r_s = sphere(ball)
    apex = lens[np.argmax(np.linalg.norm(lens - c_s, axis=1))]; axis_s = (apex - c_s) / np.linalg.norm(apex - c_s)
    ids = np.array([i for i in range(nv) if gi[f"gnm_{side}_eye"] in memb[i]])
    sc_ids = np.array([i for i in ids if gi["gnm_scleras"] in memb[i]])
    c_g, r_g = sphere(old_basis[sc_ids].astype(np.float64))
    s = r_s / r_g
    new_basis[ids] = ((old_basis[ids] - c_g) * s + c_s).astype(np.float32)
    eye_info[side] = dict(centre=c_s, radius=r_s, scale=s, axis=axis_s)
    print(f"EYE {side}: scan centre {np.round(c_s * 1000, 2)} mm r {r_s * 1000:.2f} | GNM eye scaled x{s:.4f} | scan corneal axis {np.round(axis_s, 3)}")

# rebuild every shape key on the new basis with its original GNM offset
for kb in key.key_blocks:
    co = np.empty(nv * 3, np.float32); kb.data.foreach_get("co", co); co = co.reshape(-1, 3)
    off = co - old_basis
    kb.data.foreach_set("co", (new_basis + off).reshape(-1))
me.vertices.foreach_set("co", new_basis.reshape(-1))
print("BASIS skin = scan positions; keys rebuilt:", len(key.key_blocks))

# move eye bones to the scan eye centres (armature space = GNM frame)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for side in ("left", "right"):
    b = rig.data.edit_bones[f"{side}_eye"]; L = (b.tail - b.head).length
    b.head = Vector(eye_info[side]["centre"].tolist()); b.tail = b.head + Vector((0, 0, L))
bpy.ops.object.mode_set(mode="OBJECT")
J = K["joints"].copy()
names = [str(n) for n in K["joint_names"]]
for side in ("left", "right"):
    J[names.index(f"{side}_eye")] = eye_info[side]["centre"]
np.savez(keys_out, **{k: K[k] for k in K.files if k != "joints"}, joints=J)

# subdivision like the vendor head (level 2), after the armature
if not any(m.type == "SUBSURF" for m in gh.modifiers):
    sm = gh.modifiers.new("Subdivision", "SUBSURF"); sm.levels = sm.render_levels = 2
me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))

# skin: the vendor's original material on tile 1001 (UVs are identical; UDIM layer is render-active)
skin = bpy.data.materials["Material.001"]
me.materials[0] = skin
for n in skin.node_tree.nodes:
    if n.type == "UVMAP":
        n.uv_map = "UDIM"
print("SKIN material:", skin.name, "images:", sorted(n.image.name for n in skin.node_tree.nodes if n.type == "TEX_IMAGE" and n.image))

# eye interiors: bake the scan eyeball colour onto GNM 1002/1004
RX = Matrix.Rotation(math.radians(90), 4, "X")


def bake_eye(side, name, mat_index, u_shift):
    ball = bpy.data.objects[f"Realtime Eyeball {name}"]
    tmp = ball.copy(); tmp.data = ball.data.copy(); sc.collection.objects.link(tmp)
    for m in [m for m in tmp.modifiers]:
        tmp.modifiers.remove(m)
    # The vendor eyeball material is fully subsurface (weight 1.0): Blender 5 then routes all of its
    # colour to the subsurface pass and a DIFFUSE-colour bake is black (first run). Bake from a copy
    # with subsurface 0 on this temporary object only; the vendor material is not modified.
    bm_mat = tmp.material_slots[0].material.copy(); bm_mat.name = f"eyebake_src_{side}"
    next(n for n in bm_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Subsurface Weight"].default_value = 0.0
    tmp.material_slots[0].link = "OBJECT"; tmp.material_slots[0].material = bm_mat
    # turn the scan eye about its centre so its corneal axis lies on GNM's +Z (in the GNM frame)
    info = eye_info[side]
    q = Vector(info["axis"].tolist()).rotation_difference(Vector((0.0012, -0.0055, 1.0)).normalized())
    c = Vector(info["centre"].tolist())
    A_gnm = Matrix.Translation(c) @ q.to_matrix().to_4x4() @ Matrix.Translation(-c)
    tmp.matrix_world = V2W @ A_gnm @ V2W.inverted() @ tmp.matrix_world
    # bake target: GNM eye interior faces of this eye, at their new (scan-aligned) positions, u shifted to 0-1
    bm_me = me.copy(); bm_me.shape_keys and None
    bm = bmesh.new(); bm.from_mesh(bm_me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mat_index], context="FACES")
    uvl = bm.loops.layers.uv["UDIM"]
    for f in bm.faces:
        for l in f.loops:
            l[uvl].uv = (l[uvl].uv.x - u_shift, l[uvl].uv.y)
    bm.to_mesh(bm_me); bm.free()
    bm_me.polygons.foreach_set("use_smooth", [True] * len(bm_me.polygons))
    tgt = bpy.data.objects.new(f"eyebake_{side}", bm_me); sc.collection.objects.link(tgt); tgt.matrix_world = V2W.copy()
    # Selected-to-active found no hits with the vendor x100 object scale and a shape-keyed target
    # (isolated test: 0 texels on GPU and CPU; 43,700 once scales were applied). Apply rotation/scale to
    # both temporary bake objects and drop the target's shape keys (its mesh holds the scan-shaped basis).
    bpy.context.view_layer.update()
    for o in (tmp, tgt):
        bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
        if o.data.shape_keys:
            o.shape_key_clear()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    img = bpy.data.images.new(f"scan_eye_{side}", 2048, 2048); img.colorspace_settings.name = "sRGB"
    m = bpy.data.materials.new(f"eyebake_{side}"); m.use_nodes = True
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img; m.node_tree.nodes.active = t
    bm_me.materials.clear(); bm_me.materials.append(m)
    bpy.ops.object.select_all(action="DESELECT"); tmp.select_set(True); tgt.select_set(True); bpy.context.view_layer.objects.active = tgt
    sc.cycles.samples = 16
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True, cage_extrusion=0.3, max_ray_distance=0.6, margin=16)
    path = os.path.join(os.path.dirname(os.path.abspath(out_blend)), f"scan_eye_albedo.{1002 if side == 'left' else 1004}.png")
    img.filepath_raw = path; img.file_format = "PNG"; img.save()
    bpy.data.objects.remove(tmp); bpy.data.objects.remove(tgt)
    print("BAKED", path)
    return path


eye_paths = {side: bake_eye(side, name, idx, sh) for side, name, idx, sh in (("left", "Left", 1, 1.0), ("right", "Right", 3, 3.0))}
eye_img = bpy.data.images.load(eye_paths["left"]); eye_img.source = "TILED"; eye_img.name = "scan_eye_albedo_udim"
eye_img.colorspace_settings.name = "sRGB"
for i in (1, 3):                                  # material slots for tiles 1002 / 1004
    mat = me.materials[i]; nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = eye_img
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UDIM"; nt.links.new(uv.outputs["UV"], tx.inputs["Vector"])
    iris = nt.nodes.new("ShaderNodeBsdfPrincipled"); scl = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for b in (iris, scl):
        nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    iris.inputs["Specular IOR Level"].default_value = 0.0; iris.inputs["Roughness"].default_value = 0.8
    scl.inputs["Roughness"].default_value = 0.35; scl.inputs["Subsurface Weight"].default_value = 0.3
    scl.inputs["Subsurface Scale"].default_value = 0.2           # scene units are cm here (x100)
    scl.inputs["Coat Weight"].default_value = 1.0; scl.inputs["Coat Roughness"].default_value = 0.04; scl.inputs["Coat IOR"].default_value = 1.336
    am = nt.nodes.new("ShaderNodeAttribute"); am.attribute_name = "iris_mask"
    mix = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(am.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(scl.outputs[0], mix.inputs[1]); nt.links.new(iris.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs["Surface"])
gmask = np.array([1.0 if {gi["gnm_irises"], gi["gnm_pupils"]} & memb[i] else 0.0 for i in range(nv)], np.float32)
at = me.attributes.get("iris_mask") or me.attributes.new("iris_mask", "FLOAT", "POINT"); at.data.foreach_set("value", gmask)
# corneas: smooth-IOR cap (Phase 2C), radius thresholds scaled with each eye
cw = np.zeros(nv, np.float32)
for side in ("left", "right"):
    c = eye_info[side]["centre"]; s = eye_info[side]["scale"]
    for i in range(nv):
        if gi["gnm_eye_exteriors"] in memb[i] and gi[f"gnm_{side}_eye"] in memb[i]:
            t = min(max((np.linalg.norm(new_basis[i] - c) - 0.01465 * s) / ((0.0156 - 0.01465) * s), 0), 1)
            cw[i] = t * t * (3 - 2 * t)
at = me.attributes.get("cornea_w") or me.attributes.new("cornea_w", "FLOAT", "POINT"); at.data.foreach_set("value", cw)
for i in (2, 4):
    nt = me.materials[i].node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    g = nt.nodes.new("ShaderNodeBsdfPrincipled"); g.inputs["Transmission Weight"].default_value = 1.0; g.inputs["Roughness"].default_value = 0.0
    aw = nt.nodes.new("ShaderNodeAttribute"); aw.attribute_name = "cornea_w"
    ior = nt.nodes.new("ShaderNodeMath"); ior.operation = "MULTIPLY_ADD"; ior.inputs[1].default_value = 0.376; ior.inputs[2].default_value = 1.0
    nt.links.new(aw.outputs["Fac"], ior.inputs[0]); nt.links.new(ior.outputs[0], g.inputs["IOR"]); nt.links.new(g.outputs[0], out.inputs["Surface"])

# vendor brows / lashes / eye wet follow GNM_Head (Surface Deform, bound at the scan-shaped rest pose)
bpy.context.view_layer.update()
for nm in ("Brows", "Lashes", "Eye Wet"):
    o = bpy.data.objects[nm]
    sd = o.modifiers.new("FollowGNM", "SURFACE_DEFORM"); sd.target = gh
    bpy.ops.object.modifier_move_to_index({"object": o} if False else None, modifier="FollowGNM", index=0) if False else None
    while o.modifiers[0] != sd:
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_move_up(modifier=sd.name)
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    print("BOUND", nm, "is_bound", sd.is_bound)
for nm in ("Head", "Realtime Eyeball Left", "Realtime Eyeball Right", "Lens Left", "Lens Right", "Teeth", "Tongue"):
    bpy.data.objects[nm].hide_render = True; bpy.data.objects[nm].hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), relative_remap=True)
print("SAVED", out_blend)

"""Build experiments/gnm_qualification/gnm_head_test.blend from the lossless GNM export.

    blender -b --factory-startup --python build_blend.py -- build/gnm_head_neutral.npz textures/ gnm_head_test.blend

Direct mesh construction (no OBJ/FBX round trip):
- vertex coordinates are GNM's exactly (metres, Y-up); the Y-up -> Z-up change lives in the object
  transform (+90 deg about X), so face looks -Y in Blender, as in the existing MakeHuman scene;
- polygon i == GNM quad i, loop corners in GNM order, so face order and corner UVs are preserved;
- UV layers: "UDIM" (quad_uvs_udim, the recommended layout) and "regions" (legacy 0-1 layout);
- 7 material slots, material_index = UDIM tile - 1001;
- every GNM vertex group as a Blender vertex group (weight 1), plus skinning weights per joint;
- armature with GNM's 4 joints and parents; eye bones at the eyeball centres, tails along +Z gaze.
Then it reads everything back and verifies it bit-for-bit against the source arrays.
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

TILE_NAMES = {1001: "skin", 1002: "left_eye_interior", 1003: "left_eye_cornea",
              1004: "right_eye_interior", 1005: "right_eye_cornea", 1006: "teeth_gums", 1007: "tongue"}


def build(npz_path, tex_dir):
    d = np.load(npz_path)
    V, Q = d["vertices"], d["quads"]
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    me = bpy.data.meshes.new("GNM_Head_v3")
    me.from_pydata(V.astype(float).tolist(), [], Q.tolist())
    me.update(calc_edges=True)
    for name, key in (("UDIM", "quad_uvs_udim"), ("regions", "quad_uvs")):
        uv = me.uv_layers.new(name=name)
        uv.data.foreach_set("uv", d[key].reshape(-1).astype(np.float32))
    me.uv_layers.active = me.uv_layers["UDIM"]
    me.uv_layers["UDIM"].active_render = True
    tiles = d["quad_udim_tiles"].astype(int)
    me.polygons.foreach_set("material_index", (tiles - 1001).astype(np.int32))
    ob = bpy.data.objects.new("GNM_Head", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")      # GNM Y-up -> Blender Z-up

    for n, m in zip(d["group_names"], d["group_masks"]):
        vg = ob.vertex_groups.new(name=f"gnm_{n}")
        vg.add(np.nonzero(m)[0].tolist(), 1.0, "REPLACE")

    # armature
    arm = bpy.data.armatures.new("GNM_Rig")
    rig = bpy.data.objects.new("GNM_Rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    rig.matrix_world = ob.matrix_world.copy()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    J, P, JN = d["joint_positions"], d["joint_parents"], [str(x) for x in d["joint_names"]]
    bones = []
    for i, n in enumerate(JN):
        b = arm.edit_bones.new(n)
        b.head = Vector(J[i].tolist())
        b.tail = b.head + Vector((0, 0, 0.02)) if "eye" in n else b.head + Vector((0, 0.05, 0))
        bones.append(b)
    for i, p in enumerate(P):
        if p >= 0:
            bones[i].parent = bones[p]
    bpy.ops.object.mode_set(mode="OBJECT")
    W = d["skinning_weights"]
    for i, n in enumerate(JN):
        vg = ob.vertex_groups.new(name=n)
        idx = np.nonzero(W[i] > 0)[0]
        for v, w in zip(idx.tolist(), W[i, idx].tolist()):
            vg.add([v], float(w), "REPLACE")
    ob.parent = rig
    ob.matrix_parent_inverse = rig.matrix_world.inverted()
    mod = ob.modifiers.new("GNM_Skinning", "ARMATURE")
    mod.object = rig
    mod.use_vertex_groups = True

    # UDIM checker image + one material per tile, all sampling the same tiled image
    img = None
    if tex_dir and os.path.exists(os.path.join(tex_dir, "checker.1001.png")):
        img = bpy.data.images.load(os.path.join(tex_dir, "checker.1001.png"))
        img.source = "TILED"
        img.name = "GNM_UDIM_checker"
        img.pack()
    for t in sorted(TILE_NAMES):
        mat = bpy.data.materials.new(f"GNM_{t}_{TILE_NAMES[t]}")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        if img is not None:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.uv_map = "UDIM"
            nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.6
        ob.data.materials.append(mat)

    ob["gnm_source"] = "https://huggingface.co/google/gnm-v3/resolve/main/v3_0/gnm_head.npz"
    ob["gnm_sha256"] = str(d["source_sha256"])
    ob["gnm_version"] = str(d["version"])
    ob["gnm_licence"] = "Apache-2.0 (code: github.com/google/GNM; weights: huggingface.co/google/gnm-v3)"
    ob["gnm_axis_note"] = "vertex coords are GNM Y-up metres; object rotation +90 deg X converts to Z-up"
    return ob, rig, d


def verify(ob, d):
    me = ob.data
    out = {}
    V = d["vertices"]; Q = d["quads"]
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
    out["vertex_count"] = (len(me.vertices), V.shape[0])
    out["positions_max_abs_err"] = float(np.abs(co.reshape(-1, 3) - V.astype(np.float32)).max())
    loops = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
    starts = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_start", starts)
    totals = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", totals)
    out["all_quads"] = bool((totals == 4).all())
    out["face_order_and_corners_identical"] = bool(np.array_equal(loops.reshape(-1, 4), Q) and np.array_equal(starts, np.arange(len(Q)) * 4))
    for name, key in (("UDIM", "quad_uvs_udim"), ("regions", "quad_uvs")):
        uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers[name].data.foreach_get("uv", uv)
        out[f"uv_{name}_max_abs_err"] = float(np.abs(uv.reshape(-1, 4, 2) - d[key].astype(np.float32)).max())
    mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
    out["material_index_equals_tile_minus_1001"] = bool(np.array_equal(mi + 1001, d["quad_udim_tiles"].astype(int)))
    names = {g.name for g in ob.vertex_groups}
    out["vertex_groups"] = (sum(1 for n in d["group_names"] if f"gnm_{n}" in names), len(d["group_names"]))
    # group membership round-trip for the eye groups
    for n in ("left_eye", "right_eye", "eye_interiors", "eye_exteriors", "irises", "pupils", "scleras"):
        gi = ob.vertex_groups[f"gnm_{n}"].index
        got = np.array([any(g.group == gi for g in v.groups) for v in me.vertices])
        want = d["group_masks"][list(d["group_names"]).index(n)].astype(bool)
        out[f"group_{n}_identical"] = bool(np.array_equal(got, want))
    return out


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    ob, rig, d = build(a[0], a[1])
    res = verify(ob, d)
    for k, v in res.items():
        print("VERIFY", k, v)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a[2]), compress=True)
    print("SAVED", a[2])

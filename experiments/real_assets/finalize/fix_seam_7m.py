"""PRIVATE: Phase 2N.7M - straighten the LEFT upper-lip seam notch (2N.7L -> 2N.7M). Authorised: rest of 4655 and 4697.

    blender -b <v6l_left_tuck_strip.blend> --python fix_seam_7m.py -- <out_dir> <qa_dir>

Seam (medial order): 4636, 4693, 4697, 4657, 4655, 4651, 4648. Each target vertex gets ONLY its deviant world component
replaced by the mean of its two seam neighbours: 4655 depth (y, it sits 2.8 mm deep), 4697 height (z, 0.8 mm high).
Every key is carried: new_key = new_basis + old_offset, so all 35 deformations stay identical. Nothing else moves.
"""
import json, os, sys
import bpy, numpy as np

out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:2]; TAG = os.environ.get("TAG", "v6m")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6l"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); KO = {k: K(k) for k in keys}
M = np.array(ob.matrix_world); M3 = M[:3, :3]; Mi = np.linalg.inv(M3)
W = B @ M3.T + M[:3, 3]
SEAM = [4636, 4693, 4697, 4657, 4655, 4651, 4648]
plan = {4655: 1, 4697: 2}                       # world axis to straighten
B1 = B.copy(); rec = []
for v, ax in plan.items():
    i = s2i[v]; j = SEAM.index(v); a, b = s2i[SEAM[j - 1]], s2i[SEAM[j + 1]]
    w = W[i].copy(); w[ax] = 0.5 * (W[a][ax] + W[b][ax])
    B1[i] = Mi @ (w - M[:3, 3])
    rec.append({"vertex": v, "axis": "xyz"[ax], "old_world_mm": [round(float(x) * 1000, 2) for x in W[i]], "new_world_mm": [round(float(x) * 1000, 2) for x in w],
                "move_mm": round(float(np.linalg.norm(B1[i] - B[i])) * 1000, 3), "seam_neighbours": [SEAM[j - 1], SEAM[j + 1]]})
for k in keys:
    a = KO[k] + (B1 - B) if k != "Basis" else B1
    me.shape_keys.key_blocks[k].data.foreach_set("co", a.ravel())
me.vertices.foreach_set("co", B1.ravel()); me.update()
moved = [s2i[v] for v in plan]; others = np.ones(nV, bool); others[moved] = False
per = {}
for k in keys:
    a = K(k)
    per[k] = {"others_max_mm": round(float(np.abs(a[others] - KO[k][others]).max()) * 1000, 6),
              "moved_offset_change_mm": round(float(np.abs((a - K("Basis"))[moved] - (KO[k] - B)[moved]).max()) * 1000, 6) if k != "Basis" else None}
rep = {"tag": TAG, "moves": rec, "other_vertices_all_keys_max_mm": max(v["others_max_mm"] for v in per.values()),
       "moved_vertices_offset_change_max_mm": max(v["moved_offset_change_mm"] for v in per.values() if v["moved_offset_change_mm"] is not None), "per_key": per}
json.dump(rep, open(os.path.join(qa, f"seam_report_{TAG}.json"), "w"), indent=1)
print("SEAM", json.dumps({k: v for k, v in rep.items() if k != "per_key"}))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_seam_fixed.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_seam_fixed.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

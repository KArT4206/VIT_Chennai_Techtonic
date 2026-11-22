"""PRIVATE: Phase 2N.7N - deformation-only correction of upper_lip_raise_L and mouth_smile_L on the LEFT upper-lip edge.

    blender -b <v6m_left_seam_fixed.blend> --python correct_smile_keys_7n.py -- <out_dir> <qa_dir>

Same method as 2N.7J, applied to KEYS (default upper_lip_raise_L,mouth_smile_L). Rest of every vertex is untouched.
  EDGE    = visible upper-lip edge 4648 4651 4655 4657 4697 4693 4636 4629 4691 4690 4689 4688 4589 4556 4525 4524
  FALLOFF = RINGS rings of existing upper-lip neighbours (above the lip line, not lower lip, not the back lining chain)
  PATCH   = every new (patch / tuck) vertex: re-solved on the full mesh graph so it stays continuous with its chains
  For each key, offsets on EDGE+FALLOFF(+PATCH) = harmonic continuation of all other (fixed) offsets.
  The corner 4524 also sees the lower-lip edge, so the commissure blends.
"""
import json, os, sys
import bpy, numpy as np

out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:2]
KEYS = os.environ.get("KEYS", "upper_lip_raise_L,mouth_smile_L").split(","); RINGS = int(os.environ.get("RINGS", "2")); TAG = os.environ.get("TAG", "v6n")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6m"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); KO = {k: K(k) for k in keys}
M = np.array(ob.matrix_world); M3 = M[:3, :3]; Wz = (B @ M3.T)[:, 2]
adj = [set() for _ in range(nV)]
for e in me.edges: a, b = e.vertices; adj[a].add(b); adj[b].add(a)
patch = {i for i in range(nV) if sidx[i] < 0}
EDGE_SRC = [4648, 4651, 4655, 4657, 4697, 4693, 4636, 4629, 4691, 4690, 4689, 4688, 4589, 4556, 4525, 4524]
EDGE = [s2i[v] for v in EDGE_SRC]
LOWER = {s2i[v] for v in [4554, 5176, 4534, 4560, 4605, 4722, 4717, 4721, 4678, 4627]}
BACK = {s2i[v] for v in [4641, 5795, 5825, 5771, 5857, 5845, 5843, 5841, 5839, 5755, 5811, 5783, 4621]}
zmin = min(Wz[v] for v in EDGE) - 0.0005
fall = set(); ring = set(EDGE)
for _ in range(RINGS):
    ring = {u for v in ring for u in adj[v] if u not in patch and u not in LOWER and u not in BACK and u not in EDGE and u not in fall and Wz[u] >= zmin}
    fall |= ring
FREE_EX = EDGE + sorted(fall)
FREE = FREE_EX + sorted(patch)
nbr = {v: ([u for u in adj[v] if u not in patch] if v not in patch else list(adj[v])) for v in FREE}
rec = {}
for k in KEYS:
    D = KO[k] - B; Dn = D.copy()
    for _ in range(6000):
        for v in FREE: Dn[v] = Dn[nbr[v]].mean(0)
    me.shape_keys.key_blocks[k].data.foreach_set("co", (B + Dn).ravel())
    rec[k] = [{"src": int(sidx[v]), "role": "edge" if v in EDGE else "falloff", "orig_world_mm": [round(float(x) * 1000, 2) for x in M3 @ D[v]],
               "new_world_mm": [round(float(x) * 1000, 2) for x in M3 @ Dn[v]]} for v in FREE_EX]
    rec[k + "_patch_max_change_mm"] = round(float(np.linalg.norm(Dn[sorted(patch)] - D[sorted(patch)], axis=1).max()) * 1000, 3)
me.update()
FR = np.zeros(nV, bool); FR[FREE] = True
per = {k: round(float(np.abs(K(k)[~FR] - KO[k][~FR]).max()) * 1000, 6) for k in keys}
per_free = {k: round(float(np.abs(K(k)[FR] - KO[k][FR]).max()) * 1000, 4) for k in keys}
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
rep = {"tag": TAG, "keys_corrected": KEYS, "edge": EDGE_SRC, "falloff_src": [int(sidx[v]) for v in sorted(fall)], "patch_vertices_resolved": len(patch),
       "outside_region_all_keys_max_mm": max(per.values()), "keys_changed_in_region": [k for k, v in per_free.items() if v > 1e-6],
       "eye_18_max_mm": max(max(per[k], per_free[k]) for k in EYE), "rest_max_change_mm": max(per["Basis"], per_free["Basis"]), "corrections": rec}
json.dump(rep, open(os.path.join(qa, f"smile_key_report_{TAG}.json"), "w"), indent=1)
print("KEYS", json.dumps({k: v for k, v in rep.items() if k != "corrections"}))
for r in rec["upper_lip_raise_L"][:len(EDGE)]: print("RAISE", r["src"], r["orig_world_mm"][2], "->", r["new_world_mm"][2])
for r in rec["mouth_smile_L"][:len(EDGE)]: print("SMILE", r["src"], r["orig_world_mm"][2], "->", r["new_world_mm"][2])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_smile_keys.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_smile_keys.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

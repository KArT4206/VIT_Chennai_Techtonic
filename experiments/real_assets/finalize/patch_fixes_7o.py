"""PRIVATE: Phase 2N.7O - patch-only fixes (2N.7N -> 2N.7O). Existing vertices are never touched.

    blender -b <v6n_left_smile_keys.blend> --python patch_fixes_7o.py -- <out_dir> <qa_dir>

1. Tuck-strip middle row (src_idx -3): for FOLLOW_KEYS (upper_lip_raise_L, mouth_smile_L) its offset now equals the
   upper-lip edge (outer chain 4636..4648) at the same arclength, instead of the 50/50 edge/lining blend, so it rises
   with the lip and stays hidden behind the notch.
2. Corner tip: new patch vertices adjacent to 4524/4525 are moved CORNER_IN_MM deeper into the mouth at rest
   (new geometry only); all their key offsets are kept (carried).
"""
import json, os, sys
import bpy, numpy as np

out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:2]
FOLLOW = os.environ.get("FOLLOW_KEYS", "upper_lip_raise_L,mouth_smile_L").split(","); CIN = float(os.environ.get("CORNER_IN_MM", "1.5")) / 1000
TAG = os.environ.get("TAG", "v6o")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6n"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); KO = {k: K(k) for k in keys}
adj = [set() for _ in range(nV)]
for e in me.edges: a, b = e.vertices; adj[a].add(b); adj[b].add(a)
OUT = [s2i[v] for v in (4636, 4693, 4697, 4657, 4655, 4651, 4648)]
def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B[ch[i + 1]] - B[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
mids = [i for i in range(nV) if sidx[i] == -3]
KN = {k: v.copy() for k, v in KO.items()}
rec1 = []
for n, v in enumerate(mids):                       # created in s order 0.25, 0.5, 0.75
    s = (n + 1) / (len(mids) + 1)
    for k in FOLLOW:
        old = KO[k][v] - B[v]; new = sample(OUT, s, KO[k] - B)
        KN[k][v] = B[v] + new
        rec1.append({"vertex": int(v), "s": s, "key": k, "old_mm": [round(float(x) * 1000, 2) for x in old], "new_mm": [round(float(x) * 1000, 2) for x in new]})
# corner tip: new vertices adjacent to 4524 / 4525
M3 = np.array(ob.matrix_world)[:3, :3]; inward = np.linalg.inv(M3) @ np.array([0, 1.0, 0]); inward /= np.linalg.norm(inward)
corner = sorted({u for v in (s2i[4524], s2i[4525]) for u in adj[v] if sidx[u] < 0})
for v in corner:
    for k in keys: KN[k][v] = KN[k][v] + CIN * inward
for k in keys: me.shape_keys.key_blocks[k].data.foreach_set("co", KN[k].ravel())
me.vertices.foreach_set("co", KN["Basis"].ravel()); me.update()
ex = sidx >= 0
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
per = {k: round(float(np.abs(K(k)[ex] - KO[k][ex]).max()) * 1000, 6) for k in keys}
rep = {"tag": TAG, "follow_keys": FOLLOW, "tuck_mid_vertices": len(mids), "tuck_changes": rec1, "corner_vertices_moved": len(corner), "corner_in_mm": CIN * 1000,
       "existing_vertices_all_keys_max_mm": max(per.values()), "eye_18_existing_max_mm": max(per[k] for k in EYE)}
json.dump(rep, open(os.path.join(qa, f"patch_fix_report_{TAG}.json"), "w"), indent=1)
print("FIX", json.dumps({k: v for k, v in rep.items() if k != "tuck_changes"}))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_patch_fixes.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_patch_fixes.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

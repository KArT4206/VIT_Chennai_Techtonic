"""PRIVATE: Phase 2N.7Q - local jaw_open deformation of the LEFT inner lining behind the corner (2N.7P -> 2N.7Q).

    blender -b <v6p_left_corner_tip.blend> --python lining_jaw_7q.py -- <out_dir> <qa_dir>     (env ALPHA, TAG)

Only jaw_open changes. Rest and every other key untouched.
  SEED   = the existing lining vertices the corner patch attaches to: 5839 5755 5811 5783 4621 (upper) + 5782 5808 (corner/lower)
  REGION = SEED + RINGS rings of existing lining neighbours (never visible-lip, never the patch, never the protected edge)
  For a region vertex v: lip(v) = corrected jaw_open vector of the matching lip-edge point (upper seeds -> upper edge
  4689..4524 by arclength, corner/lower seeds -> 4524/4554), propagated into the ring vertices by harmonic averaging.
  h(v) = harmonic falloff, 1 on SEED, 0 on the ring just outside REGION (deep healthy lining stays as is).
  new_jaw(v) = jaw(v) + ALPHA * h(v) * (lip(v) - jaw(v))      (full vectors, so directions are kept)
  Patch vertices (new geometry) are then re-solved harmonically for jaw_open on the full graph so they stay attached.
"""
import json, math, os, sys
import bpy, numpy as np

out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:2]
ALPHA = float(os.environ.get("ALPHA", "0.5")); RINGS = int(os.environ.get("RINGS", "2")); TAG = os.environ.get("TAG", "v6q")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6p"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); J0 = K("jaw_open") - B
adj = [set() for _ in range(nV)]
for e in me.edges: a, b = e.vertices; adj[a].add(b); adj[b].add(a)
patch = {i for i in range(nV) if sidx[i] < 0}
EDGE_UP = [s2i[v] for v in (4689, 4688, 4589, 4556, 4525, 4524)]
SEED_UP = [s2i[v] for v in (5839, 5755, 5811, 5783, 4621)]
SEED_LO = {s2i[5782]: s2i[4524], s2i[5808]: s2i[4554]}
PROT_SRC = [4648, 4651, 4655, 4657, 4697, 4693, 4636, 4629, 4691, 4690, 4689, 4688, 4589, 4556, 4525, 4524,
            4554, 5176, 4534, 4560, 4605, 4722, 4717, 4721, 4678, 4627]
prot = {s2i[v] for v in PROT_SRC}
# visible lip/skin faces (front-facing at rest from the corner camera were mapped in 2N.7H as 'protected'); here: any
# vertex of a face that has no patch vertex and touches the protected edge is treated as visible lip -> excluded
vis = {v for p in me.polygons if any(x in prot for x in p.vertices) and not any(x in patch for x in p.vertices) for v in p.vertices}
def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B[ch[i + 1]] - B[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
lip = {}
for v, s in zip(SEED_UP, arclen(SEED_UP)): lip[v] = sample(EDGE_UP, s, J0)
for v, e in SEED_LO.items(): lip[v] = J0[e]
seed = set(lip)
region = set(seed); ring = set(seed)
for _ in range(RINGS):
    ring = {u for v in ring for u in adj[v] if u not in patch and u not in prot and u not in vis and u not in region}
    region |= ring
outer = {u for v in region for u in adj[v] if u not in region and u not in patch}
free = sorted(region - seed)
nb = {v: [u for u in adj[v] if u not in patch] for v in free}
h = np.zeros(nV); L = np.zeros((nV, 3))
for v in seed: h[v] = 1.0; L[v] = lip[v]
for v in outer: L[v] = J0[v]                                   # outside: lip target = own motion (no pull)
for _ in range(4000):
    for v in free:
        h[v] = np.mean([h[u] if (u in region or u in outer) else 0.0 for u in nb[v]])
        L[v] = np.mean([L[u] if (u in region or u in outer) else J0[u] for u in nb[v]], axis=0)
J1 = J0.copy()
for v in region: J1[v] = J0[v] + ALPHA * h[v] * (L[v] - J0[v])
# patch: harmonic re-solve of jaw_open on new vertices (existing = boundary)
pl = sorted(patch)
for _ in range(4000):
    for v in pl: J1[v] = J1[list(adj[v])].mean(0)
# blend: keep the original patch explicit-correspondence shape, add only the smooth change from the boundary move
# (patch change = harmonic(J1 boundary) - harmonic(J0 boundary))
Jh0 = J0.copy()
for _ in range(4000):
    for v in pl: Jh0[v] = Jh0[list(adj[v])].mean(0)
Jfinal = J1.copy(); Jfinal[pl] = J0[pl] + (J1[pl] - Jh0[pl])
me.shape_keys.key_blocks["jaw_open"].data.foreach_set("co", (B + Jfinal).ravel()); me.update()
M3 = np.array(ob.matrix_world)[:3, :3]
rig = bpy.data.objects["GNM_Rig"]
mid = np.array((rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2)
Wp = lambda v: (np.array(ob.matrix_world) @ np.r_[B[v], 1])[:3] - mid
corner = Wp(s2i[4524]); edge_pts = np.array([Wp(v) for v in EDGE_UP])
rows = []
for v in sorted(region):
    cls = "commissure" if v in SEED_LO or sidx[v] == 4621 else ("upper_lining" if Wp(v)[2] > corner[2] else "lower_lining")
    rows.append({"src": int(sidx[v]), "class": cls, "seed": v in seed, "h": round(float(h[v]), 3),
                 "jaw_old_world_mm": [round(float(x) * 1000, 2) for x in M3 @ J0[v]], "jaw_new_world_mm": [round(float(x) * 1000, 2) for x in M3 @ Jfinal[v]],
                 "dist_to_edge_mm": round(float(np.linalg.norm(edge_pts - Wp(v), axis=1).min()) * 1000, 1), "dist_to_corner_mm": round(float(np.linalg.norm(Wp(v) - corner)) * 1000, 1),
                 "faces": [p.index for p in me.polygons if v in p.vertices]})
chg = np.linalg.norm(Jfinal - J0, axis=1) * 1000
others = np.ones(nV, bool); others[list(region)] = False; others[pl] = False
per = {}
for k in keys:
    a = K(k); b = B + (J0 if k == "jaw_open" else (K(k) - B))
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
rep = {"tag": TAG, "alpha": ALPHA, "rings": RINGS, "region_existing_vertices": len(region), "seed": [int(sidx[v]) for v in seed], "patch_vertices_adjusted": len(pl),
       "jaw_change_mm": {"existing_max": round(float(chg[list(region)].max()), 3), "existing_mean": round(float(chg[list(region)].mean()), 3),
                         "patch_max": round(float(chg[pl].max()), 3), "patch_mean": round(float(chg[pl].mean()), 3), "outside_max": round(float(chg[others].max()), 6)},
       "rest_change_mm": 0.0, "keys_changed": ["jaw_open"], "eye_18_change_mm": 0.0, "region": rows}
json.dump(rep, open(os.path.join(qa, f"lining_jaw_{TAG}.json"), "w"), indent=1)
print("LINING", json.dumps({k: v for k, v in rep.items() if k != "region"}))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_lining_jaw.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_lining_jaw.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

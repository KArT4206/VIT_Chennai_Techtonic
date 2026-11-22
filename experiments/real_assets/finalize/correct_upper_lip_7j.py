"""PRIVATE: Phase 2N.7J - jaw_open deformation correction of the LEFT visible upper-lip inner edge + patch reconciliation.

    blender -b <v6i_02_left_reconstructed.blend> --python correct_upper_lip_7j.py -- <topology_v6i.json> <out_dir> <qa_dir> [--diag-only]

Works on a copy of GNM_Head_v6i (2N.7I) renamed GNM_Head_v6j. Basis/rest of every vertex is never written.
  EDGE   = the 10 visible upper-lip inner-edge vertices (src 4636 ... 4524).
  FALLOFF= FALLOFF_RINGS rings of existing upper-lip neighbours of EDGE (above the lip line, not patch, not lower lip,
           not the back lining chain).
  jaw_open offsets on EDGE+FALLOFF are replaced by the harmonic (Laplace) interpolation of the surrounding healthy
  upper-lip offsets over the ORIGINAL mesh edges (patch vertices excluded): every vertex outside EDGE+FALLOFF keeps its
  offset and acts as the boundary. EDGE vertices are free (natural boundary), so they take the smooth continuation of
  the upper lip instead of the 5-8 mm uneven drop. The corner (4524) also sees the lower-lip edge (4554) as a fixed
  neighbour, so it blends upper and lower motion.
  Patch: every new (2N.7I) vertex is re-derived with the same explicit correspondence for ALL keys, now from the
  corrected chain offsets (only jaw_open actually changes). Optional INWARD_MM pushes new patch vertices deeper into the
  mouth at rest (new geometry only) to hide the neutral slivers.
"""
import json, math, os, sys
import bpy, numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
topo_p, out_dir, qa = argv[:3]; DIAG = "--diag-only" in argv
RINGS = int(os.environ.get("FALLOFF_RINGS", "2")); INWARD = float(os.environ.get("INWARD_MM", "0")) / 1000; TAG = os.environ.get("TAG", "v6j"); BIAS = float(os.environ.get("UPPER_BIAS", "1"))
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
T = json.load(open(topo_p))
FRONT, BACK = T["front_chain"], T["back_chain"]; FC, BC = FRONT.index(4524), BACK.index(4621)
EDGE_SRC = FRONT[:FC + 1]
src = bpy.data.objects["GNM_Head_v6i"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices)
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
newv = [i for i in range(nV) if sidx[i] < 0]
assert len(newv) == len(T["new_vertices"])
keys = [k.name for k in me.shape_keys.key_blocks]
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); D0 = {k: K(k) - B for k in keys}
M3 = np.array(ob.matrix_world)[:3, :3]
rig = bpy.data.objects["GNM_Rig"]
mid = np.array((rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2)
Wp = (np.c_[B, np.ones(nV)] @ np.array(ob.matrix_world).T)[:, :3] - mid
adj = [set() for _ in range(nV)]
for e in me.edges:
    a, b = e.vertices; adj[a].add(b); adj[b].add(a)
newset = set(newv)
EDGE = [s2i[v] for v in EDGE_SRC]
LOWER_FRONT = {s2i[v] for v in FRONT[FC + 1:]}; BACKS = {s2i[v] for v in BACK}
zmin = min(Wp[v][2] for v in EDGE) - 0.0005
fall = set(); ring = set(EDGE)
for _ in range(RINGS):
    ring = {u for v in ring for u in adj[v] if u not in newset and u not in LOWER_FRONT and u not in BACKS and u not in EDGE and u not in fall
            and Wp[u][2] >= zmin}
    fall |= ring
EXTRA = [s2i[int(x)] for x in os.environ.get("EXTRA_FALLOFF", "").split(",") if x]   # documented extra falloff (same lip-edge line)
fall |= set(EXTRA)
FREE = EDGE + sorted(fall)
# ---------- diagnosis ----------
J = D0["jaw_open"]; Jw = J @ M3.T
diag = []
for v, sv in zip(EDGE, EDGE_SRC):
    up = [int(sidx[u]) for u in adj[v] if u not in newset and u not in LOWER_FRONT and u not in EDGE]
    pt = [int(u) for u in adj[v] if u in newset]
    nb_edge = [EDGE.index(u) for u in adj[v] if u in EDGE]
    # sawtooth contribution: vertical deviation of this vertex's jaw drop from the mean of its edge neighbours
    dev = float(Jw[v][2] - np.mean([Jw[u][2] for u in adj[v] if u in EDGE])) * 1000 if nb_edge else None
    diag.append({"src_vertex": sv, "rest_rel_eyes_mm": [round(float(x) * 1000, 2) for x in Wp[v]], "jaw_vec_world_mm": [round(float(x) * 1000, 2) for x in Jw[v]],
                 "jaw_mag_mm": round(float(np.linalg.norm(Jw[v])) * 1000, 2), "upper_lip_neighbours_src": up, "patch_neighbours_v6i": pt,
                 "sawtooth_dev_vs_edge_neighbours_mm": None if dev is None else round(dev, 2)})
# ---------- harmonic correction of jaw_open on FREE (original-mesh edges only) ----------
nbr = {v: [u for u in adj[v] if u not in newset] for v in FREE}
Jn = J.copy()
for _ in range(6000):
    for v in FREE: Jn[v] = Jn[nbr[v]].mean(0)
corr = [{"src_vertex": int(sidx[v]), "role": "edge" if v in EDGE else "falloff", "orig_mm": [round(float(x) * 1000, 2) for x in (J[v] @ M3.T)],
         "new_mm": [round(float(x) * 1000, 2) for x in (Jn[v] @ M3.T)], "change_mm": round(float(np.linalg.norm(Jn[v] - J[v])) * 1000, 2)} for v in FREE]
print("FREE", len(EDGE), "edge +", len(fall), "falloff")
for r in diag: print("EDGE", r["src_vertex"], r["jaw_vec_world_mm"], r["jaw_mag_mm"], "dev", r["sawtooth_dev_vs_edge_neighbours_mm"])
for r in corr[:len(EDGE)]: print("CORR", r["src_vertex"], r["orig_mm"], "->", r["new_mm"])
json.dump({"edge_vertices": diag, "falloff_src_vertices": [int(sidx[v]) for v in sorted(fall)], "correction": corr, "falloff_rings": RINGS, "extra_falloff_src": [int(sidx[v]) for v in EXTRA]},
          open(os.path.join(qa, f"upper_lip_correction_{TAG}.json"), "w"), indent=1)
if DIAG: sys.exit(0)
D = {k: v.copy() for k, v in D0.items()}; D["jaw_open"] = Jn
# ---------- patch re-derivation (explicit correspondence, all keys) ----------
Bsrc = B  # chains are existing vertices: rest unchanged
def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B[ch[i + 1]] - B[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
Fi = [s2i[v] for v in FRONT]; Bi = [s2i[v] for v in BACK]
halves = {"upper": (Fi[:FC + 1], Bi[:BC + 1]), "lower": (Fi[FC:], Bi[BC:])}
inward = np.linalg.inv(M3) @ np.array([0, 1.0, 0]); inward /= np.linalg.norm(inward)
Bn = B.copy(); patch_change = {}
for v, nvinfo in zip(newv, T["new_vertices"]):
    F, Bk = halves[nvinfo["half"]]; t, s = nvinfo["t"], nvinfo["s"]
    for k in keys:
        if k == "Basis": continue
        tw = t ** BIAS if (nvinfo["half"] == "upper" and k != "jaw_open") else t   # upper patch hugs the lip edge for lip keys
        D[k][v] = (1 - tw) * sample(F, s, D[k]) + tw * sample(Bk, s, D[k])
    Bn[v] = B[v] + INWARD * math.sin(math.pi * t) * inward
for k in keys:
    if k == "Basis": continue
    patch_change[k] = round(float(np.linalg.norm(D[k][newv] - D0[k][newv], axis=1).max()) * 1000, 4)
# ---------- write ----------
for k in keys:
    me.shape_keys.key_blocks[k].data.foreach_set("co", (Bn + (D[k] if k != "Basis" else 0)).ravel())
me.vertices.foreach_set("co", Bn.ravel()); me.update()
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
old = np.array([i not in newset for i in range(nV)]); FREEm = np.zeros(nV, bool); FREEm[FREE] = True
per_key = {}
for k in keys:
    a = K(k); b = (B + D0[k]) if k != "Basis" else B
    diff = np.linalg.norm(a - b, axis=1) * 1000
    per_key[k] = {"existing_outside_correction_max_mm": round(float(diff[old & ~FREEm].max()), 6), "existing_correction_region_max_mm": round(float(diff[FREEm].max()), 4),
                  "patch_max_mm": round(float(diff[~old].max()), 4)}
rep = {"tag": TAG, "falloff_rings": RINGS, "inward_mm": INWARD * 1000, "edge": len(EDGE), "falloff": len(fall),
       "existing_rest_max_change_mm": per_key["Basis"]["existing_outside_correction_max_mm"] if True else None,
       "existing_rest_max_change_in_region_mm": per_key["Basis"]["existing_correction_region_max_mm"],
       "eye_18_max_mm_existing_vertices": max(max(per_key[k]["existing_outside_correction_max_mm"], per_key[k]["existing_correction_region_max_mm"]) for k in EYE),
       "eye_18_patch_offset_change_mm": max(float(np.linalg.norm(D[k][newv] - D0[k][newv], axis=1).max()) * 1000 for k in EYE),
       "patch_offset_change_mm_per_key": patch_change, "upper_bias": BIAS,
       "keys_changed_on_existing_vertices": [k for k in keys if per_key[k]["existing_correction_region_max_mm"] > 1e-6 or per_key[k]["existing_outside_correction_max_mm"] > 1e-6],
       "per_key_vs_2N7I": per_key}
json.dump(rep, open(os.path.join(qa, f"shape_key_report_{TAG}.json"), "w"), indent=1)
print("APPLY", json.dumps({k: v for k, v in rep.items() if k != "per_key_vs_2N7I"}))
g = ob.vertex_groups.new(name="upper_lip_edge_L"); g.add(EDGE, 1.0, "REPLACE")
g = ob.vertex_groups.new(name="upper_lip_falloff_L"); g.add(sorted(fall), 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_upper_lip_corrected.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_upper_lip_corrected.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

"""PRIVATE: Phase 2N.7H - expanded LEFT commissure region + reconstruction, built fresh from untouched v5.

    blender -b <v6_recon_00_checkpoint_start.blend> --python reconstruct_left_7h.py -- <selection_reference.json> <diag_v5.json> <out_dir> <qa_dir> [--plan-only]

Region (from diag_left_7h.py, camera evidence on v5):
  DEFECT  = left-mouth faces seen from their BACK side by the corner cameras (components with >= 2 faces)
            + the 14 confirmed slivers + the corner-tip faces (faces touching sliver vertices)
  PROTECTED (never moved) = vertices of any non-defect face seen from the FRONT at rest (visible lips / skin),
            the external crease chain, every non-Skin vertex.
  MOVABLE = vertices of DEFECT not PROTECTED, grown by RING_GROW hidden rings (hidden lining only).
  BOUNDARY = one ring around MOVABLE (fixed exactly).
Edit (on duplicate GNM_Head_v6h; GNM_Head is never touched):
  1. remove slivers, then peel dangling faces (>= 2 open edges, all vertices movable)
  2. rest: bi-Laplacian fairing of MOVABLE (two fixed rings, seam twins tied, tether TETHER to the scan surface)
  3. keys: every key carried (new = new_basis + old offset); jaw_open + corr_jaw_smile_L rebuilt by harmonic
     interpolation over MOVABLE on the post-removal connectivity (upper/lower sheets are not connected across the
     opening, so their motion stays distinct)
"""
import json, math, os, sys, csv
from collections import Counter
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index("--") + 1:]
ref_p, diag_p, out_dir, qa = argv[:4]; PLAN = "--plan-only" in argv
TETHER = float(os.environ.get("TETHER", "0.05")); RING_GROW = int(os.environ.get("RING_GROW", "1")); TAG = os.environ.get("TAG", "v6h")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
ref = json.load(open(ref_p)); DG = json.load(open(diag_p))
src = bpy.data.objects["GNM_Head"]; sme = src.data; nV = len(sme.vertices)
polys = [list(p.vertices) for p in sme.polygons]; mats = [m.name for m in sme.materials]
SLIV = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] == "commissure_sliver"]
CREASE = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] != "commissure_sliver"]
compsz = Counter(r["component"] for r in DG["defect_faces"])
BACK = {r["face"]: r["component"] for r in DG["defect_faces"] if compsz[r["component"]] >= 2}
EXCLUDED_SINGLE = [r["face"] for r in DG["defect_faces"] if compsz[r["component"]] < 2]
adj = [set() for _ in range(nV)]
for p in polys:
    for i in range(len(p)): a, b = p[i], p[(i + 1) % len(p)]; adj[a].add(b); adj[b].add(a)
sliv_v = {v for f in SLIV for v in polys[f]}
vf = [[] for _ in range(nV)]
for i, p in enumerate(polys):
    for v in p: vf[v].append(i)
TIP = sorted({f for v in sliv_v for f in vf[v]} - set(SLIV))
DEFECT = set(BACK) | set(SLIV) | set(TIP)
skin_v = {v for i, p in enumerate(polys) if mats[sme.polygons[i].material_index] == "Skin" for v in p}
nonskin_v = set(range(nV)) - skin_v
crease_v = {v for f in CREASE for v in polys[f]}
rest_vis = set(DG["rest_visible_faces"]) - DEFECT
protected = {v for f in rest_vis for v in polys[f]} | crease_v | nonskin_v
dverts = {v for f in DEFECT for v in polys[f]}
movable = dverts - protected
for _ in range(RING_GROW):
    movable |= {u for v in movable for u in adj[v] if u not in protected and all(g not in rest_vis for g in vf[u])}
boundary = {u for v in movable for u in adj[v]} - movable
old_core = set(json.load(open(os.environ.get("G7_CLASS", os.path.join(os.path.dirname(qa), "phase2n7g", "classification_left_core.json"))))["vertices"][i]["v"] for i in range(59))
old_ring = set(json.load(open(os.environ.get("G7_CLASS", os.path.join(os.path.dirname(qa), "phase2n7g", "classification_left_core.json"))))["ring_vertices"])
def K(m, n): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
keys = [k.name for k in sme.shape_keys.key_blocks]
B0 = K(sme, "Basis"); KO = {k: K(sme, k) for k in keys}; Jm = np.linalg.norm(KO["jaw_open"] - B0, axis=1) * 1000
rig = bpy.data.objects["GNM_Rig"]
mid = np.array((rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2)
Wd = (np.c_[B0, np.ones(nV)] @ np.array(src.matrix_world).T)[:, :3] - mid
# ---------- vertex table + plan ----------
def vclass(v):
    if v in movable:
        if v in sliv_v: return "movable_commissure_fold"
        if any(f in TIP for f in vf[v]): return "movable_corner_tip"
        if any(BACK.get(f) is not None for f in vf[v]):
            c = [BACK[f] for f in vf[v] if f in BACK][0]; return f"movable_backface_component_{c}"
        return "movable_hidden_lining_margin"
    return "fixed_boundary_protected_visible" if v in protected else "fixed_boundary_hidden"
rows = []
for v in sorted(movable | boundary):
    rows.append({"v": v, "role": vclass(v), "was_2N7G": "core" if v in old_core else ("ring" if v in old_ring else "new"),
                 "jaw_mm": round(float(Jm[v]), 2), "pos_rel_eyes_mm": " ".join(f"{x:.1f}" for x in Wd[v] * 1000)})
with open(os.path.join(qa, "region_vertices_7h.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
plan = {"defect_faces_backface": sorted(BACK), "defect_components": {str(c): sorted(f for f, cc in BACK.items() if cc == c) for c in set(BACK.values())},
        "excluded_single_face_components": EXCLUDED_SINGLE, "sliver_faces": SLIV, "corner_tip_faces": TIP,
        "movable": len(movable), "boundary": len(boundary), "boundary_protected_visible": len(boundary & protected),
        "movable_new_vs_2N7G": len(movable - old_core - old_ring), "movable_from_2N7G_ring": len(movable & old_ring), "movable_from_2N7G_core": len(movable & old_core),
        "old_ring_kept_fixed": len(old_ring - movable), "protected_in_defect_faces": sorted(dverts & protected)}
json.dump(plan, open(os.path.join(qa, "region_plan_7h.json"), "w"), indent=1)
print("PLAN", json.dumps({k: v for k, v in plan.items() if not isinstance(v, (list, dict))}), "protected_in_defect", len(plan["protected_in_defect_faces"]))
ov = {"sets": {"pinned_boundary_faces": {"rgb": [0.9, 0.9, 0.1], "faces": sorted({f for v in boundary for f in vf[v]} - DEFECT)},
               "lower_lining_backface": {"rgb": [0.1, 0.5, 1], "faces": [f for f, c in BACK.items() if Jm[polys[f]].mean() > 6 and f not in TIP]},
               "corner_tip_spike": {"rgb": [1, 1, 0.6], "faces": TIP},
               "slivers": {"rgb": [1, 0, 0], "faces": SLIV},
               "vflap_and_pink_flap": {"rgb": [1, 0.2, 0.9], "faces": [f for f, c in BACK.items() if Jm[polys[f]].mean() <= 6 and f not in TIP]}},
      "points": {"movable_new": {"rgb": [0, 1, 1], "verts": sorted(movable - old_core - old_ring)},
                 "movable_from_2N7G": {"rgb": [0.2, 1, 0.2], "verts": sorted(movable & (old_core | old_ring))},
                 "fixed_protected_visible": {"rgb": [0.1, 0.1, 1], "verts": sorted(boundary & protected)}}}
json.dump(ov, open(os.path.join(qa, "overlay_sets_7h.json"), "w"))
if PLAN: sys.exit(0)

# ---------- 1. topology plan (slivers + dangling peel) ----------
rem = set(SLIV); peeled = []
while True:
    cnt = Counter()
    for i, p in enumerate(polys):
        if i in rem: continue
        for j in range(len(p)): cnt[frozenset((p[j], p[(j + 1) % len(p)]))] += 1
    new = [i for i, p in enumerate(polys) if i not in rem and all(v in movable for v in p)
           and sum(cnt[frozenset((p[j], p[(j + 1) % len(p)]))] == 1 for j in range(len(p))) >= 2]
    if not new: break
    peeled += new; rem |= set(new)
keep = [i for i in range(len(polys)) if i not in rem]
adj2 = [set() for _ in range(nV)]; used = np.zeros(nV, bool)
for f in keep:
    p = polys[f]; used[p] = True
    for i in range(len(p)): a, b = p[i], p[(i + 1) % len(p)]; adj2[a].add(b); adj2[b].add(a)
mv = sorted(v for v in movable if used[v]); mset = set(mv)
# ---------- 2. rest fairing ----------
kd = KDTree(len(mv))
for i, v in enumerate(mv): kd.insert(Vector(B0[v]), i)
kd.balance()
group = {v: min(mv[j] for (_, j, d) in kd.find_range(Vector(B0[v]), 1e-7)) for v in mv}
reps = sorted(set(group.values())); col = {r: i for i, r in enumerate(reps)}
rowsL = sorted({u for v in mv for u in adj2[v]} | mset)
def lap(v):
    nb = list(adj2[v]); r = {v: -1.0}
    for u in nb: r[u] = r.get(u, 0) + 1.0 / len(nb)
    return r
Lr = {v: lap(v) for v in set(rowsL) | {u for v in rowsL for u in adj2[v]} if adj2[v]}
A, bb = [], []
for v in rowsL:
    r = {}
    for u, w in Lr[v].items():
        for t, w2 in Lr.get(u, {u: 0}).items(): r[t] = r.get(t, 0) + w * w2
    a = np.zeros(len(reps)); rhs = np.zeros(3)
    for t, w in r.items():
        if t in mset: a[col[group[t]]] += w
        else: rhs -= w * B0[t]
    A.append(a); bb.append(rhs)
for r_ in reps:
    a = np.zeros(len(reps)); a[col[r_]] = TETHER; A.append(a); bb.append(TETHER * B0[r_])
X = np.linalg.lstsq(np.array(A), np.array(bb), rcond=None)[0]
B1 = B0.copy()
for v in mv: B1[v] = X[col[group[v]]]
# 2b. retraction: the backfacing lining is correctly oriented but sits too far FORWARD (past the lip edge), so it is
#     tucked back into the mouth along world +Y by RETRACT_MM, weighted by a harmonic field h (0 on the fixed boundary,
#     1 on the vertices of the backfacing / tip faces) so the transition into the fixed boundary is smooth.
RETRACT = float(os.environ.get("RETRACT_MM", "0")) / 1000.0
SEED_FACES = set(BACK) if os.environ.get("SEED_TIP", "0") == "0" else DEFECT
seed = ({v for f in SEED_FACES for v in polys[f]} & mset) - (sliv_v if os.environ.get("SEED_TIP", "0") == "0" else set())
h = np.zeros(nV); h[list(seed)] = 1.0
free = [v for v in mv if v not in seed]
for _ in range(3000):
    for v in free: h[v] = np.mean(h[list(adj2[v])])
Minv = np.array(src.matrix_world.inverted())[:3, :3]
dir_local = Minv @ np.array([0.0, 1.0, 0.0]); dir_local /= np.linalg.norm(dir_local)
for v in mv: B1[v] = B1[v] + h[v] * RETRACT * dir_local
disp = np.linalg.norm(B1 - B0, axis=1) * 1000
# ---------- 3. keys ----------
KN = {k: KO[k].copy() for k in keys}
for k in keys: KN[k][mv] = B1[mv] + (KO[k][mv] - B0[mv])
KN["Basis"] = B1.copy(); KC = {k: v.copy() for k, v in KN.items()}
REPAIR = os.environ.get("REPAIR_KEYS", "jaw_open,corr_jaw_smile_L").split(","); hm = {}
for k in REPAIR:
    D = KN[k] - B1; D0 = D.copy()
    for _ in range(8000):
        nd = D.copy()
        for v in mv: nd[v] = D[list(adj2[v])].mean(0)
        D = nd
    KN[k] = B1 + D; hm[k] = round(float(np.linalg.norm(D - D0, axis=1)[mv].max()) * 1000, 3)
# ---------- apply ----------
dst = src.copy(); dst.data = src.data.copy(); dst.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(dst)
src.hide_render = True; src.hide_viewport = True
me = dst.data
for n, vs in (("repair_movable_L", mset), ("repair_boundary_L", boundary)):
    g = dst.vertex_groups.new(name=n); g.add(sorted(vs), 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_00_checkpoint_before_edit.blend"), compress=True, copy=True)
def write(Kd):
    for k in keys: me.shape_keys.key_blocks[k].data.foreach_set("co", Kd[k].ravel())
    me.vertices.foreach_set("co", Kd["Basis"].ravel()); me.update()
write(KC); bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_01_rest_corrected.blend"), compress=True, copy=True)
write(KN)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
lay = bm.verts.layers.int.new("src_idx")
for v in bm.verts: v[lay] = v.index
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sorted(rem)], context="FACES_ONLY")
wire = [e for e in bm.edges if not e.link_faces]; bmesh.ops.delete(bm, geom=wire, context="EDGES")
loose = [v for v in bm.verts if not v.link_edges]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.verts.ensure_lookup_table(); smap = np.array([v[lay] for v in bm.verts])
bm.to_mesh(me); bm.free(); me.update()
def SK(m, k): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[k].data.foreach_get("co", a); return a.reshape(-1, 3)
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
inm = np.isin(smap, mv); kr = {}
for k in keys:
    New = SK(me, k); Old = KO[k][smap]
    kr[k] = {"outside_movable_abs_max_mm": round(float(np.abs(New[~inm] - Old[~inm]).max()) * 1000, 6),
             "movable_offset_change_max_mm": round(float(np.linalg.norm((New - SK(me, "Basis"))[inm] - (Old - B0[smap])[inm], axis=1).max()) * 1000, 6)}
dm = disp[mv]
rep = {"tag": TAG, "tether": TETHER, "retract_mm": RETRACT * 1000, "ring_grow": RING_GROW, "plan": plan, "faces_removed_slivers": SLIV, "faces_removed_peeled": peeled,
       "movable_used": len(mv), "twin_groups": len(reps),
       "rest_displacement_mm": {"max": round(float(dm.max()), 3), "mean": round(float(dm.mean()), 3), "rms": round(float(np.sqrt((dm ** 2).mean())), 3)},
       "per_vertex_disp_mm": {int(v): round(float(disp[v]), 3) for v in mv}, "fixed_max_disp_mm": float(np.delete(disp, mv).max()),
       "harmonic_change_mm": hm, "vertices_before": nV, "vertices_after": len(me.vertices), "new_vertices": 0, "wire_edges_removed": len(wire),
       "loose_removed": len(loose), "non_manifold_edges": nonman, "key_report": kr,
       "eye_18_max_mm": max(max(kr[k]["outside_movable_abs_max_mm"], kr[k]["movable_offset_change_max_mm"]) for k in EYE),
       "other_keys_offset_change_in_movable_max_mm": max(kr[k]["movable_offset_change_max_mm"] for k in keys if k not in REPAIR + ["Basis"]),
       "outside_movable_all_keys_max_mm": max(v["outside_movable_abs_max_mm"] for v in kr.values())}
json.dump(rep, open(os.path.join(qa, f"reconstruct_report_{TAG}.json"), "w"), indent=1, default=float)
print("APPLY", json.dumps({k: v for k, v in rep.items() if k not in ("key_report", "plan", "per_vertex_disp_mm")}))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_02_left_reconstructed.blend"), compress=True)
keepo = {"GNM_Rig", dst.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = dst
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_02_left_reconstructed.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

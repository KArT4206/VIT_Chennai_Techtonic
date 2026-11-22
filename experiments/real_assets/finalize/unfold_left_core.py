"""PRIVATE: Phase 2N.7G - local REST-geometry unfolding + LEFT commissure reconstruction (reproducible).

    blender -b <v6_recon_00_checkpoint_start.blend> --python unfold_left_core.py -- <selection_reference.json> <classification.json> <out_dir> <qa_dir> [--dry]

Never edits GNM_Head (v5 source); works on a duplicate GNM_Head_v6g. Order of operations (all in the v5 vertex index space,
then the topology edit is done in bmesh WITH shape layers so every key follows exactly):
  1. region = 2N.7F repair_core_L / repair_ring_L; classes from classify_left_core.py.
     MOVABLE (rest) = hidden classes only (commissure_fold, corner_tip, inner_upper/lower_lining).
     FIXED   (rest) = 43-vertex ring, every visible_lip_margin vertex, crease chain, everything outside.
  2. remove the 14 sliver faces (their vertices stay if used by other faces).
  3. rest unfold: bi-Laplacian (thin-plate) fairing of MOVABLE over the post-removal connectivity, two fixed rings as the
     boundary condition (C1 continuity), coincident seam twins tied (no closure gap), mild tether to the original surface
     so the lining stays curved (not flattened).
  4. key carry: for every key k and moved vertex, new_k = new_basis + (old_k - old_basis)  -> neutral stays neutral and
     every key keeps its offsets (relative keys all point at Basis).
  5. jaw_open and corr_jaw_smile_L rebuilt on the core by harmonic interpolation over the post-removal connectivity
     (upper and lower sheets are not connected across the opening, so their motions do not mix).
  6. remove orphan wire edges / loose vertices.
Writes checkpoints 00 (before edit) / 01 (after rest correction) / 02 (final), a test GLB and JSON reports.
"""
import json, math, os, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
ref_p, cls_p, out_dir, qa = argv[:4]; DRY = "--dry" in argv
TETHER = float(os.environ.get("TETHER", "0.05")); STOP_MM = float(os.environ.get("STOP_MM", "2.0"))
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
ref = json.load(open(ref_p)); C = json.load(open(cls_p))
FLAP = [7158, 7159, 7160, 7161, 7162, 7212, 7213, 7236]
SLIV = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] == "commissure_sliver"]
CREASE = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] != "commissure_sliver"]
cls = {r["v"]: r["class"] for r in C["vertices"]}
core = set(cls); ring = set(C["ring_vertices"])
HIDDEN = {"commissure_fold", "corner_tip", "inner_upper_lining", "inner_lower_lining"}
movable = sorted(v for v, c in cls.items() if c in HIDDEN)

src = bpy.data.objects["GNM_Head"]; sme = src.data
nV = len(sme.vertices)
polys = [list(p.vertices) for p in sme.polygons]
sliv_set = set(SLIV)
# 2b. peel the damaged lining left behind by the sliver removal: core-only faces with >= 2 open edges are dangling
#     fan triangles / floating islands (e.g. face 7092 is completely isolated once the slivers go). Repeat until stable.
PEEL = os.environ.get("PEEL", "1") == "1"
peeled = []
from collections import Counter
while PEEL:
    cnt = Counter()
    for i, p in enumerate(polys):
        if i in sliv_set: continue
        for j in range(len(p)): cnt[frozenset((p[j], p[(j + 1) % len(p)]))] += 1
    new = [i for i, p in enumerate(polys) if i not in sliv_set and all(v in core for v in p)
           and sum(cnt[frozenset((p[j], p[(j + 1) % len(p)]))] == 1 for j in range(len(p))) >= 2]
    if not new: break
    peeled += new; sliv_set |= set(new)
REMOVE = sorted(sliv_set)
keep_faces = [i for i in range(len(polys)) if i not in sliv_set]
adj = [set() for _ in range(nV)]
for f in keep_faces:
    p = polys[f]
    for i in range(len(p)): a, b = p[i], p[(i + 1) % len(p)]; adj[a].add(b); adj[b].add(a)
def K(m, n): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
keys = [k.name for k in sme.shape_keys.key_blocks]
B0 = K(sme, "Basis"); KO = {k: K(sme, k) for k in keys}
used = np.zeros(nV, bool)
for f in keep_faces: used[polys[f]] = True
movable = [v for v in movable if used[v]]           # vertices only used by slivers become loose and are removed
mset = set(movable)

# ---------- 3. rest unfold (bi-Laplacian fairing, twins tied, tether) ----------
from mathutils.kdtree import KDTree
kd = KDTree(len(movable))
for i, v in enumerate(movable): kd.insert(Vector(B0[v]), i)
kd.balance()
group = {}
for v in movable:
    tw = sorted(movable[j] for (_, j, d) in kd.find_range(Vector(B0[v]), 1e-7))
    group[v] = tw[0]
reps = sorted(set(group.values())); col = {r: i for i, r in enumerate(reps)}
n1 = {u for v in movable for u in adj[v]} | mset
rows = sorted(n1)                                     # Laplacian rows whose energy is minimised (movable + 1st ring)
def lap_row(v):                                       # uniform Laplacian: mean(nb) - x
    nb = list(adj[v]); r = {v: -1.0}
    for u in nb: r[u] = r.get(u, 0) + 1.0 / len(nb)
    return r
Lr = {v: lap_row(v) for v in set(rows) | {u for v in rows for u in adj[v]}}
def bilap(v):                                         # (L L x)_v
    out = {}
    for u, w in Lr[v].items():
        for t, w2 in Lr[u].items(): out[t] = out.get(t, 0) + w * w2
    return out
A = []; b = []
for v in rows:
    r = bilap(v); a = np.zeros(len(reps)); rhs = np.zeros(3)
    for t, w in r.items():
        if t in mset: a[col[group[t]]] += w
        else: rhs -= w * B0[t]
    A.append(a); b.append(rhs)
for r_ in reps:                                       # tether keeps the curved oral surface (no flattening)
    a = np.zeros(len(reps)); a[col[r_]] = TETHER; A.append(a); b.append(TETHER * B0[r_])
A = np.array(A); b = np.array(b)
X = np.linalg.lstsq(A, b, rcond=None)[0] if os.environ.get("UNFOLD", "1") == "1" else np.array([B0[r_] for r_ in reps])
B1 = B0.copy()
for v in movable: B1[v] = X[col[group[v]]]
disp = np.linalg.norm(B1 - B0, axis=1) * 1000
dm = disp[movable]

# ---------- quality helpers (post-removal faces touching the core) ----------
rf = [f for f in keep_faces if any(v in core for v in polys[f])]
emap = {}
for f in rf:
    p = polys[f]
    for i in range(len(p)): emap.setdefault(frozenset((p[i], p[(i + 1) % len(p)])), []).append(f)
def tri_n(P, vs):
    n = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); return n
def quality(P, ref_n=None):
    N = {}; out = {"faces": len(rf), "min_area_mm2": 1e9, "faces_area_below_0_05mm2": 0, "max_aspect": 0}
    worst = []
    for f in rf:
        vs = polys[f]; n = tri_n(P, vs); ar = np.linalg.norm(n) / 2
        e = [np.linalg.norm(P[vs[i]] - P[vs[(i + 1) % 3]]) for i in range(3)]
        out["min_area_mm2"] = min(out["min_area_mm2"], ar * 1e6); out["faces_area_below_0_05mm2"] += int(ar * 1e6 < 0.05)
        out["max_aspect"] = max(out["max_aspect"], max(e) ** 2 / (4 * ar / math.sqrt(3) + 1e-18)); N[f] = n / (np.linalg.norm(n) + 1e-18)
    jumps = []
    for e, fs in emap.items():
        if len(fs) == 2: jumps.append((math.degrees(math.acos(max(-1, min(1, float(N[fs[0]] @ N[fs[1]]))))), fs))
    jumps.sort(key=lambda t: -t[0])
    out["max_normal_jump_deg"] = round(jumps[0][0], 1); out["edges_over_60deg"] = sum(1 for j in jumps if j[0] > 60)
    out["edges_over_90deg_folds"] = sum(1 for j in jumps if j[0] > 90)
    out["worst_edges"] = [{"deg": round(j[0], 1), "faces": j[1]} for j in jumps[:4]]
    # inverted: normal opposite to the area-weighted mean normal of its one-ring faces
    inv = 0
    for f in rf:
        nb = {g for e2 in [frozenset((polys[f][i], polys[f][(i + 1) % 3])) for i in range(3)] for g in emap.get(e2, []) if g != f}
        if nb:
            m = sum(N[g] for g in nb); inv += int(float(N[f] @ m) < 0)
    out["inverted_faces"] = inv
    if ref_n is not None:
        rot = [(math.degrees(math.acos(max(-1, min(1, float(N[f] @ ref_n[f]))))), f) for f in rf]; rot.sort(key=lambda t: -t[0])
        out["max_face_rotation_deg_vs_rest"] = round(rot[0][0], 1); out["faces_rotating_over_90deg"] = sum(1 for r in rot if r[0] > 90)
        out["worst_rotating_faces"] = [{"deg": round(r[0], 1), "face": r[1], "classes": [cls.get(v, "ring/outside") for v in polys[r[1]]]} for r in rot[:3]]
    out["min_area_mm2"] = round(out["min_area_mm2"], 4); out["max_aspect"] = round(out["max_aspect"], 1)
    return out, N

q_rest0, N0 = quality(B0); q_rest1, N1 = quality(B1)

# ---------- 4. key carry ----------
KN = {}
for k in keys:
    KN[k] = KO[k].copy(); KN[k][movable] = B1[movable] + (KO[k][movable] - B0[movable])
KN["Basis"] = B1.copy()
KC = {k: v.copy() for k, v in KN.items()}               # carried keys (before the local jaw rebuild) -> checkpoint 01

# ---------- 5. harmonic rebuild of jaw_open + corr_jaw_smile_L on the core (post-removal connectivity) ----------
REPAIR = ["jaw_open", "corr_jaw_smile_L"]
core_l = sorted(v for v in core if used[v])
hm = {}
for k in REPAIR:
    D = KN[k] - B1; D0 = D.copy()
    for _ in range(6000):
        newD = D.copy()
        for v in core_l: newD[v] = D[list(adj[v])].mean(0)
        D = newD
    KN[k] = B1 + D; hm[k] = round(float(np.linalg.norm(D - D0, axis=1)[core_l].max()) * 1000, 3)

def pose(w):
    P = KN["Basis"].copy()
    for k, x in w.items(): P += x * (KN[k] - KN["Basis"])
    return P
tests = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "corner_tests_7f.json")))
qual = {"rest_v5": q_rest0, "rest_corrected": q_rest1}
for nm, w in tests.items():
    q, _ = quality(pose(w), N1); qual[nm] = q

# visibility of moved vertices at rest after the edit (they must stay hidden)
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
tgt = mid + Vector((0.018, -0.030, -0.065))
bm = bmesh.new(); bm.from_mesh(sme)
bm.verts.ensure_lookup_table()
for i, v in enumerate(bm.verts): v.co = Vector(B1[i])
bm.faces.ensure_lookup_table(); bmesh.ops.delete(bm, geom=[bm.faces[i] for i in REMOVE], context="FACES_ONLY")
bm.transform(src.matrix_world); bvh = BVHTree.FromBMesh(bm); bm.free()
Mw = np.array(src.matrix_world); W1 = (np.c_[B1, np.ones(nV)] @ Mw.T)[:, :3]
views = [(0, -0.10, 0), (0.05, -0.09, 0), (0.07, -0.075, 0), (0.10, -0.03, 0), (0.03, -0.10, 0.03)]
newly_visible = []
for v in movable:
    p = Vector(W1[v])
    for off in views:
        c = tgt + Vector(off); d = p - c; L = d.length; d.normalize(); h = bvh.ray_cast(c, d, L + 1e-3)
        if h[0] is not None and (h[0] - p).length < 2e-4: newly_visible.append(v); break

eyes = np.array(mid)
rep = {"faces_removed_slivers": SLIV, "faces_removed_peeled_damaged_lining": peeled, "movable_vertices": len(movable), "twin_groups": len(reps), "tether": TETHER,
       "fixed": {"ring": len(ring), "visible_lip_margin": sum(1 for c in cls.values() if c == "visible_lip_margin"), "crease_chain": "excluded from region"},
       "displacement_mm": {"max": round(float(dm.max()), 3), "mean": round(float(dm.mean()), 3), "rms": round(float(np.sqrt((dm ** 2).mean())), 3)},
       "per_vertex": [{"v": v, "class": cls[v], "disp_mm": round(float(disp[v]), 3), "vec_mm": [round(float(x) * 1000, 3) for x in (B1[v] - B0[v])]} for v in movable],
       "fixed_vertices_max_disp_mm": float(np.delete(disp, movable).max()),
       "moved_vertices_visible_at_rest_after_edit": newly_visible, "harmonic_change_mm": hm, "quality": qual}
print("UNFOLD", json.dumps({k: rep[k] for k in ("faces_removed_peeled_damaged_lining", "movable_vertices", "twin_groups", "displacement_mm", "fixed_vertices_max_disp_mm", "moved_vertices_visible_at_rest_after_edit", "harmonic_change_mm")}))
for nm, q in qual.items():
    print("Q", nm, {k: q.get(k) for k in ("min_area_mm2", "faces_area_below_0_05mm2", "max_aspect", "max_normal_jump_deg", "edges_over_90deg_folds", "inverted_faces", "max_face_rotation_deg_vs_rest", "faces_rotating_over_90deg")}, q.get("worst_rotating_faces", q["worst_edges"])[:2])
json.dump(rep, open(os.path.join(qa, "unfold_report.json"), "w"), indent=1, default=float)
if DRY: sys.exit(0)

# ================= apply to the duplicate (same vertex indices as the source until the topology edit) =================
dst = src.copy(); dst.data = src.data.copy(); dst.name = "GNM_Head_v6g"
for c in src.users_collection: c.objects.link(dst)
src.hide_render = True; src.hide_viewport = True
me = dst.data
for n, vs in (("repair_core_L", core), ("repair_ring_L", ring), ("rest_movable_L", set(movable))):
    g = dst.vertex_groups.get(n) or dst.vertex_groups.new(name=n); g.add(sorted(vs), 1.0, "REPLACE")
for cname in sorted(set(cls.values())):
    g = dst.vertex_groups.new(name="cls_" + cname); g.add(sorted(v for v, c in cls.items() if c == cname), 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "v6g_00_checkpoint_before_edit.blend"), compress=True, copy=True)
def write(Kd):
    for k in keys: me.shape_keys.key_blocks[k].data.foreach_set("co", Kd[k].ravel())
    me.vertices.foreach_set("co", Kd["Basis"].ravel()); me.update()
write(KC)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "v6g_01_rest_corrected.blend"), compress=True, copy=True)
write(KN)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
lay = bm.verts.layers.int.new("src_idx")
for v in bm.verts: v[lay] = v.index
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in REMOVE], context="FACES_ONLY")
wire = [e for e in bm.edges if not e.link_faces]; bmesh.ops.delete(bm, geom=wire, context="EDGES")
loose = [v for v in bm.verts if not v.link_edges]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.verts.ensure_lookup_table(); smap = np.array([v[lay] for v in bm.verts])
bm.to_mesh(me); bm.free(); me.update()
# exactness: every surviving vertex vs the v5 source, per key
movm = np.isin(smap, movable); corem = np.isin(smap, core_l)
def SK(m, k): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[k].data.foreach_get("co", a); return a.reshape(-1, 3)
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
kr = {}
for k in keys:
    New = SK(me, k); Old = KO[k][smap]
    dOld = Old - B0[smap]; dNew = New - SK(me, "Basis")
    kr[k] = {"outside_core_abs_max_mm": round(float(np.abs(New[~corem] - Old[~corem]).max()) * 1000, 6),
             "core_offset_change_max_mm": round(float(np.linalg.norm(dNew[corem] - dOld[corem], axis=1).max()) * 1000, 6) if k != "Basis" else None}
rep["apply"] = {"vertices_before": nV, "vertices_after": len(me.vertices), "faces_after": len(me.polygons), "new_vertices": 0,
                "wire_edges_removed": len(wire), "loose_vertices_removed": len(loose), "non_manifold_edges": nonman, "keys": len(keys) - 1,
                "key_report": kr, "eye_18_max_mm_everywhere": max(max(kr[k]["outside_core_abs_max_mm"], kr[k]["core_offset_change_max_mm"]) for k in EYE),
                "non_repaired_keys_offset_change_in_core_max_mm": max(kr[k]["core_offset_change_max_mm"] for k in keys if k not in REPAIR + ["Basis"]),
                "outside_core_all_keys_max_mm": max(v["outside_core_abs_max_mm"] for v in kr.values())}
print("APPLY", json.dumps({k: v for k, v in rep["apply"].items() if k != "key_report"}))
json.dump(rep, open(os.path.join(qa, "unfold_report.json"), "w"), indent=1, default=float)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "v6g_02_left_reconstructed.blend"), compress=True)
keep = {"GNM_Rig", "GNM_Head_v6g", "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keep)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = dst
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, "v6g_02_left_reconstructed.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

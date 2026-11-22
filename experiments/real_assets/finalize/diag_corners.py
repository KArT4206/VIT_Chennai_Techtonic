"""Corner topology diagnosis on the SOURCE head (before any deletion), using the v5 build's jaw weights.
Run inside build_web_v2.py context? No: standalone - recomputes classification cheaply from a GLB that still has all faces (v4)."""
import sys, json, bpy, numpy as np, bmesh
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]; full_glb, cut_glb, out = args[:3]
def load(p):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=p)
    h = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head")); rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    M = np.array(h.matrix_world); kb = h.data.shape_keys.key_blocks
    def arr(k): a = np.empty(len(h.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    B = arr(kb[0]); J = arr(kb["jaw_open"]) - B
    mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
    mats = [m.name for m in h.data.materials]
    faces = [(tuple(p.vertices), mats[p.material_index]) for p in h.data.polygons]
    bm = bmesh.new(); bm.from_mesh(h.data)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary); bound = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return B, J, mid, faces, nonman, bound
Bf, Jf, mid, Ff, nm_f, bd_f = load(full_glb)
Bc, Jc, _, Fc, nm_c, bd_c = load(cut_glb)
from mathutils.kdtree import KDTree
kd = KDTree(len(Bf)); [kd.insert(Vector(v), i) for i, v in enumerate(Bf)]; kd.balance()
mapc = np.array([kd.find(Vector(v))[1] for v in Bc])
cut_set = {tuple(sorted(mapc[list(f)])) for f, m in Fc}
removed = [(f, m) for f, m in Ff if tuple(sorted(f)) not in cut_set]
rel = Bf - mid
def desc(f):
    P = rel[list(f)] * 1000; s = np.linalg.norm(Jf[list(f)], axis=1) * 1000
    return {"centre_mm": P.mean(0).round(1).tolist(), "x_abs_mm": round(float(np.abs(P[:, 0]).mean()), 1), "jaw_move_min_max_mm": [round(float(s.min()), 1), round(float(s.max()), 1)]}
rem = [desc(f) for f, m in removed]
# faces left in the cut file adjacent to removed faces near corners = flap candidates (isolated islands)
edges_removed = set()
for f, m in removed:
    for i in range(len(f)): edges_removed.add(tuple(sorted((f[i], f[(i + 1) % len(f)]))))
flaps = []
for f, m in Fc:
    fv = mapc[list(f)]; es = [tuple(sorted((fv[i], fv[(i + 1) % len(fv)]))) for i in range(len(fv))]
    shared = sum(e in edges_removed for e in es)
    if shared >= 1 and m == "Skin":
        d = desc(fv); d["edges_bordering_removed"] = shared; d["verts"] = len(fv); flaps.append(d)
res = {"full": {"faces": len(Ff), "non_manifold_edges": nm_f, "boundary_edges": bd_f}, "v5_cut": {"faces": len(Fc), "non_manifold_edges": nm_c, "boundary_edges": bd_c},
       "removed_faces": len(removed), "removed_by_region": {"centre(|x|<20)": sum(r["x_abs_mm"] < 20 for r in rem), "corner(|x|>=20)": sum(r["x_abs_mm"] >= 20 for r in rem)},
       "removed": rem, "faces_bordering_removed": len(flaps), "flap_candidates_corner": [f for f in flaps if f["x_abs_mm"] >= 18]}
json.dump(res, open(out, "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k not in ("removed", "flap_candidates_corner")}))
for f in res["flap_candidates_corner"][:20]: print("FLAP?", f)

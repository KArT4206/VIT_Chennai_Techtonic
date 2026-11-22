"""PRIVATE: Phase 2N.7G step 2 - classify the LEFT repair core vertices (read-only probe on the untouched v5 head).

    blender -b <checkpoint_start.blend> --python classify_left_core.py -- <selection_reference.json> <out.json>

Rebuilds the 2N.7F region exactly (repair_core_L / repair_ring_L), then classifies every core vertex:
  visible_lip_margin  - hit first by a camera ray at rest from any of 5 front/three-quarter/side views (never moved)
  commissure_fold     - vertex of a confirmed sliver face
  corner_tip          - one-ring of the slivers (not itself a sliver vertex)
  inner_upper_lining  - hidden, jaw_open motion < 50% of the local lower-lip motion (follows the upper lip)
  inner_lower_lining  - hidden, follows the jaw
Also lists rest-pose fold pairs (neighbouring faces > 60 deg apart) inside the region.
"""
import json, math, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ref_p, out_p = sys.argv[sys.argv.index("--") + 1:][:2]
ref = json.load(open(ref_p))
FLAP = [7158, 7159, 7160, 7161, 7162, 7212, 7213, 7236]
SLIV = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] == "commissure_sliver"]
CREASE = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] != "commissure_sliver"]
src = bpy.data.objects["GNM_Head"]; me = src.data
polys = [list(p.vertices) for p in me.polygons]; mats = [m.name for m in me.materials]
adj = [set() for _ in range(len(me.vertices))]
for e in me.edges: a, b = e.vertices; adj[a].add(b); adj[b].add(a)
sliv_v = {v for f in SLIV for v in polys[f]}
core = {v for f in FLAP + SLIV for v in polys[f]} | {u for v in sliv_v for u in adj[v]}
crease_v = {v for f in CREASE for v in polys[f]}
core -= crease_v
skin_v = {v for p in me.polygons if mats[p.material_index] == "Skin" for v in p.vertices}
core &= skin_v
ring = {u for v in core for u in adj[v]} - core

def K(n): a = np.empty(len(me.vertices) * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B0 = K("Basis"); J = K("jaw_open") - B0
Mw = np.array(src.matrix_world)
W = (np.c_[B0, np.ones(len(B0))] @ Mw.T)[:, :3]
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
tgt = mid + Vector((0.018, -0.030, -0.065))
# visibility at rest: BVH of the whole head in world space
bm = bmesh.new(); bm.from_mesh(me); bm.transform(src.matrix_world); bvh = BVHTree.FromBMesh(bm); bm.free()
views = [(0, -0.10, 0), (0.05, -0.09, 0), (0.07, -0.075, 0), (0.10, -0.03, 0), (0.03, -0.10, 0.03)]
vis = {}
for v in core:
    p = Vector(W[v]); hits = 0
    for off in views:
        c = tgt + Vector(off); d = (p - c); L = d.length; d.normalize()
        h = bvh.ray_cast(c, d, L + 1e-3)
        if h[0] is not None and (h[0] - p).length < 2e-4: hits += 1
    vis[v] = hits
jm = np.linalg.norm(J, axis=1)
lower_ref = np.percentile(jm[list(ring | core)], 90)
cls = {}
for v in core:
    if vis[v] > 0: c = "visible_lip_margin"
    elif v in sliv_v: c = "commissure_fold"
    elif any(u in sliv_v for u in adj[v]): c = "corner_tip"
    elif jm[v] < 0.5 * lower_ref: c = "inner_upper_lining"
    else: c = "inner_lower_lining"
    cls[v] = c
eyes = np.array(mid)
rows = [{"v": v, "class": cls[v], "visible_views": vis[v], "jaw_mm": round(float(jm[v]) * 1000, 2),
         "rest_rel_eyes_mm": [round(float(x) * 1000, 1) for x in (W[v] - eyes)]} for v in sorted(core)]
# rest folds in region
rf = [i for i, p in enumerate(polys) if any(v in core for v in p)]
def fn(P, vs): n = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); return n / (np.linalg.norm(n) + 1e-18)
N = {f: fn(B0, polys[f]) for f in rf}
emap = {}
for f in rf:
    p = polys[f]
    for i in range(len(p)): emap.setdefault(frozenset((p[i], p[(i + 1) % len(p)])), []).append(f)
folds = []
for e, fs in emap.items():
    if len(fs) == 2:
        a = math.degrees(math.acos(max(-1, min(1, float(N[fs[0]] @ N[fs[1]])))))
        if a > 60: folds.append({"faces": fs, "edge": sorted(e), "deg": round(a, 1), "edge_classes": [cls.get(v, "ring") for v in sorted(e)]})
folds.sort(key=lambda r: -r["deg"])
summary = {}
for c in cls.values(): summary[c] = summary.get(c, 0) + 1
out = {"core": len(core), "ring": len(ring), "class_counts": summary, "lower_ref_jaw_mm": round(float(lower_ref) * 1000, 2),
       "rest_fold_edges_over_60deg": folds, "vertices": rows, "ring_vertices": sorted(ring)}
json.dump(out, open(out_p, "w"), indent=1)
print("CLASS", json.dumps(summary), "folds>60:", len(folds), [f["deg"] for f in folds[:10]], [f["edge_classes"] for f in folds[:6]])

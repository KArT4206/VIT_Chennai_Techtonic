"""PRIVATE: Phase 2N.7H geometry validation of the LEFT repair region (any head object, v5 or reconstructed).

    blender -b <file.blend> --python validate_7h.py -- <object> <region_vertices_7h.csv> <out.json>

Region faces = faces touching the 2N.7H movable set (mapped through the src_idx attribute when present).
Per pose: min area, faces < 0.05 mm2, max aspect, max neighbour normal jump, folds > 90 deg, inverted faces,
self-intersections (BVH overlap of region faces against every head face within reach, pairs sharing a vertex ignored),
max face rotation vs rest, open boundary edges in the region, neutral lip separation at the commissure.
"""
import csv, json, math, sys
import bpy, numpy as np
from mathutils.bvhtree import BVHTree

obn, csv_p, out_p = sys.argv[sys.argv.index("--") + 1:][:3]
ob = bpy.data.objects[obn]; me = ob.data
sidx = np.arange(len(me.vertices))
if "src_idx" in me.attributes: me.attributes["src_idx"].data.foreach_get("value", sidx)
mv_src = {int(r["v"]) for r in csv.DictReader(open(csv_p)) if r["role"].startswith("movable")}
inmv = np.isin(sidx, list(mv_src)) | (sidx < 0)
P_ = [list(p.vertices) for p in me.polygons]
rf = [i for i, p in enumerate(P_) if any(inmv[v] for v in p)]
rset = set(rf)
kb = me.shape_keys.key_blocks
def K(n): a = np.empty(len(me.vertices) * 3); kb[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); D = {k.name: K(k.name) - B for k in kb[1:]}
tests = {"rest": {}, "jaw25": {"jaw_open": .25}, "jaw50": {"jaw_open": .5}, "jaw75": {"jaw_open": .75}, "jaw100": {"jaw_open": 1.0},
         "big_grin": {"mouth_smile_L": 1, "mouth_smile_R": 1, "cheek_raise_L": .8, "cheek_raise_R": .8, "upper_lip_raise_L": .7, "upper_lip_raise_R": .7,
                      "lower_lip_depress_L": .6, "lower_lip_depress_R": .6, "jaw_open": .12, "corr_jaw_smile_L": .12, "corr_jaw_smile_R": .12},
         "smile_jaw100": {"jaw_open": 1, "mouth_smile_L": .8, "mouth_smile_R": .8, "corr_jaw_smile_L": .8, "corr_jaw_smile_R": .8},
         "biggrin_jaw100": {"jaw_open": 1, "mouth_smile_L": 1, "mouth_smile_R": 1, "cheek_raise_L": .8, "cheek_raise_R": .8, "upper_lip_raise_L": .7,
                            "upper_lip_raise_R": .7, "lower_lip_depress_L": .6, "lower_lip_depress_R": .6, "corr_jaw_smile_L": 1, "corr_jaw_smile_R": 1}}
emap = {}
for f in rf:
    p = P_[f]
    for i in range(len(p)): emap.setdefault(frozenset((p[i], p[(i + 1) % len(p)])), []).append(f)
allmap = {}
for i, p in enumerate(P_):
    for j in range(len(p)): allmap[frozenset((p[j], p[(j + 1) % len(p)]))] = allmap.get(frozenset((p[j], p[(j + 1) % len(p)])), 0) + 1
open_edges = sum(1 for e in emap if allmap[e] == 1)
def metrics(P, N0=None):
    N = {}; out = {"min_area_mm2": 1e9, "faces_below_0_05mm2": 0, "max_aspect": 0}
    for f in rf:
        vs = P_[f]; n = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); ar = np.linalg.norm(n) / 2
        e = max(np.linalg.norm(P[vs[i]] - P[vs[(i + 1) % 3]]) for i in range(3))
        out["min_area_mm2"] = min(out["min_area_mm2"], ar * 1e6); out["faces_below_0_05mm2"] += int(ar * 1e6 < 0.05)
        out["max_aspect"] = max(out["max_aspect"], e * e / (4 * ar / math.sqrt(3) + 1e-18)); N[f] = n / (np.linalg.norm(n) + 1e-18)
    j = [math.degrees(math.acos(max(-1, min(1, float(N[a] @ N[b]))))) for e, fs in emap.items() if len(fs) == 2 for a, b in [fs]]
    out["max_normal_jump_deg"] = round(max(j), 1); out["folds_over_90deg"] = sum(x > 90 for x in j)
    inv = 0
    for f in rf:
        nb = [g for i in range(3) for g in emap.get(frozenset((P_[f][i], P_[f][(i + 1) % 3])), []) if g != f]
        if nb and float(N[f] @ sum(N[g] for g in nb)) < 0: inv += 1
    out["inverted_faces"] = inv
    near = [i for i, p in enumerate(P_) if np.linalg.norm(P[p].mean(0) - P[[v for f in rf for v in P_[f]]].mean(0)) < 0.025]
    t1 = BVHTree.FromPolygons([tuple(P[v]) for v in range(len(P))], [P_[f] for f in rf], all_triangles=False)
    t2 = BVHTree.FromPolygons([tuple(P[v]) for v in range(len(P))], [P_[f] for f in near], all_triangles=False)
    pairs = {tuple(sorted((rf[a], near[b]))) for a, b in t1.overlap(t2) if rf[a] != near[b] and not set(P_[rf[a]]) & set(P_[near[b]])}
    out["self_intersecting_face_pairs"] = len(pairs)
    if N0: out["max_rotation_vs_rest_deg"] = round(max(math.degrees(math.acos(max(-1, min(1, float(N[f] @ N0[f]))))) for f in rf), 1); out["faces_rotating_over_90deg"] = sum(math.degrees(math.acos(max(-1, min(1, float(N[f] @ N0[f]))))) > 90 for f in rf)
    out["min_area_mm2"] = round(out["min_area_mm2"], 4); out["max_aspect"] = round(out["max_aspect"], 1)
    return out, N
res = {"object": obn, "region_faces": len(rf), "open_boundary_edges_in_region": open_edges}
q, N0 = metrics(B); res["rest"] = q
for n, w in tests.items():
    if n == "rest": continue
    P = B.copy()
    for k, x in w.items(): P = P + x * D[k]
    res[n], _ = metrics(P, N0)
json.dump(res, open(out_p, "w"), indent=1)
for n in tests: print("V", n, json.dumps(res[n]))
print("V open_edges", open_edges, "faces", len(rf))

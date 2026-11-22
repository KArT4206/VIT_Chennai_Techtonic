"""Read-only: characterise every head face visible over the LEFT mouth corner at jaw 50 % and 100 % (v5)."""
import sys, json, bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
h = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head")); rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
me = h.data; M = np.array(h.matrix_world); kb = me.shape_keys.key_blocks
def arr(k): a = np.empty(len(me.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
B = arr(kb[0]); J = arr(kb["jaw_open"]) - B
mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
mats = [m.name for m in me.materials]; polys = [list(p.vertices) for p in me.polygons]
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
def tri(P, vs): a = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); n = np.linalg.norm(a); return n / 2, a / (n + 1e-15)
def aspect(P, vs):
    e = [np.linalg.norm(P[vs[i]] - P[vs[(i + 1) % 3]]) for i in range(3)]; a, _ = tri(P, vs)
    return max(e) ** 2 / (4 * a / np.sqrt(3) + 1e-18)   # 1 = equilateral, large = sliver
rel = B - mid
res = {}
for jaw in (0.5, 1.0):
    P = B + jaw * J; bvh = BVHTree.FromPolygons([Vector(v) for v in P], polys)
    hit = {}
    for x in np.arange(0.010, 0.030, 0.0004):
        for z in np.arange(-0.056, -0.080, -0.0004):
            hd = bvh.ray_cast(Vector((mid[0] + x, mid[1] - 0.3, mid[2] + z)), Vector((0, 1, 0)), 0.6)
            if hd[0] is not None and mats[me.polygons[hd[2]].material_index] == "Skin": hit[hd[2]] = hit.get(hd[2], 0) + 1
    rows = []
    for fi, n in hit.items():
        vs = polys[fi]; a0, n0 = tri(B, vs); a1, n1 = tri(P, vs)
        ang = float(np.degrees(np.arccos(np.clip(n0 @ n1, -1, 1))))
        rows.append({"face": fi, "rays": n, "verts": vs, "rest_area_mm2": round(a0 * 1e6, 3), "open_area_mm2": round(a1 * 1e6, 3), "normal_rotation_deg": round(ang, 1),
                     "aspect_rest": round(float(aspect(B, vs)), 1), "aspect_open": round(float(aspect(P, vs)), 1),
                     "jaw_mm": [round(float(np.linalg.norm(J[v])) * 1000, 1) for v in vs], "rest_rel_eyes_mm": [[round(float(c) * 1000, 1) for c in rel[v]] for v in vs],
                     "neighbours": sorted({f.index for e in bm.faces[fi].edges for f in e.link_faces if f.index != fi})})
    # flap candidates: big visible faces that rotate strongly or are slivers when open
    rows.sort(key=lambda r: -r["open_area_mm2"])
    res[f"jaw{int(jaw*100)}"] = rows
cands = [r for r in res["jaw100"] if r["open_area_mm2"] > 3.0 and (r["normal_rotation_deg"] > 45 or r["aspect_open"] > 6)]
json.dump({"all": res, "flap_candidates_jaw100": cands}, open(out, "w"), indent=1)
for r in cands[:12]: print("CAND", {k: r[k] for k in ("face", "rays", "rest_area_mm2", "open_area_mm2", "normal_rotation_deg", "aspect_rest", "aspect_open", "jaw_mm", "rest_rel_eyes_mm", "neighbours")})
print("N_VISIBLE", len(res["jaw50"]), len(res["jaw100"]), "CANDS", len(cands))

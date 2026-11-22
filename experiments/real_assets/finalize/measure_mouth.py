"""Measure mouth recipes on a PRIVATE GLB: lip tearing, teeth through lips, chin strain, eye-key identity."""
import sys, json, bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb, recipes, out, ref = sys.argv[sys.argv.index("--") + 1:][:4]
R = json.load(open(recipes))
def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=path)
    h = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head")); rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    M = np.array(h.matrix_world); kb = h.data.shape_keys.key_blocks
    def arr(k): a = np.empty(len(h.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    B = arr(kb[0]); K = {k.name: arr(k) - B for k in kb[1:]}
    mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
    return h, B, K, mid
refh, refB, refK, _ = load(ref)
h, B, K, mid = load(glb)
mats = [m.name for m in h.data.materials]
mi = np.array([p.material_index for p in h.data.polygons])
skin_polys = [list(p.vertices) for p in h.data.polygons if mats[p.material_index] == "Skin"]
is_skin = np.zeros(len(B), bool); [is_skin.__setitem__(p, True) for p in skin_polys]
tooth = np.zeros(len(B), bool)
for p in h.data.polygons:
    if mats[p.material_index].startswith("Teeth"): tooth[list(p.vertices)] = True
rel = B - mid; X, Z = rel[:, 0], rel[:, 2]; F = -rel[:, 1]
E = np.array([e.vertices[:] for e in h.data.edges]); E = E[is_skin[E[:, 0]] & is_skin[E[:, 1]]]; L0 = np.linalg.norm(B[E[:, 0]] - B[E[:, 1]], axis=1)
mouth = is_skin & (np.abs(X) < 0.040) & (Z < -0.045) & (Z > -0.090) & (F > 0.015)
chin = is_skin & (np.abs(X) < 0.030) & (Z < -0.085) & (Z > -0.115) & (F > 0.010)
eyes = is_skin & (Z > -0.025) & (Z < 0.035) & (np.abs(X) < 0.06) & (F > 0.0)
res = {"eye_keys_identical_to_ref_mm": {}}
from mathutils.kdtree import KDTree
kd = KDTree(len(refB))
for i, v in enumerate(refB): kd.insert(Vector(v), i)
kd.balance()
idx = np.array([kd.find(Vector(v))[1] for v in B]); dmatch = np.array([kd.find(Vector(v))[2] for v in B])
res["vertex_match"] = {"verts": len(B), "ref_verts": len(refB), "max_rest_mismatch_mm": round(float(dmatch.max()) * 1000, 5)}
for k in refK:
    if k in K: res["eye_keys_identical_to_ref_mm"][k] = round(float(np.abs(K[k] - refK[k][idx]).max()) * 1000, 4)
for name, w in R.items():
    D = sum((K[k] * v for k, v in w.items() if k in K), np.zeros_like(B)); P = B + D
    em = mouth[E[:, 0]] & mouth[E[:, 1]]; ec = chin[E[:, 0]] & chin[E[:, 1]]
    rm = np.linalg.norm(P[E[em, 0]] - P[E[em, 1]], axis=1) / L0[em]; rc = np.linalg.norm(P[E[ec, 0]] - P[E[ec, 1]], axis=1) / L0[ec]
    # teeth through lips: along front view rays, a tooth is hit first and the next skin surface behind it
    # is an outward-facing lip surface within 6 mm -> the tooth sits in front of the lip (poke-through)
    bvh = BVHTree.FromPolygons([Vector(v) for v in P], skin_polys)
    tpolys = [list(p.vertices) for p in h.data.polygons if mats[p.material_index].startswith("Teeth")]
    tbvh = BVHTree.FromPolygons([Vector(v) for v in P], tpolys)
    poke = 0; worst = 0.0; rays = 0
    for xv in np.arange(-0.030, 0.0301, 0.001):
        for zv in np.arange(-0.050, -0.095, -0.001):
            o = Vector((mid[0] + xv, mid[1] - 0.3, mid[2] + zv)); d = Vector((0, 1, 0)); rays += 1
            th = tbvh.ray_cast(o, d, 0.6); sh = bvh.ray_cast(o, d, 0.6)
            if th[0] is None or (sh[0] is not None and sh[3] < th[3]): continue
            s2 = bvh.ray_cast(th[0] + d * 1e-5, d, 0.006)
            if s2[0] is not None and s2[1].y < -0.3:   # skin behind the tooth faces the camera = outer lip
                poke += 1; worst = max(worst, s2[3])
    m = np.linalg.norm(D, axis=1)
    res[name] = {"weights": w, "mouth_max_mm": round(float(m[mouth].max()) * 1000, 2) if mouth.any() else 0,
                 "lip_edge_stretch_max": round(float(rm.max()), 2), "lip_edges_over_2x": int((rm > 2).sum()), "lip_edges_over_3x": int((rm > 3).sum()), "lip_edge_min_ratio": round(float(rm.min()), 2),
                 "chin_edge_ratio_range": [round(float(rc.min()), 2), round(float(rc.max()), 2)],
                 "teeth_poke_rays": poke, "rays": rays, "teeth_poke_max_mm": round(worst * 1000, 2),
                 "eye_region_max_mm": round(float(m[eyes].max()) * 1000, 2),
                 "L_vs_R_mouth_mm": [round(float(m[mouth & (X > 0.004)].max()) * 1000, 2), round(float(m[mouth & (X < -0.004)].max()) * 1000, 2)]}
json.dump(res, open(out, "w"), indent=1); print("MEASURED", len(R))

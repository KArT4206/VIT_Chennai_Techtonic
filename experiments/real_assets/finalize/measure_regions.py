"""Displacement of named facial landmarks (front-projected skin points) for selected keys, v1 vs v2."""
import sys, json, math, bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head"))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = np.array(head.matrix_world); kb = head.data.shape_keys.key_blocks
def arr(k):
    a = np.empty(len(head.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
B = arr(kb[0]); mats = [m.name for m in head.data.materials]
polys = [list(p.vertices) for p in head.data.polygons if mats[p.material_index].startswith("Skin")]
bvh = BVHTree.FromPolygons([Vector(v) for v in B], polys)
le = np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local); re_ = np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local); mid = (le + re_) / 2
LM = {"inner_brow_L": (0.016, 0.021), "inner_brow_R": (-0.016, 0.021), "outer_brow_L": (0.040, 0.020), "outer_brow_R": (-0.040, 0.020),
      "glabella": (0.0, 0.018), "lower_lid_L": (le[0] - mid[0], -0.0075), "cheek_L": (0.034, -0.024), "nasolabial_L": (0.020, -0.040), "nose_side_L": (0.012, -0.022)}
res = {}
for k in [x.name for x in kb[1:]]:
    D = arr(kb[k]) - B; r = {}
    for n, (x, z) in LM.items():
        h = bvh.ray_cast(Vector((mid[0] + x, -1, mid[2] + z)), Vector((0, 1, 0)), 3)
        if h[0] is None: continue
        vids = polys[h[2]]; w = poly_3d_calc([Vector(B[v]) for v in vids], h[0])
        d = sum(D[v] * wi for v, wi in zip(vids, w)) * 1000
        r[n] = {"mm": round(float(np.linalg.norm(d)), 2), "x": round(float(d[0]), 2), "fwd": round(float(-d[1]), 2), "up": round(float(d[2]), 2)}
    res[k] = r
json.dump(res, open(out, "w"), indent=1)

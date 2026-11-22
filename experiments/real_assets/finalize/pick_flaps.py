"""Ray-pick the visible geometry at the mouth corners of a GLB at a jaw pose; report each hit polygon."""
import sys, json, bpy, numpy as np, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb, out, jaw = sys.argv[sys.argv.index("--") + 1:][:3]; jaw = float(jaw)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
h = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head")); rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = np.array(h.matrix_world); kb = h.data.shape_keys.key_blocks
def arr(k): a = np.empty(len(h.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
B = arr(kb[0]); J = arr(kb["jaw_open"]) - B; P = B + jaw * J
mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
mats = [m.name for m in h.data.materials]; polys = [list(p.vertices) for p in h.data.polygons]; pm = [mats[p.material_index] for p in h.data.polygons]
bm = bmesh.new(); bm.from_mesh(h.data); bm.faces.ensure_lookup_table()
bvh = BVHTree.FromPolygons([Vector(v) for v in P], polys)
hits = {}
for sx in (1, -1):
    for x in np.arange(0.014, 0.030, 0.0005):
        for z in np.arange(-0.056, -0.080, -0.0005):
            o = Vector((mid[0] + sx * x, mid[1] - 0.3, mid[2] + z)); hd = bvh.ray_cast(o, Vector((0, 1, 0)), 0.6)
            if hd[0] is None: continue
            fi = hd[2]; vs = polys[fi]
            A0 = np.linalg.norm(np.cross(B[vs[1]] - B[vs[0]], B[vs[2]] - B[vs[0]])); A1 = np.linalg.norm(np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]))
            ratio = A1 / max(A0, 1e-12)
            if ratio < 4: continue
            f = bm.faces[fi]
            bnd = sum(1 for e in f.edges if e.is_boundary)
            jm = np.linalg.norm(J[vs], axis=1) * 1000
            hits[fi] = {"side": "L" if sx > 0 else "R", "material": pm[fi], "area_stretch": round(float(ratio), 1), "rest_centre_rel_eyes_mm": ((B[vs].mean(0) - mid) * 1000).round(1).tolist(),
                        "jaw_move_per_vertex_mm": jm.round(1).tolist(), "boundary_edges": bnd, "neighbour_faces": [len(e.link_faces) for e in f.edges]}
res = {"glb": glb.split("/")[-1], "jaw": jaw, "stretched_visible_faces": len(hits), "by_side": {s: sum(1 for v in hits.values() if v["side"] == s) for s in "LR"}, "faces": hits}
json.dump(res, open(out, "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "faces"}))
for k, v in list(hits.items())[:12]: print(k, v)

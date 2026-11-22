"""Read-only: mouth/teeth/tongue/jaw inventory of a PRIVATE web GLB."""
import sys, json, bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head"))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
print("BONES", [b.name for b in rig.data.bones])
M = np.array(head.matrix_world); a = np.empty(len(head.data.vertices) * 3); head.data.vertices.foreach_get("co", a); P = a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
mats = [m.name for m in head.data.materials]
le = np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local); re = np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local); mid = (le + re) / 2
print("EYE_MID", (mid * 1000).round(1).tolist())
for i, m in enumerate(mats):
    ids = sorted({v for p in head.data.polygons if p.material_index == i for v in p.vertices})
    Q = (P[ids] - mid) * 1000
    print("MAT", m, len(ids), "x", Q[:, 0].min().round(1), Q[:, 0].max().round(1), "z", Q[:, 2].min().round(1), Q[:, 2].max().round(1), "fwd", (-Q[:, 1]).min().round(1), (-Q[:, 1]).max().round(1))
    if m.startswith("Teeth"):
        z = Q[:, 2]; h = np.histogram(z, bins=20); print("  teeth z hist", h[0].tolist(), h[1].round(1).tolist())
        # connected components
        n = len(head.data.vertices); par = {v: v for v in ids}
        def f(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        for e in head.data.edges:
            u, w = e.vertices
            if u in par and w in par:
                ru, rw = f(u), f(w)
                if ru != rw: par[ru] = rw
        comps = {}
        for v in ids: comps.setdefault(f(v), []).append(v)
        for c, vs in sorted(comps.items(), key=lambda kv: -len(kv[1]))[:6]:
            q = (P[vs] - mid) * 1000; print("  comp", len(vs), "z", q[:, 2].min().round(1), q[:, 2].max().round(1), "x", q[:, 0].min().round(1), q[:, 0].max().round(1))
skin = [list(p.vertices) for p in head.data.polygons if mats[p.material_index] == "Skin"]
bvh = BVHTree.FromPolygons([Vector(v) for v in P], skin)
# front profile down the midline and lip opening scan
print("PROFILE (z mm below eyes: fwd mm)")
for z in range(-40, -115, -3):
    h = bvh.ray_cast(Vector((mid[0], mid[1] - 1, mid[2] + z / 1000)), Vector((0, 1, 0)), 3)
    print(f"  z{z}: {'-' if h[0] is None else round((mid[1]-h[0][1])*1000,1)} dist {'' if h[0] is None else round(h[3]*1000-1000,1)}", end="")
print()
# lip opening per x: is there a hole between lips (ray passes skin)?
for x in range(-30, 31, 5):
    hits = []
    for z in np.arange(-0.060, -0.085, -0.0005):
        h = bvh.ray_cast(Vector((mid[0] + x / 1000, mid[1] - 1, mid[2] + z)), Vector((0, 1, 0)), 3)
        hits.append(h[0] is None or (mid[1] - h[0][1]) < 0.0)
    print("x", x, "gap rows", int(sum(hits)))
kb = head.data.shape_keys.key_blocks; print("KEYS", [k.name for k in kb])

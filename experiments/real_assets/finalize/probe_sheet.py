import sys, bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
h = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head")); rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = np.array(h.matrix_world); kb = h.data.shape_keys.key_blocks
def arr(k): a = np.empty(len(h.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
B = arr(kb[0]); D = arr(kb["jaw_open"]) - B; P = B + D
mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
mats = [m.name for m in h.data.materials]
polys = [list(p.vertices) for p in h.data.polygons]; pm = [mats[p.material_index] for p in h.data.polygons]
bvh = BVHTree.FromPolygons([Vector(v) for v in P], polys)
for x in (0.0, 0.008):
  for z in np.arange(-0.066, -0.090, -0.002):
    o = Vector((mid[0] + x, mid[1] - 0.3, mid[2] + z)); hit = bvh.ray_cast(o, Vector((0, 1, 0)), 0.6)
    if hit[0] is None: print(x, round(z*1000), "miss"); continue
    vs = polys[hit[2]]; r = (B[vs] - mid).mean(0) * 1000; d = np.linalg.norm(D[vs], axis=1).mean() * 1000
    print(f"x{x*1000:.0f} z{z*1000:.0f}: {pm[hit[2]]:10s} rest(x,fwd,z)=({r[0]:.1f},{-r[1]:.1f},{r[2]:.1f}) move {d:.1f}mm hitdepth {(hit[0][1]-mid[1])*-1000:.1f}")

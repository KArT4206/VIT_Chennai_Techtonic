import bpy, sys, os, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, '..'); import gnm_engine
G = gnm_engine.GNMRig('../build/gnm_keys.npz'); ob = G.ob
for idb in (G.rig, ob.data.shape_keys):
    if idb.animation_data: idb.animation_data.action = None
lash = bpy.data.objects['GNM_Lashes']
grp = np.array([a.value for a in lash.data.attributes['lash_group'].data]).repeat(5)
def pts():
    dg = bpy.context.evaluated_depsgraph_get(); return np.array([v.vector for v in lash.evaluated_get(dg).data.position_data])
def bvh():
    dg = bpy.context.evaluated_depsgraph_get(); em = ob.evaluated_get(dg).to_mesh()
    verts = [ob.matrix_world @ v.co for v in em.vertices]; polys = [list(p.vertices) for p in em.polygons if p.material_index in (2, 4)]
    ob.evaluated_get(dg).to_mesh_clear(); return BVHTree.FromPolygons(verts, polys)
def inside(b, p):
    n, o, d = 0, Vector(p), Vector((0.3, 0.2, 0.93)).normalized()
    while True:
        h = b.ray_cast(o, d)
        if h[0] is None: return n % 2 == 1
        n += 1; o = h[0] + d * 1e-6
for name, w, (yaw, pitch) in (('open', {}, (0, 0)), ('blink', dict(blink_L=1, blink_R=1), (0, 0)), ('half', dict(blink_L=.5, blink_R=.5), (0, 0)),
                              ('up', dict(lid_follow_L=1.2, lid_follow_R=1.2), (0, 12)), ('down', dict(lid_follow_L=-.7, lid_follow_R=-.7), (0, -7))):
    G.set_keys(**w); t = G.target(yaw, pitch)
    for s in ('left', 'right'): G.set_eye_quat(s, G.eye_rotation(s, t))
    bpy.context.view_layer.update(); b = bvh(); P = pts()
    ins = [i for i, p in enumerate(P) if inside(b, p)]
    depth = [b.find_nearest(Vector(P[i]))[3] * 1000 for i in ins]
    print('POSE', name, 'inside', len(ins), 'groups', sorted(set(grp[ins].tolist())), 'point index in strand', sorted(set((np.array(ins) % 5).tolist())), 'max depth mm', round(max(depth), 3) if depth else 0)

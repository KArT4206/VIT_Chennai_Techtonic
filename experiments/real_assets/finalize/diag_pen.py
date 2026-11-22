import sys, math, bpy, numpy as np
glb = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
O = {o.name: o for o in bpy.data.objects}
head = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("GNM_Head")); la = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("Lashes"))
def W(o):
    M=np.array(o.matrix_world); a=np.empty(len(o.data.vertices)*3); o.data.vertices.foreach_get("co",a); return a.reshape(-1,3)@M[:3,:3].T+M[:3,3]
HP=W(head); LP=W(la); mats=[m.name for m in head.data.materials]
def vids(p):
    s=set()
    for q in head.data.polygons:
        if mats[q.material_index].startswith(p): s.update(q.vertices)
    return np.array(sorted(s))
def sphere(P):
    keep=P
    for _ in range(4):
        A=np.c_[2*keep,np.ones(len(keep))]; b=(keep**2).sum(1); x=np.linalg.lstsq(A,b,rcond=None)[0]; c=x[:3]; r=math.sqrt(x[3]+c@c)
        res=np.abs(np.linalg.norm(keep-c,axis=1)-r); keep=keep[res<=np.percentile(res,80)]
    return c,r
for s in "LR":
    c,r=sphere(HP[vids("Eye_"+s)]); d=np.linalg.norm(LP-c,axis=1); ins=d<r-0.0003
    if ins.any():
        P=(LP[ins]-c)*1000; print(s, "inside", int(ins.sum()), "rel x range", P[:,0].min().round(1), P[:,0].max().round(1), "z", P[:,2].min().round(1), P[:,2].max().round(1), "fwd", (-P[:,1]).min().round(1), (-P[:,1]).max().round(1), "depth max mm", round(float((r-d[ins]).max()*1000),2))
    else: print(s, "inside 0")

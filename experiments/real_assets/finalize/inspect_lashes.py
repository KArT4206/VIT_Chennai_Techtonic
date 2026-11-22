"""Read-only inspection of the lash strands vs the GNM eyelid margins on the PRIVATE web GLB."""
import sys, math, json
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
O = {o.name: o for o in bpy.data.objects}
head = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("GNM_Head"))
lashes = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("Lashes"))
mats = [m.name for m in head.data.materials]
def W(o): 
    M = np.array(o.matrix_world); a = np.empty(len(o.data.vertices)*3); o.data.vertices.foreach_get("co", a); a = a.reshape(-1,3)
    return a @ M[:3,:3].T + M[:3,3]
HP = W(head); LP = W(lashes)
def vids(prefix):
    s=set()
    for p in head.data.polygons:
        if mats[p.material_index].startswith(prefix): s.update(p.vertices)
    return np.array(sorted(s))
def sphere(P):
    keep=P
    for _ in range(4):
        A=np.c_[2*keep,np.ones(len(keep))]; b=(keep**2).sum(1); x=np.linalg.lstsq(A,b,rcond=None)[0]; c=x[:3]; r=math.sqrt(x[3]+c@c)
        res=np.abs(np.linalg.norm(keep-c,axis=1)-r); keep=keep[res<=np.percentile(res,80)]
    return c,r
eye = {s: sphere(HP[vids("Eye_"+s)]) for s in "LR"}
print("EYES", {s:(np.round(eye[s][0]*1000,1).tolist(), round(eye[s][1]*1000,2)) for s in eye})
# Blender frame after import: Z up, face toward -Y
skin = vids("Skin")
# islands
n=len(lashes.data.vertices); par=list(range(n))
def f(a):
    while par[a]!=a: par[a]=par[par[a]]; a=par[a]
    return a
for e in lashes.data.edges:
    a,b=f(e.vertices[0]),f(e.vertices[1])
    if a!=b: par[a]=b
isl=np.array([f(i) for i in range(n)])
polys=[list(p.vertices) for p in head.data.polygons if mats[p.material_index].startswith("Skin")]
bvh=BVHTree.FromPolygons([Vector(v) for v in HP], polys)
d=np.array([bvh.find_nearest(Vector(p))[3] for p in LP])
groups={}
for i,g in enumerate(isl): groups.setdefault(g,[]).append(i)
print("ISLANDS", len(groups), "verts/island median", int(np.median([len(v) for v in groups.values()])))
rows=[]
for g,ix in groups.items():
    ix=np.array(ix); r=ix[np.argmin(d[ix])]; t=ix[np.argmax(np.linalg.norm(LP[ix]-LP[r],axis=1))]
    side="L" if LP[r,0]>0 else "R"; c,rad=eye[side]
    root=LP[r]-c; tip=LP[t]-c
    rows.append(dict(side=side, root=root*1000, tip=tip*1000, gap=d[r]*1000, len=np.linalg.norm(LP[t]-LP[r])*1000))
R=np.array([x["root"] for x in rows]); T=np.array([x["tip"] for x in rows]); G=np.array([x["gap"] for x in rows]); Ln=np.array([x["len"] for x in rows])
print("root z (mm rel eye centre) hist:", np.histogram(R[:,2],bins=[-20,-10,-6,-3,0,3,6,10,20])[0].tolist())
print("tip-root dz: up", int((T[:,2]-R[:,2]>0).sum()), "down", int((T[:,2]-R[:,2]<0).sum()))
print("root forward (-y) mm: p10/50/90", np.percentile(-R[:,1],[10,50,90]).round(1).tolist())
print("root gap to skin mm p50/p90/max", np.percentile(G,[50,90,100]).round(2).tolist(), "strand length p50", round(float(np.median(Ln)),1))
# lid margin: skin verts within 1 mm of the eyeball surface and in front of the centre
for s in "L":
    c,rad=eye[s]; P=HP[skin]-c; dist=np.linalg.norm(P,axis=1)-rad
    m=(np.abs(dist)<0.0012)&(-P[:,1]>0.35*rad)&((P[:,0]>0)==(s=="L"))
    M=P[m]*1000
    ang=np.degrees(np.arctan2(M[:,2],M[:,0]*(1 if s=="L" else -1)))
    up=M[M[:,2]>0]; lo=M[M[:,2]<=0]
    print("MARGIN",s,"verts",int(m.sum()),"upper z range",up[:,2].min().round(1),up[:,2].max().round(1),"lower z range",lo[:,2].min().round(1),lo[:,2].max().round(1), "x range", M[:,0].min().round(1), M[:,0].max().round(1))
    # upper lid max z at x near 0 and lower lid min z
    nearc=np.abs(M[:,0])<3
    print("  at x~0: upper margin z", M[nearc&(M[:,2]>0),2].min().round(1) if (nearc&(M[:,2]>0)).any() else None, " lower margin z", M[nearc&(M[:,2]<=0),2].max().round(1) if (nearc&(M[:,2]<=0)).any() else None)
    Ls=np.array([x["root"] for x in rows if x["side"]==s]); 
    nc=np.abs(Ls[:,0])<3
    print("  lash roots near x~0 z:", np.sort(Ls[nc,2]).round(1).tolist()[:40])

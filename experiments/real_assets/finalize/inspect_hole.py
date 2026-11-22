"""Read-only: what hole does removing one side's commissure slivers leave? (topology only, nothing saved)"""
import sys, json, bpy, bmesh, numpy as np
side = sys.argv[sys.argv.index("--") + 1]
src = bpy.data.objects["GNM_Head"]; me = src.data; kb = me.shape_keys.key_blocks
def co(k): a = np.empty(len(me.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3)
R0 = co(kb["Basis"]); RJ = co(kb["jaw_open"])
ref = json.load(open(sys.argv[sys.argv.index("--") + 2]))
faces = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == side and d["cluster"] == "commissure_sliver"]
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
sel = [bm.faces[i] for i in faces]
fe = {e for f in sel for e in f.edges}
fv = {v for f in sel for v in f.verts}
pre_boundary = {e.index for e in fe if e.is_boundary}
bmesh.ops.delete(bm, geom=sel, context="FACES_ONLY")
bnd = [e for e in fe if e.is_valid and e.is_boundary]
loose = [v.index for v in fv if v.is_valid and not v.link_faces]
# order into loops
adj = {}
for e in bnd:
    a, b = e.verts; adj.setdefault(a.index, []).append(b.index); adj.setdefault(b.index, []).append(a.index)
seen = set(); loops = []
for s in adj:
    if s in seen: continue
    loop = [s]; seen.add(s); prev = None; cur = s
    while True:
        nxt = [n for n in adj[cur] if n != prev and n not in seen]
        if not nxt: break
        prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
    loops.append(loop)
jm = np.linalg.norm(RJ - R0, axis=1) * 1000
info = {"side": side, "faces": faces, "verts_in_faces": len(fv), "pre_existing_boundary_edges_on_slivers": len(pre_boundary), "hole_boundary_edges": len(bnd),
        "loops": [{"n": len(l), "jaw_mm": [round(float(jm[i]), 1) for i in l], "branching_verts": sum(1 for i in l if len(adj[i]) != 2),
                   "rest_perimeter_mm": round(float(sum(np.linalg.norm(R0[l[i]] - R0[l[(i + 1) % len(l)]]) for i in range(len(l)))) * 1000, 2),
                   "open_perimeter_mm": round(float(sum(np.linalg.norm(RJ[l[i]] - RJ[l[(i + 1) % len(l)]]) for i in range(len(l)))) * 1000, 2)} for l in loops],
        "loose_after_delete": loose,
        "coincident_pairs_in_region": int(sum(1 for i in fv for j in fv if i.index < j.index and (R0[i.index] - R0[j.index]).__abs__().max() < 1e-7))}
print("HOLE", json.dumps(info))

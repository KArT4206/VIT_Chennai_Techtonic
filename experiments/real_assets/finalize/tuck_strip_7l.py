"""PRIVATE: Phase 2N.7L - LEFT medial tuck strip (2N.7K -> 2N.7L). Topology only; no existing vertex or key is touched.

    blender -b <v6k_left_medial_rerouted.blend> --python tuck_strip_7l.py -- <out_dir> <qa_dir>

The 2N.7K opening is a lens bounded by
  OUTER (upper-lip seam, fixed, incl. 4693): 4636, 4693, 4697, 4657, 4655, 4651, 4648
  INNER (patch + healthy lining, fixed):     4636, r1_0, r2_0, 5825, 5795, 4641      (4641 coincides with 4640, the seam end)
A middle row of NMID new vertices (mid-way, pushed BACK_MM behind the lip, into the mouth) is zipped to both chains.
Motion: explicit correspondence, offset = 0.5*outer(s) + 0.5*inner(s) for every key (both chains are upper-lip / upper
lining, so no lower-lip motion enters). UVs: every loop of every new face gets the UV of the nearest point on the healthy
lining faces around the INNER chain (barycentric), so the strip carries lining texture.
"""
import json, math, os, sys
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:2]
NMID = int(os.environ.get("NMID", "3")); BACKMM = float(os.environ.get("BACK_MM", "1.5")) / 1000; TAG = os.environ.get("TAG", "v6l")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6k"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); D = {k: K(k) - B for k in keys if k != "Basis"}
cnt = {}
for p in me.polygons:
    for e in p.edge_keys: cnt[e] = cnt.get(e, 0) + 1
bnb = {}
for e, c in cnt.items():
    if c == 1: bnb.setdefault(e[0], []).append(e[1]); bnb.setdefault(e[1], []).append(e[0])
OUT = [s2i[v] for v in (4636, 4693, 4697, 4657, 4655, 4651, 4648)]
# inner chain: from 4636 along the open patch edge to 5825, then 5795, 4641
a0 = s2i[4636]; inner = [a0]; prev = None
nxt = [x for x in bnb[a0] if sidx[x] < 0]
cur = nxt[0]
while sidx[cur] != 5825 and len(inner) < 12:
    inner.append(cur); nn = [x for x in bnb[cur] if x != inner[-2]]; cur = nn[0]
INN = inner + [s2i[5825], s2i[5795], s2i[4641]]
for i in range(len(OUT) - 1): assert OUT[i + 1] in bnb.get(OUT[i], []), ("outer not open", i)
for i in range(len(INN) - 1): assert INN[i + 1] in bnb.get(INN[i], []), ("inner not open", i)
M3 = np.array(ob.matrix_world)[:3, :3]; back = np.linalg.inv(M3) @ np.array([0, 1.0, 0]); back /= np.linalg.norm(back)
rig = bpy.data.objects["GNM_Rig"]
mid = np.array((rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2)
Wp = lambda v: (np.array(ob.matrix_world) @ np.r_[B[v], 1])[:3] - mid
pre = {"outer_chain": [{"v": int(sidx[v]), "pos_mm": [round(float(x) * 1000, 2) for x in Wp(v)], "jaw_world_mm": [round(float(x) * 1000, 2) for x in M3 @ D["jaw_open"][v]]} for v in OUT],
       "inner_chain": [{"v": int(sidx[v]) if sidx[v] >= 0 else f"patch{v}", "pos_mm": [round(float(x) * 1000, 2) for x in Wp(v)], "jaw_world_mm": [round(float(x) * 1000, 2) for x in M3 @ D["jaw_open"][v]]} for v in INN],
       "note": "4641 coincides with seam end 4640; 4693 is a fixed attachment (not moved, keys untouched)"}
def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B[ch[i + 1]] - B[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
LO, LI = arclen(OUT), arclen(INN)
mids = []
for m in range(NMID):
    s = (m + 1) / (NMID + 1)
    pos = 0.5 * sample(OUT, s, B) + 0.5 * sample(INN, s, B) + BACKMM * back
    offs = {k: 0.5 * sample(OUT, s, D[k]) + 0.5 * sample(INN, s, D[k]) for k in D}
    mids.append({"s": s, "pos": pos, "offs": offs})
LM = [0.0] + [m["s"] for m in mids] + [1.0]
# zipper helper: chain A (params LA) vs chain Bc (params LB) -> triangles
def zipper(A, LA, Bc, LBc):
    out = []; i = j = 0
    while i < len(A) - 1 or j < len(Bc) - 1:
        if j >= len(Bc) - 1 or (i < len(A) - 1 and LA[i + 1] <= LBc[j + 1]): out.append([A[i], A[i + 1], Bc[j]]); i += 1
        else: out.append([A[i], Bc[j + 1], Bc[j]]); j += 1
    return out
MIDC = [("E", OUT[0])] + [("N", i) for i in range(NMID)] + [("E", INN[-1])]   # mid chain shares both ends
Oc = [("E", v) for v in OUT] + [("E", INN[-1])]; LOc = list(LO * 0.97) + [1.0]  # outer closes on 4641 at the far end
Ic = [("E", v) for v in INN]
faces = zipper(Oc, LOc, MIDC, LM) + zipper(MIDC, LM, Ic, list(LI))
faces = [f for f in faces if len({t for t in f}) == 3]
# orientation: the existing lip face on edge 4636-4693 must be traversed opposite by our face
dir_ex = None
for p in me.polygons:
    vs = list(p.vertices)
    if OUT[0] in vs and OUT[1] in vs:
        a, b = vs.index(OUT[0]), vs.index(OUT[1]); dir_ex = (b - a) % len(vs) == 1  # existing uses 4636->4693
ours = None
for f in faces:
    vs = [t[1] if t[0] == "E" else None for t in f]
    if OUT[0] in vs and OUT[1] in vs:
        a, b = vs.index(OUT[0]), vs.index(OUT[1]); ours = (b - a) % 3 == 1
if ours == dir_ex: faces = [f[::-1] for f in faces]
# UV source: healthy lining faces touching the inner chain's existing vertices
lin_faces = [p for p in me.polygons if any(v in (s2i[5825], s2i[5795], s2i[4641]) for v in p.vertices) and len(p.vertices) == 3]
UVL = me.uv_layers.active
tris = [(list(p.vertices), [tuple(UVL.data[l].uv) for l in p.loop_indices]) for p in lin_faces]
grow = set(v for t in tris for v in t[0])
for p in me.polygons:                       # one more ring of lining for a robust projection
    if any(v in grow for v in p.vertices) and len(p.vertices) == 3 and sidx[list(p.vertices)].min() >= 0:
        tris.append((list(p.vertices), [tuple(UVL.data[l].uv) for l in p.loop_indices]))
bvh = BVHTree.FromPolygons([tuple(c) for c in B], [t[0] for t in tris], all_triangles=True)
def lining_uv(pos):
    loc, n, fi, d = bvh.find_nearest(Vector(pos)); vs, uv = tris[fi]
    u = barycentric_transform(loc, *[Vector(B[v]) for v in vs], *[Vector((*x, 0)) for x in uv]); return (u.x, u.y), d
# ---- build ----
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
lay = bm.verts.layers.int.get("src_idx"); sk = {k: bm.verts.layers.shape[k] for k in keys}; uvL = bm.loops.layers.uv.active
skin = [m.name for m in me.materials].index("Skin")
nv = []
for m in mids:
    v = bm.verts.new(Vector(m["pos"])); v[lay] = -3
    for k in keys: v[sk[k]] = Vector(m["pos"]) + (Vector(m["offs"][k]) if k != "Basis" else Vector())
    nv.append(v)
bm.verts.ensure_lookup_table()
built = 0; loops = 0; uvdist = []
for f in faces:
    vs = [bm.verts[t[1]] if t[0] == "E" else nv[t[1]] for t in f]
    nf = bm.faces.new(vs); nf.material_index = skin; nf.smooth = True; built += 1
    for lp in nf.loops:
        uv, d = lining_uv(lp.vert.co); lp[uvL].uv = Vector(uv); loops += 1; uvdist.append(d)
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.to_mesh(me); bm.free(); me.update()
# ---- regression vs 2N.7K ----
nV2 = len(me.vertices)
def K2(n): a = np.empty(nV2 * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
per = {k: round(float(np.abs(K2(k)[:nV] - (B + (D[k] if k != "Basis" else 0))).max()) * 1000, 6) for k in keys}
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
uvs_ok = all(not (abs(l[me.uv_layers.active.name].uv.x) + 0 == 0) for l in [])  # placeholder (checked below)
zero_uv = 0
for p in me.polygons[len(me.polygons) - built:]:
    for li in p.loop_indices:
        u = me.uv_layers.active.data[li].uv
        zero_uv += int(u.x == 0 and u.y == 0)
rep = {"tag": TAG, "pre_edit": pre, "new_vertices": NMID, "new_faces": built, "new_uv_loops": loops, "uv_loops_at_0_0": zero_uv,
       "uv_projection_max_dist_mm": round(max(uvdist) * 1000, 3), "back_mm": BACKMM * 1000, "non_manifold_edges": nonman,
       "existing_vertices_all_keys_max_mm": max(per.values()), "eye_18_max_mm": max(per[k] for k in EYE), "per_key_existing_max_mm": per,
       "vertices_after": nV2, "faces_after": len(me.polygons)}
json.dump(rep, open(os.path.join(qa, f"tuck_report_{TAG}.json"), "w"), indent=1)
print("TUCK", json.dumps({k: v for k, v in rep.items() if k not in ("pre_edit", "per_key_existing_max_mm")}))
g = ob.vertex_groups.new(name="tuck_strip_L"); g.add(list(range(nV, nV2)) + OUT + INN, 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_tuck_strip.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_tuck_strip.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

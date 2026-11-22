"""PRIVATE: Phase 2N.7K - reroute the medial end of the LEFT upper lining strip (2N.7J -> 2N.7K).

    blender -b <v6j_left_upper_lip_corrected.blend> --python reroute_upper_patch_7k.py -- <topology_v6i.json> <out_dir> <qa_dir>

Only the UPPER half of the 2N.7I/7J patch is rebuilt (its new vertices and faces). Kept exactly: every existing vertex
(rest and all 35 keys, incl. the frozen 2N.7J jaw correction), the lower half, and the two shared corner-column vertices.
  upper FRONT = 4636 ... 4524 (fixed visible lip edge, 2N.7J offsets)
  upper BACK  = 5825 ... 4621 (was 4641, 5795, 5825, ...): 4641 lies 4.5 mm IN FRONT of the lip edge on the open mouth
                seam, 5825 is 6.8 mm behind / 11.1 mm above it on healthy lining (verified in anchor_check_7k.json).
  rows at T1 / T2 of the depth (default 0.45 / 0.75, deeper than 1/3 / 2/3) so the strip stays behind the lip.
  edges 4641-5795-5825 become an open edge of the existing lining (no twisted closing faces) unless CLOSE=1.
Motion: explicit correspondence per key, offset = (1-t)*front(s) + t*back(s) (upper chains only) - identical rule to 7I/7J.
UVs: new loops take the healthy back-lining UV at the same arclength (lining texture, no skin-coloured slivers).
"""
import json, math, os, sys
import bpy, bmesh, numpy as np
from mathutils import Vector

topo_p, out_dir, qa = sys.argv[sys.argv.index("--") + 1:][:3]
T1 = float(os.environ.get("T1", "0.45")); T2 = float(os.environ.get("T2", "0.75")); TAG = os.environ.get("TAG", "v6k")
INWARD = float(os.environ.get("INWARD_MM", "2.0")) / 1000; CLOSE = os.environ.get("CLOSE", "0") == "1"
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
T = json.load(open(topo_p))
FRONT, BACK = T["front_chain"], T["back_chain"]; FC, BC = FRONT.index(4524), BACK.index(4621)
src = bpy.data.objects["GNM_Head_v6j"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
newv = [i for i in range(nV) if sidx[i] < 0]
info = dict(zip(newv, T["new_vertices"]))
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); D = {k: K(k) - B for k in keys}
# corner-column vertices are the first-created upper r1/r2 at the corner, shared with the lower half
upper_new = [v for v in newv if info[v]["half"] == "upper"]
lower_faces_verts = set()
for p in me.polygons:
    if any(v in newv and info[v]["half"] == "lower" for v in p.vertices): lower_faces_verts |= set(p.vertices)
corner_keep = [v for v in upper_new if v in lower_faces_verts]
drop = [v for v in upper_new if v not in corner_keep]
Fi = [s2i[v] for v in FRONT[:FC + 1]]; Bi = [s2i[v] for v in BACK[2:BC + 1]]
cr1 = [v for v in corner_keep if info[v]["row"] == 1][0]; cr2 = [v for v in corner_keep if info[v]["row"] == 2][0]
UVL = me.uv_layers.active; vuv = {}
for p in me.polygons:
    if any(v in newv for v in p.vertices): continue
    for li in p.loop_indices:
        v = me.loops[li].vertex_index
        if v in Bi or v in Fi or v in (s2i[4641], s2i[5795]): vuv.setdefault(v, tuple(UVL.data[li].uv))
def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B[ch[i + 1]] - B[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
M3 = np.array(ob.matrix_world)[:3, :3]; inward = np.linalg.inv(M3) @ np.array([0, 1.0, 0]); inward /= np.linalg.norm(inward)
LF, LB = arclen(Fi), arclen(Bi)
pts = []
def mk(t, s):
    pos = (1 - t) * sample(Fi, s, B) + t * sample(Bi, s, B) + INWARD * math.sin(math.pi * t) * inward
    offs = {k: (1 - t) * sample(Fi, s, D[k]) + t * sample(Bi, s, D[k]) for k in keys if k != "Basis"}
    uv = sample(Bi, s, {v: np.array(vuv[v]) for v in Bi}) if False else None
    L = LB; j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(Bi) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    uv = (1 - w) * np.array(vuv[Bi[j]]) + w * np.array(vuv[Bi[j + 1]])
    pts.append({"pos": pos, "offs": offs, "uv": uv, "t": t, "s": float(s)}); return ("N", len(pts) - 1)
r1 = [mk(T1, s) for s in LF[:-1]] + [("E", cr1)]
r2 = [mk(T2, s) for s in LB[:-1]] + [("E", cr2)]
F = [("E", v) for v in Fi]; Bk = [("E", v) for v in Bi]
faces = []
for i in range(len(F) - 1): faces.append([F[i], F[i + 1], r1[i + 1], r1[i]])
for j in range(len(Bk) - 1): faces.append([r2[j], r2[j + 1], Bk[j + 1], Bk[j]])
i = j = 0
while i < len(r1) - 1 or j < len(r2) - 1:
    if j >= len(r2) - 1 or (i < len(r1) - 1 and LF[i + 1] <= LB[j + 1]): faces.append([r1[i], r1[i + 1], r2[j]]); i += 1
    else: faces.append([r1[i], r2[j + 1], r2[j]]); j += 1
if CLOSE:
    faces += [[r2[0], Bk[0], ("E", s2i[5795])], [r1[0], r2[0], ("E", s2i[5795])], [r1[0], ("E", s2i[5795]), ("E", s2i[4641])], [F[0], r1[0], ("E", s2i[4641])]]
# orientation: match the 2N.7J upper faces (the old row0-row1 quads used F[i]->F[i+1] the same way as the strip rule)
old_dir = None
for p in me.polygons:
    vs = list(p.vertices)
    if any(v in drop for v in vs) and Fi[1] in vs and Fi[2] in vs:
        a, b = vs.index(Fi[1]), vs.index(Fi[2]); old_dir = (b - a) % len(vs) == 1; break
flip = (old_dir is False)
if flip: faces = [f[::-1] for f in faces]
# ---- edit ----
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
lay = bm.verts.layers.int.get("src_idx"); sk = {k: bm.verts.layers.shape[k] for k in keys}; uvL = bm.loops.layers.uv.active
skin = [m.name for m in me.materials].index("Skin")
nv = []
for p in pts:
    v = bm.verts.new(Vector(p["pos"])); v[lay] = -2
    for k in keys: v[sk[k]] = Vector(p["pos"]) + (Vector(p["offs"][k]) if k != "Basis" else Vector())
    nv.append(v)
bm.verts.ensure_lookup_table()
def V(t): return bm.verts[t[1]] if t[0] == "E" else nv[t[1]]
dropset = set(drop)
old_faces = [f for f in bm.faces if any(v.index in dropset for v in f.verts)]
n_removed_faces = len(old_faces)
bmesh.ops.delete(bm, geom=old_faces, context="FACES_ONLY")
built = 0
for f in faces:
    vs = [V(t) for t in f]
    try:
        nf = bm.faces.new(vs); nf.material_index = skin; nf.smooth = True; built += 1
        for lp in nf.loops:
            if lp.vert in nv: lp[uvL].uv = Vector(pts[nv.index(lp.vert)]["uv"])
            else:
                i0 = lp.vert.index
                lp[uvL].uv = Vector(vuv[i0]) if i0 in vuv else lp[uvL].uv
    except ValueError: pass
bm.verts.ensure_lookup_table()
dead = [bm.verts[i] for i in drop]
bmesh.ops.delete(bm, geom=[v for v in dead if v.is_valid], context="VERTS")
wire = [e for e in bm.edges if not e.link_faces]; bmesh.ops.delete(bm, geom=wire, context="EDGES")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.verts.ensure_lookup_table(); smap = np.array([v[lay] for v in bm.verts])
bm.to_mesh(me); bm.free(); me.update()
# ---- regression vs 2N.7J (existing vertices by src index; lower-half and corner new vertices by position order) ----
nV2 = len(me.vertices)
def K2(n): a = np.empty(nV2 * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
ex2 = np.where(smap >= 0)[0]; ex1 = np.array([s2i[int(s)] for s in smap[ex2]])
kept_new1 = [v for v in newv if v not in dropset]; kept_new2 = list(np.where(smap == -1)[0])
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
per = {}
for k in keys:
    a = K2(k); b = B + (D[k] if k != "Basis" else 0)
    per[k] = {"existing_max_mm": round(float(np.abs(a[ex2] - b[ex1]).max()) * 1000, 6),
              "kept_patch_max_mm": round(float(np.abs(a[kept_new2] - b[kept_new1]).max()) * 1000, 6) if len(kept_new1) == len(kept_new2) else None}
rep = {"tag": TAG, "T1": T1, "T2": T2, "inward_mm": INWARD * 1000, "closing_faces": CLOSE, "flip": flip,
       "removed_patch_vertices": len(drop), "removed_patch_faces": n_removed_faces, "new_vertices": len(pts), "new_faces": built, "quads": sum(len(f) == 4 for f in faces),
       "tris": sum(len(f) == 3 for f in faces), "kept_corner_vertices": len(corner_keep), "vertices_after": nV2, "faces_after": len(me.polygons), "non_manifold_edges": nonman,
       "existing_vertices_all_keys_max_mm": max(v["existing_max_mm"] for v in per.values()), "kept_lower_patch_all_keys_max_mm": max((v["kept_patch_max_mm"] or 0) for v in per.values()),
       "eye_18_existing_max_mm": max(per[k]["existing_max_mm"] for k in EYE), "upper_back_chain": BACK[2:BC + 1], "per_key": per}
json.dump(rep, open(os.path.join(qa, f"reroute_report_{TAG}.json"), "w"), indent=1)
print("REROUTE", json.dumps({k: v for k, v in rep.items() if k not in ("per_key", "upper_back_chain")}))
g = ob.vertex_groups.new(name="rerouted_upper_patch_L"); g.add([int(i) for i in np.where(smap == -2)[0]], 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_medial_rerouted.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_medial_rerouted.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

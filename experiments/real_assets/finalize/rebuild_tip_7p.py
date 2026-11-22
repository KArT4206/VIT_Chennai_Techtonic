"""PRIVATE: Phase 2N.7P - LEFT corner-tip topology rebuild (2N.7O -> 2N.7P). Existing vertices/keys untouched.

    blender -b <v6o_left_patch_fixes.blend> --python rebuild_tip_7p.py -- <out_dir> <qa_dir> [--proposal]

Defective segment: the upper strip between the strip column at 4689 and the corner column 4524-c1-c2-4621, whose
first-row vertices collapsed onto the lip edge (faces with aspect up to 178 and inverted faces). It is removed and
rebuilt as a structured grid inside the four fixed sides
  FRONT  (lip edge, fixed)   4689 4688 4589 4556 4525 4524        (6)
  CORNER (2N.7I column)      4524 c1 c2 4621                      (kept)
  BACK   (healthy lining)    5839 5755 5811 5783 4621             (5)
  MEDIAL (strip column)      4689 m1 m2 5839                      (kept)
Rows: R0=FRONT, R1=[m1, 4 new, c1], R2=[m2, 3 new, c2], R3=BACK. Quads R0-R1 (5), R2-R3 (4), R1-R2 4 quads + 1 tri.
New vertex rest positions, all 35 key offsets and UVs = Coons (bilinearly blended) interpolation of the four sides at
the same (u, v): a boundary-conforming blend, so upper-lip, lining and corner motions meet continuously and nothing
is pushed arbitrarily.
"""
import json, os, sys
import bpy, bmesh, numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]; out_dir, qa = argv[:2]; PROPOSAL = "--proposal" in argv; TAG = os.environ.get("TAG", "v6p")
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
src = bpy.data.objects["GNM_Head_v6o"]
ob = src.copy(); ob.data = src.data.copy(); ob.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(ob)
src.hide_render = True; src.hide_viewport = True
me = ob.data; nV = len(me.vertices); keys = [k.name for k in me.shape_keys.key_blocks]
sidx = np.empty(nV, dtype=np.int32); me.attributes["src_idx"].data.foreach_get("value", sidx)
s2i = {int(s): i for i, s in enumerate(sidx) if s >= 0}
def K(n): a = np.empty(nV * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); KO = {k: K(k) for k in keys}
adj = [set() for _ in range(nV)]
for e in me.edges: a, b = e.vertices; adj[a].add(b); adj[b].add(a)
new = lambda i: sidx[i] < 0
F = [s2i[v] for v in (4689, 4688, 4589, 4556, 4525, 4524)]
BK = [s2i[v] for v in (5839, 5755, 5811, 5783, 4621)]
c1 = [u for u in adj[s2i[4524]] if new(u)][0]
c2 = [u for u in adj[s2i[4621]] if new(u) and u in adj[c1]][0]
m1 = [u for u in adj[s2i[4689]] if new(u)][0]
m2 = [u for u in adj[s2i[5839]] if new(u) and u in adj[m1]][0]
MED, COR = [F[0], m1, m2, BK[0]], [F[-1], c1, c2, BK[-1]]
# faces to remove: patch faces strictly inside the loop (all their vertices in the region, at least one interior vertex)
loop = set(F + BK + [m1, m2, c1, c2])
interior = set()
for v in F[1:-1] + BK[1:-1]:
    interior |= {u for u in adj[v] if new(u) and u not in loop}
grow = True
while grow:
    grow = False
    for v in list(interior):
        for u in adj[v]:
            if new(u) and u not in loop and u not in interior: interior.add(u); grow = True
remove_faces = [p.index for p in me.polygons if any(v in interior for v in p.vertices)]
UVL = me.uv_layers.active
vuv = {}
for p in me.polygons:
    if p.index in remove_faces: continue
    for li in p.loop_indices:
        v = me.loops[li].vertex_index
        if v in loop and new(v) or (v in loop and any(new(u) for u in p.vertices)): vuv.setdefault(v, np.array(UVL.data[li].uv))
for p in me.polygons:                                 # fallback: lining UV from the removed (old patch) faces
    if p.index not in remove_faces: continue
    for li in p.loop_indices:
        v = me.loops[li].vertex_index
        if v in loop: vuv.setdefault(v, np.array(UVL.data[li].uv))
def curve(ch, arr):
    L = np.r_[0, np.cumsum([np.linalg.norm(B[ch[i + 1]] - B[ch[i]]) for i in range(len(ch) - 1)])]; L /= L[-1]
    def f(t):
        j = int(np.clip(np.searchsorted(L, t) - 1, 0, len(ch) - 2)); w = (t - L[j]) / max(L[j + 1] - L[j], 1e-12)
        return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
    return f, L
def coons(arr, u, v):
    f0, _ = curve(F, arr); f1, _ = curve(BK, arr); g0, _ = curve(MED, arr); g1, _ = curve(COR, arr)
    P00, P10, P01, P11 = arr[F[0]], arr[F[-1]], arr[BK[0]], arr[BK[-1]]
    return ((1 - v) * f0(u) + v * f1(u) + (1 - u) * g0(v) + u * g1(v)
            - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))
_, LF = curve(F, B); _, LB = curve(BK, B); _, LM = curve(MED, B); _, LC = curve(COR, B)
v1 = 0.5 * (LM[1] + LC[1]); v2 = 0.5 * (LM[2] + LC[2])
uvarr = {v: vuv.get(v, np.zeros(2)) for v in loop}
pts = []
def mk(u, v):
    pos = coons(B, u, v)
    offs = {k: coons(KO[k] - B, u, v) for k in keys if k != "Basis"}
    uvA = np.zeros((nV, 2)); [uvA.__setitem__(i, uvarr[i]) for i in loop]
    pts.append({"u": float(u), "v": float(v), "pos": pos, "offs": offs, "uv": coons(uvA, u, v)}); return ("N", len(pts) - 1)
R0 = [("E", v) for v in F]; R3 = [("E", v) for v in BK]
R1 = [("E", m1)] + [mk(u, v1) for u in LF[1:-1]] + [("E", c1)]
u2 = [0.5 * (LB[j] + LF[min(j, len(LF) - 1)]) * 0 + LB[j] for j in range(1, len(LB) - 1)]
R2 = [("E", m2)] + [mk(u, v2) for u in u2] + [("E", c2)]
U1 = [0] + list(LF[1:-1]) + [1]; U2 = [0] + u2 + [1]
faces = [[R0[i], R0[i + 1], R1[i + 1], R1[i]] for i in range(len(R0) - 1)]
faces += [[R2[j], R2[j + 1], R3[j + 1], R3[j]] for j in range(len(R3) - 1)]
i = j = 0; mixed = []
while i < len(R1) - 1 or j < len(R2) - 1:            # quad where both advance, triangle where only one can
    if i < len(R1) - 1 and j < len(R2) - 1 and abs(U1[i + 1] - U2[j + 1]) < 0.5 * min(U1[i + 1] - U1[i], U2[j + 1] - U2[j]) + 1e-9:
        mixed.append([R1[i], R1[i + 1], R2[j + 1], R2[j]]); i += 1; j += 1
    elif j >= len(R2) - 1 or (i < len(R1) - 1 and U1[i + 1] < U2[j + 1]):
        mixed.append([R1[i], R1[i + 1], R2[j]]); i += 1
    else:
        mixed.append([R1[i], R2[j + 1], R2[j]]); j += 1
faces += mixed
# orientation: opposite to the existing lip face on edge 4689->4688
dir_ex = None
for p in me.polygons:
    vs = list(p.vertices)
    if p.index in remove_faces or any(new(x) for x in vs): continue
    if F[0] in vs and F[1] in vs: a, b = vs.index(F[0]), vs.index(F[1]); dir_ex = (b - a) % len(vs) == 1
if dir_ex: faces = [f[::-1] for f in faces]       # our R0 quad uses F0->F1; flip if the lip face does too
plan = {"removed_faces": remove_faces, "removed_vertices": sorted(int(v) for v in interior), "front": [int(sidx[v]) for v in F], "back": [int(sidx[v]) for v in BK],
        "medial_side": [int(x) for x in MED], "corner_side": [int(x) for x in COR], "new_vertices": [{"u": round(p["u"], 3), "v": round(p["v"], 3),
        "pos_local_mm": [round(float(x) * 1000, 3) for x in p["pos"]], "jaw_open_mm": [round(float(x) * 1000, 3) for x in p["offs"]["jaw_open"]]} for p in pts],
        "quads": sum(len(f) == 4 for f in faces), "tris": sum(len(f) == 3 for f in faces)}
json.dump(plan, open(os.path.join(qa, f"tip_plan_{TAG}.json"), "w"), indent=1)
print("PLAN", json.dumps({k: (len(v) if isinstance(v, list) and k in ("removed_faces", "removed_vertices", "new_vertices") else v) for k, v in plan.items()}))
if PROPOSAL:
    bm = bmesh.new(); vm = {}
    def V(t):
        if t not in vm: vm[t] = bm.verts.new(Vector(B[t[1]]) if t[0] == "E" else Vector(pts[t[1]]["pos"]))
        return vm[t]
    for f in faces: bm.faces.new([V(t) for t in f])
    m2 = bpy.data.meshes.new("PROPOSAL_tip"); bm.to_mesh(m2); bm.free()
    p2 = bpy.data.objects.new("PROPOSAL_tip", m2); p2.matrix_world = ob.matrix_world.copy(); bpy.context.scene.collection.objects.link(p2)
    w = p2.modifiers.new("W", "WIREFRAME"); w.thickness = 0.00006; w.use_replace = True
    mat = bpy.data.materials.new("prop"); mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (1, 0.9, 0, 1); e.inputs[1].default_value = 3
    nt.links.new(e.outputs[0], o.inputs[0]); m2.materials.append(mat)
    g = ob.vertex_groups.new(name="tip_remove"); g.add(sorted(interior), 1.0, "REPLACE")
    g = ob.vertex_groups.new(name="tip_boundary"); g.add(sorted(loop), 1.0, "REPLACE")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(qa, f"{TAG}_proposal_scene.blend"), compress=True, copy=True)
    print("PROPOSAL_SAVED"); sys.exit(0)
# ---- build ----
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
lay = bm.verts.layers.int.get("src_idx"); sk = {k: bm.verts.layers.shape[k] for k in keys}; uvL = bm.loops.layers.uv.active
skin = [m.name for m in me.materials].index("Skin")
nv = []
for p in pts:
    v = bm.verts.new(Vector(p["pos"])); v[lay] = -4
    for k in keys: v[sk[k]] = Vector(p["pos"]) + (Vector(p["offs"][k]) if k != "Basis" else Vector())
    nv.append(v)
bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in remove_faces], context="FACES_ONLY")
bm.verts.ensure_lookup_table()
ptuv = {("N", i): p["uv"] for i, p in enumerate(pts)}
built = 0; loops = 0; zero = 0
for f in faces:
    vs = [bm.verts[t[1]] if t[0] == "E" else nv[t[1]] for t in f]
    nf = bm.faces.new(vs); nf.material_index = skin; nf.smooth = True; built += 1
    for lp, t in zip(nf.loops, f):
        uv = ptuv[t] if t[0] == "N" else uvarr[t[1]]
        lp[uvL].uv = Vector(uv); loops += 1; zero += int(abs(uv[0]) + abs(uv[1]) == 0)
dead = [bm.verts[i] for i in sorted(interior)]
bmesh.ops.delete(bm, geom=[v for v in dead if v.is_valid and not v.link_faces], context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.verts.ensure_lookup_table(); keepmap = np.array([v[lay] for v in bm.verts])
bm.to_mesh(me); bm.free(); me.update()
nV2 = len(me.vertices)
def K2(n): a = np.empty(nV2 * 3); me.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
ex = np.where(keepmap >= 0)[0]; ex_old = np.array([s2i[int(s)] for s in keepmap[ex]])
per = {k: round(float(np.abs(K2(k)[ex] - KO[k][ex_old]).max()) * 1000, 6) for k in keys}
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
rep = dict(plan, built_faces=built, new_uv_loops=loops, uv_loops_zero=zero, non_manifold_edges=nonman, vertices_after=nV2, faces_after=len(me.polygons),
           existing_vertices_all_keys_max_mm=max(per.values()), eye_18_max_mm=max(per[k] for k in EYE))
json.dump(rep, open(os.path.join(qa, f"tip_report_{TAG}.json"), "w"), indent=1)
print("BUILD", json.dumps({k: v for k, v in rep.items() if k in ("built_faces", "new_uv_loops", "uv_loops_zero", "non_manifold_edges", "vertices_after", "faces_after",
                                                                   "existing_vertices_all_keys_max_mm", "eye_18_max_mm", "quads", "tris")}))
g = ob.vertex_groups.new(name="tip_rebuilt_L"); g.add([int(i) for i in np.where(keepmap == -4)[0]], 1.0, "REPLACE")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_left_corner_tip.blend"), compress=True)
keepo = {"GNM_Rig", ob.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_left_corner_tip.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

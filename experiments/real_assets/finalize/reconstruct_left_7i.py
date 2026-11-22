"""PRIVATE: Phase 2N.7I - hand-designed LEFT commissure lining strip, built fresh from untouched v5.

    blender -b <v6_recon_00_checkpoint_start.blend> --python reconstruct_left_7i.py -- <region_vertices_7h.csv> <out_dir> <qa_dir> [--proposal-only]

Design (from the 2N.7H 97-vertex region, rim analysis on v5):
  * every face touching the 97 movable hidden-lining vertices is removed (all 33 defect faces, slivers, tip faces and the
    damaged lining around them). Visible lip / skin faces are never touched; no existing vertex is moved.
  * the removed area is bounded by two fixed chains:
      FRONT = the inner edge of the visible lips, upper lip -> commissure (4524) -> lower lip      (20 vertices)
      BACK  = healthy lining deep in the mouth, upper -> its corner turning point (4621) -> lower  (31 vertices)
  * a new lining strip is built between them: per half (upper / lower) row0 = FRONT, row1 = new (one per FRONT vertex,
    1/3 of the way back), row2 = new (one per BACK vertex, 2/3 of the way back), row3 = BACK; quads row0-row1 and
    row2-row3, an arclength zipper row1-row2. The two halves share the corner column FRONT[4524] - BACK[4621], so the
    corner is a deliberate fold behind the commissure; nothing spans the mouth opening (the opening lies between the
    upper and lower FRONT halves, which the strip never connects directly).
  * explicit correspondence for motion: a new vertex at depth t between FRONT point f(s) and BACK point b(s) gets, for
    every one of the 35 keys, offset = (1-t)*offset(f) + t*offset(b), with f/b interpolated along their own chain
    half. Upper strip -> upper chains only, lower strip -> lower chains only, corner column blends both.
  * UVs: new loops get the same interpolation of the chain vertices' UVs. Material: Skin.
"""
import csv, json, math, os, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
csv_p, out_dir, qa = argv[:3]; PROPOSAL = "--proposal-only" in argv
TAG = os.environ.get("TAG", "v6i"); BULGE = float(os.environ.get("BULGE_MM", "0")) / 1000
os.makedirs(out_dir, exist_ok=True); os.makedirs(qa, exist_ok=True)
FRONT = [4636, 4629, 4691, 4690, 4689, 4688, 4589, 4556, 4525, 4524, 4554, 5176, 4534, 4560, 4605, 4722, 4717, 4721, 4678, 4627]
BACK = [4641, 5795, 5825, 5771, 5857, 5845, 5843, 5841, 5839, 5755, 5811, 5783, 4621, 5782, 5808, 5751, 5833, 5834, 5837, 5840, 5842,
        5758, 5760, 5762, 5774, 5772, 5770, 5768, 5766, 5822, 5793]
FC, BC = FRONT.index(4524), BACK.index(4621)
rows = {int(r["v"]): r for r in csv.DictReader(open(csv_p))}
mv = {v for v, r in rows.items() if r["role"].startswith("movable")}
src = bpy.data.objects["GNM_Head"]; sme = src.data; nV = len(sme.vertices)
keys = [k.name for k in sme.shape_keys.key_blocks]
def K(m, n): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B0 = K(sme, "Basis"); KD = {k: K(sme, k) - B0 for k in keys}
uvl = sme.uv_layers.active; vuv = {}
dead = {p.index for p in sme.polygons if any(v in mv for v in p.vertices)}
for p in sme.polygons:
    if p.index in dead: continue
    for li in p.loop_indices:
        v = sme.loops[li].vertex_index
        if v in FRONT or v in BACK: vuv.setdefault(v, tuple(uvl.data[li].uv))
assert all(v not in mv for v in FRONT + BACK)
# UVs come from the ORIGINAL (removed) lining surface: the nearest point on the removed faces at rest, barycentric UV.
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
_tris = []
for p in sme.polygons:
    if p.index in dead:
        vs = list(p.vertices); ls = list(p.loop_indices)
        _tris.append((vs, [tuple(uvl.data[l].uv) for l in ls]))
_bvh = BVHTree.FromPolygons([tuple(c) for c in B0], [t[0] for t in _tris], all_triangles=True)
def lining_uv(pos):
    loc, nrm, fi, d = _bvh.find_nearest(Vector(pos)); vs, uvs = _tris[fi]
    a, b, c = [Vector(B0[v]) for v in vs]
    u = barycentric_transform(loc, a, b, c, Vector((*uvs[0], 0)), Vector((*uvs[1], 0)), Vector((*uvs[2], 0)))
    return np.array([u.x, u.y])
for v in FRONT + BACK:                                  # chain vertices: lining-side UV (from a removed face)
    for p in sme.polygons:
        if p.index in dead and v in p.vertices:
            vuv[v] = tuple(uvl.data[list(p.loop_indices)[list(p.vertices).index(v)]].uv); break

def arclen(ch):
    d = [0.0] + [float(np.linalg.norm(B0[ch[i + 1]] - B0[ch[i]])) for i in range(len(ch) - 1)]
    c = np.cumsum(d); return c / c[-1]
def sample(ch, s, arr):            # value of a per-vertex array along the chain at normalised arclength s
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * arr[ch[j]] + w * arr[ch[j + 1]]
def sample_uv(ch, s):
    L = arclen(ch); j = int(np.clip(np.searchsorted(L, s) - 1, 0, len(ch) - 2)); w = (s - L[j]) / max(L[j + 1] - L[j], 1e-12)
    return (1 - w) * np.array(vuv[ch[j]]) + w * np.array(vuv[ch[j + 1]])
halves = {"upper": (FRONT[:FC + 1], BACK[:BC + 1]), "lower": (FRONT[FC:], BACK[BC:])}
# outward (away from the mouth opening, toward the cheek) bulge direction: local +x for the left side
bul = np.array(src.matrix_world.inverted().to_3x3() @ Vector((1, 0, 0))); bul /= np.linalg.norm(bul)
new_pts = []            # dicts: pos, offsets{k}, uv, half, row, t, s
def mkpt(half, row, t, s, F, Bk):
    pf = sample(F, s, B0); pb = sample(Bk, s, B0)
    pos = (1 - t) * pf + t * pb + BULGE * math.sin(math.pi * t) * bul
    offs = {k: (1 - t) * sample(F, s, KD[k]) + t * sample(Bk, s, KD[k]) for k in keys}
    uv = lining_uv(pos)
    new_pts.append({"pos": pos, "offs": offs, "uv": uv, "half": half, "row": row, "t": t, "s": s}); return len(new_pts) - 1
strip = {}
corner_r1 = corner_r2 = None
for half, (F, Bk) in halves.items():
    LF, LB = arclen(F), arclen(Bk)
    if half == "lower": LF, LB = LF, LB
    r1, r2 = [], []
    for i, s in enumerate(LF):
        is_corner = (half == "upper" and i == len(F) - 1) or (half == "lower" and i == 0)
        if is_corner and corner_r1 is not None: r1.append(corner_r1); continue
        idx = mkpt(half, 1, 1 / 3, s, F, Bk); r1.append(idx)
        if is_corner: corner_r1 = idx
    for j, s in enumerate(LB):
        is_corner = (half == "upper" and j == len(Bk) - 1) or (half == "lower" and j == 0)
        if is_corner and corner_r2 is not None: r2.append(corner_r2); continue
        idx = mkpt(half, 2, 2 / 3, s, F, Bk); r2.append(idx)
        if is_corner: corner_r2 = idx
    strip[half] = (F, Bk, r1, r2, LF, LB)
# faces in abstract form: ("E", vid) existing, ("N", idx) new
faces = []
for half, (F, Bk, r1, r2, LF, LB) in strip.items():
    for i in range(len(F) - 1): faces.append([("E", F[i]), ("E", F[i + 1]), ("N", r1[i + 1]), ("N", r1[i])])
    for j in range(len(Bk) - 1): faces.append([("N", r2[j]), ("N", r2[j + 1]), ("E", Bk[j + 1]), ("E", Bk[j])])
    i = j = 0                                         # zipper r1 (params LF) -> r2 (params LB)
    while i < len(r1) - 1 or j < len(r2) - 1:
        if j >= len(r2) - 1 or (i < len(r1) - 1 and LF[i + 1] <= LB[j + 1]):
            faces.append([("N", r1[i]), ("N", r1[i + 1]), ("N", r2[j])]); i += 1
        else:
            faces.append([("N", r1[i]), ("N", r2[j + 1]), ("N", r2[j])]); j += 1
# orientation: existing faces on the FRONT chain use F[i]->F[i+1] in one direction; the strip must use the opposite.
ef = {}
for p in sme.polygons:
    if p.index in dead: continue
    vs = list(p.vertices)
    for i in range(len(vs)): ef[(vs[i], vs[(i + 1) % len(vs)])] = p.index
def needs_flip():
    votes = 0
    for half, (F, Bk, *_r) in strip.items():
        for i in range(len(F) - 1):
            if (F[i], F[i + 1]) in ef: votes += 1          # our faces use F[i]->F[i+1] too -> clash -> flip
            elif (F[i + 1], F[i]) in ef: votes -= 1
        for j in range(len(Bk) - 1):
            if (Bk[j + 1], Bk[j]) in ef: votes += 1        # our faces use Bk[j+1]->Bk[j]
            elif (Bk[j], Bk[j + 1]) in ef: votes -= 1
    return votes
vote = needs_flip()
if vote > 0: faces = [f[::-1] for f in faces]
print("STRIP new_vertices", len(new_pts), "faces", len(faces), "quads", sum(len(f) == 4 for f in faces), "tris", sum(len(f) == 3 for f in faces), "orientation_vote", vote)

# ---------------- proposal renders (on untouched v5 + separate proposal object) ----------------
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
TGT = mid + Vector((0.022, -0.022, -0.065))          # the commissure itself (earlier views aimed 22 mm behind it)
VIEWS = {"front": Vector((0.0, -0.11, 0.0)), "threequarter": Vector((0.075, -0.085, 0.0)), "side": Vector((0.11, -0.035, 0.0)),
         "inside_low": Vector((-0.02, -0.10, -0.035))}
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
for c in bpy.data.collections:
    if c.name[:2] in ("02", "03", "04", "05", "06", "07", "08"): c.hide_render = True
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); L.data.energy = e; L.data.size = 0.5; L.location = mid + Vector(loc)
    sc.collection.objects.link(L); L.rotation_euler = (mid - L.location).to_track_quat("-Z", "Y").to_euler()
cam = bpy.data.objects.new("CAM7i", bpy.data.cameras.new("CAM7i")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 85; cam.data.clip_start = 0.002
sc.render.resolution_x, sc.render.resolution_y = 1000, 700
def emis(n, rgb, s=1.5):
    m = bpy.data.materials.new(n); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = s
    nt.links.new(e.outputs[0], o.inputs[0]); return m
def shoot(prefix, jaw, views=VIEWS):
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data.shape_keys and "jaw_open" in o.data.shape_keys.key_blocks: o.data.shape_keys.key_blocks["jaw_open"].value = jaw
    for vn, off in views.items():
        cam.location = TGT + off; cam.rotation_euler = (TGT - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(qa, f"{prefix}_jaw{int(jaw * 100):03d}_{vn}.png"); bpy.ops.render.render(write_still=True)
def proposal_object():
    bm = bmesh.new(); vm = {}
    def V(t):
        if t not in vm:
            vm[t] = bm.verts.new(Vector(B0[t[1]]) if t[0] == "E" else Vector(new_pts[t[1]]["pos"]))
        return vm[t]
    for f in faces:
        try: bm.faces.new([V(t) for t in f])
        except ValueError: pass
    bm.verts.index_update(); tlist = sorted(((t, v.index) for t, v in vm.items()), key=lambda kv: kv[1])
    me2 = bpy.data.meshes.new("PROPOSAL_strip"); bm.to_mesh(me2); bm.free()
    ob2 = bpy.data.objects.new("PROPOSAL_strip", me2); ob2.matrix_world = src.matrix_world.copy(); sc.collection.objects.link(ob2)
    ob2.shape_key_add(name="Basis"); kj = ob2.shape_key_add(name="jaw_open")
    for i, (t, _) in enumerate(tlist):
        d = KD["jaw_open"][t[1]] if t[0] == "E" else new_pts[t[1]]["offs"]["jaw_open"]
        kj.data[i].co = Vector(me2.vertices[i].co) + Vector(d)
    return ob2, tlist
def points(name, coords, rgb, r=0.00025):
    m = emis(name, rgb); out = []
    for c in coords:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=8, ring_count=6, location=c); s = bpy.context.active_object; s.name = "PT_" + name
        s.data.materials.append(m); out.append(s)
    return out
if PROPOSAL or os.environ.get("RENDER_PROPOSAL", "1") == "1":
    ob2, tlist = proposal_object()
    wf = ob2.copy(); wf.data = ob2.data.copy(); wf.name = "PROPOSAL_wire"; sc.collection.objects.link(wf)
    mod = wf.modifiers.new("W", "WIREFRAME"); mod.thickness = 0.00007; mod.use_replace = True
    wf.data.materials.append(emis("wire", (0.05, 0.05, 0.05), 1.0)); ob2.data.materials.append(emis("newpatch", (0.1, 0.85, 0.9), 0.9))
    # wireframe of the EXISTING head mesh around the region for context
    hw = src.copy(); hw.name = "EXISTING_wire"; sc.collection.objects.link(hw); m2 = hw.modifiers.new("W", "WIREFRAME"); m2.thickness = 0.00004; m2.use_replace = True
    hw.data = src.data.copy(); hw.data.materials.clear(); hw.data.materials.append(emis("exwire", (0.9, 0.9, 0.9), 0.6))
    Mw = src.matrix_world
    pf = points("front_fixed_visible", [Mw @ Vector(B0[v]) for v in FRONT], (0.1, 1, 0.1))
    pb = points("back_fixed_healthy", [Mw @ Vector(B0[v]) for v in BACK], (0.15, 0.3, 1))
    pn = points("new_vertices", [Mw @ Vector(p["pos"]) for p in new_pts], (1, 0.85, 0), 0.0002)
    # (a) shaded v5 + proposal patch + chain points
    hw.hide_render = True; wf.hide_render = False
    shoot("PROPOSAL_shaded_patch", 0.0); shoot("PROPOSAL_shaded_patch", 0.5)
    # (b) wireframe only: existing (light) + proposed (dark), patch faces hidden
    hw.hide_render = False; ob2.hide_render = True; src.hide_render = True
    for o in bpy.data.objects:
        if o.name in ("OralCavity",): o.hide_render = True
    shoot("PROPOSAL_wireframe", 0.0, {k: VIEWS[k] for k in ("front", "threequarter")}); shoot("PROPOSAL_wireframe", 0.5, {k: VIEWS[k] for k in ("front", "threequarter")})
    src.hide_render = False; ob2.hide_render = False
    # (c) untouched v5 reference from the same framed cameras
    for o in [ob2, wf, hw] + pf + pb + pn: o.hide_render = True
    bpy.data.objects["OralCavity"].hide_render = False
    shoot("V5_reference", 0.0); shoot("V5_reference", 0.5); shoot("V5_reference", 1.0)
    for o in [ob2, wf, hw] + pf + pb + pn: bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data.shape_keys and "jaw_open" in o.data.shape_keys.key_blocks: o.data.shape_keys.key_blocks["jaw_open"].value = 0
json.dump({"front_chain": FRONT, "back_chain": BACK, "corner_front": 4524, "corner_back": 4621, "removed_faces_source": sorted(dead),
           "removed_vertices_source": sorted(mv), "new_vertices": [{"i": i, "half": p["half"], "row": p["row"], "t": round(p["t"], 3), "s": round(float(p["s"]), 3),
           "pos_local_mm": [round(float(x) * 1000, 2) for x in p["pos"]]} for i, p in enumerate(new_pts)],
           "new_faces": [[f"{a}{b}" for a, b in f] for f in faces], "orientation_vote": vote}, open(os.path.join(qa, f"topology_{TAG}.json"), "w"), indent=1)
if PROPOSAL: print("PROPOSAL_DONE"); sys.exit(0)

# ---------------- build ----------------
dst = src.copy(); dst.data = src.data.copy(); dst.name = "GNM_Head_" + TAG
for c in src.users_collection: c.objects.link(dst)
src.hide_render = True; src.hide_viewport = True
me = dst.data
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_00_checkpoint_before_edit.blend"), compress=True, copy=True)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
lay = bm.verts.layers.int.new("src_idx")
for v in bm.verts: v[lay] = v.index
sk = {k: bm.verts.layers.shape[k] for k in keys}
uvL = bm.loops.layers.uv.active
skin_mi = [m.name for m in me.materials].index("Skin")
nv = []
for p in new_pts:
    v = bm.verts.new(Vector(p["pos"])); v[lay] = -1
    for k in keys: v[sk[k]] = Vector(p["pos"]) + Vector(p["offs"][k]) if k != "Basis" else Vector(p["pos"])
    nv.append(v)
bm.verts.ensure_lookup_table()
EV = {v: bm.verts[v] for v in FRONT + BACK}
built = 0; fail = 0
for f in faces:
    vs = [EV[b] if a == "E" else nv[b] for a, b in f]
    try:
        nf = bm.faces.new(vs); nf.material_index = skin_mi; built += 1
        for loop in nf.loops:
            if loop.vert in nv:
                loop[uvL].uv = Vector(new_pts[nv.index(loop.vert)]["uv"])
            else:
                loop[uvL].uv = Vector(vuv[loop.vert.index if loop.vert[lay] < 0 else loop.vert[lay]])
        nf.smooth = True
    except ValueError: fail += 1
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sorted(dead)], context="FACES_ONLY")
wire = [e for e in bm.edges if not e.link_faces]; bmesh.ops.delete(bm, geom=wire, context="EDGES")
loose = [v for v in bm.verts if not v.link_edges]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.verts.ensure_lookup_table(); smap = np.array([v[lay] for v in bm.verts])
bm.to_mesh(me); bm.free(); me.update()
g = dst.vertex_groups.new(name="new_commissure_patch_L"); g.add([int(i) for i in np.where(smap < 0)[0]], 1.0, "REPLACE")
g = dst.vertex_groups.new(name="patch_front_fixed_visible_L"); g.add([int(i) for i in np.where(np.isin(smap, FRONT))[0]], 1.0, "REPLACE")
g = dst.vertex_groups.new(name="patch_back_fixed_lining_L"); g.add([int(i) for i in np.where(np.isin(smap, BACK))[0]], 1.0, "REPLACE")
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
old = smap >= 0; kr = {}
for k in keys:
    a = np.empty(len(me.vertices) * 3); me.shape_keys.key_blocks[k].data.foreach_get("co", a); a = a.reshape(-1, 3)
    kr[k] = round(float(np.abs(a[old] - (B0 + KD[k])[smap[old]]).max()) * 1000, 6)
rep = {"tag": TAG, "bulge_mm": BULGE * 1000, "faces_removed": len(dead), "vertices_removed": int(nV - old.sum()), "new_vertices": int((~old).sum()),
       "new_faces_built": built, "new_faces_failed": fail, "quads": sum(len(f) == 4 for f in faces), "tris": sum(len(f) == 3 for f in faces),
       "vertices_after": len(me.vertices), "faces_after": len(me.polygons), "wire_edges_removed": len(wire), "loose_removed": len(loose),
       "non_manifold_edges": nonman, "existing_vertices_max_move_mm": 0.0 if kr["Basis"] == 0 else kr["Basis"],
       "existing_vertices_all_keys_max_diff_mm": max(kr.values()), "eye_18_max_diff_mm": max(kr[k] for k in EYE), "keys": len(keys) - 1, "key_report_existing": kr,
       "new_keys_added": [], "deformation_rule": "explicit correspondence: offset = (1-t)*front(s) + t*back(s) per key, per half"}
json.dump(rep, open(os.path.join(qa, f"reconstruct_report_{TAG}.json"), "w"), indent=1)
print("BUILD", json.dumps({k: v for k, v in rep.items() if k != "key_report_existing"}))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{TAG}_02_left_reconstructed.blend"), compress=True)
keepo = {"GNM_Rig", dst.name, "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keepo)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = dst
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, f"{TAG}_02_left_reconstructed.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED")

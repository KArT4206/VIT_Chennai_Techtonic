"""PRIVATE: Phase 2N.7D - build the manual mouth-corner reconstruction workspace (no geometry changes).

    blender -b --factory-startup --python prepare_corner_kit.py -- <v5.glb> <out.blend> <out_dir>

Imports v5, then ADDS (never edits geometry):
  * vertex groups + a boolean face attribute marking every region,
  * highlight copies of each region (separate objects, own collections, emissive colours),
  * text labels, front / side / three-quarter / corner close-up cameras,
  * a shape-key inventory (JSON).
Writes the .blend and a selection reference (JSON) to out_dir.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

glb, out_blend, out_dir = sys.argv[sys.argv.index("--") + 1:][:3]
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head"))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
me = head.data; M = np.array(head.matrix_world); kb = me.shape_keys.key_blocks
MM = 1000.0


def arr(k):
    a = np.empty(len(me.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


B = arr(kb[0]); KEYS = {k.name: arr(k) - B for k in kb[1:]}
mid = (np.array(rig.matrix_world @ rig.data.bones["left_eye"].head_local) + np.array(rig.matrix_world @ rig.data.bones["right_eye"].head_local)) / 2
rel = B - mid; X, Z, F = rel[:, 0], rel[:, 2], -rel[:, 1]
mats = [m.name for m in me.materials]
pmat = np.array([p.material_index for p in me.polygons]); pname = [mats[i] for i in pmat]
polys = [list(p.vertices) for p in me.polygons]
is_skin_f = np.array([n == "Skin" for n in pname])
skin_v = np.zeros(len(B), bool)
for p, s in zip(polys, is_skin_f):
    if s: skin_v[p] = True

# ---- reference geometry (same rules as the build: lip line, corners) ----
bvh_rest = BVHTree.FromPolygons([Vector(v) for v in B], [p for p, s in zip(polys, is_skin_f) if s])
def stomion(x, z0, z1):
    best = (1e9, None)
    for z in np.arange(z0, z1, -0.00025):
        h = bvh_rest.ray_cast(Vector((mid[0] + x, mid[1] - 1, mid[2] + z)), Vector((0, 1, 0)), 3)
        f = -1.0 if h[0] is None else -(h[0][1] - mid[1])
        if f < best[0]: best = (f, z)
    return best[1]
zc = stomion(0.0, -0.055, -0.080); xs = np.arange(-0.032, 0.0321, 0.001); line = np.zeros(len(xs)); i0 = int(np.argmin(np.abs(xs)))
for rng in (range(i0, len(xs)), range(i0, -1, -1)):
    zp = zc
    for i in rng:
        zp = stomion(xs[i], zp + 0.0025, zp - 0.0025); line[i] = zp
corner_x = 0.027
zl = np.interp(X, xs, np.convolve(np.pad(line, 3, mode="edge"), np.ones(7) / 7, mode="valid")); dz = Z - zl

# ---- defective slivers: measured, not guessed. A face is defective if it is a near-zero-area skin face in
#      the commissure zone whose area grows > 4x at jaw 50 % or 100 %, or under full smile.
def area(P, vs):
    a = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); return float(np.linalg.norm(a)) / 2
poses = {"jaw50": 0.5 * KEYS["jaw_open"], "jaw100": KEYS["jaw_open"],
         "smileL": KEYS.get("mouth_smile_L", 0 * B), "smileR": KEYS.get("mouth_smile_R", 0 * B),
         "laugh": KEYS["jaw_open"] * 0.4 + KEYS["mouth_smile_L"] + KEYS["mouth_smile_R"] + 0.4 * KEYS.get("corr_jaw_smile_L", 0 * B) + 0.4 * KEYS.get("corr_jaw_smile_R", 0 * B)}
zone_f = []
for fi, (vs, s) in enumerate(zip(polys, is_skin_f)):
    if not s or len(vs) != 3: continue
    c = rel[vs].mean(0)
    if 0.014 < abs(c[0]) < corner_x + 0.006 and abs(dz[vs].mean()) < 0.010 and -c[1] < 0.036:
        zone_f.append(fi)
defect = {}
for fi in zone_f:
    vs = polys[fi]; a0 = area(B, vs)
    worst = max(area(B + D, vs) / max(a0, 1e-14) for D in poses.values())
    if worst > 4.0:
        defect[fi] = {"rest_area_mm2": round(a0 * 1e6, 4), "worst_area_growth": round(worst, 1), "side": "L" if X[vs].mean() > 0 else "R",
                      "centre_rel_eyes_mm": [round(float(v) * MM, 2) for v in rel[vs].mean(0)], "vertices": vs}
# two measured clusters: tiny commissure slivers vs a chain of larger inner-cheek (buccal) seam faces
for d in defect.values():
    d["cluster"] = "commissure_sliver" if (abs(d["centre_rel_eyes_mm"][0]) < 25.5 and d["rest_area_mm2"] < 0.5) else "buccal_seam_chain"
# ---- regions (vertex sets) ----
fwd_front = F > 0.031
reg = {}
reg["commissure_defect_L"] = sorted({v for f, d in defect.items() if d["side"] == "L" for v in polys[f]})
reg["commissure_defect_R"] = sorted({v for f, d in defect.items() if d["side"] == "R" for v in polys[f]})
upper = skin_v & (np.abs(X) < corner_x + 0.002) & (dz > 0.0) & (dz < 0.010) & fwd_front
lower = skin_v & (np.abs(X) < corner_x + 0.002) & (dz <= 0.0) & (dz > -0.012) & fwd_front
reg["upper_lip"] = np.where(upper)[0].tolist(); reg["lower_lip"] = np.where(lower)[0].tolist()
inner = skin_v & (np.abs(X) < corner_x + 0.004) & (np.abs(dz) < 0.014) & (F <= 0.031) & (F > 0.0)
reg["inner_lip_mucosa"] = np.where(inner)[0].tolist()
cheek = skin_v & (np.abs(X) > corner_x - 0.002) & (np.abs(X) < corner_x + 0.020) & (np.abs(dz) < 0.018) & (F > 0.020) & ~upper & ~lower & ~inner
reg["external_cheek"] = np.where(cheek)[0].tolist()
# boundary edges of the head in the mouth area = oral cavity boundary (opening created by the 39 removed faces + scan's own)
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
ob_v = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts if abs(X[v.index]) < corner_x + 0.006 and abs(dz[v.index]) < 0.016})
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary); bm.free()
reg["oral_cavity_boundary"] = ob_v
# proposed replacement patch = the defective faces plus a one-ring around them (what gets rebuilt)
ring = {}
for s in "LR":
    seed = set(reg["commissure_defect_" + s]); grown = set(seed)
    for fi, vs in enumerate(polys):                     # exactly one ring: faces touching the ORIGINAL defect set
        if is_skin_f[fi] and any(v in seed for v in vs): grown.update(vs)
    ring[s] = grown
reg["proposed_patch_L"] = sorted(ring["L"]); reg["proposed_patch_R"] = sorted(ring["R"])
# preserved boundary = patch vertices on the patch edge (shared with faces outside the patch)
for s in "LR":
    pv = ring[s]; inside_f = [fi for fi, vs in enumerate(polys) if all(v in pv for v in vs)]
    outside_touch = {v for fi, vs in enumerate(polys) if not all(v in pv for v in vs) for v in vs if v in pv}
    reg["patch_boundary_keep_" + s] = sorted(outside_touch)
    reg["patch_faces_" + s] = inside_f

# ---- write vertex groups + face attributes (non-geometric) ----
for name, vs in reg.items():
    if name.startswith("patch_faces_"): continue
    g = head.vertex_groups.new(name=name); g.add([int(v) for v in vs], 1.0, "REPLACE")
fa = me.attributes.new("defect_commissure", "BOOLEAN", "FACE"); fa.data.foreach_set("value", [i in defect for i in range(len(polys))])
for s in "LR":
    pa = me.attributes.new("patch_" + s, "BOOLEAN", "FACE"); sel = set(reg["patch_faces_" + s]); pa.data.foreach_set("value", [i in sel for i in range(len(polys))])

# ---- collections ----
def coll(name):
    c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c
C = {n: coll(n) for n in ("01_Original_mouth_geometry", "02_Left_commissure", "03_Right_commissure", "04_Upper_lip", "05_Lower_lip", "06_Interior_lining", "07_Proposed_replacement_patches", "08_Labels_and_cameras")}
for o in list(bpy.context.scene.collection.objects):
    bpy.context.scene.collection.objects.unlink(o); C["01_Original_mouth_geometry"].objects.link(o)

def emis(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = 2.0
    nt.links.new(e.outputs[0], o.inputs[0]); return m

def highlight(name, face_ids, rgb, collection, offset=0.00015, wire=False):
    """separate copy of the selected faces, nudged along the normal so it shows on top (the head is untouched)"""
    bmh = bmesh.new(); vmap = {}
    for fi in face_ids:
        vs = polys[fi]
        for v in vs:
            if v not in vmap: vmap[v] = bmh.verts.new(Vector(me.vertices[v].co))
        try: bmh.faces.new([vmap[v] for v in vs])
        except ValueError: pass
    bmh.normal_update()
    for v in bmh.verts: v.co += v.normal * offset
    m2 = bpy.data.meshes.new(name); bmh.to_mesh(m2); bmh.free()
    ob = bpy.data.objects.new(name, m2); ob.matrix_world = head.matrix_world.copy(); collection.objects.link(ob)
    m2.materials.append(emis("hl_" + name, rgb))
    if wire:
        md = ob.modifiers.new("wire", "WIREFRAME"); md.thickness = 0.00012
    return ob

def faces_of(vset, all_in=True):
    vs_ = set(vset); return [fi for fi, vs in enumerate(polys) if (all(v in vs_ for v in vs) if all_in else any(v in vs_ for v in vs))]

for sd, cname in (("L", "02_Left_commissure"), ("R", "03_Right_commissure")):
    highlight("DEFECT_commissure_slivers_" + sd, [f for f, d in defect.items() if d["side"] == sd and d["cluster"] == "commissure_sliver"], (1.0, 0.05, 0.05), C[cname], 0.0003)
    highlight("DEFECT_buccal_seam_chain_" + sd, [f for f, d in defect.items() if d["side"] == sd and d["cluster"] == "buccal_seam_chain"], (0.75, 0.0, 1.0), C[cname], 0.0003)
highlight("upper_lip_boundary", faces_of(reg["upper_lip"]), (0.1, 0.5, 1.0), C["04_Upper_lip"], 0.0001, wire=True)
highlight("lower_lip_boundary", faces_of(reg["lower_lip"]), (0.1, 1.0, 0.4), C["05_Lower_lip"], 0.0001, wire=True)
highlight("inner_lip_mucosa", faces_of(reg["inner_lip_mucosa"]), (1.0, 0.4, 0.8), C["06_Interior_lining"], 0.0001, wire=True)
highlight("external_cheek", faces_of(reg["external_cheek"]), (1.0, 0.9, 0.1), C["06_Interior_lining"], 0.0001, wire=True)
for s in "LR":
    highlight("PROPOSED_patch_" + s, reg["patch_faces_" + s], (1.0, 0.55, 0.0), C["07_Proposed_replacement_patches"], 0.0002, wire=True)
# oral cavity boundary as a curve-like wire object (edges only)
bme = bmesh.new(); vm = {}
bmsrc = bmesh.new(); bmsrc.from_mesh(me); bmsrc.verts.ensure_lookup_table()
for e in bmsrc.edges:
    if e.is_boundary and all(v.index in set(ob_v) for v in e.verts):
        a, b = e.verts
        for v in (a, b):
            if v.index not in vm: vm[v.index] = bme.verts.new(v.co)
        bme.edges.new((vm[a.index], vm[b.index]))
bmsrc.free(); m3 = bpy.data.meshes.new("oral_cavity_boundary"); bme.to_mesh(m3); bme.free()
ocb = bpy.data.objects.new("oral_cavity_boundary", m3); ocb.matrix_world = head.matrix_world.copy(); C["06_Interior_lining"].objects.link(ocb)
md = ocb.modifiers.new("skin", "SKIN")  # make edges visible in renders
for v in m3.skin_vertices[0].data: v.radius = (0.00025, 0.00025)

# ---- labels and cameras (world space) ----
def label(text, pos, size=0.003):
    cu = bpy.data.curves.new(text, "FONT"); cu.body = text; cu.size = size
    ob = bpy.data.objects.new("LBL_" + text, cu); ob.location = Vector(pos.tolist()); ob.rotation_euler = (math.radians(90), 0, 0)
    ob.data.materials.append(emis("lbl_" + text, (1, 1, 1))); C["08_Labels_and_cameras"].objects.link(ob)
mz = mid[2] + float(np.interp(0, xs, line)); fy = mid[1] - 0.045
label("LEFT commissure (char.)", np.array([mid[0] + 0.030, fy, mz + 0.006]))
label("RIGHT commissure (char.)", np.array([mid[0] - 0.062, fy, mz + 0.006]))
label("upper lip (blue)", np.array([mid[0] - 0.010, fy, mz + 0.016]))
label("lower lip (green)", np.array([mid[0] - 0.010, fy, mz - 0.020]))
label("red = defective slivers  orange = proposed patch  pink = inner mucosa  yellow = cheek", np.array([mid[0] - 0.050, fy, mz - 0.030]), 0.0022)
target = Vector((mid[0], mid[1] - 0.030, mz))
for name, off, lens in (("CAM_front", (0, -0.20, 0), 85), ("CAM_side_L", (0.20, -0.03, 0), 85), ("CAM_threequarter_L", (0.14, -0.15, 0.0), 85),
                        ("CAM_threequarter_R", (-0.14, -0.15, 0.0), 85), ("CAM_corner_L_macro", (0.05, -0.08, 0.005), 85), ("CAM_corner_R_macro", (-0.05, -0.08, 0.005), 85)):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); cam.data.lens = lens; cam.data.clip_start = 0.002
    tgt = target + Vector(((0.022 if name.endswith("L_macro") else -0.022 if name.endswith("R_macro") else 0), 0, 0))
    cam.location = tgt + Vector(off); cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    C["08_Labels_and_cameras"].objects.link(cam)
bpy.context.scene.camera = bpy.data.objects["CAM_front"]

# ---- inventory + reference ----
inv = {"object": head.name, "vertices": len(me.vertices), "faces": len(me.polygons), "non_manifold_edges": nonman,
       "shape_keys": [{"name": k.name, "value": k.value, "slider": [k.slider_min, k.slider_max], "relative_key": k.relative_key.name,
                       "max_displacement_mm": round(float(np.linalg.norm(KEYS[k.name], axis=1).max()) * MM, 4) if k.name in KEYS else 0.0,
                       "verts_moving_over_0_01mm": int((np.linalg.norm(KEYS[k.name], axis=1) > 1e-5).sum()) if k.name in KEYS else 0}
                      for k in kb], "other_meshes": [{"name": o.name, "shape_keys": [k.name for k in o.data.shape_keys.key_blocks] if o.type == "MESH" and o.data.shape_keys else []}
                                                   for o in bpy.data.objects if o.type == "MESH" and o is not head and not any(o.name.startswith(p) for p in ("DEFECT", "PROPOSED", "upper_lip", "lower_lip", "inner_lip", "external", "oral_cavity_boundary"))]}
json.dump(inv, open(os.path.join(out_dir, "shape_key_inventory.json"), "w"), indent=1)
ref = {"source_glb": os.path.basename(glb), "corner_x_mm": corner_x * MM, "defective_faces": defect,
       "defective_face_count": {s: sum(1 for d in defect.values() if d["side"] == s) for s in "LR"},
       "defective_by_cluster": {f"{s}_{c}": sum(1 for d in defect.values() if d["side"] == s and d["cluster"] == c) for s in "LR" for c in ("commissure_sliver", "buccal_seam_chain")},
       "regions_vertex_counts": {k: len(v) for k, v in reg.items()}, "regions": {k: [int(x) for x in v] for k, v in reg.items()},
       "test_poses": list(poses)}
json.dump(ref, open(os.path.join(out_dir, "selection_reference.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
print("KIT", json.dumps({"defective": ref["defective_face_count"], "clusters": ref["defective_by_cluster"], "regions": ref["regions_vertex_counts"], "keys": len(kb), "nonman": nonman}))

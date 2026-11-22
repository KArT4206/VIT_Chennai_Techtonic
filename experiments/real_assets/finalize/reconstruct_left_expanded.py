"""PRIVATE: Phase 2N.7F - expanded LEFT commissure reconstruction (reproducible). Never touches GNM_Head (v5 source).

    blender -b <checkpoint_start.blend> --python reconstruct_left_expanded.py -- <selection_reference.json> <flap_diag.json> <out.blend> <out.glb> <report.json> <shot_dir>

Diagnosis (diag_flap.py on v5): the visible pink flap is a cluster of NORMAL-SIZED inner upper-lip lining faces
(7158-7162, 7212, 7213, 7236) whose vertices received inconsistent jaw motion (e.g. 5.2 / 0.4 / 0.7 mm on one face),
so the faces rotate 47-87 deg into view. Cause = jaw-weight classification, not topology.

Repair on a duplicate GNM_Head_v6x:
  1. remove the 14 confirmed LEFT commissure slivers (+ the wire edges they leave)        [topology]
  2. CORE = vertices of the flap faces + the sliver neighbourhood (corner tip); RING = one ring around CORE (pinned).
     For jaw_open and corr_jaw_smile_L only, CORE deltas are replaced by the harmonic interpolation of the RING deltas
     over the mesh connectivity (Laplace, RING fixed). Rest positions and every other key stay exact.
  Saves selection groups "repair_core_L" / "repair_ring_L", screenshots of the region before the edit, the .blend,
  a test GLB and a full report (counts, exactness, rest/open quality metrics of the region).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

ref_p, diag_p, out_blend, out_glb, rep_p, shots = sys.argv[sys.argv.index("--") + 1:][:6]
os.makedirs(shots, exist_ok=True)
ref = json.load(open(ref_p)); diag = json.load(open(diag_p))
FLAP = [7158, 7159, 7160, 7161, 7162, 7212, 7213, 7236]
SLIV = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] == "commissure_sliver"]
CREASE = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == "L" and d["cluster"] != "commissure_sliver"]
src = bpy.data.objects["GNM_Head"]; sme = src.data
polys = [list(p.vertices) for p in sme.polygons]
mats = [m.name for m in sme.materials]

# ---------- region ----------
core = {v for f in FLAP + SLIV for v in polys[f]}
adj = [set() for _ in range(len(sme.vertices))]
for e in sme.edges:
    a, b = e.vertices; adj[a].add(b); adj[b].add(a)
# corner tip: include the one-ring of the sliver vertices (jagged tip after removal) in the CORE
core |= {u for v in {v for f in SLIV for v in polys[f]} for u in adj[v]}
crease_v = {v for f in CREASE for v in polys[f]}
core -= crease_v                                  # the external crease chain is NOT modified
skin_v = {v for p in sme.polygons if mats[p.material_index] == "Skin" for v in p.vertices}
core &= skin_v
ring = {u for v in core for u in adj[v]} - core
for name, vs in (("repair_core_L", core), ("repair_ring_L", ring)):
    g = src.vertex_groups.get(name) or src.vertex_groups.new(name=name); g.add(sorted(vs), 1.0, "REPLACE")

# ---------- screenshots BEFORE editing (region highlighted on the untouched v5 head) ----------
def emis(n, rgb):
    m = bpy.data.materials.new(n); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = 2
    nt.links.new(e.outputs[0], o.inputs[0]); return m
def hl(name, faces, rgb, off):
    bmh = bmesh.new(); vm = {}
    for f in faces:
        for v in polys[f]:
            if v not in vm: vm[v] = bmh.verts.new(Vector(sme.vertices[v].co))
        try: bmh.faces.new([vm[v] for v in polys[f]])
        except ValueError: pass
    bmh.normal_update()
    for v in bmh.verts: v.co += v.normal * off
    m2 = bpy.data.meshes.new(name); bmh.to_mesh(m2); bmh.free(); ob = bpy.data.objects.new(name, m2); ob.matrix_world = src.matrix_world.copy()
    bpy.context.scene.collection.objects.link(ob); m2.materials.append(emis("m_" + name, rgb)); return ob
core_faces = [i for i, p in enumerate(polys) if all(v in core for v in p)]
ring_faces = [i for i, p in enumerate(polys) if any(v in ring for v in p) and not all(v in core for v in p)]
H = [hl("HL_flap_faces", FLAP, (1, 0.05, 0.05), 0.00025), hl("HL_slivers", SLIV, (1, 0.6, 0), 0.00025),
     hl("HL_core", [f for f in core_faces if f not in FLAP and f not in SLIV], (0.1, 0.5, 1), 0.0002), hl("HL_pinned_ring", ring_faces, (1, 1, 0.2), 0.00015),
     hl("HL_crease_untouched", CREASE, (0.7, 0, 1), 0.00025)]
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
try: sc.view_settings.view_transform = "AgX"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
for c in bpy.data.collections:
    if c.name[:2] in ("02", "03", "04", "05", "06", "07", "08"): c.hide_render = True
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
tgt = mid + Vector((0.018, -0.030, -0.065))
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); L.data.energy = e; L.data.size = 0.5
    L.location = tgt + Vector(loc) * 0.6; sc.collection.objects.link(L); L.rotation_euler = (tgt - L.location).to_track_quat("-Z", "Y").to_euler()
cam = bpy.data.objects.new("CAM_repair", bpy.data.cameras.new("CAM_repair")); cam.data.lens = 85; cam.data.clip_start = 0.002; sc.collection.objects.link(cam); sc.camera = cam
def shoot(name, off, jaw):
    for o in (src,):
        o.data.shape_keys.key_blocks["jaw_open"].value = jaw
    cam.location = tgt + Vector(off); cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(shots, name + ".png"); bpy.ops.render.render(write_still=True)
for nm, off in (("front", (0.0, -0.10, 0.0)), ("threequarter", (0.07, -0.075, 0.0)), ("side", (0.10, -0.03, 0.0))):
    shoot("BEFORE_region_marked_" + nm, off, 0.0)
for o in H: o.hide_render = True
for jaw in (0.0, 0.5, 1.0):
    shoot(f"BEFORE_v5_unmarked_front_jaw{int(jaw*100):03d}", (0.0, -0.10, 0.0), jaw)
src.data.shape_keys.key_blocks["jaw_open"].value = 0.0
for o in H: bpy.data.objects.remove(o, do_unlink=True)

# ---------- edit a duplicate ----------
dst = src.copy(); dst.data = src.data.copy(); dst.name = "GNM_Head_v6x"
for c in src.users_collection: c.objects.link(dst)
src.hide_render = True; src.hide_viewport = True
me = dst.data
kb = me.shape_keys.key_blocks
def K(name): a = np.empty(len(me.vertices) * 3); kb[name].data.foreach_get("co", a); return a.reshape(-1, 3)
B0 = K("Basis")
REPAIR_KEYS = ["jaw_open", "corr_jaw_smile_L"]
ring_l = sorted(ring); core_l = sorted(core)
before = {k: K(k) - B0 for k in REPAIR_KEYS}
for k in REPAIR_KEYS:
    D = before[k].copy()
    for _ in range(4000):                     # Laplace with RING fixed (Jacobi); converges on ~200 vertices
        newD = D.copy()
        for v in core_l:
            nb = list(adj[v]); newD[v] = D[nb].mean(0)
        D = newD
    a = B0 + D; kb[k].data.foreach_set("co", a.ravel())
corr = {k: {"core_max_change_mm": round(float(np.linalg.norm((K(k) - B0)[core_l] - before[k][core_l], axis=1).max()) * 1000, 3),
            "outside_core_max_change_mm": round(float(np.abs(np.delete((K(k) - B0) - before[k], core_l, axis=0)).max()) * 1000, 6)} for k in REPAIR_KEYS}
# topology: remove the 14 slivers + wire edges (bmesh with shape layers -> keys follow exactly)
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
cent = lambda P, vs: P[vs].mean(0)
dc = {tuple(np.round(cent(B0, [v.index for v in f.verts]) * 1e7).astype(int)): f for f in bm.faces}
gone = [dc.get(tuple(np.round(cent(B0, polys[f]) * 1e7).astype(int))) for f in SLIV]
gone = [f for f in gone if f is not None]
bmesh.ops.delete(bm, geom=gone, context="FACES_ONLY")
wire = [e for e in bm.edges if not e.link_faces]; bmesh.ops.delete(bm, geom=wire, context="EDGES")
loose = [v for v in bm.verts if not v.link_edges]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.to_mesh(me); bm.free(); me.update()

# ---------- exactness vs source (neighbour-checked twins) ----------
S0 = np.empty(len(sme.vertices) * 3); sme.shape_keys.key_blocks["Basis"].data.foreach_get("co", S0); S0 = S0.reshape(-1, 3)
E0 = K("Basis") if False else None
kb = me.shape_keys.key_blocks
E0 = np.empty(len(me.vertices) * 3); kb["Basis"].data.foreach_get("co", E0); E0 = E0.reshape(-1, 3)
kd = KDTree(len(S0)); [kd.insert(Vector(v), i) for i, v in enumerate(S0)]; kd.balance()
def rings(m):
    nb = [[] for _ in range(len(m.vertices))]
    for e in m.edges: a, b = e.vertices; nb[a].append(b); nb[b].append(a)
    return nb
nbS, nbE = rings(sme), rings(me)
match = np.full(len(E0), -1)
for i, v in enumerate(E0):
    c = [j for (_, j, d) in kd.find_range(Vector(v), 1e-7)]
    if len(c) > 1:
        rE = E0[nbE[i]]; c.sort(key=lambda j: float(np.mean([np.min(np.linalg.norm(S0[nbS[j]] - p, axis=1)) for p in rE])) if len(nbS[j]) and len(rE) else 1e9)
    if c: match[i] = c[0]
def SK(m, k): a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[k].data.foreach_get("co", a); return a.reshape(-1, 3)
keys = [k.name for k in sme.shape_keys.key_blocks]
in_core = np.isin(match, core_l)
diff = {k: round(float(np.abs(SK(me, k)[~in_core] - SK(sme, k)[match[~in_core]]).max()) * 1000, 6) for k in keys}
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
core_other = {k: round(float(np.abs(SK(me, k)[in_core] - SK(sme, k)[match[in_core]]).max()) * 1000, 6) for k in keys if k not in REPAIR_KEYS}

# ---------- region quality (rest / jaw50 / jaw100 / smile+jaw100) ----------
cset = set(np.where(in_core)[0].tolist())
rfaces = [p for p in me.polygons if any(v in cset for v in p.vertices)]
def quality(P):
    out = {"faces": len(rfaces), "min_area_mm2": 1e9, "max_aspect": 0, "faces_area_below_0_05mm2": 0, "max_normal_jump_deg_vs_neighbours": 0, "inverted_vs_rest": 0}
    nrm = {}
    for p in rfaces:
        vs = list(p.vertices)
        if len(vs) != 3: continue
        a = np.cross(P[vs[1]] - P[vs[0]], P[vs[2]] - P[vs[0]]); ar = np.linalg.norm(a) / 2
        e = [np.linalg.norm(P[vs[i]] - P[vs[(i + 1) % 3]]) for i in range(3)]
        out["min_area_mm2"] = min(out["min_area_mm2"], ar * 1e6); out["faces_area_below_0_05mm2"] += int(ar * 1e6 < 0.05)
        out["max_aspect"] = max(out["max_aspect"], max(e) ** 2 / (4 * ar / math.sqrt(3) + 1e-18)); nrm[p.index] = a / (np.linalg.norm(a) + 1e-15)
    bmq = bmesh.new(); bmq.from_mesh(me); bmq.faces.ensure_lookup_table()
    for fi, n in nrm.items():
        for ed in bmq.faces[fi].edges:
            for g in ed.link_faces:
                if g.index != fi and g.index in nrm:
                    out["max_normal_jump_deg_vs_neighbours"] = max(out["max_normal_jump_deg_vs_neighbours"], float(np.degrees(np.arccos(np.clip(n @ nrm[g.index], -1, 1)))))
    bmq.free()
    out["min_area_mm2"] = round(out["min_area_mm2"], 4); out["max_aspect"] = round(out["max_aspect"], 1); out["max_normal_jump_deg_vs_neighbours"] = round(out["max_normal_jump_deg_vs_neighbours"], 1)
    return out, nrm
J = SK(me, "jaw_open") - E0; SM = SK(me, "mouth_smile_L") - E0 + SK(me, "mouth_smile_R") - E0; CJ = SK(me, "corr_jaw_smile_L") - E0 + SK(me, "corr_jaw_smile_R") - E0
qrest, n0 = quality(E0)
poses = {"jaw50": E0 + 0.5 * J, "jaw100": E0 + J, "smile_jaw100": E0 + J + 0.8 * SM + 0.8 * CJ}
qual = {"rest": qrest}
for nm, P in poses.items():
    q, n1 = quality(P); q["max_face_rotation_deg_vs_rest"] = round(max(float(np.degrees(np.arccos(np.clip(n0[f] @ n1[f], -1, 1)))) for f in n1), 1); qual[nm] = q
rep = {"flap_faces": FLAP, "flap_face_diagnosis": [r for r in diag["flap_candidates_jaw100"] if r["face"] in FLAP],
       "sliver_faces_removed": len(gone), "wire_edges_removed": len(wire), "loose_vertices_removed": len(loose),
       "core_vertices": len(core), "ring_vertices_pinned": len(ring), "crease_chain_vertices_excluded": len(crease_v & set(range(len(sme.vertices)))),
       "vertices_before": len(sme.vertices), "vertices_after": len(me.vertices), "new_vertices": 0, "non_manifold_edges": nonman,
       "all_vertices_matched": bool((match >= 0).all()), "keys": len(keys) - 1, "repaired_keys": REPAIR_KEYS, "repair_change": corr,
       "outside_core_all_keys_max_diff_mm": max(diff.values()), "core_unrepaired_keys_max_diff_mm": max(core_other.values()),
       "eye_18_max_diff_mm": max(diff[k] for k in EYE), "region_quality": qual}
json.dump(rep, open(rep_p, "w"), indent=1, default=float)
print("REPAIR", json.dumps({k: v for k, v in rep.items() if k not in ("flap_face_diagnosis", "region_quality")}, default=float))
print("QUALITY", json.dumps(qual, default=float))
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
keep = {"GNM_Rig", "GNM_Head_v6x", "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects: o.select_set(o.name in keep)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = dst
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
                          export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True, export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED", out_glb)

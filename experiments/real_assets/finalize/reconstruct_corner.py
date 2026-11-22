"""PRIVATE: Phase 2N.7E - reproducible commissure reconstruction on a working copy.

    blender -b <in.blend> --python reconstruct_corner.py -- <side L|R> <selection_reference.json> <out.blend> <out.glb> <report.json>

Edits a duplicate named GNM_Head_v6 (created from GNM_Head on the first run, reused afterwards); GNM_Head stays the
untouched source. The edit is done in bmesh WITH the shape-key layers loaded, so every remaining vertex keeps all 35
key offsets exactly (no transfer needed for them); the result is then verified against the source vertex-by-vertex.

Method (from the 2N.7E hole inspection): the confirmed commissure slivers are the ragged, folded END OF THE MOUTH
OPENING - removing them leaves small boundary loops that join the existing opening boundary. So the reconstruction
  1. removes only that side's "commissure_sliver" faces (never the external crease chain),
  2. removes the wire edges / loose vertices this leaves (geometry with no faces),
  3. leaves the opening to end cleanly at the commissure; no fill is created (a fill would recreate the bridge).
"""
import json
import sys

import bmesh
import bpy
import numpy as np

side, ref_path, out_blend, out_glb, rep_path = sys.argv[sys.argv.index("--") + 1:][:5]
ref = json.load(open(ref_path))
src = bpy.data.objects["GNM_Head"]
dst = bpy.data.objects.get("GNM_Head_v6")
if dst is None:
    dst = src.copy(); dst.data = src.data.copy(); dst.name = "GNM_Head_v6"
    for c in src.users_collection: c.objects.link(dst)
    src.hide_render = True; src.hide_viewport = True
me = dst.data
targets = [int(f) for f, d in ref["defective_faces"].items() if d["side"] == side and d["cluster"] == "commissure_sliver"]

# face indices refer to the SOURCE mesh; map to the working mesh through the face attribute + centre match
def centres(m):
    v = np.empty(len(m.vertices) * 3); m.vertices.foreach_get("co", v); v = v.reshape(-1, 3)
    return np.array([v[list(p.vertices)].mean(0) for p in m.polygons])
cs = centres(src.data); cd = centres(me)
want = cs[targets]
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
idx = []
for c in want:
    d = np.linalg.norm(cd - c, axis=1); j = int(d.argmin())
    if d[j] < 1e-9: idx.append(j)
nv0, nf0 = len(bm.verts), len(bm.faces)
faces = [bm.faces[i] for i in idx]
bmesh.ops.delete(bm, geom=faces, context="FACES_ONLY")
wire = [e for e in bm.edges if not e.link_faces]
bmesh.ops.delete(bm, geom=wire, context="EDGES")
loose = [v for v in bm.verts if not v.link_edges]
bmesh.ops.delete(bm, geom=loose, context="VERTS")
nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
bm.to_mesh(me); bm.free(); me.update()

# ---- verify every remaining vertex against the source: position + all keys exact (neighbour-checked twins) ----
def keyarr(m, name):
    a = np.empty(len(m.vertices) * 3); m.shape_keys.key_blocks[name].data.foreach_get("co", a); return a.reshape(-1, 3)
S0 = keyarr(src.data, "Basis"); E0 = keyarr(me, "Basis")
from mathutils.kdtree import KDTree
from mathutils import Vector
kd = KDTree(len(S0))
for i, v in enumerate(S0): kd.insert(Vector(v), i)
kd.balance()
def ring(m):
    nb = [[] for _ in range(len(m.vertices))]
    for e in m.edges: a, b = e.vertices; nb[a].append(b); nb[b].append(a)
    return nb
nbS, nbE = ring(src.data), ring(me)
match = np.full(len(E0), -1)
for i, v in enumerate(E0):
    cands = [j for (_, j, d) in kd.find_range(Vector(v), 1e-7)]
    if len(cands) == 1: match[i] = cands[0]
    elif cands:
        ringE = E0[nbE[i]]
        cands.sort(key=lambda j: float(np.mean([np.min(np.linalg.norm(S0[nbS[j]] - p, axis=1)) for p in ringE])) if len(nbS[j]) and len(ringE) else 1e9)
        match[i] = cands[0]
keys = [k.name for k in src.data.shape_keys.key_blocks]
maxdiff = {}
for k in keys:
    maxdiff[k] = float(np.abs(keyarr(me, k) - keyarr(src.data, k)[match]).max()) * 1000 if (match >= 0).all() else None
EYE = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
       "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]
rep = {"side": side, "target_faces_source_index": targets, "faces_matched_in_working_mesh": len(idx), "faces_removed": len(faces), "wire_edges_removed": len(wire),
       "loose_vertices_removed": len(loose), "vertices_before": nv0, "vertices_after": len(me.vertices), "faces_before": nf0, "faces_after": len(me.polygons),
       "new_vertices": 0, "non_manifold_edges": nonman, "all_vertices_matched_to_source": bool((match >= 0).all()),
       "shape_keys": len(keys) - 1, "max_key_diff_mm_all": max(v for v in maxdiff.values() if v is not None),
       "max_key_diff_mm_eye_18": max(maxdiff[k] for k in EYE), "key_diff_mm": maxdiff}
json.dump(rep, open(rep_path, "w"), indent=1); print("RECON", json.dumps({k: v for k, v in rep.items() if k != "key_diff_mm"}))

# ---- save working file + export test GLB (head_v6 + rig + strands + interior only) ----
bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
keep = {"GNM_Rig", "GNM_Head_v6", "Brows_web", "Lashes_web", "OralCavity"}
for o in bpy.data.objects:
    o.hide_set(False) if o.name in bpy.context.view_layer.objects else None
    o.select_set(o.name in keep)
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
bpy.context.view_layer.objects.active = dst
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True, export_normals=True,
                          export_tangents=False, export_materials="EXPORT", export_image_format="AUTO", export_morph=True, export_morph_normal=True,
                          export_skins=True, export_animations=False, export_apply=False)
print("EXPORTED", out_glb)

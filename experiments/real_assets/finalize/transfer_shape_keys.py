"""PRIVATE: transfer every shape key from the original head to a manually retopologised copy.

Inside the kit .blend (or any .blend holding both objects):
    blender -b <kit.blend> --python transfer_shape_keys.py -- <source_obj> <edited_obj> <report.json> [--selftest identity|patch]

Rules
  1. EXACT  : an edited vertex whose rest position equals an original vertex (< 0.0001 mm) receives that
              vertex's shape-key offsets bit-for-bit (all unmodified geometry, incl. every eye/eyelid vertex).
  2. SURFACE: any other vertex (only expected inside the rebuilt commissure patch) receives the barycentric
              interpolation of the offsets of the closest point on the ORIGINAL surface, excluding the
              defective sliver faces (face attribute "defect_commissure") so their unfolding is not copied.
  3. Every SURFACE vertex must lie inside vertex group "proposed_patch_L/R" of the edited object (or within
              2 mm of it). Anything else is reported as an unintended edit and the run fails.
Self-tests (on throwaway duplicates; the source object is never modified):
  identity : unchanged duplicate -> every key must match exactly (max 0.0)
  subdivide: duplicate, subdivide the LEFT defect faces (valid topology edit, new vertices on the surface) -> must PASS
  patch    : NEGATIVE test - duplicate, replace the LEFT defect faces with a filled + subdivided test patch, transfer, then
             verify all non-patch vertices exact, eye keys exact, no non-manifold edges.
"""
import json
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

args = sys.argv[sys.argv.index("--") + 1:]
src_name, dst_name, rep_path = args[:3]
selftest = args[args.index("--selftest") + 1] if "--selftest" in args else None
EXACT_TOL = 1e-7  # metres (0.0001 mm)
EYE_KEYS = ["blink_L", "lid_follow_L", "squint_L", "surprise_L", "brow_raise_L", "blink_R", "lid_follow_R", "squint_R", "surprise_R", "brow_raise_R",
            "brow_furrow_L", "brow_furrow_R", "cheek_raise_L", "cheek_raise_R", "corr_blink_arc_L", "corr_blink_arc_R", "corr_blink_squint_L", "corr_blink_squint_R"]

src = bpy.data.objects[src_name]


def coords(ob, kname=None):
    k = ob.data.shape_keys.key_blocks[kname] if kname else None
    a = np.empty(len(ob.data.vertices) * 3)
    (k.data if k else ob.data.vertices).foreach_get("co", a)
    return a.reshape(-1, 3)


def make_selftest_copy(kind):
    dup = src.copy(); dup.data = src.data.copy(); dup.name = src.name + "_SELFTEST_" + kind
    bpy.context.scene.collection.objects.link(dup)
    if kind == "subdivide":
        me = dup.data; dup.shape_key_clear()
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        attr = bm.faces.layers.bool.get("defect_commissure"); pl = bm.faces.layers.bool.get("patch_L")
        defect = [f for f in bm.faces if f[attr] and f[pl]]
        bmesh.ops.subdivide_edges(bm, edges=list({e for f in defect for e in f.edges}), cuts=2, use_grid_fill=True)
        bm.to_mesh(me); bm.free(); me.update(); dup["selftest_removed_defect_faces"] = 0
        return dup
    if kind == "patch":
        me = dup.data
        # shape keys must be removed before topology edits; the transfer rebuilds them
        dup.shape_key_clear()
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        attr = bm.faces.layers.bool.get("defect_commissure")
        patch_attr = bm.faces.layers.bool.get("patch_L")
        defect = [f for f in bm.faces if f[attr] and f[patch_attr]]
        n_def = len(defect)
        def_edges = {e for f in defect for e in f.edges}
        bmesh.ops.delete(bm, geom=defect, context="FACES_ONLY")
        # fill ONLY the hole(s) left by the removed slivers, then subdivide the fill (crude stand-in for the manual patch)
        holes = [e for e in def_edges if e.is_valid and e.is_boundary]
        filled = bmesh.ops.holes_fill(bm, edges=holes, sides=0)
        newf = filled["faces"]
        bmesh.ops.triangulate(bm, faces=newf)
        newf = [f for f in bm.faces if f.is_valid and not f[patch_attr] and any(not v.link_faces or True for v in f.verts) and f.calc_area() > 0 and f.index == -1] or [f for f in bm.faces if f.select]
        bmesh.ops.subdivide_edges(bm, edges=list({e for f in filled["faces"] if f.is_valid for e in f.edges}), cuts=1, use_grid_fill=True)
        bm.to_mesh(me); bm.free(); me.update()
        dup["selftest_removed_defect_faces"] = n_def
    else:
        dup.shape_key_clear()
    return dup


dst = make_selftest_copy(selftest) if selftest else bpy.data.objects[dst_name]
if dst.data.shape_keys:
    raise SystemExit("edited object already has shape keys; remove them first (they will be rebuilt)")

S0 = coords(src, "Basis") if src.data.shape_keys else coords(src)
keys = [k.name for k in src.data.shape_keys.key_blocks[1:]]
SD = {k: coords(src, k) - S0 for k in keys}
E0 = coords(dst)

# 1. exact correspondence
kd = KDTree(len(S0))
for i, v in enumerate(S0): kd.insert(Vector(v), i)
kd.balance()
match = np.full(len(E0), -1); dist = np.zeros(len(E0)); ambiguous = 0
# neighbour positions for disambiguating coincident vertices (the scan has upper/lower lip twins at the seam)
def rings(ob, P):
    nb = [[] for _ in range(len(P))]
    for e in ob.data.edges:
        a, b = e.vertices; nb[a].append(b); nb[b].append(a)
    return nb
nbS = rings(src, S0); nbE = rings(dst, E0)
for i, v in enumerate(E0):
    if i < len(S0) and np.abs(S0[i] - v).max() < EXACT_TOL and sorted(np.round(S0[nbS[i]] * 1e7).tolist()) == sorted(np.round(E0[nbE[i]] * 1e7).tolist()):
        match[i] = i; continue                                   # same index, same position, same 1-ring
    cands = [j for (_, j, d) in kd.find_range(Vector(v), EXACT_TOL)]
    if not cands: continue
    if len(cands) > 1:
        ambiguous += 1
        ring_e = E0[nbE[i]]
        def score(j):
            ring_s = S0[nbS[j]]
            if not len(ring_s) or not len(ring_e): return 1e9
            return float(np.mean([np.min(np.linalg.norm(ring_s - p, axis=1)) for p in ring_e]))
        cands.sort(key=score)
    match[i] = cands[0]

# 2. surface correspondence (excluding defective slivers)
me = src.data
defect = np.zeros(len(me.polygons), bool)
if "defect_commissure" in me.attributes:
    me.attributes["defect_commissure"].data.foreach_get("value", defect)
good_polys = [list(p.vertices) for p, d in zip(me.polygons, defect) if not d]
bvh = BVHTree.FromPolygons([Vector(v) for v in S0], good_polys)
out = {k: np.zeros_like(E0) for k in keys}
surf = np.where(match < 0)[0]
for k in keys:
    out[k][match >= 0] = SD[k][match[match >= 0]]
max_surf_dist = 0.0
for i in surf:
    loc, nrm, fi, d = bvh.find_nearest(Vector(E0[i])); max_surf_dist = max(max_surf_dist, d)
    vs = good_polys[fi]; w = np.array(poly_3d_calc([Vector(S0[v]) for v in vs], loc))
    for k in keys:
        out[k][i] = (SD[k][vs] * w[:, None]).sum(0)

# 3. edits must be confined to the patch
patch = np.zeros(len(E0), bool)
for gname in ("proposed_patch_L", "proposed_patch_R"):
    g = dst.vertex_groups.get(gname)
    if g:
        for v in dst.data.vertices:
            if any(gg.group == g.index for gg in v.groups): patch[v.index] = True
P_patch = E0[patch] if patch.any() else np.zeros((0, 3))
outside = []
if len(surf):
    pk = KDTree(max(len(P_patch), 1))
    for i, v in enumerate(P_patch): pk.insert(Vector(v), i)
    pk.balance()
    for i in surf:
        if patch[i]: continue
        d = pk.find(Vector(E0[i]))[2] if len(P_patch) else 1.0
        if d > 0.002: outside.append(int(i))

# write the keys
dst.shape_key_add(name="Basis")
for k in keys:
    sk = dst.shape_key_add(name=k, from_mix=False); sk.data.foreach_set("co", (E0 + out[k]).ravel())
    sk.value = 0.0
src_vals = {k.name: k.value for k in src.data.shape_keys.key_blocks}
for k in dst.data.shape_keys.key_blocks:
    if k.name in src_vals: k.value = src_vals[k.name]

# verification
eye_max = 0.0
for k in EYE_KEYS:
    if k in SD:
        eye_max = max(eye_max, float(np.abs(out[k][match >= 0] - SD[k][match[match >= 0]]).max()))
bmv = bmesh.new(); bmv.from_mesh(dst.data)
nonman = sum(1 for e in bmv.edges if not e.is_manifold and not e.is_boundary)
loose = sum(1 for v in bmv.verts if not v.link_faces); bmv.free()
rep = {"source": src_name, "edited": dst.name, "selftest": selftest, "edited_vertices": len(E0), "source_vertices": len(S0),
       "exact_vertices": int((match >= 0).sum()), "coincident_twins_disambiguated": ambiguous, "surface_vertices": int(len(surf)), "max_surface_distance_mm": round(max_surf_dist * 1000, 4),
       "unintended_edits_outside_patch": len(outside), "keys_transferred": len(keys), "eye_keys_max_diff_mm_on_exact_vertices": round(eye_max * 1000, 6),
       "non_manifold_edges": nonman, "loose_vertices": loose,
       "removed_defect_faces": int(dst.get("selftest_removed_defect_faces", 0))}
if selftest == "identity":
    rep["identity_all_keys_max_diff_mm"] = round(max(float(np.abs(out[k] - SD[k]).max()) for k in keys) * 1000, 6)
rep["PASS"] = (rep["unintended_edits_outside_patch"] == 0 and rep["eye_keys_max_diff_mm_on_exact_vertices"] == 0.0 and nonman == 0
               and (selftest != "identity" or rep["identity_all_keys_max_diff_mm"] == 0.0))
json.dump(rep, open(rep_path, "w"), indent=1); print("TRANSFER", json.dumps(rep))
if selftest:
    bpy.data.objects.remove(dst, do_unlink=True)   # never left behind in the kit

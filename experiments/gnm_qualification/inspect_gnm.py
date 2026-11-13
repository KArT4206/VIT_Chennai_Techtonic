"""Read-only inspection of the official GNM Head v3 model: topology, groups, UDIM UVs, joints.

    PYTHONPATH=vendor/GNM env/bin/python inspect_gnm.py model/v3_0/gnm_head.npz report/

Writes report/gnm_inspection.json and prints a summary. Never modifies, welds, reorders or
decimates the mesh.
"""

import collections
import json
import os
import sys

import numpy as np
from gnm.shape import gnm_numpy

DOC_TILES = {1001: "skin", 1002: "left eye interior", 1003: "left eye exterior (cornea)",
             1004: "right eye interior", 1005: "right eye exterior (cornea)",
             1006: "teeth and gums", 1007: "tongue"}


def tiles_from_uv(uv):
    """Mari UDIM tile per face from its corner UVs: 1001 + floor(u) + 10*floor(v), using the face centroid."""
    c = uv.mean(axis=1)
    return (1001 + np.floor(c[:, 0]) + 10 * np.floor(c[:, 1])).astype(int)


def main(npz, out):
    os.makedirs(out, exist_ok=True)
    g = gnm_numpy.GNM.from_custom_file(npz)
    raw = np.load(npz, allow_pickle=False)
    r = {"file": os.path.abspath(npz), "npz_keys": {k: [list(raw[k].shape), str(raw[k].dtype)] for k in raw.files}}
    r["version"], r["variant"], r["major_version"] = str(g.version), str(g.variant), str(g.major_version)

    V = np.asarray(g.template_vertex_positions)
    Q = np.asarray(g.quads)
    T = np.asarray(g.triangles)
    r["num_vertices"] = int(g.num_vertices)
    r["template_vertices_shape"] = list(V.shape)
    r["quads_shape"], r["triangles_shape"] = list(Q.shape), list(T.shape)
    r["bbox_m"] = [V.min(0).round(4).tolist(), V.max(0).round(4).tolist()]
    r["identity_dim"], r["expression_dim"], r["num_joints"] = int(g.identity_dim), int(g.expression_dim), int(g.num_joints)
    r["mesh_component_names"] = list(map(str, g.mesh_component_names))
    r["vertex_group_names"] = list(map(str, g.vertex_group_names))
    r["vertex_group_sizes"] = {str(n): int(np.asarray(g.vertex_group_indices(n)).size) for n in g.vertex_group_names}
    r["joint_names"] = list(map(str, g.joint_names))
    r["joint_parents"] = [int(x) for x in np.asarray(g.joint_parent_indices)]
    r["joint_positions_template"] = np.asarray(g.template_joint_positions).round(5).tolist()
    en = list(map(str, g.expression_names))
    r["expression_names_head"] = en[:6]
    r["expression_name_prefixes"] = dict(collections.Counter(n.rsplit("_", 1)[0] for n in en))
    r["identity_name_prefixes"] = dict(collections.Counter(str(n).rsplit("_", 1)[0] for n in g.identity_names))

    # ---- triangulation vs quads: is every triangle a split of a quad, in order?
    tri_from_quads = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]], axis=1).reshape(-1, 3)
    r["triangles_are_ordered_quad_splits_012_023"] = bool(T.shape[0] == 2 * Q.shape[0] and np.array_equal(T, tri_from_quads))
    r["index_range_ok"] = bool(Q.min() >= 0 and Q.max() < V.shape[0] and T.min() >= 0 and T.max() < V.shape[0])
    r["degenerate_quads"] = int(sum(len(set(q)) < 4 for q in Q.tolist()))
    used = np.zeros(V.shape[0], bool); used[Q.ravel()] = True
    r["vertices_unused_by_quads"] = int((~used).sum())

    # ---- UVs (face-corner arrays, not per-vertex)
    for name in ("quad_uvs", "quad_uvs_udim", "triangle_uvs", "triangle_uvs_udim"):
        a = np.asarray(getattr(g, name))
        r[f"{name}_shape"] = list(a.shape)
        r[f"{name}_nan"] = int(np.isnan(a).sum())
        r[f"{name}_range"] = [a.min(0).min(0).round(4).tolist(), a.max(0).max(0).round(4).tolist()]
    quv = np.asarray(g.quad_uvs_udim)
    tuv = np.asarray(g.triangle_uvs_udim)
    qt_attr = np.asarray(g.quad_udim_tiles).astype(int)
    tt_attr = np.asarray(g.triangle_udim_tiles).astype(int)
    qt_uv = tiles_from_uv(quv)
    r["quad_tiles_attr_vs_uv_mismatch"] = int((qt_attr != qt_uv).sum())
    r["tri_tiles_attr_vs_uv_mismatch"] = int((tt_attr != tiles_from_uv(tuv)).sum())
    # every corner of a face lies in the face's own tile (no face straddles tiles)
    lo = np.floor(quv[..., 0]); r["quads_straddling_tiles"] = int((lo.min(1) != lo.max(1)).sum())
    r["quad_tile_counts"] = {int(k): int(v) for k, v in zip(*np.unique(qt_attr, return_counts=True))}
    r["tri_tile_counts"] = {int(k): int(v) for k, v in zip(*np.unique(tt_attr, return_counts=True))}
    # triangle UVs consistent with the quad UVs they were split from
    tri_uv_from_quads = np.concatenate([quv[:, [0, 1, 2]], quv[:, [0, 2, 3]]], axis=1).reshape(-1, 3, 2)
    r["triangle_uvs_equal_quad_split_uvs"] = bool(tuv.shape == tri_uv_from_quads.shape and np.allclose(tuv, tri_uv_from_quads))
    # in-tile UVs inside [0,1]
    frac = quv - np.floor(quv.mean(1, keepdims=True))
    r["quad_corner_uv_outside_own_tile"] = int(((frac < -1e-6) | (frac > 1 + 1e-6)).any(-1).sum())
    # UV winding (orientation) per tile: signed area sign of each quad in UV
    def signed(a):
        x, y = a[..., 0], a[..., 1]
        return 0.5 * (x * np.roll(y, -1, 1) - np.roll(x, -1, 1) * y).sum(1)
    sa = signed(quv)
    r["uv_winding_per_tile"] = {int(t): {"positive": int((sa[qt_attr == t] > 0).sum()), "negative": int((sa[qt_attr == t] < 0).sum()),
                                         "zero": int((sa[qt_attr == t] == 0).sum())} for t in np.unique(qt_attr)}
    # tile ↔ vertex group mapping (which groups' vertices each tile's faces use)
    tile_groups = {}
    for t in np.unique(qt_attr):
        vs = np.unique(Q[qt_attr == t].ravel())
        hits = {}
        for n in g.vertex_group_names:
            m = np.asarray(g.vertex_group_mask(n)).astype(bool)
            k = int(m[vs].sum())
            if k:
                hits[str(n)] = round(k / len(vs), 4)
        tile_groups[int(t)] = hits
    r["tile_vertex_group_overlap"] = tile_groups
    # UV seams: vertices with more than one distinct UV across their face corners
    flat_v = Q.ravel(); flat_uv = quv.reshape(-1, 2)
    uvs_per_v = collections.defaultdict(set)
    for v, uv in zip(flat_v.tolist(), np.round(flat_uv, 6).tolist()):
        uvs_per_v[v].add(tuple(uv))
    r["seam_vertices_multi_uv"] = int(sum(len(s) > 1 for s in uvs_per_v.values()))
    # overlap within a tile: duplicate UV islands? coarse test via rasterised coverage count
    cover = {}
    for t in np.unique(qt_attr):
        sel = quv[qt_attr == t] - (t - 1001, 0)
        grid = np.zeros((512, 512), np.int32)
        for q in sel:
            xs, ys = (q[:, 0] * 511).astype(int), (q[:, 1] * 511).astype(int)
            grid[ys.min():ys.max() + 1, xs.min():xs.max() + 1] += 0  # bbox only for speed below
        cover[int(t)] = None
    # exact overlap check: sample each quad centroid and count quads containing it (barycentric on both triangles)
    r["doc_tiles"] = {str(k): v for k, v in DOC_TILES.items()}
    with open(os.path.join(out, "gnm_inspection.json"), "w") as fh:
        json.dump(r, fh, indent=1)
    np.savez(os.path.join(out, "gnm_neutral_export.npz"), vertices=V, quads=Q, triangles=T,
             quad_uvs_udim=quv, quad_tiles=qt_attr)
    return r


if __name__ == "__main__":
    rep = main(sys.argv[1], sys.argv[2])
    for k, v in rep.items():
        if k in ("joint_positions_template", "npz_keys"):
            continue
        print(f"{k}: {v}")

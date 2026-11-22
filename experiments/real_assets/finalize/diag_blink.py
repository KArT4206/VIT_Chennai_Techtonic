"""Read-only eyelid-closure diagnostics on a PRIVATE web GLB.

    blender -b --factory-startup --python diag_blink.py -- <glb> <out.json> [side=L]

Segments the periorbital skin of one eye into regions (upper/lower margin loops, upper lid, upper fold,
lower lid, inner/outer canthus, orbital ring, brow), then evaluates the blink at 25/50/75/100 %
(including corr_blink_arc_<side> = 4w(1-w) when the file has it) and reports per region:
displacement (mean/max), direction mix (down / up / toward the closure line horizontally / backward),
edge strain (compression = gathering), surface roughness (Laplacian) and eyeball penetration,
plus the upper/lower margin gap, displacement outside the eyelid region and brow movement.
"""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
glb, out = args[:2]; SIDE = args[2] if len(args) > 2 else "L"
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("GNM_Head"))
M = np.array(head.matrix_world); kb = head.data.shape_keys.key_blocks
mats = [m.name for m in head.data.materials]
MM = 1000.0


def arr(k):
    a = np.empty(len(head.data.vertices) * 3); k.data.foreach_get("co", a); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


B = arr(kb[0]); KEYS = {k.name: arr(k) - B for k in kb[1:]}


def vids(prefix):
    s = set()
    for p in head.data.polygons:
        if mats[p.material_index].startswith(prefix): s.update(p.vertices)
    return np.array(sorted(s))


def sphere(P):
    keep = P
    for _ in range(4):
        A = np.c_[2 * keep, np.ones(len(keep))]; b = (keep ** 2).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
        c = x[:3]; r = math.sqrt(x[3] + c @ c); res = np.abs(np.linalg.norm(keep - c, axis=1) - r); keep = keep[res <= np.percentile(res, 80)]
    return c, r


C, R = sphere(B[vids("Eye_" + SIDE)])
sx = 1.0 if SIDE == "L" else -1.0
skin = vids("Skin"); is_skin = np.zeros(len(B), bool); is_skin[skin] = True
polys = [list(p.vertices) for p in head.data.polygons if mats[p.material_index].startswith("Skin")]
bvh = BVHTree.FromPolygons([Vector(v) for v in B], polys)

# opening columns (ray cast from the front: eyeball hit before skin)
def eye_hit(o, d):
    oc = o - C; b = oc @ d; cc = oc @ oc - R * R; disc = b * b - cc
    return None if disc < 0 else -b - math.sqrt(disc)


cols = []
for x in np.linspace(-R * 0.95, R * 0.95, 77):
    def open_at(z):
        o = np.array([C[0] + x, C[1] - 0.1, C[2] + z]); d = np.array([0.0, 1.0, 0.0]); te = eye_hit(o, d)
        if te is None: return False
        hs = bvh.ray_cast(Vector(o), Vector(d), 1.0); return hs[0] is None or te < hs[3] - 1e-5
    z0 = next((z for z in (0.0, -0.001, 0.001, -0.002, 0.002) if open_at(z)), None)
    if z0 is None: continue
    up = z0
    while up < R and open_at(up + 1e-4): up += 1e-4
    lo = z0
    while lo > -R and open_at(lo - 1e-4): lo -= 1e-4
    cols.append((x, up, lo))
XS = np.array([c[0] for c in cols]); UP = np.array([c[1] for c in cols]); LO = np.array([c[2] for c in cols])

rel = B - C; X = rel[:, 0]; Z = rel[:, 2]; F = -rel[:, 1]; lat = X * sx
dsph = np.linalg.norm(rel, axis=1) - R
inx = (X >= XS[0]) & (X <= XS[-1])
zu = np.interp(X, XS, UP); zl = np.interp(X, XS, LO); zmid = (zu + zl) / 2
front = F > 0.25 * R
side = (np.sign(B[:, 0]) == sx)
base = is_skin & side
rim = base & front & (np.abs(dsph) < 0.0015) & inx
reg = {
    "upper_margin_loop": rim & (Z > zmid),
    "lower_margin_loop": rim & (Z <= zmid),
    "upper_lid": base & inx & front & (Z > zu) & (Z <= zu + 0.008) & ~rim,
    "upper_fold": base & inx & front & (Z > zu + 0.008) & (Z <= zu + 0.014),
    "lower_lid": base & inx & front & (Z < zl) & (Z >= zl - 0.007) & ~rim,
    "inner_canthus": base & front & (X * sx < XS.min() * sx if sx > 0 else X * sx < -XS.max()) & (np.abs(Z) < 0.005) & (np.abs(X) < R * 1.25),
    "outer_canthus": base & front & (X * sx > XS.max() * sx if sx > 0 else X * sx > -XS.min()) & (np.abs(Z) < 0.005) & (np.abs(X) < R * 1.4),
}
inner_x = XS.min() if sx > 0 else XS.max()  # nasal side is toward the midline
lid_any = np.zeros(len(B), bool)
for m in reg.values(): lid_any |= m
radial = np.hypot(X, Z)
reg["orbital_ring"] = base & front & (radial < 0.025) & ~lid_any & (Z < 0.014)
reg["brow"] = base & (Z > 0.015) & (Z < 0.032) & (np.abs(X) < 0.025)
reg["outside_eyelid_region"] = is_skin & ~(base & (radial < 0.025) & (Z < 0.032))

# edges among skin vertices near the eye, for strain
E = np.array([e.vertices[:] for e in head.data.edges]); E = E[is_skin[E[:, 0]] & is_skin[E[:, 1]]]
L0 = np.linalg.norm(B[E[:, 0]] - B[E[:, 1]], axis=1)
nb = [[] for _ in range(len(B))]
for a, b in E: nb[a].append(b); nb[b].append(a)


def lap(P, ids):
    return np.array([np.linalg.norm(P[i] - P[nb[i]].mean(0)) if nb[i] else 0 for i in ids])


has_arc = ("corr_blink_arc_" + SIDE) in KEYS
res = {"glb": glb.split("/")[-1], "side": SIDE, "eye_radius_mm": round(R * MM, 2), "arc_corrective": has_arc,
       "opening": {"columns": len(cols), "max_height_mm": round(float((UP - LO).max()) * MM, 2), "upper_margin_z_mm_centre": round(float(np.interp(0, XS, UP)) * MM, 2), "lower_margin_z_mm_centre": round(float(np.interp(0, XS, LO)) * MM, 2)},
       "region_vertex_counts": {k: int(v.sum()) for k, v in reg.items()}, "stages": {}}
lid_band = (base & front & (radial < 0.022))
for w in (0.25, 0.5, 0.75, 1.0):
    D = w * KEYS["blink_" + SIDE] + ((4 * w * (1 - w)) * KEYS["corr_blink_arc_" + SIDE] if has_arc else 0)
    P = B + D; st = {}
    m = np.linalg.norm(D, axis=1)
    for name, mask in reg.items():
        if not mask.any(): continue
        d = D[mask]; mm = m[mask]; big = mm > 1e-5
        e = {"mean_mm": round(float(mm.mean()) * MM, 3), "max_mm": round(float(mm.max()) * MM, 3)}
        if big.any() and name not in ("outside_eyelid_region",):
            dn = d[big] / mm[big, None]
            towards_line = -np.sign(rel[mask][big, 2] - zmid[mask][big]) * dn[:, 2]
            e["dir_mean"] = {"down": round(float((-dn[:, 2]).mean()), 2), "back": round(float((dn[:, 1]).mean()), 2), "toward_closure_line": round(float(towards_line.mean()), 2),
                             "lateral_out": round(float((dn[:, 0] * sx).mean()), 2)}
        st[name] = e
    # strain in the lid band: edge-length ratios
    eb = lid_band[E[:, 0]] & lid_band[E[:, 1]]
    ratio = np.linalg.norm(P[E[eb, 0]] - P[E[eb, 1]], axis=1) / L0[eb]
    st["edge_strain_lid_band"] = {"edges": int(eb.sum()), "min_ratio": round(float(ratio.min()), 3), "p01_ratio": round(float(np.percentile(ratio, 1)), 3),
                                  "frac_compressed_below_0_6": round(float((ratio < 0.6).mean()), 4), "frac_below_0_8": round(float((ratio < 0.8).mean()), 4), "max_ratio": round(float(ratio.max()), 3)}
    # surface roughness: Laplacian magnitude in the upper lid + fold vs rest
    ids = np.where(reg["upper_lid"] | reg["upper_fold"] | reg["lower_lid"])[0]
    st["laplacian_lids_mm"] = {"rest_p99": round(float(np.percentile(lap(B, ids), 99)) * MM, 3), "pose_p99": round(float(np.percentile(lap(P, ids), 99)) * MM, 3), "pose_max": round(float(lap(P, ids).max()) * MM, 3)}
    # penetration of skin that was outside the eyeball at rest
    d0 = np.linalg.norm(B - C, axis=1); d1 = np.linalg.norm(P - C, axis=1); out0 = is_skin & (d0 >= R)
    pen = np.clip(R - d1[out0], 0, None)
    st["eyeball_penetration"] = {"verts": int((pen > 0).sum()), "max_mm": round(float(pen.max()) * MM, 3)}
    # upper/lower margin gap per column
    um = np.where(reg["upper_margin_loop"])[0]; lm = np.where(reg["lower_margin_loop"])[0]
    gaps = []
    for x in XS[3:-3]:
        cu = um[np.abs(X[um] - x) < 0.0008]; cl = lm[np.abs(X[lm] - x) < 0.0008]
        if len(cu) and len(cl):
            pu = P[cu][np.argmin(P[cu][:, 2])]; pl = P[cl][np.argmax(P[cl][:, 2])]
            gaps.append(float(pu[2] - pl[2]))
    gx = [x for x in XS[3:-3]]
    span = XS[-1] - XS[0]
    def third(x):
        t = (x - XS[0]) / span; t = t if sx > 0 else 1 - t  # 0 = nasal (inner), 1 = temporal (outer)
        return "inner" if t < 1 / 3 else ("middle" if t < 2 / 3 else "outer")
    by = {"inner": [], "middle": [], "outer": []}
    for x in XS[1:-1]:
        cu = um[np.abs(X[um] - x) < 0.0008]; cl = lm[np.abs(X[lm] - x) < 0.0008]
        if len(cu) and len(cl):
            pu = P[cu][np.argmin(P[cu][:, 2])]; pl = P[cl][np.argmax(P[cl][:, 2])]; by[third(x)].append(float(pu[2] - pl[2]))
    st["gap_by_region_mm"] = {k: {"open_max": round(max(max(v), 0) * MM, 3), "median": round(float(np.median(v)) * MM, 3), "n": len(v)} for k, v in by.items() if v}
    # corner bump: stretch and curvature in the outer-canthus region
    oc = reg["outer_canthus"] | (base & front & (np.abs(Z) < 0.007) & (np.abs(X - (XS.max() if sx > 0 else XS.min())) < 0.004))
    eo = oc[E[:, 0]] & oc[E[:, 1]]
    if eo.any():
        rr = np.linalg.norm(P[E[eo, 0]] - P[E[eo, 1]], axis=1) / L0[eo]
        ido = np.where(oc)[0]
        st["outer_corner"] = {"edges": int(eo.sum()), "max_stretch": round(float(rr.max()), 3), "min_ratio": round(float(rr.min()), 3),
                              "laplacian_max_mm": round(float(lap(P, ido).max()) * MM, 3), "laplacian_rest_max_mm": round(float(lap(B, ido).max()) * MM, 3)}
    # crease: inward (toward eye centre) movement of the band 5-9 mm above the rest upper margin
    cb = base & inx & front & (Z > zu + 0.005) & (Z < zu + 0.009)
    if cb.any():
        radial_in = -np.sum(D[cb] * (rel[cb] / np.linalg.norm(rel[cb], axis=1)[:, None]), axis=1)
        st["crease_band_inward_mm"] = {"max": round(float(radial_in.max()) * MM, 3), "mean": round(float(radial_in.mean()) * MM, 3)}
    st["margin_vertical_gap_mm"] = {"min": round(min(gaps) * MM, 3), "median": round(float(np.median(gaps)) * MM, 3), "max": round(max(gaps) * MM, 3), "columns": len(gaps)}
    res["stages"][f"{int(w * 100)}%"] = st
# brow landmarks
for nm, (xx, zz) in {"inner_brow": (0.016, 0.021), "outer_brow": (0.040, 0.020)}.items():
    h = bvh.ray_cast(Vector((C[0] - sx * 0.030 + sx * xx, C[1] - 1, C[2] + zz)), Vector((0, 1, 0)), 3)
    if h[0] is None: continue
    from mathutils.interpolate import poly_3d_calc
    v_ = polys[h[2]]; w_ = poly_3d_calc([Vector(B[v]) for v in v_], h[0])
    d = sum(KEYS["blink_" + SIDE][v] * wi for v, wi in zip(v_, w_)) * MM
    res.setdefault("brow_at_full_blink_mm", {})[nm] = [round(float(t), 3) for t in d]
json.dump(res, open(out, "w"), indent=1)
print("DIAG_DONE", out)

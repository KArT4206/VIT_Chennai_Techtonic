"""PRIVATE: Phase 2N.6 facial-detail pass on the web GLB (v1 -> v2). Never overwrites v1.

    blender -b --factory-startup --python build_web_v2.py -- <v1.glb> <v2.glb> <report.json>

1. Lashes: every strand is refitted to the GNM eyelids. The eye opening is found by ray casting from
   the front (eyeball hit before skin = opening). Each strand is classified upper/lower, its root is
   moved onto the anterior lid margin at the same horizontal position (0.5 mm outside the opening
   edge, on the skin), and the strand is rotated rigidly about its root so it grows forward-up
   (upper) or forward-down (lower). Shape, length and count are preserved.
2. brow_furrow_L/R are rebuilt: inner brow moves down and toward the midline with slight bunching;
   the outer brow lowers slightly; lids are protected; each side fades out across the midline.
3. New cheek_raise_L/R: cheek moves up and forward, with gentle lower-lid compression; nose/
   nasolabial area and the eyeball are protected (no vertex may enter the eyeball sphere).
4. All head shape keys are re-transferred to brows and lashes; lash strands are anchored at their
   fitted lid-margin root so they stay attached in every combination.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

src, dst, rep_path = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
bpy.context.view_layer.update()
O = {o.name: o for o in bpy.data.objects}
head = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("GNM_Head"))
brows = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("Brows"))
lashes = next(o for o in O.values() if o.type == "MESH" and o.name.startswith("Lashes"))
rig = next(o for o in O.values() if o.type == "ARMATURE")
for o in (head, brows, lashes):
    assert o.matrix_world == bpy.data.objects[o.name].matrix_world
MM = 1000.0
FWD = np.array([0.0, -1.0, 0.0])  # glTF +Z forward becomes Blender -Y
UP = np.array([0.0, 0.0, 1.0])
report = {}


def world_co(o):
    a = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get("co", a)
    M = np.array(o.matrix_world); return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def to_local(o, P):
    M = np.linalg.inv(np.array(o.matrix_world)); return P @ M[:3, :3].T + M[:3, 3]


def dir_to_local(o, D):
    M = np.linalg.inv(np.array(o.matrix_world)); return D @ M[:3, :3].T


mats = [m.name for m in head.data.materials]
HP = world_co(head)
kb = head.data.shape_keys.key_blocks


def head_vids(prefix):
    s = set()
    for p in head.data.polygons:
        if mats[p.material_index].startswith(prefix):
            s.update(p.vertices)
    return np.array(sorted(s))


skin_ids = head_vids("Skin")
is_skin = np.zeros(len(HP), bool); is_skin[skin_ids] = True
skin_polys = [list(p.vertices) for p in head.data.polygons if mats[p.material_index].startswith("Skin")]
skin_bvh = BVHTree.FromPolygons([Vector(v) for v in HP], skin_polys)


def sphere(P):
    keep = P
    for _ in range(4):
        A = np.c_[2 * keep, np.ones(len(keep))]; b = (keep ** 2).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
        c = x[:3]; r = math.sqrt(x[3] + c @ c)
        res = np.abs(np.linalg.norm(keep - c, axis=1) - r); keep = keep[res <= np.percentile(res, 80)]
    return c, r


EYE = {s: sphere(HP[head_vids("Eye_" + s)]) for s in "LR"}  # L = +X (character's left)
MID_Z = (EYE["L"][0][2] + EYE["R"][0][2]) / 2


def eye_hit(c, r, o, d):
    oc = o - c; b = oc @ d; cc = oc @ oc - r * r; disc = b * b - cc
    return None if disc < 0 else -b - math.sqrt(disc)


def front_point(x, z, side_c=None):
    """Skin surface point seen from the front at world (x, z)."""
    o = Vector((x, -1.0, z)); h = skin_bvh.ray_cast(o, Vector((0, 1, 0)), 3.0)
    return None if h[0] is None else np.array(h[0])


# ---------- 1. eye opening and lid margins ----------
def opening(side):
    c, r = EYE[side]; step = 0.0001
    out = []
    for x in np.linspace(-r * 0.95, r * 0.95, 77):
        def open_at(z):
            o = np.array([c[0] + x, c[1] - 0.1, c[2] + z]); d = np.array([0.0, 1.0, 0.0])
            te = eye_hit(c, r, o, d)
            if te is None: return False
            hs = skin_bvh.ray_cast(Vector(o), Vector(d), 1.0)
            return hs[0] is None or te < hs[3] - 1e-5
        if not open_at(0.0) and not open_at(-0.001) and not open_at(0.001):
            continue
        z0 = 0.0 if open_at(0.0) else (-0.001 if open_at(-0.001) else 0.001)
        up = z0
        while up < r and open_at(up + step): up += step
        lo = z0
        while lo > -r and open_at(lo - step): lo -= step
        pu = front_point(c[0] + x, c[2] + up + 0.0005); pl = front_point(c[0] + x, c[2] + lo - 0.0005)
        if pu is not None and pl is not None:
            out.append((x, up, lo, pu, pl))
    return out


OPEN = {s: opening(s) for s in "LR"}
report["opening"] = {s: {"columns": len(OPEN[s]), "x_range_mm": [round(OPEN[s][0][0] * MM, 1), round(OPEN[s][-1][0] * MM, 1)],
                         "max_height_mm": round(max(u - l for _, u, l, _, _ in OPEN[s]) * MM, 2)} for s in "LR"}


def margin_point(side, x_rel, upper):
    cols = OPEN[side]; xs = np.array([c[0] for c in cols])
    x_rel = float(np.clip(x_rel, xs[0], xs[-1])); i = int(np.searchsorted(xs, x_rel)); i = min(max(i, 1), len(xs) - 1)
    t = (x_rel - xs[i - 1]) / (xs[i] - xs[i - 1] + 1e-12)
    k = 3 if upper else 4
    return cols[i - 1][k] * (1 - t) + cols[i][k] * t


# ---------- lash strands ----------
LP0 = world_co(lashes)
n = len(LP0); par = list(range(n))


def f(a):
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a


for e in lashes.data.edges:
    a, b = f(e.vertices[0]), f(e.vertices[1])
    if a != b: par[a] = b
isl = np.array([f(i) for i in range(n)])
groups = {}
for i, g in enumerate(isl): groups.setdefault(g, []).append(i)
dist0 = np.array([skin_bvh.find_nearest(Vector(p))[3] for p in LP0])


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b); v = np.cross(a, b); s = np.linalg.norm(v); cth = a @ b
    if s < 1e-9: return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - cth) / s ** 2)


LP = LP0.copy(); strand_root = {}; before = {"upper_pointing_down": 0, "lower_pointing_up": 0, "upper": 0, "lower": 0}
moved = []
for g, ix in groups.items():
    ix = np.array(ix); r_i = ix[np.argmin(dist0[ix])]
    root = LP0[r_i]; tip = LP0[ix[np.argmax(np.linalg.norm(LP0[ix] - root, axis=1))]]
    side = "L" if root[0] > 0 else "R"; c, rad = EYE[side]
    upper = (root[2] - c[2]) > 0
    before["upper" if upper else "lower"] += 1
    dz = tip[2] - root[2]
    if upper and dz < 0: before["upper_pointing_down"] += 1
    if not upper and dz > 0: before["lower_pointing_up"] += 1
    target = margin_point(side, root[0] - c[0], upper)
    out_v = UP if upper else -UP
    fu = float(os.environ.get("LASH_UP_FWD", "0.80")); fl = float(os.environ.get("LASH_LO_FWD", "0.88"))
    want = fu * FWD + math.sqrt(1 - fu * fu) * out_v if upper else fl * FWD + math.sqrt(1 - fl * fl) * out_v
    # fan: lashes toward the corners lean outward (laterally), as real lashes do
    cols = OPEN[side]; half = max(abs(cols[0][0]), abs(cols[-1][0])) + 1e-9
    lat = np.array([1.0 if side == "L" else -1.0, 0, 0]) * np.clip((root[0] - c[0]) / half, -1, 1)
    want = want + float(os.environ.get("LASH_FAN", "0.45")) * lat; want = want / np.linalg.norm(want)
    R = rot_between(tip - root, want)
    Q = (LP0[ix] - root) @ R.T  # chord now along `want`
    # twist about the chord so the strand's bulge points forward (away from the eyeball)
    wn = want / np.linalg.norm(want); perp = Q - np.outer(Q @ wn, wn); j = int(np.argmax(np.linalg.norm(perp, axis=1)))
    bulge = perp[j]; gdir = {"fwd": FWD, "out": out_v, "back": -FWD}.get(os.environ.get("LASH_BULGE", "out"))
    goal = (gdir - (gdir @ wn) * wn) if gdir is not None else np.zeros(3)
    if np.linalg.norm(bulge) > 1e-6 and np.linalg.norm(goal) > 1e-6:
        b = bulge / np.linalg.norm(bulge); gl = goal / np.linalg.norm(goal)
        ang = math.atan2(np.cross(b, gl) @ wn, b @ gl)
        K = np.array([[0, -wn[2], wn[1]], [wn[2], 0, -wn[0]], [-wn[1], wn[0], 0]])
        Rt = np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K
        Q = Q @ Rt.T
    LP[ix] = Q + target
    strand_root[g] = (r_i, target, upper, side)
    moved.append(np.linalg.norm(target - root) * MM)
report["lashes_before"] = before
report["lash_root_move_mm"] = {"p50": round(float(np.median(moved)), 2), "p90": round(float(np.percentile(moved, 90)), 2), "max": round(float(max(moved)), 2)}

# ---------- 2/3. new head shape keys ----------
basis = np.empty(len(HP) * 3); kb[0].data.foreach_get("co", basis); basis = basis.reshape(-1, 3)
M3 = np.array(head.matrix_world)[:3, :3]


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


def gauss(P, centre, sigma):
    return np.exp(-np.sum((P - centre) ** 2, axis=1) / (2 * sigma ** 2))


def eye_guard(P, D):
    """No vertex that starts outside an eyeball may end inside it (+0.25 mm)."""
    D = D.copy()
    for s in "LR":
        c, r = EYE[s]; lim = r + 0.00025
        P1 = P + D; d0 = np.linalg.norm(P - c, axis=1); d1 = np.linalg.norm(P1 - c, axis=1)
        bad = (d0 >= lim) & (d1 < lim)
        if bad.any():
            P1[bad] = c + (P1[bad] - c) / d1[bad, None] * lim; D[bad] = P1[bad] - P[bad]
    return D


def set_key(name, D_world):
    D_local = D_world @ np.linalg.inv(M3).T
    k = kb.get(name) or head.shape_key_add(name=name, from_mix=False)
    k.data.foreach_set("co", (basis + D_local).ravel())


new_keys = {}
old_furrow = {}
for s, sx in (("L", 1.0), ("R", -1.0)):
    old = np.empty(len(HP) * 3); kb["brow_furrow_" + s].data.foreach_get("co", old)
    old_furrow[s] = (old.reshape(-1, 3) - basis) @ M3.T
    # brow furrow (corrugator): inner brow down + toward midline, slight forward bunching
    inner = front_point(sx * 0.016, MID_Z + 0.021); outer = front_point(sx * 0.040, MID_Z + 0.020)
    lid_protect = smooth(MID_Z + 0.009, MID_Z + 0.015, HP[:, 2])
    side_w = smooth(-0.004, 0.006, sx * HP[:, 0])
    w_in = gauss(HP, inner, 0.009) * lid_protect * side_w * is_skin
    w_out = gauss(HP, outer, 0.010) * lid_protect * side_w * is_skin
    D = (w_in[:, None] * np.array([-sx * 0.0020, -0.0004, -0.0022]) + w_out[:, None] * np.array([0, 0, -0.0005]))
    new_keys["brow_furrow_" + s] = eye_guard(HP, D)
    # cheek raise: cheek up and forward, gentle lower-lid compression, nose protected
    cheek = front_point(sx * 0.034, MID_Z - 0.024); lid = front_point(EYE[s][0][0], EYE[s][0][2] - 0.0085)
    nose_guard = smooth(0.014, 0.022, sx * HP[:, 0]); jaw_guard = smooth(MID_Z - 0.050, MID_Z - 0.036, HP[:, 2])
    above_guard = 1 - smooth(MID_Z + 0.000, MID_Z + 0.006, HP[:, 2])
    w_c = gauss(HP, cheek, 0.011) * nose_guard * jaw_guard * is_skin
    w_l = gauss(HP, lid, 0.005) * above_guard * is_skin
    D = w_c[:, None] * np.array([0, -0.0012, 0.0026]) + w_l[:, None] * np.array([0, -0.0002, 0.0009])
    new_keys["cheek_raise_" + s] = eye_guard(HP, D)
for k, D in new_keys.items():
    set_key(k, D)
    m = np.linalg.norm(D, axis=1); pk = int(m.argmax())
    report.setdefault("new_head_keys", {})[k] = {"max_mm": round(float(m.max()) * MM, 2), "peak_vertex_rel_mid_mm": [round(float(v) * MM, 1) for v in (HP[pk] - np.array([0, EYE['L'][0][1], MID_Z]))], "verts_over_0_1mm": int((m > 1e-4).sum())}
for s in "LR":
    m = np.linalg.norm(old_furrow[s], axis=1); pk = int(m.argmax())
    report.setdefault("old_furrow", {})[s] = {"max_mm": round(float(m.max()) * MM, 2), "peak_vertex_rel_mid_mm": [round(float(v) * MM, 1) for v in (HP[pk] - np.array([0, EYE['L'][0][1], MID_Z]))],
                                              "peak_direction": [round(float(v), 2) for v in old_furrow[s][pk] / (m[pk] + 1e-12)]}

# ---------- Phase 2N.6A: rotational eyelid closure (BLINK_MODEL=arc; default "orig" reproduces v2) ----------
BLINK_MODEL = os.environ.get("BLINK_MODEL", "orig")
if BLINK_MODEL == "arc":
    MEET = float(os.environ.get("LID_MEET", "0.22"))       # share of the opening closed by the lower lid
    OVER = float(os.environ.get("LID_OVERLAP_MM", "0.0")) / 1000.0  # extra travel so the margins touch
    H_FOLD = float(os.environ.get("LID_FOLD_MM", "7.5")) / 1000.0
    H_LOW = float(os.environ.get("LID_LOW_MM", "4.5")) / 1000.0

    def rotx(P, c, ang):
        """Rotate points about the X axis through c; +ang moves front points downward along the eyeball."""
        rel = P - c; ca = np.cos(ang); sa = np.sin(ang); out = rel.copy()
        out[:, 1] = rel[:, 1] * ca - rel[:, 2] * sa; out[:, 2] = rel[:, 1] * sa + rel[:, 2] * ca
        return out + c

    report["blink_model"] = {"model": "arc", "meet_share_lower": MEET, "overlap_mm": OVER * MM, "fold_falloff_mm": H_FOLD * MM, "lower_falloff_mm": H_LOW * MM, "sides": {}}
    for s, sx in (("L", 1.0), ("R", -1.0)):
        c, r = EYE[s]; cols = OPEN[s]
        xs = np.array([q[0] for q in cols]); zu_c = np.array([q[1] for q in cols]); zl_c = np.array([q[2] for q in cols])
        el = lambda p: math.atan2(p[2] - c[2], -(p[1] - c[1]))           # elevation of a skin point seen from the eye centre
        phu = np.array([el(q[3]) for q in cols]); phl = np.array([el(q[4]) for q in cols])
        rad_u = np.array([np.linalg.norm(q[3] - c) for q in cols])
        phm = phl + MEET * (phu - phl)
        rot_u = (phu - phm) + OVER / rad_u                                  # downward roll of the upper lid
        rot_l = -(phm - phl)                                                # upward roll of the lower lid
        rel = HP - c; xr = rel[:, 0]; z = rel[:, 2]; fw = -rel[:, 1]
        sidem = (np.sign(HP[:, 0]) == sx) & is_skin
        zu = np.interp(xr, xs, zu_c); zl = np.interp(xr, xs, zl_c); zmid = (zu + zl) / 2
        TI = float(os.environ.get("TAPER_IN_MM", "1.5")) / 1000.0; TO = float(os.environ.get("TAPER_OUT_MM", "2.5")) / 1000.0
        taper = smooth(xs[0] - TO, xs[0] + TI, xr) * (1 - smooth(xs[-1] - TI, xs[-1] + TO, xr))
        frontw = smooth(-0.3 * r, 0.15 * r, fw)
        up = z >= zmid
        wu = 1 - smooth(0.0005, H_FOLD, z - zu)
        wl = 1 - smooth(0.0005, H_LOW, zl - z)
        ang = np.where(up, wu * np.interp(xr, xs, rot_u), wl * np.interp(xr, xs, rot_l)) * taper * frontw * sidem
        D1 = rotx(HP, c, ang) - HP; Dh = rotx(HP, c, ang / 2) - HP
        # ---- Phase 2N.6B refinement (BLINK_REFINE=1): additive, linear in blink weight; rotation untouched ----
        if os.environ.get("BLINK_REFINE") == "1":
            # (0) margin meeting: per column, measure the remaining opening between the actual margin
            #     vertices after rotation and add just that much extra upper-lid roll (no global collapse)
            if os.environ.get("GAP_CLOSE", "1") == "1":
                elev = lambda P: np.arctan2(P[:, 2] - c[2], -(P[:, 1] - c[1]))
                P1 = HP + D1; dsph = np.linalg.norm(rel, axis=1) - r
                rim = sidem & (fw > 0.25 * r) & (np.abs(dsph) < 0.0015)
                extra = np.zeros(len(xs))
                for i, xv in enumerate(xs):
                    col = rim & (np.abs(xr - xv) < 0.0008)
                    uu = col & (z > zmid); ll = col & (z <= zmid)
                    if uu.any() and ll.any():
                        g = elev(P1[uu]).min() - elev(P1[ll]).max()   # >0: still open (radians)
                        extra[i] = max(0.0, g) + float(os.environ.get("GAP_OVERLAP_MM", "0.15")) / 1000.0 / r * (g > 0)
                extra = np.convolve(np.pad(extra, 2, mode="edge"), np.ones(5) / 5, mode="valid")  # smooth along the lid
                ang2 = up * wu * np.interp(xr, xs, extra) * taper * frontw * sidem
                Dg = rotx(HP + D1, c, ang2) - (HP + D1)
                report.setdefault("gap_close", {})[s] = {"extra_roll_deg_max": round(float(np.degrees(extra.max())), 2), "columns_adjusted": int((extra > 1e-4).sum())}
            else:
                Dg = np.zeros_like(HP)
            Dref = Dg.copy()
            # (a) upper-lid crease: tuck the band ~H above the rest margin toward the eyeball centre
            CH = float(os.environ.get("CREASE_H_MM", "6.0")) / 1000.0; CS = float(os.environ.get("CREASE_SIG_MM", "1.3")) / 1000.0
            CD = float(os.environ.get("CREASE_DEPTH_MM", "0.7")) / 1000.0
            cw = np.exp(-((z - zu - CH) ** 2) / (2 * CS ** 2)) * taper * frontw * sidem * (z > zu)
            rn = rel / np.linalg.norm(rel, axis=1)[:, None]
            Dref += -cw[:, None] * CD * rn
            D1c = D1 + Dref
            # (b) corners: diffuse the closure displacement across the canthus so both lids blend into the corner
            CR = float(os.environ.get("CORNER_R_MM", "4.0")) / 1000.0; IT = int(os.environ.get("CORNER_ITERS", "40"))
            mask = np.zeros(len(HP))
            for xe in (xs[0], xs[-1]):
                dd = np.hypot(xr - xe, z - (np.interp(xe, xs, zu_c) + np.interp(xe, xs, zl_c)) / 2)
                mask = np.maximum(mask, 1 - smooth(0.4 * CR, CR, dd))
            mask *= sidem * frontw
            # keep the lid margins where the rotation put them: smooth only skin away from the eyeball surface
            if os.environ.get("CORNER_KEEP_MARGIN", "1") == "1":
                mask *= smooth(0.0012, 0.0030, np.linalg.norm(rel, axis=1) - r)
            ed = np.array([e.vertices[:] for e in head.data.edges]); ed = ed[(mask[ed[:, 0]] > 0) | (mask[ed[:, 1]] > 0)]
            Ds = D1c.copy()
            for _ in range(IT):
                acc = np.zeros_like(Ds); cnt = np.zeros(len(HP))
                np.add.at(acc, ed[:, 0], Ds[ed[:, 1]]); np.add.at(acc, ed[:, 1], Ds[ed[:, 0]])
                np.add.at(cnt, ed[:, 0], 1); np.add.at(cnt, ed[:, 1], 1)
                avg = np.where(cnt[:, None] > 0, acc / np.maximum(cnt, 1)[:, None], Ds)
                Ds = Ds + 0.5 * mask[:, None] * (avg - Ds)
            Dref = Ds - D1
            # never into the eyeball
            Dref = eye_guard(HP, D1 + Dref) - D1
            report.setdefault("blink_refine", {})[s] = {"verts_changed": int((np.linalg.norm(Dref, axis=1) > 1e-5).sum()),
                                                       "max_change_mm": round(float(np.linalg.norm(Dref, axis=1).max()) * MM, 3),
                                                       "params": {"crease_h": CH * MM, "crease_sigma": CS * MM, "crease_depth": CD * MM, "corner_r": CR * MM, "iters": IT, "taper_in": TI * MM, "taper_out": TO * MM}}
            D1 = D1 + Dref; Dh = Dh + 0.5 * Dref  # refinement is linear in weight: the arc corrective is unchanged
        set_key("blink_" + s, D1)
        set_key("corr_blink_arc_" + s, Dh - 0.5 * D1)
        # fit of the 4w(1-w) in-between against the true arc at 25 % / 75 %
        err = {}
        for wq in (0.25, 0.75):
            true = rotx(HP, c, ang * wq) - HP; approx = wq * D1 + 4 * wq * (1 - wq) * (Dh - 0.5 * D1)
            err[f"{int(wq * 100)}%"] = round(float(np.linalg.norm(true - approx, axis=1).max()) * MM, 4)
        report["blink_model"]["sides"][s] = {"verts_moving": int((np.abs(ang) > 1e-4).sum()), "upper_roll_deg_max": round(float(np.degrees(rot_u.max())), 2),
                                             "lower_roll_deg_max": round(float(np.degrees(-rot_l.min())), 2), "inbetween_fit_error_mm": err}

# ---------- Phase 2N.7: reusable mouth / lip / jaw controls (MOUTH=1) ----------
if os.environ.get("MOUTH") == "1":
    MID = np.array([0.0, EYE["L"][0][1] * 0.5 + EYE["R"][0][1] * 0.5, MID_Z]); MID[0] = (EYE["L"][0][0] + EYE["R"][0][0]) / 2
    REL = HP - MID; X, Yb, Z = REL[:, 0], REL[:, 1], REL[:, 2]; FWD_ = -Yb   # forward = -y
    teeth_ids = head_vids("Teeth"); tongue_ids = head_vids("Tongue")
    is_tooth = np.zeros(len(HP), bool); is_tooth[teeth_ids] = True; is_tongue = np.zeros(len(HP), bool); is_tongue[tongue_ids] = True
    # teeth: classify whole connected pieces (a height cut would split single teeth)
    tpar = {int(v): int(v) for v in teeth_ids}
    def tf(a):
        while tpar[a] != a: tpar[a] = tpar[tpar[a]]; a = tpar[a]
        return a
    for e in head.data.edges:
        u, w = e.vertices
        if u in tpar and w in tpar:
            ru, rw = tf(u), tf(w)
            if ru != rw: tpar[ru] = rw
    tcomp = {}
    for v in teeth_ids: tcomp.setdefault(tf(int(v)), []).append(int(v))
    lower_tooth = np.zeros(len(HP), bool); tooth_split = []
    for vs in tcomp.values():
        zc_ = float(Z[vs].mean()); lo = zc_ < -0.0665
        if lo: lower_tooth[vs] = True
        tooth_split.append((len(vs), round(zc_ * MM, 1), "lower" if lo else "upper"))
    # lip line (stomion) per x from front ray casts: most posterior front-surface point (or opening) between -55 and -88 mm
    # lip line: start at the midline and track outward, searching only +-2.5 mm around the previous row
    def profile(xv, z0, z1):
        out = []
        for zv in np.arange(z0, z1, -0.00025):
            h = skin_bvh.ray_cast(Vector((MID[0] + xv, MID[1] - 1.0, MID[2] + zv)), Vector((0, 1, 0)), 3.0)
            out.append((zv, -1.0 if h[0] is None else -(h[0][1] - MID[1])))
        return np.array(out)
    pr = profile(0.0, -0.055, -0.080); zc = pr[int(np.argmin(pr[:, 1])), 0]
    xs_m = np.arange(-0.032, 0.0321, 0.001); line = np.zeros(len(xs_m)); depth = np.zeros(len(xs_m))
    i0 = int(np.argmin(np.abs(xs_m)))
    for rng in (range(i0, len(xs_m)), range(i0, -1, -1)):
        zp = zc
        for i in rng:
            pr = profile(xs_m[i], zp + 0.0025, zp - 0.0025)
            j = int(np.argmin(pr[:, 1])); line[i] = pr[j, 0]; zp = pr[j, 0]
            wide = profile(xs_m[i], zp + 0.004, zp - 0.004); depth[i] = np.max(wide[:, 1]) - pr[j, 1]
    deep = depth > 0.0012
    # corner = outermost x (each side) still showing a lip crease, contiguous from the midline
    cx = []
    for rng in (range(i0, len(xs_m)), range(i0, -1, -1)):
        last = xs_m[i0]
        for i in rng:
            if not deep[i]: break
            last = xs_m[i]
        cx.append(abs(last))
    corner_x = float(np.mean(cx)) + 0.001
    line = np.where(np.abs(xs_m) <= corner_x + 0.003, line, np.interp(np.sign(xs_m) * (corner_x + 0.003), xs_m, line))
    line_s = np.convolve(np.pad(line, 3, mode="edge"), np.ones(7) / 7, mode="valid")
    zl = np.interp(X, xs_m, line_s)                 # lip line height under each vertex
    dz = Z - zl
    lipfront = smooth(0.006, 0.020, FWD_ + 0.0)     # front of the face (fwd > ~0 relative to eyes)
    skinw = is_skin.astype(float)
    report["mouth"] = {"corner_x_each_side_mm": [round(v * MM, 1) for v in cx], "corner_x_mm": round(corner_x * MM, 1), "lip_line_centre_mm": round(float(np.interp(0, xs_m, line_s)) * MM, 1),
                       "lip_line_at_corner_mm": round(float(np.interp(corner_x, xs_m, line_s)) * MM, 1)}
    # region weights (smooth, distance based)
    mouth_r = np.hypot(X / (corner_x + 0.006), dz / 0.016)          # ~1 at the lip boundary ellipse
    lips_w = (1 - smooth(0.7, 1.15, mouth_r)) * skinw * lipfront
    up_lip = lips_w * smooth(-0.0010, 0.0015, dz); lo_lip = lips_w * (1 - smooth(-0.0015, 0.0010, dz))

    def side(sx):  # 1 on that side, 0 on the other, 0.5 on the midline (L + R = symmetric)
        return smooth(-0.006, 0.006, sx * X)

    def corner_w(sx, sig):
        c = np.array([sx * corner_x, 0, 0]); d = np.hypot(X - c[0], (Z - np.interp(sx * corner_x, xs_m, line_s)))
        return np.exp(-(d ** 2) / (2 * sig ** 2)) * skinw * smooth(-0.005, 0.010, FWD_)

    keys = {}
    for sname, sx in (("L", 1.0), ("R", -1.0)):
        sd = side(sx); out_ = np.array([sx, 0, 0])
        # smile (zygomaticus): corner up / back / out; cheek mass up and forward above the corner
        cw = corner_w(sx, 0.011)
        cheek = np.exp(-((X - sx * (corner_x + 0.012)) ** 2 + (Z - (np.interp(sx * corner_x, xs_m, line_s) + 0.018)) ** 2) / (2 * 0.012 ** 2)) * skinw * smooth(-0.005, 0.010, FWD_)
        nose_guard = smooth(0.006, 0.014, np.abs(X))
        cw2 = corner_w(sx, 0.009); lipspread = lips_w * sd * smooth(0.25, 0.9, np.abs(X) / corner_x)
        D = cw2[:, None] * (0.0042 * out_ + np.array([0, 0.0022, 0.0055])) + lipspread[:, None] * (0.0020 * out_ + np.array([0, 0.0010, 0.0015])) \
            + (cheek * nose_guard)[:, None] * np.array([0, -0.0014, 0.0026])
        keys["mouth_smile_" + sname] = D
        # frown (depressor anguli oris): corner down and slightly out
        keys["mouth_frown_" + sname] = cw[:, None] * (0.0010 * out_ + np.array([0, 0.0004, -0.0034]))
        # upper lip raise (levator labii): upper lip up, slight eversion forward; nose base protected
        ul = up_lip * sd * (1 - 0.6 * smooth(0.6, 1.0, np.abs(X) / (corner_x + 1e-6)))
        keys["upper_lip_raise_" + sname] = ul[:, None] * np.array([0, -0.0006, 0.0032])
        # lower lip depress (depressor labii): lower lip down and slightly forward
        ll = lo_lip * sd * (1 - 0.6 * smooth(0.6, 1.0, np.abs(X) / (corner_x + 1e-6)))
        keys["lower_lip_depress_" + sname] = ll[:, None] * np.array([0, -0.0008, -0.0034])
        # lip press: both lips toward the line, slightly back, corners in a little
        pw = lips_w * sd
        keys["lips_press_" + sname] = pw[:, None] * np.stack([-0.0006 * np.sign(X) * smooth(0.6, 1.0, np.abs(X) / corner_x), 0.0015 * (1 - smooth(0.004, 0.010, np.abs(dz))), -np.sign(dz) * np.minimum(0.40 * np.abs(dz), 0.0030)], 1)
        # pucker: lips toward the centre and forward (kiss / purse)
        pk = lips_w * sd
        keys["lips_pucker_" + sname] = pk[:, None] * np.stack([-0.30 * X, np.full(len(X), -0.0045), -0.25 * dz], 1)
        # pout: lower lip forward and rolled out, corners slightly down
        po = lo_lip * sd
        keys["lip_pout_" + sname] = po[:, None] * np.array([0, -0.0035, -0.0008]) + (cw * 0.5)[:, None] * np.array([0, 0, -0.0012])
    # jaw open: rotate the mandible region about a hinge axis near the TMJ
    HINGE = MID + np.array([0.0, 0.072, -0.030])            # behind and below the eyes
    JAW_DEG = float(os.environ.get("JAW_DEG", "14"))
    rel_h = HP - HINGE
    # per-x lip line at the front, rising toward the hinge further back
    t_front = smooth(0.020, 0.075, -rel_h[:, 1])
    zline = (1 - t_front) * (-0.012) + t_front * (zl - (HINGE[2] - MID[2]))   # relative to the hinge
    # lips are parted at rest: a tight boundary in the middle, softer toward and beyond the corners
    cornerness = smooth(corner_x - 0.006, corner_x + 0.004, np.abs(X))
    lo_b = -0.0012 - 0.0030 * cornerness; hi_b = 0.0004 + 0.0040 * cornerness
    jw = 1 - smooth(lo_b, hi_b, rel_h[:, 2] - zline)
    # inside the mouth the lips curl back (and the lower lip rests on the upper incisors): classify the
    # lip surfaces by mesh connectivity. Cut out the corners and the deep oral cavity; what remains of the
    # lip region splits into an upper and a lower connected piece.
    zone = is_skin & (np.abs(X) < corner_x - 0.0035) & (np.abs(dz) < 0.016) & (FWD_ > float(os.environ.get("LIP_DEPTH_CUT_MM", "28")) / 1000.0)
    zid = np.where(zone)[0]; zpos = {v: i for i, v in enumerate(zid)}; parent = list(range(len(zid)))
    def fnd(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for e in head.data.edges:
        u, w = e.vertices
        if u in zpos and w in zpos:
            ru, rw = fnd(zpos[u]), fnd(zpos[w])
            if ru != rw: parent[ru] = rw
    comp = np.array([fnd(i) for i in range(len(zid))])
    seed_up = zone & (dz > 0.004) & (np.abs(X) < 0.010); seed_lo = zone & (dz < -0.004) & (np.abs(X) < 0.010)
    cu = set(comp[[zpos[v] for v in np.where(seed_up)[0]]]); cl = set(comp[[zpos[v] for v in np.where(seed_lo)[0]]])
    report["mouth"]["lip_split"] = {"zone_verts": len(zid), "components": len(set(comp)), "upper_comps": len(cu), "lower_comps": len(cl), "shared": len(cu & cl)}
    lower_piece = np.array([c in cl and c not in cu for c in comp]); upper_piece = np.array([c in cu and c not in cl for c in comp])
    jw[zid[lower_piece]] = np.maximum(jw[zid[lower_piece]], 1.0)
    jw[zid[upper_piece]] = 0.0
    inner = np.zeros(1)
    report["mouth"]["inner_lip_vertices_reassigned"] = int(lower_piece.sum() + upper_piece.sum())
    report["mouth"]["teeth_pieces"] = sorted(tooth_split, key=lambda t: -t[0])
    if os.environ.get("MOUTH_V2") == "1":
        # deeper inner-lip mucosa (behind the connectivity cut): assign by proximity to the gum arches
        from mathutils.kdtree import KDTree
        def kd_(ids):
            t = KDTree(len(ids))
            for i in ids: t.insert(Vector(HP[i]), int(i))
            t.balance(); return t
        big = [vs for vs in tcomp.values() if len(vs) > 300]
        gl = [vs for vs in big if Z[vs].mean() < -0.0665]; gu = [vs for vs in big if Z[vs].mean() >= -0.0665]
        if gl and gu:
            tu = kd_(np.array(gu[0])); tl = kd_(np.array(gl[0]))
            cut = float(os.environ.get("LIP_DEPTH_CUT_MM", "28")) / 1000.0
            deep = np.where(is_skin & (np.abs(X) < corner_x + 0.002) & (np.abs(dz) < 0.022) & (FWD_ <= cut) & (FWD_ > -0.010))[0]
            du_ = np.array([tu.find(Vector(HP[i]))[2] for i in deep]); dl_ = np.array([tl.find(Vector(HP[i]))[2] for i in deep])
            near = 1 - smooth(0.006, 0.012, np.minimum(du_, dl_))
            jw[deep] = (1 - near) * jw[deep] + near * smooth(-0.0015, 0.0015, du_ - dl_)
            report["mouth"]["deep_mucosa_assigned"] = {"verts": int((near > 0.5).sum()), "to_jaw": int(((near > 0.5) & (du_ > dl_)).sum())}
        # any oral skin behind the lip front and below the upper incisal edge belongs to the mandible
        up_inc = (~lower_tooth) & is_tooth & (np.abs(X) < 0.012) & np.isin(np.arange(len(HP)), [v for vs in tcomp.values() if len(vs) <= 300 for v in vs])
        inc_z = float(Z[up_inc].min()) if up_inc.any() else -0.066
        # (the lips part ABOVE the upper incisal edge, so the split is by side of the lip line, not by height)
        oral = is_skin & (np.abs(X) < corner_x - 0.008) & (FWD_ < float(os.environ.get("ORAL_FRONT_MM", "33")) / 1000.0) & (FWD_ > -0.030) & (dz < 0.004) & (Z > inc_z - 0.030)
        wo = 1 - smooth(-0.0015, 0.0005, dz)
        jw = np.where(oral, np.maximum(jw, wo), jw)
        report["mouth"]["oral_mucosa_below_incisal"] = {"upper_incisal_rel_eyes_mm": round(inc_z * MM, 1), "verts": int(oral.sum())}
    # corners: diffuse the jaw weight so the lips stretch smoothly where they join
    fixed = np.zeros(len(HP), bool); fixed[zid[lower_piece | upper_piece]] = True
    band = is_skin & ~fixed & (np.abs(X) > corner_x - float(os.environ.get("JAW_BAND_IN_MM", "14")) / 1000.0) & (np.abs(X) < corner_x + 0.016) & (np.abs(dz) < 0.016)
    edl = np.array([e.vertices[:] for e in head.data.edges]); edl = edl[band[edl[:, 0]] | band[edl[:, 1]]]
    edl = edl[is_skin[edl[:, 0]] & is_skin[edl[:, 1]]]
    for _ in range(int(os.environ.get("JAW_CORNER_ITERS", "300"))):
        acc = np.zeros(len(HP)); cnt = np.zeros(len(HP))
        np.add.at(acc, edl[:, 0], jw[edl[:, 1]]); np.add.at(acc, edl[:, 1], jw[edl[:, 0]])
        np.add.at(cnt, edl[:, 0], 1); np.add.at(cnt, edl[:, 1], 1)
        nj = np.where(cnt > 0, acc / np.maximum(cnt, 1), jw); jw = np.where(band, nj, jw)
    report["mouth"]["corner_band_verts"] = int(band.sum())

    # only the mandible: in front of the hinge, and fading out into the neck under the chin
    jw *= 1 - smooth(-0.025, -0.005, rel_h[:, 1])                       # nothing behind ~2.5 cm in front of the hinge
    chin_z = np.interp(0, xs_m, line_s) - 0.040                         # approximate chin bottom (rel. eyes)
    under = smooth(0.000, 0.025, chin_z - Z) * smooth(-0.045, -0.010, Yb)  # under the chin, behind its front
    jw = np.where(is_skin, jw * (1 - under), 0.0)
    jw = np.where(lower_tooth, 1.0, jw); jw = np.where(is_tongue, float(os.environ.get("TONGUE_JAW", "0.9")), jw)
    jw = np.where(is_tooth & ~lower_tooth, 0.0, jw)
    V2M = os.environ.get("MOUTH_V2") == "1"
    if V2M:
        jw = np.where(is_tongue, 1.0, jw)                                   # tongue rides fully on the mandible
    def jaw_rotate(P, w, deg=JAW_DEG):
        r_ = P - HINGE; a_ = np.radians(deg) * w; c_, s_ = np.cos(a_), np.sin(a_); o_ = r_.copy()
        o_[:, 1] = r_[:, 1] * c_ - r_[:, 2] * s_; o_[:, 2] = r_[:, 1] * s_ + r_[:, 2] * c_
        return o_ + HINGE
    a = np.radians(JAW_DEG) * jw; ca, sa = np.cos(a), np.sin(a)
    Rr = rel_h.copy(); Rr[:, 1] = rel_h[:, 1] * ca + rel_h[:, 2] * sa * -1 * -1; Rr[:, 2] = -rel_h[:, 1] * sa * -1 * -1 + rel_h[:, 2] * ca
    # rotate so that front points (negative y) move DOWN: z' = z*cos + y*sin  (y<0 -> down)
    Rr[:, 1] = rel_h[:, 1] * ca - rel_h[:, 2] * sa; Rr[:, 2] = rel_h[:, 1] * sa + rel_h[:, 2] * ca
    keys["jaw_open"] = (Rr + HINGE) - HP
    if V2M:
        Dj = keys["jaw_open"]
        # mouth corners: the commissure travels ~45 % of the way with the jaw and draws slightly inward
        cz = np.array([np.interp(sx * corner_x, xs_m, line_s) for sx in (1.0, -1.0)])
        cwj = sum(np.exp(-((X - sx * corner_x) ** 2 + (Z - czz) ** 2) / (2 * 0.006 ** 2)) for sx, czz in zip((1.0, -1.0), cz)) * is_skin
        target = 0.45 * Dj + np.stack([-0.06 * X * (Dj[:, 2] < 0) * np.abs(Dj[:, 2]) / 0.01, np.zeros(len(X)), np.zeros(len(X))], 1)
        Dj = Dj + cwj[:, None] * (target - Dj) * (1 - is_tooth)[:, None]
        # tongue: settles lower and slightly back as the mouth opens, so the lower teeth stay visible
        # tongue settles below the lower incisal edge (in the jaw's frame) and slightly back
        inc = lower_tooth & (np.abs(X) < 0.010)
        tip_z = float(Z[inc].max()) if inc.any() else -0.067
        ex = np.clip(Z - (tip_z - 0.0015), 0, None) * is_tongue
        frontw = smooth(-0.030, 0.000, FWD_)
        settle = np.stack([np.zeros(len(X)), 0.0020 * is_tongue * frontw, -float(os.environ.get("TONGUE_SETTLE", "0.6")) * ex * frontw], 1)
        settled = HP + settle
        Dj = Dj + (jaw_rotate(settled, jw) - jaw_rotate(HP, jw)) * is_tongue[:, None]
        report["mouth"]["tongue_settle"] = {"lower_incisal_tip_rel_eyes_mm": round(tip_z * MM, 1), "max_drop_mm": round(float((0.95 * ex * frontw).max()) * MM, 2)}
        # lower lip: rolls forward a little as it separates (no lip-on-incisor sticking)
        Dj = Dj + (lo_lip * 1.0)[:, None] * np.array([0, -0.0012, -float(os.environ.get("JAW_LIP_DOWN_MM", "2.0")) / 1000.0])
        if os.environ.get("COMMISSURE") == "1":
            # commissure web: the tissue linking upper and lower lip inside each corner. Keep it connected and
            # fold it back into the mouth as it stretches (4w(1-w) peaks where the web is half upper / half lower).
            sink = float(os.environ.get("COMMISSURE_SINK_MM", "3.5")) / 1000.0
            for sx in (1.0, -1.0):
                web = is_skin & (sx * X > corner_x - 0.010) & (sx * X < corner_x + 0.004) & (np.abs(dz) < 0.008) & (FWD_ < float(os.environ.get("ORAL_FRONT_MM", "33")) / 1000.0 + 0.004)
                mid_w = 4 * jw * (1 - jw) * web
                inward = np.stack([-sx * 0.35 * np.ones(len(X)), np.ones(len(X)), np.zeros(len(X))], 1); inward /= np.linalg.norm(inward, axis=1)[:, None]
                Dj = Dj + mid_w[:, None] * sink * inward
                report["mouth"].setdefault("commissure", {})["L" if sx > 0 else "R"] = {"web_verts": int(web.sum()), "folded_verts": int((mid_w > 0.1).sum()), "max_sink_mm": round(float(mid_w.max()) * sink * MM, 2)}
        keys["jaw_open"] = Dj
        # corrective for laughter: smile pulls the corner up while the jaw pulls it down -> over-stretch.
        # corr_jaw_smile_X (driven by min(jaw_open, mouth_smile_X)) lowers the corner with the jaw and eases its outward pull.
        for sname, sx in (("L", 1.0), ("R", -1.0)):
            cw_s = np.exp(-((X - sx * corner_x) ** 2 + (Z - cz[0 if sx > 0 else 1]) ** 2) / (2 * 0.009 ** 2)) * is_skin * side(sx)
            keys["corr_jaw_smile_" + sname] = cw_s[:, None] * (0.30 * Dj * (1 - is_tooth)[:, None] + np.array([-sx * 0.0012, 0, 0]))
        # pout v2: both lips project (lower more), lower lip rises slightly to keep contact; vermilion border kept by smooth falloff
        for sname, sx in (("L", 1.0), ("R", -1.0)):
            sd = side(sx); cw = corner_w(sx, 0.011)
            keys["lip_pout_" + sname] = (lo_lip * sd)[:, None] * np.array([0, -0.0052, 0.0006]) + (up_lip * sd)[:, None] * np.array([0, -0.0030, 0.0004]) \
                + (cw * 0.5)[:, None] * np.array([0, -0.0008, -0.0010])
    report["mouth"]["jaw"] = {"hinge_rel_eyes_mm": [round(float(v) * MM, 1) for v in HINGE - MID], "max_deg": JAW_DEG, "verts_moving": int((jw > 0.01).sum())}
    for k, D in keys.items():
        D = np.where(is_tooth[:, None] & (k != "jaw_open"), 0.0, D)   # lips never drag the teeth
        D = eye_guard(HP, D); set_key(k, D)
        m = np.linalg.norm(D, axis=1)
        report["mouth"].setdefault("keys", {})[k] = {"max_mm": round(float(m.max()) * MM, 2), "verts_over_0_1mm": int((m > 1e-4).sum())}
    report["mouth"]["lip_line_mm"] = [round(float(v) * MM, 2) for v in line_s[::4]]
    if os.environ.get("MOUTH_V2") == "1":
        # the scan topology bridges the lips with faces across the mouth seam (zero-area at rest). Opening the jaw
        # stretches them into a sheet. Remove ONLY those faces (vertices and all shape keys stay untouched).
        import bmesh
        jwf = jw
        bridge = []
        for pg in head.data.polygons:
            if not mats[pg.material_index].startswith("Skin"): continue
            vs = list(pg.vertices)
            if not np.all((np.abs(X[vs]) < corner_x + float(os.environ.get("BRIDGE_X_MM", "8")) / 1000.0) & (np.abs(dz[vs]) < 0.012) & (FWD_[vs] < 0.037)): continue
            if jwf[vs].max() - jwf[vs].min() > float(os.environ.get("BRIDGE_SPAN", "0.6")):
                bridge.append(pg.index)
        bm = bmesh.new(); bm.from_mesh(head.data); bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in bridge], context="FACES_ONLY")
        bm.to_mesh(head.data); bm.free(); head.data.update()
        report["mouth"]["bridging_faces_removed"] = len(bridge)
        globals()["PATCH_CTX"] = {"jw": jw.copy(), "X": X.copy(), "dz": dz.copy(), "FWD": FWD_.copy(), "corner_x": corner_x, "is_skin": is_skin.copy()}
    if os.environ.get("MOUTH_INTERIOR") == "1":
        import bmesh
        Mw = np.array(head.matrix_world); Minv = np.linalg.inv(Mw)
        def to_obj_space(P): return P @ Minv[:3, :3].T + Minv[:3, 3]   # objects are created with the head's transform
        lip_c = MID + np.array([0, 0, np.interp(0, xs_m, line_s)])
        CEN = lip_c + np.array([0, 0.026, -0.004])        # cavity centre: 26 mm behind the lip line
        RX, RY, RZ = 0.034, 0.044, 0.021                  # half-widths (x, depth, height)
        FRONT_CUT = float(os.environ.get("CAVITY_FRONT_CUT_MM", "29")) / 1000.0   # forward distance (rel eyes) of the opening
        def make_mat(name, col, rough, use_vc=False):
            m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
            p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); p.inputs["Base Color"].default_value = (*col, 1); p.inputs["Roughness"].default_value = rough
            if use_vc:   # glTF: Color Attribute -> Base Color exports as COLOR_0 (colour and shading baked per vertex)
                vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "Col"; nt.links.new(vc.outputs["Color"], p.inputs["Base Color"])
            return m
        def new_obj(name, bm, mat):
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
            ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
            ob.matrix_world = head.matrix_world.copy(); me.materials.append(mat); return ob
        def depth_shade(ob, P):
            """vertex colour darkens with depth behind the opening (ambient occlusion of the cavity)"""
            me = ob.data; ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
            f = np.clip((-(P[:, 1] - MID[1]) - (FRONT_CUT - 0.045)) / 0.045, 0, 1)   # 1 at the opening, 0 deep inside
            sh = 0.18 + 0.82 * f ** 1.4; base = np.array([0.52, 0.17, 0.17])
            ca.data.foreach_set("color", np.concatenate([base[None] * sh[:, None], np.ones((len(sh), 1))], 1).ravel())
        interior = []
        # (1) cavity shell: inward-facing ellipsoid, open at the front; upper half = palate + cheek lining, lower = floor
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
        for v in bm.verts:
            v.co.x *= RX; v.co.y *= RY; v.co.z *= RZ
            v.co += Vector(CEN.tolist())
            v.co = Vector(to_obj_space(np.array([v.co[:]]))[0].tolist())
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        Pw = lambda v: (np.array(v.co[:]) @ Mw[:3, :3].T + Mw[:3, 3])
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(-(Pw(v)[1] - MID[1]) > FRONT_CUT for v in f.verts)], context="FACES")
        cav_mat = make_mat("OralCavity", (0.52, 0.17, 0.17), 0.45, use_vc=True)
        cav = new_obj("OralCavity", bm, cav_mat); interior.append(cav)
        # (2) gums: tubes along the cervical line of each arch
        def arch_curve(lower):
            ids = np.where(is_tooth & (lower_tooth if lower else ~lower_tooth))[0]; pts = []
            for xv in np.linspace(-0.040, 0.040, 33):
                sel = ids[np.abs(X[ids] - xv) < 0.002]
                if len(sel) < 6: continue
                zz = Z[sel]; edge = sel[zz <= np.percentile(zz, 10)] if lower else sel[zz >= np.percentile(zz, 90)]
                p = HP[edge].mean(0) + np.array([0, 0, (-0.0010 if lower else 0.0010)]); pts.append(p)
            return np.array(pts)
        gum_mat = make_mat("Gingiva", (0.80, 0.42, 0.42), 0.35)
        # the scan's two large "Teeth" arch pieces are the gums: give them the gingiva material (geometry unchanged)
        head.data.materials.append(gum_mat); gidx = len(head.data.materials) - 1
        gum_vs = set()
        for vs in tcomp.values():
            if len(vs) > 300: gum_vs.update(vs)
        ng = 0
        for pg in head.data.polygons:
            if mats[pg.material_index].startswith("Teeth") and all(v in gum_vs for v in pg.vertices):
                pg.material_index = gidx; ng += 1
        report["mouth"]["gum_faces_recoloured"] = ng
        gums = {}
        for lower in ((False, True) if os.environ.get("GUM_TUBES") == "1" else ()):
            pts = arch_curve(lower)
            cu = bpy.data.curves.new("gum", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.0024; cu.bevel_resolution = 3
            sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
            for i, p in enumerate(pts): sp.points[i].co = (*to_obj_space(p[None])[0], 1.0)
            co = bpy.data.objects.new("gc", cu); bpy.context.scene.collection.objects.link(co); co.matrix_world = head.matrix_world.copy()
            bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(co.evaluated_get(dg)); bpy.data.objects.remove(co)
            ob = bpy.data.objects.new("Gingiva_lower" if lower else "Gingiva_upper", me); bpy.context.scene.collection.objects.link(ob); ob.matrix_world = head.matrix_world.copy(); me.materials.append(gum_mat)
            gums[lower] = ob; interior.append(ob)
        # tongue surface: wetter, natural colour (head material, only shading changes)
        for m in head.data.materials:
            if m.name.startswith("Tongue") and m.use_nodes:
                p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); p.inputs["Base Color"].default_value = (0.70, 0.33, 0.35, 1); p.inputs["Roughness"].default_value = 0.32
        # jaw keys on the interior: same hinge and angle; weights from height relative to the lip line
        report["mouth"]["interior"] = {}
        for ob in interior:
            me = ob.data; co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); P = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
            if ob.name == "OralCavity":
                rz_ = (P[:, 2] - MID[2]) - np.interp(0, xs_m, line_s)
                lateral = smooth(0.55, 0.85, np.abs(P[:, 0] - CEN[0]) / RX)                       # side walls (cheek lining)
                band = np.where(lateral > 0, 0.010 * lateral + 0.0015, 0.0015)
                w = 1 - smooth(-band, band, rz_ + 0.002)                                         # palate 0 / floor 1, wide blend only on the sides
                w *= 1 - smooth(-0.010, 0.020, (P[:, 1] - HINGE[1]) + 0.030)
            else:
                w = np.full(len(P), 1.0 if ob is gums.get(True) else 0.0)
            if ob.name == "OralCavity": depth_shade(ob, P)
            ob.shape_key_add(name="Basis")
            for kname, Dk in (("jaw_open", jaw_rotate(P, w) - P),):
                if kname == "jaw_open" and V2M:
                    Dk = Dk + (w * (ob.name == "OralCavity"))[:, None] * np.array([0, 0.0010, -0.0015])  # floor sags slightly under the tongue
                sk = ob.shape_key_add(name=kname, from_mix=False)
                sk.data.foreach_set("co", ((P + Dk) @ Minv[:3, :3].T + Minv[:3, 3]).ravel())
            ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted()
            report["mouth"]["interior"][ob.name] = {"verts": len(P), "faces": len(me.polygons), "jaw_weighted_verts": int((w > 0.01).sum())}
        report["mouth"]["interior_cavity"] = {"centre_rel_eyes_mm": [round(float(v) * MM, 1) for v in CEN - MID], "radii_mm": [RX * MM, RY * MM, RZ * MM], "front_cut_mm": FRONT_CUT * MM}
        INTERIOR_OBJS = interior

# ---------- head corrective for blink + squint (driven by min(blink, squint) per side) ----------
# With the lid already closed by blink, squint's own lid motion folds the lids into each other.
# The corrective removes squint's displacement around the eye opening and keeps its brow/outer squeeze.
for s in "LR":
    c, r = EYE[s]; dsq = np.empty(len(HP) * 3); kb["squint_" + s].data.foreach_get("co", dsq)
    D_sq = (dsq.reshape(-1, 3) - basis) @ M3.T
    dist = np.linalg.norm(HP - c, axis=1); m = (1 - smooth(r + 0.003, r + 0.008, dist)) * is_skin
    set_key("corr_blink_squint_" + s, -m[:, None] * D_sq)
    report.setdefault("head_corrective", {})["corr_blink_squint_" + s] = {"verts_over_0_1mm": int((np.linalg.norm(m[:, None] * D_sq, axis=1) > 1e-4).sum()),
                                                                          "max_mm": round(float(np.linalg.norm(m[:, None] * D_sq, axis=1).max()) * MM, 2)}

# ---------- 4. transfer every head key to the strands ----------
KEYS = [k.name for k in kb[1:]]
D_head = {}
for k in KEYS:
    a = np.empty(len(HP) * 3); kb[k].data.foreach_get("co", a); D_head[k] = (a.reshape(-1, 3) - basis) @ M3.T


def delta_at(p):
    loc, _, fi, _ = skin_bvh.find_nearest(Vector(p))
    vids = skin_polys[fi]
    from mathutils.interpolate import poly_3d_calc
    w = poly_3d_calc([Vector(HP[v]) for v in vids], loc)
    return {k: sum(D_head[k][v] * wi for v, wi in zip(vids, w)) for k in KEYS}


def rebuild_strands(o, P_world, roots, extra=None):
    """roots: island -> anchor point (world). Each strand moves rigidly with the skin at its anchor."""
    me = o.data
    if me.shape_keys:
        o.shape_key_clear()
    me.vertices.foreach_set("co", to_local(o, P_world).ravel()); me.update()
    o.shape_key_add(name="Basis")
    cache = {g: delta_at(p) for g, p in roots.items()}
    Pl = to_local(o, P_world)
    for k in KEYS:
        sk = o.shape_key_add(name=k, from_mix=False)
        D = np.zeros_like(P_world)
        for g, idx in members[o.name].items():
            D[idx] = cache[g][k]
        sk.data.foreach_set("co", (Pl + dir_to_local(o, D)).ravel())
    for name, per in (extra or {}).items():
        sk = o.shape_key_add(name=name, from_mix=False)
        D = np.zeros_like(P_world)
        for g, idx in members[o.name].items():
            D[idx] = per.get(g, np.zeros(3))
        sk.data.foreach_set("co", (Pl + dir_to_local(o, D)).ravel())


members = {lashes.name: {g: np.array(ix) for g, ix in groups.items()}}

# ---- lashes are glued to their anchor face: they translate AND rotate with the eyelid skin ----
def face_frame(P3):
    """Orthonormal frame of a polygon (rows: tangent, bitangent, normal)."""
    nrm = np.zeros(3)
    for i in range(len(P3)):
        a, b = P3[i], P3[(i + 1) % len(P3)]
        nrm += np.array([(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])])
    nrm /= np.linalg.norm(nrm) + 1e-15
    t = P3[1] - P3[0]; t -= (t @ nrm) * nrm; t /= np.linalg.norm(t) + 1e-15
    return np.array([t, np.cross(nrm, t), nrm])


from mathutils.interpolate import poly_3d_calc
anchor = {}
for g, v in strand_root.items():
    loc, _, fi, _ = skin_bvh.find_nearest(Vector(v[1])); vids_ = skin_polys[fi]
    anchor[g] = (np.array(vids_), np.array(poly_3d_calc([Vector(HP[i]) for i in vids_], loc)))


from mathutils.kdtree import KDTree
_kd = KDTree(len(skin_ids))
for i in skin_ids: _kd.insert(Vector(HP[i]), int(i))
_kd.balance()
nbhd = {g: np.array([i for _, i, _ in _kd.find_n(Vector(v[1]), 12)]) for g, v in strand_root.items()}


def kabsch(A, B):
    A = A - A.mean(0); B = B - B.mean(0); U, _, Vt = np.linalg.svd(A.T @ B)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); return Vt.T @ np.diag([1, 1, d]) @ U.T


def strand_motion(g, D):
    """Anchor displacement (exact, on its face) and best-fit rotation of the 12 skin vertices around the root."""
    vids_, w = anchor[g]; nb = nbhd[g]
    return (D[vids_] * w[:, None]).sum(0), kabsch(HP[nb], HP[nb] + D[nb])


motion = {g: {k: strand_motion(g, D_head[k]) for k in KEYS} for g in strand_root}


def pose_delta(g, Q, pose):
    out = np.zeros_like(Q)
    for k, wt in pose.items():
        if k not in motion[g]: continue
        dv, R = motion[g][k]; out += wt * (dv + Q @ (R - np.eye(3)).T)
    return out


POSES = [{}] + [{k: 1.0} for k in KEYS if not k.startswith("corr_")] + [
    {"blink_L": .55, "blink_R": .55, "lid_follow_L": .5, "lid_follow_R": .5},
    *([{"blink_L": .25, "blink_R": .25, "corr_blink_arc_L": .75, "corr_blink_arc_R": .75},
       {"blink_L": .5, "blink_R": .5, "corr_blink_arc_L": 1, "corr_blink_arc_R": 1},
       {"blink_L": .75, "blink_R": .75, "corr_blink_arc_L": .75, "corr_blink_arc_R": .75}] if BLINK_MODEL == "arc" else []),
    {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1, "corr_blink_squint_L": 1, "corr_blink_squint_R": 1},
    {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1, "corr_blink_squint_L": 1, "corr_blink_squint_R": 1, "cheek_raise_L": 1, "cheek_raise_R": 1},
    {"squint_L": 1, "squint_R": 1, "cheek_raise_L": 1, "cheek_raise_R": 1}]
CLEAR = float(os.environ.get("LASH_CLEAR", "0.0001"))


def pen_depth(P):
    return max(float((r + CLEAR - np.linalg.norm(P - c, axis=1)).max()) for c, r in EYE.values())


BODY = np.array([True])


def worst(g, Q, target):
    """Deepest eyeball penetration of the strand body (vertices > 1 mm from the root) over all poses."""
    body = np.linalg.norm(Q, axis=1) > 0.001
    if not body.any(): return -1.0
    return max(pen_depth((Q + target + pose_delta(g, Q, pz))[body]) for pz in POSES)


def rodrigues(axis, ang):
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


tilted = 0; unresolved = []; tilt_deg = []; before_pen = 0; shortened = []
for g, (r_i, target, upper, side) in strand_root.items():
    ix = np.array(groups[g]); Q = LP[ix] - target
    if worst(g, Q, target) <= 0: continue
    before_pen += 1
    tip = Q[np.argmax(np.linalg.norm(Q, axis=1))]
    radial = target - EYE[side][0]; radial /= np.linalg.norm(radial)
    axis = np.cross(tip, radial)  # tilt away from the eyeball, about the root
    ok = False
    if np.linalg.norm(axis) > 1e-9:
        axis /= np.linalg.norm(axis)
        best = (worst(g, Q, target), Q, 0)
        for step in range(1, 21):
            Q2 = Q @ rodrigues(axis, math.radians(3 * step)).T; wv = worst(g, Q2, target)
            if wv < best[0]: best = (wv, Q2, 3 * step)
            if wv <= 0:
                Q = Q2; ok = True; tilt_deg.append(3 * step); break
        if not ok:  # corner strands: keep the best tilt and shorten (real corner lashes are short)
            for sc in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4):
                Q3 = best[1] * sc
                if worst(g, Q3, target) <= 0:
                    Q = Q3; ok = True; tilt_deg.append(best[2]); shortened.append(sc); break
    if ok:
        tilted += 1; LP[ix] = Q + target
    else:
        unresolved.append(round(worst(g, Q, target) * MM, 3))
        bad = [str(pz) for pz in POSES if pen_depth((Q + target + pose_delta(g, Q, pz))[np.linalg.norm(Q, axis=1) > 0.001]) > 0]
        report.setdefault("unresolved_poses", {})
        for b_ in bad: report["unresolved_poses"][b_] = report["unresolved_poses"].get(b_, 0) + 1
# diagnostics: which poses penetrate, and is the root itself inside?
diag = {}
for pi, pz in enumerate(POSES):
    n_str = 0; root_in = 0; dmax = 0
    for g, (r_i, target, upper, side) in strand_root.items():
        ix = np.array(groups[g]); Q = LP[ix] - target; P = Q + target + pose_delta(g, Q, pz)
        dd = pen_depth(P)
        if dd > 0:
            n_str += 1; dmax = max(dmax, dd)
            rootp = target + pose_delta(g, np.zeros((1, 3)), pz)[0]
            if pen_depth(rootp[None]) > 0: root_in += 1
    if n_str: diag[str(pz) if pz else "rest"] = {"strands": n_str, "roots_inside": root_in, "max_mm": round(dmax * MM, 2)}
report["penetration_by_pose"] = diag
report["eyeball_clearance"] = {"strands_penetrating_in_some_pose_before_tilt": before_pen, "strands_tilted": tilted,
                               "unresolved_strands": len(unresolved), "unresolved_depth_mm_max": max(unresolved) if unresolved else 0,
                               "tilt_deg_max": max(tilt_deg) if tilt_deg else 0, "shortened_strands": len(shortened), "shortened_min_scale": min(shortened) if shortened else 1.0, "poses_tested": len(POSES), "clearance_mm": CLEAR * MM}

# ---- corrective for blink + squint: exact glued motion of the combined pose minus the linear sum ----
corr = {}
for s in "LR":
    Dpose = D_head["blink_" + s] + D_head["squint_" + s] + D_head["corr_blink_squint_" + s]; per = {}; mags = []
    for g, (r_i, target, upper, side) in strand_root.items():
        if side != s: continue
        ix = np.array(groups[g]); Q = LP[ix] - target
        dv, R = strand_motion(g, Dpose); exact = dv + Q @ (R - np.eye(3)).T
        lin = pose_delta(g, Q, {"blink_" + s: 1, "squint_" + s: 1})
        per[g] = exact - lin; mags.append(float(np.linalg.norm(per[g], axis=1).max()) * MM)
    corr["corr_blink_squint_" + s] = per
    report.setdefault("corrective", {})["corr_blink_squint_" + s] = {"strands": len(mags), "max_mm": round(max(mags), 3), "p99_mm": round(float(np.percentile(mags, 99)), 3)}


def rebuild_lashes(o, P_world):
    me = o.data
    if me.shape_keys: o.shape_key_clear()
    me.vertices.foreach_set("co", to_local(o, P_world).ravel()); me.update()
    o.shape_key_add(name="Basis"); Pl = to_local(o, P_world)
    for k in KEYS:
        sk = o.shape_key_add(name=k, from_mix=False); D = np.zeros_like(P_world)
        for g, (r_i, target, upper, side) in strand_root.items():
            ix = np.array(groups[g])
            if k in corr:
                if g in corr[k]: D[ix] = corr[k][g]
            else:
                D[ix] = pose_delta(g, P_world[ix] - target, {k: 1.0})
        sk.data.foreach_set("co", (Pl + dir_to_local(o, D)).ravel())


if BLINK_MODEL == "arc":
    for s in "LR":
        Dh = D_head["blink_" + s] * 0.5 + D_head["corr_blink_arc_" + s]; per = {}
        for g, (r_i, target, upper, side) in strand_root.items():
            if side != s: continue
            ix = np.array(groups[g]); Q = LP[ix] - target
            dv, Rm = strand_motion(g, Dh); exact = dv + Q @ (Rm - np.eye(3)).T
            per[g] = exact - pose_delta(g, Q, {"blink_" + s: 0.5})
        corr["corr_blink_arc_" + s] = per
rebuild_lashes(lashes, LP)


BP = world_co(brows); nb = len(BP); par = list(range(nb))
for e in brows.data.edges:
    a, b = f(e.vertices[0]), f(e.vertices[1])
    if a != b: par[a] = b
bis = np.array([f(i) for i in range(nb)]); bg = {}
for i, g in enumerate(bis): bg.setdefault(g, []).append(i)
bd = np.array([skin_bvh.find_nearest(Vector(p))[3] for p in BP])
members[brows.name] = {g: np.array(ix) for g, ix in bg.items()}
rebuild_strands(brows, BP, {g: BP[np.array(ix)[np.argmin(bd[np.array(ix)])]] for g, ix in bg.items()})

# neutral checks: lashes inside the opening (crossing the eye) before/after
def crossing(P):
    cnt = 0
    for s in "LR":
        c, r = EYE[s]; cols = OPEN[s]; xs = np.array([q[0] for q in cols])
        rel = P - c; sel = (np.abs(rel[:, 0]) < r) & ((rel[:, 0] > 0) == (s == "L") if False else True)
        sel &= (np.sign(P[:, 0]) == (1 if s == "L" else -1))
        for p in rel[sel]:
            if p[0] < xs[0] or p[0] > xs[-1]: continue
            i = min(max(int(np.searchsorted(xs, p[0])), 1), len(xs) - 1)
            up = cols[i][1] - 0.0003; lo = cols[i][2] + 0.0003
            if lo < p[2] < up and -p[1] > 0.0:  # in front of the eye, inside the opening
                cnt += 1
    return cnt
report["lash_vertices_inside_opening"] = {"before": crossing(LP0), "after": crossing(LP)}


def over_eye(P):
    """Lash vertices in front of an eye whose front projection lies on the pupil (r<2.5 mm) / iris (r<6 mm)."""
    out = {"pupil": 0, "iris": 0}
    for s in "LR":
        c, r = EYE[s]; rel = P - c; sel = (np.sign(P[:, 0]) == (1 if s == "L" else -1)) & (-rel[:, 1] > 0)
        rr = np.hypot(rel[sel, 0], rel[sel, 2])
        out["pupil"] += int((rr < 0.0025).sum()); out["iris"] += int((rr < 0.006).sum())
    return out
report["lash_vertices_over_eye_front_view"] = {"before": over_eye(LP0), "after": over_eye(LP)}
report["keys"] = KEYS

# ---------- Phase 2N.7C: commissure patch (COMMISSURE_PATCH=1). Runs last: existing vertices and keys unchanged ----------
if os.environ.get("COMMISSURE_PATCH") == "1" and "PATCH_CTX" in globals():
    import bmesh
    C = PATCH_CTX; jw0 = C["jw"]; Xc = C["X"]; dzc = C["dz"]; Fc = C["FWD"]; cx = C["corner_x"]; sk = C["is_skin"]
    me = head.data; nv0 = len(me.vertices)
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    span = float(os.environ.get("PATCH_SPAN", "0.25")); xin = float(os.environ.get("PATCH_X_IN_MM", "9")) / 1000.0
    def in_web(i):
        return i < len(jw0) and sk[i] and (abs(Xc[i]) > cx - xin) and (abs(Xc[i]) < cx + 0.004) and abs(dzc[i]) < 0.010 and Fc[i] < 0.037
    web_faces = [f for f in bm.faces if all(in_web(v.index) for v in f.verts) and (max(jw0[v.index] for v in f.verts) - min(jw0[v.index] for v in f.verts)) > span]
    edges = list({e for f in web_faces for e in f.edges})
    cuts = int(os.environ.get("PATCH_CUTS", "3"))
    res_ = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True, smooth=0.0)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    # patch region = the subdivided faces' vertices; boundary = original vertices outside the patch interior
    new_vs = [v for v in bm.verts if v.index >= nv0]
    patch_vs = set(new_vs)
    for f in web_faces:
        pass
    # all faces touching a new vertex form the patch
    patch_faces = {f for v in new_vs for f in v.link_faces}
    patch_all = {v for f in patch_faces for v in f.verts}
    interior = [v for v in patch_all if v.index >= nv0 or all((u in patch_all) for e in v.link_edges for u in e.verts)]
    interior = [v for v in interior if v.index >= nv0 or not v.is_boundary]
    lay = bm.verts.layers.shape
    MW = np.array(head.matrix_world)[:3, :3]
    def get(name):
        L = lay[name]; return {v: np.array(v[L][:]) for v in patch_all}
    basis_l = lay["Basis"] if "Basis" in lay else lay[0]
    # harmonic smoothing of the jaw displacement (object space) over the patch, boundary fixed
    for kname in [k for k in ("jaw_open",) if k in lay] + [k.name for k in [] ]:
        L = lay[kname]; B0 = {v: np.array(v[basis_l][:]) for v in patch_all}
        D = {v: np.array(v[L][:]) - B0[v] for v in patch_all}
        free = [v for v in interior if v.index >= nv0 or in_web(v.index)]
        for _ in range(int(os.environ.get("PATCH_ITERS", "200"))):
            for v in free:
                nb = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) in patch_all]
                if nb: D[v] = 0.5 * D[v] + 0.5 * np.mean([D[u] for u in nb], axis=0)
        for v in free: v[L] = Vector((B0[v] + D[v]).tolist())
    # every other key on new vertices is already the linear interpolation of its edge's ends (bmesh does this)
    bm.to_mesh(me); bm.free(); me.update()
    report["commissure_patch"] = {"web_faces_subdivided": len(web_faces), "cuts": cuts, "new_vertices": len(me.vertices) - nv0, "smoothed_vertices": len(free) if web_faces else 0}

for o in bpy.data.objects:
    o.select_set(o in (rig, head, brows, lashes) or o in globals().get("INTERIOR_OBJS", []))
bpy.context.view_layer.objects.active = head
for k in head.data.shape_keys.key_blocks: k.value = 0.0
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True,
                          export_normals=True, export_tangents=False, export_materials="EXPORT", export_image_format="AUTO",
                          export_morph=True, export_morph_normal=True, export_skins=True, export_animations=False, export_apply=False)
json.dump(report, open(rep_path, "w"), indent=1, default=float)
print("V2_EXPORTED", dst)
print(json.dumps(report, default=float)[:3000])

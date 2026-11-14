"""Phase 2E: geometric checks of every expression / combination on the scan-based GNM head (CPU, exact).

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python ../real_assets/finalize/expr_geometry.py \
        ../real_assets/3dscanstore/build/scan_gnm_fit.npz ../real_assets/3dscanstore/extracted/OBJ \
        ../real_assets/3dscanstore/build/scan_controls.npz OUT_DIR

Scan base exactly as scan_controls.py (scan skin + scan-sized eyes). Adds the Phase 2D brow lowerer
(brow_furrow = semantic DISGUST eye blocks, capped at 0.67) re-expressed on the scan base, and writes its
key offsets for Blender. Per pose: lid opening per column, brow motion, the other eye, lower face, and the
deepest NEW lid penetration into the rotated eye surface (sclera + corneal bulge, direction-wise), relative
to the neutral pose.
"""
import json
import sys

sys.path.insert(0, ".")
import numpy as np  # noqa: E402
import gnm_expr as gx  # noqa: E402

fit = np.load(sys.argv[1]); X = sys.argv[2]; C = dict(np.load(sys.argv[3])); OUT = sys.argv[4]
m = gx.Model(); d = gx.SemanticDecoder()
V = fit["vertices_fit"].copy(); V[fit["skin_vertex_ids"]] = fit["scan_skin"]


def obj(p):
    return np.array([[float(x) for x in l.split()[1:4]] for l in open(p, errors="ignore") if l.startswith("v ")])


def sph(P):
    A = np.c_[2 * P, np.ones(len(P))]; c = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0]
    return c[:3], np.sqrt(c[3] + c[:3] @ c[:3])


for side, name in (("left", "Left"), ("right", "Right")):
    cs, rs = sph(obj(f"{X}/Realtime Eyeball {name}.obj")); ids = np.nonzero(m.mask[f"{side}_eye"])[0]
    cg, rg = sph(m.V0[m.mask["scleras"] & m.mask[f"{side}_eye"]]); V[ids] = (m.V0[ids] - cg) * (rs / rg) + cs
    m.eye[side]["centre"] = cs; m.eye[side]["r_sclera"] = rs
m.V0 = V
m.vertices = lambda expression=None, rotations=None: V + (0 if expression is None else np.tensordot(expression, m.B, 1))
for side in ("left", "right"):
    m.eye[side]["margins"] = m._margins(side, m.eye[side]["centre"], m.eye[side]["r_sclera"])
for side in ("left", "right"):
    v = np.zeros(383); v[gx.BLOCK[side] if hasattr(gx, "BLOCK") else (slice(0, 100) if side == "left" else slice(100, 200))] = \
        d.canonical("disgust")[slice(0, 100) if side == "left" else slice(100, 200)]
    C[f"brow_furrow_{side}"] = v * 0.67          # Phase 2D cap: 0.67 x DISGUST eye blocks = slider 1.0
ext = {s: np.nonzero(m.mask["eye_exteriors"] & m.mask[f"{s}_eye"])[0] if "eye_exteriors" in m.mask else
       np.nonzero(m.mask[f"{s}_eye"])[0] for s in ("left", "right")}


def rot(yaw, pitch):
    a, b = np.radians(yaw), np.radians(pitch)
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    return Ry @ Rx


Q = np.asarray(m.g.quads)
TRI = {}
for s_ in ("left", "right"):
    inside = np.zeros(len(V), bool); inside[ext[s_]] = True
    q = Q[inside[Q].all(1)]
    TRI[s_] = np.concatenate([q[:, [0, 1, 2]], q[:, [2, 3, 0]]])


def penetration(W, side, R):
    """Per orbital skin vertex near the eye: outermost eye-surface radius along the ray from the eye centre
    through the vertex (exact ray/triangle test against the rotated exterior: sclera + corneal bulge) - distance."""
    c = m.eye[side]["centre"]
    E = (V - c) @ R.T
    A, B_, C_ = (E[TRI[side][:, i]] for i in range(3))
    skin = np.nonzero(m.mask["skin"] & m.mask[f"{side}_orbital_region"])[0]
    P = W[skin] - c; rP = np.linalg.norm(P, axis=1); dP = P / rP[:, None]
    near = np.nonzero(rP < m.eye[side]["r_sclera"] + 0.004)[0]
    out = np.full(len(skin), -99.0)
    e1, e2 = B_ - A, C_ - A
    for j in near:
        dvec = dP[j]
        h = np.cross(dvec, e2); a = (e1 * h).sum(1)
        ok = np.abs(a) > 1e-12; f = np.where(ok, 1 / np.where(ok, a, 1), 0)
        sv = -A; u = f * (sv * h).sum(1); qv = np.cross(sv, e1); v = f * (qv @ dvec); t = f * (e2 * qv).sum(1)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        rs = t[hit].max() if hit.any() else m.eye[side]["r_sclera"]
        out[j] = (rs - rP[j]) * 1000.0
    return out


L = lambda s: "left" if s == "L" else "right"  # noqa: E731
POSES = {
    "neutral": ({}, (0, 0)),
    "squint": ({"squint": 1.0}, (0, 0)),
    "surprise": ({"surprise": 1.0}, (0, 0)),
    "brow_raise_2mm": ({"brow_raise": 1.0}, (0, 0)),
    "brow_lowerer": ({"brow_furrow": 1.0}, (0, 0)),
    "blink": ({"blink": 1.0}, (0, 0)),
    "blink_up12": ({"blink": 1.0}, (0, 12)),
    "blink_down7": ({"blink": 1.0}, (0, -7)),
    "blink_left15": ({"blink": 1.0}, (15, 0)),
    "squint_left15": ({"squint": 1.0}, (15, 0)),
    "squint_right15": ({"squint": 1.0}, (-15, 0)),
    "brow_raise_up12": ({"brow_raise": 1.0}, (0, 12)),
    "look_left20": ({}, (20, 0)),
    "look_up12": ({}, (0, 12)),
    "look_down7": ({}, (0, -7)),
}
brow_unit = {s: m.brow_height(m.vertices(C[f"brow_raise_{s}"]), s) - m.brow_height(V, s) for s in ("left", "right")}
base = {s: penetration(V, s, np.eye(3)) for s in ("left", "right")}
lowmask = m.mask["skin"] & ~np.zeros(len(V), bool)
lower = m.mask["skin"] & (m.mask["upper_lip_region"] | m.mask["lower_lip_region"] | m.mask["chin_region"])
rep = {}
for name, (w, (yaw, pitch)) in POSES.items():
    e = np.zeros(383)
    for s in ("left", "right"):
        b = w.get("blink", 0.0)
        for k, val in w.items():
            scale = 2.0 / brow_unit[s] if k == "brow_raise" else 1.0
            e += C[f"{k}_{s}"] * val * scale
        e += C[f"lid_follow_{s}"] * pitch * (1 - b)          # rig: lid_follow key = elevation/10, key = ctrl*10
    W = m.vertices(e)
    r = {}
    for s in ("left", "right"):
        pen = penetration(W, s, rot(yaw, pitch))
        new = pen[(base[s] <= 0.05) & (pen > 0.05)]
        r[s] = dict(aperture_mm=np.round(m.aperture(W, s), 2).tolist(), brow_mm=round(m.brow_height(W, s) - m.brow_height(V, s), 2),
                    new_penetration_mm=round(float(new.max()) if new.size else 0.0, 3), n_new=int(new.size))
    r["lower_face_max_mm"] = round(float(np.linalg.norm(W[lower] - V[lower], axis=1).max() * 1000), 3) if lower.any() else None
    r["max_skin_motion_mm"] = round(float(np.linalg.norm(W - V, axis=1).max() * 1000), 2)
    rep[name] = r
    print(f"{name:16s} L ap {r['left']['aperture_mm']} brow {r['left']['brow_mm']:+.2f} pen {r['left']['new_penetration_mm']:.2f}({r['left']['n_new']}) | "
          f"R ap {r['right']['aperture_mm']} brow {r['right']['brow_mm']:+.2f} pen {r['right']['new_penetration_mm']:.2f}({r['right']['n_new']}) | lowerface {r['lower_face_max_mm']} max {r['max_skin_motion_mm']}")
json.dump(rep, open(f"{OUT}/expr_geometry.json", "w"), indent=1)
np.savez(f"{OUT}/brow_furrow_offsets.npz", **{f"brow_furrow_{s}": np.tensordot(C[f"brow_furrow_{L(s)}"], m.B, 1).astype(np.float32) for s in ("L", "R")})
print("saved")

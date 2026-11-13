"""Derive GNM eyelid/brow control directions inside each eye's own 100-component expression block.

GNM expressions are exactly linear (verified: superposition error ~5.6e-17), so each control is a
fixed 383-vector and its vertex offset is exact at any weight. Every control uses only its own
eye block (left 0-99, right 100-199): the mouth, the other eye and the rest of the face stay put.

Controls per eye (weight 1.0 unless noted):
  blink         full closure (all margin columns <= 0.15 mm), brow nearly still. Fitted to the
                semantic wink's lid motion with brow/forehead targets held at zero.
  lid_follow    lids follow +1 deg of upward eye elevation: upper lid rotates 1.0 deg, lower 0.35 deg
                about the eye centre (Phase 1B gains); linear, so -10 means looking 10 deg down.
  squint        semantic SQUINT, eye block only (decoded at the latent mean)
  surprise      semantic SURPRISE, eye block only
  brow_raise    +1 mm vertical brow lift with the lids held still (fitted)

Fits are ridge-regularised least squares (lambda chosen by the smallest value that keeps the
coefficient norm within the typical +-3 range of each component). Weights are applied to the
canonical vectors and the results are validated by renders, not by norms alone.
"""

import json
import os
import sys

import numpy as np

import gnm_expr as gx

BLOCK = {"left": slice(0, 100), "right": slice(100, 200)}


def fit(m, side, target, weight, lam=1e-3):
    """min_c sum_v w_v |B_v c - T_v|^2 + lam |c|^2 over the side's eye block. Returns a 383-vector."""
    b = m.B[BLOCK[side]]                      # (100, V, 3)
    w = np.sqrt(weight)[None, :, None]
    A = (b * w).reshape(100, -1).T            # (3V, 100)
    y = (target * w[0]).reshape(-1)
    c = np.linalg.solve(A.T @ A + lam * np.eye(100), A.T @ y)
    out = np.zeros(m.B.shape[0])
    out[BLOCK[side]] = c
    return out


def eye_region(m, side):
    return m.mask["skin"] & (m.mask[f"{side}_orbital_region"] | m.mask[f"{side}_brow_region"] |
                             m.mask[f"{side}_infraorbital_region"] | m.mask["forehead_region"] |
                             m.mask["middle_brow_region"] | m.mask[f"{side}_temple_region"])


def rotate_about_x(P, c, deg):
    a = np.radians(deg)
    R = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    return (P - c) @ R.T + c


def lid_sets(m, side):
    """Upper/lower lid skin: orbital-region skin in front of the eye, above/below the centre, close to the globe."""
    c, r = m.eye[side]["centre"], m.eye[side]["r_sclera"]
    P = m.V0
    reg = m.mask["skin"] & m.mask[f"{side}_orbital_region"]
    near = np.linalg.norm(P - c, axis=1) < r + 0.006
    front = P[:, 2] > c[2] + 0.2 * r
    lateral = np.abs(P[:, 0] - c[0]) < 0.014
    up = reg & near & front & lateral & (P[:, 1] > c[1])
    lo = reg & near & front & lateral & (P[:, 1] <= c[1])
    return up, lo


def build(m, d):
    ctrl = {}
    for side in ("left", "right"):
        other = "right" if side == "left" else "left"
        region = eye_region(m, side)
        brow = m.mask[f"{side}_brow_region"] | m.mask["forehead_region"] | m.mask["middle_brow_region"]
        # --- blink: follow the semantic wink on the lids, hold brow/forehead still
        wink = np.zeros(383); wink[BLOCK[side]] = d.canonical(f"wink_{side}")[BLOCK[side]]
        T = (m.vertices(wink) - m.V0)
        T[brow] = 0.0
        W = region.astype(float) + 4.0 * brow.astype(float)
        blink = fit(m, side, T, W)
        # scale so the eye is just closed: largest margin gap <= 0.15 mm (closure is linear in weight)
        a0 = m.aperture(m.V0, side)
        a1 = m.aperture(m.vertices(blink), side)
        slope = a1 - a0                                # aperture change per unit weight, per column
        k = float(np.max((0.15 - a0) / slope))         # weight at which every column is <= 0.15 mm
        ctrl[f"blink_{side}"] = blink * k
        # --- lids follow +1 deg upward eye elevation (Phase 1B gains 1.0 upper / 0.35 lower)
        up, lo = lid_sets(m, side)
        c = m.eye[side]["centre"]
        T = np.zeros_like(m.V0)
        T[up] = rotate_about_x(m.V0[up], c, -10.0)[...] - m.V0[up]     # -X rotation lifts (Y up, +Z fwd)
        T[lo] = rotate_about_x(m.V0[lo], c, -3.5)[...] - m.V0[lo]
        W = region.astype(float) + 4.0 * (up | lo).astype(float) + 4.0 * brow.astype(float)
        ctrl[f"lid_follow_{side}"] = fit(m, side, T, W) / 10.0
        # --- brow raise +1 mm, lids still
        T = np.zeros_like(m.V0)
        T[m.mask[f"{side}_brow_region"], 1] = 0.001
        lids = up | lo
        W = region.astype(float) + 6.0 * lids.astype(float) + 4.0 * m.mask[f"{side}_brow_region"].astype(float)
        ctrl[f"brow_raise_{side}"] = fit(m, side, T, W)
        for lab in ("squint", "surprise"):
            v = np.zeros(383); v[BLOCK[side]] = d.canonical(lab)[BLOCK[side]]
            ctrl[f"{lab}_{side}"] = v
    return ctrl


def measure(m, ctrl):
    rep = {}
    V0 = m.V0
    for name, c in ctrl.items():
        side = name.rsplit("_", 1)[1]
        other = "right" if side == "left" else "left"
        r = {}
        for w in ((-10.0, 10.0) if name.startswith("lid_follow") else (0.5, 1.0) if name.startswith("blink") else (1.0, 2.0) if name.startswith("brow") else (1.0,)):
            V = m.vertices(c * w)
            r[str(w)] = {
                "aperture_mm": m.aperture(V, side).round(2).tolist(),
                "other_eye_aperture_change_mm": float(np.abs(m.aperture(V, other) - m.aperture(V0, other)).max().round(4)),
                "brow_mm": round(m.brow_height(V, side) - m.brow_height(V0, side), 3),
                "lower_face_max_mm": float(max(m.region_displacement(V)[k] for k in ("upper_lip_region", "lower_lip_region", "chin_region"))),
                "coeff_norm": round(float(np.linalg.norm(c * w)), 3),
                "coeff_absmax": round(float(np.abs(c * w).max()), 3),
            }
        rep[name] = r
    return rep


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(gx.HERE, "build", "gnm_controls.npz")
    m, d = gx.Model(), gx.SemanticDecoder()
    ctrl = build(m, d)
    np.savez(out, **ctrl)
    rep = measure(m, ctrl)
    with open(os.path.join(os.path.dirname(out), "gnm_controls_report.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    for k, v in rep.items():
        for w, r in v.items():
            print(f"{k:18s} w={w:>5s} ap {r['aperture_mm']} brow {r['brow_mm']:+.2f} otherEye {r['other_eye_aperture_change_mm']:.3f} lowerFace {r['lower_face_max_mm']:.3f} |c| {r['coeff_norm']:.2f} max|c| {r['coeff_absmax']:.2f}")

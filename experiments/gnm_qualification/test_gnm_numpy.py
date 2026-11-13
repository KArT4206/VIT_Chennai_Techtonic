"""GNM model-level tests (NumPy env). Exit code 0 only if all pass.

    PYTHONPATH=vendor/GNM env/bin/python test_gnm_numpy.py
"""

import hashlib
import sys

import numpy as np

import gnm_controls
import gnm_expr as gx
import gnm_states as gs

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


m = gx.Model(); d = gx.SemanticDecoder(); g = m.g
check(hashlib.sha256(open(gx.MODEL, "rb").read()).hexdigest() == "61d78bbfb4ad8e0b38495804a4caef3214d3df00f8c3f68761e63b41ce3747eb",
      "model file checksum matches the publisher's")
check((g.num_vertices, np.asarray(g.quads).shape[0], np.asarray(g.triangles).shape[0]) == (17821, 17662, 35324),
      "topology 17821 V / 17662 Q / 35324 T")

# linearity (basis of the exact shape-key approach)
rng = np.random.default_rng(0); a, b = rng.normal(size=383), rng.normal(size=383)
lin = np.abs((m.vertices(a + b) - m.V0) - (m.vertices(a) - m.V0) - (m.vertices(b) - m.V0)).max()
check(lin < 1e-7, f"expressions are linear (error {lin:.1e} m; limit 1e-7 m = ~3x float32 spacing at 0.4 m, GNM bases are float32)")

# eye pivots and rotation convention
for side in ("left", "right"):
    sc = m.mask["scleras"] & m.mask[f"{side}_eye"]; P = m.V0[sc]
    A = np.c_[2 * P, np.ones(len(P))]; c = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0][:3]
    off = np.linalg.norm(c - m.eye[side]["centre"]) * 1000
    check(off < 0.01, f"{side} eye joint at sclera sphere centre ({off:.4f} mm)")
R = np.zeros((4, 3)); R[m.joints.index("left_eye")] = np.radians([7, -12, 3])
V = m.vertices(rotations=R); e = m.mask["left_eye"]; c = m.eye["left"]["centre"]
th = np.linalg.norm(R[2]); k = R[2] / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
Rw = np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K
err = np.abs(V[e] - ((m.V0[e] - c) @ Rw.T + c)).max()
check(err < 1e-12, f"eye axis-angle = rigid world rotation about the eye centre ({err:.1e} m)")
nm = np.abs(V[~e] - m.V0[~e]).max()
check(nm < 1e-7, f"rotating one eye moves nothing else beyond pose-corrective noise ({nm:.1e} m; GNM correctives include the eye joints)")

# convergence: each eye's rotated gaze passes through the 35 cm target
for yaw, pitch in ((0, 0), (12, 5), (-15, -6)):
    Rg, tgt = gs.gaze_rotations(m, yaw, pitch)
    Vg = m.vertices(rotations=Rg)
    worst = 0.0
    for side in ("left", "right"):
        cc = m.eye[side]["centre"]; pu = Vg[m.mask["pupils"] & m.mask[f"{side}_eye"]].mean(0)
        dirn = (pu - cc) / np.linalg.norm(pu - cc); to = (tgt - cc) / np.linalg.norm(tgt - cc)
        worst = max(worst, np.degrees(np.arccos(np.clip(dirn @ to, -1, 1))))
    mid = (m.eye["left"]["centre"] + m.eye["right"]["centre"]) / 2
    check(worst < 0.5 and abs(np.linalg.norm(tgt - mid) - 0.35) < 1e-9,
          f"gaze ({yaw},{pitch}): both pupils point at the 35 cm target (worst {worst:.3f} deg)")

# controls: determinism and behaviour
C1 = gnm_controls.build(m, d); C2 = gnm_controls.build(gx.Model(), gx.SemanticDecoder())
check(all(np.array_equal(C1[k], C2[k]) for k in C1), "control derivation is deterministic (bit-identical rebuild)")
check(np.array_equal(d.canonical("wink_left"), d.canonical("wink_left")), "semantic decode at z=0 is deterministic")
a0 = {s: m.aperture(m.V0, s) for s in ("left", "right")}
for s, o in (("left", "right"), ("right", "left")):
    Vb = m.vertices(C1[f"blink_{s}"])
    check(m.aperture(Vb, s).max() <= 0.15 + 1e-9, f"complete blink {s}: every column closed (max gap {m.aperture(Vb, s).max():.2f} mm)")
    other = np.abs(m.aperture(Vb, o) - a0[o]).max()
    check(other < 1e-9 and np.abs(Vb[m.mask[f'{o}_eye'] | m.mask[f'{o}_orbital_region']] - m.V0[m.mask[f'{o}_eye'] | m.mask[f'{o}_orbital_region']]).max() < 1e-12,
          f"blink {s} leaves the {o} eye and its lids untouched ({other:.1e} mm)")
    frac = m.aperture(m.vertices(0.5 * C1[f"blink_{s}"]), s).mean() / a0[s].mean()
    check(0.4 < frac < 0.6, f"partial blink {s} (0.5) leaves {frac*100:.0f} % of the opening")
    lf = [m.aperture(m.vertices(w * C1[f"lid_follow_{s}"]), s).mean() for w in (-8, -4, 0, 4, 8, 12)]
    check(all(np.diff(lf) > 0), f"lid_follow {s}: opening increases monotonically with elevation {np.round(lf, 2).tolist()}")
    br = m.brow_height(m.vertices(4.0 * C1[f"brow_raise_{s}"]), s) - m.brow_height(m.V0, s)
    ap = np.abs(m.aperture(m.vertices(4.0 * C1[f"brow_raise_{s}"]), s) - a0[s]).max()
    check(br > 1.5 and ap < 0.2, f"brow_raise {s}: brow +{br:.2f} mm with lids within {ap:.2f} mm")
    lower = max(m.region_displacement(Vb)[k] for k in ("upper_lip_region", "lower_lip_region", "chin_region"))
    check(lower < 1e-9, f"blink {s}: lower face untouched ({lower:.1e} mm)")

# lid / eyeball intersection relative to neutral (as Phase 1B: base mesh tucks socket lining inside)
for s in ("left", "right"):
    skin, dep0 = m.lid_eye_intersection(m.V0, s)
    worst = 0.0
    for name, w, (yaw, pitch) in (("blink", {f"blink_{s}": 1.0}, (0, 0)),
                                  ("up", {f"lid_follow_{s}": 1.2}, (0, 12)),
                                  ("down", {f"lid_follow_{s}": -0.8}, (0, -8)),
                                  ("side", {}, (18, 0)), ("squint", {f"squint_{s}": 1.0}, (0, 0))):
        e = sum((v * (C1[k] * (10.0 if k.startswith("lid_follow") else 1.0)) for k, v in w.items()), np.zeros(383))
        Rg, _ = gs.gaze_rotations(m, yaw, pitch)
        _, dep = m.lid_eye_intersection(m.vertices(e, Rg), s)
        new = dep[(dep0 <= 0) & (dep > 0)]
        worst = max(worst, float(new.max()) if new.size else 0.0)
    check(worst < 0.5, f"{s}: lid skin entering the eyeball sphere in blink/up/down/side/squint is at most {worst:.2f} mm")

print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")
sys.exit(1 if FAILS else 0)

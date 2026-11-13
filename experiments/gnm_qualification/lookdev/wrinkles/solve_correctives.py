"""Solve corrective weights for the failing combinations (correctives.py), on exact GNM geometry.

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python lookdev/wrinkles/solve_correctives.py lookdev/wrinkles/correctives.npz

Correctives are extra amounts of existing, verified controls, driven by the PRODUCT of the two
weights that interact (standard combination-corrective practice):
  C1 blink x brow_raise   -> extra blink  k1 * (blink * raise_units/6.6)   so the blink closes again
  C2 blink x brow_furrow  -> less blink  -k2 * (blink * furrow)            so the lid stops pressing the cornea
  C3 lid_follow scaling   -> lid_follow * (1 - blink^p): p chosen so blink=1 still closes and half-blink + up
                             gaze stays within contact limits (p = 1 is the current engine rule)
  C4 half blink x side gaze -> less blink -k4 * (blink * (1 - blink) * 4) * |yaw|/15 (peaks at half closure)
Acceptance: blink cases max gap <= 0.15 mm (+1e-3 float margin); new lid/eye contact <= 0.31 mm.
"""

import sys

import numpy as np

sys.path.insert(0, ".")
import gnm_expr as gx  # noqa: E402
import gnm_states as gs  # noqa: E402

m = gx.Model(); d = gx.SemanticDecoder()
C = dict(np.load("build/gnm_controls.npz"))
both = lambda n, w: w * (C[f"{n}_left"] + C[f"{n}_right"])
furrow = np.zeros(383); furrow[:200] = d.canonical("disgust")[:200] * 1.5
base_dep = {s: m.lid_eye_intersection(m.V0, s)[1] for s in ("left", "right")}
TOL_GAP, TOL_PEN = 0.15 + 1e-3, 0.31


def measure(e, yaw=0, pitch=0):
    R, _ = gs.gaze_rotations(m, yaw, pitch)
    V = m.vertices(e, R)
    gap = max(m.aperture(V, s).max() for s in ("left", "right"))
    pen = 0.0
    for s in ("left", "right"):
        _, dep = m.lid_eye_intersection(V, s)
        new = dep[(base_dep[s] <= 0) & (dep > 0)]
        pen = max(pen, float(new.max()) if new.size else 0.0)
    return gap, pen


res = {}
# C1: blink + 3 mm brow raise
for k in np.arange(0.0, 0.5, 0.01):
    g, p = measure(both("blink", 1 + k) + both("brow_raise", 6.6))
    if g <= TOL_GAP and p <= TOL_PEN:
        break
res["k1_blink_x_raise"] = float(k); print(f"C1 blink x brow_raise: extra blink {k:.2f} -> gap {g:.3f} mm, contact {p:.2f} mm")
# C2: blink + brow lowerer
for k in np.arange(0.0, 0.5, 0.01):
    g, p = measure(both("blink", 1 - k) + furrow)
    if p <= TOL_PEN:
        break
res["k2_blink_x_furrow"] = float(k); print(f"C2 blink x brow_lowerer: blink reduced {k:.2f} -> gap {g:.3f} mm, contact {p:.2f} mm "
                                           f"{'(still closed)' if g <= TOL_GAP else '(GAP OPENS: no k satisfies both)'}")
# C3: lid_follow scaling exponent
for pexp in (1.0, 1.5, 2.0, 3.0):
    g1, p1 = measure(both("blink", 1) + both("lid_follow", 12 * (1 - 1 ** pexp)), 0, 12)
    g5, p5 = measure(both("blink", 0.5) + both("lid_follow", 12 * (1 - 0.5 ** pexp)), 0, 12)
    gd, pd = measure(both("blink", 0.5) + both("lid_follow", -7 * (1 - 0.5 ** pexp)), 0, -7)
    ok = g1 <= TOL_GAP and max(p1, p5, pd) <= TOL_PEN
    print(f"C3 lid_follow*(1-blink^{pexp}): blink+up gap {g1:.2f} / contact {p1:.2f} | half+up contact {p5:.2f} | half+down contact {pd:.2f} -> {'OK' if ok else 'fails'}")
    if ok and "p3_lidfollow_exponent" not in res:
        res["p3_lidfollow_exponent"] = pexp
# C4: half blink + side gaze
for k in np.arange(0.0, 0.5, 0.02):
    g, p = measure(both("blink", 0.5 - k * 1.0) , 15, 0)
    if p <= TOL_PEN:
        break
res["k4_halfblink_x_side15"] = float(k); print(f"C4 half blink x side 15: blink reduced {k:.2f} at |yaw| 15 -> contact {p:.2f} mm, gap {g:.2f} mm")
np.savez(sys.argv[1], **{k: np.array(v) for k, v in res.items()})
print("SOLVED", res)

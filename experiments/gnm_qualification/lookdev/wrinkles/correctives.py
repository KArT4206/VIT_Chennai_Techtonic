"""Combination / corrective analysis on exact GNM geometry (linear superposition of controls).

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python lookdev/wrinkles/correctives.py

For each combination: lid opening per eye (fixed margin columns, Phase 2B), and lid skin entering the
eyeball sphere beyond the neutral pose (Phase 2B metric). A combination needs a corrective if a blink
no longer closes (max gap > 0.15 mm) or penetration exceeds 0.31 mm (GNM's own worst single-control
value, Phase 2B). The engine already scales lid_follow by (1 - blink); both variants are reported.
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


def measure(e, yaw, pitch):
    R, t = gs.gaze_rotations(m, yaw, pitch)
    V = m.vertices(e, R)
    ap = {s: m.aperture(V, s) for s in ("left", "right")}
    pen = 0.0
    for s in ("left", "right"):
        _, dep = m.lid_eye_intersection(V, s)
        new = dep[(base_dep[s] <= 0) & (dep > 0)]
        pen = max(pen, float(new.max()) if new.size else 0.0)
    return ap, pen


def lidf(pitch, blink, suppress=True):
    return both("lid_follow", pitch * (1 - blink if suppress else 1.0))


CASES = [
    ("blink + up 12", lambda s: both("blink", 1) + lidf(12, 1, s), (0, 12), True),
    ("blink + down 7", lambda s: both("blink", 1) + lidf(-7, 1, s), (0, -7), True),
    ("squint + side 15", lambda s: both("squint", 1), (15, 0), False),
    ("brow raise 3mm + up 12", lambda s: both("brow_raise", 6.6) + lidf(12, 0, s), (0, 12), False),
    ("blink + brow raise 3mm", lambda s: both("blink", 1) + both("brow_raise", 6.6), (0, 0), True),
    ("blink + brow lowerer", lambda s: both("blink", 1) + furrow, (0, 0), True),
    ("half blink + side 15", lambda s: both("blink", 0.5) + lidf(0, 0.5, s), (15, 0), False),
    ("half blink + up 12", lambda s: both("blink", 0.5) + lidf(12, 0.5, s), (0, 12), False),
]
for name, fn, (yaw, pitch), must_close in CASES:
    for suppress in ((True, False) if "lid" in fn.__code__.co_names or "lidf" in str(fn.__code__.co_names) else (True,)):
        ap, pen = measure(fn(suppress), yaw, pitch)
        gap = max(ap["left"].max(), ap["right"].max())
        verdict = []
        if must_close and gap > 0.15:
            verdict.append(f"NOT CLOSED (gap {gap:.2f} mm)")
        if pen > 0.31:
            verdict.append(f"PENETRATION {pen:.2f} mm")
        tag = "" if suppress else "  [lid_follow NOT scaled by (1-blink)]"
        print(f"{name:26s} max gap {gap:6.2f} mm | min gap {min(ap['left'].min(), ap['right'].min()):6.2f} | "
              f"new lid/eye contact {pen:.2f} mm | {'OK' if not verdict else '; '.join(verdict)}{tag}")

"""Export GNM control offsets as shape-key data, plus GNM-computed reference poses for verification.

    PYTHONPATH=vendor/GNM env/bin/python export_keys.py build/gnm_controls.npz build/gnm_keys.npz

Shape keys (exact, because GNM expressions are linear and applied before skinning, as in Blender):
    key value 1.0 means
    blink_L / blink_R              full closure of that eye
    lid_follow_L / lid_follow_R    lids for +10 deg upward eye elevation (value -1 = 10 deg down)
    squint_L / squint_R            semantic squint (eye block)
    surprise_L / surprise_R        semantic surprise (eye block)
    brow_raise_L / brow_raise_R    +2 mm mean brow-region lift, lids still
Reference poses: GNM vertices for combinations of expression weights and eye rotations, used by the
Blender test to prove the shape keys + armature reproduce GNM exactly.
"""

import sys

import numpy as np

import gnm_expr as gx
import gnm_states as gs

m = gx.Model()
C = dict(np.load(sys.argv[1]))
V0 = m.V0
brow_unit = {s: (m.brow_height(m.vertices(C[f"brow_raise_{s}"]), s) - m.brow_height(V0, s)) for s in ("left", "right")}
spec = {}
for s, L in (("left", "L"), ("right", "R")):
    spec[f"blink_{L}"] = C[f"blink_{s}"]
    spec[f"lid_follow_{L}"] = C[f"lid_follow_{s}"] * 10.0
    spec[f"squint_{L}"] = C[f"squint_{s}"]
    spec[f"surprise_{L}"] = C[f"surprise_{s}"]
    spec[f"brow_raise_{L}"] = C[f"brow_raise_{s}"] * (2.0 / brow_unit[s])
keys = {k: (np.tensordot(v, m.B, 1)).astype(np.float32) for k, v in spec.items()}

# reference poses: (key weights, yaw, pitch)
refs = [({}, 0, 0), ({"blink_L": 1.0}, 0, 0), ({"blink_L": 0.5, "blink_R": 0.5}, 0, 0),
        ({"lid_follow_L": 1.2, "lid_follow_R": 1.2}, 0, 12), ({"lid_follow_L": -0.7, "lid_follow_R": -0.7}, 0, -7),
        ({"squint_L": 1.0, "brow_raise_R": 1.0}, 15, 3), ({"surprise_L": 1.0, "surprise_R": 1.0, "blink_R": 0.3}, -18, 8)]
RV, RW, RR = [], [], []
for w, yaw, pitch in refs:
    e = sum((wt * spec[k] for k, wt in w.items()), np.zeros(383))
    R, _ = gs.gaze_rotations(m, yaw, pitch)
    RV.append(m.vertices(e, R)); RR.append(R)
    RW.append(np.array([w.get(k, 0.0) for k in keys], np.float32))
np.savez(sys.argv[2], key_names=np.array(list(keys)), key_offsets=np.stack(list(keys.values())),
         coeffs=np.stack(list(spec.values())), ref_vertices=np.stack(RV).astype(np.float64),
         ref_weights=np.stack(RW), ref_rotvecs=np.stack(RR), ref_yaw_pitch=np.array([(y, p) for _, y, p in refs], float),
         joint_names=np.array(m.joints), joints=m.J, brow_mm_per_unit=np.array([brow_unit["left"], brow_unit["right"]]))
print("keys:", list(keys), "| brow mm per control unit L/R:", round(brow_unit["left"], 3), round(brow_unit["right"], 3))

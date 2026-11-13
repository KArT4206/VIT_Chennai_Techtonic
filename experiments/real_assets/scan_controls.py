"""Re-derive the Phase 2B lid/brow controls on the scan-shaped GNM base (same fitting procedure,
gnm_controls.build), because GNM-template blink offsets left a 1.2-2.3 mm gap on the scan's lids.

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python ../real_assets/scan_controls.py <scan_gnm_fit.npz> <extracted OBJ dir> <out_controls.npz> <out_keys_offsets.npz>
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import gnm_controls as gc
import gnm_expr as gx

fit = np.load(sys.argv[1]); X = sys.argv[2]
m = gx.Model(); d = gx.SemanticDecoder()
V = fit["vertices_fit"].copy(); V[fit["skin_vertex_ids"]] = fit["scan_skin"]
def obj(p): return np.array([[float(x) for x in l.split()[1:4]] for l in open(p, errors="ignore") if l.startswith("v ")])
def sph(P):
    A = np.c_[2 * P, np.ones(len(P))]; c = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0]; return c[:3], np.sqrt(c[3] + c[:3] @ c[:3])
for side, name in (("left", "Left"), ("right", "Right")):
    cs, rs = sph(obj(f"{X}/Realtime Eyeball {name}.obj")); ids = np.nonzero(m.mask[f"{side}_eye"])[0]
    cg, rg = sph(m.V0[m.mask["scleras"] & m.mask[f"{side}_eye"]]); V[ids] = (m.V0[ids] - cg) * (rs / rg) + cs
    m.eye[side]["centre"] = cs; m.eye[side]["r_sclera"] = rs
m.V0 = V
# Model.vertices() starts from GNM's template; on the scan base a shape is scan base + GNM offset
# (first run mixed the two: the "other eye" moved 0.999 mm, which is impossible for an eye-block control)
m.vertices = lambda expression=None, rotations=None: V + (0 if expression is None else np.tensordot(expression, m.B, 1))
for side in ("left", "right"):
    m.eye[side]["margins"] = m._margins(side, m.eye[side]["centre"], m.eye[side]["r_sclera"])
ctrl = gc.build(m, d)
rep = gc.measure(m, ctrl)
base = {s: m.lid_eye_intersection(V, s)[1] for s in ("left", "right")}
for k in ("blink_left", "blink_right", "lid_follow_left", "brow_raise_left"):
    for w, r in rep[k].items():
        print(f"{k:16s} w={w:>5s} opening {r['aperture_mm']} brow {r['brow_mm']:+.2f} other eye {r['other_eye_aperture_change_mm']:.3f}")
for s in ("left", "right"):
    W = V + np.tensordot(ctrl[f"blink_{s}"], m.B, 1)
    _, dep = m.lid_eye_intersection(W, s); new = dep[(base[s] <= 0) & (dep > 0)]
    print(f"blink_{s} on scan base: max gap {m.aperture(W, s).max():.2f} mm, new lid/eye contact {float(new.max()) if new.size else 0:.2f} mm")
np.savez(sys.argv[3], **ctrl)
brow_unit = {s: m.brow_height(m.vertices(ctrl[f"brow_raise_{s}"]), s) - m.brow_height(V, s) for s in ("left", "right")}
spec = {}
for s, L in (("left", "L"), ("right", "R")):
    spec[f"blink_{L}"] = ctrl[f"blink_{s}"]; spec[f"lid_follow_{L}"] = ctrl[f"lid_follow_{s}"] * 10.0
    spec[f"squint_{L}"] = ctrl[f"squint_{s}"]; spec[f"surprise_{L}"] = ctrl[f"surprise_{s}"]
    spec[f"brow_raise_{L}"] = ctrl[f"brow_raise_{s}"] * (2.0 / brow_unit[s])
np.savez(sys.argv[4], **{k: np.tensordot(v, m.B, 1).astype(np.float32) for k, v in spec.items()})
print("saved controls and key offsets")

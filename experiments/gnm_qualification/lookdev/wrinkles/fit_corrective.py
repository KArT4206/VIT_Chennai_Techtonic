"""Fit the blink x brow-lowerer corrective inside GNM's eye-block expression space (ridge LS, as Phase 2B),
and export corrective shape-key offsets (C1 blink x raise, C2 blink x lowerer) for Blender.

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python lookdev/wrinkles/fit_corrective.py lookdev/wrinkles/corrective_keys.npz
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import gnm_controls as gc
import gnm_expr as gx

m = gx.Model(); d = gx.SemanticDecoder(); C = dict(np.load("build/gnm_controls.npz")); c = d.canonical("disgust")
base = {s: m.lid_eye_intersection(m.V0, s)[1] for s in ("left", "right")}
out = {}
for side, sl, L in (("left", slice(0, 100), "L"), ("right", slice(100, 200), "R")):
    f = np.zeros(383); f[sl] = c[sl] * 1.0
    e0 = C[f"blink_{side}"] + f
    V = m.vertices(e0)
    skin, dep = m.lid_eye_intersection(V, side)
    bad = skin[(base[side][skin] <= 0) & (dep > 0)] if False else None
    _, dep_all = m.lid_eye_intersection(V, side)
    pen = (base[side] <= 0) & (dep_all > 0)
    idx = skin[pen]
    ctr = m.eye[side]["centre"]
    T = np.zeros_like(V); W = gc.eye_region(m, side).astype(float)
    rdir = (V[idx] - ctr); rdir /= np.linalg.norm(rdir, axis=1, keepdims=True)
    T[idx] = rdir * (dep_all[pen][:, None] / 1000.0 + 0.00005)        # push out to 0.05 mm clearance
    W[idx] += 20.0
    corr = gc.fit(m, side, T, W, lam=1e-6)
    for s_ in (1.0,):
        Vc = m.vertices(e0 + corr)
        _, dc = m.lid_eye_intersection(Vc, side); newd = dc[(base[side] <= 0) & (dc > 0)]
        gap = m.aperture(Vc, side).max()
        other = np.abs(Vc - V)[~(m.mask[f"{side}_orbital_region"] | m.mask[f"{side}_brow_region"] | m.mask[f"{side}_eye"])].max() * 1000
        print(f"{side}: {len(idx)} penetrating verts, max {dep_all[pen].max():.2f} mm -> after corrective {newd.max() if newd.size else 0:.2f} mm; "
              f"gap {gap:.2f} mm; movement outside orbit/brow {other:.3f} mm; |coef| {np.abs(corr).max():.2f}")
    out[f"corr_blink_lowerer_{L}"] = np.tensordot(corr, m.B, 1).astype(np.float32)
    out[f"corr_blink_raise_{L}"] = (0.02 * np.tensordot(C[f"blink_{side}"], m.B, 1)).astype(np.float32)
np.savez(sys.argv[1], **out); print("saved", sys.argv[1])

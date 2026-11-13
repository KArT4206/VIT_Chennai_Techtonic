"""Per-expression skin strain on the exact GNM geometry: where the skin compresses, by how much, and in
which direction. These drive the expression wrinkle maps (no random wrinkle textures).

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python lookdev/wrinkles/strain.py lookdev/wrinkles/strain.npz

For every skin triangle the deformation gradient F (3x2) maps the neutral triangle's edges (in its own
orthonormal tangent frame) to the expression's edges. C = F^T F; its smaller eigenvalue gives the
largest compression ratio lambda_min, its eigenvector the compression direction. Per vertex the
area-weighted structure tensor sum(c * d d^T) gives the dominant direction; folds form perpendicular
to it. Expressions (both eyes, controls from Phase 2B / semantic GNM, eye blocks only):
    blink        blink_left + blink_right (fitted, Phase 2B), weight 1
    squint       semantic SQUINT eye blocks, weight 1
    brow_raise   brow_raise (fitted, +0.45 mm per unit, measured), weight 6.6 (= 3 mm)
    brow_furrow  semantic DISGUST eye blocks, weight 1.5 (AU4-like: inner brows down 1.7 mm, together 1.8 mm)
Side split: left = vertices with x > 0 (subject's left), right = x < 0.
"""

import sys

import numpy as np

sys.path.insert(0, ".")
import gnm_expr as gx  # noqa: E402

m = gx.Model(); d = gx.SemanticDecoder()
C = dict(np.load("build/gnm_controls.npz"))
g = m.g
Q = np.asarray(g.quads); tiles = np.asarray(g.quad_udim_tiles).astype(int)
Qs = Q[tiles == 1001]
T = np.concatenate([Qs[:, [0, 1, 2]], Qs[:, [0, 2, 3]]])
V0 = m.V0
EDG = np.unique(np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1), axis=0)


def eyeblocks(lab, w):
    c = np.zeros(383); full = d.canonical(lab); c[:200] = full[:200]; return c * w


EXPR = {
    "blink": C["blink_left"] + C["blink_right"],
    "squint": eyeblocks("squint", 1.0),
    "brow_raise": 6.6 * (C["brow_raise_left"] + C["brow_raise_right"]),
    "brow_furrow": eyeblocks("disgust", 1.5),
}


def strain(V1):
    a, b, c = V0[T[:, 0]], V0[T[:, 1]], V0[T[:, 2]]
    e1, e2 = b - a, c - a
    t1 = e1 / np.linalg.norm(e1, axis=1, keepdims=True)
    n = np.cross(e1, e2); area = 0.5 * np.linalg.norm(n, axis=1); n /= (2 * area[:, None])
    t2 = np.cross(n, t1)
    E = np.stack([np.stack([(e1 * t1).sum(1), (e1 * t2).sum(1)], 1), np.stack([(e2 * t1).sum(1), (e2 * t2).sum(1)], 1)], 2)   # 2x2 neutral
    a1, b1, c1 = V1[T[:, 0]], V1[T[:, 1]], V1[T[:, 2]]
    D = np.stack([b1 - a1, c1 - a1], 2)                                     # 3x2 deformed
    F = D @ np.linalg.inv(E)                                                # 3x2
    Cm = np.transpose(F, (0, 2, 1)) @ F                                     # 2x2
    w, v = np.linalg.eigh(Cm)                                               # ascending
    lam_min, lam_max = np.sqrt(np.maximum(w[:, 0], 0)), np.sqrt(np.maximum(w[:, 1], 0))
    dir3 = t1 * v[:, 0, 0:1] + t2 * v[:, 1, 0:1]                            # compression direction (neutral)
    comp = np.clip(1.0 - lam_min, 0, None)
    # per-vertex: area-weighted compression and structure-tensor direction
    nv = len(V0)
    cv = np.zeros(nv); wv = np.zeros(nv); S = np.zeros((nv, 3, 3))
    for k in range(3):
        np.add.at(cv, T[:, k], comp * area); np.add.at(wv, T[:, k], area)
        np.add.at(S, T[:, k], (comp * area)[:, None, None] * dir3[:, :, None] * dir3[:, None, :])
    cv /= np.maximum(wv, 1e-12)
    # smooth the (sign-free) structure tensor over the mesh: raw per-vertex directions were noisy and
    # sign-ambiguous, which turned creases into speckle (first bake)
    for _ in range(12):
        acc = np.zeros_like(S); cnt = np.zeros(nv)
        np.add.at(acc, EDG[:, 0], S[EDG[:, 1]]); np.add.at(acc, EDG[:, 1], S[EDG[:, 0]])
        np.add.at(cnt, EDG[:, 0], 1); np.add.at(cnt, EDG[:, 1], 1)
        S = 0.5 * S + 0.5 * acc / np.maximum(cnt, 1)[:, None, None]
    ev, evec = np.linalg.eigh(S)
    dv = evec[:, :, 2]
    return cv, dv, comp, lam_max


def stripe_phase(cv, dv, c_min=0.012):
    """Scalar phase phi (metres) on the compressed region whose gradient follows the compression
    direction: least squares over mesh edges of (phi_j - phi_i - d_ij . (P_j - P_i))^2, with d only
    defined up to sign aligned per edge and to the region's dominant axis. Creases are f(phi / spacing):
    parallel folds that bend with the face, no level-set rings (first bake used P . d)."""
    sel = np.nonzero(cv > c_min)[0]
    idx = -np.ones(len(V0), np.int64); idx[sel] = np.arange(len(sel))
    e = EDG[(idx[EDG[:, 0]] >= 0) & (idx[EDG[:, 1]] >= 0)]
    i, j = idx[e[:, 0]], idx[e[:, 1]]
    di, dj = dv[e[:, 0]], dv[e[:, 1]]
    dj = np.where(((di * dj).sum(1) < 0)[:, None], -dj, dj)
    dm = di + dj; dm /= np.maximum(np.linalg.norm(dm, axis=1, keepdims=True), 1e-12)
    w_, vv = np.linalg.eigh((cv[sel, None, None] * dv[sel, :, None] * dv[sel, None, :]).sum(0))
    ref = vv[:, 2]
    dm = np.where(((dm * ref).sum(1) < 0)[:, None], -dm, dm)
    b = (dm * (V0[e[:, 1]] - V0[e[:, 0]])).sum(1)
    n = len(sel)
    A = np.zeros((n, n)); rhs = np.zeros(n)
    np.add.at(A, (i, i), 1); np.add.at(A, (j, j), 1); np.add.at(A, (i, j), -1); np.add.at(A, (j, i), -1)
    np.add.at(rhs, j, b); np.add.at(rhs, i, -b)
    A[np.arange(n), np.arange(n)] += 1e-6
    phi = np.zeros(len(V0)); phi[sel] = np.linalg.solve(A, rhs)
    resid = np.sqrt(((phi[e[:, 1]] - phi[e[:, 0]] - b) ** 2).mean()) / np.sqrt((b ** 2).mean())
    return phi, len(sel), resid


out = {}
for name, e in EXPR.items():
    V1 = m.vertices(e)
    cv, dv, comp, lmax = strain(V1)
    out[f"{name}_comp"] = cv.astype(np.float32); out[f"{name}_dir"] = dv.astype(np.float32)
    phi, nsel, resid = stripe_phase(cv, dv)
    out[f"{name}_phi"] = phi.astype(np.float32)
    print(f"  phase field: {nsel} vertices, relative gradient residual {resid:.3f}")
    disp = np.linalg.norm(V1 - V0, axis=1) * 1000
    regs = {r: round(float(cv[m.mask[r]].max()) * 100, 1) for r in
            ("left_orbital_region", "left_brow_region", "middle_brow_region", "forehead_region", "left_zygomatic_region", "left_infraorbital_region")}
    print(f"{name:12s} max disp {disp.max():5.2f} mm | vertex compression max {cv.max()*100:5.1f} % "
          f"(>3%: {int((cv > 0.03).sum())} verts) | stretch max {(lmax.max()-1)*100:5.1f} % | by region % {regs}")
out["side_left"] = (V0[:, 0] > 0).astype(np.float32)
np.savez(sys.argv[1], **out)
print("saved", sys.argv[1])

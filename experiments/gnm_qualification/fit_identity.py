"""Fit GNM's own head-identity shape to the MakeHuman head, for a geometry-aware texture bake.

    PYTHONPATH=vendor/GNM env/bin/python fit_identity.py build/mh_head.npz build/fit.npz

Only GNM's identity coefficients (170 head components, ridge-regularised) and a rigid transform of
the MakeHuman head are estimated. GNM topology, face order and UVs are untouched, so a texture baked
onto the fitted GNM surface lives in GNM's standard 1001 UV space and applies to any GNM identity.

Alternating optimisation:
  1. rigid init: MakeHuman eye-centre midpoint -> GNM eye midpoint, inter-eye axis aligned
  2. repeat: nearest MakeHuman vertex for each GNM face/skull vertex (point-to-plane residual,
     rejecting > 12 mm or normal disagreement), ridge solve for identity, Procrustes re-alignment
"""

import sys

import numpy as np

import gnm_expr as gx


def normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], n)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def nearest(A, B, chunk=2048):
    idx = np.empty(len(A), np.int64); dist = np.empty(len(A))
    for s in range(0, len(A), chunk):
        d = ((A[s:s + chunk, None, :] - B[None]) ** 2).sum(-1)
        j = d.argmin(1); idx[s:s + chunk] = j; dist[s:s + chunk] = np.sqrt(d[np.arange(len(j)), j])
    return idx, dist


def procrustes(X, Y):
    """Rigid R, t minimising |R X + t - Y|."""
    mx, my = X.mean(0), Y.mean(0)
    U, _, Vt = np.linalg.svd((X - mx).T @ (Y - my))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, my - R @ mx


def main(mh_path, out, iters=20, lam=float(__import__("os").environ.get("FIT_LAMBDA", "2e-7"))):
    m = gx.Model(); g = m.g
    mh = np.load(mh_path)
    P0, F = mh["vertices"], mh["triangles"]
    VB = np.asarray(g.vertex_identity_basis)[:170].astype(np.float64)          # (170, V, 3)
    sel = m.mask["skin_exterior"] & ~m.mask["ears"] & (m.V0[:, 1] > m.eye["left"]["centre"][1] - 0.13)
    w = np.where(m.mask["hockey_mask"], 4.0, 1.0)[sel]
    # rigid init from the eyes
    gmid = (m.eye["left"]["centre"] + m.eye["right"]["centre"]) / 2
    mmid = (mh["eye_left"] + mh["eye_right"]) / 2
    ax_g = m.eye["left"]["centre"] - m.eye["right"]["centre"]; ax_m = mh["eye_left"] - mh["eye_right"]
    R, t = procrustes(np.stack([mh["eye_left"], mh["eye_right"], mmid + [0, 0, 0.05], mmid + [0, 0.05, 0]]),
                      np.stack([m.eye["left"]["centre"], m.eye["right"]["centre"], gmid + [0, 0, 0.05], gmid + [0, 0.05, 0]]))
    c = np.zeros(170)
    hist = []
    for it in range(iters):
        P = P0 @ R.T + t
        PN = normals(P, F)
        V = m.V0 + np.tensordot(c, VB, 1)
        Vs = V[sel]
        j, d = nearest(Vs, P)
        Vn = normals(V, np.asarray(g.triangles))[sel]
        ok = (d < 0.012) & ((Vn * PN[j]).sum(1) > 0.5)
        n = PN[j][ok]
        r = ((P[j][ok] - Vs[ok]) * n).sum(1)                              # point-to-plane residual
        A = (VB[:, sel][:, ok] * n[None]).sum(-1).T                           # (N, 170)
        ww = w[ok]
        dc = np.linalg.solve((A * ww[:, None]).T @ A + lam * len(r) * np.eye(170), (A * ww[:, None]).T @ r - lam * len(r) * c)
        c = c + dc
        V = m.V0 + np.tensordot(c, VB, 1)
        # rigid re-alignment of MakeHuman onto the updated GNM surface (using current correspondences)
        Rk, tk = procrustes(P[j][ok], V[sel][ok])
        R, t = Rk @ R, Rk @ t + tk
        rms = float(np.sqrt((r ** 2).mean()) * 1000)
        hist.append((it, int(ok.sum()), rms, float(np.abs(c).max())))
        print(f"iter {it:2d}: {ok.sum():5d} pairs, point-to-plane RMS {rms:.3f} mm, max|c| {np.abs(c).max():.2f}")
    I = np.zeros(253); I[:170] = c
    Vfit = np.asarray(g(I, np.zeros(383), np.zeros((4, 3)), np.zeros(3)))
    Jfit = np.asarray(g.template_joint_positions) + np.tensordot(I, np.asarray(g.joint_identity_basis), 1)
    np.savez(out, identity=I, vertices=Vfit, joints=Jfit, mh_R=R, mh_t=t, history=np.array(hist))
    # final surface distance stats (face region), both directions
    P = P0 @ R.T + t
    face = sel & m.mask["hockey_mask"]
    j, d = nearest(Vfit[face], P)
    pp = np.abs(((P[j] - Vfit[face]) * normals(P, F)[j]).sum(1))
    print(f"final face-region GNM->MH: point-to-plane median {np.median(pp)*1000:.2f} mm, 95% {np.percentile(pp,95)*1000:.2f} mm "
          f"(nearest-vertex median {np.median(d)*1000:.2f} mm; MakeHuman vertex spacing inflates this)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

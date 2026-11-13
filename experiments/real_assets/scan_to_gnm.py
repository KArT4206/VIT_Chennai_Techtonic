"""GNM compatibility analysis of the 3D Scan Store head (CPU, exact correspondences).

    cd experiments/gnm_qualification && PYTHONPATH=vendor/GNM env/bin/python ../real_assets/scan_to_gnm.py <extracted dir> <out.npz>

The scan's Head mesh is on GNM topology (verified: same 12,410 quads in the same order, same vertex
indexing as GNM tile 1001, UVs equal to 3e-8). So GNM identity can be fitted by direct linear least
squares on known correspondences: no ICP, no projection.

Fit: scan_skin ~ template + B_id[:170] c + t (translation), ridge lambda on c; report residuals.
Eyes: the scan's eyeball/lens meshes are NOT GNM topology (1,666 vertices vs GNM's 771 per eye);
their sphere centres/radii are compared with GNM's fitted eye joints.
"""

import sys

import numpy as np

sys.path.insert(0, ".")
import gnm_expr as gx  # noqa: E402

X, out = sys.argv[1], sys.argv[2]


def obj_vertices(p):
    return np.array([[float(x) for x in l.split()[1:4]] for l in open(p, errors="ignore") if l.startswith("v ")])


m = gx.Model(); g = m.g
Q = np.asarray(g.quads); tiles = np.asarray(g.quad_udim_tiles).astype(int)
skin_v = np.unique(Q[tiles == 1001])                          # GNM vertex ids of tile 1001, ascending
S = obj_vertices(f"{X}/OBJ/Head.obj")
assert len(S) == len(skin_v), "unexpected vertex count"
# The OBJ's vertex order is the GNM-local renumbering of tile 1001 (verified face-by-face earlier)
B = np.asarray(g.vertex_identity_basis)[:170][:, skin_v].astype(np.float64)    # (170, n, 3)
T0 = m.V0[skin_v]
n = len(skin_v)
A = np.concatenate([B.reshape(170, -1).T, np.tile(np.eye(3), (n, 1))], 1)       # (3n, 173)
y = (S - T0).reshape(-1)
res = {}
for lam in (1e-6, 1e-7, 1e-8, 0.0):
    R = lam * n * np.eye(173); R[170:, 170:] = 0
    x = np.linalg.solve(A.T @ A + R, A.T @ y)
    fit = T0 + (B.reshape(170, -1).T @ x[:170]).reshape(-1, 3) + x[170:]
    d = np.linalg.norm(S - fit, axis=1) * 1000
    face = m.mask["hockey_mask"][skin_v]
    print(f"lambda {lam:7.0e}: residual all median {np.median(d):5.2f} mm, 95% {np.percentile(d, 95):5.2f}, max {d.max():5.2f} | "
          f"face median {np.median(d[face]):5.2f} mm, max {d[face].max():5.2f} | max|c| {np.abs(x[:170]).max():5.2f} | t mm {np.round(x[170:] * 1000, 2)}")
    res[lam] = (x, d)
lam = 1e-7
x, d = res[lam]
ident = np.zeros(253); ident[:170] = x[:170]
V_fit = np.asarray(g(ident, np.zeros(383), np.zeros((4, 3)), np.zeros(3))) + x[170:]
J_fit = np.asarray(g.template_joint_positions) + np.tensordot(ident, np.asarray(g.joint_identity_basis), 1) + x[170:]
print(f"chosen lambda {lam}: GNM identity explains the scan shape to median {np.median(d):.2f} mm; the rest is subject-specific detail")

# eyes: scan eyeball / lens meshes (OBJ) vs GNM fitted eye joints
for side, name in (("left", "Left"), ("right", "Right")):
    for part in ("Realtime Eyeball", "Lens"):
        P = obj_vertices(f"{X}/OBJ/{part} {name}.obj")
        Aq = np.c_[2 * P, np.ones(len(P))]; c = np.linalg.lstsq(Aq, (P ** 2).sum(1), rcond=None)[0]
        ctr = c[:3]; rad = np.sqrt(c[3] + ctr @ ctr)
        rms = np.sqrt(((np.linalg.norm(P - ctr, axis=1) - rad) ** 2).mean())
        jf = J_fit[m.joints.index(f"{side}_eye")]
        print(f"scan {part} {name}: {len(P)} v, sphere centre {np.round(ctr * 1000, 2)} mm r {rad * 1000:.2f} mm (fit rms {rms * 1000:.3f}) | "
              f"GNM-fitted {side}_eye joint {np.round(jf * 1000, 2)} -> offset {np.linalg.norm(ctr - jf) * 1000:.2f} mm")
    # which side is which: GNM left eye is +X
np.savez(out, identity=ident, translation=x[170:], vertices_fit=V_fit, joints_fit=J_fit, scan_skin=S, skin_vertex_ids=skin_v,
         residual_mm=d)
print("saved", out)

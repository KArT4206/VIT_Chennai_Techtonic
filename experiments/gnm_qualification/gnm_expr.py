"""GNM expression analysis toolkit (NumPy only; no TensorFlow).

- load(): the official GNM Head v3 model.
- SemanticDecoder: NumPy re-implementation of GNM's ExpressionSampler decoder
  (Keras Functional: concat[z(64), onehot(20)] -> Dense64/128/256/512 ReLU -> Dense383 linear),
  read with h5py from vendor/GNM/gnm/shape/data/semantic_sampler/expression_decoder_model.h5.
  canonical(label) decodes the latent mean z = 0, which is deterministic.
- Lids: fixed per-eye margin vertex sets chosen once on the neutral mesh; aperture(V) is the
  vertical gap (mm) between the upper and lower margin vertex of each column, so closure is
  measured on the same vertices however far the lid travels.

GNM frame: metres, Y up, face looks +Z, subject's left eye at +X.
"""

import os

import h5py
import numpy as np
from gnm.shape import gnm_numpy

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "model", "v3_0", "gnm_head.npz")
DECODER = os.path.join(HERE, "vendor", "GNM", "gnm", "shape", "data", "semantic_sampler", "expression_decoder_model.h5")
LABELS = ["surprise", "disgust", "suck", "compress_face", "stretch_face", "happy", "squint", "platysma", "blow",
          "funneler", "smile_wide", "corners_down", "pucker", "wink_left", "wink_right", "mouth_left", "mouth_right",
          "lips_roll_in", "snarl", "tongue_center"]
COLUMNS_MM = (-5.0, -2.5, 0.0, 2.5, 5.0)       # lateral offsets from the eye centre for aperture columns


def load():
    return gnm_numpy.GNM.from_custom_file(MODEL)


class SemanticDecoder:
    def __init__(self, path=DECODER):
        f = h5py.File(path, "r")
        w = f["model_weights"]
        self.layers = []
        for n in ("dense_13", "dense_14", "dense_15", "dense_16", "dense_17"):
            self.layers.append((np.asarray(w[n][n]["kernel:0"]), np.asarray(w[n][n]["bias:0"])))

    def decode(self, z, onehot):
        x = np.concatenate([z, onehot], axis=-1).astype(np.float32)
        for i, (k, b) in enumerate(self.layers):
            x = x @ k + b
            if i < len(self.layers) - 1:
                x = np.maximum(x, 0.0)
        return x

    def canonical(self, label, weight=1.0):
        oh = np.zeros((1, 20), np.float32)
        oh[0, LABELS.index(label)] = weight
        return self.decode(np.zeros((1, 64), np.float32), oh)[0]


class Model:
    def __init__(self):
        self.g = load()
        g = self.g
        self.I = np.zeros(g.identity_dim)
        self.R0 = np.zeros((g.num_joints, 3))
        self.T0 = np.zeros(3)
        self.V0 = np.asarray(g.template_vertex_positions).astype(np.float64)
        self.B = np.asarray(g.expression_basis).astype(np.float64)        # (383, V, 3)
        self.names = [str(n) for n in g.expression_names]
        self.mask = {str(n): np.asarray(g.vertex_group_mask(n)).astype(bool) for n in g.vertex_group_names}
        self.J = np.asarray(g.template_joint_positions).astype(np.float64)
        self.joints = [str(n) for n in g.joint_names]
        self.eye = {}
        for side in ("left", "right"):
            ji = self.joints.index(f"{side}_eye")
            c = self.J[ji]
            sc = self.mask["scleras"] & self.mask[f"{side}_eye"]
            r = float(np.linalg.norm(self.V0[sc] - c, axis=1).mean())
            cor = self.mask["eye_exteriors"] & self.mask[f"{side}_eye"]
            rc = float(np.linalg.norm(self.V0[cor] - c, axis=1).max())
            self.eye[side] = {"centre": c, "r_sclera": r, "r_cornea_max": rc, "margins": self._margins(side, c, r)}

    def vertices(self, expression=None, rotations=None):
        e = np.zeros(self.g.expression_dim) if expression is None else expression
        r = self.R0 if rotations is None else rotations
        return np.asarray(self.g(self.I, e, r, self.T0)).astype(np.float64)

    def _margins(self, side, c, r):
        """Per column: (upper margin vertex, lower margin vertex) on the neutral skin around the opening."""
        skin = self.mask["skin"] & self.mask[f"{side}_orbital_region"] if f"{side}_orbital_region" in self.mask else self.mask["skin"]
        idx = np.nonzero(skin)[0]
        P = self.V0[idx]
        front = P[:, 2] > c[2] + 0.35 * r
        near = np.linalg.norm(P - c, axis=1) < r + 0.004
        out = []
        for dx in COLUMNS_MM:
            col = np.abs(P[:, 0] - (c[0] + dx / 1000.0)) < 0.0012
            sel = front & near & col
            up = idx[sel & (P[:, 1] > c[1])]
            lo = idx[sel & (P[:, 1] <= c[1])]
            if len(up) and len(lo):
                out.append((int(up[np.argmin(self.V0[up, 1])]), int(lo[np.argmax(self.V0[lo, 1])])))
        return out

    def aperture(self, V, side):
        """Vertical lid opening (mm) per column: upper margin y - lower margin y. <= 0 means closed."""
        return np.array([(V[u, 1] - V[l, 1]) * 1000.0 for u, l in self.eye[side]["margins"]])

    def lid_eye_intersection(self, V, side, rotations=None):
        """Deepest skin penetration (mm) into the eyeball sphere / corneal bulge of one eye.

        Compared later against the neutral pose, as in Phase 1B (the base mesh's socket lining sits
        inside the sphere by design)."""
        c = self.eye[side]["centre"]
        skin = np.nonzero(self.mask["skin"] & self.mask[f"{side}_orbital_region"])[0]
        d = np.linalg.norm(V[skin] - c, axis=1)
        return skin, (self.eye[side]["r_sclera"] - d) * 1000.0

    def region_displacement(self, V, Vref=None):
        Vref = self.V0 if Vref is None else Vref
        d = np.linalg.norm(V - Vref, axis=1) * 1000.0
        regs = ["left_orbital_region", "right_orbital_region", "left_brow_region", "right_brow_region",
                "middle_brow_region", "forehead_region", "nose_region", "upper_lip_region", "lower_lip_region",
                "chin_region", "left_cheek_region", "right_cheek_region"]
        return {r: round(float(d[self.mask[r]].max()), 3) for r in regs if r in self.mask}

    def brow_height(self, V, side):
        """Mean vertical position (mm) of the brow region vertices."""
        return float(V[self.mask[f"{side}_brow_region"], 1].mean() * 1000.0)

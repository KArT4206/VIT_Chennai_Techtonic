"""Does the synthetic data train a gaze estimator?  (numpy only; pillow + matplotlib for I/O and plots)

    python tools/train_gaze_model.py <dataset_dir> [<dataset_dir> ...] --out <dir>

Input to the model: ONLY the rendered RGB image. Two fixed eye crops per image (placed once per head from the
dataset's mean pupil positions, not per sample), grey, 64x32 each, normalised per crop (zero mean, unit variance:
removes the randomised lighting gain). Target: the binocular gaze direction (yaw, pitch) in degrees, mean of the
two eyes' ground-truth gaze vectors.
Model: kernel ridge regression with an RBF kernel; gamma and lambda picked by 5-fold cross-validation on the
training split only. Evaluation: a held-out 20 % test split (fixed seed), reported as mean / median / 95th-percentile
angular error, against a baseline that always predicts the training-set mean gaze.
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("datasets", nargs="+"); ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
CW, CH = 64, 32

def load(ds):
    recs = [json.loads(l) for l in open(os.path.join(ds, "labels.jsonl"))]
    mL = np.mean([r["pupil_center_2D_L"] for r in recs], 0); mR = np.mean([r["pupil_center_2D_R"] for r in recs], 0)
    half_w = 0.32 * abs(mL[0] - mR[0]); half_h = half_w / 2            # crop size scales with the eye spacing
    X, Y = [], []
    for r in recs:
        im = Image.open(os.path.join(ds, r["rgb"])).convert("L")
        feats = []
        for c in (mL, mR):
            box = (int(c[0] - half_w), int(c[1] - half_h), int(c[0] + half_w), int(c[1] + half_h))
            a = np.asarray(im.crop(box).resize((CW, CH), Image.BILINEAR), dtype=float).ravel()
            feats.append((a - a.mean()) / (a.std() + 1e-6))
        X.append(np.concatenate(feats))
        g = (np.array(r["gaze_vector_L"]) + np.array(r["gaze_vector_R"])); g /= np.linalg.norm(g)
        Y.append([math.degrees(math.atan2(g[0], -g[1])), math.degrees(math.asin(g[2]))])
    return np.array(X), np.array(Y), recs

def ang(a, b):
    def vec(yp):
        y, p = np.radians(yp[:, 0]), np.radians(yp[:, 1])
        return np.stack([np.sin(y) * np.cos(p), -np.cos(y) * np.cos(p), np.sin(p)], 1)
    return np.degrees(np.arccos(np.clip((vec(a) * vec(b)).sum(1), -1, 1)))

def rbf(A, B, g):
    d = (A ** 2).sum(1)[:, None] + (B ** 2).sum(1)[None] - 2 * A @ B.T
    return np.exp(-g * d / A.shape[1])

def fit(X, Y, g, lam):
    K = rbf(X, X, g); alpha = np.linalg.solve(K + lam * np.eye(len(X)), Y - Y.mean(0)); return (X, alpha, Y.mean(0), g)

def predict(m, X):
    Xtr, alpha, mu, g = m; return rbf(X, Xtr, g) @ alpha + mu

def cv_select(X, Y, rng):
    idx = rng.permutation(len(X)); folds = np.array_split(idx, 5); best = None
    for g in (0.01, 0.03, 0.1, 0.3, 1.0):
        for lam in (1e-3, 1e-2, 1e-1, 1.0):
            errs = []
            for f in folds:
                tr = np.setdiff1d(idx, f); m = fit(X[tr], Y[tr], g, lam); errs.append(ang(predict(m, X[f]), Y[f]).mean())
            e = float(np.mean(errs))
            if best is None or e < best[0]:
                best = (e, g, lam)
    return best

results = {}
data = {os.path.basename(os.path.normpath(d)): load(d) for d in args.datasets}
rng = np.random.default_rng(args.seed)
split = {}
for name, (X, Y, recs) in data.items():
    p = rng.permutation(len(X)); n_te = len(X) // 5; split[name] = (p[n_te:], p[:n_te])

def run(train_names, test_name, tag):
    Xtr = np.concatenate([data[n][0][split[n][0]] for n in train_names]); Ytr = np.concatenate([data[n][1][split[n][0]] for n in train_names])
    Xte, Yte = data[test_name][0][split[test_name][1]], data[test_name][1][split[test_name][1]]
    cv, g, lam = cv_select(Xtr, Ytr, np.random.default_rng(args.seed + 1))
    m = fit(Xtr, Ytr, g, lam); P = predict(m, Xte); e = ang(P, Yte); base = ang(np.repeat(Ytr.mean(0)[None], len(Yte), 0), Yte)
    r = {"train": train_names, "test": test_name, "n_train": int(len(Xtr)), "n_test": int(len(Xte)), "gamma": g, "lambda": lam,
         "cv_mean_error_deg": round(cv, 3), "test_mean_error_deg": round(float(e.mean()), 3), "test_median_error_deg": round(float(np.median(e)), 3),
         "test_p95_error_deg": round(float(np.percentile(e, 95)), 3), "baseline_mean_error_deg": round(float(base.mean()), 3),
         "gaze_range_deg": {"yaw": [round(float(Yte[:, 0].min()), 2), round(float(Yte[:, 0].max()), 2)], "pitch": [round(float(Yte[:, 1].min()), 2), round(float(Yte[:, 1].max()), 2)]}}
    results[tag] = r
    print(f"{tag:28s} test mean {r['test_mean_error_deg']:.2f} deg  median {r['test_median_error_deg']:.2f}  p95 {r['test_p95_error_deg']:.2f}  | baseline {r['baseline_mean_error_deg']:.2f} deg")
    return Yte, P

names = list(data)
plots = {}
for n in names:
    plots[n] = run([n], n, f"{n} -> {n}")
if len(names) == 2:
    a, b = names
    run(names, a, f"both -> {a}"); run(names, b, f"both -> {b}")
    run([a], b, f"{a} -> {b} (unseen head)"); run([b], a, f"{b} -> {a} (unseen head)")
json.dump(results, open(os.path.join(args.out, "gaze_model_results.json"), "w"), indent=1)

try:
    import matplotlib
    matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, len(plots), figsize=(6 * len(plots), 5.4), facecolor="#0E1116")
    axs = np.atleast_1d(axs)
    for ax, (n, (Yt, P)) in zip(axs, plots.items()):
        ax.set_facecolor("#0E1116")
        for i in range(len(Yt)):
            ax.plot([Yt[i, 0], P[i, 0]], [Yt[i, 1], P[i, 1]], color="#8A97A8", lw=0.8, alpha=0.7)
        ax.scatter(Yt[:, 0], Yt[:, 1], s=26, color="#35D07F", label="ground truth")
        ax.scatter(P[:, 0], P[:, 1], s=18, color="#F2C14E", marker="x", label="predicted from RGB")
        r = results[f"{n} -> {n}"]
        ax.set_title(f"{n}: held-out test, mean error {r['test_mean_error_deg']:.2f}°", color="white", fontsize=13)
        ax.set_xlabel("gaze yaw (deg)", color="#B9C4D0"); ax.set_ylabel("gaze pitch (deg)", color="#B9C4D0")
        ax.tick_params(colors="#B9C4D0"); [s.set_color("#3A4350") for s in ax.spines.values()]
        ax.legend(facecolor="#1B2430", edgecolor="#3A4350", labelcolor="white", fontsize=10); ax.set_aspect("equal")
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "gaze_model_scatter.png"), dpi=140, facecolor=fig.get_facecolor())
    print("PLOT saved")
except ImportError:
    print("matplotlib not available: no plot")

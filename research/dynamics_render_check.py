"""WS5: check that RENDERED dynamics frames follow the commanded profiles (pure Python, image-only detector).

    python3 research/dynamics_render_check.py <dynamics_dir> <roi_reset.png> <out_json>

<dynamics_dir> is the output of `dynamics.py --render` (dynamics.json + <profile>/NNNN.png). For each profile the
independent detector is run on every frame. Reported per eye:
  saccade / pursuit : linear fit of detected x against commanded h (slope px/unit, R^2, max residual px);
                      saccade also: detected x is monotonic (allowing 0.5 px detector noise) and settles at the end;
  vergence          : change in each pupil's x between first and last frame (both must move toward the nose,
                      i.e. image-left eye (subject R) moves right and image-right eye moves left);
  fixation          : detected-position standard deviation (px) vs commanded drift.
Missed detections are counted, never dropped silently.
"""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

d, roi_png, out = sys.argv[1:4]
ref = P.detect(Image.open(roi_png).convert("RGB"))
ROI = [(int(c["centre"][0]) - 90, int(c["centre"][1]) - 90, int(c["centre"][0]) + 90, int(c["centre"][1]) + 90) for c in ref]
J = json.load(open(os.path.join(d, "dynamics.json"))); res = {}
for name, pr in J.items():
    rows = []
    for fr in pr["frames"]:
        dets = P.detect(Image.open(os.path.join(d, fr["file"])).convert("RGB"), roi=ROI)
        ok = len(dets) == 2 and all(x["status"] != "fail" for x in dets)
        rows.append(dict(t=fr["t"], h=fr["h"], v=fr["v"], depth=fr["depth_m"], ok=ok,
                         xy=[x["centre"] for x in dets] if ok else None))
    good = [r for r in rows if r["ok"]]
    R = dict(n_frames=len(rows), n_missed=len(rows) - len(good), trajectory=rows)
    if good:
        X = np.array([[r["xy"][0][0], r["xy"][1][0]] for r in good]); Y = np.array([[r["xy"][0][1], r["xy"][1][1]] for r in good])
        H = np.array([r["h"] for r in good])
        for j, eye in enumerate(("image_left", "image_right")):
            e = {}
            if name in ("saccade", "pursuit") and np.ptp(H) > 0:
                A = np.c_[H, np.ones_like(H)]; coef, *_ = np.linalg.lstsq(A, X[:, j], rcond=None); pred = A @ coef
                ss = ((X[:, j] - X[:, j].mean()) ** 2).sum()
                e.update(slope_px_per_unit_h=round(float(coef[0]), 3), r2=round(float(1 - ((X[:, j] - pred) ** 2).sum() / ss), 5),
                         max_residual_px=round(float(np.abs(X[:, j] - pred).max()), 3))
                if name == "saccade":
                    dx = np.diff(X[:, j]) * np.sign(H[-1] - H[0])
                    e.update(monotonic_within_0_5px=bool((dx > -0.5).all()), end_settle_range_px=round(float(np.ptp(X[-5:, j])), 3))
                    T = np.array([r["t"] for r in good]); f = (X[:, j] - X[0, j]) / (X[-1, j] - X[0, j])
                    def cross(level):            # first time the normalised rendered displacement reaches `level` (linear interp.)
                        k = int(np.argmax(f >= level)); return float(T[k - 1] + (level - f[k - 1]) / (f[k] - f[k - 1]) * (T[k] - T[k - 1])) if k else float(T[0])
                    cmd = (H - H[0]) / (H[-1] - H[0])
                    def cross_c(level):
                        k = int(np.argmax(cmd >= level)); return float(T[k - 1] + (level - cmd[k - 1]) / (cmd[k] - cmd[k - 1]) * (T[k] - T[k - 1])) if k else float(T[0])
                    e.update(measured_duration_5_95_ms=round((cross(.95) - cross(.05)) * 1000, 2), commanded_duration_5_95_ms=round((cross_c(.95) - cross_c(.05)) * 1000, 2),
                             frame_interval_ms=round(float(np.median(np.diff(T))) * 1000, 3),
                             peak_image_velocity_px_per_s=round(float(np.max(np.abs(np.diff(X[:, j]) / np.diff(T)))), 1))
                if name == "pursuit":
                    T = np.array([r["t"] for r in good]); tgt = np.array([fr["target_h"] for fr in pr["frames"]])[[i for i, r in enumerate(rows) if r["ok"]]]
                    xs = X[:, j] - X[:, j].mean(); lags = np.arange(0, 11); dt = float(np.median(np.diff(T)))
                    cc = [float(np.corrcoef(tgt[:len(tgt) - L], xs[L:])[0, 1]) for L in lags]
                    e.update(measured_lag_ms=round(float(lags[int(np.argmax(cc))] * dt * 1000), 1), lag_resolution_ms=round(dt * 1000, 1), commanded_latency_ms=100.0,
                             measured_gain_vs_target=round(float(np.ptp(X[:, j]) / (np.ptp(tgt) * coef[0])), 3) if coef[0] else None)
            if name == "vergence":
                e.update(dx_first_to_last_px=round(float(X[-1, j] - X[0, j]), 3))
            if name == "fixation":
                e.update(std_x_px=round(float(X[:, j].std()), 3), std_y_px=round(float(Y[:, j].std()), 3))
            R[eye] = e
        if name == "vergence":
            R["converges"] = bool(R["image_left"]["dx_first_to_last_px"] > 0 and R["image_right"]["dx_first_to_last_px"] < 0)
    res[name] = R
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1))

"""WS1: attribute detector-minus-ground-truth offsets to pupil depth + a constant offset (reproducible).

    python3 research/bias_root_cause.py <results_dir> <out_json> <condition> [<condition> ...]

For each condition's <results_dir>/<condition>_per_pupil.csv (evaluate_detector.py output) and each candidate
pupil depth d in pupil_geometry_probe.json -> projection_by_depth_mm (unrefracted projection of a pupil at depth d
from the eye centre, per frame/eye, produced by research/pupil_geometry_probe.py), it computes
  model(d) = projection; offset = mean(detected - model(d)) over successful pupils;
  residual = |detected - model(d) - offset|  (mean, max).
It also reports the same against the wrapper GT (pupil_center_2D, refracted, depth 14.19 mm) and the depth that
minimises the mean residual (piecewise-linear interpolation between the probed depths).
"""
import csv, json, os, sys
import numpy as np
R, out = sys.argv[1], sys.argv[2]; conds = sys.argv[3:]
probe = json.load(open(os.path.join(R, "pupil_geometry_probe.json")))["projection_by_depth_mm"]
depths = sorted({float(d) for v in probe.values() for d in v})
res = {}
for c in conds:
    rows = [r for r in csv.DictReader(open(os.path.join(R, f"{c}_per_pupil.csv"))) if r["success"] == "True"]
    def key(r):
        k = "".join(ch for ch in r["item"] if ch.isdigit())[-2:]; return f"{k}{r['eye']}"
    rows = [r for r in rows if key(r) in probe]
    det = np.array([[float(r["det_x"]), float(r["det_y"])] for r in rows]); gt = np.array([[float(r["gt_x"]), float(r["gt_y"])] for r in rows])
    out_c = dict(n=len(rows))
    def fit(model):
        off = (det - model).mean(0); e = np.linalg.norm(det - model - off, axis=1)
        return dict(constant_offset_px=off.round(3).tolist(), residual_mean=round(float(e.mean()), 3), residual_max=round(float(e.max()), 3))
    out_c["vs_wrapper_gt_refracted_14.19mm"] = fit(gt)
    curve = []
    for d in depths:
        m = np.array([probe[key(r)][f"{d:g}" if f"{d:g}" in probe[key(r)] else str(d)] for r in rows]); f = fit(m); out_c[f"vs_unrefracted_depth_{d:g}mm"] = f; curve.append((d, f["residual_mean"]))
    fine = np.linspace(depths[0], depths[-1], 200)
    def interp_model(d):
        return np.array([[np.interp(d, depths, [probe[key(r)][f"{x:g}" if f"{x:g}" in probe[key(r)] else str(x)][i] for x in depths]) for i in (0, 1)] for r in rows])
    rm = [fit(interp_model(d))["residual_mean"] for d in fine]
    out_c["best_fit_depth_mm"] = round(float(fine[int(np.argmin(rm))]), 3); out_c["best_fit"] = fit(interp_model(fine[int(np.argmin(rm))]))
    res[c] = out_c
json.dump(dict(method=__doc__.strip().splitlines()[0], note="detector uses pixel-centre (i+0.5) convention (fixed 2026-11-22)", results=res), open(out, "w"), indent=1)
for c, v in res.items():
    print(c, "n", v["n"], "GT14.19:", v["vs_wrapper_gt_refracted_14.19mm"], "| best depth", v["best_fit_depth_mm"], v["best_fit"])

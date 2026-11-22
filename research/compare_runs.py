"""Report numerical differences between the pre-clean checkpoint / scratch baseline and the clean-extraction run.

    python3 research/compare_runs.py <results_dir> <out.json>

Compares (nothing is overwritten):
  * detector metrics: checkpoint_pre_clean/<name>_metrics.json vs <name>_metrics.json (release frames are the identical
    shipped PNGs, so they must match exactly; ablation/dataset frames are re-rendered, so GPU noise can change them);
  * WS1 depth fit: ws1_depth_baseline_scratch/depth_fit.json vs ws1_depth/depth_fit.json (best depth, bootstrap,
    held-out RMSE per eye and condition).
"""
import json, os, sys
R, out = sys.argv[1:3]; res = dict(detector={}, depth_fit={})
KEYS = ["success_rate", "n_success", "on_successful.mae_x", "on_successful.mae_y", "on_successful.rmse", "on_successful.median",
        "on_successful.p95", "on_successful.max", "on_successful.mean_bias_x", "on_successful.mean_bias_y"]
def g(d, p):
    for k in p.split("."): d = d.get(k) if isinstance(d, dict) else None
    return d
for f in sorted(os.listdir(os.path.join(R, "checkpoint_pre_clean"))):
    if not f.endswith("_metrics.json"): continue
    new = os.path.join(R, f) if os.path.exists(os.path.join(R, f)) else os.path.join(R, "ws6_dataset_v1", f)
    if not os.path.exists(new): res["detector"][f] = "no clean-run counterpart"; continue
    a, b = json.load(open(os.path.join(R, "checkpoint_pre_clean", f))), json.load(open(new))
    res["detector"][f] = {k: dict(before=g(a, k), clean=g(b, k), diff=(round(g(b, k) - g(a, k), 4) if isinstance(g(a, k), (int, float)) and isinstance(g(b, k), (int, float)) else None)) for k in KEYS}
    res["detector"][f]["clean_file"] = os.path.relpath(new, R)
    res["detector"][f]["detector_sha256_before"] = (a.get("detector") or {}).get("sha256", "not recorded (pre-hash file; corrected detector per checkpoint README)")
    res["detector"][f]["detector_sha256_clean"] = (b.get("detector") or {}).get("sha256")
pa, pb = os.path.join(R, "ws1_depth_baseline_scratch", "depth_fit.json"), os.path.join(R, "ws1_depth", "depth_fit.json")
if os.path.exists(pa) and os.path.exists(pb):
    A, B = json.load(open(pa)), json.load(open(pb))
    for c in A["conditions"]:
        for e in "LR":
            x, y = A["conditions"][c][e], B["conditions"].get(c, {}).get(e)
            if not y: continue
            res["depth_fit"][f"{c}.{e}"] = {k: dict(baseline=g(x, k), clean=g(y, k)) for k in
                ("best_depth_mm", "bootstrap_depth_mm", "leave_one_pose_out_range_mm", "heldout_fitted_depth_model.rmse_px",
                 "heldout_mesh_painted_no_fit.rmse_px", "heldout_wrapper_gt_no_offset.rmse_px", "fit_offset_at_best_px")}
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res["depth_fit"], indent=1)[:3000])

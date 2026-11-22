"""WS1: fit the effective pupil depth that explains the image-detected pupils, with held-out validation (pure Python).

    python3 research/depth_fit.py <depth_ext.json> <roi_reset.png> <out_dir> <cond>=<fit_dir>:<heldout_dir> [...]

<depth_ext.json> comes from research/depth_probe_extended.py. Each fit_dir holds frame_00..10.png (+ state_NN.json)
from render_ablation.py; each heldout_dir holds frame_20..33.png from `render_ablation.py ... --poses heldout`.
The corrected detector (research/pupil_detector.py) is run on every image with the same fixed eye-region prior.

Per condition and per eye, separately:
  * for every probed depth d: offset(d) = mean over FIT poses of (detected - proj_d); residual RMSE in x and in y;
  * d* = argmin of the combined RMSE, plus d*_x and d*_y minimising x and y alone; flagged if d* is on the grid edge;
  * uncertainty: 2000 bootstrap resamples of the fit poses -> 2.5/50/97.5 % of d*; curvature (RMSE rise of 0.05 px);
  * held-out validation: proj_{d*} + offset(d*) predicts the 14 held-out pupils; reported against the same for the
    wrapper ground truth (pupil_center_2D, refracted) with its own fitted offset, and for the mesh-only painted-pupil
    prediction (no parameter fitted at all).
Raw rows (every pupil, every condition) go to <out_dir>/depth_fit_raw.csv; summary to depth_fit.json; curves to
depth_fit_curves.png. Detections more than 8 px from the wrapper point, or with status 'fail', are excluded from
fitting and counted.
"""
import csv, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

probe_p, roi_png, out = sys.argv[1:4]; conds = [c.split("=", 1) for c in sys.argv[4:]]
os.makedirs(out, exist_ok=True)
R = json.load(open(probe_p)); D = np.array(R["depths_mm"])
ref = P.detect(Image.open(roi_png).convert("RGB"))
ROI = [(int(d["centre"][0]) - 90, int(d["centre"][1]) - 90, int(d["centre"][0]) + 90, int(d["centre"][1]) + 90) for d in ref]
rng = np.random.default_rng(12345)
raw = []; summary = dict(
    method=dict(
        status="effective fitted parameter of the rendered asset as seen by the detector; NOT an anatomical dimension",
        model="detected = project(eye_centre + q_gaze @ (axis * d)) + constant offset (dx, dy) per eye and condition; unrefracted pinhole projection",
        fit_set="11 poses: 10-frame ring (theta_k = 2*pi*k/10, h=sin, v=cos) + reset (0,0)",
        heldout_set="14 poses never used for fitting: r=0.5 ring at half-step angles (k=0..9) + diagonals (+-0.7, +-0.7)",
        selection="d* = argmin over the depth grid of the combined x/y residual RMSE of the fit set, offset re-fitted at every d",
        bootstrap="non-parametric percentile bootstrap, 2000 resamples, numpy default_rng seed 12345; sampling unit = fit pose (one eye's detected pupil at one gaze, its x and y kept paired), drawn with replacement from that eye's usable fit poses; offset and d* re-fitted per resample; interval = 2.5 and 97.5 percentiles of d* (grid-quantised to the 0.05 mm step); eyes fitted separately",
        sensitivity="leave-one-pose-out d* for every fit pose; left and right eyes at the same gaze share rendering/lighting so they are reported separately, never pooled",
        heldout_separation="held-out poses (ids 20..33) enter neither the depth selection, the offset, nor the bootstrap; they are only predicted",
        exclusion="detections with status 'fail' or more than 8 px from the wrapper point are excluded and listed",
        cornea_note="the rendered 'Lens' material is Transparent+Glossy (no refraction); the projection here is unrefracted, while the official pupil_center_2D includes analytic corneal refraction (0.45-0.58 px)"),
    probe=os.path.basename(probe_p), depth_grid=[float(D[0]), float(D[-1]), float(D[1] - D[0])],
                         reset_pose_geometry=R["reset_pose"], conditions={})


def detect_dir(d, ids):
    res = {}
    for k in ids:
        p = os.path.join(d, f"frame_{k}.png")
        if not os.path.exists(p):
            continue
        dets = P.detect(Image.open(p).convert("RGB"), roi=ROI)
        for s in "LR":
            g = R["poses"][k][s]["wrapper_2D"]
            m = min(dets, key=lambda x: abs(x["centre"][0] - g[0])) if dets else None
            res[(k, s)] = m
    return res


def refine_min(curve):
    """continuous minimum: parabola through the grid minimum and its neighbours (grid value if on an edge)."""
    j = int(np.argmin(curve))
    if j in (0, len(curve) - 1):
        return float(D[j])
    y0, y1, y2 = curve[j - 1], curve[j], curve[j + 1]; den = y0 - 2 * y1 + y2
    return float(D[j] + (0.5 * (y0 - y2) / den) * (D[1] - D[0])) if den > 0 else float(D[j])


def fit(ks, s, det):
    """returns rmse curves (x, y, xy) over depth and offsets, using poses ks of eye s."""
    A = np.array([det[(k, s)]["centre"] for k in ks])                     # n x 2
    Pd = np.array([R["poses"][k][s]["proj"] for k in ks])                 # n x nd x 2
    E = A[:, None, :] - Pd                                                # n x nd x 2
    off = E.mean(0)                                                       # nd x 2
    r = E - off
    return np.sqrt((r[..., 0] ** 2).mean(0)), np.sqrt((r[..., 1] ** 2).mean(0)), np.sqrt((r ** 2).sum(2).mean(0)), off


import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axs = plt.subplots(len(conds), 2, figsize=(11, 3.6 * len(conds)), squeeze=False)
for ci, (name, dirs) in enumerate(conds):
    fd, hd = dirs.split(":")
    fit_ids = [f"{k:02d}" for k in range(11)]; ho_ids = [f"{k:02d}" for k in range(20, 34)]
    det = {**detect_dir(fd, fit_ids), **detect_dir(hd, ho_ids)}
    C = {}
    for s in "LR":
        usable = {}
        for (k, side), m in det.items():
            if side != s:
                continue
            g = np.array(R["poses"][k][s]["wrapper_2D"])
            ok = m is not None and m["status"] != "fail" and np.linalg.norm(np.array(m["centre"]) - g) <= 8
            usable[k] = ok
            raw.append(dict(condition=name, pose=k, set=R["poses"][k]["set"], eye=s, h=R["poses"][k]["input"][0], v=R["poses"][k]["input"][1],
                            det_x=m["centre"][0] if m else "", det_y=m["centre"][1] if m else "", status=m["status"] if m else "none",
                            confidence=m.get("confidence", 0) if m else 0, used=ok, gt_x=g[0], gt_y=g[1],
                            gt_unrefr_x=R["poses"][k][s]["wrapper_2D_unrefracted"][0], gt_unrefr_y=R["poses"][k][s]["wrapper_2D_unrefracted"][1],
                            painted_x=R["poses"][k][s]["painted_surface_2D"][0], painted_y=R["poses"][k][s]["painted_surface_2D"][1]))
        fk = [k for k in fit_ids if usable.get(k)]; hk = [k for k in ho_ids if usable.get(k)]
        rx, ry, rxy, off = fit(fk, s, det)
        i = int(np.argmin(rxy)); ix = int(np.argmin(rx)); iy = int(np.argmin(ry))
        boots = []; boots_raw = []
        for _ in range(2000):
            bk = list(rng.choice(fk, len(fk), replace=True))
            cb = fit(bk, s, det)[2]; boots.append(D[int(np.argmin(cb))]); boots_raw.append(refine_min(cb))
        flat = D[rxy <= rxy[i] + 0.05]
        # pose-level sensitivity (leave one fit pose out): how much d* depends on any single gaze
        loo = {k: float(D[int(np.argmin(fit([x for x in fk if x != k], s, det)[2]))]) for k in fk}
        # held-out prediction
        def ho_err(pred_fn, offset):
            e = np.array([np.array(det[(k, s)]["centre"]) - (np.array(pred_fn(k)) + offset) for k in hk])
            n = np.linalg.norm(e, axis=1)
            return dict(per_pose=[dict(pose=k, input=R["poses"][k]["input"], dx=round(float(a), 4), dy=round(float(b), 4), err=round(float(c), 4))
                                  for k, (a, b), c in zip(hk, e, n)],
                        excluded_poses=[k for k in ho_ids if not usable.get(k)], n=len(hk), mean_px=round(float(n.mean()), 3), rmse_px=round(float(np.sqrt((n ** 2).mean())), 3), max_px=round(float(n.max()), 3),
                        signed_bias_x=round(float(e[:, 0].mean()), 3), signed_bias_y=round(float(e[:, 1].mean()), 3),
                        rmse_x=round(float(np.sqrt((e[:, 0] ** 2).mean())), 3), rmse_y=round(float(np.sqrt((e[:, 1] ** 2).mean())), 3))
        gt_off = np.mean([np.array(det[(k, s)]["centre"]) - R["poses"][k][s]["wrapper_2D"] for k in fk], 0)
        pa_off = np.mean([np.array(det[(k, s)]["centre"]) - R["poses"][k][s]["painted_surface_2D"] for k in fk], 0)
        C[s] = dict(n_fit=len(fk), n_fit_excluded=11 - len(fk), n_heldout=len(hk), n_heldout_excluded=14 - len(hk),
                    best_depth_mm=float(D[i]), best_depth_on_grid_edge=bool(i in (0, len(D) - 1)),
                    best_depth_x_only_mm=float(D[ix]), best_depth_y_only_mm=float(D[iy]),
                    fit_rmse_at_best=dict(x=round(float(rx[i]), 3), y=round(float(ry[i]), 3), xy=round(float(rxy[i]), 3)),
                    fit_offset_at_best_px=[round(float(x), 3) for x in off[i]],
                    fit_rmse_at_wrapper_depth=dict(depth_mm=R["reset_pose"][s]["wrapper_pupil_depth_mm"],
                                                   xy=round(float(np.interp(R["reset_pose"][s]["wrapper_pupil_depth_mm"], D, rxy)), 3)),
                    bootstrap_depth_mm=dict(p2_5=float(np.percentile(boots, 2.5)), p50=float(np.percentile(boots, 50)), p97_5=float(np.percentile(boots, 97.5))),
                    best_depth_refined_mm=round(refine_min(rxy), 4),
                    bootstrap_depth_refined_mm_raw=dict(p2_5=float(np.percentile(boots_raw, 2.5)), p50=float(np.percentile(boots_raw, 50)), p97_5=float(np.percentile(boots_raw, 97.5))),
                    bootstrap_note="bootstrap_depth_mm: percentiles of the grid-valued d* (0.05 mm grid); bootstrap_depth_refined_mm_raw: percentiles of the parabola-refined continuous minimum, unrounded",
                    heldout_pose_ids=hk, heldout_pose_inputs={k: R["poses"][k]["input"] for k in ho_ids}, fit_pose_ids=fk,
                    depth_range_within_0_05px_of_min_mm=[float(flat.min()), float(flat.max())],
                    leave_one_pose_out_depth_mm=loo, leave_one_pose_out_range_mm=[min(loo.values()), max(loo.values())],
                    mesh_painted_pupil_depth_mm=R["reset_pose"][s]["painted_surface_depth_along_axis_mm"],
                    heldout_fitted_depth_model=ho_err(lambda k: R["poses"][k][s]["proj"][i], off[i]),
                    heldout_wrapper_gt_plus_fitted_offset=ho_err(lambda k: R["poses"][k][s]["wrapper_2D"], gt_off),
                    heldout_wrapper_gt_no_offset=ho_err(lambda k: R["poses"][k][s]["wrapper_2D"], 0),
                    heldout_mesh_painted_no_fit=ho_err(lambda k: R["poses"][k][s]["painted_surface_2D"], 0),
                    heldout_mesh_painted_plus_fitted_offset=ho_err(lambda k: R["poses"][k][s]["painted_surface_2D"], pa_off),
                    fit_offset_wrapper_gt_px=[round(float(x), 3) for x in gt_off], fit_offset_painted_px=[round(float(x), 3) for x in pa_off])
        for j, (curve, lab) in enumerate(((rx, "x"), (ry, "y"), (rxy, "xy"))):
            axs[ci][0 if s == "L" else 1].plot(D, curve, label=f"RMSE {lab}")
        a = axs[ci][0 if s == "L" else 1]
        a.axvline(D[i], color="k", ls="--", lw=.8, label=f"best {D[i]:.2f} mm")
        a.axvline(R["reset_pose"][s]["wrapper_pupil_depth_mm"], color="r", ls=":", label="wrapper depth")
        a.axvline(R["reset_pose"][s]["painted_surface_depth_along_axis_mm"], color="g", ls=":", label="mesh painted pupil")
        a.set_title(f"{name} eye {s}: fit residual vs pupil depth (offset fitted)"); a.set_xlabel("depth from eye centre (mm)"); a.set_ylabel("px"); a.grid(alpha=.3); a.legend(fontsize=7)
    summary["conditions"][name] = dict(fit_dir=fd, heldout_dir=hd, **C)
fig.tight_layout(); fig.savefig(os.path.join(out, "depth_fit_curves.png"), dpi=120)
with open(os.path.join(out, "depth_fit_raw.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(raw[0])); w.writeheader(); w.writerows(raw)
json.dump(summary, open(os.path.join(out, "depth_fit.json"), "w"), indent=1)
print(json.dumps({c: {s: {k: v[s][k] for k in ("best_depth_mm", "best_depth_on_grid_edge", "bootstrap_depth_mm", "mesh_painted_pupil_depth_mm", "heldout_fitted_depth_model", "heldout_mesh_painted_no_fit", "heldout_wrapper_gt_no_offset")} for s in "LR"} for c, v in summary["conditions"].items()}, indent=1))

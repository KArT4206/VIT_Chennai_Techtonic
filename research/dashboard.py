"""WS7: research validation dashboard generated ONLY from result files (no numbers typed in).

    python3 research/dashboard.py <results_dir=AUDIT/results> <out_html>

Every metric card shows its value, the JSON file and key path it came from, and the command that produces that
file. A source file that does not exist yet is shown as "not measured" (never a placeholder number).
Images referenced are copied next to the HTML (relative links) so the report is self-contained as a folder.
"""
import html, json, os, shutil, sys, datetime
R, OUT = sys.argv[1], sys.argv[2]; OD = os.path.dirname(os.path.abspath(OUT)); os.makedirs(OD, exist_ok=True)
CMD = {
 "compliance.json": "blender -b --factory-startup <bundle>/scene.blend -P research/compliance_tests.py -- AUDIT/results/compliance.json",
 "release_metrics.json": "python3 research/evaluate_detector.py release AUDIT/results <bundle>",
 "full_roi_metrics.json": "python3 research/evaluate_detector.py --roi-from abl/full/frame_10.png full_roi AUDIT/results abl/full",
 "no_lids_roi_metrics.json": "python3 research/evaluate_detector.py --roi-from abl/full/frame_10.png no_lids_roi AUDIT/results abl/no_lids",
 "no_lids_lens_roi_metrics.json": "python3 research/evaluate_detector.py --roi-from abl/full/frame_10.png no_lids_lens_roi AUDIT/results abl/no_lids_lens",
 "model_comparison.json": "blender ... -P research/model_comparison.py -- AUDIT/results/model_comparison.json",
 "ws2_degradation/robustness.json": "python3 research/degrade.py sweep <bundle> deg --seed 7 && python3 research/degrade_eval.py deg abl/full/frame_10.png AUDIT/results/ws2_degradation/robustness.json <bundle>",
 "ws3_masks/masks_metrics.json": "python3 research/gpuq.py -- blender ... -P research/masks.py -- masks && python3 research/masks_eval.py masks <bundle> AUDIT/results/ws3_masks --roi-from abl/full/frame_10.png",
 "ws4_dataset/coverage.json": "python3 research/gpuq.py -- blender ... -P research/dataset_v2_render.py -- --config research/configs/pilot_v2.json --out DS && python3 research/dataset_v2_post.py DS",
 "ws4_dataset/integrity.json": "python3 research/dataset_v2_post.py DS",
 "ws5_dynamics/dynamics_validation.json": "python3 research/dynamics_validate.py AUDIT/results/ws5_dynamics",
 "ws6_performance/bench_compare.json": "for c in original band persistent combined: python3 research/gpuq.py -- blender ... -P research/bench_speed.py -- bench $c; python3 research/bench_compare.py bench abl/full/frame_10.png AUDIT/results/ws6_performance/bench_compare.json",
 "ws1_depth/depth_fit.json": "blender ... -P research/depth_probe_extended.py -- ws1_depth/depth_probe_extended.json; render_ablation.py ... --poses heldout; python3 research/depth_fit.py ...  (see research/verify_all.sh stages probe/heldout/depthfit)",
 "ws1_depth/depth_probe_extended.json": "blender -b --factory-startup <bundle>/scene.blend -P research/depth_probe_extended.py -- AUDIT/results/ws1_depth/depth_probe_extended.json --dmin 12 --dmax 20 --step 0.05",
 "research_pupil_levels.json": "python3 research/annotate_three_level.py <bundle> AUDIT/results/ws1_depth/depth_probe_extended.json abl/full/frame_10.png AUDIT/results/research_pupil_levels.json",
 "no_lids_lens_nodisp_roi_metrics.json": "python3 research/evaluate_detector.py --roi-from abl/full/frame_10.png no_lids_lens_nodisp_roi AUDIT/results abl/no_lids_lens_nodisp",
 "no_lids_lens_flat_roi_metrics.json": "python3 research/evaluate_detector.py --roi-from abl/full/frame_10.png no_lids_lens_flat_roi AUDIT/results abl/no_lids_lens_flat",
 "ws6_dataset_v1/dataset_roi_metrics.json": "research/verify_all.sh stage dataset (dataset_engine.py + validate_dataset.py + evaluate_detector.py)",
 "ws6_dataset_v1/manifest.json": "blender ... -P research/dataset_engine.py -- --config research/configs_dataset_40.json --out DS",
 "ws5_dynamics/dynamics_render_check.json": "blender ... -P research/dynamics.py -- --render DYN --fps 30 --samples 16 && python3 research/dynamics_render_check.py DYN abl/full/frame_10.png AUDIT/results/ws5_dynamics/dynamics_render_check.json",
 "ws6_performance/benchmark_gpu_scene_samples.json": "blender ... -P research/benchmark.py -- BG --repeats 3",
 "ws6_performance/benchmark_cpu_64spp.json": "blender ... -P research/benchmark.py -- BC --cpu --samples 64 --repeats 2",
 "results_check.json": "python3 research/check_results.py AUDIT/results AUDIT/results/results_check.json",
 "integrity_check.json": "python3 research/integrity_check.py . AUDIT/results/integrity_check.json",
 "ws6_performance/band_audit.json": "python3 research/bench_band_audit.py BENCH AUDIT/results/ws6_performance/band_audit.json",
 "ws3_masks/unclassified_audit.json": "python3 research/masks_unclassified_audit.py MASKS AUDIT/results/ws3_masks/unclassified_audit.json",
 "run_comparison.json": "python3 research/compare_runs.py AUDIT/results AUDIT/results/run_comparison.json",
 "ws8_comparison/comparison_metrics.json": "python3 research/gpuq.py -- blender ... -P research/comparison_render.py -- cmp && python3 research/comparison_eval.py cmp abl/full/frame_10.png AUDIT/results/ws8_comparison",
}
def load(f):
    p = os.path.join(R, f); return json.load(open(p)) if os.path.exists(p) else None
def get(d, path):
    """dotted path; a list element can be picked by index or by name with  key~<name prefix>  (e.g. checks~camera 40)."""
    for k in path.split("."):
        if d is None: return None
        if isinstance(d, list) and "~" in k:
            fld, pre = k.split("~", 1); d = next((x for x in d if str(x.get(fld, "")).startswith(pre)), None)
        else:
            d = d[int(k)] if isinstance(d, list) else d.get(k)
    return d
def fmt(v):
    if v is None: return "—"
    if isinstance(v, float): return f"{v:.4g}"
    if isinstance(v, (dict, list)): return html.escape(json.dumps(v)[:160])
    return html.escape(str(v))
SECTIONS = [
 ("Compliance (Track 01)", [("compliance.json", "passed", "checks passed"), ("compliance.json", "failed", "checks failed")]),
 ("Calibration", [("compliance.json", "checks.name~K[R|t] vs Blender.value", "K[R|t] vs Blender projection, max px (500 points)"),
                  ("compliance.json", "checks.name~camera 40 cm.value", "camera distance from eye midpoint (m)"),
                  ("compliance.json", "checks.name~eye L: torsion.value", "eye L torsion, Listing's law (deg)")]),
 ("WS1 pupil-depth root cause (extended probe 12-20 mm, held-out validated)", [("ws1_depth/depth_fit.json", f"conditions.{c}.{e}.{k}", f"{c} eye {e}: {lab}")
                  for c in ("no_lids_lens", "full") for e in "LR" for k, lab in (("best_depth_mm", "best-fit depth (mm)"), ("best_depth_on_grid_edge", "minimum on grid edge?"),
                  ("bootstrap_depth_mm", "bootstrap 95% interval (mm)"), ("mesh_painted_pupil_depth_mm", "mesh+UV painted-pupil depth (mm, no fit)"),
                  ("heldout_fitted_depth_model.rmse_px", "held-out RMSE, fitted depth + offset (px)"), ("heldout_mesh_painted_no_fit.rmse_px", "held-out RMSE, mesh painted pupil, nothing fitted (px)"),
                  ("heldout_wrapper_gt_no_offset.rmse_px", "held-out RMSE vs wrapper GT (px)"))] +
                 [("ws1_depth/depth_probe_extended.json", f"reset_pose.{e}.{k}", f"eye {e}: {lab}") for e in "LR" for k, lab in
                  (("wrapper_pupil_depth_mm", "wrapper (anatomical) pupil depth mm"), ("painted_surface_depth_along_axis_mm", "painted pupil on mesh, depth mm"),
                   ("painted_surface_lateral_offset_world_mm", "painted pupil lateral offset (world mm)"))]),
 ("Pupil ground truth: three levels", [("ws3_masks/masks_metrics.json", "landmark.unoccluded_refracted_centroid_vs_gt_apparent", "rendered pupil-mask centroid, Lens on (the Lens material does not refract), vs analytic apparent GT (px)"),
                  ("ws3_masks/masks_metrics.json", "landmark.bias_unoccluded_refr_minus_gt_apparent", "mean (dx, dy) mask - GT"),
                  ("ws3_masks/masks_metrics.json", "landmark.unoccluded_refracted_centroid_vs_gt_unrefracted", "refracted mask vs unrefracted GT (px)"),
                  ("ws3_masks/masks_metrics.json", "landmark.detector_vs_unoccluded_mask_centroid", "detector vs refracted mask centroid (px)"),
                  ("ws3_masks/masks_metrics.json", "landmark.bias_detector_minus_unoccluded_centroid", "mean (dx, dy) detector - mask")]),
 ("Detection (independent, image only; corrected detector)", [(f, k, f"{f.replace('_metrics.json','')}: {lab}") for f in ("release_metrics.json", "full_roi_metrics.json", "no_lids_roi_metrics.json", "no_lids_lens_roi_metrics.json", "no_lids_lens_nodisp_roi_metrics.json", "no_lids_lens_flat_roi_metrics.json", "ws6_dataset_v1/dataset_roi_metrics.json")
                  for k, lab in (("success_rate", "success rate (≤5 px)"), ("n_success", "successful pupils"), ("n_pupils", "pupils"), ("on_successful.mae_x", "MAE x px"), ("on_successful.mae_y", "MAE y px"),
                                 ("on_successful.rmse", "RMSE px"), ("on_successful.median", "median px"), ("on_successful.p95", "P95 px"), ("on_successful.max", "max px"),
                                 ("on_successful.mean_bias_x", "signed bias x px"), ("on_successful.mean_bias_y", "signed bias y px (+down)"), ("all_pupils_max_err", "max error incl. failed detections px"))]),
 ("Three-level pupil annotation", [("research_pupil_levels.json", "schema", "schema"), ("research_pupil_levels.json", "conventions", "conventions"), ("research_pupil_levels.json", "detector_sha256", "detector version (SHA-256)")]),
 ("Robustness to camera/sensor degradation", [("ws2_degradation/robustness.json", "label_invariance_ok", "labels unchanged by all degradations")] +
                  [("ws2_degradation/robustness.json", f"results.{op}", f"{op}: per level") for op in ("noise", "motion", "defocus", "exposure", "glint", "jpeg", "eyelid", "illum")]),
 ("Segmentation", [("ws3_masks/masks_metrics.json", "validation_ok", "mask validation passed"), ("ws3_masks/masks_metrics.json", "segmentation.iou_detector_vs_visible", "IoU detector circle vs visible pupil"),
                  ("ws3_masks/masks_metrics.json", "segmentation.dice_detector_vs_visible", "Dice detector vs visible pupil"), ("ws3_masks/masks_metrics.json", "segmentation.iou_refr_vs_unrefr", "IoU refracted vs unrefracted pupil"),
                  ("ws3_masks/masks_metrics.json", "visibility.visible_fraction", "pupil visible fraction")]),
 ("Dataset v1 (40 samples, iris/lighting variants)", [("ws6_dataset_v1/manifest.json", "runs", "runs (timing)"), ("ws6_dataset_v1/manifest.json", "failures", "recorded failures"), ("ws6_dataset_v1/manifest.json", "provenance", "provenance")]),
 ("Dataset coverage and integrity", [("ws4_dataset/coverage.json", "coverage", "coverage"), ("ws4_dataset/integrity.json", "ok", "integrity ok"), ("ws4_dataset/integrity.json", "problems", "problems")]),
 ("Dynamic movement (simulated, not human data)", [("ws5_dynamics/dynamics_validation.json", "saccade.example", "saccade example"), ("ws5_dynamics/dynamics_validation.json", "pursuit", "pursuit"),
                  ("ws5_dynamics/dynamics_validation.json", "vergence", "vergence"), ("ws5_dynamics/dynamics_validation.json", "fixation", "fixation drift"), ("ws5_dynamics/dynamics_validation.json", "blink", "blink"),
                  ("ws5_dynamics/dynamics_render_check.json", "saccade", "rendered saccade: detector vs command"), ("ws5_dynamics/dynamics_render_check.json", "pursuit", "rendered pursuit"),
                  ("ws5_dynamics/dynamics_render_check.json", "vergence", "rendered vergence"), ("ws5_dynamics/dynamics_render_check.json", "fixation", "rendered fixation")]),
 ("Render performance", [("ws6_performance/bench_compare.json", f"configs.{c}.{k}", f"{c}: {k}") for c in ("original", "band", "persistent", "combined") for k in ("sequence_s", "speedup_sequence_vs_original", "init_s", "peak_rss_mb", "accept")]),
 ("Render benchmark at scene settings (GPU 512 spp, CPU 64 spp)", [("ws6_performance/benchmark_gpu_scene_samples.json", k, f"GPU: {k}") for k in ("device", "samples", "reset_render_s", "repeat_max_abs_diff_255", "repeat_mean_abs_diff_255", "peak_rss_mb", "robustness")] +
                  [("ws6_performance/benchmark_cpu_64spp.json", k, f"CPU: {k}") for k in ("device", "samples", "reset_render_s", "repeat_max_abs_diff_255", "peak_rss_mb")]),
 ("Verification status", [("results_check.json", "ok", "results complete, none stale"), ("results_check.json", "problems", "problems"),
                  ("integrity_check.json", "ok", "submission integrity"), ("integrity_check.json", "zip_sha256", "release ZIP SHA-256"),
                  ("integrity_check.json", "official_paths_ok", "official paths unchanged vs baseline tag")]),
 ("Eye-band render audit (rejected option)", [("ws6_performance/band_audit.json", f"configs.{c}.0.{k}", f"{c}: {k}") for c in ("band", "persistent") for k in ("gt_identical_to_original", "band_interior_max", "band_interior_mean", "band_edge_frame_max")]),
 ("Mask unclassified-pixel audit (segmentation provisional)", [("ws3_masks/unclassified_audit.json", "summary", "summary")]),
 ("Run-to-run comparison", [("run_comparison.json", "depth_fit", "WS1 depth fit: scratch baseline vs clean run")]),
 ("Model comparison", [("model_comparison.json", "summary", "centre-position differences (analytic)"), ("ws8_comparison/comparison_metrics.json", "planar_vs_anatomical_mean_abs", "planar vs anatomical, eye-box mean |Δpixel|"),
                  ("ws8_comparison/comparison_metrics.json", "sphere_vs_anatomical_mean_abs", "sphere vs anatomical, eye-box mean |Δpixel|"), ("ws8_comparison/comparison_metrics.json", "detector_radius", "detected pupil radius by model")]),
]
IMGS = ["ws1_depth/depth_fit_curves.png", "release_overlays.png", "full_roi_overlays.png", "ws2_degradation/degradation_levels_frame03_L.png", "ws5_dynamics/saccade.png", "ws5_dynamics/pursuit.png", "ws5_dynamics/vergence.png",
        "ws8_comparison/comparison_sheet.png", "ws4_dataset/coverage.png", "ws3_masks/mask_overlay.png"]
css = """:root{--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--bd:#e3e2dc;--ok:#1b7f3b;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ececea;--mut:#a3a39d;--card:#1e1e1c;--bd:#33332f;--ok:#5cc27a;--bad:#f07167}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:24px 16px;max-width:1100px;margin:auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}.mut{color:var(--mut)}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--bd)}td{border-top:1px solid var(--bd);padding:6px 8px;vertical-align:top}
td.v{font-variant-numeric:tabular-nums;word-break:break-word;max-width:420px}code{font-size:12px;color:var(--mut);word-break:break-all}.na{color:var(--bad)}
img{max-width:100%;border:1px solid var(--bd);margin:6px 0}"""
h = [f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Techtonic Research Dashboard</title><style>{css}</style>",
     "<h1>Techtonic research validation dashboard</h1>", f"<p class=mut>Generated {datetime.datetime.now().isoformat(timespec='seconds')} from <code>{html.escape(os.path.abspath(R))}</code>. "
     "Every value below is read from the named file; missing files show <span class=na>not measured</span>. Branch research/upgrade (post-deadline research; not part of the submitted package).</p>"]
missing = set()
for title, items in SECTIONS:
    h.append(f"<h2>{html.escape(title)}</h2><table>")
    for f, path, lab in items:
        d = load(f); v = get(d, path) if d is not None else None
        if d is not None:
            lab = lab + f" <span class=mut>[{datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(R, f))).isoformat(timespec='minutes')}]</span>"
        if d is None: missing.add(f)
        val = f"<span class=na>not measured</span>" if d is None else fmt(v)
        h.append(f"<tr><td>{lab}</td><td class=v>{val}</td><td><code>{html.escape(f)} → {html.escape(path)}</code><br><code>$ {html.escape(CMD.get(f, ''))}</code></td></tr>")
    h.append("</table>")
h.append("<h2>Evidence images</h2>")
for im in IMGS:
    p = os.path.join(R, im)
    if os.path.exists(p):
        dst = os.path.join(OD, "img", im.replace("/", "__")); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(p, dst)
        h.append(f"<p class=mut>{html.escape(im)}</p><img src='img/{html.escape(im.replace('/', '__'))}' alt='{html.escape(im)}'>")
h.append(f"<h2>Not yet measured</h2><p>{html.escape(', '.join(sorted(missing)) or 'none')}</p>")
open(OUT, "w").write("\n".join(h)); print("dashboard:", OUT, "missing:", sorted(missing))

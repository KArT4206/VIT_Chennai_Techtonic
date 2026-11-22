"""Write AUDIT/results/README.md (index) and AUDIT/results/RELEASE_NOTE.md from result files only (pure Python).

    python3 research/build_release_note.py <results_dir> <research_commit>

Every measured value is read from the named result file at build time; nothing measured is typed here.
"""
import json, os, sys
R, COMMIT = sys.argv[1:3]
J = lambda f: json.load(open(os.path.join(R, f)))
d = J("ws1_depth/depth_fit.json"); bc = J("ws6_performance/bench_compare.json"); ba = J("ws6_performance/band_audit.json")
dr = J("ws5_dynamics/dynamics_render_check.json"); ua = J("ws3_masks/unclassified_audit.json")["summary"]; integ = J("integrity_check.json")
m1 = J("ws6_dataset_v1/manifest.json"); cv = J("ws4_dataset/coverage.json")["coverage"]; chk = J("results_check.json")

idx = f"""# AUDIT/results — index

**The authoritative research report is [`INTEGRATION_REPORT.md`](INTEGRATION_REPORT.md).** The release summary is [`RELEASE_NOTE.md`](RELEASE_NOTE.md), and the browsable view is [`dashboard/index.html`](dashboard/index.html). All three are generated from the files in this folder, by `research/build_report.py`, `research/build_release_note.py` and `research/dashboard.py`.

| Folder / file | What it is | Status |
|---|---|---|
| `INTEGRATION_REPORT.md` | Full research report (sections 1–13) | **authoritative** |
| `results_check.json`, `integrity_check.json` | Completeness and staleness check; submission integrity | current |
| `compliance.json` | 40 Track 01 compliance and calibration checks | current |
| `*_metrics.json`, `*_per_pupil.csv`, `*_overlays.png` | Detector validation (frozen detector) on the released frames and 5 ablation conditions | current |
| `ws1_depth/` | Pupil-depth probe (12–20 mm) and effective-depth fit with held-out validation | current |
| `ws1_depth_baseline_scratch/` | The same fit on the first (pre-clean) renders; kept for comparison | baseline, not authoritative |
| `research_pupil_levels.json` | Three-level pupil annotation (A anatomical, B painted/rendered, C detected) | current |
| `ws2_degradation/` | Detector robustness and label invariance under image degradations | current |
| `ws3_masks/` | Semantic masks and the unclassified-pixel audit | **provisional** |
| `ws4_dataset/`, `ws6_dataset_v1/` | Dataset generation and integrity (v2 pilot, v1 40 samples) | current |
| `ws5_dynamics/` | Eye-movement models and rendered-trajectory measurements | current |
| `ws6_performance/` | Render benchmarks, eye-band audit, GPU/CPU repeatability | current |
| `ws8_comparison/`, `model_comparison.json` | Planar vs sphere vs anatomical eye models | current |
| `run_comparison.json` | Checkpoint and baseline vs clean-run differences | current |
| `checkpoint_pre_clean/` | Results recorded before the clean run (corrected detector; `ws2_degradation` copy predates the correction) | historical |
| `superseded_drafts/` | Earlier draft reports, each marked SUPERSEDED | **superseded, do not cite** |
| `gpu_job_log.jsonl`, `run_environment.txt` | GPU job queue log (commands, exit codes, times); software and hardware | provenance |
"""
open(os.path.join(R, "README.md"), "w").write(idx)

L = []; A = L.append
A("# Release note — Techtonic research branch\n")
A(f"**Branch:** `research/upgrade`. **Research commit:** `{COMMIT}`. **Submission baseline:** tag `submission-baseline-v1.0` and branch `submission/final`, both at `{integ['tag_commit'][:7]}`. "
  f"Release v1.0 `Techtonic.zip` SHA-256 `{integ['zip_sha256']}`. The research changes are confined to `research/` and `AUDIT/results/`, and none of them is part of the submitted hackathon package. "
  f"The official ground truth (`metadata.json`, `wrapper/eyes.py`) is unchanged. Integrity check: {'PASS' if integ['ok'] else 'FAIL'}; results check: {'PASS' if chk['ok'] else 'FAIL'}. "
  "Full report: [`INTEGRATION_REPORT.md`](INTEGRATION_REPORT.md).\n")
A("## Findings\n")
A("**Pupil-centre discrepancy (`ws1_depth/depth_fit.json`).** The official 2-D ground truth uses the wrapper's anatomical pupil, refracted through an analytic cornea. The rendered asset paints its pupil further out on the eyeball surface, and its `Lens` mesh does not refract. "
  "The depth below is an **effective fitted parameter of this asset as seen by this detector, not an anatomical dimension**. Bootstrap: 2000 resamples of fit poses, seed 12345, percentile interval. Held-out: 14 gaze positions, never used for fitting.\n")
A("| condition | eye | effective depth (mm) | 95% CI (mm) | held-out RMSE, fitted (px) | held-out RMSE, official GT (px) |\n|---|---|---|---|---|---|")
for c, v in d["conditions"].items():
    for e in "LR":
        x = v[e]; b = x["bootstrap_depth_mm"]
        A(f"| {c} | {e} | {x['best_depth_mm']:.2f} | {b['p2_5']:.2f}–{b['p97_5']:.2f} | {x['heldout_fitted_depth_model']['rmse_px']} | {x['heldout_wrapper_gt_no_offset']['rmse_px']} |")
A("\n**Detector validation**, separate from dataset generation (frozen detector `research/DETECTOR_FREEZE.txt`; success = within 5 px of the official GT):\n")
A("| condition | success | RMSE px | signed bias y px |\n|---|---|---|---|")
for f in ("release_metrics.json", "full_roi_metrics.json", "no_lids_lens_roi_metrics.json", "ws6_dataset_v1/dataset_roi_metrics.json"):
    m = J(f); A(f"| {f.split('/')[-1].replace('_metrics.json', '')} | {m['success_rate']:.0%} | {m['on_successful']['rmse']} | {m['on_successful']['mean_bias_y']} |")
A(f"\n**Dataset generation**, separate from the detector:\n- v1: {len(m1['samples'])}/{m1['config']['n']} samples, {len(m1['failures'])} failures, `{open(os.path.join(R, 'ws6_dataset_v1/integrity.txt')).read().strip()}`.")
A(f"- v2 pilot: {cv['n_samples']}/{cv['planned']} samples, {cv['failures']} failures, integrity ok = {J('ws4_dataset/integrity.json')['ok']}.\n")
o, p, b = bc["configs"]["original"], bc["configs"]["persistent"], bc["configs"]["band"]
A(f"**Rendering (`ws6_performance/`).** Persistent-scene rendering **passed** equivalence: speed-up {p['speedup_sequence_vs_original']}× (6-pose sequence {o['sequence_s']} s → {p['sequence_s']} s), pixels within "
  f"{ba['configs']['persistent'][0]['band_interior_max']}/255. Eye-region (ROI/border) rendering **failed** equivalence and is **not adopted**: inside the region pixels differ by up to "
  f"{ba['configs']['band'][0]['band_interior_max']}/255, and by up to {ba['configs']['band'][0]['band_edge_frame_max']}/255 at its edges. Its {b['speedup_sequence_vs_original']}× timing is therefore not claimed as a speed-up.\n")
s, pu = dr["saccade"], dr["pursuit"]
A(f"**Rendered eye movement (`ws5_dynamics/dynamics_render_check.json`, measured by the detector on rendered frames).** "
  f"Saccade: {s['n_frames']} frames at {s['image_left']['frame_interval_ms']} ms; 5–95 % duration {s['image_left']['measured_duration_5_95_ms']} ms / {s['image_right']['measured_duration_5_95_ms']} ms (image-left / image-right eye) vs {s['image_left']['commanded_duration_5_95_ms']} ms commanded. "
  f"The image-right eye has a detector glitch: maximum residual {s['image_right']['max_residual_px']} px, monotonic = {s['image_right']['monotonic_within_0_5px']}. It is reported, not removed. "
  f"Pursuit: {pu['n_frames']} frames; measured lag {pu['image_left']['measured_lag_ms']} ms (resolution {pu['image_left']['lag_resolution_ms']} ms) vs {pu['image_left']['commanded_latency_ms']} ms commanded; gain {pu['image_left']['measured_gain_vs_target']} / {pu['image_right']['measured_gain_vs_target']}. "
  f"Vergence: converges = {dr['vergence']['converges']}. Blinks are not rendered.\n")
A(f"**Semantic segmentation: provisional.** {ua['unclassified_fraction_range'][0]:.2%}–{ua['unclassified_fraction_range'][1]:.2%} of pixels per frame are unclassified. Most of them are background at the image sides, but up to {ua['max_unclassified_in_eye_band']:.1%} of eye-region pixels are unexplained (`ws3_masks/unclassified_audit.json`).\n")
A("## Reproduce\n```bash\ngit checkout research/upgrade\nPYTHON=<python with numpy scipy pillow matplotlib> research/verify_all.sh dist/final/Techtonic.zip <new_empty_work_dir>   # about 70 min on an Apple M5\n"
  "python3 research/check_results.py AUDIT/results AUDIT/results/results_check.json\npython3 research/integrity_check.py . AUDIT/results/integrity_check.json\n```\n")
A("## Limitations\n- One face asset, one detector and one machine. Pixel repeatability was measured on the same machine only.\n- The fitted depths are asset-specific effective parameters.\n"
  "- Eye-movement profiles are first-order textbook models, not fitted to human data.\n- GPU utilisation was not measured.\n- Segmentation is provisional.\n- The ROI render is rejected.\n- Four scripts in `research/` were not run in the validated pipeline (listed in `research/README.md`).\n")
open(os.path.join(R, "RELEASE_NOTE.md"), "w").write("\n".join(L)); print("wrote README.md and RELEASE_NOTE.md")

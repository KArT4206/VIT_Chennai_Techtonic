"""Completeness and staleness check of AUDIT/results (pure Python). Exit 1 on any problem.

    python3 research/check_results.py <results_dir> <out_json>

* every expected result file exists and is non-empty;
* every detector evaluation records the frozen detector SHA-256 (research/DETECTOR_FREEZE.txt);
* dataset integrity files report no problems and the sample counts equal the planned counts;
* integrity_check.json ok, package_unchanged.txt says unchanged, all research tests PASS;
* no GPU job still running (no background 'Blender -b' process).
"""
import glob, json, os, re, subprocess, sys
R, out = sys.argv[1:3]; here = os.path.dirname(os.path.abspath(__file__)); P = []
FROZEN = re.search(r"SHA-256 ([0-9a-f]{64})", open(os.path.join(here, "DETECTOR_FREEZE.txt")).read()).group(1)
EXPECT = ["compliance.json", "model_comparison.json", "pupil_geometry_probe.json", "verify_py_release_bundle.txt", "bias_root_cause.json",
          "research_pupil_levels.json", "integrity_check.json", "package_unchanged.txt", "research_tests.txt", "run_comparison.json", "run_environment.txt",
          "ws1_depth/depth_probe_extended.json", "ws1_depth/depth_fit.json", "ws1_depth/depth_fit_raw.csv", "ws1_depth/depth_fit_curves.png",
          "ws2_degradation/robustness.json", "ws3_masks/masks_metrics.json", "ws3_masks/unclassified_audit.json",
          "ws4_dataset/integrity.json", "ws4_dataset/coverage.json", "ws4_dataset/manifest.json",
          "ws5_dynamics/dynamics_validation.json", "ws5_dynamics/dynamics_render_check.json", "ws5_dynamics/selftest.txt",
          "ws6_dataset_v1/manifest.json", "ws6_dataset_v1/integrity.txt", "ws6_dataset_v1/dataset_roi_metrics.json",
          "ws6_performance/bench_compare.json", "ws6_performance/band_audit.json", "ws6_performance/benchmark_gpu_scene_samples.json",
          "ws6_performance/benchmark_cpu_64spp.json", "ws8_comparison/comparison_metrics.json", "dashboard/index.html"] + \
         [f"{c}_{k}" for c in ("release", "full_roi", "no_lids_roi", "no_lids_lens_roi", "no_lids_lens_nodisp_roi", "no_lids_lens_flat_roi") for k in ("metrics.json", "per_pupil.csv", "overlays.png")]
for f in EXPECT:
    p = os.path.join(R, f)
    if not os.path.exists(p) or os.path.getsize(p) == 0: P.append(f"missing or empty: {f}")
for p in glob.glob(os.path.join(R, "*_metrics.json")) + glob.glob(os.path.join(R, "ws*/*_metrics.json")):
    d = json.load(open(p)).get("detector")
    if d is not None and d.get("sha256") != FROZEN: P.append(f"stale detector in {os.path.relpath(p, R)}: {d.get('sha256')}")
if "0 integrity problems" not in open(os.path.join(R, "ws6_dataset_v1/integrity.txt")).read(): P.append("dataset v1 integrity problems")
m = json.load(open(os.path.join(R, "ws6_dataset_v1/manifest.json")))
if len(m["samples"]) != m["config"]["n"] or m["failures"]: P.append("dataset v1 incomplete")
c = json.load(open(os.path.join(R, "ws4_dataset/coverage.json")))["coverage"]
if c["n_samples"] != c["planned"] or c["failures"]: P.append("dataset v2 incomplete")
if not json.load(open(os.path.join(R, "ws4_dataset/integrity.json"))).get("ok"): P.append("dataset v2 integrity not ok")
if not json.load(open(os.path.join(R, "integrity_check.json"))).get("ok"): P.append("submission integrity check failed")
if open(os.path.join(R, "package_unchanged.txt")).read().strip() != "package files unchanged": P.append("extracted package changed")
t = open(os.path.join(R, "research_tests.txt")).read()
if re.search(r"^FAIL test_", t, re.M) or len(re.findall(r"^PASS test_", t, re.M)) < 6: P.append("research tests not all passing")
busy = [l for l in subprocess.run(["ps", "-axo", "args="], capture_output=True, text=True).stdout.splitlines() if "Blender" in l and " -b " in l and "grep" not in l]
if busy: P.append(f"background Blender still running: {busy[:2]}")
res = dict(ok=not P, problems=P, frozen_detector_sha256=FROZEN, files_checked=len(EXPECT))
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1)); sys.exit(0 if not P else 1)

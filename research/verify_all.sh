#!/usr/bin/env bash
# Full research validation from a CLEAN extraction of the release ZIP. Every Blender job goes through
# research/gpuq.py (one GPU job at a time). Results land in <results_dir> (default AUDIT/results).
#
#   [RESULTS=AUDIT/results] research/verify_all.sh <Techtonic.zip> <work_dir> [stage ...]
#
# Stages (default: all, in this order):
#   setup compliance comparison probe ablation heldout detector depthfit annotate masks degrade cmp8
#   dataset dataset2 dynamics bench bench_ext dashboard
# Env: BLENDER (default macOS app binary), PYTHON (numpy, scipy, Pillow, matplotlib).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; repo="$(dirname "$here")"
zip="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; W="$2"; RES="${RESULTS:-$repo/AUDIT/results}"; shift 2
stages="${*:-setup compliance comparison probe ablation heldout detector depthfit annotate masks degrade cmp8 dataset dataset2 dynamics bench bench_ext dashboard}"
B="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"; PY="${PYTHON:-python3}"
mkdir -p "$W/logs" "$RES"; W="$(cd "$W" && pwd)"; PKG="$W/pkg"; ROI="$W/abl/full/frame_10.png"; L="$W/logs"
bl() { local log="$1"; shift; "$PY" "$here/gpuq.py" --log "$L/$log" -- "$B" -b --factory-startup "$PKG/scene.blend" -P "$@"; }
py() { "$PY" -I "$@"; }
stamp() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L/verify_all.log"; }
for s in $stages; do stamp "stage $s"; case $s in
  setup)
    [ ! -e "$PKG" ] || { echo "work dir already has pkg/; use a new work dir for a clean run" >&2; exit 2; }
    mkdir "$PKG"; (cd "$PKG" && unzip -q "$zip")
    { shasum -a 256 "$zip"; "$B" --version | head -1; sw_vers 2>/dev/null | tr '\n' ' '; echo; sysctl -n machdep.cpu.brand_string 2>/dev/null || true
      "$PY" -c 'import numpy,scipy,PIL,matplotlib,sys;print("python",sys.version.split()[0],"numpy",numpy.__version__,"scipy",scipy.__version__,"Pillow",PIL.__version__,"matplotlib",matplotlib.__version__)'
      git -C "$repo" rev-parse HEAD; git -C "$repo" status --short research AUDIT | head -100; } > "$RES/run_environment.txt"
    (cd "$PKG" && find . -type f -exec shasum -a 256 {} + | sort -k2) > "$W/pkg_before.sha";;
  compliance) bl compliance.log "$here/compliance_tests.py" -- "$RES/compliance.json";;
  comparison) bl comparison.log "$here/model_comparison.py" -- "$RES/model_comparison.json";;
  probe)      bl probe.log "$here/pupil_geometry_probe.py" -- "$RES/pupil_geometry_probe.json"
              mkdir -p "$RES/ws1_depth"
              bl depth_probe.log "$here/depth_probe_extended.py" -- "$RES/ws1_depth/depth_probe_extended.json" --dmin 12 --dmax 20 --step 0.05;;
  ablation)   for m in full no_lids no_lids_lens no_lids_lens_nodisp no_lids_lens_flat; do bl "abl_$m.log" "$here/render_ablation.py" -- "$W/abl" $m --samples 64; done;;
  heldout)    for m in full no_lids_lens; do bl "abl_heldout_$m.log" "$here/render_ablation.py" -- "$W/abl_heldout" $m --samples 64 --poses heldout; done;;
  detector)   py "$here/evaluate_detector.py" release "$RES" "$PKG" > "$L/det_release.log"
              for m in full no_lids no_lids_lens no_lids_lens_nodisp no_lids_lens_flat; do py "$here/evaluate_detector.py" --roi-from "$ROI" ${m}_roi "$RES" "$W/abl/$m" > "$L/det_$m.log"; done
              py "$repo/tools/verify.py" "$PKG" > "$RES/verify_py_release_bundle.txt" || true;;   # original evaluator, unchanged (exits 1 on its known FAILs)
  depthfit)   py "$here/depth_fit.py" "$RES/ws1_depth/depth_probe_extended.json" "$ROI" "$RES/ws1_depth" \
                 "no_lids_lens=$W/abl/no_lids_lens:$W/abl_heldout/no_lids_lens" "full=$W/abl/full:$W/abl_heldout/full" > "$L/depth_fit.log"
              py "$here/bias_root_cause.py" "$RES" "$RES/bias_root_cause.json" release full_roi no_lids_roi no_lids_lens_roi no_lids_lens_nodisp_roi no_lids_lens_flat_roi > "$L/bias_root_cause.log";;
  annotate)   py "$here/annotate_three_level.py" "$PKG" "$RES/ws1_depth/depth_probe_extended.json" "$ROI" "$RES/research_pupil_levels.json" > "$L/annotate.log";;
  masks)      bl masks.log "$here/masks.py" -- "$W/masks"
              py "$here/masks_eval.py" "$W/masks" "$PKG" "$RES/ws3_masks" --roi-from "$ROI" > "$L/masks_eval.log";;
  degrade)    py "$here/degrade.py" selftest > "$L/degrade_selftest.log"
              py "$here/degrade.py" sweep "$PKG" "$W/deg" --seed 7 > "$L/degrade_sweep.log"
              mkdir -p "$RES/ws2_degradation"; py "$here/degrade_eval.py" "$W/deg" "$ROI" "$RES/ws2_degradation/robustness.json" "$PKG" > "$L/degrade_eval.log";;
  cmp8)       bl cmp8.log "$here/comparison_render.py" -- "$W/cmp" --samples 64
              py "$here/comparison_eval.py" "$W/cmp" "$ROI" "$RES/ws8_comparison" > "$L/cmp8_eval.log";;
  dataset)    bl dataset.log "$here/dataset_engine.py" -- --config "$here/configs_dataset_40.json" --out "$W/dataset" --commit "$(git -C "$repo" rev-parse HEAD)"
              mkdir -p "$RES/ws6_dataset_v1"; py "$here/validate_dataset.py" "$W/dataset" | tee "$RES/ws6_dataset_v1/integrity.txt"
              cp "$W/dataset/manifest.json" "$RES/ws6_dataset_v1/manifest.json"
              py "$here/evaluate_detector.py" --roi-from "$ROI" dataset_roi "$RES/ws6_dataset_v1" "$W/dataset" > "$L/det_dataset.log";;
  dataset2)   bl dataset2.log "$here/dataset_v2_render.py" -- --config "$here/configs/pilot_v2.json" --out "$W/ds2" --commit "$(git -C "$repo" rev-parse HEAD)"
              py "$here/dataset_v2_post.py" "$W/ds2" > "$L/dataset2_post.log" || echo "dataset_v2_post reported problems (see log)"
              mkdir -p "$RES/ws4_dataset"; cp "$W/ds2/coverage.json" "$W/ds2/integrity.json" "$W/ds2/manifest.json" "$RES/ws4_dataset/" 2>/dev/null || true
              cp "$W/ds2/coverage.png" "$RES/ws4_dataset/" 2>/dev/null || true;;
  dynamics)   mkdir -p "$RES/ws5_dynamics"; py "$here/dynamics.py" --selftest > "$RES/ws5_dynamics/selftest.txt"
              py "$here/dynamics_validate.py" "$RES/ws5_dynamics" > "$L/dynamics_validate.log"
              bl dynamics.log "$here/dynamics.py" -- --render "$W/dynamics" --fps 30 --samples 16
              cp "$W/dynamics/dynamics.json" "$RES/ws5_dynamics/dynamics_render.json"
              py "$here/dynamics_render_check.py" "$W/dynamics" "$ROI" "$RES/ws5_dynamics/dynamics_render_check.json" > "$L/dynamics_check.log";;
  bench)      mkdir -p "$RES/ws6_performance"
              for c in original band persistent combined; do
                "$PY" "$here/gpuq.py" --log "$L/bench_$c.log" -- bash -c "BENCH_T0=\$(python3 -c 'import time;print(time.time())') exec /usr/bin/time -l \"$B\" -b --factory-startup \"$PKG/scene.blend\" -P \"$here/bench_speed.py\" -- \"$W/bench\" $c --samples 128"
              done
              py "$here/bench_compare.py" "$W/bench" "$ROI" "$RES/ws6_performance/bench_compare.json" > "$L/bench_compare.log"
              for c in original band persistent combined; do cp "$W/bench/$c/bench.json" "$RES/ws6_performance/bench_$c.json"; grep -E 'maximum resident set size|real' "$L/bench_$c.log" > "$RES/ws6_performance/time_$c.txt" || true; done;;
  bench_ext)  "$PY" "$here/gpuq.py" --log "$L/bench_gpu512.log" -- /usr/bin/time -l "$B" -b --factory-startup "$PKG/scene.blend" -P "$here/benchmark.py" -- "$W/bench_gpu" --repeats 3
              cp "$W/bench_gpu/benchmark.json" "$RES/ws6_performance/benchmark_gpu_scene_samples.json"
              "$PY" "$here/gpuq.py" --log "$L/bench_cpu64.log" -- /usr/bin/time -l "$B" -b --factory-startup "$PKG/scene.blend" -P "$here/benchmark.py" -- "$W/bench_cpu" --cpu --samples 64 --repeats 2
              cp "$W/bench_cpu/benchmark.json" "$RES/ws6_performance/benchmark_cpu_64spp.json"
              grep -hE 'maximum resident set size|real' "$L/bench_gpu512.log" "$L/bench_cpu64.log" > "$RES/ws6_performance/benchmark_time.txt" || true;;
  dashboard)  (cd "$PKG" && find . -type f -exec shasum -a 256 {} + | sort -k2) > "$W/pkg_after.sha"
              if cmp -s "$W/pkg_before.sha" "$W/pkg_after.sha"; then echo "package files unchanged" > "$RES/package_unchanged.txt"; else echo "PACKAGE FILES CHANGED" > "$RES/package_unchanged.txt"; fi
              py "$here/tests/test_research.py" > "$RES/research_tests.txt" 2>&1 || true
              py "$here/integrity_check.py" "$repo" "$RES/integrity_check.json" > "$L/integrity.log" || echo "INTEGRITY CHECK FAILED"
              py "$here/compare_runs.py" "$RES" "$RES/run_comparison.json" > "$L/compare_runs.log" || true
              py "$here/masks_unclassified_audit.py" "$W/masks" "$RES/ws3_masks/unclassified_audit.json" > "$L/masks_audit.log"
              py "$here/bench_band_audit.py" "$W/bench" "$RES/ws6_performance/band_audit.json" > "$L/band_audit.log"
              py "$here/dashboard.py" "$RES" "$RES/dashboard/index.html" > "$L/dashboard.log"
              py "$here/check_results.py" "$RES" "$RES/results_check.json" > "$L/results_check.log" || echo "RESULTS CHECK FAILED"
              py "$here/build_report.py" "$RES" "$W" "$RES/INTEGRATION_REPORT.md" > "$L/build_report.log";;
  *) echo "unknown stage $s" >&2; exit 2;;
esac; done
stamp VERIFY_ALL_DONE

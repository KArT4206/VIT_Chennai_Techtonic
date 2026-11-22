#!/usr/bin/env bash
# Reproduce every research/upgrade measurement from the release ZIP, one Blender process at a time.
#   research/run_all.sh <Techtonic.zip> <work_dir> [stage...]     stages: compliance comparison ablation detector dataset dynamics benchmark evidence
# Env: BLENDER (default macOS app), PYTHON (numpy, scipy, pillow, matplotlib).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; zip="$1"; W="$2"; shift 2
stages="${*:-compliance comparison ablation detector dataset dynamics benchmark evidence}"
B="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"; PY="${PYTHON:-python3}"
R="$W/results"; mkdir -p "$W" "$R"
[ -d "$W/pkg" ] || { mkdir "$W/pkg"; (cd "$W/pkg" && unzip -q "$zip"); }
shasum -a 256 "$zip" | tee "$R/zip_sha256.txt"
"$B" --version | head -1 > "$R/blender_version.txt"
run() { echo "== $*"; "$B" -b --factory-startup "$W/pkg/scene.blend" -P "$@"; }
for s in $stages; do case $s in
  compliance) run "$here/compliance_tests.py" -- "$R/compliance.json" > "$W/compliance.log" 2>&1; grep COMPLIANCE "$W/compliance.log";;
  comparison) run "$here/model_comparison.py" -- "$R/model_comparison.json" > "$W/comparison.log" 2>&1; grep COMPARISON "$W/comparison.log";;
  ablation)   for m in full no_lids no_lids_lens; do run "$here/render_ablation.py" -- "$W/abl" $m --samples 64 > "$W/abl_$m.log" 2>&1; done;;
  detector)   "$PY" -I "$here/evaluate_detector.py" release "$R" "$W/pkg" > "$W/det_release.log"
              for m in full no_lids no_lids_lens; do "$PY" -I "$here/evaluate_detector.py" --roi-from "$W/abl/full/frame_10.png" ${m}_roi "$R" "$W/abl/$m" > "$W/det_$m.log"; done;;
  dataset)    run "$here/dataset_engine.py" -- --config "$here/configs_dataset_40.json" --out "$W/dataset" --commit "$(git -C "$here" rev-parse HEAD)" > "$W/dataset.log" 2>&1
              "$PY" -I "$here/validate_dataset.py" "$W/dataset" | tee "$R/dataset_integrity.txt"
              "$PY" -I "$here/evaluate_detector.py" --roi-from "$W/abl/full/frame_10.png" dataset_roi "$R" "$W/dataset" > "$W/det_dataset.log";;
  dynamics)   "$PY" -I "$here/dynamics.py" --selftest | tee "$R/dynamics_selftest.txt"
              run "$here/dynamics.py" -- --render "$W/dynamics" --fps 30 --samples 16 > "$W/dynamics.log" 2>&1; cp "$W/dynamics/dynamics.json" "$R/";;
  benchmark)  /usr/bin/time -l "$B" -b --factory-startup "$W/pkg/scene.blend" -P "$here/benchmark.py" -- "$W/bench_gpu" --repeats 3 > "$W/bench_gpu.log" 2>&1; cp "$W/bench_gpu/benchmark.json" "$R/benchmark_gpu_default_samples.json"
              /usr/bin/time -l "$B" -b --factory-startup "$W/pkg/scene.blend" -P "$here/benchmark.py" -- "$W/bench_cpu" --cpu --samples 64 --repeats 2 > "$W/bench_cpu.log" 2>&1; cp "$W/bench_cpu/benchmark.json" "$R/benchmark_cpu_64spp.json"
              grep -E 'real|maximum resident' "$W/bench_gpu.log" "$W/bench_cpu.log" | tee "$R/bench_time.txt";;
  evidence)   "$PY" -I "$here/make_evidence.py" "$W/pkg" "$R" "$W/evidence";;
esac; done
echo RUN_ALL_DONE

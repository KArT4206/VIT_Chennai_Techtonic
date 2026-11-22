> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Implementation report (branch `research/upgrade`)

All new code lives in `research/`. It imports `wrapper/eyes.py` from the bundle unchanged and never saves `scene.blend`.

| Stage | File | What it does | How to run |
|---|---|---|---|
| 0 | `AUDIT/TECHNICAL_AUDIT.md` | Audit, reproduction and classification of the 22 FAILs | — |
| 1 | `research/compliance_tests.py` | 40 checks: structure, geometry, known-point projection, pivot/torsion, inputs, reset, determinism | `blender -b --factory-startup <bundle>/scene.blend -P research/compliance_tests.py -- out.json` |
| 2 | `research/pupil_detector.py` | Independent detector working from the image only: adaptive dark-blob search, side-by-side pair selection, 180-ray sub-pixel edge, catchlight rejection, RANSAC circle fit, confidence score | imported |
| 2 | `research/evaluate_detector.py` | Detector vs ground truth: success rate, MAE x/y, bias, mean, RMSE, median, P95, max, error by confidence bin, CSV, overlay sheet including failures | `python research/evaluate_detector.py NAME OUTDIR SRC...` |
| 2 | `research/render_ablation.py` | The 11 poses with lids hidden, or lids and cornea hidden, to separate occlusion and refraction effects | `blender ... -P research/render_ablation.py -- OUT full\|no_lids\|no_lids_lens` |
| 3 | `research/model_comparison.py` | Planar vs spherical vs anatomical (refracted) pupil projection on the 10 poses, plus a 0–35° sweep | `blender ... -P research/model_comparison.py -- out.json` |
| 4 + 6 | `research/dataset_engine.py` | Config-driven, per-sample-seeded, resumable generator; iris hue/value variants; manifest with provenance and SHA-256; failures recorded, not fatal | `blender ... -P research/dataset_engine.py -- --config cfg.json --out DIR` |
| 6 | `research/validate_dataset.py` | Completeness, hashes, image size, input range, pupils inside the image, no partial files | `python research/validate_dataset.py DIR` |
| 5 | `research/dynamics.py` | Saccade, pursuit, vergence, fixation drift and blink profiles; self-test; optional render | `python research/dynamics.py --selftest` |

Results are written to `AUDIT/results/` as JSON, and the reports quote them.

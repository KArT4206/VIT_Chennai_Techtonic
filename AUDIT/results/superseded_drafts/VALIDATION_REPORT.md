> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Validation report

Ground truth (track A) comes from geometry: `pupil_center_2D_*` written by `wrapper/eyes.py`, as the camera projection of the 3-D pupil through an analytic cornea.
Prediction (track B) comes from `research/pupil_detector.py`, which sees only the PNG.
Pairing happens after detection, by eye.

> Status: every number below is copied from a file in `AUDIT/results/`. Items marked TODO have no result file yet.

## 1. Original evaluator on the release
51 PASS / 20 FAIL on the bundle. With `directions/` added it is 60 PASS / 22 FAIL. The cause of each failure is in TECHNICAL_AUDIT.md §4.

## 2. Independent detector vs ground truth

Values come from `AUDIT/results/<run>_metrics.json`. The per-pupil values are in `<run>_per_pupil.csv`. Every pupil, failures included, is drawn in `<run>_overlays.png`.

How to read the table:
- **Success** means the detector returned a fit within 5 px of the ground truth.
- **Error statistics are over successful detections only.** Misses are listed separately below.
- **Bias** is the mean of detector minus ground truth. Positive y means the detector is lower in the image.
- **`_roi` runs** restrict the search to a scene-level eye region. That region comes from the detector's own detection on the full-scene reset frame, never from ground truth.

| Run | n pupils | Success | MAE x / y (px) | Bias x / y (px) | Mean | RMSE | Median | P95 | Max |
|---|---|---|---|---|---|---|---|---|---|
| Release, 10 frames, no prior (`release`) | 20 | 18/20 | 1.171 / 3.079 | +0.465 / +3.079 | 3.398 | 3.622 | 3.596 | 4.953 | 4.972 |
| Full scene, 11 poses (`full_roi`) | 22 | 15/22 | 1.105 / 2.857 | +0.059 / +2.857 | 3.159 | 3.344 | 3.294 | 4.747 | 4.875 |
| Lids hidden (`no_lids_roi`) | 22 | 19/22 | 1.047 / 3.106 | +0.572 / +3.106 | 3.349 | 3.5 | 3.471 | 4.75 | 4.895 |
| Lids + cornea hidden (`no_lids_lens_roi`) | 22 | 22/22 | 1.051 / 2.894 | +0.836 / +2.894 | 3.172 | 3.317 | 3.282 | 4.494 | 4.502 |
| … + displacement removed (`no_lids_lens_nodisp_roi`) | 22 | 22/22 | 1.191 / 2.527 | +1.086 / +2.527 | 2.929 | 3.082 | 2.968 | 4.174 | 4.187 |
| … + normal map removed (`no_lids_lens_flat_roi`) | 22 | 22/22 | 1.174 / 2.444 | +1.098 / +2.444 | 2.849 | 3.003 | 2.946 | 4.084 | 4.136 |
| Dataset, 40 samples, iris/lighting variants (`dataset_roi`) | 80 | 60/80 | 0.835 / 2.679 | +0.315 / +2.609 | 2.884 | 3.045 | 2.95 | 4.328 | 4.862 |

### 2.1 Misses, reported separately

| Run | Pupil | h, v | Error (px) | Status | Kind |
|---|---|---|---|---|---|
| release | frame01 L | +0.59, +0.81 | 1.55 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| release | frame01 R | +0.59, +0.81 | 2.18 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| full_roi | frame_00 R | +0.00, +1.00 | 5.77 | ok | located 5–20 px off (lid/lash edge) |
| full_roi | frame_01 L | +0.59, +0.81 | 1.45 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| full_roi | frame_01 R | +0.59, +0.81 | 2.42 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| full_roi | frame_04 R | +0.59, -0.81 | 5.72 | ok | located 5–20 px off (lid/lash edge) |
| full_roi | frame_05 L | +0.00, -1.00 | 5.11 | ok | located 5–20 px off (lid/lash edge) |
| full_roi | frame_05 R | +0.00, -1.00 | 5.58 | ok | located 5–20 px off (lid/lash edge) |
| full_roi | frame_10 R | +0.00, +0.00 | 7.44 | low_confidence | located 5–20 px off (lid/lash edge) |
| no_lids_roi | frame_01 R | +0.59, +0.81 | 2.69 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| no_lids_roi | frame_05 L | +0.00, -1.00 | 123.06 | ok | wrong blob picked |
| no_lids_roi | frame_05 R | +0.00, -1.00 | 5.17 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000001 L | +0.45, +0.94 | 31.13 | low_confidence | wrong blob picked |
| dataset_roi | 000001 R | +0.45, +0.94 | 1.93 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| dataset_roi | 000005 L | +0.84, +0.86 | 1.66 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| dataset_roi | 000005 R | +0.84, +0.86 | 2.55 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| dataset_roi | 000013 L | +0.99, -0.82 | 5.13 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000013 R | +0.99, -0.82 | 5.51 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000014 L | +0.34, +0.88 | 6.51 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000014 R | +0.34, +0.88 | 1.98 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| dataset_roi | 000021 R | +0.24, +0.78 | 2.11 | fail | rejected by detector (fit close, confidence/inlier test failed) |
| dataset_roi | 000022 L | -0.89, -0.91 | 19.79 | fail | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000025 L | -0.77, +1.00 | 402.56 | low_confidence | wrong blob picked |
| dataset_roi | 000026 L | +0.78, -0.99 | 5.14 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000026 R | +0.78, -0.99 | 5.73 | low_confidence | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000027 L | -0.46, -0.96 | 22.83 | low_confidence | wrong blob picked |
| dataset_roi | 000027 R | -0.46, -0.96 | 33.31 | ok | wrong blob picked |
| dataset_roi | 000028 R | +0.93, +0.41 | 9.42 | low_confidence | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000029 L | -0.80, +0.30 | 8.75 | low_confidence | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000029 R | -0.80, +0.30 | 8.57 | low_confidence | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000033 R | +0.04, +0.73 | 6.21 | ok | located 5–20 px off (lid/lash edge) |
| dataset_roi | 000037 R | -0.19, +0.50 | 9.44 | low_confidence | located 5–20 px off (lid/lash edge) |

There are three kinds of miss:
1. **Self-rejected.** The detector's RANSAC or confidence test rejected a fit that was actually close. This happens mostly at upward gaze, where the upper lid covers the top of the pupil.
2. **Off by 5–20 px.** The fitted edge followed a lid or lash edge instead of the pupil.
3. **Wrong blob.** Another dark region was picked. Examples are no_lids frame 5 L and dataset 000025 L.

In the dataset run, confidence tracks error: the median error is 4.33 px at confidence below 0.35 (n = 18), 3.04 px at 0.35–0.5 (n = 38) and 2.05 px at 0.5 and above (n = 24).

### 2.2 What causes the systematic offset (status: partly explained)

What the ablations establish, with the same detector and ROI in every condition:

| Condition removed | Mean downward bias |
|---|---|
| none (full scene) | +2.64 |
| lids | +2.71 |
| + cornea `Lens` meshes | +2.39 |
| + displacement | +2.03 |
| + normal map | +1.94 |

- **Lids are not the cause.** Hiding them leaves the bias at +2.71 px.
- **The cornea meshes, displacement and normal-map shading together account for about 0.7 px.**
- **About 1.9 px remains** in the flattest condition tested.

**Hypothesis A: the pupil depth differs.** Supported, with partial evidence (`painted_pupil_geometry.json`, `bias_root_cause.json`).
- The wrapper places the pupil 14.19 mm (left eye) and 14.29 mm (right) from the eye centre.
- The scanned eyeball mesh carries the painted pupil at 15.3–16.1 mm (mean 15.8 mm).
- A deeper pupil moves further in the image for the same rotation. The detector indeed shows about 11–12 % more gaze-dependent displacement than the ground truth.
- Re-projecting a pupil at 15.8 mm and removing one constant offset leaves residuals of 0.29 px mean (0.40 max) in the flat condition. At the wrapper's 14.19 mm the residuals are 1.81 px mean (2.09 max).
- This explains the gaze-dependent part of the error.

**The constant part (about 1.9 px down and 0.6 px across in the flat condition) is not explained yet.** Candidates still open:
- **Pixel-centre convention of the detector.** A +0.5 px correction is being tested.
- **A texture centroid that differs from the wrapper's assumed pupil UV.** The measured difference is only about 0.001 UV, which looks too small for 2 px.
- **A shading or texture gradient** across the pupil edge.

An unlit-albedo probe (`research/render_bias_probe.py`, `research/analyze_bias.py`) is designed to settle this. It is not yet run.

**Unresolved contradiction in the mask check.**
- One analysis states that `tools/pupil_mask_check.py`'s linear-luminance threshold of 0.05 selects the whole iris disc, not the pupil.
- `painted_pupil_geometry.json` reports that the same threshold on the texture gives a pupil-sized region (r_uv 0.0377; the iris is about 0.11).
- Until the probe's mask radius is measured, the earlier "0.24 px mean / 0.39 px max" figure is withdrawn as evidence of pupil accuracy.

**What does not change:**
- The rotation geometry, pivots, Listing's law, camera and K[R|t] are verified (40/40 compliance checks).
- The metadata and calibration were not modified to reduce detector error. Any corrected ground-truth field, for example a "painted surface pupil", is a proposal for a future version, not a change to the submission.

## 3. Comparison of three eye models
Source: `AUDIT/results/model_comparison.json` (`research/model_comparison.py`, 22 Nov 2026 run).

Within the spec range (±5 cm at 35 cm, ≤ 8.1°, 10 poses × 2 eyes):

| | Mean | Max |
|---|---|---|
| Planar (gain fitted at h = 1) vs anatomical | 0.52 px | 0.87 px |
| Spherical without cornea vs anatomical | 0.51 px | 0.58 px |

The projected pupil aspect ratio is 0.983–0.995 for the anatomical model and 1.0 for the planar one. The planar gain is 14.3 px per unit h for the left eye and 14.0 for the right.

Extended sweep, left eye, horizontal gaze:

| Gaze | 0° | 10° | 20° | 30° | 35° |
|---|---|---|---|---|---|
| Planar − anatomical (px) | 0.07 | 0.12 | 0.08 | 1.29 | 2.95 |
| Spherical − anatomical (px) | 0.07 | 0.90 | 1.71 | 2.03 | 1.80 |

**What this shows:** at this camera distance and these angles, the three models put the pupil centre within about 1 px of each other. Planar translation is only clearly worse beyond about 30°.

**What it does not show:** that rotation matters for the centre position within the spec range. Its value there is the rendered appearance: foreshortened iris and pupil, limbus position, the lids following the eye, and corneal highlights. Both models' centre positions also depend on the analytic cornea (limitation 3).

## 4. Compliance
See CALIBRATION_REPORT.md. Result of the first run: 36 PASS / 4 FAIL, where the 4 were the float32 tolerance issue. Final run: **40/40 PASS** (`AUDIT/results/compliance.json`).

## 5. Dynamics self-test
`python research/dynamics.py --selftest`: 11/11 PASS (22 Nov 2026). Rendered sequences: TODO.

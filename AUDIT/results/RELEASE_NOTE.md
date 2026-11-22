# Release note — Techtonic research branch

**Branch:** `research/upgrade`. **Research commit:** `1b9a691`. **Submission baseline:** tag `submission-baseline-v1.0` and branch `submission/final`, both at `3155655`. Release v1.0 `Techtonic.zip` SHA-256 `acccb548c270bfab4719c3f173eda544a1b818fd858f56b1fe2d67a07790a0dc`. The research changes are confined to `research/` and `AUDIT/results/`, and none of them is part of the submitted hackathon package. The official ground truth (`metadata.json`, `wrapper/eyes.py`) is unchanged. Integrity check: PASS; results check: PASS. Full report: [`INTEGRATION_REPORT.md`](INTEGRATION_REPORT.md).

## Findings

**Pupil-centre discrepancy (`ws1_depth/depth_fit.json`).** The official 2-D ground truth uses the wrapper's anatomical pupil, refracted through an analytic cornea. The rendered asset paints its pupil further out on the eyeball surface, and its `Lens` mesh does not refract. The depth below is an **effective fitted parameter of this asset as seen by this detector, not an anatomical dimension**. Bootstrap: 2000 resamples of fit poses, seed 12345, percentile interval. Held-out: 14 gaze positions, never used for fitting.

| condition | eye | effective depth (mm) | 95% CI (mm) | held-out RMSE, fitted (px) | held-out RMSE, official GT (px) |
|---|---|---|---|---|---|
| no_lids_lens | L | 16.10 | 16.05–16.15 | 0.116 | 3.137 |
| no_lids_lens | R | 16.15 | 16.10–16.20 | 0.136 | 3.152 |
| full | L | 16.60 | 16.35–16.90 | 0.421 | 3.277 |
| full | R | 16.45 | 15.65–17.15 | 0.749 | 3.514 |

**Detector validation**, separate from dataset generation (frozen detector `research/DETECTOR_FREEZE.txt`; success = within 5 px of the official GT):

| condition | success | RMSE px | signed bias y px |
|---|---|---|---|
| release | 90% | 3.622 | 3.079 |
| full_roi | 68% | 3.344 | 2.857 |
| no_lids_lens_roi | 100% | 3.317 | 2.894 |
| dataset_roi | 75% | 3.051 | 2.619 |

**Dataset generation**, separate from the detector:
- v1: 40/40 samples, 0 failures, `40 samples, 0 recorded failures, 0 integrity problems`.
- v2 pilot: 22/22 samples, 0 failures, integrity ok = True.

**Rendering (`ws6_performance/`).** Persistent-scene rendering **passed** equivalence: speed-up 1.121× (6-pose sequence 120.25 s → 107.3 s), pixels within 1/255. Eye-region (ROI/border) rendering **failed** equivalence and is **not adopted**: inside the region pixels differ by up to 37/255, and by up to 181/255 at its edges. Its 4.469× timing is therefore not claimed as a speed-up.

**Rendered eye movement (`ws5_dynamics/dynamics_render_check.json`, measured by the detector on rendered frames).** Saccade: 27 frames at 4.167 ms; 5–95 % duration 33.94 ms / 37.06 ms (image-left / image-right eye) vs 36.72 ms commanded. The image-right eye has a detector glitch: maximum residual 8.088 px, monotonic = False. It is reported, not removed. Pursuit: 31 frames; measured lag 100.0 ms (resolution 33.3 ms) vs 100.0 ms commanded; gain 0.951 / 0.948. Vergence: converges = True. Blinks are not rendered.

**Semantic segmentation: provisional.** 13.10%–13.11% of pixels per frame are unclassified. Most of them are background at the image sides, but up to 1.1% of eye-region pixels are unexplained (`ws3_masks/unclassified_audit.json`).

## Reproduce
```bash
git checkout research/upgrade
PYTHON=<python with numpy scipy pillow matplotlib> research/verify_all.sh dist/final/Techtonic.zip <new_empty_work_dir>   # about 70 min on an Apple M5
python3 research/check_results.py AUDIT/results AUDIT/results/results_check.json
python3 research/integrity_check.py . AUDIT/results/integrity_check.json
```

## Limitations
- One face asset, one detector and one machine. Pixel repeatability was measured on the same machine only.
- The fitted depths are asset-specific effective parameters.
- Eye-movement profiles are first-order textbook models, not fitted to human data.
- GPU utilisation was not measured.
- Segmentation is provisional.
- The ROI render is rejected.
- Four scripts in `research/` were not run in the validated pipeline (listed in `research/README.md`).

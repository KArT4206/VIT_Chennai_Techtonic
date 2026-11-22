> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Technical audit — Team Techtonic, Track 01

Audit date: 22 Nov 2026 (after the 18 Nov 2026 submission deadline).
Baseline: tag `submission-baseline-v1.0` (= branch `submission/final`, release v1.0, `Techtonic.zip` SHA-256 `acccb548c270bfab4719c3f173eda544a1b818fd858f56b1fe2d67a07790a0dc`).
All upgrade work is on branch `research/upgrade`. The submitted release, its ZIP and the default branch are not modified.

Environment used for every measurement: Blender 5.3.0, Apple M5, 24 GB RAM, macOS (Darwin 27), Cycles on Metal; analysis Python 3 with numpy 2.5.4, scipy 1.18.1, Pillow.

## 1. Repository architecture

| Part | Path | Role |
|---|---|---|
| Scene | `scene.blend` | Scanned head (licensed for this publication only), armature with `eye.L` / `eye.R`, eyeball meshes `Realtime Eyeball Left/Right`, refracting `Lens Left/Right` (cornea), lids, lashes, brows; fixed camera; 5 constant lights |
| Wrapper | `wrapper/eyes.py` | `move(h,v)`, `reset()`, `render(path)`, `state()`, `render_sequence()`, CLI `--move/--reset/--out/--samples/--cpu` |
| Evaluator package | `dist/final/Techtonic.zip` | `scene.blend`, `wrapper/eyes.py`, `renders/` (10 PNG), `metadata.json`, `README.md` |
| Original evaluator | `tools/verify.py` (same file as `demo/final_hair/tools/verify.py`) | Layout, sequence maths, K[R|t] reprojection, image-based pupil check, 5-direction check |
| Lighting-free check | `tools/pupil_mask_check.py` | Renders the painted pupil as an emission mask and compares its centroid with metadata |
| API test | `demo/final_hair/tools/phase2g_api_test.py` | 19 API-level assertions |
| Upgrade code (new) | `research/` | See IMPLEMENTATION_REPORT.md |

## 2. How the wrapper works (verified by reading `wrapper/eyes.py`)

- Input `(h, v)` is validated (non-numeric, NaN, inf → `ValueError`) and clamped to [-1, 1].
- Fixation target = eye midpoint + (5 cm·h, −35 cm, 5 cm·v) in world metres (face looks along −Y).
- Each eye bone is rotated about its own head (the eyeball centre) by the shortest arc from the calibrated primary axis to the target direction (Listing's law, zero torsion). The eyes therefore converge.
- Upper and lower lid bones follow vertical gaze (gains 1.1 and 0.35).
- `pupil_center_2D_*` is the apparent (entrance) pupil: the camera ray that, refracted by an analytic corneal sphere, lands on the 3-D pupil centre, solved by Newton iteration. The unrefracted projection is also written.
- `bpy.context.view_layer.update()` is called after posing, so `render()` sees the new pose without a frame change.

## 3. The conflicting numbers: what each one measures

| Claim | Source | What it actually tests |
|---|---|---|
| 19/19 API tests passed | `phase2g_api_test.py` | Wrapper API behaviour (calls, return values, clamping, determinism). Does **not** look at rendered pixels. |
| Sub-pixel error (0.24 px mean, 0.39 px max, 22 pupils); now withdrawn as a pupil-accuracy claim, see VALIDATION_REPORT §2.2 | `pupil_mask_check.py` | Painted pupil rendered as an emission mask **with lids, skin and the corneal `Lens` meshes hidden**. Validates the geometry/projection of the pupil, not the photoreal image. |
| 60 PASS / 22 FAIL | `tools/verify.py` incl. `directions/` | Image-based detector on the photoreal renders. |

These are three different suites. They are not contradictory, but the README should not present the sub-pixel figure as image-detection accuracy.

## 4. Reproduction of the 22 failures (22 Nov 2026, fresh unzip of the release ZIP)

Command: `python tools/verify.py <unzipped bundle>` (+ the five `--move/--reset` renders in `directions/`).

- 20 × `frame k L/R: rendered pupil at metadata 2D point` — offsets 5.83–12.60 px (threshold 2.5 px).
- 2 × `reset L/R: centre pupil sits between left/right/up/down` — 5.95 px and 5.68 px off (threshold 1.5 px).
- All other 60 checks pass, including all 8 direction checks (pupil moves 11.3–33.6 px the commanded way) and K[R|t] reprojection.

### Classification

| Failure | Root cause (evidence) | Severity | Status |
|---|---|---|---|
| 20 × frame offset | **Evaluator detector failure.** `verify.detect_pupil` uses a fixed 44 × 44 px window and was tuned on the earlier MakeHuman head. On the scanned head the pupil radius is ~15–16 px, so the window clips the pupil and lashes/lid enter the dark mask. Overlays (green = metadata, red = old detector) show the old detector landing on lashes and the lid edge while the metadata point sits in the visible pupil centre. | Medium (evaluator credibility) | Explained; replaced by an independent detector in `research/pupil_detector.py`. Original `verify.py` is left unchanged. |
| 2 × reset centring | **Test assumption, not a wrapper fault.** The check expects reset to lie at the mean of the 4 direction pupils. Projection of a rotating sphere is not symmetric (up/down shifts measured 33.6 px vs 11.3 px, because the camera is level with the eyes and the lids move with gaze), so the mean of the four is not the reset position. | Low | Explained; reset correctness is tested directly instead (reset after moves = first reset, bit-identical state). |

**Open item found during this audit:** on down-gaze frames the new detector, fitting only the visible pupil arc, places the centre ~4 px lower than the metadata point. The lower lid covers the bottom of the pupil there. The mask check cannot settle it because it hides the lids and the corneal `Lens` meshes. Ablation results: the lids, the cornea meshes, displacement and the normal map together explain only about 0.7 px of the 2.6 px. The gaze-dependent part matches a pupil-depth difference: 15.8 mm painted versus 14.2 mm in the wrapper. A constant ~1.9 px is still open. See VALIDATION_REPORT.md §2.2.

## 5. Top gaps, ranked by impact

1. Image-based accuracy was never independently measured on the photoreal renders (only the mask check).
2. The original evaluator gives 22 FAILs that are not caused by the submission; jurors running it see failures.
3. README mixes three suites' numbers.
4. A systematic ~2.6 px (up to 5 px) offset between the metadata 2D pupil and the rendered pupil. Lids and the cornea are ruled out as the main cause; the pupil-depth mismatch explains the gaze-dependent part; ~1.9 px of constant offset is still unexplained.
5. No known-point projection test of K[R|t] against Blender's own projection (now added: max 0.0002 px over 500 points).
6. No machine-readable compliance report (now `research/compliance_tests.py`).
7. Planar vs rotation claim was not quantified (now `research/model_comparison.py`).
8. Dataset generator had no manifest/resume/integrity check (now `research/dataset_engine.py` + `validate_dataset.py`).
9. No timing/repeatability benchmark.
10. Only one face asset; appearance variation limited to iris colour/value and lighting.

## 6. Baseline preservation

- Tag `submission-baseline-v1.0` created on the submitted commit.
- Branch `research/upgrade` for all changes.
- `wrapper/eyes.py`, `scene.blend`, `tools/verify.py` and the release ZIP are unchanged; new code imports the wrapper read-only.

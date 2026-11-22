# Techtonic research platform (`research/`, branch `research/upgrade`)

This is post-deadline research work and is not part of the submitted Track 01 package. Nothing here changes the following:
- `wrapper/eyes.py`
- `scene.blend`
- the release ZIP
- `submission/final`
- tag `submission-baseline-v1.0`

Every script imports the bundle's wrapper unchanged and never saves the `.blend`.

## Rules the code follows

- **Ground truth comes from geometry; predictions come from pixels.** The `pupil_detector.py` module does not read metadata, and a test enforces this.
- **Clean renders and labels are never modified.** Degradations write new files, along with their seed, their parameters and SHA-256 hashes of the source, the label and the output.
- **Only one Blender render runs at a time,** through `gpuq.py`. It holds a lock and waits for any Blender job started outside the queue rather than interrupting it.
- **Every number in `AUDIT/results/` has a producing command** (listed below and in `dashboard.py`).

## Pupil-centre definitions (Workstream 1)

| Level | Symbol | Definition | Source |
|---|---|---|---|
| 1. Anatomical | **P** (world, m) | The centre of the pupil opening on the iris, rotated with the eyeball about its pivot | `state()["pupil_center_3D_*"]` |
| 1b. Projected anatomical | **p_u** (px) | π(K[R\|t]·P): the straight pinhole projection, with no cornea | `pupil_center_2D_unrefracted_*` |
| 2. Optically apparent | **p_a** (px) | The pixel whose camera ray, refracted by Snell's law at the analytic corneal sphere (centre, radius and index stored on the iris object), hits P | `pupil_center_2D_*` (primary GT) |
| 2b. Rendered apparent | **p_m** (px) | The centroid of the painted-pupil mask rendered through the actual `Lens` mesh, with lids hidden | `masks.py` → `pupil_unoccluded`, `masks_eval.py` |
| 3. Image-detected | **p_d** (px) | A circle fitted to the visible pupil edge in the photoreal RGB, taken from the image only | `pupil_detector.py` |

- **Pixel convention:** origin at the top-left corner of the image, x to the right, y down. The centre of pixel (i, j) is at (i + 0.5, j + 0.5).
- **Rotation convention:** world rotations are the shortest arc from the calibrated primary axis (Listing's law).

The differences between levels isolate one cause each:
- **p_a − p_u** is the effect of the analytic cornea (0.45–0.58 px on the release frames).
- **p_m − p_a** tests whether the analytic cornea matches the rendered Lens mesh.
- **p_d − p_m** is detector behaviour: edge criterion, shading and occlusion.

## Modules

| WS | File | Purpose | Test or evidence |
|---|---|---|---|
| 1 | `render_ablation.py`, `render_bias_probe.py`, `analyze_bias.py` | Ablation renders (full / no lids / no lids or lens) and bias attribution | `AUDIT/results/*_roi_*` |
| 2 | `degrade.py`, `degrade_eval.py` | Noise, motion blur, defocus, exposure, glints, JPEG, 2-D eyelid occluder, illumination; detector robustness; label invariance | `degrade.py selftest`, `ws2_degradation/` |
| 3 | `masks.py`, `masks_eval.py` | Pupil, iris, sclera, eyelid, lash and cornea masks; refracted and unrefracted pupil; landmarks, boundaries, IoU/Dice, validation | `ws3_masks/` |
| 4 | `dataset_v2_render.py`, `dataset_v2_post.py`, `configs/pilot_v2.json` | Config-driven sampling (gaze, profiles, iris, lighting, camera, occlusion, quality); IDs; resume; failures; coverage; integrity | `ws4_dataset/` |
| 5 | `dynamics.py`, `dynamics_validate.py` | Saccade, pursuit, vergence, drift and blink, compared with literature ranges | `dynamics.py --selftest`, `ws5_dynamics/` |
| 6 | `speed.py`, `bench_speed.py`, `bench_compare.py`, `gpuq.py` | Eye-band and persistent-data optimisation, benchmark and acceptance test; single-GPU queue | `ws6_performance/` |
| 7 | `dashboard.py` | HTML report built only from result files | `AUDIT/results/dashboard/index.html` |
| 8 | `model_comparison.py`, `comparison_render.py`, `comparison_eval.py` | Planar vs sphere vs anatomical: analytic comparison plus same-condition renders | `model_comparison.json`, `ws8_comparison/` |
| — | `tests/test_research.py` | Tests that need no Blender | `python3 research/tests/test_research.py` |

## Commands

`B` is the path to the Blender binary. `PKG` is a fresh unzip of `Techtonic.zip`.

```bash
python3 research/gpuq.py -- $B -b --factory-startup $PKG/scene.blend -P research/masks.py -- masks
python3 research/masks_eval.py masks $PKG AUDIT/results/ws3_masks --roi-from abl/full/frame_10.png
python3 research/degrade.py sweep $PKG deg --seed 7
python3 research/degrade_eval.py deg abl/full/frame_10.png AUDIT/results/ws2_degradation/robustness.json $PKG
python3 research/gpuq.py -- $B -b --factory-startup $PKG/scene.blend -P research/dataset_v2_render.py -- --config research/configs/pilot_v2.json --out DS
python3 research/dataset_v2_post.py DS
python3 research/dynamics_validate.py AUDIT/results/ws5_dynamics
python3 research/dashboard.py AUDIT/results AUDIT/results/dashboard/index.html
```

**Requirements:** Python 3 with numpy, scipy, Pillow and matplotlib, plus Blender 5.3.0.

## Limitations specific to these modules

- **The 2-D eyelid occluder in `degrade.py`** is a flat, skin-coloured band, used only as a detector stress test. Realistic occlusion comes from the lid rig (`dataset_v2_render.py`, `occlusion`).
- **Mask classes on the eyeball** follow the scan texture's UV layout (pupil r_uv 0.034, iris r_uv 0.112). The pupil class is therefore the painted geometric disc, not a dark-pixel threshold. "Eyelid" means skin within 20 px of the visible eyeball.
- **Camera variants in the v2 dataset** move the camera along its own axis and scale the focal length. K and [R|t] are recorded for each sample. These variants are not the official 40 cm camera.
- **The dynamics models are textbook first-order models.** The literature values quoted are representative ranges, not a fitted human dataset.
- **GPU utilisation is not measured.** It needs root access to `powermetrics` on macOS. The benchmark reports wall time, CPU time and peak RSS.

## Validation status (clean-extraction run, 2026-11-23)

The authoritative pipeline is `verify_all.sh`. It runs every stage below from a fresh unzip of the release ZIP, one GPU job at a time. It then runs `check_results.py` (completeness, staleness against `DETECTOR_FREEZE.txt`, submission integrity) and `build_report.py`, which writes `AUDIT/results/INTEGRATION_REPORT.md` from the result files only.

**Scripts kept in `research/` but NOT run in the validated pipeline. None of their outputs is cited.**
- `render_bias_probe.py` and `analyze_bias.py`: an alternative bias-attribution probe, superseded by `depth_probe_extended.py` and `depth_fit.py`.
- `make_evidence.py`: an early figure script, superseded by `dashboard.py`.
- `run_all.sh`: the first runner, superseded by `verify_all.sh`.

**Provisional and rejected:**
- WS3 segmentation metrics are provisional, because about 13% of pixels are unclassified (`ws3_masks/unclassified_audit.json`).
- The eye-band render option in `speed.py` failed its acceptance test (`ws6_performance/band_audit.json`) and is not used. Persistent data passed.

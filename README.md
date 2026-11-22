# VIT_Chennai_Techtonic — Synthetic Eye Movement & Virtual Camera Rendering

**Samsung PRISM XR Hackathon 2026 · Track 01 (XR Perception Group) · Team Techtonic, VIT Chennai**

This page is the navigation hub for the whole repository, on branch `research/upgrade`. The repository holds two separate things:

| | What it is | Where | Status |
|---|---|---|---|
| **Original submission (baseline)** | The Track 01 package: Blender scene, `wrapper/eyes.py`, 10 renders, `metadata.json`, deck and video | branch `submission/final`, tag [`submission-baseline-v1.0`](https://github.com/KArT4206/VIT_Chennai_Techtonic/tree/submission-baseline-v1.0), commit `3155655`, [Release v1.0](https://github.com/KArT4206/VIT_Chennai_Techtonic/releases/tag/v1.0) | **frozen**; the research work never modifies it |
| **Research upgrade** | Post-deadline validation: compliance suite, pupil-depth investigation, independent detector, datasets, eye-movement dynamics, render benchmarks | [`research/`](research/), [`AUDIT/results/`](AUDIT/results/) on branch `research/upgrade` | validated by a clean-extraction run; **not** part of the submitted package |
| **Experimental / provisional** | Semantic masks (WS3); eye-band (ROI) rendering | [`AUDIT/results/ws3_masks/`](AUDIT/results/ws3_masks/), [`AUDIT/results/ws6_performance/band_audit.json`](AUDIT/results/ws6_performance/band_audit.json) | masks **provisional**; ROI rendering **rejected** |
| **Superseded documentation** | Draft reports written before the clean run; validation of an earlier bundle | [`AUDIT/results/superseded_drafts/`](AUDIT/results/superseded_drafts/), [`validation/VALIDATION.md`](validation/VALIDATION.md) | do not cite |

The original submission README is preserved unchanged at the baseline tag: [README @ submission-baseline-v1.0](https://github.com/KArT4206/VIT_Chennai_Techtonic/blob/submission-baseline-v1.0/README.md).

---

## Quick navigation

| I want to… | Go to |
|---|---|
| Read the authoritative research report | [`AUDIT/results/INTEGRATION_REPORT.md`](AUDIT/results/INTEGRATION_REPORT.md) |
| See the research release note | [`AUDIT/results/RELEASE_NOTE.md`](AUDIT/results/RELEASE_NOTE.md) |
| Browse all research results by folder | the [index](AUDIT/results/README.md) or the [dashboard](AUDIT/results/dashboard/index.html) |
| Watch the final-round video (silent, 1:55) | [`research/demo/final_round_silent.mp4`](research/demo/final_round_silent.mp4) · [production report](research/demo/VIDEO_PRODUCTION_REPORT.md) |
| Open the final-round presentation | [`research/demo/final_round_presentation.pptx`](research/demo/final_round_presentation.pptx) · [PDF](research/demo/final_round_presentation.pdf) |
| Get the evaluator package | [Release v1.0 → `Techtonic.zip`](https://github.com/KArT4206/VIT_Chennai_Techtonic/releases/tag/v1.0) (145 MB, not stored in git) |
| See the original submission deck and video | [`submission/`](submission/) ([manifest](submission/SUBMISSION_MANIFEST.md)) |
| Use the gaze API | [`wrapper/eyes.py`](wrapper/eyes.py) · [API reference](#python-api-reference) |
| Re-run all research validation | [`research/verify_all.sh`](research/verify_all.sh) · [commands](#research-validation) |
| Read about AI assistance | [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) |

---

## Problem

Eye tracking for XR needs gaze images with exact ground truth: where each pupil is, how each eye is rotated and how the camera sees it. Real captures cannot give that ground truth precisely. A pupil that simply slides across a flat image does not look like a rotating eyeball. Track 01 asks for a textured, articulated face whose eyes rotate about their real centres under a calibrated camera, with machine-readable ground truth for every frame.

## System architecture

```
scene.blend (scanned head, eye.L / eye.R bones, corneal Lens meshes, locked camera, constant lights)
      │
wrapper/eyes.py ── move(h, v) → fixation target 35 cm ahead, displaced by (h, v)·5 cm
      │             each eyeball rotates about its own pivot (shortest arc, no torsion); lids follow
      ├── render(path) → 1024×1024 PNG (Cycles, GPU if available)
      └── state()      → inputs, rotations, 2-D/3-D pupil centres, K, [R|t]  → metadata.json
```

---

## Repository structure

| Folder / file | Contents | Belongs to |
|---|---|---|
| [`wrapper/eyes.py`](wrapper/eyes.py) | Gaze controller and renderer (public API); byte-identical to the one in `Techtonic.zip` | submission |
| [`scene.blend`](scene.blend), [`renders/`](renders/), [`metadata.json`](metadata.json), [`directions/`](directions/), [`contact_sheet.png`](contact_sheet.png) | **Early development baseline** (MakeHuman head, first commit `f31eb4e`), **not** the submitted scanned-head package. The submitted `scene.blend`, renders and `metadata.json` are only in Release v1.0 `Techtonic.zip` | development history |
| [`packaging/`](packaging/) | Evaluator README sources (`README_scan.md` is the one inside `Techtonic.zip`) | submission |
| [`submission/`](submission/) | Official deck (PPTX/PDF), detailed deck, video, manifest, evidence | submission |
| [`deck/`](deck/) | Deck build script and assets | submission |
| [`tools/`](tools/) | Scene build, original evaluator `verify.py`, mask check, early dataset and gaze-model tools | submission (`verify.py` unchanged) |
| [`demo/`](demo/) | Demo runners, scene views and the composition scripts for the submission video | submission |
| [`expression/`](expression/) | Prototype expression and eye-motion engine | development |
| [`experiments/`](experiments/), [`staging/`](staging/), [`exports/`](exports/) | Earlier qualification experiments (alternative heads, MakeHuman export) | development history |
| [`validation/`](validation/) | 17 Nov validation of an **earlier** bundle | superseded |
| [`research/`](research/) | Research-upgrade code: compliance, depth probe, detector, datasets, dynamics, benchmarks, report builders ([README](research/README.md)) | research upgrade |
| [`research/demo/`](research/demo/) | Final-round video, presentation and their reproducible sources | research upgrade |
| [`AUDIT/results/`](AUDIT/results/) | All research result files, reports and the dashboard ([index](AUDIT/results/README.md)) | research upgrade |
| [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) | AI-assistance disclosure | both |

---

## Installation and dependencies

- **Blender 5.3.0**, the only version tested. No add-ons are needed, because every texture is packed.
  - The macOS binary is `/Applications/Blender.app/Contents/MacOS/Blender`; elsewhere it is `blender`.
  - A GPU is optional (Metal, OptiX, CUDA, HIP or oneAPI), with CPU fallback.
- **Python 3** with `numpy`, `scipy`, `Pillow` and `matplotlib`, for the analysis scripts only. `tools/verify.py` needs only `numpy` and `Pillow`.
  - Results were measured with Python 3.14.7, numpy 2.5.4, scipy 1.18.1, Pillow 13.0.0 and matplotlib 3.11.2 ([`run_environment.txt`](AUDIT/results/run_environment.txt)).
- **ffmpeg / ffprobe**, only for rebuilding the final-round video.

## Running in Blender

Run these from the folder that contains `scene.blend`. Use an extracted `Techtonic.zip` for the submitted scanned head. The repository root works too, but its `scene.blend` is the early MakeHuman head.

```bash
blender -b scene.blend -P wrapper/eyes.py                              # 10 clockwise renders -> renders/, metadata.json
blender -b scene.blend -P wrapper/eyes.py -- --move -1 0 --out out     # one frame, pupils to image left
blender -b scene.blend -P wrapper/eyes.py -- --reset --out out         # one frame, centre gaze
blender -b scene.blend -P wrapper/eyes.py -- --samples 128             # faster, lower-quality preview
blender -b scene.blend -P wrapper/eyes.py -- --cpu                     # force CPU
```

## Python API reference

Use these inside Blender's Python with `scene.blend` open (`sys.path.append("<folder>/wrapper"); import eyes`):

| Call | Effect / return |
|---|---|
| `eyes.move(h, v)` | Points both eyes at the fixation target for normalised `h, v` ∈ [−1, 1]. Values are clamped; non-numbers, NaN and inf raise `ValueError`. The lids follow. Returns `state()` |
| `eyes.reset()` | Same as `move(0, 0)` |
| `eyes.render(path)` | Renders the current gaze to a PNG and returns `state()` |
| `eyes.state()` | Inputs, fixation target, per-eye rotation (Euler XYZ in degrees, plus quaternion), 2-D/3-D pupil centres |
| `eyes.render_sequence(out_dir)` | The 10-frame clockwise sequence + `metadata.json` |
| `eyes.camera_matrices()` | OpenCV K (3×3) and world→camera [R\|t] (3×4) |
| `eyes.use_best_device()` | Selects a GPU backend if available, else CPU |

## Gaze control and calibration

| Item | Value |
|---|---|
| Inputs | `h > 0` moves the pupils to the image's right, `v > 0` moves them up |
| Fixation target | 35 cm in front of the eye midpoint, displaced by (h, v) × 5 cm |
| Camera | locked 40 cm in front of the eye midpoint, facing the face; 1024 × 1024 PNG |
| Rotation | each eyeball about its own bone pivot, shortest arc from primary gaze (Listing's law, zero torsion); the eyes converge |
| Sequence | θk = 2πk/10, h = sin θk, v = cos θk, k = 0..9; starts at the top and runs clockwise on screen |
| World frame | Blender metres, +Z up, the face looks along −Y |

The measured values (camera distance, K, projection agreement, pivot stability, torsion) are in [`AUDIT/results/compliance.json`](AUDIT/results/compliance.json): **40/40 research compliance checks pass**.

## Metadata format

`metadata.json` has one record per frame. The released file is inside `Techtonic.zip`; the root `metadata.json` uses the same format but belongs to the early baseline.

| Field | Meaning |
|---|---|
| `frame`, `file`, `theta` | Frame index, image path, θk in radians |
| `input` | `{h, v}` |
| `fixation_target` | World position of the target the eyes look at |
| `eye_rotation_L/R` | Rotation from primary gaze, Euler XYZ in degrees |
| `eye_rotation_quat_L/R` | The same rotation as a quaternion (w, x, y, z) |
| `pupil_center_2D_L/R` | Pupil centre in pixels: origin top-left, x right, y down; includes analytic corneal refraction |
| `pupil_center_2D_unrefracted_L/R` | Straight projection of the anatomical pupil centre |
| `pupil_center_3D_L/R` | Anatomical pupil centre, world metres |
| `pupil_center_cornea_3D_L/R` | Where the ray to the seen pupil crosses the cornea |
| `camera_matrix` | OpenCV intrinsics K |
| `camera_extrinsic_world_to_cam` | OpenCV extrinsics [R\|t] |

The research upgrade adds a separate three-level annotation, [`AUDIT/results/research_pupil_levels.json`](AUDIT/results/research_pupil_levels.json), and never changes `metadata.json`:
- **A:** the anatomical pupil (the official ground truth);
- **B:** the pupil painted on the rendered asset;
- **C:** the independent detector's prediction.

## Dataset generation

| Generator | Command | Result |
|---|---|---|
| v1: 40 samples, iris and lighting variants, resumable | `blender -b --factory-startup scene.blend -P research/dataset_engine.py -- --config research/configs_dataset_40.json --out DS` | [`AUDIT/results/ws6_dataset_v1/`](AUDIT/results/ws6_dataset_v1/): 40/40 samples, 0 failures, 0 integrity problems |
| v2 pilot: static, saccade and pursuit samples, with camera, occlusion and quality variants | `blender -b --factory-startup scene.blend -P research/dataset_v2_render.py -- --config research/configs/pilot_v2.json --out DS2`, then `python3 research/dataset_v2_post.py DS2` | [`AUDIT/results/ws4_dataset/`](AUDIT/results/ws4_dataset/): 22/22 samples, integrity ok |
| Original, from the submission | `blender -b --factory-startup scene.blend -P tools/generate_dataset.py -- --out DIR` | not re-validated in the research run |

Generating a dataset successfully says nothing about detector accuracy. Detector results are reported separately below.

---

## Research validation

One command reproduces every research result from a clean extraction of the release ZIP. It takes about 70 minutes on an Apple M5 and runs one Blender job at a time through [`research/gpuq.py`](research/gpuq.py):

```bash
PYTHON=<python with numpy scipy pillow matplotlib> research/verify_all.sh <path/to/Techtonic.zip> <new_empty_work_dir>
```

Three further checks:

```bash
python3 research/check_results.py AUDIT/results AUDIT/results/results_check.json      # completeness and staleness
python3 research/integrity_check.py . AUDIT/results/integrity_check.json              # submission untouched
python3 research/tests/test_research.py                                              # 6 tests, no Blender
```

`Techtonic.zip` comes from Release v1.0; it is not tracked in git. Three scripts regenerate the reports from the result files: [`research/build_report.py`](research/build_report.py), [`research/build_release_note.py`](research/build_release_note.py) and [`research/dashboard.py`](research/dashboard.py).

### Pupil-depth investigation

The official 2-D ground truth uses the wrapper's anatomical pupil. It sits about 14.2–14.3 mm from the eye centre and is refracted through an analytic cornea. The scanned eyeball, however, paints its pupil further out on its surface, and its `Lens` material does not refract light.

A per-eye effective depth was fitted on 11 gaze poses. It predicts 14 held-out poses far better than the official ground truth does. The fit is in [`AUDIT/results/ws1_depth/depth_fit.json`](AUDIT/results/ws1_depth/depth_fit.json), and §4 of the [integration report](AUDIT/results/INTEGRATION_REPORT.md) explains it.

**These depths are effective fitted parameters of this asset as seen by this detector, not anatomical measurements.** The official `metadata.json` is unchanged.

### Detector evaluation

The pupil detector ([`research/pupil_detector.py`](research/pupil_detector.py)) works from the image only and is frozen ([`research/DETECTOR_FREEZE.txt`](research/DETECTOR_FREEZE.txt)). It is evaluated against the official ground truth in each condition, with per-pupil CSVs and overlays that include the failures:
- [`release_metrics.json`](AUDIT/results/release_metrics.json)
- [`full_roi_metrics.json`](AUDIT/results/full_roi_metrics.json)
- [`no_lids_lens_roi_metrics.json`](AUDIT/results/no_lids_lens_roi_metrics.json)
- [`ws6_dataset_v1/dataset_roi_metrics.json`](AUDIT/results/ws6_dataset_v1/dataset_roi_metrics.json)

The original evaluator [`tools/verify.py`](tools/verify.py), unmodified, reports **51 PASS / 20 FAIL** test records on the released bundle ([`verify_py_release_bundle.txt`](AUDIT/results/verify_py_release_bundle.txt)). Its FAILs come from its own pupil detector, which was tuned on an earlier head. This is a separate tool from the 40/40 research compliance suite.

### Dynamic eye movement experiments

[`research/dynamics.py`](research/dynamics.py) defines profiles for saccades, smooth pursuit, vergence, fixation drift and blinks. They are validated two ways:
- as models: [`ws5_dynamics/dynamics_validation.json`](AUDIT/results/ws5_dynamics/dynamics_validation.json);
- as rendered frames measured by the detector: [`ws5_dynamics/dynamics_render_check.json`](AUDIT/results/ws5_dynamics/dynamics_render_check.json).

They are simulations, not human-subject data, and blinks are not rendered.

### Performance benchmarks

Results are in [`ws6_performance/`](AUDIT/results/ws6_performance/):
- **Persistent data** (keeping scene data loaded between renders) passed the equivalence test.
- **Eye-band (ROI) rendering** failed it and is not adopted. Its timing is not claimed as a speed-up.
- Repeat renders on the same machine are compared in `benchmark_gpu_scene_samples.json` (GPU) and `benchmark_cpu_64spp.json` (CPU).

---

## Known limitations

- One face asset, one detector and one machine. No pixel-identical results across different hardware are claimed.
- The 2-D ground truth in `metadata.json` includes analytic corneal refraction, but the rendered `Lens` material does not refract. It also sits at the anatomical pupil depth, not the painted one (see the pupil-depth investigation).
- Semantic segmentation (WS3) is **provisional**: about 13.1 % of mask pixels are unclassified ([`unclassified_audit.json`](AUDIT/results/ws3_masks/unclassified_audit.json)).
- The eye-movement profiles are first-order models, and blinks are not rendered.
- Only Blender 5.3.0 has been tested.
- The full list is in [§10 of the integration report](AUDIT/results/INTEGRATION_REPORT.md) and in [`research/README.md`](research/README.md).

## Licence and asset attribution

- **Head scan:** 3D Scan Store "Free HD Head", used with the vendor's permission for this hackathon publication only. It may not be reused or redistributed outside this project.
- **MakeHuman comparison assets** (in `experiments/` and `exports/`): CC0 (makehumancommunity.org). MPFB 2.0.18 (GPL-3.0) was used as a tool only.
- **Code** in this repository: MIT.
- **AI assistance:** disclosed in [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).

## Final-round materials

- **Video:** [`research/demo/final_round_silent.mp4`](research/demo/final_round_silent.mp4), silent with an instrumental soundtrack, 1:55, 1920×1080. See also the [production report](research/demo/VIDEO_PRODUCTION_REPORT.md), [quality check](research/demo/final_quality_check.json) and [sources](research/demo/source/).
- **Presentation:** [`research/demo/final_round_presentation.pptx`](research/demo/final_round_presentation.pptx) · [PDF](research/demo/final_round_presentation.pdf).
- **Original submission video and decks** (unchanged): [`submission/`](submission/).

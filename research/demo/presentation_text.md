<!-- Slide number: 1 -->
![Both eyes of the rendered head, frame 0 of the shipped sequence](Image 0)
Synthetic gaze. Real geometry. Measured results.
Team Techtonic · VIT Chennai
Samsung PRISM XR Hackathon 2026 · Track 01 — XR Perception Group · final round
Research branch research/upgrade · baseline submission tag submission-baseline-v1.0 (unchanged)

### Notes:
Opening. The image is frame 0 of the shipped ten-frame sequence; nothing on this slide is generated imagery.

<!-- Slide number: 2 -->
Problem: gaze data needs trustworthy ground truth
![Research render of the shipped scene with gaze lines from both eyes to the fixation target](Image 0)
Eye articulation
1
each eyeball must rotate about its own centre
Calibrated camera
2
known intrinsics K and extrinsics [R|t]
Ground-truth annotation
3
2-D pupil centre per eye, per frame
Research render of the shipped scene; gaze lines to the fixation target
Synthetic data must be more than a pupil sliding across a flat image.
2

### Notes:
Eye tracking for XR is trained and tested on images whose pupil position must be known exactly. Real captures cannot give exact ground truth, and a flat sliding pupil is not how an eye looks.

<!-- Slide number: 3 -->
Solution: a rigged scanned face with a gaze API
![Side view of the real scene: camera, fixation target and eye centres](Image 0)
import eyes

eyes.move(h, v)  # h, v: -1..+1
eyes.reset()
eyes.render('frame.png')

# returns inputs, eye rotations,
# 2-D/3-D pupil centres, K, [R|t]
Side view of the real scene: camera (blue), fixation target (green), eye centres
Deliverable kept frozen: tag submission-baseline-v1.0 · research work lives only in research/ and AUDIT/results/
3

### Notes:
One Blender scene and one Python module. eyes.move takes normalised inputs; the eyes converge on a target 35 cm ahead; render writes the PNG and the ground truth.

<!-- Slide number: 4 -->
System architecture
SCHEMATIC — not a measured output
Blender scene
Eye rig
Gaze controller
Camera render
Ground truth
scene.blend
eye.L / eye.R bones
wrapper/eyes.py
Cycles, 1024×1024
metadata.json
Research layer (post-deadline)
compliance suite · depth probe · independent detector · datasets · dynamics · benchmarks · report builders
Reproducibility
research/verify_all.sh re-runs every result from a clean extraction of the release ZIP, one GPU job at a time
4

### Notes:
Schematic of the data flow. Each box is a real component in the repository.

<!-- Slide number: 5 -->
Anatomical eye articulation
![Five wrapper calls rendered: down, left, reset, right, up](Image 0)
0.000°
0 mm
9.70°
torsion about the gaze axis (Listing's law)
pivot drift over the 10 poses
vergence at the 35 cm target
Upper lid follows vertical gaze (gain 1.1), lower lid partly (0.35).
Source: AUDIT/results/compliance.json · renders: demo/final_hair/demo_assets
5

### Notes:
Real renders from the wrapper calls. Each eye rotates about its own bone pivot by the shortest arc, so there is no torsion and the eyes converge.

<!-- Slide number: 6 -->
Calibration and compliance
![The ten shipped frames, k = 0..9, clockwise from the top](Image 0)
40/40
research compliance checks passed (new deterministic suite: geometry, projection, pivots, inputs, reset)
35 cm
40 cm
Legacy tools/verify.py (unmodified): 51 PASS / 20 FAIL records
fixation distance
camera distance
1024 × 1024
10
Its FAILs come from its own pupil detector, tuned on an earlier head.
PNG output
clockwise gaze positions
Source: AUDIT/results/compliance.json · AUDIT/results/verify_py_release_bundle.txt · renders/frame_00..09.png
6

### Notes:
The ten clockwise frames, the calibrated distances, and the new 40-check research compliance suite. The legacy verifier is reported separately and unchanged.

<!-- Slide number: 7 -->
Discovery: official and painted pupils differ
![Frame 5, eye on the image right, zoomed: red official GT, green painted pupil, cyan detector](Image 0)
Depth of the pupil from the eye centre
ANATOMICAL (official GT)
PAINTED ON THE ASSET
L 14.19 mm
R 14.29 mm
L 16.28 mm
R 16.35 mm
Effective fitted depth (clean condition)
LEFT 16.10 mm · RIGHT 16.15 mm
95% bootstrap CI 16.05–16.15 · 16.10–16.20 mm
EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS
red official GT   green painted pupil   cyan detector
Source: research_pupil_levels.json · ws1_depth/depth_probe_extended.json · ws1_depth/depth_fit.json
7

### Notes:
Red is the official ground truth (anatomical pupil through an analytic cornea). Green is the pupil painted on the rendered eye, measured from mesh and texture with nothing fitted. Cyan is the independent detector.

<!-- Slide number: 8 -->
Independent held-out validation

### Chart: Held-out RMSE (px), 14 positions per eye

| Category | Fitted model | Mesh only, nothing fitted | Official ground truth |
| --- | --- | --- | --- |
| Left eye | 0.116 | 0.503 | 3.137 |
| Right eye | 0.136 | 0.533 | 3.152 |

14
held-out gaze positions per eye, never used for fitting
Clean condition (lids and lens mesh hidden). Full scene with lids: RMSE 0.421 / 0.749 px; right eye excludes 2 held-out poses where the detector failed.
Valid for this asset and this detector — not for other eyes or human subjects.
Source: AUDIT/results/ws1_depth/depth_fit.json (per-pose errors included)
8

### Notes:
The depth and a constant offset are fitted on 11 gaze poses per eye. 14 other gaze positions are only predicted. The fitted model predicts them far better than the official ground truth. Bootstrap: 2000 resamples of fit poses, seed 12345.

<!-- Slide number: 9 -->
Independent detector: condition by condition

### Chart: Detections within 5 px of ground truth

| Category | Within 5 px |
| --- | --- |
| Released frames | 90.0 |
| Full scene | 68.17999999999999 |
| Clean condition | 100.0 |
| 40-sample dataset | 75.0 |

![Actual detector overlays on the full scene; green ground truth, red detection, failed tiles labelled](Image 0)
Actual overlays, full scene: green = ground truth, red = detection, orange label = failed (> 5 px)
Detection percentages are condition-specific; missed detections are retained in reporting.
Source: release / full_roi / no_lids_lens_roi _metrics.json · ws6_dataset_v1/dataset_roi_metrics.json · full_roi_overlays.png
9

### Notes:
An image-only pupil detector, frozen after a half-pixel correction. Failures are kept in the overlays and in the statistics.

<!-- Slide number: 10 -->
Synthetic dataset generation
![Fifteen dataset v1 renders with random gaze, iris colour and lighting](Image 0)
40/40
22/22
dataset v1 samples (iris, lighting variants)
dataset v2 pilot: 12 static · 5 pursuit · 5 saccade
Variations: camera · eyelid occlusion · noise · JPEG · motion blur · defocus
![Four dataset v2 samples after image-quality degradation](Image 1)
0 generation failures · integrity checks passed
Generation success is not detector accuracy.
Semantic masks remain provisional: 13.1% of mask pixels unclassified.
Source: ws6_dataset_v1/manifest.json + integrity.txt · ws4_dataset/coverage.json + integrity.json · ws3_masks/unclassified_audit.json
10

### Notes:
Seeded, resumable generators with hashed manifests. Generation success is reported separately from detector accuracy.

<!-- Slide number: 11 -->
Dynamic eye movement (rendered and measured)
![Six frames of the rendered saccade with their timestamps](Image 0)
SACCADE (5–95 % duration)
image-left eye   33.9 ms
image-right eye  37.1 ms
commanded        36.7 ms
frame interval   4.17 ms
SMOOTH PURSUIT
![Vergence: first and last rendered frames as the target moves from 35 to 20 cm](Image 1)
lag ≈ 100 ms (resolution 33.3 ms) · gain ≈ 0.95 / 0.95
Vergence: both eyes move inward. Kept in the data: one 8.09 px detector glitch in the image-right saccade. Blink: not rendered.
Source: AUDIT/results/ws5_dynamics/dynamics_render_check.json · ws5_dynamics/dynamics_validation.json
11

### Notes:
Rendered frames measured by the detector. These are simulation measurements, not human-subject data. Blinks are modelled as a closure curve but not rendered.

<!-- Slide number: 12 -->
Rendering optimisation: verify before adopting

### Chart: 6-pose sequence at 128 spp (s)

| Category | 6-pose sequence (s) |
| --- | --- |
| Full render | 120.25 |
| Persistent data | 107.3 |

ROI (EYE-REGION) RENDERING —
NOT ADOPTED
difference up to 37/255 inside the region
difference up to 181/255 at its edges
fails the equivalence test
its faster timing is not claimed
PERSISTENT SCENE DATA — PASSED: 1.12× faster, pixels within 1/255
Source: AUDIT/results/ws6_performance/bench_compare.json · ws6_performance/band_audit.json
12

### Notes:
Every optimisation must reproduce the full render. Persistent scene data passes; eye-band (ROI) rendering fails and is not used.

<!-- Slide number: 13 -->
Limitations
Pupil depth
effective fitted parameters for this asset and detector, not anatomical measurements
Corneal refraction
official GT adds analytic refraction (0.45–0.58 px) that the rendered Lens material does not produce
Segmentation
provisional: 13.1% of mask pixels unclassified
ROI rendering
rejected after failing equivalence
Legacy verifier
unchanged; 51 PASS / 20 FAIL on the released bundle
Scope
one face asset, one detector, one machine; dynamics are simulations, blinks not rendered
Source: AUDIT/results/INTEGRATION_REPORT.md §10 · refraction range: research_pupil_levels.json (A apparent vs projected, from the released metadata)
13

### Notes:
Stated plainly so the results are read correctly.

<!-- Slide number: 14 -->
Future research and conclusion
Add a pupil-level ground-truth field that matches the painted pupil, alongside the anatomical one
Render masks with a true black background and resolve the remaining unclassified pixels
More face assets and detectors; cross-hardware repeatability
Fit eye-movement profiles to recorded human data; render blinks
From synthetic eye rendering to scientifically validated gaze generation.
Everything shown is reproducible from the release ZIP with research/verify_all.sh.
Team Techtonic · VIT Chennai
14

### Notes:
What would make the platform stronger, and the one-sentence takeaway.

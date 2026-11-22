# Submission manifest: Team Techtonic (VIT Chennai), Samsung PRISM XR Hackathon 2026, Track 1

Built 2026-11-19, updated 2026-11-22. Deadline: 20 Nov 2026 (Google Form, submitted by the registered primary member).

## Upload these three files

| File | Size | SHA-256 |
|---|---|---|
| `Techtonic.zip` | 145.3 MB | `acccb548c270bfab4719c3f173eda544a1b818fd858f56b1fe2d67a07790a0dc` |
| `VIT_Chennai_Techtonic.pptx` (official template, 9 slides; PDF copy alongside) | 1.5 MB | `9ef3f011dbd32018fa6d6dddfc70af4c7edfa9fc588cc0311b0f0d9e8aa3a1f2` |
| `VIT_Chennai_Techtonic.mp4` (2:05, 1920×1080, team voice-over) | 8.6 MB | `a7cf7e5bd2e6cd8a18d44096e902e8b9ec7f5f8a21f8d5f7bc7a5badcf54df55` |

Also here: `VIT_Chennai_Techtonic.pdf` (PDF copy of the deck), `VIT_Chennai_Techtonic_detailed_deck.pptx` (longer technical deck), `evidence/`.
Public repository: https://github.com/KArT4206/VIT_Chennai_Techtonic (release v1.0 holds `Techtonic.zip`).

## What Techtonic.zip contains

`scene.blend` (3D Scan Store Free HD Head, 4K textures packed, about 190,000 groomed hair strands),
`wrapper/eyes.py` (unchanged from the previous release), `renders/frame_00..09.png`, `metadata.json`,
`README.md`, at the ZIP root.

## Verification of this exact ZIP (fresh unzip, `demo/final_hair/run_demo.sh`)

| Check | Result |
|---|---|
| Fresh unzip, README command, `--factory-startup` | runs; 10 frames + metadata |
| Regenerated metadata vs packaged | byte-identical |
| Ground-truth pupil vs lighting-free mask (`tools/pupil_mask_check.py`) | 22 pupils, mean error 0.24 px, max 0.39 px |
| Direction shifts (ground truth) | 14.5–14.9 px per direction, 0.10 px reset offset |
| K[R\|t] reprojection | ≤ 0.0012 px |
| API tests | 19/19 |
| `tools/verify.py` | 60 pass / 22 fail: every failure is its darkness-based pupil detector on the dark brown scanned iris (see README); all layout, calibration, sequence and metadata-maths checks pass |
| Render time | about 74 s per frame on an Apple M5 GPU at 512 samples (12.3 min for 10 frames) |

## Extensions (beyond the brief; NOT inside Techtonic.zip, shown in the deck and video)

| Item | Result |
|---|---|
| `tools/generate_dataset.py`: one-command labelled dataset | 300 samples (150 scan head with hair, 150 MakeHuman): photoreal RGB, pixel-exact occlusion-correct pupil/iris/sclera masks, gaze vectors, rotations, 2D/3D pupils, camera K and [R\|t], randomised lighting |
| `tools/train_gaze_model.py`: gaze model trained on the synthetic RGB only | held-out mean error 0.297° (scan) and 0.158° (MakeHuman), vs 6.395° / 6.668° mean-guess baseline |
| Unseen head (train on one, test on the other) | 3.098° / 4.989°: identity variety matters |

Files: `extensions/dataset_scan/`, `extensions/dataset_makehuman/` (about 586 MB together, not for the form
upload), `extensions/gaze_model/`, `extensions/dataset_samples.png`. Caveat: fixed head pose and camera, so this
shows the labels are consistent and learnable, not a real-world benchmark.

## Fallbacks

- `dist/final_bald_fallback/`: the previous verified release (same scan head without hair, 83.0 MB zip,
  SHA `86abce8f…`), with its own deck, video and evidence.
- `dist/final_makehuman96/`: the MakeHuman head with the same 96 mm camera, 82/82 on `verify.py`.
- The original 60 mm `dist/Techtonic.zip` is untouched.

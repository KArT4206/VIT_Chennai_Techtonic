# Video production report: final-round silent video

**File:** `research/demo/final_round_silent.mp4`. SHA-256 `9af3912fd114a756fe084b1b9cf3688da6bb0a9a8cbb2404d782ceb2fe374361`. 14.2 MB.

| Property | Value |
|---|---|
| Duration | 115.0 s |
| Resolution | 1920×1080 (16:9) |
| Frame rate | 30/1 fps |
| Video | h264 yuv420p, CRF 17 |
| Audio | aac, 48000 Hz, 2 ch; mean -18.2 dB, max -3.6 dB |

## Audio

There is no voice, narration, speech, avatar or dialogue. The soundtrack is synthesised by `source/music.py` from sine, triangle, pulse and filtered-noise tones. It uses no samples and no vocal material. Its layers are:
- a chord pad;
- a low drone that rises during the discovery scene;
- a soft 96 bpm pulse during the dataset, dynamics and performance scenes;
- noise swells at scene boundaries;
- a resolving final chord.

All information is on screen, so the video works with the sound muted.

## Duration

The organisers' final-round duration rule was not available to this build. The video follows the brief's 1 min 55 s target. Change the scene durations in `source/build_video.py` if the rule differs.

## Evidence-to-scene map
| Scene | Time (s) | Evidence |
|---|---|---|
| 1 Hook | 0–7 | 10 shipped renders `pkg/renders/frame_00..09.png`; markers at `metadata.json → pupil_center_2D_*` |
| 2 The challenge | 7–17 | `demo/final_hair/demo_assets/scene/eyes_cutaway.png` (research render of the shipped scene); 3 concept cards (text) |
| 3 Our system | 17–31 | `demo_assets/scene/overview.png`, wrapper-call renders `demo_assets/00_reset..04_down.png`; flow diagram labelled SCHEMATIC |
| 4 Calibration and compliance | 31–43 | 10 shipped renders; `AUDIT/results/compliance.json`; `verify_py_release_bundle.txt` |
| 5 Pupil alignment discovery | 43–66 | frame 5 render; `research_pupil_levels.json` (A/B/C points); `ws1_depth/depth_probe_extended.json`; `ws1_depth/depth_fit.json` |
| 6 Detector validation | 66–78 | `AUDIT/results/full_roi_overlays.png`; release / full_roi / no_lids_lens_roi metrics; `ws6_dataset_v1/dataset_roi_metrics.json` |
| 7 Dataset generation | 78–91 | clean-run `dataset/images/` (v1), `ds2/degraded/*.png` + `.degrade.json`; `ws6_dataset_v1/manifest.json`, `ws4_dataset/coverage.json`, `integrity.json`; `ws3_masks/unclassified_audit.json` |
| 8 Dynamic eye movement | 91–102 | clean-run `dynamics/{saccade,pursuit,vergence,fixation}/*.png` + `dynamics.json`; `ws5_dynamics/dynamics_render_check.json` |
| 9 Performance engineering | 102–111 | `ws6_performance/bench_compare.json`, `ws6_performance/band_audit.json` |
| 10 Final message | 111–115 | `demo_assets/scene/overview.png` |

## Numbers shown

Every number shown is read from `AUDIT/results/` at build time. `build_video.py` stops if any value differs from the figure agreed for the video. There are 34 checks, and all of them pass. The values are in `asset_manifest.json → numbers_shown`.

The wording on screen follows the evidence:
- The fitted depths are labelled *EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS*, valid for this asset and this detector only.
- 40/40 is labelled as the new research compliance suite. The unmodified legacy `tools/verify.py` result (51 PASS / 20 FAIL) is shown next to it.
- The detector percentages are labelled as condition-specific, and failed detections appear in the overlays.
- Dataset generation is shown separately from detector accuracy.
- Segmentation is described as provisional (13.1% of pixels unclassified).
- ROI rendering is shown as NOT ADOPTED, failing at up to 37/255 inside the region and 181/255 at its edges. Its timing is not claimed.
- The 8.09 px saccade detector glitch is stated.
- Blinks are described as not rendered.
- The eye-movement values are measurements of the simulation, not of human subjects.

## Source files

162 files, each with its SHA-256, listed in `asset_manifest.json → sources`. Rendered imagery comes from the clean-extraction run (`SyntheticEyes-Track1-research-work/clean_run_2026-11-23/`, outside the repository) and from the repository's own `demo/final_hair/demo_assets/`. No new Blender rendering was done for the video.

## Reproduce
```bash
PYTHON=<python with numpy pillow> research/demo/source/make.sh <clean_run_work_dir>
python3 research/demo/source/quality_check.py
python3 research/demo/source/write_report.py
```
`make.sh` renders every frame with `build_video.py` and pipes them to `ffmpeg` (`libx264 -preset slow -crf 17 -pix_fmt yuv420p`). `music.py` writes the soundtrack. `ffmpeg` then muxes the two (`-c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart`).

## Quality check (`final_quality_check.json`)
| Check | Result |
|---|---|
| container_mp4_h264 | PASS |
| resolution_1920x1080 | PASS |
| aspect_16_9 | PASS |
| fps_30 | PASS |
| pix_fmt_yuv420p | PASS |
| duration_about_1m55s | PASS |
| audio_instrumental_only | PASS |
| no_voice_no_narration_no_avatar | PASS |
| all_numbers_match_result_files | PASS |
| original_submission_video_unchanged | PASS |
| original_submission_zip_unchanged | PASS |

Overall: **PASS**. I reviewed frames visually through contact sheets (`assets/review_sheet.png`). Fixes made during review:
- moved overlapping captions in scenes 2 and 5;
- hid the thumbnails behind the code panel;
- replaced glyphs that the font could not render;
- made the hook markers easier to read;
- replaced the overlap between the discovery scene's text phases with a short dip;
- added a soft limiter after the first soundtrack hard-clipped 120 samples.

## Limitations and missing assets

- No photograph of a real human eye was available or licensed, so the challenge scene uses the rendered eye.
- Blinks are not rendered, and are described as such.
- Text appears in English only.
- The scanned head is licensed for this hackathon publication only, so the video must not be reused outside it.
- The original submission video `submission/VIT_Chennai_Techtonic.mp4` and `Techtonic.zip` are unchanged, as checked by their hashes.
- Nothing was committed or pushed.

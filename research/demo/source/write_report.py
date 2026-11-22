"""Write research/demo/VIDEO_PRODUCTION_REPORT.md from the final QC, manifest and timeline files (pure Python)."""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); DEMO = os.path.dirname(HERE)
q = json.load(open(os.path.join(DEMO, "final_quality_check.json"))); m = json.load(open(os.path.join(DEMO, "asset_manifest.json")))
tl = list(csv.DictReader(open(os.path.join(DEMO, "scene_timeline.csv")))); v = q["ffprobe"]["video"]; a = q["ffprobe"]["audio"]
N = m["numbers_shown"]
EVID = {
 "1 Hook": "10 shipped renders `pkg/renders/frame_00..09.png`; markers at `metadata.json → pupil_center_2D_*`",
 "2 The challenge": "`demo/final_hair/demo_assets/scene/eyes_cutaway.png` (research render of the shipped scene); 3 concept cards (text)",
 "3 Our system": "`demo_assets/scene/overview.png`, wrapper-call renders `demo_assets/00_reset..04_down.png`; flow diagram labelled SCHEMATIC",
 "4 Calibration and compliance": "10 shipped renders; `AUDIT/results/compliance.json`; `verify_py_release_bundle.txt`",
 "5 Pupil alignment discovery": "frame 5 render; `research_pupil_levels.json` (A/B/C points); `ws1_depth/depth_probe_extended.json`; `ws1_depth/depth_fit.json`",
 "6 Detector validation": "`AUDIT/results/full_roi_overlays.png`; release / full_roi / no_lids_lens_roi metrics; `ws6_dataset_v1/dataset_roi_metrics.json`",
 "7 Dataset generation": "clean-run `dataset/images/` (v1), `ds2/degraded/*.png` + `.degrade.json`; `ws6_dataset_v1/manifest.json`, `ws4_dataset/coverage.json`, `integrity.json`; `ws3_masks/unclassified_audit.json`",
 "8 Dynamic eye movement": "clean-run `dynamics/{saccade,pursuit,vergence,fixation}/*.png` + `dynamics.json`; `ws5_dynamics/dynamics_render_check.json`",
 "9 Performance engineering": "`ws6_performance/bench_compare.json`, `ws6_performance/band_audit.json`",
 "10 Final message": "`demo_assets/scene/overview.png`",
}
L = []; A = L.append
A("# Video production report: final-round silent video\n")
A(f"**File:** `research/demo/final_round_silent.mp4`. SHA-256 `{q['video_sha256']}`. {q['ffprobe']['size_bytes'] / 1e6:.1f} MB.\n")
A("| Property | Value |\n|---|---|")
A(f"| Duration | {q['ffprobe']['duration_s']} s |")
A(f"| Resolution | {v['width']}×{v['height']} ({v.get('display_aspect_ratio', '16:9')}) |")
A(f"| Frame rate | {v['r_frame_rate']} fps |")
A(f"| Video | {v['codec_name']} {v['pix_fmt']}, CRF 17 |")
A(f"| Audio | {a[0]['codec_name'] if a else 'none'}, {a[0]['sample_rate'] if a else ''} Hz, {a[0]['channels'] if a else ''} ch; mean {q['audio_levels']['mean_volume']}, max {q['audio_levels']['max_volume']} |")
A("\n## Audio\n")
A("There is no voice, narration, speech, avatar or dialogue. The soundtrack is synthesised by `source/music.py` from sine, triangle, pulse and filtered-noise tones. It uses no samples and no vocal material. Its layers are:")
A("- a chord pad;")
A("- a low drone that rises during the discovery scene;")
A("- a soft 96 bpm pulse during the dataset, dynamics and performance scenes;")
A("- noise swells at scene boundaries;")
A("- a resolving final chord.\n")
A("All information is on screen, so the video works with the sound muted.\n")
A("## Duration\n")
A("The organisers' final-round duration rule was not available to this build. The video follows the brief's 1 min 55 s target. Change the scene durations in `source/build_video.py` if the rule differs.\n")
A("## Evidence-to-scene map\n| Scene | Time (s) | Evidence |\n|---|---|---|")
for r in tl:
    A(f"| {r['scene']} | {float(r['start_s']):.0f}–{float(r['end_s']):.0f} | {EVID.get(r['scene'], '')} |")
A("\n## Numbers shown\n")
A(f"Every number shown is read from `AUDIT/results/` at build time. `build_video.py` stops if any value differs from the figure agreed for the video. There are {len(m['checks'])} checks, and all of them pass. The values are in `asset_manifest.json → numbers_shown`.\n")
A("The wording on screen follows the evidence:")
A("- The fitted depths are labelled *EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS*, valid for this asset and this detector only.")
A(f"- 40/40 is labelled as the new research compliance suite. The unmodified legacy `tools/verify.py` result ({N['legacy_pass']} PASS / {N['legacy_fail']} FAIL) is shown next to it.")
A("- The detector percentages are labelled as condition-specific, and failed detections appear in the overlays.")
A("- Dataset generation is shown separately from detector accuracy.")
A(f"- Segmentation is described as provisional ({N['unc'][0]:.1%} of pixels unclassified).")
A(f"- ROI rendering is shown as NOT ADOPTED, failing at up to {N['roi_in']}/255 inside the region and {N['roi_edge']}/255 at its edges. Its timing is not claimed.")
A(f"- The {N['glitch']:.2f} px saccade detector glitch is stated.")
A("- Blinks are described as not rendered.")
A("- The eye-movement values are measurements of the simulation, not of human subjects.\n")
A("## Source files\n")
A(f"{len(m['sources'])} files, each with its SHA-256, listed in `asset_manifest.json → sources`. Rendered imagery comes from the clean-extraction run (`SyntheticEyes-Track1-research-work/clean_run_2026-11-23/`, outside the repository) and from the repository's own `demo/final_hair/demo_assets/`. No new Blender rendering was done for the video.\n")
A("## Reproduce\n```bash\nPYTHON=<python with numpy pillow> research/demo/source/make.sh <clean_run_work_dir>\npython3 research/demo/source/quality_check.py\npython3 research/demo/source/write_report.py\n```")
A("`make.sh` renders every frame with `build_video.py` and pipes them to `ffmpeg` (`libx264 -preset slow -crf 17 -pix_fmt yuv420p`). `music.py` writes the soundtrack. `ffmpeg` then muxes the two (`-c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart`).\n")
A("## Quality check (`final_quality_check.json`)\n| Check | Result |\n|---|---|")
for k, val in q["checks"].items():
    A(f"| {k} | {'PASS' if val else 'FAIL'} |")
A(f"\nOverall: **{'PASS' if q['all_pass'] else 'FAIL'}**. I reviewed frames visually through contact sheets (`assets/review_sheet.png`). Fixes made during review:")
A("- moved overlapping captions in scenes 2 and 5;")
A("- hid the thumbnails behind the code panel;")
A("- replaced glyphs that the font could not render;")
A("- made the hook markers easier to read;")
A("- replaced the overlap between the discovery scene's text phases with a short dip;")
A("- added a soft limiter after the first soundtrack hard-clipped 120 samples.\n")
A("## Limitations and missing assets\n")
A("- No photograph of a real human eye was available or licensed, so the challenge scene uses the rendered eye.")
A("- Blinks are not rendered, and are described as such.")
A("- Text appears in English only.")
A("- The scanned head is licensed for this hackathon publication only, so the video must not be reused outside it.")
A("- The original submission video `submission/VIT_Chennai_Techtonic.mp4` and `Techtonic.zip` are unchanged, as checked by their hashes.")
A("- Nothing was committed or pushed.")
open(os.path.join(DEMO, "VIDEO_PRODUCTION_REPORT.md"), "w").write("\n".join(L) + "\n"); print("report written")

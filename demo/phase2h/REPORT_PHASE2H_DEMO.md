# Phase 2H: Track 1 demo production

**Status:**
- **Automatic cut: rendered and inspected.** `output/Techtonic_Track1_demo_auto.mp4` is
  1920×1080, H.264 High, yuv420p, 30 fps, 3,150 frames, **exactly 1:45.000**, 7.2 MB,
  SHA-256 `b72fee7e…`.
- **It has no audio track.**
- **Still manual:** the voice-over and any optional live screen-recording inserts. I can't record the
  desktop or a voice, and the final narrated video has not been made.

## 1. Release protection (checked before and after)

| Item | Value |
|---|---|
| Release branch | `release/makehuman-submission` at `5b34f5e` (source `0c05142`). The development checkout stays on `phase2/scan-head-finalization` (`ae742ad`) |
| ZIP | `dist/Techtonic.zip`, SHA-256 `91f4bafe10200a9e1d4a0176060de4ef86d50b92becf279e70c25c0e245773a4`. Checked by the runner before use and again after |
| Production files | `scene.blend`, `wrapper/eyes.py`, `metadata.json` and `renders/` are unchanged (same checksums as the Phase 2F baseline) |
| Where the demo ran | A fresh extraction in `demo/phase2h/work/`. All 14 extracted package files have the same SHA-256 before and after |
| Scan content | None. Nothing from the 3D Scan Store head is used anywhere in the demo |
| Publishing | Nothing pushed or published |

**One problem was found and fixed on the way:**
- **What happened:** the first run reported "package files changed".
- **Cause:** importing the wrapper had added `wrapper/__pycache__/eyes.cpython-313.pyc` to the
  extracted copy. No packaged file was modified.
- **Fix:** the runner now sets `sys.dont_write_bytecode`, and the before/after check passes.

## 2. Storyboard and duration (target 1:45 = 105 s)

| Scene | Time | Content | Source |
|---|---|---|---|
| 1 | 0:00–0:10 | Problem and objective | Text |
| 2 | 0:10–0:25 | The actual scene from a side observer camera: head, `EyeCam` at 40.05 cm, `FixationTarget` at 35.05 cm, eye centres. Then the eyes with skin hidden: eye-bone axes and centres. Values in the side panel are read from the scene | `demo_scene.py` renders + `scene_facts.json` |
| 3 | 0:25–0:55 | Six real calls: `eyes.reset()`, `move(-1,0)`, `move(1,0)`, `move(0,1)`, `move(0,-1)`, `reset()`. Each shows its `eyes.render()` output (eye region enlarged 3×), the returned pupil centres and the shift from reset | Wrapper output |
| 4 | 0:55–1:15 | The 10 packaged clockwise frames with a clock diagram: frame k, θ, h = sin θ, v = cos θ | Packaged `renders/` + `metadata.json` |
| 5 | 1:15–1:30 | Frame 3 record: frame, theta, h/v, `eye_rotation_L/R`, `pupil_center_2D_L/R`, `camera_matrix` (rounded for display) | Packaged `metadata.json` |
| 6 | 1:30–1:45 | Validation numbers parsed from this run's `validation_results.txt`, then the conclusion | `validation_results.txt` |

The shot-by-shot list is in `SHOT_LIST.md`; the timed voice-over (about 245 words) is in
`NARRATION.md`.

**Measured shifts from reset**, read from the call log:

| Call | Pupil movement |
|---|---|
| `move(-1,0)` | L −8.59 px, R −8.81 px (image-left) |
| `move(1,0)` | L +8.81 px, R +8.59 px |
| `move(0,1)` | y −8.71 px (up) |
| `move(0,-1)` | y +8.71 px (down) |
| Second `reset()` | Identical to the first: 636.57 / 387.43, 512.41 |

## 3. Kit contents (`demo/phase2h/`)

| File | Purpose |
|---|---|
| `run_demo.sh` | Deterministic runner. Checks the ZIP hash, extracts fresh copies, runs the real wrapper calls and the scene views, the five direction renders, the sequence regeneration, `verify.py` and the API test. Writes `validation_results.txt` and `demo_assets/` |
| `tools/demo_scene.py` | Blender side of the runner. Imports the packaged `wrapper/eyes.py` unmodified |
| `tools/compose_video.py`, `tools/render_text.py` | Build the 1920×1080 cards from real outputs and encode the MP4. Text is drawn with Blender text objects, because Blender's OIIO has no FreeType and this ffmpeg has no `drawtext` |
| `tools/verify.py` | Byte-identical copy of the evaluator (SHA-256 `b0a12705…`) |
| `tools/phase2g_api_test.py` | The Phase 2G API test |
| `SHOT_LIST.md`, `NARRATION.md`, `RECORDING_INSTRUCTIONS.md`, `RUN_DEMO.md` | Production documents |
| `validation_results.txt` | This run's results, verbatim |
| `demo_assets/` | Wrapper-call PNG and JSON files, `call_log.txt`, scene views, the packaged sequence and metadata |
| `output/Techtonic_Track1_demo_auto.mp4` | The automatic cut |
| `work/` | Scratch space: extractions, logs, cards, clips. Recreated on every run |

## 4. Exact commands

```bash
cd ~/Desktop/Projects/SyntheticEyes-Track1
python3 -m venv /tmp/demo-venv && /tmp/demo-venv/bin/pip install numpy pillow
PYTHON=/tmp/demo-venv/bin/python demo/phase2h/run_demo.sh
/Applications/Blender.app/Contents/Resources/5.3/python/bin/python3.13 demo/phase2h/tools/compose_video.py demo/phase2h
```

- **Runtime:** about 15 minutes for the runner on the M5 (Metal; each 512-sample wrapper render
  takes about 33 s), and about 1 minute for the composer.
- **This session's run:** `verify.py` used Blender's Python with a local Pillow shim rather than the
  venv.

## 5. Validation evidence (this run, `validation_results.txt`)

| Check | Result |
|---|---|
| Original evaluator `verify.py` | **82 PASS, 0 FAIL** ("ALL CHECKS PASSED"), using direction renders the extracted package made itself |
| API test | **19/19 PASSED** |
| Ten clockwise renders | `frame_00`–`frame_09`, each a 1024×1024 PNG |
| Metadata | Regenerated `metadata.json` is **byte-identical** to the packaged file |
| Package integrity | All 14 extracted files unchanged after the run |

## 6. Inspection of the MP4

I extracted frames from the encoded MP4 and inspected one per scene at full size: title, overview,
cutaway, a wrapper call, a sequence frame, metadata and validation.

**Issues found and fixed:**
1. Without FreeType, the first encode had no text at all; text is now drawn with Blender.
2. Overview: the first framing cut off the head.
3. The eye-centre markers were hidden inside the eyeballs. The right sclera is now hidden in the
   cutaway, and the left centre's label says "inside the eyeball".
4. Labels overlapped the hair. They now sit in the empty band with leader lines, and a colour legend
   was added.
5. Rounding was inconsistent (40.1 vs 40.05 cm); both now show 40.05 cm.
6. The metadata card said "verbatim" although the values are rounded; it now says "rounded for
   display".

**Known limits of the automatic cut:**
- **The pink eye-bone axis doesn't run through the pupil.** That is the MPFB bone's real orientation
  (the wrapper rotates about the bone head, the eye centre). It is labelled "eye-bone axis".
- **The fixation target and camera are 35.05 and 40.05 cm away.** These are the measured
  midpoint-to-object distances, about 0.5 mm over the nominal values, and they are shown as measured.

## 7. What still needs you

1. **Voice-over.** Record `NARRATION.md` over the automatic cut (QuickTime or OBS; see
   `RECORDING_INSTRUCTIONS.md`).
2. **Optional live inserts.** Blender UI with the extracted `scene.blend` (Outliner: `eye.L`/`eye.R`,
   `FixationTarget`, `EyeCam`), plus a terminal or Python console making the calls.
3. **Final export** to the expected path `demo/phase2h/final/Techtonic_Track1_demo.mp4`, at
   1920×1080, 30 fps, H.264 with AAC, total 1:45.

**Not done in this phase, as instructed:** GitHub publishing, presentation, and ZIP changes.

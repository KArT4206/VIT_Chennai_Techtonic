# Shot list: 1:45 at 1920×1080, 30 fps

**Two cuts are prepared:**
- **A. Automatic cut.** `work/demo_track1.mp4`, built by `tools/compose_video.py` from the runner's
  real outputs. These are the cards below.
- **B. Recorded cut (optional).** Replace or overlay shots marked **[LIVE]** with your own screen
  recording, made by following `RECORDING_INSTRUCTIONS.md`.

| # | Time | Duration | Shot | Source (all real outputs) |
|---|---|---|---|---|
| 1 | 0:00–0:10 | 10 s | Title, problem, objective | Text card |
| 2a | 0:10–0:18 | 8 s | Side view of the actual scene. Markers sit at the scene's eye centres, the `FixationTarget` empty (35 cm) and the `EyeCam` camera (40 cm). The side panel lists the measured distances | `demo_assets/scene/overview.png`, `scene_facts.json`, `annotations.json` |
| 2b | 0:18–0:25 | 7 s | Eyes with skin and hair hidden. Shows the eye-bone axes (pink), eye centres (yellow) and lines to the target (green); the right sclera is hidden to reveal its centre | `demo_assets/scene/eyes_cutaway.png` |
| **[LIVE] 2** | (optional) | — | Blender UI with `scene.blend` open: Outliner showing `Human.rig` with bones `eye.L`/`eye.R`, `FixationTarget` and `EyeCam`; camera view (Numpad 0) | Your screen recording |
| 3a–3f | 0:25–0:55 | 6 × 5 s | `eyes.reset()`, `move(-1,0)`, `move(1,0)`, `move(0,1)`, `move(0,-1)`, `reset()`. Eye region enlarged 3×. The returned pupil centre (yellow) is compared with the centre gaze (grey); returned values are printed below | `demo_assets/0N_*.png` + `.json` (wrapper output) |
| **[LIVE] 3** | (optional) | — | Terminal running `demo/phase2h/run_demo.sh`, or the Blender Python console making the same calls | Your screen recording |
| 4 | 0:55–1:15 | 10 × 2 s | `frame_00`…`frame_09`. Full frame plus an enlarged eye strip; a clock diagram marks frame k, starting at the top and going clockwise; θ, h, v from the metadata | `demo_assets/sequence/` (packaged renders), `metadata.json` |
| 5 | 1:15–1:30 | 15 s | Frame 3 record from `metadata.json`: `frame`, `theta`, `input` h/v, `eye_rotation_L/R`, `pupil_center_2D_L/R`, `camera_matrix` | `demo_assets/metadata.json` (the packaged file) |
| 6 | 1:30–1:45 | 15 s | Validation numbers parsed from `validation_results.txt`, then the conclusion | `validation_results.txt` |

**Style:**
- Dark neutral background, Helvetica Neue for text and Menlo for code and values.
- 0.25 s fades only (0.12 s on the 2-second sequence cards).
- No animation of the data.

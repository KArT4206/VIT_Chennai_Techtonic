# Track 1 validation: `dist/Techtonic.zip`

Date: 2026-11-17.
- **Bundle checked:** `dist/Techtonic.zip`, SHA-256 `91f4bafe10200a9e…`, unchanged by these checks.
- **Machine:** Apple M5, Blender 5.3.0.

## 1. Fresh-unzip run (as an evaluator would do it)

**Steps:**
1. Unzip into an empty folder.
2. Delete the shipped `renders/` and `metadata.json`.
3. Run the README command exactly: `blender -b --factory-startup scene.blend -P wrapper/eyes.py`.

| Result | Value |
|---|---|
| Exit code | **0** |
| Output | 10 PNGs (`frame_00`–`frame_09`) + `metadata.json` |
| Device | Metal GPU, picked automatically |
| Wall time | 13.6 min (about 3½ min of loading, then about 40–70 s per frame) |

The log is `fresh_run_2026-11-17.log`.

## 2. Independent check (`tools/verify.py`, unchanged)

`verify.py` never imports the wrapper: it finds the pupils in the rendered pixels.

**Result: 71 PASS / 0 FAIL.**

| Check | Result |
|---|---|
| Layout | `scene.blend`, `wrapper/eyes.py`, `renders/`, `metadata.json`, `README.md` |
| Camera distance from the eye midpoint | 0.40 m |
| Fixation distance | 0.35 m |
| Sequence | θk = 2πk/10, h = sin θ, v = cos θ, starts at the top and runs clockwise on screen |
| Image format | every frame a 1024×1024 PNG |
| Camera matrix K[R\|t] reprojects the detected pupil | ≤ 0.001 px |
| Rendered pupil vs `pupil_center_2D` in the metadata | **0.16–1.18 px** (20 pupils) |
| Every frame moves the pupils in the commanded direction | min cosine 0.990 (L), 0.991 (R) |

## 3. The 5-direction check (40 points)

**Commands:** `eyes.reset()`, `move(-1,0)`, `move(1,0)`, `move(0,1)`, `move(0,-1)`, rendered through the shipped wrapper. Pupils were detected in the pixels by `verify.check_directions`.

| Direction | Left pupil moves | Right pupil moves | Result |
|---|---|---|---|
| Left | 8.1 px (1.0 sideways) | 8.9 px (0.5) | PASS |
| Right | 8.6 px (0.9) | 8.0 px (0.7) | PASS |
| Up | 8.0 px (0.5) | 7.8 px (0.3) | PASS |
| Down | 9.8 px (0.4) | 9.6 px (0.6) | PASS |
| Reset | centred within 0.61 px | 0.67 px | PASS |

**5 / 5 pass.**

**Convention:** "left" means pupils toward the **image's** left. This is stated in the README and in `metadata.json` → `conventions.inputs`.

**Visible proof:** `five_directions_zoom3x.png` shows the eye region at 3× zoom, with the reset pupil in red and the moved pupil in green. The lids also follow vertical gaze.

**Why the shift is about 9 px:** the brief limits fixation motion to ±5 cm at 35 cm, which is about ±8° of eye rotation. That moves the pupil about 1.7 mm, which is about 9 px at 40 cm on a 1024 px frame. Every compliant entry has the same small shift; the zoomed sheet is how we make it obvious.

## 4. Reproducibility

Fresh run against the files shipped in the zip:
- **`metadata.json`: bit-identical**, with 642 numeric values and 0 differences.
- **Frames:** identical to within 1/255 on isolated pixels (mean absolute difference 0.000), from GPU sampling noise.

## 5. Known limitations (honest list)

| Limitation | Impact | Mitigation |
|---|---|---|
| Only tested on Blender 5.3.0, and the file is saved in the 5.x format | An evaluator on Blender 4.x may not open it | Stated in README "Requirements". **Not tested on other versions** (would need a download) |
| Runtime: about 6–14 min on an Apple GPU. CPU-only (`--cpu`, default 512 samples): one frame took 3 min 33 s including scene loading on the M5 CPU, so the 10-frame run is likely tens of minutes on a laptop CPU | Slow for an evaluator without a GPU, but it completes | README documents `--samples 128` and per-direction single-frame commands |
| README timing (about 35 s/frame, about 6 min total) is lower than today's 13.6 min | Minor credibility | Today's run shared the machine with other jobs. In a single session, the 5 direction frames took 38–47 s each |
| Pupil shift is about 9 px | Hard to see on full frames | Inherent to the brief's ±5 cm bound; zoomed sheet for the demo and deck |
| One identity, one lighting setup, one camera | Limited variety as a gaze dataset | Exactly what the brief asks for; list variety as future work |
| Contact sheet not in the zip | Brief deliverable "contact sheet **or** demo video" | Delivered as the demo video (and the deck), so the zip layout stays exactly as specified |

## How to reproduce these checks

`verify.py` needs numpy and Pillow. Pillow isn't installed on this Mac, so the checks were run inside Blender's own Python, with a tiny PNG loader standing in for Pillow. The checker logic was unchanged.

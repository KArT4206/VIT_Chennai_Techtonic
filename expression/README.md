# Natural eye expressions (SyntheticEyes slides deliverable)

This is separate from the evaluator wrapper. `wrapper/eyes.py` and `scene.blend` are not changed.
Every eye rotation goes through `eyes.py`'s own calibrated maths: the shortest-arc rotation of
each eyeball about its own centre, the same primary axes and the same lid gains.

## Run

From the repository root (Blender 5.3.0):

```bash
blender -b scene.blend -P expression/run.py -- --input left     --out OUT
blender -b scene.blend -P expression/run.py -- --input right    --out OUT
blender -b scene.blend -P expression/run.py -- --input generate --out OUT
blender -b scene.blend -P expression/run.py -- --build-scene OUT/expression_scene.blend
blender -b OUT/expression_scene.blend -P expression/check.py -- OUT
```

- **`--input`** renders `OUT/<input>_frames/`, writes `OUT/<input>_motion.json` (per-frame
  channels) and encodes `OUT/<input>.mp4` (H.264, 24 fps, 1024×1024).
  - Add `--samples 128` for the video quality used here. The default is the scene's 512.
  - `--frames N` renders only the first N frames, for quick tests.
- **`--build-scene`** saves a new `.blend` file. It never saves over `scene.blend`. The file has three
  Actions:

  | Action | Contents |
  |---|---|
  | `Competition_Natural_Eye_Expression` | Active; 288 frames |
  | `Competition_Look_Left` | 120 frames |
  | `Competition_Look_Right` | 120 frames |

  Open the file and press Space to play the Timeline. To view the other two, pick them in the
  Action Editor.

**Left and right** are the **subject's** left and right. The subject's left is the image's right
(world +X), the same as `eyes.move(h > 0)`.

The expression actions are deliberately not in `scene.blend`. An action on the rig would
override `eyes.move()` whenever Blender evaluates a frame, and that would break the evaluator API.

## Files

| File | Role |
|---|---|
| `motion.py` | Pure-Python, seeded motion model: saccades, pursuit, fixational drift, blinks, brows |
| `engine.py` | Poses the rig from samples and keys Actions |
| `run.py` | Command line: renders each input, encodes the video, builds the Timeline scene |
| `check.py` | Acceptance checks |

## Controls (verified by rendering)

| Control | Effect |
|---|---|
| `eye.L/R` bones | Eyeball rotation about the eye centre |
| `orbicularis03.L/R` | Upper lid. Rotates about the eye centre; a world-X rotation of +27° closes it at every tested gaze. At 20° a slit remains in down-gaze; above 40° the lashes cross the lower lid. |
| `orbicularis04.L/R` | Lower lid; −2.5° when closed |
| `oculi01.L/R` | Brow. A world-Z offset moves the eyebrow mesh and the brow skin together. |

The 18 shape keys are identity and body morphs from MakeHuman (ethnicity, head shape, cheeks,
nose, lip). None of them are expressions, so lids and brows are driven by bones.

## Motion model

- **Saccades.** Duration follows the main sequence (D = 2.2·A + 21 ms). The profile is skewed
  minimum-jerk, and a 4 % glissade settles within 40 ms. Peak speeds are 300–580°/s.
- **Fixation.** About 0.1° of seeded drift, so the eyes never freeze.
- **Smooth pursuit.** Used for the eye roll in `generate`: a Catmull-Rom path, eased in and out.
- **Blink.** About 75 ms to close, 30 ms closed and 170 ms to open. Complete, partial and
  gaze-evoked blinks are all used. During a blink the eyes dip 2° (Bell's phenomenon).
- **Lids.** Inside ±8° the lids are identical to `eyes.py`: the upper lid follows 110 % of vertical
  gaze, the lower lid 35 %. Below −8° the upper lid's gain drops to 0.55, because at 1.1 the lid
  closed the eye in down-gaze.
- **Brows.** They rise 0.11 mm per degree of upward gaze, and further in brow flashes (up to
  2.2 mm). They dip 0.6 mm in a full blink, and the right brow moves 14 % less than the left.
- **Neutral fixation.** The camera, 40 cm away, so the subject makes eye contact.

## Gaze limits and why

The MakeHuman lids have no corrective shapes, so a rotated cornea starts to meet lid skin. Even
`eyes.py`'s own validated ±8° poses touch the lids by up to 0.45 mm. The limits below keep every
frame within that:

| Direction | Limit |
|---|---|
| Sideways | ±19° |
| Up | +15° |
| Down | −8° |

`check.py` measures this on every frame. Going beyond these limits needs corrective lid shapes,
which is listed as a later improvement.

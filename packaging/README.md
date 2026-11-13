# Synthetic Eye Movement & Virtual Camera Rendering (Track 1)

A textured, rigged human face in Blender. A Python wrapper rotates both eyeballs about their
true centres and renders calibrated 1024×1024 frames with per-frame ground truth.

## Package contents

```
scene.blend        textured mesh, eye bones, materials (all textures packed inside)
wrapper/eyes.py    eyes.move(h, v) / eyes.reset() / eyes.render(path)
renders/           frame_00.png … frame_09.png, the 10 clockwise frames
metadata.json      per-frame inputs, eye rotations, 2D/3D pupil centres, camera matrices
README.md          this file
```

Nothing else is needed. No add-ons and no external texture files are required.

## Requirements

- **Blender 5.3.0.** This is the version the scene was built with and the only version tested.
  The file uses curve-based hair and Blender 5.x shading, so older versions are not supported.
- macOS binary: `/Applications/Blender.app/Contents/MacOS/Blender`. On other systems use `blender`.
- A GPU is optional. The command-line run picks Metal, OptiX, CUDA, HIP or oneAPI when one is
  available, and falls back to the CPU otherwise.

All commands below are run from the folder this ZIP was extracted into, the folder that
contains `scene.blend`.

## Regenerate the 10 clockwise renders

```bash
blender -b scene.blend -P wrapper/eyes.py
```

This **overwrites** `renders/frame_00.png … frame_09.png` and `metadata.json` in this folder.
To write elsewhere and keep the shipped files, add `-- --out <folder>`:

```bash
blender -b scene.blend -P wrapper/eyes.py -- --out my_run
```

That creates `my_run/renders/` and `my_run/metadata.json`.

Other options:

```bash
blender -b scene.blend -P wrapper/eyes.py -- --move -1 0 --out checks   # one frame: pupils to image left
blender -b scene.blend -P wrapper/eyes.py -- --reset --out checks       # one frame: centre gaze
blender -b scene.blend -P wrapper/eyes.py -- --samples 128 --out quick  # faster, lower quality
blender -b scene.blend -P wrapper/eyes.py -- --cpu --out cpu_run        # force CPU
```

`--move` and `--reset` write `<name>.png` plus a `<name>.json` with the gaze state, for example
`checks/move_h-1.00_v+0.00.png` and `checks/reset.png`.

The 5-direction check (left, right, up, down, reset) is these five commands:

```bash
blender -b scene.blend -P wrapper/eyes.py -- --move -1 0 --out checks   # left
blender -b scene.blend -P wrapper/eyes.py -- --move 1 0 --out checks    # right
blender -b scene.blend -P wrapper/eyes.py -- --move 0 1 --out checks    # up
blender -b scene.blend -P wrapper/eyes.py -- --move 0 -1 --out checks   # down
blender -b scene.blend -P wrapper/eyes.py -- --reset --out checks       # reset
```

Measured on an Apple M5 (10-core GPU, Metal) at the shipped 512 samples: about 35 s per frame,
or about 6 minutes for the 10-frame sequence.

## Python API

Open `scene.blend` in Blender, then in the Python console or Text Editor:

```python
import sys
sys.path.append(bpy.path.abspath("//wrapper"))   # "//" is the folder containing scene.blend
import eyes

eyes.use_best_device()        # optional: render on the GPU (the command line does this itself)
eyes.move(0.5, -0.3)          # h, v in [-1, 1]; returns the gaze state as a dict
eyes.render("/tmp/frame.png") # renders the current gaze to a PNG; returns the gaze state
eyes.reset()                  # back to the centre fixation point
```

The same calls work headless:

```bash
blender -b scene.blend --python-expr "import bpy, sys; sys.path.append(bpy.path.abspath('//wrapper')); import eyes; eyes.use_best_device(); eyes.move(1, 0); eyes.render('api_test/right.png')"
```

| Function | Behaviour |
|---|---|
| `move(h, v)` | Points both eyes at the fixation target for (h, v). Inputs are clamped to [-1, 1]; non-numbers raise `ValueError`. The eyelids follow vertical gaze. |
| `reset()` | Same as `move(0, 0)`. |
| `render(path)` | Renders the current pose to a PNG at `path` and returns the gaze state. |
| `state()` | Current inputs, rotations and 2D/3D pupil centres, without rendering. |
| `render_sequence(out_dir)` | The 10-frame sequence into `<out_dir>/renders` plus `<out_dir>/metadata.json`. |

## Conventions and calibration

| Item | Value |
|---|---|
| Inputs | `h`, `v` normalised to [-1, +1] and clamped |
| Direction | `h > 0` moves the pupils to the **image's right**, `v > 0` moves them **up** |
| Fixation target | On the plane 35 cm in front of the eye midpoint, displaced by (h, v) × 5 cm |
| Camera | Locked 40 cm in front of the eye midpoint, facing the face, perspective, 1024×1024 PNG |
| Lighting | Constant studio lighting (key, fill, rim, eye light, neutral world), the same in every frame |
| Sequence | θₖ = 2πk/10, h = sin θₖ, v = cos θₖ, k = 0..9: starts at the top, clockwise on screen |
| World frame | Blender world, metres, +Z up, face looks along −Y, subject's left eye at +X |
| Eye midpoint | (0, −0.126892, 1.620518) m; interpupillary distance 58.8 mm |

Each eyeball rotates about its own centre to look at the target, so the eyes converge (about 4.8°
inwards each at the centre target). The rotation is the shortest arc from the eye's primary gaze
direction (Listing's law), so the eyes never twist about the gaze axis. The upper lid follows 110 %
of the eye's vertical rotation and the lower lid 35 %.

## `metadata.json`

Top level: `conventions`, `fixation_distance_m` (0.35), `motion_bound_m` (0.05),
`camera_distance_m` (0.40), `eye_midpoint`, and `frames`, with one record per frame:

| Field | Meaning |
|---|---|
| `frame`, `file`, `theta` | Index k, image path relative to this folder, θₖ in radians |
| `input` | `{h, v}` |
| `fixation_target` | World position of the point both eyes look at |
| `eye_rotation_L/R` | World-frame rotation from the eye's **rest-pose gaze axis**, Euler XYZ in degrees |
| `eye_rotation_quat_L/R` | The same rotation as a quaternion (w, x, y, z) |
| `pupil_center_2D_L/R` | Pupil centre as seen in the image: pixels, origin top-left, x right, y down |
| `pupil_center_3D_L/R` | Anatomical pupil centre in world metres |
| `pupil_center_cornea_3D_L/R` | Where the ray to the seen pupil crosses the cornea; projects exactly to the 2D point |
| `pupil_center_2D_unrefracted_L/R` | Straight projection of the anatomical centre, ignoring corneal refraction |
| `camera_matrix` | OpenCV intrinsics K (3×3) |
| `camera_extrinsic_world_to_cam` | OpenCV extrinsics [R\|t] (3×4), world metres |

`L` is the subject's left eye, which appears on the **right** of the image.

The 2D pupil centre is where the pupil is *seen*. The cornea refracts like a real eye's, which shifts
the visible pupil by up to about 0.4 px here. The wrapper therefore solves for the camera ray that,
refracted at the cornea, lands on the anatomical pupil centre.

## Known limitations

- **Rotation reference.** `eye_rotation_*` is the world-frame rotation from each eye's rest-pose
  gaze axis (eye centre → pupil centre with the eye bones unposed). Those axes are
  L = (0.0585, −0.9884, −0.1405) and R = (−0.0585, −0.9884, −0.1405): 8.08° down and 3.39°
  outwards. At `reset()` the eyes look at the centre target, so the rotation is about
  (−8.1°, ±0.1°, ∓8.1°), not zero: the eyes turn 8° up and 8° inwards from the rest axis.
  These are the true rotations and are left as they are. To get gaze relative to the centre
  fixation, compose with the inverse of the `reset()` quaternion. Directions and pupil positions
  are unaffected.
- **Gaze range.** ±5 cm at 35 cm is about ±8° of eye rotation, so the pupils move about 8–10 px
  in the 1024 px image.
- **No blink or eyebrow motion.** The lids follow gaze only.
- **Rendering time.** The CPU fallback is much slower than a GPU.
- Results were produced with Blender 5.3.0. Other versions may differ slightly in noise and denoising.

## Assets and licences

- Human, skin, eyes, brows, lashes, hair: MakeHuman system assets, **CC0**
  (makehumancommunity.org), created with MPFB 2.0.18 (GPL-3.0, used as a tool only and not included).
- Code: MIT.
- The scene-building and verification tools are kept in the team's development repository, not in
  this package.

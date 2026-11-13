# Synthetic Eye Movement & Virtual Camera Rendering (Track 1)

A textured, rigged human face in Blender with a Python wrapper that rotates both eyeballs
about their true centres and renders calibrated 1024×1024 frames with per-frame ground truth.

## Repository vs evaluator package

This is the **development repository**. The evaluator ZIP contains only the brief's core layout
(`scene.blend`, `wrapper/eyes.py`, `renders/`, `metadata.json`, `README.md`), and its README is
`packaging/README.md`. Build it with `tools/build_package.sh <new_staging_dir>`. The `tools/` and
`directions/` folders described below exist only in this repository.

## Requirements

- **Blender 5.3.0** (the only version tested; older versions are not verified). No add-ons are
  needed: every texture is packed inside `scene.blend`.
- Optional, for `tools/verify.py` only: Python 3 with `numpy` and `pillow`.

## Run

From this folder (on macOS the binary is `/Applications/Blender.app/Contents/MacOS/Blender`):

```bash
blender -b scene.blend -P wrapper/eyes.py
```

That renders the 10 clockwise frames to `renders/` and writes `metadata.json`.
It uses a GPU automatically (Metal, OptiX, CUDA, HIP, oneAPI) and falls back to the CPU.

Other commands:

```bash
blender -b scene.blend -P wrapper/eyes.py -- --move -1 0 --out out   # one frame, eyes to image left
blender -b scene.blend -P wrapper/eyes.py -- --reset --out out       # one frame, centre gaze
blender -b scene.blend -P wrapper/eyes.py -- --samples 128           # faster preview quality
blender -b scene.blend -P wrapper/eyes.py -- --cpu                   # force CPU
```

From Blender's Python console with `scene.blend` open:

```python
import sys; sys.path.append("/path/to/bundle/wrapper"); import eyes
eyes.move(0.5, -0.3)     # h, v in [-1, 1]
eyes.render("frame.png") # returns inputs, rotations and pupil centres
eyes.reset()
```

## Conventions

| Item | Value |
|---|---|
| Inputs | `h`, `v` normalised to [-1, +1], clamped; non-numbers are rejected |
| Direction | `h > 0` pupils move to the **image's right**, `v > 0` pupils move **up** |
| Fixation target | 35 cm in front of the eye midpoint, displaced by (h, v) × 5 cm |
| Camera | locked 40 cm in front of the eye midpoint, facing the face, 1024×1024 PNG |
| Lighting | constant studio lighting (key, fill, rim, neutral world) |
| Sequence | θₖ = 2πk/10, h = sin θₖ, v = cos θₖ, k = 0..9: starts at the top, clockwise on screen |
| World frame | Blender world, metres, +Z up, the face looks along −Y, subject's left eye at +X |

Each eyeball rotates about its own centre to look at the fixation target, so the eyes converge
naturally. The rotation is the shortest arc from the primary gaze direction (Listing's law), so
the eyes never twist about the gaze axis.

The eyelids follow vertical gaze as real lids do: the upper lid rotates with 110 % of the eye's
vertical rotation and the lower lid with 35 %. Looking up therefore lifts the lid instead of
hiding the pupil under it, and looking down lowers it. The lashes carry the lid skin's weights, so
they stay rooted on the lid margin.

## `metadata.json`

One record per frame:

| Field | Meaning |
|---|---|
| `frame`, `file`, `theta` | index, image path, θₖ in radians |
| `input` | `{h, v}` |
| `eye_rotation_L/R` | world-frame rotation from primary gaze, Euler XYZ in degrees |
| `eye_rotation_quat_L/R` | the same rotation as a quaternion (w, x, y, z) |
| `pupil_center_2D_L/R` | pupil centre in pixels, origin top-left, x right, y down |
| `pupil_center_3D_L/R` | anatomical pupil centre (centre of the pupil opening) in world metres |
| `pupil_center_cornea_3D_L/R` | where the ray to the seen pupil crosses the cornea; projects exactly to the 2D point |
| `pupil_center_2D_unrefracted_L/R` | straight projection of the anatomical centre, ignoring corneal refraction |
| `camera_matrix` | OpenCV intrinsics K (3×3) |
| `camera_extrinsic_world_to_cam` | OpenCV extrinsics [R\|t] (3×4), world metres |
| `fixation_target` | world position of the target the eyes look at |

The 2D pupil centre is where the pupil is *seen*. The cornea refracts like a real eye's (it
magnifies and shifts the pupil by up to about 0.4 px here), so the wrapper solves for the camera
ray that, refracted at the cornea, lands on the anatomical pupil centre. That ray's pixel is the
ground truth, and it matches the rendered pupils.

## Verify

```bash
python3 tools/verify.py .
```

It is independent of `eyes.py`. It checks the layout, the sequence, the 1024×1024 PNGs and the
40 cm / 35 cm calibration. It also finds the pupils in the rendered pixels and checks that they sit
at the metadata points and move in the commanded direction, and it reprojects the 3D pupils
through K[R|t].

## How it was built

`tools/build_scene.py` rebuilds `scene.blend` from scratch with the MPFB add-on. Evaluators do
not need to run it. It does the following:

- Creates an MPFB (MakeHuman) human: CC0 skin, high-poly eyes, brows, lashes and hair.
- Uses the default rig, with `eye.L` / `eye.R` bones.
- Replaces MPFB's painted eye with an anatomical eye (`tools/eye_model.py`). It has a sclera with
  subsurface scattering, conjunctival veins, a tear-film coat and lid occlusion. Its recessed
  procedural iris has radial fibres, crypts, a collarette and a soft limbal ring around a real
  pupil opening. Its refractive cornea has true adult geometry (7.8 mm curvature, 3.6 mm
  anterior chamber, index 1.3375).
- Adds a wet tear line along each lid margin, found by ray casting where the lid meets the eye and
  weighted to the lid bones so it rides with the lids.
- Adds a small eye light, linked to the corneas only, for one crisp catchlight on the iris clear of
  the pupil. The key and fill lights are excluded from the corneas.
- Transfers the eyelid skin weights onto the lashes, so they move with the lids.
- Connects the hair's strand normal map (MPFB leaves it unused) and removes the hair's specular.
  Without these, the rim light glares white across the crown.
- Uses coarser, stronger skin pores and more subsurface scattering than MPFB's defaults, so the
  skin doesn't look airbrushed at 1024 px.
- Uses small key and fill lights at about 5:1. This gives crisp white catchlights instead of dull
  grey discs, and keeps the face's shape.
- Adds young-adult expression lines as fine relief: faint forehead lines, nasolabial folds and
  under-eye creases. They are placed from facial landmarks and drawn per pixel from the rest
  pose, so they stay sharp and in place. Freckles and small spots are added too.
- Grows real strand hair (`tools/hair_strands.py`): 60,000 curves rooted on the scalp under
  MPFB's hair cap. It is a short textured crop, about 3 cm and lifted on top, 8 mm and lying flat
  on the sides, with clumping and a soft, natural hairline. It is shaded with Cycles' Principled
  Hair BSDF (melanin model). The cap stays underneath as a darkened base layer.
- Packs every texture into `scene.blend`.
- Fits a sphere to each eyeball. The fitted centre matches the eye bone pivot within 0.4 mm.
- Places the camera, the fixation target and the lights.

## Realism check against a real photo

`tools/photo_similarity.py <render.png> <photo.jpg>` compares a render with a real portrait at
matched scale. It scores cheek skin colour (CIE Lab ΔE), skin micro-texture, face contrast and
stubble darkening. The reference used is a studio headshot of a young man (see licences below);
it is used only to judge realism, not to copy the person's likeness.
Current score: 84 % (colour 0.57, texture 0.97, contrast 0.92, stubble 0.90).

## Assets and licences

- Human, skin, eyes, brows, lashes, hair: MakeHuman system assets, **CC0**
  (makehumancommunity.org), created with MPFB 2.0.18 (GPL-3.0, used as a tool only).
- Reference photo for the realism check (not shipped): "Max Hechtman Headshot 2024" by HM2021,
  Wikimedia Commons, CC BY 4.0.
- Code in this repository: MIT.

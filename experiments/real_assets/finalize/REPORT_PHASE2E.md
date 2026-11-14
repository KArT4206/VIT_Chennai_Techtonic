# Phase 2E: scan-based GNM head, refinement and validation

Branch `phase2/scan-head-finalization`, branched from `899e778`. All work is experimental. The
following are unchanged:

| File | SHA-256 (first 8) |
|---|---|
| `scene.blend` | `183cf99f` |
| `dist/Techtonic.zip` | `3da8efa9` |
| `wrapper/eyes.py` | `b548fad8` |
| `tools/verify.py` | `b0a12705` |
| `dist/phase1b/*.mp4` | `af1af2de 652d919e a745f1d0` |

- The previous build, `3dscanstore/build/gnm_scan.blend`, is not modified. Phase 2E writes
  `3dscanstore/build/phase2e/gnm_scan_2e.blend`.
- Scan-derived files (maps, scenes, renders) stay git-ignored. Only scripts and this report are committed.

| Script | Purpose |
|---|---|
| `diag_eye_corner.py` | Eye-corner diagnosis: per-angle pinkness, angle-coded debug renders |
| `measure_displacement.py` | Displacement-map measurements |
| `expr_geometry.py` | Exact lid / eye / brow geometry for every expression and combination; brow-lowerer key offsets |
| `build_2e.py` | Corrected eye maps, right-iris variant, brow-lowerer keys, switchable displacement |
| `render_2e.py` | Renders: `eyefix`, `disp` A–D, `iris`, `expr`, `closeups` |
| `test_2e.py` | Phase 2E checks |

## 1. Eye-corner patch: root cause and fix

**The earlier report misplaced the defect.**
- It said "inner corner".
- The angle-coded debug renders (`renders/phase2e/diag/dbg_*`) show it is the **outer (temporal)
  corner of the eye that turns toward the nose**.
- Looking left, the subject's right eye adducts and exposes temporal sclera.

**Investigation**
- **Geometry, normals, UVs, materials and the cornea are all correct.** Every visible eye pixel comes
  from the eye-interior material with the right UVs.
- **Eye-wet, tear line and lids** do not cause it. The patch appears with the cornea made transparent.
- **Eye rotation reaches far onto the eyeball.**
  - At neutral, the visible sclera reaches about 50° from the corneal axis.
  - At 15–20° gaze it reaches more than 70° at the outer corner.
- **The vendor map runs out of sclera before that angle.**
  - `Eyes_Balls_Diffuse.tga` is a fixed-gaze "realtime" map.
  - Only a four-lobed region is painted as sclera with vessels. Its edge sits at 50–69° depending on
    direction.
  - Everything beyond is a flat salmon fill.
  - Pinkness rises from about 0.05 (white) to 0.52 (fill) between 45° and 75°.
- **Aligning the scan's 8.5–9° outward-resting eye onto GNM's straight gaze moved that edge 9° closer to
  the outer corner.**

**Fix** (`build_2e.py`): re-bake from the same vendor eyeball after an angular remap of the vendor
source mesh around the corneal axis.
- **Iris, limbus and inner sclera:** everything within 30° is untouched. The test shows a mean change of
  0.0004.
- **Sclera:** the measured sclera edge in each direction is moved out to 82°.
- **Fill:** the fill is compressed behind that.
- Only original vendor pixels are used, and no colour is painted.
- Vessels in the stretched band are lengthened radially by up to 2.5×. That band is visible only at
  15–20° gaze.
- **Result:**
  - The pink patch is gone at 10, 15 and 20° gaze (`renders/phase2e/eyefix_before_after.png`).
  - Tear line, wetness, reflections, blink and half blink are unchanged.
  - Measured pinkness at 60–78° falls from 0.44 to 0.22. This is the one failing Phase 2E check, whose
    limit was < 0.2. The far edge keeps a faint warm tint, which is not visible in the 20° renders.

## 2. Distinct left and right irises

**Source:** the vendor ships one eye texture, and no second licensed iris is available. The right iris is
therefore a derived variant of the vendor iris (`build_2e.py`):
1. **Rotation.** The iris and its soft limbus are rotated 137° about the pupil centre in the baked map.
   This is an exact image rotation, cross-faded to the original over 1.00–1.12 iris radius, where the
   limbal gradient is rotationally uniform. Crypts, furrows and the collarette land in different places.
2. **Pigment variation.** A low-frequency radial and angular pigment variation of ±5% is added, with the
   mean preserved.

**Attempts rejected on inspection**
- Twisting the vendor source mesh: its coarse triangles folded and baked a hard polygonal limbus.
- A 2D twist band: it produced spiral streaks.

**Checks**
- **Different:** the irises differ (mean |L−R| 0.042).
- **Same colour:** channel means are within 0.1%.
- **Not a mirror:** the closest mirror differs by 0.038.
- **Pupil:** centred in both maps.
- **UV layout:** the same GNM UDIM layout (1002/1004), rotating with the eye bones.
- **Renders:** `iris_L_R_maps.png`, `iris/iris_pair.png` and `eyefix/eyeL_*`/`eyeR_*`.
  - Under the vendor lighting the dark brown irises look alike at a distance, as real ones do, and differ
    in close-up.

## 3. Displacement map: `Face_Displacement.tif`

| Property | Measured |
|---|---|
| Format | 8192², 1 channel, 16-bit unsigned, uncompressed, no colour profile → Non-Color |
| Range | 0–1 (both ends reached by under 0.1% of texels) |
| Midpoint | Background fill 0.4117; median inside the face region 0.439, mean 0.436 (used) |
| UV alignment | 99.86% of GNM tile-1001 texels carry data. The map matches GNM UVs (it is the vendor's own UV layout) |
| Physical scale | Fitted against the vendor normal map's pore-scale slopes: **0.66–0.83 mm per unit** on the cheeks (correlation 0.44). Other regions correlate weakly (0.03–0.17). 0.70 mm is used |
| Direction | Positive = outward. Normal map is OpenGL (+Y) |
| Content | Pore band std 0.0155 (about 11 µm); low-frequency std 0.03–0.07 (about 20–50 µm) |

**Double counting:** the displacement's pore detail correlates with the normal map (0.44).

**Comparison** (`renders/phase2e/disp/`, identical camera and light, 128 samples):

| Variant | 2048² skin close-up | Peak memory | Visual |
|---|---|---|---|
| A: current normal maps | 42.9 s | 18.9 GB | Sharpest pores; reference |
| B: displacement only (0.7 mm/unit, adaptive subdivision at 2 px) | 40.7 s | 19.2 GB | Real relief but softer pores, glossier patches. Face 0.97/255 from A |
| C: normal + displacement at 0.35 mm/unit (bump + displacement) | 72.0 s | 21.0 GB | Whole face darker (7.8/255): double-counted relief. **Rejected** |
| D: displacement + micro normal only | 49.9 s | 19.9 GB | Macro pore detail lost; flatter. **Rejected** |

- **Sizes:** front and brow views take 7–15 s in every variant.
- **Memory limit:** adaptive dicing at 1 px ran out of GPU memory for C and D.
- **Geometry:** no inflation, self-intersection, seams or proportion change was seen in B, C or D.
  Displacement is applied at render time, so topology is unchanged.
- **Decision:** keep **A**. The displacement is wired into the `Skin_2E` copy at scale 0, ready but off.
  It adds no visible gain over the vendor normal maps at these distances and costs time and memory.

## 4. Expressions

**Geometry** (`expr_geometry.py`, exact, on the scan base). Lid-to-eye penetration uses an exact
ray/triangle test against the rotated sclera and corneal bulge, and counts only overlap not present at
neutral.

| Pose | Lid opening (mm, L) | Brow (mm) | New lid / cornea overlap (mm) |
|---|---|---|---|
| Squint | 2.9–5.0 | −2.4 | 0.49 |
| Surprise | 6.0–9.8 | +1.7 | 0 |
| Brow raise | unchanged | +2.0 | ≤ 0.08 |
| Brow lowerer (new keys `brow_furrow_L/R`, the Phase 2D definition) | 5.1–8.3 | −0.7 | ≤ 0.14 |
| Blink | ≤ 0.15 (closed) | −0.9 | 0.66–0.70 |
| Blink + up 12° | closed | — | 0.93 |
| Blink + down 7° | closed | — | 0.37 |
| Blink + left 15° | closed | — | 1.19 |
| Squint + left 15° | 2.9–5.0 | — | 1.14 |
| Brow raise + up 12° | 7.0–11.4 | +2.2 | 0.52 |

- **Lower face:** still (0.0 mm) in every pose.
- **The other eye:** unaffected.
- **Lid / cornea overlap:**
  - It comes from GNM's corneal bulge, scaled ×1.055 to the scan eye, sliding under the lid lining. Pure
    side gaze gives up to 1.15 mm.
  - It sits on the **hidden inner lid lining**. No cornea pokes through a closed or open lid in any render
    (`sheet_expr_eyes.png`, blink plus side gaze included).
  - The production Phase 1B check reports the same kind of hidden lining motion (1.52 mm).

**Renders** (`renders/phase2e/expr/`, front and eye views for 16 poses). Squint, blink, half blink and all
combinations look natural, the textures stay stable and brows move with the skin. Surprise, brow raise
(2 mm) and brow lowerer are correct but subtle at full-face distance.

## 5. Contact sheets and close-ups

| Sheet | Contents |
|---|---|
| `sheet_final.png` | Front, three-quarter, gaze left/right/up/down, blink, half blink, squint, surprise, brow raise, brow lowerer |
| `sheet_expr_eyes.png` | 16 eye-region poses |
| `sheet_closeups.png` | Eye, brow, hairline, both ears, 2048² skin |

All were inspected at 100%, and the crops at 200%.

## 6. Performance

- Scan head frames: 17–23 s at 1024², 128 samples.
- 2048² skin: 43 s.
- Peak footprint: about 19 GB (variant A).
- The eye fix and iris variant cost nothing at render time; they are texture changes only.

## 7. Tests

| Suite | Result |
|---|---|
| `tools/verify.py` (production) | 82/82 |
| Phase 1B `expression/check.py` | 51/51 |
| GNM numpy | All pass |
| GNM Blender `test_gnm_blend.py` | 19/19 |
| Phase 2E `test_2e.py` | **27/28.** The one failure is the 60–78° pinkness limit (0.22 against < 0.2), see §1 |

Phase 2E checks cover:
- topology, face order and bit-identical UVs;
- 7 regions;
- basis and 11 keys identical;
- eye joints at 0.0000 mm, with rigid rotation;
- the new UDIM eye map;
- iris differences;
- blink closure in four poses;
- lower face still;
- brow directions;
- the vendor material untouched.

## 8. Remaining visual defects

1. Faint warm tint at the far temporal sclera at 20° gaze (measured, see §1).
2. Bright streaks on the forehead and temples. They come from the vendor specular and scatter maps and
   also appear in the original scan render.
3. A stray lash strand at the right eye's outer corner during blink. It is the vendor lash mesh under
   Surface Deform.
4. Brow raise, lowerer and surprise amplitudes are anatomically modest. Stronger values would need new
   control fits.
5. The head is bald, as scanned: there is no hairline to show. The subject's right ear sits in the
   vendor key light's shadow.
6. The subject's right iris sits about 1.5 mm off the camera axis at straight gaze. This is within the
   normal 5° angle between the eye's visual and optical axes.
7. The displacement map is not used (decision in §3).

## 9. Permission status

**No written permission has been supplied.** Everything in `3dscanstore/LICENCE_RECORD.md` stays
unconfirmed, beyond private personal-use experimentation:
- modification;
- baking and derived maps;
- competition demonstration;
- sharing with judges;
- GitHub redistribution;
- submission ZIP redistribution.

The user must supply the vendor's actual message before any of it is used outside this machine.

## 10. Recommendation

**Technically, this head is ready to approve as the final model.** It is the scan-based GNM head from
`gnm_scan_2e.blend`, with:
- the corrected eye maps;
- the distinct irises;
- the brow-lowerer keys;
- normal-map skin (variant A).

It meets the brief's anatomy, expression and compatibility requirements, as shown by the renders and
tests above.

**Approval for submission is blocked only by the licence.** No scan-derived file may go into the
evaluator ZIP or a repository until the written permission covers it.

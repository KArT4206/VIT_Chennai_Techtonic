> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Calibration report

Command: `blender -b --factory-startup <bundle>/scene.blend -P research/compliance_tests.py -- AUDIT/results/compliance.json`
Bundle: fresh unzip of the release `Techtonic.zip`. Blender 5.3.0, Apple M5. Values below are from the 22 Nov 2026 run; the JSON file is the authoritative record.

## Conventions
- World: Blender, metres, +Z up, the face looks along −Y.
- Image: pixels, origin top-left, x right, y down, 1024 × 1024.
- Camera matrices: OpenCV convention. K is 3 × 3; `[R|t]` maps world to camera (camera looks down +Z, +Y down).
- Eye rotation: world-frame shortest arc from the calibrated primary gaze axis, given as quaternion (w,x,y,z) and Euler XYZ in degrees.

## Measured geometry

| Quantity | Requirement | Measured |
|---|---|---|
| Resolution | 1024 × 1024 PNG | 1024 × 1024 @ 100 % |
| Camera distance from eye midpoint | 40 cm | 0.400000 m |
| Camera optical axis vs direction to midpoint | faces the face | 0.0000° |
| Eye midpoint in the image | — | (512.000, 512.000) px |
| Camera animated or constrained | locked | no animation, 0 constraints |
| Fixation target distance | 35 cm forward | 0.349999993 m (float32 precision) |
| Target displacement for h, v = ±1 | ±5 cm in the 35 cm plane | ±0.05 m exactly in x and z, 0 in y |
| Interocular distance | plausible adult | 59.404 mm |
| Vergence at the 35 cm target | — | 9.70° |
| Lights | constant | 5 lights, none animated |

## Projection test with known points
500 random world points within ±10 cm of the eye midpoint, projected with the exported K[R|t] and with Blender's own `world_to_camera_view`. Maximum disagreement: **0.0002 px**. R is orthonormal.

## Rotation tests (both eyes, all 10 sequence poses)
- Pivot drift from the eye centre: 0 mm.
- Radius change of the pupil from the pivot: ≤ 0.000028 mm (it stays on its sphere).
- Angle between the mesh pupil direction and the fixation target: 0.000°.
- Torsion about the primary axis (Listing's law): 0.000°.

## Input handling and state
- (5, −7) is clamped to (1, −1). `'x'`, NaN, inf and None each raise `ValueError`.
- A reset after other moves gives a state bit-identical to the first reset.
- The same `move` twice gives an identical state.
- The pose updates synchronously (the bone matrix changes without a frame change).
- h = +1 moves both pupils to image right of h = −1; v = +1 moves them up.

## Note on tolerances
The first run used a 1 nm tolerance for the target distance and failed 4 checks at 0.349999993 m. `mathutils.Vector` is float32 (about 1e-7 relative), so that tolerance was below the arithmetic precision. The tolerance is 1 µm (0.001 mm) and documented in the script. No requirement was relaxed: 1 µm is about 0.004 px at this camera.

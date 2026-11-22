# Phase 2G: final MakeHuman submission package

**Verdict: PACKAGE RELEASE-READY.**

The package is the MakeHuman/MPFB production model. It contains no 3D Scan Store file and nothing
derived from one. Tests run from a clean extraction pass: 82/82 evaluator checks, 19/19 API checks,
and byte-identical metadata reproduction.

## 1. Repository and release branch

**State at the start**

| Item | Value |
|---|---|
| Branch | `phase2/scan-head-finalization` at `ae742ad` |
| Working tree | Clean; scan-derived files are git-ignored |

**Production files are byte-identical on every branch:**
- `f31eb4e` baseline
- `e8a3c1d` Phase 1A
- `0c05142` Phase 1B
- `c5ba5f2` Phase 2A
- `ae742ad`

| File | SHA-256 (first 8) |
|---|---|
| `scene.blend` | `183cf99f` |
| `wrapper/eyes.py` | `b548fad8` |
| `tools/verify.py` | `b0a12705` |
| `metadata.json` | `bc3c1a07` |

`tools/build_package.sh` first appears in Phase 1A (`e8a3c1d`).

**Chosen source: `0c05142` (Phase 1B)**
- **History:** it is the last commit before any GNM or scan work. The history is linear:
  `f31eb4e` → `e8a3c1d` → `0c05142` → GNM phases → scan phases.
- **Files:** the same verified production files as above, plus the packaging script and the most
  complete evaluator README. Phase 1B adds a fuller "Rotation reference" explanation.
- **Contents:** it has no GNM, scan or real-asset files (0 matches in `git ls-files`).

**Release branch:** `release/makehuman-submission`, created at `0c05142`.
- It has no scan or GNM commits.
- It was checked out in a separate worktree, so the development checkout was untouched.
- This report is its only added commit.

## 2. Final ZIP

| Item | Value |
|---|---|
| Built with | `tools/build_package.sh` from `0c05142`, unmodified |
| Location | `dist/Techtonic.zip` (git-ignored); the build copy is in the session scratchpad `phase2g_pkg/` |
| SHA-256 | `91f4bafe10200a9e1d4a0176060de4ef86d50b92becf279e70c25c0e245773a4` |
| Backup of the previous ZIP | `dist/backup/Techtonic_pre-phase2g_nested.zip` (SHA-256 `3da8efa9…`, the old layout nested under `Techtonic/`) |

**ZIP root listing.** These 16 entries are directly at the root, with no parent folder:

```
scene.blend                 17,139,355
wrapper/
wrapper/eyes.py                 17,084
renders/
renders/frame_00.png … frame_09.png   (10 files, ~1.32 MB each)
metadata.json                   20,538
README.md                        8,186   (from packaging/README.md)
```

- **Excluded:** no `__MACOSX`, `.DS_Store`, scan, GNM or tool files.
- **Same production files:** `scene.blend`, `eyes.py`, `metadata.json` and the 10 renders are
  byte-identical to the production files.

## 3. Clean extraction and execution

The ZIP was extracted into a new empty directory, then copied for the runs so the extraction stayed
pristine. Everything below ran with `blender -b --factory-startup` from inside that copy (Blender
5.3.0, Metal GPU).

**API test**: `phase2g_api_test.py`, run in the extracted `scene.blend`, importing `wrapper/eyes.py`.
**19/19 pass:**
- **Render settings:** 1024 × 1024 at 100%.
- **Calls:**
  - `eyes.move(-1,0)`, `(1,0)`, `(0,1)`, `(0,-1)` and `(0.5,-0.3)`, plus `eyes.reset()`.
  - Each was followed by `eyes.render()`, which wrote a 1024 × 1024 PNG and returned `input`,
    `eye_rotation_L/R` and `pupil_center_2D_L/R`.
- **Direction conventions**, pupil image coordinates:

  | Eye | h = −1 | reset | h = +1 | v = +1 (y) | reset (y) | v = −1 (y) |
  |---|---|---|---|---|---|---|
  | L | 628.0 | 636.6 | 645.4 | 503.7 | 512.4 | 521.1 |
  | R | 378.6 | 387.4 | 396.0 | 503.7 | 512.4 | 521.1 |

  - h = −1 moves the pupils image-left and h = +1 image-right.
  - v = +1 moves them up and v = −1 down.
- **Determinism:** the same input twice gives an identical state.
- **Input handling:** non-numeric input is rejected, and out-of-range input is clamped to [−1, 1].
- **Fixed camera and lighting:** the camera transform and lens are unchanged after
  move/reset/render. The 4 lights (transforms and energy) and the world are unchanged. The camera
  is 40.00 cm from the eye midpoint.
- **Self-contained:** all 6 texture images are packed; there are no external files or linked
  libraries.

**Command-line runs** (`-P wrapper/eyes.py`):
- `--move -1 0`, `--move 1 0`, `--move 0 1`, `--move 0 -1` and `--reset` produced 5 PNGs with
  5 JSON files.
- With no arguments, the full 10-frame clockwise sequence rendered into a separate folder.

## 4. Test results (exact counts)

| Suite | Result |
|---|---|
| Original evaluator `verify.py` (from `0c05142`, unmodified), on the extracted package with its own fresh direction and reset renders | **82/82** |
| Phase 2G API test (`eyes.move`, `eyes.reset`, `eyes.render`, conventions, fixed camera and lights, packing) | **19/19** |
| Ten clockwise frames | 10/10 present, each a 1024 × 1024 PNG (packaged and regenerated) |

**Other suites from the same production files, run in Phase 2F at `ae742ad`:**
- Phase 1B: 51/51.
- GNM Blender: 19/19.
- GNM numpy: 26/26.

The GNM and Phase 1B suites are not part of this package.

## 5. Metadata validation

- **Reproduction:** `metadata.json` regenerated from the extracted package is **byte-identical** to
  the packaged file. The largest pupil-centre difference is 0.0 px.
- **Inputs:** 10 frames, `frame` 0–9, with h = sin(2πk/10) and v = cos(2πk/10), so they start at
  the top and go clockwise (checked to 1e-3).
- **Brief's required keys, all present:** `frame`, `input`, `eye_rotation_L/R`,
  `pupil_center_2D_L/R` and `camera_matrix`.
- **Extra keys:**
  - `eye_rotation_quat_L/R`
  - `camera_extrinsic_world_to_cam`
  - `fixation_target`
  - `pupil_center_3D_L/R`
  - `pupil_center_cornea_3D_L/R`
  - `pupil_center_2D_unrefracted_L/R`
  - `file`
  - `theta`
- **Top-level fields:** `conventions`, `fixation_distance_m`, `motion_bound_m`,
  `camera_distance_m` and `eye_midpoint`.

## 6. Asset licence inventory

**Images packed in `scene.blend`:**

| File | Size | Origin | Licence evidence |
|---|---|---|---|
| `young_lightskinned_male_diffuse.png` | 2048² | MakeHuman skin `young_caucasian_male` | `.mhmat` header: released as CC0, September 2020 (Data Collection AB) |
| `brown_eye.png` | 1024² | MakeHuman eye material `brown` | `brown.mhmat` header: CC0 |
| `eyebrow009.png` | 512² | MakeHuman eyebrow009 | `.mhclo` header: CC0 |
| `eyelashes01.png` | 512² | MakeHuman eyelashes01 | `.mhclo` header: CC0 |
| `short04_diffuse.png` | 2048² | MakeHuman hair short04 | `.mhclo` header: CC0 |
| `sss.png` | 2048² | MPFB 2.0.18 `data/textures` | No per-file header. MPFB's `LICENSE.md` makes "textures" a CC0 asset category (code is GPL-3.0); CC0 full text is in `LICENSE.ASSETS.md`. Category-level, not per-file |

**Other contents:**

| Item | Licence |
|---|---|
| Geometry | The MakeHuman base mesh and proxies (CC0 by the same MPFB asset licence), plus the anatomical eye and hair strands generated by the team's own scripts |
| Not present | Linked libraries, fonts, sounds, text blocks or external file paths |
| `wrapper/eyes.py`, `README.md`, renders, `metadata.json` | Team-authored or generated. The README declares the code MIT |
| MPFB 2.0.18 | GPL-3.0-or-later. It was used as a tool only and is not included; the scene runs with `--factory-startup` and no add-ons |
| 3D Scan Store | **Nothing included.** No scan file, map, mesh or derivative exists on the release branch or in the ZIP |
| Reference photo (CC BY 4.0, realism check) | Not shipped |

## 7. Remaining known issues

1. **No licence text file inside the ZIP.** The README states CC0 and MIT. Adding licence files would
   need to be a `packaging/README` and packaging change.
2. **`sss.png`'s CC0 status is by MPFB's asset category, not a per-file header.**
3. **Not part of this phase:**
   - the demo video or contact sheet for the form;
   - the presentation deck;
   - the GitHub repository.
4. **Brief inconsistency:** the brief gives the demo length as "1–2 min" in the Track 1 slides,
   "max 3 minutes" in the submission rules and "5-min" in the timeline.
5. **Reset rotation:** `eye_rotation_*` at `reset()` is about (−8.1°, ±0.1°, ∓8.1°), measured from
   the rest-pose axis. This is documented in the README.
6. **Filename:** the ZIP is `Techtonic.zip`. The form asks for `team_name.zip`; confirm that
   "Techtonic" is the registered team name.

## 8. Verdict

**PACKAGE RELEASE-READY.**

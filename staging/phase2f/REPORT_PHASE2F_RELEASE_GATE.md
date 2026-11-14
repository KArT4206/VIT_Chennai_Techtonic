# Phase 2F: submission integration and release gate

**Decision:**
- **Scan-based GNM head: NOT RELEASE-READY.** No written permission is on file.
- **MakeHuman production package, built with `tools/build_package.sh`: RELEASE CANDIDATE** for
  the official Track 1 brief. It is not yet the shipped ZIP: `dist/Techtonic.zip` is unchanged and still
  uses the old nested layout.

## 1. Branch and commit

| Item | Value |
|---|---|
| Branch | `phase2/scan-head-finalization`, verified at the start: commit `4c76350`, clean apart from untracked scan-derived files that are git-ignored |
| Phase 2F work | On this branch. It adds only `staging/phase2f/` and edits to Phase 2E experiment scripts |
| Production checksums | Recorded before any work in `staging/phase2f/PRODUCTION_SHA256_BEFORE.txt` (27 files) |
| Production after the work | Identical, re-checked |

Production checksums (SHA-256, first 8):

| File | Hash |
|---|---|
| `scene.blend` | `183cf99f` |
| `wrapper/eyes.py` | `b548fad8` |
| `tools/verify.py` | `b0a12705` |
| `metadata.json` | `bc3c1a07` |
| `dist/Techtonic.zip` | `3da8efa9` |

The production checksum list also covers `README.md` and `contact_sheet.png`, the 10 renders and
`dist/phase1b/`.

## 2. Asset permission and scope

Searched: the whole project (excluding the extracted asset), `~/Downloads`, the kit's licensing folder,
and all `.eml`, `.md` and `.txt` files mentioning 3D Scan Store. **No written permission was found.**
The kit's `3DSCANSTORE_PERMISSION_RECORD_TEMPLATE.md` is blank. The only evidence is the user's chat
statement and the vendor page's "Personal use only".

| Use | Explicitly covered in writing? |
|---|---|
| 1. Samsung PRISM Hackathon use | **No evidence** |
| 2. Modifying the scan and its geometry | **No evidence** |
| 3. Baking or deriving textures | **No evidence** |
| 4. Embedding scan-derived assets in a `.blend` | **No evidence** |
| 5. Giving that project to Samsung judges | **No evidence** |
| 6. Public GitHub distribution | **No evidence** (assumed prohibited) |

**Handling:**
- The scan work stays private and experimental. Every scan-derived file is git-ignored.
- Nothing scan-derived is in staging or in any package. The scan head was not integrated into a staging
  copy, as the gate requires.

**GNM-only alternative.** This is assessed, not built. Its components have documented redistribution
rights:
- the GNM mesh (Apache-2.0; the weights themselves are not shipped);
- the CC0 MakeHuman skin colour;
- the procedural Phase 2C/2D detail.

The production wrapper would need an adapter in the GNM scene:
- an armature with `eye.L` and `eye.R`;
- lid bones `orbicularis03.L/R` and `orbicularis04.L/R`, driving the GNM lid keys;
- `EyeL.Iris` and `EyeR.Iris` objects carrying `pupil_local`, `eye_dims` and `cornea_ior`.

**The official brief does not require GNM.** It lists "MakeHuman / GNM / FLAME" and "MakeHuman / MPFB
(CC0)" as allowed open assets, so the MakeHuman production model already meets the topology
requirement.

## 3. Phase 2E test failure, closed by investigation

**The test** (`test_2e.py`, as written in Phase 2E, threshold unchanged):
- **Band:** GNM eye-interior vertices 60–78° from the gaze axis.
- **Pass condition:** mean pinkness < 0.2 after the fix, and > 0.3 before.
- **Sampling:** the GNM eye has a single vertex ring in that band, at 72°, which samples the map at UV
  radius 0.418.

**Finding: a real, measurable texture property, not an artefact and not the original defect.**
- The vendor's painted sclera is not uniformly white. Pinkness rises from 0.13 at the limbus to about
  0.24 at its own painted edge, in the region the vendor's original scene shows at straight gaze.
  Real conjunctiva gets more vascular toward its fold in the same way.
- The flat salmon fill (0.52) that caused the visible patch now starts only at the 84° ring.

**Minimal correction tried:**
- The sclera edge was redefined at the sclera body's own pinkness of 0.15 (it was 0.2), keeping the
  vendor's soft transition behind 82°.
- `build_2e.py <out> 0.15` writes `3dscanstore/build/phase2f/` and leaves Phase 2E intact.
- Result: 72° ring 0.25 → 0.21, and UV radius 0.42 → 0.27 in the dense profile.

**Exact results:**

| Build | Phase 2E checks | Failing check |
|---|---|---|
| Phase 2E | **27/28** | 0.44 → 0.22 |
| Phase 2F (edge 0.15) | **27/28** | 0.44 → 0.21 |

The threshold was not loosened. The even-light gaze renders at 10, 15 and 20° show white sclera with
thin vendor vessels and no fill (`even_sclera_gaze_2e_vs_2f.png`; left half Phase 2E, right half
Phase 2F).

## 4. Visual evidence

All renders are private, git-ignored, under `experiments/real_assets/renders/`.

| Evidence | File |
|---|---|
| Even-light left and right eye close-ups, each eye looking into its own camera | `phase2f/even_phase2f/even_iris_left.png`, `even_iris_right.png`; pair in `phase2f/even_iris_R_L.png` |
| Iris textures side by side | `3dscanstore/build/phase2e/iris_L_R_maps.png` (flat maps, identical exposure) and `phase2f/even_iris_R_L.png` (identical even lighting) |
| Corrected sclera at 10, 15 and 20° (both directions) | `phase2f/even_sclera_gaze_2e_vs_2f.png`; vendor lighting in `phase2e/eyefix_before_after.png` |
| Full-face expression contact sheet | `phase2e/sheet_final.png`, `phase2e/sheet_expr_eyes.png` |
| Skin detail and displacement/normal comparison | `phase2e/disp/skin_ABCD_100pct.png`, `front_ABCD.png` |

"Even light" means all scene lights off and a uniform white world. It is a diagnostic only, not the
evaluator look. Under it the pupils read grey, because the cornea reflects the bright surroundings.

**Provenance:**
- **Left iris:** the vendor's scanned eye texture, baked onto GNM.
- **Right iris:** a **derived variation** of that same texture: rotated 137° about the pupil, plus ±5%
  pigment variation. It is **not** a separately captured eye.
- **Sclera:** vendor pixels, angularly remapped.

## 5. Staging integration

**Not performed for the scan candidate**, because the permission gate is unmet.

The production MakeHuman package was rebuilt in an isolated staging folder outside the repo, using the
untouched `tools/build_package.sh`:
`scratchpad/phase2f_pkg/Techtonic.zip`, SHA-256 `825a16a9…`.

The API and conventions are those of the production wrapper, already verified against the brief:
- `eyes.move(h, v)`, `eyes.reset()` and `eyes.render()`;
- fixation 35 cm with ±5 cm bounds;
- camera locked 40 cm ahead;
- 1024² PNG output;
- clockwise sampling starting at the top;
- metadata fields matching the brief's example record.

Nothing was changed to suit a model.

## 6. Texture and animation deliverables

**Checked against the official consolidated spec PDF (Track 1, pages 4–8).** The required deliverables
are:
- the complete `.blend` (textured mesh, eye bones, materials);
- the Python wrapper with a README;
- 10 clockwise renders with per-frame JSON metadata;
- a contact sheet or a 1–2 minute demo video.

All are present in the package, and `contact_sheet.png` exists in the repo.

**Not in the official brief:** 5–10 texture variants and Left/Right/Generate videos. They come from the
older SyntheticEyes deck. So that nothing is counted falsely:
- Left, Right and Generate motion videos exist from Phase 1B (`dist/phase1b/`, MakeHuman, each ≤ 15 s,
  verified by 51 checks).
- They have an integrated timeline with eyelid, eye and brow animation, and a reproducible script
  (`expression/run.py`).
- **No set of 5–10 documented final texture variants exists.** They were not built, per the earlier
  stopping conditions.

## 7. Test results (exact counts)

| Suite | Result |
|---|---|
| Original evaluator `tools/verify.py`, repository | **82/82** |
| Original evaluator, **clean extracted staging package** with its own fresh direction and reset renders | **82/82** |
| Same package before the five direction renders existed | 71/71 (the 11 direction and reset checks need them) |
| Phase 1B `expression/check.py` | **51/51** |
| GNM Blender `test_gnm_blend.py` | **19/19** |
| GNM NumPy `test_gnm_numpy.py` | **26/26** |
| Phase 2E `test_2e.py` | **27/28** (both builds; §3) |
| Clean-machine sequence | Re-rendered the 10 frames from the extracted package; `metadata.json` byte-identical to the shipped one (pupil difference 0.0 px) |

## 8. Package structure and extraction

| Package | Layout |
|---|---|
| Staging package from `build_package.sh` | `scene.blend`, `wrapper/eyes.py`, `renders/frame_00…09.png`, `metadata.json`, `README.md` **at the ZIP root**. Extracted cleanly and ran headless with `--factory-startup` |
| **Existing `dist/Techtonic.zip`** (unchanged, as instructed) | Nests everything under a `Techtonic/` parent folder. **It does not meet the "no unexpected parent folder" rule. It must be replaced by the staging-built package before submission.** That needs your go-ahead |

## 9. Remaining known defects

**Scan candidate (private):**
- the 60–78° vendor tint (§3);
- vendor specular streaks on the forehead;
- a stray lash at the right eye's outer corner during blink;
- subtle brow expressions;
- a bald scan;
- the right iris is a derived variant;
- no written permission.

**Production:**
- `dist/Techtonic.zip` has the nested layout;
- no texture-variant set (not required by the official brief).

**Other submission items still outstanding:**
- the 5-minute or 3-minute demo video (the brief is inconsistent on length);
- the CollegeName_TeamName deck;
- a public or shared GitHub repo.

## 10. Decision

- **Scan-based GNM head: NOT RELEASE-READY.** It is blocked by missing written permission. It must not
  be shipped or pushed.
- **MakeHuman production package (staging build): RELEASE CANDIDATE.** It has the correct root layout
  and passes 82/82 from a clean extraction, with a reproducible sequence.
- **Before shipping:** replace `dist/Techtonic.zip` with the staging build (your approval needed). The
  deadline is **18 Nov 2026, 11:59 PM**.

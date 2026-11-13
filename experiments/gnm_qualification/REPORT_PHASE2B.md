# Phase 2B: GNM facial kinematics, eyelids and material proof

Branch `phase2/gnm-expression-prototype` (from `c5ba5f2`). Everything is under
`experiments/gnm_qualification/`. Production `scene.blend`, `wrapper/eyes.py`, `tools/verify.py`,
`dist/Techtonic.zip` and `dist/phase1b/` are unchanged (SHA-256 verified before and after).

**Corrections to earlier reports**
- `tools/verify.py` has **82** checks, not 83. The earlier count matched the
  "ALL CHECKS PASSED" line too. Results were always all-pass.
- The Phase 1B suite has **51** checks.
- Phase 2A said rotating an eye moves "0 skin vertices". GNM's pose correctives do include the
  eye joints, but the effect is ≤ 6.4e-9 m: below float32 precision and physically nil.

## A. Expression parameters (measured, not assumed)

**Structure**
- 383 components: 100 left-eye region, 100 right-eye region, 150 lower face, 32 tongue, 1 pupil.
- **Exactly linear** blendshapes (superposition error 6.4e-9 m, float32), applied before
  skinning. So any control is an exact per-vertex offset, i.e. a Blender shape key.
- The eye blocks are fully isolated: a left-block change moves the right eye, mouth and chin by
  0.000 mm.

**Raw PCA components are not semantic**
- Component 0 opens the lid +4.3 mm and lifts the brow +3.8 mm.
- Component 1 opens the lid +3.9 mm and lowers the brow −1.6 mm.

So no single component is used as "blink" or "squint".

**Semantic sampler**
- A conditional-VAE decoder (concat[z 64, one-hot 20] → Dense 64/128/256/512 ReLU → 383).
- Re-implemented in NumPy from the `.h5` weights with `h5py` only (about 3 MB). TensorFlow is not
  needed. Decoding the latent mean (z = 0) is deterministic.
- **Limitation:** the NumPy forward pass could not be compared numerically against Keras without
  installing TensorFlow. It is a plain dense stack and was validated visually and geometrically.
- Measured canonical expressions (lid opening, neutral about 7.2 mm mean):

  | Label | Opening | Brows |
  |---|---|---|
  | `wink_left` | left 0.76 mm, right unchanged | left −2.4 mm |
  | `wink_right` | mirrored | mirrored |
  | `squint` | 2.8 mm | −2.5 mm |
  | `surprise` | 7.8 mm | +1.3 to +1.7 mm |
  | `compress_face` | both closed | −3.7 mm |

**Controls derived per eye (inside its own block only)** — `gnm_controls.py`

| Control | Definition | Measured |
|---|---|---|
| `blink` | semantic wink's lid motion, brow/forehead held still (ridge LS), scaled to close | all 5 columns ≤ 0.15 mm; brow −0.73 mm; other eye 0.000 |
| `lid_follow` (per +10°) | upper lid rotates with eye elevation, lower lid at 35 % (Phase 1B gains) | opening 5.9 → 9.2 mm from −8° to +12°, monotonic |
| `squint` | semantic SQUINT, eye block | opening 2.8 mm, brow −2.4 mm |
| `surprise` | semantic SURPRISE, eye block | opening 7.8 mm, brow +1.7 mm |
| `brow_raise` (per +2 mm) | brow-region lift with lids held still (ridge LS) | +1.8 mm at weight 4, lids within 0.17 mm |

## B. Contact sheets

`renders/gnm_expression_sheet.png` (labelled) shows: neutral, left/right/both closed, partial
blink, squint, surprise, raised and lowered lids, up and down gaze with lids following, brow raise.

## C. Blinks

- Complete blink, both eyes: every margin column ≤ 0.15 mm.
- The outer columns overlap by up to 0.45 mm, so the lids meet rather than leaving a slit. No
  geometry was added.
- Partial blink (0.5): 50 % of the opening remains.
- Left and right blinks are independent (the other eye moves 0.000 mm).
- Timeline blink timing comes from the Phase 1B model: 75 ms closing, 30 ms closed, 170 ms
  opening, Bell's dip.

## D. Lid deformation and intersection

- Lid opening (mm, 5 columns) is measured on fixed margin vertices chosen on the neutral mesh.
- **Intersection:** lid skin entering the eyeball sphere, compared with the neutral pose, over
  blink, up 12°, down 8°, side 18° and squint, is at most **0.31 mm** (left) and **0.22 mm**
  (right). The MakeHuman Phase 1B reference was 0.45 mm.

## E. Eye movement

- With identity joint orientations, a GNM eye axis-angle **equals a world-frame rotation about
  the eye centre** (error 5.6e-17). Frame: Y up, face +Z, +Y rotation turns the gaze toward the
  subject's left, +X turns it down.
- Each eye aims at its own point 35 cm from the midpoint, so the eyes converge. Checks:
  - both pupils point at the target (0.000° error) at (0,0), (12,5) and (−15,−6);
  - vergence 10.08° at 35 cm (inter-eye distance 61.7 mm).
- The Phase 1B motion model is reused unchanged: saccades, drift, pursuit, blinks, brows.
- **Blender:** the shape keys plus the armature eye bones reproduce GNM's own vertex output on 7
  mixed poses to **6.4e-8 m** (float32).

## F. Brows

- GNM has brow-region geometry (152 vertices per side, plus 110 in the middle and 371 on the
  forehead), and `brow_raise` moves it about 1.8 mm with the lids still.
- **There are no eyebrow hairs or brow mesh**, and the CC0 skin has only faint brow colour. The
  raise is real geometry but barely visible: a 3 mm raise is hard to see on the clay and textured
  renders.

## G. Single texture set

**Licences**
- MakeHuman skin `young_lightskinned_male_diffuse.png`: CC0 1.0. Verified by the asset's own
  header and the upstream `makehumancommunity/makehuman` `LICENSE.ASSETS.md`. CC0 §4(c) notes that
  third-party rights such as likeness are not cleared; a generic skin map is low risk.
- Eye colour: our own procedural shaders (`tools/eye_model.py`, MIT).

**Method** (geometry-aware, not UV copying)
1. Fit GNM's 170 head-identity components to the MakeHuman head: point-to-plane ICP with ridge
   regularisation, λ = 2e-7. Face median 0.64 mm, 95th percentile 1.81 mm, max |coeff| 1.26.
2. Cycles selected-to-active ray bake (DIFFUSE colour only) onto GNM's own UDIM layout, one tile
   at a time.
3. Fill unreached texels from their nearest baked neighbours.

**Result**
- Tiles 1001 (skin, 2048²), 1002 and 1004 (eye interiors, 1024²), sRGB.
- 1003/1005 are a refractive cornea material (no texture). 1006/1007 are flat colours.

**Defects found and fixed**
- The production sclera shader's ambient-occlusion "lid shadow" baked dark bands into the eyes.
  Neutralised for the bake.
- Black neck/behind-ear texels: extended the MakeHuman export and the ray distance, then filled.
- Faceted shading: set smooth normals (topology unchanged).
- GNM's eye "exterior" is a **closed shell around the whole eyeball** whose back half lies inside
  the sclera. Solid glass made the eyes milky. Fix: only the corneal cap (120 faces beyond the
  sclera radius) refracts; the rest of the shell is transparent.

**Not photorealistic** — see L.

## H. Blender prototype

`gnm_expression_test.blend` (git-ignored; rebuilt by `build_prototype.py`):
- original GNM geometry and UVs (basis bit-identical);
- 10 exact control shape keys and a 4-bone rig;
- a UDIM texture set and a camera;
- Timeline actions `Competition_GNM_Natural_Eye_Expression` (eye bones) and `…_ShapeKeys`,
  1–288 at 24 fps: 2 complete blinks, 1 partial blink, up 15° and down 7° gaze, an eye roll,
  brows, neutral start and end.

Renders (Metal, confirmed in the logs) in `renders/prototype/`: neutral at the 40 cm evaluator
camera, close-up, three-quarter, and Timeline frames for the complete blink, partial blink, up
gaze and down gaze.

## I. GNM vs MakeHuman (`renders/compare/`, production scene, same camera, lights, 128 samples, 1024²)

| # | Criterion | MakeHuman (production) | GNM (prototype) | Better |
|---|---|---|---|---|
| 1 | Eye geometry | custom sphere eye, pivot fitted within 0.4 mm | official, joint exactly at sphere centre (0.000 mm), separate iris/pupil/sclera/cornea | GNM |
| 2 | Eye rotation | true rotation about the eye bone | true rotation, exact axis-angle | equal |
| 3 | Convergence | correct, 9.58° at 35 cm (58.8 mm eye spacing) | correct, 10.08° (61.7 mm) | equal |
| 4 | Lid realism | lids + lashes + tear line, gaze-following | learned lid shapes, no lashes, no tear line | MakeHuman (visual); GNM (anatomical shape) |
| 5 | Blink quality | bone rotation, clean closure, lashes meet | statistically learned closure with fold, ≤ 0.15 mm; no lashes | GNM shape, MakeHuman look |
| 6 | UV portability | MakeHuman UV only, **not** the GNM/FLAME UVs the slides require | **official GNM UDIM**, 7 verified tiles | **GNM** |
| 7 | Texture potential | CC0 skin + procedural pores + strand hair | CC0 skin transferred by bake; no pores, brows, lashes or hair yet | MakeHuman today |
| 8 | Facial realism | hair, brows, lashes, pores, wet eyes | bald, waxy, grey irises, corneal highlight arc in side gaze | **MakeHuman** |
| 9 | Integration | done, 82/82 + 51/51 | prototype only, 26 + 19 new checks; evaluator wrapper would need porting | **MakeHuman** |
| 10 | Render time | 11.9–12.7 s/frame | 5.8–8.1 s/frame (no 60k hair strands) | GNM (fewer features) |

## J. Tests

| Suite | Result |
|---|---|
| `test_gnm_numpy.py` | **26/26** pass: checksum, topology, linearity, pivots, axis-angle convention, eye isolation, 35 cm convergence (3 gazes), deterministic controls, complete/partial blink per eye, L/R independence, lid_follow monotonic, brow_raise, lower face isolation, lid/eye intersection |
| `test_gnm_blend.py` | **19/19** pass: scene loads; positions, faces and UVs bit-identical; tiles; eye pivots; shape keys + bones = GNM (6.4e-8 m); keys present; actions exist and active; frame range; complete and partial blink, up/down gaze in the Timeline; neutral start/end; per-frame keys; render reproducible (0 difference) |
| `tools/verify.py` | **82/82** (unchanged) |
| `expression/check.py` | **51/51** (unchanged) |

Two of my new thresholds were too strict (1e-12 m, below float32), and were set to 1e-7 m with
the measured values printed.

## K. Performance (Apple M5, Metal confirmed in the logs)

| Step | Time |
|---|---|
| Identity fit | 4.9 s |
| Texture bake | 9.3 s |
| Prototype build, including 7 renders at 256 samples | 75 s |
| 7 renders at 256 samples | 6.9–10.9 s each |
| Comparison renders at 128 samples | GNM 5.8–8.1 s, MakeHuman 11.9–12.7 s per frame |

## L. Remaining defects (GNM prototype)

1. No eyebrows, eyelashes or hair geometry. GNM provides none.
2. The skin is smooth and waxy: no pores or normal detail. The bake carries base colour only.
3. The irises look grey/desaturated next to production. The bake carries colour, not the
   production iris shader's glow or depth.
4. **An arc highlight on the GNM cornea in side gaze under production lights.** Likely a
   reflection of the key area light, because the production light linking was built for the
   MakeHuman corneas. Unresolved.
5. The left and right irises are identical: the procedural shader is not seeded per eye.
6. Lid-follow and brow controls are fitted (ridge LS), not artist-validated over the full range.

## M. Recommendation

**Keep MakeHuman as the production and submission model for now. Do not migrate yet.**

**Why not migrate now**
- On facial realism, the GNM prototype is clearly behind (hair, brows, lashes, pores, eye look).
  That is the slides' biggest criterion (60 %).
- It would also reset the whole verified evaluator pipeline.

**Where GNM is clearly better**
- Eye anatomy and eye-joint precision.
- Learned, anatomical blink and squint shapes.
- Most importantly, **the official UV layout the slides require** ("use the GNM or FLAME UV map
  only"; "textures will be directly wrapped around GNM Head Model").

**Evidence-based path**
1. **Ask the organisers** whether the deliverable textures must be in GNM UV space, and whether
   google/GNM v3 is "the GNM head".
2. If yes, use a **hybrid**: keep MakeHuman for the rendered videos and evaluator pipeline, and use
   this phase's proven bake pipeline (MakeHuman → fitted GNM → GNM UDIM) to deliver the 5–10
   texture maps in official GNM UV space, rendered on the GNM head for the "texture variants"
   images.
3. A full GNM migration needs at least defects 1–4 fixed, plus a port of the evaluator wrapper.

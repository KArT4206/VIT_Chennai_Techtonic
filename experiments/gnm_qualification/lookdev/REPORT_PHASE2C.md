# Phase 2C: GNM look development (one appearance prototype)

Branch `phase2/gnm-lookdev` (from `d04d2d8`). All work is in `experiments/gnm_qualification/lookdev/`.
Production `scene.blend`, `wrapper/eyes.py`, `tools/verify.py`, `dist/Techtonic.zip`,
`dist/phase1b/` and the Phase 2A/2B outputs are unchanged (SHA-256 checked).
No texture variants were made.

**Verdict:** the GNM candidate improved substantially but **does not yet match MakeHuman**
under identical conditions. It is **not** ready for production. See N.

## A. Defects and root causes

| # | Defect (Phase 2B comparison renders) | Root cause (verified) | Fix | Verification |
|---|---|---|---|---|
| 1 | Waxy skin | 2K colour only, no micro-normal or roughness map; first lookdev pass also had subsurface weight 1.0 (face rendered lighter and flatter) | 4096² procedural normal/roughness/colour maps; subsurface 1.0 → 0.35 | Full-resolution crops; still somewhat smooth next to MakeHuman (M1) |
| 2 | No pores | None existed. First bake used bump 40 µm → normals tilted only ±2–4° (measured) | Bump 150 µm → mean tilt 12°, 95th percentile 25° | Nose/upper lip pores visible in 2048 crops; cheeks faint (M1) |
| 3 | Repeated detail | n/a (MakeHuman Voronoi is uniform) | 3D object-space procedural, non-periodic, region-weighted | No tiling visible in crops |
| 4 | Grey iris | GNM eye material kept default specular on the iris; production rule is iris specular 0 (it sits in aqueous humour) | Iris/pupil mask from GNM groups → specular 0 | Eye crops: grey veil gone |
| 5 | Identical irises | Production iris shader used one material for both eyes | `iris_material(seed)`: left 11, right 23, same colour zones | mean \|L−R\| 6.2/255 in the iris area |
| 6 | Flat sclera | GNM material had no subsurface or wet coat | Sclera: SSS 0.4 / 2 mm, coat 1.0, IOR 1.336; veins 0.8 → 0.3 | Eye crops |
| 7 | Corneal arc | Isolated per light: arc appears only with the key light. It was the key reflecting off the iris surface (defect 4), not the cornea. A ticked ring also came from the hard Phase 2B cap boundary | Iris specular 0; cornea IOR ramps 1.376 → 1.0 toward the shell's sclera junction (vertex attribute) | Arc gone; ring gone (`renders/iter2+`, comparison) |
| 8 | No eyebrows | GNM has none | Strand brows grown on GNM brow regions | Renders |
| 9 | No eyelashes | GNM has none | Strand lashes on the lid margin with a GNM-measured lid hinge | Renders, blink test |
| 10 | No hair | GNM has none | 60k strands via the production generator on GNM's scalp | Renders |
| 11 | Ear/neck transitions | Phase 2B bake coverage gaps; fixed then. MakeHuman shows a sideburn artefact; GNM shows none | — | Comparison |
| 12 | Wrong skin response | Uniform roughness 0.45, no specular breakup | Region roughness map (T-zone 0.33–0.38, cheeks 0.50, neck 0.55) + pore roughness | Renders |

## B. Texture sources and licences

| Asset | Source | Licence | File | SHA-256 |
|---|---|---|---|---|
| Skin base colour | MakeHuman system assets, `skins/young_caucasian_male/young_lightskinned_male_diffuse.png` (2048², sRGB, colour only) | CC0 1.0 (asset header + upstream `makehumancommunity/makehuman` `LICENSE.ASSETS.md`); commercial use and redistribution allowed | `build/cc0/…png` | `862a26e3…cf12963` |
| Iris / sclera colour | `tools/eye_model.py` procedural shaders (this project) | MIT (ours) | baked | — |
| Hair / brow / lash shaders, hair growth | `tools/hair_strands.py` (this project) | MIT (ours) | — | — |
| eyebrow009, eyelashes01, short04 (MakeHuman) | audited | each explicitly CC0 (Sept 2020 header) | **not used**: they are textured cards, not strands | — |

**Photographic micro-detail:** none was used. The search found only *tiling* CC0/free skin
materials (Share Textures "Human Skin 3" CC0; Sketchfab "Human Materials 1" CC0, 2K seamless;
BlendAtlas CC0, provenance unconfirmed; 3dtextures.me, informal licence; AITextured, commercial
use unverified). None is a licensed face scan, and tiling is what the brief rules out, so none
was downloaded. **All high-frequency skin detail is procedural.** The 2K CC0 colour is resampled,
not upscaled into new detail.

## C. Skin material

Principled BSDF on tile 1001:
- base colour from `skin_albedo` (4096², sRGB);
- roughness from `skin_roughness` (Non-Color);
- normal from `skin_normal` (Non-Color, tangent, UDIM UVs, strength 1.0);
- **Subsurface Weight 0.35**, Radius (1.0, 0.36, 0.20), Scale 1.2 mm;
- IOR 1.40, Specular IOR Level 0.5.

## D. High-frequency detail (`skin_maps.py`)

Region weights come from GNM's groups, smoothed over the mesh: nose, forehead+brows, cheeks,
chin, lids, lips, rest.

**Height bands**
- 3 Voronoi pore fields at 0.40 / 0.60 / 0.85 mm spacing, mixed per region (nose densest and
  deepest, lids 12 %, lips none), with per-pore radius 25–45 % and depth 0.5–1 varied.
- Regional intensity drift.
- Cross-hatched creases (two anisotropic bands, ±35–40°).
- 3 mm undulation.
- Forehead lines (~9 mm, broken by noise) and vertical lip lines.

**Colour**
- Region redness (nose, cheeks), sparse pigment spots, 0.2 mm mottling, slightly darker pores.

**Roughness**
- Region base, pores rougher, low-frequency noise.

Baked at 4096² (about 0.05 mm per texel on the face) in 25 s, 4.4 GB peak memory.

## E–F. Hair, eyebrows, eyelashes (`strands.py`)

**Hair**
- 60,000 strands on GNM skin outside the face mask, ears and neck.
- Production hairline, thinning over 6 mm. No cap mesh, so no cap edge.
- Production growth, clumping and melanin shader.

**Brows**
- 1,100 strands per side on GNM brow regions with a brow profile (half thickness 3.5 → 2.2 mm),
  growing up-and-out medially and out laterally, 8° off the skin, 6–9 mm.
- Attached by UV with "Deform Curves on Surface", so they follow `brow_raise` (+2.26 mm measured).

**Lashes**
- 150 upper and 80 lower per eye on the lid margin. The margin is the innermost skin ring around
  the opening: GNM's skin continues into the socket, so it isn't a mesh boundary.
- Upper lashes 6.5 → 4 mm, forward with a 35° curl; lower 2.8 → 1.7 mm.
- **Lid hinge:** surface deformation only translated the lashes (closed-lid elevation 39° → 43°,
  pointing up). GNM's lid margin moves like a rotation about the eye centre: radius change
  ≤ 0.4 mm, linear in the controls.

  | | blink (per unit) | lid_follow (per unit) |
  |---|---|---|
  | Upper | −24.7° | +7.47° |
  | Lower | +3.4° | +1.6° |

  The lashes are rotated by those amounts through drivers on the shape-key values. Measured
  upper-lash elevation: 33° open → 21° half → 8.5° closed. Roots drop 7.2 mm.

**Iterations**

| Iteration | Problem found | Change |
|---|---|---|
| 3 | Upper lashes invisible (curl sign bug, pointing at the camera) | Fixed the curl sign |
| 4 | Floating lashes above the lid (wrong margin detection) | Innermost-skin-ring margin |
| 5 | Vertical bristles | Forward-dominant exit angle |
| 6–7 | Lashes too long; spikes up in the blink | Shortened; GNM-driven hinge |

## G–H. Eyes

- Two seeded irises baked at 2048² per tile: radial fibres, crypts, collarette, pupillary ruff,
  limbal ring. Iris relief normal maps.
- Sclera: subtle veins, subsurface, wet coat.
- Cornea: refractive only toward its centre, through a smooth IOR ramp.
- GNM topology, UVs and eye joints are unchanged.
- **Limitation:** the production iris colour includes a wide grey limbal haze that still reads as
  a ring at close range (M4).

## I. Comparison (`renders/compare/`, same camera, portrait rig, AgX, 256 samples, 1024²)

Sheets: `sheet_A` (front, three-quarter, eyes, 200 % zoom), `sheet_B` (gaze h−1 / h+1 / v+1 / v−1),
`sheet_C` (blink, half blink), `sheet_eyes_all`. MakeHuman is left, GNM right.

| Aspect | MakeHuman | GNM lookdev |
|---|---|---|
| Skin at 200 % | visible pore relief, warm | brighter (mean face luminance 0.749 vs 0.694), smoother; pores only on the nose and upper lip |
| Eyes | good; catchlight; lashes natural | comparable; clean distinct irises; no veil or arc |
| Brows | full, natural | full, but GNM's brow region gives a high, slightly drawn arch |
| Lashes | natural | follow blink correctly; a few upper lashes still stand up at the lid centre |
| Hair | sideburn/cap artefact in front of the ears | clean short crop, no cap edge |
| Blink | clean | clean; lashes lie down with the lid |
| Noise (RMS, two seeds) | 1.33/255 | 1.27/255 |

## J. Prototype scene

- `gnm_lookdev_strands.blend` (git-ignored, rebuilt by `build_lookdev.py` then `strands.py`).
- Contents: GNM head, rig, shape keys and Timeline from Phase 2B; UDIM texture set; hair, brows,
  lashes; portrait rig.

## K. Performance (Apple M5, Metal confirmed in every log)

| Item | Value |
|---|---|
| Skin bake 4096² × 3 maps | 25 s, 4.4 GB peak |
| Eye bake 2048² × 4 maps | 13 s |
| Comparison renders, 256 samples, 1024² | MakeHuman 21–27 s per view (zoom 2048²: 77 s); GNM 17–19 s per view (zoom: 65 s) |
| Peak memory per comparison run | MakeHuman 13.9 GB, GNM 14.1 GB (GNM 7.3 GB resident) |
| Texture memory | skin 3 × 4096² + eyes 2 × 2 × 2048² |

## L. Tests

| Suite | Result |
|---|---|
| `test_lookdev.py` | **21/21** |
| Phase 2B `test_gnm_numpy.py` | **26/26** |
| Phase 2B `test_gnm_blend.py` | **19/19** |
| `tools/verify.py` | **82/82** |
| Phase 1B `check.py` | **51/51** |

`test_lookdev.py` covers:
- topology, UVs and regions bit-identical;
- rig and keys = GNM (6.4e-8 m);
- texture tiles and colour spaces;
- 4096 skin maps; distinct 2048 irises;
- 60k / 2,200 / 460 strands;
- brow attachment; lash hinge with 4 drivers;
- lashes move with the blink;
- no lash shaft inside the eye in 5 poses;
- lash roots within GNM's own skin contact;
- brows follow the raise;
- render reproducibility.

**Three lookdev test criteria were changed after a first failure, for stated reasons:**
1. **Lash attachment:** the method changed (surface deform → hinge). The test now checks the hinge.
2. **Eye volume:** the 5 "inside" points were all lash roots, ≤ 0.2 mm, lying on GNM's lid skin,
   which itself touches the shell by ≤ 0.31 mm (Phase 2B). The test now requires zero shaft points
   inside and roots within 0.31 mm.
3. **Reproducibility:** 3–8 of 36,864 pixels differ by 1/255, even with all strands hidden. That
   is GPU nondeterminism (random-walk subsurface) at 8-bit rounding. The test is now "≤ 1/255 on
   < 0.1 % of pixels".

## M. Outstanding visual defects

1. Skin reads brighter and smoother than MakeHuman. Cheek pores are faint under soft light.
   Purely procedural micro-detail has no photographic source.
2. The brow shape follows GNM's high brow region and looks slightly drawn.
3. A few upper lashes at the lid centre stand up. Lash count and length are not fully natural.
4. The grey limbal haze from the production iris reads as a ring at close range.
5. The CC0 base colour is 2K: there is no real colour detail below about 0.2 mm.

## N. Assessment

**GNM is not yet suitable for production.**

**Improved:** the eye system is now comparable to MakeHuman, with distinct irises, correct
cornea, sclera and catchlights, and lashes that follow the blink. The hair is cleaner than
MakeHuman's. Topology, UVs and controls are verified unchanged.

**Not achieved:** the success threshold ("outperform or at least compete") **is not met on skin**,
the most visible area and the slides' 60 % criterion. The skin is lighter and less detailed than
MakeHuman's under identical light, and the brows and lashes still need artistic refinement.

**Recommendation:** keep MakeHuman for production. If GNM UVs are required, the hybrid route from
Phase 2B remains the safest. Closing the gap needs a licensed photographic skin source (for
example a commercial face scan with redistribution rights) or more lookdev time on the skin
shading and brow shaping.

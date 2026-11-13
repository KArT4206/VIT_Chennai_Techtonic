# Phase 2D (experimental): expression-driven wrinkles and colour, after Adam Spring's FACS workflow

Reference: Adam Spring, "FACS Rigging & Texture Blending — Digital Humans", 25 May 2020
(adamspring.co.uk). Used as **method only**. None of its scans, project files or textures were used.
The article's scans came from Ten24 via the 3D Scan Store, and it states no licence terms for them.

**3D Scan Store asset:** none exists on this machine (searched by name and Spotlight), and this
project has no record of a permission. **No scan data was used.** If you hold such an asset and a
licence, its scope still needs documenting before it is used.

Everything is in `experiments/gnm_qualification/lookdev/wrinkles/`. GNM topology, UVs, the 7 UDIM
regions and the eye joints are unchanged (tested). The production files and every earlier phase's
outputs are unchanged (hashes).

## 1. The article's workflow, as applied

| Article | Here |
|---|---|
| Neutral first, frozen before rigging | `baseline_v1/`: skin albedo / normal / roughness / height (4096²) + eye maps, SHA-256 in `SHA256SUMS` |
| Blend shapes from FACS scans, muscle groups | GNM's own learned controls (Phase 2B): blink, squint (semantic), brow raise (fitted), plus **brow lowerer** = semantic DISGUST eye blocks (closest GNM label to AU4; see 3) |
| Expression displacement baked per wrinkle expression | Expression height = neutral height + creases **derived from that expression's measured GNM skin compression** (no scans available) |
| **Subtract neutral from each expression map** to avoid a "multiplied effect" | delta = expression height − neutral height, per texel. **Verified: delta is exactly 0.0 outside every mask** |
| Masks driven by blend-shape weight | Compression-derived masks (smoothstep of measured compression), left/right channels, scaled by the key weight |
| Composite: neutral + Σ weighted deltas + tertiary | Neutral normal map (once) → Bump(Σ w·delta) → BSDF; tertiary pores stay in the neutral map |
| Expression colour maps (blood flow) | Mask × weight × small tint per expression |
| Linear weight → texture link (author's comment) | Linear drivers from shape keys |
| Corrective shapes | Combination correctives solved or fitted on GNM geometry (section 6) |

## 2. Neutral baseline (`baseline_v1/`)

The Phase 2C maps, frozen with checksums, plus `skin_height.1001.exr`: the neutral micro-relief
height, in the same units as the bump input (× 0.15 mm), stored as float so negative values survive.
**If the neutral geometry or maps change, `strain.py` → `bake_wrinkles.py` must be re-run.**

## 3. Expressions and measured deformation (`strain.py`)

For each skin triangle, the deformation gradient from neutral to expression gives principal
stretches. Compression = 1 − λmin. The direction comes from an area-weighted structure tensor,
diffused over the mesh.

| Expression | Control | Max displacement | Max compression | Folds (from the strain field) |
|---|---|---|---|---|
| blink | blink L+R | 7.9 mm | 75 % (lids) | concentric lid creases |
| squint | semantic SQUINT eye blocks | 4.3 mm | 48 % | crow's feet at the outer corners, nose-bridge lines |
| brow raise | brow_raise × 6.6 (3 mm) | 4.1 mm | 12.5 % (forehead) | horizontal forehead lines |
| brow lowerer | DISGUST eye blocks | 3.8 mm (×1.5) | 25 % | **horizontal procerus lines** across the nose bridge |

**Brow lowerer vs "furrow":** no GNM label is a pure AU4. DISGUST's eye blocks lower the inner brows
(1.15 mm) and draw them together (1.21 mm). Its measured compression is mainly vertical, so the
derived lines are horizontal (procerus), not the vertical "11" glabellar lines. The maps follow the
deformation. Vertical 11s would need a deformation GNM's labels don't produce, so they were not
painted in.

**Correction made during the phase:** `brow_raise` is 0.45 mm per unit, not 1 mm. The first strain
run used 1.35 mm; it was re-run at 6.6 units (3 mm).

## 4. Wrinkle maps (`bake_wrinkles.py`)

The crease profile is thin valleys, f = −max(cos s, 0)^6, broken into lengths by low-frequency noise,
with s = 2π φ / spacing.

| Expression | Spacing | Amplitude | Mask (compression c0–c1) |
|---|---|---|---|
| blink | 1.2 mm | 0.60 | 0.04–0.35 |
| squint | 2.0 mm | 0.85 | 0.03–0.30 |
| brow raise | 4.5 mm | 1.00 | 0.02–0.12 |
| brow lowerer | 2.8 mm | 1.00 | 0.03–0.22 |

Amplitude is in height units (× 0.15 mm) — physically under 0.15 mm.

**Two defects found in the first bake and fixed:**
1. *Speckled noise instead of creases:* per-vertex directions are sign-ambiguous and noisy.
   → Fixed with structure-tensor diffusion.
2. *Closed contour rings on the forehead:* the phase P·d, with d varying in space, draws level sets.
   → The phase φ is now solved by least squares so that ∇φ follows the fold direction over the mesh
   edges (relative residual 0.09 for the forehead; ≈ 0.4 around the eyes, where the field is radial
   and the stripes become concentric, as lid creases are).

**Packed outputs:** 2 delta + 2 mask RGBA half-float EXRs at 2048²
(`packed_delta_A` = blink L/R, squint L/R; `_B` = brow raise L/R, brow lowerer L/R). That's 1.7 MB on
disk. The finest crease (1.2 mm) is still at least 12 texels at 2048.

## 5. Shader system (`wrinkle_material.py`, node group `GNM_ExpressionWrinkles`)

**Inputs:** Normal (neutral normal map), Albedo, Strength, and 8 weights (4 expressions × L/R).

**Computation**
- height = Strength · Σ w · delta, from the packed channels;
- Normal = Bump(height, 0.15 mm, base = neutral normal);
- Albedo = albedo · (1 + Strength · Σ w · mask · tint).

The neutral relief enters once, through the neutral normal map; the deltas never contain it.

**Tints**

| Expression | Red | Green, blue |
|---|---|---|
| squint | +3 % | −1 % |
| brow lowerer | +4 % | −1.5 % |
| brow raise | −1 % (stretch blanching) | — |
| blink | none | none |

**Drivers (on the material):**
- weight = key value;
- brow raise: × 2/3, because the key 1.0 = 2 mm and the maps are baked at 3 mm.

**Size:** 4 texture samples, 55 math nodes, 8 drivers.

## 6. Combinations and correctives (`correctives.py`, `solve_correctives.py`, `fit_corrective.py`)

Linear addition does **not** always give anatomically valid results. Measured on exact GNM geometry:

| Combination | Linear result | Action | After |
|---|---|---|---|
| blink + up 12° | closed **only because** the engine scales lid_follow by (1 − blink); without it, 2.28 mm gap | rule confirmed necessary | gap ≤ 0.15 mm |
| blink + down 7° | closed | — | — |
| blink + 3 mm brow raise | **0.27 mm gap** (raise lifts the lid) | corrective key `corr_blink_raise` = +0.02 blink, driven blink · min(raise/1.5, 1) | gap 0.11 mm |
| brow lowerer ×1.5 alone | **0.48 mm lid/eye contact** | **cap the key at 0.67** (= ×1.0 DISGUST: 0.31 mm, GNM's own limit) | ≤ 0.31 mm |
| blink + lowerer | 0.39–0.40 mm contact; reducing the blink doesn't help | **fitted corrective** in GNM's eye-block space (λ 1e-6, coefficients ≤ 0.35) pushing 14–16 lid vertices out to 0.05 mm clearance; `corr_blink_lowerer` driven blink · min(lowerer/0.67, 1) | 0.23 / 0.12 mm, still closed, ≤ 0.14 mm movement outside orbit/brow |
| squint + side 15° | OK (0.22 mm) | — | — |
| brow raise + up 12° | OK | — | — |
| half blink + side 15° | **0.39 mm** | found: −0.2 blink at 15° → 0.31 mm. **Not implemented** (needs a gaze-driven driver) | recommendation |
| half blink + up 12° | 0.38 mm (with (1 − blink)), 0.29 mm without | lid_follow · (1 − blink³) is the best tested: 0.32 / 0.30 mm. **Not implemented** (Phase 2B engine left unchanged) | 0.01 mm over, recommendation |

## 7. Performance (Apple M5, Metal confirmed in the logs)

| Item | Value |
|---|---|
| Strain + phase solve | ~1 min (CPU) |
| Wrinkle bake | 65 s, 6.8 GB peak resident |
| Render, same frame (squint, 1024², 128 samples), node group **on vs bypassed** | 8.06 s vs 7.50 s → **+7.5 %** |
| Extra texture memory | 4 × 2048² RGBA float ≈ **256 MB** (loaded as float32) |
| Validation renders | 1024²: 12.5–16.0 s; 2048²: 49–53 s; peak footprint 16.4 GB |
| UDIM maps | skin uses 3 neutral (4096²) + 4 wrinkle (2048²) |

**Visibility vs cost (important):** at the eye close-up the wrinkle maps change the image by only
**0.03–0.39/255 on average** (geometry-only vs combined), and the competition camera (40 cm, full
face) is farther still. The learned GNM geometry carries almost all of the visible expression. The
fine creases are visible only at 200 %. For the competition the maps are **not worth their cost**
unless close-ups are delivered. If kept, blink and squint are the only ones with visible effect.

## 8. Visual validation (`renders/`, `sheet_100.png`, `sheet_200.png`)

`sheet_100.png` has one row per state (neutral, blink, squint, brow raise, brow lowerer,
blink + up gaze, squint + side gaze), each as geometry-only | texture-only | combined. `sheet_200.png`
shows the combined state at 200 % for neutral, blink, squint and brow lowerer.

| Check | Result |
|---|---|
| Double wrinkles | none seen: the neutral relief appears once |
| Popping | none: a 5-step squint sweep changes 2.81–2.86/255 per step, smooth |
| Seams | none seen at 100 % or 200 % |
| Wrinkle directions | follow measured compression: concentric lid creases, crow's feet, horizontal forehead and procerus lines |
| Displacement | modest by design; arguably too subtle to read at 100 % |
| Colour | subtle, confined to masks |
| Unwanted change outside masks | delta and mask are exactly 0 outside the masks |

**Defects seen at 200 % that are not part of this phase** (Phase 2C lashes):
- lower lashes look like scattered stubble below the lid;
- upper lashes clump;
- closed-lid lashes look pale.

## 9. Tests (`test_wrinkles.py`)

**18/18 pass:**
- GNM positions, faces and UVs unchanged;
- rig and original keys still reproduce GNM (6.4e-8 m);
- for each expression, delta == expression − neutral, and delta == 0 outside its mask (8 checks);
- drivers map key values to weights;
- corrective drivers evaluate correctly;
- the brow-lowerer cap;
- the saved scene rests at neutral;
- the node group's baked Height equals Σ w·delta for 5 simultaneous weights (p99 error 0.0004);
- all weights 0 renders identical to the neutral material (≤ 1/255);
- deterministic rendering;
- no popping.

**Regressions:** all pass — Phase 2C 21, Phase 2B 26 + 19, `verify.py` 82, Phase 1B 51.

**Test fixes during the phase (reasons):**
- The cap check compared float32 0.67000008 with 0.67 exactly — a test bug.
- The first run found the saved scene had **brow-lowerer keys stuck at 0.67**, leaking a lowerer and
  a corrective into every pose. This was a real scene defect, fixed by saving a neutral rest state,
  and is now a test. The rest check allows the Phase 2B Timeline's frame-1 values (≤ 0.01) on the
  keys that action animates.

## 10. Acceptance criteria

| Criterion | Result |
|---|---|
| Neutral when all weights are zero | met (render-identical within one 8-bit step) |
| Individual blending | met (validation renders) |
| Simultaneous blending | met (Σ verified numerically; combination renders) |
| Neutral not added twice | met (delta = 0 outside masks; neutral enters once) |
| GNM UVs preserved | met (bit-identical) |
| No popping | met |
| No visible seams | met (visual) |
| Anatomically plausible wrinkles | **partly**: directions follow measured strain; the lowerer gives procerus, not vertical 11s; amplitude very subtle |
| Deterministic | met (≤ 1/255 on < 0.1 % of pixels; GPU subsurface) |
| Eye animation compatible | met (rig = GNM; correctives driven; Timeline intact) |

## 11. Limitations

- No photographic or scanned wrinkle data: the creases are generated from measured GNM deformation.
- The wrinkles are nearly invisible at the competition camera distance.
- Two combination correctives (half blink + side gaze, half blink + up gaze) are only recommended,
  not implemented.
- The brow lowerer is not a true corrugator furrow.

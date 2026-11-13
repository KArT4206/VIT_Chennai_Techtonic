# Real photogrammetry head: 3D Scan Store Free HD Head, imported, rendered and carried onto GNM

Everything is experimental and separate from production. `scene.blend`, `wrapper/eyes.py`,
`tools/verify.py`, `dist/Techtonic.zip` and `dist/phase1b/` are unchanged (SHA-256 checked). No
asset file, derived map, scene or render from this scan is committed (see
`3dscanstore/LICENCE_RECORD.md`).

## 1. Source files: downloaded, imported, rendered

| Item | Status |
|---|---|
| `3D_ScanStore_Free+Head.zip` (2,019,571,774 B, SHA-256 `9aa6a036…cfe7`) | Supplied by the user from their browser download; integrity OK; copied unchanged to `3dscanstore/original/`; extracted to `3dscanstore/extracted/` (72 files, per-file SHA-256 in `MANIFEST_SHA256.txt`) |
| Automated download | HTTP 403 for plain requests; the kit's spoofed-browser request was **not** used |
| Google GNM v3 weights / code | Reused from Phase 2A (checksum `61d78bbf…` = published) |

**Asset inventory (inspected, not assumed)**

| Component | Files | Facts |
|---|---|---|
| Head | `OBJ/Head.obj`, `FBX/Head.fbx`, `ZTL/Head.ztl` (1.26 GB, 7 subdivision levels, not opened) | 12,466 v, 12,410 quads, UV `DiffuseUV` |
| Face maps | `Face_Albedo`, `Face_Normal`, `Face_Roughness`, `Face_Specular` (JPG + TGA) | 8192², 8-bit |
| Displacement | `Face_Displacement.tif` | 8192², 16-bit, 1 channel |
| Layered albedo | `Face_Albedo_Makeup_Layer.psd` | 8192² |
| Masks | micro normal (3965²), details, scatter, eye wet, eyeball SSS | — |
| Eyes | `Realtime Eyeball L/R`, `Lens L/R` (cornea) | 1,666 v each; spheres r 15.3–15.5 mm; 4K eyeball maps, 8K lens normal; **one eyeball texture for both eyes** |
| Tear line | `Eye Wet` | 478 v |
| Brows / lashes | `Brows` (121,586 v), `Lashes` (50,120 v) | Mesh strands, **no UVs** |
| Teeth / tongue | `Teeth` (9,846 v, FBX only), `Tongue` (933 v / 912 f, FBX only) | — |
| Scenes | `Blender Scene.blend` (Blender 3.2, cm scale, Cycles, Filmic, HDRI, area light, 3 cameras), Marmoset 4 scene (not opened) | — |
| Licence file in the archive | **none** | — |

## 2. Licence

See `3dscanstore/LICENCE_RECORD.md`.
- The public page says **"Personal use only"**.
- The user reports the vendor granted permission, but the **written permission is not yet on file**.
- Modification, baking, demonstration to judges and redistribution are **unconfirmed**.
- The asset and everything derived from it are kept local and git-ignored, and are not for the
  submission ZIP.

## 3. Original appearance: the actual scan with its original textures

The vendor's own `Blender Scene.blend` was opened with auto-run scripts disabled. Its original
geometry, materials, 8K maps, HDRI and light are unchanged. Only these render settings changed:
Metal GPU, 4096 → 256 samples, plus added cameras. A copy is saved as `3dscanstore/build/scan_original.blend`.

Renders in `renders/scan_original/`:

| Render | Time |
|---|---|
| Full-face portrait | 24.6 s |
| Three-quarter | 21.4 s |
| Eye close-up | 29.2 s |
| Skin close-up (2048²) | 97.4 s |
| Brows and lashes | 25.5 s |
| Vendor "Full Shot" | 12.0 s |
| Vendor "Eyes Shot" | 13.7 s |

Peak memory was 19.6 GB, and the vendor file is byte-identical after the run.

## 4. GNM compatibility: the key finding

**The scan's head mesh is GNM topology.**
- **Faces:** its 12,410 quads have the same order and vertex numbering as GNM's skin tile 1001.
- **UVs:** its UVs equal GNM's 1001 UDIM coordinates to 3e-8.
- **Frame:** its OBJ coordinates are in GNM's frame (Y up, metres).
- **Consequence:** the scan's original 8K face maps **are already exact GNM-1001 textures**. Projection
  or re-baking would only add resampling error, so the original maps are used directly on GNM's
  untouched UVs. That is the geometrically exact transfer for this asset.

**Shape vs GNM's parameter space** (`scan_to_gnm.py`, exact correspondences, linear least squares)

| Fit | Median residual | Max residual | Largest coefficient |
|---|---|---|---|
| Plausible (λ 1e-7) | 3.2 mm | 28 mm | 3.4 |
| Unregularised | 2.5 mm | — | 21 (implausible) |

So GNM identity cannot reproduce this real face. **The scan's own vertex positions are used as the
GNM base shape** (same topology), with GNM's controls on top.

**Eyes:** the scan's eyeballs are not GNM topology. Their spheres have r 15.3 mm (GNM 14.5) and sit
**3.6 mm** from where the identity fit would put GNM's eye joints. The scan's resting gaze is about
8.5° outward.

**Brows and lashes:** no UVs, so a UV transfer is not possible. The original meshes are used, bound
to the GNM surface.

## 5. Appearance-transfer prototype (`3dscanstore/build/gnm_scan.blend`, built by `build_gnm_scan.py`)

The prototype is built inside a copy of the vendor scene, so cameras, HDRI and light are identical.
**GNM_Head** keeps GNM's 17,821 vertices, face order, **bit-identical** UDIM UVs, 7 regions and the
4-joint rig (all verified).

| Part | How |
|---|---|
| Skin shape | Basis = scan positions (verified to 1.5e-8 m). Teeth/tongue = GNM identity fitted to the scan |
| Skin appearance | **The vendor's original skin material and 8K maps** (albedo, normal, roughness, specular, micro normal, scatter) on tile 1001 |
| Eyes | GNM eye meshes moved to the scan eyeball centres and scaled ×1.055 / ×1.059; eye bones at the scan centres (0.000 mm); GNM rig and gaze code unchanged |
| Iris / sclera | **The scan's photographic eyeball colour, baked** onto GNM 1002/1004 UVs (geometry-aware, each corneal axis aligned to GNM's gaze axis); iris specular 0; smooth-IOR cornea |
| Brows, lashes, tear line | **Vendor's original meshes and materials**, bound to GNM_Head by Surface Deform: they follow blink and brow |
| Expression controls | **Re-fitted on the scan's lids** (`scan_controls.py`, Phase 2B method): GNM-template blink left a 1.2–2.3 mm gap; re-fitted blink closes to ≤ 0.15 mm with lid contact 0.29 / 0.13 mm (limit 0.31), other eye 0.000 mm |

**Defects found and fixed while building**
- The eye bake was black three times:
  1. The vendor eyeball material is 100 % subsurface, so a DIFFUSE colour bake reads black.
  2. Selected-to-active baking found no hits with the vendor's ×100 object scale and a shape-keyed
     target. Isolated tests: 0 texels on GPU and CPU, with a red emitter, and with a fresh sphere;
     43,700 texels once scales were applied.
  Fixed on temporary bake objects only.
- The first control re-fit measured scan margins on template geometry ("other eye moved 0.999 mm").
  Fixed by evaluating shapes as scan base + GNM offset.

## 6. Scan vs GNM (`renders/compare/`, identical cameras / light / 256 samples, Metal confirmed)

| View | Mean \|scan − GNM\| |
|---|---|
| Full face | 0.30/255 |
| Three-quarter | 0.33/255 |
| Vendor full shot | 0.27/255 |
| Eye close-up | 0.70/255 |
| Vendor eye shot | 0.60/255 |
| Brows and lashes | 0.87/255 |
| Skin close-up 2048² | 3.2/255 |

The GNM version is visually near-identical: the same pores, freckles, mole and lip texture. The
visible differences are in the eyes: GNM converges on the 35 cm target while the scan rests
diverged, and the iris and pupil read slightly glossier.

**GNM expression tests** (`sheet_gnm_expressions.png`): blink, half blink, look left, right, up and
down all work through the verified controls. Each frame takes 24.6 s; comparison runs peak at
21.8 GB.

## 7. Outstanding issues

1. A **pinkish patch at the inner-corner sclera at 15° side gaze**: the baked scan texture's
   conjunctival edge becomes visible on the larger, rotating GNM eye.
2. Left and right irises are identical (the vendor ships one eye texture).
3. The scan's 16-bit 8K displacement and the 7-level ZTL are not used yet. Rendering uses normal
   maps on a level-2 subdivided GNM head, which is the main source of the 3.2/255 skin difference.
4. Squint, surprise and brow-raise offsets were re-fitted on the scan, but only blink and gaze were
   render-tested.
5. **The licence scope blocks any submission use until written permission covers it.**

## 8. Recommendation

This is the strongest result so far. A real scanned person, on official GNM topology with
bit-identical GNM UVs, rendered with the original 8K maps, animated by the verified GNM eye and lid
controls. It is visually far beyond the MakeHuman and procedural GNM heads.

Before it can become the competition model:
- get the vendor's written permission covering modification, baking, judge demonstration and the
  submission ZIP;
- fix the inner-corner sclera patch;
- port the evaluator wrapper to the GNM rig.

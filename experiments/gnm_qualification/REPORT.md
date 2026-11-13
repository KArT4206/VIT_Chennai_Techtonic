# GNM Head v3 qualification (Phase 2A)

Isolated experiment. The MakeHuman project (`scene.blend`, `wrapper/`, `expression/`,
`dist/`) is untouched.

## Source and licence (verified)

| Item | Value |
|---|---|
| Code | github.com/google/GNM, commit `f84cdbdc86a34f55627526f137495f864e687679` (2026-11-13), **Apache-2.0** (LICENSE file and GitHub licence field) |
| Weights | huggingface.co/google/gnm-v3, repo sha `c01e90d2…`, `v3_0/gnm_head.npz`. Public, **not gated**, model card `license: apache-2.0` |
| File | 53,328,601 bytes, SHA-256 `61d78bbfb4ad8e0b38495804a4caef3214d3df00f8c3f68761e63b41ce3747eb`, matches the publisher's `v3_0/checksums.sha256` |
| Model | GNM Head, version 3.0, variant head |
| Technical report | arXiv 2607.23687 |

Apache-2.0 allows redistribution with the licence and a NOTICE. Even so, the weights, the
vendor clone and the derived `.blend` file are git-ignored here, until we decide what ships.

The repository does not mention a "GNM Head Editor". Whether this is the hackathon's GNM is
**not** established and needs organiser confirmation.

## Environment

- `env/`: uv-managed Python 3.13.14. Packages: numpy, absl-py, etils, immutabledict, jaxtyping
  and typing_extensions (plus wadler-lindig, a jaxtyping dependency).
- GNM is used from the vendor clone via `PYTHONPATH`; it is not pip-installed.
- No TensorFlow, JAX or PyTorch. The NumPy backend does not need them; only the semantic
  sampler does (TensorFlow).
- Blender's Python and the system Python are unchanged.

## Topology (`inspect_gnm.py`, `report/gnm_inspection.json`)

**Mesh**
- 17,821 vertices; 17,662 quads (0 degenerate; all vertices used); 35,324 triangles.
- Triangles are GNM's own ordered split: all quads' corners (0,1,2), then all quads'
  (2,3,0). Every triangle-corner UV equals its quad-corner UV (0 differences).

**Frame**
- Metres, **Y up**, face looks **+Z**, subject's left at **+X**.
- Bounding box: x −0.128..0.128, y 0.066..0.407, z −0.092..0.147.

**Components and groups**
- Mesh components: skin, left_eye, right_eye, upper_teeth_and_gums, lower_teeth_and_gums,
  tongue.
- 46 vertex groups, including eye_interiors, eye_exteriors, scleras, irises, pupils,
  eye_sockets and per-region groups (brow, orbital, infraorbital, …).

**Parameters**
- Identity: 253 = 170 head + 3 eyes + 80 teeth.
- Expression: 383 = 100 left-eye region + 100 right-eye region + 150 lower face
  + 32 tongue + 1 pupils.

**Joints**
- 4 joints: neck → head → {left_eye, right_eye}, axis-angle rotations, plus global
  translation.

## UV / UDIM

Face-corner arrays: `quad_uvs_udim [Q,4,2]`, `triangle_uvs_udim [T,3,2]`. Results:
- 0 NaN.
- 0 corners outside their own tile.
- 0 faces straddling tiles.
- `quad_udim_tiles` matches the tile computed from the UVs (0 mismatches).
- All faces have positive UV winding, in every tile.
- 614 seam vertices (vertices with more than one UV), which is expected.

| Tile | Quads | Content (vertex-group check) |
|---|---|---|
| 1001 | 12,410 | skin (100 % skin) |
| 1002 | 372 | left_eye ∩ eye_interiors: sclera 62 %, iris 38 %, pupil 13 % |
| 1003 | 384 | left_eye ∩ eye_exteriors (cornea) |
| 1004 | 372 | right_eye ∩ eye_interiors |
| 1005 | 384 | right_eye ∩ eye_exteriors (cornea) |
| 1006 | 2,828 | teeth and gums |
| 1007 | 912 | tongue |

All seven tiles match the documentation.

## Eyes and joints

- Each eye joint sits exactly at its sclera-sphere centre (0.000 mm offset; radius 14.5 mm;
  fit RMS 0.064 mm).
- All 771 vertices of each eye are weighted 1.0 to their own joint only. No other vertex uses
  the eye joints.
- Rotating `left_eye` by 15° moves only those 771 vertices, rigidly (pairwise error around
  1e-17 m). Lids and skin don't move, and pose correctives add no lid coupling.
- Primary gaze (joint → pupil) is (0.001, −0.006, 1.000), i.e. +Z. Our MakeHuman eyes rest
  8° down and 3.4° outwards, so GNM's reset rotation would be about 0°.
- `pupils_000` dilates the pupil: it moves only iris/pupil vertices, up to 1.7 mm at +2.
- **Lids and brows have no joints.** They are 100 PCA components per eye region, and the top
  components move mainly the orbital, brow and forehead regions. The semantic sampler offers
  `WINK_LEFT`, `WINK_RIGHT`, `SQUINT` and `SURPRISE`, but it needs TensorFlow (not installed).

## Blender prototype (`export_gnm.py` → `build_blend.py` → `gnm_head_test.blend`)

- Direct mesh construction (no OBJ/FBX round trip). Read-back verification:
  - positions bit-exact (0.0 error);
  - face order and corner order identical;
  - UDIM and legacy UV layers bit-exact;
  - material index = tile − 1001;
  - all 46 groups present, eye groups identical.
- The Y-up → Z-up change is an object transform (+90° X), so vertex data stays unchanged and
  the face looks −Y, like the MakeHuman scene.
- 4-bone armature at GNM's joints, with GNM skinning weights as vertex groups.
- The UDIM checker is a real 7-tile tiled image (`textures/checker.<UDIM>.png`), packed into
  the `.blend`.

## Renders (`render_gnm.py`, Cycles, Metal GPU confirmed in the log, 1024×1024)

- `clay_front.png`, `clay_three_quarter.png`: clean face, sockets, ears and neck.
- `clay_eyes_rotated.png`: the eye bones are posed. The clay corneas are uniform grey, so the
  rotation does not show; it is proven numerically above.
- `uv_checker_front.png`: tiles 1001, 1003 and 1005.
- `uv_checker_no_skin.png`: tiles 1003, 1005 and 1006.
- `uv_checker_eye_interiors.png`: tiles 1004 (image left) and 1002 (image right); digits upright.
- `uv_checker_tongue.png`: tile 1007.

## Integration with the Phase 1B engine

**Reusable unchanged**
- `motion.py`: seeded saccades, drift, pursuit, blink timing, brows.
- The `check.py` structure and the video pipeline.

**Easier with GNM**
- Each eye joint sits exactly at its eyeball centre and rests looking along +Z, so
  `eyes.py`'s shortest-arc rotation applies directly, and the reset rotation would be about 0°.

**Needs new work**
- *Lids and brows.* Map blink, gaze-following lid and brow raise to directions in the 383-D
  expression space. Either use the semantic sampler (`WINK_*`, `SURPRISE`; needs TensorFlow),
  or fit linear directions by least squares against lid and brow target displacements. Bake
  them as Blender shape keys, a few named keys rather than all 383.
- *Lid / cornea contact.* Recheck with GNM's own lids, reusing the Phase 1B gate.
- *eyes.py on GNM.* Needs a GNM scene (bones `left_eye`/`right_eye` instead of `eye.L`/`eye.R`,
  new lid controls). The evaluator wrapper and `scene.blend` would only change on a decision
  to migrate.

## Texture pipeline (designed, not built)

- **1001 skin:** a CC0 or licensed photographic face scan, baked onto the GNM 1001 UVs with
  Blender's selected-to-active bake. Base colour, roughness and normal/displacement; 4K tiles.
- **1002 / 1004 eye interiors:** separate left and right iris maps, sclera veins.
- **1003 / 1005 corneas:** transparent, refractive (IOR 1.376) and specular, so only roughness
  and normal maps are needed.
- **1006 / 1007 teeth and tongue:** low priority.
- **Seams:** bake with margin padding, then check the 614 seam vertices for discontinuities.
- **Proven:** UDIM tile images can be assigned and rendered (the checker).
- **Not yet proven:** a real photographic texture set (needs a licensed source).

## Risks and open questions

1. It is unconfirmed that google/GNM is the hackathon's "GNM Head Editor". The slides' UV
   maps must "wrap directly around the GNM head model", so the exact model and version matter.
2. No GNM texture assets are supplied (the checker is ours). A licensed photographic skin
   source is still needed.
3. Lid, blink and brow controls are PCA components. Semantic control needs fitting or TF.
4. GNM has no eyelashes, eyebrows or hair geometry, and the MakeHuman scene's realism relies
   on them.
5. A migration would invalidate the Phase 1A/1B outputs: renders, metadata, videos and the
   83/51 baselines.

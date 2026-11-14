# Phase 2M.2: Studio UI refinement and Character Asset Manager

- **Branch:** `showcase/interactive-studio` (worktree `~/Desktop/Projects/SyntheticEyes-Track1-showcase`), built on `d28f5d3`.
- **Release untouched:** `release/makehuman-submission` is still at `4a2f56b`, and `dist/Techtonic.zip` is unchanged (SHA-256 `91f4bafe…`).
- **Not done:** no character imported, no facial rigging, and no animation or thumbnail created.

## Start

```bash
cd ~/Desktop/Projects/SyntheticEyes-Track1-showcase/showcase-web
npm install && npm run build && npm start      # http://localhost:3000
```

## What changed

1. **Studio empty state.** The wireframe sphere and rings are gone. The viewport shows an empty stage
   (floor grid only) and a card:
   - **"No character loaded"**, with an explanation that no real character is loaded and nothing is
     animated;
   - a three-step readiness list: file imported, compatibility passed, clips connected;
   - an **Import character** button, linking to Character & Assets.

   When a file is stored but not connected, the card names it and states its verdict honestly.
2. **Disabled playback.** While no real clip is available, Play, Pause and Replay are grey, dashed, show
   a lock icon and have no hover effect. They carry `disabled` and `aria-disabled`, and a tooltip gives
   the reason. The old look (a dimmed gold button) still looked half-active. Play now spans the full
   row. Return to neutral stays enabled.
3. **Character & Assets page** (`/assets`):
   - **Import:** drag-and-drop or browse.
   - **Supported formats:** `.glb` recommended; `.gltf` only with embedded data; `.blend` refused with an
     explanation.
   - **Status card:** file, compatibility, clips matched out of 60, licence, studio connection.
   - **Static three.js preview:** shows a loaded / failed status; no animation is played.
   - **Report tabs:** checks, textures, facial rig (eyes and bones), shape keys, animations, meshes.
   - **Licence and source record:** source, author, licence, URL, notes, and a "written permission"
     confirmation.
   - **Replace and Remove:** both need an explicit confirmation step. Replacing is staged: the current
     file stays until "Confirm replace".
   - **Storage:** a **separate** IndexedDB database (`facial-expression-studio-assets`), so the content
     database is unchanged.
4. **Settings & Export page** (`/settings`):
   - default camera, playback speed and default intensity (the Studio applies them on open);
   - animation quality: Low, Medium or High, which sets pixel ratio and antialiasing;
   - content language;
   - backup and restore: content backup download, character file download, and restore through the
     same reviewed import;
   - configuration export and import: settings only. The 60 IDs are listed in the export for
     documentation but never imported. Invalid values are rejected and listed.
5. **Navigation:** Studio · Content Manager · Character & Assets · Settings & Export.
6. **Compatibility validator** (`src/lib/assets/gltf-inspect.ts`). It reads the GLB/glTF container and
   JSON directly, and each check reports pass, warning, fail or info, with evidence:
   - **File container:** glTF 2.0; truncated or invalid files and `.blend` are refused.
   - **Embedded resources:** an external URI fails; unsupported required extensions fail.
   - **Head mesh:** named "Head" or "Face"; it must deform through morphs or skinning.
   - **UV maps:** the head needs `TEXCOORD_0`.
   - **Materials and textures:** a colour and a normal map on the head material; full texture
     inventory with sizes and usage.
   - **Armature and bone hierarchy:** parents, and facial joint names.
   - **Morph targets:** count and names (`extras.targetNames`).
   - **Eye objects and pivots:** the pivot-to-centre offset is measured in mm, and it fails when off
     centre. Eye bones get a warning, because their pivot can't be verified statically.
   - **Facial animation clips:** each clip's channels are classified as morph, facial bone or other.
     A clip matches an expression only by exact ID name.

   **Verdict:**
   - "Not compatible" if any check fails.
   - "Partially ready" if there are only warnings.
   - "Structurally ready" only if every check passes **and** all 60 expressions have facial clips. Even
     then, the text says visual quality still needs a human review.

   A file that merely loads is never called compatible.
7. **Blender export pipeline:** `docs/BLENDER_TO_GLTF.md`, also served at `/docs/BLENDER_TO_GLTF.md` and
   linked from the page. It covers:
   - naming: Head, Eye_L and Eye_R with pivots at the eyeball centre;
   - shape keys: names, L/R splits, baking drivers, and Apply Modifiers off for shape-keyed meshes;
   - armature: baking constraints;
   - one action per expression, named with its ID;
   - materials: no subsurface scattering in glTF, bake procedural nodes;
   - an exporter settings checklist, verification steps, and a table of what glTF loses and how to
     keep it.

   Exporter option names are given as in Blender 4.x and are flagged to check in your version.

**Unchanged:**
- **Expressions:** the 60 IDs are untouched and the manifest is still frozen.
- **Content storage:** schema and code are untouched, and all existing content is preserved. Verified:
  importing, replacing and removing a character left the stored text entries intact.

## Tests

**Unit tests:** `npm test` passes **51/51**.

| Suite | Tests |
|---|---|
| `src/lib/content/content.test.ts` | 21 (manifest, parsers, validation, merge, export, example files) |
| `src/lib/storage/storage.test.ts` | 17 (IndexedDB persistence, languages, conflicts, invalid uploads, atomicity, round trips, migration, sanitizer, manifest immutability) |
| `src/lib/assets/gltf-inspect.test.ts` | 8 (see below) |
| `src/lib/settings/settings.test.ts` | 5 (validation and clamping, configuration round trip, 60 IDs never imported, non-configuration files refused, published guide matches source) |

The validator tests use synthetic GLB fixtures built in code (boxes and named nodes, never a face):
- a complete fixture is "partially ready" with 1 of 60 clips, and "structurally ready" only with all
  60 clips;
- a file with nothing facial is "not compatible";
- off-centre eye pivots fail (13.9 mm measured), and eye bones give a warning;
- missing UVs, unnamed morphs, non-facial armatures and clips, and a missing normal map are flagged;
- external resources, `.blend`, truncated and invalid files are refused;
- `.gltf` with data URIs is read.

**Build and type checks:** `npm run typecheck` is clean. `npm run build` succeeds, with `/`,
`/content`, `/assets` and `/settings` prerendered.

**Browser test** (production build, in-app browser):

| Check | Result |
|---|---|
| Studio | Empty state shown. Play, Pause and Replay are `disabled` with the tooltip "Character asset pending import"; Return to neutral is enabled. No console errors |
| Import (synthetic fixture `TEST_FIXTURE_not_a_character.glb`) | 8 checks pass and clips give a warning (2 of 60 matched; the non-expression clip is listed as unmatched). Verdict "Partially ready". Stored; preview status "Loaded · 3 mesh(es)". The status card shows "Licence: Not confirmed" and "Studio connection: Not connected" |
| Studio with a stored file | The card names the file and says "passed with warnings, but it is not connected". Step 1 is ticked; playback is still locked |
| Replace (bad fixture: off-centre pivots, no clips) | Verdict "Not compatible" (eye pivots and clips fail). Replace asks for confirmation naming both files; Cancel kept the original |
| Remove | Confirmation shown, then removed. The asset store is empty, and **both text entries in the content database are unchanged** |
| Settings | Setting the default camera to Eyes and intensity to 60% (Medium quality) persisted; the Studio opened on the Eyes camera at 60% |

All test data, both databases and the `fes.*` keys were deleted from the browser afterwards.

**Not verified:** the preview with a real character, since none exists. The fixture's preview loads,
but it is three tiny triangles with a 1×1 texture, so it isn't visually meaningful.

## Screenshots (`docs/screenshots/phase2m2/`)

| File | Content |
|---|---|
| `studio.png`, `content.png`, `assets.png`, `settings.png` | 1440×900, headless Chrome, clean profile |
| `assets-with-test-fixture-report.jpg` | In-app browser capture of the Character & Assets page with the synthetic fixture's report (lower resolution) |

## Limitations

- The validator is **structural only**. It doesn't render, evaluate skinning, or judge appearance or
  expression realism.
- **Eye-bone pivots** and **morph-target magnitudes** aren't verified.
- **Clips match expressions by exact name only.**
- **One character slot**, stored per browser. Character files up to 150 MB are accepted, but large
  files use the same browser storage as content.
- The preview is **static**: no clips are played. Connecting clips to the Studio adapter is the next,
  not-yet-started stage.
- **Settings are per browser** (`localStorage`). Configuration import applies only settings.
- The Blender option names in the guide are for the 4.x exporter and must be checked against the
  Blender version used.

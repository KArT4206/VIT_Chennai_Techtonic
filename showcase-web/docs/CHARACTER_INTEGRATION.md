# Integrating the 3D character

The studio runs without a character. It shows **"3D character asset pending import"**, and Play is
disabled. This guide covers the work needed once the approved character exists.

**Not to be used:**
- the old male MakeHuman competition head (`scene.blend`);
- the model in `makehuman_model_exports.zip`.

## What the asset must provide

1. **A glTF 2.0 binary (`.glb`)** exported from Blender, with:
   - **Frame:** the head's **eye midpoint at the origin**, +Y up, the face looking along +Z, metres.
     All camera presets in `src/lib/character/cameras.ts` assume this.
   - **Facial controls:** either
     - **morph targets** (shape keys), ideally an action-unit set with left/right variants so the
       asymmetry slider can work; or
     - **one animation clip per expression,** each going neutral, then expression, then neutral.
   - **Materials:** PBR (base colour, normal, roughness), with textures embedded.
2. **A clip map:** `expression ID → clip name` (or `→ morph-target weights`), covering only clips that
   really exist. IDs without a clip keep Play disabled.
3. **Licence and provenance:** a written licence covering web display. Record it in
   `CharacterInfo.licence`.

## Code changes (UI unchanged)

1. Put the asset in `public/character/<name>.glb`. Keep it private if its licence requires that.
2. Implement `CharacterAdapter` (`src/lib/character/adapter.ts`), for example as `GltfCharacterAdapter`:
   - `status`: `"loading"` while loading, `"ready"` once loaded;
   - `hasClip(id)` / `clipFor(id)`, read from the clip map;
   - `play`: a `THREE.AnimationMixer` action with `timeScale = speed` and weight = `intensity`. Use
     left/right morph pairs for `asymmetry` if present, and set `supportsAsymmetry` to match;
   - `pause`, `resume`, `replay` and `neutral`: neutral blends to rest over about 0.3 s.
3. Render the loaded scene in `CharacterSlot` in `src/components/studio/ViewerScene.tsx`, and drive
   the mixer from `useFrame`. Remove `PendingGuides`.
4. Return the new adapter from `createCharacterAdapter()` in `src/lib/character/registry.ts`.
5. Set `animationStatus`, `animationClip` and `thumbnail` in `src/data/expressions.ts` only for clips
   and thumbnails that really exist. The manifest test (`npm test`) currently requires them all to be
   null or pending; update that test when real clips arrive.

The expression library, Content Manager, cameras and controls need no changes.

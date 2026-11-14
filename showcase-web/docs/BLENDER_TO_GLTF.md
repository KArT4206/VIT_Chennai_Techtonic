# Blender → glTF (.glb) export pipeline for the studio character

Browsers (three.js) cannot read `.blend` files. The character must be exported from Blender as
**glTF 2.0 binary (`.glb`)**. glTF carries meshes, UVs, PBR materials, embedded textures, skinned
armatures, morph targets (shape keys) and animation clips. It does **not** carry Blender drivers,
constraints, modifiers other than the armature, or procedural shader nodes. Anything driven by those
must be baked before export, or it is lost.

Exporter option names below are those of Blender's built-in glTF exporter in the 4.x series. Labels can
move between versions, so check them in your Blender (File → Export → glTF 2.0). After exporting, always
import the `.glb` on the **Character & Assets** page: its validator reports what actually arrived.

## 1. Prepare the scene

| What | Requirement | Why |
|---|---|---|
| Head mesh | Name the object and mesh **`Head`** (or "Face"). One head mesh carries the facial shape keys | The validator and future adapter find the head by name |
| Eyes | **Separate objects `Eye_L` and `Eye_R`**, with the origin at the eyeball centre (*Object → Set Origin → Origin to Geometry* on a sphere, then check). Parent them to the head bone or head. Alternatively, use eye bones whose head is at the eyeball centre | Eyes must rotate about their own centres; the validator measures the pivot offset |
| Cornea, iris, sclera | Separate objects or material slots, parented to each eye | Keep them rotating with the eye |
| Teeth, tongue | Real meshes, weighted to the jaw (tongue to tongue bones) | Open-mouth expressions show the mouth interior |
| Scale and units | Metres, scale applied (*Ctrl+A → Scale*) on the head, eyes and armature | glTF is in metres; unapplied scale breaks pivots |
| Orientation | Face looking along **−Y in Blender** (the default front view). The exporter's **+Y Up** converts it to glTF's +Z forward | The studio cameras assume the face looks along +Z |
| Eye midpoint at origin | Place the character so the midpoint between the eye centres is at the world origin, or note the offset | The studio camera presets frame the eye midpoint |

## 2. Shape keys (morph targets)

- **Naming:** keep descriptive, stable shape-key names, preferably an action-unit set (`browInnerUp_L`,
  `jawOpen`, `mouthSmile_R`, …) with **separate L and R keys** where possible. The asymmetry slider
  needs them.
- **Names in the file:** the exporter writes the names to `mesh.extras.targetNames`. The validator warns
  when names are missing.
- **Basis:** shape keys must be relative to the Basis. Remove unused keys; each one costs memory per
  vertex.
- **Drivers are not exported.** If shape keys are driven by bones or custom properties, bake the result
  into shape-key keyframes per expression first. *Object → Animation → Bake Action* with *Visual Keying*,
  or a script that samples the driven values and keys them.
- **Modifiers:** turn off **Apply Modifiers** for the head. Blender cannot apply modifiers to a mesh
  that has shape keys while keeping those keys. Apply any non-armature modifiers (mirror, weld, …)
  **before** creating shape keys. Never apply Subdivision; export the base cage.

## 3. Armature

- **Skinning:** export a skinned armature for the jaw, eyes and any facial bones. Bone names should be
  descriptive (`jaw`, `eye.L`, `lid_upper.L`, `brow_inner.L`, …); the validator flags armatures without
  facial names.
- **Constraints and IK are not exported.** Bake them into the actions.
- **Bones:** only deforming bones are needed. Use the exporter's "Deformation Bones Only" if the rig
  has many control bones, but check that the eye and jaw bones are deform bones.

## 4. Expressions as animation clips

- **One action per expression, named with the studio ID:** `gentle_smile`, `left_wink`, `jaw_drop`, …
  The full list is in the studio's configuration export, or in `src/data/expressions.ts`. Clip-name
  matching is exact: lowercase, with underscores.
- **Shape of each action:** neutral, then the expression, then neutral, at 30 fps. Blinks are timed
  sequences.
- **Contents:** each action keys the shape keys and/or facial bones it uses. Shape-key animation lives on
  the mesh's shape-key datablock; make sure each expression's shape-key action is exported with the
  same name.
- **Exporter:** Animation → Mode **Actions** (each action becomes a clip), with **Always Sample
  Animations** on.
- **Never invent clips.** Only actions that really exist should be exported and named with expression
  IDs.

## 5. Materials and textures

- **Supported:** Principled BSDF only. Base colour, metallic/roughness, normal map, occlusion and
  emission are exported, as are IOR, specular, transmission, volume, clearcoat and sheen through glTF
  extensions.
- **Not exported:**
  - subsurface scattering (skin will look harder);
  - procedural nodes (noise, Voronoi, musgrave);
  - node groups with custom logic.

  Bake procedural detail to image textures first (*Cycles → Bake → Diffuse colour / Normal /
  Roughness*).
- **Texture formats:** PNG or JPEG (or WebP if your target browsers support it). Everything is embedded
  in the `.glb`.
- **Eyes:** a transparent cornea needs `KHR_materials_transmission` and IOR. Check how it looks in the
  preview; three.js approximates transmission.

## 6. Export settings checklist (File → Export → glTF 2.0)

| Section | Setting |
|---|---|
| Format | **glTF Binary (.glb)** |
| Include | Selected Objects (head, eyes, teeth, tongue, brows/lashes/hair, armature) or Visible Objects |
| Transform | **+Y Up** on |
| Mesh | UVs on, Normals on, **Tangents on** (normal maps), Vertex Colours as needed, **Apply Modifiers off** for shape-keyed meshes |
| Material | Materials: Export. Images: Automatic |
| Shape Keys | **Shape Keys on, Shape Key Normals on**. Shape Key Tangents on if normal-mapped. Use Sparse Accessors on (smaller file) |
| Armature | Use Rest Position on. Deformation Bones Only (optional, see §3) |
| Skinning | **Skinning on**. Include All Bone Influences if more than 4 per vertex |
| Animation | **Animation on, Mode: Actions, Always Sample Animations on**, Shape Key animations on. Optimise animation size on |
| Compression | Draco/meshopt **off** for the first export, so validation is straightforward |

## 7. Verify

1. **Studio validator:** import the `.glb` on **Character & Assets**. Check every row of
   *Compatibility checks*, and the *Shape keys*, *Facial rig* and *Animations* tabs. "Partially ready"
   means features will be missing; read each warning.
2. **Static preview:** confirm the model, textures and orientation look right.
3. **Khronos glTF Validator:** recommended for spec errors (https://github.khronos.org/glTF-Validator/).
4. **Licence:** record the source and licence on the Character & Assets page. A character without
   confirmed written permission stays private.

## What is lost in glTF, and how to keep it

| Blender feature | In glTF | How to keep it |
|---|---|---|
| Shape keys | Morph targets | Export directly |
| Drivers (corrective keys, bone→shape key) | No | Bake into per-expression actions |
| Constraints / IK | No | Bake into actions |
| Non-armature modifiers | Only if applied | Apply before creating shape keys |
| Subsurface scattering | No | Accept harder skin, or bake |
| Procedural textures | No | Bake to images |
| Multiple UV maps | Yes (TEXCOORD_0, _1, …) | Export directly |
| Custom properties | `extras` (optional) | Not used by the studio |

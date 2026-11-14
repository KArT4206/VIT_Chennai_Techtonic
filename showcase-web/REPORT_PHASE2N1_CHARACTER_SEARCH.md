# Phase 2N.1: Ara preset rejected; search for a photorealistic character

- **Branch:** `showcase/interactive-studio`.
- **Unchanged:** Studio, expression manifest (60 IDs), IndexedDB content manager, character import,
  compatibility checker and navigation.
- **Not done:** nothing downloaded, purchased or integrated.
- **Untouched:** competition release and ZIP.

## 1. Ara rejection record

| Item | Value |
|---|---|
| Candidate | Ara 3D Gen v0.3.0 (`fc0cf3f`), "The Female Executive" (glasses and handbag removed); `female_preset.glb`, SHA-256 `472850e8…6f18f` |
| Decision | **Rejected by the user (Phase 2N.1).** It looks like a game character and doesn't match the photorealistic reference |
| Evidence | `REPORT_PHASE2N_PRESET.md`; `staging/preset-candidate/visual-tests/sheet_*.png` |
| Why it fails the benchmark | Flat skin with no normal map; 2K colour; stylised irises; card brows, lashes and hair; hard hair-cap line; plastic teeth; symmetric mouth shapes; eye pivots 3.8 mm off |
| Status | Kept only as an isolated, rejected experiment in `staging/preset-candidate/` and on the `/preset-test` staging page. **Not** the default, **not** connected to the Studio, and no expressions are built on it. No further work on it |

## 2. Benchmark

The user's reference images are this project's own **Cycles** renders of the 3D Scan Store head.
They show visible pores, natural colour variation, eyelid folds and tear line, detailed irises and
corneal reflections, strand brows and lashes, and lip texture.

**Important expectation:** a browser (three.js / WebGL) render can't fully reproduce Cycles. There's no
true subsurface scattering or path tracing, and texture and memory budgets are lower. Even the
original scan, shown in the website, will look below those references unless it's carefully
optimised: baked lighting detail, normal and cavity maps, screen-space SSS approximations, and
high-resolution textures on a head-only mesh. Each candidate below is judged on its source quality
and on how well that survives in a browser.

## 3. The intended character: 3D Scan Store "Free HD Head" (Ten24 scan)

**What it is:**
- The scan is by Ten24 and distributed by 3D Scan Store.
- It's the female head already in `experiments/real_assets/3dscanstore/` (archive SHA-256 `9aa6a036…`).
- 8K albedo, normal, roughness and specular maps, plus a 16-bit displacement map.
- Separate eyes, lenses, tear line, brows, lashes, teeth and tongue.
- In Phases 2D–2F it was already carried onto GNM topology, with working blink, lid, squint, surprise
  and brow controls and corrected eye maps.
- Under the reference test (front, three-quarter, eye, skin macro, mouth) it **is the benchmark**.

**Licence evidence:**
- The product page says "Personal use only… contact us for commercial use" (recorded in Phase 2E).
- CG Channel's coverage of the release says it isn't licensed for commercial use, and may be used "for
  any private or non-commercial project, or for internal tests".
- 3D Scan Store's terms page returned HTTP 403 and couldn't be read.
- Their older terms (summarised in search results) forbid reselling scan data or modified scans, and
  forbid integration into character-maker tools whose results can be exported.
- **No written permission from the vendor is on file.**

**Rights needed**, which must each be granted explicitly; they are not equivalent:

| # | Use | Needed for |
|---|---|---|
| 1 | Private local use (my machine only) | Already covered by personal use |
| 2 | Modification: retopology onto GNM, facial rigging, new shape keys | The expression system |
| 3 | Derived files: GLB exports, baked and modified textures (eye maps, compressed web textures) | Any web version |
| 4 | Private hosting (password-protected or reviewer-only site) | Demos to judges or reviewers |
| 5 | **Public website delivery.** The site serves the GLB and textures to every visitor's browser, so users technically receive a copy | A public Studio |
| 6 | Downloads offered to users (a "download the character" button) | Not planned; ask anyway |
| 7 | Redistribution in source code (a GitHub repo containing the asset) | Not planned; the asset should stay out of public repos |
| 8 | Public demonstration and portfolio use (screenshots, videos, live demo) | Portfolio and competition |
| 9 | Attribution wording they require | Credits page |
| 10 | Whether a paid commercial licence or fee applies | Budget |

### Draft permission request (to info@3dscanstore.com; not sent)

> **Subject:** Permission request: Free HD Head (Ten24) in an interactive web facial-expression demo
>
> Hello 3D Scan Store team,
>
> I downloaded your Free HD Head (Ten24 scan) and would like written permission to use it in a
> non-commercial interactive website: a facial-expression studio where visitors choose from 60
> expressions and see them on a real-time 3D head in their browser (three.js / WebGL).
>
> To do this I would need to:
> 1. modify the scan (retopologise it, add a facial rig and expression shape keys, adjust the eyes);
> 2. create derived files: a glTF/GLB of the head and compressed or baked versions of your textures;
> 3. host those files on a website. Visitors' browsers would download the GLB and textures to render
>    them, but there would be **no download button** and the files would not be offered separately;
> 4. show the website, screenshots and videos publicly as a demonstration and in my portfolio.
>
> The raw scan, textures and derived files would not be sold, shared or placed in any public code
> repository.
>
> Could you confirm in writing which of uses 1–4 you permit, any attribution you require, and whether
> a paid licence is needed (and its price)? If public hosting is not possible, would a private,
> password-protected demo for reviewers be acceptable?
>
> Thank you,
> [name]

The scan must not be used in the website until the reply covers at least items 2, 3 and 5 (or 4 for
a private demo). The reply should be stored next to `3dscanstore/LICENCE_RECORD.md`.

## 4. Alternative candidates

Facts come from the sources cited at the end. Nothing was downloaded, so **none of the external
candidates has been rendered or visually tested here.** The visual acceptance test (front,
three-quarter, eye, skin macro, mouth) stays pending for each until you approve a download or
account.

| Candidate | Source quality (published facts) | Rig and shapes | Eyes, teeth, tongue | Blender / GLB route | Licence and web hosting | Price | First judgement |
|---|---|---|---|---|---|---|---|
| **A. Original scan** (Ten24 / 3D Scan Store Free HD Head) | 8K albedo, normal, roughness and specular; 16-bit displacement; photogrammetry. **Benchmark** | None from the vendor; our GNM transfer gives blink, lids, squint, surprise and brows (Phase 2D–2F) | Yes, separate meshes | Proven in this project (Blender → GNM); GLB export still to be done | Personal and non-commercial; **public web needs written permission** (§3) | Free | **Best fidelity, blocked on permission** |
| **B. 3D Scan Store paid HD heads** (e.g. "HD Female 3D Head Model 57") | 120-camera scan rig; mesh, displacement and Blender scene listed | Not listed (unrigged) | Not confirmed in the excerpt | Same as A, likely including the same GNM-compatible topology (to verify) | **Unknown** (terms page 403). Older terms forbid redistributing scan data, so web delivery must be cleared in writing | ~£35 (sale; list £69.99) | Strong option **if** the licence allows web delivery |
| **C. Epic MetaHuman** | Photoreal digital human; 8K-class textures; strand or card grooms | Full RigLogic facial rig. **52 ARKit blend shapes** can be exported as glTF with a Fab plugin, or through DNA tools in Blender (Poly Hammer Character DNA, free base) | Yes (eyes, teeth, tongue, lashes) | Unreal → glTF with ARKit shapes, or DNA → Blender → GLB. Tooling is third-party; quality after export must be tested | Since UE 5.6 (June 2025), MetaHumans may be used "across all engines and creative software" under the UE EULA, royalty-free below US$1M revenue. **Not confirmed:** whether a browser downloading the GLB counts as distributing the asset (the licence page is behind a login) | Free (UE EULA) | **Best licensed route to a full photoreal rig**, pending the EULA check and an export test |
| **D. Lee Perry-Smith head** (Infinite Realities / Triplegangers, in three.js examples) | Older head scan; colour and specular maps; 4096 displacement and tangent-space maps | **None** | **No eyes, teeth or tongue** | Already a GLB | **CC BY 3.0**: commercial use, modification and public hosting allowed **with attribution** | Free | Licence-clean, but male, no eyes or rig. Large build effort, and likely **fails** the eye and mouth close-up tests |
| **E. Digital Emily 2** (USC ICT / Wikihuman) | 8K-class maps, micro-displacement, very high fidelity | No rig listed | Eyes not provided as a model | Maya / Alembic / OBJ | "Research and illustration purposes only… not to transfer or redistribute", and no commercial use. **Public web delivery not allowed** | Free | **Rejected (licence)** |
| **F. Reallusion Character Creator / Headshot** | Realistic but stylised base; photo-to-head Headshot | Full facial rig and expressions | Yes | Export licence required; FBX → Blender → GLB | Export licence; a game or app needs a (free) mass-distribution authorisation. The base topology belongs to Reallusion. **Browser delivery not addressed** | Paid software and licences | Below scan fidelity, with complex licensing. **Not recommended** |
| **G. Marketplace rigged "realistic female heads"** (CGTrader, Superhive, etc.) | Varies widely | Often ARKit-52 shape keys | Varies | Usually Blender-native | Per-item. "Royalty-free" usually allows use *inside* a product but forbids redistributing the model, and web GLB delivery is often a grey area | ~$30–100+ | Only after a specific item is chosen, with rendered proof and written licence terms |

### Visual comparison against the benchmark

| Candidate | Front | Three-quarter | Eye close-up | Skin macro | Mouth | Evidence |
|---|---|---|---|---|---|---|
| A. Original scan | Pass | Pass | Pass (after the 2E/2F fixes) | Pass | Pass (teeth and tongue meshes) | Own Cycles renders (Phases 2E/2F) |
| Ara (rejected) | Fail | Fail | Fail | Fail | Fail | Phase 2N renders |
| B, C, D, F, G | Not tested | Not tested | Not tested | Not tested | Not tested | Needs approved download or account |
| E | — | — | — | — | — | Excluded on licence |

From published facts only (no rendered evidence):
- **B and C** can plausibly reach the benchmark.
- **D** is unlikely to pass the eye and mouth tests without major additions.

## 5. Rigging and GLB compatibility

- **A and B (3D Scan Store):**
  - This project already has a working pipeline: scan to GNM topology, Phase 2B controls, GNM eye
    joints.
  - Still needed for the website:
    - export to GLB with the shape keys;
    - add the missing action units (mouth corners L/R, cheek raise, cheek puff, lip roll and bite,
      jaw L/R, tongue);
    - convert the strand brows and lashes (121k + 50k vertices) to cards;
    - compress the 8K textures (KTX2 / 2–4K for the web).
- **C (MetaHuman):**
  - The ARKit-52 export covers most of the 60 IDs: L/R mouth shapes, cheek puff, jaw L/R, mouth
    roll, tongue out.
  - Problems:
    - RigLogic correctives and wrinkle maps don't survive glTF;
    - the strand grooms need cards;
    - the eyes need checking (pivots, iris refraction).
- **D:** needs eyes, teeth, tongue, a full facial rig and shape keys, essentially building a character.
- **All:** the existing **compatibility checker** and **import system** apply unchanged. The GLB must
  have a head mesh named "Head" or "Face", eye objects with centred pivots or eye bones,
  expression-named clips or a morph mapping, and embedded textures.

## 6. Estimated additional work (after a licence is secured)

| Candidate | Work to a web-ready rigged GLB | Risk |
|---|---|---|
| A. Original scan | Medium: the pipeline exists. About 25–35 new and extended shape keys, card brows and lashes, texture optimisation, GLB export, and per-expression visual sign-off | Licence |
| B. 3D Scan Store paid head | Medium–high: as A, plus checking topology compatibility | Licence; topology |
| C. MetaHuman | Medium: create the character, export glTF + ARKit, fix eyes and grooms, compress textures; mapping to 60 IDs is largely direct | EULA interpretation for browser delivery; export fidelity |
| D. Lee Perry-Smith | High: build eyes, mouth interior and a full facial rig | Visual quality likely below benchmark |
| F, G | Varies | Licence clarity |

## 7. Recommendation

1. **First choice: the original 3D Scan Store female scan (A).** Send the permission request in §3. It
   is the benchmark itself, already GNM-compatible, with working controls. It stays off the website
   until the written reply covers modification, derived files and hosting (public, or at least
   private reviewer hosting).
2. **Parallel fallback: Epic MetaHuman (C).** It offers the best licensed route to a photoreal head
   with a full facial rig and ARKit-52 shapes. Next steps, which need your approval:
   1. Read the current UE EULA and MetaHuman terms while signed in, specifically whether delivering
      a GLB to visitors' browsers is permitted.
   2. If yes, create one female MetaHuman and do a test export to GLB for the five-view visual test.
3. **Also ask 3D Scan Store about a paid licence (B)** in the same email, if the free head can't be
   cleared.
4. **Do not pursue** D (insufficient eyes, rig and quality), E (licence forbids it), F (licence
   complexity, lower fidelity) or Ara (rejected).

**No candidate is approved yet.** A needs the vendor's written permission. C needs an EULA read and an
export test that requires an Epic account. Both need your go-ahead.

## Sources

- [MetaHuman licence page](https://www.metahuman.com/license) (login-gated; not read directly)
- [CG Channel: you can now sell MetaHumans or use them in Unity or Godot (2025)](https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/)
- [Creative Bloq: MetaHuman broke free from Unreal Engine 5](https://www.creativebloq.com/3d/metahuman-just-broke-free-from-unreal-engine-5-why-everyone-can-now-create-lifelike-characters)
- [Digital Production: MetaHumans for Unity, Godot and Fab](https://digitalproduction.com/2025/06/05/metahumans-graduate-ready-for-unity-godot-and-the-fab-cash-register/)
- [Fab: Can I sell MetaHuman characters on Fab?](https://support.fab.com/s/article/Can-I-sell-characters-created-with-MetaHuman-Creator-on-Fab?language=en_US)
- [Fab listing: Export MetaHuman as glTF + ARKit](https://www.fab.com/listings/88fa82af-3210-42e1-81f0-9a613da436ef)
- [Poly Hammer Character DNA add-on](https://polyhammer.com/character-dna-addon)
- [3D Scan Store terms](https://www.3dscanstore.com/terms-and-conditions-licensing) (HTTP 403; not read)
- [3D Scan Store free head page](https://www.3dscanstore.com/blog/Free-3D-Head-Model)
- [CG Channel: Ten24's free hi-res female head scan](https://www.cgchannel.com/2023/09/download-ten24s-free-hi-res-3d-scan-of-a-female-human-head/)
- [3D Scan Store HD Female 3D Head Model 57](https://www.3dscanstore.com/hd-head-scans/hd-head-models/hd-female-3d-head-model-57)
- [three.js LeePerrySmith licence (CC BY 3.0)](https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/LeePerrySmith_License.txt)
- [USC ICT Digital Emily 2](https://vgl.ict.usc.edu/Data/DigitalEmily2)
- [Reallusion content licence](https://www.reallusion.com/license/content.html)
- [Reallusion EULA](https://www.reallusion.com/Content/EULA/AP/EULA_AP.htm)

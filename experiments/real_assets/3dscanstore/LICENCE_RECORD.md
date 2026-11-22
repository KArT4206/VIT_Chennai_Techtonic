# 3D Scan Store Free HD Head: licence and permission record

## Asset

| Field | Value |
|---|---|
| Product | 3D Scan Store "Free HD Head" |
| Product page | https://www.3dscanstore.com/blog/Tutorials/Free-3D-Head-Model |
| Archive | `3D_ScanStore_Free+Head.zip`, 2,019,571,774 bytes |
| SHA-256 | `9aa6a036462910c9dbe861d53201b3fed3bd39b37dc8f0c7d2e33c852eeecfe7` |
| Obtained | Downloaded by the user in their own browser and supplied on 2026-11-14. Automated download returned HTTP 403 and was not circumvented |
| Contents | 90 entries / 72 files, listed with per-file SHA-256 in `MANIFEST_SHA256.txt` |
| Licence file inside the archive | **None** (no LICENSE / README / EULA in the archive) |

## Licence terms available to us

- The public product page labels the asset **"Personal use only"** and asks users to contact the
  vendor for broader use. Recorded in the user's acquisition kit (`SOURCE_CATALOG_AND_LICENSE_NOTES.md`).
  Not re-verified on the live page in this session.
- **User statement (2026-11-14):** "I have contacted 3D Scan Store and received permission to use the
  asset. I will provide the actual permission message separately if required."
- **Written permission: NOT YET ON FILE.** The kit's permission template
  (`kit/.../licensing/3DSCANSTORE_PERMISSION_RECORD_TEMPLATE.md`) is blank.

## Scope: what is and isn't established

| Question | Status |
|---|---|
| Private, local experimentation (this prototype) | Covered by "personal use"; consistent with the user's reported permission |
| Modifying the asset / re-rendering | **Unknown.** Not stated in any evidence on file |
| Baking or deriving textures (e.g. onto GNM) | **Unknown** |
| Competition demonstration (renders shown to judges) | **Unknown.** Needs the vendor's written scope |
| Original or derived files inside the submission ZIP sent to judges | **Unknown; assumed NOT permitted until confirmed in writing** |
| Original or derived files in any Git repository (private or public) | **Not permitted by default.** The archive, extracted files, derived maps and every scene containing them are git-ignored |
| Public redistribution | **Assumed prohibited** |
| Attribution required | Unknown. Credit "3D Scan Store" in any shown material until told otherwise |

## Handling rules applied in this project

1. The archive and extracted files live only in `experiments/real_assets/3dscanstore/{original,extracted}/`
   and are git-ignored.
2. Every `.blend` containing the scan or its textures, and every derived map, is git-ignored.
3. Renders are kept locally under `experiments/real_assets/renders/` and **not committed**, because
   showing them publicly is not established.
4. Nothing from this asset goes into `dist/` or the evaluator ZIP.

## To complete this record

Add the vendor's actual reply (`.eml`, `.pdf` or screenshot) next to this file and fill in:
- date and vendor contact;
- exact asset and version covered;
- allowed purpose;
- whether modification, baking and derived maps are allowed;
- whether judges may receive the original or derived files;
- repository use;
- attribution;
- any other conditions.

## Update 2026-11-14: user statement on vendor permission

The user states (chat, 2026-11-14): "they told me i can use it for only this time so use the 8k skin colour".

Recorded scope (as stated, not yet in writing):
- One-time use of the Free HD Head for this project, including its 8K skin colour texture.
- Not stated: public website hosting, redistribution, GitHub, downloads, or reuse beyond this project.

Handling until the written message is on file:
- The scan-derived web GLB lives only in `build/web/` (git-ignored) and is served only to a
  local preview on the user's machine (`PRIVATE_CHARACTER_GLB` env var). It is not committed,
  not placed in any app's public folder, not deployed and not shared.
- Please add the vendor's actual message next to this file; public use waits for it.

## Clarification (2026-11-14)

User's words: "only one time means only for this publication can be used from next on i cant use it".

* Scope: this one publication only (Samsung PRISM Hackathon 2026, Track 1).
* No reuse after it: not in later projects, versions, demos or publications.
* Once this publication is finished, delete `build/web/gnm_scan_private.glb` and the other scan-derived builds, and remove the `expression-studio-private` launch entry.
* Still not stated: whether public hosting or redistribution is allowed. Until the user confirms, it stays local only.

## Public use (2026-11-14)

User's words: "Public is allowed". The scan head may be shown publicly as part of this one publication only. After it, no reuse. The rule against pushing to GitHub stays in force until the user lifts it.

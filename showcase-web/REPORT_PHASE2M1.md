# Phase 2M.1: content persistence (IndexedDB) and UI review

- **Branch:** `showcase/interactive-studio`, in the worktree `~/Desktop/Projects/SyntheticEyes-Track1-showcase`.
  This phase was built on `0dcc485`.
- **Release untouched:** `release/makehuman-submission` is still at `4a2f56b`. `dist/Techtonic.zip` is
  unchanged (SHA-256 `91f4bafe…73a4`).
- **Not done in this phase:** no character imported, and no animation created.

## Start the application

```bash
cd ~/Desktop/Projects/SyntheticEyes-Track1-showcase/showcase-web
npm install
npm run build && npm start      # http://localhost:3000   (or: npm run dev)
```

The checks:

```bash
npm test          # 38 tests
npm run typecheck
```

## 1. Storage migration: localStorage to IndexedDB

**Storage layer** (`src/lib/storage/`)

| File | Role |
|---|---|
| `repository.ts` | `ContentRepository` interface, with `IndexedDbRepository` (database `facial-expression-studio`, version 1) and `MemoryRepository` (fallback) |
| `migrate.ts` | One-time `localStorage` to IndexedDB migration |
| `backup.ts` | Full backup export; backup files are recognised on import |
| `sanitize.ts` | Plain-text sanitizer |

**IndexedDB stores**

| Store | Key | Contents |
|---|---|---|
| `entries` | `[locale, id]` | Title, description, tags and notes for one expression in one language; `updatedAt`; `origin` (file name or "manual edit") |
| `imports` | auto-increment | Import history: file name, format, size, time, languages, and counts applied, skipped and overwritten. Also the sanitized file text (up to 512 KB) and whether markup was removed |
| `meta` | `key` | Migration record, including any conflicts |

**Behaviour**

- **One transaction per write.** An import's entries and its history record commit together or not at
  all.
  - **Bug found and fixed:** a request that fails while being queued (such as an invalid key) used to
    let earlier requests commit.
  - The transaction is now aborted explicitly, and a test covers it.
- **Nothing is overwritten silently.**
  - An import is validated and previewed first. Applying it fills only empty fields.
  - Text that is already stored is replaced only for entries you tick **Overwrite**. The result shows
    "N overwritten on request".
  - Duplicates within a file are reported, and only the first copy is used.
- **Migration from Phase 2M runs once, automatically, on first load.**
  - **Added:** legacy entries that aren't yet in IndexedDB.
  - **Kept:** entries IndexedDB already holds. Where the legacy text differs, IndexedDB's text is kept
    and the legacy text is recorded as a conflict. The page lists those conflicts, so nothing is lost.
  - **Skipped and counted:** unknown IDs and invalid language codes.
  - **On success:** the legacy value moves to `fes.content.v1.migrated-backup`. It is kept, not deleted.
  - **On failure** (corrupt JSON, storage error): `localStorage` is left untouched, and the error is
    shown.
- **No executable HTML or scripts are stored.** Every text field is reduced to plain text before
  storage:
  - imported entries;
  - manual edits;
  - migrated data;
  - the stored file text.

  This removes `<script>`, `<style>` and `<iframe>` blocks, all tags, `javascript:`, `vbscript:` and
  `data:` schemes, and control characters. Imports that contained markup are flagged in the preview and
  in the history. The UI also renders text only as text.
- **Unavailable storage** (blocked or private mode): the app falls back to memory and shows a red
  banner saying content won't persist and should be exported.
- **Other tabs:** a `versionchange` handler closes the connection, so other tabs can upgrade or delete
  the database.
- **Backup:** "Download full backup" saves all languages plus import-history metadata as JSON. Restoring
  means importing that file: it goes through the same review and conflict rules.
- **Not migrated:** favourites, recents and the selected language stay in `localStorage`. They are
  per-browser preferences, not content.
- **Animation is untouched.** The manifest (`src/data/expressions.ts`) is deep-frozen, so content can't
  change IDs, categories or animation fields.

## 2. The 60 expressions

- **IDs:** exactly 60, in the approved order. The test checks the full list.
- **Category counts:** 10 / 8 / 8 / 10 / 10 / 14 (Happiness, Sadness, Anger, Surprise and Thinking,
  Eyes and Eyebrows, Mouth, Lips and Cheeks).
- **Animation fields:** `animationClip`, `thumbnail` and `description` are null or empty, and
  `animationStatus` is `pending_asset`.
- **Content can't change the manifest:** a test takes a snapshot of every ID, number, category,
  animation status, clip, thumbnail and display name. It's unchanged after imports and overwrites.
  Trying to mutate the manifest throws.

## 3. Tests

**Unit tests:** `npm test` passes **38/38**, using `fake-indexeddb` for the storage tests.

| Area | Tests |
|---|---|
| Manifest | Exact IDs, order and categories; no animation or thumbnail is claimed; frozen against mutation; unchanged after content operations |
| Parsers | JSON, CSV (quotes, commas, newlines), Markdown (front matter), TXT (two line styles, language switch); unsupported types refused |
| Validation | Unknown, invalid and duplicate IDs with typo suggestions; missing coverage; conflicts |
| Persistence | Survives closing and reopening the database (a refresh); languages are stored independently (deleting French doesn't touch English) |
| Conflicts | Default keeps the stored text; only ticked entries are overwritten |
| Invalid uploads | Broken JSON, wrong schema version, CSV without an `id` column, Markdown without sections, unknown IDs only, `.docx`: no change to entries or history |
| Atomicity | A failing batch leaves stored content byte-identical |
| Round trip | Export then re-import preserves content for the backup, CSV (all languages), JSON and Markdown |
| Migration | New entries added; conflicts recorded and IndexedDB kept; markup removed; unknown IDs and bad languages rejected; legacy key backed up; runs once; corrupt legacy data left untouched |
| Sanitizer | Scripts, tags and `javascript:` removed; `2 < 3 and 5 > 4` kept |
| Memory fallback | Same contract as IndexedDB |

**Browser test** (production build in the in-app browser, Chromium):

| Check | Result |
|---|---|
| Migration | Seeded Phase 2M `localStorage` content (English and French) was moved to IndexedDB. Banner: "2 added". Legacy key removed, backup copy kept |
| Import | A TXT file with German and English entries and a `<script>` payload applied 2 entries. Warning shown; the script is absent from both the stored entry and the stored file text |
| Page refresh | All 4 entries, in 3 languages, and the import history persisted. Migration did not run again |
| Navigation | After switching to German and going Content Manager → Studio, the library showed "Blinzeln", and the Squint panel showed the German description |
| Invalid uploads | Broken JSON: Apply disabled. `.html` file: rejected. Stored data byte-identical before and after |
| Conflict | A file changing an existing English entry was applied without ticking: 0 applied, stored text unchanged |

**Fixes made during browser testing:**
1. Two quick drops could finish out of order and clear each other's "unsupported file" message.
   Rejections are now decided synchronously.
2. The open database connection blocked deletion from another tab. The `versionchange` handler was
   added, and deleting while the app is open now succeeds.

The browser's test data (the database and `fes.*` keys) was deleted afterwards.

**Build and type checks:** `npm run typecheck` is clean; `npm run build` succeeds, with `/` and
`/content` statically prerendered.

## 4. Limitations

- **Storage is per browser and per site.** Clearing site data deletes it; use the full backup.
  Browsers may evict storage under disk pressure, and no persistent-storage request is made.
- **Only the latest version is kept.** There is no undo or version history per entry; import history
  records what happened but cannot roll it back.
- **History is not restored.** Restoring a backup restores entries, not import history (the backup has
  history metadata for reference only).
- **Large files.** File text over 512 KB isn't kept in history; uploads are limited to 2 MB.
- **Migration conflicts** are listed, but there is no one-click "use the old text". To keep an old
  value, paste it from the list or the backup key.
- **Multiple open tabs** each hold their own in-memory copy. A tab doesn't see another tab's changes
  until it reloads.
- **Sanitising text** removes anything shaped like a tag (for example `<b>`). Literal comparisons such as
  `2 < 3` are kept.
- **No character yet.** Play stays disabled.

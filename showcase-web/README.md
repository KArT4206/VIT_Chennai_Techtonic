# Facial Expression Studio

An interactive website for browsing 60 facial expressions and viewing them on a real-time 3D character.

> **Status:** no character is imported yet. The viewport shows "3D character asset pending import",
> and Play is disabled. No facial motion is simulated. See `docs/CHARACTER_INTEGRATION.md`.

## Run

```bash
npm install
npm run dev          # http://localhost:3000
npm test             # manifest, parsers, validation, merge and export tests
npm run typecheck
npm run build && npm start
```

Requires Node 20+. Tested with Node 26, Next.js 16, React 19, Tailwind CSS 4, three.js 0.180 and React
Three Fiber 9.

## Pages

**Studio (`/`)**
- **Expression library:** all 60 expressions in 6 categories, with search by name, ID or tag, category
  filters, favourites and recently selected.
- **3D viewport:** orbit and zoom, plus Front, ¾ left, ¾ right, Profile left, Profile right, Eyes and
  Mouth cameras, a Neutral pose button and Fullscreen.
- **Controls panel:** name, ID, category and description (in the selected language), intensity, speed
  and left/right asymmetry sliders, and Play, Pause, Replay and Return to neutral. Play, Pause and Replay
  are enabled only when the character adapter has a real clip.

**Content Manager (`/content`)**
- **Import:** JSON, CSV, Markdown or TXT, by drag and drop or browsing.
- **Review:** each file is previewed and validated: unknown IDs (with typo suggestions), duplicates,
  coverage per language, and conflicts with existing text.
- **Apply:** nothing is saved until you apply. Existing text is only replaced for entries you tick.
- **Edit:** any entry, per language.
- **Export:** JSON or Markdown per language, CSV for all languages, and a 60-ID template.
- **Format guide:** `public/templates/CONTENT_FORMAT.md`; example files are in `public/templates/`.

Content is stored in the browser (`localStorage`), so export it to keep it or move it.

## Structure

| Path | Purpose |
|---|---|
| `src/data/expressions.ts` | Canonical manifest: 60 stable IDs, categories, tags. `animationClip` and `thumbnail` are null until real assets exist |
| `src/lib/content/` | Parsers, validation, non-destructive merge, export (pure functions with tests) |
| `src/lib/character/adapter.ts` | `CharacterAdapter` contract and `PendingCharacterAdapter` |
| `src/lib/character/registry.ts` | Which adapter is active (currently pending) |
| `src/lib/character/cameras.ts` | Camera presets in a head-centred frame |
| `src/components/studio/` | Library, viewport (React Three Fiber), controls |
| `src/components/content/` | Content Manager UI |

## Asset restrictions

The old male MakeHuman competition head (`scene.blend`) and `makehuman_model_exports.zip` must not be
used as the showcase character. No 3D Scan Store assets are included.

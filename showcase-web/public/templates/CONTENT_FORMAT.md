# Content file formats

The Content Manager reads four formats. Every entry is matched to one of the 60 expression IDs, such as
`gentle_smile`. Text never changes animation: it only supplies titles, descriptions, tags and notes.

## Rules for all formats

- **Encoding:** UTF-8. The size limit is 2 MB per file.
- **IDs:** must be one of the 60 IDs exactly. They are lowercase with underscores; the full list is in
  the downloadable JSON template. An unknown ID is reported, often with a "Did you mean …?" suggestion,
  and is never applied.
- **Language codes:** codes like `en`, `fr`, `de`, `pt-BR`. One file may contain several languages
  (CSV, or a per-entry `locale` in JSON).
- **Duplicates:** if the same ID and language appear twice in one file, the first is kept and the
  repeat is reported.
- **Review before saving:** imports are previewed and nothing is saved until you click **Apply**.
- **Existing text is protected:** empty fields are filled. A field that already has text is replaced
  only if you tick **Overwrite** for that entry.

## JSON

The template is below; **Download JSON template** in the app gives all 60 IDs.

```json
{
  "schema_version": 1,
  "locale": "en",
  "expressions": [
    {
      "id": "gentle_smile",
      "title": "Gentle Smile",
      "description": "A subtle natural smile.",
      "tags": ["happy", "positive"],
      "notes": ""
    }
  ]
}
```

- **Required:** `schema_version` (must be `1`) and `expressions[].id`.
- **Optional:** everything else. An omitted field leaves existing text untouched.
- **Per-entry language:** an entry may carry its own `"locale"`, which overrides the file's.

## CSV

```csv
id,locale,title,description,tags,notes
gentle_smile,fr,Sourire doux,"Un sourire subtil et naturel.",positif;sourire,
```

- **Header:** a header row is required. Only `id` is mandatory, and the columns may come in any order.
- **Language:** if `locale` is empty, it is `en`.
- **Tags:** separated by `;` (`,` and `|` also work).
- **Quoting:** quote fields that contain commas, quotes or line breaks. Write a quote inside a quoted
  field as `""`.

## Markdown

```markdown
---
locale: de
---
## squint
Title: Blinzeln
Tags: Augen, Lider
Die Augen werden leicht zusammengekniffen.
```

- **Front matter:** optional, and sets the language (default `en`).
- **Sections:** each `## <id>` heading starts an entry.
- **Fields:** `Title:`, `Tags:` and `Notes:` lines directly under the heading are fields.
- **Description:** the remaining text up to the next heading.

## TXT

```text
locale: es
fear | Miedo | Ojos muy abiertos y cejas levantadas.
lip_press: Los labios se presionan entre sí.
```

- **One entry per line:** either `id: description` or `id | title | description`.
- **Language:** a `locale: xx` line switches the language for the lines below it.
- **Ignored:** lines starting with `#`, and blank lines.

## Export

The Content Manager can export:
- the current language as JSON or Markdown;
- every language as one CSV.

Exported files use the same formats and can be imported again.

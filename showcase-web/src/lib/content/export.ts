import { EXPRESSIONS } from "@/data/expressions";
import { SCHEMA_VERSION, type ContentFileJson, type ContentStore } from "./types";

/** JSON in the documented import format, one locale per file. Entries follow manifest order. */
export function exportJson(store: ContentStore, locale: string): string {
  const m = store[locale] ?? {};
  const file: ContentFileJson = {
    schema_version: SCHEMA_VERSION,
    locale,
    expressions: EXPRESSIONS.filter((e) => m[e.id]).map((e) => ({
      id: e.id,
      title: m[e.id].title,
      description: m[e.id].description,
      tags: m[e.id].tags,
      notes: m[e.id].notes,
    })),
  };
  return JSON.stringify(file, null, 2) + "\n";
}

const csvField = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);

/** CSV with every locale (one row per locale and expression). */
export function exportCsv(store: ContentStore, locales = Object.keys(store).sort()): string {
  const rows = [["id", "locale", "title", "description", "tags", "notes"]];
  for (const loc of locales)
    for (const e of EXPRESSIONS) {
      const s = store[loc]?.[e.id];
      if (s) rows.push([e.id, loc, s.title, s.description, s.tags.join(";"), s.notes]);
    }
  return rows.map((r) => r.map(csvField).join(",")).join("\n") + "\n";
}

export function exportMarkdown(store: ContentStore, locale: string): string {
  const m = store[locale] ?? {};
  const out = ["---", `locale: ${locale}`, "---", "", "# Facial expression content", ""];
  for (const e of EXPRESSIONS) {
    const s = m[e.id];
    if (!s) continue;
    out.push(`## ${e.id}`);
    if (s.title) out.push(`Title: ${s.title}`);
    if (s.tags.length) out.push(`Tags: ${s.tags.join(", ")}`);
    if (s.notes) out.push(`Notes: ${s.notes.replace(/\n/g, " ")}`);
    if (s.description) out.push("", s.description);
    out.push("");
  }
  return out.join("\n");
}

/** Full-manifest template: every ID, empty text. */
export function templateJson(locale = "en"): string {
  const file: ContentFileJson = {
    schema_version: SCHEMA_VERSION,
    locale,
    expressions: EXPRESSIONS.map((e) => ({ id: e.id, title: e.displayName, description: "", tags: e.tags, notes: "" })),
  };
  return JSON.stringify(file, null, 2) + "\n";
}

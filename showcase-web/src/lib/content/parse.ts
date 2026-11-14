import { SCHEMA_VERSION, type ContentEntry, type ContentFormat, type ParsedContent, type ParseIssue } from "./types";

export const DEFAULT_LOCALE = "en";

export function detectFormat(fileName: string): ContentFormat | null {
  const ext = fileName.toLowerCase().split(".").pop() ?? "";
  if (ext === "json") return "json";
  if (ext === "csv") return "csv";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt") return "txt";
  return null;
}

export function parseContent(fileName: string, text: string): ParsedContent {
  const format = detectFormat(fileName);
  if (!format) {
    return { format: "txt", fileName, entries: [], issues: [{ level: "error", message: `Unsupported file type: ${fileName}. Use .json, .csv, .md or .txt.` }] };
  }
  const clean = text.replace(/^﻿/, "").replace(/\r\n?/g, "\n");
  const result = format === "json" ? parseJson(clean) : format === "csv" ? parseCsv(clean) : format === "markdown" ? parseMarkdown(clean) : parseTxt(clean);
  return { format, fileName, ...result };
}

type Partial_ = { entries: ContentEntry[]; issues: ParseIssue[] };

const splitTags = (s: string): string[] =>
  s
    .split(/[;,|]/)
    .map((t) => t.trim())
    .filter(Boolean);

// ------------------------------------------------------------------ JSON

export function parseJson(text: string): Partial_ {
  const issues: ParseIssue[] = [];
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { entries: [], issues: [{ level: "error", message: `Invalid JSON: ${(e as Error).message}` }] };
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { entries: [], issues: [{ level: "error", message: 'The JSON root must be an object with "schema_version", "locale" and "expressions".' }] };
  }
  const obj = data as Record<string, unknown>;
  if (obj.schema_version === undefined) issues.push({ level: "warning", message: `"schema_version" is missing; assuming ${SCHEMA_VERSION}.` });
  else if (obj.schema_version !== SCHEMA_VERSION) issues.push({ level: "error", message: `Unsupported schema_version ${String(obj.schema_version)} (this app reads ${SCHEMA_VERSION}).` });
  const fileLocale = typeof obj.locale === "string" && obj.locale.trim() ? obj.locale.trim() : DEFAULT_LOCALE;
  if (typeof obj.locale !== "string") issues.push({ level: "warning", message: `"locale" is missing; using "${DEFAULT_LOCALE}".` });
  if (!Array.isArray(obj.expressions)) {
    issues.push({ level: "error", message: '"expressions" must be an array.' });
    return { entries: [], issues };
  }
  const entries: ContentEntry[] = [];
  obj.expressions.forEach((raw, i) => {
    const source = i + 1;
    if (!raw || typeof raw !== "object") {
      issues.push({ level: "error", message: `expressions[${i}] is not an object.`, source });
      return;
    }
    const r = raw as Record<string, unknown>;
    if (typeof r.id !== "string") {
      issues.push({ level: "error", message: `expressions[${i}] has no string "id".`, source });
      return;
    }
    const str = (k: string): string | undefined => {
      if (r[k] === undefined || r[k] === null) return undefined;
      if (typeof r[k] !== "string") {
        issues.push({ level: "warning", message: `expressions[${i}].${k} is not a string; ignored.`, source });
        return undefined;
      }
      return r[k] as string;
    };
    let tags: string[] | undefined;
    if (Array.isArray(r.tags)) tags = r.tags.filter((t): t is string => typeof t === "string").map((t) => t.trim()).filter(Boolean);
    else if (typeof r.tags === "string") tags = splitTags(r.tags);
    else if (r.tags !== undefined) issues.push({ level: "warning", message: `expressions[${i}].tags must be an array of strings; ignored.`, source });
    entries.push({
      id: r.id.trim(),
      locale: str("locale")?.trim() || fileLocale,
      title: str("title"),
      description: str("description"),
      tags,
      notes: str("notes"),
      source,
    });
  });
  return { entries, issues };
}

// ------------------------------------------------------------------ CSV (RFC 4180 quoting)

export function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else quoted = false;
      } else field += c;
    } else if (c === '"' && field === "") quoted = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((f) => f.trim() !== ""));
}

export function parseCsv(text: string): Partial_ {
  const issues: ParseIssue[] = [];
  const rows = parseCsvRows(text);
  if (!rows.length) return { entries: [], issues: [{ level: "error", message: "The CSV file is empty." }] };
  const header = rows[0].map((h) => h.trim().toLowerCase());
  const col = (name: string) => header.indexOf(name);
  if (col("id") < 0) return { entries: [], issues: [{ level: "error", message: 'The CSV header must include an "id" column (columns: id, locale, title, description, tags, notes).' }] };
  const known = new Set(["id", "locale", "title", "description", "tags", "notes"]);
  header.filter((h) => !known.has(h)).forEach((h) => issues.push({ level: "warning", message: `Unknown CSV column "${h}" ignored.` }));
  const entries: ContentEntry[] = [];
  rows.slice(1).forEach((r, i) => {
    const source = i + 2;
    const get = (name: string): string | undefined => (col(name) >= 0 && r[col(name)] !== undefined ? r[col(name)] : undefined);
    const id = (get("id") ?? "").trim();
    if (!id) {
      issues.push({ level: "error", message: "Row has an empty id.", source });
      return;
    }
    const tags = get("tags");
    entries.push({
      id,
      locale: (get("locale") ?? "").trim() || DEFAULT_LOCALE,
      title: get("title"),
      description: get("description"),
      tags: tags !== undefined ? splitTags(tags) : undefined,
      notes: get("notes"),
      source,
    });
  });
  return { entries, issues };
}

// ------------------------------------------------------------------ Markdown

/**
 * ---
 * locale: fr
 * ---
 * ## gentle_smile
 * Title: Sourire doux
 * Tags: positif, sourire
 * Notes: ...
 * Description paragraphs...
 */
export function parseMarkdown(text: string): Partial_ {
  const issues: ParseIssue[] = [];
  const lines = text.split("\n");
  let locale = DEFAULT_LOCALE;
  let start = 0;
  if (lines[0]?.trim() === "---") {
    const end = lines.findIndex((l, i) => i > 0 && l.trim() === "---");
    if (end > 0) {
      for (const l of lines.slice(1, end)) {
        const m = l.match(/^\s*locale\s*:\s*(.+?)\s*$/i);
        if (m) locale = m[1];
      }
      start = end + 1;
    } else issues.push({ level: "warning", message: "Front matter opened with --- but never closed; ignored." });
  }
  const entries: ContentEntry[] = [];
  let cur: (ContentEntry & { body: string[] }) | null = null;
  const flush = () => {
    if (!cur) return;
    const desc = cur.body.join("\n").trim();
    const { body, ...rest } = cur;
    void body;
    entries.push({ ...rest, description: desc || undefined });
    cur = null;
  };
  for (let i = start; i < lines.length; i++) {
    const line = lines[i];
    const h = line.match(/^##\s+(.+?)\s*$/);
    if (h) {
      flush();
      cur = { id: h[1].replace(/`/g, "").trim(), locale, source: i + 1, body: [] };
      continue;
    }
    if (/^#\s/.test(line)) continue; // document title
    if (!cur) {
      if (line.trim()) issues.push({ level: "info", message: "Text before the first '## <id>' heading is ignored.", source: i + 1 });
      continue;
    }
    const field = line.match(/^\s*(title|tags|notes)\s*:\s*(.*)$/i);
    if (field && cur.body.every((b) => !b.trim())) {
      const k = field[1].toLowerCase();
      if (k === "title") cur.title = field[2].trim();
      else if (k === "tags") cur.tags = splitTags(field[2]);
      else cur.notes = field[2].trim();
      continue;
    }
    cur.body.push(line);
  }
  flush();
  if (!entries.length) issues.push({ level: "error", message: "No '## <expression_id>' sections found." });
  return { entries, issues };
}

// ------------------------------------------------------------------ TXT

/**
 * locale: de            (optional, any line; applies to the lines below it)
 * gentle_smile: A subtle natural smile.
 * gentle_smile | Gentle Smile | A subtle natural smile.
 * # comments and blank lines are ignored
 */
export function parseTxt(text: string): Partial_ {
  const issues: ParseIssue[] = [];
  const entries: ContentEntry[] = [];
  let locale = DEFAULT_LOCALE;
  text.split("\n").forEach((raw, i) => {
    const source = i + 1;
    const line = raw.trim();
    if (!line || line.startsWith("#")) return;
    const loc = line.match(/^locale\s*:\s*(\S+)$/i);
    if (loc) {
      locale = loc[1];
      return;
    }
    if (line.includes("|")) {
      const [id, title, ...desc] = line.split("|").map((s) => s.trim());
      entries.push({ id, locale, title: title || undefined, description: desc.join(" | ") || undefined, source });
      return;
    }
    // Anything before the first colon is the ID; validation reports bad IDs and suggests fixes.
    const m = line.match(/^([^:]+?)\s*:\s*(.*)$/);
    if (!m) {
      issues.push({ level: "error", message: `Cannot read line (expected "id: description" or "id | title | description").`, source });
      return;
    }
    entries.push({ id: m[1], locale, description: m[2] || undefined, source });
  });
  if (!entries.length && !issues.length) issues.push({ level: "error", message: "No entries found." });
  return { entries, issues };
}

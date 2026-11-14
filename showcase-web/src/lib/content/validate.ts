import { EXPRESSION_IDS, EXPRESSIONS, expressionById } from "@/data/expressions";
import type { ContentEntry, ContentStore, ParsedContent, ParseIssue } from "./types";

export const ID_PATTERN = /^[a-z][a-z0-9_]*$/;
export const LOCALE_PATTERN = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;

export type EntryStatus = "new" | "unchanged" | "conflict" | "invalid" | "duplicate";

export interface CheckedEntry extends ContentEntry {
  status: EntryStatus;
  /** Fields whose incoming value differs from a non-empty stored value. */
  conflicts: Array<"title" | "description" | "tags" | "notes">;
  problem?: string;
  /** The closest manifest ID, for typo hints. */
  suggestion?: string;
}

export interface ValidationReport {
  entries: CheckedEntry[];
  issues: ParseIssue[];
  locales: string[];
  counts: Record<EntryStatus, number>;
  invalidIds: string[];
  unknownIds: string[];
  duplicateIds: string[];
  /** Per locale in the file: manifest IDs the file does not cover. */
  missingByLocale: Record<string, string[]>;
  canApply: boolean;
}

function levenshtein(a: string, b: string): number {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}

export function suggestId(id: string): string | undefined {
  const norm = id.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (EXPRESSION_IDS.has(norm)) return norm;
  let best: string | undefined;
  let bestD = Infinity;
  for (const e of EXPRESSIONS) {
    const dd = levenshtein(norm, e.id);
    if (dd < bestD) {
      bestD = dd;
      best = e.id;
    }
  }
  return bestD <= Math.max(2, Math.floor(norm.length / 5)) ? best : undefined;
}

const same = (a: string[] | undefined, b: string[]) => (a ?? []).join("\u0000") === b.join("\u0000");

export function validate(parsed: ParsedContent, store: ContentStore): ValidationReport {
  const issues = [...parsed.issues];
  const seen = new Map<string, number>();
  const entries: CheckedEntry[] = [];
  const invalidIds = new Set<string>();
  const unknownIds = new Set<string>();
  const duplicateIds = new Set<string>();

  for (const e of parsed.entries) {
    const key = `${e.locale}\u0000${e.id}`;
    const base: CheckedEntry = { ...e, status: "new", conflicts: [] };
    if (!LOCALE_PATTERN.test(e.locale)) {
      entries.push({ ...base, status: "invalid", problem: `Invalid locale "${e.locale}" (use codes like en, fr, pt-BR).` });
      continue;
    }
    if (!ID_PATTERN.test(e.id)) {
      invalidIds.add(e.id);
      entries.push({ ...base, status: "invalid", problem: "ID must be lowercase letters, digits and underscores.", suggestion: suggestId(e.id) });
      continue;
    }
    if (!EXPRESSION_IDS.has(e.id)) {
      unknownIds.add(e.id);
      entries.push({ ...base, status: "invalid", problem: "Not one of the 60 expression IDs.", suggestion: suggestId(e.id) });
      continue;
    }
    if (seen.has(key)) {
      duplicateIds.add(e.id);
      entries.push({ ...base, status: "duplicate", problem: `Duplicate of the entry at ${seen.get(key) ? `line/item ${seen.get(key)}` : "an earlier item"} for locale ${e.locale}; the first one is used.` });
      continue;
    }
    seen.set(key, e.source ?? 0);
    const stored = store[e.locale]?.[e.id];
    const conflicts: CheckedEntry["conflicts"] = [];
    let changed = false;
    if (stored) {
      for (const k of ["title", "description", "notes"] as const) {
        const v = e[k];
        if (v === undefined || v === stored[k]) continue;
        changed = true;
        if (stored[k]) conflicts.push(k);
      }
      if (e.tags !== undefined && !same(e.tags, stored.tags)) {
        changed = true;
        if (stored.tags.length) conflicts.push("tags");
      }
    }
    entries.push({ ...base, status: !stored ? "new" : conflicts.length ? "conflict" : changed ? "new" : "unchanged", conflicts });
  }

  const locales = [...new Set(parsed.entries.map((e) => e.locale))].filter((l) => LOCALE_PATTERN.test(l));
  const missingByLocale: Record<string, string[]> = {};
  for (const loc of locales) {
    const covered = new Set(entries.filter((e) => e.locale === loc && e.status !== "invalid" && e.status !== "duplicate").map((e) => e.id));
    missingByLocale[loc] = EXPRESSIONS.filter((x) => !covered.has(x.id)).map((x) => x.id);
  }
  const counts = { new: 0, unchanged: 0, conflict: 0, invalid: 0, duplicate: 0 } as Record<EntryStatus, number>;
  entries.forEach((e) => counts[e.status]++);
  const fatal = issues.some((i) => i.level === "error" && i.source === undefined);
  return {
    entries,
    issues,
    locales,
    counts,
    invalidIds: [...invalidIds],
    unknownIds: [...unknownIds],
    duplicateIds: [...duplicateIds],
    missingByLocale,
    canApply: !fatal && entries.some((e) => e.status === "new" || e.status === "conflict"),
  };
}

export const displayNameOf = (id: string) => expressionById(id)?.displayName ?? id;

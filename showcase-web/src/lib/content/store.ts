import type { ContentStore, StoredEntry } from "./types";
import type { CheckedEntry } from "./validate";

export const STORAGE_KEY = "fes.content.v1";

export interface ApplyOptions {
  /** Conflicting fields are only replaced for these "locale\0id" keys. Everything else keeps the stored text. */
  overwrite: ReadonlySet<string>;
  origin: string;
  now?: string;
}

export const entryKey = (locale: string, id: string) => `${locale}\u0000${id}`;

const blank = (origin: string, now: string): StoredEntry => ({ title: "", description: "", tags: [], notes: "", updatedAt: now, origin });

/**
 * Merge validated entries into a copy of the store. Never destructive by default:
 * - empty stored fields are filled;
 * - non-empty stored fields are replaced only when the user ticked that entry for overwrite;
 * - invalid and duplicate entries are skipped.
 */
export function applyEntries(store: ContentStore, entries: CheckedEntry[], opts: ApplyOptions): { store: ContentStore; applied: number; skipped: number } {
  const now = opts.now ?? new Date().toISOString();
  const next: ContentStore = Object.fromEntries(Object.entries(store).map(([l, m]) => [l, { ...m }]));
  let applied = 0;
  let skipped = 0;
  for (const e of entries) {
    if (e.status === "invalid" || e.status === "duplicate" || e.status === "unchanged") {
      skipped++;
      continue;
    }
    const allow = opts.overwrite.has(entryKey(e.locale, e.id));
    if (e.status === "conflict" && !allow && e.conflicts.length && !hasFillable(store[e.locale]?.[e.id], e)) {
      skipped++;
      continue;
    }
    const cur = next[e.locale]?.[e.id] ?? blank(opts.origin, now);
    const out: StoredEntry = { ...cur };
    let touched = false;
    for (const k of ["title", "description", "notes"] as const) {
      const v = e[k];
      if (v === undefined || v === cur[k]) continue;
      if (cur[k] && !allow) continue;
      out[k] = v;
      touched = true;
    }
    if (e.tags !== undefined && e.tags.join("\0") !== cur.tags.join("\0") && (!cur.tags.length || allow)) {
      out.tags = e.tags;
      touched = true;
    }
    if (!touched) {
      skipped++;
      continue;
    }
    next[e.locale] = { ...(next[e.locale] ?? {}), [e.id]: { ...out, updatedAt: now, origin: opts.origin } };
    applied++;
  }
  return { store: next, applied, skipped };
}

function hasFillable(stored: StoredEntry | undefined, e: CheckedEntry): boolean {
  if (!stored) return true;
  return (["title", "description", "notes"] as const).some((k) => e[k] !== undefined && !stored[k]) || (e.tags !== undefined && !stored.tags.length);
}

export function editEntry(store: ContentStore, locale: string, id: string, patch: Partial<Omit<StoredEntry, "updatedAt" | "origin">>, now = new Date().toISOString()): ContentStore {
  const cur = store[locale]?.[id] ?? blank("manual edit", now);
  return { ...store, [locale]: { ...(store[locale] ?? {}), [id]: { ...cur, ...patch, updatedAt: now, origin: "manual edit" } } };
}

export function removeEntry(store: ContentStore, locale: string, id: string): ContentStore {
  if (!store[locale]?.[id]) return store;
  const { [id]: _gone, ...rest } = store[locale];
  void _gone;
  const next = { ...store, [locale]: rest };
  if (!Object.keys(rest).length) delete next[locale];
  return next;
}

export function loadStore(): ContentStore {
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (!raw) return {};
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? (data as ContentStore) : {};
  } catch {
    return {};
  }
}

export function saveStore(store: ContentStore): boolean {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    return true;
  } catch {
    return false;
  }
}

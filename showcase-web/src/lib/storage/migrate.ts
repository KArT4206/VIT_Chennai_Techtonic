import { EXPRESSION_IDS } from "@/data/expressions";
import type { ContentStore, StoredEntry } from "@/lib/content/types";
import { LOCALE_PATTERN } from "@/lib/content/validate";
import type { ContentRepository, EntryChange } from "./repository";
import { clean } from "./sanitize";

/** Phase 2M stored content in localStorage under this key. */
export const LEGACY_KEY = "fes.content.v1";
/** After a successful migration the legacy value is kept here (not deleted) as a safety copy. */
export const LEGACY_BACKUP_KEY = "fes.content.v1.migrated-backup";
export const MIGRATION_META = "migration.localStorage.v1";

export interface MigrationConflict {
  locale: string;
  id: string;
  /** The value that was in localStorage; IndexedDB already held different text and was kept. */
  legacy: StoredEntry;
}

export interface MigrationResult {
  status: "none" | "migrated" | "already-done" | "failed";
  migrated: number;
  identical: number;
  conflicts: MigrationConflict[];
  rejected: number;
  sanitized: number;
  error?: string;
  at?: string;
}

type KV = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const blankEntry = (): StoredEntry => ({ title: "", description: "", tags: [], notes: "", updatedAt: new Date(0).toISOString(), origin: "localStorage migration" });

function coerce(raw: unknown): { entry: StoredEntry; sanitized: boolean } | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const s = (v: unknown) => (typeof v === "string" ? v : "");
  const fields = { title: s(r.title), description: s(r.description), notes: s(r.notes) };
  const cleaned = { title: clean(fields.title), description: clean(fields.description), notes: clean(fields.notes) };
  const tags = Array.isArray(r.tags) ? r.tags.filter((t): t is string => typeof t === "string").map(clean).filter(Boolean) : [];
  const sanitized = cleaned.title !== fields.title || cleaned.description !== fields.description || cleaned.notes !== fields.notes;
  return {
    entry: { ...blankEntry(), ...cleaned, tags, updatedAt: s(r.updatedAt) || blankEntry().updatedAt, origin: s(r.origin) ? `${s(r.origin)} (migrated)` : "localStorage migration" },
    sanitized,
  };
}

const sameText = (a: StoredEntry, b: StoredEntry) => a.title === b.title && a.description === b.description && a.notes === b.notes && a.tags.join("\u0000") === b.tags.join("\u0000");

/**
 * Copy Phase 2M localStorage content into the repository, once.
 * - Entries not yet in IndexedDB are added.
 * - Entries already in IndexedDB are never overwritten; differing legacy values are recorded as
 *   conflicts (kept in meta) so nothing is lost.
 * - Unknown IDs / invalid locales are skipped and counted.
 * - On any error nothing is removed from localStorage and the result reports "failed".
 * - On success the legacy value is moved to LEGACY_BACKUP_KEY (kept, not deleted).
 */
export async function migrateLocalStorage(repo: ContentRepository, kv: KV | null): Promise<MigrationResult> {
  const empty: MigrationResult = { status: "none", migrated: 0, identical: 0, conflicts: [], rejected: 0, sanitized: 0 };
  try {
    const prior = await repo.getMeta<MigrationResult>(MIGRATION_META);
    if (prior && (prior.status === "migrated" || prior.status === "none")) {
      // A legacy value written after migration (e.g. by an old tab) is migrated again below.
      if (!kv?.getItem(LEGACY_KEY)) return { ...prior, status: prior.status === "migrated" ? "already-done" : "none" };
    }
    const raw = kv?.getItem(LEGACY_KEY) ?? null;
    if (!raw) {
      if (!prior) await repo.setMeta(MIGRATION_META, { ...empty, at: new Date().toISOString() });
      return empty;
    }
    let legacy: ContentStore;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not an object");
      legacy = parsed as ContentStore;
    } catch (e) {
      const r: MigrationResult = { ...empty, status: "failed", error: `Legacy content is not valid JSON (${(e as Error).message}); it was left untouched in localStorage.` };
      await repo.setMeta(MIGRATION_META, { ...r, at: new Date().toISOString() });
      return r;
    }
    const existing = await repo.loadAll();
    const changes: EntryChange[] = [];
    const result: MigrationResult = { ...empty, status: "migrated", at: new Date().toISOString() };
    for (const [locale, entries] of Object.entries(legacy)) {
      if (!LOCALE_PATTERN.test(locale) || !entries || typeof entries !== "object") {
        result.rejected += entries && typeof entries === "object" ? Object.keys(entries).length : 1;
        continue;
      }
      for (const [id, rawEntry] of Object.entries(entries)) {
        const c = EXPRESSION_IDS.has(id) ? coerce(rawEntry) : null;
        if (!c) {
          result.rejected++;
          continue;
        }
        if (c.sanitized) result.sanitized++;
        const cur = existing[locale]?.[id];
        if (!cur) {
          changes.push({ locale, id, entry: c.entry });
          result.migrated++;
        } else if (sameText(cur, c.entry)) result.identical++;
        else result.conflicts.push({ locale, id, legacy: c.entry });
      }
    }
    await repo.write(changes);
    const prevConflicts = prior?.conflicts ?? [];
    await repo.setMeta(MIGRATION_META, { ...result, conflicts: [...prevConflicts, ...result.conflicts] });
    kv?.setItem(LEGACY_BACKUP_KEY, raw);
    kv?.removeItem(LEGACY_KEY);
    return result;
  } catch (e) {
    return { ...empty, status: "failed", error: `Migration failed: ${(e as Error).message}. localStorage content was left untouched.` };
  }
}

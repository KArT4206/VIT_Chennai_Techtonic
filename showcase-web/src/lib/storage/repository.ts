/**
 * Content repository: the only code that touches persistent storage.
 *
 * IndexedDbRepository (database "facial-expression-studio", version 1)
 *   entries  keyPath [locale, id]   one record per expression and language
 *   imports  keyPath importId (auto) import history: file metadata, sanitized file text, result counts
 *   meta     keyPath key             migration status and other bookkeeping
 *
 * MemoryRepository is used when IndexedDB is unavailable (e.g. blocked storage). The UI then warns
 * that nothing persists. All writes are explicit: callers pass the exact entries to put or delete.
 */

import type { ContentFormat, ContentStore, StoredEntry } from "@/lib/content/types";

export interface EntryRecord extends StoredEntry {
  locale: string;
  id: string;
}

export interface ImportRecord {
  importId?: number;
  fileName: string;
  format: ContentFormat | "backup";
  size: number;
  importedAt: string;
  locales: string[];
  applied: number;
  skipped: number;
  overwritten: number;
  /** File text after sanitizing (plain text only). Omitted for files over MAX_STORED_TEXT. */
  text?: string;
  sanitized: boolean;
}

export interface MetaRecord {
  key: string;
  value: unknown;
}

export interface EntryChange {
  locale: string;
  id: string;
  /** null deletes the entry. */
  entry: StoredEntry | null;
}

export interface ContentRepository {
  readonly kind: "indexeddb" | "memory";
  loadAll(): Promise<ContentStore>;
  /** Applies all changes (and optionally an import record) in one transaction. */
  write(changes: EntryChange[], importRecord?: ImportRecord): Promise<void>;
  listImports(): Promise<ImportRecord[]>;
  getMeta<T>(key: string): Promise<T | undefined>;
  setMeta(key: string, value: unknown): Promise<void>;
  close(): void;
}

export const DB_NAME = "facial-expression-studio";
export const DB_VERSION = 1;
export const MAX_STORED_TEXT = 512 * 1024;

const req = <T>(r: IDBRequest<T>) =>
  new Promise<T>((res, rej) => {
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
const done = (tx: IDBTransaction) =>
  new Promise<void>((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
    tx.onabort = () => rej(tx.error ?? new Error("Transaction aborted"));
  });

export function toStore(records: EntryRecord[]): ContentStore {
  const s: ContentStore = {};
  for (const { locale, id, ...e } of records) (s[locale] ??= {})[id] = e;
  return s;
}

export class IndexedDbRepository implements ContentRepository {
  readonly kind = "indexeddb" as const;
  private constructor(private db: IDBDatabase) {}

  static async open(factory: IDBFactory = indexedDB, name = DB_NAME): Promise<IndexedDbRepository> {
    const open = factory.open(name, DB_VERSION);
    open.onupgradeneeded = () => {
      const db = open.result;
      if (!db.objectStoreNames.contains("entries")) {
        const s = db.createObjectStore("entries", { keyPath: ["locale", "id"] });
        s.createIndex("locale", "locale");
      }
      if (!db.objectStoreNames.contains("imports")) db.createObjectStore("imports", { keyPath: "importId", autoIncrement: true });
      if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta", { keyPath: "key" });
    };
    const db = await new Promise<IDBDatabase>((res, rej) => {
      open.onsuccess = () => res(open.result);
      open.onerror = () => rej(open.error ?? new Error("IndexedDB open failed"));
      open.onblocked = () => rej(new Error("IndexedDB upgrade is blocked by another open tab"));
    });
    // Let another tab upgrade or delete the database instead of being blocked by this connection.
    db.onversionchange = () => db.close();
    return new IndexedDbRepository(db);
  }

  async loadAll(): Promise<ContentStore> {
    const tx = this.db.transaction("entries", "readonly");
    const all = (await req(tx.objectStore("entries").getAll())) as EntryRecord[];
    return toStore(all);
  }

  async write(changes: EntryChange[], importRecord?: ImportRecord): Promise<void> {
    const tx = this.db.transaction(["entries", "imports"], "readwrite");
    const finished = done(tx);
    try {
      const entries = tx.objectStore("entries");
      for (const c of changes) {
        if (c.entry) entries.put({ ...c.entry, locale: c.locale, id: c.id } satisfies EntryRecord);
        else entries.delete([c.locale, c.id]);
      }
      if (importRecord) {
        const { importId, ...rec } = importRecord;
        void importId;
        tx.objectStore("imports").add(rec);
      }
    } catch (e) {
      // A request that fails while being queued (e.g. an invalid key) must not let the earlier
      // requests commit: abort so the whole batch is all-or-nothing.
      try {
        tx.abort();
      } catch {}
      await finished.catch(() => undefined);
      throw e;
    }
    await finished;
  }

  async listImports(): Promise<ImportRecord[]> {
    const tx = this.db.transaction("imports", "readonly");
    const all = (await req(tx.objectStore("imports").getAll())) as ImportRecord[];
    return all.sort((a, b) => (b.importId ?? 0) - (a.importId ?? 0));
  }

  async getMeta<T>(key: string): Promise<T | undefined> {
    const tx = this.db.transaction("meta", "readonly");
    const r = (await req(tx.objectStore("meta").get(key))) as MetaRecord | undefined;
    return r?.value as T | undefined;
  }

  async setMeta(key: string, value: unknown): Promise<void> {
    const tx = this.db.transaction("meta", "readwrite");
    tx.objectStore("meta").put({ key, value } satisfies MetaRecord);
    await done(tx);
  }

  close() {
    this.db.close();
  }
}

export class MemoryRepository implements ContentRepository {
  readonly kind = "memory" as const;
  private entries = new Map<string, EntryRecord>();
  private imports: ImportRecord[] = [];
  private meta = new Map<string, unknown>();
  private seq = 0;
  async loadAll() {
    return toStore([...this.entries.values()].map((e) => structuredClone(e)));
  }
  async write(changes: EntryChange[], importRecord?: ImportRecord) {
    for (const c of changes) {
      const k = `${c.locale}\u0000${c.id}`;
      if (c.entry) this.entries.set(k, { ...structuredClone(c.entry), locale: c.locale, id: c.id });
      else this.entries.delete(k);
    }
    if (importRecord) this.imports.push({ ...importRecord, importId: ++this.seq });
  }
  async listImports() {
    return [...this.imports].reverse();
  }
  async getMeta<T>(key: string) {
    return this.meta.get(key) as T | undefined;
  }
  async setMeta(key: string, value: unknown) {
    this.meta.set(key, value);
  }
  close() {}
}

/** Entries that differ between two snapshots, as explicit put/delete changes. */
export function diffStores(prev: ContentStore, next: ContentStore): EntryChange[] {
  const out: EntryChange[] = [];
  const locales = new Set([...Object.keys(prev), ...Object.keys(next)]);
  for (const l of locales) {
    const a = prev[l] ?? {};
    const b = next[l] ?? {};
    for (const id of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (!b[id]) out.push({ locale: l, id, entry: null });
      else if (JSON.stringify(a[id]) !== JSON.stringify(b[id])) out.push({ locale: l, id, entry: b[id] });
    }
  }
  return out;
}

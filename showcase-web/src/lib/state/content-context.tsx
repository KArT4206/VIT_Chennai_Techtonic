"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { applyEntries, editEntry, removeEntry } from "@/lib/content/store";
import type { ContentFormat, ContentStore, StoredEntry } from "@/lib/content/types";
import type { CheckedEntry } from "@/lib/content/validate";
import { migrateLocalStorage, type MigrationResult } from "@/lib/storage/migrate";
import { diffStores, IndexedDbRepository, MAX_STORED_TEXT, MemoryRepository, type ContentRepository, type ImportRecord } from "@/lib/storage/repository";
import { clean, sanitizeText } from "@/lib/storage/sanitize";

const LOCALE_KEY = "fes.locale.v1";

export interface StorageState {
  kind: "indexeddb" | "memory" | "loading";
  error?: string;
}

export interface FileMeta {
  fileName: string;
  format: ContentFormat;
  size: number;
  text: string;
}

export interface ImportOutcome {
  applied: number;
  skipped: number;
  overwritten: number;
}

interface ContentCtx {
  store: ContentStore;
  hydrated: boolean;
  storage: StorageState;
  migration: MigrationResult | null;
  imports: ImportRecord[];
  locale: string;
  setLocale: (l: string) => void;
  locales: string[];
  entry: (id: string, locale?: string) => StoredEntry | undefined;
  /** Writes the reviewed entries (and an import-history record) in one transaction. */
  commitImport: (entries: CheckedEntry[], overwrite: ReadonlySet<string>, file: FileMeta) => Promise<ImportOutcome>;
  saveEntry: (locale: string, id: string, patch: Partial<Omit<StoredEntry, "updatedAt" | "origin">>) => Promise<void>;
  deleteEntry: (locale: string, id: string) => Promise<void>;
}

const Ctx = createContext<ContentCtx | null>(null);

function safeLocalStorage(): Storage | null {
  try {
    const s = window.localStorage;
    s.getItem("__probe__");
    return s;
  } catch {
    return null;
  }
}

export function ContentProvider({ children }: { children: ReactNode }) {
  const repoRef = useRef<ContentRepository | null>(null);
  const storeRef = useRef<ContentStore>({});
  const [store, setStoreState] = useState<ContentStore>({});
  const [hydrated, setHydrated] = useState(false);
  const [storage, setStorage] = useState<StorageState>({ kind: "loading" });
  const [migration, setMigration] = useState<MigrationResult | null>(null);
  const [imports, setImports] = useState<ImportRecord[]>([]);
  const [locale, setLocaleState] = useState("en");

  const setStore = (s: ContentStore) => {
    storeRef.current = s;
    setStoreState(s);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let repo: ContentRepository;
      try {
        if (typeof indexedDB === "undefined") throw new Error("IndexedDB is not available in this browser");
        repo = await IndexedDbRepository.open();
        setStorage({ kind: "indexeddb" });
      } catch (e) {
        repo = new MemoryRepository();
        setStorage({ kind: "memory", error: `${(e as Error).message}. Content will not persist after this page is closed; export a backup to keep it.` });
      }
      if (cancelled) return repo.close();
      repoRef.current = repo;
      const ls = safeLocalStorage();
      if (repo.kind === "indexeddb") setMigration(await migrateLocalStorage(repo, ls));
      try {
        const [all, hist] = await Promise.all([repo.loadAll(), repo.listImports()]);
        if (cancelled) return;
        setStore(all);
        setImports(hist);
      } catch (e) {
        setStorage({ kind: repo.kind, error: `Could not read stored content: ${(e as Error).message}` });
      }
      const l = ls?.getItem(LOCALE_KEY);
      if (l) setLocaleState(l);
      setHydrated(true);
    })();
    return () => {
      cancelled = true;
      repoRef.current?.close();
      repoRef.current = null;
    };
  }, []);

  const setLocale = useCallback((l: string) => {
    setLocaleState(l);
    safeLocalStorage()?.setItem(LOCALE_KEY, l);
  }, []);

  const persist = useCallback(async (next: ContentStore, record?: ImportRecord) => {
    const repo = repoRef.current;
    if (!repo) throw new Error("Storage is not ready yet");
    const changes = diffStores(storeRef.current, next);
    await repo.write(changes, record); // throws -> state untouched
    setStore(next);
    if (record) setImports(await repo.listImports());
  }, []);

  const commitImport = useCallback(
    async (entries: CheckedEntry[], overwrite: ReadonlySet<string>, file: FileMeta): Promise<ImportOutcome> => {
      const { store: next, applied, skipped } = applyEntries(storeRef.current, entries, { overwrite, origin: file.fileName });
      const s = sanitizeText(file.text);
      const record: ImportRecord = {
        fileName: clean(file.fileName),
        format: s.text.includes('"facial-expression-studio-backup"') ? "backup" : file.format,
        size: file.size,
        importedAt: new Date().toISOString(),
        locales: [...new Set(entries.map((e) => e.locale))],
        applied,
        skipped,
        overwritten: overwrite.size,
        text: s.text.length <= MAX_STORED_TEXT ? s.text : undefined,
        sanitized: s.changed,
      };
      await persist(next, record);
      return { applied, skipped, overwritten: overwrite.size };
    },
    [persist],
  );

  const saveEntry = useCallback(
    async (l: string, id: string, patch: Partial<Omit<StoredEntry, "updatedAt" | "origin">>) => {
      const p = { ...patch };
      if (p.title !== undefined) p.title = clean(p.title);
      if (p.description !== undefined) p.description = clean(p.description);
      if (p.notes !== undefined) p.notes = clean(p.notes);
      if (p.tags) p.tags = p.tags.map(clean).filter(Boolean);
      await persist(editEntry(storeRef.current, l, id, p));
    },
    [persist],
  );

  const deleteEntry = useCallback(async (l: string, id: string) => persist(removeEntry(storeRef.current, l, id)), [persist]);

  const locales = useMemo(() => [...new Set(["en", ...Object.keys(store), locale])].sort(), [store, locale]);
  const entry = useCallback((id: string, l?: string) => store[l ?? locale]?.[id], [store, locale]);

  const value = useMemo(
    () => ({ store, hydrated, storage, migration, imports, locale, setLocale, locales, entry, commitImport, saveEntry, deleteEntry }),
    [store, hydrated, storage, migration, imports, locale, setLocale, locales, entry, commitImport, saveEntry, deleteEntry],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useContent(): ContentCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useContent must be used inside ContentProvider");
  return c;
}

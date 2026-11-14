"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { loadStore, saveStore } from "@/lib/content/store";
import type { ContentStore, StoredEntry } from "@/lib/content/types";

const LOCALE_KEY = "fes.locale.v1";

interface ContentCtx {
  store: ContentStore;
  setStore: (next: ContentStore) => void;
  locale: string;
  setLocale: (l: string) => void;
  locales: string[];
  entry: (id: string, locale?: string) => StoredEntry | undefined;
  hydrated: boolean;
  persistError: boolean;
}

const Ctx = createContext<ContentCtx | null>(null);

export function ContentProvider({ children }: { children: ReactNode }) {
  const [store, setStoreState] = useState<ContentStore>({});
  const [locale, setLocaleState] = useState("en");
  const [hydrated, setHydrated] = useState(false);
  const [persistError, setPersistError] = useState(false);

  useEffect(() => {
    setStoreState(loadStore());
    try {
      const l = window.localStorage.getItem(LOCALE_KEY);
      if (l) setLocaleState(l);
    } catch {}
    setHydrated(true);
  }, []);

  const setStore = useCallback((next: ContentStore) => {
    setStoreState(next);
    setPersistError(!saveStore(next));
  }, []);

  const setLocale = useCallback((l: string) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(LOCALE_KEY, l);
    } catch {}
  }, []);

  const locales = useMemo(() => [...new Set(["en", ...Object.keys(store), locale])].sort(), [store, locale]);
  const entry = useCallback((id: string, l?: string) => store[l ?? locale]?.[id], [store, locale]);

  const value = useMemo(() => ({ store, setStore, locale, setLocale, locales, entry, hydrated, persistError }), [store, setStore, locale, setLocale, locales, entry, hydrated, persistError]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useContent(): ContentCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useContent must be used inside ContentProvider");
  return c;
}

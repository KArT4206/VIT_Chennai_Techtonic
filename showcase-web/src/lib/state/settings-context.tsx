"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { coerceSettings, DEFAULT_SETTINGS, SETTINGS_KEY, type Settings } from "@/lib/settings/settings";

interface SettingsCtx {
  settings: Settings;
  hydrated: boolean;
  update: (patch: Partial<Settings>) => void;
  replace: (s: Settings) => void;
  reset: () => void;
}

const Ctx = createContext<SettingsCtx | null>(null);

function write(s: Settings) {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {}
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SETTINGS_KEY);
      if (raw) setSettings(coerceSettings(JSON.parse(raw)).settings);
    } catch {}
    setHydrated(true);
  }, []);

  const replace = useCallback((s: Settings) => {
    setSettings(s);
    write(s);
  }, []);
  const update = useCallback((patch: Partial<Settings>) => setSettings((cur) => {
    const next = coerceSettings({ ...cur, ...patch }).settings;
    write(next);
    return next;
  }), []);
  const reset = useCallback(() => replace(DEFAULT_SETTINGS), [replace]);

  const value = useMemo(() => ({ settings, hydrated, update, replace, reset }), [settings, hydrated, update, replace, reset]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): SettingsCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSettings must be used inside SettingsProvider");
  return c;
}

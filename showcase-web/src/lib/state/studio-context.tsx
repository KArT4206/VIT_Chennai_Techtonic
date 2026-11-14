"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { EXPRESSIONS } from "@/data/expressions";
import type { CharacterAdapter, PlaybackState, PlayOptions } from "@/lib/character/adapter";
import type { CameraPresetId } from "@/lib/character/cameras";
import { createCharacterAdapter } from "@/lib/character/registry";

const FAV_KEY = "fes.favourites.v1";
const RECENT_KEY = "fes.recent.v1";
const RECENT_MAX = 8;

interface StudioCtx {
  adapter: CharacterAdapter;
  selectedId: string;
  select: (id: string) => void;
  favourites: string[];
  toggleFavourite: (id: string) => void;
  recent: string[];
  opts: PlayOptions;
  setOpts: (patch: Partial<PlayOptions>) => void;
  camera: CameraPresetId;
  setCamera: (c: CameraPresetId) => void;
  /** Increments when the user asks to re-apply the current camera preset. */
  cameraNonce: number;
  playback: PlaybackState;
  play: () => void;
  pause: () => void;
  neutral: () => void;
  replay: () => void;
}

const Ctx = createContext<StudioCtx | null>(null);

const readList = (k: string): string[] => {
  try {
    const v = JSON.parse(window.localStorage.getItem(k) ?? "[]");
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && EXPRESSIONS.some((e) => e.id === x)) : [];
  } catch {
    return [];
  }
};
const writeList = (k: string, v: string[]) => {
  try {
    window.localStorage.setItem(k, JSON.stringify(v));
  } catch {}
};

export function StudioProvider({ children }: { children: ReactNode }) {
  const adapterRef = useRef<CharacterAdapter | null>(null);
  if (!adapterRef.current) adapterRef.current = createCharacterAdapter();
  const adapter = adapterRef.current;

  const [selectedId, setSelectedId] = useState(EXPRESSIONS[0].id);
  const [favourites, setFavourites] = useState<string[]>([]);
  const [recent, setRecent] = useState<string[]>([]);
  const [opts, setOptsState] = useState<PlayOptions>({ intensity: 1, speed: 1, asymmetry: 0 });
  const [camera, setCameraState] = useState<CameraPresetId>("front");
  const [cameraNonce, setNonce] = useState(0);
  const [playback, setPlayback] = useState<PlaybackState>("neutral");

  useEffect(() => {
    setFavourites(readList(FAV_KEY));
    setRecent(readList(RECENT_KEY));
  }, []);

  const select = useCallback(
    (id: string) => {
      setSelectedId(id);
      setRecent((r) => {
        const next = [id, ...r.filter((x) => x !== id)].slice(0, RECENT_MAX);
        writeList(RECENT_KEY, next);
        return next;
      });
      adapter.neutral();
      setPlayback("neutral");
    },
    [adapter],
  );

  const toggleFavourite = useCallback((id: string) => {
    setFavourites((f) => {
      const next = f.includes(id) ? f.filter((x) => x !== id) : [...f, id];
      writeList(FAV_KEY, next);
      return next;
    });
  }, []);

  const setOpts = useCallback(
    (patch: Partial<PlayOptions>) =>
      setOptsState((o) => {
        const next = { ...o, ...patch };
        adapter.update(next);
        return next;
      }),
    [adapter],
  );

  const setCamera = useCallback((c: CameraPresetId) => {
    setCameraState(c);
    setNonce((n) => n + 1);
  }, []);

  // Every transport action goes through the adapter; with the pending adapter nothing plays.
  const play = useCallback(() => {
    if (playback === "paused") {
      adapter.resume();
      setPlayback("playing");
    } else if (adapter.play(selectedId, opts)) setPlayback("playing");
  }, [adapter, playback, selectedId, opts]);
  const pause = useCallback(() => {
    adapter.pause();
    if (playback === "playing") setPlayback("paused");
  }, [adapter, playback]);
  const neutral = useCallback(() => {
    adapter.neutral();
    setPlayback("neutral");
  }, [adapter]);
  const replay = useCallback(() => {
    if (adapter.replay(selectedId, opts)) setPlayback("playing");
  }, [adapter, selectedId, opts]);

  const value = useMemo(
    () => ({ adapter, selectedId, select, favourites, toggleFavourite, recent, opts, setOpts, camera, setCamera, cameraNonce, playback, play, pause, neutral, replay }),
    [adapter, selectedId, select, favourites, toggleFavourite, recent, opts, setOpts, camera, setCamera, cameraNonce, playback, play, pause, neutral, replay],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStudio(): StudioCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useStudio must be used inside StudioProvider");
  return c;
}

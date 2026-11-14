"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { expressionById } from "@/data/expressions";
import { CAMERA_PRESETS } from "@/lib/character/cameras";
import { useContent } from "@/lib/state/content-context";
import { useStudio } from "@/lib/state/studio-context";

const ViewerScene = dynamic(() => import("./ViewerScene"), {
  ssr: false,
  loading: () => <div className="grid h-full place-items-center text-xs text-ink-400">Starting 3D viewport…</div>,
});

export function ViewerPanel() {
  const { camera, setCamera, cameraNonce, adapter, selectedId, neutral, playback } = useStudio();
  const { entry } = useContent();
  const box = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(false);

  useEffect(() => {
    const on = () => setFull(document.fullscreenElement === box.current);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const toggleFull = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void box.current?.requestFullscreen?.();
  }, []);

  const e = expressionById(selectedId)!;
  const pending = adapter.status !== "ready";

  return (
    <div ref={box} className="relative flex min-h-0 flex-1 flex-col bg-ink-950">
      <div className="flex flex-wrap items-center gap-1 border-b border-ink-800 px-3 py-2">
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Camera view">
          {CAMERA_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setCamera(p.id)}
              aria-pressed={camera === p.id}
              className={`rounded-md px-2.5 py-1 text-xs transition-colors ${camera === p.id ? "bg-ink-700 text-ink-100" : "text-ink-300 hover:bg-ink-850 hover:text-ink-100"}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <button type="button" onClick={neutral} className="rounded-md px-2.5 py-1 text-xs text-ink-300 hover:bg-ink-850 hover:text-ink-100" title="Return the character to its neutral pose">
            Neutral pose
          </button>
          <button type="button" onClick={toggleFull} className="rounded-md px-2.5 py-1 text-xs text-ink-300 hover:bg-ink-850 hover:text-ink-100" aria-pressed={full}>
            {full ? "Exit fullscreen" : "Fullscreen"}
          </button>
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <div className="absolute inset-0">
          <ViewerScene camera={camera} nonce={cameraNonce} />
        </div>

        {pending && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center p-6">
            <div className="pointer-events-auto max-w-sm rounded-xl border border-ink-700/80 bg-ink-900/85 px-6 py-5 text-center shadow-2xl shadow-black/40 backdrop-blur-md">
              <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full border border-accent-500/40 bg-accent-900/50 text-accent-400">
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
                  <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z" strokeLinejoin="round" />
                  <path d="M4 7.5 12 12l8-4.5M12 12v9" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="text-base font-semibold text-ink-100">3D character asset pending import</p>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-300">
                The viewport, cameras and controls are live. Expressions will play here once the approved character and its animation clips are imported.
              </p>
            </div>
          </div>
        )}

        <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex items-end justify-between gap-3">
          <div className="rounded-lg bg-ink-900/80 px-3 py-2 backdrop-blur">
            <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400">Selected</p>
            <p className="text-sm font-medium text-ink-100">{entry(e.id)?.title || e.displayName}</p>
          </div>
          <div className="rounded-lg bg-ink-900/80 px-3 py-2 text-right backdrop-blur">
            <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400">Character</p>
            <p className={`text-xs ${pending ? "text-warn-500" : "text-ok-500"}`}>{pending ? "Pending import" : `${adapter.info?.name ?? "Loaded"} · ${playback}`}</p>
          </div>
        </div>
        <p className="pointer-events-none absolute right-3 top-3 hidden rounded bg-ink-900/70 px-2 py-1 text-[10px] text-ink-400 md:block">Drag to orbit · scroll to zoom · right-drag to pan</p>
      </div>
    </div>
  );
}

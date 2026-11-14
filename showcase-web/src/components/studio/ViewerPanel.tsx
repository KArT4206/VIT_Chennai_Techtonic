"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { expressionById } from "@/data/expressions";
import { CAMERA_PRESETS } from "@/lib/character/cameras";
import Link from "next/link";
import type { Verdict } from "@/lib/assets/gltf-inspect";
import { useAssets } from "@/lib/state/assets-context";
import { useContent } from "@/lib/state/content-context";
import { useSettings } from "@/lib/state/settings-context";
import { useStudio } from "@/lib/state/studio-context";

const ViewerScene = dynamic(() => import("./ViewerScene"), {
  ssr: false,
  loading: () => <div className="grid h-full place-items-center text-xs text-ink-400">Starting 3D viewport…</div>,
});

export function ViewerPanel() {
  const { camera, setCamera, cameraNonce, adapter, selectedId, neutral, playback } = useStudio();
  const { entry } = useContent();
  const { settings } = useSettings();
  const { character } = useAssets();
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
          <ViewerScene camera={camera} nonce={cameraNonce} quality={settings.quality} adapter={adapter} />
        </div>

        {pending && <EmptyState storedName={character?.fileName ?? null} verdict={character?.report.verdict ?? null} />}

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

const VERDICT_TEXT: Record<Verdict, string> = {
  "not-compatible": "failed required compatibility checks",
  "partially-ready": "passed with warnings",
  "structurally-ready": "passed all structural checks",
};

function EmptyState({ storedName, verdict }: { storedName: string | null; verdict: Verdict | null }) {
  const steps = [
    { label: "Character file imported", done: !!storedName },
    { label: "Compatibility review passed", done: verdict === "structurally-ready" },
    { label: "Expression clips connected to the studio", done: false },
  ];
  return (
    <div className="pointer-events-none absolute inset-0 grid place-items-center p-6">
      <div className="pointer-events-auto w-full max-w-md rounded-2xl border border-ink-700/70 bg-ink-900/90 p-7 shadow-2xl shadow-black/50 backdrop-blur-md">
        <div className="flex items-start gap-4">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-ink-600 bg-ink-850 text-ink-300">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
              <circle cx="12" cy="8" r="3.5" />
              <path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" strokeLinecap="round" />
              <path d="M18.5 3.5v5M16 6h5" strokeLinecap="round" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="text-lg font-semibold text-ink-100">No character loaded</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-300">
              {storedName ? (
                <>
                  <span className="font-mono text-ink-200">{storedName}</span> is stored and {verdict ? VERDICT_TEXT[verdict] : "has not been checked"}, but it is not connected to this viewport yet. Nothing shown here is a character.
                </>
              ) : (
                "This viewport has no 3D character yet. Import a glTF character (.glb) to check its face rig, textures and expression clips. Until a real character is connected, no face is shown and nothing is animated."
              )}
            </p>
          </div>
        </div>
        <ol className="mt-5 space-y-2 border-t border-ink-800 pt-4">
          {steps.map((s, i) => (
            <li key={s.label} className="flex items-center gap-3 text-sm">
              <span className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${s.done ? "bg-ok-500/20 text-ok-500" : "border border-ink-600 text-ink-500"}`}>{s.done ? "✓" : i + 1}</span>
              <span className={s.done ? "text-ink-200" : "text-ink-400"}>{s.label}</span>
            </li>
          ))}
        </ol>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Link href="/assets" className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-ink-950 hover:bg-accent-400">
            {storedName ? "Review character" : "Import character"}
          </Link>
          <span className="text-xs text-ink-500">glTF 2.0 · .glb · Blender export guide included</span>
        </div>
      </div>
    </div>
  );
}

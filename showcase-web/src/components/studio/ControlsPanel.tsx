"use client";

import Link from "next/link";
import { categoryById, expressionById } from "@/data/expressions";
import { CAMERA_PRESETS, type CameraPresetId } from "@/lib/character/cameras";
import { useContent } from "@/lib/state/content-context";
import { useSettings } from "@/lib/state/settings-context";
import { useStudio } from "@/lib/state/studio-context";

export function ControlsPanel() {
  const { selectedId, adapter, opts, setOpts, camera, setCamera, playback, play, pause, neutral, replay, favourites, toggleFavourite } = useStudio();
  const { entry, locale } = useContent();
  const { settings } = useSettings();
  const e = expressionById(selectedId)!;
  const c = entry(e.id);
  const ready = adapter.status === "ready";
  const hasClip = ready && adapter.hasClip(e.id);
  const reason = !ready ? "Character asset pending import" : !hasClip ? "No animation clip for this expression yet" : "";
  const fav = favourites.includes(e.id);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="space-y-3 border-b border-ink-800 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-accent-400">{categoryById(e.categoryId).name}</p>
            <h2 className="mt-1 text-xl font-semibold leading-tight text-ink-100">{c?.title || e.displayName}</h2>
          </div>
          <button type="button" onClick={() => toggleFavourite(e.id)} aria-pressed={fav} aria-label={fav ? "Remove from favourites" : "Add to favourites"} className={`rounded-md border px-2 py-1 text-sm ${fav ? "border-accent-500/60 text-accent-400" : "border-ink-700 text-ink-400 hover:text-ink-100"}`}>
            {fav ? "★" : "☆"}
          </button>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
          <dt className="text-ink-400">Expression ID</dt>
          <dd className="font-mono text-ink-200">{e.id}</dd>
          <dt className="text-ink-400">Number</dt>
          <dd className="font-mono text-ink-200">{e.number} of 60</dd>
          <dt className="text-ink-400">Animation</dt>
          <dd className={hasClip ? "text-ok-500" : "text-warn-500"}>{hasClip ? adapter.clipFor(e.id) : "Not available yet"}</dd>
        </dl>
        <div className="flex flex-wrap gap-1">
          {(c?.tags?.length ? c.tags : e.tags).map((t) => (
            <span key={t} className="rounded bg-ink-800 px-1.5 py-0.5 text-[11px] text-ink-300">
              {t}
            </span>
          ))}
        </div>
        <div className="rounded-md border border-ink-800 bg-ink-850 p-3">
          <p className="mb-1 flex items-center justify-between text-[11px] uppercase tracking-wider text-ink-400">
            <span>Description</span>
            <span className="font-mono normal-case tracking-normal">{locale}</span>
          </p>
          {c?.description ? (
            <p className="whitespace-pre-line text-sm leading-relaxed text-ink-200">{c.description}</p>
          ) : (
            <p className="text-sm text-ink-400">
              No description for this language yet.{" "}
              <Link href="/content" className="text-accent-400 underline-offset-2 hover:underline">
                Add one in the Content Manager
              </Link>
              .
            </p>
          )}
          {c?.notes ? <p className="mt-2 border-t border-ink-700 pt-2 text-xs text-ink-400">{c.notes}</p> : null}
        </div>
      </div>

      <div className="space-y-5 border-b border-ink-800 p-5">
        <Slider label="Intensity" value={opts.intensity} min={0} max={1} step={0.01} format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => setOpts({ intensity: v })} />
        <Slider label="Animation speed" value={opts.speed} min={0.25} max={2} step={0.05} format={(v) => `${v.toFixed(2)}×`} onChange={(v) => setOpts({ speed: v })} />
        <Slider
          label="Left / right asymmetry"
          value={opts.asymmetry}
          min={-1}
          max={1}
          step={0.05}
          format={(v) => (Math.abs(v) < 0.025 ? "Symmetric" : v < 0 ? `Left ${Math.round(-v * 100)}%` : `Right ${Math.round(v * 100)}%`)}
          onChange={(v) => setOpts({ asymmetry: v })}
          hint={ready && !adapter.supportsAsymmetry ? "The loaded character has no left/right controls." : undefined}
        />
        <button type="button" onClick={() => setOpts({ intensity: settings.defaultIntensity, speed: settings.playbackSpeed, asymmetry: 0 })} className="text-xs text-ink-400 hover:text-ink-100">
          Reset sliders to defaults
        </button>
      </div>

      <div className="space-y-3 p-5">
        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 grid">
            <TransportButton primary disabled={!hasClip || playback === "playing"} onClick={play} label={playback === "paused" ? "Resume" : "Play expression"} reason={reason || "Already playing"} />
          </div>
          <TransportButton disabled={!hasClip || playback !== "playing"} onClick={pause} label="Pause" reason={reason || "Nothing is playing"} />
          <TransportButton disabled={!hasClip} onClick={replay} label="Replay" reason={reason} />
          <TransportButton disabled={false} onClick={neutral} label="Return to neutral" />
        </div>
        {reason && (
          <p role="status" className="flex items-start gap-2 rounded-md border border-warn-500/30 bg-warn-500/10 px-3 py-2 text-xs leading-relaxed text-warn-500">
            <span aria-hidden>●</span>
            <span>{reason}. Playback is disabled; no facial motion is simulated.</span>
          </p>
        )}
        <label className="block text-xs text-ink-400">
          Camera
          <select value={camera} onChange={(ev) => setCamera(ev.target.value as CameraPresetId)} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-2 py-2 text-sm text-ink-100">
            {CAMERA_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function Slider({ label, value, min, max, step, format, onChange, hint }: { label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onChange: (v: number) => void; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center justify-between text-xs">
        <span className="text-ink-300">{label}</span>
        <span className="font-mono text-ink-100">{format(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full" />
      {hint && <span className="mt-1 block text-[11px] text-ink-400">{hint}</span>}
    </label>
  );
}

function TransportButton({ label, onClick, disabled, primary, reason }: { label: string; onClick: () => void; disabled: boolean; primary?: boolean; reason?: string }) {
  if (disabled)
    return (
      <button
        type="button"
        disabled
        aria-disabled="true"
        title={reason || `${label} is unavailable`}
        className="flex cursor-not-allowed items-center justify-center gap-1.5 rounded-md border border-dashed border-ink-700 bg-ink-900 px-3 py-2 text-sm font-medium text-ink-500"
      >
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
          <rect x="3.5" y="7" width="9" height="6.5" rx="1.2" />
          <path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7" />
        </svg>
        {label}
      </button>
    );
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${primary ? "bg-accent-500 text-ink-950 hover:bg-accent-400" : "border border-ink-700 text-ink-200 hover:border-ink-500 hover:text-ink-100"}`}
    >
      {label}
    </button>
  );
}

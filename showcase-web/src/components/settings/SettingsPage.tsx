"use client";

import { useRef, useState } from "react";
import { download } from "@/components/content/download";
import { ImportPanel } from "@/components/content/ImportPanel";
import { CAMERA_PRESETS, type CameraPresetId } from "@/lib/character/cameras";
import { LOCALE_PATTERN } from "@/lib/content/validate";
import { exportConfig, parseConfig, QUALITY_INFO, type Quality, type Settings } from "@/lib/settings/settings";
import { exportBackup } from "@/lib/storage/backup";
import { useAssets } from "@/lib/state/assets-context";
import { useContent } from "@/lib/state/content-context";
import { useSettings } from "@/lib/state/settings-context";

export function SettingsPage() {
  const { settings, update, replace, reset } = useSettings();
  const { store, imports, locale, setLocale, locales } = useContent();
  const { character } = useAssets();
  const [newLocale, setNewLocale] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const total = Object.values(store).reduce((n, m) => n + Object.keys(m).length, 0);

  const changeLocale = (l: string) => {
    setLocale(l);
    update({ contentLocale: l });
  };

  return (
    <div className="mx-auto w-full max-w-5xl flex-1 space-y-8 px-4 py-8 md:px-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Settings &amp; Export</h1>
        <p className="mt-1 text-sm text-ink-300">Studio defaults, content language, backups and configuration export. Settings are saved in this browser and apply the next time the Studio opens.</p>
      </header>

      <Card title="Studio defaults">
        <div className="grid gap-5 md:grid-cols-2">
          <label className="block text-sm">
            <span className="text-ink-300">Default camera</span>
            <select value={settings.defaultCamera} onChange={(e) => update({ defaultCamera: e.target.value as CameraPresetId })} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-2 py-2 text-ink-100">
              {CAMERA_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <Range label="Playback speed" value={settings.playbackSpeed} min={0.25} max={2} step={0.05} fmt={(v) => `${v.toFixed(2)}×`} onChange={(v) => update({ playbackSpeed: v })} />
          <Range label="Default expression intensity" value={settings.defaultIntensity} min={0} max={1} step={0.01} fmt={(v) => `${Math.round(v * 100)}%`} onChange={(v) => update({ defaultIntensity: v })} />
          <fieldset className="text-sm">
            <legend className="text-ink-300">Animation quality</legend>
            <div className="mt-1 grid grid-cols-3 gap-1 rounded-md border border-ink-700 p-1">
              {(Object.keys(QUALITY_INFO) as Quality[]).map((q) => (
                <button key={q} type="button" aria-pressed={settings.quality === q} onClick={() => update({ quality: q })} className={`rounded px-2 py-1.5 text-xs ${settings.quality === q ? "bg-ink-700 text-ink-100" : "text-ink-300 hover:text-ink-100"}`}>
                  {QUALITY_INFO[q].label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-ink-500">{QUALITY_INFO[settings.quality].note}</p>
          </fieldset>
        </div>
        <div className="mt-5 flex items-center gap-2 border-t border-ink-800 pt-4">
          {confirmReset ? (
            <>
              <span className="text-sm text-warn-500">Reset all studio defaults?</span>
              <button type="button" onClick={() => (reset(), setConfirmReset(false))} className="rounded-md border border-warn-500/60 px-3 py-1.5 text-sm text-warn-500">
                Confirm reset
              </button>
              <button type="button" onClick={() => setConfirmReset(false)} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300">
                Cancel
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setConfirmReset(true)} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300 hover:text-ink-100">
              Reset to defaults…
            </button>
          )}
        </div>
      </Card>

      <Card title="Content language" subtitle="The language used for titles and descriptions in the Studio. Each language is stored separately.">
        <div className="flex flex-wrap items-center gap-2">
          {locales.map((l) => (
            <button key={l} type="button" aria-pressed={l === locale} onClick={() => changeLocale(l)} className={`rounded-md border px-3 py-1.5 font-mono text-sm ${l === locale ? "border-accent-500 bg-accent-900 text-accent-300" : "border-ink-700 text-ink-300 hover:text-ink-100"}`}>
              {l} <span className="opacity-60">{Object.keys(store[l] ?? {}).length}</span>
            </button>
          ))}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (LOCALE_PATTERN.test(newLocale.trim())) {
                changeLocale(newLocale.trim());
                setNewLocale("");
              }
            }}
            className="flex items-center gap-1"
          >
            <input value={newLocale} onChange={(e) => setNewLocale(e.target.value)} placeholder="e.g. fr, pt-BR" aria-label="New language code" className="w-32 rounded-md border border-ink-700 bg-ink-850 px-2 py-1.5 font-mono text-sm text-ink-100 placeholder:text-ink-600" />
            <button type="submit" disabled={!LOCALE_PATTERN.test(newLocale.trim())} className="rounded-md border border-ink-700 px-2 py-1.5 text-sm text-ink-200 disabled:opacity-40">
              Add
            </button>
          </form>
        </div>
      </Card>

      <Card title="Backup and restore" subtitle="Backups contain all text content in every language plus import history. Restoring goes through the same review as any import: existing text is only replaced where you tick Overwrite.">
        <div className="flex flex-wrap gap-2">
          <Btn disabled={!total} onClick={() => download(`expression-studio-backup.${new Date().toISOString().slice(0, 10)}.json`, exportBackup(store, imports), "application/json")}>
            Download content backup ({total} entries)
          </Btn>
          <Btn disabled={!character} onClick={() => character && downloadBinary(character.fileName, character.data)}>
            {character ? `Download character file (${character.fileName})` : "No character file to back up"}
          </Btn>
        </div>
        <div className="mt-5">
          <ImportPanel />
        </div>
      </Card>

      <ConfigCard settings={settings} replace={replace} setLocale={setLocale} />
    </div>
  );
}

function ConfigCard({ settings, replace, setLocale }: { settings: Settings; replace: (s: Settings) => void; setLocale: (l: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<ReturnType<typeof parseConfig> | null>(null);
  const [done, setDone] = useState(false);
  const read = async (f: File) => {
    setDone(false);
    setPending(parseConfig(await f.text()));
  };
  return (
    <Card title="Export configuration" subtitle="A JSON file with your studio settings plus the fixed expression and camera definitions they refer to. Importing a configuration applies only the settings; the 60 expression IDs are never changed.">
      <div className="flex flex-wrap gap-2">
        <Btn onClick={() => download("expression-studio-config.json", exportConfig(settings), "application/json")}>Export configuration</Btn>
        <Btn onClick={() => input.current?.click()}>Import configuration…</Btn>
        <input
          ref={input}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void read(f);
            e.target.value = "";
          }}
        />
      </div>
      {pending && (
        <div className="mt-4 space-y-2 rounded-lg border border-ink-800 bg-ink-850 p-4 text-sm">
          {pending.error ? (
            <p className="text-err-500">{pending.error}</p>
          ) : (
            <>
              <p className="text-ink-200">
                Settings in file: camera <b>{pending.settings.defaultCamera}</b>, speed <b>{pending.settings.playbackSpeed}×</b>, intensity <b>{Math.round(pending.settings.defaultIntensity * 100)}%</b>, quality <b>{pending.settings.quality}</b>, language <b>{pending.settings.contentLocale}</b>.
              </p>
              {pending.rejected.length > 0 && <p className="text-warn-500">Invalid values ignored (defaults used): {pending.rejected.join(", ")}.</p>}
              {pending.expressionMismatch && <p className="text-warn-500">The file lists a different expression set. It is ignored; the studio&apos;s 60 IDs are unchanged.</p>}
              <div className="flex gap-2">
                <button type="button" onClick={() => (replace(pending.settings), setLocale(pending.settings.contentLocale), setPending(null), setDone(true))} className="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-ink-950">
                  Apply these settings
                </button>
                <button type="button" onClick={() => setPending(null)} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300">
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {done && <p className="mt-3 text-sm text-ok-500">Configuration applied.</p>}
    </Card>
  );
}

function downloadBinary(name: string, data: ArrayBuffer) {
  const url = URL.createObjectURL(new Blob([data], { type: "model/gltf-binary" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-ink-800 bg-ink-900 p-6">
      <h2 className="text-lg font-semibold text-ink-100">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-ink-400">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Range({ label, value, min, max, step, fmt, onChange }: { label: string; value: number; min: number; max: number; step: number; fmt: (v: number) => string; onChange: (v: number) => void }) {
  return (
    <label className="block text-sm">
      <span className="flex justify-between">
        <span className="text-ink-300">{label}</span>
        <span className="font-mono text-ink-100">{fmt(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="mt-2 w-full" />
    </label>
  );
}

function Btn({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="rounded-md border border-ink-700 px-3 py-2 text-sm text-ink-200 hover:border-ink-500 hover:text-ink-100 disabled:cursor-not-allowed disabled:opacity-40">
      {children}
    </button>
  );
}

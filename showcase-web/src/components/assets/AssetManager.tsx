"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import { emptyLicence, type LicenceRecord } from "@/lib/assets/asset-store";
import { useAssets, type Candidate } from "@/lib/state/assets-context";
import type { PreviewStatus } from "./AssetPreview";
import { ReportView, VERDICT_STYLE } from "./ReportView";

const AssetPreview = dynamic(() => import("./AssetPreview"), { ssr: false, loading: () => <div className="grid h-full place-items-center text-xs text-ink-400">Starting preview…</div> });

const fmt = (n: number) => (n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);

export function AssetManager() {
  const { ready, storageKind, storageError, character } = useAssets();
  return (
    <div className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-8 md:px-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Character &amp; Assets</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-300">
          Import the studio character, check its face rig, textures, shape keys and expression clips, and record where it came from. Nothing here creates or simulates animation; a character only plays expressions that its own file contains.
        </p>
      </header>
      {storageError && (
        <p role="alert" className="rounded-md border border-err-500/40 bg-err-500/10 px-4 py-3 text-sm text-err-500">
          {storageError}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">{!ready ? <p className="text-sm text-ink-400">Opening asset storage…</p> : character ? <CurrentCharacter /> : <ImportSection />}</div>
        <aside className="space-y-6">
          <StatusCard />
          <FormatsCard />
        </aside>
      </div>
      {ready && character && <ImportSection replacing />}
      <p className="text-xs text-ink-500">Asset storage: {storageKind === "indexeddb" ? "this browser's IndexedDB (separate from text content)" : storageKind === "memory" ? "memory only (not persisted)" : "opening…"}</p>
    </div>
  );
}

function StatusCard() {
  const { character } = useAssets();
  const rows: Array<[string, string, "ok" | "warn" | "muted"]> = character
    ? [
        ["Character file", character.fileName, "ok"],
        ["Compatibility", VERDICT_STYLE[character.report.verdict].label, character.report.verdict === "structurally-ready" ? "ok" : "warn"],
        ["Expression clips", `${character.report.expressionCoverage.matched.length} of 60 matched`, character.report.expressionCoverage.matched.length === 60 ? "ok" : "warn"],
        ["Licence", character.licence.confirmed ? "Confirmed by you" : "Not confirmed", character.licence.confirmed ? "ok" : "warn"],
        ["Studio connection", "Not connected (rigging stage pending)", "muted"],
      ]
    : [
        ["Character file", "None imported", "muted"],
        ["Compatibility", "Not checked", "muted"],
        ["Expression clips", "None", "muted"],
        ["Licence", "No record", "muted"],
        ["Studio connection", "Not connected", "muted"],
      ];
  const col = { ok: "text-ok-500", warn: "text-warn-500", muted: "text-ink-400" };
  return (
    <section className="rounded-xl border border-ink-800 bg-ink-900 p-5">
      <h2 className="text-sm font-semibold text-ink-100">Character asset status</h2>
      <dl className="mt-3 space-y-2 text-sm">
        {rows.map(([k, v, c]) => (
          <div key={k} className="flex justify-between gap-3">
            <dt className="text-ink-400">{k}</dt>
            <dd className={`text-right ${col[c]}`}>{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function FormatsCard() {
  return (
    <section className="space-y-3 rounded-xl border border-ink-800 bg-ink-900 p-5 text-sm">
      <h2 className="font-semibold text-ink-100">Supported formats</h2>
      <ul className="space-y-1.5 text-ink-300">
        <li>
          <b className="text-ok-500">.glb</b>: glTF 2.0 binary, everything embedded (recommended)
        </li>
        <li>
          <b className="text-ink-200">.gltf</b>: only with embedded (data URI) buffers and images
        </li>
        <li>
          <b className="text-err-500">.blend</b>: not readable in a browser. Export to .glb first.
        </li>
      </ul>
      <h3 className="pt-2 font-semibold text-ink-100">What the studio needs</h3>
      <ul className="list-disc space-y-1 pl-5 text-ink-300">
        <li>A head mesh named “Head” or “Face”, with UVs</li>
        <li>Named morph targets (shape keys) and/or facial bones</li>
        <li>Separate eye objects (pivot at the eyeball centre) or eye bones</li>
        <li>One animation clip per expression, named with its ID (e.g. gentle_smile)</li>
        <li>PBR materials with embedded textures</li>
      </ul>
      <a href="/docs/BLENDER_TO_GLTF.md" target="_blank" rel="noreferrer" className="inline-block text-accent-400 hover:underline">
        Blender → glTF export guide
      </a>
    </section>
  );
}

function Dropzone({ onFile, busy }: { onFile: (f: File) => void; busy: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-accent-500 bg-accent-900/30" : "border-ink-700 bg-ink-900"}`}
    >
      <svg viewBox="0 0 24 24" className="h-8 w-8 text-ink-400" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
        <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z" strokeLinejoin="round" />
        <path d="M4 7.5 12 12l8-4.5M12 12v9" strokeLinejoin="round" />
      </svg>
      <p className="text-sm text-ink-200">Drag a character file here (.glb recommended)</p>
      <button type="button" disabled={busy} onClick={() => input.current?.click()} className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-ink-950 hover:bg-accent-400 disabled:opacity-50">
        {busy ? "Checking…" : "Choose character file"}
      </button>
      <input
        ref={input}
        type="file"
        accept=".glb,.gltf,.blend,model/gltf-binary,model/gltf+json"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      <p className="text-xs text-ink-500">Up to 150 MB · the file is checked in your browser before anything is stored</p>
    </div>
  );
}

function ImportSection({ replacing = false }: { replacing?: boolean }) {
  const { inspectFile, storeCandidate, character } = useAssets();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [licence, setLicence] = useState<LicenceRecord>(emptyLicence());
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [saved, setSaved] = useState(false);

  const onFile = async (f: File) => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      setCandidate(await inspectFile(f));
      setLicence(emptyLicence());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const unreadable = candidate?.report.checks.some((c) => c.id === "container" && c.status === "fail");
  const store = async () => {
    if (!candidate) return;
    try {
      await storeCandidate(candidate, licence);
      setCandidate(null);
      setConfirmReplace(false);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <section aria-labelledby="import-char" className="space-y-4">
      <div>
        <h2 id="import-char" className="text-lg font-semibold text-ink-100">
          {replacing ? "Replace character" : "Import character"}
        </h2>
        <p className="text-sm text-ink-400">{replacing ? "Choose a new file to check it. The current character stays until you confirm the replacement." : "No character has been imported. Choose a glTF file to check it; nothing is stored until you confirm."}</p>
      </div>
      <Dropzone onFile={onFile} busy={busy} />
      {saved && <p role="status" className="rounded-md bg-ok-500/10 px-3 py-2 text-sm text-ok-500">Character stored.</p>}
      {error && (
        <p role="alert" className="rounded-md border border-err-500/40 bg-err-500/10 px-3 py-2 text-sm text-err-500">
          {error}
        </p>
      )}
      {candidate && (
        <article className="space-y-4 rounded-xl border border-ink-800 bg-ink-900 p-5">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-mono text-sm text-ink-100">{candidate.fileName}</h3>
            <span className="text-xs text-ink-500">
              {fmt(candidate.size)} · SHA-256 {candidate.sha256.slice(0, 16)}…
            </span>
          </header>
          <ReportView report={candidate.report} />
          {!unreadable && <LicenceForm value={licence} onChange={setLicence} />}
          <div className="flex flex-wrap items-center gap-2">
            {unreadable ? (
              <p className="text-sm text-err-500">This file cannot be stored. Export it as glTF 2.0 (.glb) and try again.</p>
            ) : character && !confirmReplace ? (
              <button type="button" onClick={() => setConfirmReplace(true)} className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-ink-950 hover:bg-accent-400">
                Replace current character…
              </button>
            ) : character ? (
              <>
                <span className="text-sm text-warn-500">
                  Replace <b className="font-mono">{character.fileName}</b> with <b className="font-mono">{candidate.fileName}</b>? The current file will be deleted from this browser.
                </span>
                <button type="button" onClick={store} className="rounded-md border border-warn-500/60 px-4 py-2 text-sm font-medium text-warn-500">
                  Confirm replace
                </button>
                <button type="button" onClick={() => setConfirmReplace(false)} className="rounded-md border border-ink-700 px-3 py-2 text-sm text-ink-300">
                  Cancel
                </button>
              </>
            ) : (
              <button type="button" onClick={store} className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-ink-950 hover:bg-accent-400">
                Store as studio character
              </button>
            )}
            <button type="button" onClick={() => setCandidate(null)} className="rounded-md border border-ink-700 px-3 py-2 text-sm text-ink-300">
              Discard
            </button>
          </div>
        </article>
      )}
    </section>
  );
}

function CurrentCharacter() {
  const { character, removeCharacter, updateLicence } = useAssets();
  const [preview, setPreview] = useState<PreviewStatus>({ state: "loading" });
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [licence, setLicence] = useState<LicenceRecord>(character!.licence);
  const [licSaved, setLicSaved] = useState(false);
  const onStatus = useCallback((s: PreviewStatus) => setPreview(s), []);
  if (!character) return null;
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink-100">Current character</h2>
          <p className="font-mono text-sm text-ink-300">{character.fileName}</p>
          <p className="text-xs text-ink-500">
            {fmt(character.size)} · imported {new Date(character.importedAt).toLocaleString()} · SHA-256 {character.sha256.slice(0, 16)}…
          </p>
        </div>
        {confirmRemove ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-err-500">Delete this character from the browser?</span>
            <button type="button" onClick={() => void removeCharacter()} className="rounded-md border border-err-500/60 px-3 py-1.5 text-sm text-err-500">
              Confirm remove
            </button>
            <button type="button" onClick={() => setConfirmRemove(false)} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300">
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirmRemove(true)} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300 hover:border-err-500/60 hover:text-err-500">
            Remove…
          </button>
        )}
      </div>
      <div className="overflow-hidden rounded-xl border border-ink-800">
        <div className="flex items-center justify-between border-b border-ink-800 bg-ink-900 px-4 py-2 text-xs">
          <span className="text-ink-300">Model preview (static, as loaded by three.js; no animation is played)</span>
          <span className={preview.state === "loaded" ? "text-ok-500" : preview.state === "failed" ? "text-err-500" : "text-ink-400"}>
            {preview.state === "loaded" ? `Loaded · ${preview.meshes} mesh(es)` : preview.state === "failed" ? `Failed: ${preview.error}` : "Loading…"}
          </span>
        </div>
        <div className="h-80 bg-ink-950">
          <AssetPreview data={character.data} onStatus={onStatus} />
        </div>
      </div>
      <ReportView report={character.report} />
      <div className="space-y-3 rounded-xl border border-ink-800 bg-ink-900 p-5">
        <LicenceForm value={licence} onChange={(l) => (setLicence(l), setLicSaved(false))} />
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => void updateLicence(licence).then(() => setLicSaved(true))} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-200 hover:border-ink-500">
            Save licence record
          </button>
          {licSaved && <span className="text-xs text-ok-500">Saved</span>}
        </div>
      </div>
    </section>
  );
}

function LicenceForm({ value, onChange }: { value: LicenceRecord; onChange: (l: LicenceRecord) => void }) {
  const f = (k: keyof Omit<LicenceRecord, "confirmed">, label: string, placeholder: string) => (
    <label className="block text-xs text-ink-400">
      {label}
      <input value={value[k]} onChange={(e) => onChange({ ...value, [k]: e.target.value })} placeholder={placeholder} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600" />
    </label>
  );
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-semibold text-ink-100">Licence and source</legend>
      <div className="grid gap-3 md:grid-cols-2">
        {f("source", "Source", "Where the model came from")}
        {f("author", "Author / rights holder", "Name or studio")}
        {f("licence", "Licence", "e.g. CC BY 4.0, written permission")}
        {f("url", "Licence or source URL", "https://…")}
      </div>
      <label className="block text-xs text-ink-400">
        Notes
        <textarea value={value.notes} onChange={(e) => onChange({ ...value, notes: e.target.value })} rows={2} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-3 py-2 text-sm text-ink-100" />
      </label>
      <label className="flex items-start gap-2 text-sm text-ink-300">
        <input type="checkbox" checked={value.confirmed} onChange={(e) => onChange({ ...value, confirmed: e.target.checked })} className="mt-1" />
        I confirm I hold written permission to use this model (and its textures) in this studio. Without this, the character is treated as private and unconfirmed.
      </label>
    </fieldset>
  );
}

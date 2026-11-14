"use client";

import { useState } from "react";
import { exportCsv, exportJson, exportMarkdown, templateJson } from "@/lib/content/export";
import { exportBackup } from "@/lib/storage/backup";
import { LOCALE_PATTERN } from "@/lib/content/validate";
import { useContent } from "@/lib/state/content-context";
import { download } from "./download";
import { ImportPanel } from "./ImportPanel";
import { LibraryEditor } from "./LibraryEditor";

export function ContentManager() {
  const { store, locale, setLocale, locales, storage, migration, imports, hydrated } = useContent();
  const [newLocale, setNewLocale] = useState("");
  const count = (l: string) => Object.keys(store[l] ?? {}).length;
  const total = Object.values(store).reduce((n, m) => n + Object.keys(m).length, 0);

  const addLocale = () => {
    const l = newLocale.trim();
    if (!LOCALE_PATTERN.test(l)) return;
    setLocale(l);
    setNewLocale("");
  };

  return (
    <div className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-8 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Content Manager</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-300">
            Add titles, descriptions, tags and notes for the 60 expressions from JSON, CSV, Markdown or TXT files, in any language. Text is matched to expressions by ID and never touches the animation engine.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ActionButton onClick={() => download("expression-content.template.json", templateJson(locale), "application/json")} label="Download JSON template" />
          <a href="/templates/CONTENT_FORMAT.md" target="_blank" rel="noreferrer" className="rounded-md border border-ink-700 px-3 py-2 text-sm text-ink-200 hover:border-ink-500 hover:text-ink-100">
            Format guide
          </a>
        </div>
      </header>

      <StorageBanner kind={storage.kind} error={storage.error} />
      {migration && (migration.status === "migrated" || migration.status === "failed") && (
        <div role="status" className={`rounded-md border px-4 py-3 text-sm ${migration.status === "failed" ? "border-err-500/40 bg-err-500/10 text-err-500" : "border-info-500/40 bg-info-500/10 text-info-500"}`}>
          {migration.status === "failed" ? (
            migration.error
          ) : (
            <>
              Moved earlier browser content into IndexedDB: {migration.migrated} added, {migration.identical} already identical
              {migration.rejected ? `, ${migration.rejected} skipped (unknown ID or language)` : ""}
              {migration.sanitized ? `, ${migration.sanitized} cleaned of markup` : ""}.
              {migration.conflicts.length > 0 && (
                <details className="mt-1">
                  <summary className="cursor-pointer">
                    {migration.conflicts.length} older entr{migration.conflicts.length === 1 ? "y differs" : "ies differ"} from what IndexedDB already holds; the IndexedDB text was kept.
                  </summary>
                  <ul className="mt-1 space-y-1 text-xs">
                    {migration.conflicts.map((c) => (
                      <li key={`${c.locale}-${c.id}`}>
                        <span className="font-mono">
                          {c.locale}/{c.id}
                        </span>{" "}
                        old text: “{c.legacy.description || c.legacy.title || "(empty)"}”
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
      )}

      <section aria-labelledby="stats" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <h2 id="stats" className="sr-only">
          Summary
        </h2>
        <Stat label="Expressions" value="60" />
        <Stat label="Languages with content" value={hydrated ? String(Object.keys(store).length) : "…"} />
        <Stat label="Entries stored" value={hydrated ? String(total) : "…"} />
        <Stat label={`Covered in ${locale}`} value={hydrated ? `${count(locale)} / 60` : "…"} />
      </section>

      <ImportPanel />

      <section aria-labelledby="library" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="library" className="text-lg font-semibold text-ink-100">
              Expression text
            </h2>
            <p className="text-sm text-ink-400">Edit any entry. Changes save in this browser immediately.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 rounded-md border border-ink-700 p-1" role="group" aria-label="Language">
              {locales.map((l) => (
                <button key={l} type="button" onClick={() => setLocale(l)} aria-pressed={l === locale} className={`rounded px-2 py-1 font-mono text-xs ${l === locale ? "bg-ink-700 text-ink-100" : "text-ink-300 hover:text-ink-100"}`}>
                  {l} <span className="opacity-60">{count(l)}</span>
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                addLocale();
              }}
              className="flex items-center gap-1"
            >
              <input value={newLocale} onChange={(e) => setNewLocale(e.target.value)} placeholder="Add language, e.g. fr" aria-label="New language code" className="w-40 rounded-md border border-ink-700 bg-ink-850 px-2 py-1.5 font-mono text-xs text-ink-100 placeholder:text-ink-500" />
              <button type="submit" disabled={!LOCALE_PATTERN.test(newLocale.trim())} className="rounded-md border border-ink-700 px-2 py-1.5 text-xs text-ink-200 disabled:opacity-40">
                Add
              </button>
            </form>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <ActionButton disabled={!count(locale)} onClick={() => download(`expression-content.${locale}.json`, exportJson(store, locale), "application/json")} label={`Export ${locale} as JSON`} />
          <ActionButton disabled={!count(locale)} onClick={() => download(`expression-content.${locale}.md`, exportMarkdown(store, locale), "text/markdown")} label={`Export ${locale} as Markdown`} />
          <ActionButton disabled={!total} onClick={() => download("expression-content.all-languages.csv", exportCsv(store), "text/csv")} label="Export all languages as CSV" />
          <ActionButton
            disabled={!total}
            onClick={() => download(`expression-studio-backup.${new Date().toISOString().slice(0, 10)}.json`, exportBackup(store, imports), "application/json")}
            label="Download full backup"
          />
        </div>
        <p className="text-xs text-ink-500">To restore a backup, import it above like any other file: it is reviewed first and conflicts are only overwritten where you tick them.</p>
        <LibraryEditor />
      </section>

      <section aria-labelledby="history" className="space-y-3">
        <h2 id="history" className="text-lg font-semibold text-ink-100">
          Import history
        </h2>
        {imports.length === 0 ? (
          <p className="text-sm text-ink-400">No files imported yet.</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-ink-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-ink-850 text-ink-400">
                <tr>
                  <th className="px-3 py-2 font-medium">When</th>
                  <th className="px-3 py-2 font-medium">File</th>
                  <th className="px-3 py-2 font-medium">Format</th>
                  <th className="px-3 py-2 font-medium">Languages</th>
                  <th className="px-3 py-2 font-medium">Applied</th>
                  <th className="px-3 py-2 font-medium">Overwritten</th>
                  <th className="px-3 py-2 font-medium">Skipped</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800 bg-ink-900 text-ink-300">
                {imports.map((r) => (
                  <tr key={r.importId}>
                    <td className="px-3 py-2">{new Date(r.importedAt).toLocaleString()}</td>
                    <td className="px-3 py-2 font-mono text-ink-200">
                      {r.fileName}
                      {r.sanitized && <span className="ml-2 text-warn-500">markup removed</span>}
                    </td>
                    <td className="px-3 py-2">{r.format}</td>
                    <td className="px-3 py-2 font-mono">{r.locales.join(", ")}</td>
                    <td className="px-3 py-2">{r.applied}</td>
                    <td className="px-3 py-2">{r.overwritten}</td>
                    <td className="px-3 py-2">{r.skipped}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StorageBanner({ kind, error }: { kind: "indexeddb" | "memory" | "loading"; error?: string }) {
  if (kind === "loading") return <p className="text-xs text-ink-500">Opening browser storage…</p>;
  if (error)
    return (
      <p role="alert" className="rounded-md border border-err-500/40 bg-err-500/10 px-4 py-3 text-sm text-err-500">
        {error}
      </p>
    );
  return <p className="text-xs text-ink-500">Saved in this browser&apos;s IndexedDB. Use “Download full backup” to keep a copy or move it to another browser.</p>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900 px-4 py-3">
      <p className="text-xs text-ink-400">{label}</p>
      <p className="mt-1 font-mono text-xl text-ink-100">{value}</p>
    </div>
  );
}

export function ActionButton({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="rounded-md border border-ink-700 px-3 py-2 text-sm text-ink-200 hover:border-ink-500 hover:text-ink-100 disabled:cursor-not-allowed disabled:opacity-40">
      {label}
    </button>
  );
}

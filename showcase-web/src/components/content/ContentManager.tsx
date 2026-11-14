"use client";

import { useState } from "react";
import { exportCsv, exportJson, exportMarkdown, templateJson } from "@/lib/content/export";
import { LOCALE_PATTERN } from "@/lib/content/validate";
import { useContent } from "@/lib/state/content-context";
import { download } from "./download";
import { ImportPanel } from "./ImportPanel";
import { LibraryEditor } from "./LibraryEditor";

export function ContentManager() {
  const { store, locale, setLocale, locales, persistError, hydrated } = useContent();
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

      {persistError && (
        <p role="alert" className="rounded-md border border-err-500/40 bg-err-500/10 px-4 py-3 text-sm text-err-500">
          This browser is blocking local storage, so changes will be lost when the page reloads. Export your content to keep it.
        </p>
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
        </div>
        <LibraryEditor />
      </section>
    </div>
  );
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

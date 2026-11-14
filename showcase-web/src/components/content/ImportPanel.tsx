"use client";

import { useMemo, useRef, useState } from "react";
import { detectFormat, parseContent } from "@/lib/content/parse";
import { applyEntries, entryKey } from "@/lib/content/store";
import type { ParsedContent } from "@/lib/content/types";
import { displayNameOf, validate, type CheckedEntry, type EntryStatus } from "@/lib/content/validate";
import { useContent } from "@/lib/state/content-context";

const MAX_BYTES = 2 * 1024 * 1024;
const ACCEPT = ".json,.csv,.md,.markdown,.txt";

interface Pending {
  key: string;
  parsed: ParsedContent;
  text: string;
  size: number;
}

export function ImportPanel() {
  const [files, setFiles] = useState<Pending[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const accept = async (list: FileList | File[]) => {
    const bad: string[] = [];
    const ok: Pending[] = [];
    for (const f of Array.from(list)) {
      if (!detectFormat(f.name)) bad.push(`${f.name}: unsupported type (use .json, .csv, .md or .txt)`);
      else if (f.size > MAX_BYTES) bad.push(`${f.name}: larger than 2 MB`);
      else {
        const text = await f.text();
        ok.push({ key: `${f.name}-${f.lastModified}-${Math.random().toString(36).slice(2, 7)}`, parsed: parseContent(f.name, text), text, size: f.size });
      }
    }
    setRejected(bad);
    setFiles((cur) => [...ok, ...cur]);
  };

  return (
    <section aria-labelledby="import" className="space-y-4">
      <div>
        <h2 id="import" className="text-lg font-semibold text-ink-100">
          Import content files
        </h2>
        <p className="text-sm text-ink-400">Files are read in your browser and reviewed here first. Nothing is saved until you apply it.</p>
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void accept(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-accent-500 bg-accent-900/30" : "border-ink-700 bg-ink-900"}`}
      >
        <svg viewBox="0 0 24 24" className="h-8 w-8 text-ink-400" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
          <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="text-sm text-ink-200">Drag and drop JSON, CSV, Markdown or TXT files here</p>
        <button type="button" onClick={() => input.current?.click()} className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-ink-950 hover:bg-accent-400">
          Browse files
        </button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          onChange={(e) => {
            if (e.target.files) void accept(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="text-xs text-ink-500">Up to 2 MB per file · UTF-8</p>
      </div>
      {rejected.length > 0 && (
        <ul role="alert" className="space-y-1 rounded-md border border-err-500/40 bg-err-500/10 px-4 py-3 text-sm text-err-500">
          {rejected.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {files.map((f) => (
        <FileReview key={f.key} file={f} onClose={() => setFiles((cur) => cur.filter((x) => x.key !== f.key))} />
      ))}
    </section>
  );
}

const STATUS_STYLE: Record<EntryStatus, string> = {
  new: "bg-ok-500/15 text-ok-500",
  unchanged: "bg-ink-700 text-ink-300",
  conflict: "bg-warn-500/15 text-warn-500",
  invalid: "bg-err-500/15 text-err-500",
  duplicate: "bg-err-500/15 text-err-500",
};
const STATUS_LABEL: Record<EntryStatus, string> = { new: "New / fills empty", unchanged: "Unchanged", conflict: "Conflict", invalid: "Invalid ID", duplicate: "Duplicate" };

function FileReview({ file, onClose }: { file: Pending; onClose: () => void }) {
  const { store, setStore } = useContent();
  const report = useMemo(() => validate(file.parsed, store), [file.parsed, store]);
  const [overwrite, setOverwrite] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<"entries" | "preview">("entries");
  const [result, setResult] = useState<string | null>(null);
  const conflicts = report.entries.filter((e) => e.status === "conflict");

  const apply = () => {
    const { store: next, applied, skipped } = applyEntries(store, report.entries, { overwrite, origin: file.parsed.fileName });
    setStore(next);
    setOverwrite(new Set());
    setResult(`Applied ${applied} entr${applied === 1 ? "y" : "ies"}; ${skipped} left unchanged or skipped.`);
  };

  const toggle = (e: CheckedEntry) =>
    setOverwrite((s) => {
      const n = new Set(s);
      const k = entryKey(e.locale, e.id);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  const errors = report.issues.filter((i) => i.level === "error");
  return (
    <article className="overflow-hidden rounded-xl border border-ink-800 bg-ink-900">
      <header className="flex flex-wrap items-center gap-3 border-b border-ink-800 px-4 py-3">
        <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-ink-300">{file.parsed.format}</span>
        <h3 className="min-w-0 truncate font-mono text-sm text-ink-100">{file.parsed.fileName}</h3>
        <span className="text-xs text-ink-500">{(file.size / 1024).toFixed(1)} KB</span>
        <span className="text-xs text-ink-400">Languages: {report.locales.join(", ") || "none"}</span>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={apply} disabled={!report.canApply} className="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-ink-950 hover:bg-accent-400 disabled:cursor-not-allowed disabled:opacity-40">
            Apply{overwrite.size ? ` (overwrite ${overwrite.size})` : ""}
          </button>
          <button type="button" onClick={onClose} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300 hover:text-ink-100">
            Dismiss
          </button>
        </div>
      </header>
      <div className="space-y-3 px-4 py-3">
        <div className="flex flex-wrap gap-2 text-xs">
          {(Object.keys(STATUS_LABEL) as EntryStatus[]).map((s) => (
            <span key={s} className={`rounded px-2 py-1 ${STATUS_STYLE[s]}`}>
              {STATUS_LABEL[s]}: <b className="font-mono">{report.counts[s]}</b>
            </span>
          ))}
        </div>
        {result && (
          <p role="status" className="rounded-md bg-ok-500/10 px-3 py-2 text-sm text-ok-500">
            {result}
          </p>
        )}
        {errors.length > 0 && (
          <ul className="space-y-1 rounded-md border border-err-500/40 bg-err-500/10 px-3 py-2 text-sm text-err-500">
            {errors.map((i, n) => (
              <li key={n}>
                {i.source ? <span className="font-mono">line {i.source}: </span> : null}
                {i.message}
              </li>
            ))}
          </ul>
        )}
        {report.issues.some((i) => i.level !== "error") && (
          <ul className="space-y-1 text-xs text-warn-500">
            {report.issues
              .filter((i) => i.level !== "error")
              .map((i, n) => (
                <li key={n}>
                  {i.source ? <span className="font-mono">line {i.source}: </span> : null}
                  {i.message}
                </li>
              ))}
          </ul>
        )}
        {conflicts.length > 0 && (
          <p className="text-xs text-ink-300">
            {conflicts.length} entr{conflicts.length === 1 ? "y differs" : "ies differ"} from text you already have. By default only empty fields are filled; tick <b>Overwrite</b> on an entry to replace its existing text.
          </p>
        )}
        {Object.entries(report.missingByLocale).map(([l, ids]) =>
          ids.length ? (
            <details key={l} className="text-xs text-ink-400">
              <summary className="cursor-pointer">
                {ids.length} of 60 expressions not covered for <span className="font-mono">{l}</span>
              </summary>
              <p className="mt-1 font-mono leading-relaxed text-ink-500">{ids.join(", ")}</p>
            </details>
          ) : null,
        )}
        <div className="flex gap-1 border-b border-ink-800" role="tablist">
          {(["entries", "preview"] as const).map((t) => (
            <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)} className={`-mb-px border-b-2 px-3 py-1.5 text-xs ${tab === t ? "border-accent-500 text-ink-100" : "border-transparent text-ink-400 hover:text-ink-200"}`}>
              {t === "entries" ? `Entries (${report.entries.length})` : "File preview"}
            </button>
          ))}
        </div>
        {tab === "preview" ? (
          <pre className="max-h-80 overflow-auto rounded-md bg-ink-950 p-3 font-mono text-xs leading-relaxed text-ink-300">{file.text.length > 40000 ? `${file.text.slice(0, 40000)}\n… (truncated in preview)` : file.text}</pre>
        ) : (
          <div className="max-h-96 overflow-auto rounded-md border border-ink-800">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-ink-850 text-ink-400">
                <tr>
                  <th className="px-3 py-2 font-medium">Line</th>
                  <th className="px-3 py-2 font-medium">ID</th>
                  <th className="px-3 py-2 font-medium">Lang</th>
                  <th className="px-3 py-2 font-medium">Title / description</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Overwrite</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800">
                {report.entries.map((e, n) => (
                  <tr key={n} className="align-top">
                    <td className="px-3 py-2 font-mono text-ink-500">{e.source ?? "–"}</td>
                    <td className="px-3 py-2">
                      <span className="font-mono text-ink-100">{e.id}</span>
                      {e.status !== "invalid" && <span className="block text-ink-500">{displayNameOf(e.id)}</span>}
                      {e.suggestion && <span className="block text-warn-500">Did you mean {e.suggestion}?</span>}
                    </td>
                    <td className="px-3 py-2 font-mono text-ink-300">{e.locale}</td>
                    <td className="max-w-md px-3 py-2 text-ink-300">
                      {e.title && <span className="block font-medium text-ink-200">{e.title}</span>}
                      <span className="line-clamp-2">{e.description ?? <i className="text-ink-500">no description</i>}</span>
                      {e.problem && <span className="block text-err-500">{e.problem}</span>}
                      {e.conflicts.length > 0 && <span className="block text-warn-500">Differs in: {e.conflicts.join(", ")}</span>}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`whitespace-nowrap rounded px-1.5 py-0.5 ${STATUS_STYLE[e.status]}`}>{STATUS_LABEL[e.status]}</span>
                    </td>
                    <td className="px-3 py-2">
                      {e.status === "conflict" ? (
                        <input type="checkbox" checked={overwrite.has(entryKey(e.locale, e.id))} onChange={() => toggle(e)} aria-label={`Overwrite existing text for ${e.id} (${e.locale})`} />
                      ) : (
                        <span className="text-ink-600">–</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </article>
  );
}

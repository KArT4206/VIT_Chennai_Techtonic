"use client";

import { useState } from "react";
import { CATEGORIES, EXPRESSIONS, type Expression } from "@/data/expressions";
import { useContent } from "@/lib/state/content-context";

export function LibraryEditor() {
  const { store, locale } = useContent();
  const [editing, setEditing] = useState<string | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const m = store[locale] ?? {};

  return (
    <div className="overflow-hidden rounded-xl border border-ink-800">
      <div className="flex items-center justify-between border-b border-ink-800 bg-ink-900 px-4 py-2 text-xs text-ink-400">
        <span>
          Language <span className="font-mono text-ink-200">{locale}</span>
        </span>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} />
          Show only expressions without a description
        </label>
      </div>
      {CATEGORIES.map((c) => {
        const rows = EXPRESSIONS.filter((e) => e.categoryId === c.id && (!onlyMissing || !m[e.id]?.description));
        if (!rows.length) return null;
        return (
          <div key={c.id}>
            <h3 className="bg-ink-850 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{c.name}</h3>
            <ul className="divide-y divide-ink-800">
              {rows.map((e) =>
                editing === e.id ? (
                  <EditRow key={e.id} e={e} onDone={() => setEditing(null)} />
                ) : (
                  <li key={e.id} className="grid grid-cols-[3rem_14rem_1fr_auto] items-start gap-4 bg-ink-900 px-4 py-3 text-sm">
                    <span className="font-mono text-xs text-ink-500">{String(e.number).padStart(2, "0")}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-ink-100">{m[e.id]?.title || e.displayName}</span>
                      <span className="block truncate font-mono text-[11px] text-ink-500">{e.id}</span>
                    </span>
                    <span className="min-w-0 text-ink-300">
                      {m[e.id]?.description ? <span className="line-clamp-2">{m[e.id].description}</span> : <span className="text-ink-500">No description</span>}
                      {m[e.id] && <span className="mt-0.5 block text-[11px] text-ink-500">From {m[e.id].origin} · {new Date(m[e.id].updatedAt).toLocaleString()}</span>}
                    </span>
                    <button type="button" onClick={() => setEditing(e.id)} className="rounded-md border border-ink-700 px-2.5 py-1 text-xs text-ink-200 hover:border-ink-500">
                      Edit
                    </button>
                  </li>
                ),
              )}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function EditRow({ e, onDone }: { e: Expression; onDone: () => void }) {
  const { store, saveEntry, deleteEntry, locale } = useContent();
  const cur = store[locale]?.[e.id];
  const [title, setTitle] = useState(cur?.title ?? "");
  const [description, setDescription] = useState(cur?.description ?? "");
  const [tags, setTags] = useState((cur?.tags ?? []).join(", "));
  const [notes, setNotes] = useState(cur?.notes ?? "");
  const [confirmClear, setConfirmClear] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    try {
      await fn();
      onDone();
    } catch (err) {
      setError(`Not saved: ${(err as Error).message}`);
    }
  };
  const save = () => run(() => saveEntry(locale, e.id, { title: title.trim(), description: description.trim(), notes: notes.trim(), tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }));

  return (
    <li className="space-y-3 bg-ink-850 px-4 py-4">
      <div className="flex items-baseline justify-between">
        <p className="text-sm text-ink-100">
          {e.displayName} <span className="font-mono text-xs text-ink-500">{e.id} · {locale}</span>
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Title" value={title} onChange={setTitle} placeholder={e.displayName} />
        <Field label="Tags (comma separated)" value={tags} onChange={setTags} placeholder={e.tags.join(", ")} />
      </div>
      <label className="block text-xs text-ink-400">
        Description
        <textarea value={description} onChange={(ev) => setDescription(ev.target.value)} rows={3} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100" />
      </label>
      <Field label="Notes" value={notes} onChange={setNotes} />
      <p className="text-[11px] text-ink-500">Plain text only. Any HTML or script markup is removed when saved.</p>
      {error && (
        <p role="alert" className="text-sm text-err-500">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={save} className="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-ink-950 hover:bg-accent-400">
          Save
        </button>
        <button type="button" onClick={onDone} className="rounded-md border border-ink-700 px-3 py-1.5 text-sm text-ink-300">
          Cancel
        </button>
        {cur &&
          (confirmClear ? (
            <button
              type="button"
              onClick={() => run(() => deleteEntry(locale, e.id))}
              className="ml-auto rounded-md border border-err-500/60 px-3 py-1.5 text-sm text-err-500"
            >
              Confirm: clear {locale} text
            </button>
          ) : (
            <button type="button" onClick={() => setConfirmClear(true)} className="ml-auto rounded-md px-3 py-1.5 text-sm text-ink-400 hover:text-err-500">
              Clear text…
            </button>
          ))}
      </div>
    </li>
  );
}

function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="block text-xs text-ink-400">
      {label}
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="mt-1 w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600" />
    </label>
  );
}

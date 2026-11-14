"use client";

import { useMemo, useState } from "react";
import { CATEGORIES, EXPRESSIONS, type CategoryId, type Expression } from "@/data/expressions";
import { useContent } from "@/lib/state/content-context";
import { useStudio } from "@/lib/state/studio-context";

type Filter = "all" | "favourites" | "recent" | CategoryId;

export function ExpressionLibrary() {
  const { selectedId, select, favourites, toggleFavourite, recent, adapter } = useStudio();
  const { entry } = useContent();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const titleOf = (e: Expression) => entry(e.id)?.title || e.displayName;

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    let items: Expression[] =
      filter === "all"
        ? [...EXPRESSIONS]
        : filter === "favourites"
          ? EXPRESSIONS.filter((e) => favourites.includes(e.id))
          : filter === "recent"
            ? (recent.map((id) => EXPRESSIONS.find((e) => e.id === id)).filter(Boolean) as Expression[])
            : EXPRESSIONS.filter((e) => e.categoryId === filter);
    if (q)
      items = items.filter((e) => {
        const c = entry(e.id);
        return [e.displayName, e.id, c?.title ?? "", ...e.tags, ...(c?.tags ?? [])].some((s) => s.toLowerCase().includes(q));
      });
    return items;
  }, [query, filter, favourites, recent, entry]);

  const chips: Array<{ id: Filter; label: string; count: number }> = [
    { id: "all", label: "All", count: EXPRESSIONS.length },
    { id: "favourites", label: "★ Favourites", count: favourites.length },
    { id: "recent", label: "Recent", count: recent.length },
    ...CATEGORIES.map((c) => ({ id: c.id as Filter, label: c.name, count: EXPRESSIONS.filter((e) => e.categoryId === c.id).length })),
  ];

  const grouped = filter === "all" && !query.trim();

  return (
    <>
      <div className="space-y-3 border-b border-ink-800 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-ink-100">Expression library</h2>
          <span className="font-mono text-xs text-ink-400">{list.length} / 60</span>
        </div>
        <label className="relative block">
          <span className="sr-only">Search expressions</span>
          <svg aria-hidden viewBox="0 0 20 20" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="9" cy="9" r="5.5" />
            <path d="m13.5 13.5 3 3" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, ID or tag"
            className="w-full rounded-md border border-ink-700 bg-ink-850 py-2 pl-8 pr-3 text-sm text-ink-100 placeholder:text-ink-400 focus:border-accent-500 focus:outline-none"
          />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
          {chips.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setFilter(c.id)}
              aria-pressed={filter === c.id}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${filter === c.id ? "border-accent-500 bg-accent-900 text-accent-300" : "border-ink-700 text-ink-300 hover:border-ink-500 hover:text-ink-100"}`}
            >
              {c.label} <span className="font-mono text-[10px] opacity-70">{c.count}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {list.length === 0 && <p className="px-3 py-8 text-center text-sm text-ink-400">{filter === "favourites" ? "No favourites yet. Star an expression to keep it here." : filter === "recent" ? "Nothing selected yet." : "No expressions match your search."}</p>}
        {grouped
          ? CATEGORIES.map((c) => (
              <div key={c.id} className="mb-2">
                <h3 className="sticky top-0 z-10 bg-ink-900/95 px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400 backdrop-blur">{c.name}</h3>
                <ul className="space-y-0.5">
                  {list
                    .filter((e) => e.categoryId === c.id)
                    .map((e) => (
                      <Card key={e.id} e={e} title={titleOf(e)} selected={e.id === selectedId} fav={favourites.includes(e.id)} hasClip={adapter.hasClip(e.id)} onSelect={select} onFav={toggleFavourite} />
                    ))}
                </ul>
              </div>
            ))
          : (
              <ul className="space-y-0.5">
                {list.map((e) => (
                  <Card key={e.id} e={e} title={titleOf(e)} selected={e.id === selectedId} fav={favourites.includes(e.id)} hasClip={adapter.hasClip(e.id)} onSelect={select} onFav={toggleFavourite} />
                ))}
              </ul>
            )}
      </div>
    </>
  );
}

function Card({ e, title, selected, fav, hasClip, onSelect, onFav }: { e: Expression; title: string; selected: boolean; fav: boolean; hasClip: boolean; onSelect: (id: string) => void; onFav: (id: string) => void }) {
  return (
    <li className="group relative">
      <button
        type="button"
        onClick={() => onSelect(e.id)}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full items-center gap-3 rounded-md border px-2.5 py-2 text-left transition-colors ${selected ? "border-accent-500/70 bg-accent-900/60" : "border-transparent hover:bg-ink-850"}`}
      >
        <span className={`w-6 shrink-0 text-right font-mono text-[11px] ${selected ? "text-accent-300" : "text-ink-500"}`}>{String(e.number).padStart(2, "0")}</span>
        <span className="min-w-0 flex-1">
          <span className={`block truncate text-sm ${selected ? "font-medium text-ink-100" : "text-ink-200"}`}>{title}</span>
          <span className="block truncate font-mono text-[10px] text-ink-500">{e.id}</span>
        </span>
        <span
          title={hasClip ? "Animation clip available" : "No animation clip yet (character asset pending)"}
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${hasClip ? "bg-ok-500" : "bg-ink-600"}`}
        />
        <span className="w-6 shrink-0" />
      </button>
      <button
        type="button"
        onClick={() => onFav(e.id)}
        aria-label={fav ? `Remove ${title} from favourites` : `Add ${title} to favourites`}
        aria-pressed={fav}
        className={`absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-sm transition-opacity ${fav ? "text-accent-400 opacity-100" : "text-ink-500 opacity-0 hover:text-ink-200 focus:opacity-100 group-hover:opacity-100"}`}
      >
        {fav ? "★" : "☆"}
      </button>
    </li>
  );
}

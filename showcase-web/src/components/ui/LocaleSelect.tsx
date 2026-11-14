"use client";

import { useContent } from "@/lib/state/content-context";

export function LocaleSelect() {
  const { locale, setLocale, locales } = useContent();
  return (
    <label className="flex items-center gap-2 text-xs text-ink-400">
      <span>Content language</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value)}
        className="rounded-md border border-ink-700 bg-ink-850 px-2 py-1 font-mono text-xs text-ink-100"
      >
        {locales.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

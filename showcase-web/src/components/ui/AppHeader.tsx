"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LocaleSelect } from "./LocaleSelect";

const NAV = [
  { href: "/", label: "Studio" },
  { href: "/content", label: "Content Manager" },
  { href: "/assets", label: "Character & Assets" },
  { href: "/settings", label: "Settings & Export" },
];

export function AppHeader() {
  const path = usePathname();
  return (
    <header className="flex min-h-14 shrink-0 flex-wrap items-center gap-x-6 gap-y-2 border-b border-ink-800 bg-ink-900/80 px-4 py-2 backdrop-blur md:px-6">
      <Link href="/" className="flex items-center gap-2.5">
        <span aria-hidden className="grid h-7 w-7 place-items-center rounded-md bg-accent-900 text-accent-400">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="12" cy="12" r="8.5" />
            <path d="M9 10h.01M15 10h.01M8.5 14.5c1 1.3 2.2 2 3.5 2s2.5-.7 3.5-2" strokeLinecap="round" />
          </svg>
        </span>
        <span className="text-sm font-semibold tracking-tight text-ink-100">Facial Expression Studio</span>
      </Link>
      <nav className="flex flex-wrap items-center gap-1" aria-label="Main">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${active ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-850 hover:text-ink-100"}`}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="ml-auto flex items-center gap-3">
        <LocaleSelect />
      </div>
    </header>
  );
}

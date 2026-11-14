import { EXPRESSIONS } from "@/data/expressions";
import type { ContentStore } from "@/lib/content/types";
import type { ImportRecord } from "./repository";

export const BACKUP_FORMAT = "facial-expression-studio-backup";
export const BACKUP_VERSION = 1;

export interface BackupFile {
  format: typeof BACKUP_FORMAT;
  version: number;
  exportedAt: string;
  /** Every stored entry, all languages. */
  entries: Array<{ locale: string; id: string; title: string; description: string; tags: string[]; notes: string; updatedAt: string; origin: string }>;
  /** Import history (metadata only; file text is not included). */
  imports: Array<Omit<ImportRecord, "text">>;
}

/**
 * Full backup of all languages plus import history metadata. Restoring goes through the normal
 * Content Manager review (parseContent recognises this format), so restore never overwrites
 * silently either.
 */
export function exportBackup(store: ContentStore, imports: ImportRecord[], now = new Date().toISOString()): string {
  const order = new Map(EXPRESSIONS.map((e, i) => [e.id, i]));
  const entries = Object.entries(store)
    .flatMap(([locale, m]) => Object.entries(m).map(([id, e]) => ({ locale, id, ...e })))
    .sort((a, b) => a.locale.localeCompare(b.locale) || (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));
  const file: BackupFile = {
    format: BACKUP_FORMAT,
    version: BACKUP_VERSION,
    exportedAt: now,
    entries,
    imports: imports.map(({ text, ...rest }) => {
      void text;
      return rest;
    }),
  };
  return JSON.stringify(file, null, 2) + "\n";
}

export const isBackup = (data: unknown): data is BackupFile => !!data && typeof data === "object" && (data as { format?: unknown }).format === BACKUP_FORMAT;

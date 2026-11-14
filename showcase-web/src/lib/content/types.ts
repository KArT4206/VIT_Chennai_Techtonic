/** Text content attached to expression IDs. Independent of the animation engine. */

export const SCHEMA_VERSION = 1;

export type ContentFormat = "json" | "csv" | "markdown" | "txt";

/** One expression's text in one locale, as read from a file. */
export interface ContentEntry {
  id: string;
  locale: string;
  title?: string;
  description?: string;
  tags?: string[];
  notes?: string;
  /** 1-based line (or JSON array index + 1) the entry came from, for error messages. */
  source?: number;
}

export type IssueLevel = "error" | "warning" | "info";

export interface ParseIssue {
  level: IssueLevel;
  message: string;
  source?: number;
}

export interface ParsedContent {
  format: ContentFormat;
  fileName: string;
  entries: ContentEntry[];
  issues: ParseIssue[];
}

/** Stored text for one expression in one locale. */
export interface StoredEntry {
  title: string;
  description: string;
  tags: string[];
  notes: string;
  updatedAt: string;
  /** File name or "manual edit". */
  origin: string;
}

/** locale -> expression id -> entry */
export type ContentStore = Record<string, Record<string, StoredEntry>>;

/** The documented JSON file shape. */
export interface ContentFileJson {
  schema_version: number;
  locale: string;
  expressions: Array<{ id: string; title?: string; description?: string; tags?: string[]; notes?: string; locale?: string }>;
}

/**
 * Content is plain text only. Before anything is stored, HTML/script markup is removed so no
 * executable HTML or script ever reaches IndexedDB (the UI also renders text as text, never as HTML).
 */

const BLOCK = /<\s*(script|style|iframe|object|embed|template|noscript)\b[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi;
const UNCLOSED_BLOCK = /<\s*(script|style|iframe|object|embed|template|noscript)\b[\s\S]*$/gi;
const TAG = /<\/?[a-zA-Z!][^<>]*>/g;
const URL_SCHEME = /\b(?:javascript|vbscript|data)\s*:/gi;
// C0 controls except tab (\t), newline (\n) and carriage return (\r).
// eslint-disable-next-line no-control-regex
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

export interface SanitizeResult {
  text: string;
  changed: boolean;
}

export function sanitizeText(input: string): SanitizeResult {
  const text = input.replace(BLOCK, "").replace(UNCLOSED_BLOCK, "").replace(TAG, "").replace(URL_SCHEME, "").replace(CONTROL, "");
  return { text, changed: text !== input };
}

export const clean = (s: string) => sanitizeText(s).text;

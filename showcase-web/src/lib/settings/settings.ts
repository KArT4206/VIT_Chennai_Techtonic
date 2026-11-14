import { CATEGORIES, EXPRESSIONS } from "@/data/expressions";
import { CAMERA_PRESETS, type CameraPresetId } from "@/lib/character/cameras";
import { LOCALE_PATTERN } from "@/lib/content/validate";

export type Quality = "low" | "medium" | "high";

export interface Settings {
  defaultCamera: CameraPresetId;
  playbackSpeed: number;
  defaultIntensity: number;
  quality: Quality;
  contentLocale: string;
}

export const DEFAULT_SETTINGS: Settings = { defaultCamera: "front", playbackSpeed: 1, defaultIntensity: 1, quality: "high", contentLocale: "en" };

export const QUALITY_INFO: Record<Quality, { label: string; dpr: [number, number]; antialias: boolean; note: string }> = {
  low: { label: "Low", dpr: [1, 1], antialias: false, note: "1× pixel ratio, no antialiasing. For slow or battery-powered devices." },
  medium: { label: "Medium", dpr: [1, 1.5], antialias: true, note: "Up to 1.5× pixel ratio with antialiasing." },
  high: { label: "High", dpr: [1, 2], antialias: true, note: "Up to 2× pixel ratio with antialiasing (sharpest on retina displays)." },
};

export const SETTINGS_KEY = "fes.settings.v1";
export const CONFIG_FORMAT = "facial-expression-studio-config";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Returns valid settings from untrusted input plus a list of fields that were rejected. */
export function coerceSettings(raw: unknown): { settings: Settings; rejected: string[] } {
  const s = { ...DEFAULT_SETTINGS };
  const rejected: string[] = [];
  if (!raw || typeof raw !== "object") return { settings: s, rejected: raw === undefined ? [] : ["settings"] };
  const r = raw as Record<string, unknown>;
  if (r.defaultCamera !== undefined) {
    if (CAMERA_PRESETS.some((p) => p.id === r.defaultCamera)) s.defaultCamera = r.defaultCamera as CameraPresetId;
    else rejected.push("defaultCamera");
  }
  if (r.playbackSpeed !== undefined) {
    if (typeof r.playbackSpeed === "number" && Number.isFinite(r.playbackSpeed)) s.playbackSpeed = clamp(r.playbackSpeed, 0.25, 2);
    else rejected.push("playbackSpeed");
  }
  if (r.defaultIntensity !== undefined) {
    if (typeof r.defaultIntensity === "number" && Number.isFinite(r.defaultIntensity)) s.defaultIntensity = clamp(r.defaultIntensity, 0, 1);
    else rejected.push("defaultIntensity");
  }
  if (r.quality !== undefined) {
    if (r.quality === "low" || r.quality === "medium" || r.quality === "high") s.quality = r.quality;
    else rejected.push("quality");
  }
  if (r.contentLocale !== undefined) {
    if (typeof r.contentLocale === "string" && LOCALE_PATTERN.test(r.contentLocale)) s.contentLocale = r.contentLocale;
    else rejected.push("contentLocale");
  }
  return { settings: s, rejected };
}

/** Configuration export: settings plus the fixed definitions they refer to (for documentation). */
export function exportConfig(s: Settings, now = new Date().toISOString()): string {
  return (
    JSON.stringify(
      {
        format: CONFIG_FORMAT,
        version: 1,
        exportedAt: now,
        settings: s,
        cameraPresets: CAMERA_PRESETS,
        categories: CATEGORIES.map((c) => ({ id: c.id, name: c.name })),
        expressions: EXPRESSIONS.map((e) => ({ id: e.id, number: e.number, categoryId: e.categoryId, displayName: e.displayName, animationStatus: e.animationStatus, animationClip: e.animationClip })),
      },
      null,
      2,
    ) + "\n"
  );
}

/** Reads a configuration file. Only `settings` is applied; the expression list is never imported. */
export function parseConfig(text: string): { settings: Settings; rejected: string[]; error?: string; expressionMismatch: boolean } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { settings: DEFAULT_SETTINGS, rejected: [], error: `Not valid JSON: ${(e as Error).message}`, expressionMismatch: false };
  }
  const d = data as { format?: unknown; version?: unknown; settings?: unknown; expressions?: Array<{ id?: unknown }> };
  if (!d || d.format !== CONFIG_FORMAT) return { settings: DEFAULT_SETTINGS, rejected: [], error: "This is not a studio configuration file.", expressionMismatch: false };
  if (d.version !== 1) return { settings: DEFAULT_SETTINGS, rejected: [], error: `Unsupported configuration version ${String(d.version)}.`, expressionMismatch: false };
  const ids = Array.isArray(d.expressions) ? d.expressions.map((e) => e?.id) : null;
  const expressionMismatch = !!ids && ids.join(",") !== EXPRESSIONS.map((e) => e.id).join(",");
  const { settings, rejected } = coerceSettings(d.settings);
  return { settings, rejected, expressionMismatch };
}

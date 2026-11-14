import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { EXPRESSIONS } from "@/data/expressions";
import { coerceSettings, DEFAULT_SETTINGS, exportConfig, parseConfig } from "./settings";

describe("settings", () => {
  it("rejects invalid values and clamps ranges", () => {
    const { settings, rejected } = coerceSettings({ defaultCamera: "drone", playbackSpeed: 9, defaultIntensity: -2, quality: "ultra", contentLocale: "<script>" });
    expect(rejected.sort()).toEqual(["contentLocale", "defaultCamera", "quality"]);
    expect(settings).toMatchObject({ defaultCamera: "front", playbackSpeed: 2, defaultIntensity: 0, quality: "high", contentLocale: "en" });
  });

  it("round-trips through a configuration export", () => {
    const s = { ...DEFAULT_SETTINGS, defaultCamera: "eye_closeup" as const, playbackSpeed: 0.75, defaultIntensity: 0.6, quality: "medium" as const, contentLocale: "de" };
    const r = parseConfig(exportConfig(s));
    expect(r.error).toBeUndefined();
    expect(r.settings).toEqual(s);
    expect(r.expressionMismatch).toBe(false);
  });

  it("documents all 60 expressions in the export but never imports them", () => {
    const json = JSON.parse(exportConfig(DEFAULT_SETTINGS));
    expect(json.expressions.map((e: { id: string }) => e.id)).toEqual(EXPRESSIONS.map((e) => e.id));
    json.expressions = [{ id: "hacked" }];
    const r = parseConfig(JSON.stringify(json));
    expect(r.expressionMismatch).toBe(true);
    expect(EXPRESSIONS).toHaveLength(60);
  });

  it("refuses non-configuration files", () => {
    expect(parseConfig("{bad").error).toMatch(/JSON/);
    expect(parseConfig('{"schema_version":1}').error).toMatch(/not a studio configuration/);
    expect(parseConfig('{"format":"facial-expression-studio-config","version":2}').error).toMatch(/version/);
  });
});

describe("published docs", () => {
  it("the Blender export guide served by the app matches docs/", () => {
    const root = path.resolve(__dirname, "../../..");
    expect(fs.readFileSync(path.join(root, "public/docs/BLENDER_TO_GLTF.md"), "utf8")).toBe(fs.readFileSync(path.join(root, "docs/BLENDER_TO_GLTF.md"), "utf8"));
  });
});

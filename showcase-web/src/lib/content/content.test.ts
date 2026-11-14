import { describe, expect, it } from "vitest";
import { CATEGORIES, EXPRESSIONS, EXPRESSION_IDS } from "@/data/expressions";
import { exportCsv, exportJson, exportMarkdown, templateJson } from "./export";
import { parseContent } from "./parse";
import { applyEntries, editEntry, entryKey } from "./store";
import type { ContentStore } from "./types";
import { validate } from "./validate";

const APPROVED = `gentle_smile happy_smile big_grin laughter joyful_closed_eye_smile excitement amused affectionate proud_smile playful_happiness
mild_sadness deep_sadness disappointment crying about_to_cry worried nervous embarrassed
mild_annoyance angry furious frustration disgust contempt determined pain
mild_surprise full_surprise shock fear confusion skeptical curious thinking suspicious awe_and_amazement
one_eyebrow_raised both_eyebrows_raised furrowed_eyebrows squint wide_open_eyes left_wink right_wink natural_single_blink double_blink slow_sleepy_blink
open_mouth jaw_drop clenched_teeth pouting_lips asymmetric_smirk lower_lip_bite nose_wrinkle upper_lip_raise lip_press cheeks_puffed rounded_o_mouth pursed_lips_kiss tongue_out mischievous_grin`;

describe("expression manifest", () => {
  it("has exactly the 60 approved IDs, in order, in six categories", () => {
    const lines = APPROVED.split("\n").map((l) => l.split(" "));
    expect(EXPRESSIONS.map((e) => e.id)).toEqual(lines.flat());
    expect(EXPRESSIONS).toHaveLength(60);
    expect(EXPRESSION_IDS.size).toBe(60);
    expect(CATEGORIES).toHaveLength(6);
    CATEGORIES.forEach((c, i) => expect(EXPRESSIONS.filter((e) => e.categoryId === c.id).map((e) => e.id)).toEqual(lines[i]));
    expect(EXPRESSIONS.map((e) => e.number)).toEqual(Array.from({ length: 60 }, (_, i) => i + 1));
  });
  it("claims no animation or thumbnail that does not exist", () => {
    for (const e of EXPRESSIONS) {
      expect(e.animationClip).toBeNull();
      expect(e.thumbnail).toBeNull();
      expect(e.description).toBe("");
      expect(e.animationStatus).toBe("pending_asset");
    }
  });
});

describe("parsers", () => {
  it("reads the documented JSON template shape", () => {
    const p = parseContent("x.json", JSON.stringify({ schema_version: 1, locale: "en", expressions: [{ id: "gentle_smile", title: "Gentle Smile", description: "A subtle natural smile.", tags: ["happy", "positive"], notes: "" }] }));
    expect(p.issues.filter((i) => i.level === "error")).toEqual([]);
    expect(p.entries[0]).toMatchObject({ id: "gentle_smile", locale: "en", title: "Gentle Smile", description: "A subtle natural smile.", tags: ["happy", "positive"] });
  });
  it("rejects malformed JSON and unknown schema versions", () => {
    expect(parseContent("x.json", "{oops").issues[0].level).toBe("error");
    expect(parseContent("x.json", '{"schema_version":2,"locale":"en","expressions":[]}').issues.some((i) => i.level === "error")).toBe(true);
  });
  it("reads CSV with quoted commas, quotes and newlines", () => {
    const csv = 'id,locale,title,description,tags\nangry,fr,Colère,"Sourcils froncés, ""lèvres"" serrées\nligne 2",négatif;sourcils\n';
    const p = parseContent("x.csv", csv);
    expect(p.entries[0]).toMatchObject({ id: "angry", locale: "fr", title: "Colère", description: 'Sourcils froncés, "lèvres" serrées\nligne 2', tags: ["négatif", "sourcils"] });
  });
  it("reads Markdown sections with front-matter locale", () => {
    const md = "---\nlocale: de\n---\n# Inhalt\n## squint\nTitle: Blinzeln\nTags: Augen, Lider\nAugen leicht\nzusammengekniffen.\n\n## shock\nSchock.\n";
    const p = parseContent("x.md", md);
    expect(p.entries).toHaveLength(2);
    expect(p.entries[0]).toMatchObject({ id: "squint", locale: "de", title: "Blinzeln", tags: ["Augen", "Lider"], description: "Augen leicht\nzusammengekniffen." });
  });
  it("reads TXT in both line styles with a locale switch", () => {
    const p = parseContent("x.txt", "# comment\nlip_press: Lips pressed.\nlocale: es\nfear | Miedo | Ojos abiertos.\n");
    expect(p.entries).toEqual([
      expect.objectContaining({ id: "lip_press", locale: "en", description: "Lips pressed." }),
      expect.objectContaining({ id: "fear", locale: "es", title: "Miedo", description: "Ojos abiertos." }),
    ]);
  });
  it("refuses unsupported file types", () => {
    expect(parseContent("x.docx", "").issues[0].level).toBe("error");
  });
});

describe("validation", () => {
  it("flags unknown, invalid and duplicate IDs with typo suggestions, and lists missing IDs", () => {
    const p = parseContent("x.txt", "gentle_smile: a\ngentle_smile: b\ngentle_smiles: c\nBig Grin: d\nnope_nothing: e\n");
    const r = validate(p, {});
    expect(r.counts).toMatchObject({ new: 1, duplicate: 1, invalid: 3 });
    expect(r.duplicateIds).toEqual(["gentle_smile"]);
    expect(r.unknownIds).toContain("gentle_smiles");
    expect(r.entries.find((e) => e.id === "gentle_smiles")?.suggestion).toBe("gentle_smile");
    expect(r.missingByLocale.en).toHaveLength(59);
  });
  it("detects conflicts against stored text", () => {
    const store: ContentStore = { en: { angry: { title: "", description: "Old.", tags: [], notes: "", updatedAt: "", origin: "a" } } };
    const r = validate(parseContent("x.txt", "angry: New.\n"), store);
    expect(r.entries[0]).toMatchObject({ status: "conflict", conflicts: ["description"] });
  });
});

describe("merging never overwrites silently", () => {
  const store: ContentStore = { en: { angry: { title: "Angry", description: "Old.", tags: ["a"], notes: "", updatedAt: "t0", origin: "a" } } };
  const checked = validate(parseContent("x.json", JSON.stringify({ schema_version: 1, locale: "en", expressions: [{ id: "angry", description: "New.", notes: "n" }, { id: "fear", description: "Fear." }] })), store).entries;
  it("fills empty fields and keeps conflicting ones by default", () => {
    const { store: s } = applyEntries(store, checked, { overwrite: new Set(), origin: "f.json", now: "t1" });
    expect(s.en.angry.description).toBe("Old.");
    expect(s.en.angry.notes).toBe("n");
    expect(s.en.fear.description).toBe("Fear.");
    expect(store.en.angry.notes).toBe(""); // input store not mutated
  });
  it("overwrites only entries the user selected", () => {
    const { store: s } = applyEntries(store, checked, { overwrite: new Set([entryKey("en", "angry")]), origin: "f.json", now: "t1" });
    expect(s.en.angry.description).toBe("New.");
  });
});

describe("export round-trips through the parsers", () => {
  let store: ContentStore = {};
  store = editEntry(store, "en", "gentle_smile", { title: "Gentle Smile", description: 'A "subtle", natural smile.\nSecond line.', tags: ["happy", "positive"], notes: "x" }, "t");
  store = editEntry(store, "fr", "shock", { title: "Choc", description: "Bouche ouverte.", tags: [], notes: "" }, "t");
  for (const [name, text] of [["e.json", exportJson(store, "en")], ["e.csv", exportCsv(store)], ["e.md", exportMarkdown(store, "en")]] as const) {
    it(name, () => {
      const p = parseContent(name, text);
      expect(p.issues.filter((i) => i.level === "error")).toEqual([]);
      const g = p.entries.find((e) => e.id === "gentle_smile")!;
      expect(g).toMatchObject({ locale: "en", title: "Gentle Smile", description: 'A "subtle", natural smile.\nSecond line.', tags: ["happy", "positive"] });
    });
  }
  it("CSV keeps every locale", () => {
    expect(parseContent("e.csv", exportCsv(store)).entries.map((e) => e.locale).sort()).toEqual(["en", "fr"]);
  });
  it("template lists all 60 IDs and validates cleanly", () => {
    const r = validate(parseContent("t.json", templateJson()), {});
    expect(r.counts.new).toBe(60);
    expect(r.counts.invalid + r.counts.duplicate).toBe(0);
  });
});

describe("shipped example files", () => {
  const fs = require("node:fs") as typeof import("node:fs");
  const path = require("node:path") as typeof import("node:path");
  const dir = path.resolve(__dirname, "../../../public/templates");
  for (const f of fs.readdirSync(dir).filter((n) => n.startsWith("example."))) {
    it(`${f} validates with no invalid or duplicate entries`, () => {
      const r = validate(parseContent(f, fs.readFileSync(path.join(dir, f), "utf8")), {});
      expect(r.issues.filter((i) => i.level === "error")).toEqual([]);
      expect(r.counts.invalid + r.counts.duplicate).toBe(0);
      expect(r.counts.new).toBeGreaterThan(0);
    });
  }
});

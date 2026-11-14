import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { CATEGORIES, EXPRESSIONS } from "@/data/expressions";
import { exportCsv, exportJson, exportMarkdown } from "@/lib/content/export";
import { parseContent } from "@/lib/content/parse";
import { applyEntries, editEntry, entryKey } from "@/lib/content/store";
import type { ContentStore } from "@/lib/content/types";
import { validate } from "@/lib/content/validate";
import { exportBackup } from "./backup";
import { LEGACY_BACKUP_KEY, LEGACY_KEY, MIGRATION_META, migrateLocalStorage, type MigrationResult } from "./migrate";
import { diffStores, IndexedDbRepository, MemoryRepository, type ContentRepository, type ImportRecord } from "./repository";
import { sanitizeText } from "./sanitize";

let factory: IDBFactory;
beforeEach(() => {
  factory = new IDBFactory(); // fresh, isolated database per test
});

const open = () => IndexedDbRepository.open(factory, "test-db");

/** What the UI does on Apply: review -> merge -> diff -> one transaction. */
async function importFile(repo: ContentRepository, name: string, text: string, overwrite: string[] = []) {
  const current = await repo.loadAll();
  const report = validate(parseContent(name, text), current);
  if (!report.canApply) return { report, applied: 0 };
  const { store: next, applied, skipped } = applyEntries(current, report.entries, { overwrite: new Set(overwrite), origin: name });
  const rec: ImportRecord = { fileName: name, format: "json", size: text.length, importedAt: "t", locales: report.locales, applied, skipped, overwritten: overwrite.length, text, sanitized: false };
  await repo.write(diffStores(current, next), rec);
  return { report, applied };
}

const fixture = JSON.stringify({ schema_version: 1, locale: "en", expressions: [{ id: "gentle_smile", title: "Gentle Smile", description: "A subtle natural smile.", tags: ["happy"] }, { id: "angry", description: "Brows down." }] });

class KV {
  m = new Map<string, string>();
  getItem(k: string) {
    return this.m.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.m.set(k, v);
  }
  removeItem(k: string) {
    this.m.delete(k);
  }
}

describe("IndexedDB repository", () => {
  it("persists across a reopen (page refresh)", async () => {
    const a = await open();
    await importFile(a, "f.json", fixture);
    a.close();
    const b = await open();
    const s = await b.loadAll();
    expect(s.en.gentle_smile.description).toBe("A subtle natural smile.");
    expect(s.en.angry.description).toBe("Brows down.");
    expect((await b.listImports())[0]).toMatchObject({ fileName: "f.json", applied: 2 });
  });

  it("keeps languages independent", async () => {
    const r = await open();
    await importFile(r, "en.json", fixture);
    await importFile(r, "fr.txt", "locale: fr\ngentle_smile | Sourire doux | Un sourire subtil.\n");
    const s = await r.loadAll();
    expect(s.en.gentle_smile.title).toBe("Gentle Smile");
    expect(s.fr.gentle_smile.title).toBe("Sourire doux");
    await r.write([{ locale: "fr", id: "gentle_smile", entry: null }]);
    const s2 = await r.loadAll();
    expect(s2.fr).toBeUndefined();
    expect(s2.en.gentle_smile.description).toBe("A subtle natural smile.");
  });

  it("never overwrites conflicting text unless that entry is selected", async () => {
    const r = await open();
    await importFile(r, "a.json", fixture);
    const changed = "gentle_smile: Replaced.\nangry: Also replaced.\n";
    const first = await importFile(r, "b.txt", changed);
    expect(first.report.counts.conflict).toBe(2);
    expect((await r.loadAll()).en.gentle_smile.description).toBe("A subtle natural smile.");
    await importFile(r, "b.txt", changed, [entryKey("en", "angry")]);
    const s = await r.loadAll();
    expect(s.en.gentle_smile.description).toBe("A subtle natural smile.");
    expect(s.en.angry.description).toBe("Also replaced.");
  });

  it("invalid uploads change nothing", async () => {
    const r = await open();
    await importFile(r, "a.json", fixture);
    const before = JSON.stringify(await r.loadAll());
    for (const [n, t] of [
      ["bad.json", "{not json"],
      ["bad2.json", '{"schema_version":9,"locale":"en","expressions":[{"id":"angry","description":"x"}]}'],
      ["bad.csv", "title,description\nx,y\n"],
      ["bad.md", "no sections here"],
      ["only-unknown.txt", "not_an_expression: x\n"],
      ["bad.docx", "x"],
    ])
      expect((await importFile(r, n, t)).applied).toBe(0);
    expect(JSON.stringify(await r.loadAll())).toBe(before);
    expect(await r.listImports()).toHaveLength(1);
  });

  it("a failed transaction leaves stored content intact", async () => {
    const r = await open();
    await importFile(r, "a.json", fixture);
    const before = JSON.stringify(await r.loadAll());
    // key path needs strings; an object id makes the put throw inside the transaction
    await expect(r.write([{ locale: "en", id: "lip_press", entry: { title: "", description: "ok", tags: [], notes: "", updatedAt: "", origin: "" } }, { locale: "en", id: {} as unknown as string, entry: null }])).rejects.toBeTruthy();
    expect(JSON.stringify(await r.loadAll())).toBe(before);
  });
});

describe("export and re-import preserve content", () => {
  let store: ContentStore = {};
  store = editEntry(store, "en", "gentle_smile", { title: "Gentle Smile", description: 'A "subtle", natural smile.\nLine 2.', tags: ["happy", "positive"], notes: "n1" }, "t");
  store = editEntry(store, "fr", "angry", { title: "Colère", description: "Sourcils froncés.", tags: ["négatif"], notes: "" }, "t");
  const cases: Array<[string, string, string[]]> = [
    ["backup.json", exportBackup(store, []), ["en", "fr"]],
    ["all.csv", exportCsv(store), ["en", "fr"]],
    ["en.json", exportJson(store, "en"), ["en"]],
    ["en.md", exportMarkdown(store, "en"), ["en"]],
  ];
  for (const [name, text, locales] of cases)
    it(name, async () => {
      const r = await open();
      await importFile(r, name, text);
      const s = await r.loadAll();
      for (const l of locales)
        for (const [id, e] of Object.entries(store[l])) expect(s[l][id]).toMatchObject({ title: e.title, description: e.description, tags: e.tags, notes: e.notes });
    });
});

describe("localStorage migration", () => {
  const legacy: ContentStore = {
    en: {
      gentle_smile: { title: "Gentle", description: "Legacy smile.", tags: ["a"], notes: "", updatedAt: "2026-11-14T00:00:00Z", origin: "old.json" },
      angry: { title: "", description: "<script>alert(1)</script>Legacy <b>angry</b>.", tags: [], notes: "", updatedAt: "x", origin: "old.json" },
      not_real: { title: "", description: "x", tags: [], notes: "", updatedAt: "x", origin: "x" },
    },
    "bad locale!": { shock: { title: "", description: "x", tags: [], notes: "", updatedAt: "", origin: "" } },
  };

  it("copies everything new, keeps IndexedDB text on conflict, keeps a backup and runs once", async () => {
    const r = await open();
    await r.write([{ locale: "en", id: "gentle_smile", entry: { title: "Gentle", description: "Newer text.", tags: [], notes: "", updatedAt: "y", origin: "idb" } }]);
    const kv = new KV();
    kv.setItem(LEGACY_KEY, JSON.stringify(legacy));
    const res = await migrateLocalStorage(r, kv);
    expect(res).toMatchObject({ status: "migrated", migrated: 1, rejected: 2, sanitized: 1 });
    expect(res.conflicts.map((c) => c.id)).toEqual(["gentle_smile"]);
    const s = await r.loadAll();
    expect(s.en.gentle_smile.description).toBe("Newer text.");
    expect(s.en.angry.description).toBe("Legacy angry.");
    expect(s.en.not_real).toBeUndefined();
    expect(kv.getItem(LEGACY_KEY)).toBeNull();
    expect(kv.getItem(LEGACY_BACKUP_KEY)).toBe(JSON.stringify(legacy));
    expect((await r.getMeta<MigrationResult>(MIGRATION_META))?.conflicts).toHaveLength(1);
    expect((await migrateLocalStorage(r, kv)).status).toBe("already-done");
  });

  it("leaves corrupt legacy data untouched and reports failure", async () => {
    const r = await open();
    const kv = new KV();
    kv.setItem(LEGACY_KEY, "{corrupt");
    const res = await migrateLocalStorage(r, kv);
    expect(res.status).toBe("failed");
    expect(kv.getItem(LEGACY_KEY)).toBe("{corrupt");
    expect(await r.loadAll()).toEqual({});
  });

  it("does nothing when there is no legacy content", async () => {
    expect((await migrateLocalStorage(await open(), new KV())).status).toBe("none");
  });
});

describe("plain text only", () => {
  it("strips script, HTML and javascript: URLs", () => {
    expect(sanitizeText('Hi<script>evil()</script> <img src=x onerror="a()">there <a href="javascript:x">l</a>').text).toBe("Hi there l");
    expect(sanitizeText("<style>body{}</style>ok").text).toBe("ok");
    expect(sanitizeText("2 < 3 and 5 > 4").text).toBe("2 < 3 and 5 > 4");
  });
  it("imports are sanitized before storage and flagged", async () => {
    const r = await open();
    const { report } = await importFile(r, "x.txt", "gentle_smile: Nice <script>steal()</script>smile.\n");
    expect(report.issues.some((i) => i.message.includes("markup was removed"))).toBe(true);
    expect((await r.loadAll()).en.gentle_smile.description).toBe("Nice smile.");
  });
});

describe("memory fallback", () => {
  it("implements the same contract", async () => {
    const r = new MemoryRepository();
    await importFile(r, "a.json", fixture);
    expect((await r.loadAll()).en.angry.description).toBe("Brows down.");
  });
});

describe("expression manifest is unaffected by content", () => {
  const snapshot = () => JSON.stringify(EXPRESSIONS.map((e) => [e.id, e.number, e.categoryId, e.animationStatus, e.animationClip, e.thumbnail, e.displayName]));
  it("IDs, categories and animation fields are unchanged after imports and edits", async () => {
    const before = snapshot();
    const r = await open();
    await importFile(r, "a.json", fixture);
    await importFile(r, "b.txt", "gentle_smile: changed\n", [entryKey("en", "gentle_smile")]);
    expect(snapshot()).toBe(before);
    expect(EXPRESSIONS).toHaveLength(60);
    expect(CATEGORIES.map((c) => EXPRESSIONS.filter((e) => e.categoryId === c.id).length)).toEqual([10, 8, 8, 10, 10, 14]);
  });
  it("is frozen against mutation", () => {
    expect(Object.isFrozen(EXPRESSIONS)).toBe(true);
    expect(() => {
      (EXPRESSIONS[0] as { animationClip: string | null }).animationClip = "fake";
    }).toThrow();
    expect(EXPRESSIONS[0].animationClip).toBeNull();
  });
});

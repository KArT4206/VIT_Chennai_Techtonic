"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { IdbAssetStore, MemoryAssetStore, emptyLicence, sha256Hex, type AssetStore, type CharacterAsset, type LicenceRecord } from "@/lib/assets/asset-store";
import { inspectGltf, type AssetReport } from "@/lib/assets/gltf-inspect";
import { clean } from "@/lib/storage/sanitize";

export const MAX_ASSET_BYTES = 150 * 1024 * 1024;

export interface Candidate {
  fileName: string;
  size: number;
  sha256: string;
  data: ArrayBuffer;
  report: AssetReport;
}

interface AssetsCtx {
  ready: boolean;
  storageKind: "indexeddb" | "memory" | "loading";
  storageError?: string;
  character: CharacterAsset | null;
  /** Reads and validates a file without storing it. */
  inspectFile: (file: File) => Promise<Candidate>;
  /** Stores a validated file as the character (replaces any existing one; the UI confirms first). */
  storeCandidate: (c: Candidate, licence: LicenceRecord) => Promise<void>;
  updateLicence: (licence: LicenceRecord) => Promise<void>;
  removeCharacter: () => Promise<void>;
}

const Ctx = createContext<AssetsCtx | null>(null);

const cleanLicence = (l: LicenceRecord): LicenceRecord => ({ source: clean(l.source).trim(), author: clean(l.author).trim(), licence: clean(l.licence).trim(), url: clean(l.url).trim(), notes: clean(l.notes).trim(), confirmed: !!l.confirmed });

export function AssetsProvider({ children }: { children: ReactNode }) {
  const store = useRef<AssetStore | null>(null);
  const [ready, setReady] = useState(false);
  const [storageKind, setKind] = useState<AssetsCtx["storageKind"]>("loading");
  const [storageError, setError] = useState<string>();
  const [character, setCharacter] = useState<CharacterAsset | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let s: AssetStore;
      try {
        if (typeof indexedDB === "undefined") throw new Error("IndexedDB is not available");
        s = await IdbAssetStore.open();
      } catch (e) {
        s = new MemoryAssetStore();
        setError(`${(e as Error).message}. An imported character will only last until this page is closed.`);
      }
      if (cancelled) return s.close();
      store.current = s;
      setKind(s.kind);
      try {
        setCharacter((await s.get()) ?? null);
      } catch (e) {
        setError(`Could not read the stored character: ${(e as Error).message}`);
      }
      setReady(true);
    })();
    return () => {
      cancelled = true;
      store.current?.close();
    };
  }, []);

  const inspectFile = useCallback(async (file: File): Promise<Candidate> => {
    if (file.size > MAX_ASSET_BYTES) throw new Error(`${file.name} is larger than 150 MB.`);
    const data = await file.arrayBuffer();
    return { fileName: clean(file.name), size: file.size, sha256: await sha256Hex(data), data, report: inspectGltf(file.name, data) };
  }, []);

  const storeCandidate = useCallback(async (c: Candidate, licence: LicenceRecord) => {
    if (!store.current) throw new Error("Storage is not ready");
    if (c.report.checks.some((x) => x.id === "container" && x.status === "fail")) throw new Error("This file is not a readable glTF 2.0 file and cannot be stored as a character.");
    const a: CharacterAsset = { slot: "character", fileName: c.fileName, size: c.size, sha256: c.sha256, importedAt: new Date().toISOString(), data: c.data, report: c.report, licence: cleanLicence(licence) };
    await store.current.put(a);
    setCharacter(a);
  }, []);

  const updateLicence = useCallback(
    async (licence: LicenceRecord) => {
      if (!store.current || !character) return;
      const a = { ...character, licence: cleanLicence(licence) };
      await store.current.put(a);
      setCharacter(a);
    },
    [character],
  );

  const removeCharacter = useCallback(async () => {
    if (!store.current) return;
    await store.current.remove();
    setCharacter(null);
  }, []);

  const value = useMemo(() => ({ ready, storageKind, storageError, character, inspectFile, storeCandidate, updateLicence, removeCharacter }), [ready, storageKind, storageError, character, inspectFile, storeCandidate, updateLicence, removeCharacter]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAssets(): AssetsCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAssets must be used inside AssetsProvider");
  return c;
}

export { emptyLicence };

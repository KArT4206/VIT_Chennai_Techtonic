/**
 * Character asset storage. A SEPARATE IndexedDB database from the text content
 * ("facial-expression-studio"), so content storage is untouched by asset changes.
 *
 *   database "facial-expression-studio-assets" v1, store "assets", keyPath "slot"
 *   slot "character": the one active character file (bytes + validation report + licence record)
 */

import type { AssetReport } from "./gltf-inspect";

export const ASSET_DB = "facial-expression-studio-assets";

export interface LicenceRecord {
  source: string;
  author: string;
  licence: string;
  url: string;
  notes: string;
  /** The user confirms they hold written permission to use this file in the studio. */
  confirmed: boolean;
}

export const emptyLicence = (): LicenceRecord => ({ source: "", author: "", licence: "", url: "", notes: "", confirmed: false });

export interface CharacterAsset {
  slot: "character";
  fileName: string;
  size: number;
  sha256: string;
  importedAt: string;
  data: ArrayBuffer;
  report: AssetReport;
  licence: LicenceRecord;
}

export interface AssetStore {
  readonly kind: "indexeddb" | "memory";
  get(): Promise<CharacterAsset | undefined>;
  put(a: CharacterAsset): Promise<void>;
  remove(): Promise<void>;
  close(): void;
}

const req = <T>(r: IDBRequest<T>) =>
  new Promise<T>((res, rej) => {
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
const done = (tx: IDBTransaction) =>
  new Promise<void>((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
    tx.onabort = () => rej(tx.error ?? new Error("aborted"));
  });

export class IdbAssetStore implements AssetStore {
  readonly kind = "indexeddb" as const;
  private constructor(private db: IDBDatabase) {}
  static async open(factory: IDBFactory = indexedDB, name = ASSET_DB): Promise<IdbAssetStore> {
    const o = factory.open(name, 1);
    o.onupgradeneeded = () => {
      if (!o.result.objectStoreNames.contains("assets")) o.result.createObjectStore("assets", { keyPath: "slot" });
    };
    const db = await new Promise<IDBDatabase>((res, rej) => {
      o.onsuccess = () => res(o.result);
      o.onerror = () => rej(o.error ?? new Error("IndexedDB open failed"));
      o.onblocked = () => rej(new Error("Asset database upgrade blocked by another tab"));
    });
    db.onversionchange = () => db.close();
    return new IdbAssetStore(db);
  }
  async get() {
    return (await req(this.db.transaction("assets").objectStore("assets").get("character"))) as CharacterAsset | undefined;
  }
  async put(a: CharacterAsset) {
    const tx = this.db.transaction("assets", "readwrite");
    tx.objectStore("assets").put(a);
    await done(tx);
  }
  async remove() {
    const tx = this.db.transaction("assets", "readwrite");
    tx.objectStore("assets").delete("character");
    await done(tx);
  }
  close() {
    this.db.close();
  }
}

export class MemoryAssetStore implements AssetStore {
  readonly kind = "memory" as const;
  private a: CharacterAsset | undefined;
  async get() {
    return this.a;
  }
  async put(a: CharacterAsset) {
    this.a = a;
  }
  async remove() {
    this.a = undefined;
  }
  close() {}
}

export async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

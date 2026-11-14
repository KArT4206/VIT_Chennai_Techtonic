import type { CharacterAdapter } from "./adapter";
import { ScanHeadAdapter } from "./scan-head";

/**
 * The active character: the built-in 3D Scan Store scan head (see scan-head.ts for its licence
 * scope). Only expressions its real shape keys can produce have clips.
 *
 * Deliberately NOT used: the old male MakeHuman competition head (scene.blend) and the
 * makehuman_model_exports.zip model.
 */
export function createCharacterAdapter(): CharacterAdapter {
  return new ScanHeadAdapter();
}

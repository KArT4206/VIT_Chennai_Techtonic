import { PendingCharacterAdapter, type CharacterAdapter } from "./adapter";

/**
 * The active character. Swap this for a real adapter once the approved character asset and its
 * expression clips have been imported (docs/CHARACTER_INTEGRATION.md).
 *
 * Deliberately NOT used: the old male MakeHuman competition head (scene.blend) and the
 * makehuman_model_exports.zip model.
 */
export function createCharacterAdapter(): CharacterAdapter {
  return new PendingCharacterAdapter();
}

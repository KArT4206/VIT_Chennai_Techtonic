/**
 * Character animation adapter: the only contract between the studio UI and a 3D character.
 *
 * The studio never animates faces itself. It asks the adapter whether a clip exists for an
 * expression and, if so, asks it to play. Until a real character asset (with real clips) is imported,
 * the PendingCharacterAdapter is used: it reports "pending" and refuses to play. No facial motion is
 * faked.
 *
 * To integrate a character later, implement this interface (see docs/CHARACTER_INTEGRATION.md) and
 * register it in src/lib/character/registry.ts. The UI does not change.
 */

export type AssetStatus = "pending" | "loading" | "ready" | "error";

export interface PlayOptions {
  /** 0..1, scales the expression's weight. */
  intensity: number;
  /** Playback rate multiplier, 0.25..2. */
  speed: number;
  /** -1 (left side only) .. 0 (symmetric) .. +1 (right side only). Adapters without L/R data ignore it. */
  asymmetry: number;
}

export type PlaybackState = "idle" | "playing" | "paused" | "neutral";

export interface CharacterInfo {
  name: string;
  source: string;
  licence: string;
}

export interface CharacterAdapter {
  readonly status: AssetStatus;
  /** Human-readable reason when status is "pending" or "error". */
  readonly statusMessage: string;
  readonly info: CharacterInfo | null;
  /** True only if the imported asset really contains a clip for this expression ID. */
  hasClip(expressionId: string): boolean;
  /** Clip name inside the asset for this expression, or null. */
  clipFor(expressionId: string): string | null;
  /** Whether the asset supports independent left/right weighting. */
  readonly supportsAsymmetry: boolean;
  play(expressionId: string, opts: PlayOptions): boolean;
  pause(): void;
  resume(): void;
  /** Blend back to the neutral pose. */
  neutral(): void;
  replay(expressionId: string, opts: PlayOptions): boolean;
  /** Live updates while playing. */
  update(opts: PlayOptions): void;
}

export class PendingCharacterAdapter implements CharacterAdapter {
  readonly status: AssetStatus = "pending";
  readonly statusMessage = "3D character asset pending import";
  readonly info = null;
  readonly supportsAsymmetry = false;
  hasClip(): boolean {
    return false;
  }
  clipFor(): string | null {
    return null;
  }
  play(): boolean {
    return false;
  }
  pause(): void {}
  resume(): void {}
  neutral(): void {}
  replay(): boolean {
    return false;
  }
  update(): void {}
}

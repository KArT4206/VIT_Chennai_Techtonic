import type { AssetStatus, CharacterAdapter, CharacterInfo, PlayOptions } from "./adapter";

/**
 * Built-in character: the 3D Scan Store Free HD Head (8K skin colour) on the GNM rig.
 *
 * Licence: one-time permission for the Samsung PRISM Hackathon 2026 Track 1 publication only
 * (public display allowed within it). The GLB is NOT committed; it is copied into
 * public/characters/ locally (git-ignored). Do not reuse it in any later project or publication.
 *
 * The head has 12 real shape keys (eyes and brows only). Only expressions that those keys can
 * genuinely produce get a clip; every other expression reports "no clip". Nothing is faked.
 */
export const SCAN_HEAD_URL = "/characters/scan_head.glb";

type W = Record<string, number>;
/** [time in seconds, shape-key weights at that time]. Weights not listed are 0. */
type Key = [number, W];

const both = (a: string, v: number): W => ({ [`${a}_L`]: v, [`${a}_R`]: v });
const hold = (w: W, attack = 0.35): Key[] => [
  [0, {}],
  [attack, w],
];
const blink = (t0: number, close = 0.08, shut = 0.05, open = 0.14): Key[] => [
  [t0, {}],
  [t0 + close, both("blink", 1)],
  [t0 + close + shut, both("blink", 1)],
  [t0 + close + shut + open, {}],
];

/** Clips built only from the head's real shape keys. */
const CLIPS: Record<string, Key[]> = {
  one_eyebrow_raised: hold({ brow_raise_L: 1, brow_furrow_R: 0.3 }),
  both_eyebrows_raised: hold(both("brow_raise", 1)),
  furrowed_eyebrows: hold(both("brow_furrow", 1)),
  squint: hold({ ...both("squint", 1), ...both("brow_furrow", 0.3) }),
  wide_open_eyes: hold({ ...both("surprise", 1), ...both("brow_raise", 0.4) }),
  left_wink: [[0, {}], [0.15, { blink_L: 1, squint_R: 0.2 }], [0.55, { blink_L: 1, squint_R: 0.2 }], [0.8, {}]],
  right_wink: [[0, {}], [0.15, { blink_R: 1, squint_L: 0.2 }], [0.55, { blink_R: 1, squint_L: 0.2 }], [0.8, {}]],
  natural_single_blink: blink(0.1),
  double_blink: [...blink(0.1), ...blink(0.5).slice(1)],
  slow_sleepy_blink: [[0, {}], [0.6, { ...both("blink", 0.55), ...both("lid_follow", 0.5) }], [1.1, both("blink", 1)], [1.5, both("blink", 1)], [2.3, { ...both("blink", 0.4), ...both("lid_follow", 0.3) }]],
  mild_surprise: hold({ ...both("surprise", 0.5), ...both("brow_raise", 0.6) }),
};

export const SCAN_HEAD_CLIP_IDS = Object.keys(CLIPS);

function sample(keys: Key[], t: number): W {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, w1] = keys[i];
    if (t <= t1) {
      const [t0, w0] = keys[i - 1];
      const k = t1 === t0 ? 1 : (t - t0) / (t1 - t0);
      const s = k * k * (3 - 2 * k);
      const out: W = {};
      for (const n of new Set([...Object.keys(w0), ...Object.keys(w1)])) out[n] = (w0[n] ?? 0) + ((w1[n] ?? 0) - (w0[n] ?? 0)) * s;
      return out;
    }
  }
  return keys[keys.length - 1][1];
}

/** Morph targets the scene registers: name -> (influence array, index). */
export interface MorphBinding {
  influences: number[];
  index: number;
}

export class ScanHeadAdapter implements CharacterAdapter {
  status: AssetStatus = "ready";
  readonly statusMessage = "";
  readonly info: CharacterInfo = {
    name: "Scan head (3D Scan Store)",
    source: "3D Scan Store · Free HD Head, 8K skin colour",
    licence: "One-time permission for this publication only",
  };
  readonly supportsAsymmetry = true;

  private bindings = new Map<string, MorphBinding[]>();
  private clip: Key[] | null = null;
  private t = 0;
  private paused = false;
  private opts: PlayOptions = { intensity: 1, speed: 1, asymmetry: 0 };
  /** Current weights, blended toward the target each frame (smooth neutral / switching). */
  private current: W = {};

  /** Called by the viewport once the GLB has loaded. */
  attach(bindings: Map<string, MorphBinding[]>) {
    this.bindings = bindings;
  }
  detach() {
    this.bindings = new Map();
  }

  hasClip(id: string) {
    return id in CLIPS;
  }
  clipFor(id: string) {
    return id in CLIPS ? `${id} (shape keys)` : null;
  }
  play(id: string, opts: PlayOptions) {
    const c = CLIPS[id];
    if (!c) return false;
    this.clip = c;
    this.t = 0;
    this.paused = false;
    this.opts = opts;
    return true;
  }
  replay(id: string, opts: PlayOptions) {
    return this.play(id, opts);
  }
  pause() {
    this.paused = true;
  }
  resume() {
    this.paused = false;
  }
  neutral() {
    this.clip = null;
    this.paused = false;
  }
  update(opts: PlayOptions) {
    this.opts = opts;
  }

  /** Advances playback and writes morph influences. Called every frame by the viewport. */
  tick(dt: number) {
    if (this.clip && !this.paused) this.t += dt * this.opts.speed;
    const raw = this.clip ? sample(this.clip, this.t) : {};
    const a = this.opts.asymmetry;
    const sideL = Math.min(1, 1 - a); // asymmetry -1 = left side only, +1 = right side only
    const sideR = Math.min(1, 1 + a);
    const k = 1 - Math.exp(-dt * 25);
    for (const name of this.bindings.keys()) {
      const side = name.endsWith("_L") ? sideL : name.endsWith("_R") ? sideR : 1;
      const target = Math.min(1, (raw[name] ?? 0) * this.opts.intensity * side);
      const v = (this.current[name] ?? 0) + (target - (this.current[name] ?? 0)) * k;
      this.current[name] = v;
      for (const b of this.bindings.get(name)!) b.influences[b.index] = v;
    }
  }
}

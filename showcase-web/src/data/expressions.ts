/**
 * Canonical expression manifest: exactly 60 stable IDs in six categories.
 *
 * IDs are permanent. Content files (descriptions, translations) and future animation clips attach to
 * these IDs. Never rename an ID; add a new one instead.
 *
 * `animationClip` and `thumbnail` stay null until a real character asset and its clips are imported.
 * Nothing here pretends an animation exists.
 */

export type CategoryId = "happiness" | "sadness" | "anger" | "surprise_thinking" | "eyes_eyebrows" | "mouth_lips_cheeks";

export type AnimationStatus = "pending_asset" | "clip_missing" | "ready";

export interface Category {
  id: CategoryId;
  name: string;
  order: number;
}

export interface Expression {
  /** Stable machine ID, e.g. "gentle_smile". */
  id: string;
  /** 1-based position in the approved list. */
  number: number;
  categoryId: CategoryId;
  displayName: string;
  /** Empty until supplied by a content file. */
  description: string;
  tags: string[];
  animationStatus: AnimationStatus;
  /** Name of the animation clip inside the imported character asset; null until it exists. */
  animationClip: string | null;
  /** URL of a thumbnail; null until real renders of the real character exist. */
  thumbnail: string | null;
}

export const CATEGORIES: readonly Category[] = [
  { id: "happiness", name: "Happiness", order: 1 },
  { id: "sadness", name: "Sadness", order: 2 },
  { id: "anger", name: "Anger", order: 3 },
  { id: "surprise_thinking", name: "Surprise and Thinking", order: 4 },
  { id: "eyes_eyebrows", name: "Eyes and Eyebrows", order: 5 },
  { id: "mouth_lips_cheeks", name: "Mouth, Lips and Cheeks", order: 6 },
] as const;

type Row = [id: string, displayName: string, tags: string[]];

const ROWS: Record<CategoryId, Row[]> = {
  happiness: [
    ["gentle_smile", "Gentle smile", ["positive", "smile", "subtle"]],
    ["happy_smile", "Happy smile", ["positive", "smile"]],
    ["big_grin", "Big grin", ["positive", "smile", "teeth"]],
    ["laughter", "Laughter", ["positive", "mouth-open", "teeth"]],
    ["joyful_closed_eye_smile", "Joyful closed-eye smile", ["positive", "smile", "eyes-closed"]],
    ["excitement", "Excitement", ["positive", "brows", "mouth-open"]],
    ["amused", "Amused", ["positive", "smile", "asymmetric"]],
    ["affectionate", "Affectionate", ["positive", "smile", "soft"]],
    ["proud_smile", "Proud smile", ["positive", "smile", "head"]],
    ["playful_happiness", "Playful happiness", ["positive", "wink", "asymmetric"]],
  ],
  sadness: [
    ["mild_sadness", "Mild sadness", ["negative", "brows", "subtle"]],
    ["deep_sadness", "Deep sadness", ["negative", "brows", "mouth"]],
    ["disappointment", "Disappointment", ["negative", "mouth"]],
    ["crying", "Crying", ["negative", "eyes", "mouth"]],
    ["about_to_cry", "About to cry", ["negative", "chin", "eyes"]],
    ["worried", "Worried", ["negative", "brows"]],
    ["nervous", "Nervous", ["negative", "brows", "mouth"]],
    ["embarrassed", "Embarrassed", ["negative", "smile", "gaze"]],
  ],
  anger: [
    ["mild_annoyance", "Mild annoyance", ["negative", "brows", "subtle"]],
    ["angry", "Angry", ["negative", "brows", "mouth"]],
    ["furious", "Furious", ["negative", "brows", "teeth"]],
    ["frustration", "Frustration", ["negative", "brows", "mouth"]],
    ["disgust", "Disgust", ["negative", "nose", "upper-lip"]],
    ["contempt", "Contempt", ["negative", "asymmetric", "mouth"]],
    ["determined", "Determined", ["brows", "lips"]],
    ["pain", "Pain", ["negative", "brows", "eyes", "nose"]],
  ],
  surprise_thinking: [
    ["mild_surprise", "Mild surprise", ["surprise", "brows", "subtle"]],
    ["full_surprise", "Full surprise", ["surprise", "brows", "mouth-open"]],
    ["shock", "Shock", ["surprise", "mouth-open", "eyes"]],
    ["fear", "Fear", ["negative", "brows", "mouth"]],
    ["confusion", "Confusion", ["thinking", "brows", "asymmetric"]],
    ["skeptical", "Skeptical", ["thinking", "brows", "asymmetric"]],
    ["curious", "Curious", ["thinking", "brows", "head"]],
    ["thinking", "Thinking", ["thinking", "gaze", "lips"]],
    ["suspicious", "Suspicious", ["thinking", "eyes", "gaze"]],
    ["awe_and_amazement", "Awe and amazement", ["surprise", "brows", "mouth-open"]],
  ],
  eyes_eyebrows: [
    ["one_eyebrow_raised", "One eyebrow raised", ["brows", "asymmetric"]],
    ["both_eyebrows_raised", "Both eyebrows raised", ["brows"]],
    ["furrowed_eyebrows", "Furrowed eyebrows", ["brows"]],
    ["squint", "Squint", ["eyes", "lids"]],
    ["wide_open_eyes", "Wide-open eyes", ["eyes", "lids"]],
    ["left_wink", "Left wink", ["eyes", "wink", "asymmetric"]],
    ["right_wink", "Right wink", ["eyes", "wink", "asymmetric"]],
    ["natural_single_blink", "Natural single blink", ["eyes", "blink"]],
    ["double_blink", "Double blink", ["eyes", "blink"]],
    ["slow_sleepy_blink", "Slow sleepy blink", ["eyes", "blink"]],
  ],
  mouth_lips_cheeks: [
    ["open_mouth", "Open mouth", ["mouth", "jaw"]],
    ["jaw_drop", "Jaw drop", ["mouth", "jaw"]],
    ["clenched_teeth", "Clenched teeth", ["mouth", "teeth"]],
    ["pouting_lips", "Pouting lips", ["lips"]],
    ["asymmetric_smirk", "Asymmetric smirk", ["mouth", "asymmetric"]],
    ["lower_lip_bite", "Lower lip bite", ["lips", "teeth"]],
    ["nose_wrinkle", "Nose wrinkle", ["nose"]],
    ["upper_lip_raise", "Upper lip raise", ["lips", "upper-lip"]],
    ["lip_press", "Lip press", ["lips"]],
    ["cheeks_puffed", "Cheeks puffed", ["cheeks"]],
    ["rounded_o_mouth", "Rounded O-shaped mouth", ["mouth", "lips"]],
    ["pursed_lips_kiss", "Pursed lips / kiss", ["lips"]],
    ["tongue_out", "Tongue out", ["mouth", "tongue"]],
    ["mischievous_grin", "Mischievous grin", ["mouth", "smile", "asymmetric"]],
  ],
};

export const EXPRESSIONS: readonly Expression[] = (() => {
  const out: Expression[] = [];
  for (const cat of CATEGORIES) {
    for (const [id, displayName, tags] of ROWS[cat.id]) {
      out.push({
        id,
        number: out.length + 1,
        categoryId: cat.id,
        displayName,
        description: "",
        tags,
        animationStatus: "pending_asset",
        animationClip: null,
        thumbnail: null,
      });
    }
  }
  return out;
})();

export const EXPRESSION_IDS: ReadonlySet<string> = new Set(EXPRESSIONS.map((e) => e.id));

export const expressionById = (id: string): Expression | undefined => EXPRESSIONS.find((e) => e.id === id);

export const categoryById = (id: CategoryId): Category => CATEGORIES.find((c) => c.id === id)!;

/** Expression IDs whose motion is a timed sequence rather than a held pose. */
export const SEQUENCE_EXPRESSIONS: ReadonlySet<string> = new Set(["natural_single_blink", "double_blink", "slow_sleepy_blink", "laughter"]);

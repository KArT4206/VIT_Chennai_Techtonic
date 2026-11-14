/**
 * Visual TEST combinations for the preset candidate (Phase 2N). They use only the 34 morph targets the
 * exported GLB actually contains (ARKit-style names). They are candidate mappings under review, not
 * approved expression definitions, and nothing here is used by the Studio.
 */
export type Weights = Record<string, number>;

export const TEST_COMBOS: Array<{ id: string; label: string; weights: Weights; note?: string }> = [
  { id: "happy_smile", label: "Happy smile", weights: { mouthSmile: 0.85, eyeSquintLeft: 0.35, eyeSquintRight: 0.35 } },
  { id: "laughter", label: "Laughter", weights: { mouthSmile: 1, jawOpen: 0.45, eyeSquintLeft: 0.6, eyeSquintRight: 0.6, browInnerUp: 0.2 } },
  { id: "deep_sadness", label: "Sadness", weights: { browInnerUp: 0.9, mouthFrown: 0.8, eyeSquintLeft: 0.15, eyeSquintRight: 0.15 } },
  { id: "angry", label: "Anger", weights: { browDownLeft: 1, browDownRight: 1, noseSneerLeft: 0.35, noseSneerRight: 0.35, mouthPress: 0.6, eyeSquintLeft: 0.35, eyeSquintRight: 0.35 } },
  { id: "full_surprise", label: "Surprise", weights: { browInnerUp: 0.8, browOuterUpLeft: 1, browOuterUpRight: 1, eyeWideLeft: 0.9, eyeWideRight: 0.9, jawOpen: 0.4 } },
  { id: "fear", label: "Fear", weights: { browInnerUp: 1, browOuterUpLeft: 0.5, browOuterUpRight: 0.5, eyeWideLeft: 1, eyeWideRight: 1, mouthStretch: 0.8, jawOpen: 0.15 } },
  { id: "confusion", label: "Confusion", weights: { browDownLeft: 0.7, browOuterUpRight: 0.8, mouthPress: 0.3 }, note: "Brow asymmetry only; the mouth shapes are symmetric." },
  { id: "left_wink", label: "Left wink", weights: { eyeBlinkLeft: 1, mouthSmile: 0.25 } },
  { id: "right_wink", label: "Right wink", weights: { eyeBlinkRight: 1, mouthSmile: 0.25 } },
  { id: "open_mouth", label: "Open mouth", weights: { jawOpen: 0.75 } },
  { id: "pursed_lips_kiss", label: "Pursed lips", weights: { mouthPucker: 1 } },
  { id: "nose_wrinkle", label: "Nose wrinkle", weights: { noseSneerLeft: 1, noseSneerRight: 1 } },
];

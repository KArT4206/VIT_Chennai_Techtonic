/**
 * Camera presets in a head-centred frame: origin at the midpoint between the eyes, +Y up, the face
 * looks along +Z, the subject's left is +X. Units are metres. A future character is placed so that
 * its eye midpoint sits at the origin (see docs/CHARACTER_INTEGRATION.md).
 */
export type CameraPresetId = "front" | "three_quarter_left" | "three_quarter_right" | "profile_left" | "profile_right" | "eye_closeup" | "mouth_closeup";

export interface CameraPreset {
  id: CameraPresetId;
  label: string;
  position: [number, number, number];
  target: [number, number, number];
}

const D = 0.85;
const Q = D * Math.SQRT1_2;

export const CAMERA_PRESETS: readonly CameraPreset[] = [
  { id: "front", label: "Front", position: [0, -0.02, D], target: [0, -0.04, 0] },
  { id: "three_quarter_left", label: "¾ left", position: [Q, -0.02, Q], target: [0, -0.04, 0] },
  { id: "three_quarter_right", label: "¾ right", position: [-Q, -0.02, Q], target: [0, -0.04, 0] },
  { id: "profile_left", label: "Profile left", position: [D, -0.02, 0], target: [0, -0.04, 0] },
  { id: "profile_right", label: "Profile right", position: [-D, -0.02, 0], target: [0, -0.04, 0] },
  { id: "eye_closeup", label: "Eyes", position: [0, 0.0, 0.32], target: [0, 0.0, 0.06] },
  { id: "mouth_closeup", label: "Mouth", position: [0, -0.075, 0.32], target: [0, -0.075, 0.06] },
];

export const presetById = (id: CameraPresetId) => CAMERA_PRESETS.find((p) => p.id === id)!;

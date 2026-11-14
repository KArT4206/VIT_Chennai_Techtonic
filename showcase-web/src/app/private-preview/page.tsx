import type { Metadata } from "next";
import { CharacterTest } from "@/components/preset-test/PresetTest";

export const metadata: Metadata = { title: "Private character preview · Facial Expression Studio", robots: { index: false } };

/** Real shape keys of the scan-based GNM head (Phase 2B/2D controls, scan-calibrated). */
const COMBOS: Array<{ id: string; label: string; weights: Record<string, number> }> = [
  { id: "blink", label: "Blink (both)", weights: { blink_L: 1, blink_R: 1 } },
  { id: "left_wink", label: "Left wink", weights: { blink_L: 1 } },
  { id: "right_wink", label: "Right wink", weights: { blink_R: 1 } },
  { id: "squint", label: "Squint", weights: { squint_L: 1, squint_R: 1 } },
  { id: "surprise", label: "Surprise", weights: { surprise_L: 1, surprise_R: 1 } },
  { id: "brow_raise", label: "Brows raised", weights: { brow_raise_L: 1, brow_raise_R: 1 } },
  { id: "one_brow", label: "One brow raised", weights: { brow_raise_L: 1 } },
  { id: "brow_furrow", label: "Brows furrowed", weights: { brow_furrow_L: 1, brow_furrow_R: 1 } },
];

export default function Page() {
  return <CharacterTest src="/api/private/character" banner="PRIVATE · 3D Scan Store head (one-time permission) · local preview only" fileLabel="gnm_scan_private.glb · 8K skin colour" combos={COMBOS} />;
}

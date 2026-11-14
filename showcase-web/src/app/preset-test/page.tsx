import type { Metadata } from "next";
import { PresetTest } from "@/components/preset-test/PresetTest";

export const metadata: Metadata = { title: "Preset candidate test · Facial Expression Studio", robots: { index: false } };

export default function Page() {
  return <PresetTest />;
}

import type { Metadata } from "next";
import { AssetManager } from "@/components/assets/AssetManager";

export const metadata: Metadata = { title: "Character & Assets · Facial Expression Studio" };

export default function AssetsPage() {
  return <AssetManager />;
}

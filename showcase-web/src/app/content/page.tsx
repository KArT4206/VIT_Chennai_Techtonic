import type { Metadata } from "next";
import { ContentManager } from "@/components/content/ContentManager";

export const metadata: Metadata = { title: "Content Manager · Facial Expression Studio" };

export default function ContentPage() {
  return <ContentManager />;
}

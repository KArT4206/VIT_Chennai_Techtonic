import type { Metadata } from "next";
import { SettingsPage } from "@/components/settings/SettingsPage";

export const metadata: Metadata = { title: "Settings & Export · Facial Expression Studio" };

export default function Page() {
  return <SettingsPage />;
}

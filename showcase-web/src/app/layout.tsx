import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { ContentProvider } from "@/lib/state/content-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Facial Expression Studio",
  description: "Select any of 60 facial expressions and view them on a real-time 3D character.",
};

export const viewport: Viewport = { themeColor: "#0b0c0f" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-full flex-col">
        <ContentProvider>
          <AppHeader />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
        </ContentProvider>
      </body>
    </html>
  );
}

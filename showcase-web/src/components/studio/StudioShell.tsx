"use client";

import { StudioProvider } from "@/lib/state/studio-context";
import { ControlsPanel } from "./ControlsPanel";
import { ExpressionLibrary } from "./ExpressionLibrary";
import { ViewerPanel } from "./ViewerPanel";

export function StudioShell() {
  return (
    <StudioProvider>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-ink-800 lg:h-[calc(100dvh-3.5rem)] lg:grid-cols-[320px_minmax(0,1fr)_340px]">
        <section aria-label="Expression library" className="order-2 flex min-h-0 flex-col bg-ink-900 lg:order-1">
          <ExpressionLibrary />
        </section>
        <section aria-label="3D character viewer" className="order-1 flex min-h-[60vh] flex-col bg-ink-950 lg:order-2 lg:min-h-0">
          <ViewerPanel />
        </section>
        <section aria-label="Expression controls" className="order-3 flex min-h-0 flex-col bg-ink-900">
          <ControlsPanel />
        </section>
      </div>
    </StudioProvider>
  );
}

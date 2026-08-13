import { GlobeView } from "@/components/globe/globe-view";
import { AppShell } from "@/components/shared/app-shell";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "G-SIB Systemic Risk — Geographic View" };

export default function GlobePage() {
  return (
    <AppShell>
      <GlobeView />
    </AppShell>
  );
}

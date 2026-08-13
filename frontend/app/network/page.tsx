import { NetworkView } from "@/components/network/network-view";
import { AppShell } from "@/components/shared/app-shell";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "G-SIB Systemic Risk — Propagation Network" };

export default function NetworkPage() {
  return (
    <AppShell>
      <NetworkView />
    </AppShell>
  );
}

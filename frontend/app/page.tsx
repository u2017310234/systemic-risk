import { AppShell } from "@/components/shared/app-shell";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "G-SIB Systemic Risk Dashboard — SRISK, ΔCoVaR, MES" };

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardView />
    </AppShell>
  );
}

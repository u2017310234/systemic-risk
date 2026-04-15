import { AppShell } from "@/components/shared/app-shell";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { getAvailableDates, getLatestSnapshot } from "@/lib/data-adapter";

export default async function DashboardPage() {
  const [dates, latest] = await Promise.all([getAvailableDates(), getLatestSnapshot()]);

  return (
    <AppShell dates={dates} lastUpdated={latest.date}>
      <DashboardView />
    </AppShell>
  );
}

import { NetworkView } from "@/components/network/network-view";
import { AppShell } from "@/components/shared/app-shell";
import { getAvailableDates, getLatestSnapshot } from "@/lib/data-adapter";

export default async function NetworkPage() {
  const [dates, latest] = await Promise.all([getAvailableDates(), getLatestSnapshot()]);

  return (
    <AppShell dates={dates} lastUpdated={latest.date}>
      <NetworkView dates={dates} />
    </AppShell>
  );
}

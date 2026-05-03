"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

import { GlobeCanvas } from "@/components/globe/globe-canvas";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageSkeleton } from "@/components/shared/page-skeleton";
import { Panel } from "@/components/shared/panel";
import { REGION_COLORS, REGION_LABELS } from "@/lib/constants";
import { formatDelta, formatPercent, formatUsdBn } from "@/lib/format";
import { BANK_LOCATIONS } from "@/lib/bank-locations";
import { fetchSnapshotByDate } from "@/lib/public-data";
import type { BankMetric } from "@/lib/types";

export function GlobeView() {
  const searchParams = useSearchParams();
  const selectedDate = searchParams.get("date") ?? undefined;
  const region = searchParams.get("region") ?? undefined;
  const [selectedBankId, setSelectedBankId] = useState<string | null>(null);

  const snapshotQuery = useQuery({
    queryKey: ["globe-snapshot", selectedDate, region],
    queryFn: () => fetchSnapshotByDate(selectedDate, region)
  });

  const enrichedBanks = useMemo(() => {
    if (!snapshotQuery.data) {
      return [];
    }

    const maxSrisk = Math.max(...snapshotQuery.data.banks.map((bank) => bank.srisk_usd_bn), 1);

    return snapshotQuery.data.banks
      .map((bank) => {
        const location = BANK_LOCATIONS[bank.bank_id];
        if (!location) {
          return null;
        }
        return {
          ...bank,
          location,
          markerSize: 5 + (bank.srisk_usd_bn / maxSrisk) * 10
        };
      })
      .flatMap((bank) => (bank ? [bank] : []))
      .sort((left, right) => right.srisk_usd_bn - left.srisk_usd_bn);
  }, [snapshotQuery.data]);

  const selectedBank =
    enrichedBanks.find((bank) => bank.bank_id === selectedBankId) ?? enrichedBanks[0] ?? null;

  const markers = enrichedBanks.map((bank) => ({
    id: bank.bank_id,
    label: bank.bank_name,
    lat: bank.location.lat,
    lon: bank.location.lon,
    size: bank.markerSize,
    color: hexToRgba(REGION_COLORS[bank.region]),
    selected: bank.bank_id === selectedBank?.bank_id
  }));

  if (snapshotQuery.isLoading) {
    return <PageSkeleton chartCount={2} />;
  }

  if (snapshotQuery.isError) {
    return (
      <div className="mt-6">
        <ErrorState
          title="Globe data failed to load"
          description="The geographic systemic view could not load the selected snapshot."
          onRetry={() => snapshotQuery.refetch()}
        />
      </div>
    );
  }

  if (!enrichedBanks.length) {
    return (
      <div className="mt-6">
        <EmptyState
          title="No banks available on the globe"
          description="The selected region currently has no mapped geographic points."
        />
      </div>
    );
  }

  return (
    <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.8fr)_380px]">
      <div className="space-y-6">
        <Panel className="overflow-hidden">
          <div className="mb-5 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.28em] text-cool">Geographic Systemic Map</p>
              <h2 className="mt-2 text-3xl font-semibold">Drag the globe to inspect where systemic concentration sits</h2>
            </div>
            <p className="max-w-xl text-sm text-muted">
              Marker size tracks SRISK magnitude. Click a visible point to inspect the bank and its latest systemic metrics.
            </p>
          </div>

          <GlobeCanvas
            markers={markers}
            selectedId={selectedBank?.bank_id}
            onSelect={(bankId) => setSelectedBankId(bankId)}
          />

          <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted">
            <span className="rounded-full border border-line/70 bg-panelAlt/60 px-3 py-1">Drag: rotate globe</span>
            <span className="rounded-full border border-line/70 bg-panelAlt/60 px-3 py-1">Click point: open details</span>
            <span className="rounded-full border border-line/70 bg-panelAlt/60 px-3 py-1">
              Snapshot: {snapshotQuery.data?.date}
            </span>
          </div>
        </Panel>

        <Panel>
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Top Systemic Footprint</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {enrichedBanks.slice(0, 6).map((bank, index) => (
              <button
                key={bank.bank_id}
                type="button"
                onClick={() => setSelectedBankId(bank.bank_id)}
                className="rounded-2xl border border-line/70 bg-panelAlt/50 p-4 text-left transition hover:border-accent/70"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">#{index + 1}</p>
                    <h3 className="mt-2 text-lg font-semibold">{bank.bank_name}</h3>
                    <p className="mt-1 text-xs uppercase tracking-[0.2em] text-muted">
                      {bank.bank_id} · {bank.location.city}
                    </p>
                  </div>
                  <div
                    className="mt-1 h-3 w-3 rounded-full"
                    style={{ backgroundColor: REGION_COLORS[bank.region] }}
                    aria-hidden="true"
                  />
                </div>
                <div className="mt-4 flex items-end justify-between gap-3">
                  <span className="text-sm text-muted">{REGION_LABELS[bank.region]}</span>
                  <span className="text-base font-semibold">{formatUsdBn(bank.srisk_usd_bn)}</span>
                </div>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      <Panel className="h-fit xl:sticky xl:top-6">
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Selected Location</p>
        {selectedBank ? <SelectedBankCard bank={selectedBank} /> : null}
      </Panel>
    </div>
  );
}

function SelectedBankCard({
  bank
}: {
  bank: BankMetric & {
    location: { city: string; country: string };
  };
}) {
  return (
    <div className="mt-4">
      <div className="rounded-[28px] border border-line/70 bg-[radial-gradient(circle_at_top,rgba(74,184,217,0.22),transparent_45%),linear-gradient(180deg,rgba(10,25,39,0.96),rgba(5,13,22,0.96))] p-5">
        <p className="text-xs uppercase tracking-[0.24em] text-muted">
          {bank.location.city}, {bank.location.country}
        </p>
        <h3 className="mt-3 text-2xl font-semibold">{bank.bank_name}</h3>
        <p className="mt-2 text-sm uppercase tracking-[0.22em] text-muted">
          {bank.bank_id} · {REGION_LABELS[bank.region]}
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <MetricChip label="SRISK" value={formatUsdBn(bank.srisk_usd_bn)} />
          <MetricChip label="Share" value={formatPercent(bank.srisk_share_pct)} />
          <MetricChip label="MES" value={formatDelta(bank.mes)} />
          <MetricChip label="LRMES" value={formatDelta(bank.lrmes)} />
          <MetricChip label="CoVaR" value={formatDelta(bank.covar)} />
          <MetricChip label="Delta CoVaR" value={formatDelta(bank.delta_covar)} />
        </div>
      </div>
    </div>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line/70 bg-black/10 p-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">{label}</p>
      <p className="mt-2 text-base font-semibold">{value}</p>
    </div>
  );
}

function hexToRgba(hex: string) {
  const normalized = hex.replace("#", "");
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, 1)`;
}

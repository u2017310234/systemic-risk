"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/shared/chart-card";
import { AppShell } from "@/components/shared/app-shell";
import { EChartsClient } from "@/components/shared/echarts-client";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageSkeleton } from "@/components/shared/page-skeleton";
import { Panel } from "@/components/shared/panel";
import { REGION_LABELS } from "@/lib/constants";
import { formatDelta, formatPercent, formatUsdBn } from "@/lib/format";
import { fetchBankHistory, fetchLatestSnapshot } from "@/lib/public-data";
import type { BankMetric } from "@/lib/types";

export default function BankPage() {
  const params = useParams<{ bankId: string }>();
  const bankId = params.bankId.toUpperCase();

  const latestQuery = useQuery({
    queryKey: ["latest-snapshot"],
    queryFn: () => fetchLatestSnapshot()
  });
  const historyQuery = useQuery({
    queryKey: ["bank-history-page", bankId],
    queryFn: () => fetchBankHistory(bankId)
  });

  const snapshotBank = useMemo(
    () => latestQuery.data?.banks.find((bank: BankMetric) => bank.bank_id === bankId) ?? null,
    [bankId, latestQuery.data]
  );

  if (latestQuery.isLoading || historyQuery.isLoading) {
    return (
      <AppShell>
        <PageSkeleton chartCount={1} />
      </AppShell>
    );
  }

  if (latestQuery.isError || historyQuery.isError) {
    return (
      <AppShell>
        <div className="mt-6">
          <ErrorState
            title="Bank page failed to load"
            description="The app could not load the selected bank snapshot or history."
            onRetry={() => {
              latestQuery.refetch();
              historyQuery.refetch();
            }}
          />
        </div>
      </AppShell>
    );
  }

  if (!snapshotBank || !historyQuery.data?.length) {
    return (
      <AppShell>
        <div className="mt-6">
          <EmptyState
            title="Bank not found"
            description="The requested bank ID is missing from the current dataset."
          />
        </div>
      </AppShell>
    );
  }

  const trendOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "#10263a",
      borderColor: "#1c3851"
    },
    legend: {
      textStyle: { color: "#eff7ff" }
    },
    grid: { top: 36, left: 18, right: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: "category",
      data: historyQuery.data.map((row) => row.date),
      axisLabel: { color: "#8ea7bc", formatter: (value: string) => value.slice(5) }
    },
    yAxis: [
      {
        type: "value",
        axisLabel: { color: "#8ea7bc" },
        splitLine: { lineStyle: { color: "rgba(28,56,81,0.4)" } }
      },
      {
        type: "value",
        axisLabel: { color: "#8ea7bc" }
      }
    ],
    series: [
      {
        type: "line",
        name: "SRISK",
        smooth: true,
        showSymbol: false,
        data: historyQuery.data.map((row) => row.srisk_usd_bn),
        lineStyle: { color: "#f4b860", width: 3 }
      },
      {
        type: "line",
        name: "Delta CoVaR",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: historyQuery.data.map((row) => row.delta_covar),
        lineStyle: { color: "#4ab8d9", width: 2 }
      }
    ]
  };

  return (
    <AppShell>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_360px]">
        <ChartCard
          title={`${snapshotBank.bank_name} Historical View`}
          description="Reserved single-bank drill-down page with the core two-metric trend view."
        >
          <EChartsClient option={trendOption} className="h-[560px] w-full" />
        </ChartCard>

        <Panel>
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Current Snapshot</p>
          <h2 className="mt-3 text-2xl font-semibold">{snapshotBank.bank_name}</h2>
          <p className="mt-2 text-sm uppercase tracking-[0.24em] text-muted">
            {snapshotBank.bank_id} · {REGION_LABELS[snapshotBank.region]}
          </p>
          <div className="mt-5 space-y-3">
            <Metric label="SRISK" value={formatUsdBn(snapshotBank.srisk_usd_bn)} />
            <Metric label="SRISK Share" value={formatPercent(snapshotBank.srisk_share_pct)} />
            <Metric label="MES" value={formatDelta(snapshotBank.mes)} />
            <Metric label="LRMES" value={formatDelta(snapshotBank.lrmes)} />
            <Metric label="CoVaR" value={formatDelta(snapshotBank.covar)} />
            <Metric label="Delta CoVaR" value={formatDelta(snapshotBank.delta_covar)} />
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line/70 bg-panelAlt/50 p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">{label}</p>
      <p className="mt-2 text-base font-semibold">{value}</p>
    </div>
  );
}

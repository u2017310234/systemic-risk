import { notFound } from "next/navigation";

import { ChartCard } from "@/components/shared/chart-card";
import { AppShell } from "@/components/shared/app-shell";
import { EChartsClient } from "@/components/shared/echarts-client";
import { Panel } from "@/components/shared/panel";
import { getAvailableDates, getBankHistory, getLatestSnapshot } from "@/lib/data-adapter";
import { formatDelta, formatPercent, formatUsdBn } from "@/lib/format";
import { REGION_LABELS } from "@/lib/constants";
import type { BankHistoryRow, BankMetric } from "@/lib/types";

type Props = {
  params: Promise<{ bankId: string }>;
};

export default async function BankPage({ params }: Props) {
  const { bankId } = await params;
  const [dates, latest, history]: [string[], { date: string; banks: BankMetric[] }, BankHistoryRow[]] =
    await Promise.all([
    getAvailableDates(),
    getLatestSnapshot(),
    getBankHistory(bankId)
    ]);

  const snapshotBank = latest.banks.find(
    (bank: BankMetric) => bank.bank_id === bankId.toUpperCase()
  );
  if (!snapshotBank || !history.length) {
    notFound();
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
      data: history.map((row: BankHistoryRow) => row.date),
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
        data: history.map((row: BankHistoryRow) => row.srisk_usd_bn),
        lineStyle: { color: "#f4b860", width: 3 }
      },
      {
        type: "line",
        name: "ΔCoVaR",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: history.map((row: BankHistoryRow) => row.delta_covar),
        lineStyle: { color: "#4ab8d9", width: 2 }
      }
    ]
  };

  return (
    <AppShell dates={dates} lastUpdated={latest.date}>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_360px]">
        <ChartCard
          title={`${snapshotBank.bank_name} Historical View`}
          description="Reserved single-bank drill-down page with the core 2-metric trend view."
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
            <Metric label="ΔCoVaR" value={formatDelta(snapshotBank.delta_covar)} />
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

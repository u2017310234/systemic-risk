"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { EChartsClient } from "@/components/shared/echarts-client";
import { Panel } from "@/components/shared/panel";
import { formatDelta, formatPercent, formatUsdBn } from "@/lib/format";
import { buildMiniTrend, fetchBankHistory } from "@/lib/public-data";
import type { BankMetric } from "@/lib/types";
import { REGION_LABELS } from "@/lib/constants";

export function BankDetailPanel({
  bank,
  topBanks
}: {
  bank: BankMetric | null;
  topBanks: BankMetric[];
}) {
  const bankQuery = useQuery({
    queryKey: ["bank-detail", bank?.bank_id],
    queryFn: async () => {
      const rows = await fetchBankHistory(bank!.bank_id);
      return { miniTrend: buildMiniTrend(rows, "srisk_usd_bn", 30) };
    },
    enabled: Boolean(bank)
  });

  const trendOption = {
    backgroundColor: "transparent",
    grid: { top: 14, left: 10, right: 10, bottom: 14, containLabel: true },
    xAxis: {
      type: "category",
      data: bankQuery.data?.miniTrend.map((item) => item.date.slice(5)) ?? [],
      axisLabel: { color: "#8ea7bc" }
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8ea7bc" },
      splitLine: { lineStyle: { color: "rgba(28,56,81,0.4)" } }
    },
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: false,
        data: bankQuery.data?.miniTrend.map((item) => item.value) ?? [],
        lineStyle: { color: "#f4b860", width: 2 },
        areaStyle: { color: "rgba(244,184,96,0.12)" }
      }
    ],
    tooltip: {
      trigger: "axis",
      backgroundColor: "#10263a",
      borderColor: "#1c3851"
    }
  };

  return (
    <div className="space-y-6">
      <Panel className="sticky top-6">
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Selected Bank</p>
        {bank ? (
          <>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold">{bank.bank_name}</h3>
              <p className="mt-2 text-sm uppercase tracking-[0.24em] text-muted">
                {bank.bank_id} · {REGION_LABELS[bank.region]}
              </p>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <MiniStat label="SRISK" value={formatUsdBn(bank.srisk_usd_bn)} />
              <MiniStat label="Share" value={formatPercent(bank.srisk_share_pct)} />
              <MiniStat label="MES" value={formatDelta(bank.mes)} />
              <MiniStat label="LRMES" value={formatDelta(bank.lrmes)} />
              <MiniStat label="CoVaR" value={formatDelta(bank.covar)} />
              <MiniStat label="Delta CoVaR" value={formatDelta(bank.delta_covar)} />
            </div>

            <div className="mt-6">
              <p className="mb-3 text-sm text-muted">Recent 30-day SRISK trend</p>
              <EChartsClient option={trendOption} className="h-44 w-full" />
            </div>

            <Link
              href={`/bank/${bank.bank_id}`}
              className="mt-5 inline-flex rounded-full border border-line px-4 py-2 text-sm transition hover:border-accent/80"
            >
              Open bank drill-down
            </Link>
          </>
        ) : (
          <div className="mt-5 rounded-2xl border border-dashed border-line/70 p-5 text-sm text-muted">
            Click a node to open the bank detail panel.
          </div>
        )}
      </Panel>

      <Panel>
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Current Top Systemic Banks</p>
        <div className="mt-4 space-y-3">
          {topBanks.slice(0, 5).map((item) => (
            <div key={item.bank_id} className="rounded-2xl border border-line/70 bg-panelAlt/50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{item.bank_name}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.24em] text-muted">{item.bank_id}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">{formatUsdBn(item.srisk_usd_bn)}</p>
                  <p className="mt-1 text-xs text-muted">{formatDelta(item.delta_covar)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line/70 bg-panelAlt/50 p-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">{label}</p>
      <p className="mt-2 text-base font-semibold">{value}</p>
    </div>
  );
}

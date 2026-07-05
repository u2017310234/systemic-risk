"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/shared/chart-card";
import { EChartsClient } from "@/components/shared/echarts-client";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { PageSkeleton } from "@/components/shared/page-skeleton";
import { Panel } from "@/components/shared/panel";
import { useI18n } from "@/lib/i18n";
import { formatDate, formatDelta, formatPercent, formatUsdBn } from "@/lib/format";
import { fetchSnapshotByDate, fetchSnapshotSeries } from "@/lib/public-data";
import type { Region, SystemSnapshot } from "@/lib/types";
import { REGION_COLORS, REGION_OPTIONS } from "@/lib/constants";

export function DashboardView() {
  const { lang, t, regionLabel } = useI18n();
  const searchParams = useSearchParams();
  const selectedDate = searchParams.get("date") ?? undefined;
  const selectedRegion = searchParams.get("region") ?? undefined;

  const snapshotQuery = useQuery({
    queryKey: ["snapshot", selectedDate, selectedRegion],
    queryFn: () => fetchSnapshotByDate(selectedDate, selectedRegion)
  });
  const historyQuery = useQuery({
    queryKey: ["snapshot-series", selectedDate, selectedRegion],
    queryFn: () => fetchSnapshotSeries(selectedDate, 30, selectedRegion)
  });

  const derived = useMemo(() => {
    const snapshot = snapshotQuery.data;
    const series = historyQuery.data?.snapshots ?? [];
    if (!snapshot) {
      return null;
    }
    const banks = [...snapshot.banks].sort((left, right) => right.srisk_usd_bn - left.srisk_usd_bn);
    const deltaLeaders = [...snapshot.banks].sort((left, right) => left.delta_covar - right.delta_covar);
    const regionTotals = REGION_OPTIONS.map((region) => ({
      region,
      value: snapshot.banks
        .filter((bank) => bank.region === region)
        .reduce((sum, bank) => sum + bank.srisk_usd_bn, 0)
    })).filter((item) => item.value > 0);

    return {
      topSrisk: banks[0],
      topDelta: deltaLeaders[0],
      topBanks: banks.slice(0, 10),
      regionTotals,
      systemSeries: series.map((item) => ({
        date: item.date,
        value: item.system_srisk_usd_bn
      }))
    };
  }, [historyQuery.data?.snapshots, snapshotQuery.data]);

  if (snapshotQuery.isLoading || historyQuery.isLoading) {
    return <PageSkeleton chartCount={2} />;
  }

  if (snapshotQuery.isError || historyQuery.isError) {
    return (
      <div className="mt-6">
        <ErrorState
          title={t.dashboard.dataErrorTitle}
          description={t.dashboard.dataErrorDescription}
          onRetry={() => {
            snapshotQuery.refetch();
            historyQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (!snapshotQuery.data || !derived || !snapshotQuery.data.banks.length) {
    return (
      <div className="mt-6">
        <EmptyState
          title={t.dashboard.emptyTitle}
          description={t.dashboard.emptyDescription}
        />
      </div>
    );
  }

  const snapshot = snapshotQuery.data;

  const rankingOption = {
    backgroundColor: "transparent",
    grid: { top: 10, left: 10, right: 18, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { color: "#8ea7bc" },
      splitLine: { lineStyle: { color: "rgba(28,56,81,0.4)" } }
    },
    yAxis: {
      type: "category",
      inverse: true,
      axisLabel: { color: "#eff7ff" },
      data: derived.topBanks.map((bank) => bank.bank_id)
    },
    series: [
      {
        type: "bar",
        data: derived.topBanks.map((bank) => ({
          value: bank.srisk_usd_bn,
          itemStyle: { color: REGION_COLORS[bank.region] }
        })),
        barWidth: 18,
        label: {
          show: true,
          position: "right",
          color: "#eff7ff",
          formatter: ({ value }: { value: number }) => formatUsdBn(value, lang)
        }
      }
    ],
    tooltip: {
      trigger: "axis",
      backgroundColor: "#10263a",
      borderColor: "#1c3851"
    }
  };

  const seriesOption = {
    backgroundColor: "transparent",
    grid: { top: 16, left: 20, right: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      axisLabel: { color: "#8ea7bc", formatter: (value: string) => value.slice(5) },
      data: derived.systemSeries.map((item) => item.date)
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8ea7bc" },
      splitLine: { lineStyle: { color: "rgba(28,56,81,0.4)" } }
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#10263a",
      borderColor: "#1c3851"
    },
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: false,
        data: derived.systemSeries.map((item) => item.value),
        lineStyle: { color: "#f4b860", width: 3 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(244,184,96,0.35)" },
              { offset: 1, color: "rgba(244,184,96,0.02)" }
            ]
          }
        }
      }
    ]
  };

  const regionOption = {
    tooltip: {
      trigger: "item",
      backgroundColor: "#10263a",
      borderColor: "#1c3851"
    },
    series: [
      {
        type: "pie",
        radius: ["52%", "75%"],
        data: derived.regionTotals.map((item) => ({
          value: item.value,
          name: regionLabel(item.region as Region),
          itemStyle: { color: REGION_COLORS[item.region as Region] }
        })),
        label: {
          color: "#eff7ff"
        }
      }
    ]
  };

  const metricCards = [
    {
      label: t.dashboard.systemWideSrisk,
      value: formatUsdBn(snapshot.system_srisk_usd_bn, lang),
      hint: t.dashboard.systemWideSriskHint
    },
    {
      label: t.dashboard.mostSystemicSrisk,
      value: `${derived.topSrisk.bank_name} (${derived.topSrisk.bank_id})`,
      hint: formatUsdBn(derived.topSrisk.srisk_usd_bn, lang)
    },
    {
      label: t.dashboard.mostSystemicDelta,
      value: `${derived.topDelta.bank_name} (${derived.topDelta.bank_id})`,
      hint: formatDelta(derived.topDelta.delta_covar)
    },
    {
      label: t.dashboard.lastUpdatedDate,
      value: formatDate(snapshot.date),
      hint: lang === "zh" ? `${snapshot.banks.length} ${t.dashboard.banksInFilter}` : `${snapshot.banks.length} ${t.dashboard.banksInFilter}`
    }
  ];

  return (
    <div className="mt-6 space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((card) => (
          <Panel key={card.label} className="overflow-hidden">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">{card.label}</p>
            <h2 className="mt-4 text-2xl font-semibold leading-tight">{card.value}</h2>
            <p className="mt-3 text-sm text-muted">{card.hint}</p>
          </Panel>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_360px]">
        <div className="space-y-6">
          <ChartCard
            title={t.dashboard.rankingTitle}
            description={t.dashboard.rankingDescription}
          >
            <EChartsClient option={rankingOption} className="h-[420px] w-full" />
          </ChartCard>

          <ChartCard
            title={t.dashboard.replayTitle}
            description={t.dashboard.replayDescription}
          >
            <EChartsClient option={seriesOption} className="h-[320px] w-full" />
          </ChartCard>
        </div>

        <div className="space-y-6">
          <ChartCard
            title={t.dashboard.concentrationTitle}
            description={t.dashboard.concentrationDescription}
          >
            <EChartsClient option={regionOption} className="h-[320px] w-full" />
          </ChartCard>

          <Panel>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">{t.dashboard.methodology}</p>
                <h3 className="mt-2 text-lg font-semibold">{t.dashboard.metricGuide}</h3>
              </div>
              <Link href="/network" className="rounded-full border border-line px-3 py-2 text-sm transition hover:border-accent">
                {t.dashboard.openNetwork}
              </Link>
            </div>
            <div className="mt-4 space-y-4 text-sm text-muted">
              <p>
                <span className="text-text">SRISK</span> {t.dashboard.sriskGuide}
              </p>
              <p>
                <span className="text-text">Delta CoVaR</span> {t.dashboard.deltaGuide}
              </p>
              <p>
                <span className="text-text">MES / LRMES</span> {t.dashboard.mesGuide}
              </p>
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">{t.dashboard.drillDown}</p>
            <div className="mt-4 space-y-3">
              {derived.topBanks.slice(0, 6).map((bank) => (
                <Link
                  key={bank.bank_id}
                  href={`/bank/${bank.bank_id}`}
                  className="flex items-center justify-between rounded-2xl border border-line/70 bg-panelAlt/50 px-4 py-3 transition hover:border-accent/80"
                >
                  <div>
                    <p className="font-medium">{bank.bank_name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.24em] text-muted">
                      {bank.bank_id} · {regionLabel(bank.region)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold">{formatUsdBn(bank.srisk_usd_bn, lang)}</p>
                    <p className="mt-1 text-xs text-muted">{formatPercent(bank.srisk_share_pct)}</p>
                  </div>
                </Link>
              ))}
            </div>
          </Panel>
        </div>
      </section>
    </div>
  );
}

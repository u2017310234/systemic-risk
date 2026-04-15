"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { BankDetailPanel } from "@/components/network/bank-detail-panel";
import { Legend } from "@/components/network/legend";
import { NetworkControls } from "@/components/network/network-controls";
import { NetworkGraph } from "@/components/network/network-graph";
import { NetworkSummary } from "@/components/network/network-summary";
import { TimelinePlayer } from "@/components/network/timeline-player";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Panel } from "@/components/shared/panel";
import { buildInterpretiveGraph } from "@/lib/network-builder";
import type { BankMetric, MetricEmphasis, NetworkViewMode, SystemSnapshot } from "@/lib/types";

async function fetchSnapshot(date?: string, region?: string) {
  const params = new URLSearchParams();
  if (date) {
    params.set("date", date);
  }
  if (region && region !== "ALL") {
    params.set("region", region);
  }
  const response = await fetch(`/api/system/history?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch snapshot");
  }
  return (await response.json()) as SystemSnapshot;
}

async function fetchSeries(date?: string, region?: string, lookback = 30) {
  const params = new URLSearchParams({
    series: "true",
    lookback: String(lookback)
  });
  if (date) {
    params.set("date", date);
  }
  if (region && region !== "ALL") {
    params.set("region", region);
  }
  const response = await fetch(`/api/system/history?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch history");
  }
  return (await response.json()) as { snapshots: SystemSnapshot[] };
}

export function NetworkView({ dates }: { dates: string[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const selectedDate = searchParams.get("date") ?? dates.at(-1) ?? "";
  const region = searchParams.get("region") ?? undefined;
  const thresholdFromUrl = Number(searchParams.get("threshold") ?? 0.6);
  const lookbackFromUrl = Number(searchParams.get("lookback") ?? 30);
  const emphasisFromUrl = (searchParams.get("metric") ?? "balanced") as MetricEmphasis;

  const [selectedBankId, setSelectedBankId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<NetworkViewMode>("full");
  const [playbackWindow, setPlaybackWindow] = useState(90);
  const [isPlaying, setIsPlaying] = useState(false);

  const snapshotQuery = useQuery({
    queryKey: ["network-snapshot", selectedDate, region],
    queryFn: () => fetchSnapshot(selectedDate, region)
  });
  const historyQuery = useQuery({
    queryKey: ["network-history", selectedDate, region, lookbackFromUrl],
    queryFn: () => fetchSeries(selectedDate, region, lookbackFromUrl)
  });

  useEffect(() => {
    if (viewMode !== "ego" && selectedBankId) {
      return;
    }
    if (!selectedBankId) {
      return;
    }
  }, [selectedBankId, viewMode]);

  const graph = useMemo(() => {
    if (!snapshotQuery.data || !historyQuery.data?.snapshots.length) {
      return null;
    }
    return buildInterpretiveGraph(snapshotQuery.data, historyQuery.data.snapshots, {
      threshold: thresholdFromUrl,
      metricEmphasis: emphasisFromUrl,
      selectedBankId,
      viewMode
    });
  }, [emphasisFromUrl, historyQuery.data?.snapshots, selectedBankId, snapshotQuery.data, thresholdFromUrl, viewMode]);

  const topBanks = useMemo(
    () =>
      snapshotQuery.data?.banks
        ? [...snapshotQuery.data.banks].sort((left, right) => right.srisk_usd_bn - left.srisk_usd_bn)
        : [],
    [snapshotQuery.data?.banks]
  );

  const selectedBank: BankMetric | null =
    snapshotQuery.data?.banks.find((bank) => bank.bank_id === selectedBankId) ?? null;

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    router.replace(`/network?${params.toString()}`, { scroll: false });
  }

  if (snapshotQuery.isError || historyQuery.isError) {
    return (
      <div className="mt-6">
        <ErrorState
          title="Network data failed to load"
          description="The propagation view could not compute the graph from the selected history window."
          onRetry={() => {
            snapshotQuery.refetch();
            historyQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (!snapshotQuery.data || !historyQuery.data || !graph) {
    return <div className="mt-6" />;
  }

  if (!graph.nodes.length) {
    return (
      <div className="mt-6">
        <EmptyState
          title="No network nodes to render"
          description="The current region and threshold combination removed all nodes or edges."
        />
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-6">
      <NetworkSummary summary={graph.summary} currentDate={selectedDate} />

      <NetworkControls
        lookback={lookbackFromUrl}
        threshold={thresholdFromUrl}
        emphasis={emphasisFromUrl}
        viewMode={viewMode}
        onLookbackChange={(value) => updateParam("lookback", String(value))}
        onThresholdChange={(value) => updateParam("threshold", String(value))}
        onEmphasisChange={(value) => updateParam("metric", value)}
        onViewModeChange={(value) => setViewMode(value)}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.9fr)_360px]">
        <div className="space-y-6">
          <Panel className="overflow-hidden">
            <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Interpretive Risk Propagation View</p>
                <h2 className="mt-2 text-2xl font-semibold">Co-movement-derived systemic similarity network</h2>
              </div>
              <p className="max-w-lg text-sm text-muted">
                Edges represent co-movement-based propagation similarity, not disclosed bilateral exposure.
              </p>
            </div>

            <NetworkGraph
              nodes={graph.nodes}
              edges={graph.edges}
              selectedBankId={selectedBankId}
              onNodeClick={(bankId) => setSelectedBankId(bankId)}
              onNodeDoubleClick={(bankId) => {
                setSelectedBankId(bankId);
                setViewMode("ego");
              }}
            />
          </Panel>

          <TimelinePlayer
            dates={dates}
            selectedDate={selectedDate}
            playbackWindow={playbackWindow}
            isPlaying={isPlaying}
            onPlaybackWindowChange={setPlaybackWindow}
            onDateChange={(value) => updateParam("date", value)}
            onPlayingChange={setIsPlaying}
          />

          <Legend />
        </div>

        <BankDetailPanel bank={selectedBank} topBanks={topBanks} />
      </div>
    </div>
  );
}

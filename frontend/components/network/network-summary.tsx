import { Panel } from "@/components/shared/panel";
import { formatDelta } from "@/lib/format";
import type { NetworkSummary as NetworkSummaryType } from "@/lib/types";

export function NetworkSummary({ summary, currentDate }: { summary: NetworkSummaryType; currentDate: string }) {
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Network summary</p>
          <h3 className="mt-2 text-lg font-semibold">Interpretive propagation status</h3>
        </div>
        <p className="font-mono text-sm text-muted">{currentDate}</p>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Total Nodes" value={String(summary.totalNodes)} />
        <Metric label="Rendered Edges" value={String(summary.renderedEdges)} />
        <Metric label="Densest Region" value={summary.densestRegion} />
        <Metric label="Most Connected" value={summary.mostConnectedBank} />
        <Metric label="Stress Index" value={formatDelta(summary.networkStressIndex)} />
      </div>
      <p className="mt-4 text-sm text-muted">
        Cross-Region Tension: <span className="text-text">{formatDelta(summary.crossRegionTension)}</span>
      </p>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line/70 bg-panelAlt/50 p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}

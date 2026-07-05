import { Panel } from "@/components/shared/panel";
import { formatDelta } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { Region } from "@/lib/types";
import type { NetworkSummary as NetworkSummaryType } from "@/lib/types";

export function NetworkSummary({ summary, currentDate }: { summary: NetworkSummaryType; currentDate: string }) {
  const { t, regionLabel } = useI18n();

  return (
    <Panel>
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">{t.network.summary}</p>
          <h3 className="mt-2 text-lg font-semibold">{t.network.status}</h3>
        </div>
        <p className="font-mono text-sm text-muted">{currentDate}</p>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label={t.network.totalNodes} value={String(summary.totalNodes)} />
        <Metric label={t.network.renderedEdges} value={String(summary.renderedEdges)} />
        <Metric
          label={t.network.densestRegion}
          value={summary.densestRegion === "Mixed" ? t.network.mixed : regionLabel(summary.densestRegion as Region)}
        />
        <Metric label={t.network.mostConnected} value={summary.mostConnectedBank} />
        <Metric label={t.network.stressIndex} value={formatDelta(summary.networkStressIndex)} />
      </div>
      <p className="mt-4 text-sm text-muted">
        {t.network.crossRegionTension}: <span className="text-text">{formatDelta(summary.crossRegionTension)}</span>
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

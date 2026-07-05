import { Panel } from "@/components/shared/panel";
import { REGION_COLORS, REGION_OPTIONS } from "@/lib/constants";
import { useI18n } from "@/lib/i18n";

export function Legend() {
  const { t, regionLabel } = useI18n();

  return (
    <Panel>
      <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">{t.network.legend}</p>
      <div className="mt-4 space-y-4 text-sm text-muted">
        <p>{t.network.legendEdges}</p>
        <div className="space-y-2">
          {REGION_OPTIONS.map((region) => (
            <div key={region} className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: REGION_COLORS[region] }} />
              <span>{regionLabel(region)}</span>
            </div>
          ))}
        </div>
        <p>{t.network.legendNodes}</p>
      </div>
    </Panel>
  );
}

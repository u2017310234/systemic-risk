import { Panel } from "@/components/shared/panel";
import { REGION_COLORS, REGION_LABELS, REGION_OPTIONS } from "@/lib/constants";

export function Legend() {
  return (
    <Panel>
      <p className="font-mono text-xs uppercase tracking-[0.28em] text-muted">Legend</p>
      <div className="mt-4 space-y-4 text-sm text-muted">
        <p>Edges represent co-movement-based propagation similarity, not disclosed bilateral exposure.</p>
        <div className="space-y-2">
          {REGION_OPTIONS.map((region) => (
            <div key={region} className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: REGION_COLORS[region] }} />
              <span>{REGION_LABELS[region]}</span>
            </div>
          ))}
        </div>
        <p>Node size tracks SRISK. Outer intensity is driven by the magnitude of negative Delta CoVaR.</p>
      </div>
    </Panel>
  );
}

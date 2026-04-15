"use client";

import { EDGE_THRESHOLDS, EMPHASIS_LABELS, LOOKBACK_WINDOWS } from "@/lib/constants";
import type { MetricEmphasis, NetworkViewMode } from "@/lib/types";

type Props = {
  lookback: number;
  threshold: number;
  emphasis: MetricEmphasis;
  viewMode: NetworkViewMode;
  onLookbackChange: (value: number) => void;
  onThresholdChange: (value: number) => void;
  onEmphasisChange: (value: MetricEmphasis) => void;
  onViewModeChange: (value: NetworkViewMode) => void;
};

export function NetworkControls(props: Props) {
  const {
    lookback,
    threshold,
    emphasis,
    viewMode,
    onLookbackChange,
    onThresholdChange,
    onEmphasisChange,
    onViewModeChange
  } = props;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <ControlGroup title="Lookback">
        {LOOKBACK_WINDOWS.map((value) => (
          <PillButton
            key={value}
            active={lookback === value}
            onClick={() => onLookbackChange(value)}
            label={`${value}D`}
          />
        ))}
      </ControlGroup>

      <ControlGroup title="Edge Threshold">
        {EDGE_THRESHOLDS.map((value) => (
          <PillButton
            key={value}
            active={threshold === value}
            onClick={() => onThresholdChange(value)}
            label={value.toFixed(1)}
          />
        ))}
      </ControlGroup>

      <ControlGroup title="Metric Emphasis">
        {(["balanced", "srisk", "delta"] as MetricEmphasis[]).map((value) => (
          <PillButton
            key={value}
            active={emphasis === value}
            onClick={() => onEmphasisChange(value)}
            label={EMPHASIS_LABELS[value]}
          />
        ))}
      </ControlGroup>

      <ControlGroup title="View Mode">
        {([
          ["full", "Full Network"],
          ["ego", "Ego Network"],
          ["cluster", "Region Cluster"]
        ] as const).map(([value, label]) => (
          <PillButton
            key={value}
            active={viewMode === value}
            onClick={() => onViewModeChange(value)}
            label={label}
          />
        ))}
      </ControlGroup>
    </div>
  );
}

function ControlGroup({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[24px] border border-line/70 bg-panel/80 p-4">
      <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function PillButton({
  active,
  onClick,
  label
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-2 text-sm transition ${
        active ? "border-accent bg-accent/10 text-text" : "border-line bg-panelAlt/60 text-muted hover:border-accent/70 hover:text-text"
      }`}
    >
      {label}
    </button>
  );
}

import type { MetricEmphasis, Region } from "@/lib/types";

export const REGION_OPTIONS: Region[] = ["US", "CN", "GB", "EU", "JP"];

export const REGION_LABELS: Record<Region, string> = {
  US: "United States",
  CN: "China",
  GB: "United Kingdom",
  EU: "Europe",
  JP: "Japan"
};

export const REGION_COLORS: Record<Region, string> = {
  US: "#f4b860",
  CN: "#ff7a59",
  GB: "#d57cff",
  EU: "#4ab8d9",
  JP: "#8dd17e"
};

export const EMPHASIS_LABELS: Record<MetricEmphasis, string> = {
  balanced: "Balanced",
  srisk: "SRISK emphasis",
  delta: "Delta CoVaR emphasis"
};

export const LOOKBACK_WINDOWS = [30, 60, 90] as const;
export const PLAYBACK_WINDOWS = [30, 90, 180] as const;
export const EDGE_THRESHOLDS = [0.4, 0.6, 0.8] as const;

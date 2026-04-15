import { z } from "zod";

export const regionSchema = z.enum(["US", "CN", "GB", "EU", "JP"]);

export type Region = z.infer<typeof regionSchema>;

const finiteNumber = z.preprocess((value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}, z.number().optional());

export const bankMetricSchema = z.object({
  bank_id: z.string(),
  bank_name: z.string(),
  region: regionSchema,
  mes: z.number(),
  lrmes: z.number(),
  covar: z.number(),
  delta_covar: z.number(),
  srisk_usd_bn: z.number(),
  srisk_share_pct: z.number(),
  market_cap_usd_bn: z.number(),
  debt_usd_bn: z.number(),
  covar_beta: z.number().optional()
});

export const systemSnapshotSchema = z.object({
  date: z.string(),
  system_srisk_usd_bn: z.number(),
  banks: z.array(bankMetricSchema)
});

export const bankHistoryRowSchema = z.object({
  date: z.string(),
  mes: finiteNumber,
  lrmes: finiteNumber,
  covar: finiteNumber,
  delta_covar: finiteNumber,
  covar_beta: finiteNumber,
  srisk_usd_bn: finiteNumber,
  srisk_share_pct: finiteNumber,
  market_cap_usd_bn: finiteNumber,
  debt_usd_bn: finiteNumber
});

export type BankMetric = z.infer<typeof bankMetricSchema>;
export type SystemSnapshot = z.infer<typeof systemSnapshotSchema>;
export type BankHistoryRow = z.infer<typeof bankHistoryRowSchema>;

export type GraphNode = {
  id: string;
  label: string;
  region: Region;
  srisk: number;
  deltaCoVar: number;
  size: number;
  riskScore: number;
  x?: number;
  y?: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  weight: number;
  components: {
    sriskCorr: number;
    deltaCoVarCorr: number;
    sameRegion: number;
  };
};

export type NetworkSummary = {
  totalNodes: number;
  renderedEdges: number;
  densestRegion: Region | "Mixed";
  mostConnectedBank: string;
  crossRegionTension: number;
  networkStressIndex: number;
};

export type NetworkViewMode = "full" | "ego" | "cluster";
export type MetricEmphasis = "balanced" | "srisk" | "delta";

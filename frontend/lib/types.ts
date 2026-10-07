import { z } from "zod";

export const regionSchema = z.enum(["US", "CN", "GB", "EU", "JP", "CA"]);

export type Region = z.infer<typeof regionSchema>;

const finiteNumber = z.preprocess((value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}, z.number().optional());

const metric = z.number().finite().nullable();
export const bankMetricSchema = z.object({
  bank_id: z.string(), bank_name: z.string(), region: regionSchema,
  mes: metric, lrmes: metric, covar: metric, delta_covar: metric,
  srisk_usd_bn: metric, srisk_share_pct: metric, market_cap_usd_bn: metric,
  debt_usd_bn: metric, covar_beta: metric.optional(), beta_ols: metric.optional()
});
export const systemSnapshotSchema = z.object({
  dataset_kind: z.string().optional(), calibration_id: z.string().optional(),
  parameters: z.record(z.unknown()).optional(), generated_at: z.string().optional(),
  date: z.string(), methodology_version: z.literal("2.0-beta-scenario"),
  system_srisk_usd_bn: metric, covered_srisk_usd_bn: metric.optional(),
  coverage: z.object({ complete: z.boolean(), expected_count: z.number(), srisk_count: z.number(),
    eligible_complete: z.boolean().optional(), eligible_count: z.number().optional(),
    srisk_ids: z.array(z.string()), expected_ids: z.array(z.string()),
    missing: z.record(z.string()), universe_version: z.string()
  }).optional(),
  quality: z.object({status:z.string(), alerts:z.array(z.object({code:z.string(), severity:z.string(), bank_id:z.string().nullable().optional(), message:z.string()}))}).optional(),
  banks: z.array(bankMetricSchema)
});

export const bankHistoryRowSchema = z.object({
  methodology_version: z.literal("2.0-beta-scenario"),
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
  diagnostics?: Record<string, {observations:number; start:string | null; end:string | null; firstHalf:number | null; secondHalf:number | null; stableSign:boolean | null}>;
  components: {
    sriskCorr: number | null;
    deltaCoVarCorr: number | null;
    sameRegion: number;
  };
};

export type NetworkSummary = {
  totalNodes: number;
  renderedEdges: number;
  densestRegion: Region | "Mixed";
  mostConnectedBank: string;
  crossRegionTension: number;
  networkStressIndex: number | null;
  density: number;
};

export type NetworkViewMode = "full" | "ego" | "cluster";
export type MetricEmphasis = "balanced" | "srisk" | "delta";

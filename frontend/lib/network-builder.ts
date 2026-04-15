import { assignGraphLayout } from "@/lib/graph-layout";
import { buildNodeRiskScores } from "@/lib/risk-score";
import type {
  GraphEdge,
  GraphNode,
  MetricEmphasis,
  NetworkSummary,
  NetworkViewMode,
  SystemSnapshot
} from "@/lib/types";
import { average, clamp, diffSeries, normalizeCorrelation, pearsonCorrelation } from "@/lib/utils";

type BuildGraphOptions = {
  metricEmphasis?: MetricEmphasis;
  threshold?: number;
  viewMode?: NetworkViewMode;
  selectedBankId?: string | null;
};

export function buildInterpretiveGraph(
  snapshot: SystemSnapshot,
  history: SystemSnapshot[],
  options: BuildGraphOptions = {}
) {
  const {
    metricEmphasis = "balanced",
    threshold = 0.6,
    viewMode = "full",
    selectedBankId = null
  } = options;

  const nodeScores = buildNodeRiskScores(snapshot.banks);
  const nodes: GraphNode[] = snapshot.banks.map((bank) => ({
    id: bank.bank_id,
    label: bank.bank_name,
    region: bank.region,
    srisk: bank.srisk_usd_bn,
    deltaCoVar: bank.delta_covar,
    size: 18 + Math.sqrt(Math.max(bank.srisk_usd_bn, 0)) * 2.3,
    riskScore: nodeScores[bank.bank_id] ?? 0
  }));

  const weightFactors =
    metricEmphasis === "srisk"
      ? { srisk: 0.65, delta: 0.2, region: 0.15 }
      : metricEmphasis === "delta"
        ? { srisk: 0.2, delta: 0.65, region: 0.15 }
        : { srisk: 0.45, delta: 0.35, region: 0.2 };

  const rawEdges: GraphEdge[] = [];

  for (let sourceIndex = 0; sourceIndex < snapshot.banks.length; sourceIndex += 1) {
    for (let targetIndex = sourceIndex + 1; targetIndex < snapshot.banks.length; targetIndex += 1) {
      const sourceBank = snapshot.banks[sourceIndex];
      const targetBank = snapshot.banks[targetIndex];

      const sourceHistory = history
        .map((item) => item.banks.find((bank) => bank.bank_id === sourceBank.bank_id)?.srisk_usd_bn)
        .filter((value): value is number => typeof value === "number");
      const targetHistory = history
        .map((item) => item.banks.find((bank) => bank.bank_id === targetBank.bank_id)?.srisk_usd_bn)
        .filter((value): value is number => typeof value === "number");
      const sourceDeltaHistory = history
        .map((item) => item.banks.find((bank) => bank.bank_id === sourceBank.bank_id)?.delta_covar)
        .filter((value): value is number => typeof value === "number");
      const targetDeltaHistory = history
        .map((item) => item.banks.find((bank) => bank.bank_id === targetBank.bank_id)?.delta_covar)
        .filter((value): value is number => typeof value === "number");

      const sriskCorr = normalizeCorrelation(
        pearsonCorrelation(diffSeries(sourceHistory), diffSeries(targetHistory))
      );
      const deltaCoVarCorr = normalizeCorrelation(
        pearsonCorrelation(diffSeries(sourceDeltaHistory), diffSeries(targetDeltaHistory))
      );
      const sameRegion = sourceBank.region === targetBank.region ? 1 : 0;
      const weight =
        sriskCorr * weightFactors.srisk +
        deltaCoVarCorr * weightFactors.delta +
        sameRegion * weightFactors.region;

      rawEdges.push({
        source: sourceBank.bank_id,
        target: targetBank.bank_id,
        weight,
        components: {
          sriskCorr,
          deltaCoVarCorr,
          sameRegion
        }
      });
    }
  }

  const topEdges = retainTopEdges(rawEdges, threshold);
  const viewEdges =
    viewMode === "ego" && selectedBankId
      ? topEdges.filter(
          (edge) => edge.source === selectedBankId || edge.target === selectedBankId
        )
      : topEdges;

  const activeNodeIds =
    viewMode === "ego" && selectedBankId
      ? new Set([selectedBankId, ...viewEdges.flatMap((edge) => [edge.source, edge.target])])
      : new Set(nodes.map((node) => node.id));

  const viewNodes = assignGraphLayout(
    nodes.filter((node) => activeNodeIds.has(node.id)),
    viewMode === "cluster" ? "cluster" : "full"
  );

  return {
    nodes: viewNodes,
    edges: viewEdges.filter(
      (edge) => activeNodeIds.has(edge.source) && activeNodeIds.has(edge.target)
    ),
    summary: buildNetworkSummary(viewNodes, viewEdges)
  };
}

function retainTopEdges(edges: GraphEdge[], threshold: number) {
  const byNode = new Map<string, GraphEdge[]>();
  for (const edge of edges) {
    if (edge.weight < threshold) {
      continue;
    }
    for (const nodeId of [edge.source, edge.target]) {
      const current = byNode.get(nodeId) ?? [];
      current.push(edge);
      byNode.set(nodeId, current);
    }
  }

  const selected = new Set<GraphEdge>();
  for (const [, nodeEdges] of byNode) {
    nodeEdges
      .sort((left, right) => right.weight - left.weight)
      .slice(0, 5)
      .forEach((edge) => selected.add(edge));
  }

  return Array.from(selected);
}

function buildNetworkSummary(nodes: GraphNode[], edges: GraphEdge[]): NetworkSummary {
  const degreeMap = new Map<string, number>();
  nodes.forEach((node) => degreeMap.set(node.id, 0));
  edges.forEach((edge) => {
    degreeMap.set(edge.source, (degreeMap.get(edge.source) ?? 0) + 1);
    degreeMap.set(edge.target, (degreeMap.get(edge.target) ?? 0) + 1);
  });

  const mostConnectedBank =
    [...degreeMap.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? "N/A";
  const density = nodes.length > 1 ? edges.length / ((nodes.length * (nodes.length - 1)) / 2) : 0;
  const regions = Array.from(new Set(nodes.map((node) => node.region)));
  const regionStrengths = regions.map((region) => {
    const regionEdges = edges.filter((edge) => {
      const source = nodes.find((node) => node.id === edge.source);
      const target = nodes.find((node) => node.id === edge.target);
      return source?.region === region && target?.region === region;
    });
    return [region, average(regionEdges.map((edge) => edge.weight))] as const;
  });

  const densestRegion = regionStrengths.sort((left, right) => right[1] - left[1])[0]?.[0] ?? "Mixed";
  const crossRegionTension = edges
    .filter((edge) => {
      const source = nodes.find((node) => node.id === edge.source);
      const target = nodes.find((node) => node.id === edge.target);
      return source?.region !== target?.region;
    })
    .reduce((sum, edge) => sum + edge.weight, 0);

  const networkStressIndex = clamp(average(nodes.map((node) => node.riskScore)) * density, -10, 10);

  return {
    totalNodes: nodes.length,
    renderedEdges: edges.length,
    densestRegion,
    mostConnectedBank,
    crossRegionTension,
    networkStressIndex
  };
}

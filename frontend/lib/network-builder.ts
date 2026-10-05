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
import { average, diffSeries, pearsonCorrelation } from "@/lib/utils";

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
  const nodes: GraphNode[] = snapshot.banks.filter(bank => bank.srisk_usd_bn != null && bank.delta_covar != null).map((bank) => ({
    id: bank.bank_id,
    label: bank.bank_name,
    region: bank.region,
    srisk: bank.srisk_usd_bn!,
    deltaCoVar: bank.delta_covar!,
    size: 18 + Math.sqrt(Math.max(bank.srisk_usd_bn!, 0)) * 2.3,
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

      // Join on dates BEFORE differencing: both banks now use identical intervals.
      const paired = [...new Map(history.filter(item => item.date <= snapshot.date &&
        item.methodology_version === snapshot.methodology_version && item.calibration_id === snapshot.calibration_id).map(item => [item.date, item])).values()]
        .sort((a, b) => a.date.localeCompare(b.date));
      const correlation = (field: "srisk_usd_bn" | "delta_covar") => {
        const pairs = paired.map(item => [
          item.banks.find(bank => bank.bank_id === sourceBank.bank_id)?.[field],
          item.banks.find(bank => bank.bank_id === targetBank.bank_id)?.[field]
        ]).filter((pair): pair is [number, number] => pair.every(value => typeof value === "number" && Number.isFinite(value)));
        if (pairs.length < 11) return null;
        return pearsonCorrelation(diffSeries(pairs.map(pair => pair[0])), diffSeries(pairs.map(pair => pair[1])));
      };
      const sriskCorr = correlation("srisk_usd_bn");
      const deltaCoVarCorr = correlation("delta_covar");
      // Constant/missing series provide no evidence of an edge. Zero correlation
      // is zero strength, not 0.5. Region is metadata, not fabricated evidence.
      if (sriskCorr == null && deltaCoVarCorr == null) continue;
      const sameRegion = sourceBank.region === targetBank.region ? 1 : 0;
      const denominator = (sriskCorr == null ? 0 : weightFactors.srisk) +
        (deltaCoVarCorr == null ? 0 : weightFactors.delta);
      const weight = ((sriskCorr == null ? 0 : Math.max(0, sriskCorr) * weightFactors.srisk) +
        (deltaCoVarCorr == null ? 0 : Math.max(0, deltaCoVarCorr) * weightFactors.delta)) / denominator;
      if (weight <= 0) continue;

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

  const validIds = new Set(nodes.map(node => node.id));
  const topEdges = retainTopEdges(rawEdges.filter(edge => validIds.has(edge.source) && validIds.has(edge.target)), threshold);
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
    summary: buildNetworkSummary(viewNodes, viewEdges, snapshot, history)
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

function buildNetworkSummary(nodes: GraphNode[], edges: GraphEdge[], snapshot: SystemSnapshot, history: SystemSnapshot[]): NetworkSummary {
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

  // Historical percentile of the SAME current cohort's covered subtotal.
  // Relative cross-sectional z-scores remain node colors only.
  const ids = nodes.map(node => node.id).sort();
  const pastTotals = [...new Map(history.filter(item => item.date < snapshot.date &&
    item.methodology_version === snapshot.methodology_version && item.calibration_id === snapshot.calibration_id).map(item => [item.date, item])).values()]
    .flatMap(item => {
      const values = ids.map(id => item.banks.find(bank => bank.bank_id === id)?.srisk_usd_bn);
      return values.every(value => typeof value === "number" && Number.isFinite(value))
        ? [values.reduce<number>((sum, value) => sum + (value as number), 0)] : [];
    });
  const total = nodes.reduce((sum, node) => sum + node.srisk, 0);
  const networkStressIndex = ids.length && pastTotals.length >= 20
    ? 100 * pastTotals.reduce((count, value) => count + (value < total ? 1 : value === total ? 0.5 : 0), 0) / pastTotals.length : null;

  return {
    density,
    totalNodes: nodes.length,
    renderedEdges: edges.length,
    densestRegion,
    mostConnectedBank,
    crossRegionTension,
    networkStressIndex
  };
}

"use client";

import { useMemo } from "react";

import { EChartsClient } from "@/components/shared/echarts-client";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { REGION_COLORS } from "@/lib/constants";

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedBankId: string | null;
  onNodeClick: (bankId: string | null) => void;
  onNodeDoubleClick: (bankId: string) => void;
};

export function NetworkGraph({
  nodes,
  edges,
  selectedBankId,
  onNodeClick,
  onNodeDoubleClick
}: Props) {
  const option = useMemo(
    () => ({
      backgroundColor: "transparent",
      animationDurationUpdate: 700,
      tooltip: {
        backgroundColor: "#10263a",
        borderColor: "#1c3851",
        formatter: (params: { dataType: string; data: Record<string, unknown> }) => {
          if (params.dataType === "node") {
            return `${params.data.label}<br/>SRISK: ${Number(params.data.srisk).toFixed(1)} bn<br/>ΔCoVaR: ${Number(params.data.deltaCoVar).toFixed(4)}`;
          }
          const edgeData = params.data as unknown as { weight: number; components: GraphEdge["components"] };
          return `Edge weight: ${edgeData.weight.toFixed(3)}<br/>SRISK corr: ${edgeData.components.sriskCorr.toFixed(3)}<br/>ΔCoVaR corr: ${edgeData.components.deltaCoVarCorr.toFixed(3)}<br/>Same region: ${edgeData.components.sameRegion}`;
        }
      },
      series: [
        {
          type: "graph",
          layout: "none",
          roam: true,
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 2.4
            }
          },
          edgeSymbol: ["none", "none"],
          edgeLabel: {
            show: false
          },
          lineStyle: {
            color: "rgba(142,167,188,0.45)",
            width: 1.4,
            opacity: 0.65
          },
          label: {
            show: true,
            color: "#eff7ff",
            fontSize: 11,
            formatter: "{b}"
          },
          data: nodes.map((node) => ({
            ...node,
            name: node.id,
            value: node.srisk,
            symbolSize: node.size,
            x: (node.x ?? 50) * 10,
            y: (node.y ?? 50) * 7,
            itemStyle: {
              color: REGION_COLORS[node.region],
              borderColor: selectedBankId === node.id ? "#eff7ff" : "rgba(255,255,255,0.3)",
              borderWidth: 1 + Math.abs(Math.min(node.deltaCoVar, 0)) * 80,
              shadowBlur: selectedBankId === node.id ? 18 : 8,
              shadowColor: REGION_COLORS[node.region],
              opacity: selectedBankId && selectedBankId !== node.id ? 0.35 : 0.95
            }
          })),
          links: edges.map((edge) => ({
            ...edge,
            lineStyle: {
              color: "rgba(244,184,96,0.35)",
              width: Math.max(edge.weight * 4, 1.4),
              opacity: selectedBankId && ![edge.source, edge.target].includes(selectedBankId) ? 0.15 : 0.8
            }
          }))
        }
      ]
    }),
    [edges, nodes, selectedBankId]
  );

  return (
    <EChartsClient
      option={option}
      className="h-[780px] w-full"
      onEvents={{
        click: (params: unknown) => {
          const event = params as { dataType?: string; data?: { id?: string } };
          if (event.dataType === "node" && event.data?.id) {
            onNodeClick(event.data.id);
            return;
          }
          onNodeClick(null);
        },
        dblclick: (params: unknown) => {
          const event = params as { dataType?: string; data?: { id?: string } };
          if (event.dataType === "node" && event.data?.id) {
            onNodeDoubleClick(event.data.id);
          }
        }
      }}
    />
  );
}

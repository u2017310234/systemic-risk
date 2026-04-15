import type { GraphNode, Region } from "@/lib/types";
import { REGION_OPTIONS } from "@/lib/constants";

const regionAnchors: Record<Region, { x: number; y: number }> = {
  US: { x: 18, y: 36 },
  CN: { x: 82, y: 32 },
  GB: { x: 42, y: 24 },
  EU: { x: 50, y: 50 },
  JP: { x: 78, y: 62 }
};

export function assignGraphLayout(nodes: GraphNode[], mode: "full" | "cluster") {
  if (!nodes.length) {
    return nodes;
  }
  if (mode === "cluster") {
    const grouped = REGION_OPTIONS.flatMap((region) =>
      nodes.filter((node) => node.region === region)
    );
    return grouped.map((node, index) => {
      const anchor = regionAnchors[node.region];
      const regionNodes = grouped.filter((item) => item.region === node.region);
      const regionIndex = regionNodes.findIndex((item) => item.id === node.id);
      const angle = (Math.PI * 2 * regionIndex) / Math.max(regionNodes.length, 1);
      return {
        ...node,
        x: anchor.x + Math.cos(angle) * 8,
        y: anchor.y + Math.sin(angle) * 8
      };
    });
  }

  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / nodes.length;
    return {
      ...node,
      x: 50 + Math.cos(angle) * 26,
      y: 50 + Math.sin(angle) * 26
    };
  });
}

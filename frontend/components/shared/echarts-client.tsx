"use client";

import dynamic from "next/dynamic";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

export function EChartsClient({
  option,
  className,
  onEvents
}: {
  option: object;
  className?: string;
  onEvents?: Record<string, (params: unknown) => void>;
}) {
  return <ReactECharts option={option} className={className} notMerge lazyUpdate onEvents={onEvents} />;
}

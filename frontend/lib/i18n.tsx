"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { MetricEmphasis, Region } from "@/lib/types";

export type Language = "zh" | "en";

const STORAGE_KEY = "systemic-risk-language";

const dictionaries = {
  zh: {
    shell: {
      eyebrow: "系统性风险前端 V1",
      title: "29 家活跃 G-SIB 的系统性压力监测",
      description: "浏览 SRISK、MES、LRMES、CoVaR 和 Delta CoVaR 快照、排名及基于联动性的风险传播模式。",
      lastUpdated: "最后更新",
      dashboard: "仪表盘",
      network: "网络",
      globe: "全球地图",
      region: "地区",
      allRegions: "全部地区",
      date: "日期",
      language: "语言",
      dataPartner: "AutoFRM 数据伙伴",
      metadataErrorTitle: "应用元数据加载失败",
      metadataErrorDescription: "应用无法加载导航和日期回放所需的静态数据清单。"
    },
    common: {
      error: "错误",
      emptyState: "空状态",
      retry: "重试"
    },
    regions: {
      US: "美国",
      CN: "中国",
      GB: "英国",
      EU: "欧洲",
      JP: "日本"
    },
    emphasis: {
      balanced: "均衡",
      srisk: "偏重 SRISK",
      delta: "偏重 Delta CoVaR"
    },
    dashboard: {
      dataErrorTitle: "仪表盘数据加载失败",
      dataErrorDescription: "前端无法读取当前系统性风险快照。",
      emptyTitle: "当前筛选条件下没有银行",
      emptyDescription: "请尝试其他地区，或选择覆盖数据更完整的较晚日期。",
      systemWideSrisk: "全系统 SRISK",
      systemWideSriskHint: "系统性压力下的预期资本缺口",
      mostSystemicSrisk: "按 SRISK 排名最高",
      mostSystemicDelta: "按 Delta CoVaR 排名最高",
      lastUpdatedDate: "最后更新日期",
      banksInFilter: "家银行符合当前筛选",
      rankingTitle: "今日系统性排名",
      rankingDescription: "按当前 SRISK 排序的头部银行。点击银行可进入预留的详情页。",
      replayTitle: "系统压力回放",
      replayDescription: "当前筛选条件下，最近 30 个可用交易日的全系统 SRISK。",
      concentrationTitle: "地区集中度",
      concentrationDescription: "当前系统性风险负荷的地区分布。",
      methodology: "方法说明",
      metricGuide: "指标指南",
      openNetwork: "打开网络",
      sriskGuide: "衡量系统性危机中的预期资本缺口。",
      deltaGuide: "捕捉某家银行陷入压力时，整体系统压力恶化的程度。",
      mesGuide: "量化短期和较长期市场尾部风险暴露。",
      drillDown: "银行详情"
    },
    network: {
      dataErrorTitle: "网络数据加载失败",
      dataErrorDescription: "传播视图无法根据所选历史窗口计算图谱。",
      emptyTitle: "没有可渲染的网络节点",
      emptyDescription: "当前地区和阈值组合移除了所有节点或边。",
      summary: "网络摘要",
      status: "解释性传播状态",
      totalNodes: "节点总数",
      renderedEdges: "已渲染边",
      densestRegion: "最密集地区",
      mostConnected: "连接最多",
      stressIndex: "压力指数",
      crossRegionTension: "跨地区张力",
      mixed: "混合",
      lookback: "回看窗口",
      edgeThreshold: "边阈值",
      metricEmphasis: "指标权重",
      viewMode: "视图模式",
      fullNetwork: "完整网络",
      egoNetwork: "单点网络",
      regionCluster: "地区聚类",
      viewEyebrow: "解释性风险传播视图",
      viewTitle: "基于联动性的系统性相似网络",
      viewDescription: "边代表基于联动性的传播相似度，并非披露的双边敞口。",
      timeline: "时间轴",
      timelineDescription: "回放最近 30、90 或 180 个可用交易日。",
      play: "播放",
      pause: "暂停",
      step: "前进",
      legend: "图例",
      legendEdges: "边代表基于联动性的传播相似度，并非披露的双边敞口。",
      legendNodes: "节点大小对应 SRISK，外圈强度由负 Delta CoVaR 的绝对值驱动。",
      selectedBank: "已选银行",
      share: "占比",
      recentTrend: "最近 30 日 SRISK 趋势",
      openBank: "打开银行详情",
      clickNode: "点击节点以打开银行详情面板。",
      currentTop: "当前系统性风险最高银行",
      nodeTooltipSrisk: "SRISK",
      nodeTooltipDelta: "Delta CoVaR",
      edgeWeight: "边权重",
      sriskCorr: "SRISK 相关性",
      deltaCorr: "Delta CoVaR 相关性",
      sameRegion: "同地区"
    },
    globe: {
      dataErrorTitle: "全球地图数据加载失败",
      dataErrorDescription: "地理系统性视图无法加载所选快照或位置数据集。",
      emptyTitle: "全球地图上没有可用银行",
      emptyDescription: "所选地区当前没有已映射的地理点。",
      eyebrow: "地理系统性地图",
      title: "拖动地球查看系统性风险集中位置",
      description: "标记大小对应 SRISK。点击可见点可查看该银行及其最新系统性指标。",
      drag: "拖动：旋转地球",
      click: "点击点：打开详情",
      snapshot: "快照",
      topFootprint: "头部系统性足迹",
      selectedLocation: "已选位置"
    },
    bank: {
      pageErrorTitle: "银行页面加载失败",
      pageErrorDescription: "应用无法加载所选银行快照或历史数据。",
      notFoundTitle: "未找到银行",
      notFoundDescription: "当前数据集中缺少所请求的银行 ID。",
      historicalView: "历史视图",
      historicalDescription: "预留的单银行详情页，展示核心双指标趋势。",
      currentSnapshot: "当前快照",
      sriskShare: "SRISK 占比"
    },
    notFound: {
      label: "未找到",
      title: "请求的银行或页面不存在。",
      back: "返回仪表盘"
    }
  },
  en: {
    shell: {
      eyebrow: "Systemic Risk Frontend V1",
      title: "Interpretive systemic stress monitor for 29 active G-SIBs",
      description: "Browse SRISK, MES, LRMES, CoVaR and Delta CoVaR snapshots, rankings, and co-movement-based propagation patterns.",
      lastUpdated: "Last updated",
      dashboard: "Dashboard",
      network: "Network",
      globe: "Globe",
      region: "Region",
      allRegions: "All regions",
      date: "Date",
      language: "Language",
      dataPartner: "AutoFRM Data Partner",
      metadataErrorTitle: "App metadata failed to load",
      metadataErrorDescription: "The app could not load the static data manifest required for navigation and date playback."
    },
    common: {
      error: "Error",
      emptyState: "Empty state",
      retry: "Retry"
    },
    regions: {
      US: "United States",
      CN: "China",
      GB: "United Kingdom",
      EU: "Europe",
      JP: "Japan"
    },
    emphasis: {
      balanced: "Balanced",
      srisk: "SRISK emphasis",
      delta: "Delta CoVaR emphasis"
    },
    dashboard: {
      dataErrorTitle: "Dashboard data failed to load",
      dataErrorDescription: "The frontend could not read the current systemic risk snapshot.",
      emptyTitle: "No banks available for this filter",
      emptyDescription: "Try a different region or a later date with data coverage.",
      systemWideSrisk: "System-wide SRISK",
      systemWideSriskHint: "Expected capital shortfall under systemic stress",
      mostSystemicSrisk: "Most Systemic by SRISK",
      mostSystemicDelta: "Most Systemic by Delta CoVaR",
      lastUpdatedDate: "Last Updated Date",
      banksInFilter: "banks in current filter",
      rankingTitle: "Today's Systemic Ranking",
      rankingDescription: "Top banks by current SRISK. Node drill-down routes to the reserved bank detail page.",
      replayTitle: "System Stress Replay",
      replayDescription: "Last 30 available trading days for system-wide SRISK under the current filter.",
      concentrationTitle: "Regional Concentration",
      concentrationDescription: "Where the current systemic risk load is concentrated.",
      methodology: "Methodology",
      metricGuide: "Metric guide",
      openNetwork: "Open network",
      sriskGuide: "measures expected capital shortfall in a systemic crisis.",
      deltaGuide: "captures how much broader system stress worsens when a bank is distressed.",
      mesGuide: "quantify short-horizon and longer-horizon market tail exposure.",
      drillDown: "Bank drill-down"
    },
    network: {
      dataErrorTitle: "Network data failed to load",
      dataErrorDescription: "The propagation view could not compute the graph from the selected history window.",
      emptyTitle: "No network nodes to render",
      emptyDescription: "The current region and threshold combination removed all nodes or edges.",
      summary: "Network summary",
      status: "Interpretive propagation status",
      totalNodes: "Total Nodes",
      renderedEdges: "Rendered Edges",
      densestRegion: "Densest Region",
      mostConnected: "Most Connected",
      stressIndex: "Stress Index",
      crossRegionTension: "Cross-Region Tension",
      mixed: "Mixed",
      lookback: "Lookback",
      edgeThreshold: "Edge Threshold",
      metricEmphasis: "Metric Emphasis",
      viewMode: "View Mode",
      fullNetwork: "Full Network",
      egoNetwork: "Ego Network",
      regionCluster: "Region Cluster",
      viewEyebrow: "Interpretive Risk Propagation View",
      viewTitle: "Co-movement-derived systemic similarity network",
      viewDescription: "Edges represent co-movement-based propagation similarity, not disclosed bilateral exposure.",
      timeline: "Timeline",
      timelineDescription: "Replay the latest 30, 90 or 180 available trading days.",
      play: "Play",
      pause: "Pause",
      step: "Step",
      legend: "Legend",
      legendEdges: "Edges represent co-movement-based propagation similarity, not disclosed bilateral exposure.",
      legendNodes: "Node size tracks SRISK. Outer intensity is driven by the magnitude of negative Delta CoVaR.",
      selectedBank: "Selected Bank",
      share: "Share",
      recentTrend: "Recent 30-day SRISK trend",
      openBank: "Open bank drill-down",
      clickNode: "Click a node to open the bank detail panel.",
      currentTop: "Current Top Systemic Banks",
      nodeTooltipSrisk: "SRISK",
      nodeTooltipDelta: "Delta CoVaR",
      edgeWeight: "Edge weight",
      sriskCorr: "SRISK corr",
      deltaCorr: "Delta CoVaR corr",
      sameRegion: "Same region"
    },
    globe: {
      dataErrorTitle: "Globe data failed to load",
      dataErrorDescription: "The geographic systemic view could not load the selected snapshot or location dataset.",
      emptyTitle: "No banks available on the globe",
      emptyDescription: "The selected region currently has no mapped geographic points.",
      eyebrow: "Geographic Systemic Map",
      title: "Drag the globe to inspect where systemic concentration sits",
      description: "Marker size tracks SRISK magnitude. Click a visible point to inspect the bank and its latest systemic metrics.",
      drag: "Drag: rotate globe",
      click: "Click point: open details",
      snapshot: "Snapshot",
      topFootprint: "Top Systemic Footprint",
      selectedLocation: "Selected Location"
    },
    bank: {
      pageErrorTitle: "Bank page failed to load",
      pageErrorDescription: "The app could not load the selected bank snapshot or history.",
      notFoundTitle: "Bank not found",
      notFoundDescription: "The requested bank ID is missing from the current dataset.",
      historicalView: "Historical View",
      historicalDescription: "Reserved single-bank drill-down page with the core two-metric trend view.",
      currentSnapshot: "Current Snapshot",
      sriskShare: "SRISK Share"
    },
    notFound: {
      label: "Not found",
      title: "The requested bank or page does not exist.",
      back: "Back to dashboard"
    }
  }
} as const;

type Dictionary = (typeof dictionaries)[Language];

const I18nContext = createContext<{
  lang: Language;
  setLang: (language: Language) => void;
  t: Dictionary;
  regionLabel: (region: Region) => string;
  emphasisLabel: (emphasis: MetricEmphasis) => string;
} | null>(null);

function isLanguage(value: string | null): value is Language {
  return value === "zh" || value === "en";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const [lang, setLangState] = useState<Language>("zh");

  useEffect(() => {
    const queryLang = searchParams.get("lang");
    if (isLanguage(queryLang)) {
      setLangState(queryLang);
      window.localStorage.setItem(STORAGE_KEY, queryLang);
      return;
    }
    const storedLang = window.localStorage.getItem(STORAGE_KEY);
    if (isLanguage(storedLang)) {
      setLangState(storedLang);
    }
  }, [searchParams]);

  const value = useMemo(() => {
    const dictionary = dictionaries[lang];
    return {
      lang,
      setLang(language: Language) {
        setLangState(language);
        window.localStorage.setItem(STORAGE_KEY, language);
        const params = new URLSearchParams(searchParams.toString());
        params.set("lang", language);
        router.replace(`${pathname}?${params.toString()}`, { scroll: false });
      },
      t: dictionary,
      regionLabel(region: Region) {
        return dictionary.regions[region];
      },
      emphasisLabel(emphasis: MetricEmphasis) {
        return dictionary.emphasis[emphasis];
      }
    };
  }, [lang, pathname, router, searchParams]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}

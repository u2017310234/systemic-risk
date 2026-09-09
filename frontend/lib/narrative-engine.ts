import type { BankHistoryRow, BankMetric, Region, SystemSnapshot } from "@/lib/types";

export type NarrativeLanguage = "en" | "zh";
export type NarrativeSalience = "normal" | "notable" | "high";

export type NarrativeItem = {
  type: string;
  priority: number;
  salience: NarrativeSalience;
  text: string;
  asOfDate: string;
  data: Record<string, string | number | boolean | null>;
};

type BuildNarrativeArgs = {
  snapshot: SystemSnapshot;
  bankId: string;
  history: BankHistoryRow[];
  lang?: NarrativeLanguage;
};

const MIN_COMPLETE_BANK_COUNT = 28;
const LOOKBACK_TARGET_DAYS = 30;
const LOOKBACK_TOLERANCE_DAYS = 7;
const HISTORY_STALE_TOLERANCE_DAYS = 7;
const MIN_PERCENTILE_OBSERVATIONS = 60;
const FIVE_YEAR_MIN_COVERAGE_DAYS = Math.floor(365.25 * 4.75);

export function buildBankNarratives({
  snapshot,
  bankId,
  history,
  lang = "en"
}: BuildNarrativeArgs): NarrativeItem[] {
  const bank = snapshot.banks.find((item) => item.bank_id === bankId);
  if (!bank) return [];

  const items: NarrativeItem[] = [];
  const comparable = comparableBanks(snapshot.banks);
  const comparableId = canonicalComparableId(bankId, snapshot.banks);
  const regionComparable = comparable.filter((item) => item.region === bank.region);
  const snapshotIsComplete = snapshot.banks.length >= MIN_COMPLETE_BANK_COUNT;
  const snapshotDateLabel = formatDate(snapshot.date, lang);

  if (isSharedProxyBank(bankId)) {
    items.push({
      type: "shared_proxy_note",
      priority: 100,
      salience: "notable",
      asOfDate: snapshot.date,
      data: {
        bank_id: bankId,
        proxy_group: "GLE/BPCE",
        de_duplicated_for_ranking: true
      },
      text:
        lang === "zh"
          ? "本数据集中 Société Générale（GLE）与 Groupe BPCE（BPCE）使用相同的上市权益代理序列；横截面排名会将两者按一个可比观测处理。"
          : "Société Générale (GLE) and Groupe BPCE (BPCE) share the same listed-equity proxy series in this dataset; cross-sectional ranks treat the pair as one comparable observation."
    });
  }

  if (!snapshotIsComplete) {
    items.push({
      type: "coverage_warning",
      priority: 99,
      salience: "high",
      asOfDate: snapshot.date,
      data: {
        bank_count: snapshot.banks.length,
        minimum_complete_bank_count: MIN_COMPLETE_BANK_COUNT,
        rank_facts_suppressed: true
      },
      text:
        lang === "zh"
          ? `${snapshotDateLabel} 的快照仅覆盖 ${snapshot.banks.length} 家银行；为避免部分快照产生误导，横截面排名类描述已自动抑制。`
          : `The ${snapshotDateLabel} snapshot covers only ${snapshot.banks.length} banks; cross-sectional rank statements are suppressed to avoid misleading results from a partial snapshot.`
    });
  } else {
    const sriskGlobalRank = competitionRank(
      comparable,
      comparableId,
      (item) => item.srisk_usd_bn,
      "desc"
    );
    const sriskRegionRank = competitionRank(
      regionComparable,
      comparableId,
      (item) => item.srisk_usd_bn,
      "desc"
    );
    const deltaRegionRank = competitionRank(
      regionComparable,
      comparableId,
      (item) => item.delta_covar,
      "asc"
    );

    if (sriskGlobalRank !== null) {
      items.push({
        type: "srisk_global_rank",
        priority: sriskGlobalRank <= 5 ? 88 : 62,
        salience: sriskGlobalRank <= 5 ? "high" : sriskGlobalRank <= 10 ? "notable" : "normal",
        asOfDate: snapshot.date,
        data: {
          bank_id: bankId,
          metric: "srisk_usd_bn",
          rank: sriskGlobalRank,
          universe_size: comparable.length,
          universe: "covered_gsib_comparable_observations",
          proxy_deduplicated: true
        },
        text:
          lang === "zh"
            ? `截至 ${snapshotDateLabel}，${bank.bank_name} 按 SRISK 在可比覆盖样本中排名第 ${sriskGlobalRank}。`
            : `As of ${snapshotDateLabel}, ${bank.bank_name} ranks ${ordinal(sriskGlobalRank)} by SRISK among comparable covered G-SIB observations.`
      });
    }

    if (sriskRegionRank !== null) {
      const regionName = regionLabel(bank.region, lang);
      items.push({
        type: "srisk_region_rank",
        priority: sriskRegionRank <= 3 ? 82 : 54,
        salience: sriskRegionRank <= 3 ? "notable" : "normal",
        asOfDate: snapshot.date,
        data: {
          bank_id: bankId,
          metric: "srisk_usd_bn",
          rank: sriskRegionRank,
          universe_size: regionComparable.length,
          region: bank.region,
          proxy_deduplicated: true
        },
        text:
          lang === "zh"
            ? `截至 ${snapshotDateLabel}，${bank.bank_name} 的 SRISK 在${regionName}可比样本中排名第 ${sriskRegionRank}。`
            : `As of ${snapshotDateLabel}, ${bank.bank_name} ranks ${ordinal(sriskRegionRank)} by SRISK within the comparable ${regionName} sample.`
      });
    }

    if (sriskRegionRank !== null && deltaRegionRank !== null) {
      const gap = Math.abs(sriskRegionRank - deltaRegionRank);
      const divergenceThreshold = Math.max(3, Math.ceil(regionComparable.length * 0.3));
      if (gap >= divergenceThreshold) {
        const regionName = regionLabel(bank.region, lang);
        items.push({
          type: "cross_metric_region_rank_divergence",
          priority: gap >= divergenceThreshold + 2 ? 94 : 86,
          salience: gap >= divergenceThreshold + 2 ? "high" : "notable",
          asOfDate: snapshot.date,
          data: {
            bank_id: bankId,
            region: bank.region,
            srisk_region_rank: sriskRegionRank,
            delta_covar_region_rank: deltaRegionRank,
            rank_gap: gap,
            universe_size: regionComparable.length,
            proxy_deduplicated: true
          },
          text:
            lang === "zh"
              ? `截至 ${snapshotDateLabel}，${bank.bank_name} 在${regionName}样本中按 SRISK 排名第 ${sriskRegionRank}，但按 ΔCoVaR 排名第 ${deltaRegionRank}，两个系统性风险维度的区域排名存在明显差异。`
              : `As of ${snapshotDateLabel}, ${bank.bank_name} ranks ${ordinal(sriskRegionRank)} by SRISK but ${ordinal(deltaRegionRank)} by Delta CoVaR within the ${regionName} sample, a notable within-region rank divergence.`
        });
      }
    }
  }

  const usableHistory = [...history]
    .filter(
      (row): row is BankHistoryRow & { srisk_usd_bn: number } =>
        typeof row.srisk_usd_bn === "number" && row.date <= snapshot.date
    )
    .sort((a, b) => a.date.localeCompare(b.date));

  const endRow = usableHistory.at(-1);
  if (!endRow) return items.sort((a, b) => b.priority - a.priority);

  const historyLagDays = calendarDaysBetween(endRow.date, snapshot.date);
  if (historyLagDays > HISTORY_STALE_TOLERANCE_DAYS) {
    items.push({
      type: "history_stale_warning",
      priority: 98,
      salience: "high",
      asOfDate: snapshot.date,
      data: {
        bank_id: bankId,
        snapshot_date: snapshot.date,
        latest_history_date: endRow.date,
        lag_days: historyLagDays,
        trend_facts_suppressed: true
      },
      text:
        lang === "zh"
          ? `${bank.bank_name} 的银行级历史序列最新仅到 ${formatDate(endRow.date, lang)}，落后当前快照 ${historyLagDays} 天；趋势类描述已自动抑制。`
          : `${bank.bank_name}'s bank-level history ends on ${formatDate(endRow.date, lang)}, ${historyLagDays} days behind the current snapshot; trend statements are suppressed.`
    });
    return items.sort((a, b) => b.priority - a.priority);
  }

  const startRow = nearestLookbackRow(
    usableHistory,
    endRow.date,
    LOOKBACK_TARGET_DAYS,
    LOOKBACK_TOLERANCE_DAYS
  );
  if (startRow && startRow.srisk_usd_bn !== endRow.srisk_usd_bn) {
    const usdChange = endRow.srisk_usd_bn - startRow.srisk_usd_bn;
    const absUsdChange = Math.abs(usdChange);
    const windowDays = calendarDaysBetween(startRow.date, endRow.date);
    const startLabel = formatDate(startRow.date, lang);
    const endLabel = formatDate(endRow.date, lang);

    if (startRow.srisk_usd_bn > 0) {
      const changePct = (usdChange / startRow.srisk_usd_bn) * 100;
      const absChangePct = Math.abs(changePct);
      const salience =
        absChangePct >= 15 && absUsdChange >= 5
          ? "high"
          : absChangePct >= 8 && absUsdChange >= 2
            ? "notable"
            : "normal";
      items.push({
        type: "srisk_change_30d",
        priority: salience === "high" ? 92 : salience === "notable" ? 78 : 58,
        salience,
        asOfDate: endRow.date,
        data: {
          bank_id: bankId,
          metric: "srisk_usd_bn",
          start_date: startRow.date,
          end_date: endRow.date,
          window_days: windowDays,
          start_value_usd_bn: startRow.srisk_usd_bn,
          end_value_usd_bn: endRow.srisk_usd_bn,
          change_usd_bn: usdChange,
          change_pct: changePct
        },
        text:
          lang === "zh"
            ? `从 ${startLabel} 到 ${endLabel}，${bank.bank_name} 的 SRISK ${changePct >= 0 ? "上升" : "下降"}${absChangePct.toFixed(1)}%。`
            : `From ${startLabel} to ${endLabel}, ${bank.bank_name}'s SRISK ${changePct >= 0 ? "increased" : "decreased"} ${absChangePct.toFixed(1)}%.`
      });
    } else {
      const salience: NarrativeSalience = absUsdChange >= 5 ? "notable" : "normal";
      items.push({
        type: "srisk_change_30d_absolute",
        priority: salience === "notable" ? 74 : 56,
        salience,
        asOfDate: endRow.date,
        data: {
          bank_id: bankId,
          metric: "srisk_usd_bn",
          start_date: startRow.date,
          end_date: endRow.date,
          window_days: windowDays,
          start_value_usd_bn: startRow.srisk_usd_bn,
          end_value_usd_bn: endRow.srisk_usd_bn,
          change_usd_bn: usdChange,
          change_pct: null
        },
        text:
          lang === "zh"
            ? `从 ${startLabel} 到 ${endLabel}，${bank.bank_name} 的 SRISK 从 ${startRow.srisk_usd_bn.toFixed(1)} 十亿美元变为 ${endRow.srisk_usd_bn.toFixed(1)} 十亿美元；由于起始值为零，不计算百分比变化。`
            : `From ${startLabel} to ${endLabel}, ${bank.bank_name}'s SRISK moved from $${startRow.srisk_usd_bn.toFixed(1)}bn to $${endRow.srisk_usd_bn.toFixed(1)}bn; no percentage change is reported because the starting value was zero.`
      });
    }
  }

  if (usableHistory.length >= MIN_PERCENTILE_OBSERVATIONS) {
    const historyStart = usableHistory[0];
    const historySpanDays = calendarDaysBetween(historyStart.date, endRow.date);
    const current = endRow.srisk_usd_bn;
    const less = usableHistory.filter((row) => row.srisk_usd_bn < current).length;
    const equal = usableHistory.filter((row) => row.srisk_usd_bn === current).length;
    const percentile = Math.round(((less + 0.5 * equal) / usableHistory.length) * 100);
    const hasFiveYearCoverage = historySpanDays >= FIVE_YEAR_MIN_COVERAGE_DAYS;
    const historyStartLabel = formatDate(historyStart.date, lang);

    items.push({
      type: hasFiveYearCoverage ? "srisk_percentile_5y" : "srisk_percentile_available_history",
      priority: percentile >= 95 ? 90 : percentile >= 85 ? 76 : 50,
      salience: percentile >= 95 ? "high" : percentile >= 85 ? "notable" : "normal",
      asOfDate: endRow.date,
      data: {
        bank_id: bankId,
        metric: "srisk_usd_bn",
        percentile,
        observation_count: usableHistory.length,
        history_start_date: historyStart.date,
        history_end_date: endRow.date,
        history_span_days: historySpanDays,
        five_year_coverage: hasFiveYearCoverage
      },
      text: hasFiveYearCoverage
        ? lang === "zh"
          ? `${bank.bank_name} 当前 SRISK 约处于其近五年历史的第 ${percentile} 百分位。`
          : `${bank.bank_name}'s current SRISK is around the ${ordinal(percentile)} percentile of its five-year history.`
        : lang === "zh"
          ? `${bank.bank_name} 当前 SRISK 约处于自 ${historyStartLabel} 起可用历史的第 ${percentile} 百分位。`
          : `${bank.bank_name}'s current SRISK is around the ${ordinal(percentile)} percentile of the available history since ${historyStartLabel}.`
    });

    const observedMax = Math.max(...usableHistory.map((row) => row.srisk_usd_bn));
    if (current > 0 && current >= observedMax - 1e-9) {
      items.push({
        type: hasFiveYearCoverage ? "srisk_five_year_high" : "srisk_available_history_high",
        priority: 96,
        salience: "high",
        asOfDate: endRow.date,
        data: {
          bank_id: bankId,
          metric: "srisk_usd_bn",
          current_value_usd_bn: current,
          observed_max_usd_bn: observedMax,
          history_start_date: historyStart.date,
          history_end_date: endRow.date,
          five_year_coverage: hasFiveYearCoverage
        },
        text: hasFiveYearCoverage
          ? lang === "zh"
            ? `${bank.bank_name} 当前 SRISK 位于其近五年观测区间的最高水平。`
            : `${bank.bank_name}'s current SRISK is at the highest observed level in its five-year window.`
          : lang === "zh"
            ? `${bank.bank_name} 当前 SRISK 达到自 ${historyStartLabel} 起可用历史中的最高观测水平。`
            : `${bank.bank_name}'s current SRISK is at the highest observed level in the available history since ${historyStartLabel}.`
      });
    }
  }

  return items.sort((a, b) => b.priority - a.priority);
}

function comparableBanks(banks: BankMetric[]) {
  const hasGle = banks.some((bank) => bank.bank_id === "GLE");
  return banks.filter((bank) => bank.bank_id !== "BPCE" || !hasGle);
}

function canonicalComparableId(bankId: string, banks: BankMetric[]) {
  return bankId === "BPCE" && banks.some((bank) => bank.bank_id === "GLE") ? "GLE" : bankId;
}

function isSharedProxyBank(bankId: string) {
  return bankId === "GLE" || bankId === "BPCE";
}

function competitionRank(
  banks: BankMetric[],
  bankId: string,
  value: (bank: BankMetric) => number,
  direction: "asc" | "desc"
): number | null {
  const target = banks.find((bank) => bank.bank_id === bankId);
  if (!target) return null;
  const targetValue = value(target);
  const betterCount = banks.filter((bank) =>
    direction === "desc" ? value(bank) > targetValue : value(bank) < targetValue
  ).length;
  return betterCount + 1;
}

function nearestLookbackRow(
  rows: Array<BankHistoryRow & { srisk_usd_bn: number }>,
  endDate: string,
  targetDays: number,
  toleranceDays: number
) {
  const end = Date.parse(`${endDate}T00:00:00Z`);
  const target = end - targetDays * 86_400_000;
  const candidates = rows.filter((row) => Date.parse(`${row.date}T00:00:00Z`) < end);
  if (!candidates.length) return null;
  const nearest = candidates.reduce((best, row) => {
    const rowTime = Date.parse(`${row.date}T00:00:00Z`);
    const bestTime = Date.parse(`${best.date}T00:00:00Z`);
    return Math.abs(rowTime - target) < Math.abs(bestTime - target) ? row : best;
  });
  const distanceDays = Math.abs(Date.parse(`${nearest.date}T00:00:00Z`) - target) / 86_400_000;
  return distanceDays <= toleranceDays ? nearest : null;
}

function calendarDaysBetween(startDate: string, endDate: string) {
  return Math.max(
    0,
    Math.round(
      (Date.parse(`${endDate}T00:00:00Z`) - Date.parse(`${startDate}T00:00:00Z`)) / 86_400_000
    )
  );
}

function regionLabel(region: Region, lang: NarrativeLanguage) {
  const labels: Record<NarrativeLanguage, Record<Region, string>> = {
    en: {
      US: "United States",
      CN: "China",
      GB: "United Kingdom",
      EU: "Europe",
      JP: "Japan"
    },
    zh: {
      US: "美国",
      CN: "中国",
      GB: "英国",
      EU: "欧洲",
      JP: "日本"
    }
  };
  return labels[lang][region];
}

function formatDate(dateString: string, lang: NarrativeLanguage) {
  const date = new Date(`${dateString}T00:00:00Z`);
  if (lang === "zh") {
    return `${date.getUTCFullYear()}年${date.getUTCMonth() + 1}月${date.getUTCDate()}日`;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC"
  }).format(date);
}

function ordinal(n: number) {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

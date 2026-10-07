"use client";
import { Panel } from "@/components/shared/panel";
import type { BankMetric, SystemSnapshot } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
export function ScenarioPanel({bank,snapshot}:{bank:BankMetric;snapshot:SystemSnapshot}) {
  const {lang} = useI18n();
  const originalDrop = snapshot.parameters?.lrmes_market_drop;
  const beta = bank.beta_ols ?? (typeof originalDrop === "number" && originalDrop>0 && originalDrop<1 && bank.lrmes != null && bank.lrmes>0 && bank.lrmes<1 ? Math.log1p(-bank.lrmes)/Math.log1p(-originalDrop) : null);
  if (beta == null || !Number.isFinite(beta) || bank.market_cap_usd_bn == null || bank.debt_usd_bn == null) return null;
  const drops=[.2,.3,.4,.5,.6], ratios=[.04,.06,.08,.10];
  return <div className="mt-6"><Panel>
    <h2 className="text-xl font-semibold">{lang === "zh" ? "SRISK 情景敏感性（十亿美元）" : "SRISK scenario sensitivity (USD bn)"}</h2>
    <p className="my-3 text-sm text-muted">{lang === "zh" ? "固定市值与负债，改变市场跌幅和资本率。此范围不是置信区间。β 从原场景的 LRMES 反推时受舍入影响。" : "Equity and liabilities held fixed. This range is not a confidence interval. Beta inferred from LRMES is subject to rounding."}</p>
    <div className="overflow-auto"><table className="w-full text-right text-sm"><thead><tr><th>Market drop / k</th>{ratios.map(k=><th key={k}>{(k*100).toFixed(0)}%</th>)}</tr></thead><tbody>
    {drops.map(drop=><tr key={drop} className="border-t border-line"><td className="py-3">{drop*100}%</td>{ratios.map(k=>{
      const loss=Math.max(0,Math.min(1,-Math.expm1(Math.log1p(-drop)*beta)));
      const risk=Math.max(0,k*bank.debt_usd_bn!-(1-k)*bank.market_cap_usd_bn!*(1-loss));
      return <td key={k}>{risk.toFixed(2)}</td>;
    })}</tr>)}
    </tbody></table></div>
  </Panel></div>;
}

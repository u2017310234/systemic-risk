"use client";

import { useState } from "react";
import { Panel } from "@/components/shared/panel";

const endpoint = "https://systemic-risk.2017310234.workers.dev/mcp";
const command = `claude mcp add --transport http gsib-risk ${endpoint}`;
const config = JSON.stringify({ mcpServers: { "gsib-risk": { type: "http", url: endpoint } } }, null, 2);

function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return <button type="button" className="rounded-full border border-line px-3 py-1 text-xs hover:border-accent" onClick={async () => { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 1500); }}>{done ? "Copied" : "Copy"}</button>;
}

export function DataAccessView({ chinese = false }: { chinese?: boolean }) {
  const cursorConfig = btoa(JSON.stringify({ mcpServers: { "gsib-risk": { url: endpoint, type: "http" } } }));
  const vscodeConfig = encodeURIComponent(JSON.stringify({ name: "gsib-risk", serverUrl: endpoint }));
  return <div className="mt-6 space-y-6">
    <section className="rounded-[28px] border border-accent/40 bg-accent/5 p-6">
      <p className="font-mono text-xs uppercase tracking-[.28em] text-accent">Data & API</p>
      <h2 className="mt-3 text-3xl font-semibold">{chinese ? "让你的 AI 直接查询系统性风险数据" : "Connect your agent to the data"}</h2>
      <p className="mt-3 max-w-3xl text-sm text-muted">{chinese ? "推荐使用 MCP；它提供最新指标、历史序列、SRISK 与 ΔCoVaR 排名和方法说明。" : "MCP is the preferred interface for latest metrics, history, rankings, and methodology."}</p>
      <div className="mt-4 flex flex-wrap gap-2"><a className="rounded-full border border-line px-4 py-2 text-sm hover:border-accent" href={`cursor://anysphere.cursor-deeplink/mcp/install?name=gsib-risk&config=${cursorConfig}`}>Add to Cursor</a><a className="rounded-full border border-line px-4 py-2 text-sm hover:border-accent" href={`vscode:mcp/install?${vscodeConfig}`}>Install in VS Code</a></div>
      <p className="mt-3 text-xs text-muted">Claude: Settings → Connectors → Add custom connector → paste the endpoint URL.</p>
    </section>
    <Panel><div className="flex items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">MCP endpoint</h3><p className="mt-2 break-all font-mono text-sm text-cool">{endpoint}</p></div><CopyButton value={endpoint} /></div><div className="mt-4 rounded-xl bg-bg/70 p-4"><div className="flex justify-between gap-3"><code className="overflow-x-auto text-sm text-text">{command}</code><CopyButton value={command} /></div></div><pre className="mt-4 overflow-x-auto rounded-xl bg-bg/70 p-4 text-xs text-muted">{config}</pre><ul className="mt-4 grid gap-2 text-sm text-muted sm:grid-cols-2"><li>get_latest_metrics — current snapshot</li><li>get_historical — bank time series</li><li>get_srisk_ranking — capital shortfall rank</li><li>get_delta_covar_ranking — regional-risk rank</li><li>get_methodology — definitions and sources</li></ul></Panel>
    <Panel><h3 className="text-lg font-semibold">Raw public data</h3><div className="mt-4 grid gap-3 text-sm"><a href="/data/latest.json" className="text-cool hover:text-text">/data/latest.json — latest snapshot</a><a href="/data/manifest.json" className="text-cool hover:text-text">/data/manifest.json — dates and bank counts</a><code className="text-muted">/data/history/YYYY-MM-DD.json — daily snapshot</code><code className="text-muted">/data/banks/JPM.csv — per-bank CSV</code></div><pre className="mt-4 overflow-x-auto rounded-xl bg-bg/70 p-4 text-xs text-muted">curl {endpoint.replace("/mcp", "/data/latest.json")}</pre><p className="mt-4 text-sm text-muted">Check each history snapshot&apos;s <code>bank_count</code>. GLE / BPCE share proxy data; BK ends on 2026-07-02. <a className="text-cool" href="https://github.com/u2017310234/systemic-risk#readme">Schema & caveats</a> · <a className="text-cool" href="/status.json">Status</a></p></Panel>
  </div>;
}

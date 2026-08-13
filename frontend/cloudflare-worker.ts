/** Cloudflare entrypoint. Bind ASSETS and set MCP_ORIGIN (including /mcp). */
export interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  MCP_ORIGIN: string;
}
const SITE = "https://systemic-risk.2017310234.workers.dev";
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, If-None-Match" };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
function nextWeekday(date: string) {
  const value = new Date(`${date}T00:00:00Z`);
  do value.setUTCDate(value.getUTCDate() + 1); while (value.getUTCDay() === 0 || value.getUTCDay() === 6);
  return value.toISOString().slice(0, 10);
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/mcp") {
      const headers = new Headers(request.headers); headers.delete("host");
      // Preserve mcp-session-id and return the untouched stream for SSE.
      const upstream = await fetch(env.MCP_ORIGIN, { method: request.method, headers, body: request.body, redirect: "manual" });
      const out = new Headers(upstream.headers); out.set("Cache-Control", "no-store");
      return new Response(upstream.body, { status: upstream.status, headers: out });
    }
    if (url.pathname.startsWith("/api/")) return json({ error: "No REST API on this deployment", mcp: `${SITE}/mcp`, data: `${SITE}/data/latest.json`, docs: `${SITE}/llms.txt` }, 404);
    if (url.pathname === "/status.json") {
      const manifestResponse = await env.ASSETS.fetch(new Request(new URL("/data/manifest.json", url), request));
      const data: { lastUpdated?: string; cadence?: string; expected_next_update?: string } = manifestResponse.ok ? await manifestResponse.json() : {};
      let mcpOriginHealth = "unreachable";
      try { mcpOriginHealth = (await fetch(new URL("/health", env.MCP_ORIGIN))).ok ? "ok" : "unreachable"; } catch {}
      const expected = data.expected_next_update ?? (data.lastUpdated ? nextWeekday(data.lastUpdated) : null);
      return json({ latest_date: data.lastUpdated ?? null, generated_at: new Date().toISOString(), cadence: data.cadence ?? "weekdays, T+1", expected_next_update: expected, is_stale: Boolean(expected && new Date().toISOString().slice(0, 10) > expected), mcp_origin_health: mcpOriginHealth });
    }
    if (url.pathname.startsWith("/data/")) {
      if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
      const response = await env.ASSETS.fetch(request);
      if (!response.ok) return json({ error: "Data file not found", manifest: `${SITE}/data/manifest.json` }, 404);
      const out = new Headers(response.headers); Object.entries(cors).forEach(([key, value]) => out.set(key, value));
      out.set("Cache-Control", /\/(latest|manifest)\.json$/.test(url.pathname) ? "max-age=0, must-revalidate" : "public, max-age=3600");
      return new Response(response.body, { status: response.status, headers: out });
    }
    const response = await env.ASSETS.fetch(request); const out = new Headers(response.headers);
    out.append("Link", '</data/latest.json>; rel="alternate"; type="application/json", </llms.txt>; rel="llms-txt"');
    return new Response(response.body, { status: response.status, headers: out });
  }
};

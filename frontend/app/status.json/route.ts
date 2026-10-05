import { compareBackendHealth } from "@/lib/health";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function nextWeekday(date: string) {
  const value = new Date(`${date}T00:00:00Z`);
  do value.setUTCDate(value.getUTCDate() + 1); while (value.getUTCDay() === 0 || value.getUTCDay() === 6);
  return value.toISOString().slice(0, 10);
}

export async function GET() {
  const manifest = await fetch(new URL("/data/manifest.json", process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"), { cache: "no-store" })
    .then((response) => response.json())
    .catch(() => null);
  const latestDate = manifest?.lastUpdated ?? null;
  const today = new Date().toISOString().slice(0, 10);
  let mcpOriginHealth: string = "not_configured";
  if (process.env.MCP_ORIGIN_URL) {
    try {
      const response = await fetch(new URL("/health", process.env.MCP_ORIGIN_URL), { signal: AbortSignal.timeout(3000), cache: "no-store" });
      const body = response.ok ? await response.json() : {};
      mcpOriginHealth = compareBackendHealth(response.ok, body, manifest ?? {});
    } catch { mcpOriginHealth = "unreachable"; }
  }
  return NextResponse.json({
    latest_date: latestDate,
    generated_at: new Date().toISOString(),
    cadence: manifest?.cadence ?? "weekdays, T+1",
    expected_next_update: manifest?.expected_next_update ?? (latestDate ? nextWeekday(latestDate) : null),
    is_stale: !latestDate || today > nextWeekday(latestDate),
    mcp_origin_health: mcpOriginHealth
  });
}

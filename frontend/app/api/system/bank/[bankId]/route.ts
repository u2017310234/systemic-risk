import { NextResponse } from "next/server";

import { buildMiniTrend, getBankHistoryRange, getMethodologySummary } from "@/lib/data-adapter";

type RouteContext = {
  params: Promise<{
    bankId: string;
  }>;
};

export async function GET(request: Request, context: RouteContext) {
  try {
    const { searchParams } = new URL(request.url);
    const { bankId } = await context.params;
    const startDate = searchParams.get("startDate") ?? undefined;
    const endDate = searchParams.get("endDate") ?? undefined;
    const rows = await getBankHistoryRange(bankId, startDate, endDate);

    if (!rows.length) {
      return NextResponse.json({ error: "Bank not found" }, { status: 404 });
    }

    const methodology = searchParams.get("methodology") === "true" ? await getMethodologySummary() : undefined;
    return NextResponse.json({
      bankId: bankId.toUpperCase(),
      records: rows,
      miniTrend: buildMiniTrend(rows, "srisk_usd_bn", 30),
      methodology
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load bank history" },
      { status: 500 }
    );
  }
}

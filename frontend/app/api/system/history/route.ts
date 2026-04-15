import { NextResponse } from "next/server";

import { getSnapshotByDate, getSnapshotSeries } from "@/lib/data-adapter";
import { regionSchema } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get("date") ?? undefined;
    const lookback = Number(searchParams.get("lookback") ?? 30);
    const series = searchParams.get("series") === "true";
    const regionParam = searchParams.get("region");
    const region = regionParam ? regionSchema.parse(regionParam) : undefined;

    if (series) {
      const snapshots = await getSnapshotSeries(date, lookback, region);
      return NextResponse.json({ date, lookback, snapshots });
    }

    const snapshot = await getSnapshotByDate(date, region);
    return NextResponse.json(snapshot);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load snapshot" },
      { status: 500 }
    );
  }
}

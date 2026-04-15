import { NextResponse } from "next/server";

import { getLatestSnapshot } from "@/lib/data-adapter";
import { regionSchema } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const regionParam = searchParams.get("region");
    const region = regionParam ? regionSchema.parse(regionParam) : undefined;
    const snapshot = await getLatestSnapshot(region);
    return NextResponse.json(snapshot);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load latest snapshot" },
      { status: 500 }
    );
  }
}

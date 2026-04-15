import { NextResponse } from "next/server";

import { getAvailableDates } from "@/lib/data-adapter";

export async function GET() {
  try {
    const dates = await getAvailableDates();
    return NextResponse.json({ dates });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load dates" },
      { status: 500 }
    );
  }
}

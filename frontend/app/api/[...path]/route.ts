import { NextResponse } from "next/server";

const guide = {
  error: "No REST API on this deployment",
  mcp: "https://systemic-risk.2017310234.workers.dev/mcp",
  data: "https://systemic-risk.2017310234.workers.dev/data/latest.json",
  docs: "https://systemic-risk.2017310234.workers.dev/llms.txt"
};

export function GET() { return NextResponse.json(guide, { status: 404 }); }
export function POST() { return NextResponse.json(guide, { status: 404 }); }

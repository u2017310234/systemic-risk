import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest) {
  const origin = process.env.MCP_ORIGIN_URL;
  if (!origin) return Response.json({ error: "MCP proxy is not configured" }, { status: 503 });
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, origin).toString();
  const headers = new Headers(request.headers);
  headers.delete("host");
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    // Required for Node's streaming request body and preserves upstream SSE.
    // @ts-expect-error Next's fetch passes through the duplex option.
    duplex: "half",
    cache: "no-store"
  });
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set("Cache-Control", "no-store");
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;

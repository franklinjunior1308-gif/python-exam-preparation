import { type NextRequest } from "next/server";
import { API_URL, COOKIE_ORG, COOKIE_TOKEN } from "@/lib/config";

/**
 * Live updates (API-06): a streaming pass-through of the backend's Server-Sent Events.
 * The generic /bff proxy buffers whole bodies, which would hang on a stream, so this route is separate.
 * The token stays in the httpOnly cookie; the browser's EventSource cannot set headers, this route does.
 */
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest): Promise<Response> {
  const token = req.cookies.get(COOKIE_TOKEN)?.value;
  const org = req.cookies.get(COOKIE_ORG)?.value;
  if (!token || !org) return new Response("unauthorized", { status: 401 });

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/api/v1/events`, {
      headers: { authorization: `Bearer ${token}`, "x-organization-id": org, accept: "text/event-stream" },
      cache: "no-store",
      signal: req.signal,
    });
  } catch {
    return new Response("backend unreachable", { status: 503 });
  }
  if (!upstream.ok || !upstream.body) return new Response("stream unavailable", { status: upstream.status || 502 });

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-store, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    },
  });
}

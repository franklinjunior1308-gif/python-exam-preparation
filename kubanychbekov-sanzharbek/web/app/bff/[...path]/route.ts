import { type NextRequest, NextResponse } from "next/server";
import { API_URL, COOKIE_LANG, COOKIE_ORG, COOKIE_SECURE, COOKIE_TOKEN } from "@/lib/config";

/**
 * Backend-for-frontend proxy.
 *
 * - The access token lives in an httpOnly cookie, so page scripts can never read it.
 * - Every state-changing call must carry the custom `x-requested-with` header (CSRF guard).
 * - The selected organization is also a cookie and is forwarded as X-Organization-Id; the
 *   backend re-checks membership on every request, the cookie is never trusted by itself.
 */

type Ctx = { params: Promise<{ path: string[] }> };

const cookieOptions = { httpOnly: true, sameSite: "lax", path: "/", secure: COOKIE_SECURE } as const;

function json(status: number, body: unknown): NextResponse {
  return NextResponse.json(body, { status, headers: { "cache-control": "no-store" } });
}

async function handle(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const { path } = await ctx.params;
  const route = path.join("/");
  const isRead = req.method === "GET" || req.method === "HEAD";

  if (!isRead && req.headers.get("x-requested-with") !== "fixflow") {
    return json(403, { error: { code: "csrf_blocked", message: "Missing request header" } });
  }

  const token = req.cookies.get(COOKIE_TOKEN)?.value;
  const org = req.cookies.get(COOKIE_ORG)?.value;

  // UI language preference (not a secret, so not httpOnly).
  if (route === "set-lang" && req.method === "POST") {
    const { lang } = (await req.json()) as { lang?: string };
    if (lang !== "en" && lang !== "ru") {
      return json(422, { error: { code: "validation_error", message: "Unsupported language" } });
    }
    const res = json(200, { ok: true });
    res.cookies.set(COOKIE_LANG, lang, {
      sameSite: "lax",
      path: "/",
      secure: COOKIE_SECURE,
      maxAge: 60 * 60 * 24 * 365,
    });
    return res;
  }

  // Choose the working organization: validated against the user's real memberships.
  if (route === "select-org" && req.method === "POST") {
    const { organization_id } = (await req.json()) as { organization_id?: number };
    const me = await fetch(`${API_URL}/api/v1/me`, {
      headers: token ? { authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (!me.ok) return json(me.status, await safeJson(me));
    const data = (await me.json()) as { memberships: { organization_id: number }[] };
    if (!data.memberships.some((m) => m.organization_id === organization_id)) {
      return json(403, { error: { code: "not_a_member", message: "No access to this organization" } });
    }
    const res = json(200, { ok: true });
    res.cookies.set(COOKIE_ORG, String(organization_id), cookieOptions);
    return res;
  }

  const headers = new Headers({
    "content-type": req.headers.get("content-type") ?? "application/json",
  });
  if (token) headers.set("authorization", `Bearer ${token}`);
  if (org && route !== "auth/login") headers.set("x-organization-id", org);

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/api/v1/${route}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: isRead ? undefined : await req.arrayBuffer(),
      cache: "no-store",
    });
  } catch {
    return json(503, { error: { code: "network", message: "Backend unreachable" } });
  }

  if (route === "auth/login" && upstream.ok) {
    const data = (await upstream.json()) as { access_token: string; expires_at: string };
    const res = json(200, { ok: true });
    res.cookies.set(COOKIE_TOKEN, data.access_token, {
      ...cookieOptions,
      expires: new Date(data.expires_at),
    });
    res.cookies.delete(COOKIE_ORG);
    return res;
  }

  if (route === "auth/logout") {
    const res = new NextResponse(null, { status: 204, headers: { "cache-control": "no-store" } });
    res.cookies.delete(COOKIE_TOKEN);
    res.cookies.delete(COOKIE_ORG);
    return res;
  }

  // bytes, not text: attachments are binary images and must pass through unchanged
  const body = upstream.status === 204 ? null : await upstream.arrayBuffer();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });
}

async function safeJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return { error: { code: "generic", message: res.statusText } };
  }
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };

import { type NextRequest, NextResponse } from "next/server";
import { COOKIE_TOKEN } from "@/lib/config";

/** Cheap gate: no session cookie, no workspace pages. The backend still authorizes every call. */
export function proxy(request: NextRequest) {
  if (!request.cookies.get(COOKIE_TOKEN)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/app/:path*", "/select-org"] };

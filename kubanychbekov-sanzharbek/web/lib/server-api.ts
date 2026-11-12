import { cookies } from "next/headers";
import { API_URL, COOKIE_ORG, COOKIE_TOKEN } from "./config";

export type ServerResult<T> = { ok: boolean; status: number; data: T | null };

/** Call the backend from a server component using the session cookie. Never cached. */
export async function serverApi<T>(path: string): Promise<ServerResult<T>> {
  const jar = await cookies();
  const headers: Record<string, string> = {};
  const token = jar.get(COOKIE_TOKEN)?.value;
  const org = jar.get(COOKIE_ORG)?.value;
  if (token) headers.authorization = `Bearer ${token}`;
  if (org) headers["x-organization-id"] = org;

  try {
    const res = await fetch(`${API_URL}/api/v1${path}`, { headers, cache: "no-store" });
    const data = res.ok ? ((await res.json()) as T) : null;
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 503, data: null };
  }
}

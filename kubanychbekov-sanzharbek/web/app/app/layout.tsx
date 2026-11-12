import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { COOKIE_ORG } from "@/lib/config";
import { serverApi } from "@/lib/server-api";
import type { Me } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const jar = await cookies();
  const orgId = Number(jar.get(COOKIE_ORG)?.value);

  const result = await serverApi<Me>("/me");
  if (result.status === 401) redirect("/login?reason=expired");
  if (!result.data) throw new Error("Backend unavailable");

  const membership = result.data.memberships.find((m) => m.organization_id === orgId);
  if (!membership) redirect("/select-org");

  return (
    <Shell me={result.data} membership={membership}>
      {children}
    </Shell>
  );
}

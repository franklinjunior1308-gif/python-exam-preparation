import { redirect } from "next/navigation";
import { OrgPicker } from "@/components/OrgPicker";
import { getT } from "@/lib/i18n/server";
import { serverApi } from "@/lib/server-api";
import type { Me } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SelectOrgPage() {
  const result = await serverApi<Me>("/me");
  if (result.status === 401) redirect("/login?reason=expired");
  if (!result.data) throw new Error("Backend unavailable");
  const { t } = await getT();

  return (
    <main className="auth">
      <div className="card auth-card">
        <h1 style={{ fontSize: "1.5rem" }}>{t("org.title")}</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          {t("org.subtitle")}
        </p>
        <OrgPicker memberships={result.data.memberships} />
      </div>
    </main>
  );
}

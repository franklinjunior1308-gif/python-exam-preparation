import Link from "next/link";
import { LoginForm } from "@/components/LoginForm";
import { LogoMark } from "@/components/icons";
import { getT } from "@/lib/i18n/server";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const { reason } = await searchParams;
  const { t } = await getT();

  return (
    <main className="auth">
      <div className="card auth-card">
        <Link href="/" className="brand" aria-label="FixFlow" style={{ marginBottom: 18 }}>
          <LogoMark size={36} />
          <span>FixFlow</span>
        </Link>
        <h1 style={{ fontSize: "1.5rem" }}>{t("login.title")}</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          {t("login.subtitle")}
        </p>
        {reason === "expired" && (
          <div className="alert" role="status" style={{ marginTop: 14 }}>
            {t("login.expired")}
          </div>
        )}
        <LoginForm />
        <p style={{ marginTop: 18 }}>
          <Link href="/" className="muted">
            {t("login.back")}
          </Link>
        </p>
      </div>
    </main>
  );
}

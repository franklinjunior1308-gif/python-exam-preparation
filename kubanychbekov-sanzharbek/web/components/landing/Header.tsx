import Link from "next/link";
import { LangSwitch } from "@/components/LangSwitch";
import { LogoMark } from "@/components/icons";
import { getT } from "@/lib/i18n/server";

export async function Header() {
  const { t } = await getT();
  const nav = [
    { href: "#features", label: t("nav.features") },
    { href: "#roles", label: t("nav.roles") },
    { href: "#preview", label: t("nav.preview") },
  ];

  return (
    <header className="l-header">
      <div className="container l-header-row">
        <Link href="/" className="brand" aria-label="FixFlow">
          <LogoMark size={36} />
          <span>FixFlow</span>
        </Link>
        <nav aria-label="Main" className="l-nav">
          {nav.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="l-actions">
          <LangSwitch />
          <Link href="/login" className="btn btn-outline">
            {t("nav.login")}
          </Link>
          <Link href="/login" className="btn btn-primary l-try">
            {t("nav.try")}
          </Link>
        </div>
      </div>
    </header>
  );
}

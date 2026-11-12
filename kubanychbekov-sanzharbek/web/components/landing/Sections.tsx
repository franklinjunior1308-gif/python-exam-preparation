import Link from "next/link";
import {
  BoltIcon,
  CalendarIcon,
  ChartIcon,
  ClipboardIcon,
  HelmetIcon,
  LayersIcon,
  LogoMark,
  UserIcon,
  UsersIcon,
  WrenchIcon,
  CogIcon,
} from "@/components/icons";
import { getT } from "@/lib/i18n/server";
import type { TKey } from "@/lib/i18n";

export async function Strip() {
  const { t } = await getT();
  const items = [
    { icon: <BoltIcon size={30} />, label: t("landing.strip.1") },
    { icon: <UsersIcon size={30} />, label: t("landing.strip.2") },
    { icon: <LayersIcon size={30} />, label: t("landing.strip.3") },
    { icon: <ChartIcon size={30} />, label: t("landing.strip.4") },
  ];
  return (
    <section className="container" aria-label="FixFlow">
      <ul className="l-strip">
        {items.map((item) => (
          <li key={item.label}>
            <span className="l-strip-icon">{item.icon}</span>
            {item.label}
          </li>
        ))}
      </ul>
    </section>
  );
}

export async function PreviewAndFeatures() {
  const { t } = await getT();
  const features: { icon: React.ReactNode; title: TKey; text: TKey }[] = [
    { icon: <ClipboardIcon size={26} />, title: "landing.f.requests", text: "landing.f.requestsText" },
    { icon: <CalendarIcon size={26} />, title: "landing.f.dispatch", text: "landing.f.dispatchText" },
    { icon: <LayersIcon size={26} />, title: "landing.f.assets", text: "landing.f.assetsText" },
    { icon: <ChartIcon size={26} />, title: "landing.f.reports", text: "landing.f.reportsText" },
  ];
  const menu = [t("nav.dashboard"), t("nav.requests"), "Dispatch", "Assets", "Reports"];
  const stats = [
    { value: "24", label: t("stat.total") },
    { value: "18", label: t("stat.inProgress") },
    { value: "56", label: t("chart.completed") },
  ];
  const rows = [
    { id: "#4837", title: "HVAC", status: "IN_PROGRESS" as const },
    { id: "#4836", title: "Pump (B2)", status: "SCHEDULED" as const },
    { id: "#4835", title: "Electrical", status: "SUBMITTED" as const },
  ];

  return (
    <section className="container l-split">
      <div id="preview" className="l-preview-wrap">
        <div className="l-preview" aria-hidden="true">
          <aside>
            <div className="l-preview-brand">
              <LogoMark size={22} /> FixFlow
            </div>
            {menu.map((item, i) => (
              <div key={item} className={i === 0 ? "active" : undefined}>
                {item}
              </div>
            ))}
          </aside>
          <div className="l-preview-main">
            <strong>{t("nav.dashboard")}</strong>
            <div className="l-preview-stats">
              {stats.map((s) => (
                <div key={s.label}>
                  <b>{s.value}</b>
                  <small>{s.label}</small>
                </div>
              ))}
            </div>
            <div className="l-preview-card">
              {rows.map((r) => (
                <div key={r.id} className="l-preview-row">
                  <span>{r.id}</span>
                  <span>{r.title}</span>
                  <em className={`st-${r.status}`}>{t(`status.${r.status}`)}</em>
                </div>
              ))}
            </div>
          </div>
        </div>
        <p className="caption">{t("landing.previewCaption")}</p>
      </div>

      <div id="features">
        <h2 className="l-h2">
          {t("landing.featuresTitle")} <span className="accent">&#8203;</span>
        </h2>
        <ul className="l-features">
          {features.map((f) => (
            <li key={f.title}>
              <span className="l-feature-icon">{f.icon}</span>
              <div>
                <h3>{t(f.title)}</h3>
                <p>{t(f.text)}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export async function Roles() {
  const { t } = await getT();
  const roles = [
    { key: "customer", icon: <UserIcon size={28} />, text: t("landing.r.customer") },
    { key: "dispatcher", icon: <CalendarIcon size={28} />, text: t("landing.r.dispatcher") },
    { key: "admin", icon: <CogIcon size={28} />, text: t("landing.r.admin") },
    { key: "technician", icon: <HelmetIcon size={28} />, text: t("landing.r.technician") },
  ] as const;

  return (
    <section id="roles" className="container l-roles" aria-labelledby="roles-title">
      <h2 id="roles-title" className="l-h2">
        {t("landing.rolesTitle")}
      </h2>
      <ul className="l-role-grid">
        {roles.map((role) => (
          <li key={role.key}>
            <Link href="/login" className="l-role">
              <span className="l-feature-icon">{role.icon}</span>
              <h3>{t(`role.${role.key}`)}</h3>
              <p>{role.text}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export async function Footer() {
  const { t } = await getT();
  return (
    <footer className="l-footer">
      <div className="container l-footer-row">
        <Link href="/" className="brand" aria-label="FixFlow">
          <LogoMark size={28} />
          <span>FixFlow</span>
        </Link>
        <p>{t("landing.footer")}</p>
        <nav aria-label="Footer">
          <a href="#features">{t("nav.features")}</a>
          <a href="#roles">{t("nav.roles")}</a>
          <Link href="/login">{t("nav.login")}</Link>
        </nav>
      </div>
    </footer>
  );
}

// WrenchIcon is re-exported so the icon set stays referenced from one place.
export { WrenchIcon };

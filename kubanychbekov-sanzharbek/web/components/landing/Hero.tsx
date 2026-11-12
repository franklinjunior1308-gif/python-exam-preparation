import Link from "next/link";
import { ArrowIcon, CalendarIcon, CheckCircleIcon, CheckIcon, PlayIcon, WrenchIcon } from "@/components/icons";
import { getT } from "@/lib/i18n/server";

export async function Hero() {
  const { t } = await getT();
  const points = [t("landing.point1"), t("landing.point2"), t("landing.point3")];

  return (
    <section className="container l-hero" aria-labelledby="hero-title">
      <div className="l-hero-copy">
        <span className="l-badge">
          <WrenchIcon size={16} /> {t("landing.badge")}
        </span>
        <h1 id="hero-title">
          {t("landing.title")} <span className="accent">{t("landing.titleAccent")}</span>
        </h1>
        <p className="l-lead">{t("landing.lead")}</p>
        <div className="l-cta">
          <Link href="/login" className="btn btn-primary btn-lg">
            {t("landing.cta")} <ArrowIcon size={18} />
          </Link>
          <a href="#preview" className="btn btn-outline btn-lg">
            <PlayIcon size={16} /> {t("landing.demo")}
          </a>
        </div>
        <ul className="l-points">
          {points.map((point) => (
            <li key={point}>
              <CheckIcon size={18} /> {point}
            </li>
          ))}
        </ul>
      </div>

      <div className="l-hero-photo">
        {/* Marketing photo: used only in this hero block. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/technician.webp" alt="" width={345} height={426} />
        <div className="l-chip l-chip-a" aria-hidden="true">
          <CheckCircleIcon size={26} />
          <span>
            {t("landing.chip.done")}
            <b>{t("landing.chip.doneStatus")}</b>
          </span>
        </div>
        <div className="l-chip l-chip-b" aria-hidden="true">
          <CalendarIcon size={26} />
          <span>
            {t("landing.chip.next")}
            <b>{t("landing.chip.nextWhen")}</b>
          </span>
        </div>
      </div>
    </section>
  );
}

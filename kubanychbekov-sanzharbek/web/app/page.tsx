import { Header } from "@/components/landing/Header";
import { Hero } from "@/components/landing/Hero";
import { Footer, PreviewAndFeatures, Roles, Strip } from "@/components/landing/Sections";
import { getT } from "@/lib/i18n/server";
import "./landing.css";

export default async function HomePage() {
  const { t } = await getT();
  return (
    <>
      <a className="skip-link" href="#main">
        {t("common.skip")}
      </a>
      <Header />
      <main id="main">
        <Hero />
        <Strip />
        <PreviewAndFeatures />
        <Roles />
      </main>
      <Footer />
    </>
  );
}

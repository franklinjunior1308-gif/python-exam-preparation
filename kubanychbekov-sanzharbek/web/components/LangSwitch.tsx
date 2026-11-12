"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import type { Lang } from "@/lib/i18n";
import { useI18n } from "./Providers";

export function LangSwitch() {
  const { lang, t } = useI18n();
  const router = useRouter();

  async function choose(next: Lang) {
    // the server stores the choice in a cookie so server-rendered pages follow it too
    await api("set-lang", { method: "POST", body: { lang: next } });
    router.refresh();
  }

  return (
    <div className="lang" role="group" aria-label={t("common.language")}>
      {(["en", "ru"] as const).map((code) => (
        <button key={code} type="button" aria-pressed={lang === code} onClick={() => choose(code)}>
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

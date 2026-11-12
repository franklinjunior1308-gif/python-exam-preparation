import { cookies, headers } from "next/headers";
import { type Lang, pickLang, translate, type TKey } from "./index";

export async function getLang(): Promise<Lang> {
  const jar = await cookies();
  const hdrs = await headers();
  return pickLang(jar.get("lang")?.value, hdrs.get("accept-language"));
}

/** Translator for server components. */
export async function getT() {
  const lang = await getLang();
  return {
    lang,
    t: (key: TKey, params?: Record<string, string | number>) => translate(lang, key, params),
  };
}

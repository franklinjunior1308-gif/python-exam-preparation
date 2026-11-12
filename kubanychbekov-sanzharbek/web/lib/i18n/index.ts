import { type Dict, en, ru, type TKey } from "./dict";

export type Lang = "en" | "ru";
export type { TKey };

const DICTS: Record<Lang, Dict> = { en, ru };

export function isLang(value: string | undefined | null): value is Lang {
  return value === "en" || value === "ru";
}

/** Pick a language from the cookie, else from Accept-Language, else English. */
export function pickLang(cookie: string | undefined, acceptLanguage: string | null): Lang {
  if (isLang(cookie)) return cookie;
  return acceptLanguage?.toLowerCase().startsWith("ru") ? "ru" : "en";
}

export function translate(
  lang: Lang,
  key: TKey,
  params?: Record<string, string | number>,
): string {
  let text: string = DICTS[lang][key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

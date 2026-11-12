"use client";

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { en } from "@/lib/i18n/dict";
import { type Lang, translate, type TKey } from "@/lib/i18n";

type I18n = {
  lang: Lang;
  t: (key: TKey, params?: Record<string, string | number>) => string;
  /** Translate an error key that may not exist; falls back to the generic message. */
  tError: (error: unknown) => string;
};

const I18nContext = createContext<I18n | null>(null);

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <Providers>");
  return value;
}

export function Providers({ lang, children }: { lang: Lang; children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error) => {
            // expired or revoked session: back to the sign-in page, nothing stale stays visible
            if (error instanceof ApiError && error.status === 401) {
              // full reload on purpose: drops every cached query and in-memory state
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination
              window.location.assign("/login?reason=expired");
            }
          },
        }),
        defaultOptions: { queries: { staleTime: 10_000, retry: false, refetchOnWindowFocus: false } },
      }),
  );

  const i18n: I18n = {
    lang,
    t: (key, params) => translate(lang, key, params),
    tError: (error) => {
      const key = error instanceof ApiError ? `err.${error.code}` : "err.generic";
      const resolved = (key in en ? key : "err.generic") as TKey;
      const text = translate(lang, resolved);
      // an unexplained failure carries the request id so support can find it in the logs (SEC-08)
      return resolved === "err.generic" && error instanceof ApiError && error.requestId
        ? `${text} (ID: ${error.requestId})`
        : text;
    },
  };

  return (
    <I18nContext.Provider value={i18n}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </I18nContext.Provider>
  );
}

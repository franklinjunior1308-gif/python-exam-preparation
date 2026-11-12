import type { Lang } from "./i18n";
import type { RequestStatus } from "./types";

const LOCALES: Record<Lang, string> = { en: "en-GB", ru: "ru-RU" };

/** Stored in UTC, shown in the organization's IANA timezone (DATA-03). */
export function formatDateTime(iso: string, lang: Lang, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALES[lang], {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(iso));
}

/** Short label for a calendar day such as "2026-11-12". */
export function formatDay(day: string, lang: Lang): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, date ?? 1)));
}

export const STATUS_COLORS: Record<RequestStatus, string> = {
  SUBMITTED: "#3a86ff",
  TRIAGED: "#06d6ff",
  SCHEDULED: "#8b7bff",
  ACCEPTED: "#6c8cff",
  IN_PROGRESS: "#fbbf24",
  BLOCKED: "#fb923c",
  COMPLETED: "#34d399",
  CLOSED: "#94a3b8",
  CANCELED: "#fb7185",
  REOPENED: "#f472b6",
};

export const CATEGORY_COLORS = ["#3a86ff", "#8b7bff", "#34d399", "#fbbf24", "#06d6ff", "#f472b6"];

/** Whether the backend will insist on a reason; mirrors the rules to guide the form (UX only). */
export function needsReason(
  source: RequestStatus,
  target: RequestStatus,
  role: string,
): boolean {
  if (target === "BLOCKED" || target === "REOPENED") return true;
  if (source === "BLOCKED" && target === "IN_PROGRESS") return true;
  return role !== "customer" && (target === "CANCELED" || target === "CLOSED");
}

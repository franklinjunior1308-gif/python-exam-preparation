"use client";

import type { Priority, RequestStatus } from "@/lib/types";
import { useI18n } from "./Providers";

/** Status is shown as a dot plus its name, never as colour alone (WEB-06). */
export function StatusBadge({ status }: { status: RequestStatus }) {
  const { t } = useI18n();
  return <span className={`badge st-${status}`}>{t(`status.${status}`)}</span>;
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const { t } = useI18n();
  return <span className={`badge pr-${priority}`}>{t(`priority.${priority}`)}</span>;
}

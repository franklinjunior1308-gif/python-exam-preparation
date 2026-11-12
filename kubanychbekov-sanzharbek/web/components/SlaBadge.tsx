"use client";

import { formatDateTime } from "@/lib/format";
import { formatDuration } from "@/lib/money";
import type { Sla } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** SLA state as a dot plus words (never colour alone), with the working time left or overdue. */
export function SlaBadge({ sla, detailed = false }: { sla: Sla | null; detailed?: boolean }) {
  const { t, lang } = useI18n();
  const { membership } = useSession();
  if (!sla) return <span className="muted">-</span>;

  const time = formatDuration(sla.remaining_minutes, t("time.h"), t("time.min"));
  const amount = sla.remaining_minutes >= 0 ? t("sla.left", { time }) : t("sla.over", { time });

  return (
    <span className="sla">
      <span className={`badge sla-${sla.state}`}>{t(`sla.${sla.state}`)}</span>
      {!sla.finished && <small className="muted"> {amount}</small>}
      {detailed && (
        <>
          {sla.due_at && !sla.finished && (
            <small className="muted block">
              {t("sla.due", { when: formatDateTime(sla.due_at, lang, membership.timezone) })}
            </small>
          )}
          {sla.paused && <small className="block paused">{t("sla.paused")}</small>}
          {sla.finished && <small className="muted block">{t("sla.final")}</small>}
        </>
      )}
    </span>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatDuration } from "@/lib/money";
import type { Overdue } from "@/lib/types";
import { PriorityBadge, StatusBadge } from "./Badges";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** Queue of open requests past their SLA (SLA-06), most overdue first. */
export function OverduePage() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const staff = role === "dispatcher" || role === "admin";

  const queue = useQuery({
    queryKey: ["overdue", orgId],
    queryFn: () => api<Overdue[]>("sla/overdue"),
    enabled: staff,
  });

  if (!staff) return <div className="alert">{t("schedule.onlyStaff")}</div>;

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("overdue.title")}</h1>
          <p className="page-sub">{t("overdue.sub")}</p>
        </div>
      </div>

      <section className="card">
        {queue.isPending && <p className="muted">{t("common.loading")}</p>}
        {queue.isError && (
          <div className="alert alert-error" role="alert">
            {tError(queue.error)}{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => queue.refetch()}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {queue.data && queue.data.length === 0 && <p className="empty">{t("overdue.empty")}</p>}
        {queue.data && queue.data.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("req.col.id")}</th>
                  <th>{t("req.col.title")}</th>
                  <th>{t("req.col.priority")}</th>
                  <th>{t("req.col.status")}</th>
                  <th>{t("overdue.by")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {queue.data.map((item) => (
                  <tr key={item.request_id}>
                    <td>#{item.request_id}</td>
                    <td>
                      <Link href={`/app/requests/${item.request_id}`}>{item.title}</Link>
                    </td>
                    <td>
                      <PriorityBadge priority={item.priority} />
                    </td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td>
                      <strong>{formatDuration(item.overdue_minutes, t("time.h"), t("time.min"))}</strong>
                    </td>
                    <td>{item.escalated ? t("overdue.escalated") : t("overdue.notEscalated")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

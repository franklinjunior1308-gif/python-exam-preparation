"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { AuditPage as AuditPageData } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const PAGE = 25;

/** Administrator audit feed (ORG-05): who changed what, newest first, filterable by action prefix. */
export function AuditPage() {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const admin = role === "admin";
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");

  const feed = useQuery({
    queryKey: ["audit", orgId, offset, action],
    queryFn: () => api<AuditPageData>("audit", { query: { limit: PAGE, offset, action: action || undefined } }),
    enabled: admin,
  });

  if (!admin) return <div className="alert">{t("settings.onlyAdmin")}</div>;

  const total = feed.data?.total ?? 0;

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("audit.title")}</h1>
          <p className="page-sub">{t("audit.sub")}</p>
        </div>
      </div>

      <section className="card">
        <div className="field" style={{ maxWidth: 320 }}>
          <label htmlFor="audit-filter">{t("audit.filter")}</label>
          <select
            id="audit-filter"
            className="select"
            value={action}
            onChange={(e) => {
              setOffset(0);
              setAction(e.target.value);
            }}
          >
            <option value="">{t("common.all")}</option>
            {["request.", "assignment.", "estimate.", "inventory.", "settings.", "sla.", "plan.", "auth."].map((prefix) => (
              <option key={prefix} value={prefix}>
                {prefix}*
              </option>
            ))}
          </select>
        </div>
        {feed.isPending && <p className="muted">{t("common.loading")}</p>}
        {feed.isError && (
          <div className="alert alert-error" role="alert">
            {tError(feed.error)}{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => feed.refetch()}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {feed.data && feed.data.items.length === 0 && <p className="empty">{t("audit.empty")}</p>}
        {feed.data && feed.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("audit.when")}</th>
                  <th>{t("audit.who")}</th>
                  <th>{t("audit.action")}</th>
                  <th>{t("audit.object")}</th>
                  <th>{t("audit.details")}</th>
                </tr>
              </thead>
              <tbody>
                {feed.data.items.map((event) => (
                  <tr key={event.id}>
                    <td>{formatDateTime(event.created_at, lang, membership.timezone)}</td>
                    <td>{event.actor_name ?? t("audit.system")}</td>
                    <td>
                      <code>{event.action}</code>
                    </td>
                    <td>
                      {event.object_type} #{event.object_id}
                    </td>
                    <td>
                      <small className="muted">{summarize(event.before, event.after)}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="actions" style={{ marginTop: 12 }}>
          <button type="button" className="btn btn-outline btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            {t("audit.prev")}
          </button>
          <span className="muted">
            {total === 0 ? 0 : offset + 1}-{Math.min(offset + PAGE, total)} / {total}
          </span>
          <button type="button" className="btn btn-outline btn-sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            {t("audit.next")}
          </button>
        </div>
      </section>
    </>
  );
}

function summarize(before: Record<string, unknown> | null, after: Record<string, unknown> | null): string {
  const keys = new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]);
  const parts = [...keys].slice(0, 4).map((key) => {
    const from = before?.[key];
    const to = after?.[key];
    const show = (v: unknown) => (typeof v === "object" ? JSON.stringify(v) : String(v));
    return from !== undefined && to !== undefined ? `${key}: ${show(from)} → ${show(to)}` : `${key}: ${show(to ?? from)}`;
  });
  return parts.join("; ");
}

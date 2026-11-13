"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatDuration } from "@/lib/money";
import type { SlaReportData } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** SLA report for a period: share finished on time, average resolution, late per priority (WEB-04). */
export function SlaReport() {
  const { t, tError } = useI18n();
  const { orgId } = useSession();
  const [days, setDays] = useState(30);

  const report = useQuery({
    queryKey: ["sla-report", orgId, days],
    queryFn: () => api<SlaReportData>("reports/sla", { query: { days } }),
  });

  const data = report.data;
  const onTime = data && data.total > 0 ? Math.round((data.on_time / data.total) * 100) : null;

  return (
    <section className="card" style={{ marginTop: 14 }}>
      <div className="topbar" style={{ marginBottom: 8 }}>
        <h2 className="grow" style={{ margin: 0 }}>
          {t("slareport.title")}
        </h2>
        <label htmlFor="sla-days" className="muted">
          {t("slareport.period")}{" "}
        </label>
        <select id="sla-days" className="select" style={{ width: "auto" }} value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[7, 30, 90].map((d) => (
            <option key={d} value={d}>
              {t("slareport.days", { n: d })}
            </option>
          ))}
        </select>
      </div>
      {report.isPending && <p className="muted">{t("common.loading")}</p>}
      {report.isError && (
        <div className="alert alert-error" role="alert">
          {tError(report.error)}
        </div>
      )}
      {data && data.total === 0 && <p className="empty">{t("slareport.empty")}</p>}
      {data && data.total > 0 && (
        <>
          <div className="sla-totals">
            <div className="card sla-total">
              <span>{t("slareport.onTime")}</span>
              <strong>{onTime}%</strong>
            </div>
            <div className="card sla-total">
              <span>{t("slareport.finished")}</span>
              <strong>{data.total}</strong>
            </div>
            <div className="card sla-total">
              <span>{t("slareport.avg")}</span>
              <strong>{formatDuration(Math.round(data.avg_resolution_minutes ?? 0), t("time.h"), t("time.min"))}</strong>
            </div>
            <div className="card sla-total">
              <span>{t("slareport.escalated")}</span>
              <strong>{data.escalated}</strong>
            </div>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("req.col.priority")}</th>
                  <th>{t("slareport.finished")}</th>
                  <th>{t("slareport.late")}</th>
                </tr>
              </thead>
              <tbody>
                {data.by_priority.map((row) => (
                  <tr key={row.priority}>
                    <td>{t(`priority.${row.priority}`)}</td>
                    <td>{row.total}</td>
                    <td>{row.late}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

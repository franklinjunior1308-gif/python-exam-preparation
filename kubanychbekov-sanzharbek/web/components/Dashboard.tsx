"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";
import { api } from "@/lib/api-client";
import { CATEGORY_COLORS, formatDateTime, formatDay, STATUS_COLORS } from "@/lib/format";
import { type RequestPage, STATUSES, type Summary } from "@/lib/types";
import { PriorityBadge, StatusBadge } from "./Badges";
import { Donut, LineChart } from "./Charts";
import { CheckCircleIcon, ClipboardIcon, ClockIcon, PlusIcon, WrenchIcon } from "./icons";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

function StatCard({
  icon,
  value,
  label,
  color,
}: {
  icon: ReactNode;
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div className="card stat" style={{ ["--c" as string]: color }}>
      <span className="stat-icon">{icon}</span>
      <div>
        <b>{value}</b>
        <span>{label}</span>
      </div>
    </div>
  );
}

export function Dashboard() {
  const { t, tError } = useI18n();
  const { me, membership, orgId, role } = useSession();
  const enabled = role !== "technician";

  const summary = useQuery({
    queryKey: ["summary", orgId],
    queryFn: () => api<Summary>("reports/summary", { query: { days: 14 } }),
    enabled,
  });
  const recent = useQuery({
    queryKey: ["requests", orgId, "recent"],
    queryFn: () => api<RequestPage>("requests", { query: { page: 1, page_size: 6 } }),
    enabled,
  });

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("dash.greeting", { name: me.full_name.split(" ")[0] ?? me.full_name })}</h1>
          <p className="page-sub">
            {t(`dash.sub.${role}`)} · {membership.organization_name}
          </p>
        </div>
        {role === "customer" && (
          <Link href="/app/requests/new" className="btn btn-primary">
            <PlusIcon size={18} /> {t("req.new")}
          </Link>
        )}
      </div>

      {!enabled && <div className="alert">{t("dash.technician")}</div>}

      {enabled && (summary.isError || recent.isError) && (
        <div className="alert alert-error" role="alert">
          {tError(summary.error ?? recent.error)}{" "}
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => {
              void summary.refetch();
              void recent.refetch();
            }}
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {enabled && summary.isPending && <p className="muted">{t("common.loading")}</p>}

      {summary.data && (
        <SummarySection
          summary={summary.data}
          recent={recent.data}
          recentLoading={recent.isPending}
        />
      )}
    </>
  );
}

function SummarySection({
  summary,
  recent,
  recentLoading,
}: {
  summary: Summary;
  recent: RequestPage | undefined;
  recentLoading: boolean;
}) {
  const { t, lang } = useI18n();
  const { membership } = useSession();

  const labels = summary.daily.map((d) => formatDay(d.date, lang));
  const statusBars = STATUSES.map((s) => ({ status: s, count: summary.by_status[s] ?? 0 }));
  const maxCount = Math.max(1, ...statusBars.map((b) => b.count));
  const categorySlices = summary.by_category.map((c, i) => ({
    label: c.name,
    value: c.count,
    color: CATEGORY_COLORS[i % CATEGORY_COLORS.length] ?? "#3a86ff",
  }));

  return (
    <>
      <div className="stats">
        <StatCard icon={<ClipboardIcon />} value={summary.total} label={t("stat.total")} color="#3a86ff" />
        <StatCard icon={<ClockIcon />} value={summary.open} label={t("stat.open")} color="#06d6ff" />
        <StatCard icon={<WrenchIcon />} value={summary.in_progress} label={t("stat.inProgress")} color="#fbbf24" />
        <StatCard
          icon={<CheckCircleIcon />}
          value={summary.completed_in_period}
          label={t("stat.completed", { days: summary.period_days })}
          color="#34d399"
        />
      </div>

      <div className="grid-2">
        <section className="card" aria-labelledby="recent-title">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h2 id="recent-title">{t("dash.recent")}</h2>
            <Link href="/app/requests" className="accent">
              {t("dash.viewAll")}
            </Link>
          </div>
          {recentLoading && <p className="muted">{t("common.loading")}</p>}
          {recent && recent.items.length === 0 && <p className="empty">{t("req.empty")}</p>}
          {recent && recent.items.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("req.col.id")}</th>
                    <th>{t("req.col.title")}</th>
                    <th>{t("req.col.priority")}</th>
                    <th>{t("req.col.status")}</th>
                    <th>{t("req.col.created")}</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.items.map((r) => (
                    <tr key={r.id}>
                      <td>#{r.id}</td>
                      <td>
                        <Link href={`/app/requests/${r.id}`}>{r.title}</Link>
                      </td>
                      <td>
                        <PriorityBadge priority={r.priority} />
                      </td>
                      <td>
                        <StatusBadge status={r.status} />
                      </td>
                      <td>{formatDateTime(r.created_at, lang, membership.timezone)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card" aria-labelledby="status-title">
          <h2 id="status-title">{t("chart.byStatus")}</h2>
          <div className="bars">
            {statusBars.map((bar) => (
              <div key={bar.status} className="bar" style={{ ["--c" as string]: STATUS_COLORS[bar.status] }}>
                <span>{t(`status.${bar.status}`)}</span>
                <i style={{ width: `${(bar.count / maxCount) * 100}%` }} />
                <b>{bar.count}</b>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)" }}>
        <section className="card" aria-labelledby="dyn-title">
          <h2 id="dyn-title">{t("chart.dynamics")}</h2>
          <LineChart
            labels={labels}
            title={t("chart.dynamics")}
            description={t("chart.dynamicsDesc", { days: summary.period_days })}
            series={[
              { key: "created", label: t("chart.created"), color: "#3a86ff", values: summary.daily.map((d) => d.created) },
              { key: "completed", label: t("chart.completed"), color: "#34d399", values: summary.daily.map((d) => d.completed) },
            ]}
          />
        </section>

        <section className="card" aria-labelledby="cat-title">
          <h2 id="cat-title">{t("chart.byCategory")}</h2>
          <Donut slices={categorySlices} title={t("chart.byCategory")} />
        </section>
      </div>
    </>
  );
}

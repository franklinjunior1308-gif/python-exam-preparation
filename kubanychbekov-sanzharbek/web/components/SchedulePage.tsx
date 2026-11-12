"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api-client";
import { formatDay } from "@/lib/format";
import {
  addDays,
  formatClock,
  localParts,
  rangeIso,
  todayInZone,
  weekdayOf,
  weekStart,
  zonedInputToIso,
} from "@/lib/time";
import type { Assignment, AssignmentStatus, RequestPage, Schedule, Technician } from "@/lib/types";
import { CalendarIcon, ClockIcon, UsersIcon, WrenchIcon } from "./icons";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const ACTIVE: AssignmentStatus[] = ["SCHEDULED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"];
const DAY_START = 7 * 60; // the day timeline shows 07:00 - 20:00
const DAY_END = 20 * 60;
const COLORS: Record<AssignmentStatus, string> = {
  SCHEDULED: "#3a86ff",
  ACCEPTED: "#8b7bff",
  IN_PROGRESS: "#34d399",
  BLOCKED: "#fb923c",
  COMPLETED: "#94a3b8",
  CANCELED: "#fb7185",
  DECLINED: "#fb7185",
};
const LEGEND: AssignmentStatus[] = ["SCHEDULED", "ACCEPTED", "IN_PROGRESS", "BLOCKED", "COMPLETED"];

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function toMinutes(time: string): number {
  const [h = "0", m = "0"] = time.split(":");
  return Number(h) * 60 + Number(m);
}

export function SchedulePage() {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const tz = membership.timezone;
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const staff = role === "dispatcher" || role === "admin";

  const view = params.get("view") === "week" ? "week" : "day";
  const rawDate = params.get("date");
  const date = rawDate && DATE_PATTERN.test(rawDate) ? rawDate : todayInZone(tz);
  const first = view === "week" ? weekStart(date) : date;
  const days = view === "week" ? 7 : 1;
  const { from, to } = rangeIso(first, days, tz);
  const dayList = Array.from({ length: days }, (_, i) => addDays(first, i));

  function go(changes: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) next.set(key, value);
    router.replace(`${pathname}?${next}`);
  }

  const schedule = useQuery({
    queryKey: ["schedule", orgId, from, to],
    queryFn: () => api<Schedule>("schedule", { query: { from, to } }),
    enabled: staff,
  });
  const awaiting = useQuery({
    queryKey: ["requests", orgId, "awaiting"],
    queryFn: () => api<RequestPage>("requests", { query: { status: "TRIAGED", page_size: 1 } }),
    enabled: staff,
  });

  if (!staff) return <div className="alert">{t("schedule.onlyStaff")}</div>;

  const data = schedule.data;
  const active = data?.assignments.filter((a) => ACTIVE.includes(a.status)).length ?? 0;
  const usable = data?.technicians.filter((tech) => tech.is_active) ?? [];
  const averageLoad = usable.length
    ? Math.round(usable.reduce((sum, tech) => sum + tech.load_percent, 0) / usable.length)
    : 0;
  const absentIds = new Set(data?.absences.map((a) => a.technician_id));
  const awayCount = (data?.technicians.filter((tech) => !tech.is_active || absentIds.has(tech.id)).length) ?? 0;

  const heading =
    view === "week"
      ? `${formatDay(first, lang)} - ${formatDay(addDays(first, 6), lang)}`
      : formatDay(first, lang);

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("schedule.title")}</h1>
          <p className="page-sub">{t("schedule.sub")}</p>
        </div>
      </div>

      <div className="sched-controls">
        <div className="lang" role="group" aria-label={t("schedule.view")}>
          {(["day", "week"] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => go({ view: v, date })}>
              {t(`schedule.${v}`)}
            </button>
          ))}
        </div>
        <div className="actions">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => go({ date: addDays(date, -days) })}>
            {t("common.previous")}
          </button>
          <strong aria-live="polite" className="sched-range">
            {heading}
          </strong>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => go({ date: addDays(date, days) })}>
            {t("common.next")}
          </button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => go({ date: todayInZone(tz) })}>
            {t("schedule.today")}
          </button>
        </div>
      </div>

      <div className="stats">
        <Stat icon={<CalendarIcon />} value={active} label={t("schedule.stat.active")} color="#3a86ff" />
        <Stat icon={<ClockIcon />} value={awaiting.data?.total ?? 0} label={t("schedule.stat.awaiting")} color="#06d6ff" />
        <Stat icon={<WrenchIcon />} value={`${averageLoad}%`} label={t("schedule.stat.load")} color="#34d399" />
        <Stat icon={<UsersIcon />} value={awayCount} label={t("schedule.stat.away")} color="#fb923c" />
      </div>

      {schedule.isPending && <p className="muted">{t("common.loading")}</p>}
      {schedule.isError && (
        <div className="alert alert-error" role="alert">
          {tError(schedule.error)}{" "}
          <button type="button" className="btn btn-outline btn-sm" onClick={() => schedule.refetch()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && data.technicians.length === 0 && <p className="empty">{t("schedule.noTechnicians")}</p>}

      {data && data.technicians.length > 0 && (
        <section className="card sched" aria-label={t("schedule.title")}>
          {view === "day" ? (
            <DayGrid data={data} date={first} tz={tz} />
          ) : (
            <WeekGrid data={data} days={dayList} tz={tz} lang={lang} />
          )}
          {data.assignments.length === 0 && <p className="empty">{t("schedule.empty")}</p>}
        </section>
      )}

      <ul className="legend sched-legend" aria-label={t("schedule.legend")}>
        {LEGEND.map((status) => (
          <li key={status} style={{ ["--c" as string]: COLORS[status] }}>
            <i /> {t(`assignment.${status}`)}
          </li>
        ))}
        <li style={{ ["--c" as string]: "#fb923c" }}>
          <i /> {t("schedule.away")}
        </li>
      </ul>
    </>
  );
}

function Stat({ icon, value, label, color }: { icon: React.ReactNode; value: number | string; label: string; color: string }) {
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

function TechCell({ tech }: { tech: Technician }) {
  const { t } = useI18n();
  return (
    <div className="tech-cell">
      <span className="avatar" aria-hidden="true">
        {tech.full_name.slice(0, 1)}
      </span>
      <div>
        <strong>{tech.full_name}</strong>
        <div className="muted small">{tech.skills.join(" · ")}</div>
        <div className="load" aria-label={t("schedule.load", { n: tech.load_percent })}>
          <i style={{ width: `${tech.load_percent}%` }} />
          <span>{tech.is_active ? t("schedule.load", { n: tech.load_percent }) : t("schedule.inactive")}</span>
        </div>
      </div>
    </div>
  );
}

function chipLabel(a: Assignment, tz: string, t: ReturnType<typeof useI18n>["t"]): string {
  return `${formatClock(a.start_at, tz)}-${formatClock(a.end_at, tz)}, #${a.request_id} ${a.request_title}, ${t(`assignment.${a.status}`)}`;
}

function DayGrid({ data, date, tz }: { data: Schedule; date: string; tz: string }) {
  const { t } = useI18n();
  const hours = Array.from({ length: (DAY_END - DAY_START) / 60 + 1 }, (_, i) => DAY_START / 60 + i);
  const span = DAY_END - DAY_START;
  const dayFrom = new Date(zonedInputToIso(`${date}T00:00`, tz)).getTime();
  const dayTo = dayFrom + 24 * 3600 * 1000;
  const weekday = weekdayOf(date);

  return (
    <div className="sched-day">
      <div className="sched-head">
        <div className="sched-label">{t("schedule.technicians", { n: data.technicians.length })}</div>
        <div className="sched-hours" aria-hidden="true">
          {hours.map((h) => (
            <span key={h} style={{ left: `${((h * 60 - DAY_START) / span) * 100}%` }}>
              {String(h).padStart(2, "0")}:00
            </span>
          ))}
        </div>
      </div>

      {data.technicians.map((tech) => {
        const shifts = tech.availability.filter((a) => a.weekday === weekday);
        const mine = data.assignments.filter((a) => a.technician_id === tech.id && localParts(a.start_at, tz).date === date);
        const away = data.absences.filter(
          (a) => a.technician_id === tech.id && new Date(a.start_at).getTime() < dayTo && new Date(a.end_at).getTime() > dayFrom,
        );
        return (
          <div className="sched-row" key={tech.id}>
            <TechCell tech={tech} />
            <div className="sched-track">
              {shifts.map((s) => (
                <i
                  key={s.start_time}
                  className="shift"
                  style={{
                    left: `${((toMinutes(s.start_time) - DAY_START) / span) * 100}%`,
                    width: `${((toMinutes(s.end_time) - toMinutes(s.start_time)) / span) * 100}%`,
                  }}
                />
              ))}
              {shifts.length === 0 && <span className="off">{t("schedule.offShift")}</span>}
              {away.length > 0 && <span className="away-tag">{t("schedule.away")}</span>}
              {mine.map((a) => {
                const s = localParts(a.start_at, tz).minutes;
                const e = localParts(a.end_at, tz).minutes || 24 * 60;
                const left = Math.max(0, ((s - DAY_START) / span) * 100);
                const width = Math.min(100 - left, ((e - Math.max(s, DAY_START)) / span) * 100);
                return (
                  <Link
                    key={a.id}
                    href={`/app/requests/${a.request_id}`}
                    className="chip"
                    style={{ left: `${left}%`, width: `${width}%`, ["--c" as string]: COLORS[a.status] }}
                    aria-label={chipLabel(a, tz, t)}
                    title={chipLabel(a, tz, t)}
                  >
                    <b>#{a.request_id}</b> {a.request_title}
                    <small>
                      {formatClock(a.start_at, tz)}-{formatClock(a.end_at, tz)} · {t(`assignment.${a.status}`)}
                    </small>
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function WeekGrid({ data, days, tz, lang }: { data: Schedule; days: string[]; tz: string; lang: "en" | "ru" }) {
  const { t } = useI18n();
  const today = todayInZone(tz);

  return (
    <div className="table-wrap">
      <table className="week-table">
        <thead>
          <tr>
            <th>{t("schedule.technicians", { n: data.technicians.length })}</th>
            {days.map((d) => (
              <th key={d} className={d === today ? "today" : undefined}>
                {new Intl.DateTimeFormat(lang === "ru" ? "ru-RU" : "en-GB", { weekday: "short", timeZone: "UTC" }).format(
                  new Date(`${d}T00:00:00Z`),
                )}
                <br />
                {formatDay(d, lang)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.technicians.map((tech) => (
            <tr key={tech.id}>
              <td>
                <TechCell tech={tech} />
              </td>
              {days.map((d) => {
                const dayFrom = new Date(zonedInputToIso(`${d}T00:00`, tz)).getTime();
                const away = data.absences.some(
                  (a) => a.technician_id === tech.id && new Date(a.start_at).getTime() < dayFrom + 86400000 && new Date(a.end_at).getTime() > dayFrom,
                );
                const mine = data.assignments.filter((a) => a.technician_id === tech.id && localParts(a.start_at, tz).date === d);
                const off = !tech.availability.some((a) => a.weekday === weekdayOf(d));
                return (
                  <td key={d} className={d === today ? "today" : undefined}>
                    {away && <span className="away-tag">{t("schedule.away")}</span>}
                    {!away && off && <span className="off">{t("schedule.offShift")}</span>}
                    {mine.map((a) => (
                      <Link
                        key={a.id}
                        href={`/app/requests/${a.request_id}`}
                        className="chip static"
                        style={{ ["--c" as string]: COLORS[a.status] }}
                        aria-label={chipLabel(a, tz, t)}
                        title={chipLabel(a, tz, t)}
                      >
                        <b>
                          {formatClock(a.start_at, tz)}-{formatClock(a.end_at, tz)}
                        </b>
                        #{a.request_id} {a.request_title}
                        <small>{t(`assignment.${a.status}`)}</small>
                      </Link>
                    ))}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

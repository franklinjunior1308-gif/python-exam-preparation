"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import type { WorkingHours } from "@/lib/types";
import { useI18n } from "./Providers";
import { OrganizationSettings } from "./OrganizationSettings";
import { useSession } from "./Shell";

type Day = { open: boolean; start: string; end: string };
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const;
const WEEKDAY_KEYS = [
  "weekday.0",
  "weekday.1",
  "weekday.2",
  "weekday.3",
  "weekday.4",
  "weekday.5",
  "weekday.6",
] as const;

/** Admin settings: working hours per weekday and holidays (the SLA clock only runs in working time). */
export function SettingsPage() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const queryClient = useQueryClient();
  const admin = role === "admin";
  const [edited, setEdited] = useState<Day[] | null>(null);
  const [holiday, setHoliday] = useState({ day: "", name: "" });
  const [saved, setSaved] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const hours = useQuery({
    queryKey: ["working-hours", orgId],
    queryFn: () => api<WorkingHours>("settings/working-hours"),
    enabled: admin,
  });

  const serverDays: Day[] = hours.data
    ? WEEKDAYS.map((weekday) => {
        const interval = hours.data.intervals.find((i) => i.weekday === weekday);
        return interval
          ? { open: true, start: interval.start_time.slice(0, 5), end: interval.end_time.slice(0, 5) }
          : { open: false, start: "09:00", end: "18:00" };
      })
    : [];
  const days = edited ?? serverDays;

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["working-hours", orgId] });
  const afterChange = async () => {
    await refresh();
    // SLA states depend on working time: refresh everything that shows them
    await Promise.all(["requests", "request", "overdue", "summary"].map((key) => queryClient.invalidateQueries({ queryKey: [key, orgId] })));
  };

  const save = useMutation({
    mutationFn: (intervals: { weekday: number; start_time: string; end_time: string }[]) =>
      api<WorkingHours>("settings/working-hours", { method: "PUT", body: { intervals } }),
    onSuccess: async () => {
      setSaved(true);
      setEdited(null);
      await afterChange();
    },
  });
  const addHoliday = useMutation({
    mutationFn: (body: { day: string; name: string }) => api<WorkingHours>("settings/holidays", { method: "POST", body }),
    onSuccess: async () => {
      setHoliday({ day: "", name: "" });
      await afterChange();
    },
  });
  const removeHoliday = useMutation({
    mutationFn: (id: number) => api<WorkingHours>(`settings/holidays/${id}`, { method: "DELETE" }),
    onSuccess: afterChange,
  });

  if (!admin) return <div className="alert">{t("settings.onlyAdmin")}</div>;

  function update(index: number, patch: Partial<Day>) {
    setSaved(false);
    setEdited(days.map((d, i) => (i === index ? { ...d, ...patch } : d)));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (days.some((d) => d.open && d.end <= d.start)) {
      setFormError(t("settings.invalidHours"));
      return;
    }
    setFormError(null);
    save.mutate(
      days.flatMap((d, weekday) => (d.open ? [{ weekday, start_time: d.start, end_time: d.end }] : [])),
    );
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("settings.title")}</h1>
          <p className="page-sub">{t("settings.sub")}</p>
        </div>
      </div>

      <div className="detail-grid">
        <form className="card" onSubmit={submit}>
          <h2>{t("settings.hours")}</h2>
          {hours.isPending && <p className="muted">{t("common.loading")}</p>}
          {hours.isError && (
            <div className="alert alert-error" role="alert">
              {tError(hours.error)}
            </div>
          )}
          {(formError || save.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(save.error)}
            </div>
          )}
          {saved && (
            <div className="alert" role="status">
              {t("settings.saved")}
            </div>
          )}
          {hours.data?.is_default && <p className="muted">{t("settings.default")}</p>}
          {days.map((day, index) => (
            <div className="hours-row" key={index}>
              <label className="check">
                <input type="checkbox" checked={day.open} onChange={(e) => update(index, { open: e.target.checked })} />{" "}
                {t(WEEKDAY_KEYS[index] ?? "weekday.0")}
              </label>
              <input
                className="input"
                type="time"
                aria-label={`${t(WEEKDAY_KEYS[index] ?? "weekday.0")} ${t("settings.from")}`}
                disabled={!day.open}
                value={day.start}
                onChange={(e) => update(index, { start: e.target.value })}
              />
              <input
                className="input"
                type="time"
                aria-label={`${t(WEEKDAY_KEYS[index] ?? "weekday.0")} ${t("settings.to")}`}
                disabled={!day.open}
                value={day.end}
                onChange={(e) => update(index, { end: e.target.value })}
              />
            </div>
          ))}
          <button type="submit" className="btn btn-primary" disabled={save.isPending || days.length === 0}>
            {t("common.confirm")}
          </button>
          {hours.data && (
            <p className="muted">
              {t("settings.timezone")}: {hours.data.timezone}
            </p>
          )}
        </form>

        {admin && <OrganizationSettings />}
        <section className="card">
          <h2>{t("settings.holidays")}</h2>
          {(addHoliday.isError || removeHoliday.isError) && (
            <div className="alert alert-error" role="alert">
              {tError(addHoliday.error ?? removeHoliday.error)}
            </div>
          )}
          <form
            className="form-row"
            onSubmit={(e) => {
              e.preventDefault();
              if (holiday.day) addHoliday.mutate(holiday);
            }}
          >
            <div className="field">
              <label htmlFor="hol-day">{t("settings.date")}</label>
              <input id="hol-day" className="input" type="date" required value={holiday.day} onChange={(e) => setHoliday({ ...holiday, day: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="hol-name">{t("inventory.name")}</label>
              <input id="hol-name" className="input" maxLength={120} value={holiday.name} onChange={(e) => setHoliday({ ...holiday, name: e.target.value })} />
            </div>
            <div className="field" style={{ alignSelf: "end" }}>
              <button type="submit" className="btn btn-primary" disabled={addHoliday.isPending}>
                {t("settings.addHoliday")}
              </button>
            </div>
          </form>
          {hours.data && hours.data.holidays.length === 0 && <p className="empty">{t("settings.noHolidays")}</p>}
          <ul className="notif-list">
            {hours.data?.holidays.map((h) => (
              <li className="notif" key={h.id}>
                <div className="grow">
                  <strong>{h.day}</strong> {h.name}
                </div>
                <button type="button" className="btn btn-outline btn-sm" disabled={removeHoliday.isPending} onClick={() => removeHoliday.mutate(h.id)}>
                  {t("settings.remove")}
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

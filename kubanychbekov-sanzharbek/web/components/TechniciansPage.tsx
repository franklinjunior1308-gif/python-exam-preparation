"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import type { Technician } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type Row = { weekday: number; start: string; end: string };
const WEEKDAY_KEYS = [
  "weekday.0",
  "weekday.1",
  "weekday.2",
  "weekday.3",
  "weekday.4",
  "weekday.5",
  "weekday.6",
] as const;

/** Technicians: skills, weekly availability and load. Staff read, admins edit (ORG-01). */
export function TechniciansPage() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const admin = role === "admin";
  const [editing, setEditing] = useState<Technician | null>(null);
  const [skills, setSkills] = useState("");
  const [active, setActive] = useState(true);
  const [rows, setRows] = useState<Row[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["technicians", orgId],
    queryFn: () => api<Technician[]>("technicians"),
    enabled: staff,
  });

  const save = useMutation({
    mutationFn: (input: { id: number; body: Record<string, unknown> }) =>
      api<Technician>(`technicians/${input.id}/profile`, { method: "PUT", body: input.body }),
    onSuccess: async () => {
      setEditing(null);
      await Promise.all(
        ["technicians", "suggestions", "schedule", "assign"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key, orgId] }),
        ),
      );
    },
  });

  if (!staff) return <div className="alert">{t("schedule.onlyStaff")}</div>;

  function edit(tech: Technician) {
    save.reset();
    setFormError(null);
    setEditing(tech);
    setSkills(tech.skills.join(", "));
    setActive(tech.is_active);
    setRows(
      tech.availability.map((a) => ({
        weekday: a.weekday,
        start: a.start_time.slice(0, 5),
        end: a.end_time.slice(0, 5),
      })),
    );
  }

  function patchRow(index: number, patch: Partial<Row>) {
    setRows(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    if (rows.some((r) => r.end <= r.start)) {
      setFormError(t("settings.invalidHours"));
      return;
    }
    setFormError(null);
    save.mutate({
      id: editing.id,
      body: {
        skills: skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        is_active: active,
        availability: rows.map((r) => ({ weekday: r.weekday, start_time: r.start, end_time: r.end })),
      },
    });
  }

  const summary = (tech: Technician) =>
    tech.availability.length === 0
      ? "-"
      : tech.availability
          .map(
            (a) =>
              `${t(WEEKDAY_KEYS[a.weekday] ?? "weekday.0").slice(0, 3)} ${a.start_time.slice(0, 5)}-${a.end_time.slice(0, 5)}`,
          )
          .join(", ");

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("tech.title")}</h1>
          <p className="page-sub">{t("tech.sub")}</p>
        </div>
      </div>

      <section className="card">
        {list.isPending && <p className="muted">{t("common.loading")}</p>}
        {list.isError && (
          <div className="alert alert-error" role="alert">
            {tError(list.error)}
          </div>
        )}
        {list.data && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("tech.name")}</th>
                  <th>{t("tech.skills")}</th>
                  <th>{t("tech.availability")}</th>
                  <th>{t("tech.load")}</th>
                  {admin && <th />}
                </tr>
              </thead>
              <tbody>
                {list.data.map((tech) => (
                  <tr key={tech.id}>
                    <td>
                      {tech.full_name}
                      <small className="muted block">{tech.email}</small>
                      {!tech.is_active && <small className="paused block">{t("tech.inactive")}</small>}
                    </td>
                    <td>{tech.skills.join(", ") || "-"}</td>
                    <td>
                      <small>{summary(tech)}</small>
                    </td>
                    <td>{Math.round(tech.load_percent)}%</td>
                    {admin && (
                      <td>
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => edit(tech)}>
                          {t("tech.edit")}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {admin && editing && (
        <form className="card" onSubmit={submit} style={{ marginTop: 14 }}>
          <h2>{t("tech.editing", { name: editing.full_name })}</h2>
          {(formError || save.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(save.error)}
            </div>
          )}
          <div className="field">
            <label htmlFor="tech-skills">{t("tech.skillsHint")}</label>
            <input id="tech-skills" className="input" value={skills} onChange={(e) => setSkills(e.target.value)} />
          </div>
          <label className="check">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> {t("tech.active")}
          </label>
          <h3>{t("tech.availability")}</h3>
          {rows.map((row, index) => (
            <div className="hours-row" key={index}>
              <select
                className="select"
                aria-label={t("tech.weekday")}
                value={row.weekday}
                onChange={(e) => patchRow(index, { weekday: Number(e.target.value) })}
              >
                {WEEKDAY_KEYS.map((key, day) => (
                  <option key={key} value={day}>
                    {t(key)}
                  </option>
                ))}
              </select>
              <input
                className="input"
                type="time"
                aria-label={t("settings.from")}
                value={row.start}
                onChange={(e) => patchRow(index, { start: e.target.value })}
              />
              <input
                className="input"
                type="time"
                aria-label={t("settings.to")}
                value={row.end}
                onChange={(e) => patchRow(index, { end: e.target.value })}
              />
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setRows(rows.filter((_, i) => i !== index))}
              >
                {t("settings.remove")}
              </button>
            </div>
          ))}
          <div className="actions">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => setRows([...rows, { weekday: 0, start: "09:00", end: "18:00" }])}
            >
              {t("tech.addInterval")}
            </button>
            <button type="submit" className="btn btn-primary" disabled={save.isPending}>
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setEditing(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

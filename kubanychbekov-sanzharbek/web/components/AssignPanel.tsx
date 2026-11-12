"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { en } from "@/lib/i18n/dict";
import type { TKey } from "@/lib/i18n";
import { isoToZonedInput, zonedInputToIso } from "@/lib/time";
import type { Assignment, Candidate, ServiceRequest, Suggestion } from "@/lib/types";
import { BoltIcon, CalendarIcon } from "./icons";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const ACTIVE = ["SCHEDULED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"];
const MOVABLE = ["SCHEDULED", "ACCEPTED"];

type Window = { start_at: string; end_at: string };

export function AssignPanel({ request }: { request: ServiceRequest }) {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const tz = membership.timezone;
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const triaged = request.status === "TRIAGED";

  const [manual, setManual] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [editing, setEditing] = useState(false);
  const [confirmUnassign, setConfirmUnassign] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const assignments = useQuery({
    queryKey: ["assignments", orgId, request.id],
    queryFn: () => api<Assignment[]>(`requests/${request.id}/assignments`),
    enabled: staff,
  });
  const suggestions = useQuery({
    queryKey: ["suggestions", orgId, request.id, request.updated_at],
    queryFn: () => api<Suggestion[]>(`requests/${request.id}/suggestions`),
    enabled: staff && triaged,
  });

  const startIso = start ? zonedInputToIso(start, tz) : "";
  const endIso = end ? zonedInputToIso(end, tz) : "";
  const windowValid = Boolean(startIso && endIso && new Date(endIso) > new Date(startIso));
  const candidates = useQuery({
    queryKey: ["candidates", orgId, request.id, startIso, endIso],
    queryFn: () =>
      api<Candidate[]>(`requests/${request.id}/candidates`, {
        query: { start_at: startIso, end_at: endIso },
      }),
    enabled: staff && triaged && manual && windowValid,
  });

  async function refresh() {
    await Promise.all(
      ["request", "history", "requests", "summary", "assignments", "suggestions", "schedule"].map(
        (key) => queryClient.invalidateQueries({ queryKey: [key, orgId] }),
      ),
    );
  }

  const assign = useMutation({
    mutationFn: (input: Window & { technician_id: number }) =>
      api<Assignment>(`requests/${request.id}/assignments`, { method: "POST", body: input }),
    onSuccess: async () => {
      setNotice(t("assign.done"));
      setManual(false);
      await refresh();
    },
  });
  const reschedule = useMutation({
    mutationFn: (input: { id: number } & Window) =>
      api<Assignment>(`assignments/${input.id}`, {
        method: "PATCH",
        body: { start_at: input.start_at, end_at: input.end_at },
      }),
    onSuccess: async () => {
      setEditing(false);
      await refresh();
    },
  });
  const unassign = useMutation({
    mutationFn: (id: number) =>
      api<Assignment>(`assignments/${id}/unassign`, { method: "POST", body: { reason: null } }),
    onSuccess: async () => {
      setConfirmUnassign(false);
      await refresh();
    },
  });

  if (!staff) return null;

  const current = assignments.data?.find((a) => ACTIVE.includes(a.status));
  const busy = assign.isPending || reschedule.isPending || unassign.isPending;
  const error = assign.error ?? reschedule.error ?? unassign.error;

  function reasonText(code: string, detail: string | null): string {
    const key = `reason.${code}`;
    return key in en ? t(key as TKey, { detail: detail ?? "" }) : code;
  }

  function startEditing(a: Assignment) {
    setStart(isoToZonedInput(a.start_at, tz));
    setEnd(isoToZonedInput(a.end_at, tz));
    reschedule.reset();
    setEditing(true);
  }

  return (
    <section className="card" aria-labelledby="assign-title">
      <h2 id="assign-title">{t("assign.current")}</h2>

      {notice && !error && (
        <div className="alert" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="alert alert-error" role="alert">
          {tError(error)}
        </div>
      )}

      {current && (
        <div>
          <dl className="dl">
            <dt>{t("assign.current")}</dt>
            <dd>
              <strong>{current.technician_name}</strong>{" "}
              <span className="muted">({t(`assignment.${current.status}`)})</span>
            </dd>
            <dt>{t("assign.start")}</dt>
            <dd>{formatDateTime(current.start_at, lang, tz)}</dd>
            <dt>{t("assign.end")}</dt>
            <dd>{formatDateTime(current.end_at, lang, tz)}</dd>
          </dl>

          {MOVABLE.includes(current.status) && !editing && (
            <div className="actions" style={{ marginTop: 14 }}>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => startEditing(current)}>
                {t("assign.reschedule")}
              </button>
              {!confirmUnassign ? (
                <button type="button" className="btn btn-danger btn-sm" onClick={() => setConfirmUnassign(true)}>
                  {t("assign.unassign")}
                </button>
              ) : (
                <span className="actions" role="group" aria-label={t("assign.unassignConfirm")}>
                  <span className="hint">{t("assign.unassignConfirm")}</span>
                  <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => unassign.mutate(current.id)}>
                    {t("common.confirm")}
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirmUnassign(false)}>
                    {t("common.cancel")}
                  </button>
                </span>
              )}
            </div>
          )}

          {editing && (
            <form
              style={{ marginTop: 14 }}
              onSubmit={(e) => {
                e.preventDefault();
                if (windowValid && !busy) reschedule.mutate({ id: current.id, start_at: startIso, end_at: endIso });
              }}
            >
              <div className="row">
                <div className="field">
                  <label htmlFor="re-start">{t("assign.start")}</label>
                  <input id="re-start" className="input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="re-end">{t("assign.end")}</label>
                  <input id="re-end" className="input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
                </div>
              </div>
              <div className="actions">
                <button type="submit" className="btn btn-primary btn-sm" disabled={!windowValid || busy}>
                  {t("assign.save")}
                </button>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {!current && triaged && (
        <>
          <div className="smart">
            <h3>
              <BoltIcon size={18} /> {t("smart.title")}
            </h3>
            <p className="hint">{t("smart.lead")}</p>
            {suggestions.isPending && <p className="muted">{t("common.loading")}</p>}
            {suggestions.isError && (
              <p className="field-error" role="alert">
                {tError(suggestions.error)}
              </p>
            )}
            {suggestions.data && suggestions.data.length === 0 && <p className="empty">{t("smart.empty")}</p>}
            <ul className="suggest-list">
              {suggestions.data?.map((s) => (
                <li key={s.technician_id} className={s.is_best ? "suggest best" : "suggest"}>
                  <div>
                    <strong>{s.full_name}</strong>{" "}
                    {s.is_best && <span className="tag tag-best">{t("smart.best")}</span>}
                    <div>
                      <CalendarIcon size={14} /> {formatDateTime(s.start_at, lang, tz)} - {formatDateTime(s.end_at, lang, tz).split(", ").pop()}
                    </div>
                    <small className="muted">
                      {t("schedule.load", { n: s.load_percent })}
                      {s.within_desired_window !== null && (
                        <> · {s.within_desired_window ? t("smart.inside") : t("smart.outside")}</>
                      )}
                    </small>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busy}
                    onClick={() => assign.mutate({ technician_id: s.technician_id, start_at: s.start_at, end_at: s.end_at })}
                  >
                    {assign.isPending ? t("smart.applying") : t("smart.apply")}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <button type="button" className="btn btn-outline btn-sm" style={{ marginTop: 14 }} aria-expanded={manual} onClick={() => setManual((v) => !v)}>
            {manual ? t("assign.hideManual") : t("assign.manual")}
          </button>

          {manual && (
            <div style={{ marginTop: 14 }}>
              <div className="row">
                <div className="field">
                  <label htmlFor="m-start">{t("assign.start")}</label>
                  <input id="m-start" className="input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="m-end">{t("assign.end")}</label>
                  <input id="m-end" className="input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
                </div>
              </div>
              {!windowValid && <p className="hint">{t("assign.pickTime")}</p>}
              {candidates.isPending && windowValid && <p className="muted">{t("common.loading")}</p>}
              {candidates.isError && <p className="field-error">{tError(candidates.error)}</p>}
              {candidates.data && (
                <ul className="suggest-list" aria-label={t("assign.candidates")}>
                  {candidates.data.map((c) => (
                    <li key={c.technician_id} className="suggest">
                      <div>
                        <strong>{c.full_name}</strong>{" "}
                        <span className={c.available ? "tag tag-ok" : "tag tag-bad"}>
                          {c.available ? t("assign.available") : t("assign.unavailable")}
                        </span>
                        <div className="muted">{c.skills.join(", ")}</div>
                        <small className="muted">
                          {t("schedule.load", { n: c.load_percent })}
                          {c.reasons.map((r) => (
                            <span key={r.code} className="reason">
                              {" · "}
                              {reasonText(r.code, r.detail)}
                            </span>
                          ))}
                        </small>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={!c.available || busy}
                        onClick={() => assign.mutate({ technician_id: c.technician_id, start_at: startIso, end_at: endIso })}
                      >
                        {t("smart.apply")}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}

      <h3 style={{ marginTop: 18 }}>{t("assign.history")}</h3>
      {assignments.data && assignments.data.length === 0 && <p className="muted">{t("assign.noHistory")}</p>}
      <ul className="history-list">
        {assignments.data?.map((a) => (
          <li key={a.id}>
            <strong>{a.technician_name}</strong> · {formatDateTime(a.start_at, lang, tz)} · {t(`assignment.${a.status}`)}
          </li>
        ))}
      </ul>
    </section>
  );
}

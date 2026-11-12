"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import {
  formatKgs,
  laborTotalCents,
  lineTotalCents,
  parseKgsToCents,
  parseQuantityMilli,
  trimQuantity,
} from "@/lib/money";
import type { Estimate, ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type LineForm = { description: string; quantity: string; price: string };
type Errors = { minutes?: string; rate?: string; lines: Record<number, string> };

const EMPTY_LINE: LineForm = { description: "", quantity: "1", price: "" };

function toForm(est: Estimate | undefined) {
  if (!est) return { minutes: "60", rate: "", lines: [] as LineForm[] };
  return {
    minutes: String(est.labor_minutes),
    rate: (est.labor_rate_cents / 100).toFixed(2),
    lines: est.lines.map((l) => ({
      description: l.description,
      quantity: trimQuantity(l.quantity),
      price: (l.unit_price_cents / 100).toFixed(2),
    })),
  };
}

export function EstimatesPanel({ request }: { request: ServiceRequest }) {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const tz = membership.timezone;
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const customer = role === "customer";

  const estimates = useQuery({
    queryKey: ["estimates", orgId, request.id],
    queryFn: () => api<Estimate[]>(`requests/${request.id}/estimates`),
    enabled: staff || customer,
  });

  const [editing, setEditing] = useState(false);
  const [minutes, setMinutes] = useState("60");
  const [rate, setRate] = useState("");
  const [lines, setLines] = useState<LineForm[]>([]);
  const [errors, setErrors] = useState<Errors>({ lines: {} });
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const refresh = () =>
    Promise.all(
      ["estimates", "request", "history", "requests"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key, orgId] }),
      ),
    );

  const save = useMutation({
    mutationFn: (input: { id: number | null; body: unknown }) =>
      input.id === null
        ? api<Estimate>(`requests/${request.id}/estimates`, { method: "POST", body: input.body })
        : api<Estimate>(`estimates/${input.id}`, { method: "PUT", body: input.body }),
    onSuccess: async () => {
      setEditing(false);
      await refresh();
    },
  });
  const act = useMutation({
    mutationFn: (input: { id: number; action: "submit" | "withdraw" }) =>
      api<Estimate>(`estimates/${input.id}/${input.action}`, { method: "POST" }),
    onSuccess: refresh,
  });
  const decide = useMutation({
    mutationFn: (input: { id: number; approve: boolean; reason?: string }) =>
      api<Estimate>(`estimates/${input.id}/decision`, {
        method: "POST",
        body: { approve: input.approve, reason: input.reason },
      }),
    onSuccess: async () => {
      setRejecting(false);
      setReason("");
      await refresh();
    },
  });

  if (!staff && !customer) return null;
  const all = estimates.data ?? [];
  const latest = all[0];
  const busy = save.isPending || act.isPending || decide.isPending;
  const error = save.error ?? act.error ?? decide.error ?? estimates.error;
  const open = latest && (latest.status === "DRAFT" || latest.status === "AWAITING_APPROVAL");
  const blocksStart =
    request.status === "ACCEPTED" &&
    latest &&
    (latest.status === "AWAITING_APPROVAL" || latest.status === "REJECTED");

  function startForm(from: Estimate | undefined) {
    const form = toForm(from);
    setMinutes(form.minutes);
    setRate(form.rate);
    setLines(form.lines);
    setErrors({ lines: {} });
    save.reset();
    setEditing(true);
  }

  // Preview only: the server recalculates and is the source of truth.
  const rateCents = parseKgsToCents(rate);
  const minutesValue = /^\d{1,6}$/.test(minutes.trim()) ? Number(minutes) : null;
  const preview = (() => {
    if (rateCents === null || minutesValue === null) return null;
    let materials = 0;
    for (const l of lines) {
      const q = parseQuantityMilli(l.quantity);
      const p = parseKgsToCents(l.price);
      if (q === null || p === null) return null;
      materials += lineTotalCents(q, p);
    }
    const labor = laborTotalCents(minutesValue, rateCents);
    return { labor, materials, total: labor + materials };
  })();

  function validate(): { body: unknown } | null {
    const next: Errors = { lines: {} };
    if (minutesValue === null) next.minutes = t("est.err.minutes");
    if (rateCents === null) next.rate = t("est.err.money");
    lines.forEach((l, i) => {
      if (!l.description.trim()) next.lines[i] = t("est.err.description");
      else if (parseQuantityMilli(l.quantity) === null) next.lines[i] = t("est.err.quantity");
      else if (parseKgsToCents(l.price) === null) next.lines[i] = t("est.err.money");
    });
    setErrors(next);
    if (next.minutes || next.rate || Object.keys(next.lines).length > 0) return null;
    return {
      body: {
        labor_minutes: minutesValue,
        labor_rate_cents: rateCents,
        lines: lines.map((l) => ({
          description: l.description.trim(),
          quantity: l.quantity.trim().replace(",", "."),
          unit_price_cents: parseKgsToCents(l.price),
        })),
      },
    };
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const valid = validate();
    if (valid) save.mutate({ id: latest?.status === "DRAFT" ? latest.id : null, body: valid.body });
  }

  const statusLabel = (e: Estimate) => t(`est.status.${e.status}`);

  return (
    <section className="card" aria-labelledby="est-title">
      <h2 id="est-title">{t("est.title")}</h2>

      {error && (
        <div className="alert alert-error" role="alert">
          {tError(error)}
        </div>
      )}
      {blocksStart && <div className="alert">{t("est.startBlocked")}</div>}

      {!estimates.isPending && all.length === 0 && !editing && <p className="muted">{t("est.none")}</p>}

      {latest && !editing && (
        <EstimateView
          estimate={latest}
          render={{ t, lang, tz }}
          statusLabel={statusLabel(latest)}
        />
      )}

      {/* customer decision */}
      {customer && latest?.status === "AWAITING_APPROVAL" && (
        <div style={{ marginTop: 12 }}>
          {!rejecting ? (
            <div className="actions">
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => decide.mutate({ id: latest.id, approve: true })}
              >
                {t("est.approve")}
              </button>
              <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setRejecting(true)}>
                {t("est.reject")}
              </button>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (reason.trim() && !busy) decide.mutate({ id: latest.id, approve: false, reason });
              }}
            >
              <div className="field">
                <label htmlFor="est-reason">{t("est.rejectReason")}</label>
                <textarea id="est-reason" className="textarea" style={{ minHeight: 80 }} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
              </div>
              <div className="actions">
                <button type="submit" className="btn btn-danger" disabled={busy || !reason.trim()}>
                  {t("est.confirmReject")}
                </button>
                <button type="button" className="btn btn-outline" onClick={() => setRejecting(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* dispatcher / admin actions */}
      {staff && !editing && (
        <div className="actions" style={{ marginTop: 12 }}>
          {!latest && (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => startForm(undefined)}>
              {t("est.create")}
            </button>
          )}
          {latest?.status === "DRAFT" && (
            <>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => startForm(latest)}>
                {t("est.saveDraft")}
              </button>
              <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => act.mutate({ id: latest.id, action: "submit" })}>
                {t("est.submit")}
              </button>
            </>
          )}
          {latest && latest.status !== "SUPERSEDED" && latest.status !== "APPROVED" && (
            <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => act.mutate({ id: latest.id, action: "withdraw" })}>
              {t("est.withdraw")}
            </button>
          )}
          {latest && !open && (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => startForm(latest)}>
              {t("est.newVersion")}
            </button>
          )}
        </div>
      )}
      {staff && latest?.status === "AWAITING_APPROVAL" && <p className="hint">{t("est.locked")}</p>}

      {editing && (
        <form onSubmit={onSubmit} noValidate style={{ marginTop: 12 }}>
          <div className="row">
            <div className="field">
              <label htmlFor="est-min">{t("est.laborMinutes")}</label>
              <input id="est-min" className="input" inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value)} aria-invalid={Boolean(errors.minutes)} />
              {errors.minutes && <span className="field-error">{errors.minutes}</span>}
            </div>
            <div className="field">
              <label htmlFor="est-rate">{t("est.rate")}</label>
              <input id="est-rate" className="input" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} aria-invalid={Boolean(errors.rate)} />
              {errors.rate && <span className="field-error">{errors.rate}</span>}
            </div>
          </div>

          <h3 style={{ margin: "6px 0" }}>{t("est.materials")}</h3>
          {lines.map((line, i) => (
            <fieldset key={i} className="line-box">
              <legend className="sr-only">{`${t("est.item")} ${i + 1}`}</legend>
              <div className="field">
                <label htmlFor={`l-d-${i}`}>{t("est.item")}</label>
                <input id={`l-d-${i}`} className="input" value={line.description} onChange={(e) => setLines(lines.map((l, k) => (k === i ? { ...l, description: e.target.value } : l)))} />
              </div>
              <div className="row">
                <div className="field">
                  <label htmlFor={`l-q-${i}`}>{t("est.quantity")}</label>
                  <input id={`l-q-${i}`} className="input" inputMode="decimal" value={line.quantity} onChange={(e) => setLines(lines.map((l, k) => (k === i ? { ...l, quantity: e.target.value } : l)))} />
                </div>
                <div className="field">
                  <label htmlFor={`l-p-${i}`}>{t("est.price")}</label>
                  <input id={`l-p-${i}`} className="input" inputMode="decimal" value={line.price} onChange={(e) => setLines(lines.map((l, k) => (k === i ? { ...l, price: e.target.value } : l)))} />
                </div>
              </div>
              {errors.lines[i] && <span className="field-error">{errors.lines[i]}</span>}
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setLines(lines.filter((_, k) => k !== i))}>
                {t("est.removeLine")}
              </button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setLines([...lines, { ...EMPTY_LINE }])}>
            {t("est.addLine")}
          </button>

          {preview && (
            <p className="hint" style={{ marginTop: 10 }}>
              {t("est.preview")}: {t("est.labor")} {formatKgs(preview.labor)} + {t("est.materialsTotal")} {formatKgs(preview.materials)} = <strong>{formatKgs(preview.total)}</strong>
            </p>
          )}
          <div className="actions" style={{ marginTop: 12 }}>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {t("est.saveDraft")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setEditing(false)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}

      {all.length > 1 && !editing && (
        <details style={{ marginTop: 14 }}>
          <summary>{t("est.history")}</summary>
          <ul className="history-list">
            {all.slice(1).map((e) => (
              <li key={e.id}>
                {t("est.version", { n: e.version })} · {t(`est.status.${e.status}`)} · {formatKgs(e.total_cents)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function EstimateView({
  estimate,
  render,
  statusLabel,
}: {
  estimate: Estimate;
  render: { t: ReturnType<typeof useI18n>["t"]; lang: "en" | "ru"; tz: string };
  statusLabel: string;
}) {
  const { t, lang, tz } = render;
  return (
    <div>
      <p style={{ margin: "0 0 8px" }}>
        <strong>{t("est.version", { n: estimate.version })}</strong>{" "}
        <span className={`badge est-${estimate.status}`}>{statusLabel}</span>
      </p>
      <table className="table">
        <tbody>
          <tr>
            <td>
              {t("est.labor")} ({estimate.labor_minutes} {t("time.min")})
            </td>
            <td style={{ textAlign: "right" }}>{formatKgs(estimate.labor_cents)}</td>
          </tr>
          {estimate.lines.map((l) => (
            <tr key={l.id}>
              <td>
                {l.description} × {trimQuantity(l.quantity)}
              </td>
              <td style={{ textAlign: "right" }}>{formatKgs(l.line_total_cents)}</td>
            </tr>
          ))}
          <tr>
            <td>
              <strong>{t("est.total")}</strong>
            </td>
            <td style={{ textAlign: "right" }}>
              <strong>{formatKgs(estimate.total_cents)}</strong>
            </td>
          </tr>
        </tbody>
      </table>
      {estimate.decided_at && (
        <p className="hint">
          {t("est.decision", { status: statusLabel, when: formatDateTime(estimate.decided_at, lang, tz) })}
          {estimate.decision_reason ? ` · ${t("est.reasonLabel", { reason: estimate.decision_reason })}` : ""}
        </p>
      )}
    </div>
  );
}

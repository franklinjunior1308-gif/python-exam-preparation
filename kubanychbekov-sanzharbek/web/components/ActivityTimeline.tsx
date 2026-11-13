"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { formatKgs } from "@/lib/money";
import type { Assignment, Estimate, Feedback, HistoryEntry, MaterialUsage, Note, ServiceRequest } from "@/lib/types";
import { StatusBadge } from "./Badges";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type Item = { key: string; at: string; node: React.ReactNode };

/**
 * One chronology of the request (COMM-07): status changes, notes, visits, estimates, materials and the
 * customer's rating, newest first. Each source is loaded with the same query keys as its own panel.
 */
export function ActivityTimeline({ request }: { request: ServiceRequest }) {
  const { t, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const staff = role === "dispatcher" || role === "admin";
  const finished = request.status === "COMPLETED" || request.status === "CLOSED";
  const tz = membership.timezone;

  const history = useQuery({ queryKey: ["history", orgId, request.id], queryFn: () => api<HistoryEntry[]>(`requests/${request.id}/history`) });
  const notes = useQuery({ queryKey: ["notes", orgId, request.id], queryFn: () => api<Note[]>(`requests/${request.id}/notes`) });
  const assignments = useQuery({
    queryKey: ["assignments", orgId, request.id],
    queryFn: () => api<Assignment[]>(`requests/${request.id}/assignments`),
    enabled: staff,
  });
  const estimates = useQuery({ queryKey: ["estimates", orgId, request.id], queryFn: () => api<Estimate[]>(`requests/${request.id}/estimates`) });
  const usages = useQuery({
    queryKey: ["materials", orgId, request.id],
    queryFn: () => api<MaterialUsage[]>(`requests/${request.id}/materials`),
    enabled: staff,
  });
  const feedback = useQuery({
    queryKey: ["feedback", orgId, request.id],
    queryFn: () => api<Feedback | null>(`requests/${request.id}/feedback`),
    enabled: finished,
  });

  const items: Item[] = [];
  for (const h of history.data ?? []) {
    items.push({
      key: `h${h.id}`,
      at: h.created_at,
      node: (
        <>
          <StatusBadge status={h.to_status} />
          {h.reason && <small>{h.reason}</small>}
        </>
      ),
    });
  }
  for (const n of notes.data ?? []) {
    items.push({
      key: `n${n.id}`,
      at: n.created_at,
      node: (
        <>
          <span>
            {n.kind === "completion" ? t("tl.completion") : t("tl.note")}: {n.author_name}
            {n.visibility === "internal" ? ` (${t("notes.internal")})` : ""}
          </span>
          <small>{n.body}</small>
        </>
      ),
    });
  }
  for (const a of assignments.data ?? []) {
    if (!a.created_at) continue;
    items.push({
      key: `a${a.id}`,
      at: a.created_at,
      node: (
        <span>
          {t("tl.visit", { tech: a.technician_name, when: formatDateTime(a.start_at, lang, tz) })} ({t(`assignment.${a.status}`)})
        </span>
      ),
    });
  }
  for (const e of estimates.data ?? []) {
    if (e.submitted_at) {
      items.push({ key: `es${e.id}`, at: e.submitted_at, node: <span>{t("tl.estimateSent", { v: e.version, total: formatKgs(e.total_cents) })}</span> });
    }
    if (e.decided_at) {
      items.push({
        key: `ed${e.id}`,
        at: e.decided_at,
        node: (
          <>
            <span>{t("tl.estimateDecided", { v: e.version, state: t(`est.status.${e.status}` as never) })}</span>
            {e.decision_reason && <small>{e.decision_reason}</small>}
          </>
        ),
      });
    }
  }
  for (const u of usages.data ?? []) {
    items.push({ key: `m${u.id}`, at: u.created_at, node: <span>{t("tl.material", { item: u.item_name, qty: u.quantity })}</span> });
  }
  if (feedback.data) {
    items.push({
      key: "fb",
      at: feedback.data.created_at,
      node: (
        <>
          <span>{t("tl.rated", { n: feedback.data.rating })}</span>
          {feedback.data.comment && <small>{feedback.data.comment}</small>}
        </>
      ),
    });
  }
  items.push({ key: "created", at: request.created_at, node: <span>{t("tl.created")}</span> });
  items.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));

  return (
    <section className="card" aria-labelledby="timeline-title">
      <h2 id="timeline-title">{t("detail.history")}</h2>
      {history.isPending && <p className="muted">{t("common.loading")}</p>}
      <ol className="timeline">
        {items.map((item) => (
          <li key={item.key}>
            {item.node}
            <small>{formatDateTime(item.at, lang, tz)}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}

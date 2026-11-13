"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { formatDateTime, needsReason } from "@/lib/format";
import type { Category, Property, RequestStatus, ServiceRequest } from "@/lib/types";
import { ActivityTimeline } from "./ActivityTimeline";
import { AttachmentsPanel } from "./AttachmentsPanel";
import { AssignPanel } from "./AssignPanel";
import { EstimatesPanel } from "./EstimatesPanel";
import { FeedbackPanel } from "./FeedbackPanel";
import { MaterialsPanel } from "./MaterialsPanel";
import { NotesPanel } from "./NotesPanel";
import { SlaBadge } from "./SlaBadge";
import { PriorityBadge, StatusBadge } from "./Badges";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

export function RequestDetail({ requestId }: { requestId: number }) {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const queryClient = useQueryClient();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [target, setTarget] = useState<RequestStatus | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);

  const request = useQuery({
    queryKey: ["request", orgId, requestId],
    queryFn: () => api<ServiceRequest>(`requests/${requestId}`),
  });
  const categories = useQuery({ queryKey: ["categories", orgId], queryFn: () => api<Category[]>("categories") });
  const properties = useQuery({ queryKey: ["properties", orgId], queryFn: () => api<Property[]>("properties") });

  const transition = useMutation({
    mutationFn: (input: { to_status: RequestStatus; reason: string | null }) =>
      api<ServiceRequest>(`requests/${requestId}/transitions`, { method: "POST", body: input }),
    onSuccess: async () => {
      dialogRef.current?.close();
      setTarget(null);
      setReason("");
      await Promise.all(
        ["request", "history", "requests", "summary", "assignments", "suggestions", "schedule"].map(
          (key) => queryClient.invalidateQueries({ queryKey: [key, orgId] }),
        ),
      );
    },
    onError: () => {
      // a conflict means someone else changed the request: refresh what we show
      void queryClient.invalidateQueries({ queryKey: ["request", orgId, requestId] });
    },
  });

  if (request.isPending) return <p className="muted">{t("common.loading")}</p>;
  if (request.isError) {
    const notFound = request.error instanceof ApiError && request.error.status === 404;
    return (
      <div className="alert alert-error" role="alert">
        {notFound ? t("detail.notFound") : tError(request.error)}{" "}
        <Link href="/app/requests" className="accent">
          {t("detail.back")}
        </Link>
      </div>
    );
  }

  const req = request.data;
  const categoryName = categories.data?.find((c) => c.id === req.category_id)?.name ?? "-";
  const property = properties.data?.find((p) => p.id === req.property_id);
  const required = target ? needsReason(req.status, target, role) : false;

  function openAction(next: RequestStatus) {
    setTarget(next);
    setReason("");
    setReasonError(false);
    transition.reset();
    dialogRef.current?.showModal();
  }

  function confirm() {
    if (!target || transition.isPending) return;
    if (required && !reason.trim()) {
      setReasonError(true);
      return;
    }
    transition.mutate({ to_status: target, reason: reason.trim() || null });
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <p className="muted">
            <Link href="/app/requests">&larr; {t("detail.back")}</Link>
          </p>
          <h1>
            #{req.id} {req.title}
          </h1>
        </div>
        <StatusBadge status={req.status} />
        <PriorityBadge priority={req.priority} />
      </div>

      <div className="detail-grid">
        <section className="card">
          <h2>{t("detail.info")}</h2>
          <p style={{ whiteSpace: "pre-wrap", marginTop: 0 }}>{req.description}</p>
          <dl className="dl">
            <dt>{t("req.col.category")}</dt>
            <dd>{categoryName}</dd>
            <dt>{t("req.col.property")}</dt>
            <dd>{property ? `${property.name}, ${property.address}` : "-"}</dd>
            {req.desired_start && (
              <>
                <dt>{t("detail.window")}</dt>
                <dd>
                  {formatDateTime(req.desired_start, lang, membership.timezone)}
                  {req.desired_end && ` - ${formatDateTime(req.desired_end, lang, membership.timezone)}`}
                </dd>
              </>
            )}
            <dt>{t("detail.created")}</dt>
            <dd>{formatDateTime(req.created_at, lang, membership.timezone)}</dd>
            <dt>{t("detail.updated")}</dt>
            <dd>{formatDateTime(req.updated_at, lang, membership.timezone)}</dd>
            <dt>{t("sla.title")}</dt>
            <dd>
              <SlaBadge sla={req.sla} detailed />
            </dd>
          </dl>
        </section>

        <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
          <AssignPanel request={req} />
          <EstimatesPanel request={req} />
          <FeedbackPanel request={req} />
          <MaterialsPanel request={req} />
          <NotesPanel request={req} />
          <AttachmentsPanel request={req} />
          <section className="card">
            <h2>{t("detail.actions")}</h2>
            {req.allowed_actions.length === 0 ? (
              <p className="muted">{t("detail.noActions")}</p>
            ) : (
              <div className="actions">
                {req.allowed_actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    className={action === "CANCELED" ? "btn btn-danger" : "btn btn-primary"}
                    onClick={() => openAction(action)}
                  >
                    {t(`action.${action}`)}
                  </button>
                ))}
              </div>
            )}
          </section>

          <ActivityTimeline request={req} />
        </div>
      </div>

      <dialog ref={dialogRef} onClose={() => setTarget(null)} aria-labelledby="dlg-title">
        {target && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              confirm();
            }}
          >
            <h2 id="dlg-title" style={{ marginBottom: 14 }}>
              {t("detail.confirm", { action: t(`action.${target}`) })}
            </h2>
            {transition.isError && (
              <div className="alert alert-error" role="alert">
                {tError(transition.error)}
              </div>
            )}
            <div className="field">
              <label htmlFor="reason">{required ? t("detail.reason") : t("detail.reasonOptional")}</label>
              <textarea
                id="reason"
                className="textarea"
                style={{ minHeight: 90 }}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                aria-invalid={reasonError}
                maxLength={1000}
              />
              {reasonError && <span className="field-error">{t("detail.reasonRequired")}</span>}
            </div>
            <div className="actions" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-outline" onClick={() => dialogRef.current?.close()}>
                {t("common.cancel")}
              </button>
              <button type="submit" className={target === "CANCELED" ? "btn btn-danger" : "btn btn-primary"} disabled={transition.isPending}>
                {t("common.confirm")}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </>
  );
}

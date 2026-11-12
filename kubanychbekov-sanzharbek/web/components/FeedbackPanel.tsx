"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { Feedback, ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const stars = (n: number) => "★".repeat(n) + "☆".repeat(5 - n);

/** Customer rating of finished work (COMM-07): shown once, leaves a 1-5 rating with an optional comment. */
export function FeedbackPanel({ request }: { request: ServiceRequest }) {
  const { t, tError, lang } = useI18n();
  const { orgId, role, me, membership } = useSession();
  const queryClient = useQueryClient();
  const finished = request.status === "COMPLETED" || request.status === "CLOSED";
  const mayRate = role === "customer" && request.created_by_user_id === me.id;
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [missing, setMissing] = useState(false);

  const existing = useQuery({
    queryKey: ["feedback", orgId, request.id],
    queryFn: () => api<Feedback | null>(`requests/${request.id}/feedback`),
    enabled: finished,
  });

  const submit = useMutation({
    mutationFn: (body: { rating: number; comment: string | null }) =>
      api<Feedback>(`requests/${request.id}/feedback`, { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feedback", orgId, request.id] }),
    onError: () => queryClient.invalidateQueries({ queryKey: ["feedback", orgId, request.id] }),
  });

  if (!finished) return null;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (rating < 1 || submit.isPending) {
      setMissing(rating < 1);
      return;
    }
    setMissing(false);
    submit.mutate({ rating, comment: comment.trim() || null });
  }

  return (
    <section className="card">
      <h2>{t("feedback.title")}</h2>
      {existing.isPending && <p className="muted">{t("common.loading")}</p>}
      {existing.data && (
        <div>
          <p style={{ margin: 0 }}>
            <span className="stars" role="img" aria-label={t("feedback.ratingLabel", { n: String(existing.data.rating) })}>
              {stars(existing.data.rating)}
            </span>{" "}
            <small className="muted">{formatDateTime(existing.data.created_at, lang, membership.timezone)}</small>
          </p>
          {existing.data.comment && <p style={{ whiteSpace: "pre-wrap" }}>{existing.data.comment}</p>}
        </div>
      )}
      {existing.data === null && !mayRate && <p className="muted">{t("feedback.none")}</p>}
      {existing.data === null && mayRate && (
        <form onSubmit={onSubmit}>
          {submit.isError && (
            <div className="alert alert-error" role="alert">
              {tError(submit.error)}
            </div>
          )}
          <fieldset className="rating" aria-describedby={missing ? "rating-error" : undefined}>
            <legend>{t("feedback.rate")}</legend>
            {[1, 2, 3, 4, 5].map((n) => (
              <label key={n} className="rating-star">
                <input type="radio" name="rating" value={n} checked={rating === n} onChange={() => setRating(n)} />
                <span aria-hidden="true">{n <= rating ? "★" : "☆"}</span>
                <span className="sr-only">{t("feedback.ratingLabel", { n: String(n) })}</span>
              </label>
            ))}
          </fieldset>
          {missing && (
            <span id="rating-error" className="field-error">
              {t("feedback.pick")}
            </span>
          )}
          <div className="field">
            <label htmlFor="fb-comment">{t("feedback.comment")}</label>
            <textarea id="fb-comment" className="textarea" maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={submit.isPending}>
            {t("feedback.send")}
          </button>
        </form>
      )}
    </section>
  );
}

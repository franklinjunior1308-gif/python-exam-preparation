"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { Note, ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/**
 * Notes on a request (COMM-01, COMM-02). Public notes are visible to everyone involved, internal ones
 * only to staff; the server hides internal notes from customers. Notes cannot be edited.
 */
export function NotesPanel({ request }: { request: ServiceRequest }) {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const closed = request.status === "CLOSED" || request.status === "CANCELED";
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [empty, setEmpty] = useState(false);
  // one command id per message: a double click or a retry stores the note only once
  const commandId = useRef(crypto.randomUUID());

  const notes = useQuery({
    queryKey: ["notes", orgId, request.id],
    queryFn: () => api<Note[]>(`requests/${request.id}/notes`),
  });

  const add = useMutation({
    mutationFn: () =>
      api<Note>(`requests/${request.id}/notes`, {
        method: "POST",
        body: { body: body.trim(), visibility: internal ? "internal" : "public", client_command_id: commandId.current },
      }),
    onSuccess: async () => {
      setBody("");
      setInternal(false);
      commandId.current = crypto.randomUUID();
      await Promise.all(["notes", "audit"].map((key) => queryClient.invalidateQueries({ queryKey: [key, orgId] })));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (body.trim().length === 0) {
      setEmpty(true);
      return;
    }
    setEmpty(false);
    add.mutate();
  }

  return (
    <section className="card" aria-labelledby="notes-title">
      <h2 id="notes-title">{t("notes.title")}</h2>
      {notes.isPending && <p className="muted">{t("common.loading")}</p>}
      {notes.isError && (
        <div className="alert alert-error" role="alert">
          {tError(notes.error)}
        </div>
      )}
      {notes.data && notes.data.length === 0 && <p className="muted">{t("notes.empty")}</p>}
      <ul className="list">
        {(notes.data ?? []).map((n) => (
          <li key={n.id}>
            <strong>{n.author_name || "-"}</strong>{" "}
            <small className="muted">
              {formatDateTime(n.created_at, lang, membership.timezone)}
              {n.kind === "completion" ? ` · ${t("notes.completion")}` : ""}
              {n.visibility === "internal" ? ` · ${t("notes.internal")}` : ""}
            </small>
            <div style={{ whiteSpace: "pre-wrap" }}>{n.body}</div>
          </li>
        ))}
      </ul>
      {!closed && (
        <form onSubmit={submit}>
          {(empty || add.isError) && (
            <div className="alert alert-error" role="alert">
              {empty ? t("notes.emptyError") : tError(add.error)}
            </div>
          )}
          <div className="field">
            <label htmlFor="note-body">{t("notes.add")}</label>
            <textarea id="note-body" className="textarea" maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          {staff && (
            <label className="check">
              <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> {t("notes.internalHint")}
            </label>
          )}
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={add.isPending}>
              {t("notes.send")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

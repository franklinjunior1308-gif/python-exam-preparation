"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, apiUpload } from "@/lib/api-client";
import type { Attachment, ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const ACCEPT = "image/jpeg,image/png,image/webp";
const MAX_BYTES = 10 * 1024 * 1024;

/** Photos of a request: thumbnails through the authorized proxy, upload with an idempotency key. */
export function AttachmentsPanel({ request }: { request: ServiceRequest }) {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const closed = request.status === "CLOSED" || request.status === "CANCELED";
  const canUpload = !closed && (role === "customer" || role === "dispatcher" || role === "admin");

  const list = useQuery({
    queryKey: ["attachments", orgId, request.id],
    queryFn: () => api<Attachment[]>(`requests/${request.id}/attachments`),
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("file", file);
      form.set("client_command_id", crypto.randomUUID());
      form.set("purpose", "evidence");
      return apiUpload<Attachment>(`requests/${request.id}/attachments`, form);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", orgId, request.id] }),
  });

  function pick(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setLocalError(null);
    if (!ACCEPT.split(",").includes(file.type)) {
      setLocalError(t("photos.badType"));
    } else if (file.size > MAX_BYTES) {
      setLocalError(t("photos.tooLarge"));
    } else {
      upload.mutate(file);
    }
    if (input.current) input.current.value = "";
  }

  return (
    <section className="card">
      <h2>{t("photos.title")}</h2>
      {(localError || upload.isError) && (
        <div className="alert alert-error" role="alert">
          {localError ?? tError(upload.error)}
        </div>
      )}
      {list.isPending && <p className="muted">{t("common.loading")}</p>}
      {list.data && list.data.length === 0 && <p className="muted">{t("photos.empty")}</p>}
      {list.data && list.data.length > 0 && (
        <div className="photo-grid">
          {list.data.map((photo) => (
            <a key={photo.id} href={`/bff/attachments/${photo.id}/file`} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/bff/attachments/${photo.id}/file`} alt={`${t("photos.title")} #${photo.id}`} loading="lazy" />
            </a>
          ))}
        </div>
      )}
      {canUpload && (
        <>
          <input
            ref={input}
            id="photo-input"
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => pick(e.target.files)}
          />
          <button type="button" className="btn btn-outline" disabled={upload.isPending} onClick={() => input.current?.click()}>
            {upload.isPending ? t("common.loading") : t("photos.add")}
          </button>
          <p className="muted">{t("photos.hint")}</p>
        </>
      )}
    </section>
  );
}

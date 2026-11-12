"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { AppNotification } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** In-app notification inbox (COMM-*): newest first, mark one or all as read. */
export function NotificationsPage() {
  const { t, tError, lang } = useI18n();
  const { orgId, membership, role } = useSession();
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);

  const list = useQuery({
    queryKey: ["notifications", orgId, unreadOnly],
    queryFn: () => api<AppNotification[]>("notifications", { query: { unread: unreadOnly } }),
    refetchInterval: 30_000,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications", orgId] });
  const readOne = useMutation({
    mutationFn: (id: number) => api(`notifications/${id}/read`, { method: "POST" }),
    onSuccess: refresh,
  });
  const readAll = useMutation({
    mutationFn: () => api("notifications/read-all", { method: "POST" }),
    onSuccess: refresh,
  });

  const unread = (list.data ?? []).filter((n) => !n.read_at).length;

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("notif.title")}</h1>
          <p className="page-sub">{t("notif.sub")}</p>
        </div>
        <button type="button" className="btn btn-outline" disabled={readAll.isPending || unread === 0} onClick={() => readAll.mutate()}>
          {t("notif.readAll")}
        </button>
      </div>

      <section className="card">
        <label className="check">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> {t("notif.unreadOnly")}
        </label>
        {list.isPending && <p className="muted">{t("common.loading")}</p>}
        {list.isError && (
          <div className="alert alert-error" role="alert">
            {tError(list.error)}{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => list.refetch()}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {list.data && list.data.length === 0 && <p className="empty">{t("notif.empty")}</p>}
        {list.data && list.data.length > 0 && (
          <ul className="notif-list">
            {list.data.map((n) => (
              <li key={n.id} className={n.read_at ? "notif" : "notif notif-unread"}>
                <div className="grow">
                  <strong>{n.title}</strong>
                  <p style={{ margin: "4px 0" }}>{n.body}</p>
                  <small className="muted">{formatDateTime(n.created_at, lang, membership.timezone)}</small>
                  {n.request_id && role !== "technician" && (
                    <>
                      {" "}
                      <Link href={`/app/requests/${n.request_id}`}>#{n.request_id}</Link>
                    </>
                  )}
                </div>
                {!n.read_at && (
                  <button type="button" className="btn btn-outline btn-sm" disabled={readOne.isPending} onClick={() => readOne.mutate(n.id)}>
                    {t("notif.markRead")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

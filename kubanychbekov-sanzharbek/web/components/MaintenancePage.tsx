"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { Asset, AssetSummary, Category, MaintenancePlan, Priority } from "@/lib/types";
import { PRIORITIES } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** Preventive maintenance plans (PM-*) with last/next service per asset (ASSET-05). */
export function MaintenancePage() {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const admin = role === "admin";
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    asset_id: "",
    category_id: "",
    title: "",
    description: "",
    priority: "NORMAL" as Priority,
    frequency: "WEEKLY",
    first_date: new Date().toISOString().slice(0, 10),
  });

  const plans = useQuery({
    queryKey: ["plans", orgId],
    queryFn: () => api<MaintenancePlan[]>("maintenance-plans"),
    enabled: staff,
  });
  const assets = useQuery({ queryKey: ["assets", orgId, "all"], queryFn: () => api<Asset[]>("assets"), enabled: staff });
  const categories = useQuery({ queryKey: ["categories", orgId], queryFn: () => api<Category[]>("categories"), enabled: staff });
  const summary = useQuery({
    queryKey: ["asset-summaries", orgId, (plans.data ?? []).map((p) => p.asset_id).join(",")],
    enabled: staff && !!plans.data,
    queryFn: async () => {
      const ids = [...new Set((plans.data ?? []).map((p) => p.asset_id))];
      const rows = await Promise.all(ids.map((id) => api<AssetSummary>(`assets/${id}/summary`)));
      return new Map(rows.map((row) => [row.asset_id, row]));
    },
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["plans", orgId] });

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<MaintenancePlan>("maintenance-plans", { method: "POST", body }),
    onSuccess: async () => {
      setAdding(false);
      await refresh();
    },
  });
  const disable = useMutation({
    mutationFn: (id: number) => api<MaintenancePlan>(`maintenance-plans/${id}/disable`, { method: "POST" }),
    onSuccess: refresh,
  });
  const generate = useMutation({
    mutationFn: () =>
      api<{ created_requests: number; skipped_existing: number }>("maintenance/generate", { method: "POST", body: {} }),
    onSuccess: async (result) => {
      setMessage(t("plans.generated", { created: String(result.created_requests), skipped: String(result.skipped_existing) }));
      await Promise.all([
        refresh(),
        queryClient.invalidateQueries({ queryKey: ["requests", orgId] }),
        queryClient.invalidateQueries({ queryKey: ["asset-summaries", orgId] }),
      ]);
    },
  });

  if (!staff) return <div className="alert">{t("plans.onlyStaff")}</div>;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft.asset_id || !draft.category_id || draft.title.trim().length < 5) {
      setFormError(t("plans.invalid"));
      return;
    }
    setFormError(null);
    create.mutate({
      ...draft,
      asset_id: Number(draft.asset_id),
      category_id: Number(draft.category_id),
      title: draft.title.trim(),
    });
  }

  const day = (iso: string | null | undefined) => (iso ? formatDateTime(iso, lang, membership.timezone).split(",")[0] : "-");

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("plans.title")}</h1>
          <p className="page-sub">{t("plans.sub")}</p>
        </div>
        <button type="button" className="btn btn-outline" disabled={generate.isPending} onClick={() => generate.mutate()}>
          {t("plans.generate")}
        </button>
        {admin && (
          <button type="button" className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            {t("plans.add")}
          </button>
        )}
      </div>

      {message && (
        <div className="alert" role="status">
          {message}
        </div>
      )}
      {generate.isError && (
        <div className="alert alert-error" role="alert">
          {tError(generate.error)}
        </div>
      )}

      {admin && adding && (
        <form className="card" onSubmit={submit} style={{ marginBottom: 14 }}>
          <h2>{t("plans.add")}</h2>
          {(formError || create.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(create.error)}
            </div>
          )}
          <div className="form-row">
            <div className="field">
              <label htmlFor="pl-asset">{t("plans.asset")}</label>
              <select id="pl-asset" className="select" value={draft.asset_id} onChange={(e) => setDraft({ ...draft, asset_id: e.target.value })}>
                <option value="">-</option>
                {assets.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="pl-cat">{t("req.col.category")}</label>
              <select id="pl-cat" className="select" value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}>
                <option value="">-</option>
                {categories.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="pl-title">{t("req.col.title")}</label>
              <input id="pl-title" className="input" value={draft.title} maxLength={120} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pl-prio">{t("req.col.priority")}</label>
              <select id="pl-prio" className="select" value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: e.target.value as Priority })}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {t(`priority.${p}`)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="pl-freq">{t("plans.frequency")}</label>
              <select id="pl-freq" className="select" value={draft.frequency} onChange={(e) => setDraft({ ...draft, frequency: e.target.value })}>
                <option value="WEEKLY">{t("plans.WEEKLY")}</option>
                <option value="MONTHLY">{t("plans.MONTHLY")}</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="pl-first">{t("plans.first")}</label>
              <input id="pl-first" className="input" type="date" value={draft.first_date} onChange={(e) => setDraft({ ...draft, first_date: e.target.value })} />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {t("common.confirm")}
          </button>
        </form>
      )}

      <section className="card">
        {plans.isPending && <p className="muted">{t("common.loading")}</p>}
        {plans.isError && (
          <div className="alert alert-error" role="alert">
            {tError(plans.error)}
          </div>
        )}
        {plans.data && plans.data.length === 0 && <p className="empty">{t("plans.empty")}</p>}
        {plans.data && plans.data.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("req.col.title")}</th>
                  <th>{t("plans.asset")}</th>
                  <th>{t("plans.frequency")}</th>
                  <th>{t("plans.next")}</th>
                  <th>{t("plans.last")}</th>
                  <th>{t("plans.open")}</th>
                  <th>{t("plans.generatedCount")}</th>
                  {admin && <th />}
                </tr>
              </thead>
              <tbody>
                {plans.data.map((plan) => {
                  const info = summary.data?.get(plan.asset_id);
                  return (
                    <tr key={plan.id}>
                      <td>
                        {plan.title}
                        {!plan.is_active && <small className="muted block">{t("plans.disabled")}</small>}
                      </td>
                      <td>{plan.asset_name}</td>
                      <td>{t(`plans.${plan.frequency}`)}</td>
                      <td>{plan.is_active ? day(plan.next_date) : "-"}</td>
                      <td>{day(info?.last_completed_at)}</td>
                      <td>
                        {info ? (
                          info.open_requests > 0 ? (
                            <Link href="/app/requests">{info.open_requests}</Link>
                          ) : (
                            0
                          )
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>{plan.generated_count}</td>
                      {admin && (
                        <td>
                          {plan.is_active && (
                            <button type="button" className="btn btn-outline btn-sm" disabled={disable.isPending} onClick={() => disable.mutate(plan.id)}>
                              {t("plans.disable")}
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

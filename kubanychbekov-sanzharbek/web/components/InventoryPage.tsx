"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { formatKgs, parseKgsToCents, parseQuantityMilli, trimQuantity } from "@/lib/money";
import type { InventoryItem } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** Parts stock with a low-stock marker (INV-*). Dispatchers/admins see it; only admins add or replenish. */
export function InventoryPage() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const admin = role === "admin";
  const [onlyLow, setOnlyLow] = useState(false);
  const [target, setTarget] = useState<InventoryItem | null>(null);
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ code: "", name: "", unit: "pcs", stock: "0", threshold: "0", price: "0" });

  const items = useQuery({
    queryKey: ["inventory", orgId],
    queryFn: () => api<InventoryItem[]>("inventory"),
    enabled: staff,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["inventory", orgId] });

  const replenish = useMutation({
    mutationFn: (input: { id: number; quantity: string; reason: string }) =>
      api<InventoryItem>(`inventory/${input.id}/replenish`, {
        method: "POST",
        body: { quantity: input.quantity, reason: input.reason },
      }),
    onSuccess: async () => {
      setTarget(null);
      setQty("");
      setReason("");
      await refresh();
    },
  });

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<InventoryItem>("inventory", { method: "POST", body }),
    onSuccess: async () => {
      setAdding(false);
      setDraft({ code: "", name: "", unit: "pcs", stock: "0", threshold: "0", price: "0" });
      await refresh();
    },
  });

  if (!staff) return <div className="alert">{t("inventory.onlyStaff")}</div>;

  const shown = (items.data ?? []).filter((item) => !onlyLow || item.low_stock);
  const lowCount = (items.data ?? []).filter((item) => item.low_stock).length;

  function submitReplenish(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    const milli = parseQuantityMilli(qty);
    if (milli === null || milli <= 0 || !reason.trim()) {
      setFormError(t("inventory.invalidReplenish"));
      return;
    }
    setFormError(null);
    replenish.mutate({ id: target.id, quantity: qty.replace(",", "."), reason: reason.trim() });
  }

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    const price = parseKgsToCents(draft.price);
    const stock = parseQuantityMilli(draft.stock);
    const threshold = parseQuantityMilli(draft.threshold);
    if (!draft.code.trim() || !draft.name.trim() || price === null || stock === null || threshold === null) {
      setFormError(t("inventory.invalidItem"));
      return;
    }
    setFormError(null);
    create.mutate({
      code: draft.code.trim(),
      name: draft.name.trim(),
      unit: draft.unit.trim() || "pcs",
      stock: draft.stock.replace(",", "."),
      reorder_threshold: draft.threshold.replace(",", "."),
      unit_price_cents: price,
    });
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("inventory.title")}</h1>
          <p className="page-sub">{t("inventory.sub")}</p>
        </div>
        {admin && (
          <button type="button" className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            {t("inventory.add")}
          </button>
        )}
      </div>

      {admin && adding && (
        <form className="card" onSubmit={submitCreate} style={{ marginBottom: 14 }}>
          <h2>{t("inventory.add")}</h2>
          {formError && (
            <div className="alert alert-error" role="alert">
              {formError}
            </div>
          )}
          {create.isError && (
            <div className="alert alert-error" role="alert">
              {tError(create.error)}
            </div>
          )}
          <div className="form-row">
            {(
              [
                ["code", "inventory.code"],
                ["name", "inventory.name"],
                ["unit", "inventory.unit"],
                ["stock", "inventory.stock"],
                ["threshold", "inventory.threshold"],
                ["price", "inventory.price"],
              ] as const
            ).map(([key, label]) => (
              <div className="field" key={key}>
                <label htmlFor={`inv-${key}`}>{t(label)}</label>
                <input
                  id={`inv-${key}`}
                  className="input"
                  value={draft[key]}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                />
              </div>
            ))}
          </div>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {t("common.confirm")}
          </button>
        </form>
      )}

      <section className="card">
        <label className="check">
          <input type="checkbox" checked={onlyLow} onChange={(e) => setOnlyLow(e.target.checked)} />{" "}
          {t("inventory.onlyLow", { count: String(lowCount) })}
        </label>
        {items.isPending && <p className="muted">{t("common.loading")}</p>}
        {items.isError && (
          <div className="alert alert-error" role="alert">
            {tError(items.error)}{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => items.refetch()}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {items.data && shown.length === 0 && <p className="empty">{t("inventory.empty")}</p>}
        {shown.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("inventory.code")}</th>
                  <th>{t("inventory.name")}</th>
                  <th>{t("inventory.stock")}</th>
                  <th>{t("inventory.threshold")}</th>
                  <th>{t("inventory.price")}</th>
                  <th>{t("inventory.state")}</th>
                  {admin && <th />}
                </tr>
              </thead>
              <tbody>
                {shown.map((item) => (
                  <tr key={item.id}>
                    <td>{item.code}</td>
                    <td>{item.name}</td>
                    <td>
                      <strong>
                        {trimQuantity(item.stock)} {item.unit}
                      </strong>
                    </td>
                    <td>{trimQuantity(item.reorder_threshold)}</td>
                    <td>{formatKgs(item.unit_price_cents)}</td>
                    <td>
                      <span className={`badge ${item.low_stock ? "sla-OVERDUE" : "sla-ON_TRACK"}`}>
                        {item.low_stock ? t("inventory.low") : t("inventory.ok")}
                      </span>
                    </td>
                    {admin && (
                      <td>
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => {
                            setTarget(item);
                            setFormError(null);
                            replenish.reset();
                          }}
                        >
                          {t("inventory.replenish")}
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

      {admin && target && (
        <form className="card" onSubmit={submitReplenish} style={{ marginTop: 14 }}>
          <h2>{t("inventory.replenishTitle", { name: target.name })}</h2>
          {formError && (
            <div className="alert alert-error" role="alert">
              {formError}
            </div>
          )}
          {replenish.isError && (
            <div className="alert alert-error" role="alert">
              {tError(replenish.error)}
            </div>
          )}
          <div className="form-row">
            <div className="field">
              <label htmlFor="rep-qty">{t("inventory.quantity")}</label>
              <input id="rep-qty" className="input" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="rep-reason">{t("inventory.reason")}</label>
              <input
                id="rep-reason"
                className="input"
                value={reason}
                maxLength={300}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
          </div>
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={replenish.isPending}>
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setTarget(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

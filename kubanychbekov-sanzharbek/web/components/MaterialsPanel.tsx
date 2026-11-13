"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { formatKgs, trimQuantity } from "@/lib/money";
import type { MaterialUsage, ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

/** Materials written off on this request, with the price at the time of use (REQ-05, INV-05). Staff only. */
export function MaterialsPanel({ request }: { request: ServiceRequest }) {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const staff = role === "dispatcher" || role === "admin";
  const usages = useQuery({
    queryKey: ["materials", orgId, request.id],
    queryFn: () => api<MaterialUsage[]>(`requests/${request.id}/materials`),
    enabled: staff,
  });
  if (!staff) return null;
  const total = (usages.data ?? []).reduce((sum, u) => sum + u.total_cents, 0);

  return (
    <section className="card" aria-labelledby="materials-title">
      <h2 id="materials-title">{t("mat.title")}</h2>
      {usages.isError && (
        <div className="alert alert-error" role="alert">
          {tError(usages.error)}
        </div>
      )}
      {usages.data && usages.data.length === 0 && <p className="muted">{t("mat.empty")}</p>}
      {usages.data && usages.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("mat.item")}</th>
                <th>{t("mat.qty")}</th>
                <th>{t("mat.price")}</th>
                <th>{t("mat.total")}</th>
              </tr>
            </thead>
            <tbody>
              {usages.data.map((u) => (
                <tr key={u.id}>
                  <td>{u.item_name}</td>
                  <td>{trimQuantity(u.quantity)}</td>
                  <td>{formatKgs(u.unit_price_cents)}</td>
                  <td>{formatKgs(u.total_cents)}</td>
                </tr>
              ))}
              <tr>
                <td colSpan={3}>
                  <strong>{t("mat.total")}</strong>
                </td>
                <td>
                  <strong>{formatKgs(total)}</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

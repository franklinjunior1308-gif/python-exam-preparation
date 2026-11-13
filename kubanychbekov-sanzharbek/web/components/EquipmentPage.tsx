"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { formatKgs } from "@/lib/money";
import type { Asset, AssetHistoryEntry, AssetSummary, Property } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type PropertyDraft = { id: number | null; name: string; address: string; contact: string; active: boolean };
type AssetDraft = {
  id: number | null;
  property_id: string;
  code: string;
  name: string;
  asset_type: string;
  serial: string;
  installed_on: string;
  status: string;
  notes: string;
};

const NO_PROPERTY: PropertyDraft = { id: null, name: "", address: "", contact: "", active: true };
const STATUSES = ["ACTIVE", "OUT_OF_SERVICE", "RETIRED"] as const;

/** Properties and equipment with service history, open work and the next planned service (ASSET-01..05). */
export function EquipmentPage() {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const timezone = membership.timezone;
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const [propertyDraft, setPropertyDraft] = useState<PropertyDraft | null>(null);
  const [assetDraft, setAssetDraft] = useState<AssetDraft | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const properties = useQuery({
    queryKey: ["properties", orgId, "all"],
    queryFn: () => api<Property[]>("properties", { query: { include_inactive: true } }),
    enabled: staff,
  });
  const assets = useQuery({ queryKey: ["assets", orgId, "all"], queryFn: () => api<Asset[]>("assets"), enabled: staff });
  const summary = useQuery({
    queryKey: ["asset-summary", orgId, selected],
    queryFn: () => api<AssetSummary>(`assets/${selected}/summary`),
    enabled: staff && selected !== null,
  });
  const history = useQuery({
    queryKey: ["asset-history", orgId, selected],
    queryFn: () => api<AssetHistoryEntry[]>(`assets/${selected}/history`),
    enabled: staff && selected !== null,
  });

  async function refresh() {
    await Promise.all(
      ["properties", "assets", "asset-summary", "asset-history", "audit"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key, orgId] }),
      ),
    );
  }

  const saveProperty = useMutation({
    mutationFn: (d: PropertyDraft) => {
      const body = { name: d.name.trim(), address: d.address.trim(), contact_instructions: d.contact.trim() || null, is_active: d.active };
      return d.id === null
        ? api<Property>("properties", { method: "POST", body })
        : api<Property>(`properties/${d.id}`, { method: "PUT", body });
    },
    onSuccess: async () => {
      setPropertyDraft(null);
      await refresh();
    },
  });

  const saveAsset = useMutation({
    mutationFn: (d: AssetDraft) => {
      const body = {
        property_id: Number(d.property_id),
        name: d.name.trim(),
        asset_type: d.asset_type.trim(),
        serial_number: d.serial.trim() || null,
        installed_on: d.installed_on || null,
        status: d.status,
        notes: d.notes.trim() || null,
      };
      return d.id === null
        ? api<Asset>("assets", { method: "POST", body: { ...body, code: d.code.trim() } })
        : api<Asset>(`assets/${d.id}`, { method: "PUT", body });
    },
    onSuccess: async (saved) => {
      setAssetDraft(null);
      setSelected(saved.id);
      await refresh();
    },
  });

  if (!staff) return <div className="alert">{t("schedule.onlyStaff")}</div>;

  function submitProperty(event: FormEvent) {
    event.preventDefault();
    if (!propertyDraft) return;
    if (propertyDraft.name.trim().length < 2 || propertyDraft.address.trim().length < 3) {
      setFormError(t("assets.invalidProperty"));
      return;
    }
    setFormError(null);
    saveProperty.mutate(propertyDraft);
  }

  function submitAsset(event: FormEvent) {
    event.preventDefault();
    if (!assetDraft) return;
    const bad =
      !assetDraft.property_id ||
      (assetDraft.id === null && assetDraft.code.trim().length < 1) ||
      assetDraft.name.trim().length < 2 ||
      assetDraft.asset_type.trim().length < 2;
    if (bad) {
      setFormError(t("assets.invalidAsset"));
      return;
    }
    setFormError(null);
    saveAsset.mutate(assetDraft);
  }

  function openProperty(p: Property | null) {
    saveProperty.reset();
    setFormError(null);
    setAssetDraft(null);
    setPropertyDraft(
      p ? { id: p.id, name: p.name, address: p.address, contact: p.contact_instructions ?? "", active: p.is_active } : NO_PROPERTY,
    );
  }

  function openAsset(a: Asset | null) {
    saveAsset.reset();
    setFormError(null);
    setPropertyDraft(null);
    setAssetDraft(
      a
        ? {
            id: a.id,
            property_id: String(a.property_id),
            code: a.code,
            name: a.name,
            asset_type: a.asset_type,
            serial: a.serial_number ?? "",
            installed_on: a.installed_on ?? "",
            status: a.status,
            notes: a.notes ?? "",
          }
        : {
            id: null,
            property_id: String(properties.data?.find((p) => p.is_active)?.id ?? ""),
            code: "",
            name: "",
            asset_type: "",
            serial: "",
            installed_on: "",
            status: "ACTIVE",
            notes: "",
          },
    );
  }

  const propertyName = (id: number) => properties.data?.find((p) => p.id === id)?.name ?? "-";
  const retired = assetDraft?.id != null && assets.data?.find((a) => a.id === assetDraft.id)?.status === "RETIRED";

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("assets.title")}</h1>
          <p className="page-sub">{t("assets.sub")}</p>
        </div>
        <button type="button" className="btn btn-outline" onClick={() => openProperty(null)}>
          {t("assets.addProperty")}
        </button>
        <button type="button" className="btn btn-primary" onClick={() => openAsset(null)} disabled={!properties.data?.length}>
          {t("assets.addAsset")}
        </button>
      </div>

      <section className="card">
        <h2>{t("assets.properties")}</h2>
        {properties.isError && (
          <div className="alert alert-error" role="alert">
            {tError(properties.error)}
          </div>
        )}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("assets.name")}</th>
                <th>{t("assets.address")}</th>
                <th>{t("inventory.state")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(properties.data ?? []).map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.name}
                    {p.contact_instructions && <small className="muted block">{p.contact_instructions}</small>}
                  </td>
                  <td>{p.address}</td>
                  <td>{p.is_active ? t("users.active") : t("assets.inactive")}</td>
                  <td>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => openProperty(p)}>
                      {t("tech.edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card" style={{ marginTop: 14 }}>
        <h2>{t("assets.equipment")}</h2>
        {assets.isError && (
          <div className="alert alert-error" role="alert">
            {tError(assets.error)}
          </div>
        )}
        {assets.data && assets.data.length === 0 && <p className="muted">{t("assets.none")}</p>}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("assets.code")}</th>
                <th>{t("assets.name")}</th>
                <th>{t("assets.type")}</th>
                <th>{t("assets.property")}</th>
                <th>{t("inventory.state")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(assets.data ?? []).map((a) => (
                <tr key={a.id} aria-selected={selected === a.id}>
                  <td>{a.code}</td>
                  <td>{a.name}</td>
                  <td>{a.asset_type}</td>
                  <td>{propertyName(a.property_id)}</td>
                  <td>{t(`assets.status.${a.status}` as never)}</td>
                  <td>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setSelected(a.id)}>
                      {t("assets.details")}
                    </button>{" "}
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => openAsset(a)}>
                      {t("tech.edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {propertyDraft && (
        <form className="card" onSubmit={submitProperty} style={{ marginTop: 14 }}>
          <h2>{propertyDraft.id === null ? t("assets.addProperty") : t("assets.editProperty")}</h2>
          {(formError || saveProperty.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(saveProperty.error)}
            </div>
          )}
          <div className="form-row">
            <div className="field">
              <label htmlFor="p-name">{t("assets.name")}</label>
              <input id="p-name" className="input" maxLength={200} value={propertyDraft.name} onChange={(e) => setPropertyDraft({ ...propertyDraft, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="p-address">{t("assets.address")}</label>
              <input id="p-address" className="input" maxLength={500} value={propertyDraft.address} onChange={(e) => setPropertyDraft({ ...propertyDraft, address: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="p-contact">{t("assets.contact")}</label>
            <textarea id="p-contact" className="textarea" maxLength={2000} value={propertyDraft.contact} onChange={(e) => setPropertyDraft({ ...propertyDraft, contact: e.target.value })} />
          </div>
          <label className="check">
            <input type="checkbox" checked={propertyDraft.active} onChange={(e) => setPropertyDraft({ ...propertyDraft, active: e.target.checked })} /> {t("assets.activeHint")}
          </label>
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={saveProperty.isPending}>
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setPropertyDraft(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}

      {assetDraft && (
        <form className="card" onSubmit={submitAsset} style={{ marginTop: 14 }}>
          <h2>{assetDraft.id === null ? t("assets.addAsset") : t("assets.editAsset")}</h2>
          {(formError || saveAsset.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(saveAsset.error)}
            </div>
          )}
          {retired && <div className="alert">{t("assets.retiredHint")}</div>}
          <div className="form-row">
            <div className="field">
              <label htmlFor="a-property">{t("assets.property")}</label>
              <select id="a-property" className="select" value={assetDraft.property_id} onChange={(e) => setAssetDraft({ ...assetDraft, property_id: e.target.value })}>
                {(properties.data ?? []).filter((p) => p.is_active || String(p.id) === assetDraft.property_id).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="a-code">{t("assets.code")}</label>
              <input id="a-code" className="input" maxLength={64} disabled={assetDraft.id !== null} value={assetDraft.code} onChange={(e) => setAssetDraft({ ...assetDraft, code: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="a-name">{t("assets.name")}</label>
              <input id="a-name" className="input" maxLength={200} value={assetDraft.name} onChange={(e) => setAssetDraft({ ...assetDraft, name: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <div className="field">
              <label htmlFor="a-type">{t("assets.type")}</label>
              <input id="a-type" className="input" maxLength={100} value={assetDraft.asset_type} onChange={(e) => setAssetDraft({ ...assetDraft, asset_type: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="a-serial">{t("assets.serial")}</label>
              <input id="a-serial" className="input" maxLength={100} value={assetDraft.serial} onChange={(e) => setAssetDraft({ ...assetDraft, serial: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="a-installed">{t("assets.installedOn")}</label>
              <input id="a-installed" className="input" type="date" value={assetDraft.installed_on} onChange={(e) => setAssetDraft({ ...assetDraft, installed_on: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="a-status">{t("inventory.state")}</label>
              <select id="a-status" className="select" value={assetDraft.status} disabled={retired} onChange={(e) => setAssetDraft({ ...assetDraft, status: e.target.value })}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`assets.status.${s}` as never)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="a-notes">{t("assets.notes")}</label>
            <textarea id="a-notes" className="textarea" maxLength={2000} value={assetDraft.notes} onChange={(e) => setAssetDraft({ ...assetDraft, notes: e.target.value })} />
          </div>
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={saveAsset.isPending}>
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setAssetDraft(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}

      {selected !== null && (
        <section className="card" style={{ marginTop: 14 }} aria-live="polite">
          <h2>
            {summary.data ? `${summary.data.code} - ${summary.data.name}` : t("common.loading")}
          </h2>
          {summary.data && (
            <dl className="kv">
              <dt>{t("assets.openWork")}</dt>
              <dd>{summary.data.open_requests}</dd>
              <dt>{t("assets.lastService")}</dt>
              <dd>{summary.data.last_completed_at ? formatDateTime(summary.data.last_completed_at, lang, timezone) : t("assets.noneYet")}</dd>
              <dt>{t("assets.nextService")}</dt>
              <dd>{summary.data.next_planned ?? t("assets.noneYet")}</dd>
            </dl>
          )}
          <h3>{t("assets.history")}</h3>
          {history.isError && (
            <div className="alert alert-error" role="alert">
              {tError(history.error)}
            </div>
          )}
          {history.data && history.data.length === 0 && <p className="muted">{t("assets.noHistory")}</p>}
          <ul className="list">
            {(history.data ?? []).map((h) => (
              <li key={h.request_id}>
                <strong>
                  #{h.request_id} {h.title}
                </strong>{" "}
                <span className="muted">
                  {t(`status.${h.status}` as never)} - {formatDateTime(h.completed_at ?? h.created_at, lang, timezone)}
                </span>
                <small className="muted block">
                  {t("assets.technicians")}: {h.technicians.length ? h.technicians.join(", ") : "-"}
                </small>
                {h.result && (
                  <small className="block">
                    {t("assets.result")}: {h.result}
                  </small>
                )}
                {h.materials.length > 0 && (
                  <small className="muted block">
                    {t("assets.materials")}: {h.materials.map((m) => `${m.item_name} x ${m.quantity} = ${formatKgs(m.total_cents)}`).join("; ")}
                  </small>
                )}
                {h.attachments.length > 0 && (
                  <small className="muted block">
                    {t("assets.photos")}: {h.attachments.length}
                  </small>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

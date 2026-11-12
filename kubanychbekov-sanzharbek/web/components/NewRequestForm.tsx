"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { type Asset, type Category, PRIORITIES, type Property, type ServiceRequest } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const TITLE = { min: 5, max: 120 };
const DESC = { min: 20, max: 3000 };

type Errors = Partial<Record<"title" | "description" | "category" | "property" | "window", string>>;

export function NewRequestForm() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  const categories = useQuery({ queryKey: ["categories", orgId], queryFn: () => api<Category[]>("categories") });
  const properties = useQuery({ queryKey: ["properties", orgId], queryFn: () => api<Property[]>("properties") });
  const assets = useQuery({
    queryKey: ["assets", orgId, propertyId],
    queryFn: () => api<Asset[]>("assets", { query: { property_id: propertyId } }),
    enabled: Boolean(propertyId),
  });

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<ServiceRequest>("requests", { method: "POST", body }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["requests", orgId] });
      await queryClient.invalidateQueries({ queryKey: ["summary", orgId] });
      router.push(`/app/requests/${created.id}`);
    },
  });

  if (role !== "customer") {
    return <div className="alert">{t("form.onlyCustomer")}</div>;
  }

  function validate(): Errors {
    const next: Errors = {};
    const titleLength = title.trim().length;
    const descLength = description.trim().length;
    if (titleLength < TITLE.min || titleLength > TITLE.max) next.title = t("form.err.title");
    if (descLength < DESC.min || descLength > DESC.max) next.description = t("form.err.description");
    if (!categoryId) next.category = t("form.err.category");
    if (!propertyId) next.property = t("form.err.property");
    if (start && end && new Date(end) <= new Date(start)) next.window = t("form.err.window");
    return next;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (create.isPending) return; // no double submit
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    create.mutate({
      title: title.trim(),
      description: description.trim(),
      category_id: Number(categoryId),
      property_id: Number(propertyId),
      asset_id: assetId ? Number(assetId) : null,
      priority,
      desired_start: start ? new Date(start).toISOString() : null,
      desired_end: end ? new Date(end).toISOString() : null,
    });
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("req.new")}</h1>
        </div>
        <Link href="/app/requests" className="btn btn-outline">
          {t("detail.back")}
        </Link>
      </div>

      <form className="card" style={{ maxWidth: 760 }} onSubmit={onSubmit} noValidate>
        {create.isError && (
          <div className="alert alert-error" role="alert">
            {tError(create.error)}
          </div>
        )}

        <div className="field">
          <label htmlFor="title">{t("form.title")}</label>
          <input id="title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} aria-invalid={Boolean(errors.title)} aria-describedby="title-hint" maxLength={200} />
          <span id="title-hint" className="hint">
            {t("form.titleHint")} · {t("form.counter", { n: title.trim().length, max: TITLE.max })}
          </span>
          {errors.title && <span className="field-error">{errors.title}</span>}
        </div>

        <div className="field">
          <label htmlFor="description">{t("form.description")}</label>
          <textarea id="description" className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} aria-invalid={Boolean(errors.description)} aria-describedby="desc-hint" />
          <span id="desc-hint" className="hint">
            {t("form.descriptionHint")} · {t("form.counter", { n: description.trim().length, max: DESC.max })}
          </span>
          {errors.description && <span className="field-error">{errors.description}</span>}
        </div>

        <div className="row">
          <div className="field">
            <label htmlFor="category">{t("form.category")}</label>
            <select id="category" className="select" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} aria-invalid={Boolean(errors.category)}>
              <option value="">{t("form.select")}</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {errors.category && <span className="field-error">{errors.category}</span>}
          </div>
          <div className="field">
            <label htmlFor="priority">{t("form.priority")}</label>
            <select id="priority" className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {t(`priority.${p}`)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label htmlFor="property">{t("form.property")}</label>
            <select
              id="property"
              className="select"
              value={propertyId}
              onChange={(e) => {
                setPropertyId(e.target.value);
                setAssetId("");
              }}
              aria-invalid={Boolean(errors.property)}
            >
              <option value="">{t("form.select")}</option>
              {properties.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} - {p.address}
                </option>
              ))}
            </select>
            {errors.property && <span className="field-error">{errors.property}</span>}
          </div>
          <div className="field">
            <label htmlFor="asset">{t("form.asset")}</label>
            <select id="asset" className="select" value={assetId} onChange={(e) => setAssetId(e.target.value)} disabled={!propertyId}>
              <option value="">{t("form.assetNone")}</option>
              {assets.data
                ?.filter((a) => a.status !== "RETIRED")
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} - {a.name}
                  </option>
                ))}
            </select>
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label htmlFor="start">{t("form.windowStart")}</label>
            <input id="start" className="input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="end">{t("form.windowEnd")}</label>
            <input id="end" className="input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} aria-invalid={Boolean(errors.window)} />
            {errors.window && <span className="field-error">{errors.window}</span>}
          </div>
        </div>

        <p className="hint">{t("form.noPhotos")}</p>
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {create.isPending ? t("form.submitting") : t("form.submit")}
        </button>
      </form>
    </>
  );
}

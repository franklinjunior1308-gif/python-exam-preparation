"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import {
  type Category,
  PRIORITIES,
  type Property,
  type RequestPage,
  STATUSES,
} from "@/lib/types";
import { PriorityBadge, StatusBadge } from "./Badges";
import { SlaBadge } from "./SlaBadge";
import { PlusIcon } from "./icons";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const PAGE_SIZES = [10, 20, 50];

export function RequestsView() {
  const { t, tError, lang } = useI18n();
  const { orgId, role, membership } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // The URL is the single source of truth for filters, so links and reloads keep the view.
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const pageSize = PAGE_SIZES.includes(Number(params.get("size"))) ? Number(params.get("size")) : 20;
  const status = params.get("status") ?? "";
  const priority = params.get("priority") ?? "";
  const categoryId = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const sla = params.get("sla") ?? "";
  const sortBy = params.get("sort") ?? "created_at";
  const descending = params.get("dir") !== "asc";

  function update(changes: Record<string, string | null>, resetPage = true) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    if (resetPage) next.delete("page");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`);
  }

  // Debounced search box
  const [searchText, setSearchText] = useState(q);
  const lastQ = useRef(q);
  useEffect(() => {
    if (searchText === lastQ.current) return;
    const timer = setTimeout(() => {
      lastQ.current = searchText;
      update({ q: searchText.trim() });
    }, 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText]);

  function clearFilters() {
    lastQ.current = "";
    setSearchText("");
    router.replace(pathname);
  }

  const list = useQuery({
    queryKey: ["requests", orgId, { page, pageSize, status, priority, categoryId, sla, q, sortBy, descending }],
    queryFn: () =>
      api<RequestPage>("requests", {
        query: {
          page,
          page_size: pageSize,
          status,
          priority,
          category_id: categoryId,
          sla,
          q,
          sort_by: sortBy,
          descending,
        },
      }),
  });
  const categories = useQuery({
    queryKey: ["categories", orgId],
    queryFn: () => api<Category[]>("categories"),
  });
  const properties = useQuery({
    queryKey: ["properties", orgId],
    queryFn: () => api<Property[]>("properties"),
  });

  const categoryName = new Map(categories.data?.map((c) => [c.id, c.name]));
  const propertyName = new Map(properties.data?.map((p) => [p.id, p.name]));
  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / list.data.page_size)) : 1;
  const filtered = Boolean(status || priority || categoryId || sla || q);

  function sortState(column: string): "ascending" | "descending" | undefined {
    if (sortBy !== column) return undefined;
    return descending ? "descending" : "ascending";
  }

  function sortHeader(column: string, label: string) {
    const active = sortBy === column;
    return (
      <button
        type="button"
        className="sort-btn"
        onClick={() => update({ sort: column, dir: active && descending ? "asc" : "desc" }, false)}
      >
        {label} {active ? (descending ? "▼" : "▲") : ""}
      </button>
    );
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("req.title")}</h1>
          {list.data && <p className="page-sub">{t("common.results", { n: list.data.total })}</p>}
        </div>
        {role === "customer" && (
          <Link href="/app/requests/new" className="btn btn-primary">
            <PlusIcon size={18} /> {t("req.new")}
          </Link>
        )}
      </div>

      <section className="card">
        <form className="toolbar" role="search" onSubmit={(e) => e.preventDefault()}>
          <div className="field grow">
            <label htmlFor="q">{t("common.search")}</label>
            <input
              id="q"
              className="input"
              type="search"
              value={searchText}
              placeholder={t("req.searchPlaceholder")}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="f-status">{t("req.status")}</label>
            <select id="f-status" className="select" value={status} onChange={(e) => update({ status: e.target.value })}>
              <option value="">{t("common.all")}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`status.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-priority">{t("req.priority")}</label>
            <select id="f-priority" className="select" value={priority} onChange={(e) => update({ priority: e.target.value })}>
              <option value="">{t("common.all")}</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {t(`priority.${p}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-category">{t("req.category")}</label>
            <select id="f-category" className="select" value={categoryId} onChange={(e) => update({ category: e.target.value })}>
              <option value="">{t("common.all")}</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-sla">{t("sla.filter")}</label>
            <select id="f-sla" className="select" value={sla} onChange={(e) => update({ sla: e.target.value })}>
              <option value="">{t("common.all")}</option>
              {(["ON_TRACK", "AT_RISK", "OVERDUE"] as const).map((s) => (
                <option key={s} value={s}>
                  {t(`sla.${s}`)}
                </option>
              ))}
            </select>
          </div>
          {filtered && (
            <button type="button" className="btn btn-outline" onClick={clearFilters}>
              {t("req.clear")}
            </button>
          )}
        </form>

        {list.isError && (
          <div className="alert alert-error" role="alert">
            {tError(list.error)}{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => list.refetch()}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {list.isPending && <p className="muted">{t("common.loading")}</p>}

        {list.data && list.data.items.length === 0 && (
          <p className="empty">{filtered || role !== "customer" ? t("req.empty") : t("req.emptyCustomer")}</p>
        )}

        {list.data && list.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th aria-sort={sortState("id")}>{sortHeader("id", t("req.col.id"))}</th>
                  <th>{t("req.col.title")}</th>
                  <th>{t("req.col.property")}</th>
                  <th>{t("req.col.category")}</th>
                  <th aria-sort={sortState("priority")}>{sortHeader("priority", t("req.col.priority"))}</th>
                  <th>{t("req.col.status")}</th>
                  <th>{t("req.col.sla")}</th>
                  <th aria-sort={sortState("created_at")}>{sortHeader("created_at", t("req.col.created"))}</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>
                      <Link href={`/app/requests/${r.id}`}>{r.title}</Link>
                    </td>
                    <td>{propertyName.get(r.property_id) ?? "-"}</td>
                    <td>{categoryName.get(r.category_id) ?? "-"}</td>
                    <td>
                      <PriorityBadge priority={r.priority} />
                    </td>
                    <td>
                      <StatusBadge status={r.status} />
                    </td>
                    <td>
                      <SlaBadge sla={r.sla} />
                    </td>
                    <td>{formatDateTime(r.created_at, lang, membership.timezone)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {list.data && (
          <div className="pager">
            <span>{t("common.page", { page: list.data.page, pages })}</span>
            <label>
              {t("req.pageSize")}{" "}
              <select className="select" style={{ width: "auto" }} value={pageSize} onChange={(e) => update({ size: e.target.value })}>
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <span className="buttons">
              <button type="button" className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) }, false)}>
                {t("common.previous")}
              </button>
              <button type="button" className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => update({ page: String(page + 1) }, false)}>
                {t("common.next")}
              </button>
            </span>
          </div>
        )}
      </section>
    </>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import type { Category } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type Draft = { id: number | null; name: string; description: string; duration: string; skills: string; active: boolean };
const EMPTY: Draft = { id: null, name: "", description: "", duration: "60", skills: "", active: true };

/** Service categories with required skills and default duration (ORG-03). Admin edits, dispatcher reads. */
export function CategoriesPage() {
  const { t, tError } = useI18n();
  const { orgId, role } = useSession();
  const queryClient = useQueryClient();
  const staff = role === "dispatcher" || role === "admin";
  const admin = role === "admin";
  const [draft, setDraft] = useState<Draft | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["categories", orgId, "all"],
    queryFn: () => api<Category[]>("categories", { query: { include_inactive: true } }),
    enabled: staff,
  });

  const save = useMutation({
    mutationFn: (input: Draft) => {
      const body = {
        name: input.name.trim(),
        description: input.description.trim(),
        default_duration_min: Number(input.duration),
        required_skills: input.skills.split(",").map((s) => s.trim()).filter(Boolean),
        ...(input.id === null ? {} : { is_active: input.active }),
      };
      return input.id === null
        ? api<Category>("categories", { method: "POST", body })
        : api<Category>(`categories/${input.id}`, { method: "PUT", body });
    },
    onSuccess: async () => {
      setDraft(null);
      await Promise.all(
        ["categories", "suggestions", "audit"].map((key) => queryClient.invalidateQueries({ queryKey: [key, orgId] })),
      );
    },
  });

  if (!staff) return <div className="alert">{t("schedule.onlyStaff")}</div>;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const minutes = Number(draft.duration);
    if (draft.name.trim().length < 2 || !Number.isInteger(minutes) || minutes < 5 || minutes > 480) {
      setFormError(t("categories.invalid"));
      return;
    }
    setFormError(null);
    save.mutate(draft);
  }

  function open(category: Category | null) {
    save.reset();
    setFormError(null);
    setDraft(
      category
        ? {
            id: category.id,
            name: category.name,
            description: category.description,
            duration: String(category.default_duration_min),
            skills: (category.required_skills ?? []).join(", "),
            active: category.is_active,
          }
        : EMPTY,
    );
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("categories.title")}</h1>
          <p className="page-sub">{t("categories.sub")}</p>
        </div>
        {admin && (
          <button type="button" className="btn btn-primary" onClick={() => open(null)}>
            {t("categories.add")}
          </button>
        )}
      </div>

      <section className="card">
        {list.isPending && <p className="muted">{t("common.loading")}</p>}
        {list.isError && (
          <div className="alert alert-error" role="alert">
            {tError(list.error)}
          </div>
        )}
        {list.data && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("users.name")}</th>
                  <th>{t("categories.skills")}</th>
                  <th>{t("categories.duration")}</th>
                  <th>{t("inventory.state")}</th>
                  {admin && <th />}
                </tr>
              </thead>
              <tbody>
                {list.data.map((c) => (
                  <tr key={c.id}>
                    <td>
                      {c.name}
                      {c.description && <small className="muted block">{c.description}</small>}
                    </td>
                    <td>{(c.required_skills ?? []).join(", ") || "-"}</td>
                    <td>{c.default_duration_min} {t("time.min")}</td>
                    <td>{c.is_active ? t("users.active") : t("categories.disabled")}</td>
                    {admin && (
                      <td>
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => open(c)}>
                          {t("tech.edit")}
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

      {admin && draft && (
        <form className="card" onSubmit={submit} style={{ marginTop: 14 }}>
          <h2>{draft.id === null ? t("categories.add") : t("categories.edit")}</h2>
          {(formError || save.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(save.error)}
            </div>
          )}
          <div className="form-row">
            <div className="field">
              <label htmlFor="c-name">{t("users.name")}</label>
              <input id="c-name" className="input" maxLength={120} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="c-dur">{t("categories.duration")}</label>
              <input id="c-dur" className="input" inputMode="numeric" value={draft.duration} onChange={(e) => setDraft({ ...draft, duration: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="c-skills">{t("tech.skillsHint")}</label>
              <input id="c-skills" className="input" value={draft.skills} onChange={(e) => setDraft({ ...draft, skills: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="c-desc">{t("categories.description")}</label>
            <textarea id="c-desc" className="textarea" maxLength={1000} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          </div>
          {draft.id !== null && (
            <label className="check">
              <input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} /> {t("categories.activeHint")}
            </label>
          )}
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={save.isPending}>
              {t("common.confirm")}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setDraft(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

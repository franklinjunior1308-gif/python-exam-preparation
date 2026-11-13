"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { ROLES, type AppUser, type Role } from "@/lib/types";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

const EMPTY = { email: "", full_name: "", role: "customer" as Role, password: "" };

/** Staff and roles of the organization (ORG-04): create members, change roles, deactivate. Admin only. */
export function UsersPage() {
  const { t, tError } = useI18n();
  const { orgId, role, me } = useSession();
  const queryClient = useQueryClient();
  const admin = role === "admin";
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(EMPTY);
  const [formError, setFormError] = useState<string | null>(null);

  const users = useQuery({
    queryKey: ["users", orgId],
    queryFn: () => api<AppUser[]>("users"),
    enabled: admin,
  });

  const refresh = () =>
    Promise.all(
      ["users", "technicians", "audit"].map((key) => queryClient.invalidateQueries({ queryKey: [key, orgId] })),
    );

  const create = useMutation({
    mutationFn: (body: typeof EMPTY) => api<AppUser>("users", { method: "POST", body }),
    onSuccess: async () => {
      setAdding(false);
      setDraft(EMPTY);
      await refresh();
    },
  });
  const update = useMutation({
    mutationFn: (input: { id: number; body: { role?: Role; is_active?: boolean } }) =>
      api<AppUser>(`users/${input.id}`, { method: "PUT", body: input.body }),
    onSuccess: refresh,
  });

  if (!admin) return <div className="alert">{t("settings.onlyAdmin")}</div>;

  function submit(event: FormEvent) {
    event.preventDefault();
    const strong = draft.password.length >= 10 && /[A-Za-z]/.test(draft.password) && /\d/.test(draft.password);
    if (!draft.email.includes("@") || draft.full_name.trim().length < 2 || !strong) {
      setFormError(t("users.invalid"));
      return;
    }
    setFormError(null);
    create.mutate({ ...draft, email: draft.email.trim(), full_name: draft.full_name.trim() });
  }

  return (
    <>
      <div className="topbar">
        <div className="grow">
          <h1>{t("users.title")}</h1>
          <p className="page-sub">{t("users.sub")}</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
          {t("users.add")}
        </button>
      </div>

      {adding && (
        <form className="card" onSubmit={submit} style={{ marginBottom: 14 }}>
          <h2>{t("users.add")}</h2>
          {(formError || create.isError) && (
            <div className="alert alert-error" role="alert">
              {formError ?? tError(create.error)}
            </div>
          )}
          <div className="form-row">
            <div className="field">
              <label htmlFor="u-email">{t("users.email")}</label>
              <input id="u-email" className="input" type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="u-name">{t("users.name")}</label>
              <input id="u-name" className="input" value={draft.full_name} onChange={(e) => setDraft({ ...draft, full_name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="u-role">{t("users.role")}</label>
              <select id="u-role" className="select" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`role.${r}`)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="u-pass">{t("users.password")}</label>
              <input id="u-pass" className="input" type="password" autoComplete="new-password" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
              <small className="muted">{t("users.passwordHint")}</small>
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {t("common.confirm")}
          </button>
        </form>
      )}

      <section className="card">
        {update.isError && (
          <div className="alert alert-error" role="alert">
            {tError(update.error)}
          </div>
        )}
        {users.isPending && <p className="muted">{t("common.loading")}</p>}
        {users.isError && (
          <div className="alert alert-error" role="alert">
            {tError(users.error)}
          </div>
        )}
        {users.data && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("users.name")}</th>
                  <th>{t("users.email")}</th>
                  <th>{t("users.role")}</th>
                  <th>{t("inventory.state")}</th>
                </tr>
              </thead>
              <tbody>
                {users.data.map((user) => {
                  const self = user.id === me.id;
                  return (
                    <tr key={user.id}>
                      <td>{user.full_name}</td>
                      <td>{user.email}</td>
                      <td>
                        <select
                          className="select"
                          aria-label={`${t("users.role")}: ${user.full_name}`}
                          value={user.role}
                          disabled={update.isPending}
                          onChange={(e) => update.mutate({ id: user.id, body: { role: e.target.value as Role } })}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {t(`role.${r}`)}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <label className="check">
                          <input
                            type="checkbox"
                            checked={user.is_active}
                            disabled={update.isPending || self}
                            onChange={(e) => update.mutate({ id: user.id, body: { is_active: e.target.checked } })}
                          />{" "}
                          {user.is_active ? t("users.active") : t("users.inactive")}
                        </label>
                      </td>
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

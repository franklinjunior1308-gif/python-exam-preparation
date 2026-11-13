"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import { useI18n } from "./Providers";
import { useSession } from "./Shell";

type Org = { id: number; name: string; timezone: string };

function knownZones(): string[] {
  try {
    return (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.("timeZone") ?? [];
  } catch {
    return [];
  }
}

/** Organization name and IANA time zone (ORG-01). Stored instants stay in UTC; only display and working days change. */
export function OrganizationSettings() {
  const { t, tError } = useI18n();
  const { orgId } = useSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [edited, setEdited] = useState<{ name: string; timezone: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const org = useQuery({ queryKey: ["organization", orgId], queryFn: () => api<Org>("settings/organization") });
  const form = edited ?? (org.data ? { name: org.data.name, timezone: org.data.timezone } : null);

  const save = useMutation({
    mutationFn: (body: { name: string; timezone: string }) => api<Org>("settings/organization", { method: "PUT", body }),
    onSuccess: async () => {
      setSaved(true);
      setEdited(null);
      await queryClient.invalidateQueries();
      router.refresh(); // the shell reads the organization from the server: show the new name and zone
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    if (form.name.trim().length < 2 || form.timezone.trim().length < 3) {
      setFormError(t("org.invalid"));
      return;
    }
    setFormError(null);
    setSaved(false);
    save.mutate({ name: form.name.trim(), timezone: form.timezone.trim() });
  }

  return (
    <section className="card" style={{ marginBottom: 14 }} aria-labelledby="org-title">
      <h2 id="org-title">{t("org.title")}</h2>
      <p className="muted">{t("org.hint")}</p>
      {org.isError && (
        <div className="alert alert-error" role="alert">
          {tError(org.error)}
        </div>
      )}
      {(formError || save.isError) && (
        <div className="alert alert-error" role="alert">
          {formError ?? tError(save.error)}
        </div>
      )}
      {saved && (
        <div className="alert" role="status">
          {t("org.saved")}
        </div>
      )}
      {form && (
        <form onSubmit={submit}>
          <div className="form-row">
            <div className="field">
              <label htmlFor="org-name">{t("org.name")}</label>
              <input id="org-name" className="input" maxLength={200} value={form.name} onChange={(e) => setEdited({ ...form, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="org-tz">{t("org.timezone")}</label>
              <input id="org-tz" className="input" list="org-tz-list" maxLength={64} value={form.timezone} onChange={(e) => setEdited({ ...form, timezone: e.target.value })} />
              <datalist id="org-tz-list">
                {knownZones().map((zone) => (
                  <option key={zone} value={zone} />
                ))}
              </datalist>
            </div>
          </div>
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={save.isPending}>
              {t("common.confirm")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api-client";
import type { Membership } from "@/lib/types";
import { useI18n } from "./Providers";

export function OrgPicker({ memberships }: { memberships: Membership[] }) {
  const { t, tError } = useI18n();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  async function choose(organizationId: number) {
    if (pendingId !== null) return;
    setPendingId(organizationId);
    setError(null);
    try {
      await api("select-org", { method: "POST", body: { organization_id: organizationId } });
      router.push("/app");
      router.refresh();
    } catch (err) {
      setError(tError(err));
      setPendingId(null);
    }
  }

  return (
    <>
      {error && (
        <div className="alert alert-error" role="alert" style={{ marginTop: 14 }}>
          {error}
        </div>
      )}
      <ul className="org-list">
        {memberships.map((m) => (
          <li key={m.organization_id}>
            <button
              type="button"
              className="btn btn-outline"
              disabled={pendingId !== null}
              onClick={() => choose(m.organization_id)}
            >
              <strong>{m.organization_name}</strong>
              <span className="muted">{t(`role.${m.role}`)}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

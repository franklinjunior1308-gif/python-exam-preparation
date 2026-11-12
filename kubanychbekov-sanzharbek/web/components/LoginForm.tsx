"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import type { Me } from "@/lib/types";
import { useI18n } from "./Providers";

// Demo-only accounts created by the seed command. Hidden when NEXT_PUBLIC_DEMO_LOGINS=false.
const DEMO_PASSWORD = "Demo-2345!";
const DEMO = [
  { role: "customer", email: "customer1.a@fixflow.test" },
  { role: "dispatcher", email: "dispatcher.a@fixflow.test" },
  { role: "admin", email: "admin.a@fixflow.test" },
] as const;
const SHOW_DEMO = process.env.NEXT_PUBLIC_DEMO_LOGINS !== "false";

export function LoginForm() {
  const { t, tError } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending) return; // guards against double submit (WEB-05)
    setPending(true);
    setError(null);
    try {
      await api("auth/login", { method: "POST", body: { email, password } });
      const me = await api<Me>("me");
      const [only] = me.memberships;
      if (me.memberships.length === 1 && only) {
        await api("select-org", { method: "POST", body: { organization_id: only.organization_id } });
        router.push("/app");
      } else {
        router.push("/select-org");
      }
      router.refresh();
    } catch (err) {
      setError(tError(err));
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ marginTop: 18 }} noValidate>
      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}
      <div className="field">
        <label htmlFor="email">{t("login.email")}</label>
        <input
          id="email"
          className="input"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="password">{t("login.password")}</label>
        <input
          id="password"
          className="input"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={pending}>
        {pending ? t("login.submitting") : t("login.submit")}
      </button>

      {SHOW_DEMO && (
        <section style={{ marginTop: 22 }} aria-label={t("login.demo")}>
          <p className="label">{t("login.demo")}</p>
          <ul className="demo-list">
            {DEMO.map((account) => (
              <li key={account.email}>
                <strong>{t(`role.${account.role}`)}</strong>
                <span>{account.email}</span>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                  }}
                >
                  {t("login.demoFill")}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </form>
  );
}

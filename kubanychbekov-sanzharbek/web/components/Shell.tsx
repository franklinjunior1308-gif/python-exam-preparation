"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, type FormEvent, type ReactNode, useContext, useState } from "react";
import { api } from "@/lib/api-client";
import type { Me, Membership, Role } from "@/lib/types";
import { CalendarIcon, ClockIcon, BoltIcon, HomeIcon, LayersIcon, ListIcon, LogoMark, LogoutIcon, PlusIcon, SearchIcon, WrenchIcon } from "./icons";
import { LangSwitch } from "./LangSwitch";
import { useI18n } from "./Providers";

type Session = { me: Me; membership: Membership; orgId: number; role: Role };
const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside <Shell>");
  return value;
}

export function Shell({
  me,
  membership,
  children,
}: {
  me: Me;
  membership: Membership;
  children: ReactNode;
}) {
  const { t, tError } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [switchError, setSwitchError] = useState<string | null>(null);
  const role = membership.role;

  const nav = [
    { href: "/app", label: t("nav.dashboard"), icon: <HomeIcon />, show: true },
    { href: "/app/requests", label: t("nav.requests"), icon: <ListIcon />, show: role !== "technician" },
    { href: "/app/requests/new", label: t("nav.newRequest"), icon: <PlusIcon />, show: role === "customer" },
    {
      href: "/app/schedule",
      label: t("nav.schedule"),
      icon: <CalendarIcon />,
      show: role === "dispatcher" || role === "admin",
    },
    {
      href: "/app/overdue",
      label: t("nav.overdue"),
      icon: <ClockIcon />,
      show: role === "dispatcher" || role === "admin",
    },
    {
      href: "/app/inventory",
      label: t("nav.inventory"),
      icon: <LayersIcon />,
      show: role === "dispatcher" || role === "admin",
    },
    {
      href: "/app/maintenance",
      label: t("nav.plans"),
      icon: <WrenchIcon />,
      show: role === "dispatcher" || role === "admin",
    },
    { href: "/app/notifications", label: t("nav.notifications"), icon: <BoltIcon />, show: true },
  ].filter((item) => item.show);

  function isCurrent(href: string): boolean {
    if (href === "/app") return pathname === "/app";
    if (href === "/app/requests") {
      return pathname.startsWith("/app/requests") && pathname !== "/app/requests/new";
    }
    return pathname === href;
  }

  async function switchOrg(organizationId: number) {
    setSwitchError(null);
    try {
      await api("select-org", { method: "POST", body: { organization_id: organizationId } });
      queryClient.clear(); // never show cached data of the previous organization (WEB-07)
      router.push("/app");
      router.refresh();
    } catch (error) {
      setSwitchError(tError(error));
    }
  }

  async function signOut() {
    try {
      await api("auth/logout", { method: "POST" });
    } finally {
      queryClient.clear();
      router.push("/login");
      router.refresh();
    }
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    router.push(`/app/requests${search.trim() ? `?q=${encodeURIComponent(search.trim())}` : ""}`);
  }

  return (
    <SessionContext.Provider value={{ me, membership, orgId: membership.organization_id, role }}>
      <a className="skip-link" href="#main">
        {t("common.skip")}
      </a>
      <div className="shell">
        <aside className="side">
          <Link href="/app" className="brand" aria-label="FixFlow">
            <LogoMark size={34} />
            <span>
              FixFlow
              <small>{membership.organization_name}</small>
            </span>
          </Link>

          <nav className="nav" aria-label="Main">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isCurrent(item.href) ? "page" : undefined}
              >
                {item.icon} {item.label}
              </Link>
            ))}
          </nav>

          <div className="side-bottom">
            {me.memberships.length > 1 && (
              <div className="field" style={{ margin: 0 }}>
                <label htmlFor="org-switch">{t("org.switch")}</label>
                <select
                  id="org-switch"
                  className="select"
                  value={membership.organization_id}
                  onChange={(e) => switchOrg(Number(e.target.value))}
                >
                  {me.memberships.map((m) => (
                    <option key={m.organization_id} value={m.organization_id}>
                      {m.organization_name} ({t(`role.${m.role}`)})
                    </option>
                  ))}
                </select>
                {switchError && <span className="field-error">{switchError}</span>}
              </div>
            )}
            <div className="who">
              <span className="avatar" aria-hidden="true">
                {me.full_name.slice(0, 1).toUpperCase()}
              </span>
              <span>
                <strong>{me.full_name}</strong>
                <br />
                <span className="muted">{t(`role.${role}`)}</span>
              </span>
            </div>
            <button type="button" className="btn btn-outline btn-sm" onClick={signOut}>
              <LogoutIcon size={16} /> {t("common.signOut")}
            </button>
          </div>
        </aside>

        <div className="main" id="main">
          <div className="topbar" style={{ justifyContent: "flex-end" }}>
            {role !== "technician" && (
              <form className="search" role="search" onSubmit={submitSearch}>
                <input
                  className="input"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t("req.searchPlaceholder")}
                  aria-label={t("common.search")}
                />
                <button type="submit" className="btn btn-outline" aria-label={t("common.search")}>
                  <SearchIcon size={18} />
                </button>
              </form>
            )}
            <LangSwitch />
          </div>
          {children}
        </div>
      </div>
    </SessionContext.Provider>
  );
}

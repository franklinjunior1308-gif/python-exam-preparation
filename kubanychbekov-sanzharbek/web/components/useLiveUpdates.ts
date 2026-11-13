"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

const KEYS_BY_SCOPE: Record<string, string[]> = {
  requests: ["requests", "request", "history", "summary", "overdue", "sla-totals", "feedback", "attachments", "estimates"],
  assignments: ["assignments", "schedule", "suggestions", "technicians", "requests", "request"],
  notifications: ["notifications"],
};

/**
 * Subscribes to the backend's SSE stream (through the /bff/events proxy). An event only says WHAT changed; the
 * canonical state is always refetched through the normal authorized endpoints. After a reconnect everything is
 * refetched, because events may have been missed meanwhile (API-06).
 */
export function useLiveUpdates(orgId: number): "live" | "reconnecting" {
  const queryClient = useQueryClient();
  const [state, setState] = useState<"live" | "reconnecting">("reconnecting");

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/bff/events");
    let dropped = false;

    const refetchAll = () => void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[1] === orgId });

    source.onopen = () => {
      setState("live");
      if (dropped) refetchAll(); // missed events are recovered from the canonical state
      dropped = false;
    };
    source.onerror = () => {
      dropped = true;
      setState("reconnecting");
    };
    source.addEventListener("changed", (event) => {
      let scope = "requests";
      try {
        scope = (JSON.parse((event as MessageEvent<string>).data) as { scope?: string }).scope ?? scope;
      } catch {
        // an unreadable event still means "something changed": refresh the request views
      }
      for (const key of KEYS_BY_SCOPE[scope] ?? KEYS_BY_SCOPE.requests ?? []) {
        void queryClient.invalidateQueries({ queryKey: [key, orgId] });
      }
    });
    return () => source.close();
  }, [orgId, queryClient]);

  return state;
}

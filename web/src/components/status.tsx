"use client";

import { createContext, useContext, type ReactNode } from "react";

import { useApi } from "@/lib/api";
import type { Status } from "@/lib/types";

interface StatusValue {
  status: Status | null;
  /** Why the status request failed, or null. */
  error: string | null;
  refresh: () => void;
}

const StatusContext = createContext<StatusValue>({
  status: null,
  error: null,
  refresh: () => undefined,
});

/** The project name, the version and whether premium is on, shared by every page. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const { data, error, reload } = useApi<Status>("/api/status");
  return (
    <StatusContext.Provider value={{ status: data, error, refresh: reload }}>
      {children}
    </StatusContext.Provider>
  );
}

export function useStatus(): StatusValue {
  return useContext(StatusContext);
}

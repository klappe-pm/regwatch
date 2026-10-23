"use client";

import { createContext, useContext, type ReactNode } from "react";

import { useApi } from "@/lib/api";
import type { Status } from "@/lib/types";

interface StatusValue {
  status: Status | null;
  refresh: () => void;
}

const StatusContext = createContext<StatusValue>({ status: null, refresh: () => undefined });

/** The project name, the version and whether premium is on, shared by every page. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const { data, reload } = useApi<Status>("/api/status");
  return (
    <StatusContext.Provider value={{ status: data, refresh: reload }}>{children}</StatusContext.Provider>
  );
}

export function useStatus(): StatusValue {
  return useContext(StatusContext);
}

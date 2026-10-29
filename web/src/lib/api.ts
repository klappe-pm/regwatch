"use client";

import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";

import { t } from "./text.ts";

/** A refusal or failure from the local server, with its short message. */
export class ApiFailure extends Error {}

async function read<T>(response: Response): Promise<T> {
  let body: unknown = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  if (!response.ok) {
    const message =
      typeof body === "object" && body !== null && "error" in body
        ? String((body as { error: unknown }).error)
        : t("global.ui.state.request-failed-status", { status: response.status });
    throw new ApiFailure(message);
  }
  return body as T;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "same-origin",
  });
  return read<T>(response);
}

export async function postJson<T>(path: string, data: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(data),
    cache: "no-store",
    credentials: "same-origin",
  });
  return read<T>(response);
}

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Load a route once, and again when ``reload`` is called. ``null`` loads nothing. */
export function useApi<T>(path: string | null): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let live = true;
    setLoading(true);
    getJson<T>(path)
      .then((value) => {
        if (live) {
          setData(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (live) setError(reason instanceof Error ? reason.message : t("global.ui.state.request-failed"));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [path, round]);

  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { data, error, loading, reload };
}

/** One query parameter of the current address; empty until the router has read the address. */
export function useQueryParam(name: string): string {
  const value = useRouter().query[name];
  return typeof value === "string" ? value : Array.isArray(value) ? (value[0] ?? "") : "";
}

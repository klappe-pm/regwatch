"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Icon } from "@/components/icon";
import {
  Button,
  CONTROL,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import type { KeyRow, Keys } from "@/lib/types";

/** Set a key. The value is sent once and the field is cleared; it is never read back. */
function SetKey({
  row,
  onDone,
  disabled,
}: {
  row: KeyRow;
  onDone: (message: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!value) return;
    const key = value;
    setValue("");
    try {
      await postJson("/api/keys/set", { source_id: row.source_id, key });
      onDone(`Stored a key for ${row.source_id}.`);
    } catch (reason) {
      onDone(reason instanceof Error ? reason.message : "The key could not be stored.");
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
      <input
        type="password"
        autoComplete="off"
        spellCheck={false}
        aria-label={`Key for ${row.source_id}`}
        placeholder="Paste the key"
        className={`${CONTROL} w-48`}
        disabled={disabled}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <Button type="submit" disabled={disabled || !value}>
        {row.where.startsWith("Stored") ? "Replace" : "Set"}
      </Button>
    </form>
  );
}

export default function KeysPage() {
  const { data, error, loading, reload } = useApi<Keys>("/api/keys");
  const [notice, setNotice] = useState<string | null>(null);

  function done(message: string) {
    setNotice(message);
    reload();
  }

  async function remove(row: KeyRow) {
    try {
      const result = await postJson<{ removed: boolean; still_in_environment: boolean }>(
        "/api/keys/remove",
        { source_id: row.source_id },
      );
      done(
        result.still_in_environment
          ? `Removed the stored key for ${row.source_id}. The environment variable ${row.key_env} still supplies one.`
          : result.removed
            ? `Removed the key for ${row.source_id}.`
            : `No key was stored for ${row.source_id}.`,
      );
    } catch (reason) {
      done(reason instanceof Error ? reason.message : "The key could not be removed.");
    }
  }

  return (
    <>
      <PageHeader
        title="Keys"
        description={
          data?.keychain_available
            ? `Keys for the sources you watch that need one, kept in ${data.keychain}. This page shows only whether a key is available, never the key.`
            : "Keys for the sources you watch that need one. This page shows only whether a key is available, never the key."
        }
      />
      {notice ? (
        <p role="status" className="mb-4 text-sm">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && data.keys.length === 0 ? (
        <EmptyState command="regwatch keys set">
          None of your sources needs a key. Sources marked Free Key or Paid in the{" "}
          <Link className="text-structure underline underline-offset-2" href="/sources/">
            catalogue
          </Link>{" "}
          appear here once you add them.
        </EmptyState>
      ) : null}
      {data && data.keys.length > 0 && !data.keychain_available ? (
        <div className="mb-4 border border-line bg-raised px-4 py-2 text-sm">
          No keychain tool was found on this computer (security on macOS, secret-tool from libsecret
          on Linux), so keys cannot be stored here. Set each key in the environment variable shown
          under its source instead, before starting <code className="font-mono">regwatch ui</code>{" "}
          or a scheduled run.
        </div>
      ) : null}
      {data && data.keys.length > 0 ? (
        <>
          <Table label="Keys">
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Key</Th>
                <Th>Set or Replace</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {data.keys.map((row) => (
                <tr key={row.source_id}>
                  <Td>
                    <span className="font-mono text-xs">{row.source_id}</span>
                    <span className="block font-mono text-xs text-muted">{row.key_env}</span>
                    {row.signup_url ? (
                      <a
                        className="text-xs text-structure underline underline-offset-2"
                        href={row.signup_url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        Get a key
                      </a>
                    ) : null}
                  </Td>
                  <Td>
                    {row.present ? (
                      <span className="inline-flex items-center gap-1 text-ok">
                        <Icon name="check_circle" size={16} />
                        {row.where}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-accent">
                        <Icon name="warning" size={16} />
                        {row.where}
                      </span>
                    )}
                  </Td>
                  <Td>
                    <SetKey row={row} onDone={done} disabled={!data.keychain_available} />
                  </Td>
                  <Td numeric>
                    {row.where.startsWith("Stored") ? (
                      <Button variant="quiet" onClick={() => remove(row)} label={`Remove the key for ${row.source_id}`}>
                        <Icon name="delete" size={18} />
                        Remove
                      </Button>
                    ) : null}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <p className="mt-2 text-sm text-muted">
            An environment variable with the name shown overrides the keychain, for a scheduled job or a
            container.
          </p>
        </>
      ) : null}
    </>
  );
}

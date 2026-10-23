"use client";

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
function SetKey({ row, onDone }: { row: KeyRow; onDone: (message: string) => void }) {
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
        className={`${CONTROL} w-56`}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <Button type="submit" disabled={!value}>
        {row.present ? "Replace" : "Set"}
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
      await postJson("/api/keys/remove", { source_id: row.source_id });
      done(`Removed the key for ${row.source_id}.`);
    } catch (reason) {
      done(reason instanceof Error ? reason.message : "The key could not be removed.");
    }
  }

  return (
    <>
      <PageHeader
        title="Keys"
        description="Keys for sources that need one are kept in your system keychain. This page shows only whether a key is stored, never the key."
      />
      {notice ? (
        <p role="status" className="mb-4 text-sm">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && !data.available ? (
        <EmptyState command={data.command}>
          The sources you watch that need a key will be listed here, each showing whether a key is
          stored, with forms to set or remove it.
        </EmptyState>
      ) : null}
      {data?.available && data.keys.length === 0 ? (
        <EmptyState>None of your sources needs a key.</EmptyState>
      ) : null}
      {data?.available && data.keys.length > 0 ? (
        <Table label="Keys">
          <thead>
            <tr>
              <Th>Source</Th>
              <Th>Environment Variable</Th>
              <Th>Key</Th>
              <Th>Set or Replace</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {data.keys.map((row) => (
              <tr key={row.source_id}>
                <Td className="font-mono text-xs">{row.source_id}</Td>
                <Td className="font-mono text-xs">{row.key_env}</Td>
                <Td>
                  {row.present ? (
                    <span className="inline-flex items-center gap-1 text-ok">
                      <Icon name="check_circle" size={16} />
                      Stored
                    </span>
                  ) : (
                    <span className="text-muted">Not set</span>
                  )}
                </Td>
                <Td>
                  <SetKey row={row} onDone={done} />
                </Td>
                <Td numeric>
                  {row.present ? (
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
      ) : null}
    </>
  );
}

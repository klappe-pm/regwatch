import Box from "@mui/material/Box";
import TableBody from "@mui/material/TableBody";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { type FormEvent, useState } from "react";

import {
  Button,
  ControlInput,
  DataTable,
  EmptyState,
  ErrorNote,
  ExternalLink,
  Icon,
  Loading,
  Notice,
  PageHeader,
  Piece,
  Sub,
  Td,
  TextLink,
  Th,
} from "@/components/ui";
import { postJson, useApi } from "@/lib/api";
import { t } from "@/lib/text";
import type { KeyRow, Keys } from "@/lib/types";

const p = (key: string, vars?: Record<string, string>) => t(`pages.keys.${key}`, vars);

/** Set a key. The value is sent once and the field is cleared; it is never read back. */
function SetKey({ row, onDone, disabled }: { row: KeyRow; onDone: (message: string) => void; disabled: boolean }) {
  const [value, setValue] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!value) return;
    const key = value;
    setValue("");
    try {
      await postJson("/api/keys/set", { source_id: row.source_id, key });
      onDone(p("messages.stored", { source: row.source_id }));
    } catch (reason) {
      onDone(reason instanceof Error ? reason.message : p("messages.store-failed"));
    }
  }

  return (
    <Box component="form" onSubmit={submit} sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 2 }}>
      <ControlInput
        type="password"
        autoComplete="off"
        inputProps={{ spellCheck: false, "aria-label": p("table.key-for", { source: row.source_id }) }}
        placeholder={p("table.paste")}
        disabled={disabled}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        sx={{ width: "180px" }}
      />
      <Button type="submit" disabled={disabled || !value}>
        {row.where.startsWith("Stored") ? p("table.replace") : p("table.set-button")}
      </Button>
    </Box>
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
      const result = await postJson<{ removed: boolean; still_in_environment: boolean }>("/api/keys/remove", { source_id: row.source_id });
      done(
        result.still_in_environment
          ? p("messages.removed-env", { source: row.source_id, env: row.key_env })
          : result.removed
            ? p("messages.removed", { source: row.source_id })
            : p("messages.none-stored", { source: row.source_id }),
      );
    } catch (reason) {
      done(reason instanceof Error ? reason.message : p("messages.remove-failed"));
    }
  }

  return (
    <>
      <PageHeader
        title={p("header.title")}
        description={data?.keychain_available ? p("header.description-keychain", { keychain: data.keychain }) : p("header.description")}
      />
      <Notice message={notice} />
      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Loading /> : null}
      {data && data.keys.length === 0 ? (
        <EmptyState command="keys-set">
          {p("empty.before")} <TextLink href="/sources/">{p("empty.link")}</TextLink> {p("empty.after")}
        </EmptyState>
      ) : null}
      {data && data.keys.length > 0 && !data.keychain_available ? (
        <Piece name="panel" modifier="panel-compact" sx={{ mb: 4 }}>
          {p("no-keychain.before")}{" "}
          <Box component="code" sx={{ typography: "mono", fontSize: "13px" }}>
            {p("no-keychain.command")}
          </Box>{" "}
          {p("no-keychain.after")}
        </Piece>
      ) : null}
      {data && data.keys.length > 0 ? (
        <>
          <DataTable label={p("table.label")}>
            <TableHead>
              <TableRow>
                <Th>{p("table.source")}</Th>
                <Th>{p("table.key")}</Th>
                <Th>{p("table.set")}</Th>
                <Th />
              </TableRow>
            </TableHead>
            <TableBody>
              {data.keys.map((row) => (
                <TableRow key={row.source_id}>
                  <Td>
                    <Box component="span" sx={{ typography: "mono", fontSize: "12px" }}>
                      {row.source_id}
                    </Box>
                    <Sub mono>{row.key_env}</Sub>
                    {row.signup_url ? (
                      <ExternalLink href={row.signup_url} small>
                        {p("table.get-key")}
                      </ExternalLink>
                    ) : null}
                  </Td>
                  <Td>
                    <Box
                      component="span"
                      sx={{ display: "inline-flex", alignItems: "center", gap: 1, color: row.present ? "var(--ds-role-tertiary)" : "var(--ds-role-error)" }}
                    >
                      <Icon name={row.present ? "check_circle" : "warning"} size={16} />
                      {row.where}
                    </Box>
                  </Td>
                  <Td>
                    <SetKey row={row} onDone={done} disabled={!data.keychain_available} />
                  </Td>
                  <Td numeric>
                    {row.where.startsWith("Stored") ? (
                      <Button variant="quiet" onClick={() => remove(row)} label={p("table.remove-label", { source: row.source_id })}>
                        <Icon name="delete" size={18} />
                        {p("table.remove")}
                      </Button>
                    ) : null}
                  </Td>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
          <Typography component="p" sx={{ mt: 2, typography: "small", color: "var(--ds-role-on-surface-variant)" }}>
            {p("table.environment")}
          </Typography>
        </>
      ) : null}
    </>
  );
}

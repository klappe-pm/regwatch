// The shared parts of the local application, built from Material UI and styled by the components
// in DESIGN.md. Every part renders through `Piece`, which tags it with data-part for the hub.
import { Part, T, type PartProps } from "@klappe/design-system";
import Box from "@mui/material/Box";
import InputBase, { type InputBaseProps } from "@mui/material/InputBase";
import NativeSelect from "@mui/material/NativeSelect";
import Stack from "@mui/material/Stack";
import SvgIcon from "@mui/material/SvgIcon";
import Table from "@mui/material/Table";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import Typography from "@mui/material/Typography";
import type { SxProps, Theme } from "@mui/material/styles";
import NextLink from "next/link";
import type { ReactNode } from "react";

import { ICON_PATHS, type IconName } from "@/lib/icons.generated";
import { SEVERITY, words } from "@/lib/labels";
import { t } from "@/lib/text";

/** A part from DESIGN.md, marked with data-part so the hub's usage scan finds it in the built pages. */
export function Piece({ name, ...rest }: PartProps) {
  return <Part name={name} data-part={name} {...rest} />;
}

/** A Material Symbols Outlined icon at weight 400, drawn inline. Decorative unless labelled. */
export function Icon({ name, size = 20, label, sx }: { name: IconName; size?: number; label?: string; sx?: SxProps<Theme> }) {
  return (
    <SvgIcon
      viewBox="0 -960 960 960"
      titleAccess={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      sx={[{ width: size, height: size, fontSize: size, flexShrink: 0 }, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
    >
      <path d={ICON_PATHS[name]} />
    </SvgIcon>
  );
}

/** A link inside the application, rendered by Material UI with Next's client navigation. */
export function TextLink({ href, children, sx }: { href: string; children: ReactNode; sx?: SxProps<Theme> }) {
  return (
    <Piece name="text-link" component={NextLink} href={href} sx={sx}>
      {children}
    </Piece>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <Piece
      name="page-header"
      component="header"
      sx={{ mb: 6, pb: 4, display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 4 }}
    >
      <Box sx={{ minWidth: 0 }}>
        <Typography component="h1" sx={{ typography: "page-title", m: 0 }}>
          {title}
        </Typography>
        {description ? (
          <Typography component="p" sx={{ mt: 1, maxWidth: "720px", color: "var(--ds-role-on-surface-variant)" }}>
            {description}
          </Typography>
        ) : null}
      </Box>
      {actions ? (
        <Stack className="no-print" direction="row" sx={{ flexWrap: "wrap", alignItems: "center", gap: 2 }}>
          {actions}
        </Stack>
      ) : null}
    </Piece>
  );
}

export function Section({ title, actions, children, id }: { title: string; actions?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <Box component="section" aria-labelledby={id} sx={{ mb: 8, minWidth: 0 }}>
      <Stack direction="row" sx={{ mb: 2, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Typography component="h2" id={id} sx={{ typography: "section-title", m: 0 }}>
          {title}
        </Typography>
        {actions}
      </Stack>
      {children}
    </Box>
  );
}

export function Command({ children }: { children: string }) {
  return (
    <Piece name="command" component="code" sx={{ fontSize: "13px" }}>
      {children}
    </Piece>
  );
}

/** What a page or a section will show, and which command fills it (a key under global.ui.commands). */
export function EmptyState({ children, command }: { children: ReactNode; command?: string }) {
  return (
    <Piece name="empty-state">
      <Typography component="p">{children}</Typography>
      {command ? (
        <Typography component="p" sx={{ mt: 2, typography: "small" }}>
          <T k="global.ui.state.filled-by" /> <Command>{t(`global.ui.commands.${command}`)}</Command>
        </Typography>
      ) : null}
    </Piece>
  );
}

/** A premium feature shown, not hidden, while premium is off. */
export function Locked({ feature, onSettings = false }: { feature: string; onSettings?: boolean }) {
  return (
    <Piece name="panel" sx={{ display: "flex", alignItems: "flex-start", gap: 2, p: 4 }}>
      <Icon name="lock" sx={{ mt: "2px", color: "var(--ds-role-on-surface-variant)" }} />
      {onSettings ? (
        <Typography component="p">
          <T k="global.ui.locked.on-settings" vars={{ feature }} />
        </Typography>
      ) : (
        <Typography component="p">
          <T k="global.ui.locked.before-link" vars={{ feature }} />{" "}
          <TextLink href="/settings/">
            <T k="global.ui.locked.link" />
          </TextLink>{" "}
          <T k="global.ui.locked.between" /> <Command>{t("global.ui.locked.command")}</Command>
          <T k="global.ui.locked.after" />
        </Typography>
      )}
    </Piece>
  );
}

/** A quiet label, such as "Generated" beside text a language model wrote. */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <Piece name="generated-tag" component="span" sx={{ display: "inline-block", fontWeight: 500 }}>
      {children}
    </Piece>
  );
}

/**
 * A preview of a newsletter or a document. The frame loads the preview route, which
 * answers with its own policy (inline styles and data: images only), and is sandboxed
 * without scripts, forms or access to this page, so nothing in it can run and this
 * page keeps inline styles out.
 */
export function Preview({ src, title }: { src: string; title: string }) {
  return (
    <Piece
      name="preview-frame"
      component="iframe"
      title={title}
      sandbox=""
      referrerPolicy="no-referrer"
      src={src}
      sx={{ display: "block", height: "70vh", minHeight: "480px", width: "100%" }}
    />
  );
}

/** A short status line after an action, read out by screen readers. */
export function Notice({ message }: { message: string | null }) {
  return message ? (
    <Typography component="p" role="status" sx={{ mb: 4, typography: "small" }}>
      {message}
    </Typography>
  ) : null;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <Piece name="error-note" role="alert" sx={{ display: "flex", alignItems: "flex-start", gap: 2 }}>
      <Icon name="error" sx={{ mt: "2px", color: "var(--ds-role-error)" }} />
      <Typography component="p">{message}</Typography>
    </Piece>
  );
}

export function Loading() {
  return (
    <Typography component="p" aria-live="polite" sx={{ color: "var(--ds-role-on-surface-variant)" }}>
      <T k="global.ui.state.loading" />
    </Typography>
  );
}

const ATTENTION = new Set(["SUSPICIOUS", "ERROR", "MISSING"]);

/** A source status. The accent marks only the states that need attention. */
export function StatusLabel({ status }: { status: string }) {
  if (!status) {
    return (
      <Box component="span" sx={{ color: "var(--ds-role-on-surface-variant)" }}>
        <T k="global.ui.state.not-checked" />
      </Box>
    );
  }
  const attention = ATTENTION.has(status);
  const flagged = status === "NEW" || status === "CHANGED";
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        typography: "small",
        fontWeight: 500,
        color: attention ? "var(--ds-role-error)" : flagged ? "var(--ds-role-primary)" : "var(--ds-role-on-surface-variant)",
      }}
    >
      {attention ? <Icon name="warning" size={16} /> : null}
      {words(status.toLowerCase())}
    </Box>
  );
}

/** A severity. The accent marks only "act now". */
export function SeverityLabel({ severity }: { severity: string }) {
  const part = severity === "act-now" ? "severity-act-now" : severity === "high" ? "severity-high" : "severity-watch";
  return (
    <Piece name={part} component="span" sx={{ display: "inline-block", whiteSpace: "nowrap" }}>
      {SEVERITY[severity] ?? severity}
    </Piece>
  );
}

export function DataTable({ children, label }: { children: ReactNode; label: string }) {
  return (
    <Piece name="data-table" component={TableContainer} sx={{ overflowX: "auto" }}>
      <Table aria-label={label} sx={{ borderCollapse: "collapse", typography: "small", textAlign: "left" }}>
        {children}
      </Table>
    </Piece>
  );
}

type Hide = "sm" | "md";
const shown = (hide?: Hide) => (hide ? { display: { xs: "none", [hide]: "table-cell" } } : {});

export function Th({ children, numeric = false, hide }: { children?: ReactNode; numeric?: boolean; hide?: Hide }) {
  return (
    <TableCell
      component="th"
      scope="col"
      sx={{
        ...shown(hide),
        whiteSpace: "nowrap",
        px: 2,
        py: 2,
        borderBottom: "1px solid var(--ds-role-outline-variant)",
        textAlign: numeric ? "right" : "left",
        color: "var(--ds-role-on-surface-variant)",
        typography: "overline",
      }}
    >
      {children}
    </TableCell>
  );
}

export function Td({
  children,
  numeric = false,
  hide,
  muted = false,
  colSpan,
  sx,
}: {
  children?: ReactNode;
  numeric?: boolean;
  hide?: Hide;
  muted?: boolean;
  colSpan?: number;
  sx?: SxProps<Theme>;
}) {
  return (
    <TableCell
      colSpan={colSpan}
      className={numeric ? "numeric" : undefined}
      sx={[
        {
          ...shown(hide),
          px: 2,
          py: 2,
          verticalAlign: "top",
          borderBottom: "1px solid var(--ds-role-outline-variant)",
          color: muted ? "var(--ds-role-on-surface-variant)" : "inherit",
          typography: "small",
          ...(numeric ? { textAlign: "right", whiteSpace: "nowrap" } : {}),
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    >
      {children}
    </TableCell>
  );
}

/** A second line under a table cell's main text. */
export function Sub({ children, mono = false }: { children: ReactNode; mono?: boolean }) {
  return (
    <Box
      component="span"
      sx={{ display: "block", typography: mono ? "mono" : "caption", fontSize: "12px", lineHeight: "16px", color: "var(--ds-role-on-surface-variant)" }}
    >
      {children}
    </Box>
  );
}

const BUTTON_PART = { primary: "button-primary", secondary: "button-secondary", quiet: "button-quiet" } as const;

export function Button({
  children,
  onClick,
  variant = "secondary",
  type = "button",
  disabled = false,
  label,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: keyof typeof BUTTON_PART;
  type?: "button" | "submit";
  disabled?: boolean;
  label?: string;
}) {
  return (
    <Piece
      name={BUTTON_PART[variant]}
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      disableElevation
      sx={{ gap: 1, minWidth: 0, "&.Mui-disabled": { opacity: 0.6, cursor: "not-allowed", color: "inherit" } }}
    >
      {children}
    </Piece>
  );
}

export function ButtonLink({ children, href, download = false }: { children: ReactNode; href: string; download?: boolean }) {
  return (
    <Piece name="button-secondary" component="a" href={href} download={download || undefined} sx={{ gap: 1, minWidth: 0 }}>
      {children}
    </Piece>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box component="label" sx={{ display: "flex", minWidth: 0, flexDirection: "column", gap: 1 }}>
      <Piece name="field-label" component="span">
        {label}
      </Piece>
      {children}
    </Box>
  );
}

const CONTROL_SX = {
  px: 2,
  "& input, & select": { p: 0, height: "28px", fontSize: "13px" },
  "&.Mui-disabled": { opacity: 0.6 },
};

/** A text box in the application's compact control style. */
export function ControlInput({ sx, ...props }: InputBaseProps) {
  return (
    <Piece
      name="control-input"
      component={InputBase}
      {...props}
      sx={[CONTROL_SX, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
    />
  );
}

export function Select({
  value,
  onChange,
  options,
  disabled = false,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
  disabled?: boolean;
  label?: string;
}) {
  return (
    <NativeSelect
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      inputProps={label ? { "aria-label": label } : undefined}
      input={<ControlInput />}
    >
      {options.map(([id, text]) => (
        <option key={id} value={id}>
          {text}
        </option>
      ))}
    </NativeSelect>
  );
}

/** Counts in one aligned row, divided by thin rules. */
export function Figures({ items }: { items: { label: string; value: ReactNode; urgent?: boolean }[] }) {
  return (
    <Piece
      name="figures"
      component="dl"
      sx={{
        mb: 8,
        mt: 0,
        display: "grid",
        gridTemplateColumns: { xs: "repeat(2, 1fr)", sm: "repeat(3, 1fr)", lg: "repeat(5, 1fr)" },
        "& > div": { borderRight: "1px solid var(--ds-role-outline-variant)", borderBottom: "1px solid var(--ds-role-outline-variant)", px: 4, py: 2 },
        "& > div:last-of-type": { gridColumn: { xs: "span 2", sm: "span 1" }, borderRight: 0 },
      }}
    >
      {items.map((item) => (
        <div key={item.label}>
          <Typography component="dt" sx={{ typography: "overline", color: "var(--ds-role-on-surface-variant)" }}>
            {item.label}
          </Typography>
          <Typography
            component="dd"
            className="numeric"
            sx={{ m: 0, typography: "figure", color: item.urgent ? "var(--ds-role-error)" : "var(--ds-role-on-surface)" }}
          >
            {item.value}
          </Typography>
        </div>
      ))}
    </Piece>
  );
}

/** Definition rows (a label and its value) laid out in two columns. */
export function Details({ rows, sx }: { rows: [ReactNode, ReactNode, boolean?][]; sx?: SxProps<Theme> }) {
  return (
    <Box
      component="dl"
      sx={[
        { m: 0, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 4, rowGap: 1, typography: "small", "& dd": { m: 0 } },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    >
      {rows.map(([term, value, mono], index) => (
        <Box key={index} sx={{ display: "contents" }}>
          <Box component="dt" sx={{ color: "var(--ds-role-on-surface-variant)" }}>
            {term}
          </Box>
          <Box component="dd" sx={mono ? { typography: "mono", fontSize: "12px", lineHeight: "20px" } : undefined}>
            {value}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

/** A link that opens an official or provider page in a new tab. */
export function ExternalLink({ href, children, small = false }: { href: string; children: ReactNode; small?: boolean }) {
  return (
    <Piece
      name="text-link"
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      sx={small ? { typography: "caption", fontSize: "12px" } : undefined}
    >
      {children}
    </Piece>
  );
}

/** Filters in one row on wide screens. */
export function FilterRow({ children, columns = 4 }: { children: ReactNode; columns?: number }) {
  return (
    <Box
      className="no-print"
      sx={{ mb: 4, display: "grid", gap: 2, gridTemplateColumns: { xs: "minmax(0, 1fr)", sm: "repeat(2, minmax(0, 1fr))", lg: `repeat(${columns}, minmax(0, 1fr))` } }}
    >
      {children}
    </Box>
  );
}

/** A row of controls that wraps on narrow screens. */
export function ControlRow({ children, end = false }: { children: ReactNode; end?: boolean }) {
  return (
    <Stack className="no-print" direction="row" sx={{ mb: 4, flexWrap: "wrap", alignItems: end ? "flex-end" : "center", gap: 2 }}>
      {children}
    </Stack>
  );
}

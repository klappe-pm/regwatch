import Link from "next/link";
import type { ReactNode } from "react";

import { SEVERITY, words } from "@/lib/labels";

import { Icon } from "./icon";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="no-print flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Section({
  title,
  actions,
  children,
  id,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section className="mb-8 min-w-0" aria-labelledby={id}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Command({ children }: { children: string }) {
  return (
    <code className="rounded-sm border border-line bg-raised px-1 font-mono text-sm">{children}</code>
  );
}

/** What a page or a section will show, and which command fills it. */
export function EmptyState({ children, command }: { children: ReactNode; command?: string }) {
  return (
    <div className="border border-dashed border-line bg-raised px-4 py-4 text-muted">
      <p>{children}</p>
      {command ? (
        <p className="mt-2 text-sm">
          Filled by <Command>{command}</Command>
        </p>
      ) : null}
    </div>
  );
}

/** A premium feature shown, not hidden, while premium is off. */
export function Locked({ feature, onSettings = false }: { feature: string; onSettings?: boolean }) {
  return (
    <div className="flex items-start gap-2 border border-line bg-raised px-4 py-4">
      <Icon name="lock" className="mt-0.5 text-muted" />
      {onSettings ? (
        <p>{feature} is a premium feature. Turn on premium features above to use it.</p>
      ) : (
        <p>
          {feature} is a premium feature. Turn premium on in{" "}
          <Link className="text-structure underline underline-offset-2" href="/settings/">
            Settings
          </Link>{" "}
          or with <Command>regwatch premium on</Command>.
        </p>
      )}
    </div>
  );
}

/** A quiet label, such as "Generated" beside text a language model wrote. */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block border border-control px-1 text-xs font-medium leading-4 text-muted">
      {children}
    </span>
  );
}

/**
 * A preview of a newsletter or a document. The HTML is shown in a frame sandboxed
 * without scripts, forms or access to this page, so nothing in it can run.
 */
export function Preview({ html, title }: { html: string; title: string }) {
  return (
    <iframe
      title={title}
      sandbox=""
      referrerPolicy="no-referrer"
      srcDoc={html}
      className="block h-[70vh] min-h-[480px] w-full border border-line bg-white"
    />
  );
}

/** A short status line after an action, read out by screen readers. */
export function Notice({ message }: { message: string | null }) {
  return message ? (
    <p role="status" className="mb-4 text-sm">
      {message}
    </p>
  ) : null;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 border border-accent bg-accent-soft px-4 py-2">
      <Icon name="error" className="mt-0.5 text-accent" />
      <p>{message}</p>
    </div>
  );
}

export function Loading() {
  return (
    <p className="text-muted" aria-live="polite">
      Loading
    </p>
  );
}

const ATTENTION = new Set(["SUSPICIOUS", "ERROR", "MISSING"]);

/** A source status. The accent marks only the states that need attention. */
export function StatusLabel({ status }: { status: string }) {
  if (!status) return <span className="text-muted">Not checked</span>;
  const attention = ATTENTION.has(status);
  const flagged = status === "NEW" || status === "CHANGED";
  return (
    <span
      className={`inline-flex items-center gap-1 text-sm font-medium ${
        attention ? "text-accent" : flagged ? "text-structure" : "text-muted"
      }`}
    >
      {attention ? <Icon name="warning" size={16} /> : null}
      {words(status.toLowerCase())}
    </span>
  );
}

/** A severity. The accent marks only "act now". */
export function SeverityLabel({ severity }: { severity: string }) {
  const urgent = severity === "act-now";
  return (
    <span
      className={`inline-block whitespace-nowrap border px-1 text-xs font-semibold uppercase tracking-wide ${
        urgent
          ? "border-accent bg-accent-soft text-accent"
          : severity === "high"
            ? "border-control text-ink"
            : "border-line text-muted"
      }`}
    >
      {SEVERITY[severity] ?? severity}
    </span>
  );
}

export function Table({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="overflow-x-auto border border-line bg-raised">
      <table className="w-full border-collapse text-left text-sm" aria-label={label}>
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  numeric = false,
  className = "",
}: {
  children?: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap border-b border-line px-2 py-2 text-xs font-semibold uppercase tracking-wide text-muted ${
        numeric ? "text-right" : ""
      } ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  numeric = false,
  className = "",
}: {
  children?: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <td
      className={`border-b border-line px-2 py-2 align-top ${
        numeric ? "numeric text-right whitespace-nowrap" : ""
      } ${className}`}
    >
      {children}
    </td>
  );
}

const BUTTON = {
  primary: "bg-structure text-on-structure border border-structure hover:opacity-90",
  secondary: "bg-raised text-ink border border-control hover:bg-selection",
  quiet: "text-structure border border-transparent hover:bg-selection",
};

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
  variant?: keyof typeof BUTTON;
  type?: "button" | "submit";
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`inline-flex h-8 items-center gap-1 rounded-sm px-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 ${BUTTON[variant]}`}
    >
      {children}
    </button>
  );
}

export function ButtonLink({
  children,
  href,
  download = false,
}: {
  children: ReactNode;
  href: string;
  download?: boolean;
}) {
  return (
    <a
      href={href}
      download={download || undefined}
      className={`inline-flex h-8 items-center gap-1 rounded-sm px-2 text-sm font-medium ${BUTTON.secondary}`}
    >
      {children}
    </a>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-sm">
      <span className="font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

export const CONTROL =
  "h-8 min-w-0 rounded-sm border border-control bg-raised px-2 text-sm text-ink disabled:opacity-60";

export function Select({
  value,
  onChange,
  options,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
  disabled?: boolean;
}) {
  return (
    <select
      className={CONTROL}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {options.map(([id, text]) => (
        <option key={id} value={id}>
          {text}
        </option>
      ))}
    </select>
  );
}

/** Counts in one aligned row, divided by thin rules. */
export function Figures({ items }: { items: { label: string; value: ReactNode; urgent?: boolean }[] }) {
  return (
    <dl className="mb-8 grid grid-cols-2 border border-line bg-raised sm:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => (
        <div
          key={item.label}
          className="border-b border-r border-line px-4 py-2 last:col-span-2 last:border-r-0 sm:last:col-span-1"
        >
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{item.label}</dt>
          <dd
            className={`numeric text-2xl font-semibold ${item.urgent ? "text-accent" : "text-ink"}`}
          >
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

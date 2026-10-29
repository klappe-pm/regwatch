"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

import { getJson } from "@/lib/api";
import type { IconName } from "@/lib/icons.generated";
import { type SearchOption, searchNote, searchOptions } from "@/lib/search-options";
import type { SearchResults } from "@/lib/types";

import { Icon } from "./icon";
import { useStatus } from "./status";
import { Brand } from "./brand";
import { isPublicPage } from "@/lib/bev-watch";

const NAV: { href: string; label: string; icon: IconName; premium?: boolean }[] = [
  { href: "/", label: "Overview", icon: "dashboard" },
  { href: "/changes/", label: "Changes", icon: "difference" },
  { href: "/sources/", label: "Sources", icon: "database" },
  { href: "/obligations/", label: "Obligations", icon: "gavel" },
  { href: "/briefings/", label: "Briefings", icon: "article" },
  { href: "/newsletters/", label: "Newsletters", icon: "mail", premium: true },
  { href: "/documents/", label: "Documents", icon: "description", premium: true },
  { href: "/automations/", label: "Automations", icon: "schedule" },
  { href: "/keys/", label: "Keys", icon: "key" },
  { href: "/settings/", label: "Settings", icon: "settings" },
];

const RAIL_KEY = "regwatch.rail";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(RAIL_KEY) === "collapsed";
  } catch {
    return false;
  }
}

function writeCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(RAIL_KEY, collapsed ? "collapsed" : "expanded");
  } catch {
    // Storage may be blocked; the rail still works for this visit.
  }
}

function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 767px)");
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return narrow;
}

/** One search over sources, changes and obligations, as a keyboard-driven combobox. */
function Search({ compact }: { compact: boolean }) {
  const router = useRouter();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setResults(null);
      setFailure(null);
      return;
    }
    let live = true;
    const timer = window.setTimeout(() => {
      getJson<SearchResults>(`/api/search?q=${encodeURIComponent(text)}`)
        .then((value) => {
          if (live) {
            setResults(value);
            setFailure(null);
            setActive(-1);
          }
        })
        .catch((reason: unknown) => {
          if (live) {
            setResults(null);
            setFailure(reason instanceof Error ? reason.message : "The request failed.");
          }
        });
    }, 150);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  const list = searchOptions(results);
  const note = searchNote(query, list.length, failure);
  const showPanel = compact ? open : open && query.trim() !== "";

  function close() {
    setOpen(false);
    setActive(-1);
  }

  function go(option: SearchOption) {
    close();
    setQuery("");
    router.push(option.href);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((value) => (list.length ? (value + 1) % list.length : -1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => (list.length ? (value - 1 + list.length) % list.length : -1));
    } else if (event.key === "Enter" && active >= 0 && list[active]) {
      event.preventDefault();
      go(list[active]);
    } else if (event.key === "Escape") {
      close();
    }
  }

  const input = (
    <div className="flex h-8 items-center gap-1 rounded-sm border border-control bg-raised px-2">
      <Icon name="search" size={18} className="text-muted" />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-label="Search sources, changes and obligations"
        aria-expanded={showPanel && list.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 && list[active] ? `${listId}-${list[active].id}` : undefined}
        placeholder="Search"
        className="w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-muted"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
    </div>
  );

  const groups = ["Sources", "Changes", "Obligations"];
  const panel = (
    <div className="absolute left-full top-0 z-30 ml-2 w-[min(28rem,calc(100vw-5rem))] border border-line bg-raised shadow-sm">
      {compact ? <div className="border-b border-line p-2">{input}</div> : null}
      <div id={listId} role="listbox" aria-label="Search results" className="max-h-[70vh] overflow-y-auto py-1">
        {note !== null ? (
          <p role={failure ? "alert" : undefined} className="px-4 py-2 text-sm text-muted">
            {note}
          </p>
        ) : (
          groups.map((group) => {
            const items = list.filter((o) => o.group === group);
            if (!items.length) return null;
            return (
              <div key={group} role="group" aria-label={group}>
                <p className="px-4 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{group}</p>
                {items.map((option) => {
                  const selected = list[active]?.id === option.id;
                  return (
                    <div
                      key={option.id}
                      id={`${listId}-${option.id}`}
                      role="option"
                      aria-selected={selected}
                      className={`cursor-pointer px-4 py-1 ${selected ? "bg-selection" : "hover:bg-selection"}`}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => go(option)}
                    >
                      <span className="block truncate text-sm text-ink">{option.text}</span>
                      <span className="block truncate text-xs text-muted">{option.detail}</span>
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close();
      }}
    >
      {compact ? (
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-sm text-ink hover:bg-selection"
          aria-label="Search sources, changes and obligations"
          aria-expanded={open}
          onClick={() => {
            setOpen((value) => !value);
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }}
        >
          <Icon name="search" />
        </button>
      ) : (
        input
      )}
      {showPanel ? panel : null}
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const narrow = useNarrow();
  const { status } = useStatus();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(readCollapsed());
  }, []);

  const compact = collapsed || narrow;

  if (isPublicPage(pathname)) return <>{children}</>;

  function toggle() {
    setCollapsed((value) => {
      writeCollapsed(!value);
      return !value;
    });
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:bg-raised focus:px-2 focus:py-1"
      >
        Skip to content
      </a>
      <nav
        aria-label="Main"
        className={`no-print fixed inset-y-0 left-0 z-20 flex flex-col border-r border-line bg-raised ${
          compact ? "w-14 items-center" : "w-60"
        }`}
      >
        <div className={`flex h-14 items-center border-b border-line ${compact ? "justify-center" : "px-4"}`}>
          {compact ? (
            <Brand compact/>
          ) : (
            <div className="min-w-0">
              <Brand/>
              <p className="truncate text-xs text-muted">{status ? status.project : " "}</p>
            </div>
          )}
        </div>
        <div className={compact ? "py-2" : "p-2"}>
          <Search compact={compact} />
        </div>
        <ul className={`flex-1 overflow-y-auto ${compact ? "w-full px-1" : "px-2"}`}>
          {NAV.map((item) => {
            const current = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const locked = item.premium && status !== null && !status.premium;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  title={compact ? item.label : undefined}
                  aria-label={compact ? `${item.label}${locked ? " (premium)" : ""}` : undefined}
                  className={`my-0.5 flex h-10 items-center gap-2 rounded-sm text-sm ${
                    compact ? "justify-center" : "px-2"
                  } ${
                    current
                      ? "bg-selection font-semibold text-structure"
                      : "text-ink hover:bg-selection"
                  }`}
                >
                  <Icon name={item.icon} />
                  {compact ? null : <span className="flex-1">{item.label}</span>}
                  {!compact && locked ? <Icon name="lock" size={16} label="Premium" className="text-muted" /> : null}
                </Link>
              </li>
            );
          })}
        </ul>
        {narrow ? null : (
          <div className={`border-t border-line ${compact ? "py-2" : "p-2"}`}>
            <button
              type="button"
              onClick={toggle}
              aria-expanded={!collapsed}
              aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
              title={collapsed ? "Expand navigation" : "Collapse navigation"}
              className={`flex h-10 items-center gap-2 rounded-sm text-sm text-muted hover:bg-selection ${
                compact ? "w-10 justify-center" : "w-full px-2"
              }`}
            >
              <Icon name={collapsed ? "left_panel_open" : "left_panel_close"} />
              {compact ? null : <span>Collapse</span>}
            </button>
          </div>
        )}
      </nav>
      <main id="main" className={`min-w-0 px-4 py-6 md:px-8 ${compact ? "ml-14" : "ml-60"}`}>
        <div className="mx-auto max-w-6xl">
          {children}
          <p className="mt-12 border-t border-line pt-4 text-xs text-muted">
            Bev Watch flags candidates for human review. It is not legal advice.
            {status ? ` Version ${status.version}.` : ""}
          </p>
        </div>
      </main>
    </div>
  );
}

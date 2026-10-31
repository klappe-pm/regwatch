"use client";

import { T } from "@klappe/design-system";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import InputBase from "@mui/material/InputBase";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import useMediaQuery from "@mui/material/useMediaQuery";
import NextLink from "next/link";
import { useRouter } from "next/router";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

import { getJson } from "@/lib/api";
import { isPublicPage } from "@/lib/bev-watch";
import type { IconName } from "@/lib/icons.generated";
import { SEARCH_GROUPS, type SearchOption, searchGroupName, searchNote, searchOptions } from "@/lib/search-options";
import { t } from "@/lib/text";
import type { SearchResults } from "@/lib/types";

import { Brand } from "./brand";
import { useStatus } from "./status";
import { Icon, Piece } from "./ui";

const NAV: { href: string; key: string; icon: IconName; premium?: boolean }[] = [
  { href: "/", key: "overview", icon: "dashboard" },
  { href: "/changes/", key: "changes", icon: "difference" },
  { href: "/sources/", key: "sources", icon: "database" },
  { href: "/obligations/", key: "obligations", icon: "gavel" },
  { href: "/briefings/", key: "briefings", icon: "article" },
  { href: "/newsletters/", key: "newsletters", icon: "mail", premium: true },
  { href: "/documents/", key: "documents", icon: "description", premium: true },
  { href: "/automations/", key: "automations", icon: "schedule" },
  { href: "/keys/", key: "keys", icon: "key" },
  { href: "/settings/", key: "settings", icon: "settings" },
];

const RAIL_KEY = "regwatch.rail";
const muted = "var(--ds-role-on-surface-variant)";
const selection = "var(--ds-role-secondary-container)";

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
            setFailure(reason instanceof Error ? reason.message : t("global.ui.state.request-failed"));
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
    void router.push(option.href);
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
    <Piece name="control-input" sx={{ display: "flex", height: "30px", alignItems: "center", gap: 1 }}>
      <Icon name="search" size={18} sx={{ color: muted }} />
      <InputBase
        inputRef={inputRef}
        type="search"
        placeholder={t("global.shell.search.placeholder")}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        inputProps={{
          role: "combobox",
          "aria-label": t("global.shell.search.label"),
          "aria-expanded": showPanel && list.length > 0,
          "aria-controls": listId,
          "aria-autocomplete": "list",
          "aria-activedescendant": active >= 0 && list[active] ? `${listId}-${list[active].id}` : undefined,
        }}
        sx={{ width: "100%", minWidth: 0, fontSize: "13px", color: "inherit", "& input": { p: 0, "&::placeholder": { color: muted, opacity: 1 } } }}
      />
    </Piece>
  );

  const panel = (
    <Piece
      name="search-panel"
      sx={{ position: "absolute", left: "100%", top: 0, zIndex: 30, ml: 2, width: "min(28rem, calc(100vw - 5rem))" }}
    >
      {compact ? <Box sx={{ borderBottom: "1px solid var(--ds-role-outline-variant)", p: 2 }}>{input}</Box> : null}
      <Box id={listId} role="listbox" aria-label={t("global.shell.search.results")} sx={{ maxHeight: "70vh", overflowY: "auto", py: 1 }}>
        {note !== null ? (
          <Typography component="p" role={failure ? "alert" : undefined} sx={{ px: 4, py: 2, typography: "small", color: muted }}>
            {note}
          </Typography>
        ) : (
          SEARCH_GROUPS.map((group) => {
            const items = list.filter((o) => o.group === group);
            if (!items.length) return null;
            const name = searchGroupName(group);
            return (
              <div key={group} role="group" aria-label={name}>
                <Typography component="p" sx={{ px: 4, pt: 2, typography: "overline", color: muted }}>
                  {name}
                </Typography>
                {items.map((option) => {
                  const selected = list[active]?.id === option.id;
                  return (
                    <Box
                      key={option.id}
                      id={`${listId}-${option.id}`}
                      role="option"
                      aria-selected={selected}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => go(option)}
                      sx={{ cursor: "pointer", px: 4, py: 1, bgcolor: selected ? selection : "transparent", "&:hover": { bgcolor: selection } }}
                    >
                      <Box component="span" sx={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", typography: "small" }}>
                        {option.text}
                      </Box>
                      <Box component="span" sx={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", typography: "caption", color: muted }}>
                        {option.detail}
                      </Box>
                    </Box>
                  );
                })}
              </div>
            );
          })
        )}
      </Box>
    </Piece>
  );

  return (
    <Box
      sx={{ position: "relative" }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close();
      }}
    >
      {compact ? (
        <ButtonBase
          aria-label={t("global.shell.search.label")}
          aria-expanded={open}
          onClick={() => {
            setOpen((value) => !value);
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }}
          sx={{ display: "flex", height: "37.5px", width: "37.5px", borderRadius: 1, "&:hover": { bgcolor: selection } }}
        >
          <Icon name="search" />
        </ButtonBase>
      ) : (
        input
      )}
      {showPanel ? panel : null}
    </Box>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useRouter();
  const narrow = useMediaQuery("(max-width: 767px)", { noSsr: false });
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

  const rail = compact ? "var(--ds-space-rail-compact)" : "var(--ds-space-rail)";

  return (
    <Box sx={{ minHeight: "100vh" }}>
      <Link
        href="#main"
        sx={{
          position: "absolute",
          width: "1px",
          height: "1px",
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          "&:focus": { position: "fixed", left: "7.5px", top: "7.5px", zIndex: 50, width: "auto", height: "auto", clip: "auto", px: 2, py: 1, bgcolor: "var(--ds-role-surface-container-lowest)" },
        }}
      >
        <T k="global.shell.nav.skip" />
      </Link>
      <Piece
        name="nav-rail"
        component="nav"
        aria-label={t("global.shell.nav.label")}
        className="no-print"
        sx={{ position: "fixed", top: 0, bottom: 0, left: 0, zIndex: 20, display: "flex", flexDirection: "column", width: rail, alignItems: compact ? "center" : "stretch" }}
      >
        <Box
          sx={{
            display: "flex",
            height: "52.5px",
            flexShrink: 0,
            alignItems: "center",
            borderBottom: "1px solid var(--ds-role-outline-variant)",
            width: "100%",
            ...(compact ? { justifyContent: "center" } : { px: 4 }),
          }}
        >
          {compact ? (
            <Brand compact local />
          ) : (
            <Box sx={{ minWidth: 0 }}>
              <Brand local />
              <Typography component="p" sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", typography: "caption", color: muted }}>
                {status ? status.project : " "}
              </Typography>
            </Box>
          )}
        </Box>
        <Box sx={compact ? { py: 2 } : { p: 2 }}>
          <Search compact={compact} />
        </Box>
        <Box component="ul" sx={{ m: 0, listStyle: "none", flex: 1, overflowY: "auto", width: "100%", px: compact ? 1 : 2 }}>
          {NAV.map((item) => {
            const current = item.href === "/" ? pathname === "/" || pathname === "/overview" : pathname.startsWith(item.href.slice(0, -1));
            const locked = item.premium && status !== null && !status.premium;
            const text = t(`global.shell.nav.${item.key}`);
            return (
              <li key={item.href}>
                <Piece
                  name="nav-link"
                  modifier={compact ? "nav-link-compact" : undefined}
                  component={NextLink}
                  href={item.href}
                  selected={current}
                  aria-current={current ? "page" : undefined}
                  title={compact ? text : undefined}
                  aria-label={compact ? (locked ? t("global.ui.locked.premium-suffix", { label: text }) : text) : undefined}
                  sx={{ my: "1.875px", gap: 2, justifyContent: compact ? "center" : "flex-start" }}
                >
                  <Icon name={item.icon} />
                  {compact ? null : <Box component="span" sx={{ flex: 1 }}>{text}</Box>}
                  {!compact && locked ? <Icon name="lock" size={16} label={t("global.ui.locked.premium")} sx={{ color: muted }} /> : null}
                </Piece>
              </li>
            );
          })}
        </Box>
        {narrow ? null : (
          <Box sx={{ borderTop: "1px solid var(--ds-role-outline-variant)", width: "100%", ...(compact ? { py: 2, display: "flex", justifyContent: "center" } : { p: 2 }) }}>
            <ButtonBase
              onClick={toggle}
              aria-expanded={!collapsed}
              aria-label={t(collapsed ? "global.shell.nav.expand-label" : "global.shell.nav.collapse-label")}
              title={t(collapsed ? "global.shell.nav.expand-label" : "global.shell.nav.collapse-label")}
              sx={{
                display: "flex",
                height: "37.5px",
                alignItems: "center",
                gap: 2,
                borderRadius: 1,
                typography: "small",
                color: muted,
                "&:hover": { bgcolor: selection },
                ...(compact ? { width: "37.5px", justifyContent: "center" } : { width: "100%", px: 2, justifyContent: "flex-start" }),
              }}
            >
              <Icon name={collapsed ? "left_panel_open" : "left_panel_close"} />
              {compact ? null : <span>{t("global.shell.nav.collapse")}</span>}
            </ButtonBase>
          </Box>
        )}
      </Piece>
      <Box component="main" id="main" sx={{ minWidth: 0, px: { xs: 4, md: 8 }, py: 6, ml: rail }}>
        <Box sx={{ mx: "auto", maxWidth: "var(--ds-space-content)" }}>
          {children}
          <Typography
            component="p"
            sx={{ mt: 12, borderTop: "1px solid var(--ds-role-outline-variant)", pt: 4, typography: "caption", color: muted }}
          >
            <T k="global.ui.footer.disclaimer" />
            {status ? ` ${t("global.ui.footer.version", { version: status.version })}` : ""}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

import Box from "@mui/material/Box";
import NextLink from "next/link";
import { useRouter } from "next/router";
import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { Brand } from "@/components/brand";
import {
  ActionButton,
  Arrow,
  Choice,
  FeatureList,
  Meta,
  PublicError,
  PublicField,
  PublicFrame,
  PublicInput,
  PublicNote,
  PublicNotice,
  PublicSelect,
  PublicTag,
  TextAction,
  c,
  srOnly,
} from "@/components/public";
import { Icon, Piece } from "@/components/ui";
import {
  CATEGORIES,
  MARKETS,
  SAMPLE_UPDATES,
  SOURCES,
  WORKSPACE_STORAGE,
  briefingText,
  categoryName,
  downloadText,
  emptyWorkspace,
  loadWorkspace,
  marketName,
  parseWorkspace,
  restoreProduct,
  saveWorkspace,
  toggleValue,
  type Product,
  type Workspace,
} from "@/lib/bev-watch";
import type { IconName } from "@/lib/icons.generated";
import { t } from "@/lib/text";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.workspace.${key}`, vars);
const muted = { color: c("bw-muted") };
const line = `1px solid ${c("bw-line")}`;
const cadenceName = (value: Workspace["cadence"]) => t(`pages.onboarding.fields.${value.toLowerCase()}`);

const NAV: { id: string; icon: IconName }[] = [
  { id: "overview", icon: "dashboard" },
  { id: "updates", icon: "difference" },
  { id: "portfolio", icon: "description" },
  { id: "sources", icon: "database" },
  { id: "briefings", icon: "article" },
  { id: "membership", icon: "lock" },
  { id: "settings", icon: "settings" },
];

function Heading({ level = 2, size, children, sx }: { level?: 1 | 2 | 3; size: string; children: ReactNode; sx?: object }) {
  return (
    <Box component={`h${level}`} sx={{ fontSize: size, fontWeight: 600, ...sx }}>
      {children}
    </Box>
  );
}

/** A centred empty state with an optional icon. */
function Empty({ icon, title, body, children, level = 2 }: { icon?: IconName; title: string; body?: string; children?: ReactNode; level?: 2 | 3 }) {
  return (
    <Box sx={{ textAlign: "center", py: "55px", px: "20px", "& a": { color: c("tag-ink"), fontSize: "13px", textDecoration: "underline" } }}>
      {icon ? <Icon name={icon} size={icon === "check_circle" ? 32 : 38} sx={{ mx: "auto", display: "block", color: c("empty-icon") }} /> : null}
      <Heading level={level} size="22px" sx={{ fontWeight: 550, mt: "18px" }}>
        {title}
      </Heading>
      {body ? (
        <Box component="p" sx={{ fontSize: "14px", mx: "auto", mt: "12px", mb: "22px", ...muted }}>
          {body}
        </Box>
      ) : null}
      {children}
    </Box>
  );
}

function Actions({ children, sx }: { children: ReactNode; sx?: object }) {
  return <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "22px", "@media (max-width: 540px)": { gap: "18px" }, ...sx }}>{children}</Box>;
}

function ProductForm({ initial, markets, onSave, onCancel }: { initial?: Product; markets: string[]; onSave: (p: Product) => void; onCancel: () => void }) {
  const [name, setName] = useState(initial?.name || "");
  const [category, setCategory] = useState(initial?.category || CATEGORIES[0]);
  const [ingredients, setIngredients] = useState(initial?.ingredients || "");
  const [selected, setSelected] = useState(initial?.markets || markets);
  const [error, setError] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !selected.length) {
      setError(p("portfolio.required"));
      return;
    }
    onSave({ id: initial?.id || crypto.randomUUID(), name: name.trim(), category, ingredients: ingredients.trim(), markets: selected });
  }
  return (
    <Box
      component="form"
      onSubmit={submit}
      sx={{ bgcolor: c("white"), p: "28px", border: line, borderRadius: "10px", mb: "30px", "@media (max-width: 540px)": { p: "20px" } }}
    >
      <Heading size="21px" sx={{ mb: "24px" }}>
        {initial ? p("portfolio.edit") : p("portfolio.add-first")}
      </Heading>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: "20px", "@media (max-width: 540px)": { gridTemplateColumns: "1fr" } }}>
        <PublicField label={p("portfolio.name")}>
          <PublicInput autoFocus required inputProps={{ maxLength: 120 }} placeholder={p("portfolio.name-placeholder")} value={name} onChange={(e) => setName(e.target.value)} />
        </PublicField>
        <PublicField label={p("portfolio.category")}>
          <PublicSelect value={category} onChange={setCategory} options={CATEGORIES.map((value) => [value, categoryName(value)])} />
        </PublicField>
        <PublicField label={p("portfolio.ingredients")} full>
          <PublicInput
            multiline
            rows={3}
            inputProps={{ maxLength: 2000 }}
            placeholder={p("portfolio.ingredients-placeholder")}
            value={ingredients}
            onChange={(e) => setIngredients(e.target.value)}
          />
        </PublicField>
      </Box>
      <Box component="fieldset" sx={{ mb: "24px", minWidth: 0 }}>
        <Box component="legend" sx={{ fontSize: "13px", fontWeight: 600, mb: "12px" }}>
          {p("portfolio.markets")}
        </Box>
        <Box sx={{ display: "flex", gap: "12px 24px", flexWrap: "wrap" }}>
          {MARKETS.map((m) => (
            <Box component="label" key={m} sx={{ display: "flex", alignItems: "center", gap: "7px", fontSize: "12px" }}>
              <Box component="input" type="checkbox" checked={selected.includes(m)} onChange={() => setSelected(toggleValue(selected, m))} sx={{ m: 0 }} />
              {marketName(m)}
            </Box>
          ))}
        </Box>
      </Box>
      {error ? <PublicError>{error}</PublicError> : null}
      <Actions>
        <ActionButton type="submit">{p("portfolio.save")}</ActionButton>
        <TextAction onClick={onCancel}>{p("portfolio.cancel")}</TextAction>
      </Actions>
    </Box>
  );
}

export default function WorkspacePage() {
  const router = useRouter();
  const viewParam = typeof router.query.view === "string" ? router.query.view : "";
  const itemParam = typeof router.query.item === "string" ? router.query.item : "";
  const view = NAV.some((n) => n.id === viewParam) ? viewParam : "overview";
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [deleted, setDeleted] = useState<Product | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftCadence, setDraftCadence] = useState<Workspace["cadence"]>("Weekly");
  const importRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const w = loadWorkspace();
    setWorkspace(w);
    setDraftName(w.company);
    setDraftCadence(w.cadence);
    setReady(true);
  }, []);
  useEffect(() => {
    setNotice("");
    setError("");
    setQuery("");
    setFilter("all");
    setExpanded(null);
  }, [view]);
  function update(next: Workspace, message = p("messages.saved"), replace = false): boolean {
    try {
      if (!saveWorkspace(next, replace ? undefined : workspace)) {
        setError(p("messages.save-failed"));
        return false;
      }
    } catch (reason) {
      setConflict(true);
      setNotice("");
      setError(reason instanceof Error ? reason.message : p("messages.reload-needed"));
      return false;
    }
    setWorkspace(next);
    setNotice(message);
    setError("");
    setConflict(false);
    return true;
  }
  function saveProduct(product: Product) {
    const products = workspace.products.some((x) => x.id === product.id) ? workspace.products.map((x) => (x.id === product.id ? product : x)) : [...workspace.products, product];
    if (update({ ...workspace, products }, p("messages.product-saved"))) setEditing(null);
  }
  async function importWorkspace(file?: File) {
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error(p("messages.too-large"));
      const restored = parseWorkspace(JSON.parse(await file.text()));
      if (!restored) throw new Error(p("messages.invalid"));
      if (update(restored, p("messages.restored"), true)) {
        setDraftName(restored.company);
        setDraftCadence(restored.cadence);
        setDeleted(null);
        setEditing(null);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : p("messages.import-failed"));
    }
    if (importRef.current) importRef.current.value = "";
  }
  function clearWorkspace() {
    try {
      localStorage.removeItem(WORKSPACE_STORAGE);
      const w = emptyWorkspace();
      setWorkspace(w);
      setDraftName("");
      setDraftCadence("Weekly");
      setConfirmClear(false);
      setDeleted(null);
      setNotice(p("messages.cleared"));
      setError("");
      setConflict(false);
    } catch {
      setError(p("messages.clear-failed"));
    }
  }
  const pending = SAMPLE_UPDATES.filter((u) => !workspace.reviewed.includes(u.id));
  const filtered = SAMPLE_UPDATES.filter(
    (u) =>
      `${u.title} ${u.category} ${u.source} ${u.market}`.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "unreviewed" && !workspace.reviewed.includes(u.id)) ||
        (filter === "saved" && workspace.saved.includes(u.id)) ||
        (filter === "reviewed" && workspace.reviewed.includes(u.id))),
  );
  const matchingSources = SOURCES.filter((s) => `${s.name} ${s.short} ${s.market} ${s.topic}`.toLowerCase().includes(query.toLowerCase()));
  const label = p(`nav.${view}`);
  const meta = (u: (typeof SAMPLE_UPDATES)[number]) => `${u.source} · ${marketName(u.market)} · ${p("overview.synthetic")}`;

  const search = (props: { label: string; placeholder: string; wide?: boolean }) => (
    <Box
      component="label"
      sx={{
        display: props.wide ? "flex" : "inline-flex",
        alignItems: "center",
        gap: "8px",
        p: "9px 12px",
        bgcolor: c("white"),
        border: `1px solid ${c("control-border")}`,
        borderRadius: "5px",
        ...(props.wide ? { maxWidth: "500px", mb: "25px" } : {}),
        "@media (max-width: 540px)": { width: "100%" },
      }}
    >
      <Icon name="search" size={19} />
      <PublicInputBare type="search" aria-label={props.label} value={query} onChange={setQuery} placeholder={props.placeholder} wide={props.wide} />
    </Box>
  );

  return (
    <PublicFrame
      tightHeadings={false}
      sx={{
        display: "grid",
        gridTemplateColumns: "240px minmax(0, 1fr)",
        "@media (max-width: 800px)": { display: "block" },
      }}
    >
      <Meta title={p("meta.title")} index={false} />
      <Box
        component="a"
        href="#workspace-main"
        sx={{ ...srOnly, "&:focus": { position: "fixed", width: "auto", height: "auto", clipPath: "none", top: "10px", left: "10px", zIndex: 100, p: "12px", bgcolor: c("white") } }}
      >
        {p("nav.skip")}
      </Box>
      <Box
        component="aside"
        sx={{
          position: "sticky",
          top: 0,
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          p: "28px 18px 24px",
          borderRight: line,
          bgcolor: c("white"),
          "& > [data-part='brand']": { pl: "10px" },
          "@media (max-width: 800px)": { position: "static", height: "auto", p: "18px 24px 0", borderRight: 0, borderBottom: line, "& > [data-part='brand']": { p: 0 } },
        }}
      >
        <Brand />
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: "3px",
            p: "25px 12px 23px",
            mt: "20px",
            mb: "12px",
            borderTop: line,
            borderBottom: line,
            "@media (max-width: 800px)": { position: "absolute", top: "17px", right: "24px", p: 0, border: 0, m: 0, maxWidth: "40%", textAlign: "right" },
          }}
        >
          <Box component="strong" sx={{ fontSize: "13px", fontWeight: 600, overflowWrap: "anywhere", "@media (max-width: 800px)": { fontSize: "11px" } }}>
            {ready ? workspace.company || p("nav.your-workspace") : p("nav.your-workspace")}
          </Box>
          <Box component="span" sx={{ fontSize: "11px", ...muted }}>
            {p("nav.access")}
          </Box>
        </Box>
        <Box
          component="nav"
          aria-label={p("nav.label")}
          sx={{
            display: "grid",
            gap: "5px",
            "@media (max-width: 800px)": { display: "flex", overflowX: "auto", mt: "24px", gap: "4px", pb: "8px", "& a": { whiteSpace: "nowrap", p: "9px 12px", gap: "7px" }, "& svg": { width: 17, height: 17 } },
          }}
        >
          {NAV.map((n) => (
            <Piece
              key={n.id}
              name="workspace-nav-link"
              component={NextLink}
              href={`/workspace/?view=${n.id}`}
              selected={view === n.id}
              aria-current={view === n.id ? "page" : undefined}
              sx={{ display: "flex", alignItems: "center", gap: "12px", flexGrow: 0 }}
            >
              <Icon name={n.icon} size={21} />
              <span>{p(`nav.${n.id}`)}</span>
            </Piece>
          ))}
        </Box>
        <Box sx={{ mt: "auto", p: "24px 12px 0", "@media (max-width: 800px)": { display: "none" } }}>
          <Box component="p" sx={{ fontSize: "11px", mb: "9px", ...muted }}>
            {p("nav.built-around")}
          </Box>
          <TextAction href="/onboarding/">
            {workspace.completed ? p("nav.edit-setup") : p("nav.finish-setup")}
            <Arrow size={17} />
          </TextAction>
          <Box component={NextLink} href="/" sx={{ display: "block", fontSize: "11px", mt: "22px", ...muted }}>
            {p("nav.back")}
          </Box>
        </Box>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Box
          component="header"
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
            p: "19px 42px",
            bgcolor: c("white"),
            borderBottom: line,
            fontSize: "12px",
            "@media (max-width: 800px)": { px: "24px" },
          }}
        >
          <span>{label}</span>
          <Box component={NextLink} href="/privacy/" sx={{ display: "inline-flex", alignItems: "center", gap: "7px", fontSize: "11px", ...muted }}>
            {p("nav.saved-device")} <Icon name="lock" size={15} />
          </Box>
        </Box>
        <Box
          component="main"
          id="workspace-main"
          sx={{
            maxWidth: "1300px",
            mx: "auto",
            p: "30px 42px",
            "@media (max-width: 1100px)": { px: "28px" },
            "@media (max-width: 800px)": { p: "24px" },
            "@media (max-width: 540px)": { px: "20px" },
            "& p": { maxWidth: "72ch" },
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "start",
              gap: "12px",
              border: `1px solid ${c("banner-border")}`,
              bgcolor: c("banner-surface"),
              p: "14px 18px",
              borderRadius: "6px",
              fontSize: "12px",
              color: c("banner-ink"),
              "& p": { maxWidth: "none" },
              "@media (max-width: 540px)": { p: "12px", fontSize: "11px" },
            }}
          >
            <Icon name="article" size={20} sx={{ mt: "1px" }} />
            <p>
              <strong>{p("banner.strong")}</strong> {p("banner.body")}
            </p>
          </Box>
          <Box
            component="header"
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "end",
              gap: "28px",
              mt: "38px",
              mb: "32px",
              "@media (max-width: 800px)": { alignItems: "start" },
              "@media (max-width: 540px)": { flexDirection: "column", gap: "20px", mt: "26px" },
            }}
          >
            <div>
              <Box
                component="h1"
                sx={{ fontSize: "30px", fontWeight: 550, lineHeight: 1.25, letterSpacing: "-.03em", textWrap: "balance", "@media (max-width: 540px)": { fontSize: "27px" } }}
              >
                {view === "overview" ? p("headings.overview-title") : label}
              </Box>
              <Box component="p" sx={{ fontSize: "13px", mt: "10px", ...muted }}>
                {p(`headings.${view}`)}
              </Box>
            </div>
            {view === "overview" ? (
              <ActionButton href="/workspace/?view=portfolio" sx={{ flexShrink: 0 }}>
                <Icon name="add" size={19} />
                {p("headings.add-a-product")}
              </ActionButton>
            ) : null}
            {view === "portfolio" && !editing ? (
              <ActionButton onClick={() => setEditing("new")} sx={{ flexShrink: 0 }}>
                <Icon name="add" size={19} />
                {p("headings.add-product")}
              </ActionButton>
            ) : null}
          </Box>
          {notice ? <PublicNotice>{notice}</PublicNotice> : null}
          {error ? <PublicError>{error}</PublicError> : null}
          {conflict ? (
            <ActionButton tone="public-button-outline" onClick={() => window.location.reload()}>
              {p("messages.reload")}
            </ActionButton>
          ) : null}
          {!ready ? (
            <Box component="p" aria-live="polite">
              {p("headings.loading")}
            </Box>
          ) : (
            <>
              {view === "overview" ? (
                <>
                  {!workspace.completed ? (
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "24px",
                        bgcolor: c("white"),
                        border: line,
                        p: "24px",
                        mb: "32px",
                        borderRadius: "8px",
                        "@media (max-width: 540px)": { flexDirection: "column", alignItems: "start", p: "20px" },
                      }}
                    >
                      <div>
                        <Heading size="18px">{p("overview.setup-title")}</Heading>
                        <Box component="p" sx={{ fontSize: "13px", mt: "7px", ...muted }}>
                          {p("overview.setup-body")}
                        </Box>
                      </div>
                      <ActionButton href="/onboarding/">
                        {p("overview.setup-action")} <Arrow size={19} />
                      </ActionButton>
                    </Box>
                  ) : null}
                  <Box sx={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "36px", "@media (max-width: 1100px)": { gridTemplateColumns: "1fr" } }}>
                    <section>
                      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "18px" }}>
                        <Heading size="17px">{p("overview.queue-title")}</Heading>
                        <Box component={NextLink} href="/workspace/?view=updates" sx={{ display: "inline-flex", alignItems: "center", gap: "6px", color: c("tag-ink"), fontSize: "12px" }}>
                          {p("overview.view-all")} <Icon name="arrow_forward" size={17} />
                        </Box>
                      </Box>
                      <Box component="p" sx={{ fontSize: "12px", mt: "5px", mb: "18px", ...muted }}>
                        {p("overview.left", { count: pending.length })}
                      </Box>
                      <Box sx={{ borderTop: line }}>
                        {pending.slice(0, 3).map((u) => (
                          <Box
                            component={NextLink}
                            href={`/workspace/?view=updates&item=${u.id}`}
                            key={u.id}
                            sx={{ display: "block", position: "relative", p: "24px 28px 24px 0", borderBottom: line, "&:hover h3": { color: c("row-hover") } }}
                          >
                            <PublicTag priority={u.first}>{u.priority}</PublicTag>
                            <Box component="h3" sx={{ fontWeight: 600, fontSize: "16px", lineHeight: 1.5, my: "10px" }}>
                              {u.title}
                            </Box>
                            <Box component="p" sx={{ fontSize: "11px", ...muted }}>
                              {meta(u)}
                            </Box>
                            <Icon name="chevron_right" size={20} sx={{ position: "absolute", right: 0, top: "50%" }} />
                          </Box>
                        ))}
                        {!pending.length ? (
                          <Empty icon="check_circle" title={p("overview.clear-title")} body={p("overview.clear-body")} level={3}>
                            <NextLink href="/workspace/?view=updates">{p("overview.clear-link")}</NextLink>
                          </Empty>
                        ) : null}
                      </Box>
                    </section>
                    <Piece name="context-panel" component="aside" sx={{ alignSelf: "start", "@media (max-width: 540px)": { p: "22px" } }}>
                      <Heading size="17px">{p("overview.context-title")}</Heading>
                      <Box
                        component="dl"
                        sx={{
                          my: "22px",
                          "& > div": { my: "18px" },
                          "& dt": { fontSize: "11px", mb: "5px", ...muted },
                          "& dd": { fontSize: "13px", overflowWrap: "anywhere" },
                          "@media (max-width: 1100px)": { display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: "20px" },
                          "@media (max-width: 540px)": { gridTemplateColumns: "1fr" },
                        }}
                      >
                        {(
                          [
                            ["products", workspace.products.length || p("overview.no-products")],
                            ["categories", workspace.categories.map(categoryName).join(", ") || p("overview.choose")],
                            ["markets", workspace.markets.map(marketName).join(", ") || p("overview.choose")],
                            ["sources", workspace.sources.length],
                            ["cadence", cadenceName(workspace.cadence)],
                          ] as [string, ReactNode][]
                        ).map(([key, value]) => (
                          <div key={key}>
                            <dt>{p(`overview.${key}`)}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </Box>
                      <TextAction href="/workspace/?view=briefings">
                        {p("overview.open-briefing")} <Arrow size={18} />
                      </TextAction>
                    </Piece>
                  </Box>
                </>
              ) : null}
              {view === "updates" ? (
                <>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: "20px", alignItems: "center", mb: "24px", flexWrap: "wrap" }}>
                    <Box role="group" aria-label={p("updates.filter-label")} sx={{ display: "flex", gap: "5px", flexWrap: "wrap" }}>
                      {["all", "unreviewed", "saved", "reviewed"].map((id) => (
                        <Piece
                          key={id}
                          name="filter-tab"
                          aria-pressed={filter === id}
                          className={filter === id ? "Mui-selected" : undefined}
                          onClick={() => setFilter(id)}
                          sx={{ minWidth: 0 }}
                        >
                          {p(`updates.${id}`)}
                        </Piece>
                      ))}
                    </Box>
                    {search({ label: p("updates.search-label"), placeholder: p("updates.search") })}
                  </Box>
                  <Box sx={{ borderTop: line }}>
                    {filtered.map((u) => {
                      const open = expanded === u.id || (expanded === null && itemParam === u.id);
                      const reviewed = workspace.reviewed.includes(u.id);
                      return (
                        <Box component="article" key={u.id} sx={{ py: "24px", borderBottom: line }}>
                          <Box sx={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center", fontSize: "11px", ...muted }}>
                            <PublicTag priority={u.first}>{reviewed ? p("updates.reviewed") : u.priority}</PublicTag>
                            <span>{meta(u)}</span>
                          </Box>
                          <Box
                            component="button"
                            type="button"
                            aria-expanded={open}
                            aria-controls={`detail-${u.id}`}
                            onClick={() => setExpanded(open ? "" : u.id)}
                            sx={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", gap: "24px", textAlign: "left", cursor: "pointer", background: "none", border: 0, padding: "14px 0 0", color: "inherit", font: "inherit" }}
                          >
                            <Box component="h2" sx={{ fontSize: "18px", fontWeight: 600, lineHeight: 1.5 }}>
                              {u.title}
                            </Box>
                            <Icon name={open ? "close" : "chevron_right"} size={22} />
                          </Box>
                          {open ? (
                            <Box id={`detail-${u.id}`} sx={{ pt: "22px", pb: "4px", maxWidth: "760px", fontSize: "14px", color: c("update-ink") }}>
                              <p>{u.summary}</p>
                              <Box component="h3" sx={{ color: c("bw-ink"), fontSize: "14px", fontWeight: 650, mt: "22px", mb: "7px" }}>
                                {p("updates.suggested")}
                              </Box>
                              <p>{u.action}</p>
                              <TextAction href={u.url} external sx={{ mt: "22px", mb: "5px" }}>
                                {p("updates.visit")} <Arrow size={18} />
                              </TextAction>
                              <Box component="small" sx={{ display: "block", fontSize: "11px" }}>
                                {p("updates.visit-note")}
                              </Box>
                              <Actions sx={{ mt: "24px" }}>
                                <ActionButton
                                  onClick={() =>
                                    update({ ...workspace, reviewed: toggleValue(workspace.reviewed, u.id) }, reviewed ? p("messages.unreviewed") : p("messages.reviewed"))
                                  }
                                >
                                  {reviewed ? p("updates.mark-unreviewed") : p("updates.mark-reviewed")}
                                </ActionButton>
                                <ActionButton
                                  tone="public-button-outline"
                                  aria-pressed={workspace.saved.includes(u.id)}
                                  onClick={() => update({ ...workspace, saved: toggleValue(workspace.saved, u.id) })}
                                >
                                  {workspace.saved.includes(u.id) ? p("updates.unsave") : p("updates.save")}
                                </ActionButton>
                              </Actions>
                            </Box>
                          ) : null}
                        </Box>
                      );
                    })}
                    {!filtered.length ? (
                      <Empty title={p("updates.empty-title")} body={p("updates.empty-body")}>
                        <TextAction
                          onClick={() => {
                            setQuery("");
                            setFilter("all");
                          }}
                        >
                          {p("updates.show-all")}
                        </TextAction>
                      </Empty>
                    ) : null}
                  </Box>
                </>
              ) : null}
              {view === "portfolio" ? (
                <>
                  {editing ? (
                    <ProductForm
                      key={editing === "new" ? "new" : editing.id}
                      initial={editing === "new" ? undefined : editing}
                      markets={workspace.markets}
                      onSave={saveProduct}
                      onCancel={() => setEditing(null)}
                    />
                  ) : null}
                  <div>
                    {workspace.products.map((x) => (
                      <Box
                        component="article"
                        key={x.id}
                        sx={{ display: "flex", justifyContent: "space-between", gap: "28px", py: "28px", borderTop: line, "@media (max-width: 540px)": { flexDirection: "column", gap: "18px" } }}
                      >
                        <div>
                          <PublicTag>{categoryName(x.category)}</PublicTag>
                          <Heading size="20px" sx={{ my: "12px", overflowWrap: "anywhere" }}>
                            {x.name}
                          </Heading>
                          <Box component="p" sx={{ fontSize: "14px", overflowWrap: "anywhere", ...muted }}>
                            {x.ingredients || p("portfolio.no-ingredients")}
                          </Box>
                          <Box component="small" sx={{ display: "block", fontSize: "12px", mt: "12px", ...muted }}>
                            {x.markets.map(marketName).join(" · ")}
                          </Box>
                        </div>
                        <Box sx={{ display: "flex", alignItems: "start", gap: "20px", flexShrink: 0 }}>
                          <TextAction onClick={() => setEditing(x)}>{p("portfolio.edit-button")}</TextAction>
                          <TextAction
                            onClick={() => {
                              if (update({ ...workspace, products: workspace.products.filter((y) => y.id !== x.id) }, p("messages.removed"))) setDeleted(x);
                            }}
                          >
                            {p("portfolio.remove")}
                            <Box component="span" sx={srOnly}>
                              {" "}
                              {x.name}
                            </Box>
                          </TextAction>
                        </Box>
                      </Box>
                    ))}
                  </div>
                  {deleted ? (
                    <PublicNotice live={false}>
                      {p("portfolio.removed", { name: deleted.name })}{" "}
                      <TextAction
                        onClick={() => {
                          if (update({ ...workspace, products: restoreProduct(workspace.products, deleted) }, p("messages.restored-product"))) setDeleted(null);
                        }}
                      >
                        {p("portfolio.undo")}
                      </TextAction>
                    </PublicNotice>
                  ) : null}
                  {!workspace.products.length && !editing ? (
                    <Empty icon="description" title={p("portfolio.empty-title")} body={p("portfolio.empty-body")}>
                      <ActionButton onClick={() => setEditing("new")}>{p("portfolio.add-first")}</ActionButton>
                    </Empty>
                  ) : null}
                </>
              ) : null}
              {view === "sources" ? (
                <>
                  {search({ label: p("sources.search-label"), placeholder: p("sources.search"), wide: true })}
                  <div>
                    {matchingSources.map((s) => {
                      const chosen = workspace.sources.includes(s.id);
                      return (
                        <Box
                          component="article"
                          key={s.id}
                          sx={{ display: "flex", gap: "22px", alignItems: "center", borderTop: line, py: "25px", "@media (max-width: 540px)": { flexWrap: "wrap", gap: "14px" } }}
                        >
                          <Piece
                            name="source-monogram"
                            component="span"
                            sx={{ display: "flex", alignItems: "center", justifyContent: "center", width: 66, height: 60, flexShrink: 0 }}
                          >
                            {s.short}
                          </Piece>
                          <Box sx={{ "@media (max-width: 540px)": { width: "calc(100% - 82px)" } }}>
                            <Heading size="16px">{s.name}</Heading>
                            <Box component="p" sx={{ fontSize: "13px", my: "5px", ...muted }}>
                              {s.topic}
                            </Box>
                            <Box component="small" sx={{ fontSize: "11px", ...muted, "@media (max-width: 540px)": { display: "block" } }}>
                              {p("sources.official", { market: marketName(s.market) })}
                            </Box>
                            <Box
                              component="a"
                              href={s.url}
                              target="_blank"
                              rel="noreferrer"
                              sx={{ fontSize: "11px", color: `${c("tag-ink")} !important`, ml: "12px", textDecoration: "underline !important", textUnderlineOffset: "3px", "@media (max-width: 540px)": { display: "block", ml: 0 } }}
                            >
                              {p("sources.visit")}
                            </Box>
                          </Box>
                          <ActionButton
                            tone={chosen ? "public-button-outline" : "public-button"}
                            aria-pressed={chosen}
                            onClick={() => update({ ...workspace, sources: toggleValue(workspace.sources, s.id) }, p("messages.source-saved"))}
                            sx={{ ml: "auto", flexShrink: 0, "@media (max-width: 540px)": { ml: "80px" } }}
                          >
                            {chosen ? p("sources.selected") : p("sources.select")}
                          </ActionButton>
                        </Box>
                      );
                    })}
                  </div>
                  {!matchingSources.length ? (
                    <Empty title={p("sources.empty-title")}>
                      <TextAction onClick={() => setQuery("")}>{p("sources.show-all")}</TextAction>
                    </Empty>
                  ) : null}
                </>
              ) : null}
              {view === "briefings" ? (
                <>
                  <Box
                    sx={{ display: "flex", justifyContent: "space-between", gap: "22px", alignItems: "center", mb: "28px", "@media (max-width: 540px)": { flexDirection: "column", alignItems: "start" } }}
                  >
                    <div>
                      <Heading size="18px">{p("briefings.title")}</Heading>
                      <Box component="p" sx={{ fontSize: "12px", mt: "6px", ...muted }}>
                        {p("briefings.intro")}
                      </Box>
                    </div>
                    <ActionButton
                      onClick={() => {
                        downloadText(t("global.preview-data.briefing-export.filename"), briefingText(workspace));
                        setNotice(p("messages.exported"));
                      }}
                    >
                      <Icon name="download" size={19} />
                      {p("briefings.export")}
                    </ActionButton>
                  </Box>
                  <Piece name="briefing-paper" component="article" sx={{ maxWidth: "820px", "@media (max-width: 540px)": { p: "28px 22px" } }}>
                    <Brand />
                    <Box component="h2" sx={{ fontFamily: "Georgia, serif", fontSize: "30px", mt: "34px", mb: "10px", overflowWrap: "anywhere" }}>
                      {workspace.company || p("briefings.your-business")}
                    </Box>
                    <Box component="p" sx={{ fontSize: "13px", ...muted }}>
                      {p("briefings.subtitle", { cadence: cadenceName(workspace.cadence) })}
                    </Box>
                    <PublicNote>
                      <p>{p("briefings.note")}</p>
                    </PublicNote>
                    {SAMPLE_UPDATES.map((u) => (
                      <Box component="section" key={u.id} sx={{ borderTop: line, py: "28px", "& p": { fontSize: "14px", color: c("update-ink"), mt: "12px" } }}>
                        <PublicTag>{u.category}</PublicTag>
                        <Box component="h3" sx={{ fontSize: "20px", lineHeight: 1.5, fontWeight: 600, my: "13px" }}>
                          {u.title}
                        </Box>
                        <p>{u.summary}</p>
                        <p>
                          <strong>{p("briefings.suggested")}</strong> {u.action}
                        </p>
                      </Box>
                    ))}
                    <Box component="small" sx={{ fontSize: "11px", ...muted }}>
                      {p("briefings.footer")}
                    </Box>
                  </Piece>
                </>
              ) : null}
              {view === "membership" ? (
                <Box
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "1.2fr 1fr",
                    gap: "50px",
                    p: "36px",
                    bgcolor: c("white"),
                    border: line,
                    borderRadius: "10px",
                    "& p": { fontSize: "14px", ...muted },
                    "@media (max-width: 1100px)": { gap: "30px", p: "28px" },
                    "@media (max-width: 800px)": { gridTemplateColumns: "1fr" },
                    "@media (max-width: 540px)": { p: "24px" },
                  }}
                >
                  <div>
                    <PublicTag>{p("membership.tag")}</PublicTag>
                    <Heading size="32px" sx={{ fontWeight: 550, my: "20px" }}>
                      {p("membership.title")}
                    </Heading>
                    <p>{p("membership.body")}</p>
                    <FeatureList size={19} sx={{ fontSize: "13px" }} />
                    <ActionButton href="/pricing/" sx={{ mt: "25px" }}>
                      {p("membership.details")} <Arrow size={19} />
                    </ActionButton>
                  </div>
                  <div>
                    <Heading level={3} size="17px" sx={{ mt: "28px", mb: "12px" }}>
                      {p("membership.coming-title")}
                    </Heading>
                    <p>{p("membership.coming-body")}</p>
                    <Heading level={3} size="17px" sx={{ mt: "28px", mb: "12px" }}>
                      {p("membership.next-title")}
                    </Heading>
                    <p>{p("membership.next-body")}</p>
                  </div>
                </Box>
              ) : null}
              {view === "settings" ? (
                <Box
                  sx={{
                    maxWidth: "760px",
                    "& section": { borderTop: line, py: "30px" },
                    "& section > p": { fontSize: "14px", mb: "24px", ...muted },
                    "& h2": { fontSize: "20px", fontWeight: 600, mb: "20px" },
                  }}
                >
                  <section>
                    <h2>{p("settings.preferences")}</h2>
                    <Box
                      component="form"
                      onSubmit={(e: FormEvent) => {
                        e.preventDefault();
                        update({ ...workspace, company: draftName.trim(), cadence: draftCadence });
                      }}
                      sx={{ maxWidth: "480px" }}
                    >
                      <PublicField label={p("settings.business")}>
                        <PublicInput required inputProps={{ maxLength: 100 }} value={draftName} onChange={(e) => setDraftName(e.target.value)} />
                      </PublicField>
                      <PublicField label={p("settings.cadence")}>
                        <PublicSelect
                          value={draftCadence}
                          onChange={(value) => setDraftCadence(value as Workspace["cadence"])}
                          options={(["Daily", "Weekly"] as const).map((value) => [value, cadenceName(value)])}
                        />
                      </PublicField>
                      <Box component="p" sx={{ fontSize: "13px", lineHeight: 1.6, mt: "12px", mb: "20px", ...muted }}>
                        {p("settings.cadence-note")}
                      </Box>
                      <ActionButton type="submit">{p("settings.save")}</ActionButton>
                    </Box>
                  </section>
                  <section>
                    <h2>{p("settings.data")}</h2>
                    <p>{p("settings.data-body")}</p>
                    <Actions>
                      <ActionButton
                        tone="public-button-outline"
                        onClick={() => downloadText(t("global.preview-data.briefing-export.backup-filename"), JSON.stringify(workspace, null, 2), "application/json")}
                      >
                        {p("settings.export")}
                      </ActionButton>
                      <TextAction onClick={() => importRef.current?.click()}>{p("settings.import")}</TextAction>
                      <Box
                        component="input"
                        ref={importRef}
                        type="file"
                        accept="application/json,.json"
                        aria-label={p("settings.import-label")}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => void importWorkspace(e.target.files?.[0])}
                        sx={srOnly}
                      />
                    </Actions>
                    <Box component="p" sx={{ fontSize: "13px", lineHeight: 1.6, mt: "12px", mb: "20px", ...muted }}>
                      {p("settings.import-note")}
                    </Box>
                    <TextAction href="/privacy/">{p("settings.read")}</TextAction>
                  </section>
                  <section>
                    <h2>{p("settings.fresh")}</h2>
                    <p>{p("settings.fresh-body")}</p>
                    {confirmClear ? (
                      <PublicNote>
                        <div>
                          <p>{p("settings.confirm")}</p>
                          <Actions>
                            <ActionButton tone="public-button-outline" onClick={clearWorkspace}>
                              {p("settings.clear")}
                            </ActionButton>
                            <TextAction onClick={() => setConfirmClear(false)}>{p("settings.keep")}</TextAction>
                          </Actions>
                        </div>
                      </PublicNote>
                    ) : (
                      <TextAction onClick={() => setConfirmClear(true)}>{p("settings.clear")}</TextAction>
                    )}
                  </section>
                </Box>
              ) : null}
            </>
          )}
          <Box component="footer" sx={{ borderTop: line, mt: "55px", pt: "20px", fontSize: "11px", ...muted, "& a": { textDecoration: "underline", ml: "8px" } }}>
            {p("footer.body")} <NextLink href="/privacy/">{p("footer.privacy")}</NextLink>
          </Box>
        </Box>
      </Box>
    </PublicFrame>
  );
}

/** The borderless text box inside a search field. */
function PublicInputBare({
  value,
  onChange,
  placeholder,
  wide,
  ...rest
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  wide?: boolean;
  type: string;
  "aria-label": string;
}) {
  return (
    <Box
      component="input"
      {...rest}
      value={value}
      placeholder={placeholder}
      onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      sx={{
        minWidth: 0,
        bgcolor: "transparent",
        border: 0,
        p: 0,
        outlineOffset: "4px",
        font: "inherit",
        fontSize: "13px",
        width: wide ? "100%" : "210px",
        color: "inherit",
        "&::placeholder": { color: c("bw-muted") },
        "@media (max-width: 540px)": { width: "100%" },
      }}
    />
  );
}

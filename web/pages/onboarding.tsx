import Box from "@mui/material/Box";
import { useRouter } from "next/router";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Brand } from "@/components/brand";
import {
  ActionButton,
  Arrow,
  Choice,
  Container,
  Meta,
  PublicError,
  PublicField,
  PublicFrame,
  PublicInput,
  PublicNote,
  TextAction,
  c,
  headingSx,
  srOnly,
} from "@/components/public";
import { Icon, Piece } from "@/components/ui";
import { CATEGORIES, MARKETS, SOURCES, categoryName, emptyWorkspace, loadWorkspace, marketName, saveWorkspace, toggleValue, type Workspace } from "@/lib/bev-watch";
import { t } from "@/lib/text";

const p = (key: string, vars?: Record<string, string | number>) => t(`pages.onboarding.${key}`, vars);
const STEPS = [1, 2, 3, 4, 5];
const muted = { color: c("bw-muted") };
const legendSx = { fontSize: "13px", fontWeight: 600, mb: "12px" };

export default function OnboardingPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const baseline = useRef<Workspace>(emptyWorkspace());
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const loaded = loadWorkspace();
    setWorkspace(loaded);
    baseline.current = loaded;
  }, []);
  function change(patch: Partial<Workspace>) {
    setWorkspace((w) => ({ ...w, ...patch }));
    setError("");
  }
  function go(next: number) {
    setStep(next);
    setError("");
    window.setTimeout(() => heading.current?.focus(), 0);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && (!workspace.company.trim() || workspace.categories.length === 0)) {
      setError(p("errors.business"));
      return;
    }
    if (step === 1 && workspace.markets.length === 0) {
      setError(p("errors.markets"));
      return;
    }
    if (step === 2 && workspace.sources.length === 0) {
      setError(p("errors.sources"));
      return;
    }
    const next = { ...workspace, company: workspace.company.trim(), completed: step === 4 || workspace.completed };
    if (step === 1) next.sources = next.sources.filter((id) => SOURCES.some((s) => s.id === id && next.markets.includes(s.market)));
    try {
      if (!saveWorkspace(next, baseline.current)) {
        setError(p("errors.storage"));
        return;
      }
    } catch (reason) {
      setConflict(true);
      setError(reason instanceof Error ? reason.message : p("errors.reload-needed"));
      return;
    }
    baseline.current = next;
    setWorkspace(next);
    if (step === 4) void router.push("/workspace/");
    else go(step + 1);
  }
  const suggested = SOURCES.filter((s) => workspace.markets.includes(s.market));
  const n = step + 1;

  return (
    <PublicFrame>
      <Meta title={p("meta.title")} index={false} />
      <Container component="header" sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "24px", py: "30px", "@media (max-width: 540px)": { py: "22px" } }}>
        <Brand />
        <TextAction href="/workspace/">
          {p("frame.explore")} <Arrow size={18} />
        </TextAction>
      </Container>
      <Container
        component="main"
        id="main"
        sx={{
          display: "grid",
          gridTemplateColumns: ".85fr 1.3fr",
          gap: "10%",
          pt: "45px",
          pb: "80px",
          "@media (max-width: 800px)": { gap: "35px", gridTemplateColumns: "1fr", pt: "20px" },
          "@media (max-width: 540px)": { pb: "45px" },
        }}
      >
        <aside>
          <Box component="h2" sx={{ ...headingSx, fontSize: "46px", fontWeight: 500, "@media (max-width: 800px)": { display: "none" } }}>
            {p("frame.aside-1")}
            <br />
            {p("frame.aside-2")}
            <br />
            <em>{p("frame.aside-emphasis")}</em>
          </Box>
          <Box
            component="ol"
            aria-label={p("frame.progress")}
            sx={{ my: "36px", "@media (max-width: 800px)": { display: "flex", justifyContent: "space-between", m: 0, gap: "8px" } }}
          >
            {STEPS.map((s, i) => {
              const current = step === i;
              return (
                <Box
                  component="li"
                  key={s}
                  aria-current={current ? "step" : undefined}
                  sx={{
                    display: "flex",
                    gap: "13px",
                    alignItems: "center",
                    my: "20px",
                    fontSize: "14px",
                    color: current ? c("bw-navy") : c("bw-muted"),
                    fontWeight: current ? 650 : 400,
                    "@media (max-width: 800px)": { m: 0, fontSize: 0 },
                  }}
                >
                  <Box
                    component="span"
                    sx={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 28,
                      height: 28,
                      border: `1px solid ${current ? c("bw-navy") : c("choice-border")}`,
                      borderRadius: "50%",
                      fontSize: "12px",
                      bgcolor: current ? c("bw-navy") : "transparent",
                      color: current ? c("white") : "inherit",
                    }}
                  >
                    {i < step ? <Icon name="check_circle" size={20} /> : i + 1}
                  </Box>
                  {p(`steps.${s}-name`)}
                </Box>
              );
            })}
          </Box>
          <Box component="p" sx={{ maxWidth: "30ch", fontSize: "12px", ...muted, "@media (max-width: 800px)": { display: "none" } }}>
            {p("frame.saved-note")}
          </Box>
        </aside>
        <Piece
          name="onboarding-panel"
          component="form"
          onSubmit={submit}
          sx={{ minWidth: 0, alignSelf: "start", "@media (max-width: 800px)": { p: "30px" }, "@media (max-width: 540px)": { p: "24px 20px" } }}
        >
          <Box sx={{ fontSize: "12px", mb: "14px", ...muted }}>{p("frame.step-count", { step: n, total: STEPS.length })}</Box>
          <Box
            component="h1"
            tabIndex={-1}
            ref={heading}
            sx={{ ...headingSx, fontSize: "33px", fontWeight: 550, "@media (max-width: 540px)": { fontSize: "28px" } }}
          >
            {p(`steps.${n}-title`)}
          </Box>
          <Box component="p" sx={{ fontSize: "14px", mt: "18px", mb: "30px", ...muted }}>
            {p(`steps.${n}-intro`)}
          </Box>
          {step === 0 ? (
            <>
              <PublicField label={p("fields.business")}>
                <PublicInput
                  autoComplete="organization"
                  inputProps={{ maxLength: 100 }}
                  value={workspace.company}
                  onChange={(e) => change({ company: e.target.value })}
                  placeholder={p("fields.business-placeholder")}
                  required
                />
              </PublicField>
              <Box component="fieldset" sx={{ mb: "24px", minWidth: 0 }}>
                <Box component="legend" sx={legendSx}>
                  {p("fields.categories")}
                </Box>
                <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", "@media (max-width: 540px)": { gridTemplateColumns: "1fr" } }}>
                  {CATEGORIES.map((value) => (
                    <Choice key={value} checked={workspace.categories.includes(value)} onChange={() => change({ categories: toggleValue(workspace.categories, value) })}>
                      <span>{categoryName(value)}</span>
                    </Choice>
                  ))}
                </Box>
              </Box>
            </>
          ) : null}
          {step === 1 ? (
            <Box component="fieldset" sx={{ mb: "24px", minWidth: 0 }}>
              <Box component="legend" sx={srOnly}>
                {p("fields.markets")}
              </Box>
              <Box sx={{ display: "grid", gap: "10px" }}>
                {MARKETS.map((value) => (
                  <Choice key={value} checked={workspace.markets.includes(value)} onChange={() => change({ markets: toggleValue(workspace.markets, value) })}>
                    <span>{marketName(value)}</span>
                  </Choice>
                ))}
              </Box>
            </Box>
          ) : null}
          {step === 2 ? (
            <Box component="fieldset" sx={{ mb: "24px", minWidth: 0 }}>
              <Box component="legend" sx={legendSx}>
                {p("fields.sources")}
              </Box>
              <Box sx={{ display: "grid", gap: "10px" }}>
                {suggested.map((s) => (
                  <Choice key={s.id} checked={workspace.sources.includes(s.id)} onChange={() => change({ sources: toggleValue(workspace.sources, s.id) })}>
                    <span>
                      <Box component="strong" sx={{ fontWeight: 550 }}>
                        {s.name}
                      </Box>
                      <Box component="small" sx={{ display: "block", mt: "3px", fontSize: "11px", ...muted }}>
                        {s.topic}
                      </Box>
                    </span>
                  </Choice>
                ))}
              </Box>
            </Box>
          ) : null}
          {step === 3 ? (
            <>
              <Box component="fieldset" sx={{ mb: "24px", minWidth: 0 }}>
                <Box component="legend" sx={legendSx}>
                  {p("fields.frequency")}
                </Box>
                <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", "@media (max-width: 540px)": { gridTemplateColumns: "1fr" } }}>
                  {(["Daily", "Weekly"] as const).map((value) => (
                    <Choice key={value} type="radio" name="cadence" checked={workspace.cadence === value} onChange={() => change({ cadence: value })}>
                      <span>{p(`fields.${value.toLowerCase()}`)}</span>
                    </Choice>
                  ))}
                </Box>
              </Box>
              <PublicNote icon="article">
                <p>{p("fields.briefing-note")}</p>
              </PublicNote>
            </>
          ) : null}
          {step === 4 ? (
            <>
              <Box
                component="dl"
                sx={{
                  "& > div": {
                    display: "grid",
                    gridTemplateColumns: "130px 1fr",
                    gap: "18px",
                    borderTop: `1px solid ${c("bw-line")}`,
                    py: "14px",
                    fontSize: "13px",
                    "@media (max-width: 540px)": { gridTemplateColumns: "1fr", gap: "6px" },
                  },
                  "& dt": muted,
                  "& dd": { overflowWrap: "anywhere" },
                }}
              >
                <div>
                  <dt>{p("summary.business")}</dt>
                  <dd>{workspace.company}</dd>
                </div>
                <div>
                  <dt>{p("summary.beverages")}</dt>
                  <dd>{workspace.categories.map(categoryName).join(", ")}</dd>
                </div>
                <div>
                  <dt>{p("summary.markets")}</dt>
                  <dd>{workspace.markets.map(marketName).join(", ")}</dd>
                </div>
                <div>
                  <dt>{p("summary.sources")}</dt>
                  <dd>
                    {SOURCES.filter((s) => workspace.sources.includes(s.id))
                      .map((s) => s.short)
                      .join(", ")}
                  </dd>
                </div>
                <div>
                  <dt>{p("summary.briefing")}</dt>
                  <dd>{p(`fields.${workspace.cadence.toLowerCase()}`)}</dd>
                </div>
              </Box>
              <PublicNote icon="check_circle">
                <p>{p("summary.free-note")}</p>
              </PublicNote>
            </>
          ) : null}
          {error ? <PublicError>{error}</PublicError> : null}
          {conflict ? (
            <ActionButton tone="public-button-outline" onClick={() => window.location.reload()}>
              {p("errors.reload")}
            </ActionButton>
          ) : null}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "20px",
              borderTop: `1px solid ${c("bw-line")}`,
              mt: "32px",
              pt: "24px",
              "@media (max-width: 540px)": { gap: "10px", "& [data-part='public-text-link']": { fontSize: "12px" } },
            }}
          >
            {step > 0 ? <TextAction onClick={() => go(step - 1)}>{p("actions.back")}</TextAction> : <TextAction href="/">{p("actions.back-to-site")}</TextAction>}
            <ActionButton type="submit">
              {step === 4 ? p("actions.open") : p("actions.continue")}
              <Arrow />
            </ActionButton>
          </Box>
          <Box component="p" sx={{ fontSize: "11px", mt: "26px", ...muted, "& a": { textDecoration: "underline", ml: "5px" } }}>
            {p("actions.footer")}
            <TextAction href="/privacy/" modifier="public-text-link-inline" sx={{ ml: "5px" }}>
              {p("actions.your-data")}
            </TextAction>
          </Box>
        </Piece>
      </Container>
    </PublicFrame>
  );
}

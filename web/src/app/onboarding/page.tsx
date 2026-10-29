"use client";

import { Copy } from "@/components/copy";
import { t, type CopyKey } from "@/lib/copy.generated";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Brand } from "@/components/brand";
import { Icon } from "@/components/icon";
import { ManagedError, LABEL_KEYS, publicLabel, CATEGORIES, MARKETS, SOURCES, emptyWorkspace, loadWorkspace, saveWorkspace, toggleValue, type Workspace } from "@/lib/bev-watch";

type PageError = { copy: CopyKey } | { text: string };

const STEPS = ["pages.onboarding.your-business", "pages.onboarding.your-markets", "pages.onboarding.your-sources", "pages.onboarding.your-briefing", "pages.onboarding.ready-to-review"] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<PageError|null>(null);
  const [conflict, setConflict] = useState(false);
  const baseline = useRef<Workspace>(emptyWorkspace());
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { const loaded=loadWorkspace();setWorkspace(loaded);baseline.current=loaded; }, []);
  function change(patch: Partial<Workspace>) { setWorkspace(w => ({...w, ...patch})); setError(null); }
  function go(next: number) { setStep(next); setError(null); window.setTimeout(() => heading.current?.focus(), 0); }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && (!workspace.company.trim() || workspace.categories.length === 0)) { setError({copy:"pages.onboarding.add-your-business-name-and-choose-at"}); return; }
    if (step === 1 && workspace.markets.length === 0) { setError({copy:"pages.onboarding.choose-at-least-one-market-to-continue"}); return; }
    if (step === 2 && workspace.sources.length === 0) { setError({copy:"pages.onboarding.choose-at-least-one-source-for-your"}); return; }
    const next = {...workspace, company: workspace.company.trim(), completed: step === 4 || workspace.completed};
    if (step === 1) next.sources = next.sources.filter(id => SOURCES.some(s=>s.id===id && next.markets.includes(s.market)));
    try {
      if (!saveWorkspace(next,baseline.current)) { setError({copy:"pages.onboarding.your-browser-could-not-save-the-workspace"}); return; }
    } catch (reason) {
      setConflict(true);setError(reason instanceof ManagedError ? {copy:reason.copyKey} : reason instanceof Error ? {text:reason.message} : {copy:"pages.onboarding.reload-the-workspace-before-saving-again"});return;
    }
    baseline.current=next;
    setWorkspace(next);
    if (step === 4) router.push("/workspace/"); else go(step + 1);
  }
  const suggested = SOURCES.filter(s => workspace.markets.includes(s.market));
  return <div className="bw-onboarding">
    <header className="bw-container bw-onboard-header"><Brand/><Link href="/workspace/" className="bw-text-link" data-component="text-action" data-component-name="text-action"><Copy k="pages.onboarding.explore-first" /> <Icon name="arrow_forward" size={18}/></Link></header>
    <main id="main" className="bw-container bw-onboard-grid">
      <aside><h2><Copy k="pages.onboarding.a-watchlist" /><br/><Copy k="pages.onboarding.that-knows" /><br/><em><Copy k="pages.onboarding.your-business-2" /></em></h2><ol aria-label={t("pages.onboarding.setup-progress")}>{STEPS.map((s,i)=><li key={s} aria-current={step===i ? "step" : undefined}><span>{i<step ? <Icon name="check_circle" size={20}/> : i+1}</span><Copy k={s} /></li>)}</ol><p><Copy k="pages.onboarding.your-choices-are-saved-in-this-browser" /></p></aside>
      <form onSubmit={submit} className="bw-onboard-form" data-component="onboarding-panel" data-component-name="onboarding-panel">
        <div className="bw-step-count"><Copy k="pages.onboarding.step" /> {step+1}  <Copy k="pages.onboarding.of" /> {STEPS.length}</div>
        <h1 tabIndex={-1} ref={heading}><Copy k={(["pages.onboarding.what-do-you-make", "pages.onboarding.where-do-you-sell", "pages.onboarding.build-your-source-list", "pages.onboarding.make-the-briefing-yours", "pages.onboarding.your-watchlist-is-ready"] as const)[step]} /></h1>
        <p className="bw-form-intro"><Copy k={(["pages.onboarding.start-with-the-business-and-beverage-categories", "pages.onboarding.choose-your-current-markets-you-can-add", "pages.onboarding.choose-the-official-sources-your-team-wants", "pages.onboarding.set-your-preferred-review-rhythm-email-delivery", "pages.onboarding.review-your-choices-then-explore-the-workspace"] as const)[step]} /></p>
        {step===0 && <><label className="bw-field" data-component="field" data-component-name="field"><Copy k="pages.onboarding.business-name" /><input autoComplete="organization" maxLength={100} value={workspace.company} onChange={e=>change({company:e.target.value})} placeholder={t("pages.onboarding.your-beverage-business")} required/></label><fieldset><legend><Copy k="pages.onboarding.beverage-categories" /></legend><div className="bw-choice-grid">{CATEGORIES.map(c=><label key={c} data-component="choice-selected" data-component-name="choice-selected" className={`bw-choice ${workspace.categories.includes(c)?"is-selected":""}`}><input type="checkbox" checked={workspace.categories.includes(c)} onChange={()=>change({categories:toggleValue(workspace.categories,c)})}/><span data-copy-key={LABEL_KEYS[c]}>{publicLabel(c)}</span></label>)}</div></fieldset></>}
        {step===1 && <fieldset><legend className="bw-sr-only"><Copy k="pages.onboarding.markets" /></legend><div className="bw-choice-stack">{MARKETS.map(m=><label data-component="choice-selected" data-component-name="choice-selected" className={`bw-choice ${workspace.markets.includes(m)?"is-selected":""}`} key={m}><input type="checkbox" checked={workspace.markets.includes(m)} onChange={()=>change({markets:toggleValue(workspace.markets,m)})}/><span data-copy-key={LABEL_KEYS[m]}>{publicLabel(m)}</span></label>)}</div></fieldset>}
        {step===2 && <fieldset><legend><Copy k="pages.onboarding.sources-for-your-selected-markets" /></legend><div className="bw-choice-stack">{suggested.map(s=><label key={s.id} data-component="choice-selected" data-component-name="choice-selected" className={`bw-choice ${workspace.sources.includes(s.id)?"is-selected":""}`}><input type="checkbox" checked={workspace.sources.includes(s.id)} onChange={()=>change({sources:toggleValue(workspace.sources,s.id)})}/><span><strong><Copy k={s.nameCopy} /></strong><small><Copy k={s.topicCopy} /></small></span></label>)}</div></fieldset>}
        {step===3 && <><fieldset><legend><Copy k="pages.onboarding.preferred-briefing-frequency" /></legend><div className="bw-choice-grid">{(["Daily","Weekly"] as const).map(c=><label data-component="choice-selected" data-component-name="choice-selected" className={`bw-choice ${workspace.cadence===c?"is-selected":""}`} key={c}><input type="radio" name="cadence" checked={workspace.cadence===c} onChange={()=>change({cadence:c})}/><span data-copy-key={LABEL_KEYS[c]}>{publicLabel(c)}</span></label>)}</div></fieldset><div className="bw-note"><Icon name="article"/><p><Copy k="pages.onboarding.you-can-export-a-sample-briefing-from" /></p></div></>}
        {step===4 && <><dl className="bw-summary"><div><dt><Copy k="pages.onboarding.business" /></dt><dd>{workspace.company}</dd></div><div><dt><Copy k="pages.onboarding.beverages" /></dt><dd>{workspace.categories.map(publicLabel).join(", ")}</dd></div><div><dt><Copy k="pages.onboarding.markets" /></dt><dd>{workspace.markets.map(publicLabel).join(", ")}</dd></div><div><dt><Copy k="pages.onboarding.sources" /></dt><dd>{SOURCES.filter(s=>workspace.sources.includes(s.id)).map(s=>s.short).join(", ")}</dd></div><div><dt><Copy k="pages.onboarding.briefing-preference" /></dt><dd><Copy k={LABEL_KEYS[workspace.cadence]} /></dd></div></dl><div className="bw-note"><Icon name="check_circle"/><p><Copy k="pages.onboarding.preview-access-is-free-no-card-account" /></p></div></>}
        {error && <p role="alert" className="bw-error">{"copy" in error ? <Copy k={error.copy} /> : error.text}</p>}
        {conflict && <button type="button" className="bw-outline" data-component="button-outline" data-component-name="button-outline" onClick={()=>window.location.reload()}><Copy k="pages.onboarding.reload-workspace" /></button>}
        <div className="bw-form-actions">{step>0 ? <button className="bw-text-link" data-component="text-action" data-component-name="text-action" type="button" onClick={()=>go(step-1)}><Copy k="pages.onboarding.back" /></button> : <Link href="/" className="bw-text-link" data-component="text-action" data-component-name="text-action"><Copy k="pages.onboarding.back-to-website" /></Link>}<button type="submit" className="bw-button" data-component="button-primary" data-component-name="button-primary"><Copy k={step===4?"pages.onboarding.open-my-workspace":"pages.onboarding.continue"} /><Icon name="arrow_forward" size={20}/></button></div>
        <p className="bw-form-footer"><Copy k="pages.onboarding.for-human-review-not-legal-advice" /> <Link href="/privacy/"><Copy k="pages.onboarding.your-data" /></Link></p>
      </form>
    </main>
  </div>;
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Brand } from "@/components/brand";
import { Icon } from "@/components/icon";
import { CATEGORIES, MARKETS, SOURCES, emptyWorkspace, loadWorkspace, saveWorkspace, toggleValue, type Workspace } from "@/lib/bev-watch";

const STEPS = ["Your business", "Your markets", "Your sources", "Your briefing", "Ready to review"];

export default function OnboardingPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const baseline = useRef<Workspace>(emptyWorkspace());
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { const loaded=loadWorkspace();setWorkspace(loaded);baseline.current=loaded; }, []);
  function change(patch: Partial<Workspace>) { setWorkspace(w => ({...w, ...patch})); setError(""); }
  function go(next: number) { setStep(next); setError(""); window.setTimeout(() => heading.current?.focus(), 0); }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && (!workspace.company.trim() || workspace.categories.length === 0)) { setError("Add your business name and choose at least one beverage category."); return; }
    if (step === 1 && workspace.markets.length === 0) { setError("Choose at least one market to continue."); return; }
    if (step === 2 && workspace.sources.length === 0) { setError("Choose at least one source for your watchlist."); return; }
    const next = {...workspace, company: workspace.company.trim(), completed: step === 4 || workspace.completed};
    if (step === 1) next.sources = next.sources.filter(id => SOURCES.some(s=>s.id===id && next.markets.includes(s.market)));
    try {
      if (!saveWorkspace(next,baseline.current)) { setError("Your browser could not save the workspace. Allow site storage, then try again."); return; }
    } catch (reason) {
      setConflict(true);setError(reason instanceof Error?reason.message:"Reload the workspace before saving again.");return;
    }
    baseline.current=next;
    setWorkspace(next);
    if (step === 4) router.push("/workspace/"); else go(step + 1);
  }
  const suggested = SOURCES.filter(s => workspace.markets.includes(s.market));
  return <div className="bw-onboarding">
    <header className="bw-container bw-onboard-header"><Brand/><Link href="/workspace/" className="bw-text-link">Explore first <Icon name="arrow_forward" size={18}/></Link></header>
    <main id="main" className="bw-container bw-onboard-grid">
      <aside><h2>A watchlist<br/>that knows<br/><em>your business.</em></h2><ol aria-label="Setup progress">{STEPS.map((s,i)=><li key={s} aria-current={step===i ? "step" : undefined}><span>{i<step ? <Icon name="check_circle" size={20}/> : i+1}</span>{s}</li>)}</ol><p>Your choices are saved in this browser as you continue. No account or payment is created.</p></aside>
      <form onSubmit={submit} className="bw-onboard-form">
        <div className="bw-step-count">Step {step+1} of {STEPS.length}</div>
        <h1 tabIndex={-1} ref={heading}>{["What do you make?", "Where do you sell?", "Build your source list.", "Make the briefing yours.", "Your watchlist is ready."][step]}</h1>
        <p className="bw-form-intro">{["Start with the business and beverage categories you want to keep in focus.", "Choose your current markets. You can add more as your business grows.", "Choose the official sources your team wants to review. These are watchlist preferences; live monitoring is not active.", "Set your preferred review rhythm. Email delivery is not active in the public preview.", "Review your choices, then explore the workspace with clearly labeled sample updates."][step]}</p>
        {step===0 && <><label className="bw-field">Business name<input autoComplete="organization" maxLength={100} value={workspace.company} onChange={e=>change({company:e.target.value})} placeholder="Your beverage business" required/></label><fieldset><legend>Beverage categories</legend><div className="bw-choice-grid">{CATEGORIES.map(c=><label key={c} className={`bw-choice ${workspace.categories.includes(c)?"is-selected":""}`}><input type="checkbox" checked={workspace.categories.includes(c)} onChange={()=>change({categories:toggleValue(workspace.categories,c)})}/><span>{c}</span></label>)}</div></fieldset></>}
        {step===1 && <fieldset><legend className="bw-sr-only">Markets</legend><div className="bw-choice-stack">{MARKETS.map(m=><label className={`bw-choice ${workspace.markets.includes(m)?"is-selected":""}`} key={m}><input type="checkbox" checked={workspace.markets.includes(m)} onChange={()=>change({markets:toggleValue(workspace.markets,m)})}/><span>{m}</span></label>)}</div></fieldset>}
        {step===2 && <fieldset><legend>Sources for your selected markets</legend><div className="bw-choice-stack">{suggested.map(s=><label key={s.id} className={`bw-choice ${workspace.sources.includes(s.id)?"is-selected":""}`}><input type="checkbox" checked={workspace.sources.includes(s.id)} onChange={()=>change({sources:toggleValue(workspace.sources,s.id)})}/><span><strong>{s.name}</strong><small>{s.topic}</small></span></label>)}</div></fieldset>}
        {step===3 && <><fieldset><legend>Preferred briefing frequency</legend><div className="bw-choice-grid">{(["Daily","Weekly"] as const).map(c=><label className={`bw-choice ${workspace.cadence===c?"is-selected":""}`} key={c}><input type="radio" name="cadence" checked={workspace.cadence===c} onChange={()=>change({cadence:c})}/><span>{c}</span></label>)}</div></fieldset><div className="bw-note"><Icon name="article"/><p>You can export a sample briefing from your workspace. This preference is saved for future setup; it does not schedule a run or an email.</p></div></>}
        {step===4 && <><dl className="bw-summary"><div><dt>Business</dt><dd>{workspace.company}</dd></div><div><dt>Beverages</dt><dd>{workspace.categories.join(", ")}</dd></div><div><dt>Markets</dt><dd>{workspace.markets.join(", ")}</dd></div><div><dt>Sources</dt><dd>{SOURCES.filter(s=>workspace.sources.includes(s.id)).map(s=>s.short).join(", ")}</dd></div><div><dt>Briefing preference</dt><dd>{workspace.cadence}</dd></div></dl><div className="bw-note"><Icon name="check_circle"/><p>Preview access is free. No card, account, live monitoring, or paid subscription is created.</p></div></>}
        {error && <p role="alert" className="bw-error">{error}</p>}
        {conflict && <button type="button" className="bw-outline" onClick={()=>window.location.reload()}>Reload workspace</button>}
        <div className="bw-form-actions">{step>0 ? <button className="bw-text-link" type="button" onClick={()=>go(step-1)}>Back</button> : <Link href="/" className="bw-text-link">Back to website</Link>}<button type="submit" className="bw-button">{step===4?"Open my workspace":"Continue"}<Icon name="arrow_forward" size={20}/></button></div>
        <p className="bw-form-footer">For human review. Not legal advice. <Link href="/privacy/">Your data</Link></p>
      </form>
    </main>
  </div>;
}

"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Brand } from "@/components/brand";
import { Icon } from "@/components/icon";
import type { IconName } from "@/lib/icons.generated";
import { CATEGORIES, MARKETS, SOURCES, SAMPLE_UPDATES, PLAN_FEATURES, WORKSPACE_STORAGE, briefingText, downloadText, emptyWorkspace, loadWorkspace, parseWorkspace, restoreProduct, saveWorkspace, toggleValue, type Product, type Workspace } from "@/lib/bev-watch";

const NAV: {id:string; label:string; icon:IconName}[] = [
  {id:"overview",label:"Overview",icon:"dashboard"}, {id:"updates",label:"Review queue",icon:"difference"},
  {id:"portfolio",label:"Your portfolio",icon:"description"}, {id:"sources",label:"Sources",icon:"database"},
  {id:"briefings",label:"Briefings",icon:"article"}, {id:"membership",label:"Membership",icon:"lock"},
  {id:"settings",label:"Settings",icon:"settings"},
];

function ProductForm({ initial, markets, onSave, onCancel }: { initial?:Product; markets:string[]; onSave:(p:Product)=>void; onCancel:()=>void }) {
  const [name,setName] = useState(initial?.name || "");
  const [category,setCategory] = useState(initial?.category || CATEGORIES[0]);
  const [ingredients,setIngredients] = useState(initial?.ingredients || "");
  const [selected,setSelected] = useState(initial?.markets || markets);
  const [error,setError] = useState("");
  function submit(e:FormEvent) {
    e.preventDefault();
    if (!name.trim() || !selected.length) {setError("Add a product name and at least one market.");return;}
    onSave({id:initial?.id || crypto.randomUUID(),name:name.trim(),category,ingredients:ingredients.trim(),markets:selected});
  }
  return <form className="bw-product-form" onSubmit={submit}><h2>{initial?"Edit product":"Add your first product"}</h2><div className="bw-form-grid"><label className="bw-field">Product name<input autoFocus required maxLength={120} placeholder="e.g. Sparkling lemon tea" value={name} onChange={e=>setName(e.target.value)}/></label><label className="bw-field">Beverage category<select value={category} onChange={e=>setCategory(e.target.value)}>{CATEGORIES.map(c=><option key={c}>{c}</option>)}</select></label><label className="bw-field bw-full">Ingredients and claims<textarea rows={3} maxLength={2000} placeholder="e.g. Tea, lemon, vitamin C. No added sugar." value={ingredients} onChange={e=>setIngredients(e.target.value)}/></label></div><fieldset><legend>Markets for this product</legend><div className="bw-check-row">{MARKETS.map(m=><label key={m}><input type="checkbox" checked={selected.includes(m)} onChange={()=>setSelected(toggleValue(selected,m))}/>{m}</label>)}</div></fieldset>{error && <p role="alert" className="bw-error">{error}</p>}<div className="bw-actions"><button className="bw-button" type="submit">Save product</button><button className="bw-text-link" type="button" onClick={onCancel}>Cancel</button></div></form>;
}

export default function WorkspacePage() {
  const params = useSearchParams();
  const view = NAV.some(n=>n.id===params.get("view")) ? params.get("view")! : "overview";
  const [workspace,setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [ready,setReady] = useState(false);
  const [notice,setNotice] = useState("");
  const [error,setError] = useState("");
  const [conflict,setConflict] = useState(false);
  const [query,setQuery] = useState("");
  const [filter,setFilter] = useState("all");
  const [expanded,setExpanded] = useState<string|null>(null);
  const [editing,setEditing] = useState<Product|"new"|null>(null);
  const [confirmClear,setConfirmClear] = useState(false);
  const [deleted,setDeleted] = useState<Product|null>(null);
  const [draftName,setDraftName] = useState("");
  const [draftCadence,setDraftCadence] = useState<Workspace["cadence"]>("Weekly");
  const importRef = useRef<HTMLInputElement>(null);
  useEffect(()=>{const w=loadWorkspace();setWorkspace(w);setDraftName(w.company);setDraftCadence(w.cadence);setReady(true);},[]);
  useEffect(()=>{setNotice("");setError("");setQuery("");setFilter("all");setExpanded(null);},[view]);
  function update(next:Workspace,message="Saved in this browser.",replace=false):boolean {
    try {
      if (!saveWorkspace(next,replace?undefined:workspace)) {setError("Your browser could not save this change. Allow site storage and try again.");return false;}
    } catch (reason) {
      setConflict(true);setNotice("");setError(reason instanceof Error?reason.message:"Reload the workspace before saving again.");return false;
    }
    setWorkspace(next);setNotice(message);setError("");setConflict(false);return true;
  }
  function saveProduct(product:Product) {
    const products=workspace.products.some(p=>p.id===product.id)?workspace.products.map(p=>p.id===product.id?product:p):[...workspace.products,product];
    if(update({...workspace,products},"Product saved in this browser."))setEditing(null);
  }
  async function importWorkspace(file?:File) {
    if(!file)return;
    try {
      if(file.size>1024*1024)throw new Error("Choose a workspace export smaller than 1 MB.");
      const restored=parseWorkspace(JSON.parse(await file.text()));
      if(!restored)throw new Error("This file is not a valid Bev Watch workspace export.");
      if(update(restored,"Workspace restored in this browser.",true)){setDraftName(restored.company);setDraftCadence(restored.cadence);setDeleted(null);setEditing(null);}
    }catch(reason){setError(reason instanceof Error?reason.message:"Could not import the workspace.");}
    if(importRef.current)importRef.current.value="";
  }
  function clearWorkspace() {
    try {localStorage.removeItem(WORKSPACE_STORAGE);const w=emptyWorkspace();setWorkspace(w);setDraftName("");setDraftCadence("Weekly");setConfirmClear(false);setDeleted(null);setNotice("This browser workspace has been cleared.");setError("");setConflict(false);}
    catch {setError("Your browser could not clear the workspace. Clear this site's storage in browser settings.");}
  }
  const pending=SAMPLE_UPDATES.filter(u=>!workspace.reviewed.includes(u.id));
  const filtered=SAMPLE_UPDATES.filter(u=>(`${u.title} ${u.category} ${u.source} ${u.market}`.toLowerCase().includes(query.toLowerCase())) && (filter==="all" || (filter==="unreviewed" && !workspace.reviewed.includes(u.id)) || (filter==="saved" && workspace.saved.includes(u.id)) || (filter==="reviewed" && workspace.reviewed.includes(u.id))));
  const current=NAV.find(n=>n.id===view)!;
  return <div className="bw-workspace">
    <a className="bw-skip" href="#workspace-main">Skip to workspace</a>
    <aside className="bw-sidebar"><Brand/><div className="bw-company"><strong>{ready ? workspace.company || "Your workspace" : "Your workspace"}</strong><span>Preview access</span></div><nav aria-label="Workspace">{NAV.map(n=><Link key={n.id} href={`/workspace/?view=${n.id}`} aria-current={view===n.id?"page":undefined}><Icon name={n.icon} size={21}/><span>{n.label}</span></Link>)}</nav><div className="bw-sidebar-bottom"><p>Built around your business.</p><Link href="/onboarding/" className="bw-text-link">{workspace.completed?"Edit setup":"Finish setup"}<Icon name="arrow_forward" size={17}/></Link><Link href="/" className="bw-back-site">Back to website</Link></div></aside>
    <div className="bw-workspace-body"><header className="bw-workspace-top"><span>{current.label}</span><Link href="/privacy/">Saved on this device <Icon name="lock" size={15}/></Link></header><main id="workspace-main">
      <div className="bw-preview-banner"><Icon name="article" size={20}/><p><strong>Preview workspace.</strong> Regulatory updates are synthetic examples. Live monitoring, email, accounts, and paid subscriptions are not active.</p></div>
      <header className="bw-page-heading"><div><h1>{view==="overview"?"Your next move, in focus.":current.label}</h1><p>{({overview:"A clear place to review what could matter to your beverage business.",updates:"Explore the review workflow using illustrative regulatory updates.",portfolio:"Keep your products, ingredients, and market context together.",sources:"Choose the official sources you want on your watchlist.",briefings:"A useful starting point for your next regulatory conversation.",membership:"Your access and subscription details, in one place.",settings:"Your workspace, preferences, and data."} as Record<string,string>)[view]}</p></div>{view==="overview" && <Link href="/workspace/?view=portfolio" className="bw-button"><Icon name="add" size={19}/>Add a product</Link>}{view==="portfolio" && !editing && <button type="button" className="bw-button" onClick={()=>setEditing("new")}><Icon name="add" size={19}/>Add product</button>}</header>
      {notice && <p className="bw-notice" role="status">{notice}</p>}{error && <p className="bw-error" role="alert">{error}</p>}{conflict && <button type="button" className="bw-outline" onClick={()=>window.location.reload()}>Reload workspace</button>}
      {!ready ? <p aria-live="polite">Loading your browser workspace…</p> : <>
      {view==="overview" && <>
        {!workspace.completed && <div className="bw-setup-callout"><div><h2>Make This Workspace Yours.</h2><p>Choose your beverages, markets, and sources in a few simple steps.</p></div><Link href="/onboarding/" className="bw-button">Complete setup <Icon name="arrow_forward" size={19}/></Link></div>}
        <div className="bw-overview-grid"><section><div className="bw-section-heading"><h2>Sample Review Queue</h2><Link href="/workspace/?view=updates">View all <Icon name="arrow_forward" size={17}/></Link></div><p className="bw-section-note">{pending.length} sample updates left to review</p><div className="bw-update-list">{pending.slice(0,3).map(u=><Link href={`/workspace/?view=updates&item=${u.id}`} key={u.id} className="bw-update-row"><span className={`bw-tag ${u.priority==="Review first"?"bw-tag-warm":""}`}>{u.priority}</span><h3>{u.title}</h3><p>{u.source} · {u.market} · Synthetic example</p><Icon name="chevron_right" size={20}/></Link>)}{!pending.length && <div className="bw-empty"><Icon name="check_circle" size={32}/><h3>Your Sample Queue Is Clear.</h3><p>Find your review decisions in the reviewed tab.</p><Link href="/workspace/?view=updates">View reviewed updates</Link></div>}</div></section><aside className="bw-context"><h2>Your Business in View</h2><dl><div><dt>Products</dt><dd>{workspace.products.length || "No products yet"}</dd></div><div><dt>Beverage categories</dt><dd>{workspace.categories.join(", ") || "Choose in setup"}</dd></div><div><dt>Markets</dt><dd>{workspace.markets.join(", ") || "Choose in setup"}</dd></div><div><dt>Selected sources</dt><dd>{workspace.sources.length}</dd></div><div><dt>Briefing preference</dt><dd>{workspace.cadence}</dd></div></dl><Link className="bw-text-link" href="/workspace/?view=briefings">Open sample briefing <Icon name="arrow_forward" size={18}/></Link></aside></div>
      </>}
      {view==="updates" && <><div className="bw-toolbar"><div className="bw-tabs" role="group" aria-label="Filter updates">{[["all","All"],["unreviewed","To review"],["saved","Saved"],["reviewed","Reviewed"]].map(([id,label])=><button key={id} type="button" aria-pressed={filter===id} onClick={()=>setFilter(id)}>{label}</button>)}</div><label className="bw-search"><Icon name="search" size={19}/><input type="search" aria-label="Search sample updates" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search updates"/></label></div><div className="bw-update-list">{filtered.map(u=>{const open=expanded===u.id || (expanded===null&&params.get("item")===u.id);const reviewed=workspace.reviewed.includes(u.id);return <article className="bw-update-detail" key={u.id}><div className="bw-update-meta"><span className={`bw-tag ${u.priority==="Review first"?"bw-tag-warm":""}`}>{reviewed?"Reviewed":u.priority}</span><span>{u.source} · {u.market} · Synthetic example</span></div><button className="bw-update-title" type="button" aria-expanded={open} aria-controls={`detail-${u.id}`} onClick={()=>setExpanded(open?"":u.id)}><h2>{u.title}</h2><Icon name={open?"close":"chevron_right"} size={22}/></button>{open && <div className="bw-update-content" id={`detail-${u.id}`}><p>{u.summary}</p><h3>Suggested Review</h3><p>{u.action}</p><a href={u.url} target="_blank" rel="noreferrer" className="bw-text-link">Visit source website <Icon name="arrow_forward" size={18}/></a><small>This link opens the source website, not a document supporting this invented update.</small><div className="bw-actions"><button type="button" className="bw-button" onClick={()=>update({...workspace,reviewed:toggleValue(workspace.reviewed,u.id)},reviewed?"Moved back to the review queue.":"Sample update marked reviewed.")}>{reviewed?"Mark as unreviewed":"Mark reviewed"}</button><button type="button" className="bw-outline" aria-pressed={workspace.saved.includes(u.id)} onClick={()=>update({...workspace,saved:toggleValue(workspace.saved,u.id)})}>{workspace.saved.includes(u.id)?"Remove from saved":"Save for later"}</button></div></div>}</article>;})}{!filtered.length && <div className="bw-empty"><h2>No Sample Updates Here.</h2><p>Try another search or filter.</p><button type="button" className="bw-text-link" onClick={()=>{setQuery("");setFilter("all");}}>Show all updates</button></div>}</div></>}
      {view==="portfolio" && <>{editing && <ProductForm key={editing==="new"?"new":editing.id} initial={editing==="new"?undefined:editing} markets={workspace.markets} onSave={saveProduct} onCancel={()=>setEditing(null)}/>}<div className="bw-product-list">{workspace.products.map(p=><article key={p.id}><div><span className="bw-tag">{p.category}</span><h2>{p.name}</h2><p>{p.ingredients || "No ingredients or claims added."}</p><small>{p.markets.join(" · ")}</small></div><div className="bw-product-actions"><button type="button" className="bw-text-link" onClick={()=>setEditing(p)}>Edit</button><button type="button" className="bw-text-link" onClick={()=>{if(update({...workspace,products:workspace.products.filter(x=>x.id!==p.id)},"Product removed. You can undo this change."))setDeleted(p);}}>Remove<span className="bw-sr-only"> {p.name}</span></button></div></article>)}</div>{deleted && <p className="bw-notice">Removed {deleted.name}. <button type="button" className="bw-text-link" onClick={()=>{if(update({...workspace,products:restoreProduct(workspace.products,deleted)},"Product restored."))setDeleted(null);}}>Undo</button></p>}{!workspace.products.length && !editing && <div className="bw-empty"><Icon name="description" size={38}/><h2>Start with What You Make.</h2><p>Add a beverage, its ingredients, and the markets where you sell it.</p><button type="button" className="bw-button" onClick={()=>setEditing("new")}>Add your first product</button></div>}</>}
      {view==="sources" && <><label className="bw-search bw-source-search"><Icon name="search" size={19}/><input type="search" placeholder="Search sources, topics, or markets" aria-label="Search sources" value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="bw-source-list">{SOURCES.filter(s=>`${s.name} ${s.short} ${s.market} ${s.topic}`.toLowerCase().includes(query.toLowerCase())).map(s=><article key={s.id}><span className="bw-source-monogram">{s.short}</span><div><h2>{s.name}</h2><p>{s.topic}</p><small>{s.market} · Official source</small><a href={s.url} target="_blank" rel="noreferrer">Visit website</a></div><button type="button" className={workspace.sources.includes(s.id)?"bw-outline":"bw-button"} aria-pressed={workspace.sources.includes(s.id)} onClick={()=>update({...workspace,sources:toggleValue(workspace.sources,s.id)},"Source preference saved. Live monitoring is not active.")}>{workspace.sources.includes(s.id)?"Selected":"Select source"}</button></article>)}</div>{!SOURCES.some(s=>`${s.name} ${s.short} ${s.market} ${s.topic}`.toLowerCase().includes(query.toLowerCase())) && <div className="bw-empty"><h2>No Sources Match That Search.</h2><button type="button" className="bw-text-link" onClick={()=>setQuery("")}>Show all sources</button></div>}</>}
      {view==="briefings" && <><div className="bw-briefing-actions"><div><h2>Your Sample Briefing</h2><p>Built from the preview examples, with your portfolio context.</p></div><button type="button" className="bw-button" onClick={()=>{downloadText("bev-watch-preview-briefing.txt",briefingText(workspace));setNotice("Sample briefing exported.");}}><Icon name="download" size={19}/>Export briefing</button></div><article className="bw-briefing-paper"><Brand/><h2>{workspace.company || "Your beverage business"}</h2><p>Preview regulatory briefing · {workspace.cadence} preference</p><div className="bw-note"><p>All updates below are synthetic examples. This document contains no current regulatory findings or confirmed product impacts.</p></div>{SAMPLE_UPDATES.map(u=><section key={u.id}><span className="bw-tag">{u.category}</span><h3>{u.title}</h3><p>{u.summary}</p><p><strong>Suggested review:</strong> {u.action}</p></section>)}<small>For human review. Not legal advice. No monitoring or email delivery is active.</small></article></>}
      {view==="membership" && <div className="bw-membership"><div><span className="bw-tag">Your current access</span><h2>Public Preview</h2><p>Try the workflow at no charge. You have no paid subscription, renewal date, or payment method.</p><ul>{PLAN_FEATURES.map(f=><li key={f}><Icon name="check_circle" size={19}/>{f}</li>)}</ul><Link href="/pricing/" className="bw-button">View membership details <Icon name="arrow_forward" size={19}/></Link></div><div><h3>Paid Membership Is Coming.</h3><p>Subscription pricing and checkout have not been activated. No payment is collected by this website.</p><h3>What Happens Next?</h3><p>A production launch needs secure accounts, hosted monitoring, and a payment provider. Your preview does not enroll you automatically.</p></div></div>}
      {view==="settings" && <div className="bw-settings"><section><h2>Workspace Preferences</h2><form onSubmit={e=>{e.preventDefault();update({...workspace,company:draftName.trim(),cadence:draftCadence});}}><label className="bw-field">Business name<input required maxLength={100} value={draftName} onChange={e=>setDraftName(e.target.value)}/></label><label className="bw-field">Briefing preference<select value={draftCadence} onChange={e=>setDraftCadence(e.target.value as Workspace["cadence"])}><option>Daily</option><option>Weekly</option></select></label><p className="bw-caption">This saves a preference. It does not schedule monitoring or email.</p><button className="bw-button" type="submit">Save preferences</button></form></section><section><h2>Your Data</h2><p>Your workspace stays in this browser. Export a backup before switching devices or clearing site storage.</p><div className="bw-actions"><button type="button" className="bw-outline" onClick={()=>downloadText("bev-watch-workspace.json",JSON.stringify(workspace,null,2),"application/json")}>Export workspace</button><button type="button" className="bw-text-link" onClick={()=>importRef.current?.click()}>Import backup</button><input ref={importRef} type="file" accept="application/json,.json" className="bw-sr-only" aria-label="Import workspace backup" onChange={e=>void importWorkspace(e.target.files?.[0])}/></div><p className="bw-caption">Import replaces the workspace in this browser. Export your current workspace first.</p><Link href="/privacy/" className="bw-text-link">Read about your data</Link></section><section><h2>Start Fresh</h2><p>Remove the saved business, products, source preferences, and review decisions from this browser.</p>{confirmClear?<div className="bw-note"><div><p>Clear this browser workspace? Export a backup above to keep a copy.</p><div className="bw-actions"><button type="button" className="bw-outline" onClick={clearWorkspace}>Clear this browser workspace</button><button type="button" className="bw-text-link" onClick={()=>setConfirmClear(false)}>Keep my workspace</button></div></div></div>:<button type="button" className="bw-text-link" onClick={()=>setConfirmClear(true)}>Clear this browser workspace</button>}</section></div>}
      </>}
      <footer className="bw-workspace-footer">Bev Watch helps organize reviews. A qualified person must verify regulatory information. <Link href="/privacy/">Privacy</Link></footer>
    </main></div>
  </div>;
}

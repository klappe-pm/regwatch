import Link from "next/link";
import { BRAND } from "@/lib/bev-watch";
export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link href="/" className="bw-brand" aria-label={`${BRAND} home`}><svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#b33a36"/><path d="M8 11h5.5a5 5 0 0 1 0 10H8V11Zm5.5 0H24l-4 10h-6.5M8 16h12" stroke="white" strokeWidth="2" strokeLinejoin="round"/></svg>{!compact && <span>Bev <span className="bw-brand-light">Watch</span></span>}</Link>;
}
export function PublicHeader() {
  return <header className="bw-header"><div className="bw-container bw-header-inner"><Brand/><nav aria-label="Website"><Link href="/#how-it-works">How it works</Link><Link href="/pricing/">Membership</Link><Link href="/workspace/" className="bw-header-workspace">Workspace</Link><Link href="/onboarding/" className="bw-button bw-button-small">Get started</Link></nav></div></header>;
}
export function PublicFooter() {
  return <footer className="bw-footer bw-container"><Brand/><p>Beverage regulation, in focus.</p><nav aria-label="Footer"><Link href="/pricing/">Membership</Link><Link href="/privacy/">Privacy</Link><Link href="/workspace/">Explore the preview</Link></nav><small>For human review. Not legal advice.</small></footer>;
}

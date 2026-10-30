import { Copy } from "@/components/copy";
import { t } from "@/lib/copy.generated";
import Link from "next/link";
export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link href="/" className="bw-brand" data-component="brand" data-component-name="brand" aria-label={t("global.brand.home-label")}><svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><rect width="32" height="32" rx="9" fill="var(--ds-color-brand-red)"/><path d="M8 11h5.5a5 5 0 0 1 0 10H8V11Zm5.5 0H24l-4 10h-6.5M8 16h12" stroke="var(--ds-color-raised)" strokeWidth="2" strokeLinejoin="round"/></svg>{!compact && <span><Copy k="global.brand.bev" /> <span className="bw-brand-light"><Copy k="global.brand.watch" /></span></span>}</Link>;
}
export function PublicHeader() {
  return <header className="bw-header"><div className="bw-container bw-header-inner"><Brand/><nav data-component="public-navigation" data-component-name="public-navigation" aria-label={t("global.brand.website")}><Link href="/#how-it-works"><Copy k="global.brand.how-it-works" /></Link><Link href="/pricing/"><Copy k="global.brand.membership" /></Link><Link href="/workspace/" className="bw-header-workspace"><Copy k="global.brand.workspace" /></Link><Link href="/onboarding/" className="bw-button bw-button-small" data-component="button-primary" data-component-name="button-primary"><Copy k="global.brand.get-started" /></Link></nav></div></header>;
}
export function PublicFooter() {
  return <footer className="bw-footer bw-container"><Brand/><p><Copy k="global.brand.beverage-regulation-in-focus" /></p><nav data-component="public-navigation" data-component-name="public-navigation" aria-label={t("global.brand.footer")}><Link href="/pricing/"><Copy k="global.brand.membership" /></Link><Link href="/privacy/"><Copy k="global.brand.privacy" /></Link><Link href="/workspace/"><Copy k="global.brand.explore-the-preview" /></Link></nav><small><Copy k="global.brand.for-human-review-not-legal-advice" /></small></footer>;
}

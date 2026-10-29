import { Copy } from "@/components/copy";
import { PublicHeader, PublicFooter } from "@/components/brand";
export default function PrivacyPage() {
  return <div className="bw-public"><PublicHeader/><main id="main" className="bw-container bw-prose"><h1><Copy k="pages.privacy.your-preview-workspace" /></h1><h2><Copy k="pages.privacy.what-this-website-stores" /></h2><p><Copy k="pages.privacy.the-public-preview-stores-your-company-name" /></p><h2><Copy k="pages.privacy.control-your-data" /></h2><p><Copy k="pages.privacy.export-a-copy-in-workspace-settings-use" /></p><h2><Copy k="pages.privacy.hosting-and-external-links" /></h2><p><Copy k="pages.privacy.the-hosting-provider-may-process-standard-request" /></p><h2><Copy k="pages.privacy.subscriptions-and-email" /></h2><p><Copy k="pages.privacy.the-preview-collects-no-payment-details-or" /></p></main><PublicFooter/></div>;
}

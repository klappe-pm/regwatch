import { OverviewView } from "@/views/overview";
import { PublicHome } from "@/views/public-home";

// The public build shows the landing page at /; the local application shows its overview there.
export default function HomePage() {
  if (process.env.NEXT_PUBLIC_BEV_WATCH_MODE !== "hosted-preview") return <OverviewView />;
  return <PublicHome />;
}

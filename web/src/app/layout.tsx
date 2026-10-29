import { t } from "@/lib/copy.generated";
import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";

import { Shell } from "@/components/shell";
import { StatusProvider } from "@/components/status";
import { Loading } from "@/components/ui";

import "../../design/tokens.css";
import "./globals.css";
import "../../design/components.css";

export const metadata: Metadata = {
  title: { default: t("global.metadata.bev-watch-beverage-regulation-in-focus"), template: t("global.metadata.s-bev-watch") },
  description: t("global.metadata.bring-your-beverage-products-markets-and-regulatory"),
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <StatusProvider>
          <Shell>
            <Suspense fallback={<Loading />}>{children}</Suspense>
          </Shell>
        </StatusProvider>
      </body>
    </html>
  );
}

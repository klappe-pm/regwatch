import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";

import { Shell } from "@/components/shell";
import { StatusProvider } from "@/components/status";
import { Loading } from "@/components/ui";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Bev Watch | Beverage regulation, in focus", template: "%s | Bev Watch" },
  description: "Bring your beverage products, markets, and regulatory source reviews into one clear workspace.",
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

import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";

import { Shell } from "@/components/shell";
import { StatusProvider } from "@/components/status";
import { Loading } from "@/components/ui";

import "./globals.css";

export const metadata: Metadata = {
  title: "Regwatch",
  description: "Regulatory changes and their candidate impacts, for human review.",
  robots: { index: false, follow: false },
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

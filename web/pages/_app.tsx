import { CacheProvider, type EmotionCache } from "@emotion/react";
import { DesignSystemProvider } from "@klappe/design-system";
import { createCspEmotionCache } from "@klappe/design-system/emotion";
import type { AppProps } from "next/app";
import { useEffect } from "react";

import { Meta } from "@/components/public";
import { Shell } from "@/components/shell";
import { StatusProvider } from "@/components/status";
import { themeOptions, themeSpec } from "@/design";
import { isPublicPage } from "@/lib/bev-watch";
import { t } from "@/lib/text";

import "../design/ds.css";
import "../styles/app.css";

// The local server sends `style-src 'self'`, which blocks the <style> elements Emotion normally writes. This cache
// puts Material UI's styles into adopted constructed style sheets in the `mui` cascade layer, so the policy holds
// and the plain style sheets in styles/ win. One cache per page; at build time _document passes its own.
let browserCache: EmotionCache | undefined;

// One theme for every page, generated from DESIGN.md. The copy comes from the copy documents through
// one createCopy function that throws on a missing key, so a page cannot build with one.
export default function App({ Component, pageProps, router, emotionCache }: AppProps & { emotionCache?: EmotionCache }) {
  const light = isPublicPage(router.pathname);

  // The public pages stay light; the local application follows the system setting.
  useEffect(() => {
    if (light) document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
  }, [light]);

  return (
    <CacheProvider value={emotionCache ?? (browserCache ??= createCspEmotionCache())}>
      <DesignSystemProvider spec={themeSpec} copy={t} onMissing="throw" themeOptions={themeOptions}>
        <Meta />
        <StatusProvider>
          <Shell>
            <Component {...pageProps} />
          </Shell>
        </StatusProvider>
      </DesignSystemProvider>
    </CacheProvider>
  );
}

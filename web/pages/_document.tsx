import { createServerEmotionCache } from "@klappe/design-system/emotion";
import { DocumentHeadTags, documentGetInitialProps, type DocumentHeadTagsProps } from "@mui/material-nextjs/v16-pagesRouter";
import { Head, Html, Main, NextScript, type DocumentContext, type DocumentProps } from "next/document";

import { isPublicPage } from "@/lib/bev-watch";

type Props = DocumentProps & DocumentHeadTagsProps & { light: boolean };

// The Pages Router keeps every executable script an external file. The Emotion styles rendered here
// are moved into style sheet files by `ds csp`, so the export holds no inline style.
export default function Document(props: Props) {
  return (
    <Html lang="en" data-theme={props.light ? "light" : undefined}>
      <Head>
        <DocumentHeadTags {...props} />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" sizes="any" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}

Document.getInitialProps = async (ctx: DocumentContext) => {
  const props = await documentGetInitialProps(ctx, { emotionCache: createServerEmotionCache() });
  return { ...props, light: isPublicPage(ctx.pathname) };
};

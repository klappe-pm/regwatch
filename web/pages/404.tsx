import Head from "next/head";

import { PageHeader, TextLink } from "@/components/ui";
import { t } from "@/lib/text";

const p = (key: string) => t(`pages.not-found.content.${key}`);

export default function NotFound() {
  return (
    <>
      <Head>
        <meta name="robots" content="noindex" key="not-found" />
      </Head>
      <PageHeader title={p("title")} description={p("description")} />
      <TextLink href="/">{p("link")}</TextLink>
    </>
  );
}

"use client";

import { useStatus } from "@/components/status";
import { EmptyState, Loading, Locked, PageHeader } from "@/components/ui";

export default function NewslettersPage() {
  const { status } = useStatus();
  return (
    <>
      <PageHeader
        title="Newsletters"
        description="A send-ready newsletter assembled from the period's changes, as HTML email with a plain text part. Regwatch does not send email; you review it and send it from your own mail tool."
      />
      {status === null ? <Loading /> : null}
      {status && !status.premium ? <Locked feature="Newsletters" /> : null}
      {status?.premium ? (
        <EmptyState command="regwatch render --formats newsletter">
          Newsletters assembled from the period&apos;s changes will appear here in a later release.
          Until then, render a newsletter from a saved briefing with the command below.
        </EmptyState>
      ) : null}
    </>
  );
}

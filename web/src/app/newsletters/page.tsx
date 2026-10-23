"use client";

import { useStatus } from "@/components/status";
import { EmptyState, ErrorNote, Loading, Locked, PageHeader } from "@/components/ui";
import { premiumView } from "@/lib/premium-view";

export default function NewslettersPage() {
  const { status, error } = useStatus();
  const view = premiumView(status, error);
  return (
    <>
      <PageHeader
        title="Newsletters"
        description="A send-ready newsletter assembled from the period's changes, as HTML email with a plain text part. Regwatch does not send email; you review it and send it from your own mail tool."
      />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature="Newsletters" /> : null}
      {view === "open" ? (
        <EmptyState command="regwatch render --formats newsletter">
          Newsletters assembled from the period&apos;s changes will appear here in a later release.
          Until then, render a newsletter from a saved briefing with the command below.
        </EmptyState>
      ) : null}
    </>
  );
}

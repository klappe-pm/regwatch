"use client";

import { useStatus } from "@/components/status";
import { EmptyState, ErrorNote, Loading, Locked, PageHeader } from "@/components/ui";
import { premiumView } from "@/lib/premium-view";

export default function DocumentsPage() {
  const { status, error } = useStatus();
  const view = premiumView(status, error);
  return (
    <>
      <PageHeader
        title="Documents"
        description="Documents built from a template that follows your design specification: headings, colours, typeface and logo, set once in Settings."
      />
      {view === "loading" ? <Loading /> : null}
      {view === "error" && error ? <ErrorNote message={error} /> : null}
      {view === "locked" ? <Locked feature="Documents" /> : null}
      {view === "open" ? (
        <EmptyState command="regwatch render --formats docx">
          Documents built from your template will appear here in a later release. Until then, render
          a Word document from a saved briefing with the command below.
        </EmptyState>
      ) : null}
    </>
  );
}

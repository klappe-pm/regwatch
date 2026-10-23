"use client";

import { useStatus } from "@/components/status";
import { EmptyState, Loading, Locked, PageHeader } from "@/components/ui";

export default function DocumentsPage() {
  const { status } = useStatus();
  return (
    <>
      <PageHeader
        title="Documents"
        description="Documents built from a template that follows your design specification: headings, colours, typeface and logo, set once in Settings."
      />
      {status === null ? <Loading /> : null}
      {status && !status.premium ? <Locked feature="Documents" /> : null}
      {status?.premium ? (
        <EmptyState command="regwatch render --formats docx">
          Documents built from your template will appear here in a later release. Until then, render
          a Word document from a saved briefing with the command below.
        </EmptyState>
      ) : null}
    </>
  );
}

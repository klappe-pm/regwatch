import Link from "next/link";

import { PageHeader } from "@/components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page Not Found" description="There is no page at this address." />
      <Link className="text-structure underline underline-offset-2" href="/">
        Go to the overview
      </Link>
    </>
  );
}

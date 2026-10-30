import { t, type CopyKey } from "@/lib/copy.generated";

export function Copy({ k }: { k: CopyKey }) {
  return <span data-copy-key={k}>{t(k)}</span>;
}

import { cn } from "@/lib/utils";
import { SEVERITY_LABEL, SEVERITY_STYLES } from "@/constants/severity";
import type { Severity } from "@/types";

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        SEVERITY_STYLES[severity],
        className
      )}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

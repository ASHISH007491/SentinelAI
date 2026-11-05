import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { SEVERITY_LABEL, SEVERITY_ORDER, SEVERITY_STYLES } from "@/constants/severity";
import type { Severity } from "@/types";

export function SeverityCards({ counts }: { counts: Record<Severity, number> }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {SEVERITY_ORDER.map((sev) => (
        <Card key={sev}>
          <CardContent className="p-4">
            <span className={cn("inline-flex rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", SEVERITY_STYLES[sev])}>
              {SEVERITY_LABEL[sev]}
            </span>
            <p className="mt-2 text-2xl font-semibold">{counts[sev] ?? 0}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

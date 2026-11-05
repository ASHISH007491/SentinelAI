"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import { useRuns } from "@/hooks/use-runs";
import { timeAgo } from "@/lib/utils";

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability analysis",
  phishing: "Phishing analysis",
  code_review: "Code review",
};
const WORKFLOWS = ["all", "vuln", "phishing", "code_review"] as const;

/** Chronological Security Operations timeline of runs, filterable by workflow. */
export function OperationsTimeline() {
  const { isAuthenticated } = useAuth();
  const { data: runs, isLoading } = useRuns(isAuthenticated);
  const [filter, setFilter] = useState<(typeof WORKFLOWS)[number]>("all");

  const events = useMemo(() => {
    const list = (runs ?? []).slice().sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    return filter === "all" ? list : list.filter((r) => r.workflow === filter);
  }, [runs, filter]);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <CardTitle>Security Operations Timeline</CardTitle>
        <div className="flex flex-wrap gap-1.5">
          {WORKFLOWS.map((w) => (
            <button
              key={w}
              onClick={() => setFilter(w)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                filter === w ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
              }`}
            >
              {w === "all" ? "All" : WORKFLOW_LABEL[w]}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        )}
        {!isLoading && events.length === 0 && (
          <EmptyState title="No operations yet" description="Runs will appear here as you analyse artefacts." />
        )}
        {!isLoading && events.length > 0 && (
          <ol className="relative space-y-4 border-l border-border pl-6">
            {events.map((r) => (
              <li key={r.id} className="relative">
                <span className="absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
                <div className="flex flex-wrap items-center gap-2">
                  <a href={`/runs/${r.id}`} className="text-sm font-medium hover:underline">
                    {WORKFLOW_LABEL[r.workflow] ?? r.workflow} · Run #{r.id}
                  </a>
                  <StatusBadge status={r.status} />
                  <Badge variant="outline">{r.architecture === "multi" ? "Multi-agent" : "Legacy"}</Badge>
                  {r.created_at && (
                    <span className="text-xs text-muted-foreground">{timeAgo(r.created_at)}</span>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

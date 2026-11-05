"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { useRuns } from "@/hooks/use-runs";
import { useAuth } from "@/hooks/use-auth";
import { timeAgo } from "@/lib/utils";

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability",
  phishing: "Phishing",
  code_review: "Code Review",
};

/** Live recent runs from the backend. Degrades gracefully when offline. */
export function RecentRuns() {
  const { isAuthenticated } = useAuth();
  const { data, isLoading, isError } = useRuns(isAuthenticated);

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Recent Runs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}

        {!isLoading && (isError || !data || data.length === 0) && (
          <EmptyState
            title={isError ? "Backend unreachable" : "No runs yet"}
            description={isError ? "Start the API to see live runs." : "Kick off an analysis to populate this list."}
          />
        )}

        {!isLoading && data && data.length > 0 &&
          data.slice(0, 6).map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="flex items-center justify-between rounded-lg border border-border/50 bg-card/40 p-3 transition-colors hover:bg-accent/40"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">Run #{run.id}</span>
                <Badge variant="secondary">{WORKFLOW_LABEL[run.workflow] ?? run.workflow}</Badge>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={run.status} />
                {run.created_at && <span className="text-xs text-muted-foreground">{timeAgo(run.created_at)}</span>}
              </div>
            </Link>
          ))}
      </CardContent>
    </Card>
  );
}

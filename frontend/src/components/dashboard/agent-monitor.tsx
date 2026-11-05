"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import { useRun, useRuns } from "@/hooks/use-runs";
import { timeAgo } from "@/lib/utils";

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_COLOR: Record<string, string> = {
  completed: "text-emerald-500",
  running: "text-amber-500",
  failed: "text-red-500",
  queued: "text-muted-foreground",
};

/** Live per-agent telemetry from the most recent run (status, latency, tokens, confidence). */
export function AgentMonitor() {
  const { isAuthenticated } = useAuth();
  const { data: runs } = useRuns(isAuthenticated);
  const latestId = useMemo(() => {
    const sorted = (runs ?? []).slice().sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    return sorted[0]?.id ?? null;
  }, [runs]);
  const { data: detail, isLoading } = useRun(latestId);

  const agents = detail?.agent_outputs ?? [];
  const status = detail?.status ?? "queued";

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>AI Agent Monitor</CardTitle>
        {detail && <Badge variant="outline">Run #{detail.id}</Badge>}
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
        {!isLoading && agents.length === 0 && (
          <EmptyState title="No agent activity" description="Run an analysis to see live agent status." />
        )}
        {!isLoading && agents.map((a) => {
          const out = a.output as { confidence?: number; findings?: { confidence?: number }[] } | undefined;
          const conf = out?.confidence ?? out?.findings?.[0]?.confidence;
          return (
            <div key={a.id} className="flex items-center justify-between rounded-lg border border-border/50 p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{titleCase(a.agent_name)}</p>
                <p className="text-xs text-muted-foreground">
                  {detail?.completed_at ? timeAgo(detail.completed_at) : "just now"}
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className={STATUS_COLOR[status] ?? ""}>
                  {status === "completed" ? "Completed" : titleCase(status)}
                </span>
                <span className="text-muted-foreground">{Math.round(a.latency_ms)} ms</span>
                <span className="text-muted-foreground">{a.prompt_tokens + a.completion_tokens} tok</span>
                {conf != null && (
                  <Badge variant="secondary">{Math.round(conf * 100)}% conf</Badge>
                )}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

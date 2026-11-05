"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { useRuns } from "@/hooks/use-runs";

/** Dashboard hero driven by real runs (replaces the hardcoded placeholder). */
export function LiveHero() {
  const { isAuthenticated } = useAuth();
  const { data } = useRuns(isAuthenticated);
  const runs = data ?? [];
  const completed = runs.filter((r) => r.status === "completed").length;
  const running = runs.filter((r) => r.status === "running").length;

  const headline =
    completed > 0
      ? `${completed} completed ${completed === 1 ? "analysis" : "analyses"} in your workspace`
      : "Run your first analysis to see live results";

  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">Good to see you, Analyst</p>
          <h2 className="text-xl font-semibold">{headline}</h2>
          <p className="text-sm text-muted-foreground">
            {runs.length} total runs · {running} in progress · orchestrated by the multi-agent engine.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/operations">View operations timeline</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

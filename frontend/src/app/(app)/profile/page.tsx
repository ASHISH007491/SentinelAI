"use client";

import Link from "next/link";
import { Mail, Shield } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { useAuth } from "@/hooks/use-auth";
import { useRuns } from "@/hooks/use-runs";
import { timeAgo } from "@/lib/utils";

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability",
  phishing: "Phishing",
  code_review: "Code Review",
};

/** Real account details from /auth/me plus run statistics from the backend. */
export default function ProfilePage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const { data: runs, isLoading: runsLoading } = useRuns(isAuthenticated);

  const all = runs ?? [];
  const stats = [
    { label: "Analyses run", value: all.length },
    { label: "Completed", value: all.filter((r) => r.status === "completed").length },
    { label: "Failed", value: all.filter((r) => r.status === "failed").length },
  ];

  const initials = (user?.email ?? "?").slice(0, 2).toUpperCase();
  const recent = [...all].sort((a, b) => b.id - a.id).slice(0, 5);

  return (
    <>
      <PageHeader
        title="Profile"
        description="Your account and analysis activity."
        actions={
          <Button variant="outline" asChild>
            <Link href="/settings">Settings</Link>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardContent className="flex flex-col items-center gap-3 p-6 text-center">
            <Avatar className="h-20 w-20">
              <AvatarFallback className="text-xl">{initials}</AvatarFallback>
            </Avatar>
            <div>
              {isLoading ? (
                <Skeleton className="h-6 w-40" />
              ) : (
                <p className="text-lg font-semibold">{user?.email ?? "Not signed in"}</p>
              )}
              <Badge variant="secondary" className="mt-1">
                <Shield className="mr-1 h-3 w-3" /> Analyst
              </Badge>
            </div>
            {user?.email && (
              <div className="w-full space-y-2 pt-2 text-sm text-muted-foreground">
                <p className="flex items-center justify-center gap-2">
                  <Mail className="h-4 w-4" /> {user.email}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <div className="grid grid-cols-3 gap-4">
            {stats.map((s) => (
              <Card key={s.label}>
                <CardContent className="p-5 text-center">
                  {runsLoading ? (
                    <Skeleton className="mx-auto h-8 w-12" />
                  ) : (
                    <p className="text-2xl font-semibold tabular-nums">{s.value}</p>
                  )}
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {runsLoading &&
                Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}

              {!runsLoading && recent.length === 0 && (
                <EmptyState
                  title="No activity yet"
                  description="Runs you start will appear here."
                />
              )}

              {!runsLoading &&
                recent.map((run) => (
                  <Link
                    key={run.id}
                    href={`/runs/${run.id}`}
                    className="flex items-center justify-between rounded-lg border border-border/50 bg-card/40 p-3 transition-colors hover:bg-accent/40"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">Run #{run.id}</span>
                      <Badge variant="secondary">
                        {WORKFLOW_LABEL[run.workflow] ?? run.workflow}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusBadge status={run.status} />
                      {run.created_at && (
                        <span className="text-xs text-muted-foreground">
                          {timeAgo(run.created_at)}
                        </span>
                      )}
                    </div>
                  </Link>
                ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

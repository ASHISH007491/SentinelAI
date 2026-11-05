"use client";

import Link from "next/link";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRuns } from "@/hooks/use-runs";
import { useAuth } from "@/hooks/use-auth";
import { timeAgo } from "@/lib/utils";

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability",
  phishing: "Phishing",
  code_review: "Code Review",
};

/** All analysis runs for the signed-in analyst, newest first. */
export default function RunsPage() {
  const { isAuthenticated } = useAuth();
  const { data, isLoading, isError } = useRuns(isAuthenticated);

  const runs = [...(data ?? [])].sort((a, b) => b.id - a.id);

  return (
    <>
      <PageHeader
        title="Runs"
        description="Every analysis run you have started, with its workflow, architecture and status."
      />

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}

          {!isLoading && (isError || runs.length === 0) && (
            <div className="p-6">
              <EmptyState
                title={isError ? "Backend unreachable" : "No runs yet"}
                description={
                  isError
                    ? "Start the API to see your runs."
                    : "Start an analysis from Vulnerability, Phishing or Code Review to see it here."
                }
              />
            </div>
          )}

          {!isLoading && !isError && runs.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Architecture</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Started</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id} className="cursor-pointer hover:bg-accent/40">
                    <TableCell className="font-medium">
                      <Link href={`/runs/${run.id}`} className="hover:underline">
                        Run #{run.id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {WORKFLOW_LABEL[run.workflow] ?? run.workflow}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {run.architecture === "single" ? "Single-LLM" : "Multi-agent"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={run.status} />
                    </TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">
                      {run.created_at ? timeAgo(run.created_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

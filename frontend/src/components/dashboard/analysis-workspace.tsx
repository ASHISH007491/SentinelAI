"use client";

import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { LiveRunPanel } from "@/components/dashboard/live-run-panel";
import { extractFindings, countSeverities } from "@/lib/findings";
import type { RunDetailDto } from "@/services/runs.service";
import type { Severity, WorkflowType } from "@/types";

interface AnalysisWorkspaceProps {
  workflow: WorkflowType;
  runTitle: string;
  accept: string;
  hint: string;
  /** Agent whose raw verdict/summary is worth surfacing, if present. */
  verdictAgents?: string[];
}

const ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

/**
 * Live analysis surface: upload an artefact, run the orchestrator against the
 * real backend, and render the findings and agent verdicts it returns.
 * No mock data — an empty state is shown until a run completes.
 */
export function AnalysisWorkspace({
  workflow,
  runTitle,
  accept,
  hint,
  verdictAgents = [],
}: AnalysisWorkspaceProps) {
  const [detail, setDetail] = useState<RunDetailDto | null>(null);

  const findings = extractFindings(detail);
  const counts = countSeverities(findings);

  const verdicts = (detail?.agent_outputs ?? []).filter((o) =>
    verdictAgents.includes(o.agent_name),
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-4">
        <LiveRunPanel
          workflow={workflow}
          title={runTitle}
          accept={accept}
          hint={hint}
          onComplete={setDetail}
        />

        <Card>
          <CardHeader>
            <CardTitle>Findings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {findings.length === 0 && (
              <EmptyState
                title="No findings yet"
                description="Upload a file above to run the agents and populate this list."
              />
            )}

            {findings.map((f, i) => (
              <div
                key={`${f.title}-${i}`}
                className="rounded-lg border border-border/50 bg-card/40 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{f.title}</p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {f.component || "artefact"}
                      {f.cve ? ` · ${f.cve}` : ""}
                      {typeof f.line === "number" ? ` · line ${f.line}` : ""}
                    </p>
                  </div>
                  <SeverityBadge severity={f.severity as Severity} />
                </div>
                {f.recommendation && (
                  <p className="mt-2 text-xs text-muted-foreground">{f.recommendation}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Severity Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {findings.length === 0 && (
              <p className="text-sm text-muted-foreground">Awaiting a completed run.</p>
            )}
            {findings.length > 0 &&
              ORDER.map((s) => (
                <div key={s} className="flex items-center justify-between">
                  <SeverityBadge severity={s} />
                  <span className="text-sm font-medium tabular-nums">{counts[s]}</span>
                </div>
              ))}
          </CardContent>
        </Card>

        {verdicts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" /> Agent Verdict
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {verdicts.map((o) => {
                const out = o.output as Record<string, unknown>;
                const verdict = String(out.verdict ?? out.label ?? "");
                const summary = String(out.summary ?? "");
                return (
                  <div key={o.id} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium capitalize">
                        {o.agent_name.replace(/_/g, " ")}
                      </span>
                      {verdict && <Badge variant="secondary">{verdict}</Badge>}
                    </div>
                    {summary && (
                      <p className="text-xs text-muted-foreground">{summary}</p>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

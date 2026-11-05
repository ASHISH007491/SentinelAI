"use client";

import { SeverityCards } from "@/components/dashboard/severity-cards";
import { VulnerabilityTable } from "@/components/dashboard/vulnerability-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { countSeverities, extractFindings, findingToRow } from "@/lib/findings";
import type { RunDetailDto } from "@/services/runs.service";

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability",
  phishing: "Phishing",
  code_review: "Code Review",
};

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ReportPayload {
  executive_summary?: string;
  recommendations?: string[];
}

/** Full run view: header, consolidated report, per-agent trace, and findings. */
export function RunDetail({ detail }: { detail: RunDetailDto }) {
  const findings = extractFindings(detail);
  const counts = countSeverities(findings);
  const rows = findings.map((f, i) => findingToRow(f, i, detail.created_at));

  const reportOut = detail.agent_outputs.find((o) => o.agent_name === "security_report");
  const report = (reportOut?.output as { report?: ReportPayload } | undefined)?.report;
  const agents = detail.agent_outputs.filter((o) => o.agent_name !== "security_report");

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-6">
          <h2 className="text-lg font-semibold">
            {WORKFLOW_LABEL[detail.workflow] ?? detail.workflow} run #{detail.id}
          </h2>
          <StatusBadge status={detail.status} />
          <Badge variant="outline">
            {detail.architecture === "multi" ? "Multi-agent" : "Legacy"} engine
          </Badge>
          {detail.artefacts?.[0] && (
            <span className="text-sm text-muted-foreground">{detail.artefacts[0].filename}</span>
          )}
        </CardContent>
      </Card>

      {report?.executive_summary && (
        <Card>
          <CardHeader>
            <CardTitle>Security Report</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{report.executive_summary}</p>
            {report.recommendations && report.recommendations.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {report.recommendations.slice(0, 8).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Agent trace</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => {
            const out = a.output as { summary?: string; findings?: unknown[] } | undefined;
            const fcount = (out?.findings ?? []).length;
            return (
              <div key={a.id} className="rounded-lg border p-3">
                <p className="text-sm font-medium">{titleCase(a.agent_name)}</p>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                  {out?.summary || "—"}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{fcount} finding{fcount === 1 ? "" : "s"}</span>
                  <span>{a.prompt_tokens + a.completion_tokens} tok</span>
                  <span>{Math.round(a.latency_ms)} ms</span>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <SeverityCards counts={counts} />
      <VulnerabilityTable rows={rows} />
    </div>
  );
}

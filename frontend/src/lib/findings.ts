import type { AgentFinding, RunDetailDto } from "@/services/runs.service";
import type { Severity, Vulnerability } from "@/types";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

function coerceSeverity(s: string): Severity {
  const v = s.toLowerCase() as Severity;
  return SEVERITIES.includes(v) ? v : "info";
}

/**
 * Pull the consolidated findings out of a completed run. Prefers the report
 * agent's compiled data, then the prioritisation agent, then any agent output.
 */
export function extractFindings(detail: RunDetailDto | null): AgentFinding[] {
  if (!detail) return [];
  const byName = (name: string) => detail.agent_outputs.find((o) => o.agent_name === name);

  const report = byName("report");
  const reportFindings = (report?.output?.data as { findings?: AgentFinding[] } | undefined)?.findings;
  if (reportFindings?.length) return reportFindings;

  for (const name of ["prioritisation", "detection"]) {
    const out = byName(name);
    const findings = (out?.output as { findings?: AgentFinding[] } | undefined)?.findings;
    if (findings?.length) return findings;
  }
  return [];
}

export function countSeverities(findings: AgentFinding[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) counts[coerceSeverity(f.severity)] += 1;
  return counts;
}

/** Map a backend finding to the row shape the findings table renders. */
export function findingToRow(finding: AgentFinding, index: number, discoveredAt?: string): Vulnerability {
  return {
    id: `f${index}`,
    title: finding.title,
    cve: finding.cve ?? undefined,
    severity: coerceSeverity(finding.severity),
    cvss: finding.cvss ?? 0,
    component: finding.component || "artefact",
    status: "open",
    recommendation: finding.recommendation || "Review and remediate.",
    discoveredAt: discoveredAt ?? new Date().toISOString(),
  };
}

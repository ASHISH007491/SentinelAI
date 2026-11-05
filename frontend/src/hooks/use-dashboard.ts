"use client";

import { useQueries } from "@tanstack/react-query";
import { useRuns } from "@/hooks/use-runs";
import { runsService, type RunDetailDto, type RunDto } from "@/services/runs.service";
import { extractFindings, countSeverities } from "@/lib/findings";
import type { ActivityItem, AgentInfo, AgentState, Severity } from "@/types";

/** How many recent runs to pull details for when aggregating findings. */
const DETAIL_DEPTH = 12;

const WORKFLOW_LABEL: Record<string, string> = {
  vuln: "Vulnerability",
  phishing: "Phishing",
  code_review: "Code Review",
};

const AGENT_DESCRIPTION: Record<string, string> = {
  detection: "Surfaces findings from the artefact",
  prioritisation: "Ranks findings by exploitability",
  indicator_extraction: "Extracts phishing indicators",
  phishing_verdict: "Reaches a phishing verdict",
  code_review: "Flags vulnerable code patterns",
  advisor: "Executive recommendations",
  report: "Compiles the deliverable",
};

/** Weighted penalty per severity, used to turn findings into a 0-100 score. */
const PENALTY: Record<Severity, number> = {
  critical: 12,
  high: 6,
  medium: 2,
  low: 0.5,
  info: 0,
};

function titleise(name: string): string {
  return name
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function dayKey(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short" });
}

/**
 * Derives every dashboard figure from real backend data: the runs list plus
 * details for the most recent runs. No mock data is used anywhere.
 */
export function useDashboardStats(enabled: boolean) {
  const runsQuery = useRuns(enabled);
  const runs: RunDto[] = runsQuery.data ?? [];

  const recentIds = [...runs]
    .sort((a, b) => b.id - a.id)
    .slice(0, DETAIL_DEPTH)
    .map((r) => r.id);

  const detailQueries = useQueries({
    queries: recentIds.map((id) => ({
      queryKey: ["runs", "detail", id],
      queryFn: () => runsService.get(id),
      enabled: enabled && recentIds.length > 0,
      staleTime: 30_000,
    })),
  });

  const details = detailQueries
    .map((q) => q.data)
    .filter((d): d is RunDetailDto => Boolean(d));

  // --- findings + severity -------------------------------------------------
  const allFindings = details.flatMap((d) => extractFindings(d));
  const severityCounts = countSeverities(allFindings);

  const penalty = (Object.keys(PENALTY) as Severity[]).reduce(
    (sum, s) => sum + severityCounts[s] * PENALTY[s],
    0,
  );
  const securityScore = Math.max(0, Math.min(100, Math.round(100 - penalty)));

  // --- workflow volume -----------------------------------------------------
  const volumeMap = new Map<string, number>();
  for (const r of runs) {
    const label = WORKFLOW_LABEL[r.workflow] ?? r.workflow;
    volumeMap.set(label, (volumeMap.get(label) ?? 0) + 1);
  }
  const workflowVolume = [...volumeMap.entries()].map(([name, value]) => ({ name, value }));

  // --- run trend: started vs completed, last 7 days ------------------------
  const days: string[] = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(now.getDate() - i);
    days.push(d.toLocaleDateString(undefined, { weekday: "short" }));
  }
  const trendMap = new Map(days.map((d) => [d, { day: d, detected: 0, resolved: 0 }]));
  for (const r of runs) {
    if (!r.created_at) continue;
    const key = dayKey(r.created_at);
    const slot = trendMap.get(key);
    if (!slot) continue;
    slot.detected += 1;
    if (r.status === "completed") slot.resolved += 1;
  }
  const runTrend = [...trendMap.values()];

  // --- risk per recent run -------------------------------------------------
  const riskTimeline = [...details]
    .sort((a, b) => a.id - b.id)
    .map((d) => {
      const counts = countSeverities(extractFindings(d));
      const p = (Object.keys(PENALTY) as Severity[]).reduce(
        (sum, s) => sum + counts[s] * PENALTY[s],
        0,
      );
      return { week: `#${d.id}`, risk: Math.max(0, Math.min(100, Math.round(p))) };
    });

  // --- agents seen in real runs -------------------------------------------
  const agentMap = new Map<string, { count: number; latency: number; last: string }>();
  for (const d of details) {
    for (const o of d.agent_outputs) {
      const prev = agentMap.get(o.agent_name) ?? { count: 0, latency: 0, last: "" };
      const last = o.created_at ?? d.completed_at ?? prev.last;
      agentMap.set(o.agent_name, {
        count: prev.count + 1,
        latency: prev.latency + (o.latency_ms || 0),
        last: last > prev.last ? last : prev.last,
      });
    }
  }
  const agents: AgentInfo[] = [...agentMap.entries()].map(([name, v]) => {
    const avg = v.count ? Math.round(v.latency / v.count) : 0;
    const state: AgentState = avg === 0 ? "idle" : avg > 5000 ? "degraded" : "online";
    return {
      id: name,
      name: titleise(name),
      description: AGENT_DESCRIPTION[name] ?? `Ran in ${v.count} run(s)`,
      state,
      lastRun: v.last || undefined,
      latencyMs: avg,
    };
  });

  // --- activity feed from real runs ---------------------------------------
  const severityOf = (d: RunDetailDto): Severity | undefined => {
    const f = extractFindings(d);
    const order: Severity[] = ["critical", "high", "medium", "low", "info"];
    return order.find((s) => f.some((x) => x.severity?.toLowerCase() === s));
  };
  const activities: ActivityItem[] = [...details]
    .sort((a, b) => b.id - a.id)
    .slice(0, 6)
    .map((d) => ({
      id: `run-${d.id}`,
      actor: WORKFLOW_LABEL[d.workflow] ?? d.workflow,
      action: d.status === "completed" ? "completed analysis on" : `is ${d.status} for`,
      target: d.artefacts[0]?.filename ?? `Run #${d.id}`,
      timestamp: d.completed_at ?? d.created_at ?? new Date().toISOString(),
      severity: severityOf(d),
    }));

  const criticalCount = severityCounts.critical;
  const completedCount = runs.filter((r) => r.status === "completed").length;
  const detailsLoading = detailQueries.some((q) => q.isLoading);

  return {
    isLoading: runsQuery.isLoading || detailsLoading,
    isError: runsQuery.isError,
    hasRuns: runs.length > 0,
    runs,
    totalRuns: runs.length,
    completedCount,
    criticalCount,
    totalFindings: allFindings.length,
    severityCounts,
    securityScore,
    workflowVolume,
    runTrend,
    riskTimeline,
    agents,
    activities,
  };
}

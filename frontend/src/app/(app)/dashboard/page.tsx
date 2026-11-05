"use client";

import Link from "next/link";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { MetricCard } from "@/components/dashboard/metric-card";
import { SecurityScore } from "@/components/dashboard/security-score";
import { AgentStatusCard } from "@/components/dashboard/agent-card";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { RecentRuns } from "@/components/dashboard/recent-runs";
import {
  RiskTimelineChart,
  SeverityPieChart,
  ThreatTrendChart,
  WorkflowVolumeChart,
} from "@/components/dashboard/charts";
import { useAuth } from "@/hooks/use-auth";
import { useDashboardStats } from "@/hooks/use-dashboard";

export default function DashboardPage() {
  const { isAuthenticated, user } = useAuth();
  const s = useDashboardStats(isAuthenticated);

  const headline = !s.hasRuns
    ? "No analyses yet — start your first run"
    : s.criticalCount > 0
      ? `${s.criticalCount} critical finding${s.criticalCount === 1 ? "" : "s"} need your attention`
      : `${s.totalFindings} finding${s.totalFindings === 1 ? "" : "s"} across ${s.totalRuns} run${s.totalRuns === 1 ? "" : "s"}`;

  return (
    <>
      <PageHeader
        title="Security Dashboard"
        description="Live posture derived from your analysis runs."
        actions={
          <Button asChild>
            <Link href="/vulnerability-analysis">New analysis</Link>
          </Button>
        }
      />

      {/* Welcome / hero */}
      <Card className="overflow-hidden">
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              Good to see you{user?.email ? `, ${user.email}` : ""}
            </p>
            {s.isLoading ? (
              <Skeleton className="h-7 w-72" />
            ) : (
              <h2 className="text-xl font-semibold">{headline}</h2>
            )}
            <p className="text-sm text-muted-foreground">
              {s.totalRuns} total run{s.totalRuns === 1 ? "" : "s"} · {s.completedCount} completed ·
              orchestrated by the multi-agent engine.
            </p>
          </div>
          <Button variant="outline" asChild>
            <Link href="/operations">View operations timeline</Link>
          </Button>
        </CardContent>
      </Card>

      {!s.isLoading && !s.hasRuns && (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title="Nothing to show yet"
              description="Run a vulnerability, phishing or code-review analysis and this dashboard will populate with real results."
            />
          </CardContent>
        </Card>
      )}

      {(s.isLoading || s.hasRuns) && (
        <>
          {/* Metric row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Security Score"
              value={s.securityScore}
              hint="derived from open findings"
              icon="ShieldCheck"
              accent="text-emerald-500"
              index={0}
            />
            <MetricCard
              label="Critical Findings"
              value={s.severityCounts.critical}
              hint={`${s.totalFindings} findings total`}
              icon="ShieldAlert"
              accent="text-severity-critical"
              index={1}
            />
            <MetricCard
              label="High Findings"
              value={s.severityCounts.high}
              hint="across recent runs"
              icon="Bug"
              accent="text-severity-high"
              index={2}
            />
            <MetricCard
              label="Completed Runs"
              value={s.completedCount}
              hint={`of ${s.totalRuns} total`}
              icon="Activity"
              accent="text-severity-low"
              index={3}
            />
          </div>

          {/* Score + trends */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <SecurityScore score={s.securityScore} />
            <div className="lg:col-span-2">
              <ThreatTrendChart
                data={s.runTrend}
                title="Run Activity"
                description="Runs started vs. completed over the last 7 days"
              />
            </div>
          </div>

          {/* Charts grid */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <SeverityPieChart
              data={s.severityCounts}
              title="Risk Distribution"
              description="Findings by severity across recent runs"
            />
            <WorkflowVolumeChart
              data={s.workflowVolume}
              title="Workflow Volume"
              description="Runs by analysis type"
            />
            <RiskTimelineChart
              data={s.riskTimeline}
              title="Risk by Run"
              description="Weighted risk score per recent run"
            />
          </div>

          {/* Live runs + agents + quick actions */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-1">
              <RecentRuns />
            </div>
            <div className="lg:col-span-1">
              <AgentStatusCard agents={s.agents} />
            </div>
            <div className="lg:col-span-1">
              <QuickActions />
            </div>
          </div>

          {/* Activity */}
          <div className="grid grid-cols-1 gap-4">
            <ActivityFeed items={s.activities} />
          </div>
        </>
      )}
    </>
  );
}

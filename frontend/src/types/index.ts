/** Shared domain types for SentinelAI. */

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type RunStatus = "queued" | "running" | "completed" | "failed";

export type WorkflowType = "vuln" | "phishing" | "code_review";

export type AgentState = "online" | "degraded" | "offline" | "idle";

export interface NavItem {
  title: string;
  href: string;
  icon: string; // lucide icon name
  badge?: string;
}

export interface MetricCardData {
  label: string;
  value: string | number;
  delta?: number; // percentage change
  hint?: string;
  severity?: Severity;
}

export interface Vulnerability {
  id: string;
  title: string;
  cve?: string;
  severity: Severity;
  cvss: number;
  component: string;
  status: "open" | "in_review" | "resolved";
  recommendation: string;
  discoveredAt: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  state: AgentState;
  lastRun?: string;
  latencyMs?: number;
}

export interface ActivityItem {
  id: string;
  actor: string;
  action: string;
  target: string;
  timestamp: string;
  severity?: Severity;
}

export interface ReportItem {
  id: string;
  title: string;
  type: "executive" | "technical";
  workflow: WorkflowType;
  createdAt: string;
  status: "ready" | "generating";
}

export interface ApiError {
  detail: string;
  status: number;
}

export interface CveItem {
  id: string; // CVE-YYYY-NNNN
  title: string;
  severity: Severity;
  cvss: number;
  published: string;
  vendor: string;
  exploited: boolean;
}

export interface MitreTechnique {
  id: string; // Txxxx
  name: string;
  tactic: string;
  count: number;
}

export interface CodeFinding {
  id: string;
  line: number;
  rule: string;
  severity: Severity;
  message: string;
  recommendation: string;
}

export interface Recommendation {
  id: string;
  title: string;
  priority: "P0" | "P1" | "P2";
  impact: string;
  effort: "Low" | "Medium" | "High";
  confidence: number;
  rationale: string;
}

export interface ProjectItem {
  id: string;
  name: string;
  description: string;
  workflow: WorkflowType;
  score: number;
  openFindings: number;
  status: "active" | "archived";
  updatedAt: string;
}

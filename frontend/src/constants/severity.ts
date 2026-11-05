import type { Severity } from "@/types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

/** Tailwind utility groups per severity (text + subtle background + ring). */
export const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "text-severity-critical bg-severity-critical/10 ring-severity-critical/30",
  high: "text-severity-high bg-severity-high/10 ring-severity-high/30",
  medium: "text-severity-medium bg-severity-medium/10 ring-severity-medium/30",
  low: "text-severity-low bg-severity-low/10 ring-severity-low/30",
  info: "text-severity-info bg-severity-info/10 ring-severity-info/30",
};

export const SEVERITY_HEX: Record<Severity, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#22c55e",
  info: "#3b82f6",
};

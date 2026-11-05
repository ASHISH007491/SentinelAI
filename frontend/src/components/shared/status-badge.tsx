import { cn } from "@/lib/utils";
import type { AgentState, RunStatus } from "@/types";

const STATUS_DOT: Record<AgentState | RunStatus, string> = {
  online: "bg-emerald-500",
  idle: "bg-slate-400",
  degraded: "bg-amber-500",
  offline: "bg-rose-500",
  queued: "bg-slate-400",
  running: "bg-blue-500 animate-pulse",
  completed: "bg-emerald-500",
  failed: "bg-rose-500",
};

export function StatusBadge({ status }: { status: AgentState | RunStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium capitalize text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", STATUS_DOT[status])} aria-hidden />
      {status}
    </span>
  );
}

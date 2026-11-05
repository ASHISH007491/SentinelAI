import type { Metadata } from "next";
import { AgentMonitor } from "@/components/dashboard/agent-monitor";
import { OperationsTimeline } from "@/components/dashboard/operations-timeline";
import { PageHeader } from "@/components/shared/page-header";

export const metadata: Metadata = { title: "Operations" };

export default function OperationsPage() {
  return (
    <>
      <PageHeader
        title="Security Operations"
        description="Live AI agent status and a chronological timeline of security operations."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <AgentMonitor />
        </div>
        <div className="lg:col-span-2">
          <OperationsTimeline />
        </div>
      </div>
    </>
  );
}

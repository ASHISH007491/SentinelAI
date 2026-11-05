"use client";

import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { timeAgo } from "@/lib/utils";
import type { AgentInfo } from "@/types";

export function AgentStatusCard({ agents }: { agents: AgentInfo[] }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Agent Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {agents.map((agent, i) => (
          <motion.div
            key={agent.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/40 p-3"
          >
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary">
              <Bot className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{agent.name}</p>
              <p className="truncate text-xs text-muted-foreground">{agent.description}</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <StatusBadge status={agent.state} />
              {agent.lastRun && <span className="text-[11px] text-muted-foreground">{timeAgo(agent.lastRun)}</span>}
            </div>
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}

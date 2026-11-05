"use client";

import { useState } from "react";
import { Bot, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileUpload } from "@/components/shared/file-upload";
import { StatusBadge } from "@/components/shared/status-badge";
import { useCreateRun, useExecuteRun, useUploadArtefact } from "@/hooks/use-runs";
import type { RunDetailDto } from "@/services/runs.service";
import type { WorkflowType } from "@/types";

interface LiveRunPanelProps {
  workflow: WorkflowType;
  title?: string;
  accept?: string;
  hint?: string;
  onComplete?: (detail: RunDetailDto) => void;
}

/**
 * End-to-end run island: create -> upload -> execute against the live backend,
 * then render the orchestrator's agent outputs. Falls back to a toast if the
 * API is unreachable, so the page still works in static/demo mode.
 */
export function LiveRunPanel({ workflow, title = "Run Analysis", accept, hint, onComplete }: LiveRunPanelProps) {
  const createRun = useCreateRun();
  const upload = useUploadArtefact();
  const execute = useExecuteRun();

  const [stage, setStage] = useState<string>("");
  const [result, setResult] = useState<RunDetailDto | null>(null);
  const busy = stage !== "";

  async function onFile(file: File) {
    setResult(null);
    try {
      setStage("Creating run…");
      const run = await createRun.mutateAsync({ workflow });
      setStage("Uploading artefact…");
      await upload.mutateAsync({ runId: run.id, file });
      setStage("Running agents…");
      const detail = await execute.mutateAsync(run.id);
      setResult(detail);
      onComplete?.(detail);
      toast.success(`Analysis complete — ${detail.agent_outputs.length} agent(s)`);
    } catch (err) {
      const detail = (err as { detail?: string })?.detail ?? "Run failed — is the backend running?";
      toast.error(detail);
    } finally {
      setStage("");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          {title}
          {busy && (
            <span className="flex items-center gap-1.5 text-xs font-normal text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> {stage}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <FileUpload accept={accept} hint={hint} onFile={onFile} />

        {result && (
          <div className="space-y-2 rounded-lg border border-border/60 bg-card/40 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Run #{result.id}</span>
              <StatusBadge status={result.status} />
            </div>
            {result.agent_outputs.map((o) => (
              <div key={o.id} className="flex items-center gap-3 rounded-md border border-border/40 p-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Bot className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium capitalize">{o.agent_name.replace(/_/g, " ")}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {String((o.output as { summary?: string })?.summary ?? "completed")}
                  </p>
                </div>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> {Math.round(o.latency_ms)}ms
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

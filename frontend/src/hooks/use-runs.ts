"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { runsService } from "@/services/runs.service";
import type { WorkflowType } from "@/types";

const KEYS = {
  all: ["runs"] as const,
  detail: (id: number) => ["runs", id] as const,
};

/** List the current user's runs. Disabled until authenticated. */
export function useRuns(enabled = true) {
  return useQuery({ queryKey: KEYS.all, queryFn: runsService.list, enabled });
}

export function useRun(id: number | null) {
  return useQuery({
    queryKey: KEYS.detail(id ?? -1),
    queryFn: () => runsService.get(id as number),
    enabled: id != null,
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workflow, architecture = "multi" }: { workflow: WorkflowType; architecture?: "multi" | "single" }) =>
      runsService.create(workflow, architecture),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useUploadArtefact() {
  return useMutation({
    mutationFn: ({ runId, file }: { runId: number; file: File }) => runsService.uploadArtefact(runId, file),
  });
}

export function useExecuteRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: number) => runsService.execute(runId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: KEYS.all });
      qc.setQueryData(KEYS.detail(data.id), data);
    },
  });
}

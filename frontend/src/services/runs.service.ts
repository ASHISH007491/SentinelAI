import { apiClient } from "@/lib/api-client";
import type { RunStatus, WorkflowType } from "@/types";

export interface RunDto {
  id: number;
  workflow: WorkflowType;
  status: RunStatus;
  architecture: string;
  created_at?: string;
}

export interface ArtefactDto {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at?: string;
}

export interface AgentFinding {
  title: string;
  severity: string;
  cvss: number;
  component?: string;
  cve?: string | null;
  rule?: string | null;
  line?: number | null;
  evidence?: string;
  recommendation?: string;
  confidence?: number;
}

export interface AgentOutputDto {
  id: number;
  agent_name: string;
  output: Record<string, unknown>;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  created_at?: string;
}

export interface RunDetailDto extends RunDto {
  completed_at?: string;
  artefacts: ArtefactDto[];
  agent_outputs: AgentOutputDto[];
}

export const runsService = {
  list: () => apiClient.get<RunDto[]>("/runs"),
  get: (id: number) => apiClient.get<RunDetailDto>(`/runs/${id}`),
  create: (workflow: WorkflowType, architecture: "multi" | "single" = "multi") =>
    apiClient.post<RunDto>("/runs", { workflow, architecture }),
  execute: (id: number) => apiClient.post<RunDetailDto>(`/runs/${id}/execute`),
  uploadArtefact: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.postForm<ArtefactDto>(`/runs/${id}/artefacts`, form);
  },
};

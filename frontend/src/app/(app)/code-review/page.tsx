import type { Metadata } from "next";
import { PageHeader } from "@/components/shared/page-header";
import { AnalysisWorkspace } from "@/components/dashboard/analysis-workspace";

export const metadata: Metadata = { title: "Code Review" };

export default function CodeReviewPage() {
  return (
    <>
      <PageHeader
        title="Secure Code Review"
        description="Upload a source file to have the code-review agent flag vulnerable patterns and map them to CWEs."
      />
      <AnalysisWorkspace
        workflow="code_review"
        runTitle="Review Source File"
        accept=".py,.js,.ts,.java,.go,.rb,.php,.c,.cpp,.cs,.txt"
        hint="Source file (.py, .js, .ts, .java, .go, .php, .c, .cpp …)"
        verdictAgents={["code_review", "advisor"]}
      />
    </>
  );
}

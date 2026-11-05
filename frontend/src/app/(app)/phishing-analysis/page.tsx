import type { Metadata } from "next";
import { PageHeader } from "@/components/shared/page-header";
import { AnalysisWorkspace } from "@/components/dashboard/analysis-workspace";

export const metadata: Metadata = { title: "Phishing Analysis" };

export default function PhishingAnalysisPage() {
  return (
    <>
      <PageHeader
        title="Phishing Analysis"
        description="Submit a suspicious email to run indicator extraction and a phishing verdict against the live agents."
      />
      <AnalysisWorkspace
        workflow="phishing"
        runTitle="Analyse Email"
        accept=".eml,.msg,.txt"
        hint="Raw email (.eml / .msg) or pasted headers"
        verdictAgents={["phishing_verdict", "indicator_extraction", "advisor"]}
      />
    </>
  );
}

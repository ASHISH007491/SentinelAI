"use client";

import { useParams } from "next/navigation";
import { RunDetail } from "@/components/dashboard/run-detail";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useRun } from "@/hooks/use-runs";

export default function RunDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const raw = Array.isArray(rawId) ? rawId[0] : rawId;
  const id = Number(raw);
  const { data, isLoading, isError } = useRun(Number.isFinite(id) ? id : null);

  return (
    <>
      <PageHeader
        title="Run detail"
        description="Full multi-agent trace and the consolidated security report."
      />
      {isLoading && <Skeleton className="h-64 w-full" />}
      {!isLoading && (isError || !data) && (
        <EmptyState
          title="Run not found"
          description="This run may not exist, or the API is unreachable."
        />
      )}
      {data && <RunDetail detail={data} />}
    </>
  );
}

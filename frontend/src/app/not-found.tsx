import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center px-6 text-center">
      <div className="space-y-4">
        <p className="text-6xl font-semibold tracking-tight">404</p>
        <p className="text-muted-foreground">This page could not be found.</p>
        <Button asChild><Link href="/dashboard">Back to dashboard</Link></Button>
      </div>
    </div>
  );
}

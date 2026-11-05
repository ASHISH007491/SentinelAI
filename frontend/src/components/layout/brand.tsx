import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { siteConfig } from "@/config/site";

export function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 px-1" aria-label={siteConfig.name}>
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
        <ShieldCheck className="h-5 w-5" />
      </span>
      <span className={cn("flex flex-col leading-tight transition-opacity", collapsed && "hidden")}>
        <span className="text-sm font-semibold tracking-tight">{siteConfig.name}</span>
        <span className="text-[11px] text-muted-foreground">{siteConfig.tagline}</span>
      </span>
    </Link>
  );
}

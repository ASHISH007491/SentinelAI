import { siteConfig } from "@/config/site";

export function Footer() {
  return (
    <footer className="border-t border-border/60 px-6 py-4 text-xs text-muted-foreground">
      <div className="flex flex-col items-center justify-between gap-2 sm:flex-row">
        <p>
          © {new Date().getFullYear()} {siteConfig.name} · v{siteConfig.version}
        </p>
        <p className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
          All systems operational
        </p>
      </div>
    </footer>
  );
}

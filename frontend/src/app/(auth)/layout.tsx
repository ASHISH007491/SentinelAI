import { ShieldCheck } from "lucide-react";
import { siteConfig } from "@/config/site";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand / marketing panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border/60 bg-card/40 p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="text-sm font-semibold">{siteConfig.name}</span>
        </div>
        <div className="relative z-10 space-y-3">
          <h2 className="text-3xl font-semibold leading-tight">
            Multi-agent defense,<br />one copilot.
          </h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Detect vulnerabilities, investigate phishing, and review code with an
            orchestrated team of AI security agents.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} {siteConfig.name}</p>
        <div className="pointer-events-none absolute inset-0 app-aurora" aria-hidden />
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}

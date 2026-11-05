import Link from "next/link";
import { Code2, ListChecks, MailWarning, ShieldAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ACTIONS = [
  { title: "Scan for Vulnerabilities", href: "/vulnerability-analysis", icon: ShieldAlert, accent: "text-severity-critical" },
  { title: "Analyze Phishing Email", href: "/phishing-analysis", icon: MailWarning, accent: "text-severity-high" },
  { title: "Review Source Code", href: "/code-review", icon: Code2, accent: "text-severity-info" },
  { title: "View All Runs", href: "/runs", icon: ListChecks, accent: "text-severity-low" },
];

export function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick Actions</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3">
        {ACTIONS.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className="group flex flex-col gap-2 rounded-lg border border-border/60 bg-card/40 p-4 transition-colors hover:border-primary/50 hover:bg-accent/40"
          >
            <action.icon className={`h-5 w-5 ${action.accent}`} />
            <span className="text-sm font-medium">{action.title}</span>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}

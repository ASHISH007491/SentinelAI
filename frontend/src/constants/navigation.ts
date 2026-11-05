import type { NavItem } from "@/types";

/** Primary sidebar navigation. Icons are lucide-react component names. */
export const NAV_ITEMS: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
  { title: "Operations", href: "/operations", icon: "Activity" },
  { title: "Runs", href: "/runs", icon: "ListChecks" },
  { title: "Vulnerability Analysis", href: "/vulnerability-analysis", icon: "ShieldAlert" },
  { title: "Phishing Analysis", href: "/phishing-analysis", icon: "MailWarning" },
  { title: "Code Review", href: "/code-review", icon: "Code2" },
];

export const SECONDARY_NAV: NavItem[] = [
  { title: "Settings", href: "/settings", icon: "Settings" },
  { title: "Profile", href: "/profile", icon: "UserRound" },
];

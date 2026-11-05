"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useMounted } from "@/hooks/use-mounted";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const active = mounted ? theme : undefined;

  return (
    <div className="grid grid-cols-3 gap-3">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border p-4 text-sm transition-colors",
            active === opt.value ? "border-primary bg-primary/5 text-foreground" : "border-border/60 text-muted-foreground hover:bg-accent/40"
          )}
          aria-pressed={active === opt.value}
        >
          <opt.icon className="h-5 w-5" />
          {opt.label}
        </button>
      ))}
    </div>
  );
}

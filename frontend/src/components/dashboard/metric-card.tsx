"use client";

import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Icon } from "@/components/shared/icon";
import type { icons } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: number;
  hint?: string;
  icon?: keyof typeof icons;
  accent?: string; // tailwind text color class
  index?: number;
}

export function MetricCard({ label, value, delta, hint, icon, accent = "text-primary", index = 0 }: MetricCardProps) {
  const positive = (delta ?? 0) >= 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
    >
      <Card className="overflow-hidden transition-shadow hover:shadow-glow">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            {icon && (
              <span className={cn("rounded-lg bg-muted/60 p-2", accent)}>
                <Icon name={icon} className="h-4 w-4" />
              </span>
            )}
          </div>
          <div className="mt-3 flex items-end gap-2">
            <span className="text-3xl font-semibold tracking-tight">{value}</span>
            {typeof delta === "number" && (
              <span
                className={cn(
                  "mb-1 inline-flex items-center gap-0.5 text-xs font-medium",
                  positive ? "text-emerald-500" : "text-rose-500"
                )}
              >
                {positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {Math.abs(delta)}%
              </span>
            )}
          </div>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </CardContent>
      </Card>
    </motion.div>
  );
}

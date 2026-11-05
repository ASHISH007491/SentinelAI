"use client";

import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Radial security score gauge (SVG, theme-aware). */
export function SecurityScore({ score }: { score: number }) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const tone = score >= 80 ? "text-emerald-500" : score >= 60 ? "text-amber-500" : "text-rose-500";

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Overall Security Score</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center justify-center">
        <div className="relative grid place-items-center">
          <svg width="180" height="180" viewBox="0 0 180 180" className="-rotate-90">
            <circle cx="90" cy="90" r={radius} className="stroke-muted" strokeWidth="14" fill="none" />
            <motion.circle
              cx="90"
              cy="90"
              r={radius}
              className={tone}
              stroke="currentColor"
              strokeWidth="14"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="text-4xl font-semibold">{score}</span>
            <span className="text-xs text-muted-foreground">out of 100</span>
          </div>
        </div>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Posture is <span className={tone}>{score >= 80 ? "strong" : score >= 60 ? "moderate" : "at risk"}</span>.
          Continue triaging critical findings.
        </p>
      </CardContent>
    </Card>
  );
}

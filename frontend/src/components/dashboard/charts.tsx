"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SEVERITY_HEX } from "@/constants/severity";

const axisProps = {
  stroke: "hsl(var(--muted-foreground))",
  fontSize: 12,
  tickLine: false,
  axisLine: false,
} as const;

const tooltipStyle = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  fontSize: 12,
  color: "hsl(var(--popover-foreground))",
} as const;

interface ChartCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

function ChartCard({ title, description, children }: ChartCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full">{children}</div>
      </CardContent>
    </Card>
  );
}

export function ThreatTrendChart({
  data,
  title = "Security Trends",
  description = "Threats detected vs. resolved this week",
}: {
  data: { day: string; detected: number; resolved: number }[];
  title?: string;
  description?: string;
}) {
  return (
    <ChartCard title={title} description={description}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <defs>
            <linearGradient id="detected" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={SEVERITY_HEX.critical} stopOpacity={0.4} />
              <stop offset="95%" stopColor={SEVERITY_HEX.critical} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="resolved" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={SEVERITY_HEX.low} stopOpacity={0.4} />
              <stop offset="95%" stopColor={SEVERITY_HEX.low} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="day" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip contentStyle={tooltipStyle} />
          <Area type="monotone" dataKey="detected" stroke={SEVERITY_HEX.critical} fill="url(#detected)" strokeWidth={2} />
          <Area type="monotone" dataKey="resolved" stroke={SEVERITY_HEX.low} fill="url(#resolved)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function SeverityPieChart({
  data,
  title = "Risk Distribution",
  description = "Open findings by severity",
}: {
  data: Record<string, number>;
  title?: string;
  description?: string;
}) {
  const pie = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <ChartCard title={title} description={description}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
            {pie.map((entry) => (
              <Cell key={entry.name} fill={SEVERITY_HEX[entry.name as keyof typeof SEVERITY_HEX]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function WorkflowVolumeChart({
  data,
  title = "Threat Overview",
  description = "Analyses run by workflow",
}: {
  data: { name: string; value: number }[];
  title?: string;
  description?: string;
}) {
  return (
    <ChartCard title={title} description={description}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="name" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
          <Bar dataKey="value" radius={[8, 8, 0, 0]} fill={SEVERITY_HEX.info} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function RiskTimelineChart({
  data,
  title = "Risk Timeline",
  description = "Aggregate risk score trend",
}: {
  data: { week: string; risk: number }[];
  title?: string;
  description?: string;
}) {
  return (
    <ChartCard title={title} description={description}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="week" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="risk" stroke={SEVERITY_HEX.medium} strokeWidth={2.5} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

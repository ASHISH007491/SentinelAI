"use client";

import { useState } from "react";
import { Copy, Eye, EyeOff, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ThemePicker } from "@/components/shared/theme-picker";

function NotificationRow({ label, hint, defaultOn = true }: { label: string; hint: string; defaultOn?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div><p className="text-sm font-medium">{label}</p><p className="text-xs text-muted-foreground">{hint}</p></div>
      <Switch defaultChecked={defaultOn} />
    </div>
  );
}

export default function SettingsPage() {
  const [showKey, setShowKey] = useState(false);
  const apiKey = "sk-sentinel-7Q2c••••••••••••••••3f9A";

  return (
    <>
      <PageHeader title="Settings" description="Manage your account, workspace, and integrations." />

      <Tabs defaultValue="profile">
        <TabsList className="flex-wrap">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="api">API &amp; Model</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader><CardTitle>Profile</CardTitle><CardDescription>How you appear across the workspace.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="name">Full name</Label><Input id="name" defaultValue="Security Analyst" /></div>
                <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" defaultValue="analyst@sentinelai.app" /></div>
                <div className="space-y-2"><Label htmlFor="role">Role</Label><Input id="role" defaultValue="SOC Analyst" /></div>
                <div className="space-y-2">
                  <Label>Language</Label>
                  <Select defaultValue="en">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="es">Español</SelectItem>
                      <SelectItem value="de">Deutsch</SelectItem>
                      <SelectItem value="fr">Français</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={() => toast.success("Profile saved")}>Save changes</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance">
          <Card>
            <CardHeader><CardTitle>Appearance</CardTitle><CardDescription>Choose how SentinelAI looks. Dark is default.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <ThemePicker />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api">
          <Card>
            <CardHeader><CardTitle>API &amp; Model</CardTitle><CardDescription>Keys and model selection for agent inference.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label>API key</Label>
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input className="pl-9 font-mono" readOnly value={showKey ? "sk-sentinel-7Q2c8sJd2k1mZ0pX3f9A" : apiKey} />
                  </div>
                  <Button variant="outline" size="icon" onClick={() => setShowKey((s) => !s)} aria-label="Toggle key visibility">
                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => toast.success("API key copied")} aria-label="Copy key"><Copy className="h-4 w-4" /></Button>
                </div>
              </div>
              <Separator />
              <div className="space-y-2">
                <Label>Inference model</Label>
                <Select defaultValue="claude-sonnet-4-6">
                  <SelectTrigger className="sm:w-72"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="claude-opus-4-8">Claude Opus 4.8 (highest quality)</SelectItem>
                    <SelectItem value="claude-sonnet-4-6">Claude Sonnet 4.6 (balanced)</SelectItem>
                    <SelectItem value="claude-haiku-4-5">Claude Haiku 4.5 (fastest)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">Used by all agents and the single-agent baseline.</p>
              </div>
              <Button onClick={() => toast.success("Preferences saved")}>Save</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader><CardTitle>Notifications</CardTitle><CardDescription>Choose what SentinelAI alerts you about.</CardDescription></CardHeader>
            <CardContent className="divide-y divide-border/50">
              <NotificationRow label="Critical findings" hint="Immediate alert on critical-severity detections" />
              <NotificationRow label="Run completion" hint="Notify when an analysis finishes" />
              <NotificationRow label="Weekly digest" hint="Summary of posture and trends" />
              <NotificationRow label="Product updates" hint="New features and releases" defaultOn={false} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader><CardTitle>Security</CardTitle><CardDescription>Protect your account.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border border-border/50 p-4">
                <div><p className="text-sm font-medium">Two-factor authentication</p><p className="text-xs text-muted-foreground">Require a second factor at sign-in</p></div>
                <Switch defaultChecked />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pw">Change password</Label>
                <Input id="pw" type="password" placeholder="New password" />
              </div>
              <Button variant="destructive" onClick={() => toast.success("Password updated")}>Update password</Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import { ArrowRight, Building2, Monitor, Moon, Save, Sparkles, Sun } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { QuickNav } from "@/components/shared/quick-nav";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { useMounted } from "@/hooks/use-mounted";
import { API_BASE_URL } from "@/lib/constants";
import { API_URL_STORAGE_KEY, getApiBaseUrl } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { DataSeeder } from "@/components/settings/data-seeder";
import { useProfileStore } from "@/stores/profile-store";
import { businessSummaryMd } from "@/lib/personalization";

interface NotificationPrefs {
  criticalAlerts: boolean;
  simulationComplete: boolean;
  dailyDigest: boolean;
  reportReady: boolean;
  riskChanges: boolean;
}

interface SystemPrefs {
  compactMode: boolean;
  autoRefresh: boolean;
  liveTelemetry: boolean;
  sounds: boolean;
}

export default function SettingsPage() {
  const { resolvedTheme, setTheme } = useTheme();
  // resolvedTheme is undefined during SSR → use a stable default until mounted
  // so the theme picker matches between server and client HTML.
  const mounted = useMounted();
  const themeValue = mounted ? (resolvedTheme ?? "dark") : "dark";
  const [notifPrefs, setNotifPrefs] = useLocalStorage<NotificationPrefs>("bta-notif-prefs", {
    criticalAlerts: true,
    simulationComplete: true,
    dailyDigest: false,
    reportReady: true,
    riskChanges: true,
  });
  const [systemPrefs, setSystemPrefs] = useLocalStorage<SystemPrefs>("bta-system-prefs", {
    compactMode: false,
    autoRefresh: true,
    liveTelemetry: true,
    sounds: false,
  });
  const { business, personal, setStatus, updateBusiness, updatePersonal } = useProfileStore();
  const [draft, setDraft] = useState(() => ({
    name: personal.name || "Alex Morgan",
    role: personal.role || "Chief Operations Officer",
    email: personal.email || "alex.morgan@acmecorp.com",
    company: business.name || "Acme Corp",
  }));
  // Reflect the effective base URL (build-time constant or the saved override).
  // Start from the build-time constant to avoid a hydration mismatch, then
  // adopt the saved runtime override once mounted (same pattern as the theme picker).
  const [apiUrl, setApiUrl] = useState(API_BASE_URL);
  useEffect(() => {
    if (mounted) setApiUrl(getApiBaseUrl());
  }, [mounted]);

  // Re-sync the draft if the profile changes elsewhere (e.g. AI Assistant setup).
  useEffect(() => {
    setDraft({
      name: personal.name || "Alex Morgan",
      role: personal.role || "Chief Operations Officer",
      email: personal.email || "alex.morgan@acmecorp.com",
      company: business.name || "Acme Corp",
    });
  }, [personal.name, personal.role, personal.email, business.name]);

  const toggleNotif = (key: keyof NotificationPrefs) => setNotifPrefs((p) => ({ ...p, [key]: !p[key] }));
  const toggleSystem = (key: keyof SystemPrefs) => setSystemPrefs((p) => ({ ...p, [key]: !p[key] }));

  const saveProfile = () => {
    updatePersonal({ name: draft.name, role: draft.role, email: draft.email });
    updateBusiness({ name: draft.company });
    setStatus("complete");
    toast.success("Profile saved — the whole workspace now reflects it");
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Profile, appearance, notifications and system preferences" />

      <QuickNav
        items={[
          { id: "profile", label: "Profile", icon: <Save className="h-3 w-3" /> },
          { id: "business-profile", label: "Business", icon: <Building2 className="h-3 w-3" /> },
          { id: "appearance", label: "Appearance", icon: <Monitor className="h-3 w-3" /> },
          { id: "notification-prefs", label: "Notifications", icon: <Sparkles className="h-3 w-3" /> },
          { id: "system", label: "System", icon: <Sun className="h-3 w-3" /> },
          { id: "data", label: "Data & Seeding", icon: <ArrowRight className="h-3 w-3" /> },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Profile — synced with the AI-assistant collected profile */}
        <Card id="profile" className="scroll-mt-28">
          <CardHeader>
            <CardTitle className="text-sm">Profile</CardTitle>
            <CardDescription className="text-xs">Your identity across the platform — collected by the AI assistant</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <Avatar className="h-14 w-14">
                <AvatarFallback className="bg-gradient-to-br from-blue-500 to-violet-600 text-base font-semibold text-white">
                  {draft.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                </AvatarFallback>
              </Avatar>
              <div className="text-xs text-muted-foreground">
                <p className="font-medium text-foreground">{personal.name ? "Collected via AI Assistant" : "Set up via the AI Assistant for the full experience"}</p>
                <p>Changes here update the topbar, chat greeting and reports.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="p-name">Full name</Label>
                <Input id="p-name" value={draft.name} onChange={(e) => setDraft((p) => ({ ...p, name: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-role">Role</Label>
                <Input id="p-role" value={draft.role} onChange={(e) => setDraft((p) => ({ ...p, role: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-email">Email</Label>
              <Input id="p-email" type="email" value={draft.email} onChange={(e) => setDraft((p) => ({ ...p, email: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-company">Company</Label>
              <Input id="p-company" value={draft.company} onChange={(e) => setDraft((p) => ({ ...p, company: e.target.value }))} />
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={saveProfile}><Save /> Save profile</Button>
              <Button size="sm" variant="outline" asChild>
                <Link href="/chat?setup=1"><Sparkles /> Personalise more in AI Assistant</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Business profile — collected conversationally */}
        <Card id="business-profile" className="scroll-mt-28">
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle className="text-sm flex items-center gap-2"><Building2 className="h-4 w-4 text-primary" /> Business profile</CardTitle>
              <CardDescription className="text-xs">What the assistant knows about your company</CardDescription>
            </div>
            <Badge variant={business.name ? "default" : "secondary"} className="text-[10px]">
              {business.name ? "Configured" : "Not set up"}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            {business.name ? (
              <div className="space-y-3">
                <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg border bg-muted/40 p-3 text-xs prose-p:my-0.5 prose-strong:text-foreground">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{businessSummaryMd(business)}</ReactMarkdown>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(business.challenges ?? []).map((c) => (
                    <Badge key={c} variant="secondary" className="text-[10px] capitalize">{c.replace("_", " ")}</Badge>
                  ))}
                  {(business.goals ?? []).map((g) => (
                    <Badge key={g} variant="outline" className="text-[10px] capitalize text-chart-3">{g.replace("_", " ")}</Badge>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  This profile powers your digital twin, dashboards, suggested questions and the executive briefing.
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                No business profile yet. Let the AI assistant ask you a few questions and the whole platform will adapt to your company.
              </div>
            )}
            <Button size="sm" variant={business.name ? "outline" : "default"} asChild className="gap-2">
              <Link href="/chat?setup=1">
                {business.name ? "Edit business profile" : "Set up business profile"} <ArrowRight />
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* Appearance */}
        <Card id="appearance" className="scroll-mt-28">
          <CardHeader>
            <CardTitle className="text-sm">Appearance</CardTitle>
            <CardDescription className="text-xs">Theme preference for the whole platform</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs value={themeValue} onValueChange={(v) => setTheme(v)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="light"><Sun /> Light</TabsTrigger>
                <TabsTrigger value="dark"><Moon /> Dark</TabsTrigger>
                <TabsTrigger value="system"><Monitor /> System</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="grid grid-cols-2 gap-3">
              <ThemePreview label="Light" active={mounted && resolvedTheme === "light"} onClick={() => setTheme("light")} light />
              <ThemePreview label="Dark" active={mounted && resolvedTheme === "dark"} onClick={() => setTheme("dark")} light={false} />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Compact density</p>
                <p className="text-xs text-muted-foreground">Show more content per screen</p>
              </div>
              <Switch checked={systemPrefs.compactMode} onCheckedChange={() => toggleSystem("compactMode")} />
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card id="notification-prefs" className="scroll-mt-28">
          <CardHeader>
            <CardTitle className="text-sm">Notification Preferences</CardTitle>
            <CardDescription className="text-xs">Choose what triggers a notification</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <PrefRow
              title="Critical alerts"
              sub="Inventory, risk and logistics emergencies"
              checked={notifPrefs.criticalAlerts}
              onChange={() => toggleNotif("criticalAlerts")}
            />
            <PrefRow
              title="Simulation complete"
              sub="When a scenario finishes running"
              checked={notifPrefs.simulationComplete}
              onChange={() => toggleNotif("simulationComplete")}
            />
            <PrefRow
              title="Daily digest"
              sub="Morning summary of KPIs and alerts"
              checked={notifPrefs.dailyDigest}
              onChange={() => toggleNotif("dailyDigest")}
            />
            <PrefRow
              title="Report ready"
              sub="When generated reports are available"
              checked={notifPrefs.reportReady}
              onChange={() => toggleNotif("reportReady")}
            />
            <PrefRow
              title="Risk changes"
              sub="When risk scores or severities change"
              checked={notifPrefs.riskChanges}
              onChange={() => toggleNotif("riskChanges")}
            />
          </CardContent>
        </Card>

        {/* API + System */}
        <div id="system" className="scroll-mt-28 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">API Configuration</CardTitle>
              <CardDescription className="text-xs">Backend endpoints consumed by this dashboard</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="api-url">API base URL</Label>
                <Input id="api-url" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} className="font-mono text-xs" />
              </div>
              <Button size="sm" variant="outline" onClick={() => { localStorage.setItem(API_URL_STORAGE_KEY, apiUrl); toast.success("API configuration saved — reloading data"); setTimeout(() => window.location.reload(), 400); }}>
                <Save /> Save API config
              </Button>
              <div className="flex items-center gap-2 rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
                <span className={cn("h-2 w-2 rounded-full", apiUrl.includes("localhost") ? "bg-warning" : "bg-success")} />
                {apiUrl.includes("localhost") ? "Local backend detected — live data will load when the API is running" : "Remote backend configured"}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">System Preferences</CardTitle>
              <CardDescription className="text-xs">Runtime behaviour of the dashboard</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <PrefRow title="Auto-refresh data" sub="Poll backend for changes" checked={systemPrefs.autoRefresh} onChange={() => toggleSystem("autoRefresh")} />
              <PrefRow title="Live telemetry" sub="Simulate real-time node updates" checked={systemPrefs.liveTelemetry} onChange={() => toggleSystem("liveTelemetry")} />
              <PrefRow title="Interface sounds" sub="Audio feedback for actions" checked={systemPrefs.sounds} onChange={() => toggleSystem("sounds")} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Data & Seeding — upload your own profile or restore the demo dataset */}
      <div id="data" className="scroll-mt-28">
        <DataSeeder />
      </div>
    </div>
  );
}

function PrefRow({ title, sub, checked, onChange }: { title: string; sub: string; checked: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{sub}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function ThemePreview({ label, active, onClick, light }: { label: string; active: boolean; onClick: () => void; light: boolean }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "overflow-hidden rounded-lg border text-left transition-all",
        active ? "border-primary ring-2 ring-primary/40" : "border-border hover:border-primary/40"
      )}
      aria-pressed={active}
      aria-label={`${label} theme`}
    >
      <div className={cn("flex h-16 items-center justify-center gap-1", light ? "bg-slate-100" : "bg-slate-900")}>
        <div className={cn("flex h-8 w-1/3 flex-col gap-1 rounded p-1", light ? "bg-white" : "bg-slate-800")}>
          <span className={cn("h-1 w-3/4 rounded-full", light ? "bg-slate-300" : "bg-slate-600")} />
          <span className={cn("h-1 w-1/2 rounded-full", light ? "bg-slate-300" : "bg-slate-600")} />
        </div>
        <div className={cn("h-8 w-1/2 rounded", light ? "bg-white" : "bg-slate-800", "ring-1", light ? "ring-slate-200" : "ring-slate-700")} />
      </div>
      <div className={cn("flex items-center justify-between px-3 py-1.5 text-xs font-medium", light ? "bg-white text-slate-700" : "bg-slate-950 text-slate-200")}>
        {label}
        {active && <span className="text-primary">●</span>}
      </div>
    </button>
  );
}

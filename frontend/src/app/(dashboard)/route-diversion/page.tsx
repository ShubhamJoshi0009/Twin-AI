"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeftRight, Clock, CloudSun, DollarSign, Loader2, Map as MapIcon, Route as RouteIcon, RefreshCw, Ship, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { QuickNav } from "@/components/shared/quick-nav";
import { RiskRadar } from "@/components/route-risk/risk-radar";
import { WorldMap } from "@/components/route-diversion/world-map";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SkeletonGrid } from "@/components/shared/state-views";
import { errorMessage } from "@/lib/api/client";
import * as routes from "@/lib/api/routes";
import { useRouteRiskScenarios, useRouteWeather, useRouteWeatherDetail, useTwins } from "@/hooks/use-api";
import type { RouteNetwork, RoutePathPayload, RouteRiskScenario, RouteSimulation, RouteWeatherDetail, RouteWeatherResponse } from "@/lib/types";
import { weatherLevelColor, WEATHER_LEVEL_STYLES } from "@/components/route-diversion/world-map";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";

const PRESET_BLOCKS: Record<string, string[]> = {
  red_sea_crisis: ["suez_canal", "red_sea", "bab_el_mandeb", "gulf_of_aden"],
  eu_asia_rail_block: ["eu_asia_rail"],
  us_land_bridge_block: ["us_land_bridge"],
  hormuz_conflict: ["strait_of_hormuz"],
  panama_drought: ["panama_canal"],
  malacca_piracy: ["malacca_strait"],
};

const POPULAR_ROUTES = [
  { origin: "shanghai", destination: "rotterdam", label: "Shanghai → Rotterdam" },
  { origin: "shanghai", destination: "los_angeles", label: "Shanghai → Los Angeles" },
  { origin: "singapore", destination: "rotterdam", label: "Singapore → Rotterdam" },
  { origin: "mumbai", destination: "piraeus", label: "Mumbai → Piraeus" },
  { origin: "houston", destination: "rotterdam", label: "Houston → Rotterdam" },
  { origin: "vancouver", destination: "new_york", label: "Vancouver → New York" },
  { origin: "los_angeles", destination: "shanghai", label: "Los Angeles → Shanghai" },
];

export default function RouteDiversionPage() {
  const { data: twins } = useTwins();
  const twin = twins?.[0];

  const [origin, setOrigin] = useState("shanghai");
  const [destination, setDestination] = useState("rotterdam");
  const [eventType, setEventType] = useState("war_conflict");
  const [blocked, setBlocked] = useState<string[]>([]);
  const [selectedCp, setSelectedCp] = useState<string | null>(null);
  const [cargoValue, setCargoValue] = useState(1_000_000);
  const [runId, setRunId] = useState(0);
  const [appliedScenario, setAppliedScenario] = useState<RouteRiskScenario | null>(null);
  const [cpFilter, setCpFilter] = useState<"all" | "maritime" | "land">("all");

  const {
    data: riskRadar,
    isLoading: radarLoading,
    error: radarError,
    refetch: refetchRadar,
  } = useRouteRiskScenarios(5);

  const {
    data: weather,
    refetch: refetchWeather,
    isFetching: weatherFetching,
  } = useRouteWeather(60_000); // auto-refresh every 60s
  const {
    data: routeWeather,
    refetch: refetchRouteWeather,
    isFetching: routeWeatherFetching,
  } = useRouteWeatherDetail(runId > 0 ? origin : null, runId > 0 ? destination : null, 60_000);

  const { data: network, isLoading: networkLoading } = useQuery({
    queryKey: ["route-network"],
    queryFn: routes.getRouteNetwork,
    retry: 1,
  });

  const { data: result, isLoading: running, error, refetch } = useQuery<RouteSimulation | null>({
    queryKey: ["route-simulate", runId, origin, destination, JSON.stringify(blocked), eventType, cargoValue],
    queryFn: async () => {
      if (runId === 0) return null;
      try {
        return await routes.simulateRoute({
          origin,
          destination,
          blocked_chokepoints: blocked,
          event_type: eventType,
          cargo_value: cargoValue,
          include_news: true,
        });
      } catch (err) {
        const axiosErr = err as { response?: { status?: number } };
        if (!axiosErr.response || axiosErr.response.status === 422) throw err;
        return null;
      }
    },
    retry: 1,
    enabled: runId > 0,
  });

  // Memoize the derived collections so downstream useMemo deps stay stable.
  const ports = useMemo(() => network?.ports ?? [], [network]);
  const chokepoints = useMemo(() => network?.chokepoints ?? [], [network]);
  const segments = useMemo(() => network?.segments ?? [], [network]);

  const toggleBlock = (id: string) =>
    setBlocked((prev) => (prev.includes(id) ? prev.filter((b) => b !== id) : [...prev, id]));

  const applyScenario = (s: RouteRiskScenario) => {
    setAppliedScenario(s);
    setBlocked([s.chokepoint_id]);
    setEventType(s.event_type);
    setSelectedCp(s.chokepoint_id);
    // Prefer the lane this chokepoint actually sits on so the diversion is
    // visible, not a "route clear" because the current voyage avoids it.
    if (s.suggest_origin && s.suggest_destination) {
      setOrigin(s.suggest_origin);
      setDestination(s.suggest_destination);
    }
    setRunId((k) => k + 1);
    toast.success(`${s.chokepoint_name} blocked — ${s.event_label} scenario applied`);
  };

  const applyPreset = (preset: string) => {
    if (preset === "clear") {
      setBlocked([]);
      setSelectedCp(null);
      return;
    }
    setBlocked(PRESET_BLOCKS[preset] ?? []);
    setSelectedCp(PRESET_BLOCKS[preset]?.[0] ?? null);
    if (preset === "red_sea_crisis") setEventType("war_conflict");
    if (preset === "eu_asia_rail_block") setEventType("war_conflict");
    if (preset === "us_land_bridge_block") setEventType("congestion");
    if (preset === "hormuz_conflict") setEventType("war_conflict");
    if (preset === "panama_drought") setEventType("natural_disaster");
    if (preset === "malacca_piracy") setEventType("piracy");
  };

  const portOptions = useMemo(
    () => [...ports].sort((a, b) => a.name.localeCompare(b.name)),
    [ports]
  );

  const swapRoute = () => {
    setOrigin(destination);
    setDestination(origin);
  };

  const applyPopularRoute = (o: string, d: string) => {
    setOrigin(o);
    setDestination(d);
    if (runId === 0) setRunId(1); // kick off the first simulation right away
  };

  const landCount = chokepoints.filter((c) => c.kind === "land").length;
  const waterCount = chokepoints.length - landCount;
  const visibleChokepoints = cpFilter === "all" ? chokepoints : chokepoints.filter((c) => (c.kind ?? "maritime") === cpFilter);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Route Diversion Simulator"
        description="Block a chokepoint — war, piracy, drought or sanctions — and watch the world re-route your cargo"
        actions={
          <Button variant="outline" size="sm" onClick={() => { setRunId(0); setBlocked([]); }}>
            Reset
          </Button>
        }
      />

      <QuickNav
        items={[
          { id: "voyage", label: "Voyage", icon: <RouteIcon className="h-3 w-3" /> },
          { id: "map", label: "World Map", icon: <MapIcon className="h-3 w-3" /> },
          { id: "risk-radar", label: "Risk Radar", icon: <AlertTriangle className="h-3 w-3" /> },
          { id: "disruptions", label: "Disruptions", icon: <AlertTriangle className="h-3 w-3" /> },
          { id: "results", label: "Results", icon: <TrendingUp className="h-3 w-3" /> },
        ]}
      />

      {/* Voyage configuration — kept at the very top so the route is always one glance away */}
      <Card id="voyage" className="scroll-mt-28 border-border/60">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <RouteIcon className="h-4 w-4 text-primary" /> Voyage
          </CardTitle>
          <CardDescription className="text-xs">Set your route — simulating re-routes your cargo instantly</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr_auto]">
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">Origin port</p>
              <Select value={origin} onValueChange={setOrigin}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {portOptions.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-center pb-1">
              <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full border" onClick={swapRoute} title="Swap origin & destination" aria-label="Swap origin and destination">
                <ArrowLeftRight className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">Destination port</p>
              <Select value={destination} onValueChange={setDestination}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {portOptions.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">Cargo value (USD)</p>
                <input
                  type="number"
                  value={cargoValue}
                  onChange={(e) => setCargoValue(Math.max(0, Number(e.target.value)))}
                  className="flex h-9 w-28 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <Button size="sm" onClick={() => setRunId((k) => k + 1)} disabled={runId > 0 && running} className="h-9 gap-2">
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RouteIcon className="h-4 w-4" />}
                {runId > 0 ? "Re-simulate" : "Simulate"}
              </Button>
            </div>
          </div>
          {/* Popular routes — one click to set origin + destination */}
          <div className="flex flex-wrap items-center gap-1.5 border-t border-border/50 pt-3">
            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Popular routes</span>
            {POPULAR_ROUTES.map((r) => {
              const active = origin === r.origin && destination === r.destination;
              return (
                <button
                  key={r.label}
                  onClick={() => applyPopularRoute(r.origin, r.destination)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all",
                    active
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-border bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground"
                  )}
                >
                  {r.label}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        {/* Map */}
        <div className="scroll-mt-28 space-y-4" id="map">
          {networkLoading && !network ? (
            <SkeletonGrid count={2} className="!grid-cols-1" />
          ) : (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <WorldMap
                ports={ports}
                segments={segments}
                chokepoints={chokepoints}
                blocked={blocked}
                baseline={result?.baseline ?? null}
                diverted={result?.diverted ?? null}
                originId={origin}
                destinationId={destination}
                selectedChokepoint={selectedCp}
                onSelectChokepoint={setSelectedCp}
                weather={weather}
              />

              {/* Legend */}
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-sky-400" /> Baseline route</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-green-400" /> Diverted route</span>
                <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-amber-400" /> Water blockade (click to block)</span>
                <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-violet-500" /> Land blockade (click to block)</span>
                <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-red-400" /> Blocked</span>
                <span className="flex items-center gap-1.5"><CloudSun className="h-3 w-3 text-sky-400" /> Port ring = weather risk (GREEN→RED)</span>
              </div>
            </motion.div>
          )}

          {/* Selected chokepoint info */}
          {selectedCp && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              {(() => {
                const cp = chokepoints.find((c) => c.id === selectedCp);
                if (!cp) return null;
                const isBlocked = blocked.includes(cp.id);
                return (
                  <Card className={cn("border", isBlocked ? "border-red-500/40" : "border-amber-500/40")}>
                    <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-sm">
                          <MapIcon className="h-4 w-4 text-amber-500" /> {cp.name}
                        </CardTitle>
                        <CardDescription className="text-xs">{cp.region}</CardDescription>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="secondary" className="!text-[9px]">
                          {cp.kind === "land" ? "🚆 Land" : "🌊 Water"}
                        </Badge>
                        <Badge variant={isBlocked ? "destructive" : "warning"}>{isBlocked ? "Blocked" : cp.severity}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <p className="text-xs text-muted-foreground">{cp.description}</p>
                      {cp.solution && (
                        <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2">
                          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-success">
                            <TrendingUp className="h-3.5 w-3.5" /> Optimal solution
                          </p>
                          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{cp.solution}</p>
                        </div>
                      )}
                      <Button size="sm" variant={isBlocked ? "outline" : "destructive"} onClick={() => toggleBlock(cp.id)}>
                        {isBlocked ? "Clear this chokepoint" : "Block this chokepoint"}
                      </Button>
                    </CardContent>
                  </Card>
                );
              })()}
            </motion.div>
          )}
        </div>

        {/* Controls + results */}
        <div className="space-y-4">
          {/* Live Weather Monitor — real-time conditions along the route */}
          <div id="live-weather" className="scroll-mt-28">
            <LiveWeatherPanel
              weather={weather}
              routeWeather={routeWeather}
              fetching={weatherFetching || routeWeatherFetching}
              onRefresh={() => { refetchWeather(); refetchRouteWeather(); }}
              hasRoute={runId > 0}
            />
          </div>

          {/* Live Risk Radar — news-driven scenarios */}
          <div id="risk-radar" className="scroll-mt-28">
            <RiskRadar
              scenarios={riskRadar?.scenarios ?? []}
              mode={riskRadar?.mode}
              loading={radarLoading}
              error={radarError ? radarError.userMessage ?? radarError.message : null}
              onApply={applyScenario}
              onRetry={() => refetchRadar()}
            />
          </div>

          {appliedScenario && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-600 dark:text-amber-400">
              Applied: <span className="font-semibold">{appliedScenario.chokepoint_name}</span> · {appliedScenario.event_label} · risk {appliedScenario.risk_score}/100
            </div>
          )}

          <Card id="disruptions" className="scroll-mt-28">
            <CardHeader>
              <CardTitle className="text-sm">Disruption Scenarios</CardTitle>
              <CardDescription className="text-xs">Pre-built real-world situations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex flex-wrap gap-1.5">
                {[
                  { id: "clear", label: "✓ All clear" },
                  { id: "red_sea_crisis", label: "⚔️ Red Sea crisis" },
                  { id: "eu_asia_rail_block", label: "🚆 Eurasian rail blockade" },
                  { id: "us_land_bridge_block", label: "🛤️ US rail bridge blocked" },
                  { id: "hormuz_conflict", label: "🚫 Hormuz conflict" },
                  { id: "panama_drought", label: "🌪️ Panama drought" },
                  { id: "malacca_piracy", label: "🏴☠️ Malacca piracy" },
                ].map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => applyPreset(preset.id)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all",
                      preset.id === "clear" && blocked.length === 0
                        ? "border-primary/50 bg-primary/15 text-primary"
                        : preset.id !== "clear" && blocked.length > 0 && PRESET_BLOCKS[preset.id]?.every((b) => blocked.includes(b))
                          ? "border-red-500/50 bg-red-500/15 text-red-500"
                          : "border-border bg-card hover:border-foreground/40"
                    )}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <div className="pt-1">
                <div className="mb-1.5 flex items-center justify-between">
                  <p className="text-[11px] font-medium text-muted-foreground">Toggle chokepoints on the map / below</p>
                  <div className="flex overflow-hidden rounded-md border">
                    {([
                      { id: "all", label: "All" },
                      { id: "water", label: `🌊 Water ${waterCount}` },
                      { id: "land", label: `🚆 Land ${landCount}` },
                    ] as const).map((f) => (
                      <button
                        key={f.id}
                        onClick={() => setCpFilter(f.id === "water" ? "maritime" : f.id === "land" ? "land" : "all")}
                        className={cn(
                          "px-2 py-1 text-[10px] font-medium transition-colors",
                          (f.id === "water" && cpFilter === "maritime") || (f.id === "land" && cpFilter === "land") || (f.id === "all" && cpFilter === "all")
                            ? "bg-primary/15 text-primary"
                            : "bg-card text-muted-foreground hover:bg-accent"
                        )}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-1.5">
                  {visibleChokepoints.map((cp) => {
                    const isBlocked = blocked.includes(cp.id);
                    const isLand = cp.kind === "land";
                    return (
                      <button
                        key={cp.id}
                        onClick={() => { toggleBlock(cp.id); setSelectedCp(cp.id); }}
                        className={cn(
                          "flex items-center justify-between rounded-md border px-2.5 py-1.5 text-left text-[11px] transition-all",
                          isBlocked ? "border-red-500/50 bg-red-500/10 text-red-400" : "border-border bg-card hover:border-amber-500/40"
                        )}
                      >
                        <span className="flex items-center gap-1.5">
                          <span className={cn("h-1.5 w-1.5 rounded-full", isBlocked ? "bg-red-400" : isLand ? "bg-violet-500" : "bg-amber-400")} />
                          {cp.name}
                        </span>
                        <span className="flex items-center gap-1">
                          <Badge variant="secondary" className="!text-[8px]">{isLand ? "land" : "water"}</Badge>
                          <Badge variant={isBlocked ? "destructive" : "secondary"} className="!text-[9px]">{isBlocked ? "blocked" : cp.severity}</Badge>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {runId > 0 && (
            <motion.div id="results" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="scroll-mt-28 space-y-4">
              {error ? (
                <Card className="p-5 text-center">
                  <p className="text-sm font-semibold text-destructive">Simulation failed</p>
                  <p className="mt-1 text-xs text-muted-foreground">{errorMessage(error)}</p>
                  <Button className="mt-3" size="sm" variant="outline" onClick={() => refetch()}>Retry</Button>
                </Card>
              ) : running || !result ? (
                <div className="space-y-3">
                  <SkeletonGrid count={1} />
                  <Card className="p-5"><div className="h-24 animate-pulse rounded-md bg-muted" /></Card>
                </div>
              ) : (
                <>
                  <ResultSummary result={result} />
                  {result.blocked_chokepoints.length > 0 && <BlockedSolutions blocked={result.blocked_chokepoints} />}
                  <RouteCard label="Baseline route" payload={result.baseline} accent="sky" />
                  {result.diverted && result.status !== "clear" && (
                    <RouteCard label="Diverted route" payload={result.diverted} accent="green" deltaDays={result.impact.extra_days} deltaKm={result.impact.extra_km} deltaCost={result.impact.extra_cost} />
                  )}
                  {result.news && result.news.length > 0 && (
                    <Card className="border-chart-1/30 bg-chart-1/5">
                      <CardHeader className="pb-2">
                        <CardTitle className="flex items-center gap-2 text-sm">
                          <AlertTriangle className="h-4 w-4 text-chart-1" /> Live news on the disruption
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {result.news.slice(0, 3).map((n, i) => (
                          <a key={i} href={n.url} target="_blank" rel="noreferrer" className="block rounded-md border border-border/50 bg-card/70 p-2.5 transition-colors hover:border-chart-1/40">
                            <p className="line-clamp-2 text-xs font-medium">{n.title}</p>
                            <p className="mt-0.5 text-[10px] text-muted-foreground">{n.source}</p>
                          </a>
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}

function LiveWeatherPanel({
  weather,
  routeWeather,
  fetching,
  onRefresh,
  hasRoute,
}: {
  weather?: RouteWeatherResponse | null;
  routeWeather?: RouteWeatherDetail | null;
  fetching: boolean;
  onRefresh: () => void;
  hasRoute: boolean;
}) {
  const worst = weather?.summary.worst_level ?? "GREEN";
  const levelMeta = WEATHER_LEVEL_STYLES[worst] ?? WEATHER_LEVEL_STYLES.GREEN;
  const alerts = weather?.alerts ?? [];

  const overall = routeWeather?.overall_level ?? null;
  const overallMeta = overall ? (WEATHER_LEVEL_STYLES[overall] ?? WEATHER_LEVEL_STYLES.GREEN) : null;

  return (
    <Card id="weather" className={cn("scroll-mt-28 border", weather && worst !== "GREEN" ? "" : "border-border/60")}>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <CloudSun className="h-4 w-4" style={{ color: weatherLevelColor(worst) }} />
          Live Weather Monitor
        </CardTitle>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="!text-[9px]">
            {weather?.mode === "live" ? "Live · Open-Meteo" : "Simulated · offline"}
          </Badge>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onRefresh} title="Refresh weather" aria-label="Refresh weather">
            <RefreshCw className={cn("h-3.5 w-3.5", fetching && "animate-spin")} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!weather || weather.ports.length === 0 ? (
          <p className="text-xs text-muted-foreground">Weather data unavailable — start the backend to enable live monitoring.</p>
        ) : (
          <>
            {/* Route-level summary */}
            {hasRoute && routeWeather && overallMeta && (
              <div
                className="rounded-lg border px-3 py-2"
                style={{ borderColor: `${overallMeta.color}55`, backgroundColor: `${overallMeta.color}14` }}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold" style={{ color: overallMeta.color }}>
                    Route weather · {routeWeather.overall_level} · {routeWeather.overall_risk_score}/100
                  </p>
                  <span className="text-[10px] text-muted-foreground">
                    {routeWeather.points.length} ports monitored
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{routeWeather.recommendation}</p>
              </div>
            )}

            {/* Alerts */}
            {alerts.length > 0 ? (
              <div className="space-y-1.5">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Hazard alerts ({alerts.length})
                </p>
                {alerts.slice(0, 4).map((a) => (
                  <div
                    key={a.location}
                    className="flex items-start justify-between gap-2 rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5"
                  >
                    <p className="text-[11px]">
                      <span className="font-semibold">{a.location}</span>
                      <span className="text-muted-foreground"> — {a.summary}</span>
                    </p>
                    <Badge variant={a.level === "RED" ? "destructive" : "warning"} className="!text-[9px]">{a.level}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-success">No hazardous weather at any monitored port.</p>
            )}

            {/* Port chips */}
            <div className="flex flex-wrap gap-1.5">
              {weather.ports.slice(0, 12).map((pw) => {
                const style = WEATHER_LEVEL_STYLES[pw.risk_level] ?? WEATHER_LEVEL_STYLES.GREEN;
                return (
                  <span
                    key={pw.port_id}
                    className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]"
                    style={{ borderColor: `${style.color}55`, backgroundColor: `${style.color}10` }}
                    title={`${pw.summary}`}
                  >
                    <span>{pw.conditions.weather_icon}</span>
                    <span className="font-medium text-foreground">{pw.name}</span>
                    <span className="text-muted-foreground">{pw.conditions.temperature_c.toFixed(0)}°C</span>
                    <span className="text-[9px] font-semibold" style={{ color: style.color }}>{pw.risk_level}</span>
                  </span>
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function BlockedSolutions({ blocked }: { blocked: RouteSimulation["blocked_chokepoints"] }) {
  return (
    <Card className="border-amber-500/30 bg-amber-500/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-500" /> Blocked {blocked.length === 1 ? "blockade" : "blockades"} — optimal solutions
        </CardTitle>
        <CardDescription className="text-xs">Land &amp; water blockades applied to this voyage, with the recommended alternative for each</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {blocked.map((cp) => (
          <div key={cp.id} className="rounded-lg border border-border/60 bg-card/70 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold">{cp.name}</p>
              <Badge variant="secondary" className="!text-[9px]">{cp.kind === "land" ? "🚆 Land" : "🌊 Water"}</Badge>
              <Badge variant={cp.severity === "critical" ? "destructive" : "warning"} className="!text-[9px] capitalize">{cp.severity}</Badge>
              <span className="text-[10px] text-muted-foreground">{cp.region}</span>
            </div>
            {cp.solution && (
              <p className="mt-1.5 flex items-start gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
                <TrendingUp className="mt-0.5 h-3 w-3 shrink-0 text-success" /> {cp.solution}
              </p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ResultSummary({ result }: { result: RouteSimulation }) {
  const statusMeta =
    result.status === "clear"
      ? { label: "Route clear", tone: "success" as const, icon: Ship }
      : result.status === "diverted"
        ? { label: "Diverted", tone: "warning" as const, icon: RouteIcon }
        : { label: "No alternative", tone: "destructive" as const, icon: AlertTriangle };
  const Icon = statusMeta.icon;

  return (
    <Card className={cn("border", result.status === "clear" ? "border-success/40" : "border-warning/40")}>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Icon className="h-4 w-4" /> {statusMeta.label}
        </CardTitle>
        <Badge variant={statusMeta.tone}>{result.event.label}</Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <p className="text-muted-foreground">{result.recommendation}</p>
        {result.status !== "clear" && (
          <div className="grid grid-cols-3 gap-2 pt-1">
            <ImpactTile icon={RouteIcon} label="Extra distance" value={`${formatNumber(result.impact.extra_km)} km`} />
            <ImpactTile icon={Clock} label="Extra days" value={`+${result.impact.extra_days}d`} />
            <ImpactTile icon={DollarSign} label="Extra cost" value={formatCurrency(result.impact.extra_cost, { compact: true })} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ImpactTile({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/70 p-2.5 text-center">
      <Icon className="mx-auto h-3.5 w-3.5 text-muted-foreground" />
      <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-bold tabular-nums">{value}</p>
    </div>
  );
}

function RouteCard({
  label,
  payload,
  accent,
  deltaDays,
  deltaKm,
  deltaCost,
}: {
  label: string;
  payload: RoutePathPayload;
  accent: "sky" | "green";
  deltaDays?: number;
  deltaKm?: number;
  deltaCost?: number;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <TrendingUp className={cn("h-4 w-4", accent === "sky" ? "text-sky-400" : "text-green-400")} /> {label}
        </CardTitle>
        <Badge variant="secondary">{payload.port_ids.length} ports</Badge>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md bg-muted/60 p-2 text-center">
            <p className="text-[10px] text-muted-foreground">Distance</p>
            <p className="text-sm font-bold tabular-nums">{formatNumber(payload.total_km)} km</p>
          </div>
          <div className="rounded-md bg-muted/60 p-2 text-center">
            <p className="text-[10px] text-muted-foreground">Voyage</p>
            <p className="text-sm font-bold tabular-nums">{payload.days}d</p>
          </div>
          <div className="rounded-md bg-muted/60 p-2 text-center">
            <p className="text-[10px] text-muted-foreground">Risk</p>
            <p className={cn("text-sm font-bold tabular-nums", payload.risk > 60 ? "text-destructive" : payload.risk > 35 ? "text-warning" : "text-success")}>{payload.risk}/100</p>
          </div>
        </div>
        {deltaDays !== undefined && (
          <p className="rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-[11px] text-warning">
            +{formatNumber(deltaKm ?? 0)} km · +{deltaDays}d · {formatCurrency(deltaCost ?? 0, { compact: true })} versus baseline
          </p>
        )}
        <div className="flex flex-wrap gap-1 pt-0.5">
          {payload.port_ids.map((id: string, i: number) => (
            <span key={id} className="flex items-center gap-1 text-[10px] text-muted-foreground">
              {i > 0 && <span className="text-primary/40">→</span>}
              {id}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
